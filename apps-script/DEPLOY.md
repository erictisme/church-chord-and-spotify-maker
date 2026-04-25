# Deploying the FMH Worship Doc Creator (Apps Script)

This is a one-time setup. Takes about 5 minutes. After this you'll have a URL you paste into the app's Settings panel, and the "📄 Create Google Doc" button will work.

## Step 1 — Create a new Apps Script project

1. Open <https://script.google.com> in the browser where you're logged into the Google account that owns your worship Drive folder.
2. Click the blue **+ New project** button (top-left).
3. A code editor opens with a file called `Code.gs` containing an empty `myFunction()`.

## Step 2 — Paste the script

1. Select everything inside `Code.gs` and delete it.
2. Open `apps-script/CreateDoc.gs` from this repo.
3. Copy the entire file contents and paste into the Apps Script editor.
4. Rename the project: click the title at the top-left ("Untitled project") → name it `FMH Worship Doc Creator` → press Enter.
5. Click the floppy-disk **Save** icon (or ⌘S).

## Step 3 — Deploy as a web app

1. Top-right of the editor, click **Deploy** → **New deployment**.
2. Click the gear icon next to "Select type" → choose **Web app**.
3. Fill the form:
   - **Description:** `FMH Worship Doc Creator v1`
   - **Execute as:** **Me (your-email@gmail.com)** — this is what lets the script create Docs in your Drive.
   - **Who has access:** **Anyone** — don't worry, "Anyone" still requires the secret URL Apps Script generates. The URL itself is the password.
4. Click **Deploy**.

## Step 4 — Authorize the script

The first deploy asks for permission to act on your Drive.

1. Click **Authorize access**.
2. Pick the same Google account.
3. You'll see **"Google hasn't verified this app"**. This is expected — you wrote the app, so Google has nothing to verify against. It is safe.
4. Click **Advanced** at the bottom-left.
5. Click **Go to FMH Worship Doc Creator (unsafe)**.
6. On the permissions screen, click **Allow**.

## Step 5 — Copy the web app URL

After authorizing, Apps Script shows a dialog with two URLs.

1. Copy the **Web app URL**. It looks like:
   ```
   https://script.google.com/macros/s/AKfycb.../exec
   ```
2. Save it somewhere safe for a moment (a sticky note, a fresh email draft to yourself, anywhere).

## Step 6 — Paste into the app

1. Open the FMH Worship app.
2. Click the **⚙️ Settings** gear in the top-right.
3. Paste the URL into the **Apps Script URL** field under "Google Doc Integration".
4. Click **Test** — you should see ✓ green and a test Doc will appear in your Drive.
5. Click **Save**.

Done. The "📄 Create Google Doc" button now works.

---

## Verify it works (optional, before integrating)

You can test the deployment from your Mac terminal before touching the app. Replace `<YOUR_URL>` with the URL from Step 5:

```bash
curl -L -X POST '<YOUR_URL>' \
  -H 'Content-Type: application/json' \
  -d '{"title":"Apps Script smoke test","content":"hello from curl\n\nA  D  E\nworship line"}'
```

Expected response (one line of JSON):

```json
{"url":"https://docs.google.com/document/d/.../edit","id":"..."}
```

Open that `url` — you should see a new Doc in your Drive with the test content. If you see `{"error":"..."}`, the message tells you what went wrong.

---

## Updating the script later

If `CreateDoc.gs` changes in this repo:

1. Open the same Apps Script project.
2. Replace the file contents.
3. **Deploy → Manage deployments → pencil/edit icon → Version: New version → Deploy.**
4. The URL stays the same. No need to re-paste into the app.

(Choosing "New deployment" instead would give a new URL — only do that if you intentionally want a fresh one.)
