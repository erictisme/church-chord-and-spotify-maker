#!/usr/bin/env python3
"""FMH song catalogue: MECE facets over the master list, rendered to one HTML page.

Every facet puts every song in exactly ONE bucket (tests enforce it), so any
facet, or any pair of facets crossed in the page's pivot, is a clean split of
the whole repertoire. 18+ facets -> 150+ two-way pivots, times every filter
combination.

Usage:
    python3 catalogue.py            # reads eric-songs/master-list/master-list.json
"""

import datetime as dt
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
MASTER = os.path.abspath(os.path.join(HERE, "..", "eric-songs", "master-list"))
HISTORY = os.path.abspath(os.path.join(HERE, "..", "eric-songs", "history"))

UNKNOWN = "Unknown"

# ---------- artist knowledge ----------

# artist substring -> (family label, region, tradition)
ARTISTS = [
    ("cityalight", "CityAlight", "Australia", "Reformed modern"),
    ("city alight", "CityAlight", "Australia", "Reformed modern"),
    ("getty", "Getty", "UK & Ireland", "Reformed modern"),
    ("stuart townend", "Getty", "UK & Ireland", "Reformed modern"),
    ("sovereign grace", "Sovereign Grace", "USA", "Reformed modern"),
    ("emu kids", "Emu Music", "Australia", "Kids"),
    ("emu", "Emu Music", "Australia", "Reformed modern"),
    ("shane", "Shane & Shane", "USA", "Reformed modern"),
    ("boswell", "Boswell / Papa", "USA", "Reformed modern"),
    ("matt papa", "Boswell / Papa", "USA", "Reformed modern"),
    ("austin stone", "Other reformed", "USA", "Reformed modern"),
    ("indelible grace", "Other reformed", "USA", "Hymn & traditional"),
    ("norton hall", "Other reformed", "USA", "Reformed modern"),
    ("matt merker", "Other reformed", "USA", "Reformed modern"),
    ("awesome cutlery", "Awesome Cutlery", "Singapore & local", "Kids"),
    ("colin buchanan", "Other kids", "Australia", "Kids"),
    ("seeds family", "Other kids", "USA", "Kids"),
    ("hillsong", "Hillsong", "Australia", "Charismatic / CCM"),
    ("planetshakers", "Other charismatic", "Australia", "Charismatic / CCM"),
    ("bethel", "Bethel", "USA", "Charismatic / CCM"),
    ("jenn johnson", "Bethel", "USA", "Charismatic / CCM"),
    ("brian johnson", "Bethel", "USA", "Charismatic / CCM"),
    ("cory asbury", "Bethel", "USA", "Charismatic / CCM"),
    ("elevation", "Elevation", "USA", "Charismatic / CCM"),
    ("maverick city", "Other charismatic", "USA", "Charismatic / CCM"),
    ("jesus culture", "Other charismatic", "USA", "Charismatic / CCM"),
    ("cody carnes", "Other charismatic", "USA", "Charismatic / CCM"),
    ("kari jobe", "Other charismatic", "USA", "Charismatic / CCM"),
    ("housefires", "Other charismatic", "USA", "Charismatic / CCM"),
    ("brooke ligertwood", "Hillsong", "Australia", "Charismatic / CCM"),
    ("tomlin", "Chris Tomlin", "USA", "Charismatic / CCM"),
    ("passion", "Chris Tomlin", "USA", "Charismatic / CCM"),
    ("redman", "Matt Redman", "UK & Ireland", "Charismatic / CCM"),
    ("phil wickham", "Phil Wickham", "USA", "Charismatic / CCM"),
    ("baloche", "Other CCM", "USA", "Charismatic / CCM"),
    ("brenton brown", "Other CCM", "USA", "Charismatic / CCM"),
    ("don moen", "Other CCM", "USA", "Charismatic / CCM"),
    ("hosanna! music", "Other CCM", "USA", "Charismatic / CCM"),
    ("vineyard", "Other CCM", "USA", "Charismatic / CCM"),
    ("graham kendrick", "Other CCM", "UK & Ireland", "Charismatic / CCM"),
    ("tim hughes", "Other CCM", "UK & Ireland", "Charismatic / CCM"),
    ("rend collective", "Other CCM", "UK & Ireland", "Charismatic / CCM"),
    ("delirious", "Other CCM", "UK & Ireland", "Charismatic / CCM"),
    ("crowder", "Other CCM", "USA", "Charismatic / CCM"),
    ("michael w. smith", "Other CCM", "USA", "Charismatic / CCM"),
    ("lenny leblanc", "Other CCM", "USA", "Charismatic / CCM"),
    ("aaron shust", "Other CCM", "USA", "Charismatic / CCM"),
    ("kristian stanfill", "Chris Tomlin", "USA", "Charismatic / CCM"),
    ("david crowder", "Other CCM", "USA", "Charismatic / CCM"),
    ("newsboys", "Other CCM", "USA", "Charismatic / CCM"),
    ("casting crowns", "Other CCM", "USA", "Charismatic / CCM"),
    ("all sons", "Other CCM", "USA", "Charismatic / CCM"),
    ("jonny robinson", "CityAlight", "Australia", "Reformed modern"),
    ("bob kauflin", "Sovereign Grace", "USA", "Reformed modern"),
    ("worship initiative", "Shane & Shane", "USA", "Reformed modern"),
    ("hymns of grace", "Other reformed", "USA", "Hymn & traditional"),
    ("the sing team", "Other reformed", "USA", "Reformed modern"),
    ("page cxvi", "Other reformed", "USA", "Hymn & traditional"),
    ("fernando ortega", "Other reformed", "USA", "Hymn & traditional"),
    ("still waters worship", "Other reformed", "USA", "Hymn & traditional"),
    ("selah", "Other CCM", "USA", "Hymn & traditional"),
    ("reuben morgan", "Hillsong", "Australia", "Charismatic / CCM"),
    ("maranatha", "Other CCM", "USA", "Charismatic / CCM"),
    ("vertical worship", "Other charismatic", "USA", "Charismatic / CCM"),
    ("charity gayle", "Other charismatic", "USA", "Charismatic / CCM"),
    ("john mark mcmillan", "Other charismatic", "USA", "Charismatic / CCM"),
    ("brian doerksen", "Other CCM", "Canada", "Charismatic / CCM"),
    ("rich mullins", "Other CCM", "USA", "Charismatic / CCM"),
    ("jeremy camp", "Other CCM", "USA", "Charismatic / CCM"),
    ("twila paris", "Other CCM", "USA", "Charismatic / CCM"),
    ("lincoln brewster", "Other CCM", "USA", "Charismatic / CCM"),
    ("phillips, craig", "Other CCM", "USA", "Charismatic / CCM"),
    ("crystal lewis", "Other CCM", "USA", "Charismatic / CCM"),
    ("sara groves", "Other CCM", "USA", "Charismatic / CCM"),
    ("dennis jernigan", "Other CCM", "USA", "Charismatic / CCM"),
    ("gaither", "Other CCM", "USA", "Hymn & traditional"),
    ("keith green", "Other CCM", "USA", "Charismatic / CCM"),
    ("lou fellingham", "Other CCM", "UK & Ireland", "Charismatic / CCM"),
    ("rivers & robots", "Other CCM", "UK & Ireland", "Charismatic / CCM"),
    ("city harvest", "Other charismatic", "Singapore & local", "Charismatic / CCM"),
    ("the crossing", "FMH & partner originals", "Singapore & local", "FMH & local originals"),
    ("edgar", "FMH & partner originals", "Singapore & local", "FMH & local originals"),
    ("fmh", "FMH & partner originals", "Singapore & local", "FMH & local originals"),
]

STREAMS = {
    "reformed-modern": "Reformed modern",
    "hymn-traditional": "Hymn & traditional",
    "charismatic-ccm": "Charismatic / CCM",
    "kids-awesome-cutlery": "Kids",
    "local-original": "FMH & local originals",
}

THEMES = ["Awe", "Cross", "Thanks", "Invitation", "Edify", "Surrender", "Lament",
          "Praise", "Pre-sermon", "Declaration", "Confess", "Assurance"]
THEME_ALIASES = {"thanksgiving": "Thanks", "worship": "Awe", "reverence": "Awe",
                 "confession": "Confess", "trust": "Assurance", "grace": "Cross",
                 "love": "Cross", "humility": "Surrender", "purpose": "Edify",
                 "presermon": "Pre-sermon", "pre sermon": "Pre-sermon"}


def artist_of(song):
    return (song.get("artist") or (song.get("match") or {}).get("artist") or "").lower()


def _artist_row(song):
    a = artist_of(song)
    for needle, family, region, tradition in ARTISTS:
        if needle in a:
            return family, region, tradition
    return None


# ---------- facet functions: (song, today 'YYYY-MM-DD') -> bucket ----------

def f_era(s, today):
    raw = f"{s.get('era', '')} {s.get('lib_era', '')}".lower()
    if "hymn" in raw and "modern" not in raw or "traditional" in raw:
        return "Hymn"
    if "classic" in raw:
        return "Classic (1990s–2000s)"
    if "contemporary" in raw or "modern" in raw:
        return "Contemporary (2010+)"
    if s.get("stream") == "hymn-traditional":
        return "Hymn"
    y = s.get("release_year")
    if y:
        return "Hymn" if y < 1990 else "Classic (1990s–2000s)" if y < 2010 else "Contemporary (2010+)"
    return "Unknown era"


def f_tradition(s, today):
    if s.get("kids"):
        return "Kids"
    if s.get("local"):
        return "FMH & local originals"
    if s.get("stream") in STREAMS:
        return STREAMS[s["stream"]]
    row = _artist_row(s)
    if row:
        return row[2]
    if f_era(s, today) == "Hymn":
        return "Hymn & traditional"
    return "Other / unknown"


def f_theme(s, today):
    for raw in (s.get("theme"), s.get("lib_theme"), s.get("ai_theme")):
        if not raw:
            continue
        r = str(raw).strip().lower()
        for t in THEMES:
            if r == t.lower():
                return t
        if r in THEME_ALIASES:
            return THEME_ALIASES[r]
    return "Untagged"


def f_pace(s, today):
    for raw in (s.get("pace"), s.get("lib_pace"), s.get("ai_pace")):
        r = str(raw or "").strip().lower()
        if r == "slow":
            return "Slow"
        if r in ("medium", "moderate", "mid"):
            return "Medium"
        if r == "fast":
            return "Fast"
    return "Unknown pace"


def f_frequency(s, today):
    n = s.get("count") or 0
    return ("Staple (8+)" if n >= 8 else "Regular (4–7)" if n >= 4 else
            "Occasional (2–3)" if n >= 2 else "Once" if n == 1 else "Not sung 2024–26")


def _months_between(a, b):
    da, db = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    return (db.year - da.year) * 12 + db.month - da.month


def f_recency(s, today):
    if not s.get("last_sung"):
        return "Not since 2024"
    m = _months_between(s["last_sung"], today)
    return "Last 6 months" if m <= 6 else "6–18 months ago" if m <= 18 else "18+ months ago"


def f_first_seen(s, today):
    y = s.get("first_year")
    if not y:
        return "Unknown"
    return ("2014–2016" if y <= 2016 else "2017–2019" if y <= 2019 else
            "2020–2022" if y <= 2022 else "2023–2026")


def f_lifespan(s, today):
    a, b = s.get("first_year"), s.get("last_year")
    if not a:
        return "Unknown"
    span = (b or a) - a + 1
    return "5+ years" if span >= 5 else "2–4 years" if span >= 2 else "Single year"


def f_release_decade(s, today):
    y = s.get("release_year")
    if not y:
        return "Unknown"
    return ("Pre-1990" if y < 1990 else "1990s" if y < 2000 else "2000s" if y < 2010
            else "2010s" if y < 2020 else "2020s")


def f_artist_family(s, today):
    row = _artist_row(s)
    if row:
        return row[0]
    return "Other named artist" if artist_of(s) else "Traditional / unknown"


def f_region(s, today):
    row = _artist_row(s)
    if row:
        return row[1]
    if f_era(s, today) == "Hymn" or s.get("stream") == "hymn-traditional":
        return "Historic hymn writers"
    return UNKNOWN


def f_key(s, today):
    k = str(s.get("latest_key") or s.get("chart_key") or "").strip()
    m = re.match(r"^([A-G])([#b]?)", k)
    if not m:
        return "Key unknown"
    return m.group(1) if not m.group(2) else "Sharp / flat keys"


def f_audience(s, today):
    return "Kids" if s.get("kids") or f_artist_family(s, today) in ("Awesome Cutlery", "Other kids") else "Adult"


def f_spotify(s, today):
    st = s.get("status")
    if st == "on":
        return "Check version" if s.get("reason") else "On playlist"
    return "Not on playlist"


def f_chart(s, today):
    return "Has chord chart" if s.get("has_chart") or "library" in s.get("sources", []) else "No chart in library"


def f_popularity(s, today):
    p = s.get("popularity")
    if p is None:
        return UNKNOWN
    return "Widely known (50+)" if p >= 50 else "Known (25–49)" if p >= 25 else "Niche (<25)"


def f_eric_rating(s, today):
    n = s.get("eric_count")
    if n in (None, ""):
        return "Not on Eric's list"
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "Not on Eric's list"
    return "Eric: 7–10" if n >= 7 else "Eric: 3–6" if n >= 3 else "Eric: 0–2"


def f_introduced(s, today):
    v = str(s.get("introduced") or "").strip().lower()
    if v.startswith("y"):
        return "Introduced"
    if v.startswith("n"):
        return "Not yet introduced"
    return "Not on Eric's list"


def f_coverage(s, today):
    n = len(s.get("sources", []))
    return "4–5 sources" if n >= 4 else "2–3 sources" if n >= 2 else "1 source"


def f_fatigue(s, today):
    return "On fatigue list" if s.get("fatigue") else "Not flagged"


def f_scripture(s, today):
    t = s.get("title", "").lower()
    return "Psalm / scripture in title" if re.search(r"\bpsalm|\bisaiah|\bromans|\bjohn \d", t) else "Other"


def _f(id_, label, fn, buckets, group):
    return {"id": id_, "label": label, "fn": fn, "buckets": buckets, "group": group}


FACETS = [
    _f("era", "Era", f_era, ["Hymn", "Classic (1990s–2000s)", "Contemporary (2010+)", "Unknown era"], "Music"),
    _f("tradition", "Tradition", f_tradition, ["Reformed modern", "Hymn & traditional", "Charismatic / CCM",
                                                "Kids", "FMH & local originals", "Other / unknown"], "Music"),
    _f("theme", "Theme (service role)", f_theme, THEMES + ["Untagged"], "Music"),
    _f("pace", "Pace", f_pace, ["Slow", "Medium", "Fast", "Unknown pace"], "Music"),
    _f("key", "Key (latest played)", f_key, list("CDEFGAB") + ["Sharp / flat keys", "Key unknown"], "Music"),
    _f("artist_family", "Artist / source", f_artist_family, sorted({a[1] for a in ARTISTS})
       + ["Other named artist", "Traditional / unknown"], "Who"),
    _f("region", "Region of origin", f_region, ["Australia", "USA", "UK & Ireland", "Canada", "Singapore & local",
                                                   "Historic hymn writers", UNKNOWN], "Who"),
    _f("release_decade", "Recording decade", f_release_decade,
       ["Pre-1990", "1990s", "2000s", "2010s", "2020s", UNKNOWN], "Who"),
    _f("popularity", "How well known (Spotify)", f_popularity,
       ["Widely known (50+)", "Known (25–49)", "Niche (<25)", UNKNOWN], "Who"),
    _f("frequency", "Times sung 2024–26", f_frequency,
       ["Staple (8+)", "Regular (4–7)", "Occasional (2–3)", "Once", "Not sung 2024–26"], "FMH usage"),
    _f("recency", "Last sung", f_recency, ["Last 6 months", "6–18 months ago", "18+ months ago", "Not since 2024"], "FMH usage"),
    _f("first_seen", "First seen at FMH", f_first_seen, ["2014–2016", "2017–2019", "2020–2022", "2023–2026", "Unknown"], "FMH usage"),
    _f("lifespan", "Years in rotation", f_lifespan, ["5+ years", "2–4 years", "Single year", "Unknown"], "FMH usage"),
    _f("audience", "Audience", f_audience, ["Adult", "Kids"], "FMH usage"),
    _f("fatigue", "Congregation fatigue", f_fatigue, ["On fatigue list", "Not flagged"], "FMH usage"),
    _f("eric_rating", "Eric's rating (1–10)", f_eric_rating, ["Eric: 7–10", "Eric: 3–6", "Eric: 0–2", "Not on Eric's list"], "Eric's list"),
    _f("introduced", "Introduced to FMH?", f_introduced, ["Introduced", "Not yet introduced", "Not on Eric's list"], "Eric's list"),
    _f("coverage", "Records it appears in", f_coverage, ["4–5 sources", "2–3 sources", "1 source"], "Data"),
    _f("chart", "Chord chart", f_chart, ["Has chord chart", "No chart in library"], "Data"),
    _f("spotify", "Spotify", f_spotify, ["On playlist", "Check version", "Not on playlist"], "Data"),
    _f("scripture", "Scripture in title", f_scripture, ["Psalm / scripture in title", "Other"], "Music"),
]


def facet(id_):
    return next(f for f in FACETS if f["id"] == id_)


# ---------- enrichment + render ----------

def enrich(songs):
    """Add stream + fatigue from the history indices."""
    import create_master_playlist as cmp
    canon = cmp.load_parser().canon_key
    with open(os.path.join(HISTORY, "indices", "by-source.json")) as f:
        streams = {canon(t): v.get("stream", "") for t, v in json.load(f).items()}
    fatigue = set()
    with open(os.path.join(HISTORY, "congregation-fatigue.md")) as f:
        for line in f:
            cells = [c.strip() for c in line.split("|")]
            if len(cells) > 3 and cells[1] and cells[1] not in ("Song",) and not cells[1].startswith("-"):
                fatigue.add(canon(cells[1]))
    for s in songs:
        s["stream"] = s.get("stream") or streams.get(s["key"], "")
        s["fatigue"] = s["key"] in fatigue
    return songs


def catalogue_songs(songs):
    """Drop headings the AI flagged and unconfirmed one-word script scraps."""
    import build_master_list as b
    keep = [s for s in songs if not s.get("not_a_song") and b.trusted(s)]
    by_uri = {s["match"]["uri"]: s for s in keep if s.get("status") == "on" and s.get("match")}
    out = []
    for s in keep:
        target = by_uri.get((s.get("match") or {}).get("uri")) if s.get("status") == "dupe" else None
        if target is None:
            out.append(s)
            continue
        # Same recording, different spelling: one song, combined usage.
        target["count"] = (target.get("count") or 0) + (s.get("count") or 0)
        target["script_uses"] = (target.get("script_uses") or 0) + (s.get("script_uses") or 0)
        target["last_sung"] = max(target.get("last_sung") or "", s.get("last_sung") or "")
        years = [y for y in (target.get("first_year"), target.get("last_year"),
                             s.get("first_year"), s.get("last_year")) if y]
        if years:
            target["first_year"], target["last_year"] = min(years), max(years)
        target["sources"] = sorted(set(target["sources"]) | set(s["sources"]))
        for field in ("owners", "year_counts", "roster_leaders"):
            merged = dict(target.get(field) or {})
            for k, v in (s.get(field) or {}).items():
                merged[k] = merged.get(k, 0) + v
            if merged:
                target[field] = merged
        for k, v in s.items():
            if target.get(k) in (None, "") and v not in (None, ""):
                target[k] = v
    return out


TRAD_NAMED = ["Reformed modern", "Hymn & traditional", "Charismatic / CCM", "Kids", "FMH & local originals"]


def _balance(counts):
    """Evenness of the tradition mix, 0 (one tradition) to 100 (all equal)."""
    import math
    vals = [counts.get(t, 0) for t in TRAD_NAMED]
    total = sum(vals)
    if not total:
        return 0
    h = -sum(v / total * math.log(v / total) for v in vals if v)
    return round(100 * h / math.log(len(TRAD_NAMED)))


def chart_data(songs, today, mashups=None):
    """Everything the charts draw, precomputed so the page stays dumb."""
    # Kids' songs repeat for a month by design, so they'd swamp every top-hits list.
    adult = [s for s in songs if f_tradition(s, today) != "Kids"]
    people = {}
    for s in adult:
        totals = dict(s.get("owners") or {})
        for who, n in (s.get("roster_leaders") or {}).items():
            totals[who] = totals.get(who, 0) + n
        for who, n in totals.items():
            people.setdefault(who, []).append({"t": s["title"], "n": n})
    people = {who: sorted(rows, key=lambda r: (-r["n"], r["t"]))[:10]
              for who, rows in people.items()}
    by_year, new_by_year = {}, {}
    for s in songs:
        trad = f_tradition(s, today)
        for y, n in (s.get("year_counts") or {}).items():
            if n:
                by_year.setdefault(y, {})
                by_year[y][trad] = by_year[y].get(trad, 0) + 1
        if s.get("first_year"):
            y = str(s["first_year"])
            new_by_year[y] = new_by_year.get(y, 0) + 1
    top = sorted((s for s in songs if s.get("count")), key=lambda s: (-s["count"], s["title"]))[:15]

    year_top = {}
    for y in by_year:
        rows = [(s["title"], s["year_counts"][y], f_tradition(s, today)) for s in adult
                if (s.get("year_counts") or {}).get(y)]
        rows.sort(key=lambda r: (-r[1], r[0]))
        year_top[y] = [{"t": t, "n": n, "trad": tr} for t, n, tr in rows[:10]]

    # Evergreens: sung in the most different years.
    ever = [(s["title"], sorted(y for y, n in (s.get("year_counts") or {}).items() if n)) for s in songs]
    ever = sorted((e for e in ever if len(e[1]) >= 2), key=lambda e: (-len(e[1]), e[0]))[:10]

    # Gone quiet: 3+ appearances up to 2021, none from 2023.
    def total(s, cond):
        return sum(n for y, n in (s.get("year_counts") or {}).items() if cond(y))
    quiet = [(s["title"], total(s, lambda y: y <= "2021"), f_tradition(s, today)) for s in songs
             if total(s, lambda y: y <= "2021") >= 3 and total(s, lambda y: y >= "2023") == 0]
    quiet.sort(key=lambda r: (-r[1], r[0]))
    people_by_year = {}
    for s in adult:
        for who, ys in (s.get("owner_years") or {}).items():
            for y, n in ys.items():
                people_by_year.setdefault(who, {}).setdefault(y, []).append({"t": s["title"], "n": n})
    for who in people_by_year:
        for y in people_by_year[who]:
            people_by_year[who][y] = sorted(people_by_year[who][y], key=lambda r: (-r["n"], r["t"]))[:10]

    mashups = mashups or []
    vitality = {}
    for y in sorted(by_year):
        sung = [s for s in songs if (s.get("year_counts") or {}).get(y)]
        vitality[y] = {
            "songs": len(sung),
            "new": sum(1 for s in songs if str(s.get("first_year") or "") == y),
            "mashups": sum(m["years"].count(int(y)) for m in mashups),
            "originals": sum(1 for s in sung if s.get("local")),
            "balance": _balance(by_year[y]),
        }

    import collections
    # 2014-15 look small only because fewer scripts were saved; judge from 2016.
    years_full = [y for y in by_year if "2016" <= y < today[:4]]
    ahead = {y: by_year[y].get("Reformed modern", 0) > by_year[y].get("Charismatic / CCM", 0)
             for y in by_year}
    ys = sorted(by_year)
    cross = next((y for i, y in enumerate(ys) if all(ahead[z] for z in ys[i:])), None)
    quiet_year = min(years_full, key=lambda y: (sum(by_year[y].values()), y)) if years_full else None
    keys = collections.Counter(s.get("latest_key") or s.get("chart_key") for s in songs
                               if s.get("latest_key") or s.get("chart_key"))
    story = {
        "crossover_year": cross,
        "quietest_year": quiet_year,
        "quietest_n": sum(by_year[quiet_year].values()) if quiet_year else 0,
        "top_key": keys.most_common(1)[0] if keys else None,
        "keys": keys.most_common(),
        "most_balanced_year": max(years_full, key=lambda y: (_balance(by_year[y]), y)) if years_full else None,
        "one_offs": sum(1 for s in songs if sum((s.get("year_counts") or {}).values()) == 1),
        "total_songs": len(songs),
    }

    return {
        "story": story,
        "people_by_year": people_by_year,
        "vitality": vitality,
        "mashups": mashups,
        "year_top": year_top,
        "evergreens": [{"t": t, "years": len(ys), "first": ys[0], "last": ys[-1]} for t, ys in ever],
        "gone_quiet": [{"t": t, "n": n, "trad": tr} for t, n, tr in quiet[:12]],
        "people": people,
        "by_year": dict(sorted(by_year.items())),
        "new_by_year": dict(sorted(new_by_year.items())),
        "top_sung": [{"t": s["title"], "n": s["count"], "trad": f_tradition(s, today)} for s in top],
    }


def rows_for_page(songs, today):
    # Hymnal-style numbers: each tradition is a "book", numbered A to Z.
    numbers, by_book = {}, {}
    for s in songs:
        by_book.setdefault(f_tradition(s, today), []).append(s)
    for book, items in by_book.items():
        for i, s in enumerate(sorted(items, key=lambda x: re.sub(r"^(the|a|o|oh)\s+", "", x["title"].lower())), 1):
            numbers[id(s)] = i
    out = []
    for s in songs:
        m = s.get("match") or {}
        uri = m.get("uri", "")
        out.append({
            "t": s["title"],
            "a": s.get("artist") or m.get("artist", ""),
            "n": s.get("count") or 0,
            "l": s.get("last_sung", ""),
            "u": f"https://open.spotify.com/track/{uri.split(':')[-1]}" if uri else "",
            "f": {f["id"]: f["fn"](s, today) for f in FACETS},
            "book": f_tradition(s, today),
            "no": numbers[id(s)],
            "h": {"years": s.get("year_counts") or {}, "dates": sorted(s.get("dates") or []),
                  "who": {**(s.get("owners") or {})}, "src": s.get("sources", []),
                  "lead": s.get("roster_leaders") or {}, "key": s.get("chart_key", ""),
                  "keys": s.get("keys_played") or {}, "latest_key": s.get("latest_key", ""),
                  "theme": f_theme(s, today), "pace": f_pace(s, today), "era": f_era(s, today),
                  "first": s.get("first_year"), "last": s.get("last_year"),
                  "rec": (m.get("artist", "") + " · " + m.get("album", "")) if m else "",
                  "held": s.get("reason", "") if s.get("status") != "on" else ""},
        })
    return out


def render(songs, today, playlist_url="", mashups=None):
    data = {
        "today": today,
        "playlist": playlist_url,
        "facets": [{k: f[k] for k in ("id", "label", "buckets", "group")} for f in FACETS],
        "songs": rows_for_page(songs, today),
        "charts": chart_data(songs, today, mashups=mashups),
    }
    with open(os.path.join(HERE, "catalogue_template.html")) as f:
        html = f.read()
    return html.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False))


def main():
    today = dt.date.today().isoformat()
    with open(os.path.join(MASTER, "master-list.json")) as f:
        songs = enrich(catalogue_songs(json.load(f)))
    ids_path = os.path.join(HERE, "master_playlist_ids.json")
    url = ""
    if os.path.exists(ids_path):
        pid = json.load(open(ids_path)).get("all_songs")
        url = f"https://open.spotify.com/playlist/{pid}" if pid else ""
    mash_path = os.path.join(MASTER, "mashups.json")
    mashups = json.load(open(mash_path)) if os.path.exists(mash_path) else []
    out = os.path.join(MASTER, "fmh-song-catalogue.html")
    with open(out, "w") as f:
        f.write(render(songs, today, url, mashups))
    print("Wrote", out)


if __name__ == "__main__":
    main()
