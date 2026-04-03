Counselor course mindmaps (JSON)
================================

Place JSON files here (collected as static assets):

  course.json              — Full course map (curriculum page). Shown when this file exists and counselor course mindmaps are enabled (Core website settings).
  chapter_<id>.json        — One chapter (e.g. chapter_3.json). When present, a mindmap icon appears on that chapter’s row in course learning (same pattern as part mindmaps).
  part_<id>.json           — One part (e.g. part_99.json). Mindmap tab / sidebar icon when file exists and counselor course mindmaps are enabled.

Each file must be valid JSON with a "markdown" string for Markmap, for example:

  {"markdown": "# Root\n## Child\n### Leaf"}

After adding files, run collectstatic in production if applicable.

Regenerate from the database (also writes richer JSON with an "xmind" tree under ../coursemindmap/<segment>/):
  python manage.py export_course_mindmap_json --segment 14
Then copy course.json / chapter_*.json / part_*.json from that folder into this directory as needed.
