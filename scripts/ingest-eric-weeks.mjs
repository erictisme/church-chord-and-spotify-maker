#!/usr/bin/env node
// Parses .docx files in eric-all-weeks/, extracts individual songs (title + key + chord block),
// writes them to eric-songs/all-songs/ as canonical eric-archive entries, and updates the catalog.

import { promises as fs } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import mammoth from 'mammoth';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const WEEKS_DIR = path.join(ROOT, 'eric-all-weeks');
const SONGS_DIR = path.join(ROOT, 'eric-songs', 'all-songs');
const CATALOG_PATH = path.join(ROOT, 'eric-songs', 'indices', 'tsv-catalog.json');

const KEY_RE = /^[A-G](?:#|b)?(?:m|maj|sus)?$/;

function slugify(s) {
  return s
    .toLowerCase()
    .replace(/['']/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function looksLikeChordLine(line) {
  const t = line.trim();
  if (!t) return false;
  if (/^\[.+\]$/.test(t)) return true; // [Verse 1]
  if (/^(verse|chorus|bridge|intro|outro|tag|pre[- ]?chorus|interlude|ending|coda)\b/i.test(t)) return true;
  // Tokenize, see if all tokens look like chords
  const tokens = t.split(/\s+/);
  if (tokens.length === 0) return false;
  let chordTokens = 0;
  for (const tok of tokens) {
    if (/^[A-G](?:#|b)?(?:m|maj|min|sus|add|dim|aug)?[0-9]?(?:sus[24]?|add[0-9]+)?(?:\/[A-G](?:#|b)?)?$/.test(tok)) {
      chordTokens += 1;
    }
  }
  return chordTokens === tokens.length && chordTokens > 0;
}

// Detect a song header line: "Title (KEY)" possibly with extra spaces; also "Title - KEY".
function titleHasRealWord(title) {
  // A "real word" is an alphabetic token of 3+ letters that doesn't look like a chord.
  const tokens = title.split(/[\s\-/]+/).filter(Boolean);
  for (const tok of tokens) {
    if (!/^[A-Za-z]+$/.test(tok)) continue;
    if (tok.length < 3) continue;
    if (/^[A-G](?:#|b)?(?:m|maj|min|sus|add|dim|aug)?$/.test(tok)) continue;
    return true;
  }
  return false;
}

function parseSongHeader(line) {
  const t = line.trim();
  if (!t) return null;
  // Skip obvious service-plan lines
  if (/^(welcome|offering|sermon|prayer|announcements|lord'?s supper|mutual upbuilding|declaration|bible reading|kids?'? song|closing song|opening song|song\s*\d+\s*[–-])/i.test(t)) {
    return null;
  }
  let m = t.match(/^(.+?)\s*\(\s*([A-G](?:#|b)?(?:m|maj)?)\s*\)\s*$/);
  if (m && titleHasRealWord(m[1])) return { title: m[1].trim(), key: m[2] };
  // "Title - KEY" or "Title – KEY"
  m = t.match(/^(.+?)\s*[–-]\s*([A-G](?:#|b)?(?:m|maj)?)\s*$/);
  if (m && m[1].length > 2 && !/song\s*\d/i.test(m[1]) && titleHasRealWord(m[1])) {
    return { title: m[1].trim(), key: m[2] };
  }
  return null;
}

function looksLikeSetlistEntry(line) {
  return /^song\s*\d+\s*[–-]/i.test(line.trim()) ||
         /^closing song\b/i.test(line.trim()) ||
         /^opening song\b/i.test(line.trim()) ||
         /^kids?'? song\b/i.test(line.trim());
}

function extractSongs(rawText) {
  const lines = rawText.split(/\r?\n/);
  // Find header indices (skip those that appear in the setlist preamble, where lines around are setlist entries)
  const headers = [];
  for (let i = 0; i < lines.length; i++) {
    const h = parseSongHeader(lines[i]);
    if (!h) continue;
    // Look ahead a few non-blank lines: does a chord-like line appear within 8 lines?
    let chordSeen = false;
    for (let j = i + 1; j < Math.min(lines.length, i + 10); j++) {
      if (lines[j].trim() === '') continue;
      if (looksLikeChordLine(lines[j])) { chordSeen = true; break; }
      // If we hit another header quickly, stop
      if (parseSongHeader(lines[j])) break;
    }
    if (chordSeen) headers.push({ idx: i, ...h });
  }

  const songs = [];
  for (let k = 0; k < headers.length; k++) {
    const start = headers[k].idx + 1;
    const end = k + 1 < headers.length ? headers[k + 1].idx : lines.length;
    const body = lines.slice(start, end).join('\n').trim();
    if (body.length < 40) continue; // skip trivial blocks
    songs.push({ title: headers[k].title, key: headers[k].key, body });
  }
  return songs;
}

function buildMarkdown({ title, key, body, sourceFile, mtime }) {
  const fm = [
    '---',
    `title: ${title}`,
    'artist: unknown',
    `key: ${key}`,
    'source: eric-archive',
    `source_file: ${sourceFile}`,
    `first_seen: ${mtime.toISOString().slice(0, 10)}`,
    '---',
    '',
    `# ${title}`,
    '',
    body,
    '',
  ];
  return fm.join('\n');
}

async function fileExists(p) {
  try { await fs.access(p); return true; } catch { return false; }
}

async function main() {
  const allSongs = await fs.readdir(SONGS_DIR);
  const existingSlugs = new Set(allSongs.map(f => f.replace(/\.md$/, '').toLowerCase()));
  const catalog = JSON.parse(await fs.readFile(CATALOG_PATH, 'utf8'));
  const existingTitles = new Set(Object.keys(catalog).map(k => k.toLowerCase()));

  const docxFiles = (await fs.readdir(WEEKS_DIR)).filter(f => /\.docx$/i.test(f));
  let processed = 0, extracted = 0, written = 0, skippedDup = 0, parseFailed = 0;

  for (const fname of docxFiles) {
    const full = path.join(WEEKS_DIR, fname);
    let raw;
    try {
      const r = await mammoth.extractRawText({ path: full });
      raw = r.value;
    } catch (err) {
      parseFailed += 1;
      console.warn(`! parse failed: ${fname} — ${err.message}`);
      continue;
    }
    processed += 1;
    const stat = await fs.stat(full);
    const songs = extractSongs(raw);
    extracted += songs.length;

    for (const s of songs) {
      const titleSlug = slugify(s.title);
      if (!titleSlug) continue;
      const baseName = `${titleSlug}-${s.key}`;
      const targetMain = `${baseName}.md`;
      const titleKey = s.title.toLowerCase();

      // If main exists, write sibling eric-archive copy
      const mainExists = existingSlugs.has(baseName.toLowerCase()) ||
                         existingTitles.has(titleKey);
      const dateTag = stat.mtime.toISOString().slice(0, 10);
      const filename = mainExists
        ? `${titleSlug}-${s.key}-eric-${dateTag}.md`
        : targetMain;
      const outPath = path.join(SONGS_DIR, filename);
      if (await fileExists(outPath)) { skippedDup += 1; continue; }

      const md = buildMarkdown({
        title: s.title,
        key: s.key,
        body: s.body,
        sourceFile: fname,
        mtime: stat.mtime,
      });
      await fs.writeFile(outPath, md);
      existingSlugs.add(filename.replace(/\.md$/, '').toLowerCase());
      written += 1;

      // Catalog entry — only add if title doesn't already exist (preserve curated metadata)
      if (!existingTitles.has(titleKey)) {
        catalog[titleKey] = {
          title: s.title,
          artist: '',
          era: 'Contemporary',
          pace: 'Medium',
          themes: [],
          acoustic: true,
          count: '0',
          filename,
          key: s.key,
          source: 'eric-archive',
        };
        existingTitles.add(titleKey);
      }
    }
  }

  await fs.writeFile(CATALOG_PATH, JSON.stringify(catalog, null, 2) + '\n');
  console.log(`processed=${processed} extracted=${extracted} written=${written} skipped_duplicates=${skippedDup} parse_failed=${parseFailed}`);
}

main().catch(err => { console.error(err); process.exit(1); });
