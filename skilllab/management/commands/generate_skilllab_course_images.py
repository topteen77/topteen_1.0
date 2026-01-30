#!/usr/bin/env python3
"""
Management command to generate/assign images for Skill Lab Courses.

This command:
1. Maps each course to relevant keywords
2. Fetches images from Unsplash API (or uses placeholder)
3. Downloads and assigns images to courses
"""

import os
import sys
import json
import requests
from pathlib import Path
from io import BytesIO
from django.core.management.base import BaseCommand
from django.core.files import File
from django.core.files.base import ContentFile
from django.conf import settings
from skilllab.models import SkillLabCourse
from PIL import Image, ImageDraw, ImageFont
import hashlib


class Command(BaseCommand):
    help = 'Generate/assign images for Skill Lab Courses'

    def add_arguments(self, parser):
        parser.add_argument(
            '--use-unsplash',
            action='store_true',
            help='Use Unsplash API to fetch real images (requires UNSPLASH_ACCESS_KEY)',
        )
        parser.add_argument(
            '--use-placeholder',
            action='store_true',
            help='Generate placeholder images with course names',
        )
        parser.add_argument(
            '--course-name',
            type=str,
            help='Process specific course by name',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview without saving images',
        )

    def handle(self, *args, **options):
        use_unsplash = options.get('use_unsplash', False)
        use_placeholder = options.get('use_placeholder', False)
        course_name = options.get('course_name')
        dry_run = options.get('dry_run', False)

        # Default to placeholder if no option specified
        if not use_unsplash and not use_placeholder:
            use_placeholder = True

        # Course to keyword mapping
        course_keywords = self.get_course_keywords()

        # Get courses to process
        if course_name:
            courses = SkillLabCourse.objects.filter(name__icontains=course_name)
        else:
            courses = SkillLabCourse.objects.all()

        total = courses.count()
        self.stdout.write(f'Found {total} course(s) to process')
        self.stdout.write('=' * 80)

        success_count = 0
        error_count = 0

        for course in courses:
            self.stdout.write(f'\nProcessing: {course.name}')
            
            # Skip if already has image (unless forced)
            if course.image and course.image.name and not dry_run:
                self.stdout.write(f'  → Course already has image: {course.image.name}')
                continue

            try:
                keywords = course_keywords.get(course.name, [course.name])
                search_query = ' '.join(keywords[:3])  # Use first 3 keywords

                if use_unsplash:
                    image_data = self.fetch_unsplash_image(search_query)
                else:
                    image_data = self.generate_placeholder_image(course.name, search_query)

                if image_data:
                    if not dry_run:
                        # Save image
                        filename = f"{course.slug or self.slugify(course.name)}.jpg"
                        course.image.save(
                            filename,
                            ContentFile(image_data),
                            save=True
                        )
                        self.stdout.write(self.style.SUCCESS(f'  ✓ Image saved: {filename}'))
                    else:
                        self.stdout.write(f'  [DRY RUN] Would save image for: {course.name}')
                    success_count += 1
                else:
                    self.stdout.write(self.style.WARNING(f'  ⚠ Could not generate image'))
                    error_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Error: {e}'))
                error_count += 1

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('SUMMARY')
        self.stdout.write('=' * 80)
        self.stdout.write(f'Success: {success_count}')
        self.stdout.write(f'Errors: {error_count}')
        self.stdout.write(f'Total: {total}')

    def get_course_keywords(self):
        """Map course names to relevant search keywords for images"""
        return {
            "AI & Future Work Preparedness": ["artificial intelligence", "future technology", "career development"],
            "Adaptability & Resilience Skills in a Changing World": ["adaptability", "resilience", "change management"],
            "Are you career ready": ["career readiness", "job preparation", "professional development"],
            "Canadian Cultural Immersion Program": ["canada", "cultural diversity", "immigration"],
            "Career Readiness course for class 7 and 8": ["career planning", "students", "education"],
            "Coding & App Development for Beginners": ["coding", "programming", "app development"],
            "Creative Writing & Personal Expression for Teens": ["creative writing", "writing", "expression"],
            "Crisis Management & First Aid Basics for Teens": ["first aid", "crisis management", "safety"],
            "Cultural Competency & Global Awareness": ["cultural diversity", "global awareness", "inclusion"],
            "Cyber security & Digital Safety for High School Students": ["cybersecurity", "digital safety", "online security"],
            "Data Literacy & Basic Analytics for High Schoolers": ["data analytics", "statistics", "data science"],
            "Design Thinking & Creative Problem-Solving": ["design thinking", "problem solving", "innovation"],
            "Digital Content Creation & Storytelling Skills": ["content creation", "storytelling", "digital media"],
            "Digital Detox Strategies for Students": ["digital detox", "mindfulness", "wellness"],
            "Digital Literacy & AI Tools for Students": ["digital literacy", "AI tools", "technology"],
            "Emotional Intelligence & Conflict Resolution": ["emotional intelligence", "conflict resolution", "communication"],
            "Entrepreneurship & Side Hustle Basics for Teens": ["entrepreneurship", "business", "startup"],
            "Event Planning & Organizational Skills for High Schoolers": ["event planning", "organization", "management"],
            "Exam Stress & Mindfulness Toolkit": ["exam stress", "mindfulness", "study techniques"],
            "goal setting for highschoolers": ["goal setting", "planning", "achievement"],
            "Health & Wellness Foundations for Teenagers": ["health", "wellness", "fitness"],
            "Interview Skills & Professional Etiquette for High Schoolers": ["interview", "professional", "etiquette"],
            "Leadership Development & Initiative Building for Teens": ["leadership", "initiative", "teamwork"],
            "Media Literacy & Critical Information Consumption for Teens": ["media literacy", "critical thinking", "information"],
            "Negotiation & Persuasion Techniques for High Schoolers": ["negotiation", "persuasion", "communication"],
            "Networking & Professional Relationship Building": ["networking", "professional relationships", "connections"],
            "Personal Branding & Online Reputation Management for Teens": ["personal branding", "reputation", "online presence"],
            "Personal Finance 101 Budgeting & Banking": ["personal finance", "budgeting", "banking"],
            "Project Management Basics": ["project management", "planning", "organization"],
            "Public Policy Awareness & Civic Engagement for High Schoolers": ["public policy", "civic engagement", "government"],
            "Public Speaking and communication Skills": ["public speaking", "communication", "presentation"],
            "Research Skills & Academic Integrity": ["research", "academic", "study skills"],
            "Self-Advocacy & Confidence Building for Teens": ["self advocacy", "confidence", "empowerment"],
            "soft skills for success after highschool": ["soft skills", "professional skills", "communication"],
            "STEM Exploration for High Schoolers": ["STEM", "science", "technology"],
            "Study Techniques & Memory Mastery": ["study techniques", "memory", "learning"],
            "Sustainability Practices & Green Skills for Teens": ["sustainability", "environment", "green skills"],
            "Time-Management & Productivity Hacks": ["time management", "productivity", "efficiency"],
            "career planning": ["career planning", "career development", "professional growth"],
        }

    def fetch_unsplash_image(self, query, width=800, height=600):
        """Fetch image from Unsplash API"""
        access_key = os.environ.get('UNSPLASH_ACCESS_KEY')
        if not access_key:
            self.stdout.write(self.style.WARNING('  ⚠ UNSPLASH_ACCESS_KEY not set. Using placeholder instead.'))
            return None

        try:
            # Search for image
            url = 'https://api.unsplash.com/search/photos'
            headers = {'Authorization': f'Client-ID {access_key}'}
            params = {
                'query': query,
                'per_page': 1,
                'orientation': 'landscape'
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get('results') and len(data['results']) > 0:
                image_url = data['results'][0]['urls']['regular']
                
                # Download image
                img_response = requests.get(image_url, timeout=10)
                img_response.raise_for_status()
                
                # Resize if needed
                img = Image.open(BytesIO(img_response.content))
                img = img.resize((width, height), Image.Resampling.LANCZOS)
                
                # Convert to RGB if needed
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Save to bytes
                output = BytesIO()
                img.save(output, format='JPEG', quality=85)
                output.seek(0)
                
                return output.getvalue()
            else:
                self.stdout.write(self.style.WARNING(f'  ⚠ No images found for: {query}'))
                return None
                
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠ Error fetching from Unsplash: {e}'))
            return None

    def generate_placeholder_image(self, course_name, keywords, width=800, height=600):
        """Generate a placeholder image with course name and gradient background"""
        try:
            # Create image with gradient background
            img = Image.new('RGB', (width, height), color='#4A90E2')
            draw = ImageDraw.Draw(img)
            
            # Create gradient effect
            for i in range(height):
                r = int(74 + (i / height) * 30)  # Blue to lighter blue
                g = int(144 + (i / height) * 40)
                b = int(226 + (i / height) * 20)
                draw.line([(0, i), (width, i)], fill=(r, g, b))
            
            # Try to load a font, fallback to default if not available
            try:
                # Try to use a nice font
                font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
                font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
            except:
                try:
                    font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
                    font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
                except:
                    font_large = ImageFont.load_default()
                    font_small = ImageFont.load_default()
            
            # Calculate text position (centered)
            text_bbox = draw.textbbox((0, 0), course_name, font=font_large)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            
            x = (width - text_width) // 2
            y = (height - text_height) // 2 - 30
            
            # Draw text with shadow effect
            shadow_offset = 2
            draw.text((x + shadow_offset, y + shadow_offset), course_name, 
                     fill=(0, 0, 0, 128), font=font_large)
            draw.text((x, y), course_name, fill='white', font=font_large)
            
            # Draw keywords below
            if keywords and keywords != course_name:
                keyword_text = f"Skills & Development"
                keyword_bbox = draw.textbbox((0, 0), keyword_text, font=font_small)
                keyword_width = keyword_bbox[2] - keyword_bbox[0]
                keyword_x = (width - keyword_width) // 2
                keyword_y = y + text_height + 20
                
                draw.text((keyword_x + shadow_offset, keyword_y + shadow_offset), 
                         keyword_text, fill=(0, 0, 0, 128), font=font_small)
                draw.text((keyword_x, keyword_y), keyword_text, 
                         fill='#E8F4F8', font=font_small)
            
            # Save to bytes
            output = BytesIO()
            img.save(output, format='JPEG', quality=90)
            output.seek(0)
            
            return output.getvalue()
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ Error generating placeholder: {e}'))
            return None

    def slugify(self, text):
        """Simple slugify function"""
        import re
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text[:50]
