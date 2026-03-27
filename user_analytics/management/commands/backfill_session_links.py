from django.core.management.base import BaseCommand
from django.db import transaction

from core import choices
from user_analytics.models import UserActivity, UserEvent, UserJourney


class Command(BaseCommand):
    help = "Backfill UserJourney/UserEvent rows from UserActivity session data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--session-id",
            dest="session_id",
            default=None,
            help="Backfill only one session_id (optional).",
        )
        parser.add_argument(
            "--create-pageview-events",
            action="store_true",
            help="Create page_view UserEvent rows when a session has no events.",
        )

    def handle(self, *args, **options):
        session_id = options.get("session_id")
        create_pageview_events = options.get("create_pageview_events", False)

        activities = UserActivity.objects.all()
        if session_id:
            activities = activities.filter(session_id=session_id)

        session_ids = (
            activities.exclude(session_id__isnull=True)
            .exclude(session_id="")
            .values_list("session_id", flat=True)
            .distinct()
        )

        processed = 0
        journeys_created = 0
        events_created = 0

        for sid in session_ids:
            session_activities = UserActivity.objects.filter(session_id=sid).order_by("created")
            first_activity = session_activities.first()
            last_activity = session_activities.last()
            if not first_activity or not last_activity:
                continue

            with transaction.atomic():
                journey_defaults = {
                    "user": first_activity.user,
                    "start_time": first_activity.created,
                    "end_time": last_activity.created,
                    "total_pages": session_activities.count(),
                    "total_time": max(
                        0, int((last_activity.created - first_activity.created).total_seconds())
                    ),
                    "entry_page": first_activity.page_path or "",
                    "exit_page": last_activity.page_path or "",
                    "referrer": first_activity.referrer,
                    "utm_source": first_activity.utm_source,
                    "utm_medium": first_activity.utm_medium,
                    "utm_campaign": first_activity.utm_campaign,
                    "device_type": first_activity.device_type,
                    "country": first_activity.country,
                    "traffic_source_category": first_activity.traffic_source_category,
                    "journey_path": list(
                        session_activities.values_list("page_path", flat=True)
                    ),
                    "enquiry_source_id": first_activity.enquiry_source_id,
                }
                journey = UserJourney.objects.complete().filter(session_id=sid).first()
                if journey is None:
                    journey = UserJourney.objects.create(session_id=sid, **journey_defaults)
                    created = True
                else:
                    created = False

                if not created:
                    changed = False
                    if journey.object_status != choices.ObjectStatus.ACTIVE:
                        journey.object_status = choices.ObjectStatus.ACTIVE
                        changed = True
                    if not journey.user and first_activity.user:
                        journey.user = first_activity.user
                        changed = True
                    if not journey.enquiry_source_id and first_activity.enquiry_source_id:
                        journey.enquiry_source_id = first_activity.enquiry_source_id
                        changed = True
                    if changed:
                        journey.save(update_fields=["object_status", "user", "enquiry_source"])
                else:
                    journeys_created += 1

                if create_pageview_events and not UserEvent.objects.complete().filter(session_id=sid).exists():
                    for activity in session_activities:
                        UserEvent.objects.create(
                            user=activity.user,
                            event_type="page_view",
                            event_name=activity.page_path or "Page View",
                            event_value=0,
                            metadata={
                                "source": "activity_backfill",
                                "activity_id": activity.id,
                                "page_url": activity.page_url,
                                "page_title": activity.page_title,
                            },
                            session_id=sid,
                            ip_address=activity.ip_address,
                            user_agent=activity.user_agent,
                        )
                        events_created += 1

            processed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed sessions={processed}, journeys_created={journeys_created}, events_created={events_created}"
            )
        )
