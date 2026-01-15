"""
Management command to seed initial forum data
Run: python manage.py seed_forum_data
"""
from django.core.management.base import BaseCommand
from forum.models import Category, AIFeature, AICapability, Country


class Command(BaseCommand):
    help = 'Seed initial forum data (categories, AI features, capabilities, countries)'

    def handle(self, *args, **options):
        self.stdout.write('Seeding forum data...')
        
        # Seed Categories
        categories_data = [
            {'name': 'Admission', 'slug': 'admission', 'description': 'University and college admission queries', 'icon': 'fas fa-graduation-cap', 'order': 1},
            {'name': 'Visa & Immigration', 'slug': 'visa', 'description': 'Visa and immigration related questions', 'icon': 'fas fa-passport', 'order': 2},
            {'name': 'Finance & Scholarships', 'slug': 'finance', 'description': 'Financial aid and scholarship information', 'icon': 'fas fa-dollar-sign', 'order': 3},
            {'name': 'Accommodation', 'slug': 'accommodation', 'description': 'Housing and accommodation queries', 'icon': 'fas fa-home', 'order': 4},
            {'name': 'Work & Career', 'slug': 'work', 'description': 'Work rights and career opportunities', 'icon': 'fas fa-briefcase', 'order': 5},
            {'name': 'Pre-Departure', 'slug': 'predeparture', 'description': 'Pre-departure preparation', 'icon': 'fas fa-plane', 'order': 6},
            {'name': 'Country Specific', 'slug': 'country', 'description': 'Country-specific information', 'icon': 'fas fa-globe', 'order': 7},
            {'name': 'STEM', 'slug': 'stem', 'description': 'Science, Technology, Engineering, Mathematics careers', 'icon': 'fas fa-flask', 'order': 8},
            {'name': 'Commerce', 'slug': 'commerce', 'description': 'Commerce and business careers', 'icon': 'fas fa-chart-line', 'order': 9},
            {'name': 'Arts', 'slug': 'arts', 'description': 'Arts and humanities careers', 'icon': 'fas fa-palette', 'order': 10},
            {'name': 'Vocational', 'slug': 'vocational', 'description': 'Vocational and skill-based careers', 'icon': 'fas fa-tools', 'order': 11},
            {'name': 'Emerging Careers', 'slug': 'emerging', 'description': 'Emerging and future careers', 'icon': 'fas fa-rocket', 'order': 12},
            {'name': 'Study Abroad', 'slug': 'studyabroad', 'description': 'International education opportunities', 'icon': 'fas fa-globe-americas', 'order': 13},
        ]
        
        created_categories = 0
        for cat_data in categories_data:
            category, created = Category.objects.get_or_create(
                slug=cat_data['slug'],
                defaults=cat_data
            )
            if created:
                created_categories += 1
            else:
                # Update existing category
                for key, value in cat_data.items():
                    setattr(category, key, value)
                category.save()
        
        self.stdout.write(self.style.SUCCESS(f'✓ Created/Updated {created_categories} categories'))
        
        # Seed AI Features
        features_data = [
            {'name': 'Psychometric Assessment Link', 'icon': 'fas fa-check-circle', 'order': 1},
            {'name': 'Stream Selection Guidance', 'icon': 'fas fa-check-circle', 'order': 2},
            {'name': 'Career Cluster Matching', 'icon': 'fas fa-check-circle', 'order': 3},
            {'name': 'College & University Finder', 'icon': 'fas fa-check-circle', 'order': 4},
            {'name': 'Entrance Exam Guidance', 'icon': 'fas fa-check-circle', 'order': 5},
            {'name': 'Emerging Careers Alert', 'icon': 'fas fa-check-circle', 'order': 6},
            {'name': 'Part-time Job Options', 'icon': 'fas fa-check-circle', 'order': 7},
            {'name': 'Study Abroad Guidance', 'icon': 'fas fa-check-circle', 'order': 8},
        ]
        
        created_features = 0
        for feat_data in features_data:
            feature, created = AIFeature.objects.get_or_create(
                name=feat_data['name'],
                defaults=feat_data
            )
            if created:
                created_features += 1
            else:
                # Update existing feature
                for key, value in feat_data.items():
                    setattr(feature, key, value)
                feature.save()
        
        self.stdout.write(self.style.SUCCESS(f'✓ Created/Updated {created_features} AI features'))
        
        # Seed AI Capabilities
        capabilities_data = [
            {'name': 'Career Cluster Analysis', 'icon': 'fas fa-brain', 'order': 1},
            {'name': 'Job Market Trends', 'icon': 'fas fa-chart-line', 'order': 2},
            {'name': 'College Predictor', 'icon': 'fas fa-graduation-cap', 'order': 3},
            {'name': 'Salary Calculator', 'icon': 'fas fa-calculator', 'order': 4},
            {'name': 'Study Abroad Guide', 'icon': 'fas fa-globe', 'order': 5},
            {'name': 'Skills Gap Analysis', 'icon': 'fas fa-briefcase', 'order': 6},
            {'name': 'Accommodation Finder', 'icon': 'fas fa-home', 'order': 7},
            {'name': 'Timeline Planner', 'icon': 'fas fa-clock', 'order': 8},
        ]
        
        created_capabilities = 0
        for cap_data in capabilities_data:
            capability, created = AICapability.objects.get_or_create(
                name=cap_data['name'],
                defaults=cap_data
            )
            if created:
                created_capabilities += 1
            else:
                # Update existing capability
                for key, value in cap_data.items():
                    setattr(capability, key, value)
                capability.save()
        
        self.stdout.write(self.style.SUCCESS(f'✓ Created/Updated {created_capabilities} AI capabilities'))
        
        # Seed some common countries
        countries_data = [
            {'name': 'United States', 'code': 'US', 'flag_emoji': '🇺🇸'},
            {'name': 'United Kingdom', 'code': 'GB', 'flag_emoji': '🇬🇧'},
            {'name': 'Canada', 'code': 'CA', 'flag_emoji': '🇨🇦'},
            {'name': 'Australia', 'code': 'AU', 'flag_emoji': '🇦🇺'},
            {'name': 'Germany', 'code': 'DE', 'flag_emoji': '🇩🇪'},
            {'name': 'France', 'code': 'FR', 'flag_emoji': '🇫🇷'},
            {'name': 'Singapore', 'code': 'SG', 'flag_emoji': '🇸🇬'},
            {'name': 'Japan', 'code': 'JP', 'flag_emoji': '🇯🇵'},
            {'name': 'Netherlands', 'code': 'NL', 'flag_emoji': '🇳🇱'},
            {'name': 'New Zealand', 'code': 'NZ', 'flag_emoji': '🇳🇿'},
        ]
        
        created_countries = 0
        for country_data in countries_data:
            country, created = Country.objects.get_or_create(
                code=country_data['code'],
                defaults=country_data
            )
            if created:
                created_countries += 1
            else:
                # Update existing country
                for key, value in country_data.items():
                    setattr(country, key, value)
                country.save()
        
        self.stdout.write(self.style.SUCCESS(f'✓ Created/Updated {created_countries} countries'))
        
        self.stdout.write(self.style.SUCCESS('\n✓ Forum data seeding completed!'))
        self.stdout.write('You can now access the forum at /forum/')
