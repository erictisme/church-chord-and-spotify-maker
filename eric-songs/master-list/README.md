# FMH master song list

- `fmh-song-catalogue.html` — the catalogue (21 MECE splits + two-way pivot). Published: https://claude.ai/artifact/Ub8bwqkgDWyQwZWVyitEZb
- Spotify: **FMH — Every Song (Master List)** https://open.spotify.com/playlist/7fwwwaURGpXvUE0FIWvnBt (508 tracks, updates in place; roster through 18 Oct 2026)
- `master-list.csv` — every song, its sources, playlist status and why anything was held back
- `ai-tags.json` / `ai-artists.json` — AI-judged theme/pace/original artist for songs Eric hadn't tagged (Eric's list + library tags always win)
- `sources/` — Eric's Song Main List, Edgar's Drive folder, OneDrive scripts (downloaded 21 Oct 2026)

## Rebuild (e.g. after adding the Song & Praise Scripts zip)

    cd service-builder
    mkdir -p /tmp/fmh-scripts && unzip -oq ../eric-songs/master-list/sources/onedrive-scripts-2014-2026.zip -d /tmp/fmh-scripts
    python3 build_master_list.py --main ../eric-songs/master-list/sources/song-main-list.xlsx \
      --edgar-zip ../eric-songs/master-list/sources/edgar-master-list.zip \
      --scripts /tmp/fmh-scripts --scripts ../eric-all-weeks [--scripts <song-and-praise-folder>] \
      --spotify --publish
    python3 catalogue.py
    python3 -m pytest tests -q

New titles get searched; everything else comes from `spotify-match-cache.json`.
New songs with no theme/artist show as Untagged until an AI tagging pass is rerun.
