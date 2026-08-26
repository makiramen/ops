/* extract_reviews_rawdata.js — Pipe 5 (reviews) STEP 1, browser-side.
 *
 * WHY BROWSER-SIDE: the container cannot reach docs.google.com. Run this in the
 * DevTools console of a tab that is already open on the Google Reviews workbook
 * (any docs.google.com tab with the user's session works — the gviz call is
 * same-origin and uses the logged-in cookies).
 *
 *   https://docs.google.com/spreadsheets/d/1aFGfbGrEBeqWny8myF6H4LVxO0YegT0MdIJHrxpxk3I/edit?gid=284143046
 *
 * WHAT IT DOES: pulls the `Raw Data` tab (gid 284143046 — FULL lifetime history
 * per location), dedupes on reviewId, maps source labels to site codes, buckets
 * every review into its Mon–Sun week by the date it was RECEIVED, and downloads
 * one aggregate JSON. Feed that file to builders/build_weekly_reviews.py.
 *
 * 🔴 WHY NOT THE OTHER TWO SOURCES:
 *   - the per-site "Maki N -" star tabs are CORRUPT and hand-maintained (frozen
 *     tabs, an average of 12.30, M17 reading 158 reviews in a week that had 47);
 *   - the DAILY feed (Pipe 8b) is healthy but its `reviews[]` array is a DISPLAY
 *     LIST: positives are capped at 12 per site per file and comment-less
 *     reviews are dropped entirely. Its COUNTS are fine, its LIST is not.
 *   Raw Data is the only complete source. Use it for everything.
 *
 * 🔴 WEEK-DATE MATCHING is the whole point: a weekly slice contains exactly the
 * reviews RECEIVED Monday..Sunday of that week. Never a rolling 7-day window.
 *
 * Source traps (learned the hard way — see project_daily_reviews_pipe):
 *   - col L `Date` is dd/mm/yyyy TEXT on a plain select, but comes back as
 *     `Date(y,m,d)` (month 0-indexed) if the query GROUPs on it. isoOf() handles
 *     both, and falls back to createTime (col G) when L is blank.
 *   - dedupe on col A reviewId is MANDATORY (684 dupes in 7,879 rows on 19/08).
 *   - `Leith` is a real, high-volume source and is DROPPED on purpose (M4, dead
 *     site). `West end` (MAF1), `Maki O2` (MAF3), `NQ` (MAF-NQ) are non-dashboard.
 *     `#N/A` is the Meet Fresh orphan — a different business entirely.
 *   - IKI2 (Ikigai) has NO rows in this workbook, ever. It is not wired. Never
 *     invent a zero for it — leave it null.
 */
(async function () {
  const SHEET = '1aFGfbGrEBeqWny8myF6H4LVxO0YegT0MdIJHrxpxk3I';
  const GID   = '284143046';                 // Raw Data
  const FROM  = '2026-04-20';                // pull window start (createTime, col G, string compare)
  const WEEK0 = [2026, 4, 4];                // first Monday to bucket: 2026-05-04 (month is 0-indexed)

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

  // LOCKED label -> site code map. Verify against reference_maki_site_codes before editing.
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

  function isoOf(v, f, createTime) {
    if (v == null || v === '') return createTime ? String(createTime).slice(0, 10) : null;
    const s = String(v);
    let m = s.match(/^Date\((\d+),(\d+),(\d+)/);
    if (m) return m[1] + '-' + String(+m[2] + 1).padStart(2, '0') + '-' + String(+m[3]).padStart(2, '0');
    m = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);           // dd/mm/yyyy
    if (m) return m[3] + '-' + String(+m[2]).padStart(2, '0') + '-' + String(+m[1]).padStart(2, '0');
    m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
    if (m) return m[1] + '-' + String(+m[2]).padStart(2, '0') + '-' + String(+m[3]).padStart(2, '0');
    return createTime ? String(createTime).slice(0, 10) : null;
  }

  // A=reviewId D=author E=rating(words) F=comment G=createTime K=site L=date
  const q = "select A,D,E,F,G,K,L where G >= '" + FROM + "' ";
  const url = 'https://docs.google.com/spreadsheets/d/' + SHEET +
              '/gviz/tq?gid=' + GID + '&tqx=out:json&tq=' + encodeURIComponent(q);
  const raw = await (await fetch(url, { credentials: 'include' })).text();
  const rows = JSON.parse(raw.substring(raw.indexOf('{'), raw.lastIndexOf('}') + 1)).table.rows;

  const seen = {}, recs = [], unmapped = {};
  let dup = 0;
  for (const row of rows) {
    const c = row.c;
    const id = c[0] && c[0].v != null ? String(c[0].v) : null;
    if (id) { if (seen[id]) { dup++; continue; } seen[id] = 1; }
    const label = c[5] && c[5].v != null ? String(c[5].v).trim() : '';   // trailing space on 'Renfield '
    if (DROP[label]) continue;
    const code = MAP[label];
    if (!code) { unmapped[label] = (unmapped[label] || 0) + 1; continue; }
    const stars = RW[String((c[2] && c[2].v) || '').toUpperCase().trim()];
    if (!stars) continue;
    const iso = isoOf(c[6] ? c[6].v : null, c[6] ? c[6].f : null, c[4] ? c[4].v : null);
    if (!iso) continue;
    recs.push({ s: stars, a: (c[1] && c[1].v) ? String(c[1].v) : null,
                t: (c[3] && c[3].v) ? String(c[3].v).trim() : '', d: iso, c: code });
  }

  const weeks = [];
  for (let i = 0; i < NWEEKS; i++) {
    weeks.push(new Date(Date.UTC(WEEK0[0], WEEK0[1], WEEK0[2] + 7 * i)).toISOString().slice(0, 10));
  }

  console.log('weeks emitted', NWEEKS, ':', weeks[0], '->', weeks[weeks.length - 1]);

  const out = {};
  for (const wk of weeks) {
    const from = wk;
    const to = new Date(Date.UTC(+wk.slice(0, 4), +wk.slice(5, 7) - 1, +wk.slice(8, 10) + 6)).toISOString().slice(0, 10);
    const per = {};
    for (const x of recs) {
      if (x.d < from || x.d > to) continue;                     // <-- the week-date match
      const p = per[x.c] || (per[x.c] = { n: 0, sum: 0, bd: {'5':0,'4':0,'3':0,'2':0,'1':0}, neg: 0, list: [] });
      p.n++; p.sum += x.s; p.bd[String(x.s)]++;
      if (x.s <= 3) { p.neg++; if (x.t) p.list.push({ stars: x.s, author: x.a, text: x.t, date: x.d, url: null }); }
    }
    for (const k in per) {
      const p = per[k];
      p.avg = Math.round(p.sum / p.n * 10000) / 10000; delete p.sum;
      p.list.sort((a, b) => a.date < b.date ? 1 : a.date > b.date ? -1 : b.stars - a.stars);
    }
    out[wk] = { from, to, sites: per };
  }

  // firstSeen lets the builder tell "connected but no reviews this week" (write 0)
  // apart from "not connected yet" (leave null). M19 2026-06-04, M20 2026-06-22.
  const firstSeen = {};
  for (const x of recs) if (!firstSeen[x.c] || x.d < firstSeen[x.c]) firstSeen[x.c] = x.d;

  const payload = JSON.stringify({
    meta: { rows: rows.length, kept: recs.length, dup, unmapped, firstSeen }, weeks: out
  });
  console.log('rows', rows.length, 'kept', recs.length, 'dupes dropped', dup, 'UNMAPPED', unmapped);
  if (Object.keys(unmapped).length) console.warn('🔴 UNMAPPED LABELS — do not ship until these are resolved');

  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([payload], { type: 'application/json' }));
  a.download = 'maki_reviews_agg_' + new Date().toISOString().slice(0, 10) + '.json';
  document.body.appendChild(a); a.click();
})();
