/**
 * Site Control Centre: certificate and contractor logs from Mapal (08/10/2026). Add-on to the Mapal Broker, same project
 * as SiteCC_Mapal.gs; reuses sccFetch_(), sccName_(), sccDay_(), sheet_(), log_(), isoDaysAgo_() so the API key never leaves Google.
 *
 * Why: the PPM schedule (ppm_contractors.json) is a static list, so a certificate completed in Mapal (the M7 Fire Risk
 * Assessment, 10/12/2025) still showed as overdue since 2023. Tab "certs" holds every completed Mapal form whose name looks like
 * a certificate or contractor check (fire risk, fire alarm, emergency lighting, extinguishers, gas, EICR, PAT, TR19, extraction,
 * pest, grease, legionella, lift, sprinkler, asbestos): form_id, form_name, location, date, who, state, url.
 * pull_ppm.py takes the latest one per PPM line, so "Last done" and "Next due" come from Mapal where Mapal has the log.
 *
 * Backfill: Mapal only exports answers by date range, 7 days a call, so pullCerts() walks back from today in 7 day windows
 * inside the 4.5 minute budget and remembers how far it got (Script Property SCC_CERT_CURSOR). Each run first tops up the
 * newest 14 days, then continues the backfill until SCC_CERT_MONTHS back. Stops cleanly on a Mapal 429 and carries on next run.
 * Daily trigger sccScheduledCerts at 08:15 UK (clear of the 06:29 broth and 07:00 forms pulls). sccCertsSetup() once.
 */
var SCC_CERT_RE = /Fire Risk|Fire Alarm|Emergency Light|Extinguisher|Gas Safety|CP42|EICR|Electrical Installation|\bPAT\b|Portable Appliance|TR19|Extraction|Duct|Pest|Grease|Legionella|Water (Hygiene|Risk)|\bLift\b|Sprinkler|Asbestos/i;
var SCC_CH = ['form_id', 'form_name', 'location', 'date', 'who', 'state', 'url', 'pulled'];
var SCC_CERT_MONTHS = 36;

function pullCerts(force) {
  var pr = PropertiesService.getScriptProperties();
  var cur = force ? 0 : Number(pr.getProperty('SCC_CERT_CURSOR') || 0);   // days back already covered by the backfill
  var max = SCC_CERT_MONTHS * 31;
  var t0 = Date.now(), sh = sheet_('certs', SCC_CH), have = {}, last = sh.getLastRow();
  if (last > 1) sh.getRange(2, 1, last - 1, SCC_CH.length).getValues().forEach(function (v) { have[String(v[0])] = 1; });
  var windows = [[0, 14]];
  for (var k = Math.max(cur, 14); k < max; k += 7) windows.push([k, Math.min(k + 7, max)]);
  var add = [], notes = [], done = cur, n = 0, today = new Date().toISOString().slice(0, 10);
  for (var w = 0; w < windows.length; w++) {
    if (Date.now() - t0 > 270000) { notes.push('time budget at ' + windows[w][0] + ' days back'); break; }
    var s = isoDaysAgo_(windows[w][1]), e = isoDaysAgo_(windows[w][0]), a;
    try { a = sccFetch_(s, e); } catch (err) { notes.push(s + ' FAILED ' + String(err.message).slice(0, 100)); if (/429/.test(err.message)) break; continue; }
    n++;
    var by = {};
    for (var i = 0; i < a.length; i++) {
      var r = a[i];
      if (r.IsDeleted || !SCC_CERT_RE.test(sccName_(r))) continue;
      var f = by[r.FormId] || (by[r.FormId] = { name: sccName_(r).trim(), loc: r.LocationNameLabel || '', day: '', who: '', state: r.FormState || '',
        url: (r.LocationId && r.FormTemplateId) ? 'https://do.getcompliant.com/app/l/' + r.LocationId + '/forms/folder/-1/revisions/' + r.FormTemplateId + '/false/false/revision/' + r.FormId : '' });
      var d = sccDay_(r); if (d && (!f.day || d < f.day)) f.day = d;
      if (!f.who && (r.FirstName || r.LastName)) f.who = (r.FirstName || '') + (r.LastName ? ' ' + String(r.LastName).charAt(0) + '.' : '');
      if (r.FormState) f.state = r.FormState;
    }
    Object.keys(by).forEach(function (id) {
      var f = by[id];
      if (have[id] || !f.day) return;
      have[id] = 1; add.push([id, f.name, f.loc, f.day, f.who, f.state, f.url, today]);
    });
    if (w > 0) done = windows[w][1];
    Utilities.sleep(3000);   // Mapal rate-limits bursts
  }
  if (add.length) sh.getRange(sh.getLastRow() + 1, 1, add.length, SCC_CH.length).setValues(add);
  done = Math.min(done, max); pr.setProperty('SCC_CERT_CURSOR', String(done));
  var msg = n + ' windows, ' + add.length + ' new certificate forms, backfill covers ' + done + ' of ' + max + ' days back' + (notes.length ? ' (' + notes.join(' ; ') + ')' : '');
  log_('pullCerts', msg); Logger.log(msg);
  return msg;
}

function sccScheduledCerts() { pullCerts(); }

function sccInstallCertsTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) { if (t.getHandlerFunction() === 'sccScheduledCerts') ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('sccScheduledCerts').timeBased().atHour(8).nearMinute(15).everyDays(1).inTimezone('Europe/London').create();
  Logger.log('trigger set: sccScheduledCerts daily about 08:15 UK');
}

/** First run: install the daily trigger and start the backfill (later runs continue it until 36 months are covered). */
function sccCertsSetup() { sccInstallCertsTrigger(); return pullCerts(); }
