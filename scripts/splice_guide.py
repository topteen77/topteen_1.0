main_path = r'e:\shanti sir\topteen_1.0\templates\template20\topteen_guide.html'
sections_path = r'e:\shanti sir\topteen_1.0\templates\template20\_guide_sections_full.html'

with open(main_path, 'r', encoding='utf-8') as f:
    content = f.read()
with open(sections_path, 'r', encoding='utf-8') as f:
    new_sections = f.read()

start = content.find('        <!-- ═══════ SECTION 1: OVERVIEW')
if start == -1:
    start = content.find('        <!-- SECTION 1: OVERVIEW')
idx12 = content.find('id="section-12"')
end = content.find('      </div>\n    </div>\n  </main>', idx12)
if start == -1 or end == -1:
    raise SystemExit(f'markers not found start={start} end={end}')
new_content = content[:start] + new_sections + content[end:]
with open(main_path, 'w', encoding='utf-8') as f:
    f.write(new_content)
print('Updated main HTML, chars:', len(new_content))
