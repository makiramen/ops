/**
 * Site Control Centre: Asana web app (07/10/2026).
 * Mark done on a Site CC page completes the Asana task straight away (evidence added as a comment).
 * Add action on the page creates the task in the site's section of "Maki & Ramen Management".
 * The Asana token lives only in Script Properties (ASANA_TOKEN), never in the page or the repo.
 * Only tasks inside the site's own section of that project can be touched.
 *
 * Setup (once): Project Settings, Script Properties, add ASANA_TOKEN. Deploy, New deployment, Web app,
 * Execute as: Me, Who has access: Anyone. Put the /exec URL in site_cc/sites.json sources.asana.webapp.
 */
var PROJECT = '1177163204793489';
var SECTIONS = {
  M1: '1219205670910230', M3: '1219205670910231', M6: '1219205670910232', M7: '1219205670910233',
  M8: '1219205670910234', M9: '1219205670910235', M10: '1219205670910236', M11: '1219205670910237',
  M12: '1219205670910238', M13: '1219205670910239', M14: '1219205670910240', M15: '1219205670910241',
  M16: '1219205670910242', M17: '1219205670910243', M18: '1219205670910244', M19: '1219205670910245',
  M20: '1219205670910246', M21: '1219205670910247', MakiNori: '1219205670910248', IKI2: '1219205670910249'
};

function out_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }

function asana_(method, path, body) {
  var tok = PropertiesService.getScriptProperties().getProperty('ASANA_TOKEN');
  if (!tok) throw new Error('ASANA_TOKEN not set in Script Properties');
  var opt = { method: method, muteHttpExceptions: true, contentType: 'application/json',
              headers: { Authorization: 'Bearer ' + tok, Accept: 'application/json' } };
  if (body) opt.payload = JSON.stringify({ data: body });
  var r = UrlFetchApp.fetch('https://app.asana.com/api/1.0' + path, opt);
  var j = JSON.parse(r.getContentText() || '{}');
  if (r.getResponseCode() >= 300) throw new Error('Asana ' + r.getResponseCode() + ': ' + ((j.errors && j.errors[0] && j.errors[0].message) || ''));
  return j.data;
}

function clean_(s, n) { return String(s == null ? '' : s).replace(/[\u2013\u2014]/g, ', ').slice(0, n || 500); }

function doGet() { return out_({ ok: true, service: 'Site CC Asana sync' }); }

function doPost(e) {
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000);
    var m = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    var sec = SECTIONS[m.site];
    if (!sec) return out_({ ok: false, error: 'unknown site' });

    if (m.op === 'done') {
      if (!/^\d+$/.test(String(m.gid || ''))) return out_({ ok: false, error: 'bad task id' });
      var t = asana_('get', '/tasks/' + m.gid + '?opt_fields=completed,memberships.section.gid,memberships.project.gid');
      var inSec = (t.memberships || []).some(function (x) { return x.project && x.project.gid === PROJECT && x.section && x.section.gid === sec; });
      if (!inSec) return out_({ ok: false, error: 'task is not in the ' + m.site + ' section' });
      if (!t.completed) {
        asana_('post', '/tasks/' + m.gid + '/stories', { text: 'Marked done on the Site Control Centre (' + m.site + ', ' + clean_(m.by, 20) + '). Evidence: ' + clean_(m.ev) });
        asana_('put', '/tasks/' + m.gid, { completed: true });
      }
      return out_({ ok: true, gid: m.gid });
    }

    if (m.op === 'add') {
      var name = clean_(m.t, 250).trim();
      if (!name) return out_({ ok: false, error: 'empty action' });
      var body = { name: name, projects: [PROJECT],
                   notes: 'Owner: ' + clean_(m.o, 80) + '\nSource: ' + clean_(m.src, 40) + ', w/c ' + clean_(m.wc, 10) +
                          (m.esc ? '\nNeeds a support team (EC, maintenance, marketing).' : '') +
                          '\nAdded on the Site Control Centre (' + m.site + ').' };
      if (/^\d{4}-\d{2}-\d{2}$/.test(m.d || '')) body.due_on = m.d;
      var nt = asana_('post', '/tasks', body);
      asana_('post', '/sections/' + sec + '/addTask', { task: nt.gid });
      return out_({ ok: true, gid: nt.gid });
    }
    return out_({ ok: false, error: 'unknown op' });
  } catch (err) {
    return out_({ ok: false, error: String(err.message || err) });
  } finally {
    try { lock.releaseLock(); } catch (x) {}
  }
}
