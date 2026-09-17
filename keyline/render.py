import asyncio, json, sys, os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width':1280,'height':900})
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('file://' + os.path.abspath('keyline-control.html')); await pg.wait_for_timeout(500)
        # force UK clock: page uses device clock; container is UTC (UK is BST = UTC+1) so evaluate stats only
        stats = await pg.evaluate("""()=>{const c={};ROWS.forEach(r=>c[r.status]=(c[r.status]||0)+1);
          return {c, rag:SITES.map(s=>s.code+':'+siteRag(s.code).rag).join(' '),
            top:ROWS.filter(r=>['URGENT','ORDER'].includes(r.status)).map(r=>r.site+' '+r.item.name+' '+r.status+' D='+r.cover+' Rnow='+r.Rnow+' thr='+r.threshold+' '+r.sup).join('\\n'),
            watch:ROWS.filter(r=>r.status==='WATCH').map(r=>r.site+' '+r.item.name+' D='+r.cover+' thr='+r.threshold+' '+r.sup+(r.assumed?' (asm)':'')).join('\\n'),
            assumed:ROWS.filter(r=>r.assumed).length}}""")
        # dump what this run is ASKING each site to order, so tomorrow can check whether it happened.
        # naive UK wall-clock strings throughout (parseTs in part_e reads them back the same way); the page
        # runs on Europe/London because render.py is invoked with TZ=Europe/London.
        asks = await pg.evaluate("""()=>{
          const p=n=>(n<10?'0':'')+n;
          const iso=d=>d? d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate())+'T'+p(d.getHours())+':'+p(d.getMinutes()) : null;
          return ROWS.filter(r=>['URGENT','ORDER'].includes(r.status) && r.netOrder>0).map(r=>({
            site:r.site, key:r.item.id, name:r.item.name, sup:r.sup, qty:r.netOrder, status:r.status,
            cut:(r.del && r.del.next && r.del.next.cut) ? iso(r.del.next.cut).slice(0,11) + (r.del.next.cutTime || '00:00') : null}));}""")
        import datetime as _dt
        _now = _dt.datetime.now()
        _day = _now.strftime('%Y-%m-%d'); _ts = _now.strftime('%Y-%m-%dT%H:%M')
        for a in asks: a['d'] = _day; a['ts'] = _ts
        open('asks-%s.json' % _day, 'w').write(json.dumps(asks, separators=(', ', ': ')))
        print('asks', len(asks), '->', 'asks-%s.json' % _day)

        # stamp the RED / AMBER site lists into part_data so other pages (ops shell badge) can read them without running the engine
        rag = dict(x.split(':') for x in stats['rag'].split())
        pd = open('part_data.html').read()
        import re as _re
        m = _re.search(r'"meta": (\{.*?\}), "siteMeta"', pd)
        meta = json.loads(m.group(1)); meta['redSites']=[k for k,v in rag.items() if v=='RED']; meta['amberSites']=[k for k,v in rag.items() if v=='AMBER']
        pd = pd[:m.start(1)] + json.dumps(meta) + pd[m.end(1):]
        open('part_data.html','w').write(pd)
        print(json.dumps(stats['c']), stats['rag'], 'assumed', stats['assumed']); print(stats['top']); print('--- watch'); print(stats['watch']); print('errors', errs)
        await pg.screenshot(path='shot-today.png', full_page=False)
        await pg.click('button[data-view="email"]'); await pg.wait_for_timeout(200)
        html = await pg.evaluate("document.getElementById('mailprev').innerHTML")
        open('mail.html','w').write(html)
        await pg.screenshot(path='shot-email.png', full_page=True)
        await b.close()
asyncio.run(main())
