from django.core.management.base import BaseCommand

from app.aptitude_improvement_plans import (
    seed_class_10_plans_from_class_12,
    upsert_class_12_plans_from_docx,
)


class Command(BaseCommand):
    help = 'Import Class 12 aptitude improvement plans from docx and seed Class 10 placeholders.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--docx',
            default='/home/itpc6/Public/django/git-repo/7nov/git/new_template-demo-topteens/improvement plan- 12.docx',
            help='Path to improvement plan- 12.docx',
        )
        parser.add_argument(
            '--skip-class-10',
            action='store_true',
            help='Only import Class 12 rows; do not seed Class 10.',
        )

    def handle(self, *args, **options):
        docx_path = options['docx']
        result = upsert_class_12_plans_from_docx(docx_path)
        self.stdout.write(self.style.SUCCESS(
            f"Class 12: {result['total']} areas ({result['created']} created, {result['updated']} updated)"
        ))
        if not options['skip_class_10']:
            seed = seed_class_10_plans_from_class_12()
            self.stdout.write(self.style.SUCCESS(
                f"Class 10: {seed['total']} areas ({seed['created']} created, {seed['updated']} updated)"
            ))
