import asyncio, base64, json, datetime, os
from playwright.async_api import async_playwright
CSS = """body{font:14px/1.45 -apple-system,Helvetica,Arial,sans-serif;color:#171717;margin:0;padding:24px;max-width:720px}
h4{margin:16px 0 4px;font-size:14px} ul{margin:4px 0;padding-left:18px} li{margin:2px 0}
.h{border-bottom:2px solid #E8730C;padding-bottom:8px;margin-bottom:12px;color:#6B7280;font-size:12.5px} .h b{color:#171717}
.note{color:#6B7280;font-size:12.5px;margin-top:10px} .hd{font-size:20px;font-weight:700;margin:0 0 2px}"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page()
        await pg.goto('file://' + os.path.abspath('keyline-control.html')); await pg.wait_for_timeout(400)
        inner = await pg.evaluate("document.querySelector('#mailprev .mail').innerHTML")
        html = '<html><head><meta charset="utf-8"><style>'+CSS+'</style></head><body><p class="hd">Keyline Control</p>'+inner+'</body></html>'
        open('mail.html','w').write(html)
        subj = (await pg.evaluate("document.querySelector('#mailprev .mail .h').textContent")).split('Subject:')[1].split('Sent:')[0].strip()
        p2 = await b.new_page(); await p2.set_content(html)
        await p2.pdf(path='keyline-'+datetime.date.today().isoformat()+'.pdf', format='A4', margin={'top':'14mm','bottom':'14mm','left':'12mm','right':'12mm'}, print_background=True)
        print(subj); await b.close()
asyncio.run(main())
