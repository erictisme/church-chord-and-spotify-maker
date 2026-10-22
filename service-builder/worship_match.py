#!/usr/bin/env python3
"""Match FMH song titles to the right Spotify recording.

A bare title search is not safe for this repertoire: "Welcome to the Family"
returns Avenged Sevenfold, "What Love My God" returns 21 Savage. So a match is
only accepted when we can tie it to a worship artist, and every match carries a
confidence level the caller can gate on.

    high    - matched the artist we already knew for this song
    medium  - matched a known worship artist or label, title matches
    low     - nothing worship-shaped found; do not publish without a human look
"""

from __future__ import annotations

import re

from create_spotify_playlist import _is_junk_version

# Artists and labels that actually appear in FMH's repertoire, plus the wider
# worship/hymn publishing world. Substring match, lowercase.
WORSHIP_ARTISTS = {
    # FMH's core sources
    "sovereign grace", "cityalight", "city alight", "emu music", "emu kids",
    "awesome cutlery", "keith & kristyn getty", "keith and kristyn getty",
    "getty", "matt boswell", "matt papa", "shane & shane", "shane and shane",
    "stuart townend", "colin buchanan", "ben slee",
    # Hymn / traditional recordings
    "norton hall", "indelible grace", "hymns of grace", "the corner room",
    "cardiphonia", "reawaken hymns", "page cxvi", "fernando ortega",
    "sandra mccracken", "poor bishop hooper", "the worship initiative",
    "still waters worship", "enfield", "grace music", "doorpost",
    "red mountain", "hymnicity", "the sing team", "greenroom",
    # Contemporary worship
    "hillsong", "elevation worship", "bethel music", "passion", "chris tomlin",
    "matt redman", "phil wickham", "cody carnes", "kari jobe", "brooke ligertwood",
    "vertical worship", "north point", "gateway worship", "jesus culture",
    "housefires", "maverick city", "rend collective", "crowder", "citizens",
    "kings kaleidoscope", "ascend the hill", "aaron keyes", "paul baloche",
    "planetshakers", "all sons & daughters", "all sons and daughters",
    "austin stone", "the porter's gate", "caroline cobb", "ellie holcomb",
    "andrew peterson", "michael w. smith", "don moen", "graham kendrick",
    "dennis jernigan", "delirious", "charity gayle", "benjamin william hastings",
    "cageless birds", "sons of korah", "psalms", "seeds family worship",
    "cedarmont kids", "yancy", "slugs & bugs", "jesus storybook",
    # Generic markers that only ever show up on worship records
    "worship", "hymn", "psalter", "church music", "praise",
}

# Words that mark a recording we never want as the team's reference version.
EXTRA_JUNK = ("cover version", "originally performed", "backing track",
              # Instrumental / mood albums that pass the "worship" marker test.
              "piano worship", "worship piano", "piano hymns", "quiet piano", "hymns piano",
              "guitar hymns", "worship guitar", "guitars in worship", "acoustic guitar worship",
              "soaking", "chill worship", "jazz worship", "calming", "for prayer",
              "quiet time", "heavenly vocals", "lofi", "lo-fi", "study music",
              "worship instrumentals", "peaceful", "for sleep")

# Album names that mean an instrumental record, whoever is credited (hymn
# composers like Fanny Crosby get credited on classical piano albums).
INSTRUMENTAL_ALBUM = re.compile(r"piano|orchestra|on guitar|guitar hymns|instrumental|hymn tunes|\bstrings?\b|"
                                r"classical settings|strings|music box|harp", re.I)

# Markers above that say "worship-shaped" but name no real artist; a track that
# matches only these ranks below one by a named worship artist.
GENERIC_MARKERS = {"worship", "hymn", "psalter", "church music", "praise", "psalms"}
NAMED_ARTISTS = WORSHIP_ARTISTS - GENERIC_MARKERS


def _artists_of(track) -> str:
    return " ".join(a["name"].lower() for a in track["artists"])


def _haystack(track) -> str:
    return f"{track['name']} {track['album']['name']} {_artists_of(track)}".lower()


def is_worship_artist(track) -> bool:
    hay = _haystack(track)
    return any(marker in hay for marker in WORSHIP_ARTISTS)


def is_named_artist(track) -> bool:
    who = f"{_artists_of(track)} {track['album']['name'].lower()}"
    return any(marker in who for marker in NAMED_ARTISTS)


def known_artist_match(track, artist: str) -> bool:
    """Does the track credit an artist we already had on file for this song?"""
    if not artist:
        return False
    wanted = [w.strip().lower() for w in re.split(r"[,/&]|\band\b", artist) if len(w.strip()) > 2]
    have = _artists_of(track)
    return any(w in have for w in wanted)


# British/American and archaic spellings that split the same song in two.
_SPELLING = [
    (r"saviour", "savior"), (r"honour", "honor"), (r"glorious", "glorius"),
    (r"\bthou art\b", "thou are"), (r"\bo\b", "oh"), (r"\btis\b", "it is"),
]


def _title_key(text: str, keep_brackets: bool = False) -> str:
    """Loose title comparison: drop punctuation, bracketed suffixes, leading 'the'."""
    t = text.lower() if keep_brackets else re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", text.lower())
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"^the ", "", t)
    for pattern, replacement in _SPELLING:
        t = re.sub(pattern, replacement, t)
    t = re.sub(r"(?<=[a-z]{3})s\b", "", t)   # sorrows/sorrow, praises/praise
    return re.sub(r"\s+", " ", t).strip()


def _has_phrase(big: str, small: str) -> bool:
    return f" {small} " in f" {big} "


def _title_matches(track_title: str, wanted_key: str) -> bool:
    """Is this track actually the song we asked for?

    Whole-word phrases only, and a one-word fragment never counts: "trust" is
    not "In Whom I Can Trust", and "Trust" is not "Trust In God (feat. ...)".
    """
    tkey = _title_key(track_title)
    if not tkey or not wanted_key:
        return False
    full = _title_key(track_title, keep_brackets=True)      # "Oceans (Where Feet May Fail)"
    head = re.split(r" live\b| acoustic\b| radio\b| feat\b| remaster", tkey)[0].strip()
    if wanted_key in (tkey, full, head):
        return True
    wanted_n = len(wanted_key.split())
    # Our title inside a longer Spotify title: "Come Thou Fount" in "... of Every Blessing".
    if wanted_n >= 2 and any(_has_phrase(t, wanted_key) for t in (tkey, full, head)):
        return True
    # Spotify title inside ours: only when it is nearly all of ours.
    for t in (tkey, head):
        n = len(t.split())
        if n >= 2 and n >= wanted_n - 1 and _has_phrase(wanted_key, t):
            return True
    return False


def find(sp, title: str, artist: str = "") -> dict | None:
    """Search Spotify and return the best worship recording for this title.

    Returns a dict with uri / artist / album / confidence, or None if nothing
    was found at all.
    """
    clean_artist = re.sub(r"\s*\(.*?\)", "", artist).strip()
    # Strip our own disambiguating suffixes before searching: "Sovereign (Tomlin)"
    # searches far better as "Sovereign".
    clean_title = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip() or title

    queries = []
    if clean_artist:
        queries += [
            f'track:"{clean_title}" artist:"{clean_artist}"',
            f"{clean_title} {clean_artist}",
        ]
    queries += [
        f'track:"{clean_title}" worship',
        f"{clean_title} worship",
        f'track:"{clean_title}" hymn',
        clean_title,
    ]

    wanted_key = _title_key(clean_title)
    candidates, seen = [], set()
    for query in queries:
        try:
            items = sp.search(q=query, type="track", limit=20)["tracks"]["items"]
        except Exception:
            continue
        for track in items:
            if track["uri"] in seen:
                continue
            seen.add(track["uri"])
            if (_is_junk_version(track) or any(w in _haystack(track) for w in EXTRA_JUNK)
                    or INSTRUMENTAL_ALBUM.search(track["album"]["name"])):
                continue
            candidates.append(track)

    # Being the right SONG comes first. A worship artist singing something else
    # must never outrank the actual title, so filter before scoring.
    candidates = [t for t in candidates if _title_matches(t["name"], wanted_key)]
    if not candidates:
        return None

    def score(track):
        return (
            known_artist_match(track, clean_artist),
            is_named_artist(track),
            is_worship_artist(track),
            _title_key(track["name"]) == wanted_key,
            track.get("popularity", 0),
        )

    best = max(candidates, key=score)
    known, _, worship, _, _ = score(best)

    if known:
        confidence = "high"
    elif worship:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "uri": best["uri"],
        "name": best["name"],
        "artist": best["artists"][0]["name"],
        "album": best["album"]["name"],
        "confidence": confidence,
    }
