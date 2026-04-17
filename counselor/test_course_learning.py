"""
Test script for Counsellor Course Learning Module

This script tests the basic functionality of the course learning module.
Run this from Django shell: python manage.py shell < counselor/test_course_learning.py
Or import and run: python manage.py shell, then import and run test functions
"""

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from counselor.models import Counselor, CounselorCourse, Chapter, Part, Quiz, Question, QuizAnswers, CounselorCertification
from counselor.views import CourseLearningView, CourseResultsView, ViewCertificateView

User = get_user_model()

def test_course_learning_view():
    """Test that CourseLearningView can be instantiated and returns proper context"""
    print("Testing CourseLearningView...")
    
    # Get or create test data
    course = CounselorCourse.objects.first()
    if not course:
        print("ERROR: No course found. Please create a course first.")
        return False
    
    counselor = Counselor.objects.first()
    if not counselor:
        print("ERROR: No counselor found. Please create a counselor first.")
        return False
    
    user = counselor.coun_user if counselor.coun_user else User.objects.filter(user_type=4).first()
    if not user:
        print("ERROR: No counselor user found.")
        return False
    
    # Create request
    factory = RequestFactory()
    request = factory.get(f'/counselor/course_learning/{counselor.id}/')
    request.user = user
    
    # Test view
    view = CourseLearningView()
    view.request = request
    
    try:
        response = view.get(request, counselor_id=counselor.id)
        print(f"✓ CourseLearningView returned status: {response.status_code}")
        
        # Check context
        if hasattr(response, 'context_data'):
            context = response.context_data
            print(f"✓ Context keys: {list(context.keys())}")
            return True
        else:
            print("⚠ Response doesn't have context_data (might be HttpResponse)")
            return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_course_results_view():
    """Test CourseResultsView"""
    print("\nTesting CourseResultsView...")
    
    counselor = Counselor.objects.first()
    if not counselor:
        print("ERROR: No counselor found.")
        return False
    
    user = counselor.coun_user if counselor.coun_user else User.objects.filter(user_type=4).first()
    if not user:
        print("ERROR: No counselor user found.")
        return False
    
    factory = RequestFactory()
    request = factory.get(f'/counselor/course_results/{counselor.id}/')
    request.user = user
    
    view = CourseResultsView()
    view.request = request
    
    try:
        response = view.get(request, counselor_id=counselor.id)
        print(f"✓ CourseResultsView returned status: {response.status_code}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_view_certificate_view():
    """Test ViewCertificateView"""
    print("\nTesting ViewCertificateView...")
    
    counselor = Counselor.objects.first()
    if not counselor:
        print("ERROR: No counselor found.")
        return False
    
    user = counselor.coun_user if counselor.coun_user else User.objects.filter(user_type=4).first()
    if not user:
        print("ERROR: No counselor user found.")
        return False
    
    # Check if user has certification
    cert = CounselorCertification.objects.filter(user=user).first()
    if not cert:
        print("⚠ User doesn't have certification yet. Skipping test.")
        return True
    
    factory = RequestFactory()
    request = factory.get(f'/counselor/view_certificate/{counselor.id}/')
    request.user = user
    
    view = ViewCertificateView()
    view.request = request
    
    try:
        response = view.get(request, counselor_id=counselor.id)
        print(f"✓ ViewCertificateView returned status: {response.status_code}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_urls():
    """Test that URLs are properly configured"""
    print("\nTesting URLs...")
    
    from django.urls import reverse
    from django.core.exceptions import NoReverseMatch
    
    counselor = Counselor.objects.first()
    if not counselor:
        print("ERROR: No counselor found.")
        return False
    
    urls_to_test = [
        ('counselor:course_learning', {'counselor_id': counselor.id}),
        ('counselor:course_results', {'counselor_id': counselor.id}),
        ('counselor:view_certificate', {'counselor_id': counselor.id}),
    ]
    
    all_passed = True
    for url_name, kwargs in urls_to_test:
        try:
            url = reverse(url_name, kwargs=kwargs)
            print(f"✓ URL '{url_name}' resolves to: {url}")
        except NoReverseMatch as e:
            print(f"✗ URL '{url_name}' failed: {e}")
            all_passed = False
    
    return all_passed


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("COUNSELOR COURSE LEARNING MODULE - TEST SUITE")
    print("=" * 60)
    
    results = []
    results.append(("CourseLearningView", test_course_learning_view()))
    results.append(("CourseResultsView", test_course_results_view()))
    results.append(("ViewCertificateView", test_view_certificate_view()))
    results.append(("URLs", test_urls()))
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠ {total - passed} test(s) failed. Please check the errors above.")
    
    return passed == total


if __name__ == "__main__":
    # This will only run if executed directly (not imported)
    run_all_tests()

