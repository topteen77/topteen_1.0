"""
Management command to clean up old/unused analytics data from the local database.
Deletes UserActivity, UserJourney, UserEvent, Lead, AnalyticsCache, and GA4Session
records older than a given number of days. Use for local DB maintenance or to free space.

Also supports --purge-all (full wipe of selected models) and --domain local|demo|production
(host-bucket delete; see user_analytics.domain_cleanup).
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import os


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
        parser.add_argument(
            '--purge-all',
            action='store_true',
            help='Delete ALL rows in the selected models (ignores --days). Destructive. '
                 'Default models: user_activity, user_journey, user_event. '
                 'Order is fixed: UserJourney first (FK to UserEvent), then UserEvent, then UserActivity.',
        )
        parser.add_argument(
            '--domain',
            type=str,
            default=None,
            help='Delete rows for one host/pattern key (see user_analytics.domain_cleanup). '
                 'Examples: localhost, 127.0.0.1, testserver, demo.topteen.in, www.topteen.in, '
                 'production_topteen, client_ip_loopback, private_192_168. Mutually exclusive with --purge-all.',
        )

    @staticmethod
    def _hard_delete_queryset(qs):
        """
        Permanently delete records for models inheriting BaseModel soft delete.
        """
        for obj in qs.iterator():
            if hasattr(obj, 'delete') and callable(getattr(obj, 'delete')):
                obj.delete(hard_delete=True)
            else:
                obj.delete()

    @staticmethod
    def _destructive_cleanup_enabled():
        """
        Safety lock for production: destructive cleanup must be explicitly enabled.
        Enable via Django setting ANALYTICS_CLEANUP_ALLOW_DESTRUCTIVE=True
        or env var ANALYTICS_CLEANUP_ALLOW_DESTRUCTIVE=1/true/yes/on.
        """
        flag = getattr(settings, 'ANALYTICS_CLEANUP_ALLOW_DESTRUCTIVE', False)
        if flag:
            return True
        env_val = (os.getenv('ANALYTICS_CLEANUP_ALLOW_DESTRUCTIVE') or '').strip().lower()
        return env_val in {'1', 'true', 'yes', 'on'}

    def _handle_purge_all(self, options, models_filter, dry_run):
        """Delete every row for selected models; order respects FKs (journey before event)."""
        if not models_filter:
            models_filter = ['user_journey', 'user_event', 'user_activity']
        purge_order = [
            'user_journey',
            'user_event',
            'user_activity',
            'lead',
            'analytics_cache',
            'ga4_session',
        ]
        allowed = set(purge_order)
        bad = [m for m in models_filter if m not in allowed]
        if bad:
            self.stderr.write(self.style.ERROR('Unknown model(s): %s' % ', '.join(bad)))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN – no data will be deleted'))

        self.stdout.write(self.style.WARNING('=' * 60))
        self.stdout.write(self.style.WARNING('PURGE ALL (destructive)'))
        self.stdout.write(self.style.WARNING('=' * 60))

        total_deleted = 0
        selected = set(models_filter)

        for name in purge_order:
            if name not in selected:
                continue
            if name == 'user_journey':
                from user_analytics.models import UserJourney
                qs = UserJourney.objects.all()
            elif name == 'user_event':
                from user_analytics.models import UserEvent
                qs = UserEvent.objects.all()
            elif name == 'user_activity':
                from user_analytics.models import UserActivity
                qs = UserActivity.objects.all()
            elif name == 'lead':
                from user_analytics.models import Lead
                qs = Lead.objects.all()
            elif name == 'analytics_cache':
                from user_analytics.models import AnalyticsCache
                qs = AnalyticsCache.objects.all()
            elif name == 'ga4_session':
                from user_analytics.models import GA4Session
                qs = GA4Session.objects.all()
            else:
                continue

            count = qs.count()
            if count and not dry_run:
                self._hard_delete_queryset(qs)
            label = {
                'user_journey': 'UserJourney',
                'user_event': 'UserEvent',
                'user_activity': 'UserActivity',
                'lead': 'Lead',
                'analytics_cache': 'AnalyticsCache',
                'ga4_session': 'GA4Session',
            }[name]
            self.stdout.write(
                '%s: %s record(s) %s'
                % (label, count, 'would be deleted' if dry_run else 'deleted')
            )
            total_deleted += count

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(
            self.style.SUCCESS(
                'Total: %s record(s) %s'
                % (total_deleted, 'would be deleted' if dry_run else 'deleted')
            )
        )
        self.stdout.write(self.style.SUCCESS('=' * 60))

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        models_filter = [m.strip().lower() for m in options['models'].split(',') if m.strip()]
        temp_leads_only = options['temp_leads_only']
        expired_cache_only = options['expired_cache_only']
        purge_all = options['purge_all']
        domain = options.get('domain')
        core_models = {'user_activity', 'user_journey', 'user_event'}
        effective_models = set(models_filter) if models_filter else {
            'user_activity', 'user_journey', 'user_event', 'lead', 'analytics_cache', 'ga4_session'
        }
        touches_core_models = bool(effective_models & core_models)
        destructive = (not dry_run) and (purge_all or domain or touches_core_models)

        if destructive and not self._destructive_cleanup_enabled():
            raise CommandError(
                'Destructive analytics cleanup is disabled. '
                'Set ANALYTICS_CLEANUP_ALLOW_DESTRUCTIVE=True in settings or '
                'env ANALYTICS_CLEANUP_ALLOW_DESTRUCTIVE=1 to proceed.'
            )

        if purge_all and domain:
            raise CommandError('Use either --purge-all or --domain, not both.')
        if domain:
            from user_analytics.domain_cleanup import run_domain_cleanup, VALID_DOMAINS
            if domain not in VALID_DOMAINS:
                raise CommandError(
                    'Invalid --domain %r. Valid keys: %s'
                    % (domain, ', '.join(sorted(VALID_DOMAINS)))
                )
            text, _ = run_domain_cleanup(domain, dry_run=dry_run)
            self.stdout.write(text)
            return
        if purge_all:
            return self._handle_purge_all(options, models_filter, dry_run)

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
                    self._hard_delete_queryset(qs)
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
                    self._hard_delete_queryset(qs)
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
                    self._hard_delete_queryset(qs)
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
                    self._hard_delete_queryset(qs)
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
                    self._hard_delete_queryset(qs)
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
                    self._hard_delete_queryset(qs)
                report('GA4Session', count)
                total_deleted += count
            else:
                report('GA4Session', 0, total=total, oldest=oldest)

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Total: %s record(s) %s' % (total_deleted, 'would be deleted' if dry_run else 'deleted')))
        self.stdout.write(self.style.SUCCESS('=' * 60))
