/**
 * Site Control Centre: Google review reply web app (13/10/2026).
 * A GM writes a reply on the "Needs a reply" card; the page POSTs here; this script posts the reply
 * to Google through the Business Profile API as Michael (the script owner), so no GM needs Google access.
 *
 * Setup (once), in Michael's Google account:
 *  1. script.new, paste this file. Project Settings: tick "Show appsscript.json", set the manifest to:
 *       {"timeZone":"Europe/London","exceptionLogging":"STACKDRIVER","runtimeVersion":"V8",
 *        "oauthScopes":["https://www.googleapis.com/auth/business.manage","https://www.googleapis.com/auth/script.external_request"]}
 *  2. Project Settings, Google Cloud Platform project: change project, number 735643875179 (maki-reviews,
 *     the project that already holds the Business Profile API approval).
 *  3. Run doGet once from the editor to grant the scopes.
 *  4. Deploy, New deployment, Web app: Execute as Me, Who has access Anyone. Put the /exec URL in
 *     site_cc/sites.json sources.google_reply.webapp.
 *
 * Guard rails: only reviews the page sends with both reviewId and locationId; reply 1 to 4000 characters;
 * dashes replaced with commas (house style); one reply at a time (script lock). The account that owns a
 * location is looked up once and cached in Script Properties.
 */
var V4 = 'https://mybusiness.googleapis.com/v4';
var ACC = 'https://mybusinessaccountmanagement.googleapis.com/v1/accounts';

function out_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }

function call_(method, url, body) {
  var opt = { method: method, muteHttpExceptions: true, contentType: 'application/json',
              headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken(), Accept: 'application/json' } };
  if (body) opt.payload = JSON.stringify(body);
  var r = UrlFetchApp.fetch(url, opt);
  var txt = r.getContentText() || '{}', j;
  try { j = JSON.parse(txt); } catch (e) { j = { raw: txt }; }
  return { code: r.getResponseCode(), body: j };
}

function clean_(s, n) { return String(s == null ? '' : s).replace(/[–—]/g, ', ').replace(/\s+\n/g, '\n').trim().slice(0, n || 4000); }

/* Which account owns this location? Cached per locationId. */
function accountFor_(loc) {
  var props = PropertiesService.getScriptProperties(), key = 'acc:' + loc, hit = props.getProperty(key);
  if (hit) return hit;
  var r = call_('get', ACC + '?pageSize=20');
  if (r.code >= 300) throw new Error('accounts list ' + r.code + ': ' + JSON.stringify(r.body).slice(0, 200));
  var accounts = r.body.accounts || [];
  for (var i = 0; i < accounts.length; i++) {
    var a = accounts[i].name;
    var probe = call_('get', V4 + '/' + a + '/' + loc + '/reviews?pageSize=1');
    if (probe.code < 300) { props.setProperty(key, a); return a; }
  }
  throw new Error('no account owns ' + loc);
}

function doGet() { return out_({ ok: true, service: 'Site CC Google reply' }); }

function doPost(e) {
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000);
    var m = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    if (m.op !== 'reply') return out_({ ok: false, error: 'unknown op' });
    var rid = String(m.rid || ''), loc = String(m.loc || '');
    if (!/^[A-Za-z0-9_\-]{10,}$/.test(rid) || !/^locations\/\d+$/.test(loc)) return out_({ ok: false, error: 'bad review reference' });
    var text = clean_(m.text);
    if (text.length < 1) return out_({ ok: false, error: 'empty reply' });
    var acc = accountFor_(loc), name = acc + '/' + loc + '/reviews/' + rid;
    var chk = call_('get', V4 + '/' + name);
    if (chk.code >= 300) return out_({ ok: false, error: 'review not found (' + chk.code + ')' });
    var r = call_('put', V4 + '/' + name + '/reply', { comment: text });
    if (r.code >= 300) return out_({ ok: false, error: 'Google ' + r.code + ': ' + ((r.body.error && r.body.error.message) || '').slice(0, 200) });
    return out_({ ok: true, rid: rid, at: new Date().toISOString().slice(0, 10), by: clean_(m.by, 40), site: clean_(m.site, 10) });
  } catch (err) {
    return out_({ ok: false, error: String(err && err.message || err).slice(0, 200) });
  } finally {
    try { lock.releaseLock(); } catch (e2) {}
  }
}
