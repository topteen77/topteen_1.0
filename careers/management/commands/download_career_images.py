from django.core.management.base import BaseCommand
from careers.models import Career
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import requests
import os
from urllib.parse import urlparse
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Download external career images and store them locally in media/career folder'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without downloading or updating',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-download images even if they already exist locally',
        )
        parser.add_argument(
            '--career-id',
            type=int,
            help='Download image for a specific career ID only',
        )
        parser.add_argument(
            '--url',
            type=str,
            help='External URL to download (use with --career-id)',
        )
        parser.add_argument(
            '--check-missing',
            action='store_true',
            help='Only check and report missing files, do not download',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        career_id = options.get('career_id')
        external_url = options.get('url')
        check_missing = options.get('check_missing', False)

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Career Image Downloader'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')

        # If URL is provided, download it for the specified career
        if external_url and career_id:
            try:
                career = Career.objects.get(id=career_id)
                self._download_image_for_career(career, external_url, dry_run, force)
                return
            except Career.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Career with ID {career_id} not found.'))
                return

        # Get careers to process
        if career_id:
            careers = Career.objects.filter(id=career_id, publish_status=1)
        else:
            careers = Career.objects.filter(publish_status=1).exclude(image__isnull=True).exclude(image='')

        total = careers.count()
        if total == 0:
            self.stdout.write(self.style.WARNING('No careers found to process.'))
            return

        self.stdout.write(f'Found {total} careers to check')
        self.stdout.write('')

        downloaded = 0
        skipped = 0
        errors = 0
        already_local = 0

        for i, career in enumerate(careers, 1):
            try:
                # Check if image field has a value
                if not career.image or not career.image.name:
                    skipped += 1
                    if i % 10 == 0:
                        self.stdout.write(f'Progress: {i}/{total} (✓ {downloaded} downloaded, ⊘ {skipped} skipped, ✗ {errors} errors)')
                    continue

                image_name = career.image.name
                image_url = None

                # Check raw database value - sometimes URLs might be stored directly
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute("SELECT image FROM careers_career WHERE id = %s", [career.id])
                    row = cursor.fetchone()
                    if row and row[0]:
                        raw_image_value = str(row[0])
                        # Check if it's an external URL
                        if raw_image_value.startswith('http://') or raw_image_value.startswith('https://'):
                            image_url = raw_image_value
                            self.stdout.write(f'[{i}/{total}] Career: {career.name} (ID: {career.id})')
                            self.stdout.write(f'  External URL in database: {image_url}')
                
                # If not found in raw DB, check the image field name
                if not image_url:
                    if image_name.startswith('http://') or image_name.startswith('https://'):
                        image_url = image_name
                        self.stdout.write(f'[{i}/{total}] Career: {career.name} (ID: {career.id})')
                        self.stdout.write(f'  External URL: {image_url}')
                    elif 'http://' in image_name or 'https://' in image_name:
                        image_url = image_name
                        self.stdout.write(f'[{i}/{total}] Career: {career.name} (ID: {career.id})')
                        self.stdout.write(f'  URL in path: {image_url}')
                        else:
                            # Check if file exists locally
                            from django.conf import settings
                            file_path = os.path.join(settings.MEDIA_ROOT, image_name)
                            if os.path.exists(file_path):
                                already_local += 1
                                if i % 10 == 0:
                                    self.stdout.write(f'Progress: {i}/{total} (✓ {downloaded} downloaded, ⊘ {skipped} skipped, ✓ {already_local} local, ✗ {errors} errors)')
                                continue
                            else:
                                # File path exists in DB but file is missing
                                # Check if directory exists and has any image files
                                career_media_dir = os.path.join(settings.MEDIA_ROOT, 'upload', 'career', 'media', str(career.id))
                                if os.path.exists(career_media_dir):
                                    # Check if there are any image files in the directory
                                    image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
                                    existing_files = [f for f in os.listdir(career_media_dir) 
                                                     if any(f.lower().endswith(ext) for ext in image_extensions)]
                                    if existing_files:
                                        if check_missing:
                                            self.stdout.write(f'[{i}/{total}] Career: {career.name} (ID: {career.id})')
                                            self.stdout.write(self.style.WARNING(f'  ⚠️  DB path missing: {image_name}'))
                                            self.stdout.write(self.style.SUCCESS(f'  ✓ Found {len(existing_files)} image(s) in directory: {existing_files[0]}'))
                                        already_local += 1
                                        if i % 10 == 0:
                                            self.stdout.write(f'Progress: {i}/{total} (✓ {downloaded} downloaded, ⊘ {skipped} skipped, ✓ {already_local} local, ✗ {errors} errors)')
                                        continue
                                
                                # No files found
                                if check_missing:
                                    self.stdout.write(f'[{i}/{total}] Career: {career.name} (ID: {career.id})')
                                    self.stdout.write(self.style.WARNING(f'  ⚠️  File missing: {image_name}'))
                                skipped += 1
                                if i % 10 == 0:
                                    self.stdout.write(f'Progress: {i}/{total} (✓ {downloaded} downloaded, ⊘ {skipped} skipped, ✓ {already_local} local, ✗ {errors} errors)')
                                continue

                if not image_url:
                    continue

                # Download the image
                self._download_image_for_career(career, image_url, dry_run, force, i, total)
                downloaded += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error processing career {career.id}: {str(e)}'))
                errors += 1
                logger.exception(f"Error processing career {career.id}")

        # Final summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Summary'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'Total careers checked: {total}')
        self.stdout.write(self.style.SUCCESS(f'✓ Downloaded: {downloaded}'))
        self.stdout.write(f'⊘ Skipped: {skipped}')
        self.stdout.write(f'✓ Already local: {already_local}')
        if errors > 0:
            self.stdout.write(self.style.ERROR(f'✗ Errors: {errors}'))
        
        if dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('DRY RUN - No changes were made'))
            self.stdout.write('Run without --dry-run to download and update images')

    def _download_image_for_career(self, career, image_url, dry_run, force, index=None, total=None):
        """Download an image for a specific career"""
        try:
            if index and total:
                self.stdout.write(f'[{index}/{total}] Career: {career.name} (ID: {career.id})')
            else:
                self.stdout.write(f'Career: {career.name} (ID: {career.id})')
            
            if dry_run:
                self.stdout.write(self.style.WARNING(f'  [DRY RUN] Would download: {image_url}'))
                return

            self.stdout.write(f'  Downloading from: {image_url}')
            
            response = requests.get(image_url, timeout=30, stream=True)
            response.raise_for_status()

            # Get content type
            content_type = response.headers.get('content-type', '')
            if 'image' not in content_type:
                self.stdout.write(self.style.WARNING(f'  ⚠️  Not an image (content-type: {content_type}), skipping'))
                return

            # Get file extension from URL or content-type
            parsed_url = urlparse(image_url)
            url_path = parsed_url.path
            ext = os.path.splitext(url_path)[1] or '.jpg'
            
            # Clean extension (remove query params if any)
            ext = ext.split('?')[0].split('#')[0]
            if not ext or ext == '.':
                # Try to get from content-type
                if 'jpeg' in content_type or 'jpg' in content_type:
                    ext = '.jpg'
                elif 'png' in content_type:
                    ext = '.png'
                elif 'webp' in content_type:
                    ext = '.webp'
                elif 'gif' in content_type:
                    ext = '.gif'
                else:
                    ext = '.jpg'  # Default

            # Generate filename - use career slug or ID
            from careers.utils import career_media_directory
            filename = f"{career.slug or f'career-{career.id}'}{ext}"
            # Use the career_media_directory function which returns: upload/career/media/{career.id}/{filename}
            file_path = career_media_directory(career, filename)
            
            # Ensure the directory exists
            from django.conf import settings
            full_dir_path = os.path.join(settings.MEDIA_ROOT, 'upload', 'career', 'media', str(career.id))
            os.makedirs(full_dir_path, exist_ok=True)

            # Check if file already exists (unless force)
            if not force:
                from django.conf import settings
                full_path = os.path.join(settings.MEDIA_ROOT, file_path)
                if os.path.exists(full_path):
                    self.stdout.write(self.style.WARNING(f'  ⊘ File already exists: {file_path}'))
                    return

            # Save the image
            image_content = response.content
            career.image.save(filename, ContentFile(image_content), save=True)

            self.stdout.write(self.style.SUCCESS(f'  ✓ Downloaded and saved: {file_path}'))
            
        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f'  ✗ Download failed: {str(e)}'))
            raise
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ Error: {str(e)}'))
            raise

