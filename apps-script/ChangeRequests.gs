/**
 * J+S House: change requests from the web viewer (house.carterwiens.com).
 *
 * A standalone Apps Script project (script.google.com > New project), separate from the sheet's own
 * Extensions > Apps Script code, so it never touches the Rhino sync script. Deployed as a web app.
 * It writes to the project sheet by ID.
 *   doPost  - the viewer sends {from, text, image (data URL), view}; adds a row to "Change Requests",
 *             saves the snapshot to a Drive folder, and emails you.
 *   doGet   - the viewer reads the list (newest first) for the Changes menu.
 * You manage requests in the sheet: set Status (Open / In progress / Done / Won't do) and write a Response;
 * both show on the website.
 */
const SHEET_ID = '1bF1fqLSDdm4ScPzXNKSm-N9VOvhhqmqtqIGnrslrTso';   // J+S House project sheet
const SHEET = 'Change Requests';
const FOLDER = 'J+S House - Change Request Snapshots';
const HEAD = ['#', 'Submitted', 'From', 'Description', 'Status', 'Response', 'Snapshot', 'View (for the viewer)', 'Snapshot file ID'];
const STATUSES = ['Open', 'In progress', 'Done', "Won't do"];
const NOTIFY = true;   // email the owner of this script for every new request

/** Run this once from the editor: it asks for permission and creates the tab and the Drive folder. */
function setup() {
  sheet_();
  folder_();
  Logger.log('Ready. Now Deploy > New deployment > Web app.');
}

function sheet_() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  let sh = ss.getSheetByName(SHEET);
  if (!sh) {
    sh = ss.insertSheet(SHEET);
    sh.getRange(1, 1, 1, HEAD.length).setValues([HEAD]).setFontWeight('bold').setBackground('#e8eef9');
    sh.setFrozenRows(1);
    sh.getRange('E2:E').setDataValidation(
      SpreadsheetApp.newDataValidation().requireValueInList(STATUSES, true).build());
    sh.setColumnWidth(1, 40); sh.setColumnWidth(2, 140); sh.setColumnWidth(3, 120);
    sh.setColumnWidth(4, 420); sh.setColumnWidth(5, 100); sh.setColumnWidth(6, 300); sh.setColumnWidth(7, 90);
    sh.getRange('D2:D').setWrap(true); sh.getRange('F2:F').setWrap(true);
    sh.hideColumns(8, 2);
  }
  return sh;
}

function folder_() {
  const props = PropertiesService.getScriptProperties();
  const id = props.getProperty('FOLDER_ID');
  if (id) { try { return DriveApp.getFolderById(id); } catch (e) { /* deleted: make a new one */ } }
  const f = DriveApp.createFolder(FOLDER);
  props.setProperty('FOLDER_ID', f.getId());
  return f;
}

function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

function doGet() {
  const sh = sheet_();
  const n = sh.getLastRow() - 1;
  const rows = n > 0 ? sh.getRange(2, 1, n, HEAD.length).getValues() : [];
  const items = rows.filter((r) => r[0] !== '' && r[3] !== '').map((r) => ({
    id: r[0],
    date: r[1] instanceof Date ? r[1].toISOString() : String(r[1]),
    from: String(r[2]),
    text: String(r[3]),
    status: String(r[4] || 'Open'),
    response: String(r[5] || ''),
    link: String(r[6] || ''),
    view: String(r[7] || ''),
    image: r[8] ? 'https://drive.google.com/thumbnail?id=' + r[8] + '&sz=w1600' : '',
  }));
  return json_({ ok: true, items: items.reverse() });
}

function doPost(e) {
  let d;
  try { d = JSON.parse(e.postData.contents); } catch (err) { return json_({ ok: false, error: 'Bad request' }); }
  if (d.website) return json_({ ok: true, id: 0 });              // honeypot field: bots fill it, people never see it
  const text = String(d.text || '').trim().slice(0, 5000);
  if (!text) return json_({ ok: false, error: 'Please describe the change.' });
  const from = String(d.from || '').trim().slice(0, 100);

  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const sh = sheet_();
    const last = sh.getLastRow();
    const id = last > 1 ? (Number(sh.getRange(last, 1).getValue()) || last - 1) + 1 : 1;
    let fileId = '', link = '';
    const m = String(d.image || '').match(/^data:image\/(png|jpeg);base64,(.+)$/);
    if (m) {
      const ext = m[1] === 'png' ? 'png' : 'jpg';
      const blob = Utilities.newBlob(Utilities.base64Decode(m[2]), 'image/' + m[1], 'Change ' + id + '.' + ext);
      const f = folder_().createFile(blob);
      f.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);   // so the website can show it
      fileId = f.getId(); link = f.getUrl();
    }
    sh.appendRow([id, new Date(), from, text, 'Open', '', link, JSON.stringify(d.view || {}).slice(0, 4000), fileId]);
    if (NOTIFY) {
      try {
        MailApp.sendEmail(Session.getEffectiveUser().getEmail(),
          'J+S House change request #' + id + (from ? ' from ' + from : ''),
          text + (link ? '\n\nSnapshot: ' + link : '') + '\n\nAll requests: ' + SpreadsheetApp.openById(SHEET_ID).getUrl());
      } catch (err) { /* email quota or permission: the row is still saved */ }
    }
    return json_({ ok: true, id: id });
  } finally {
    lock.releaseLock();
  }
}
