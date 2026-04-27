"""
Populate UserResume and related rows with realistic dummy content for a student.

Resolves the student by display school ID (e.g. SCH/STU002743) using the same
rules as User.get_display_student_id().

Usage:
  python manage.py seed_student_resume_dummy --display-id SCH/STU002743
"""

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from core import choices
from core.choices import UserResumeProficiency
from core.models import Configuration
from institute.models import StudentManagement
from users.models import (
    User,
    UserProfile,
    UserResume,
    UserResumeActivity,
    UserResumeCertificate,
    UserResumeInternship,
    UserResumeSkill,
    UserResumeVolunteerInvolvement,
)


def resolve_student_by_display_id(display_id: str) -> User | None:
    """
    Match User.get_display_student_id() for school students without scanning the full table.
    Format: {SCHOOL_STUDENT_ID_PREFIX}/{STUDENT_ID_PREFIX}{user.id zero-padded to 6}.
    """
    display_id = (display_id or "").strip()
    if not display_id:
        return None
    school_prefix = (
        Configuration.get("SCHOOL_STUDENT_ID_PREFIX", "SCH", editable=True) or "SCH"
    ).strip() or "SCH"
    stud_prefix = (Configuration.get("STUDENT_ID_PREFIX", "STU", editable=True) or "STU").strip() or "STU"
    head = f"{school_prefix}/"
    if not display_id.startswith(head):
        return None
    rest = display_id[len(head) :]
    if not rest.startswith(stud_prefix):
        return None
    num = rest[len(stud_prefix) :]
    if not num.isdigit():
        return None
    uid = int(num)
    user = User.objects.filter(id=uid, user_type=choices.UserType.STUDENT).first()
    if not user:
        return None
    if not StudentManagement.objects.filter(student=user).exists():
        return None
    try:
        if user.get_display_student_id() != display_id:
            return None
    except Exception:
        return None
    return user


class Command(BaseCommand):
    help = "Fill resume builder tables with dummy data for a student (by SCH/... display id)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--display-id",
            default="SCH/STU002743",
            help='School display student id (default: SCH/STU002743)',
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Remove existing resume skills/certs/internships/activities/volunteer rows first.",
        )

    def handle(self, *args, **options):
        display_id = (options["display_id"] or "").strip()
        replace = options["replace"]

        user = resolve_student_by_display_id(display_id)
        if not user:
            self.stderr.write(
                self.style.ERROR(f"No student found with display id {display_id!r}.")
            )
            return

        with transaction.atomic():
            profile, _ = UserProfile.objects.get_or_create(
                user=user,
                defaults={"gender": choices.GenderChoices.MALE},
            )
            if replace:
                profile.schoolname = "Green Valley International School"
                profile.grade = "Grade 11 — Science"
            else:
                if not (profile.schoolname or "").strip():
                    profile.schoolname = "Green Valley International School"
                if not (profile.grade or "").strip():
                    profile.grade = "Grade 11 — Science"
            if profile.birthdate is None:
                profile.birthdate = date(2008, 6, 15)
            profile.save()

            if replace or not (user.name or "").strip() or (user.name or "").strip() == "Student":
                user.name = "Aarav Mehta"
                user.save(update_fields=["name"])

            resume, _ = UserResume.objects.get_or_create(user=user)

            if replace:
                UserResumeSkill.objects.filter(resume=resume).delete()
                UserResumeCertificate.objects.filter(resume=resume).delete()
                UserResumeInternship.objects.filter(resume=resume).delete()
                UserResumeActivity.objects.filter(resume=resume).delete()
                UserResumeVolunteerInvolvement.objects.filter(resume=resume).delete()

            resume.about = (
                "Motivated high school student with strong foundations in science and mathematics. "
                "Enjoys collaborative projects, public speaking, and applying classroom learning to "
                "real-world problems through clubs and volunteer work. Seeking opportunities to grow "
                "leadership and technical skills before university."
            )
            resume.save(update_fields=["about"])

            skills_data = [
                ("Python (basics)", UserResumeProficiency.INTERMEDIATE, "Variables, functions, simple scripts."),
                ("Public speaking", UserResumeProficiency.EXPERT, "School debates and assembly hosting."),
                ("Microsoft Excel", UserResumeProficiency.INTERMEDIATE, "Charts, tables, and basic formulas."),
                ("Team collaboration", UserResumeProficiency.EXPERT, "Group projects and event committees."),
            ]
            for title, prof, desc in skills_data:
                UserResumeSkill.objects.get_or_create(
                    resume=resume,
                    title=title,
                    defaults={"description": desc, "profficiency": prof},
                )

            certs_data = [
                (
                    "Introduction to Programming — NPTEL (IIT Madras)",
                    "Completed online fundamentals course with graded assignments.",
                    date(2025, 3, 1),
                ),
                (
                    "First Aid & CPR — Indian Red Cross Society",
                    "One-day certified workshop on emergency response.",
                    date(2024, 11, 20),
                ),
            ]
            for title, desc, issue in certs_data:
                UserResumeCertificate.objects.get_or_create(
                    resume=resume,
                    title=title,
                    defaults={"description": desc, "issue_date": issue},
                )

            if not UserResumeInternship.objects.filter(resume=resume).exists():
                UserResumeInternship.objects.create(
                    resume=resume,
                    provider="STEM Labs Pvt. Ltd.",
                    role="Summer intern — Lab assistant",
                    description=(
                        "Supported facilitators during robotics workshops for middle school students; "
                        "prepared kits, documented attendance, and helped troubleshoot simple circuits."
                    ),
                    start_date=date(2025, 5, 10),
                    end_date=date(2025, 6, 28),
                )

            acts_data = [
                (
                    "Science Club — Core member",
                    "Organised intra-school quiz and mentored juniors for Olympiad prep.",
                    date(2024, 8, 1),
                ),
                (
                    "Model United Nations",
                    "Delegate (UNHRC); researched position papers and participated in two-day conference.",
                    date(2025, 1, 15),
                ),
            ]
            for title, desc, issue in acts_data:
                UserResumeActivity.objects.get_or_create(
                    resume=resume,
                    title=title,
                    defaults={"description": desc, "issue_date": issue},
                )

            vol_data = [
                (
                    "Beach clean-up drive",
                    "Volunteer",
                    "Coastal community drive; sorted waste and recorded weights for NGO report.",
                    date(2024, 9, 7),
                    date(2024, 9, 7),
                ),
                (
                    "Neighbourhood tuition support",
                    "Tutor (volunteer)",
                    "Weekly maths help for two Grade 8 students from local government school.",
                    date(2024, 10, 1),
                    date(2025, 2, 28),
                ),
            ]
            for title, role, desc, sd, ed in vol_data:
                UserResumeVolunteerInvolvement.objects.get_or_create(
                    resume=resume,
                    title=title,
                    defaults={"role": role, "description": desc, "start_date": sd, "end_date": ed},
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Resume dummy data ensured for {user.name} (id={user.id}, {display_id}). "
                f"Open /user/resume-builder/ while logged in as this student to review or export PDF."
            )
        )
