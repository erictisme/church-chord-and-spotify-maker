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
    if ":" in t:                                           # "Run to the Father: Cody Carnes"
        head, _, tail = t.partition(":")
        if re.match(r"^[A-Z][\w ,&.]+$", tail.strip()) and len(tail.split()) <= 4:
            t, artist = head.strip(), tail.strip()
        else:
            return None
    m = DASH_ARTIST.search(t)
    if m and not re.search(r"\b(of|the|my|me|you|thou|lord|god)\b$", t[: m.start()], re.I):
        artist, t = m.group(1).strip(), t[: m.start()].strip()
    if t.isupper():
        t = t.title()
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
    for song in adult + kids:
        yield {"title": song["title"], "artist": song["artist"], "source": "history",
               "count": song["count"], "last_sung": song["last_sung"],
               "local": song["local"], "kids": song in kids}


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


def script_headings(path):
    """Bold headings that are immediately followed by a chord chart."""
    import docx
    try:
        doc = docx.Document(path)
    except Exception:
        return []
    paras = [(p.text.strip(), p) for p in doc.paragraphs if p.text.strip()]
    found = []
    for i, (text, p) in enumerate(paras):
        runs = [r for r in p.runs if r.text.strip()]
        if not (runs and all(r.bold for r in runs) and len(text) <= 80):
            continue
        if JUNK_WORDS.search(text) or text[0].islower() or text[0].isdigit():
            continue
        after = [t for t, _ in paras[i + 1:i + 4]]
        if any(_chordy(t) or SECTION_START.match(t) for t in after):
            found += re.split(r"\s*/\s*|\s+&\s+(?=[A-Z])|\s+\+\s+|\s+[xX]\s+(?=[A-Z])", text)
    return found


def year_from_filename(name):
    """Service year from a script file name: 2014-01-04, 180819 (DDMMYY), 8.11.2020."""
    m = re.search(r"(20[12]\d)", name)
    if m:
        return int(m.group(1))
    m = re.search(r"(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)", name)
    if m and 1 <= int(m.group(1)) <= 31 and 1 <= int(m.group(2)) <= 12:
        return 2000 + int(m.group(3))
    return None


def from_scripts(dirs):
    for d in dirs:
        for path in sorted(glob.glob(os.path.join(d, "**", "*.docx"), recursive=True)):
            if os.path.basename(path).startswith("~"):
                continue
            for raw in script_headings(path):
                cleaned = clean_title(raw)
                if cleaned:
                    yield {"title": cleaned[0], "artist": cleaned[1], "source": "scripts",
                           "year": year_from_filename(os.path.basename(path))}


def from_edgar(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            base = os.path.basename(name)
            if not base or base.startswith(("~", ".")):
                continue
            stem, ext = os.path.splitext(base)
            if ext.lower() not in (".doc", ".docx", ".pdf", ".pages", ".txt", ".rtf"):
                continue
            cleaned = clean_title(re.sub(r"\.docx$", "", stem))
            if cleaned:
                yield {"title": cleaned[0], "artist": cleaned[1], "source": "edgar"}


# ---------- merge ----------

def merge(rows):
    canon = cmp.load_parser().canon_key
    songs = {}
    for r in rows:
        key = canon(r["title"])
        if not key or len(key) < 3:
            continue
        s = songs.setdefault(key, {"key": key, "titles": {}, "artists": {}, "sources": set(),
                                   "count": 0, "last_sung": "", "script_uses": 0,
                                   "local": False, "kids": False, "era": "", "years": set()})
        if r.get("year"):
            s["years"].add(r["year"])
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
        s["first_year"] = min(s["years"]) if s["years"] else None
        s["last_year"] = max(s["years"]) if s["years"] else None
        del s["titles"], s["artists"], s["years"]
        out.append(s)

    def order(s):
        return (-s["count"], -s["script_uses"], -len(s["sources"]), s["title"].lower())
    return sorted(out, key=order)


def trusted(s):
    """Scripts-only titles are often headings, not songs: need two sightings or
    a multi-word title. decide() also demands an exact Spotify title for them."""
    return (s["sources"] != ["scripts"] or s["script_uses"] >= 2
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


def match_all(sp, songs):
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    for i, s in enumerate(songs, 1):
        ck = f"{s['title']}|{s['artist']}"
        if ck not in cache:
            m = cmp.worship_match.find(sp, s["title"], s["artist"])
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
    ap.add_argument("--spotify", action="store_true", help="match on Spotify")
    ap.add_argument("--publish", action="store_true", help="create/update the playlist")
    args = ap.parse_args()

    rows = list(from_history()) + list(from_library())
    if args.main:
        rows += list(from_main(args.main))
    if args.edgar_zip:
        rows += list(from_edgar(args.edgar_zip))
    rows += list(from_scripts(args.scripts))
    songs = merge(rows)
    print(f"{len(rows)} sightings -> {len(songs)} distinct songs")
    tags_path = os.path.join(OUT, "ai-tags.json")
    if os.path.exists(tags_path):
        apply_ai_tags(songs, json.load(open(tags_path)))
    artists_path = os.path.join(OUT, "ai-artists.json")
    if os.path.exists(artists_path):
        apply_ai_artists(songs, json.load(open(artists_path)))

    if args.spotify:
        sp = spotify()
        match_all(sp, [s for s in songs if not s["local"] and trusted(s) and not s.get("not_a_song")])
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
