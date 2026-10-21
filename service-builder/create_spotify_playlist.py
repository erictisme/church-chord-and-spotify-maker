#!/usr/bin/env python3
"""Create a Spotify playlist from a week config.

Usage:
    python3 create_spotify_playlist.py weeks/2026-06-21.json

First-time setup: fill in service-builder/spotify_config.json with your
Spotify app credentials (see /spotify-playlist skill for setup steps).
"""

import json
import os
import re
import sys

import spotipy
from spotipy.oauth2 import SpotifyOAuth

HERE = os.path.dirname(os.path.abspath(__file__))
LIBRARY = os.path.join(HERE, "..", "eric-songs", "all-songs")
CONFIG_PATH = os.path.join(HERE, "spotify_config.json")
TOKEN_CACHE = os.path.join(HERE, ".spotify_token_cache")
SCOPE = "playlist-modify-public playlist-modify-private"


def load_spotify_config():
    if not os.path.exists(CONFIG_PATH):
        print("ERROR: spotify_config.json not found.")
        print(f"Create it at: {CONFIG_PATH}")
        print('Template: {"client_id": "...", "client_secret": "...", "redirect_uri": "http://localhost:8888/callback"}')
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def parse_frontmatter(path):
    with open(path) as f:
        text = f.read()
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


# Versions we never want as the team's reference recording: sleep/ambient
# remixes, karaoke, instrumental covers, tribute acts. The original never carries
# these words. NOTE "live" and "acoustic" are legit versions, so they are NOT here.
JUNK_VERSION_WORDS = [
    "sleep", "relaxation", "lullaby", "lullabies", "instrumental",
    "karaoke", "music box", "meditation", "ambient", "8-bit", "8 bit",
    "made famous", "made popular", "in the style of", "tribute",
    "rain sound", "white noise", "piano tribute",
]


def _haystack(track):
    parts = [track["name"], track["album"]["name"]] + [a["name"] for a in track["artists"]]
    return " ".join(parts).lower()


def _is_junk_version(track):
    return any(w in _haystack(track) for w in JUNK_VERSION_WORDS)


def _artist_matches(track, clean_artist):
    wanted = [w.strip().lower() for w in re.split(r"[,/&]", clean_artist) if w.strip()]
    if not wanted:
        return False
    have = " ".join(a["name"].lower() for a in track["artists"])
    return any(w in have for w in wanted)


def search_track(sp, title, artist):
    """Search Spotify and return the ORIGINAL recording, not a sleep/karaoke/
    instrumental clone. Returns (uri, artist, album) or (None, None, None)."""
    clean_artist = re.sub(r"\s*\(.*?\)", "", artist).strip()
    queries = [
        f'track:"{title}" artist:"{clean_artist}"',
        f'"{title}" {clean_artist}',
        f"{title} {clean_artist}",
        f"{title} worship",
    ]
    title_l = title.lower()

    def rank(t):
        # Higher tuple wins: real artist > exact title > more popular.
        return (_artist_matches(t, clean_artist), t["name"].lower() == title_l, t.get("popularity", 0))

    fallback = None
    for query in queries:
        try:
            tracks = sp.search(q=query, type="track", limit=20)["tracks"]["items"]
        except Exception:
            continue
        if not tracks:
            continue
        real = [t for t in tracks if not _is_junk_version(t)]
        if real:
            best = max(real, key=rank)
            return best["uri"], best["artists"][0]["name"], best["album"]["name"]
        if fallback is None:
            fallback = tracks[0]  # everything looked like a clone; remember one just in case
    if fallback:
        return fallback["uri"], fallback["artists"][0]["name"], fallback["album"]["name"]
    return None, None, None


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 create_spotify_playlist.py weeks/YYYY-MM-DD.json")
        sys.exit(1)

    arg = sys.argv[1]
    config_path = arg if os.path.isabs(arg) else os.path.join(HERE, arg)
    with open(config_path) as f:
        config = json.load(f)

    display_date = config["display_date"]
    playlist_name = f"FMH {display_date}"

    creds = load_spotify_config()
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=creds["client_id"],
        client_secret=creds["client_secret"],
        redirect_uri=creds.get("redirect_uri", "http://localhost:8888/callback"),
        scope=SCOPE,
        cache_path=TOKEN_CACHE,
    ))

    me = sp.current_user()
    print(f"Logged in as: {me['display_name']} ({me['id']})\n")

    uris = []
    not_found = []
    for slot in config["slots"]:
        section = slot.get("section", "")

        song_path = os.path.join(LIBRARY, slot["file"])
        if not os.path.exists(song_path):
            print(f"  [skip] File not in library: {slot['file']}")
            not_found.append(slot["file"])
            continue

        fm = parse_frontmatter(song_path)
        title = fm.get("title", slot["file"])
        artist = fm.get("artist", "")

        uri, found_artist, found_album = search_track(sp, title, artist)
        if uri:
            uris.append(uri)
            print(f"  [ok]   {title}  →  {found_artist} / {found_album}")
        else:
            print(f"  [miss] {title} by {artist}")
            not_found.append(title)

    if not uris:
        print("\nNo tracks found on Spotify — playlist not created.")
        sys.exit(1)

    playlist = sp.user_playlist_create(
        user=me["id"],
        name=playlist_name,
        public=True,
        description=f"FMH worship set — {display_date}. Theme: {config.get('theme', '')}",
    )
    sp.playlist_add_items(playlist["id"], uris)

    url = playlist["external_urls"]["spotify"]
    print(f"\nPlaylist created: {url}")
    if not_found:
        print(f"Not on Spotify (add manually if needed): {', '.join(not_found)}")

    return url


if __name__ == "__main__":
    main()
