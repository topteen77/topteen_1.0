from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from core import choices
from core.models import Lead as ContactLead
from counselor.models import Counselor
from institute.models import Institute, StudentManagement
from notifications.models import Notification, NotificationCategory
from notifications.services import (
    detect_notification_environment,
    ensure_default_notification_types,
    notification_role_hint_for_user,
)
from payments.models import Payment
from users.models import User


def _student_on_institute(institute):
    if institute is None:
        return None, "Test Student", "student@example.com", None
    sm = (
        StudentManagement.objects.filter(institute_id=institute.id)
        .select_related("student")
        .exclude(student__isnull=True)
        .order_by("-id")
        .first()
    )
    student = getattr(sm, "student", None) if sm else None
    if student is None:
        return None, "Test Student", "student@example.com", None
    name = (student.name or student.email or "Test Student")
    email = student.email or "student@example.com"
    return sm, name, email, student.id


def _safe_reverse(name, args=None, extra="", kwargs=None):
    try:
        if kwargs:
            url = reverse(name, kwargs=kwargs)
        else:
            url = reverse(name, args=args or [])
    except Exception:
        return ""
    return url + extra if extra else url


class Command(BaseCommand):
    help = "Create 2 clickable test notifications for each dashboard role."

    def handle(self, *args, **options):
        ensure_default_notification_types()
        stamp = timezone.now().strftime("%Y%m%d%H%M%S")
        created = []

        inst = Institute.objects.select_related("created_by", "institute_group").order_by("id").first()
        sm = (
            StudentManagement.objects.select_related("student", "institute", "counselor", "counselor__coun_user")
            .exclude(student__isnull=True)
            .order_by("-id")
            .first()
        )
        tieup = Payment.objects.filter(obj_type=choices.PaymentObjectType.INSTITUTE_TIEUP).order_by("-id").first()
        any_pay = tieup or Payment.objects.order_by("-id").first()
        lead = (
            ContactLead.objects.exclude(name="")
            .exclude(mobile__isnull=True)
            .exclude(mobile="")
            .order_by("-id")
            .first()
        )
        if lead is None:
            lead = ContactLead(name="Test Lead Ananya", mobile="9876543210")
            lead.save()
        lead_url = _safe_reverse("notifications:lead_capture_contact", [lead.id])

        inst_slug = getattr(inst, "slug", None) or ""
        inst_name = getattr(inst, "name", None) or "Test Institute"
        student = getattr(sm, "student", None) if sm else None
        student_name = (getattr(student, "name", None) or getattr(student, "email", None) or "Test Student")
        student_email = (getattr(student, "email", None) or "student@example.com")
        student_id = getattr(student, "id", None)
        pay_id = getattr(any_pay, "id", None)
        pay_capture = _safe_reverse("notifications:payment_capture", extra=("?payment_id=%s" % pay_id) if pay_id else "")
        mktg_pay_url = _safe_reverse(
            "institute:marketinggroupdashboard_page",
            ["payments"],
            extra=("?institute=%s&payment_id=%s" % (inst_slug, pay_id or "")),
        )
        group_students = _safe_reverse("institute:institutegroupdashboard_page", ["students"])
        roles = []
        seen = set()

        def _add(role_key, user, rows):
            if not user or user.id in seen:
                return
            seen.add(user.id)
            roles.append((role_key, user, rows))

        lead_name = (lead.name or "Test Lead Ananya").strip()
        lead_phone = (lead.mobile or "9876543210").strip()
        for user in _users_of_type(choices.UserType.MARKETINGGROUPADMIN):
            _add("marketing", user, [
                {
                    "event_type": "marketing.new_lead",
                    "title": "[TEST] New lead: %s" % lead_name,
                    "body": "%s · enquiry form" % lead_phone,
                    "category": NotificationCategory.MARKETING,
                    "payload": {
                        "lead_id": lead.id, "lead_kind": "contact",
                        "name": "[TEST] %s" % lead_name, "phone": lead_phone, "email": "",
                        "source": "enquiry form", "item_url": lead_url,
                    },
                },
                {
                    "event_type": "payment.failed",
                    "title": "[TEST] Payment failed · %s" % inst_name,
                    "body": "₹1.00 INR · Institute tie-up · %s" % inst_name,
                    "category": NotificationCategory.PAYMENT,
                    "payload": {
                        "payment_id": pay_id, "obj_type": choices.PaymentObjectType.INSTITUTE_TIEUP,
                        "institute_slug": inst_slug, "institute_name": inst_name,
                        "item": "Institute tie-up · %s" % inst_name, "amount_display": "₹1.00 INR",
                        "show_retry_payment": False, "item_url": mktg_pay_url or pay_capture,
                    },
                },
            ])

        for user in _users_of_type(choices.UserType.INSTITUTE):
            own = Institute.objects.filter(created_by_id=user.id).order_by("id").only("id", "slug", "name").first()
            if own is None:
                continue
            slug = own.slug or ""
            name = own.name or "Institute"
            _, sname, semail, sid = _student_on_institute(own)
            inst_students = _safe_reverse("institute:institutedashboard_page", [slug, "students"]) if slug else ""
            rows = []
            if sid:
                rows.append(
                    {
                        "event_type": "institute.student_registered",
                        "title": "[TEST] New student registered",
                        "body": "%s registered at %s." % (sname, name),
                        "category": NotificationCategory.INSTITUTE,
                        "payload": {
                            "student_id": sid,
                            "student_name": "[TEST] %s" % sname,
                            "student_email": semail,
                            "institute_id": own.id,
                            "institute_slug": slug,
                            "institute_name": name,
                            "item_url": inst_students,
                        },
                    }
                )
            rows.append(
                {
                    "event_type": "payment.failed",
                    "title": "[TEST] Payment failed",
                    "body": "We could not confirm your payment of ₹1.00 INR for Institute tie-up.",
                    "category": NotificationCategory.PAYMENT,
                    "payload": {
                        "payment_id": pay_id, "obj_type": choices.PaymentObjectType.INSTITUTE_TIEUP,
                        "payer_id": user.id, "institute_slug": slug, "institute_name": name,
                        "item": "Institute tie-up · %s" % name, "amount_display": "₹1.00 INR",
                        "show_retry_payment": True,
                        "retry_payment_path": _safe_reverse("institute:institute_tieup_pay", kwargs={"slug": slug} if slug else None, extra="?retry=1"),
                        "retry_payment_label": "Retry payment",
                        "cancel_payment_path": inst_students.replace("/students", "/payments") if inst_students else "",
                        "item_url": pay_capture,
                    },
                }
            )
            _add("institute", user, rows)

        for user in _users_of_type(choices.UserType.INSTITUTEGROUPADMIN):
            own = (
                Institute.objects.filter(institute_group__institute_group_admin_id=user.id)
                .order_by("id")
                .only("id", "slug", "name")
                .first()
            )
            if own is None:
                continue
            slug = own.slug or ""
            name = own.name or "Institute"
            _, sname, semail, sid = _student_on_institute(own)
            group_students_url = _safe_reverse(
                "institute:institutegroupdashboard_page",
                ["students"],
                extra=("?institute_slug=%s" % slug) if slug else "",
            )
            rows = []
            if sid:
                rows.append(
                    {
                        "event_type": "institute.student_registered",
                        "title": "[TEST] New student registered",
                        "body": "%s registered at %s." % (sname, name),
                        "category": NotificationCategory.INSTITUTE,
                        "payload": {
                            "student_id": sid,
                            "student_name": "[TEST] %s" % sname,
                            "student_email": semail,
                            "institute_id": own.id,
                            "institute_slug": slug,
                            "institute_name": name,
                            "item_url": group_students_url,
                        },
                    }
                )
            rows.append(
                {
                    "event_type": "payment.success",
                    "title": "[TEST] Payment successful",
                    "body": "Your payment of ₹1.00 INR for Institute tie-up was received successfully.",
                    "category": NotificationCategory.PAYMENT,
                    "payload": {
                        "payment_id": pay_id, "obj_type": choices.PaymentObjectType.INSTITUTE_TIEUP,
                        "payer_id": user.id, "institute_slug": slug, "institute_name": name,
                        "item": "Institute tie-up · %s" % name, "amount_display": "₹1.00 INR",
                        "show_retry_payment": False, "item_url": pay_capture,
                    },
                }
            )
            _add("institute_group", user, rows)

        for user in _users_of_type(choices.UserType.COUNSELOR):
            coun = Counselor.objects.filter(coun_user_id=user.id).select_related("counselor_admin").first()
            cid = getattr(coun, "id", None)
            own = getattr(coun, "counselor_admin", None) if coun else None
            _, sname, semail, sid = _student_on_institute(own)
            extra = "?student_name=%s" % semail
            counselor_students = _safe_reverse("counselor:CounselorDashboardSection", [cid, "students"], extra=extra) if cid else ""
            rows = []
            if cid:
                rows.append(
                    {
                        "event_type": "institute.student_assigned",
                        "title": "[TEST] New student assigned",
                        "body": "%s was assigned to you by %s." % (sname, getattr(own, "name", None) or "your institute"),
                        "category": NotificationCategory.INSTITUTE,
                        "payload": {
                            "student_id": sid,
                            "student_name": "[TEST] %s" % sname,
                            "student_email": semail,
                            "institute_id": getattr(own, "id", None),
                            "institute_slug": getattr(own, "slug", None) or "",
                            "institute_name": getattr(own, "name", None) or "",
                            "counselor_id": cid,
                            "item_url": counselor_students,
                        },
                    }
                )
            rows.append(
                {
                    "event_type": "payment.failed",
                    "title": "[TEST] Payment failed",
                    "body": "We could not confirm your payment of ₹1.00 INR for Counsellor Course.",
                    "category": NotificationCategory.PAYMENT,
                    "payload": {
                        "payment_id": pay_id, "obj_type": choices.PaymentObjectType.COUNSELOR,
                        "payer_id": user.id, "item": "Counsellor Course",
                        "amount_display": "₹1.00 INR", "show_retry_payment": True,
                        "retry_payment_path": _safe_reverse("counselor:CounselorCoursepayment"),
                        "retry_payment_label": "Retry payment",
                        "cancel_payment_path": counselor_students,
                        "item_url": pay_capture,
                    },
                }
            )
            _add("counselor", user, rows)

        admin_qs = (
            User.objects.filter(is_active=True)
            .filter(Q(is_superuser=True) | Q(is_staff=True))
            .exclude(user_type__in=(
                choices.UserType.MARKETINGGROUPADMIN,
                choices.UserType.INSTITUTE,
                choices.UserType.INSTITUTEGROUPADMIN,
                choices.UserType.COUNSELOR,
            ))
            .order_by("id")[:20]
        )
        for user in admin_qs:
            _add("admin", user, [
                {
                    "event_type": "accounts.new_registration",
                    "title": "[TEST] Direct student registration",
                    "body": "%s registered directly." % student_name,
                    "category": NotificationCategory.MARKETING,
                    "payload": {
                        "user_id": student_id, "email": student_email, "name": "[TEST] %s" % student_name,
                        "user_type": choices.UserType.STUDENT, "registration_kind": "direct",
                    },
                },
                {
                    "event_type": "payment.status_updated",
                    "title": "[TEST] Payment received",
                    "body": "₹1.00 INR · Institute tie-up · %s" % inst_name,
                    "category": NotificationCategory.PAYMENT,
                    "payload": {
                        "payment_id": pay_id, "obj_type": choices.PaymentObjectType.INSTITUTE_TIEUP,
                        "institute_slug": inst_slug, "institute_name": inst_name, "status": "success",
                        "item": "Institute tie-up · %s" % inst_name, "amount_display": "₹1.00 INR",
                        "show_retry_payment": False, "item_url": pay_capture,
                    },
                },
            ])

        for role_key, user, rows in roles:
            for idx, spec in enumerate(rows, start=1):
                payload = spec["payload"]
                if spec["event_type"].startswith("payment.") and not payload.get("item_url"):
                    payload["item_url"] = pay_capture
                row = Notification.objects.create(
                    recipient=user,
                    role_hint=notification_role_hint_for_user(user),
                    category=spec["category"],
                    environment=detect_notification_environment(),
                    event_type=spec["event_type"],
                    title=spec["title"][:255],
                    body=spec["body"],
                    payload=payload,
                    dedupe_key="test_notif_%s_%s_%s_%s" % (role_key, user.id, idx, stamp),
                    is_read=False,
                )
                cache.delete("notif_latest:%s" % user.id)
                created.append((role_key, user.email or user.id, spec["title"], row.id))

        if not created:
            self.stderr.write("No role users found to seed.")
            return
        counts = {}
        for role_key, email, title, nid in created:
            counts[role_key] = counts.get(role_key, 0) + 1
        self.stdout.write(self.style.SUCCESS("Created %s test notifications:" % len(created)))
        for role_key, total in counts.items():
            self.stdout.write("  %s: %s items (%s users)" % (role_key, total, total // 2))
        self.stdout.write("Refresh /notifications/ while logged in as that role. Empty lists now show 'No new notification'.")
