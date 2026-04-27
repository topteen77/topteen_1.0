from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from users.models import User
from user_analytics.models import UserActivity, UserEvent


class Command(BaseCommand):
    help = "Generate dummy activity/events so dashboard streaks appear."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, required=True, help="User id to generate data for")
        parser.add_argument("--days", type=int, default=7, help="How many consecutive days (ending today) to generate")
        parser.add_argument(
            "--source",
            choices=["activity", "event"],
            default="activity",
            help="Which table to populate: UserActivity or UserEvent",
        )
        parser.add_argument(
            "--event-type",
            default="page_view",
            help="UserEvent.event_type to use when --source=event",
        )
        parser.add_argument(
            "--page-path",
            default="/user/dashboard/",
            help="UserActivity.page_path to use when --source=activity",
        )
        parser.add_argument(
            "--session-id",
            default="dummy-streak-session",
            help="session_id value for created rows",
        )

    def handle(self, *args, **options):
        user_id: int = options["user_id"]
        days: int = options["days"]
        source: str = options["source"]
        event_type: str = options["event_type"]
        page_path: str = options["page_path"]
        session_id: str = options["session_id"]

        if days <= 0 or days > 365:
            raise CommandError("--days must be between 1 and 365")

        user = User.objects.filter(id=user_id).first()
        if not user:
            raise CommandError(f"User not found: {user_id}")

        now = timezone.now()
        created_rows = 0

        # Create one row per day (at 12:00 local time) so `dates('created','day')` sees it.
        for i in range(days):
            day = (now - timedelta(days=i)).date()
            created_dt = timezone.make_aware(
                timezone.datetime.combine(day, timezone.datetime.min.time()).replace(hour=12, minute=0, second=0)
            )

            if source == "activity":
                row = UserActivity.objects.create(
                    user=user,
                    session_id=session_id,
                    page_path=page_path,
                    page_url=f"http://localhost{page_path}",
                    page_title="Dummy activity",
                    time_on_page=10,
                )
                # created is auto_now_add; override for deterministic streak
                UserActivity.objects.filter(id=row.id).update(created=created_dt)
                created_rows += 1
            else:
                row = UserEvent.objects.create(
                    user=user,
                    event_type=event_type,
                    event_name="Dummy streak event",
                    event_value=0,
                    session_id=session_id,
                    metadata={"generated": True, "reason": "dummy streaks"},
                )
                UserEvent.objects.filter(id=row.id).update(created=created_dt)
                created_rows += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_rows} dummy {source} rows for user_id={user_id} (days={days})."
            )
        )
