"""Help sections for admin sidebar popup."""

SIDEBAR_HELP_SECTIONS = [
    {
        "id": "create",
        "title": "How to create a mindmap",
        "steps": [
            "Go to Course mindmap generations → Generate mindmap (or use the link on a SkillLab course edit page).",
            "Select course type: SkillLab Course.",
            "Pick the target course from the dropdown.",
            "Optional: choose map type (defaults to site DEFAULT_course_MINDMAP_TYPE).",
            "Click Dry Run first to preview without saving.",
            "Click Run to save mindmap JSON to the database (CourseMindmapData).",
        ],
    },
    {
        "id": "preview",
        "title": "Preview & verify",
        "steps": [
            "From the generations list, click Preview on any row.",
            "Expand each scope (course / chapter / section) to see the mindmap iframe.",
            "Review warnings (e.g. sections with no headings).",
            "When satisfied, click Mark as verified on a Run (not dry run) generation.",
            "Verification unlocks placement configuration (title / sidebar / content area toggles).",
        ],
    },
    {
        "id": "configure",
        "title": "Configure placements & classes",
        "steps": [
            "Open Course mindmap configurations after verification.",
            "Enable title mindmap, sidebar mindmap, and/or content area mindmap.",
            "Set grade mode: None (hidden), All classes, or Selected classes (multiselect grades).",
            "Save — toggles are blocked until the mindmap is verified.",
        ],
    },
    {
        "id": "regenerate",
        "title": "Regenerate an existing mindmap",
        "steps": [
            "Open Generate mindmap (or Regenerate on the preview page).",
            "Select the same course type and course.",
            "Click Run (not Dry Run).",
            "This replaces all CourseMindmapData rows and resets is_verified to False.",
            "Preview again → Mark as verified → re-configure placements if needed.",
        ],
    },
    {
        "id": "remove",
        "title": "Delete a complete mindmap",
        "steps": [
            "Deleting any config, data row, or generation log removes the ENTIRE mindmap for that course.",
            "Removed: all CourseMindmapData rows, CourseMindmapConfig (placements + grades), and all generation logs.",
            "Use Action: Delete complete mindmap — or the standard Delete button on any mindmap record.",
            "Dry-run logs only: Action → Delete selected dry-run entries (does NOT remove live data).",
            "Terminal: python manage.py export_course_mindmap --course-type skilllab --id COURSE_ID --delete",
        ],
    },
]
