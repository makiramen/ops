import sys
p=sys.argv[1]; s=open(p,encoding='utf-8').read()
def rep(a,b):
    global s; assert s.count(a)==1,a[:60]; s=s.replace(a,b)
rep(" * v4 (6 Oct 2026): adds DATA.slerp from the Slerp Orders SoT sheet for the\n *   Hub's Slerp tab (v6.5), replacing its 5 Oct snapshot. Built after doGet,\n *   wrapped so a Slerp failure never blocks the publish (status.slerp records it).\n */",
    " * v4 (6 Oct 2026): adds DATA.slerp from the Slerp Orders SoT sheet for the\n *   Hub's Slerp tab (v6.5), replacing its 5 Oct snapshot. Built after doGet,\n *   wrapped so a Slerp failure never blocks the publish (status.slerp records it).\n * v5 (20 Oct 2026): DATA.slerp.dayStores = [[date, store, orders, revenue]] for\n *   the latest 60 days, so the Hub's Slerp Daily / Weekly / Monthly views (v6.10)\n *   can show which sites had orders. Nothing else changes.\n */")
rep("  var byStore = {}, byDay = {}, byCust = {};",
    "  var byStore = {}, byDay = {}, byCust = {}, byDayStore = {};")
rep("    (byDay[d] = byDay[d] || [d, 0, 0])[1]++; byDay[d][2] += paid;",
    "    (byDay[d] = byDay[d] || [d, 0, 0])[1]++; byDay[d][2] += paid;\n    var dk = d + '|' + st; (byDayStore[dk] = byDayStore[dk] || [d, st, 0, 0])[2]++; byDayStore[dk][3] += paid;")
rep("  var fin = function(rows) { return rows.map(function(r) { return [r[0], r[1], r2(r[2])]; }); };",
    "  var fin = function(rows) { return rows.map(function(r) { return [r[0], r[1], r2(r[2])]; }); };\n  var dayKeys = Object.keys(byDay).sort().reverse().slice(0, 60), dayKeep = {};\n  dayKeys.forEach(function(k) { dayKeep[k] = 1; });\n  var dayStores = Object.keys(byDayStore).filter(function(k) { return dayKeep[byDayStore[k][0]]; }).sort()\n    .map(function(k) { var r = byDayStore[k]; return [r[0], r[1], r[2], r2(r[3])]; });")
rep("    days: fin(Object.keys(byDay).sort().reverse().slice(0, 60).map(function(k) { return byDay[k]; })),",
    "    days: fin(dayKeys.map(function(k) { return byDay[k]; })),\n    dayStores: dayStores,")
rep("'\\nstores ' + s.stores.length + ' · days ' + s.days.length + ' · products ' + s.products.length);",
    "'\\nstores ' + s.stores.length + ' · days ' + s.days.length + ' · dayStores ' + s.dayStores.length + ' · products ' + s.products.length);")
rep("HubPublish.gs — MARKETING HUB STATIC PAYLOAD PUBLISHER  ·  v3, 8 Sept 2026","HubPublish.gs — MARKETING HUB STATIC PAYLOAD PUBLISHER  ·  v5, 20 Oct 2026")
open(sys.argv[2],'w',encoding='utf-8').write(s); print('ok')
