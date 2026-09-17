"""Compact the v1.7.0 email body for the Gmail send tool: same content and column layout as mail.html, but with
table attributes instead of long repeated inline styles. Reads email-body.html, writes email-compact.html."""
import re
from bs4 import BeautifulSoup, NavigableString

G = '#6B7280'; R = '#B3200E'
src = open('email-body.html').read()
soup = BeautifulSoup(src, 'html.parser')

def inline(node):
    """Render a cell's children compactly: b stays b, red spans become font color, sub-line divs become br+small."""
    out = []
    for ch in node.children:
        if isinstance(ch, NavigableString):
            t = str(ch).strip()
            if t: out.append(t)
            continue
        n = ch.name; st = ch.get('style', '') or ''
        if n == 'div':
            out.append('<br><font color="%s" size="1">%s</font>' % (G, ch.get_text(' ', strip=True)))
            continue
        if n == 'br': out.append('<br>'); continue
        if n == 'a':
            out.append('<a href="%s">%s</a>' % (ch.get('href'), ch.get_text(' ', strip=True))); continue
        inner = inline(ch) if ch.find(True) else ch.get_text(' ', strip=True)
        if n == 'b' or 'font-weight:700' in st: inner = '<b>' + inner + '</b>'
        if R in st: inner = '<font color="%s">%s</font>' % (R, inner)
        elif G in st: inner = '<font color="%s">%s</font>' % (G, inner)
        out.append(inner)
    return ' '.join(out).replace(' <br>', '<br>').replace('<br> ', '<br>')

parts = []
for el in soup.body.children:
    n = getattr(el, 'name', None)
    if not n: continue
    if n == 'p':
        cls = el.get('class') or []
        if 'hd' in cls: parts.append('<p style="font-size:20px;font-weight:700;margin:0 0 2px">Keyline Control</p>'); continue
        if 'rag' in cls:
            t = el.get_text(' ', strip=True)
            parts.append('<p style="margin:0 0 6px"><b><font color="%s">%s</font></b> %s</p>' % (R, t.split(' ·')[0], ' ·' + ' ·'.join(t.split(' ·')[1:]) if ' ·' in t else '')); continue
        if 'note' in cls: parts.append('<p style="color:%s;font-size:12.5px;margin:6px 0 12px">%s</p>' % (G, inline(el))); continue
        parts.append('<p style="margin:0 0 12px">%s</p>' % inline(el))
    elif n == 'h3': parts.append('<h3 style="font-size:14.5px;margin:18px 0 6px;color:#B5470B">%s</h3>' % el.get_text(' ', strip=True))
    elif n == 'h4':
        parts.append('<h4 style="margin:16px 0 4px;font-size:14px">%s</h4>' % inline(el))
    elif n == 'table':
        rows = ['<table cellpadding="4" cellspacing="0" width="100%" style="font-size:13px;margin:3px 0 12px;border-collapse:collapse">']
        for tr in el.find_all('tr'):
            cells = tr.find_all(['td', 'th'])
            if not cells: continue
            if len(cells) == 1 and cells[0].get('colspan'):
                rows.append('<tr><td colspan="%s" style="padding-top:9px;border-bottom:1px solid #E7E1D6">%s</td></tr>' % (cells[0]['colspan'], inline(cells[0])))
                continue
            if cells[0].name == 'th':
                rows.append('<tr>' + ''.join('<th align="%s" style="font-size:10.5px;color:%s;border-bottom:1px solid #E7E1D6">%s</th>' % ('right' if 'right' in (c.get('style') or '') else 'left', G, c.get_text(' ', strip=True).upper()) for c in cells) + '</tr>')
                continue
            tds = []
            for c in cells:
                st = c.get('style') or ''
                attrs = ' align="right" nowrap' if 'right' in st else ''
                tds.append('<td%s>%s</td>' % (attrs, inline(c)))
            rows.append('<tr valign="top" style="border-bottom:1px solid #F1ECE2">' + ''.join(tds) + '</tr>')
        rows.append('</table>')
        parts.append(''.join(rows))
html = html_fix = '<div style="font-family:-apple-system,Helvetica,Arial,sans-serif;font-size:14px;line-height:1.45;color:#171717;max-width:760px">' + '\n'.join(parts) + '</div>'
html = html.replace('</a> .','</a>.').replace('</b> ,','</b>,')
assert '—' not in html and '–' not in html
open('email-compact.html', 'w').write(html)
print(len(html))
