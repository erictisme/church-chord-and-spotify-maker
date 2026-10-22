#!/usr/bin/env python3
"""Build the FMH "every song we've ever sung" master list and Spotify playlist.

Widens create_master_playlist.py (which only knows the 2024-26 roster) with
every other place FMH songs are recorded:

  history   eric-songs/history (2024-26 roster, with counts)       best evidence
  main      Eric's "Song Main List.xlsx", Songlists tab            has artists
  library   eric-songs/all-songs chord-sheet frontmatter           has artists
  scripts   worship-script .docx folders (2014 onwards)            bold song headings
  edgar     Edgar's "Master List" chord folder (Drive zip)          file names

Titles are merged on parse_history.canon_key, then matched with worship_match
(original recordings only, worship artists only). Anything not tied to a
worship recording is held back and listed in the report, never published on
a guess.

Usage:
    python3 build_master_list.py --main ~/Downloads/"Song Main List.xlsx" \
        --edgar-zip ~/Downloads/"Master List - Edgar-....zip" \
        --scripts DIR [--scripts DIR ...] [--spotify] [--publish]
"""

import argparse
import csv
import glob
import json
import os
import re
import time
import zipfile

import create_master_playlist as cmp

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "eric-songs", "master-list"))
CACHE = os.path.join(OUT, "spotify-match-cache.json")
PLAYLIST_KEY = "all_songs"
PLAYLIST_NAME = "FMH — Every Song (Master List)"

# Bold lines in scripts that are service furniture, not songs.
NOT_SONGS = re.compile(
    r"^(verse|chorus|pre-?chorus|bridge|intro|outro|tag|ending|interlude|"
    r"instrumental|refrain|coda|turnaround|key|capo|repeat|vamp|end|leader|"
    r"congregation|announcements?|introduction|narration|ot |nt |bible|"
    r"mutual|explanation|welcome|prayer|scripture|reading|call to|benediction|"
    r"offering|sermon|confession|assurance|communion|closing|opening|"
    r"pre-sermon|kids|response|theme|order of|lord.s supper|no capo|"
    r"song ?\d|songs?$|worship$|praise$|lament$|thanksgiving$|declaration$|"
    r"all$|men$|women$|ladies$|guys$|everyone$|silence|reflection|"
    r"acousticguitar|no name yet|untitled|new song|medley$|guitar|piano|"
    r"lead sheet|chords?$|lyrics?$|script|worship\W*\d|worship:|original|psalm \d+:|"
    r"hillsongs?( live)?$|paul baloche$|keith and kristyn getty$|krystin getty$|"
    r"just |second time|third time|first time|riffs?$|strings$|strumming$|quaver$|"
    r"slow$|soft$|sit$|robots$|diamond$|medley one$|v\d )", re.I)
CHORD = re.compile(r"^[A-G][#b]?(m|maj|min|sus|add|dim|aug)?\d*(/[A-G][#b]?)?$")
# Trailing artist credits we can lift into an artist hint.
DASH_ARTIST = re.compile(r"\s+[-–—]\s+([A-Z][\w&'. ]{2,40})$")


# Artists that turn up glued to titles in file names and script headings.
KNOWN_ARTISTS = ["Chris Tomlin", "Matt Redman", "Don Moen", "Aaron Shust", "Brenton Brown",
                 "Kristian Stanfill", "Paul Baloche", "Hillsong", "Bethel", "Phil Wickham",
                 "Keith & Kristyn Getty", "Getty", "CityAlight", "Emu Music", "Planetshakers"]


def smart_title(t):
    """'ISN'T HE?' -> "Isn't He?" (str.title() gives "Isn'T")."""
    return re.sub(r"[A-Za-z][A-Za-z']*", lambda m: m.group(0)[0].upper() + m.group(0)[1:].lower(), t)


NOTES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
NOTE_INDEX = {**{n: i for i, n in enumerate(NOTES)}, "Db": 1, "D#": 3, "Gb": 6, "G#": 8, "A#": 10}


def detect_key(heading, after):
    """Sounding key of a song in a script: the chord shape (from '(G)' in the
    heading, or the first chord line after it) moved up by any capo."""
    text = " ".join([heading] + list(after[:4]))
    m = re.search(r"capo\s*(-?\d+)", text, re.I)
    capo = int(m.group(1)) if m else 0
    shape = None
    m = re.search(r"\((?:in\s+)?([A-G][#b]?)m?[\s,)]", heading)
    if m:
        shape = m.group(1)
    else:
        for line in after[:6]:
            toks = [t for t in line.split() if not t.endswith(":")]
            if toks and sum(bool(CHORD.match(t.strip("()|-"))) for t in toks) / len(toks) > 0.5:
                first = next(t.strip("()|-") for t in toks if CHORD.match(t.strip("()|-")))
                shape = re.match(r"[A-G][#b]?", first).group(0)
                break
    if not shape or shape not in NOTE_INDEX:
        return ""
    return NOTES[(NOTE_INDEX[shape] + capo) % 12]


MASHUP_SPLIT = re.compile(r"\s+/\s+|\s*/\s*(?=[A-Z])|\s+[xX]\s+(?=[A-Za-z])|\s+&\s+(?=[A-Za-z])")


def split_mashup(heading):
    """'WHO AM I / LOVE CAME DOWN' -> ['Who Am I', 'Love Came Down']; None if not a mashup."""
    h = re.sub(r"^(medley|opening medley|song \d+)\s*[-–:]\s*", "", heading.strip(), flags=re.I)
    parts = [p for p in MASHUP_SPLIT.split(h) if p.strip()]
    if len(parts) < 2:
        return None
    cleaned = [clean_title(p) for p in parts]
    if any(c is None for c in cleaned):
        return None
    return [c[0] for c in cleaned]


# Different songs that share a title, told apart by a lyric line under the heading.
LYRIC_TWINS = {
    "forever": [("Chris Tomlin", r"forever god is faithful|give thanks to the lord our god"),
                ("Kari Jobe", r"the moon and stars they wept|morning sun was dead")],
}


def disambiguate(title, after):
    """'Forever' + Kari Jobe's lyrics -> 'Forever (Kari Jobe)'. Unchanged if unsure."""
    twins = LYRIC_TWINS.get(re.sub(r"\s*\(.*\)$", "", title).strip().lower())
    text = " ".join(after).lower()
    for artist, pattern in twins or []:
        if re.search(pattern, text):
            return f"{re.sub(r'\s*\(.*\)$', '', title).strip()} ({artist})"
    return title


# Two names for one song, not a mashup.
ALT_TITLES = [("My Hope Is Built", "The Solid Rock"), ("Rock Of Ages Cleft For Me", "Rock Of Ages"),
              ("I Surrender All", "All To Jesus I Surrender")]


def build_mashups(raw, songs):
    """raw: [(parts, year, owner)] -> [{songs, n, years, who}] for mashups of known songs."""
    canon = cmp.load_parser().canon_key
    known = {s["key"] for s in songs}
    alts = [frozenset(canon(t) for t in pair) for pair in ALT_TITLES]
    agg = {}
    for parts, year, owner in raw:
        keys = tuple(canon(p) for p in parts)
        if any(k not in known for k in keys) or frozenset(keys) in alts or len(set(keys)) < 2:
            continue
        m = agg.setdefault(keys, {"songs": list(parts), "n": 0, "years": [], "who": {}})
        m["n"] += 1
        if year:
            m["years"].append(year)
        if owner:
            m["who"][owner] = m["who"].get(owner, 0) + 1
    out = list(agg.values())
    for m in out:
        m["years"].sort()
    return sorted(out, key=lambda m: (-m["n"], m["songs"][0]))


def apply_originals(songs, titles):
    canon = cmp.load_parser().canon_key
    keys = {canon(t) for t in titles}
    for s in songs:
        if s["key"] in keys:
            s["local"] = True


def clean_title(raw):
    """Raw heading / file name -> (title, artist_hint), or None if not a song."""
    t = raw.replace("_s ", "'s ").replace("’", "'").replace("‘", "'")
    t = re.sub(r"\(.*?conflicted copy.*?\)|\(case conflict\)|\(\d\)$", "", t, flags=re.I)
    t = re.sub(r"\[[^\]]*\]?", "", t)                      # [Capo 2]
    t = re.sub(r"\.(docx?|pages|pdf)$", "", t.strip(), flags=re.I)
    t = re.sub(r"\s+[A-G][#b]?m?\)$", "", t)                # "Spirit lead me G)"
    t = re.sub(r"\((?:[A-G][#b]?m?\d*|[A-Z]?\d+|key.*?|capo.*?|acoustic|alt.*?|"
               r"new|old|female|male|low|high)\)", "", t, flags=re.I)
    t = re.sub(r"\b(new|final|edited|v\d)$", "", t.strip(), flags=re.I)
    t = re.sub(r"\s+(?:[A-G][#b]?m?|x\d|\d?x)$", "", t.strip(), flags=re.I)   # "Christ is Enough G"
    t = re.sub(r"\s+", " ", t).strip(" -–:.,'&(")
    artist = ""
    # Artist glued on without a dash: "Mercy Matt Redman", "Brenton Brown - Jesus Take All Of Me".
    for name in KNOWN_ARTISTS:
        m = re.match(rf"^(.+?)\s+(?:[-–—]\s+|by\s+)?({re.escape(name)})$", t, re.I)
        if m and len(m.group(1).split()) >= 1:
            t, artist = m.group(1).strip(), m.group(2)
            break
        m = re.match(rf"^({re.escape(name)})\s+[-–—]\s+(.+)$", t, re.I)
        if m:
            artist, t = m.group(1), m.group(2).strip()
            t = re.sub(r"\s*\(.*$", "", t)
            break
    if ":" in t:                                           # "Run to the Father: Cody Carnes"
        head, _, tail = t.partition(":")
        if re.match(r"^[A-Z][\w ,&.]+$", tail.strip()) and len(tail.split()) <= 4:
            t, artist = head.strip(), tail.strip()
        else:
            return None
    m = None if artist else DASH_ARTIST.search(t)
    if m and not re.search(r"\b(of|the|my|me|you|thou|lord|god)\b$", t[: m.start()], re.I):
        artist, t = m.group(1).strip(), t[: m.start()].strip()
    if t.isupper():
        t = smart_title(t)
    if len(t) < 3 or len(t) > 60 or NOT_SONGS.match(t) or re.match(r"^[\d\W]+$", t):
        return None
    if re.search(r"\d{1,3}:\d", t) or re.search(r"[_]|rec_", t):
        return None
    toks = t.split()
    if sum(bool(CHORD.match(x.strip("()|-"))) for x in toks) / len(toks) > 0.5:
        return None
    return t, artist


# ---------- sources ----------

def from_history():
    adult, kids = cmp.load_songs()
    with open(cmp.FREQ) as f:
        freq = json.load(f)
    for song in adult + kids:
        yield {"title": song["title"], "artist": song["artist"], "source": "history",
               "count": song["count"], "last_sung": song["last_sung"],
               "local": song["local"], "kids": song in kids,
               "dates": freq.get(song["title"], {}).get("dates", []),
               "slots": freq.get(song["title"], {}).get("slots", {})}


# ---------- who picked it ----------

PEOPLE = {"rizvan": "Rizvan", "riz": "Rizvan", "edgar": "Edgar", "eric": "Eric",
          "francis": "Francis", "janessa": "Janessa", "chester": "Chester", "seb": "Seb"}
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_scripts_spec(spec):
    """'Rizvan=/path' -> ('Rizvan', '/path'); a bare path has no owner."""
    if "=" in spec and not os.path.exists(spec):
        owner, _, path = spec.partition("=")
        return owner.strip(), path
    return "", spec


def owner_for(owner, path):
    """Edgar's subfolder inside someone else's scripts is still Edgar's."""
    return "Edgar" if f"{os.sep}Edgar{os.sep}" in path else owner


def _parse_date(text):
    t = text.strip().lower()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.match(r"^(\d{1,2})[/.](\d{1,2})[/.](\d{4})$", t)          # DD/MM/YYYY (Singapore)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    m = re.match(r"^(\d{1,2})\s+([a-z]{3})[a-z]*\.?\s+(\d{4})", t)
    if m and m.group(2) in MONTHS:
        return f"{m.group(3)}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"
    return None


def parse_leader_csv(path):
    """Roster export -> {date: leader}. Takes the first known name after the date
    cell on each row, so column order and headers don't matter."""
    leaders = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            date = None
            for cell in row:
                if date is None:
                    date = _parse_date(cell)
                    continue
                low = cell.lower()
                name = next((v for k, v in PEOPLE.items() if re.search(rf"\b{k}\b", low)), None)
                if name:
                    leaders[date] = name
                    break
    return leaders


def apply_leaders(songs, leaders):
    for s in songs:
        for d in s.get("dates", []):
            if d in leaders:
                s.setdefault("roster_leaders", {})
                s["roster_leaders"][leaders[d]] = s["roster_leaders"].get(leaders[d], 0) + 1


def from_main(path):
    import openpyxl
    ws = openpyxl.load_workbook(path, data_only=True)["Songlists"]
    for row in ws.iter_rows(min_row=3, values_only=True):
        era, title, artist = row[0], row[1], row[2]
        if not title or not str(title).strip():
            continue
        artist = "" if not artist or str(artist).strip() in "-?" else str(artist).strip()
        yield {"title": str(title).strip(), "artist": artist, "source": "main",
               "era": era or "", "extra": {
                   "eric_count": row[3], "pace": row[4] or "", "rough_category": row[5] or "",
                   "theme": row[6] or "", "sub_category": row[7] or "",
                   "acoustic": row[8] or "", "introduced": row[12] or ""}}


def from_library():
    for name in sorted(os.listdir(cmp.LIBRARY)):
        if name.endswith(".md"):
            fm = cmp.parse_frontmatter(os.path.join(cmp.LIBRARY, name))
            if fm.get("title"):
                artist = fm.get("artist", "")
                themes = fm.get("themes") or ""
                if isinstance(themes, str):
                    themes = [x.strip() for x in themes.strip("[]").split(",") if x.strip()]
                yield {"title": fm["title"], "source": "library",
                       "artist": "" if artist in ("unknown", "Unknown") else artist,
                       "extra": {"chart_key": fm.get("key", ""), "lib_pace": fm.get("pace", ""),
                                 "lib_era": fm.get("era", ""),
                                 "lib_theme": themes[0] if themes else "", "has_chart": True}}


SECTION_START = re.compile(r"^\s*\(?(verse|v\d|intro|chorus|pre-?chorus|stanza|refrain|capo)\b", re.I)
JUNK_WORDS = re.compile(r"\b(chorus|interlude|intro|outr?o|stanza|verse|drums?|bass|"
                        r"softly?|build|strum|pluck|repeat|service|worship \d|psalm of|"
                        r"prayers?|reading|only\)|time only|clapping|keys|cello)\b", re.I)


def _chordy(text):
    toks = text.split()
    return bool(toks) and sum(bool(CHORD.match(x.strip("()|-"))) for x in toks) / len(toks) > 0.5


def _open_docx(path):
    import docx
    return docx.Document(path)


# Newer service scripts list songs as "SONG 1: Title" with no chord chart.
SONG_LINE = re.compile(r"^(?:song\s*\d*|closing\s+song|opening\s+song|response\s+song)\s*[:\-–]\s*(.+)$", re.I)


def script_headings(path):
    """Song headings: bold lines followed by a chord chart, or 'SONG n: Title' lines."""
    try:
        doc = _open_docx(path)
    except Exception:
        return []
    paras = [(re.sub(r"[\u2060\u200b\xa0]", " ", p.text).strip(), p) for p in doc.paragraphs if p.text.strip()]
    found = []
    for i, (text, p) in enumerate(paras):
        m = SONG_LINE.match(text)
        if m and m.group(1).strip():
            found.append((re.sub(r"\s+", " ", m.group(1)).strip(), [t for t, _ in paras[i + 1:i + 7]]))
            continue
        runs = [r for r in p.runs if r.text.strip()]
        if not (runs and all(r.bold for r in runs) and len(text) <= 80):
            continue
        if JUNK_WORDS.search(text) or text[0].islower() or text[0].isdigit():
            continue
        after = [t for t, _ in paras[i + 1:i + 4]]
        if any(_chordy(t) or SECTION_START.match(t) for t in after):
            found.append((text, [t for t, _ in paras[i + 1:i + 7]]))
    return found


def year_from_filename(name):
    """Service year from a script file name: 2014-01-04, 180819 (DDMMYY), 8.11.2020."""
    m = re.search(r"(20[12]\d)", name)
    if m:
        return int(m.group(1))
    m = re.search(r"(?<!\d)(\d{1,2})\.(\d{1,2})\.(\d{2})(?!\d)", name)       # 01.07.18
    if m and 1 <= int(m.group(1)) <= 31 and 1 <= int(m.group(2)) <= 12:
        return 2000 + int(m.group(3))
    m = re.search(r"(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)", name)
    if m and 1 <= int(m.group(1)) <= 31 and 1 <= int(m.group(2)) <= 12:
        return 2000 + int(m.group(3))
    return None


def from_scripts(specs, mashups=None):
    """Song rows from worship scripts. Mashup headings also go to `mashups`
    as (parts, year, owner)."""
    for spec in specs:
        owner, d = parse_scripts_spec(spec)
        for path in sorted(glob.glob(os.path.join(d, "**", "*.docx"), recursive=True)):
            if os.path.basename(path).startswith("~"):
                continue
            year = year_from_filename(os.path.basename(path))
            who = owner_for(owner, path)
            seen = set()
            for h in script_headings(path):
                heading, after = (h, []) if isinstance(h, str) else h
                parts = split_mashup(heading)
                if parts and mashups is not None:
                    mashups.append((parts, year, who))
                titles = [(p, "") for p in parts] if parts else (
                    [clean_title(heading)] if clean_title(heading) else [])
                key = "" if parts else detect_key(heading, after)
                for title, artist in titles:
                    if not parts:
                        twin = disambiguate(title, after)
                        if twin != title:
                            title, artist = twin, twin[twin.rindex("(") + 1:-1]
                    if title.lower() in seen:
                        continue
                    seen.add(title.lower())
                    row = {"title": title, "artist": artist, "source": "scripts",
                           "year": year, "owner": who, "key": key}
                    if title.endswith(")") and artist and title.endswith(f"({artist})"):
                        row["canon"] = f"{title[:title.rindex('(')].strip().lower()} {artist.lower()}"
                    yield row


def from_edgar(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            base = os.path.basename(name)
            if not base or base.startswith(("~", ".")):
                continue
            stem, ext = os.path.splitext(base)
            if ext.lower() not in (".doc", ".docx", ".pdf", ".pages", ".txt", ".rtf"):
                continue
            stem = re.sub(r"\.docx$", "", stem)
            parts = split_mashup(stem)
            for title, artist in ([(p, "") for p in parts] if parts else
                                  [clean_title(stem)] if clean_title(stem) else []):
                yield {"title": title, "artist": artist, "source": "edgar", "owner": "Edgar"}


# ---------- merge ----------

def merge(rows):
    canon = cmp.load_parser().canon_key
    songs = {}
    for r in rows:
        key = r.get("canon") or canon(r["title"])
        if not key or len(key) < 3:
            continue
        s = songs.setdefault(key, {"key": key, "titles": {}, "artists": {}, "sources": set(),
                                   "count": 0, "last_sung": "", "script_uses": 0,
                                   "local": False, "kids": False, "era": "", "years": set(),
                                   "owners": {}, "script_years": {}, "roster_years": {},
                                   "owner_years": {}, "keys_played": {}, "latest_key": "",
                                   "latest_key_year": 0, "slots": {},
                                   "dates": []})
        if r.get("year"):
            s["years"].add(r["year"])
            y = str(r["year"])
            s["script_years"][y] = s["script_years"].get(y, 0) + 1
        if r.get("owner"):
            s["owners"][r["owner"]] = s["owners"].get(r["owner"], 0) + 1
            if r.get("year"):
                oy = s["owner_years"].setdefault(r["owner"], {})
                oy[str(r["year"])] = oy.get(str(r["year"]), 0) + 1
        if r.get("key"):
            s["keys_played"][r["key"]] = s["keys_played"].get(r["key"], 0) + 1
            if (r.get("year") or 0) >= s["latest_key_year"]:
                s["latest_key"], s["latest_key_year"] = r["key"], r.get("year") or 0
        for d in r.get("dates") or []:
            s["roster_years"][d[:4]] = s["roster_years"].get(d[:4], 0) + 1
            s["dates"].append(d)
        if r["source"] == "history" and r.get("last_sung"):
            s["years"].add(int(r["last_sung"][:4]))
        s["titles"][r["title"]] = s["titles"].get(r["title"], 0) + 1
        if r.get("artist"):
            # Prefer artists from the better sources.
            weight = {"library": 5, "main": 4, "history": 3, "edgar": 2, "scripts": 1}[r["source"]]
            s["artists"][r["artist"]] = s["artists"].get(r["artist"], 0) + weight
        s["sources"].add(r["source"])
        for k, v in (r.get("extra") or {}).items():
            if v not in (None, "") and s.get(k) in (None, ""):
                s[k] = v
        if r["source"] == "history":
            for k, v in (r.get("slots") or {}).items():
                s["slots"][k] = s["slots"].get(k, 0) + v
            s["count"] = max(s["count"], r["count"])
            s["last_sung"] = max(s["last_sung"], r["last_sung"] or "")
            s["local"] |= r["local"]
            s["kids"] |= r["kids"]
        if r["source"] == "scripts":
            s["script_uses"] += 1
        if r.get("era"):
            s["era"] = r["era"]
    out = []
    for s in songs.values():
        # Display title: the history title if there is one, else the most common spelling.
        s["title"] = max(s["titles"], key=lambda t: (s["titles"][t], not t.isupper(), -len(t)))
        s["artist"] = max(s["artists"], key=s["artists"].get) if s["artists"] else ""
        s["sources"] = sorted(s["sources"])
        s["local"] = s["local"] or cmp.is_local(" ".join(s["titles"]) + " " + s["artist"])
        # Mostly sung in the roster's Kids' slot -> a kids' song, whoever published it.
        slot_total = sum(s["slots"].values())
        if slot_total and s["slots"].get("kids", 0) * 2 > slot_total:
            s["kids"] = True
        s["first_year"] = min(s["years"]) if s["years"] else None
        s["last_year"] = max(s["years"]) if s["years"] else None
        # Same Sunday can be in both a script and the roster: take the larger, never the sum.
        s["year_counts"] = {y: max(s["script_years"].get(y, 0), s["roster_years"].get(y, 0))
                            for y in sorted(set(s["script_years"]) | set(s["roster_years"]))}
        del s["titles"], s["artists"], s["years"], s["script_years"], s["roster_years"]
        out.append(s)

    def order(s):
        return (-s["count"], -s["script_uses"], -len(s["sources"]), s["title"].lower())
    return sorted(out, key=order)


def trusted(s):
    """Scripts-only titles are often headings, not songs: need two sightings or
    a multi-word title. decide() also demands an exact Spotify title for them."""
    return (s["sources"] != ["scripts"] or s.get("script_uses", 0) >= 2
            or len(s["title"].split()) >= 2)


def scripts_only(s):
    return s["sources"] == ["scripts"]


def apply_ai_tags(songs, tags):
    """AI theme/pace only fill gaps (catalogue prefers Eric's and the library's tags)."""
    for s in songs:
        t = tags.get(s["title"])
        if t:
            s["ai_theme"], s["ai_pace"] = t.get("theme", ""), t.get("pace", "")
            s["not_a_song"] = bool(t.get("not_a_song"))
            s["ai_confident"] = t.get("confident", True)


def apply_ai_artists(songs, artists):
    """Fill a missing artist with the AI's original-recording artist (confident only)."""
    for s in songs:
        a = artists.get(s["title"]) or {}
        if not s["artist"] and a.get("artist") and a.get("confident", True):
            s["artist"], s["artist_source"] = a["artist"], "ai"


def release_year(date):
    m = re.match(r"^(\d{4})", date or "")
    return int(m.group(1)) if m else None


# ---------- spotify ----------

def spotify():
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    creds = cmp.load_spotify_config()
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=creds["client_id"], client_secret=creds["client_secret"],
        redirect_uri=creds.get("redirect_uri", "http://localhost:8888/callback"),
        scope=cmp.SCOPE, cache_path=cmp.TOKEN_CACHE, open_browser=False),
        requests_timeout=20, retries=5)


def search_artist(s):
    """The artist to search with. A hymn's 'artist' is often its 18th-century
    writer, which only finds classical tribute albums, so drop it unless it is
    a real worship recording artist."""
    a = s.get("artist", "")
    is_hymn = s.get("stream") == "hymn-traditional" or "hymn" in f"{s.get('era', '')} {s.get('lib_era', '')}".lower()
    if is_hymn and a and not any(n in a.lower() for n in cmp.worship_match.NAMED_ARTISTS):
        return ""
    return a


def apply_overrides(songs, overrides):
    """Hand-pinned recordings (overrides.json) beat the search."""
    for s in songs:
        o = overrides.get(s["title"])
        if o:
            s["match"] = {"uri": o["uri"], "artist": o.get("artist", ""), "name": o.get("name", ""),
                          "album": o.get("album", ""), "confidence": "high"}


def still_valid(m, title):
    """Re-check a saved match against today's title and album rules."""
    wm = cmp.worship_match
    clean = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip() or title
    return (wm._title_matches(m.get("name", ""), wm._title_key(clean))
            and not wm.INSTRUMENTAL_ALBUM.search(m.get("album", "")))


def match_all(sp, songs):
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    for i, s in enumerate(songs, 1):
        artist = search_artist(s)
        ck = f"{s['title']}|{artist}"
        if ck in cache and cache[ck] and not still_valid(cache[ck], s["title"]):
            del cache[ck]                      # saved before a newer rule existed
        if ck not in cache:
            m = cmp.worship_match.find(sp, s["title"], artist)
            cache[ck] = m and {k: m[k] for k in ("uri", "artist", "album", "confidence")} | {
                "name": m.get("name", "")}
            if i % 20 == 0:
                json.dump(cache, open(CACHE, "w"), indent=1)
                print(f"  {i}/{len(songs)} matched", flush=True)
            time.sleep(0.05)
        s["match"] = cache[ck]
    json.dump(cache, open(CACHE, "w"), indent=1)


def fetch_details(sp, songs):
    """Recording year + popularity for every matched track (50 per call, cached)."""
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    details = cache.setdefault("__details__", {})
    ids = sorted({s["match"]["uri"].split(":")[-1] for s in songs if s.get("match")} - set(details))
    for i in range(0, len(ids), 50):
        for t in sp.tracks(ids[i:i + 50])["tracks"]:
            if t:
                details[t["id"]] = {"date": t["album"].get("release_date", ""),
                                    "popularity": t.get("popularity")}
    json.dump(cache, open(CACHE, "w"), indent=1)
    for s in songs:
        if s.get("match"):
            d = details.get(s["match"]["uri"].split(":")[-1], {})
            s["release_year"], s["popularity"] = release_year(d.get("date")), d.get("popularity")


def decide(songs):
    seen = {}
    for s in songs:
        m = s.get("match")
        if s.get("not_a_song"):
            s["status"], s["reason"] = "held", "AI check: not a song title"
        elif s["local"]:
            s["status"], s["reason"] = "held", "written in-house, no commercial recording"
        elif not trusted(s):
            s["status"], s["reason"] = "held", "seen once in one script only, may not be a song"
        elif not m:
            s["status"], s["reason"] = "held", "no Spotify match found"
        elif m["confidence"] not in cmp.PUBLISHABLE:
            s["status"], s["reason"] = "held", f"only a non-worship recording ({m['artist']})"
        elif scripts_only(s) and cmp.worship_match._title_key(m.get("name", "")) != \
                cmp.worship_match._title_key(s["title"]):
            s["status"], s["reason"] = "held", f"script heading, Spotify title differs ({m.get('name')})"
        elif m["uri"] in seen:
            s["status"], s["reason"] = "dupe", f"same recording as “{seen[m['uri']]}”"
        else:
            seen[m["uri"]] = s["title"]
            s["status"], s["reason"] = "on", "" if m["confidence"] == "high" else "check version"


def write_outputs(songs):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "master-list.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["title", "artist_on_file", "times_sung_2024_26", "last_sung",
                    "script_appearances", "sources", "kids", "playlist_status", "reason",
                    "spotify_artist", "spotify_album", "spotify_uri"])
        for s in songs:
            m = s.get("match") or {}
            w.writerow([s["title"], s["artist"], s["count"] or "", s["last_sung"],
                        s["script_uses"] or "", " ".join(s["sources"]), "yes" if s["kids"] else "",
                        s.get("status", ""), s.get("reason", ""), m.get("artist", ""),
                        m.get("album", ""), m.get("uri", "")])
    with open(os.path.join(OUT, "master-list.json"), "w") as f:
        json.dump(songs, f, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--main")
    ap.add_argument("--edgar-zip")
    ap.add_argument("--scripts", action="append", default=[])
    ap.add_argument("--leaders", help="roster CSV export with who led each date")
    ap.add_argument("--spotify", action="store_true", help="match on Spotify")
    ap.add_argument("--publish", action="store_true", help="create/update the playlist")
    args = ap.parse_args()

    rows = list(from_history()) + list(from_library())
    if args.main:
        rows += list(from_main(args.main))
    if args.edgar_zip:
        rows += list(from_edgar(args.edgar_zip))
    raw_mashups = []
    rows += list(from_scripts(args.scripts, raw_mashups))
    songs = merge(rows)
    # Roster mashups ("Man of Sorrows / Mercy"), one per date sung.
    for r in rows:
        if r["source"] == "history" and split_mashup(r["title"]):
            raw_mashups += [(split_mashup(r["title"]), int(d[:4]), "") for d in r.get("dates", [])]
    originals_path = os.path.join(OUT, "originals.json")
    if os.path.exists(originals_path):
        apply_originals(songs, json.load(open(originals_path)))
    with open(os.path.join(OUT, "mashups.json"), "w") as f:
        json.dump(build_mashups(raw_mashups, songs), f, indent=1)
    print(f"{len(rows)} sightings -> {len(songs)} distinct songs")
    if args.leaders:
        apply_leaders(songs, parse_leader_csv(args.leaders))
    tags_path = os.path.join(OUT, "ai-tags.json")
    if os.path.exists(tags_path):
        apply_ai_tags(songs, json.load(open(tags_path)))
    artists_path = os.path.join(OUT, "ai-artists.json")
    if os.path.exists(artists_path):
        apply_ai_artists(songs, json.load(open(artists_path)))

    if args.spotify:
        sp = spotify()
        match_all(sp, [s for s in songs if not s["local"] and trusted(s) and not s.get("not_a_song")])
        overrides_path = os.path.join(OUT, "overrides.json")
        if os.path.exists(overrides_path):
            apply_overrides(songs, json.load(open(overrides_path)))
        fetch_details(sp, songs)
        decide(songs)
        on = [s for s in songs if s["status"] == "on"]
        print(f"on playlist: {len(on)}  held: {sum(s['status'] == 'held' for s in songs)}  "
              f"dupes: {sum(s['status'] == 'dupe' for s in songs)}")
        if args.publish:
            me = sp.current_user()
            url = cmp.publish(sp, me["id"], PLAYLIST_KEY, PLAYLIST_NAME,
                              "Every song FMH has sung or kept charts for, 2014–2026, "
                              "original recordings. Most-sung first.",
                              [s["match"]["uri"] for s in on])
            print("Playlist:", url)
    write_outputs(songs)
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
