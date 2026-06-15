# 21 June 2026 — Service Leading (Eric)

**Theme:** Patiently Trust in the Lord · **Sermon:** Habakkuk 2:2-5 (Marcus)

Morning click-through. I built the scaffolding; the calls are yours.

---

## Do these, in order

1. **Reflect first, before logistics** → open [`reflection.md`](reflection.md). Raw Scripture + your song lyrics + open questions. I wrote none of the reflection on purpose.
2. **Decide the 3 open roles** (below) — Bible reader, Projection, Announcements.
3. **Send message 1** (roles + theme) to the service-leading group → [`messages.md`](messages.md). Fill the `[brackets]` first.
4. **Send message 2** (order of service) once roles are filled.
5. **Music doc** — open the chord doc, add the one missing song, then it's ready to share (see below).
6. **Sat evening:** send the prayer-gather message (message 4).

---

## Decisions only you can make

| # | Decision | My note |
|---|---|---|
| 1 | **Bible reader** | 2 readings (Rom 1:16-23, Hab 2:2-5). You usually read both yourself — message 3 offers it out. |
| 2 | **Projection** | Unassigned. Who's free? |
| 3 | **Announcements** | Unassigned — often the preacher. Confirm with Marcus. |
| 4 | **Declaration passage** | Pick one — options listed in `reflection.md`. |
| 5 | **Confession number** | From the FMH set (you have it). |
| 6 | **"Our God is for us"** — which song? | Almost certainly **Chris Tomlin "Our God"** ("if our God is for us…"). Not in your library yet. Confirm, then I'll add it via `/add-song`. |
| 7 | **"Sovereign" key** | Built in **D** (Chris Tomlin, the version tagged pre-sermon). You also have it in G. Change if you want. |

---

## What I built

- **Order of service** → [`order-of-service.md`](order-of-service.md) — full flow + roster + gaps.
- **Reflection worksheet** → [`reflection.md`](reflection.md) — scaffold only, your words.
- **Messages** → [`messages.md`](messages.md) — copy-paste, in your voice.
- **Music chord doc** → `service-builder/output/21 June 2026.docx` — 4 songs built (Still, Sovereign, I Will Trust My Saviour Jesus, kids song) + "Our God is for us" as a TBC placeholder. Open it to eyeball.

## Music doc — how to finish it

1. Confirm "Our God is for us" (decision 6) → tell me, I'll run `/add-song`.
2. I rebuild → `python3 service-builder/build_service.py service-builder/weeks/2026-06-21.json`.
3. Upload the `.docx` to your song-scripts Drive folder → share link → drop into message 2.

(The chord doc goes to the **music** team. Keys default to no-transposition.)

---

## Version control

Committed locally on `main` as one scoped commit (`service: 21 Jun 2026…`) — only this folder, the week config, and the Still title fix. **Not pushed** — pushing also redeploys your web app, so that's your call. Your earlier in-progress song edits were left untouched.

*Why no big AI fan-out: you asked for minimal AI on the reflection, so I kept this hands-on — fetched the real Scripture text, read your real song files, and left the thinking to you. Cost tally is in the chat.*
