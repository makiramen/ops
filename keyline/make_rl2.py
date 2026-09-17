"""Small table-based PDF for the v1.7.0 keyline email: reportlab base-14 fonts, no embedding.
Reads email-body.html (the Gmail body), writes keyline-<date>.pdf. Subtitle = argv[1]."""
import sys, datetime, re
from reportlab import rl_config
rl_config.useA85 = 0; rl_config.pageCompression = 1; rl_config.invariant = 1
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm

RED = colors.HexColor('#B3200E'); GREY = colors.HexColor('#6B7280'); LINE = colors.HexColor('#E7E1D6')
T = ParagraphStyle('t', fontName='Helvetica-Bold', fontSize=18, leading=22, spaceAfter=2)
S = ParagraphStyle('s', fontName='Helvetica', fontSize=9, leading=12, textColor=GREY, spaceAfter=8)
B = ParagraphStyle('b', fontName='Helvetica', fontSize=9.5, leading=13)
N = ParagraphStyle('n', parent=B, textColor=GREY, fontSize=8.5, leading=11.5, spaceBefore=4)
H3 = ParagraphStyle('h3', fontName='Helvetica-Bold', fontSize=13, leading=16, spaceBefore=12, spaceAfter=4)
H4 = ParagraphStyle('h4', fontName='Helvetica-Bold', fontSize=11, leading=14, spaceBefore=9, spaceAfter=3)
C = ParagraphStyle('c', fontName='Helvetica', fontSize=8.5, leading=10.5)
CB = ParagraphStyle('cb', parent=C, fontName='Helvetica-Bold')
CR = ParagraphStyle('cr', parent=C, alignment=2)
CH = ParagraphStyle('ch', parent=C, fontName='Helvetica-Bold', textColor=GREY, fontSize=7.5)
CHR = ParagraphStyle('chr', parent=CH, alignment=2)
SUP = ParagraphStyle('sup', parent=C, fontName='Helvetica-Bold', fontSize=8.5)

def esc(t): return t.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def cell(td, right=False):
    """Render a td: bold and red inline where the HTML has it, sub-lines in grey."""
    parts=[]
    for ch in td.children:
        if getattr(ch,'name',None)=='div':
            parts.append('<br/><font color="#6B7280" size="7.5">'+esc(ch.get_text(' ',strip=True))+'</font>')
        elif getattr(ch,'name',None)=='br':
            parts.append('<br/>')
        else:
            txt = ch.get_text(' ',strip=True) if getattr(ch,'name',None) else str(ch).strip()
            if not txt: continue
            style = (ch.get('style','') if getattr(ch,'name',None) else '') or ''
            inner = esc(txt)
            if getattr(ch,'name',None)=='b' or 'font-weight:700' in style: inner='<b>'+inner+'</b>'
            if '#B3200E' in style or (getattr(ch,'name',None) and ch.find(style=re.compile('B3200E'))): inner='<font color="#B3200E">'+inner+'</font>'
            parts.append(inner)
    return Paragraph(' '.join(parts).replace('<br/> ','<br/>'), CR if right else C)

def table_from(tbl, widths):
    rows=[]; styles=[('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),0.3,LINE),
                     ('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),('TOPPADDING',(0,0),(-1,-1),2.5),('BOTTOMPADDING',(0,0),(-1,-1),2.5)]
    ncol=len(widths)
    for tr in tbl.find_all('tr'):
        cells=tr.find_all(['td','th'])
        if len(cells)==1 and cells[0].get('colspan'):
            # supplier band
            txt=esc(cells[0].get_text(' ',strip=True))
            red = cells[0].find(style=re.compile('B3200E')) is not None
            if red: txt=re.sub(r'(today \d\d:\d\d)', r'<font color="#B3200E">\1</font>', txt)
            rows.append([Paragraph(txt, SUP)]+['']*(ncol-1))
            styles += [('SPAN',(0,len(rows)-1),(-1,len(rows)-1)),('BACKGROUND',(0,len(rows)-1),(-1,len(rows)-1),colors.HexColor('#FBF7F0'))]
            continue
        if cells and cells[0].name=='th':
            rows.append([Paragraph(esc(c.get_text(' ',strip=True)), CHR if i>0 and 'right' in (c.get('style') or '') else CH) for i,c in enumerate(cells)])
            continue
        rows.append([cell(c, right=('right' in (c.get('style') or ''))) for c in cells])
    t=Table(rows, colWidths=widths, repeatRows=0)
    t.setStyle(TableStyle(styles)); return t

src=open('email-body.html').read()
soup=BeautifulSoup(src,'html.parser')
story=[Paragraph('Keyline Control', T), Paragraph(esc(sys.argv[1] if len(sys.argv)>1 else ''), S)]
W = A4[0]-30*mm
skip=False
for el in soup.body.children:
    n=getattr(el,'name',None)
    if not n: continue
    txt=el.get_text(' ',strip=True)
    if n=='table' and skip: skip=False; continue
    if n=='p':
        cls=el.get('class') or []
        if 'hd' in cls: continue
        if not cls and txt.startswith('Morning both'): continue
        if 'rag' in cls:
            story.append(Paragraph('<b><font color="#B3200E">'+esc(txt.split('·')[0].strip())+'</font></b> · '+esc('·'.join(txt.split('·')[1:]).strip()), B)); continue
        story.append(Paragraph(esc(txt), N if 'note' in cls else B))
    elif n=='h3':
        if txt.startswith('2.'): skip=True; continue
        story.append(Paragraph(esc(txt), H3))
    elif n=='h4': story.append(Paragraph(esc(txt), H4))
    elif n=='table':
        ncol=max(len(tr.find_all(['td','th'])) for tr in el.find_all('tr'))
        if ncol==4: widths=[W*0.40, W*0.20, W*0.20, W*0.20]
        else: widths=[W*0.07, W*0.26, W*0.12, W*0.13, W*0.13, W*0.12, W*0.17]
        story.append(table_from(el, widths))
out='keyline-'+datetime.date.today().isoformat()+'.pdf'
SimpleDocTemplate(out, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=14*mm, bottomMargin=14*mm,
                  title='Keyline Control', author='Maki & Ramen').build(story)
print(out)
