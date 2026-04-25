#!/usr/bin/env python3
"""Parse FMH worship history into per-service JSON + indices.

Idempotent: wipes parsed/ and indices/ at start of each run.
"""
from __future__ import annotations

import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "pasted-2025-2026.txt"
PARSED_DIR = ROOT / "parsed"
INDICES_DIR = ROOT / "indices"

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

# Slot normalization map — lowercase keys, normalized values
SLOT_MAP = {
    "kids'": "kids",
    "kid's": "kids",
    "kids' spot": "kids",
    "kid's song": "kids",
    "kids": "kids",
    "pre-sermon": "pre-sermon",
    "pre sermon": "pre-sermon",
    "post-communion": "post-communion",
    "post communion": "post-communion",
    "post-sermon": "post-sermon",
    "post sermon": "post-sermon",
    "song of dedication": "dedication",
    "dedication": "dedication",
    "closing": "closing",
}


def normalize_slot(label: str) -> str | None:
    if not label:
        return None
    key = label.strip().lower().rstrip(":")
    return SLOT_MAP.get(key)


def clean_title(raw: str) -> str | None:
    """Clean a song title cell. Return None if it's a placeholder."""
    if not raw:
        return None
    t = raw.strip()
    if not t or t in {"-", "--", "---", "----", "-----", "nil", "—", "–"}:
        return None
    # Strip leading question mark artifacts, trailing whitespace
    return t


# ---------- Fuzzy canonicalization ----------

def canon_key(title: str) -> str:
    """Aggressive normalization for fuzzy matching."""
    t = title.lower()
    # Drop parenthetical and bracketed suffixes
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"\[[^\]]*\]", " ", t)
    # Drop artist suffixes after "-" or "by" or "//"
    t = re.sub(r"\s*[-–—]\s*(hillsong|getty|emu|shane and shane|cityalight|"
               r"matt papa.*|matt boswell.*|sovereign grace|chris tomlin|"
               r"paul baloche|planetshakers|edgar.*|lenny leblanc|getty tgc).*$",
               " ", t)
    t = re.sub(r"\s+by\s+.*$", " ", t)
    t = re.sub(r"//.*$", " ", t)
    # Normalize punctuation — apostrophes just drop (so "god's" -> "gods")
    t = t.replace("'", "").replace("’", "")
    t = t.replace("&", " and ")
    t = re.sub(r"[,.!?;:\"]", " ", t)
    t = re.sub(r"[/]", " ", t)
    # Drop trivial fillers (pad with spaces so leading/trailing words get caught too)
    t = f" {t} "
    for filler in (" the ", " a ", " of ", " my ", " our ", " is ", " in "):
        while filler in t:
            t = t.replace(filler, " ")
    t = t.strip()
    # Collapse whitespace so alias patterns (which use single spaces) can match
    t = re.sub(r"\s+", " ", t)
    # Handle specific aliases / merges
    # (apply post-filler-stripping; keys operate on the normalized token stream)
    aliases = [
        (r"\bim following\b", "im following"),
        (r"\bi am following\b", "im following"),
        # "My hope is built" family — all merge
        (r"\bhope built my hope built\b", "hope built"),
        (r"\bhope built on nothing less\b", "hope built"),
        (r"\bsolid rock\b", "hope built"),
        # Ancient word(s) typo
        (r"\bancient word\b", "ancient words"),
        # King of Kings Majesty typo
        (r"\bking king majesty\b", "king kings majesty"),
        # Oh vs O church
        (r"\boh church arise\b", "o church arise"),
        (r"\boh how good\b", "oh how good"),
        (r"^o how good\b", "oh how good"),
        (r"\bhope built hope built\b", "hope built"),
        (r"\bsilent night lonely night\b", "silent night"),
        (r"\bstanding on promises christ king\b", "standing on promises"),
        (r"^for you alone$", "for you alone are worthy"),
        # "Oh how good it" vs "oh how good it is" (is is stripped as filler — already same)
    ]
    for pat, rep in aliases:
        t = re.sub(pat, rep, t)
    t = re.sub(r"\s+", " ", t).strip()
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


# Preferred canonical titles (nice capitalization).
# Keys MUST match what canon_key() produces — see the 'dump all keys' output
# for authoritative list.
CANONICAL_DISPLAY = {
    # opening / reformed-modern workhorses
    "behold god": "Behold Our God",
    "lord salvation": "The Lord is My Salvation",
    "god for us": "God is For Us",
    "im following king": "I'm Following the King",
    "salvation belongs to god": "Salvation Belongs to Our God",
    "saved soul": "Saved My Soul",
    "all creatures god and king": "All Creatures of Our God and King",
    "christ enough": "Christ is Enough",
    "brick after brick": "Brick after Brick",
    "yet not i but through christ me": "Yet Not I But Through Christ in Me",
    "christ alone": "In Christ Alone",
    "come behold wondrous mystery": "Come Behold the Wondrous Mystery",
    "jesus strong and kind": "Jesus Strong and Kind",
    "hope built": "My Hope is Built on Nothing Less",
    "o praise name": "O Praise the Name (Anastasis)",
    "all i have christ": "All I Have is Christ",
    "christ hope life and death": "Christ Our Hope in Life and Death",
    "we are church": "We Are The Church",
    "beautiful saviour": "Beautiful Saviour",
    "hymn saviour": "Hymn of the Saviour",
    "undivided": "Undivided",
    "oh how good it": "Oh How Good It Is",
    "we are one": "We Are One (Gathered Together)",
    "o church arise": "O Church Arise",
    "let nations be glad": "Let the Nations Be Glad",
    "all sufficient merit": "All Sufficient Merit",
    "crown him with many crowns": "Crown Him with Many Crowns",
    "above all": "Above All",
    "father you are king heaven": "Father You Are King of Heaven",
    "king kings majesty": "King of Kings, Majesty",
    "name above all names": "Name Above All Names",
    "come praise and glorify": "Come Praise and Glorify",
    "his robes for mine": "His Robes For Mine",
    "we declare": "We Declare",
    "this i believe hillsong": "This I Believe (The Creed)",
    "how great god": "How Great is Our God",
    "how great god how great thou art": "How Great is Our God / How Great Thou Art",
    "come thou fount every blessing nothing but blood jesus": "Come Thou Fount / Nothing But The Blood",
    "near cross": "Near the Cross",
    "how deep fathers love for us": "How Deep the Father's Love For Us",
    "jesus paid it all": "Jesus Paid It All",
    "resurrecting": "Resurrecting",
    "god speaks": "God Speaks",
    "for you alone are worthy": "For You Alone Are Worthy",
    "jesus i cross have taken": "Jesus, I My Cross Have Taken",
    "grace awaiting me": "Grace Awaiting Me",
    "his mercy more": "His Mercy is More",
    "jesus came to earth": "Jesus Came To Earth",
    "love god": "The Love of God",
    "speak o lord": "Speak O Lord",
    "be thou vision": "Be Thou My Vision",
    "man sorrow": "Man of Sorrow (Hillsong)",
    "rejoice": "Rejoice",
    "blessed assurance": "Blessed Assurance",
    "gods great family": "God's Great Family",
    "to god be glory": "To God Be the Glory",
    "oh deep deep love jesus": "Oh the Deep, Deep Love of Jesus",
    "praise to lord almighty": "Praise to the Lord, the Almighty",
    "i give you heart": "I Give You My Heart",
    "i have decided to follow jesus": "I Have Decided to Follow Jesus",
    "lay me down": "Lay Me Down",
    "take life and let it be": "Take My Life and Let It Be",
    "this life i live": "This Life I Live",
    "w-i-s-d-o-m": "W-I-S-D-O-M",
    "all hail power jesus name": "All Hail the Power of Jesus' Name",
    "christ be magnified": "Christ Be Magnified",
    "turn your eyes": "Turn Your Eyes",
    "your word": "Your Word",
    "this amazing grace": "This Is Amazing Grace",
    "what grace mine": "What Grace is Mine",
    "his glory and good": "His Glory and My Good",
    "ancient words": "Ancient Words",
    "tis so sweet": "'Tis So Sweet",
    "day": "Day By Day",
    "amazing grace": "Amazing Grace",
    "how great thou art": "How Great Thou Art",
    "sovereign": "Sovereign (Tomlin)",
    "immortal invisible god only wise": "Immortal, Invisible, God Only Wise",
    "before throne god above": "Before the Throne of God Above",
    "10 000 reasons": "10,000 Reasons",
    "i stand amazed": "I Stand Amazed",
    "psalm 23": "Psalm 23",
    "psalm 34": "Psalm 34 (Taste and See)",
    "i will trust saviour jesus": "I Will Trust My Saviour Jesus",
    "joy to world": "Joy to the World",
    "hark herald angels sing": "Hark! The Herald Angels Sing",
    "o holy night": "O Holy Night",
    "joy christmas": "The Joy of Christmas",
    "this book": "In This Book",
    "calling all sinners": "Calling All Sinners",
    "just way god wanted us to be": "Just the Way God Wanted Us to Be",
    "standing on promises": "Standing on the Promises",
    "majesty": "Majesty",
    "there fountain": "There is a Fountain",
    "thank you jesus": "Thank You Jesus",
    "god very very very big god": "My God Is A Very, Very, Very Big God",
    "build life": "Build My Life",
    "i surrender all": "I Surrender All",
    "servant king": "The Servant King",
    "king all his beauty": "The King in All His Beauty",
    "mighty mighty saviour": "Mighty, Mighty Saviour",
    "shepherd soul": "Shepherd of My Soul",
    "grace and peace": "Grace and Peace (Sovereign Grace)",
    "we give thanks": "We Give Thanks",
    "only holy god": "Only a Holy God",
    "holy holy holy": "Holy Holy Holy",
    "more like jesus": "More Like Jesus",
    "jesus loves me": "Jesus Loves Me",
    "goodness jesus": "The Goodness of Jesus",
    "power cross": "Power of the Cross",
    "because he lives": "Because He Lives",
    "see what morning": "See What A Morning",
    "come thou fount every blessing": "Come Thou Fount of Every Blessing",
    "great thy faithfulness": "Great is Thy Faithfulness",
    "to be like jesus": "To Be Like Jesus",
    "good good father": "Good Good Father",
    "trust and obey": "Trust and Obey",
    "guide me o great redeemer": "Guide Me, O My Great Redeemer",
    "you are all all": "You Are My All in All",
    "this fathers world": "This Is My Father's World",
    "welcome to family": "Welcome to the Family",
    "adopted": "Adopted",
    "he will hold me fast": "He Will Hold Me Fast",
    "here love": "Here is Love",
    "what love god": "What Love My God",
    "o great god": "O Great God",
    "tell them": "Tell Them",
    "refiners fire": "Refiner's Fire",
    "risen": "Risen (The Crossing)",
    "king kings": "King of Kings (Hillsong)",
    "jesus reigns": "Jesus Reigns (Edgar)",
    "indescribable": "Indescribable",
    "when i survey wondrous cross": "When I Survey the Wondrous Cross",
    "he lives": "He Lives",
    "heavens home": "Heaven's Home",
    "god omniscient god all knowing": "God Omniscient, God All Knowing",
    "goodness god": "Goodness of God",
    "all world for jesus": "All the World for Jesus",
    "more precious than gold": "More Precious Than Gold (Psalm 19)",
    "hes coming back again": "He's Coming Back Again",
    "living hope": "Living Hope",
    "facing task unfinished": "Facing a Task Unfinished",
    "you are god alone": "You Are God Alone",
    "it came upon midnight clear": "It Came Upon A Midnight Clear",
    "o come all you unfaithful": "O Come, All You Unfaithful",
    "silent night": "Silent Night",
    "into deep": "Into the Deep",
    "king king majesty": "King of Kings, Majesty",  # typo merge
}


def canonical_title(display_candidates: list[str], key: str) -> str:
    if key in CANONICAL_DISPLAY:
        return CANONICAL_DISPLAY[key]
    # Fall back to longest cleaned candidate with title case preserved
    # Pick the one with the fewest non-alpha trailing chars
    best = max(display_candidates, key=lambda s: (len(s), s))
    return best


# ---------- Date parsing ----------

def infer_year(section_label: str, idx_in_section: int, month: int, prev_month: int | None) -> int:
    """Infer year for a service.

    Section '2026' first section layout (empirically):
      Jan-Apr 2026 (actual, current), then Jul-Dec 2024 (historical) appears in
      SAME section because Eric grouped past Eph/Gen series with forward plan.
      But within the section entries go: Jan..Apr (2026), then Jul..Dec (2024).

    Section '2025' section: Jan-Dec 2025.
    """
    # Default handled by caller; this helper is unused now; kept for clarity.
    return 0


# ---------- Main parse ----------

def parse() -> tuple[list[dict], list[str]]:
    text = RAW.read_text(encoding="utf-8")
    lines = text.split("\n")

    warnings: list[str] = []
    services: list[dict] = []

    # Split into sections by '# 2026' / '# 2025' markers and ↓2025↓
    # Strategy: iterate line by line, track current section + current service block.
    # Sections:
    #   "y2026"  — first header "# 2026", covers Jan-Apr 2026 actual services
    #   "y2024"  — "# 2025" header section, actually 2024 historical (Eph + Gen 37-48)
    #              confirmed by passages: Eph series Jul-Sep, Gen 37-48 Sep-Dec 2024
    #   "y2025"  — after "↓2025↓" marker, full 2025 year
    current_section = None
    # For the first section we'll assign years based on month transitions:
    # Months in order: Jan-Apr -> 2026, then Jul-Dec -> 2024.
    # We'll track: within first section, once we see a month < previous month AND
    # the new month is Jul, flip to 2024.

    # For 2025 section: all months 2025, unless month jumps backward (then next year 2026), unlikely here.

    current = None  # dict being built
    prev_month_first = None
    year_first = 2026  # start assumption for first section
    prev_month_2025 = None
    year_2025 = 2025

    def finalize(svc):
        if svc and svc.get("date"):
            services.append(svc)

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        if not line.strip():
            continue
        if line.startswith("#"):
            # comment / section header
            if line.strip() == "# 2026":
                current_section = "y2026"
            elif line.strip() == "# 2025":
                # Despite label, content is 2024 historical (Eph + Gen 37-48)
                current_section = "y2024"
            continue
        if line.startswith("↓2025↓"):
            current_section = "y2025"
            continue

        # Tab split
        cells = line.split("\t")
        first = cells[0].strip() if cells else ""

        if first == "Date":
            # Finalize previous
            finalize(current)
            current = None

            # cells: ["Date", "<day> <mon>", "<passage>", ...]
            if len(cells) < 2:
                warnings.append(f"Date row with <2 cells: {line!r}")
                continue
            date_cell = cells[1].strip()
            passage = cells[2].strip() if len(cells) > 2 else ""

            # date_cell forms: "4 Jan", "3 Apr (Good Friday)", "18 Apr"
            m = re.match(r"^\s*(\d{1,2})\s+([A-Za-z]{3})", date_cell)
            if not m:
                warnings.append(f"Unparseable date cell: {date_cell!r}")
                continue
            day = int(m.group(1))
            mon_str = m.group(2).capitalize()
            if mon_str not in MONTHS:
                warnings.append(f"Unknown month abbrev: {mon_str!r}")
                continue
            month = MONTHS[mon_str]

            # Year inference
            if current_section == "y2026":
                year = 2026
            elif current_section == "y2024":
                year = 2024
            elif current_section == "y2025":
                year = 2025
            else:
                year = 2026  # fallback

            try:
                d = date(year, month, day)
            except ValueError as e:
                warnings.append(f"Bad date {year}-{month}-{day}: {e}")
                continue

            current = {
                "date": d.isoformat(),
                "passage": passage,
                "theme": None,
                "songs": [],
                "_seen_opening": 0,
            }
            continue

        if current is None:
            # Row outside a service block (headers like 'Theme\tSongs\tLink...')
            continue

        # Header row: "Theme\tSongs..." signals theme row follows? Actually the "Theme" row IS a header.
        if first == "Theme":
            continue

        # If first column is non-empty and we haven't captured theme yet, it's the theme row
        # Theme row layout:
        #   col0 = theme text, col1 = "" , col2 = song title (or empty), col3 = link, ...
        # Subsequent song rows:
        #   col0 = "" , col1 = slot label (or empty for 2nd opening), col2 = song title, ...
        #
        # So: row with a non-empty col0 is the theme row.

        if first and current["theme"] is None:
            current["theme"] = first
            # Also this row may contain the first opening song in col2
            title = clean_title(cells[2]) if len(cells) > 2 else None
            link = cells[3].strip() if len(cells) > 3 and cells[3].strip() else None
            note = None
            if len(cells) > 4 and cells[4].strip():
                note = cells[4].strip()
            if len(cells) > 5 and cells[5].strip():
                note = (note + " | " if note else "") + cells[5].strip()
            if title:
                current["songs"].append({
                    "slot": "opening",
                    "title": title,
                    "link": link if link and link.startswith("http") else None,
                    "note": note,
                })
                current["_seen_opening"] += 1
            continue

        # Non-theme row (first cell empty). Parse slot + title.
        if first:
            # Unexpected — a second 'themish' row? treat as warning but try to continue
            warnings.append(f"Unexpected non-empty col0 mid-service on {current['date']}: {line!r}")
            continue

        slot_cell = cells[1].strip() if len(cells) > 1 else ""
        title_cell = cells[2].strip() if len(cells) > 2 else ""
        link_cell = cells[3].strip() if len(cells) > 3 else ""
        note_parts = []
        for extra in cells[4:]:
            s = extra.strip()
            if s:
                note_parts.append(s)
        note = " | ".join(note_parts) if note_parts else None

        title = clean_title(title_cell)
        link = link_cell if link_cell.startswith("http") else None

        normalized_slot = normalize_slot(slot_cell)

        if not slot_cell and title:
            # 2nd opening song (or 3rd) — indented extra opening
            normalized_slot = "opening"
            current["_seen_opening"] += 1
        elif not title and not normalized_slot:
            # Empty row inside the block — skip
            continue
        elif not normalized_slot and slot_cell:
            warnings.append(f"Unknown slot label on {current['date']}: {slot_cell!r}")
            normalized_slot = slot_cell.strip().lower()

        if not title:
            # slot label present but no song (placeholder row like "-") — skip
            continue

        current["songs"].append({
            "slot": normalized_slot or "unknown",
            "title": title,
            "link": link,
            "note": note,
        })

    finalize(current)

    # Clean up helper field
    for s in services:
        s.pop("_seen_opening", None)

    return services, warnings


# ---------- Source tagging ----------

REFORMED_MODERN = {
    "christ alone", "yet not i but through christ me",
    "his glory and good", "come behold wondrous mystery",
    "only holy god", "come praise and glorify", "all i have christ",
    "his mercy more", "lord salvation", "christ hope life and death",
    "let nations be glad", "o church arise",
    "king all his beauty", "behold god",
    "all sufficient merit", "grace awaiting me", "hymn saviour",
    "we declare", "god for us", "saved soul", "turn your eyes",
    "christ be magnified", "what grace mine",
    "christ enough", "o praise name", "rejoice",
    "jesus strong and kind", "his robes for mine",
    "calling all sinners", "i will trust saviour jesus",
    "grace and peace", "speak o lord",
    "more like jesus", "goodness jesus", "power cross",
    "see what morning", "oh deep deep love jesus",
    "before throne god above", "o great god", "he will hold me fast",
    "what love god", "your word", "o come all you unfaithful",
    "name above all names", "king kings majesty", "king king majesty",
    "jesus paid it all",  # Papa
    "shepherd soul",
    "psalm 23", "psalm 34",
    "ancient words", "ancient word",  # typo variant
    "this book", "we give thanks",
    "hope built",
    "facing task unfinished", "more precious than gold",
    "come thou fount every blessing nothing but blood jesus",
    "for you alone are worthy",
    "joy christmas",
    "thank you jesus",
    "into deep",
    "salvation belongs to god",
    "this life i live",
    "oh how good it",  # "Oh How Good It Is" — Getty
}

HYMN_TRADITIONAL = {
    "crown him with many crowns", "how great thou art", "holy holy holy",
    "amazing grace", "be thou vision", "praise to lord almighty",
    "great thy faithfulness", "come thou fount every blessing",
    "blessed assurance", "when i survey wondrous cross",
    "joy to world",
    "hark herald angels sing", "o holy night", "silent night",
    "all creatures god and king", "all hail power jesus name",
    "immortal invisible god only wise", "love god",
    "there fountain", "take life and let it be",
    "standing on promises", "because he lives",
    "i surrender all", "trust and obey", "day",
    "i stand amazed", "tis so sweet", "near cross",
    "to god be glory",
    "jesus i cross have taken", "guide me o great redeemer",
    "this fathers world", "he lives",
    "how deep fathers love for us", "majesty",
    "i have decided to follow jesus",
    "here love", "it came upon midnight clear",
    "you are god alone",
    "how great god how great thou art",  # compound hymn medley
    "all world for jesus",
}

CHARISMATIC_CCM = {
    "above all", "king kings",  # King of Kings Hillsong
    "good good father", "build life", "goodness god",
    "this amazing grace", "10 000 reasons",
    "living hope", "how great god", "indescribable",
    "sovereign",
    "this i believe hillsong", "man sorrow",
    "refiners fire", "i give you heart", "you are all all",
    "resurrecting",
    "lay me down",
    "beautiful saviour",  # often Planetshakers arrangement
    "servant king",       # Graham Kendrick
    "welcome to family",  # CCM
}

# Kids — Awesome Cutlery / Emu Kids / similar
KIDS_AWESOME = {
    "brick after brick", "we are church",
    "father you are king heaven", "jesus came to earth",
    "gods great family", "w-i-s-d-o-m",
    "just way god wanted us to be",
    "god very very very big god",
    "mighty mighty saviour", "to be like jesus",
    "jesus loves me", "adopted", "tell them",
    "heavens home", "hes coming back again",
    "im following king",
    "god speaks",
}

LOCAL_ORIGINAL = {
    "we are one",
    "jesus reigns",
    "risen",  # thecrossingchurch — FMH-local/related
    "undivided",
}


def tag_source(canon_display: str, key: str) -> tuple[str, bool]:
    if key in KIDS_AWESOME:
        return "kids-awesome-cutlery", False
    if key in LOCAL_ORIGINAL:
        return "local-original", False
    if key in REFORMED_MODERN:
        return "reformed-modern", False
    if key in HYMN_TRADITIONAL:
        return "hymn-traditional", False
    if key in CHARISMATIC_CCM:
        return "charismatic-ccm", False

    # Heuristics for anything not in explicit lists
    lower = canon_display.lower()
    if any(kw in lower for kw in ["hillsong", "elevation", "bethel",
                                   "tomlin", "planetshakers", "passion",
                                   "lenny leblanc", "baloche"]):
        return "charismatic-ccm", False
    if any(kw in lower for kw in ["getty", "cityalight", "sovereign grace",
                                   "emu", "boswell", "papa", "shane and shane",
                                   "norton hall"]):
        return "reformed-modern", False

    return "unknown", True


# ---------- Build indices ----------

def build_indices(services: list[dict]):
    # Song frequency with fuzzy merge
    groups: dict[str, dict] = {}
    for svc in services:
        for song in svc["songs"]:
            title = song["title"]
            k = canon_key(title)
            if not k:
                continue
            g = groups.setdefault(k, {
                "canonical_title": None,
                "variants": [],
                "count": 0,
                "dates": [],
                "slots": Counter(),
                "_display_candidates": [],
            })
            if title not in g["variants"]:
                g["variants"].append(title)
            g["_display_candidates"].append(title)
            g["count"] += 1
            g["dates"].append(svc["date"])
            slot = song["slot"] or "unknown"
            g["slots"][slot] += 1

    # Finalize
    freq_out = {}
    source_out = {}
    for k, g in groups.items():
        canon = canonical_title(g["_display_candidates"], k)
        g["canonical_title"] = canon
        g["dates"] = sorted(set(g["dates"]))
        g["last_sung"] = g["dates"][-1]
        g["slots"] = dict(g["slots"])
        g.pop("_display_candidates")
        freq_out[canon] = g

        stream, needs_review = tag_source(canon, k)
        source_out[canon] = {"stream": stream, "needs_review": needs_review}

    return freq_out, source_out


# ---------- Summary ----------

def build_summary(services, freq, sources, warnings) -> str:
    total = len(services)
    earliest = min((s["date"] for s in services), default="N/A")
    latest = max((s["date"] for s in services), default="N/A")

    # Top 20
    sorted_songs = sorted(freq.items(), key=lambda kv: (-kv[1]["count"], kv[0]))
    top20 = sorted_songs[:20]

    # Stream distribution (by distinct-song-appearance-count across services)
    stream_appearances = Counter()
    for title, data in freq.items():
        stream = sources[title]["stream"]
        stream_appearances[stream] += data["count"]
    total_appearances = sum(stream_appearances.values()) or 1

    # Over-used watchlist (>=5)
    over_used = [(t, d) for t, d in sorted_songs if d["count"] >= 5]

    # Rested: sung once, >6 months ago from today (2026-04-21)
    from datetime import date as _date
    today = _date(2026, 4, 21)
    rested = []
    for t, d in sorted_songs:
        if d["count"] == 1:
            last = _date.fromisoformat(d["last_sung"])
            days = (today - last).days
            if days > 183:
                rested.append((t, d["last_sung"], days))
    rested.sort(key=lambda x: x[1])

    # Charismatic gap
    charismatic_songs = [(t, d) for t, d in sorted_songs
                         if sources[t]["stream"] == "charismatic-ccm"]

    # Needs review
    review_list = [t for t, s in sources.items() if s["needs_review"]]

    lines = []
    lines.append(f"# FMH Worship History Summary")
    lines.append("")
    lines.append(f"- Total services parsed: **{total}**")
    lines.append(f"- Date range: **{earliest}** → **{latest}**")
    lines.append(f"- Distinct songs: **{len(freq)}**")
    lines.append(f"- Total song appearances: **{total_appearances}**")
    lines.append("")

    lines.append("## Top 20 Most-Sung Songs")
    lines.append("")
    lines.append("| # | Title | Count | Last Sung |")
    lines.append("|---|-------|-------|-----------|")
    for i, (t, d) in enumerate(top20, 1):
        lines.append(f"| {i} | {t} | {d['count']} | {d['last_sung']} |")
    lines.append("")

    lines.append("## Stream Distribution (by appearance)")
    lines.append("")
    lines.append("| Stream | Appearances | % |")
    lines.append("|--------|-------------|---|")
    for stream in ["reformed-modern", "hymn-traditional", "charismatic-ccm",
                   "kids-awesome-cutlery", "local-original", "unknown"]:
        n = stream_appearances.get(stream, 0)
        pct = 100.0 * n / total_appearances
        lines.append(f"| {stream} | {n} | {pct:.1f}% |")
    lines.append("")

    lines.append("## Over-used Watchlist (5+ appearances)")
    lines.append("")
    if not over_used:
        lines.append("_None._")
    else:
        for t, d in over_used:
            lines.append(f"- **{t}** — {d['count']} times (last: {d['last_sung']})")
    lines.append("")

    lines.append("## Rested Songs (sung once, >6 months ago)")
    lines.append("")
    lines.append("Candidates to bring back. Reference date = 2026-04-21.")
    lines.append("")
    if not rested:
        lines.append("_None._")
    else:
        for t, last, days in rested[:40]:
            lines.append(f"- **{t}** — last sung {last} ({days} days ago)")
        if len(rested) > 40:
            lines.append(f"- …and {len(rested)-40} more.")
    lines.append("")

    lines.append("## Charismatic / CCM Gap")
    lines.append("")
    if not charismatic_songs:
        lines.append("_No charismatic-ccm songs detected._")
    else:
        lines.append("| Title | Count | Last Sung |")
        lines.append("|-------|-------|-----------|")
        for t, d in charismatic_songs:
            lines.append(f"| {t} | {d['count']} | {d['last_sung']} |")
    lines.append("")

    lines.append("## Songs Flagged for Review")
    lines.append("")
    if not review_list:
        lines.append("_None._")
    else:
        for t in sorted(review_list):
            lines.append(f"- {t}")
    lines.append("")

    lines.append("## Parsing Warnings")
    lines.append("")
    if not warnings:
        lines.append("_None._")
    else:
        for w in warnings:
            lines.append(f"- {w}")
    lines.append("")

    return "\n".join(lines)


# ---------- Main ----------

def main():
    # Wipe
    if PARSED_DIR.exists():
        shutil.rmtree(PARSED_DIR)
    if INDICES_DIR.exists():
        shutil.rmtree(INDICES_DIR)
    PARSED_DIR.mkdir(parents=True)
    INDICES_DIR.mkdir(parents=True)

    services, warnings = parse()

    for svc in services:
        out = PARSED_DIR / f"{svc['date']}.json"
        out.write_text(json.dumps(svc, indent=2, ensure_ascii=False), encoding="utf-8")

    freq, sources = build_indices(services)

    (INDICES_DIR / "song-frequency.json").write_text(
        json.dumps(freq, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (INDICES_DIR / "by-source.json").write_text(
        json.dumps(sources, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    summary = build_summary(services, freq, sources, warnings)
    (INDICES_DIR / "summary.md").write_text(summary, encoding="utf-8")

    print(f"Parsed {len(services)} services.")
    print(f"Warnings: {len(warnings)}")
    if warnings:
        for w in warnings[:10]:
            print(f"  ! {w}")


if __name__ == "__main__":
    main()
