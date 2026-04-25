/**
 * FMH Worship — Google Doc creator
 * Deployed as a web app under Eric's Google account.
 * POST { title, content, columns? } -> { url, id } or { error }
 */

function doPost(e) {
  try {
    var body = {};
    if (e && e.postData && e.postData.contents) {
      body = JSON.parse(e.postData.contents);
    }

    var title = (body.title && String(body.title).trim()) || 'Worship Script';
    var content = body.content == null ? '' : String(body.content);
    var columns = body.columns === 2 ? 2 : 1;

    var doc = DocumentApp.create(title);
    var docId = doc.getId();
    var bodyEl = doc.getBody();

    // Two-column layout: Apps Script doesn't expose column-section APIs reliably,
    // so we approximate by setting tight page margins. Real two-column rendering
    // can be applied manually in Docs (Format > Columns) — Eric usually copy-pastes.
    if (columns === 2) {
      bodyEl.setMarginLeft(36);
      bodyEl.setMarginRight(36);
      bodyEl.setMarginTop(36);
      bodyEl.setMarginBottom(36);
    }

    // Insert content. We split by lines so we can apply Courier New to chord lines
    // (chord-over-lyric alignment depends on a monospace font).
    var lines = content.split(/\r?\n/);
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      var p = bodyEl.appendParagraph(line);
      if (looksLikeChordLine(line)) {
        p.editAsText().setFontFamily('Courier New');
      }
    }

    // Remove the empty leading paragraph that DocumentApp.create() inserts.
    if (bodyEl.getNumChildren() > lines.length) {
      var first = bodyEl.getChild(0);
      if (first.getType() === DocumentApp.ElementType.PARAGRAPH &&
          first.asParagraph().getText() === '') {
        bodyEl.removeChild(first);
      }
    }

    doc.saveAndClose();

    var file = DriveApp.getFileById(docId);
    file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);

    return jsonOut({ url: doc.getUrl(), id: docId });
  } catch (err) {
    return jsonOut({ error: String(err && err.message ? err.message : err) });
  }
}

/**
 * Heuristic: a chord line is mostly chord tokens (letters A-G with optional
 * accidentals + suffixes) and whitespace, with no lowercase prose words.
 */
function looksLikeChordLine(line) {
  var t = line.trim();
  if (!t) return false;
  // Lowercase prose disqualifies.
  if (/[a-z]{3,}/.test(t)) return false;
  var tokens = t.split(/\s+/);
  if (!tokens.length) return false;
  var chordRe = /^[A-G](#|b)?(maj|min|m|sus|aug|dim|add)?\d*(\/[A-G](#|b)?)?$/;
  var chordCount = 0;
  for (var i = 0; i < tokens.length; i++) {
    if (chordRe.test(tokens[i])) chordCount++;
  }
  return chordCount / tokens.length >= 0.6;
}

function jsonOut(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

// Optional GET handler so Eric can sanity-check the deployment in a browser.
function doGet() {
  return jsonOut({ ok: true, service: 'fmh-worship-doc-creator' });
}
