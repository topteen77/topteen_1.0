import zipfile
import xml.etree.ElementTree as ET

docx_path = r'g:\new data\topteen data\arvinder\+2 apptitute report new\topteen reference guide -new.docx'
with zipfile.ZipFile(docx_path, 'r') as z:
    root = ET.fromstring(z.read('word/document.xml'))

paragraphs = []
for p in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
    texts = []
    for t in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'):
        if t.text:
            texts.append(t.text)
        if t.tail:
            texts.append(t.tail)
    line = ''.join(texts).strip()
    if line:
        paragraphs.append(line)

for i in range(6, 13):
    print(f'{i+1}. {paragraphs[i]}')
