# FMH Worship Prep — Actual Flow (observed 25 Apr 2026)

This is what Eric actually does each week. The app already covers ~60% of it but has friction points that push him back to manual. Documented after watching the 26 Apr 2026 prep go fully manual despite the app existing.

## Inputs

1. **WhatsApp from Marcus (worship pastor)** — usually contains:
   - Theme (e.g. "Christ is above all")
   - Passage (e.g. Matthew 8:23-9:8)
   - 2-3 suggested songs (opener, kids, closer typically)
2. **Eric's own taste** — fills the remaining slots, often pulling from past services he led
3. **Past chord sheets** — FMH Drive folder with hundreds of past worship docs (key/format he likes)
4. **Ultimate Guitar** — fallback for songs not in his library or when he wants a different version

## Steps Eric takes manually

| # | Step | Tool used today | App equivalent |
|---|------|-----------------|----------------|
| 1 | Read Marcus's WhatsApp, draft set list | WhatsApp + brain | ❌ no ingest path |
| 2 | Negotiate set with Marcus (e.g. Still vs Cornerstone) | WhatsApp | ❌ |
| 3 | Lock final 5 songs | brain | ❌ |
| 4 | Open new Google Doc, name it `<service date>` | docs.google.com | ❌ generates plaintext for copy-paste |
| 5 | Format → 2 columns | Doc menu | ✅ app has 2-col preview |
| 6 | For each song: search FMH Drive folder for past chord sheet, copy/paste | Drive search | ⚠️ partial — app has 225 songs but not all of his Drive past charts |
| 7 | For songs not in Drive: Ultimate Guitar → copy chord block | tabs.ultimate-guitar.com | ✅ app has UG import |
| 8 | Paste into Doc, adjust spacing (monospace), tweak key if needed | manual | ✅ app handles transposition |
| 9 | Add header: passage + numbered set list at top | manual typing | ✅ app generates header |
| 10 | Share → "Anyone with link, viewer" → copy link | Doc share dialog | ❌ no Doc API integration |
| 11 | Open Spotify → New playlist `<service date>` | open.spotify.com | ✅ app has Spotify OAuth + create playlist |
| 12 | Search each song, add to playlist, copy share link | Spotify UI | ✅ app does this |
| 13 | WhatsApp the team: doc link + Spotify link + prac confirmation | WhatsApp | ❌ |

## Why he goes manual despite the app existing

Three friction points, ranked by frequency:

1. **No Google Doc creation** — biggest gap. The app outputs plaintext for copy-paste; Eric still has to: (a) make a new Doc, (b) paste, (c) format columns, (d) share, (e) copy link. That's 5 manual steps. A `Create Google Doc` button using the Drive API would collapse all 5 to one click.

2. **Library coverage gap** — his Drive folder has chord sheets for songs the app doesn't have, OR in keys he prefers. He trusts the Drive version. Fix: ingest `eric-all-weeks/*.docx` into the song library so past versions are first-class. (Folder is already in the repo — 194 files. Just not parsed.)

3. **No WhatsApp ingest** — the prep starts with a WhatsApp message from Marcus. The app starts blank. A "paste Marcus's message" textbox that extracts theme + passage + suggested songs would put the app at the actual start of his flow, not the middle.

## What the app already does well (don't rebuild)

- Song library (225+ songs with keys, themes, era, pace)
- Real-time chord sheet preview
- Transposition
- Ultimate Guitar import
- 2-column layout
- Spotify OAuth (PKCE) + playlist creation — fully wired, working
- Gemini AI song suggestion from passage/theme

## Build plan — ranked by ROI

**P0: Google Doc auto-create** — kills the biggest friction. Drive API call, OAuth flow (you already have the pattern from Spotify). Output: button "Create Google Doc" → returns shareable link. Ship: 2-3 hours focused work.

**P1: Eric Drive folder ingest** — script that reads `eric-all-weeks/*.docx`, extracts chord sheets, adds them as authoritative versions to the song library (preferred over generic UG versions). Ship: 1-2 hours, mostly parsing pain.

**P2: WhatsApp message paste → set list draft** — textbox at the top, paste Marcus's message, Gemini extracts theme/passage/suggested songs and pre-fills the form. Ship: 1 hour (it's just a Gemini prompt + parse).

**P3: One-click WhatsApp message generator** — at the end, button outputs the team-message draft with Doc link + Spotify link + prac time + names to ping. Ship: 30 min.

Total: ~5 hours of focused work to take this from "60% covered, still go manual" to "open app, paste Marcus's msg, click 3 buttons, done".

## Decisions Eric needs to make

1. **Worth building?** Or is once-a-month worship prep too low-frequency to justify the build effort? (Counter: he's the worship rotation lead, this is a recurring task forever.)
2. **Tonight, this week, or Ralph it overnight?** Tonight is dinner + family. Tomorrow worship. Realistic ship windows: (a) 1-2hr session next weekend, (b) Ralph overnight one weeknight, (c) staged: P0 first session, rest later.
3. **Public or private?** Currently public on GitHub Pages — fine for chord sheets but if he adds Drive API write access, he probably wants OAuth scoped to his account only. (Spotify already works this way.)

## Recommendation

Schedule a Ralph background agent for one weeknight to build P0 (Google Doc auto-create). It's the highest-ROI single change and unblocks 80% of the manual-fallback pattern. Park P1-P3 until P0 ships and gets used for 2-3 actual services.
