/* extract_reviews_fulltext.js — Reviews Intelligence (Pipe 5c) STEP 1, browser-side.
 *
 * Run in the DevTools console (or the Chrome MCP javascript tool) of a tab that is open on
 * the Google Reviews workbook:
 *   https://docs.google.com/spreadsheets/d/1aFGfbGrEBeqWny8myF6H4LVxO0YegT0MdIJHrxpxk3I/edit?gid=284143046
 *
 * WHAT IT DOES: pulls EVERY review row from the `Raw Data` tab (gid 284143046) received since
 * FROM, dedupes on reviewId, maps the source label to the site code and downloads ONE flat JSON
 * (`maki_reviews_full_<date>.json`) carrying the FULL comment text of every review, positive and
 * negative, plus the createTime (UTC, to the second) so day-of-week / time-of-day cuts are possible.
 * Feed that file to builders/build_reviews_intel.py.
 *
 * Differences from extract_reviews_rawdata.js (Pipe 5): that script keeps text for <=3* only and
 * pre-buckets by week. This one keeps everything and leaves all aggregation to the builder, so the
 * same file serves week, month and quarter views.
 *
 * Source facts (verified 25/08/2026): Raw Data columns are
 *   A reviewId | B locationId | C siteName | D author_name | E rating (FIVE..ONE) | F comment |
 *   G createTime (ISO UTC) | H updateTime | K Site (label) | L Date (dd/mm/yyyy text, or Date(y,m,d))
 * There is NO owner-reply column in the source, so reply/response tracking is not possible here.
 *
 * Same traps as the other extractors: dedupe is mandatory (713 dupes in 8,444 rows on 25/08);
 * `Leith` / `West end` / `Maki O2` / `NQ` / `#N/A` are dropped on purpose; IKI2 has no rows,
 * ever; any OTHER unmapped label is logged loudly and must be resolved before the build ships.
 */
(async function () {
  const SHEET = '1aFGfbGrEBeqWny8myF6H4LVxO0YegT0MdIJHrxpxk3I';
  const GID   = '284143046';
  const FROM  = '2026-04-20';   // createTime lower bound (string compare on ISO)

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

  function isoOf(v, createTime) {
    if (v == null || v === '') return createTime ? String(createTime).slice(0, 10) : null;
    const s = String(v);
    let m = s.match(/^Date\((\d+),(\d+),(\d+)/);
    if (m) return m[1] + '-' + String(+m[2] + 1).padStart(2, '0') + '-' + String(+m[3]).padStart(2, '0');
    m = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
    if (m) return m[3] + '-' + String(+m[2]).padStart(2, '0') + '-' + String(+m[1]).padStart(2, '0');
    m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
    if (m) return m[1] + '-' + String(+m[2]).padStart(2, '0') + '-' + String(+m[3]).padStart(2, '0');
    return createTime ? String(createTime).slice(0, 10) : null;
  }

  // A=reviewId D=author E=rating F=comment G=createTime K=site L=date
  const q = "select A,D,E,F,G,K,L where G >= '" + FROM + "'";
  const url = 'https://docs.google.com/spreadsheets/d/' + SHEET +
              '/gviz/tq?gid=' + GID + '&tqx=out:json&headers=1&tq=' + encodeURIComponent(q);
  const raw = await (await fetch(url, { credentials: 'include' })).text();
  const rows = JSON.parse(raw.substring(raw.indexOf('{'), raw.lastIndexOf('}') + 1)).table.rows;

  const seen = {}, recs = [], unmapped = {}, dropped = {};
  let dup = 0, noStars = 0, noDate = 0;
  for (const row of rows) {
    const c = row.c;
    const id = c[0] && c[0].v != null ? String(c[0].v) : null;
    if (id) { if (seen[id]) { dup++; continue; } seen[id] = 1; }
    const label = c[5] && c[5].v != null ? String(c[5].v).trim() : '';
    if (DROP[label]) { dropped[label] = (dropped[label] || 0) + 1; continue; }
    const code = MAP[label];
    if (!code) { unmapped[label] = (unmapped[label] || 0) + 1; continue; }
    const stars = RW[String((c[2] && c[2].v) || '').toUpperCase().trim()];
    if (!stars) { noStars++; continue; }
    const ct = c[4] && c[4].v ? String(c[4].v) : null;
    const d = isoOf(c[6] ? c[6].v : null, ct);
    if (!d) { noDate++; continue; }
    recs.push({
      id: id ? id.slice(0, 26) : null,
      c: code, s: stars, d: d, ct: ct,
      a: (c[1] && c[1].v) ? String(c[1].v) : null,
      t: (c[3] && c[3].v) ? String(c[3].v).trim() : ''
    });
  }
  recs.sort((x, y) => (x.d + (x.ct || '')) < (y.d + (y.ct || '')) ? -1 : 1);

  const firstSeen = {}, lastSeen = {}, perSite = {};
  for (const x of recs) {
    if (!firstSeen[x.c] || x.d < firstSeen[x.c]) firstSeen[x.c] = x.d;
    if (!lastSeen[x.c] || x.d > lastSeen[x.c]) lastSeen[x.c] = x.d;
    perSite[x.c] = (perSite[x.c] || 0) + 1;
  }
  const pulledAt = new Date().toISOString();
  const payload = JSON.stringify({
    meta: { pulledAt, from: FROM, rows: rows.length, kept: recs.length, dup, noStars, noDate,
            dropped, unmapped, firstSeen, lastSeen, perSite,
            withText: recs.filter(x => x.t).length },
    reviews: recs
  });
  console.log('rows', rows.length, 'kept', recs.length, 'dup', dup, 'dropped', dropped, 'UNMAPPED', unmapped);
  if (Object.keys(unmapped).length) console.warn('🔴 UNMAPPED LABELS — resolve before shipping', unmapped);

  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([payload], { type: 'application/json' }));
  a.download = 'maki_reviews_full_' + pulledAt.slice(0, 10) + '.json';
  document.body.appendChild(a); a.click();
  window.__RV_META = JSON.parse(payload).meta;
  return window.__RV_META;
})();
