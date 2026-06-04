from django.core.management.base import BaseCommand

from app.career_resolve import resolve_career_by_name
from app.models import Class10FutureRelevantCareer, Class10PremiumStreamCareer
from app.stream_sorter_guidance import clear_stream_sorter_guidance_cache


class Command(BaseCommand):
    help = 'Link Class 10 report guidance rows to published Career records by name.'

    def handle(self, *args, **options):
        premium_linked = 0
        future_linked = 0

        for row in Class10PremiumStreamCareer.objects.filter(career__isnull=True).exclude(career_name=''):
            career = resolve_career_by_name(row.career_name)
            if career:
                row.career = career
                row.career_name = career.name
                row.save(update_fields=['career', 'career_name'])
                premium_linked += 1

        for row in Class10FutureRelevantCareer.objects.filter(career__isnull=True).exclude(career_name=''):
            career = resolve_career_by_name(row.career_name)
            if career:
                row.career = career
                row.career_name = career.name
                row.save(update_fields=['career', 'career_name'])
                future_linked += 1

        clear_stream_sorter_guidance_cache()
        self.stdout.write(
            self.style.SUCCESS(
                f'Linked {premium_linked} premium stream careers and '
                f'{future_linked} future-relevant careers.'
            )
        )
