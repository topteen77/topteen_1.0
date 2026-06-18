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
        
        # Seed AI Features with links to relevant pages
        features_data = [
            {
                'name': 'Psychometric Assessment Link',
                'icon': 'fas fa-brain',
                'description': 'Take psychometric tests to discover your career interests',
                'link_url': '/psychometrictest/career-direction/',  # Default, will be dynamically updated based on user class
                'order': 1
            },
            {
                'name': 'Stream Selection Guidance',
                'icon': 'fas fa-graduation-cap',
                'description': 'Get guidance on choosing the right stream after 10th',
                'link_url': '/careers/',
                'order': 2,
                'is_active': False,  # temporarily hidden
            },
            {
                'name': 'Career Cluster Matching',
                'icon': 'fas fa-sitemap',
                'description': 'Explore careers by clusters and find your match',
                'link_url': '/careers/',
                'order': 3
            },
            {
                'name': 'College & University Finder',
                'icon': 'fas fa-university',
                'description': 'Find the best colleges and universities for your career',
                'link_url': '/colleges/',
                'order': 4
            },
            {
                'name': 'Entrance Exam Guidance',
                'icon': 'fas fa-clipboard-list',
                'description': 'Get information about entrance exams and preparation',
                'link_url': '/entrance-test-prep/',
                'order': 5
            },
            {
                'name': 'Emerging Careers Alert',
                'icon': 'fas fa-rocket',
                'description': 'Discover emerging and future career opportunities',
                'link_url': '/careers/',
                'order': 6,
                'is_active': False,  # temporarily hidden
            },
            {
                'name': 'Part-time Job Options',
                'icon': 'fas fa-briefcase',
                'description': 'Explore part-time job opportunities for students',
                'link_url': '/careers/',
                'order': 7,
                'is_active': False,  # temporarily hidden
            },
            {
                'name': 'Study Abroad Guidance',
                'icon': 'fas fa-globe',
                'description': 'Get guidance on studying abroad and international education',
                'link_url': 'https://www.canamgroup.com/guide-to-study-abroad',
                'order': 8
            },
        ]
        
        created_features = 0
        updated_features = 0
        for feat_data in features_data:
            feature, created = AIFeature.objects.get_or_create(
                name=feat_data['name'],
                defaults=feat_data
            )
            if created:
                created_features += 1
            else:
                # Update existing feature with new data (especially link_url)
                updated = False
                for key, value in feat_data.items():
                    if key != 'name':  # Don't update the name (used for lookup)
                        if getattr(feature, key, None) != value:
                            setattr(feature, key, value)
                            updated = True
                if updated:
                    feature.save()
                    updated_features += 1
        
        self.stdout.write(self.style.SUCCESS(f'✓ Created {created_features} AI features, Updated {updated_features} existing features'))
        
        # Seed AI Capabilities with links to relevant pages
        capabilities_data = [
            {
                'name': 'Career Cluster Analysis',
                'icon': 'fas fa-sitemap',
                'description': 'Analyze career clusters based on your interests',
                'link_url': '/careers/careerlibrary/',
                'order': 1
            },
            {
                'name': 'Job Market Trends',
                'icon': 'fas fa-chart-line',
                'description': 'Explore current job market trends and opportunities',
                'link_url': '/careers/',
                'order': 2
            },
            {
                'name': 'College Predictor',
                'icon': 'fas fa-university',
                'description': 'Find colleges that match your profile and preferences',
                'link_url': '/colleges/',
                'order': 3
            },
            {
                'name': 'Salary Calculator',
                'icon': 'fas fa-calculator',
                'description': 'Calculate and compare career salaries',
                'link_url': '/careers/',
                'order': 4
            },
            {
                'name': 'Study Abroad Guide',
                'icon': 'fas fa-globe',
                'description': 'Comprehensive guide for studying abroad',
                'link_url': '/colleges/',
                'order': 5
            },
            {
                'name': 'Skills Gap Analysis',
                'icon': 'fas fa-briefcase',
                'description': 'Identify skills needed for your target career',
                'link_url': '/careers/',
                'order': 6
            },
            {
                'name': 'Accommodation Finder',
                'icon': 'fas fa-home',
                'description': 'Find accommodation options for students',
                'link_url': '/colleges/',
                'order': 7
            },
            {
                'name': 'Timeline Planner',
                'icon': 'fas fa-clock',
                'description': 'Plan your career journey timeline',
                'link_url': '/careers/',
                'order': 8
            },
        ]
        
        created_capabilities = 0
        updated_capabilities = 0
        for cap_data in capabilities_data:
            capability, created = AICapability.objects.get_or_create(
                name=cap_data['name'],
                defaults=cap_data
            )
            if created:
                created_capabilities += 1
            else:
                # Update existing capability with new data (especially link_url)
                updated = False
                for key, value in cap_data.items():
                    if key != 'name':  # Don't update the name (used for lookup)
                        if getattr(capability, key, None) != value:
                            setattr(capability, key, value)
                            updated = True
                if updated:
                    capability.save()
                    updated_capabilities += 1
        
        self.stdout.write(self.style.SUCCESS(f'✓ Created {created_capabilities} AI capabilities, Updated {updated_capabilities} existing capabilities'))
        
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
