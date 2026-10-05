/**
 * Site Control Centre: Mapal forms (hygiene, food quality, FOH audit). Add-on to the Mapal Broker.
 * Own file in the same Apps Script project, so the broth code is untouched. Reuses gc_(), sheet_(), log_(),
 * apiDate_(), isoDaysAgo_() from Code.gs. The API key never leaves Google.
 *
 * Tab "forms": one row per completed Mapal form (FormId). Score = sum FormScore / sum FormMaxScore over its
 * answers (each scored question is 1 point, so BOH Hygiene Check reads x/49). Rolling 45 day window, replaced
 * in place each run, so re-running is safe. Daily trigger sccScheduledForms at 07:00 UK (after the 06:29 broth
 * pull, to stay clear of Mapal's rate limit). sccInstallTrigger() sets it up once.
 * discoverForms() lists every form name Mapal returns (tab form_catalog); run it if a form is renamed.
 *
 * Tab "form_answers" (added 05/10/2026): every answer of the audit forms (BOH Hygiene Check, Food Quality Audit,
 * Weekly intangibles, FOH Audit), so the Site CC can open the full report: section, question, answer, pass or fail,
 * comment, deviation text, actions, and photos. Same 45 day window, same run, no extra Mapal calls.
 * Photos: answers that carry Attachments are fetched (red points first, at most 12 a form) into the Drive folder
 * "Site CC Mapal photos", shared read only with the Site CC service account; tab photo_index maps answer to file.
 * sccPhotos_ logs any attachment it cannot fetch (with the HTTP code) to broker_log.
 */
var SCC_FORM_EP = '/externalreport/export-form-task-answers-for-date-range';
var SCC_FORMS_RE = /BOH Hygiene Check|Food Quality Audit|Food quality check|FOH Audit|Intangible/i;
var SCC_DETAIL_RE = /BOH Hygiene Check|Food Quality Audit|FOH Audit|Intangible/i;
var SCC_DH = ['form_id', 'form_name', 'location', 'date', 'section', 'seq', 'question', 'answer', 'score', 'max_score',
              'is_dev', 'open_dev', 'severity', 'comment', 'dev_desc', 'direct_action', 'corrective_action', 'dev_state',
              'answer_id', 'attachments', 'who'];
var SCC_PHOTO_FOLDER = 'Site CC Mapal photos';
var SCC_READER = 'site-cc-reader@maki-reviews.iam.gserviceaccount.com';
var SCC_H = ['form_id', 'form_name', 'location', 'date', 'score', 'max_score', 'pct', 'answers', 'deviations',
             'open_deviations', 'auditor', 'state', 'deviation_items', 'last_modified', 'url'];

function sccName_(r) { return r.FormName || r.FormTemplateName || r.TaskName || '(no name)'; }
function sccDay_(r) {
  var v = r.ActualBusinessDay || r.AnsweredDateTime || r.DateTimeFormCreated || r.DateTimeFormLastModified || '';
  return String(v).slice(0, 10).replace(/\//g, '-');
}
function sccFetch_(s, e) {
  var a = gc_(SCC_FORM_EP, { StartDate: apiDate_(s), EndDate: apiDate_(e) });
  if (!Array.isArray(a)) a = (a && (a.Items || a.items || a.Data || a.data || a.Results)) || [];
  return a;
}

function pullForms(days) {
  days = days || 45;
  var det = [];
  var t0 = Date.now(), by = {}, seen = {}, raw = 0, notes = [], start = isoDaysAgo_(days), end = isoDaysAgo_(0), covered = [];
  for (var k = 0; k <= days; k += 7) {   // newest week first, so a rate limit only costs the oldest weeks
    if (Date.now() - t0 > 270000) { notes.push('time budget hit at ' + isoDaysAgo_(k)); break; }
    var s = isoDaysAgo_(Math.min(k + 6, days)), e = isoDaysAgo_(k), a;
    try { a = sccFetch_(s, e); } catch (err) { notes.push(s + ' FAILED ' + String(err.message).slice(0, 100)); if (/429/.test(err.message)) break; continue; }
    raw += a.length; covered.push(s, e);
    Utilities.sleep(3000);   // spacing between chunks: Mapal rate-limits bursts (429s on 02/10/26)
    for (var i = 0; i < a.length; i++) {
      var r = a[i];
      if (!SCC_FORMS_RE.test(sccName_(r)) || r.IsDeleted) continue;
      var aid = r.AnswerID != null ? r.AnswerID : (r.FormId + '|' + r.TaskID);
      if (seen[aid]) continue; seen[aid] = 1;
      var f = by[r.FormId] || (by[r.FormId] = { name: sccName_(r).trim(), loc: r.LocationNameLabel || '', day: '', sc: 0, mx: 0,
        n: 0, dev: 0, open: 0, who: '', state: r.FormState || '', items: [], mod: '',
        url: (r.LocationId && r.FormTemplateId) ? 'https://do.getcompliant.com/app/l/' + r.LocationId + '/forms/folder/-1/revisions/' + r.FormTemplateId + '/false/false/revision/' + r.FormId : '' });
      var d = sccDay_(r); if (d && (!f.day || d < f.day)) f.day = d;
      f.sc += Number(r.FormScore) || 0; f.mx += Number(r.FormMaxScore) || 0; f.n++;
      if (r.IsDeviation) { f.dev++; if (f.items.length < 8) f.items.push(String(r.TaskName || '').replace(/^\s*\d+\.\s*/, '').replace(/\s+/g, ' ').trim().slice(0, 90)); }
      if (r.IsOpenDeviation) f.open++;
      if (!f.who && (r.FirstName || r.LastName)) f.who = (r.FirstName || '') + (r.LastName ? ' ' + String(r.LastName).charAt(0) + '.' : '');
      var m = String(r.DateTimeFormLastModified || ''); if (m > f.mod) f.mod = m;
      if (r.FormState) f.state = r.FormState;
      if (SCC_DETAIL_RE.test(f.name)) det.push([r.FormId, f.name, r.LocationNameLabel || '', d || sccDay_(r), sccTxt_(r.TaskParentName, 120),
        (Number(r.TaskParentSequence) || 0) * 1000 + (Number(r.TaskSequence) || 0), sccTxt_(String(r.TaskName || '').replace(/^\s*\d+\.\s*/, ''), 300),
        sccTxt_(r.Answer, 200), Number(r.FormScore) || 0, Number(r.FormMaxScore) || 0, r.IsDeviation ? 1 : 0, r.IsOpenDeviation ? 1 : 0,
        sccTxt_(r.Severity, 30), sccTxt_(r.TaskComments, 500), sccTxt_(r.DeviationDescription || r.DirectActionProblem || r.CorrectiveActionProblem, 500),
        sccTxt_(r.DirectAction, 300), sccTxt_(r.CorrectiveAction, 300), sccTxt_(r.DeviationState, 40), aid,
        sccTxt_(r.Attachments == null ? '' : JSON.stringify(r.Attachments), 2000), (r.FirstName || '') + (r.LastName ? ' ' + String(r.LastName).charAt(0) + '.' : '')]);
    }
  }
  if (!covered.length) { log_('pullForms FAILED', notes.join(' ; ')); throw new Error('pullForms: no window fetched. ' + notes.join(' ; ')); }
  var rows = Object.keys(by).map(function (id) {
    var f = by[id];
    return [id, f.name, f.loc, f.day, f.sc, f.mx, f.mx ? Math.round(1000 * f.sc / f.mx) / 10 : '', f.n, f.dev, f.open,
            f.who, f.state, f.items.join(' | '), f.mod, f.url];
  }).filter(function (r) { return r[3]; }).sort(function (a, b) { return a[3] < b[3] ? -1 : a[3] > b[3] ? 1 : 0; });
  var cs = covered.slice().sort();
  var fsh = sheet_('forms', SCC_H); fsh.getRange(1, 1, 1, SCC_H.length).setValues([SCC_H]);   // adds the url header to an existing tab
  var w = upsert_(fsh, SCC_H, rows, 3, cs[0], cs[cs.length - 1]);
  det = det.filter(function (r) { return r[3]; });
  var wd = upsert_(sheet_('form_answers', SCC_DH), SCC_DH, det, 3, cs[0], cs[cs.length - 1]);
  notes.push(wd.written + ' audit answers');
  try { notes.push(sccPhotos_(det, t0)); } catch (err) { notes.push('photos FAILED ' + String(err.message).slice(0, 120)); }
  var msg = cs[0] + ' to ' + cs[cs.length - 1] + ': ' + w.written + ' forms from ' + raw + ' raw answers' + (notes.length ? ' (' + notes.join(' ; ') + ')' : '');
  log_('pullForms', msg); Logger.log(msg);
  return msg;
}

function sccTxt_(v, n) {
  if (v == null) return '';
  if (typeof v === 'object') v = JSON.stringify(v);
  return String(v).replace(/[\u2013\u2014]/g, ', ').replace(/\s+/g, ' ').trim().slice(0, n);
}

/** Attachment URLs inside the raw Attachments value (string, object or array, any nesting). */
function sccUrls_(raw) {
  var out = [];
  (function walk(v) {
    if (v == null) return;
    if (typeof v === 'string') {
      if (/^https?:\/\//i.test(v)) out.push(v);
      else if (/^[\[{]/.test(v)) { try { walk(JSON.parse(v)); } catch (e) {} }
      return;
    }
    if (Array.isArray(v)) { v.forEach(walk); return; }
    if (typeof v === 'object') Object.keys(v).forEach(function (k) { walk(v[k]); });
  })(raw);
  return out;
}

function sccPhotoFolder_() {
  var it = DriveApp.getFoldersByName(SCC_PHOTO_FOLDER);
  var f = it.hasNext() ? it.next() : DriveApp.createFolder(SCC_PHOTO_FOLDER);
  try { if (!f.getViewers().some(function (u) { return u.getEmail() === SCC_READER; })) f.addViewer(SCC_READER); } catch (e) { log_('sccPhotos share', String(e.message).slice(0, 150)); }
  return f;
}

/** Fetch audit photos into Drive: red points first, then the rest, at most 12 per form, inside the time budget. */
function sccPhotos_(det, t0) {
  var withA = det.filter(function (r) { return r[19] && r[19] !== 'null' && r[19] !== '[]'; });
  if (!withA.length) return 'no attachments in the window';
  var idx = sheet_('photo_index', ['answer_id', 'n', 'file_id', 'form_id', 'url', 'status']);
  var have = {}, last = idx.getLastRow();
  if (last > 1) idx.getRange(2, 1, last - 1, 6).getValues().forEach(function (v) { have[v[0] + '|' + v[1]] = 1; });
  withA.sort(function (a, b) { return (b[10] - a[10]) || (a[0] - b[0]) || (a[5] - b[5]); });
  var perForm = {}, add = [], fails = {}, folder = null, got = 0;
  for (var i = 0; i < withA.length; i++) {
    if (Date.now() - t0 > 330000) break;
    var r = withA[i], urls = sccUrls_(r[19]);
    for (var j = 0; j < urls.length; j++) {
      var key = r[18] + '|' + j;
      if (have[key]) continue;
      if ((perForm[r[0]] = (perForm[r[0]] || 0) + 1) > 12) break;
      var resp;
      try { resp = UrlFetchApp.fetch(urls[j], { muteHttpExceptions: true, followRedirects: true }); } catch (e) { fails['ERR'] = (fails['ERR'] || 0) + 1; continue; }
      var code = resp.getResponseCode(), type = String(resp.getHeaders()['Content-Type'] || resp.getHeaders()['content-type'] || '');
      if (code !== 200 || !/^image\//i.test(type)) { fails[code + ' ' + type.slice(0, 20)] = (fails[code + ' ' + type.slice(0, 20)] || 0) + 1; add.push([r[18], j, '', r[0], urls[j].slice(0, 300), 'http ' + code + ' ' + type.slice(0, 30)]); have[key] = 1; continue; }
      folder = folder || sccPhotoFolder_();
      var file = folder.createFile(resp.getBlob().setName(r[18] + '_' + j));
      add.push([r[18], j, file.getId(), r[0], urls[j].slice(0, 300), 'ok']); have[key] = 1; got++;
    }
  }
  if (add.length) idx.getRange(idx.getLastRow() + 1, 1, add.length, 6).setValues(add);
  var f = Object.keys(fails);
  var msg = got + ' photos saved, ' + withA.length + ' answers with attachments' + (f.length ? ', not fetched: ' + f.map(function (k) { return k + ' x' + fails[k]; }).join('; ') : '');
  log_('sccPhotos', msg);
  return msg;
}

/** One off check: the first attachment values Mapal returns, written to broker_log, so the photo format can be confirmed. */
function sccSampleAttachments() {
  var a = sccFetch_(isoDaysAgo_(10), isoDaysAgo_(0)), n = 0;
  for (var i = 0; i < a.length && n < 5; i++) if (a[i].Attachments) { log_('attachment sample', String(sccName_(a[i])) + ' : ' + JSON.stringify(a[i].Attachments).slice(0, 800)); n++; }
  Logger.log(n + ' samples logged to broker_log');
}

function sccScheduledForms() { pullForms(14); }   // daily: last 14 days is plenty for late completions

function sccInstallTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) { if (t.getHandlerFunction() === 'sccScheduledForms') ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('sccScheduledForms').timeBased().atHour(7).nearMinute(0).everyDays(1).inTimezone('Europe/London').create();
  Logger.log('trigger set: sccScheduledForms daily about 07:00 UK');
}

/** First run: install the daily trigger, then backfill 45 days (the trigger tops up from there). */
function sccSetup() { sccInstallTrigger(); pullForms(45); }

function discoverForms() {
  var t0 = Date.now(), cat = {}, total = 0, notes = [];
  for (var back = 35; back > 0 && Date.now() - t0 < 300000; back -= 7) {
    var s = isoDaysAgo_(back), e = isoDaysAgo_(Math.max(back - 6, 0)), a;
    try { a = sccFetch_(s, e); } catch (err) { notes.push(s + ' FAILED ' + String(err.message).slice(0, 120)); continue; }
    total += a.length;
    for (var i = 0; i < a.length; i++) {
      var r = a[i], n = sccName_(r), c = cat[n];
      if (!c) c = cat[n] = { n: 0, locs: {}, newest: '', keys: Object.keys(r).join(' | '), sample: JSON.stringify(r).slice(0, 4000) };
      c.n++; c.locs[r.LocationNameLabel || '?'] = 1;
      var d = sccDay_(r); if (d > c.newest) c.newest = d;
    }
    notes.push(s + ' to ' + e + ': ' + a.length + ' answers');
  }
  var H = ['form_name', 'answers', 'locations', 'newest', 'location_names', 'fields', 'sample_record'];
  var sh = sheet_('form_catalog', H);
  if (sh.getLastRow() > 1) sh.getRange(2, 1, sh.getLastRow() - 1, H.length).clearContent();
  var rows = Object.keys(cat).sort().map(function (k) {
    var c = cat[k], L = Object.keys(c.locs).sort();
    return [k, c.n, L.length, c.newest, L.join(', ').slice(0, 2000), c.keys.slice(0, 4000), c.sample];
  });
  rows.push(['(run notes)', total, '', new Date().toISOString(), notes.join(' ; ').slice(0, 2000), '', '']);
  sh.getRange(2, 1, rows.length, H.length).setValues(rows);
  log_('discoverForms', total + ' form answers, ' + (rows.length - 1) + ' form names');
}


/**
 * Certificates probe (05/10/2026, v2): which GetCompliant public API reports hold documents, certificates or asset due dates
 * (fire risk assessment, gas safety, EICR, PAT, extinguishers, ventilation, pest control).
 * v2: one plain call per endpoint (no gc_ retries, which ran v1 past the 6 minute limit on 504s), 7 day window,
 * each result written to tab api_probe as soon as it returns, stops itself at 4.5 minutes. Read only; re-run to continue.
 */
function sccProbeCertificates() {
  var C = ['/externalreport/export-documents', '/externalreport/export-documents-for-date-range', '/externalreport/export-certificates',
           '/externalreport/export-certificates-for-date-range', '/externalreport/export-assets', '/externalreport/export-asset-tasks-for-date-range',
           '/externalreport/export-scheduled-tasks-for-date-range', '/externalreport/export-task-answers-for-date-range',
           '/externalreport/export-locations', '/externalreport/export-modules', '/externalreport/export-deviations-by-date-range'];
  var H = ['endpoint', 'http', 'rows', 'fields', 'sample', 'checked'];
  var sh = sheet_('api_probe', H), done = {};
  for (var x = sh.getLastRow(); x >= 2; x--) { var v = sh.getRange(x, 1, 1, 2).getValues()[0]; if (String(v[1]).indexOf('429') >= 0 || String(v[1]).indexOf('HTTP') >= 0) sh.deleteRow(x); else done[v[0]] = 1; }
  var t0 = Date.now(), qs = '?StartDate=' + encodeURIComponent(apiDate_(isoDaysAgo_(7))) + '&EndDate=' + encodeURIComponent(apiDate_(isoDaysAgo_(0)));
  for (var k = 0; k < C.length; k++) {
    var ep = C[k];
    if (done[ep]) continue;
    if (Date.now() - t0 > 270000) { log_('sccProbeCertificates', 'time budget hit, re-run to continue'); return; }
    var code = '', rows = '', fields = '', sample = '';
    try {
      var res = UrlFetchApp.fetch(API + ep + qs, { method: 'get', muteHttpExceptions: true,
        headers: { 'X-apiKeyId': P_('GC_API_KEY'), 'Accept': 'application/json' } });
      code = res.getResponseCode();
      var body = res.getContentText();
      if (code === 200) {
        var a; try { a = JSON.parse(body); } catch (e) { a = null; sample = String(body).slice(0, 300); }
        if (a && !Array.isArray(a)) a = a.Items || a.items || a.Data || a.data || a.Results || [a];
        var r0 = a && a.length ? a[0] : null;
        rows = a ? a.length : '';
        fields = r0 && typeof r0 === 'object' ? Object.keys(r0).join(' | ').slice(0, 2000) : '';
        if (r0) sample = JSON.stringify(r0).slice(0, 2000);
      } else sample = String(body).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 200);
    } catch (e) { code = 'ERR'; sample = String(e.message).slice(0, 200); }
    if (code === 429) { log_('sccProbeCertificates', 'Mapal 429 at ' + ep + ', stopped; re-run later to continue'); return; }
    sh.appendRow([ep, code, rows, fields, sample, new Date()]);
    SpreadsheetApp.flush();
    Utilities.sleep(2000);
  }
  log_('sccProbeCertificates', 'v2 done');
}

/** One off: run the certificates probe tomorrow at 07:45 UK, after the 07:00 forms pull, when Mapal's rate limit has reset. */
function sccProbeTomorrow() {
  ScriptApp.newTrigger('sccProbeCertificates').timeBased().at(new Date('2026-10-06T06:45:00Z')).create();
  log_('sccProbeTomorrow', 'probe trigger set for 2026-10-06 06:45Z');
}
