import zipfile, xml.etree.ElementTree as ET
docx = r'g:\new data\topteen data\arvinder\+2 apptitute report new\topteen reference guide -new.docx'
with zipfile.ZipFile(docx) as z:
    root = ET.fromstring(z.read('word/document.xml'))
ps = []
for p in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
    t = ''.join((x.text or '') + (x.tail or '') for x in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'))
    if t.strip(): ps.append(t.strip())
start = ps.index('How to Use This Guide')
for p in ps[start:start+20]:
    print(p)
