# FMH Worship Generator — Build-Out PRD (v1)

## Intent

Close the gap between Eric's actual weekly worship-prep flow (documented in `FLOW.md`) and what the app does today. The app already handles chord sheets, transposition, Ultimate Guitar import, Gemini song suggestions, and Spotify playlist creation — yet Eric still does the prep manually because of friction at the start (no WhatsApp ingest), middle (library doesn't cover his Drive archive), and end (no Google Doc auto-create, no team-message generator).

P0 must ship: Google Doc auto-creation. That alone collapses the biggest 5-step manual sequence (new Doc → paste → format → share → copy link) to one click. Everything else is bonus.

## References

- `FLOW.md` — observed actual flow with friction-point analysis. **READ FIRST.**
- `CLAUDE.md` — repo conventions, single-file architecture
- `INTENT.md` — project purpose
- `index.html` lines 3036-3160 — existing Spotify PKCE OAuth + playlist creation. **Use this as the pattern for the new Doc integration UX, but the implementation will use Apps Script (see Task 1) not Google OAuth — different mechanism, same UX shape (one-time setup → recurring one-click).**

## Architecture decisions (locked — do not relitigate)

1. **Google Doc creation uses Google Apps Script web app**, not direct Drive API OAuth.
   - **Why:** Direct Drive API requires Eric to set up a GCP project, OAuth consent screen, redirect URIs, verification — hours of manual config for a non-technical solo user. Apps Script: paste code → click Deploy → get URL. 5 min total.
   - **How it works:** Apps Script runs under Eric's Google account with permission to create Docs in his Drive. Frontend POSTs JSON `{title, content}` to the Apps Script web app URL. Apps Script creates the Doc, sets sharing to "anyone with link can view", returns `{url, id}`.
   - **Auth:** the Apps Script URL itself is the secret. Eric pastes it once into the app's settings panel (localStorage). No additional OAuth in the browser.
2. **Single-file architecture stays.** All new frontend code goes into `index.html`. New backend file: `apps-script/CreateDoc.gs` (single file, Eric copy-pastes into Apps Script editor).
3. **No build step.** Pure HTML+JS. Test by opening `index.html` directly or via `python3 -m http.server 8000`.

## Scope guardrails

- **NO** rewriting the existing 2500-line `index.html`. Add features incrementally.
- **NO** changing the existing Spotify integration (it works). Mirror its UX patterns; don't refactor it.
- **NO** introducing build tooling, npm/pnpm, TypeScript, or frameworks. Static HTML only.
- **NO** breaking the existing chord-sheet preview, transposition, UG import, or Gemini suggestion features.
- **Verification per task:** since there's no test suite, each task verifies via (a) `node --check` on any extracted standalone JS, (b) `python3 -m http.server 8000 &` then visiting `http://localhost:8000` and confirming new feature renders without console errors, (c) explicit smoke-test steps in the task description. Kill the server after each verification with `pkill -f "http.server 8000"`.
- **Commit cadence:** one commit per task with conventional message `feat:`, `fix:`, or `chore:`. No squashing.
- **Deploy:** repo deploys via Vercel + GitHub Pages on push to main. Ralph runs with `--deploy`.

---

## Task 1 — Apps Script backend for Doc creation

**Category:** feature
**Priority:** 0
**Files:** `apps-script/CreateDoc.gs` (new), `apps-script/DEPLOY.md` (new)

Write a Google Apps Script web app that creates a formatted Google Doc and returns its URL.

**What "done" looks like:**
- `apps-script/CreateDoc.gs` contains a `doPost(e)` function that:
  - Parses JSON body: `{title: string, content: string, columns?: 1|2}`
  - Creates a new Google Doc named `title` (e.g. "26 Apr 2026")
  - Inserts `content` as the body. If `columns === 2`, applies 2-column layout to the body section.
  - Sets the Doc's chord-line font to **Courier New** (so chord-over-lyric alignment survives — the agent earlier today flagged this as the #1 visual gotcha when converting markdown chord blocks to Docs)
  - Sets sharing: `setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW)`
  - Returns JSON: `{url: string, id: string}`
  - Handles errors with try/catch, returns `{error: string}` with appropriate status
- `apps-script/DEPLOY.md` walks Eric step-by-step (with screenshots-of-clicks-described-in-words since he's non-technical):
  1. Go to script.google.com → New project
  2. Paste contents of `CreateDoc.gs`
  3. Click Deploy → New deployment → Type: Web app → Execute as: Me → Who has access: Anyone (Apps Script's "Anyone" still requires the URL, which is the secret) → Deploy
  4. Authorize the script (he'll see a "Google hasn't verified this app" warning — explain it's safe because he wrote it, click "Advanced → Go to [project] (unsafe)")
  5. Copy the web app URL
  6. Paste into the app's Settings panel (built in Task 3)

**What NOT to touch:**
- Don't modify `index.html` in this task — that's Tasks 2 and 3
- Don't add other Apps Script functions beyond `doPost` and any helpers it needs

**How to verify:**
- `node --check apps-script/CreateDoc.gs` will fail (it's not Node) — instead, visually verify the file is syntactically valid JS by running `node -e "new Function(require('fs').readFileSync('apps-script/CreateDoc.gs', 'utf8'))"` to confirm it parses
- Confirm `DEPLOY.md` has all 6 steps and ends with a "test it" curl command Eric can run from terminal to verify the deployment works before integrating with the frontend

- [x] Task 1 done

---

## Task 2 — "Create Google Doc" button + handler in frontend

**Category:** feature
**Priority:** 0
**Files:** `index.html`

Add a Google Doc creation button next to the existing Spotify button, with the same UX shape (click → creates → shows URL → auto-copy to clipboard).

**What "done" looks like:**
- New button appears in the same control row as `#spotifyBtn` (around line 1195), labeled "📄 Create Google Doc", id `gdocBtn`, styled to match (use existing button styles, color: Google Docs blue `#4285F4`)
- Click handler `handleGoogleDocCreate()`:
  1. Reads Apps Script URL from `localStorage.getItem('apps_script_doc_url')`. If empty, shows the same modal pattern used for empty Gemini API key: "Set up your Google Doc integration first" → opens Settings panel (Task 3)
  2. Collects current chord sheet preview content + service date + theme/passage from the existing form fields
  3. POSTs to Apps Script URL with `{title: <service date or "Worship Script">, content: <preview content>, columns: 2}`
  4. Shows loading state on button ("Creating...")
  5. On success: shows the Doc URL in a result panel (mirror Spotify's `playlistUrl` display), auto-copies URL to clipboard, shows toast "Google Doc created — URL copied!"
  6. On error: surfaces the error message in a red banner, does NOT clear the chord sheet
- Reuses the existing `escapeHtml` and toast helpers — don't reinvent them

**What NOT to touch:**
- Don't change `handleSpotifyPlaylist()` or any Spotify functions
- Don't change the chord sheet preview generation or transposition logic
- Don't touch the catalog loading or song selection code

**How to verify:**
- `python3 -m http.server 8000 &`
- Open `http://localhost:8000`, select 2-3 songs, generate preview
- Confirm the new "Create Google Doc" button is visible next to the Spotify button
- Without an Apps Script URL set, click it and confirm the settings modal opens
- Open browser DevTools → Console, confirm no errors on page load or button click
- `pkill -f "http.server 8000"`

- [x] Task 2 done

---

## Task 3 — Settings panel: Apps Script URL configuration

**Category:** feature
**Priority:** 0
**Files:** `index.html`

Add a settings panel for Eric to paste the Apps Script web app URL once. Mirror the existing Gemini API key UX exactly.

**What "done" looks like:**
- A "⚙️ Settings" gear icon in the top-right of the header, opens a modal
- Modal has two sections:
  1. **Gemini API Key** (existing — surface the existing localStorage `gemini_api_key` here)
  2. **Google Doc Integration**
     - Text input for Apps Script URL, placeholder `https://script.google.com/macros/s/.../exec`
     - "Test" button: POSTs `{title: "Test", content: "Test from FMH Worship app"}` to the URL, shows green "✓ Connected — test Doc created" or red error
     - "Save" button: writes to `localStorage.setItem('apps_script_doc_url', value)`
     - Inline help: "Don't have a URL yet? See [DEPLOY.md](https://github.com/erictisme/church-chord-and-spotify-maker/blob/main/apps-script/DEPLOY.md)"
- Settings modal also opens automatically when user clicks Create Google Doc and has no URL set (from Task 2)
- Modal is dismissible (X in top-right, ESC key, click outside)

**What NOT to touch:**
- Don't migrate the existing Gemini API key storage to a new key — surface the existing `localStorage.getItem('gemini_api_key')` value
- Don't change the Spotify auth state UI

**How to verify:**
- `python3 -m http.server 8000 &`
- Open the app, click the new gear icon, confirm modal opens with both sections
- Paste a fake URL, click Test → confirm it shows an error gracefully (network error or Apps Script 404)
- Paste an empty value, click Save → confirm it does nothing or shows "URL required"
- Refresh the page, open Settings, confirm a saved URL persists
- DevTools console clean
- `pkill -f "http.server 8000"`

- [x] Task 3 done

---

## Task 4 — Ingest eric-all-weeks/ archive into song library

**Category:** feature
**Priority:** 1
**Files:** `scripts/ingest-eric-weeks.mjs` (new), `eric-songs/all-songs/*.md` (additions), `eric-songs/indices/tsv-catalog.json` (updates)

Eric's `eric-all-weeks/` folder has 194 past worship `.docx` files containing chord sheets in his preferred keys. The library currently doesn't reflect this. Build a script that parses these and adds canonical "Eric-archive" versions to the library.

**What "done" looks like:**
- `scripts/ingest-eric-weeks.mjs` is a Node ESM script (uses `mammoth` npm package or similar to parse .docx — install via `npm install mammoth --save-dev` in repo root, add `package.json` with `{"type":"module"}` if not present)
- Script:
  1. Reads every `.docx` in `eric-all-weeks/`
  2. Extracts text, identifies song boundaries (heuristic: bold headings, "Song 1:" patterns, blank-line separators)
  3. For each song: extracts title, key (first chord seen), chord-lyric block
  4. Writes to `eric-songs/all-songs/<title-key>.md` with frontmatter:
     ```
     ---
     title: ...
     artist: unknown   # filled later or from existing catalog
     key: ...
     source: eric-archive
     source_file: <docx filename>
     first_seen: <docx mtime>
     ---
     ```
  5. Updates `eric-songs/indices/tsv-catalog.json` with new entries, marking `source: eric-archive` so frontend can prefer them
  6. Logs: total files processed, songs extracted, duplicates merged, parse failures
- If a song already exists in `all-songs/` with the same title, **don't overwrite** — instead, write a sibling file `<title>-eric-<date>.md` and let frontend deduplication handle it
- Run the script as part of this task and commit the resulting new song files + updated catalog

**What NOT to touch:**
- Don't modify or delete any existing files in `eric-all-weeks/`
- Don't modify the existing 225 songs in `all-songs/` — only add new ones
- Don't change the frontend search logic in this task (separate task if needed)

**How to verify:**
- `node scripts/ingest-eric-weeks.mjs` runs to completion without crashing
- Check `eric-songs/all-songs/` count increased
- Open `tsv-catalog.json`, find a song with `"source": "eric-archive"`
- Open the app, search for a known song from his archive (e.g. "Lord is my Salvation"), confirm it appears with correct key

- [ ] Task 4 done

---

## Task 5 — WhatsApp paste parser at top of app

**Category:** feature
**Priority:** 2
**Files:** `index.html`

Add a paste-area at the top of the app that takes Marcus's WhatsApp message and pre-fills theme, passage, and song suggestions via Gemini.

**What "done" looks like:**
- New section above the existing Service Planning area: "Start from your worship pastor's message"
- Textarea, placeholder: paste a real-looking example message
- "Extract" button:
  1. Sends content to Gemini with structured-output prompt: extract `{theme: string, passage: string, suggested_songs: string[], notes?: string}`
  2. On response: pre-fills the existing theme field, passage field, and queues the suggested songs into the song-search area (don't auto-add — show as "Suggested from message" chips that Eric clicks to add)
- Failure mode: if Gemini returns malformed JSON, show "Couldn't parse — paste manually" and don't break the form
- Reuses the existing Gemini API key from localStorage. If no key set, opens Settings (Task 3) — don't ask for the key again here.

**What NOT to touch:**
- Don't change the existing Gemini AI Song Planning Assistant — this is a NEW input ABOVE it, feeding the same downstream form
- Don't change the song-selection logic

**How to verify:**
- Paste a sample message like "Hi Eric, this Sunday's theme is Christ is above all. Passage: Matthew 8:23-9:8. Songs I'm thinking: behold our God, The Lord is my Salvation, Above all, Crown Him." into the textarea, click Extract
- Confirm theme/passage fields populate, song chips appear with the 4 song names
- Click a chip, confirm it adds to the selected songs list
- DevTools console clean

- [ ] Task 5 done

---

## Task 6 — Team-message generator (one-click WhatsApp draft)

**Category:** feature
**Priority:** 3
**Files:** `index.html`

After the Doc + Spotify playlist exist, generate a paste-ready WhatsApp message for the team.

**What "done" looks like:**
- Button "📱 Copy Team Message" appears after both a Google Doc URL and a Spotify URL exist
- On click: composes a message in Eric's voice (lowercase, warm, no corporate-speak):
  ```
  hi @[team names from a settable field, default: Clarissa, Amanda, YY] we serving this sun! [prac time] prac on sun ok?

  set list 🙏

  1. <song 1> — <key>
  2. <song 2> — <key>
  ...

  doc: <Google Doc URL>
  spotify: <Spotify URL>

  pls run thru ur parts b4 sun. lmk if anything 🙏
  ```
- Auto-copy to clipboard, show toast "Team message copied!"
- "Team names" are stored in localStorage `team_names`, configurable via Settings panel (Task 3 — extend it)
- "Prac time" defaults to "330pm" but is editable in the form

**What NOT to touch:**
- Don't auto-send to WhatsApp (no API for that)
- Don't change Doc or Spotify creation logic

**How to verify:**
- After creating a Doc + Spotify playlist, confirm the new button appears
- Click it, paste into a text editor, confirm the message format is correct
- DevTools console clean

- [ ] Task 6 done
