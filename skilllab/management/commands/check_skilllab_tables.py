"""
Check all Skill Lab tables exist in the database.
Reports missing tables and optionally creates them (--fix).
"""
from django.core.management.base import BaseCommand
from django.db import connection


EXPECTED_SKILLLAB_TABLES = [
    'skilllab_skilllabcourse',
    'skilllab_skilllabcoursechapter',
    'skilllab_skilllabcourseactivity',
    'skilllab_skilllabchaptersection',
    'skilllab_skilllabmcq',
    'skilllab_skilllabmcqquestion',
    'skilllab_skilllabmcqanswer',
    'skilllab_skilllabworksheetprogress',
    'skilllab_skilllabmcqattempt',
    'skilllab_skilllabcourseprogress',
    'skilllab_skilllabcourseprogresssummary',
    'skilllab_skilllabcourseresume',
    'skilllab_skilllabcoursepayment',
]

# SQL to create missing MCQ tables (when 0002 was faked but only skilllab_skilllabmcq existed)
CREATE_MCQ_QUESTION_SQL = """
CREATE TABLE IF NOT EXISTS skilllab_skilllabmcqquestion (
    id bigint NOT NULL AUTO_INCREMENT,
    created datetime(6) NOT NULL,
    modified datetime(6) NOT NULL,
    object_status smallint NOT NULL DEFAULT 1,
    question_number int unsigned NOT NULL DEFAULT 1,
    question_text longtext NOT NULL,
    `order` int unsigned NOT NULL DEFAULT 0,
    mcq_id bigint NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY skilllab_skilllabmcqq_mcq_id_question__uniq (mcq_id, question_number),
    KEY skilllab_skilllabmcqq_mcq_id_idx (mcq_id),
    CONSTRAINT skilllab_skilllabmcqq_mcq_id_fk FOREIGN KEY (mcq_id) REFERENCES skilllab_skilllabmcq (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

CREATE_MCQ_ANSWER_SQL = """
CREATE TABLE IF NOT EXISTS skilllab_skilllabmcqanswer (
    id bigint NOT NULL AUTO_INCREMENT,
    created datetime(6) NOT NULL,
    modified datetime(6) NOT NULL,
    object_status smallint NOT NULL DEFAULT 1,
    answer_letter varchar(1) NOT NULL,
    answer_text longtext NOT NULL,
    is_correct tinyint(1) NOT NULL DEFAULT 0,
    `order` int unsigned NOT NULL DEFAULT 0,
    question_id bigint NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY skilllab_skilllabmcqa_question_id_answer__uniq (question_id, answer_letter),
    KEY skilllab_skilllabmcqa_question_id_idx (question_id),
    CONSTRAINT skilllab_skilllabmcqa_question_id_fk FOREIGN KEY (question_id) REFERENCES skilllab_skilllabmcqquestion (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

# Map of table -> SQL to create it (only for tables we can safely create via raw SQL)
CREATE_SQL_MAP = {
    'skilllab_skilllabmcqquestion': CREATE_MCQ_QUESTION_SQL,
    'skilllab_skilllabmcqanswer': CREATE_MCQ_ANSWER_SQL,
}


class Command(BaseCommand):
    help = 'Check all Skill Lab tables exist. Use --fix to create missing MCQ tables.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Create missing skilllab_skilllabmcqquestion and skilllab_skilllabmcqanswer tables',
        )

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES LIKE 'skilllab_%'")
            existing = {row[0] for row in cursor.fetchall()}

        missing = [t for t in EXPECTED_SKILLLAB_TABLES if t not in existing]
        extra = [t for t in existing if t not in EXPECTED_SKILLLAB_TABLES]

        self.stdout.write(f"Expected Skill Lab tables: {len(EXPECTED_SKILLLAB_TABLES)}")
        self.stdout.write(f"Found in DB: {len(existing)}")
        self.stdout.write("")

        if missing:
            self.stdout.write(self.style.WARNING(f"Missing tables ({len(missing)}):"))
            for t in missing:
                self.stdout.write(f"  - {t}")
            self.stdout.write("")
        else:
            self.stdout.write(self.style.SUCCESS("All expected tables exist."))

        if extra:
            self.stdout.write(self.style.NOTICE(f"Extra tables (not in expected list): {len(extra)}"))
            for t in sorted(extra):
                self.stdout.write(f"  - {t}")
            self.stdout.write("")

        if missing and options.get('fix'):
            fixable = [t for t in missing if t in CREATE_SQL_MAP]
            if not fixable:
                self.stdout.write(self.style.ERROR(
                    "Cannot auto-fix: missing tables require Django migrations. "
                    "Run: python manage.py migrate skilllab"
                ))
                return

            self.stdout.write(f"Creating missing tables: {fixable}")
            with connection.cursor() as cursor:
                for table in fixable:
                    sql = CREATE_SQL_MAP[table]
                    try:
                        cursor.execute(sql)
                        self.stdout.write(self.style.SUCCESS(f"  Created: {table}"))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"  Failed {table}: {e}"))

            unfixable = [t for t in missing if t not in CREATE_SQL_MAP]
            if unfixable:
                self.stdout.write(self.style.WARNING(
                    f"Still missing (run migrate): {unfixable}"
                ))
        elif missing:
            self.stdout.write("Run with --fix to create missing MCQ tables, or: python manage.py migrate skilllab")
