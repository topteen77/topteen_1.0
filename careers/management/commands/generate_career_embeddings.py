from django.core.management.base import BaseCommand
from careers.models import Career, CareerEmbedding
from careers.ai_query_processor import QueryProcessor
import logging
from django.db import transaction

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Pre-generate embeddings for all careers and store in database (one-time setup)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force regenerate all embeddings even if they exist',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of careers to process before showing progress (default: 10)',
        )
    
    def handle(self, *args, **options):
        force = options['force']
        batch_size = options['batch_size']
        
        processor = QueryProcessor()
        
        if not processor.ai_client:
            self.stdout.write(
                self.style.ERROR('❌ AI client not initialized. Check API keys in env.local')
            )
            self.stdout.write(f'Provider: {processor.ai_provider}')
            self.stdout.write('')
            self.stdout.write('Required environment variables:')
            self.stdout.write('  - ENABLE_SEMANTIC_SEARCH=True')
            self.stdout.write('  - AI_PROVIDER=openai (or gemini)')
            self.stdout.write('  - OPENAI_API_KEY=your_key (or GOOGLE_API_KEY for Gemini)')
            return
        
        careers = Career.objects.filter(publish_status=1)
        total = careers.count()
        
        if total == 0:
            self.stdout.write(self.style.WARNING('No published careers found.'))
            return
        
        # Check existing embeddings
        existing_count = CareerEmbedding.objects.count()
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Career Embedding Generation'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'Total careers to process: {total}')
        self.stdout.write(f'Existing embeddings: {existing_count}')
        self.stdout.write(f'Provider: {processor.ai_provider}')
        self.stdout.write(f'Model: {processor.embedding_model}')
        self.stdout.write(f'Force regenerate: {force}')
        self.stdout.write(f'Batch size: {batch_size}')
        self.stdout.write('')
        
        if not force and existing_count > 0:
            self.stdout.write(self.style.WARNING(
                f'⚠️  Found {existing_count} existing embeddings. Use --force to regenerate all.'
            ))
            self.stdout.write('')
        
        success_count = 0
        error_count = 0
        skipped_count = 0
        
        for i, career in enumerate(careers, 1):
            try:
                # Check if embedding already exists (unless force)
                if not force:
                    try:
                        existing = CareerEmbedding.objects.get(career=career)
                        # Check if it's still valid
                        career_text = processor._build_career_text(career)
                        text_hash = processor._get_text_hash(career_text)
                        
                        if (existing.embedding_text_hash == text_hash and
                            existing.provider == processor.ai_provider and
                            existing.model_name == processor.embedding_model):
                            skipped_count += 1
                            if i % batch_size == 0:
                                self.stdout.write(f'Progress: {i}/{total} (✓ {success_count} generated, ⊘ {skipped_count} skipped, ✗ {error_count} errors)')
                            continue
                        else:
                            # Invalid cache, delete it
                            existing.delete()
                    except CareerEmbedding.DoesNotExist:
                        pass
                
                # Generate embedding
                with transaction.atomic():
                    processor._get_career_embedding(career)
                
                success_count += 1
                
                if i % batch_size == 0:
                    self.stdout.write(f'Progress: {i}/{total} (✓ {success_count} generated, ⊘ {skipped_count} skipped, ✗ {error_count} errors)')
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'✗ Error processing {career.name} (ID: {career.id}): {str(e)}')
                )
                logger.exception(f"Error processing career {career.id}: {e}")
        
        # Final summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Generation Complete!'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'✓ Successfully generated: {success_count}')
        self.stdout.write(f'⊘ Skipped (already cached): {skipped_count}')
        self.stdout.write(f'✗ Errors: {error_count}')
        self.stdout.write(f'📊 Total in database: {CareerEmbedding.objects.count()}')
        self.stdout.write('')
        
        if success_count > 0:
            self.stdout.write(self.style.SUCCESS(
                '✅ Embeddings are now cached in database!'
            ))
            self.stdout.write('')
            self.stdout.write('Next steps:')
            self.stdout.write('  1. Set ENABLE_SEMANTIC_SEARCH=True in env.local')
            self.stdout.write('  2. You can now remove API keys if you want (embeddings will use cache)')
            self.stdout.write('  3. Query embeddings will still need API keys (or Redis cache)')
            self.stdout.write('')
        
        if error_count > 0:
            self.stdout.write(self.style.WARNING(
                f'⚠️  {error_count} careers failed. Check logs for details.'
            ))

