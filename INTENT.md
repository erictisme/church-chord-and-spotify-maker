# INTENT: Church Chord & Spotify Maker

## Purpose
Static web app for church worship song management. Music leader selects songs from a 225+ song library, transposes chords to the right key, and generates formatted Word-ready documents for the team. No backend — runs entirely in the browser from a single `index.html`.

Live at: https://erictisme.github.io/church-chord-and-spotify-maker/

## Status
**Active** — deployed on GitHub Pages, used for weekly worship planning.

## Agent Instructions
- Everything is in `index.html` (~2500 lines). No build process, no dependencies.
- Song library is markdown files in `eric-songs/all-songs/`, indexed by `eric-songs/indices/tsv-catalog.json`.
- Generated documents go in `eric-all-weeks/` and `created-weeks/`.
- Data is fetched from GitHub raw URLs — no backend required.
- Read `CLAUDE.md` for full architecture and data structure before modifying.
- Read `MUSIC-LEADER-INSTRUCTIONS.md` to understand the user-facing workflow.
