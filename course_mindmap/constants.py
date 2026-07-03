"""Constants and help text for course mindmap admin."""

COURSE_TYPE_SKILLLAB = "skilllab.skilllabcourse"

SCOPE_COURSE = "course"
SCOPE_CHAPTER = "chapter"
SCOPE_SECTION = "section"

SCOPE_CHOICES = (
    (SCOPE_COURSE, "Course"),
    (SCOPE_CHAPTER, "Chapter"),
    (SCOPE_SECTION, "Section"),
)

GENERATION_STATUS_DRY_RUN = "dry_run"
GENERATION_STATUS_GENERATED = "generated"
GENERATION_STATUS_VERIFIED = "verified"
GENERATION_STATUS_FAILED = "failed"

GENERATION_STATUS_CHOICES = (
    (GENERATION_STATUS_DRY_RUN, "Dry run"),
    (GENERATION_STATUS_GENERATED, "Generated"),
    (GENERATION_STATUS_VERIFIED, "Verified"),
    (GENERATION_STATUS_FAILED, "Failed"),
)

GRADE_MODE_NONE = "none"
GRADE_MODE_ALL = "all"
GRADE_MODE_SELECTED = "selected"

GRADE_MODE_CHOICES = (
    (GRADE_MODE_NONE, "None — mindmap hidden for all classes"),
    (GRADE_MODE_ALL, "All classes"),
    (GRADE_MODE_SELECTED, "Selected classes only"),
)

IMPLEMENTATION_STEPS = [
    "Select course type (e.g. SkillLab Course) and pick a course.",
    "Choose map type (optional; defaults to site DEFAULT_course_MINDMAP_TYPE).",
    "Click Dry Run to build mindmaps in memory and review the report (nothing saved to DB).",
    "Click Run to persist mindmap JSON rows in the database (fast reads for preview and frontend).",
    "Open Preview from the listing to view each scope (course / chapter / section) in the mindmap widget.",
    "Click Mark as verified after previews look correct — this unlocks placement configuration.",
    "Configure enable title / sidebar / content-area mindmap and class visibility (grades).",
    "To regenerate: open Generate (or Regenerate on preview), select the same course, click Run — replaces all DB mindmap rows and resets verification.",
    "To clean up dry-run logs only: generations list → Action: Delete selected dry-run entries.",
    "To delete a complete mindmap: delete any config/data/generation row, or use Action: Delete complete mindmap.",
    "Phase 2: wire frontend player after admin sign-off on at least one course.",
]

DEBUG_COMMANDS = [
    {
        "title": "Generate mindmap (dry run)",
        "command": "python manage.py export_course_mindmap --course-type skilllab --slug YOUR_COURSE_SLUG --dry-run",
    },
    {
        "title": "Generate mindmap (save to DB)",
        "command": "python manage.py export_course_mindmap --course-type skilllab --slug YOUR_COURSE_SLUG",
    },
    {
        "title": "Generate by course ID",
        "command": "python manage.py export_course_mindmap --course-type skilllab --id 42",
    },
    {
        "title": "Validate existing DB mindmaps for a course",
        "command": "python manage.py export_course_mindmap --course-type skilllab --slug YOUR_COURSE_SLUG --validate-only",
    },
    {
        "title": "List scopes in shell",
        "command": (
            "python manage.py shell -c \"from course_mindmap.models import CourseMindmapData; "
            "print(list(CourseMindmapData.objects.values('scope','scope_id','label','is_valid')))\""
        ),
    },
    {
        "title": "Delete complete mindmap for a course",
        "command": "python manage.py export_course_mindmap --course-type skilllab --id COURSE_ID --delete",
    },
    {
        "title": "Delete all dry-run log rows (shell)",
        "command": (
            "python manage.py shell -c \"from course_mindmap.models import CourseMindmapGeneration; "
            "n,_=CourseMindmapGeneration.objects.filter(dry_run=True).delete(); print(f'Deleted {n} dry-run entries')\""
        ),
    },
    {
        "title": "Run migrations",
        "command": "python manage.py migrate course_mindmap",
    },
]
