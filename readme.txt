===================================================
--- Student Import (topteen12 → topteen12-old) ---
# Validate and import student data from production (topteen12) to target (topteen12-old).
# Rule: No duplicate student entries. Origin DB is never modified (read-only).
# Run all commands from project root (where manage.py is).

---------- COMPLETE COMMANDS STEP BY STEP ----------

Step 1. Ensure .env has source and target DB settings (already set):
   DB_SOURCE_NAME=topteen12
   DB_SOURCE_HOST=13.234.119.81
   DB_SOURCE_USER=root12
   DB_SOURCE_PASSWORD=root12
   DB_SOURCE_PORT=3306
   DB_TARGET_NAME=topteen12-old
   DB_TARGET_HOST=13.234.119.81
   DB_TARGET_USER=root12
   DB_TARGET_PASSWORD=root12
   DB_TARGET_PORT=3306

Step 2. Dry-run on origin (connect and count only; no full validation):
   python manage.py validate_students_origin_db --dry-run

Step 3. Validate a single student on origin (replace 12345 with real user id):
   python manage.py validate_students_origin_db --student-id 12345

Step 4. Validate all students on origin (read-only; reports duplicates and issues):
   python manage.py validate_students_origin_db

Step 5. If duplicates were reported in Step 4, fix them in origin DB before import. Then run import (when import command is implemented).

Step 6. After import, dry-run on target:
   python manage.py validate_students_target_db --dry-run

Step 7. Validate a single student on target (replace 12345 with user id):
   python manage.py validate_students_target_db --student-id 12345

Step 8. Validate all students on target (verify imported data):
   python manage.py validate_students_target_db

Step 9. Compare record counts source vs target and re-import any missing rows if gap found.

Step 10. Login after import: imported users keep the source DB's hashed password. To log in with a known password (e.g. 12345), set it in the default DB:
   python manage.py set_student_password --email shivagujral03@gmail.com --password 12345 --student-only

---------- END STEP BY STEP ----------

## Environment (use these in .env; validation commands read them automatically)
# Source (topteen12): DB_SOURCE_NAME=topteen12, DB_SOURCE_HOST, DB_SOURCE_USER, DB_SOURCE_PASSWORD, DB_SOURCE_PORT
# Target (topteen12-old): DB_TARGET_NAME=topteen12-old, DB_TARGET_HOST, DB_TARGET_USER, DB_TARGET_PASSWORD, DB_TARGET_PORT
# Example (same host): DB_SOURCE_NAME=topteen12, DB_SOURCE_HOST=13.234.119.81, DB_SOURCE_USER=root12, DB_SOURCE_PASSWORD=root12, DB_SOURCE_PORT=3306
#                       DB_TARGET_NAME=topteen12-old, DB_TARGET_HOST=13.234.119.81, DB_TARGET_USER=root12, DB_TARGET_PASSWORD=root12, DB_TARGET_PORT=3306
# If DB_TARGET_* not set, target falls back to default DATABASES.

## Validation commands (reference)
# Origin DB (topteen12) - read-only
python manage.py validate_students_origin_db --dry-run
python manage.py validate_students_origin_db --dry-run --student-id 12345
python manage.py validate_students_origin_db --student-id 12345
python manage.py validate_students_origin_db

# Target DB (topteen12-old) - read-only, run after import to verify
python manage.py validate_students_target_db --dry-run
python manage.py validate_students_target_db --student-id 12345
python manage.py validate_students_target_db

## Implementation steps (workflow)
Step 1. Configure .env with DB_SOURCE_* (topteen12) and DB_TARGET_* (topteen12-old).
Step 2. Validate origin (read-only): run validate_students_origin_db; use --dry-run first, then --student-id or all.
Step 3. Resolve any duplicate students in origin (duplicate email or duplicate StudentManagement) before export.
Step 4. Run import: copy student data from topteen12 to topteen12-old in FK order, using target DB column list (INFORMATION_SCHEMA) and existence checks so no duplicate student or StudentManagement is created (pending command).
Step 5. Validate target: run validate_students_target_db to verify imported data.
Step 6. Compare record counts per table (source vs target); if gap, re-import missing rows for affected user_ids/studentmanagement_ids.

## Completed
# - institute/student_validation_utils.py: get_db_config, ensure_connection, get_student_user_ids, check_duplicate_students, student_exists_in_target, student_management_exists, validate_one_student, STUDENT_RELATED_TABLES.
# - institute/management/commands/validate_students_origin_db.py: --dry-run, --student-id, all students, duplicate report.
# - institute/management/commands/validate_students_target_db.py: same options, for target DB.
# - Duplicate checks: duplicate emails in users_user, duplicate (student_id, institute_id) in institute_studentmanagement; import must use exists-check or INSERT IGNORE.

## Pending
# - Import command: copy students + related data from topteen12 to topteen12-old in FK order, using topteen12-old table structure (INFORMATION_SCHEMA columns), and student_exists_in_target / student_management_exists so no duplicate entry is ever created.
# - Optional: record-count comparison report (source vs target per table) in a command or as part of validate_students_target_db.

===================================================
# Check for compatibility issues
python manage.py check_production_db_compatibility

# Show SQL fixes
python manage.py check_production_db_compatibility --fix-suggestions
```

### 2. User-Test Session Diagnostic
**File:** `app_post_matric/management/commands/diagnose_user_test_sessions.py`

**Usage:**
```bash
# Check specific user
python manage.py diagnose_user_test_sessions --email latika2010@gmail.com

# Check for duplicates
python manage.py diagnose_user_test_sessions --check-duplicates
```

+++++
# Basic check (default: app_post_matric)
python manage.py check_db_structure

# Check specific app
python manage.py check_db_structure --app users

# Check all apps
python manage.py check_db_structure --all-apps

# Save report to file
python manage.py check_db_structure --output db_report.txt

# Detailed check (includes default values)
python manage.py check_db_structure --detailed


+++ Migrations++

# If you manually add tables that have Django models: Check migration status:
python manage.py showmigrations app_name
# If migrations exist but table is already created, fake the migration:
# Find the migration number that creates the table
python manage.py showmigrations app_post_matric
# Fake it (tell Django "this is already done")
python manage.py migrate app_post_matric 0001_initial --fake
# Create the migration
python manage.py makemigrations app_name
# Fake it since table already exists
python manage.py migrate app_name --fake

--- Safe schema migrations (idempotent: table/column exists or not) ---
# Location: core/safe_schema_utils.py
# Migration: core/migrations/0021_safe_ensure_schema.py
# Behaviour: Creates tables/columns only if they do not exist. Safe to run on production
# and when some migrations were skipped or DB was partially created.
python manage.py migrate

# Run safe-schema tests (no actual migration, no DB required; uses mocks):
python manage.py test core.test_safe_schema
python manage.py test core.test_safe_schema -v 2


===================================================



kill port:

pkill -f "manage.py runserver.*8002"

** testing script start ***
python scripts/run_test_students_manager.py create --limit 1

python scripts/run_test_students_manager.py remove --dry-run  # Preview
python scripts/run_test_students_manager.py remove            # Remove

python scripts/run_test_students_manager.py create --class10-only --limit 1
python scripts/run_test_students_manager.py create --class12-only --limit 1

python scripts/verify_class10_st
python scripts/verify_class12_st


** testing script end ***


===================================================
--- Class 10 RIASEC Data Update ---
# Class 10 Personality Assessment (Test 1) reports use RIASEC three-letter codes
# (e.g. RIA, CES) from app.models Category / Course / Stream — NOT RIASEC.json at runtime.
# After editing RIASEC.json you MUST run sync_riasec to update the database.
# Run all commands from project root (where manage.py is).

---------- OVERVIEW ----------
# Test affected:  Test 1 (Personality / RIASEC) — Class 9–10 Stream Sorter
# Report URL:     /psychometric/web/test1_report/<user_id>/
# Data file:      RIASEC.json (project root)
# Backup:         RIASEC-backup.json (keep a copy before replacing)
# DB models:      app.Category, app.Course, app.Stream
# Sync command:   app/management/commands/sync_riasec.py
# Migration:      app/migrations/0004_alter_stream_stream_name.py
#                 (Stream.stream_name max_length increased to 50 for keys like
#                  "Fine Arts / Design", "Humanities / Commerce", "HUM (Set 2)")

---------- SOURCE DOCX FILES (for content authoring) ----------
# Original RIASEC content is maintained in six .docx files (one per leading letter):
#   /home/itpc6/Public/django/git-repo/7nov/git/new_template-demo-topteens/RIASEC/
#     Realistic.docx, Investigative.docx, Enterprising.docx,
#     Conventional.docx, Artistic.docx, social.docx
# Each file contains a table with columns:
#   Code | Stream 1 | Stream 2 | Code Breakdown & Alignment Explanation | Career Options
# Total valid codes: 120 (all permutations of R, I, A, S, E, C taken 3 at a time).
# Optional extracted output (if regenerated): RIASEC/output/riasec-new.json

---------- RIASEC.json STRUCTURE (one object per three-letter code) ----------
# [
#   {
#     "category": "CES",
#     "fullname": "CES (Conventional, Enterprising, Social)",
#     "summary": "Conventional + Enterprising + Social: ...",
#     "fields": "Training Operations Director, HR Compliance Lead, ...",
#     "courses": ["Training Operations Director", "HR Compliance Lead", ...],
#     "best_colleges": "",
#     "streams": {
#       "CWM": ["Commerce With Mathematics"],
#       "PCM": ["Physics Chemistry Mathematics"]
#     },
#     "stream_careers": {
#       "CWM": ["Training Operations Director", "HR Compliance Lead", ...],
#       "PCM": ["Engineering Program Manager", "Technical Facility Lead", ...]
#     }
#   },
#   ...
# ]
# JSON field mapping:
#   category        -> Category.category
#   fullname        -> Category.fullname
#   summary         -> Category.summary (shown on report)
#   fields          -> Category.fields (comma-joined all stream careers)
#   best_colleges   -> Category.best_colleges (preserved from RIASEC-backup.json on generate)
#   courses[]       -> Course.course_name rows (report "Suggested Careers" list)
#   streams{}       -> Stream rows (legacy format: stream_name = key, subjects = label list[0])
#   stream_careers{}-> Per-stream job titles; synced into Course rows (Suggested Careers)
#
# Backward compatibility:
#   streams keeps the OLD list format so existing readers/tools are not broken.
#   stream_careers is the NEW key for docx career options per stream.
#   sync_riasec also accepts legacy dict streams {label, careers} if present.

---------- REGENERATE FROM DOCX ----------
python manage.py generate_riasec_json
python manage.py generate_riasec_json --source /path/to/RIASEC --backup RIASEC-backup.json
# Preserves best_colleges from backup for codes that had values (RIA, RIS, RIE, RIC).

---------- COMPLETE COMMANDS STEP BY STEP ----------

Step 1. Back up the current file before replacing:
   cp RIASEC.json RIASEC-backup.json

Step 2. Place the updated JSON at project root:
   RIASEC.json
   # Must contain exactly 120 unique three-letter codes.

Step 3. Apply migration (first time only, or after pulling 0004):
   python manage.py migrate app

Step 4. Validate JSON without writing to DB:
   python manage.py sync_riasec --dry-run

Step 5. Sync JSON into database (required for reports to show new content):
   python manage.py sync_riasec
   # Optional custom path:
   python manage.py sync_riasec --file /path/to/RIASEC.json

Step 6. Verify a Class 10 report (replace 2959 with a user who completed Test 1):
   # Open in browser (must be logged in):
   http://localhost:8002/psychometric/web/test1_report/2959/
   # Or verify in shell — summary should match new JSON, not backup:
   python manage.py shell -c "
   import json
   from app.models import Category
   with open('RIASEC.json') as f:
       data = {e['category']: e for e in json.load(f)}
   match = sum(1 for c in Category.objects.all()
               if c.summary.strip() == data[c.category]['summary'].strip())
   print(f'DB summaries matching RIASEC.json: {match}/120')
   "

Step 7. (Production) Restart app if needed, then spot-check one report per environment.

---------- SYNC COMMAND REFERENCE ----------
python manage.py sync_riasec                         # sync project root RIASEC.json
python manage.py sync_riasec --dry-run               # validate only, no DB writes
python manage.py sync_riasec --file /path/to/file.json

# Expected output after successful sync:
#   Sync complete: 120 categories (0 created, 120 updated), 1440 courses, 240 streams

---------- IMPORTANT NOTES ----------
# 1. Replacing RIASEC.json alone does NOT update live reports — always run sync_riasec.
# 2. sync_riasec replaces all Course and Stream rows per category (delete + recreate).
# 3. Category rows are update_or_create by three-letter code (existing IDs preserved).
# 4. Test 2 (Interest) and Test 3 (Aptitude) use different data sources; this section
#    applies only to Class 10 Test 1 Personality / RIASEC report.
# 5. Compare codes against backup:
#    python -c \"import json; a={e['category'] for e in json.load(open('RIASEC.json'))}; b={e['category'] for e in json.load(open('RIASEC-backup.json'))}; print(len(a), len(b), len(a&b), len(a-b), len(b-a))\"

---------- END CLASS 10 RIASEC DATA UPDATE ----------


=== Career Battle (React game) ===
# Career Battle is integrated with the main site: same header/footer and same login session.
# - /career-battle/  -> Django page with site header and footer; game loads in iframe from /career-battle/app/
# - /career-battle/app/  -> SPA (React) so the game shares the same session cookie for auth.
# Build outputs to static/game/.
# Local: build once, then run Django on port 8002 (or your main port).
cd react-game/react-game
npm install
npm run build
cd ../..
python manage.py runserver 8002
# Open http://localhost:8002/career-battle
# If "localhost refused to connect": (1) Ensure the server is running in a terminal; (2) Try http://127.0.0.1:8002/career-battle/ (include port and trailing path).

# Production: after building, run collectstatic so staticfiles/game/ is deployed.
cd react-game/react-game && npm run build && cd ../..
python manage.py collectstatic --noinput
# Deploy; ensure your server serves /static/ from STATIC_ROOT and /career-battle/ is handled by Django.

--- Production deployment (deploy.sh) ---
# All deployment via deploy.sh (run from project root). Docker Compose files live in docker/ and are run from that folder by deploy.sh.
# App image and tags configurable in .env:
#   DOCKER_IMAGE=developertopteen/demotopteen
#   DOCKER_IMAGE_NGINX=developertopteen/demotopteen-nginx
#   DOCKER_TAG_ENV=topteens_django_env
#   DOCKER_TAG_PROD=topteens_django_prod
# Deploy tags image as :topteens_django_prod; up-code tags as :topteens_django_env. Rollback uses :previous (pull_policy: never).
# Domain (production) and IP (staging) configurable in .env – used by nginx server_name and deploy messages:
#   PRODUCTION_DOMAIN=topteen.in
#   PRODUCTION_SERVER_NAMES=topteen.in www.topteen.in
#   STAGING_IP=43.204.127.118
#   STAGING_SERVER_NAMES=demo.topteen.in 43.204.127.118 localhost
# Let's Encrypt SSL (domain from .env: PRODUCTION_SERVER_NAMES, PRODUCTION_DOMAIN):
#   1. Set PRODUCTION_SERVER_NAMES=yourdomain.com www.yourdomain.com and ensure domain points to this server, port 80 open.
#   2. Start stack so nginx serves /.well-known/acme-challenge/: ./deploy.sh deploy (or up-code).
#   3. Obtain cert: CERTBOT_EMAIL=you@example.com ./scripts/letsencrypt-obtain.sh
#   4. Reload nginx or restart: ./deploy.sh stop && ./deploy.sh deploy
#   Optional in .env: CERTBOT_EMAIL, CERTBOT_WEBROOT (default ./certbot-webroot), CERTBOT_CONF_PATH (default ./certbot-conf), SSL_CERT_PATH (default ./ssl).
# ENV stack (infra):   ./deploy.sh up-env | down-env | rebuild-env | down-env-remove-images
# CODE stack (app):   ./deploy.sh up-code | down-code | rebuild-code | down-code-remove-images
# Push: DOCKER_PUSH_TAG=topteens_django_prod ./deploy.sh deploy   or   DOCKER_PUSH_TAG=topteens_django_env ./deploy.sh up-code
# Logs folder: set LOG_PATH in .env (default ./logs). Contains: django_app.log, django_error.log, gunicorn_access.log, gunicorn_error.log, nginx access/error when using code stack.
# Worker tuning: GUNICORN_WORKERS, GUNICORN_THREADS, CELERY_CONCURRENCY, DB_CONN_MAX_AGE in .env (see docker/.env.example).


--- Entrance Exam (Test Prep) commands ---
# Data lives under core: EntranceTestPrepCategory (levels: After 10 / After 12 / After Graduation), EntranceTestPrepExam, EntranceTestPrepExamSection.
# Workflow: (1) Convert .docx → HTML .txt, (2) Import .txt into DB, (3) Optionally upload category images.

# 1. Convert .docx to HTML (.txt) – preserves folder structure (After 10/..., After 12/..., After Graduation/...)
python manage.py convert_entrance_test_prep_docx
python manage.py convert_entrance_test_prep_docx --source /path/to/docx_folder --output entrance_test_prep_html
python manage.py convert_entrance_test_prep_docx --dry-run

# 2. Import from converted HTML folder – creates/updates categories and exams (no duplicates; re-runs safe)
python manage.py import_entrance_test_prep
python manage.py import_entrance_test_prep --source entrance_test_prep_html
python manage.py import_entrance_test_prep --source entrance_test_prep_html --dry-run
python manage.py import_entrance_test_prep --replace
# Single record: folder + file name
python manage.py import_entrance_test_prep "After 12/Engineering" "JEE Main.txt"
# Single file by path (relative to --source)
python manage.py import_entrance_test_prep --file "After 10/Defence Related/Indian Army Soldier.txt"
# If DB has no content_json column yet (e.g. production pre-migration): updates work; new exam creation will fail until you run: python manage.py migrate core

# 3. Upload category images – match image filename stem to category slug
python manage.py upload_entrance_test_prep_images
python manage.py upload_entrance_test_prep_images --images-dir /path/to/entrance-exam/images --dry-run
python manage.py upload_entrance_test_prep_images --overwrite

# 4. Test and fix exam categories – exams must be under a leaf category (not a level)
python manage.py test_fix_exam_categories
python manage.py test_fix_exam_categories --fix
python manage.py test_fix_exam_categories --fix --dry-run
python manage.py test_fix_exam_categories --fix --source entrance_test_prep_html
python manage.py test_fix_exam_categories --fix --source entrance_test_prep_html --dry-run

# 5. List folder structure (Level / Category / exams) for manual check – .docx or .txt
python manage.py list_entrance_test_prep_folder
python manage.py list_entrance_test_prep_folder --source "/path/to/Entrance test prep 2026"
python manage.py list_entrance_test_prep_folder -o entrance_test_prep_folder_list.txt --quiet

# 6. Hard delete all entrance test prep data (sections, exams, categories) – permanent
python manage.py hard_delete_entrance_test_prep
python manage.py hard_delete_entrance_test_prep --dry-run   # show counts only
# Admin: Categories list has "Hard delete" link per row and action "Hard delete selected categories (permanent)".
#        Exams list has "Hard delete" link per row and action "Hard delete selected exams (permanent)".

--- DOCX to HTML (scripts/convert_docx_to_html.py) ---
# Converts .docx to HTML with proper H1/H2/H3 from Word "Heading 1/2/3" styles (and outline level). Output: .txt files with HTML body.

# Single file: first arg = path to one .docx (output: <output_dir>/<stem>.txt)
python scripts/convert_docx_to_html.py "JEE Main.docx"
python scripts/convert_docx_to_html.py "JEE Main.docx" ./my_output

# Directory: first arg = folder (converts all .docx under it, keeps structure)
python scripts/convert_docx_to_html.py "/path/to/source_folder" career_html_output

# Debug H1/H2/H3 detection (prints to console: outline level, w:pStyle, style.name, and [NOT HEADING] when style looks like heading but did not match)
DEBUG_HEADINGS=1 python scripts/convert_docx_to_html.py "JEE Main.docx"
DEBUG_HEADINGS=1 python scripts/convert_docx_to_html.py "/path/to/source" career_html_output

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

# Populate description_json field for careers (stores parsed JSON structure from description)
# Script name: populate_career_description_json
# Location: careers/management/commands/populate_career_description_json.py
# Preview mode (no changes)
python manage.py populate_career_description_json --dry-run

# Process a specific career
python manage.py populate_career_description_json --career-id 1790

# Process with limit
python manage.py populate_career_description_json --limit 10

# Skip careers that already have JSON
python manage.py populate_career_description_json --skip-existing

# Process all careers
python manage.py populate_career_description_json



python3 manage.py makemigrations
 python3 manage.py migrate
 python3 manage.py showmigrations careers
#dgango.db.utils.OperationalError: (1050, "Table 'careers_career_courses' already exists").py", line 265, in query in executeh_wrapperse_forwards

 python3 manage.py migrate careers 0002 --fake

 python3 manage.py showmigrations counselor
#Duplicate column name 'student_id'
python3 manage.py showmigrations careers
python3 manage.py migrate careers 0002 --fake
python3 manage.py migrate

DB queries:
===========
use topteen12;
CREATE TABLE `app_post_matric_testcompletionpopup` (
  `id` bigint NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `test_type` varchar(20) NOT NULL,
  `answer` varchar(200) NOT NULL,
  `country` varchar(100) DEFAULT NULL,
  `user_id` int NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE `app_post_matric_testcompletionpopup`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `app_post_matric_testcomp_user_id_test_type_1868a281_uniq` (`user_id`,`test_type`);
ALTER TABLE `app_post_matric_testcompletionpopup`
  MODIFY `id` bigint NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=15;



Migrations log:
python3 manage.py makemigrations

Migrations for 'app':
  app/migrations/0001_initial.py
    - Create model Category
    - Create model Question
    - Create model TestCompletion
    - Create model Stream
    - Create model Results
    - Create model Course
    - Create model Answer
Migrations for 'blog':
  blog/migrations/0001_initial.py
    - Create model BlogCategory
    - Create model BlogTag
    - Create model SubscriptionEmail
    - Create model Blog
Migrations for 'communication':
  communication/migrations/0001_initial.py
    - Create model CommunicationLog
    - Create model OTP
Migrations for 'crm':
  crm/migrations/0001_initial.py
    - Create model Lead
Migrations for 'payments':
  payments/migrations/0001_initial.py
    - Create model Payment
Migrations for 'psychometric_tests':
  psychometric_tests/migrations/0001_initial.py
    - Create model CandidateTest
    - Create model PsychometricFAQ
    - Create model PsychometricTestResult
    - Create model PsychometricTestPayment
    - Create model CentralTestCandidate
    - Add field central_test_candidate to candidatetest
    - Add field pyschometric_test_payment to candidatetest
Migrations for 'skilllab':
  skilllab/migrations/0001_initial.py
    - Create model SkillLabCourse
    - Create model SkilllabCoursePayment
    - Create model SkillLabCourseChapter
    - Create model SkillLabCourseActivity
Migrations for 'careers':
  careers/migrations/0001_initial.py
    - Create model Career
    - Create model CareerPathStep
    - Create model CareerTags
    - Create model ProspectiveEmploymentArea
    - Create model ProspectiveRecruiter
    - Create model Skill
    - Create model VideoCategory
    - Create model Videos
    - Create model RIASECCareer
    - Create model Profession
    - Create model CareerShortlist
    - Create model CareerRating
    - Create model CareerPath
    - Create model CareerMedia
    - Create model CareerFAQ
    - Create model CareerCluster
    - Add field career_cluster to career
    - Add field career_paths to career
    - Add field career_tags to career
  careers/migrations/0002_initial.py
    - Add field courses to career
    - Add field prospective_employment_areas to career
    - Add field prospective_recruiters to career
    - Add field skills to career
    - Add field videos to career
Migrations for 'colleges':
  colleges/migrations/0001_initial.py
    - Create model College
    - Create model CollegeCategory
    - Create model Facility
    - Create model RecruitingCompanies
    - Create model Stream
    - Create model CollegeText
    - Create model CollegeShortlist
    - Create model CollegeRecruitingCompanies
    - Create model CollegeMoneyValue
    - Create model CollegeImages
    - Create model CollegeFlatText
    - Create model CollegeFacts
    - Create model CollegeFacility
    - Add field category to college
    - Add field city to college
    - Add field country to college
    - Add field created_by to college
    - Add field shortlist to college
    - Add field state to college
    - Add field stream to college
    - Add field updated_by to college
Migrations for 'courses':
  courses/migrations/0001_initial.py
    - Create model Course
    - Create model Degree
    - Create model Stream
    - Create model CourseText
    - Create model CourseShortlist
    - Create model CourseMoneyValue
    - Create model CourseIntake
    - Create model CourseFacts
    - Create model CourseEnglighRequirements
    - Add field stream to course
Migrations for 'entrance_exams':
  entrance_exams/migrations/0001_initial.py
    - Create model ExamTags
    - Create model EntranceExam
Migrations for 'counselor':
  counselor/migrations/0001_initial.py
    - Create model Chapter
    - Create model Counselor
    - Create model CounselorCertification
    - Create model CounselorCourse
    - Create model Part
    - Create model Question
    - Create model VideoProgress
    - Create model QuizResults
    - Create model QuizAnswers
    - Create model Quiz
    - Add field quiz to question
    - Create model Notes
    - Create model FollowUpStatus
  counselor/migrations/0002_initial.py
    - Add field student to followupstatus
    - Add field user to counselorcertification
    - Add field coun_user to counselor
    - Add field counselor_admin to counselor
    - Add field students to counselor
    - Add field course to chapter
Migrations for 'institute':
  institute/migrations/0001_initial.py
    - Create model ClassAndSection
    - Create model Institute
    - Create model StudentManagement
    - Create model InstituteMarketingGroup
    - Create model InstituteLog
    - Create model InstituteGroup
    - Create model InstituteAccountDeletion
    - Add field institute_group to institute
    - Add field marketing_group to institute
    - Create index institute_i_name_44590d_idx on field(s) name of model institute
    - Create index institute_i_address_513b94_idx on field(s) address of model institute


.

========================================================
Dummy Enquiry Source Testing Script (seed + cleanup)
========================================================
Script:
  scripts/dummy_enquiry_source_test.sh

Purpose:
  Create and remove dummy analytics data for Enquiry Source dashboard validation,
  including page views, sessions, registrations, paid, enrolled, converted, and
  Payment-model fallback paths.

Make executable (one-time):
  chmod +x scripts/dummy_enquiry_source_test.sh

Usage:
  1) Seed dummy data for a source (optionally pick user by email):
     scripts/dummy_enquiry_source_test.sh seed "laply marketing" admin@topteen.careers

  2) Cleanup by exact session id (printed by seed command):
     scripts/dummy_enquiry_source_test.sh cleanup "dummy-enq-20260327-123000-ab12cd"

  3) Cleanup all dummy data created for one source:
     scripts/dummy_enquiry_source_test.sh cleanup-source "laply marketing"

What seed creates:
  - UserActivity row with enquiry_source
  - UserJourney row for same session
  - UserEvent rows:
      registration, payment_pending, payment_failed, payment_success, course_enrolled
  - Payment rows:
      one success + one failed row (for fallback counters)
  - Journey converted=true for Converted column testing

Seed output includes:
  - session_id
  - dummy_tag
  - stats_preview
  - exact cleanup command

Notes:
  - Script uses hard delete in cleanup modes where supported.
  - Dummy rows are tagged (`dummy_test` / `dummy_tag`) and isolated by session/source.
  - Run from project root (same folder as manage.py).

========================================================

### 1. Seed Forum Data

Run the management command to populate initial data:

```bash
python manage.py seed_forum_data
```

This creates:
- Categories (Stream Selection, Career Options, Entrance Exams, etc.)
- AI Features (Psychometric Assessment Link, Stream Selection Guidance, etc.)
- AI Capabilities (Career Cluster Analysis, Job Market Trends, etc.)
- Countries (India, USA, UK, Canada, Australia, etc.)

### 2. Generate Sample Content (Optional)

To populate sample queries and responses:

```bash
python manage.py generate_sample_content
```

.
.....
....
.


========================================================
Enquiry source analytics – manual check on production
========================================================
Dashboard: https://www.topteen.in/user-analytics/admin-analytics/enquiry-sources/
Tracking only runs when the response is HTTP 200. Redirects (e.g. login) do not record a visit.

---------- MANUAL STEPS TO TEST ON PRODUCTION ----------

Step 1. Confirm the ref-landing page is deployed and returns 200
   - Open: https://www.topteen.in/ref-landing/
   - You must see plain "OK" and the URL must stay as above (no redirect to login).
   - If you get a redirect to login, use the test URL in Step 3 only in an incognito window after logging in elsewhere is not an option, or use a public page that you know returns 200 (e.g. /about-us/ if it is public).

Step 2. Get a valid token from the dashboard
   - Log in as staff/superuser and go to: Enquiry Sources.
   - Create a source or pick an existing one. Copy the "Link" (or the token from the link; it is the value of ref=).
   - Example link: https://www.topteen.in/ref-landing/?ref=Ab12Cd34Ef56
   - Token in this example: Ab12Cd34Ef56

Step 3. Verify token (optional but recommended)
   - While logged in, open: https://www.topteen.in/user-analytics/admin-analytics/enquiry-sources/test-ref/?ref=YOUR_TOKEN
   - Replace YOUR_TOKEN with the token from Step 2.
   - Response should be JSON with "found": true and current "page_views" and "sessions" counts.
   - If "found": false, the token is wrong or the source is inactive/soft-deleted.

Step 4. Trigger a visit that will be counted
   - In a new incognito/private browser window (so you get a new session), open exactly:
     https://www.topteen.in/ref-landing/?ref=YOUR_TOKEN
   - The page must load and show "OK" and the URL must still contain ?ref=YOUR_TOKEN (no redirect that drops the query string).
   - Wait for the page to fully load.

Step 5. Check that counts increased
   - In your normal (logged-in) window, refresh the Enquiry Sources list page.
   - The row for that source should show Page views and Sessions increased by 1.
   - If they did not increase, go to "Fix checklist" below.

Step 6. (Optional) Confirm in database
   On the server (with same DB as the app):
   python manage.py shell -c "
   from user_analytics.models import EnquirySource, UserActivity, UserJourney
   es = EnquirySource.objects.filter(token='YOUR_TOKEN').first()
   if es: print('Page views:', UserActivity.objects.filter(enquiry_source=es).count()); print('Sessions:', UserJourney.objects.filter(enquiry_source=es).count())
   "

---------- FIX CHECKLIST (if counts still 0) ----------

1. Query string preserved?
   - Nginx/proxy must NOT strip query parameters. In nginx, do not use rewrite rules that remove $args. The request to the app should include QUERY_STRING with ref=TOKEN.
   - Test: open https://www.topteen.in/ref-landing/?ref=test123 and confirm in server logs or a debug view that request.GET.get('ref') == 'test123'.

2. Response is 200?
   - Tracking runs only when response.status_code == 200. If /ref-landing/ or the page you use redirects (302), the middleware does not record the visit.
   - Use /ref-landing/ which is designed to always return 200. If /ref-landing/ redirects (e.g. to login), make the ref-landing view public (no login_required).

3. Path not skipped?
   - Middleware skips: /admin/, /static/, /media/, /api/, /analytics/api/.
   - Your URL (e.g. /ref-landing/) must not start with any of these.

4. Same database?
   - The app server that serves the request must use the same database as where you view the Enquiry Sources dashboard. If you have multiple app servers, they must all use the same DB and have the latest code (with ref handling and ref-landing).

5. Logging (temporary)
   Use one of the two methods below to confirm the ref token is received and resolved on the server.

   Method A – Enable DEBUG for user_analytics logger (so existing logger.debug() lines appear):
   - The project already has a 'user_analytics' logger in settings; its level is read from env LOG_LEVEL_USER_ANALYTICS (default WARNING).
   - On the app server, set in .env or the process environment: LOG_LEVEL_USER_ANALYTICS=DEBUG
   - Restart the app (e.g. gunicorn/uwsgi or restart the process).
   - Visit https://www.topteen.in/ref-landing/?ref=YOUR_TOKEN (use the exact token from the dashboard).
   - Check logs: tail -f /path/to/logs/django_app.log (or wherever LOG_PATH in .env points). You should see a line like "Enquiry ref=BFxiH5R2 -> source id=5" if the token was resolved, or "no matching active source" if not.
   - When done debugging, remove LOG_LEVEL_USER_ANALYTICS or set it to WARNING and restart.

   Method B – Temporary INFO log (no settings change; works even when root level is WARNING):
   - In user_analytics/middleware.py, in process_request, right after the line "enquiry_source_id = es.id" (inside "if es:"), add:
       logger.info("Enquiry ref=%s -> source id=%s (path=%s)", ref_token[:12], enquiry_source_id, path)
   - Deploy and restart the app. Visit https://www.topteen.in/ref-landing/?ref=YOUR_TOKEN.
   - Check the same log file; you should see the INFO line with ref, source id, and path. Remove this line after debugging.

6. Share link for campaigns
   - For real campaigns, share the link that returns 200 with ref=TOKEN, e.g. https://www.topteen.in/ref-landing/?ref=TOKEN or https://www.topteen.in/about-us/?ref=TOKEN (if about-us is public and returns 200). Do not share a URL that redirects before returning 200.

---------- Tables and SQL for Enquiry Source counts ----------
Page views and Sessions on the Enquiry Sources page come from these tables:

  • user_analytics_enquirysource  – one row per source (name, token, agency, etc.).
  • user_analytics_useractivity   – one row per page view; enquiry_source_id = FK to enquirysource when visit had ?ref=TOKEN.
  • user_analytics_userjourney    – one row per session; enquiry_source_id = FK to enquirysource when visit had ?ref=TOKEN.

SQL to test in DB (replace TOKEN and id 5 with your source’s token/id):

  -- List all enquiry sources and their counts (same logic as the dashboard)
  SELECT
    es.id,
    es.name,
    es.token,
    (SELECT COUNT(*) FROM user_analytics_useractivity a WHERE a.enquiry_source_id = es.id) AS page_views,
    (SELECT COUNT(*) FROM user_analytics_userjourney j WHERE j.enquiry_source_id = es.id) AS sessions
  FROM user_analytics_enquirysource es
  WHERE es.object_status = 'ACTIVE'
  ORDER BY es.id;

  -- For one source by token (e.g. Iapply marketing, token BFxiH5R2l8id)
  SELECT id, name, token FROM user_analytics_enquirysource WHERE token = 'BFxiH5R2l8id' AND object_status = 'ACTIVE';

  -- Page views for that source (use id from above, e.g. 5)
  SELECT id, session_id, page_path, created FROM user_analytics_useractivity WHERE enquiry_source_id = 5 ORDER BY created DESC LIMIT 10;

  -- Sessions for that source
  SELECT id, session_id, page_path, created FROM user_analytics_userjourney WHERE enquiry_source_id = 5 ORDER BY created DESC LIMIT 10;

  -- If both return 0 rows for source id 5, no request with ?ref=BFxiH5R2l8id has yet returned HTTP 200 on the server that writes to this DB.

---------- Search engine indexing (Google, etc.) ----------
Only production is allowed to be indexed. Set in .env:
  ENVIRONMENT=production   # Production site: no noindex meta; Google can index.
  ENVIRONMENT=development  # Staging/local: <meta name="robots" content="noindex, nofollow"> is output; site is not indexed.
Defaults: ALLOW_SEARCH_ENGINE_INDEX = (ENVIRONMENT == 'production'). Used in template20/base.html and topteenfrontend/super_base.html.

---------- User analytics: tracking toggle and admin URL ----------
.env:
  ENABLE_USER_ANALYTICS_TRACKING=True   # Set to False to disable all page/session tracking (debugging or before bulk delete).

Django Admin → user_analytics → User Activity:
  • URL column: full page_url is stored and shown (link). Use to identify local vs production hits.
  • Filter "URL type": "Local (localhost, 127.0.0.1, test)" / "Production / other (topteen.in)" / "No URL stored (old records)".
  • Filter to e.g. Local, select rows, Action → Delete to clean test data. Or set ENABLE_USER_ANALYTICS_TRACKING=False, then clean, then set back to True.
---------- END ENQUIRY SOURCE PRODUCTION CHECK ----------

. 