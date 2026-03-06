#!/usr/bin/env python
"""
Test script to verify visitors_detail view filters work correctly
"""
import os
import sys
import django
from django.test import RequestFactory
from django.contrib.auth import get_user_model

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteens.settings')

try:
    django.setup()
except Exception as e:
    print(f"Error: Could not setup Django: {e}")
    sys.exit(1)

from user_analytics.views import visitors_detail
from django.contrib.auth.models import AnonymousUser

def test_visitors_filters():
    """Test visitors_detail view with various filters"""
    print("=" * 80)
    print("Testing Visitors Detail Filters")
    print("=" * 80)
    
    factory = RequestFactory()
    User = get_user_model()
    
    # Create a test user (staff)
    try:
        test_user = User.objects.filter(is_staff=True).first()
        if not test_user:
            print("✗ No staff user found. Please create a staff user first.")
            return False
    except Exception as e:
        print(f"✗ Error getting user: {e}")
        return False
    
    # Test cases
    test_cases = [
        {
            'name': 'Today + New Users + China',
            'params': {'period': 'today', 'user_type': 'new', 'country': 'China'}
        },
        {
            'name': 'Today + All Users + China',
            'params': {'period': 'today', 'user_type': 'all', 'country': 'China'}
        },
        {
            'name': 'Today + Registered Users',
            'params': {'period': 'today', 'user_type': 'registered'}
        },
        {
            'name': '30 Days + New Users',
            'params': {'period': '30days', 'user_type': 'new'}
        },
        {
            'name': '30 Days + Source Google',
            'params': {'period': '30days', 'source': 'google'}
        },
        {
            'name': '7 Days + Source Facebook',
            'params': {'period': '7days', 'source': 'facebook'}
        },
    ]
    
    for test_case in test_cases:
        print(f"\nTest: {test_case['name']}")
        print(f"Params: {test_case['params']}")
        
        try:
            request = factory.get('/user-analytics/business/visitors/', test_case['params'])
            request.user = test_user
            
            # Mock session
            from django.contrib.sessions.middleware import SessionMiddleware
            middleware = SessionMiddleware(lambda x: None)
            middleware.process_request(request)
            request.session.save()
            
            response = visitors_detail(request)
            
            if response.status_code == 200:
                print(f"  ✓ Response OK (200)")
                # Check context
                if hasattr(response, 'context_data'):
                    context = response.context_data
                    print(f"  - Total count: {context.get('total_count', 0)}")
                    print(f"  - User type filter: {context.get('user_type_filter', 'N/A')}")
                    print(f"  - Country filter: {context.get('country_filter', 'N/A')}")
                    print(f"  - Source filter: {context.get('source_filter', 'N/A')}")
                    print(f"  - Has GA4 data: {context.get('has_database_data', False)}")
                    print(f"  - GA4 needs sync: {context.get('ga4_needs_sync', False)}")
            elif response.status_code == 302:
                print(f"  ⚠ Redirected (302) - likely login required")
            else:
                print(f"  ✗ Unexpected status: {response.status_code}")
                
        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("Testing completed")
    print("=" * 80)
    return True

if __name__ == '__main__':
    test_visitors_filters()
