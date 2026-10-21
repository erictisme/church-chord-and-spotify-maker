#!/usr/bin/env python3
"""Build the FMH master Spotify playlists from the mined song history.

Two playlists: the adult set (ordered most-sung first) and the kids set.

Artist attribution comes from three places, best first:
  1. the chord-sheet library frontmatter in eric-songs/all-songs/
  2. the roster's own links and comments (publisher domains, "Emu", "Getty"...)
  3. the song title itself ("Sovereign (Tomlin)", "Man of Sorrow - Hillsong")

Anything that still cannot be tied to a worship artist is held back from the
playlist and listed in the report instead of being published on a guess.

Usage:
    python3 create_master_playlist.py --dry-run   # search only, create nothing
    python3 create_master_playlist.py             # create both playlists
"""

import argparse
import glob
import importlib.util
import json
import os
import re

import spotipy
from spotipy.oauth2 import SpotifyOAuth

import worship_match
from create_spotify_playlist import (
    TOKEN_CACHE,
    SCOPE,
    load_spotify_config,
    parse_frontmatter,
)

HERE = os.path.dirname(os.path.abspath(__file__))
SONGS = os.path.abspath(os.path.join(HERE, "..", "eric-songs"))
LIBRARY = os.path.join(SONGS, "all-songs")
HISTORY = os.path.join(SONGS, "history")
FREQ = os.path.join(HISTORY, "indices", "song-frequency.json")
SOURCES = os.path.join(HISTORY, "indices", "by-source.json")
PARSER = os.path.join(HISTORY, "scripts", "parse_history.py")
REPORT = os.path.join(HISTORY, "indices", "spotify-master-report.md")
PLAYLIST_IDS = os.path.join(HERE, "master_playlist_ids.json")

KIDS_STREAM = "kids-awesome-cutlery"
MAX_ADD = 100  # Spotify caps playlist_add_items at 100 URIs per call
PUBLISHABLE = {"high", "medium"}

# Publisher domains and names that appear in the roster's link/comment columns.
ARTIST_HINTS = [
    (r"sovereigngracemusic|sovereign grace", "Sovereign Grace Music"),
    (r"awesomecutlery|awesome cutlery", "Awesome Cutlery"),
    (r"emumusic|\bemu\b", "Emu Music"),
    (r"cityalight|city alight", "CityAlight"),
    (r"\bgetty\b|getty tgc", "Keith & Kristyn Getty"),
    (r"shane and shane|shane & shane", "Shane & Shane"),
    (r"boswell", "Matt Boswell"),
    (r"matt papa|\bpapa\b", "Matt Papa"),
    (r"hillsong", "Hillsong Worship"),
    (r"tomlin", "Chris Tomlin"),
    (r"baloche", "Paul Baloche"),
    (r"planetshakers", "Planetshakers"),
    (r"norton hall", "Norton Hall Band"),
    (r"lenny leblanc", "Lenny LeBlanc"),
    (r"colin buchanan", "Colin Buchanan"),
    (r"elevation", "Elevation Worship"),
]

# Songs written in-house or by a partner church — no commercial recording exists.
LOCAL_MARKERS = (r"fmh original", r"thecrossingchurch", r"\bedgar\b")


def load_parser():
    spec = importlib.util.spec_from_file_location("parse_history", PARSER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def library_artists(canon_key):
    """canon_key(title) -> artist, from the chord-sheet library frontmatter."""
    index = {}
    for name in sorted(os.listdir(LIBRARY)):
        if not name.endswith(".md"):
            continue
        fm = parse_frontmatter(os.path.join(LIBRARY, name))
        if fm.get("title") and fm.get("artist"):
            index.setdefault(canon_key(fm["title"]), fm["artist"])
    return index


def roster_evidence(canon_key):
    """canon_key(title) -> all link/comment text the roster carries for it."""
    evidence = {}
    for path in glob.glob(os.path.join(HISTORY, "parsed", "*.json")):
        with open(path) as f:
            service = json.load(f)
        for song in service["songs"]:
            key = canon_key(song["title"])
            blob = " ".join(filter(None, [song["title"], song.get("link"), song.get("note")]))
            evidence[key] = (evidence.get(key, "") + " " + blob).strip()
    return evidence


def hint_artist(text):
    for pattern, artist in ARTIST_HINTS:
        if re.search(pattern, text, re.I):
            return artist
    return ""


def is_local(text):
    return any(re.search(p, text, re.I) for p in LOCAL_MARKERS)


def load_songs():
    """Return (adult, kids) lists of song dicts, most-sung first."""
    parser = load_parser()
    canon_key = parser.canon_key
    with open(FREQ) as f:
        freq = json.load(f)
    with open(SOURCES) as f:
        sources = json.load(f)

    from_library = library_artists(canon_key)
    evidence = roster_evidence(canon_key)

    adult, kids = [], []
    for title, data in freq.items():
        key = canon_key(title)
        text = evidence.get(key, "")
        stream = sources.get(title, {}).get("stream", "unknown")
        song = {
            "title": title,
            "count": data["count"],
            "last_sung": data.get("last_sung", ""),
            "stream": stream,
            "artist": from_library.get(key) or hint_artist(text),
            "local": stream == "local-original" or is_local(text),
        }
        (kids if stream == KIDS_STREAM else adult).append(song)

    def order(song):
        recency = -int(song["last_sung"].replace("-", "")) if song["last_sung"] else 0
        return (-song["count"], recency, song["title"])

    return sorted(adult, key=order), sorted(kids, key=order)


def resolve(sp, songs, label):
    """Search Spotify for each song. Returns (uris, published, held_back)."""
    print(f"\n=== {label} ({len(songs)} songs) ===")
    uris, published, held = [], [], []
    seen = {}
    for song in songs:
        # Songs written in-house or by a partner church have no commercial
        # release, so any "match" is a different song that happens to share a
        # title. Never search for these.
        if song["local"]:
            reason = "written in-house, no commercial recording exists"
            print(f"  [local] {song['title']} — {reason}")
            held.append({**song, "reason": reason})
            continue

        match = worship_match.find(sp, song["title"], song["artist"])

        if match is None:
            print(f"  [miss] {song['title']} — no Spotify match found")
            held.append({**song, "reason": "no Spotify match found"})
            continue

        row = {**song, "found_artist": match["artist"],
               "found_album": match["album"], "confidence": match["confidence"]}

        if match["confidence"] not in PUBLISHABLE:
            reason = f"only found a non-worship recording ({match['artist']})"
            print(f"  [low]  {song['title']} — {reason}")
            held.append({**row, "reason": reason})
            continue

        if match["uri"] in seen:
            reason = f"same recording as “{seen[match['uri']]}”"
            print(f"  [dupe] {song['title']} — {reason}")
            held.append({**row, "reason": reason})
            continue

        seen[match["uri"]] = song["title"]
        uris.append(match["uri"])
        published.append(row)
        flag = "" if match["confidence"] == "high" else "  (check)"
        print(f"  [ok]   {song['title']} ({song['count']}x) -> {match['artist']}{flag}")

    return uris, published, held


def publish(sp, user_id, key, name, description, uris):
    """Create the playlist, or update it in place if we made it before.

    Updating matters: the link gets shared with the team, so a rebuild must not
    hand back a different URL.
    """
    known = {}
    if os.path.exists(PLAYLIST_IDS):
        with open(PLAYLIST_IDS) as f:
            known = json.load(f)

    playlist_id = known.get(key)
    if playlist_id:
        try:
            sp.playlist_change_details(playlist_id, name=name, description=description)
        except Exception:
            playlist_id = None  # deleted on Spotify's side; fall through and recreate

    if playlist_id:
        # replace_items with the first chunk clears the playlist, then append.
        sp.playlist_replace_items(playlist_id, uris[:MAX_ADD])
        start = MAX_ADD
    else:
        created = sp.user_playlist_create(user=user_id, name=name, public=True,
                                          description=description)
        playlist_id = created["id"]
        start = 0

    for i in range(start, len(uris), MAX_ADD):
        sp.playlist_add_items(playlist_id, uris[i:i + MAX_ADD])

    known[key] = playlist_id
    with open(PLAYLIST_IDS, "w") as f:
        json.dump(known, f, indent=2)

    return sp.playlist(playlist_id)["external_urls"]["spotify"]


def write_report(sections, coverage):
    lines = [
        "# FMH master Spotify playlists — build report",
        "",
        f"Built from {coverage['services']} services, "
        f"{coverage['first']} to {coverage['last']}.",
        "Source: `history/indices/song-frequency.json`. "
        "Rebuild with `service-builder/create_master_playlist.py`.",
        "",
        "Confidence: **high** = matched the artist we had on file. "
        "**check** = matched a known worship artist, but not one we had recorded "
        "for this song, so the version may not be the one FMH sings.",
        "",
    ]
    for label, url, published, held in sections:
        lines += [f"## {label}", ""]
        lines.append(f"- Playlist: {url}" if url else "- Playlist: not created (dry run)")
        lines += [f"- On the playlist: **{len(published)}** · "
                  f"Held back: **{len(held)}**", ""]
        if held:
            lines += ["### Held back — needs a human look", "",
                      "| Song | Times sung | Last sung | Why |", "|---|---|---|---|"]
            for h in sorted(held, key=lambda x: -x["count"]):
                lines.append(f"| {h['title']} | {h['count']} | "
                             f"{h['last_sung'] or '-'} | {h['reason']} |")
            lines.append("")
        lines += ["### On the playlist", "",
                  "| # | Song | Times sung | Matched to | Confidence |",
                  "|---|---|---|---|---|"]
        for i, p in enumerate(published, 1):
            conf = "high" if p["confidence"] == "high" else "check"
            lines.append(f"| {i} | {p['title']} | {p['count']} | "
                         f"{p['found_artist']} | {conf} |")
        lines.append("")
    with open(REPORT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nReport: {REPORT}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="search only, create no playlists")
    args = ap.parse_args()

    adult, kids = load_songs()
    services = sorted(os.path.basename(p)[:-5]
                      for p in glob.glob(os.path.join(HISTORY, "parsed", "*.json")))
    coverage = {"services": len(services), "first": services[0], "last": services[-1]}
    span = f"{coverage['first']} to {coverage['last']}"

    creds = load_spotify_config()
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=creds["client_id"],
        client_secret=creds["client_secret"],
        redirect_uri=creds.get("redirect_uri", "http://localhost:8888/callback"),
        scope=SCOPE,
        cache_path=TOKEN_CACHE,
    ))
    me = sp.current_user()
    print(f"Logged in as: {me['display_name']} ({me['id']})")

    adult_uris, adult_pub, adult_held = resolve(sp, adult, "Adult set")
    kids_uris, kids_pub, kids_held = resolve(sp, kids, "Kids set")

    adult_url = kids_url = None
    if not args.dry_run:
        adult_url = publish(
            sp, me["id"], "adult", "FMH — Songs We Sing",
            f"Every song sung at FMH Sunday services, {span}. Most-sung first.",
            adult_uris,
        )
        kids_url = publish(
            sp, me["id"], "kids", "FMH — Kids' Songs",
            f"Kids' spot songs from FMH Sunday services, {span}.",
            kids_uris,
        )
        print(f"\nAdult playlist: {adult_url}")
        print(f"Kids playlist:  {kids_url}")

    write_report([
        ("Adult set — FMH: Songs We Sing", adult_url, adult_pub, adult_held),
        ("Kids set — FMH: Kids' Songs", kids_url, kids_pub, kids_held),
    ], coverage)


if __name__ == "__main__":
    main()
