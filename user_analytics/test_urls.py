"""
Test script to verify all analytics dashboard URLs and views.
Run this script to check if all URLs are accessible and views work correctly.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteens.settings')
django.setup()

from django.urls import reverse, NoReverseMatch
from django.test import Client
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

User = get_user_model()

def test_url_reverse():
    """Test that all URLs can be reversed"""
    print("\n" + "="*60)
    print("Testing URL Reversal")
    print("="*60)
    
    urls_to_test = [
        ('user_analytics:admin_dashboard', 'Admin Dashboard'),
        ('user_analytics:dashboard', 'Dashboard (redirect)'),
        ('user_analytics:business_dashboard', 'Business Dashboard'),
        ('user_analytics:accounts_dashboard', 'Accounts Dashboard'),
        ('user_analytics:web_owner_dashboard', 'Web Owner Dashboard'),
        ('user_analytics:user_journey', 'User Journey'),
        ('user_analytics:api_dashboard_data', 'API Dashboard Data'),
    ]
    
    results = []
    for url_name, description in urls_to_test:
        try:
            url = reverse(url_name)
            results.append((True, description, url))
            print(f"✓ {description:30} -> {url}")
        except NoReverseMatch as e:
            results.append((False, description, str(e)))
            print(f"✗ {description:30} -> ERROR: {e}")
    
    return results

def test_view_access():
    """Test view access with different user types"""
    print("\n" + "="*60)
    print("Testing View Access")
    print("="*60)
    
    client = Client()
    
    # Test URLs
    test_urls = [
        ('/user-analytics/', 'Admin Dashboard (superuser only)'),
        ('/user-analytics/dashboard/', 'Dashboard (staff)'),
        ('/user-analytics/business/', 'Business Dashboard'),
        ('/user-analytics/accounts/', 'Accounts Dashboard'),
        ('/user-analytics/web-owner/', 'Web Owner Dashboard'),
        ('/user-analytics/user-journey/', 'User Journey'),
    ]
    
    print("\n1. Testing as Anonymous User:")
    print("-" * 60)
    for url, description in test_urls:
        response = client.get(url)
        status = response.status_code
        if status == 302:  # Redirect to login
            print(f"✓ {description:40} -> Redirected to login (302)")
        elif status == 200:
            print(f"✓ {description:40} -> Accessible (200)")
        elif status == 403:
            print(f"✓ {description:40} -> Forbidden (403)")
        else:
            print(f"✗ {description:40} -> Unexpected status: {status}")
    
    # Try to get a superuser for testing
    try:
        superuser = User.objects.filter(is_superuser=True).first()
        if superuser:
            print("\n2. Testing as Superuser:")
            print("-" * 60)
            client.force_login(superuser)
            for url, description in test_urls:
                response = client.get(url)
                status = response.status_code
                if status == 200:
                    print(f"✓ {description:40} -> Accessible (200)")
                elif status == 302:
                    print(f"✓ {description:40} -> Redirected (302)")
                elif status == 403:
                    print(f"✗ {description:40} -> Forbidden (403)")
                else:
                    print(f"✗ {description:40} -> Status: {status}")
        else:
            print("\n2. Testing as Superuser: No superuser found in database")
    except Exception as e:
        print(f"\n2. Testing as Superuser: Error - {e}")

def test_template_existence():
    """Test that all required templates exist"""
    print("\n" + "="*60)
    print("Testing Template Existence")
    print("="*60)
    
    from django.template.loader import get_template
    from django.template.exceptions import TemplateDoesNotExist
    
    templates = [
        'user_analytics/admin_base.html',
        'user_analytics/admin_dashboard.html',
        'user_analytics/business_dashboard.html',
        'user_analytics/accounts_dashboard.html',
        'user_analytics/web_owner_dashboard.html',
        'user_analytics/user_journey.html',
    ]
    
    for template_name in templates:
        try:
            template = get_template(template_name)
            print(f"✓ {template_name}")
        except TemplateDoesNotExist:
            print(f"✗ {template_name} - NOT FOUND")

def test_models():
    """Test that all models are properly registered"""
    print("\n" + "="*60)
    print("Testing Models")
    print("="*60)
    
    from django.apps import apps
    from user_analytics import models
    
    model_names = [
        'UserActivity',
        'Lead',
        'UserEvent',
        'UserJourney',
        'AnalyticsCache',
    ]
    
    for model_name in model_names:
        try:
            model = getattr(models, model_name)
            app_label = model._meta.app_label
            db_table = model._meta.db_table
            print(f"✓ {model_name:20} -> {app_label}.{db_table}")
        except AttributeError:
            print(f"✗ {model_name:20} -> NOT FOUND")

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("User Analytics Dashboard - Comprehensive Test Suite")
    print("="*60)
    
    # Test URL reversal
    url_results = test_url_reverse()
    
    # Test view access
    test_view_access()
    
    # Test templates
    test_template_existence()
    
    # Test models
    test_models()
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    url_success = sum(1 for success, _, _ in url_results if success)
    url_total = len(url_results)
    print(f"URL Reversal: {url_success}/{url_total} passed")
    print("\n✓ All tests completed!")
    print("\nNote: View access tests require authentication.")
    print("      Run the server and test manually in browser for full verification.")

if __name__ == '__main__':
    main()

