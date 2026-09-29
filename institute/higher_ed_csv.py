"""CSV upload for students above Class 12. School Class 10 and Class 12 uploads stay separate."""

from __future__ import annotations

import csv
import random
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, View

from core import choices
from institute.models import Institute, StudentManagement
from institute.views import (
    _csv_indian_mobile_ok,
    _institute_logo_url_safe,
    _normalize_csv_mobile_digits,
    user_can_bulk_upload_students_for_institute,
)
from users.models import User

HIGHER_ED_PACKAGE_CODES = frozenset({
    'pkg_c12_personality',
    'pkg_c12_motivation',
    'pkg_c12_interest',
    'pkg_c12_aptitude',
})

def normalize_education_level(raw) -> str:
    text = (raw or '').strip().lower().replace(' ', '_').replace('-', '_')
    aliases = {
        'class_12_passout': choices.EducationAudience.CLASS12_PASSOUT,
        'class12passout': choices.EducationAudience.CLASS12_PASSOUT,
        '12_passout': choices.EducationAudience.CLASS12_PASSOUT,
        'passout': choices.EducationAudience.CLASS12_PASSOUT,
        'pg': choices.EducationAudience.POSTGRADUATE,
        'post_graduate': choices.EducationAudience.POSTGRADUATE,
    }
    if text in aliases:
        return aliases[text]
    if text in choices.EducationAudience.HIGHER:
        return text
    return ''


def higher_ed_package_error(institute, package_code: str) -> str:
    code = (package_code or '').strip()
    if code not in HIGHER_ED_PACKAGE_CODES:
        return 'Choose one Class 12 test. Class 10 packages and the full bundle are not used for this upload.'
    if institute.uses_package_psychometric_mode():
        allowed = set(institute.get_enabled_psychometric_package_codes())
        if allowed and code not in allowed:
            return 'This institute is not allowed to assign that package.'
    return ''


def higher_ed_package_choices(institute) -> list:
    from institute.psychometric_packages import get_package_choices_for_institute, institute_package_mode_active

    if not institute_package_mode_active(institute):
        return []
    return [
        row for row in get_package_choices_for_institute(institute)
        if row.get('code') in HIGHER_ED_PACKAGE_CODES
    ]


class HigherEdStudentSampleCsvView(View):
    def get(self, request, *args, **kwargs):
        sample = (
            "name,mobile,email\n"
            "Asha Rao,9876543210,asha@example.com\n"
            "Ravi Menon,9876543211,ravi@example.com\n"
            "Neha Shah,9876543212,neha@example.com\n"
            "Amit Verma,9876543213,amit@example.com\n"
        )
        response = HttpResponse(sample, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="College professional student sample.csv"'
        return response


@method_decorator(login_required(login_url=reverse_lazy('users:login')), name='dispatch')
class InstituteHigherEdCsvStudentCreateView(TemplateView):
    def post(self, request, *args, **kwargs):
        from core.ttv2_institute_credits import institute_bulk_upload_block_reason
        from institute.psychometric_packages import try_assign_package_code
        from institute.task import create_institute_log, create_student_and_send_mail, update_student_data
        from users.models import UserProfile

        referer = request.META.get('HTTP_REFERER') or reverse('institute:institutegroupdashboard')
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        raw_inst = (request.POST.get('institute') or '').strip()
        if not raw_inst.isdigit():
            messages.error(request, 'Please select an institute before uploading.')
            return HttpResponseRedirect(referer)

        institute = get_object_or_404(Institute, id=int(raw_inst))
        if not user_can_bulk_upload_students_for_institute(request, institute):
            messages.error(request, "You don't have permission to upload students for this institute.")
            return HttpResponseRedirect(referer)

        block = institute_bulk_upload_block_reason(institute)
        if block:
            messages.error(request, block)
            return HttpResponseRedirect(referer)

        csv_file = request.FILES.get('stu_file')
        if not csv_file:
            messages.error(request, 'No file uploaded')
            return HttpResponseRedirect(referer)

        file_content = csv_file.read()
        try:
            csvfile = file_content.decode('utf-8').splitlines()
        except UnicodeDecodeError:
            try:
                csvfile = file_content.decode('utf-8-sig').splitlines()
            except Exception:
                csvfile = file_content.decode('latin-1').splitlines()

        reader = csv.reader(csvfile)
        try:
            header = [h.strip().lower() for h in next(reader)]
        except StopIteration:
            messages.error(request, 'CSV file is empty')
            return HttpResponseRedirect(referer)

        required_headers = ['name', 'mobile']
        missing_headers = [h for h in required_headers if h not in header]
        if missing_headers:
            messages.error(
                request,
                'CSV file is missing required columns: '
                + ', '.join(missing_headers)
                + '. Required columns are: name, mobile. Email is optional.',
            )
            return HttpResponseRedirect(referer)

        education_level = normalize_education_level(request.POST.get('education_level'))
        if not education_level:
            messages.error(
                request,
                'Choose an education level: Class 12 passout, graduate, postgraduate, or professional.',
            )
            return HttpResponseRedirect(referer)

        package_code = (request.POST.get('psychometric_package') or '').strip()
        if institute.uses_package_psychometric_mode() or package_code:
            package_error = higher_ed_package_error(institute, package_code)
            if package_error:
                messages.error(request, package_error)
                return HttpResponseRedirect(referer)

        error_list = []
        email_list = []
        row_number = 1
        imported_ok = 0

        for stu in reader:
            row_number += 1
            if not any(stu):
                continue
            email_list.append(stu)
            stu_d = {
                header[i]: s.strip() if s and s.strip() else None
                for i, s in enumerate(stu)
                if i < len(header)
            }
            stu_name = stu_d.get('name')
            stu_mobile_norm = _normalize_csv_mobile_digits(stu_d.get('mobile'))
            stu_email = stu_d.get('email')

            if not stu_email:
                suffix = str(random.randint(1000, 9999))
                if stu_name:
                    stu_email = f"{stu_name.lower().replace(' ', '_')}_{suffix}@yopmail.com"
                else:
                    stu_email = f"student_{suffix}@yopmail.com"

            if not (stu_name and stu_email and stu_mobile_norm):
                missing_fields = []
                if not stu_name:
                    missing_fields.append('name')
                if not stu_mobile_norm:
                    missing_fields.append('mobile')
                messages.error(
                    request,
                    f"Row {row_number}: Missing or invalid fields - " + ', '.join(missing_fields),
                )
                error_list.append(f"Row {row_number}")
                continue

            if User.objects.filter(email=stu_email).exists():
                messages.error(request, f"{stu_email} Already Exist !!")
                error_list.append(stu_email)
                continue
            if not institute.is_valid_credit_count():
                messages.error(request, 'No remaining credits')
                error_list.append(stu_email)
                continue
            if not re.match(evalid, stu_email):
                messages.error(request, f"{stu_email} Invalid Email !!")
                error_list.append(stu_email)
                continue
            if not _csv_indian_mobile_ok(stu_mobile_norm):
                messages.error(
                    request,
                    f"Invalid mobile number (row {row_number}): use 10 digits starting 6–9, or +91 prefix.",
                )
                error_list.append(str(stu_mobile_norm))
                continue

            password = ''.join(str(random.randint(0, 9)) for _ in range(6))
            student = User.create_user(
                name=stu_name,
                mobile=stu_mobile_norm,
                email=stu_email,
                password=password,
            )
            stu_manage = StudentManagement.objects.create(
                institute=institute,
                student=student,
                class_and_section=None,
                education_audience=education_level,
            )
            profile, _created = UserProfile.objects.get_or_create(user=student)
            if not (profile.schoolname or '').strip() or (profile.schoolname or '').strip().lower() == 'none':
                profile.schoolname = (institute.name or '')[:250]
                profile.save(update_fields=['schoolname'])
            if package_code and institute.uses_package_psychometric_mode():
                ok_pkg, pkg_msg = try_assign_package_code(
                    institute, student, package_code, assigned_by=request.user
                )
                if not ok_pkg and pkg_msg:
                    messages.error(request, f'{stu_email}: {pkg_msg}')
            update_student_data.delay(institute.id, institute.name)
            create_student_and_send_mail.delay(
                stu_manage.id,
                stu_email,
                password,
                institute.name,
                _institute_logo_url_safe(institute),
            )
            imported_ok += 1

        create_institute_log.delay(institute.id, error_list, len(email_list))
        if imported_ok:
            messages.success(request, f"Successfully imported {imported_ok} student(s).")
        elif email_list:
            messages.error(request, 'No students were imported. Fix the CSV errors above and try again.')
        return HttpResponseRedirect(referer)
