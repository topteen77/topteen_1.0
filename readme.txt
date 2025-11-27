** testing script start ***
python scripts/run_test_students_manager.py create --limit 1

python scripts/run_test_students_manager.py remove --dry-run  # Preview
python scripts/run_test_students_manager.py remove            # Remove

python scripts/run_test_students_manager.py create --class10-only --limit 1
python scripts/run_test_students_manager.py create --class12-only --limit 1

python scripts/verify_class10_st
python scripts/verify_class12_st


** testing script end ***




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
