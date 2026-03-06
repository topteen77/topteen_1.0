"""
Management command to clean up old/unused analytics data from the local database.
Deletes UserActivity, UserJourney, UserEvent, Lead, AnalyticsCache, and GA4Session
records older than a given number of days. Use for local DB maintenance or to free space.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Clean up old analytics data (UserActivity, UserJourney, UserEvent, Lead, AnalyticsCache, GA4Session)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Delete records older than this many days (default: 365)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only show what would be deleted, do not delete',
        )
        parser.add_argument(
            '--models',
            type=str,
            default='',
            help='Comma-separated list of models to clean: user_activity, user_journey, user_event, lead, analytics_cache, ga4_session. Default: all.',
        )
        parser.add_argument(
            '--temp-leads-only',
            action='store_true',
            help='For Lead: only delete temporary leads (email like session_%%@temp.topteen.in)',
        )
        parser.add_argument(
            '--expired-cache-only',
            action='store_true',
            help='For AnalyticsCache: only delete entries where expires_at has passed (ignores --days)',
        )
    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        models_filter = [m.strip().lower() for m in options['models'].split(',') if m.strip()]
        temp_leads_only = options['temp_leads_only']
        expired_cache_only = options['expired_cache_only']

        cutoff = timezone.now() - timedelta(days=days)
        # When 0 records would be deleted, show total/oldest per model so user sees why
        show_totals = True

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN – no data will be deleted'))

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Cleanup analytics data (older than %s days)' % days))
        self.stdout.write(self.style.SUCCESS('Cutoff date: %s' % cutoff))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        def should_clean(model_name):
            if not models_filter:
                return True
            return model_name in models_filter

        def report(name, to_delete, total=None, oldest=None):
            if to_delete:
                self.stdout.write('%s: %s record(s) %s' % (name, to_delete, 'would be deleted' if dry_run else 'deleted'))
            else:
                line = '%s: 0 records to delete' % name
                # Always show total/oldest when 0 so user knows why (e.g. all data is newer than cutoff)
                if total is not None or oldest is not None:
                    extra = []
                    if total is not None:
                        extra.append('total=%s' % total)
                    if oldest is not None:
                        extra.append('oldest=%s' % oldest)
                    line += ' (%s)' % ', '.join(extra)
                self.stdout.write(line)

        total_deleted = 0

        # 1. UserActivity (no FK from others)
        if should_clean('user_activity'):
            from user_analytics.models import UserActivity
            qs = UserActivity.objects.filter(created__lt=cutoff)
            count = qs.count()
            total = UserActivity.objects.count() if show_totals else None
            oldest = UserActivity.objects.order_by('created').values_list('created', flat=True).first() if show_totals else None
            if count:
                if not dry_run:
                    qs.delete()
                report('UserActivity', count)
                total_deleted += count
            else:
                report('UserActivity', 0, total=total, oldest=oldest)

        # 2. UserJourney (FK to UserEvent – we delete journeys first)
        if should_clean('user_journey'):
            from user_analytics.models import UserJourney
            qs = UserJourney.objects.filter(start_time__lt=cutoff)
            count = qs.count()
            total = UserJourney.objects.count() if show_totals else None
            oldest = UserJourney.objects.order_by('start_time').values_list('start_time', flat=True).first() if show_totals else None
            if count:
                if not dry_run:
                    qs.delete()
                report('UserJourney', count)
                total_deleted += count
            else:
                report('UserJourney', 0, total=total, oldest=oldest)

        # 3. UserEvent
        if should_clean('user_event'):
            from user_analytics.models import UserEvent
            qs = UserEvent.objects.filter(created__lt=cutoff)
            count = qs.count()
            total = UserEvent.objects.count() if show_totals else None
            oldest = UserEvent.objects.order_by('created').values_list('created', flat=True).first() if show_totals else None
            if count:
                if not dry_run:
                    qs.delete()
                report('UserEvent', count)
                total_deleted += count
            else:
                report('UserEvent', 0, total=total, oldest=oldest)

        # 4. Lead (optional: only temp leads, or all old by first_visit)
        if should_clean('lead'):
            from user_analytics.models import Lead
            if temp_leads_only:
                qs = Lead.objects.filter(
                    email__startswith='session_',
                    email__endswith='@temp.topteen.in',
                    first_visit__lt=cutoff,
                )
            else:
                qs = Lead.objects.filter(first_visit__lt=cutoff)
            count = qs.count()
            total = Lead.objects.count() if show_totals else None
            oldest = Lead.objects.order_by('first_visit').values_list('first_visit', flat=True).first() if show_totals else None
            if count:
                if not dry_run:
                    qs.delete()
                report('Lead', count)
                total_deleted += count
            else:
                report('Lead', 0, total=total, oldest=oldest)

        # 5. AnalyticsCache (by expires_at or by created/updated)
        if should_clean('analytics_cache'):
            from user_analytics.models import AnalyticsCache
            if expired_cache_only:
                qs = AnalyticsCache.objects.filter(expires_at__lt=timezone.now())
            else:
                qs = AnalyticsCache.objects.filter(expires_at__lt=cutoff)
            count = qs.count()
            total = AnalyticsCache.objects.count() if show_totals else None
            oldest = AnalyticsCache.objects.order_by('expires_at').values_list('expires_at', flat=True).first() if show_totals else None
            if count:
                if not dry_run:
                    qs.delete()
                report('AnalyticsCache', count)
                total_deleted += count
            else:
                report('AnalyticsCache', 0, total=total, oldest=oldest)

        # 6. GA4Session (by date)
        if should_clean('ga4_session'):
            from user_analytics.models import GA4Session
            cutoff_date = cutoff.date()
            qs = GA4Session.objects.filter(date__lt=cutoff_date)
            count = qs.count()
            total = GA4Session.objects.count() if show_totals else None
            oldest = GA4Session.objects.order_by('date').values_list('date', flat=True).first() if show_totals else None
            if count:
                if not dry_run:
                    qs.delete()
                report('GA4Session', count)
                total_deleted += count
            else:
                report('GA4Session', 0, total=total, oldest=oldest)

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Total: %s record(s) %s' % (total_deleted, 'would be deleted' if dry_run else 'deleted')))
        self.stdout.write(self.style.SUCCESS('=' * 60))
