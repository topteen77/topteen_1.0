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

--- AI Counselling (Deep-Counselling Engine) ---
# Separate FastAPI microservice; Django proxies to it for logged-in users.
# URL (Django): /career-counselling/  (login required). API: POST /career-counselling/api/
# Engine: counselling_engine/ (see counselling_engine/README.md).
# Django .env: COUNSELLING_ENGINE_URL (e.g. http://localhost:8000), TOPTEEN_COUNSELLING_API_KEY (same as engine TOPTEEN_API_KEY).
# Run engine: cd counselling_engine && uvicorn main:app --host 0.0.0.0 --port 8000 (requires Redis; use COUNSELLING_REDIS_DB=0 to avoid clash with Django cache).

** testing script start ***
python scripts/run_test_students_manager.py create --limit 1

python scripts/run_test_students_manager.py remove --dry-run  # Preview
python scripts/run_test_students_manager.py remove            # Remove

python scripts/run_test_students_manager.py create --class10-only --limit 1
python scripts/run_test_students_manager.py create --class12-only --limit 1

python scripts/verify_class10_st
python scripts/verify_class12_st


** testing script end ***


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
....