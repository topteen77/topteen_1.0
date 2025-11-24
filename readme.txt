python3 scripts/convert_docx_to_html.py
python manage.py upload_careers_from_txt --input-dir career_html_output
python manage.py upload_careers_from_txt --input-dir career_html_output --dry-run



# Test with 2 records
python manage.py upload_careers_from_txt --input-dir career_html_output --limit 2

# Test with 5 records
python manage.py upload_careers_from_txt --input-dir career_html_output --limit 5

# Full upload (when ready)
python manage.py upload_careers_from_txt --input-dir career_html_output

# Fix <th> to <td> tags in both description and description_en
python manage.py fix_career_table_tags --dry-run
python manage.py fix_career_table_tags

# Fix <li> tags with numbers/bullets in both description and description_en  
python manage.py fix_li_tags_with_numbers_bullets --dry-run
python manage.py fix_li_tags_with_numbers_bullets