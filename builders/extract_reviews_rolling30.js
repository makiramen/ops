/* extract_reviews_rolling30.js — Pipe 5b (30-DAY ROLLING GOOGLE STAR), browser-side.
 *
 * ADDED 20/08/2026. Feeds `data/reviews_rolling30.json`, which powers the
 * "30-Day ★" column on the Regional Accountability Board.
 *
 * WHY IT EXISTS — Michael, 20/08:
 *   The LIFETIME star flatters NEW sites (few, recent reviews) and punishes OLD
 *   ones (years of accumulated history), so it cannot be used to compare people.
 *   On top of that, the dashboard's lifetime figure is a BAKED CONSTANT pulled on
 *   29 May 2026 that has never refreshed. Lifetime was KEPT everywhere it already
 *   appears (site league table, heat-map toggle, site modal, and the board) —
 *   nothing was removed — and the 30-day rolling star was added ALONGSIDE it.
 *
 * WHY BROWSER-SIDE: the container cannot reach docs.google.com. Run this in the
 * DevTools console of a tab already open on the Google Reviews workbook:
 *   https://docs.google.com/spreadsheets/d/1aFGfbGrEBeqWny8myF6H4LVxO0YegT0MdIJHrxpxk3I/edit?gid=284143046
 *
 * WHAT IT DOES: pulls `Raw Data` (gid 284143046 — FULL lifetime history), dedupes
 * on reviewId, maps source labels to site codes, buckets every review by the DAY
 * it was RECEIVED, then for each dashboard week sums the TRUE 30 days ENDING on
 * that week's SUNDAY. Rolling the dashboard's week selector back rolls the window
 * back with it.
 *
 * 🔴 WINDOW DEFINITION — do not change without changing the page caption:
 *      week 2026-08-10  ->  Sunday 2026-08-16  ->  window 2026-07-18..2026-08-16
 *    i.e. 30 calendar days INCLUSIVE, ending on the week's Sunday.
 *
 * 🔴 The page does NOT fall back to the newest week when the active week is absent
 *    from the file — it renders N/A. That is deliberate: a silent fallback is
 *    exactly how a stale number ends up under a heading claiming to be current.
 *
 * SAME SOURCE TRAPS as extract_reviews_rawdata.js — read that file's header:
 *   - dedupe on col A reviewId is MANDATORY (840 dupes in 9,120 rows on 20/08);
 *   - col L `Date` is dd/mm/yyyy TEXT, or `Date(y,m,d)` if the query GROUPs;
 *   - `Leith` (M4, dead), `West end` (MAF1), `Maki O2` (MAF3), `NQ`, `#N/A` are
 *     DROPPED on purpose;
 *   - IKI2 has NO rows in this workbook, ever — it is absent from the output by
 *     design. NEVER write a zero or a rating for it.
 *
 * OUTPUT: window.__ROLL, then a downloaded JSON. Minify it (no indent) before
 * publishing — the page fetches it on every load. ~20 KB minified (16 weeks at 24/08/2026).
 * Publish to repo path: data/reviews_rolling30.json
 */
(async function () {
  const SHEET = '1aFGfbGrEBeqWny8myF6H4LVxO0YegT0MdIJHrxpxk3I';
  const GID   = '284143046';
  const FROM  = '2026-04-01';        // must be >= 30 days before the FIRST week's Sunday
  const WEEK0 = [2026, 4, 4];        // 2026-05-04 (month 0-indexed)

  // NWEEKS is DERIVED, never hard-coded. Fault found 24/08/2026: a hard-coded 15 stopped the output
  // at w/c 2026-08-10, so w/c 2026-08-17 was never emitted. Count the Mon-start weeks from WEEK0 up
  // to and including the most recent COMPLETE week — the Monday of the week that ended last Sunday.
  // Correct forever; never needs an annual edit.
  const MS_WEEK = 7 * 86400000;
  const _now = new Date();
  const _todayUTC = Date.UTC(_now.getFullYear(), _now.getMonth(), _now.getDate());
  const _thisMon = _todayUTC - ((new Date(_todayUTC).getUTCDay() + 6) % 7) * 86400000;  // Mon of the CURRENT (incomplete) week
  const _lastCompleteMon = _thisMon - MS_WEEK;                                          // Mon of the last COMPLETE week
  const NWEEKS = Math.max(1, Math.floor((_lastCompleteMon - Date.UTC(WEEK0[0], WEEK0[1], WEEK0[2])) / MS_WEEK) + 1);

  const MAP = {
    'Maki1/2': 'M1', 'Fountainbridge': 'M3', 'Bath st': 'M6', 'SJQ': 'M7',
    'Renfield': 'M8', 'Manchester': 'M9', 'Leeds': 'M10', 'Leicester': 'M11',
    'Newcastle': 'M12', 'Aberdeen': 'M13', 'Meadowhall': 'M14', 'Metro': 'M15',
    'Nottingham': 'M16', 'Lakeside': 'M17', 'Soho': 'M18',
    'Maki Shoreditch': 'M19', 'Maki Southampton': 'M20', 'Nori': 'MakiNori',
    // 25/08/2026: label appeared at source 20/08; M21 mapping approved by Michael.
    'Maki Birmingham': 'M21'
  };
  const DROP = { 'Leith': 1, 'West end': 1, 'Maki O2': 1, 'NQ': 1, '#N/A': 1 };
  const RW = { FIVE: 5, FOUR: 4, THREE: 3, TWO: 2, ONE: 1, '5': 5, '4': 4, '3': 3, '2': 2, '1': 1 };

  function isoOf(v, f, ct) {
    if (v == null || v === '') return ct ? String(ct).slice(0, 10) : null;
    const s = String(v);
    let m = s.match(/^Date\((\d+),(\d+),(\d+)/);
    if (m) return m[1] + '-' + String(+m[2] + 1).padStart(2, '0') + '-' + String(+m[3]).padStart(2, '0');
    m = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
    if (m) return m[3] + '-' + String(+m[2]).padStart(2, '0') + '-' + String(+m[1]).padStart(2, '0');
    m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
    if (m) return m[1] + '-' + String(+m[2]).padStart(2, '0') + '-' + String(+m[3]).padStart(2, '0');
    return ct ? String(ct).slice(0, 10) : null;
  }

  // A=reviewId E=rating(words) G=createTime K=site L=date
  const q = "select A,E,G,K,L where G >= '" + FROM + "' ";
  const url = 'https://docs.google.com/spreadsheets/d/' + SHEET +
              '/gviz/tq?gid=' + GID + '&tqx=out:json&tq=' + encodeURIComponent(q);
  const raw = await (await fetch(url, { credentials: 'include' })).text();
  const rows = JSON.parse(raw.substring(raw.indexOf('{'), raw.lastIndexOf('}') + 1)).table.rows;

  const seen = {}, days = {}, unmapped = {};
  let dup = 0, kept = 0;
  for (const row of rows) {
    const c = row.c;
    const id = c[0] && c[0].v != null ? String(c[0].v) : null;
    if (id) { if (seen[id]) { dup++; continue; } seen[id] = 1; }
    const label = c[3] && c[3].v != null ? String(c[3].v).trim() : '';
    if (DROP[label]) continue;
    const code = MAP[label];
    if (!code) { unmapped[label] = (unmapped[label] || 0) + 1; continue; }
    const stars = RW[String((c[1] && c[1].v) || '').toUpperCase().trim()];
    if (!stars) continue;
    const iso = isoOf(c[4] ? c[4].v : null, c[4] ? c[4].f : null, c[2] ? c[2].v : null);
    if (!iso) continue;
    const d = days[code] || (days[code] = {});
    const a = d[iso] || (d[iso] = [0, 0, 0, 0, 0]);   // [5,4,3,2,1]
    a[5 - stars]++; kept++;
  }
  if (Object.keys(unmapped).length) console.warn('🔴 UNMAPPED LABELS — do not ship until resolved', unmapped);

  const out = {};
  for (let i = 0; i < NWEEKS; i++) {
    const mon = new Date(Date.UTC(WEEK0[0], WEEK0[1], WEEK0[2] + 7 * i));
    const monISO = mon.toISOString().slice(0, 10);
    const sun = new Date(mon.getTime() + 6 * 86400000);
    const start = new Date(sun.getTime() - 29 * 86400000);          // 30 days INCLUSIVE
    const sunISO = sun.toISOString().slice(0, 10), startISO = start.toISOString().slice(0, 10);
    const per = {};
    for (const code in days) {
      let n = 0, sum = 0; const bd = [0, 0, 0, 0, 0];
      for (const d in days[code]) {
        if (d < startISO || d > sunISO) continue;
        const a = days[code][d];
        for (let k = 0; k < 5; k++) { bd[k] += a[k]; n += a[k]; sum += (5 - k) * a[k]; }
      }
      per[code] = n > 0
        ? { rating: Math.round(sum / n * 10000) / 10000, n: n,
            bd: { "5": bd[0], "4": bd[1], "3": bd[2], "2": bd[3], "1": bd[4] } }
        : { rating: null, n: 0, bd: { "5": 0, "4": 0, "3": 0, "2": 0, "1": 0 } };
    }
    out[monISO] = { from: startISO, to: sunISO, sites: per };
  }

  console.log('weeks emitted', NWEEKS, ':', Object.keys(out)[0], '->', Object.keys(out)[NWEEKS - 1]);

  window.__ROLL = {
    schema_version: 1,
    generated_at: new Date().toISOString().slice(0, 10),
    window_days: 30,
    note: "True 30-day rolling Google review window ENDING on each week's Sunday (inclusive). Source: Google Reviews workbook 'Raw Data' tab gid 284143046, full-history rows deduped on reviewId, bucketed by review RECEIVED date. Per-site star tabs NOT used (corrupt). IKI2 has no rows in this workbook and is absent by design - never write a zero for it.",
    meta: { rows: rows.length, kept: kept, dup: dup, unmapped: unmapped, from: FROM,
            built: new Date().toISOString().slice(0, 10) },
    weeks: out
  };
  console.log('rows', rows.length, 'kept', kept, 'dupes dropped', dup, 'sites', Object.keys(days).length);

  const s = JSON.stringify(window.__ROLL);          // MINIFIED — the page fetches this on every load
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([s], { type: 'application/json' }));
  a.download = 'reviews_rolling30.json';
  document.body.appendChild(a); a.click();
})();
