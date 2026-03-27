#!/usr/bin/env bash
set -euo pipefail

# Seed / cleanup dummy analytics records for Enquiry Source testing.
# Usage:
#   scripts/dummy_enquiry_source_test.sh seed "<SOURCE_NAME>" [user@email.com]
#   scripts/dummy_enquiry_source_test.sh cleanup "<SESSION_ID>"
#   scripts/dummy_enquiry_source_test.sh cleanup-source "<SOURCE_NAME>"
#
# Example:
#   scripts/dummy_enquiry_source_test.sh seed "laply marketing" admin@topteen.careers
#   scripts/dummy_enquiry_source_test.sh cleanup "dummy-enq-20260327-123000"
#   scripts/dummy_enquiry_source_test.sh cleanup-source "laply marketing"

MODE="${1:-}"
ARG1="${2:-}"
ARG2="${3:-}"

if [[ -z "$MODE" ]]; then
  echo "Usage:"
  echo "  $0 seed \"<SOURCE_NAME>\" [user@email.com]"
  echo "  $0 cleanup \"<SESSION_ID>\""
  echo "  $0 cleanup-source \"<SOURCE_NAME>\""
  exit 1
fi

if [[ "$MODE" != "seed" && "$MODE" != "cleanup" && "$MODE" != "cleanup-source" ]]; then
  echo "Invalid mode: $MODE"
  echo "Use: seed | cleanup | cleanup-source"
  exit 1
fi

if [[ "$MODE" == "seed" && -z "$ARG1" ]]; then
  echo "Missing source name for seed mode."
  exit 1
fi

if [[ "$MODE" == "cleanup" && -z "$ARG1" ]]; then
  echo "Missing session id for cleanup mode."
  exit 1
fi
if [[ "$MODE" == "cleanup-source" && -z "$ARG1" ]]; then
  echo "Missing source name for cleanup-source mode."
  exit 1
fi

export DUMMY_MODE="$MODE"
export DUMMY_ARG1="$ARG1"
export DUMMY_ARG2="$ARG2"

python manage.py shell <<'PY'
import os
from datetime import timedelta
from uuid import uuid4

from django.utils import timezone
from django.db.models import Q
from django.contrib.auth import get_user_model

from core import choices
from user_analytics.models import EnquirySource, UserActivity, UserJourney, UserEvent
from user_analytics.tasks import update_user_journey_sync, track_user_event_sync
from user_analytics.views import _enquiry_source_stats
from payments.models import Payment

mode = (os.environ.get("DUMMY_MODE") or "").strip().lower()
arg1 = (os.environ.get("DUMMY_ARG1") or "").strip()
arg2 = (os.environ.get("DUMMY_ARG2") or "").strip()

def hard_delete_qs(qs):
    deleted = 0
    for obj in qs.iterator():
        try:
            obj.delete(hard_delete=True)
        except TypeError:
            obj.delete()
        deleted += 1
    return deleted

if mode == "cleanup":
    session_id = arg1
    pay_q = Payment._base_manager.filter(
        Q(gateway_receipt__startswith=f"dummy-enq::{session_id}::")
        | Q(gateway_order_id__startswith=f"order_dummy_{session_id}_")
        | Q(gateway_payment_id__startswith=f"pay_dummy_{session_id}_")
    )
    ev_q = UserEvent._base_manager.filter(session_id=session_id)
    ua_q = UserActivity._base_manager.filter(session_id=session_id)
    uj_q = UserJourney._base_manager.filter(session_id=session_id)
    pay_deleted = hard_delete_qs(pay_q)
    ev_deleted = hard_delete_qs(ev_q)
    ua_deleted = hard_delete_qs(ua_q)
    uj_deleted = hard_delete_qs(uj_q)
    print("cleanup_done", {
        "session_id": session_id,
        "payments": pay_deleted,
        "events": ev_deleted,
        "activities": ua_deleted,
        "journeys": uj_deleted,
    })
    raise SystemExit(0)

if mode == "cleanup-source":
    source_name = arg1
    source = EnquirySource._base_manager.filter(name__iexact=source_name).first()
    if not source:
        print("cleanup_source_done", {"source": source_name, "deleted": 0, "note": "source not found"})
        raise SystemExit(0)
    tag_prefix = f"dummy-enq::{source.id}::"
    pay_q = Payment._base_manager.filter(gateway_receipt__startswith=tag_prefix)
    ev_q = UserEvent._base_manager.filter(
        Q(metadata__dummy_tag__startswith=tag_prefix) | Q(metadata__source=source.name)
    ).filter(event_name__icontains="(Dummy)")
    ua_q = UserActivity._base_manager.filter(enquiry_source_id=source.id, page_path="/dummy/enquiry-test")
    uj_q = UserJourney._base_manager.filter(enquiry_source_id=source.id, entry_page="/dummy/enquiry-test")
    pay_deleted = hard_delete_qs(pay_q)
    ev_deleted = hard_delete_qs(ev_q)
    ua_deleted = hard_delete_qs(ua_q)
    uj_deleted = hard_delete_qs(uj_q)
    print("cleanup_source_done", {
        "source": source.name,
        "payments": pay_deleted,
        "events": ev_deleted,
        "activities": ua_deleted,
        "journeys": uj_deleted,
    })
    raise SystemExit(0)

source_name = arg1
User = get_user_model()

source = EnquirySource.objects.filter(
    name__iexact=source_name,
    object_status=choices.ObjectStatus.ACTIVE
).first()
if not source:
    sample = list(EnquirySource.objects.filter(object_status=choices.ObjectStatus.ACTIVE).values_list("name", flat=True)[:10])
    print("error: source_not_found", source_name)
    print("sample_active_sources:", sample)
    raise SystemExit(1)

if arg2:
    user = User.objects.filter(email__iexact=arg2).first()
else:
    user = User.objects.filter(is_active=True).order_by("-id").first()

if not user:
    print("error: no user found for dummy records.")
    raise SystemExit(1)

stamp = timezone.now().strftime("%Y%m%d-%H%M%S")
session_id = f"dummy-enq-{stamp}-{uuid4().hex[:6]}"
dummy_tag = f"dummy-enq::{source.id}::{session_id}"
now = timezone.now()

# 1) Page view activity + source attribution
UserActivity.objects.create(
    user=user,
    session_id=session_id,
    page_path="/dummy/enquiry-test",
    page_url=f"https://www.topteen.in/dummy/enquiry-test?ref={source.token}",
    page_title="Dummy enquiry test",
    referrer="https://www.google.com/",
    utm_source=source.name,
    traffic_source_category="referral",
    enquiry_source=source,
    created=now - timedelta(minutes=5),
)

# 2) Ensure a journey exists for this session/source
update_user_journey_sync(
    session_id=session_id,
    user_id=user.id,
    page_path="/dummy/enquiry-test",
    referrer="https://www.google.com/",
    utm_source=source.name,
    enquiry_source_id=source.id,
)

# 3) Seed event metrics used by enquiry source cards
base_meta = {"source": source.name, "dummy_test": True, "dummy_tag": dummy_tag}
track_user_event_sync(
    event_type="registration",
    event_name="User Registered (Dummy)",
    user_id=user.id,
    session_id=session_id,
    metadata=base_meta,
)
track_user_event_sync(
    event_type="payment_pending",
    event_name="Payment Checkout Started (Dummy)",
    user_id=user.id,
    session_id=session_id,
    metadata={**base_meta, "payment_stage": "checkout_started"},
)
track_user_event_sync(
    event_type="payment_failed",
    event_name="Payment Checkout Error (Dummy)",
    user_id=user.id,
    session_id=session_id,
    metadata={**base_meta, "stage": "error", "detail": "Dummy gateway error"},
)
track_user_event_sync(
    event_type="payment_success",
    event_name="Payment Success - Skilllabcourse (Dummy)",
    user_id=user.id,
    event_value=199,
    session_id=session_id,
    metadata={**base_meta, "obj_type": "Skilllabcourse", "gateway": "razorpay", "gateway_payment_id": f"pay_dummy_{uuid4().hex[:8]}"},
)
track_user_event_sync(
    event_type="course_enrolled",
    event_name="SkillLab Course Enrolled (Dummy)",
    user_id=user.id,
    session_id=session_id,
    metadata=base_meta,
)

# 5) Also create Payment rows so Enquiry Source fallbacks can be tested.
Payment.objects.create(
    user=user,
    amount=199,
    obj_id=1,
    obj_type=choices.PaymentObjectType.SKILLLABCOURSE,
    is_success=choices.YesNoChoices.YES,
    gateway=choices.GatewayChoices.RAZORPAY if hasattr(choices, "GatewayChoices") else 1,
    gateway_receipt=dummy_tag,
    gateway_order_id=f"order_dummy_{session_id}_ok",
    gateway_payment_id=f"pay_dummy_{session_id}_ok",
)
Payment.objects.create(
    user=user,
    amount=99,
    obj_id=1,
    obj_type=choices.PaymentObjectType.SKILLLABCOURSE,
    is_success=choices.YesNoChoices.NO,
    gateway=choices.GatewayChoices.RAZORPAY if hasattr(choices, "GatewayChoices") else 1,
    gateway_receipt=dummy_tag,
    gateway_order_id=f"order_dummy_{session_id}_fail",
    gateway_payment_id="",
)

# 4) Mark converted on this journey for "Converted" column
journey = UserJourney._base_manager.filter(session_id=session_id).first()
if journey:
    journey.converted = True
    journey.user_id = user.id
    if journey.object_status != choices.ObjectStatus.ACTIVE:
        journey.object_status = choices.ObjectStatus.ACTIVE
    journey.save()

stats = _enquiry_source_stats(source)
print("seed_done")
print("session_id:", session_id)
print("source:", source.name, "| user:", user.email)
print("dummy_tag:", dummy_tag)
print("stats_preview:", {
    "page_views": stats.get("page_views"),
    "sessions": stats.get("visit_count"),
    "registrations": stats.get("registrations"),
    "paid": stats.get("payment_success"),
    "course_enrolled": stats.get("course_enrolled"),
    "converted": stats.get("converted_sessions"),
})
print("cleanup_cmd:", f"scripts/dummy_enquiry_source_test.sh cleanup \"{session_id}\"")
print("cleanup_source_cmd:", f"scripts/dummy_enquiry_source_test.sh cleanup-source \"{source.name}\"")
PY
