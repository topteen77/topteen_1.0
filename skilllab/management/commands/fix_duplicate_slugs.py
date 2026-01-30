#!/usr/bin/env python3
"""
Management command to fix duplicate slugs in SkillLabCourse.
"""

from django.core.management.base import BaseCommand
from skilllab.models import SkillLabCourse
from django.utils.text import slugify
from collections import Counter


class Command(BaseCommand):
    help = 'Fix duplicate slugs in SkillLabCourse'

    def handle(self, *args, **options):
        # Find duplicate slugs
        all_slugs = list(SkillLabCourse.objects.values_list('slug', flat=True))
        slug_counts = Counter(all_slugs)
        duplicates = [slug for slug, count in slug_counts.items() if count > 1 and slug]
        
        if not duplicates:
            self.stdout.write(self.style.SUCCESS('No duplicate slugs found.'))
            return
        
        self.stdout.write(f'Found {len(duplicates)} duplicate slug(s)')
        self.stdout.write('=' * 80)
        
        fixed_count = 0
        for dup_slug in duplicates:
            courses = SkillLabCourse.objects.filter(slug=dup_slug).order_by('id')
            self.stdout.write(f'\nDuplicate slug: {dup_slug}')
            self.stdout.write(f'  Found {courses.count()} courses:')
            
            # Keep the first one, fix the rest
            keep_course = courses.first()
            self.stdout.write(f'  Keeping: ID {keep_course.id} - {keep_course.name}')
            
            for course in courses[1:]:
                # Generate new unique slug
                base_slug = slugify(course.name)
                counter = 1
                new_slug = f"{base_slug}-{counter}"
                while SkillLabCourse.objects.filter(slug=new_slug).exclude(id=course.id).exists():
                    counter += 1
                    new_slug = f"{base_slug}-{counter}"
                
                old_slug = course.slug
                course.slug = new_slug
                course.save(update_fields=['slug'])
                fixed_count += 1
                self.stdout.write(f'  Fixed: ID {course.id} - {course.name}')
                self.stdout.write(f'    {old_slug} → {new_slug}')
        
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS(f'Fixed {fixed_count} duplicate slug(s).'))
