"""
Shared read-only utilities for validating student data in origin (topteen12)
and target (topteen12-old) DBs. Used by management commands validate_students_origin_db
and validate_students_target_db.
"""
import json


def _parse_json(val):
    """Parse JSON from DB (may be str or dict). Return dict or list or None."""
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return None
    return None


# IMPORT RULE: No duplicate student entries. Use existence checks or INSERT IGNORE when importing.
from django.conf import settings
from decouple import config

# user_type value for students (core.choices.UserType.STUDENT)
USER_TYPE_STUDENT = 1

# object_status active (core.choices.ObjectStatus.ACTIVE)
OBJECT_STATUS_ACTIVE = 1

# Tables that store student-related data (for count report and FK order reference)
STUDENT_RELATED_TABLES = [
    'users_user',
    'users_userprofile',
    'institute_institute',
    'institute_classandsection',
    'institute_studentmanagement',
    'users_parentstudentlink',
    'users_parentstudentbookmark',
    'app_testcompletion',
    'app_results',
    'psychometric_tests_psychometrictestpayment',
    'psychometric_tests_centraltestcandidate',
    'psychometric_tests_candidatetest',
    'psychometric_tests_psychometrictestresult',
    'payments_payment',
    'skilllab_skilllabcoursepayment',
    'counselor_counselor_students',
    'counselor_followupstatus',
    'core_counsellingsession',
    'app_post_matric_testsession',
    'app_post_matric_testresult',
    'app_post_matric_sectionsession',
    'app_post_matric_userresponse',
    'invoices_invoice',
]


def get_db_config(prefix):
    """
    Build DB config dict from .env. Use prefix 'DB_SOURCE_' or 'DB_TARGET_'.
    Reads: {prefix}NAME, {prefix}USER, {prefix}PASSWORD, {prefix}HOST, {prefix}PORT
    (e.g. DB_SOURCE_NAME=topteen12, DB_SOURCE_HOST=..., DB_TARGET_NAME=topteen12-old, ...).
    """
    base = settings.DATABASES.get('default', {}).copy()
    base.update({
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config(f'{prefix}NAME', default=base.get('NAME', '')),
        'USER': config(f'{prefix}USER', default=base.get('USER', config('DB_USER', default=''))),
        'PASSWORD': config(f'{prefix}PASSWORD', default=base.get('PASSWORD', config('DB_PASSWORD', default=''))),
        'HOST': config(f'{prefix}HOST', default=base.get('HOST', config('DB_HOST', default='127.0.0.1'))),
        'PORT': config(f'{prefix}PORT', default=base.get('PORT', config('DB_PORT', default='3306'))),
        'OPTIONS': base.get('OPTIONS', {}) or {'charset': 'utf8mb4'},
    })
    return base


def ensure_connection(alias, role='source'):
    """
    Register DB alias in settings if not present. role is 'source' or 'target'.
    Source uses .env: DB_SOURCE_NAME, DB_SOURCE_HOST, DB_SOURCE_USER, DB_SOURCE_PASSWORD, DB_SOURCE_PORT.
    Target uses .env: DB_TARGET_NAME, DB_TARGET_HOST, DB_TARGET_USER, DB_TARGET_PASSWORD, DB_TARGET_PORT.
    """
    if alias not in settings.DATABASES:
        prefix = 'DB_SOURCE_' if role == 'source' else 'DB_TARGET_'
        cfg = get_db_config(prefix)
        if not cfg.get('NAME') and role == 'source':
            raise ValueError(
                f'Source DB not configured. Set DB_SOURCE_NAME (and DB_SOURCE_*) in .env or add "{alias}" to settings.DATABASES.'
            )
        if not cfg.get('NAME') and role == 'target':
            cfg = dict(settings.DATABASES.get('default', {}))
        settings.DATABASES[alias] = cfg


def get_student_user_ids(cursor, student_id=None):
    """
    Return list of user ids that are students (user_type=1). Optionally filter to one id.
    Uses object_status=1 if table has object_status column (BaseModel).
    """
    # users_user may have object_status from BaseModel
    try:
        cursor.execute(
            "SELECT id FROM users_user WHERE user_type = %s AND (object_status = %s OR object_status IS NULL)",
            [USER_TYPE_STUDENT, OBJECT_STATUS_ACTIVE]
        )
        all_ids = [row[0] for row in cursor.fetchall()]
    except Exception:
        cursor.execute("SELECT id FROM users_user WHERE user_type = %s", [USER_TYPE_STUDENT])
        all_ids = [row[0] for row in cursor.fetchall()]

    if student_id is not None:
        student_id = int(student_id)
        if student_id not in all_ids:
            return []  # not a student or not found
        return [student_id]
    return all_ids


def get_table_count(cursor, table):
    """Return row count for table or (None, error_message) on failure."""
    try:
        cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
        return cursor.fetchone()[0]
    except Exception as e:
        return (None, str(e))


def check_duplicate_students(cursor):
    """
    Detect duplicate student entries. Read-only.
    Returns dict:
      - duplicate_emails: list of (email, count) for emails with count > 1 among students
      - duplicate_student_management: list of (student_id, institute_id, count) for (student_id, institute_id) with count > 1
    """
    out = {'duplicate_emails': [], 'duplicate_student_management': []}
    try:
        cursor.execute(
            """
            SELECT email, COUNT(*) AS cnt FROM users_user
            WHERE user_type = %s AND email IS NOT NULL AND email != ''
            GROUP BY email HAVING cnt > 1
            """,
            [USER_TYPE_STUDENT]
        )
        out['duplicate_emails'] = [(row[0], row[1]) for row in cursor.fetchall()]
    except Exception:
        pass
    try:
        cursor.execute(
            """
            SELECT student_id, institute_id, COUNT(*) AS cnt
            FROM institute_studentmanagement
            WHERE (object_status = %s OR object_status IS NULL)
            GROUP BY student_id, institute_id HAVING cnt > 1
            """,
            [OBJECT_STATUS_ACTIVE]
        )
        out['duplicate_student_management'] = [(row[0], row[1], row[2]) for row in cursor.fetchall()]
    except Exception:
        pass
    return out


def student_exists_in_target(cursor, email=None, user_id=None):
    """
    For import: check if a student already exists in target DB to avoid duplicate.
    Returns (True, user_id) if found, (False, None) otherwise.
    """
    if email:
        cursor.execute(
            "SELECT id FROM users_user WHERE user_type = %s AND email = %s LIMIT 1",
            [USER_TYPE_STUDENT, email]
        )
        row = cursor.fetchone()
        if row:
            return (True, row[0])
    if user_id is not None:
        cursor.execute(
            "SELECT id FROM users_user WHERE id = %s AND user_type = %s LIMIT 1",
            [user_id, USER_TYPE_STUDENT]
        )
        if cursor.fetchone():
            return (True, user_id)
    return (False, None)


def student_management_exists(cursor, institute_id, student_id):
    """For import: check if (institute_id, student_id) already exists; avoid duplicate."""
    cursor.execute(
        """
        SELECT id FROM institute_studentmanagement
        WHERE institute_id = %s AND student_id = %s AND (object_status = %s OR object_status IS NULL)
        LIMIT 1
        """,
        [institute_id, student_id, OBJECT_STATUS_ACTIVE]
    )
    return cursor.fetchone() is not None


def get_table_columns(cursor, table):
    """Return list of column names for table in the DB connected by cursor."""
    cursor.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION",
        [table]
    )
    return [row[0] for row in cursor.fetchall()]


def get_columns_for_copy(source_cursor, target_cursor, table, exclude_columns=None):
    """Return list of column names present in both source and target, in source order. Exclude id if needed for insert."""
    exclude_columns = exclude_columns or []
    src_cols = set(get_table_columns(source_cursor, table))
    tgt_cols = set(get_table_columns(target_cursor, table))
    common = (src_cols & tgt_cols) - set(exclude_columns)
    src_ordered = get_table_columns(source_cursor, table)
    return [c for c in src_ordered if c in common]


def resolve_or_insert_student_in_target(source_cursor, target_cursor, source_user_id, dry_run=False):
    """
    Resolve target student by email. Do NOT overwrite: identify by email only.
    - If a student with same email exists in target -> use that id (skip insert).
    - If email does not exist in target -> insert new user row and use new id.
    Returns (target_user_id, status, log_message) where status is 'existing' or 'new'.
    Uses only id, email for lookup so it works when source/target have different columns.
    """
    source_cursor.execute(
        "SELECT id, email FROM users_user WHERE id = %s AND user_type = %s LIMIT 1",
        [source_user_id, USER_TYPE_STUDENT]
    )
    row = source_cursor.fetchone()
    if not row:
        return (None, 'error', f'Source student id={source_user_id} not found or not a student')
    email = row[1]
    if not email or not str(email).strip():
        return (None, 'error', f'Source student id={source_user_id} has no email; cannot identify by email')
    # Check target by email first (never overwrite; identify by email only)
    exists, existing_id = student_exists_in_target(target_cursor, email=email)
    if exists:
        return (existing_id, 'existing', f'Student exists (email={email!r}), using existing id {existing_id}')
    if dry_run:
        return (None, 'would_insert', f'[DRY-RUN] Would insert student as new (email={email!r})')
    # Insert new student: use TARGET columns (except id) so we satisfy NOT NULL / no-default columns
    tgt_cols = get_table_columns(target_cursor, 'users_user')
    cols = [c for c in tgt_cols if c != 'id']
    if not cols:
        return (None, 'error', 'No columns for users_user in target')
    # Defaults for target-only or required columns when source has no value
    DEFAULT_VALUES = {
        'is_demo_account': 0,
        'is_system_demo': 0,
        'object_status': OBJECT_STATUS_ACTIVE,
        'is_active': 1,
        'is_staff': 0,
        'is_superuser': 0,
        'user_type': USER_TYPE_STUDENT,
    }
    placeholders = ', '.join(['%s'] * len(cols))
    col_list = ', '.join(f'`{c}`' for c in cols)
    src_all_cols = get_table_columns(source_cursor, 'users_user')
    src_col_to_idx = {c: i for i, c in enumerate(src_all_cols)}
    source_cursor.execute(
        "SELECT * FROM users_user WHERE id = %s LIMIT 1",
        [source_user_id]
    )
    full_row = source_cursor.fetchone()
    if not full_row:
        return (None, 'error', 'Source user row not found')
    values = []
    for c in cols:
        if c in src_col_to_idx:
            values.append(full_row[src_col_to_idx[c]])
        elif c in DEFAULT_VALUES:
            values.append(DEFAULT_VALUES[c])
        else:
            values.append(None)
    try:
        target_cursor.execute(
            f"INSERT INTO users_user ({col_list}) VALUES ({placeholders})",
            values
        )
        new_id = target_cursor.lastrowid
        return (new_id, 'new', f'Student inserted as new, id={new_id} (email={email!r})')
    except Exception as e:
        return (None, 'error', f'Insert failed: {e}')


def copy_user_table_rows(source_cursor, target_cursor, table, user_column, id_map, dry_run=False):
    """
    Copy rows from source to target for the given table, mapping source user_id to target user_id.
    id_map: {source_user_id: target_user_id}. Uses only columns present in both DBs; excludes id.
    Returns (rows_copied, error_message or None).
    """
    if not id_map:
        return (0, None)
    cols = get_columns_for_copy(source_cursor, target_cursor, table, exclude_columns=['id'])
    if not cols or user_column not in cols:
        return (0, f'No common columns or no {user_column} for {table}')
    src_all = get_table_columns(source_cursor, table)
    src_idx = {c: i for i, c in enumerate(src_all)}
    col_list = ', '.join(f'`{c}`' for c in cols)
    placeholders = ', '.join(['%s'] * len(cols))
    user_col_idx = cols.index(user_column)
    copied = 0
    for src_uid, tgt_uid in id_map.items():
        source_cursor.execute(
            f"SELECT * FROM `{table}` WHERE `{user_column}` = %s",
            [src_uid]
        )
        for row in source_cursor.fetchall():
            vals = []
            for c in cols:
                if c == user_column:
                    vals.append(tgt_uid)
                elif c in src_idx:
                    vals.append(row[src_idx[c]])
                else:
                    vals.append(None)
            if dry_run:
                copied += 1
                continue
            try:
                target_cursor.execute(
                    f"INSERT INTO `{table}` ({col_list}) VALUES ({placeholders})",
                    vals
                )
                copied += 1
            except Exception as e:
                # Duplicate or constraint: skip this row
                pass
    return (copied, None)


def get_student_table_counts(cursor, table, user_ids, user_column='user_id'):
    """
    Return count of rows in table where user_column IN user_ids.
    For counselor_followupstatus we need student_id -> studentmanagement.id; handled in validate_one.
    """
    if not user_ids:
        return 0
    placeholders = ','.join(['%s'] * len(user_ids))
    try:
        cursor.execute(
            f"SELECT COUNT(*) FROM `{table}` WHERE `{user_column}` IN ({placeholders})",
            user_ids
        )
        return cursor.fetchone()[0]
    except Exception:
        return (None,)


def validate_one_student(cursor, user_id):
    """
    Run full validation for one student (user_id). Read-only.
    Returns dict: {
        'user_id': int,
        'email': str,
        'name': str,
        'class': str or None,  # '10', '12', or None
        'is_school_student': bool,
        'institute_id': int or None,
        'class_and_section_id': int or None,
        'issues': list of str,
        'counts': dict table -> count for this student
    }
    """
    out = {
        'user_id': user_id,
        'email': None,
        'name': None,
        'class': None,
        'is_school_student': False,
        'institute_id': None,
        'class_and_section_id': None,
        'issues': [],
        'counts': {},
    }
    try:
        cursor.execute(
            "SELECT id, email, name FROM users_user WHERE id = %s AND user_type = %s",
            [user_id, USER_TYPE_STUDENT]
        )
        row = cursor.fetchone()
        if not row:
            out['issues'].append('User not found or not a student')
            return out
        out['email'] = row[1] or ''
        out['name'] = row[2] or ''

        # Duplicate check: same email used by more than one student row
        if out['email']:
            try:
                cursor.execute(
                    "SELECT COUNT(*) FROM users_user WHERE user_type = %s AND email = %s",
                    [USER_TYPE_STUDENT, out['email']]
                )
                if cursor.fetchone()[0] > 1:
                    out['issues'].append('Duplicate student: email appears for more than one user')
            except Exception:
                pass

        # StudentManagement: school student relation and class
        cursor.execute(
            "SELECT id, institute_id, class_and_section_id FROM institute_studentmanagement "
            "WHERE student_id = %s AND (object_status = %s OR object_status IS NULL) LIMIT 1",
            [user_id, OBJECT_STATUS_ACTIVE]
        )
        sm_row = cursor.fetchone()
        if sm_row:
            out['is_school_student'] = True
            sm_id, out['institute_id'], out['class_and_section_id'] = sm_row
            # Duplicate check: same (student_id, institute_id) more than once
            try:
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM institute_studentmanagement
                    WHERE student_id = %s AND institute_id = %s AND (object_status = %s OR object_status IS NULL)
                    """,
                    [user_id, out['institute_id'], OBJECT_STATUS_ACTIVE]
                )
                if cursor.fetchone()[0] > 1:
                    out['issues'].append('Duplicate StudentManagement: same student + institute has multiple rows')
            except Exception:
                pass
            if out['class_and_section_id']:
                cursor.execute(
                    "SELECT class_and_section FROM institute_classandsection WHERE id = %s",
                    [out['class_and_section_id']]
                )
                cas_row = cursor.fetchone()
                if cas_row and cas_row[0]:
                    import re
                    nums = re.findall(r'\d+', cas_row[0])
                    if nums:
                        n = int(nums[0])
                        out['class'] = '12' if n >= 11 else '10'
            else:
                out['issues'].append('School student has no class_and_section_id')
        else:
            # Not school student; class might come from UserProfile.grade or test data
            out['class'] = None

        # Counts for this student (user_id)
        for table, col in [
            ('users_userprofile', 'user_id'),
            ('app_testcompletion', 'user_id'),
            ('app_results', 'user_id'),
            ('psychometric_tests_psychometrictestpayment', 'user_id'),
            ('payments_payment', 'user_id'),
            ('core_counsellingsession', 'user_id'),
            ('app_post_matric_testsession', 'user_id'),
        ]:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM `{table}` WHERE `{col}` = %s", [user_id])
                out['counts'][table] = cursor.fetchone()[0]
            except Exception:
                out['counts'][table] = None

        # Counselor: via StudentManagement
        if sm_row:
            sm_id = sm_row[0]
            try:
                cursor.execute(
                    "SELECT COUNT(*) FROM counselor_followupstatus WHERE student_id = %s",
                    [sm_id]
                )
                out['counts']['counselor_followupstatus'] = cursor.fetchone()[0]
            except Exception:
                out['counts']['counselor_followupstatus'] = None
            try:
                cursor.execute(
                    "SELECT COUNT(*) FROM counselor_counselor_students WHERE studentmanagement_id = %s",
                    [sm_id]
                )
                out['counts']['counselor_counselor_students'] = cursor.fetchone()[0]
            except Exception:
                out['counts']['counselor_counselor_students'] = None
        else:
            out['counts']['counselor_followupstatus'] = 0
            out['counts']['counselor_counselor_students'] = 0

        # Class vs test data consistency
        if out['class'] == '10':
            if out['counts'].get('app_post_matric_testsession') and out['counts']['app_post_matric_testsession'] > 0:
                out['issues'].append('Class 10 but has post_matric sessions (expected psychometric)')
            if out['counts'].get('app_testcompletion') == 0 and out['counts'].get('app_results') == 0:
                out['issues'].append('Class 10 with no psychometric test completion or results')
        elif out['class'] == '12':
            if out['counts'].get('app_post_matric_testsession') == 0 and not out['counts'].get('app_post_matric_testsession') is None:
                out['issues'].append('Class 12 but no post_matric sessions (expected for non-demo)')

    except Exception as e:
        out['issues'].append(f'Error: {e}')
    return out


def get_student_data_prepared_for_insert(cursor, user_id):
    """
    Fetch from the given DB (typically source/origin) all student data that would be
    prepared for insert into target. Read-only. Used for dry-run display.
    Returns a dict with keys: user, student_management, class_and_section, institute,
    user_profile, related_counts, and optional error.
    """
    out = {
        'user': None,
        'student_management': None,
        'class_and_section': None,
        'institute': None,
        'user_profile': None,
        'related_counts': {},
        'test_data': {},  # app_testcompletion, app_results, app_post_matric_testsession
        'error': None,
    }
    try:
        # users_user: minimal set first (id, email, name, mobile, user_type, is_active, created, modified)
        cursor.execute(
            """SELECT id, email, name, mobile, user_type, is_active, created, modified
               FROM users_user WHERE id = %s AND user_type = %s LIMIT 1""",
            [user_id, USER_TYPE_STUDENT]
        )
        row = cursor.fetchone()
        if not row:
            out['error'] = f'No student found with user_id={user_id}'
            return out
        out['user'] = {
            'id': row[0], 'email': row[1], 'name': row[2], 'mobile': row[3],
            'user_type': row[4], 'is_active': row[5], 'created': str(row[6]) if row[6] else None,
            'modified': str(row[7]) if row[7] else None,
            'object_status': None, 'is_demo_account': False, 'is_system_demo': False,
        }
        try:
            cursor.execute(
                """SELECT object_status, is_demo_account, is_system_demo
                   FROM users_user WHERE id = %s LIMIT 1""",
                [user_id]
            )
            opt = cursor.fetchone()
            if opt:
                out['user']['object_status'] = opt[0]
                out['user']['is_demo_account'] = bool(opt[1]) if opt[1] is not None else False
                out['user']['is_system_demo'] = bool(opt[2]) if opt[2] is not None else False
        except Exception:
            pass

        # institute_studentmanagement
        cursor.execute(
            """SELECT id, institute_id, student_id, class_and_section_id, counselor_id, created, modified, object_status
               FROM institute_studentmanagement
               WHERE student_id = %s AND (object_status = %s OR object_status IS NULL)""",
            [user_id, OBJECT_STATUS_ACTIVE]
        )
        sm_rows = cursor.fetchall()
        if sm_rows:
            r = sm_rows[0]
            out['student_management'] = {
                'id': r[0], 'institute_id': r[1], 'student_id': r[2],
                'class_and_section_id': r[3], 'counselor_id': r[4],
                'created': str(r[5]) if r[5] else None, 'modified': str(r[6]) if r[6] else None,
                'object_status': r[7],
            }
            if r[3]:
                cursor.execute(
                    "SELECT id, class_and_section, stream FROM institute_classandsection WHERE id = %s",
                    [r[3]]
                )
                cas = cursor.fetchone()
                if cas:
                    out['class_and_section'] = {'id': cas[0], 'class_and_section': cas[1], 'stream': cas[2]}
            if r[1]:
                cursor.execute("SELECT id, name FROM institute_institute WHERE id = %s", [r[1]])
                inst = cursor.fetchone()
                if inst:
                    out['institute'] = {'id': inst[0], 'name': inst[1]}

        # users_userprofile
        cursor.execute(
            """SELECT user_id, birthdate, gender, schoolname, grade
               FROM users_userprofile WHERE user_id = %s LIMIT 1""",
            [user_id]
        )
        up = cursor.fetchone()
        if up:
            out['user_profile'] = {
                'user_id': up[0], 'birthdate': str(up[1]) if up[1] else None,
                'gender': up[2], 'schoolname': up[3], 'grade': up[4],
            }

        # Related table counts (rows that would be inserted for this student)
        for table, col in [
            ('users_parentstudentlink', 'student_id'),
            ('app_testcompletion', 'user_id'),
            ('app_results', 'user_id'),
            ('psychometric_tests_psychometrictestpayment', 'user_id'),
            ('payments_payment', 'user_id'),
            ('core_counsellingsession', 'user_id'),
            ('app_post_matric_testsession', 'user_id'),
        ]:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM `{table}` WHERE `{col}` = %s", [user_id])
                out['related_counts'][table] = cursor.fetchone()[0]
            except Exception:
                out['related_counts'][table] = None
        if out.get('student_management'):
            sm_id = out['student_management']['id']
            try:
                cursor.execute("SELECT COUNT(*) FROM counselor_followupstatus WHERE student_id = %s", [sm_id])
                out['related_counts']['counselor_followupstatus'] = cursor.fetchone()[0]
            except Exception:
                out['related_counts']['counselor_followupstatus'] = None
            try:
                cursor.execute("SELECT COUNT(*) FROM counselor_counselor_students WHERE studentmanagement_id = %s", [sm_id])
                out['related_counts']['counselor_counselor_students'] = cursor.fetchone()[0]
            except Exception:
                out['related_counts']['counselor_counselor_students'] = None

        # Test data (prepared for insert): completion, results, post-matric sessions
        out['test_data'] = {}
        try:
            cursor.execute(
                """SELECT id, user_id, test1_complete, test2_complete, test3_complete,
                          numerical_complete, verbal_complete, logical_complete, emotional_complete,
                          machanical_complete, language_complete, spatial_complete, created, modified
                   FROM app_testcompletion WHERE user_id = %s""",
                [user_id]
            )
            rows = cursor.fetchall()
            if rows:
                out['test_data']['app_testcompletion'] = []
                for r in rows:
                    out['test_data']['app_testcompletion'].append({
                        'id': r[0], 'user_id': r[1],
                        'test1_complete': r[2], 'test2_complete': r[3], 'test3_complete': r[4],
                        'numerical_complete': r[5], 'verbal_complete': r[6], 'logical_complete': r[7],
                        'emotional_complete': r[8], 'machanical_complete': r[9],
                        'language_complete': r[10], 'spatial_complete': r[11],
                        'created': str(r[12]) if r[12] else None, 'modified': str(r[13]) if r[13] else None,
                    })
        except Exception:
            try:
                cursor.execute(
                    "SELECT id, user_id, test1_complete, test2_complete, test3_complete FROM app_testcompletion WHERE user_id = %s",
                    [user_id]
                )
                for r in cursor.fetchall():
                    out['test_data'].setdefault('app_testcompletion', []).append({
                        'id': r[0], 'user_id': r[1], 'test1_complete': r[2], 'test2_complete': r[3], 'test3_complete': r[4],
                    })
            except Exception:
                pass

        try:
            cursor.execute(
                """SELECT id, user_id, test_paper, scores, results, selected_answers, modified
                   FROM app_results WHERE user_id = %s ORDER BY modified""",
                [user_id]
            )
            rows = cursor.fetchall()
            if rows:
                out['test_data']['app_results'] = []
                for r in rows:
                    row = {
                        'id': r[0], 'user_id': r[1], 'test_paper': r[2],
                        'scores': r[3], 'results': r[4], 'selected_answers': r[5],
                        'modified': str(r[6]) if r[6] else None,
                    }
                    out['test_data']['app_results'].append(row)
        except Exception:
            try:
                cursor.execute(
                    "SELECT id, user_id, test_paper, modified FROM app_results WHERE user_id = %s ORDER BY modified",
                    [user_id]
                )
                out['test_data']['app_results'] = [
                    {'id': r[0], 'user_id': r[1], 'test_paper': r[2], 'modified': str(r[3]) if r[3] else None, 'scores': None, 'results': None, 'selected_answers': None}
                    for r in cursor.fetchall()
                ]
            except Exception:
                pass

        try:
            cursor.execute(
                """SELECT id, user_id, test_id, attempt_count, is_completed, start_time, end_time
                   FROM app_post_matric_testsession WHERE user_id = %s ORDER BY attempt_count""",
                [user_id]
            )
            rows = cursor.fetchall()
            if rows:
                out['test_data']['app_post_matric_testsession'] = []
                session_ids = []
                for r in rows:
                    out['test_data']['app_post_matric_testsession'].append({
                        'id': r[0], 'user_id': r[1], 'test_id': r[2], 'attempt_count': r[3],
                        'is_completed': r[4], 'start_time': str(r[5]) if r[5] else None, 'end_time': str(r[6]) if r[6] else None,
                    })
                    session_ids.append(r[0])
                # Post-matric answers: TestResult (result_data, score) and UserResponse count per session
                out['test_data']['app_post_matric_testresult'] = []
                out['test_data']['app_post_matric_userresponse_count'] = {}
                for sid in session_ids:
                    try:
                        cursor.execute(
                            "SELECT id, session_id, score, result_data, grade FROM app_post_matric_testresult WHERE session_id = %s",
                            [sid]
                        )
                        tr = cursor.fetchone()
                        if tr:
                            out['test_data']['app_post_matric_testresult'].append({
                                'id': tr[0], 'session_id': tr[1], 'score': tr[2],
                                'result_data': tr[3], 'grade': tr[4] if len(tr) > 4 else None,
                            })
                    except Exception:
                        pass
                    try:
                        cursor.execute("SELECT COUNT(*) FROM app_post_matric_userresponse WHERE session_id = %s", [sid])
                        out['test_data']['app_post_matric_userresponse_count'][sid] = cursor.fetchone()[0]
                    except Exception:
                        out['test_data']['app_post_matric_userresponse_count'][sid] = None
                    try:
                        cursor.execute(
                            "SELECT id, session_id, selected_answer FROM app_post_matric_userresponse WHERE session_id = %s",
                            [sid]
                        )
                        resp_rows = cursor.fetchall()
                        out['test_data'].setdefault('app_post_matric_userresponse', []).extend([
                            {'id': rr[0], 'session_id': rr[1], 'selected_answer': rr[2]} for rr in resp_rows
                        ])
                    except Exception:
                        pass
            else:
                out['test_data']['app_post_matric_testresult'] = []
                out['test_data']['app_post_matric_userresponse_count'] = {}
        except Exception:
            try:
                cursor.execute(
                    "SELECT id, user_id, test_id, attempt_count, is_completed FROM app_post_matric_testsession WHERE user_id = %s",
                    [user_id]
                )
                rows = cursor.fetchall()
                out['test_data']['app_post_matric_testsession'] = [
                    {'id': r[0], 'user_id': r[1], 'test_id': r[2], 'attempt_count': r[3], 'is_completed': r[4]}
                    for r in rows
                ]
                out['test_data']['app_post_matric_testresult'] = []
                out['test_data']['app_post_matric_userresponse_count'] = {}
                for r in rows:
                    sid = r[0]
                    try:
                        cursor.execute("SELECT id, session_id, score, result_data FROM app_post_matric_testresult WHERE session_id = %s", [sid])
                        tr = cursor.fetchone()
                        if tr:
                            out['test_data']['app_post_matric_testresult'].append({'id': tr[0], 'session_id': tr[1], 'score': tr[2], 'result_data': tr[3], 'grade': None})
                    except Exception:
                        pass
                    try:
                        cursor.execute("SELECT COUNT(*) FROM app_post_matric_userresponse WHERE session_id = %s", [sid])
                        out['test_data']['app_post_matric_userresponse_count'][sid] = cursor.fetchone()[0]
                    except Exception:
                        out['test_data']['app_post_matric_userresponse_count'][sid] = None
                    try:
                        cursor.execute(
                            "SELECT id, session_id, selected_answer FROM app_post_matric_userresponse WHERE session_id = %s",
                            [sid]
                        )
                        for rr in cursor.fetchall():
                            out['test_data'].setdefault('app_post_matric_userresponse', []).append(
                                {'id': rr[0], 'session_id': rr[1], 'selected_answer': rr[2]}
                            )
                    except Exception:
                        pass
            except Exception:
                pass

        try:
            cursor.execute(
                "SELECT id, user_id, test_type, is_success, gateway_receipt FROM psychometric_tests_psychometrictestpayment WHERE user_id = %s",
                [user_id]
            )
            rows = cursor.fetchall()
            if rows:
                out['test_data']['psychometric_tests_psychometrictestpayment'] = [
                    {'id': r[0], 'user_id': r[1], 'test_type': r[2], 'is_success': r[3], 'gateway_receipt': r[4]}
                    for r in rows
                ]
        except Exception:
            pass
    except Exception as e:
        out['error'] = str(e)
    return out


def format_student_data_prepared_for_insert(data):
    """Format get_student_data_prepared_for_insert output as readable lines for stdout."""
    lines = []
    if data.get('error'):
        lines.append(f"  Error: {data['error']}")
        return lines
    u = data.get('user')
    if u:
        lines.append("  users_user:")
        lines.append(f"    id={u['id']} email={u['email']!r} name={u['name']!r} mobile={u.get('mobile')!r}")
        lines.append(f"    user_type={u['user_type']} is_active={u['is_active']} object_status={u.get('object_status')}")
        lines.append(f"    created={u.get('created')} modified={u.get('modified')}")
        lines.append(f"    is_demo_account={u.get('is_demo_account')} is_system_demo={u.get('is_system_demo')}")
    sm = data.get('student_management')
    if sm:
        lines.append("  institute_studentmanagement:")
        lines.append(f"    id={sm['id']} institute_id={sm['institute_id']} student_id={sm['student_id']} class_and_section_id={sm['class_and_section_id']} counselor_id={sm.get('counselor_id')}")
        lines.append(f"    created={sm.get('created')} modified={sm.get('modified')} object_status={sm.get('object_status')}")
    if data.get('class_and_section'):
        cas = data['class_and_section']
        lines.append(f"  institute_classandsection: id={cas['id']} class_and_section={cas['class_and_section']!r} stream={cas.get('stream')!r}")
    if data.get('institute'):
        inst = data['institute']
        lines.append(f"  institute_institute: id={inst['id']} name={inst['name']!r}")
    up = data.get('user_profile')
    if up:
        lines.append("  users_userprofile:")
        lines.append(f"    user_id={up['user_id']} birthdate={up.get('birthdate')} gender={up.get('gender')} schoolname={up.get('schoolname')!r} grade={up.get('grade')!r}")

    # Test data (prepared for insert) — includes student answers (scores, results, selected_answers, result_data, UserResponse)
    td = data.get('test_data') or {}
    if td:
        lines.append("  --- Test data (prepared for insert; includes student answers) ---")
        if td.get('app_testcompletion'):
            lines.append("  app_testcompletion:")
            for row in td['app_testcompletion']:
                lines.append(f"    id={row.get('id')} user_id={row.get('user_id')} test1={row.get('test1_complete')} test2={row.get('test2_complete')} test3={row.get('test3_complete')}")
        if td.get('app_results'):
            lines.append("  app_results — student answers (scores, results, selected_answers):")
            for row in td['app_results']:
                lines.append(f"    id={row.get('id')} test_paper={row.get('test_paper')!r} modified={row.get('modified')}")
                s = _parse_json(row.get('scores'))
                if s and isinstance(s, dict):
                    lines.append(f"      scores (student answer scores): {str(s)[:200]}{'...' if len(str(s)) > 200 else ''}")
                elif row.get('scores'):
                    lines.append(f"      scores: (raw) {str(row.get('scores'))[:150]}...")
                res = _parse_json(row.get('results'))
                if res and isinstance(res, dict):
                    lines.append(f"      results (student answer results): {str(res)[:200]}{'...' if len(str(res)) > 200 else ''}")
                sa = _parse_json(row.get('selected_answers'))
                if sa and isinstance(sa, dict):
                    lines.append(f"      selected_answers (student chosen answers): {str(sa)[:300]}{'...' if len(str(sa)) > 300 else ''}")
                elif row.get('selected_answers'):
                    lines.append(f"      selected_answers: (raw) {str(row.get('selected_answers'))[:150]}...")
        if td.get('app_post_matric_testsession'):
            lines.append("  app_post_matric_testsession:")
            for row in td['app_post_matric_testsession']:
                lines.append(f"    id={row.get('id')} user_id={row.get('user_id')} test_id={row.get('test_id')} attempt_count={row.get('attempt_count')} is_completed={row.get('is_completed')}")
        if td.get('app_post_matric_testresult'):
            lines.append("  app_post_matric_testresult — student result_data (answers):")
            for row in td['app_post_matric_testresult']:
                rd = _parse_json(row.get('result_data'))
                if rd and isinstance(rd, dict):
                    lines.append(f"    session_id={row.get('session_id')} score={row.get('score')} grade={row.get('grade')!r}")
                    lines.append(f"      result_data: {str(rd)[:250]}{'...' if len(str(rd)) > 250 else ''}")
                else:
                    lines.append(f"    session_id={row.get('session_id')} score={row.get('score')} result_data={'present' if row.get('result_data') else 'empty'}")
        if td.get('app_post_matric_userresponse'):
            lines.append("  app_post_matric_userresponse — student answers (selected_answer per response):")
            for resp in td['app_post_matric_userresponse'][:30]:  # show first 30
                sa = _parse_json(resp.get('selected_answer'))
                if sa is not None:
                    lines.append(f"    id={resp.get('id')} session_id={resp.get('session_id')} selected_answer: {str(sa)[:120]}{'...' if len(str(sa)) > 120 else ''}")
                else:
                    lines.append(f"    id={resp.get('id')} session_id={resp.get('session_id')} selected_answer: {str(resp.get('selected_answer'))[:80]}...")
            if len(td.get('app_post_matric_userresponse', [])) > 30:
                lines.append(f"    ... and {len(td['app_post_matric_userresponse']) - 30} more response(s)")
        elif td.get('app_post_matric_userresponse_count'):
            lines.append("  app_post_matric_userresponse count (no rows fetched):")
            for sid, cnt in td['app_post_matric_userresponse_count'].items():
                if cnt is not None:
                    lines.append(f"    session_id={sid}: {cnt} response(s)")
        if td.get('psychometric_tests_psychometrictestpayment'):
            lines.append("  psychometric_tests_psychometrictestpayment:")
            for row in td['psychometric_tests_psychometrictestpayment']:
                lines.append(f"    id={row.get('id')} user_id={row.get('user_id')} test_type={row.get('test_type')} is_success={row.get('is_success')} gateway_receipt={row.get('gateway_receipt')!r}")

    rc = data.get('related_counts') or {}
    if rc:
        lines.append("  related row counts (prepared for insert):")
        for t, c in sorted(rc.items()):
            if c is not None and c != 0:
                lines.append(f"    {t}: {c}")
    return lines
