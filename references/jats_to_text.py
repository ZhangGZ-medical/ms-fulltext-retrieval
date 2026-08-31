import sys,re
from xml.etree import ElementTree as ET
f=sys.argv[1]
t=ET.parse(f); r=t.getroot()
body=r.find('.//body')
def txt(e):
    return ''.join(e.itertext())
out=[]
for sec in body.findall('.//sec'):
    ti=sec.find('title')
    out.append('## '+(ti.text if ti is not None else '(no title)'))
    for p in sec.findall('p'):
        s=re.sub(r'\s+',' ',txt(p)).strip()
        if len(s)>25: out.append(s)
    for tbl in sec.findall('.//table-wrap'):
        lb=tbl.find('label'); cp=tbl.find('caption')
        out.append('[TABLE %s] %s'%(lb.text if lb is not None else '', re.sub(r'\s+',' ',txt(cp)).strip() if cp is not None else ''))
print('\n\n'.join(out))
