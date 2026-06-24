# -*- coding: utf-8 -*-
import zipfile
import xml.etree.ElementTree as ET
import re

docx = r'g:\new data\topteen data\arvinder\+2 apptitute report new\topteen reference guide -new.docx'
out = r'e:\shanti sir\topteen_1.0\scripts\doc_full.txt'

with zipfile.ZipFile(docx) as z:
    root = ET.fromstring(z.read('word/document.xml'))

ps = []
for p in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
    t = ''.join((x.text or '') + (x.tail or '') for x in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'))
    if t.strip():
        ps.append(t.strip())

with open(out, 'w', encoding='utf-8') as f:
    for i, p in enumerate(ps):
        f.write(f'{i+1}|{p}\n')

print(len(ps), 'paragraphs written')
