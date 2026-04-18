"""Shared resume editor JSON for classic builder modals (template20) and API responses."""

from .models import (
    UserResumeActivity,
    UserResumeCertificate,
    UserResumeInternship,
    UserResumeSkill,
    UserResumeVolunteerInvolvement,
)


def resume_editor_payload(resume):
    """JSON-serializable rows for classic resume modals (edit from DB in the browser)."""

    def dstr(d):
        if not d:
            return ""
        return d.isoformat()

    skills = []
    for s in UserResumeSkill.objects.filter(resume=resume).order_by("id"):
        skills.append(
            {
                "id": s.pk,
                "title": s.title or "",
                "description": s.description or "",
                "profficiency": int(s.profficiency),
            }
        )
    certificates = []
    for c in UserResumeCertificate.objects.filter(resume=resume).order_by("id"):
        certificates.append(
            {
                "id": c.pk,
                "title": c.title or "",
                "description": c.description or "",
                "issue_date": dstr(c.issue_date),
            }
        )
    internships = []
    for it in UserResumeInternship.objects.filter(resume=resume).order_by("id"):
        internships.append(
            {
                "id": it.pk,
                "provider": it.provider or "",
                "role": it.role or "",
                "description": it.description or "",
                "start_date": dstr(it.start_date),
                "end_date": dstr(it.end_date),
            }
        )
    activities = []
    for a in UserResumeActivity.objects.filter(resume=resume).order_by("id"):
        activities.append(
            {
                "id": a.pk,
                "title": a.title or "",
                "description": a.description or "",
                "issue_date": dstr(a.issue_date),
            }
        )
    volunteers = []
    for v in UserResumeVolunteerInvolvement.objects.filter(resume=resume).order_by("id"):
        volunteers.append(
            {
                "id": v.pk,
                "title": v.title or "",
                "role": v.role or "",
                "description": v.description or "",
                "start_date": dstr(v.start_date),
                "end_date": dstr(v.end_date),
            }
        )
    return {
        "skills": skills,
        "certificates": certificates,
        "internships": internships,
        "activities": activities,
        "volunteers": volunteers,
    }
