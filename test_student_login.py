#!/usr/bin/env python3
"""
Test script for Institute Student Login
Shows debug information for existing school students with:
- Password set
- Profile hobbies
- Profile interests (subjects, figure_out)
"""

import os
import sys
import django
from django.conf import settings

# Setup Django
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteens.settings')
django.setup()

# Enable debug logging
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Get Django modules
from django.contrib.auth import get_user_model, authenticate
from django.test import Client
from institute.models import StudentManagement, Institute
from core import choices
from users.models import UserProfile

User = get_user_model()

def print_separator(title=""):
    """Print a visual separator"""
    if title:
        print("\n" + "=" * 80)
        print(f"  {title}")
        print("=" * 80)
    else:
        print("-" * 80)

def test_student_login():
    """Find and test login for an existing institute student"""
    
    print_separator("INSTITUTE STUDENT LOGIN TEST")
    
    # Find institute students
    print("\n[1] Finding Institute Students...")
    student_managements = StudentManagement.objects.filter(
        student__user_type=choices.UserType.STUDENT,
        student__is_active=True
    ).select_related('student', 'institute', 'class_and_section').prefetch_related(
        'student__user_profile__hobbies',
        'student__user_profile__subject',
        'student__user_profile__figure_out'
    )[:10]
    
    if not student_managements.exists():
        print("❌ No institute students found!")
        return
    
    print(f"✓ Found {student_managements.count()} institute student(s)")
    
    # Find a student with profile data
    selected_student = None
    for sm in student_managements:
        student = sm.student
        if hasattr(student, 'user_profile') and student.user_profile:
            profile = student.user_profile
            has_hobbies = profile.hobbies.exists()
            has_subjects = profile.subject.exists()
            has_figure_out = profile.figure_out.exists()
            
            if has_hobbies or has_subjects or has_figure_out:
                selected_student = sm
                print(f"\n✓ Selected student with profile data: {student.email}")
                break
    
    if not selected_student:
        # Use first student even without profile
        selected_student = student_managements.first()
        print(f"\n⚠ Using first available student: {selected_student.student.email}")
        print("  (Profile may be incomplete)")
    
    student = selected_student.student
    institute = selected_student.institute
    class_section = selected_student.class_and_section
    
    # Display student information
    print_separator("STUDENT INFORMATION")
    
    print(f"\n📧 Email: {student.email}")
    print(f"👤 Name: {student.name or 'Not set'}")
    print(f"📱 Mobile: {student.mobile or 'Not set'}")
    print(f"🆔 User ID: {student.id}")
    print(f"✅ Is Active: {student.is_active}")
    print(f"✅ Is Completed: {getattr(student, 'is_completed', False)}")
    print(f"🏫 Institute: {institute.name if institute else 'Not assigned'}")
    print(f"📚 Class & Section: {class_section.class_and_section if class_section else 'Not assigned'}")
    
    # Check password
    print_separator("PASSWORD STATUS")
    has_password = student.has_usable_password()
    print(f"🔐 Has Password Set: {'✅ YES' if has_password else '❌ NO'}")
    
    if not has_password:
        print("\n⚠️  WARNING: Student has no password set!")
        print("   Password cannot be retrieved, but you can reset it.")
        return
    
    # Display profile information
    print_separator("PROFILE INFORMATION")
    
    hobbies = []
    subjects = []
    figure_outs = []
    
    if hasattr(student, 'user_profile') and student.user_profile:
        profile = student.user_profile
        print(f"📅 Birthdate: {profile.birthdate or 'Not set'}")
        print(f"⚧️  Gender: {profile.get_gender_display() if profile.gender else 'Not set'}")
        print(f"🏫 School: {profile.schoolname or 'Not set'}")
        print(f"📊 Grade: {profile.grade or 'Not set'}")
        
        # Hobbies
        print("\n🎨 HOBBIES:")
        hobbies = list(profile.hobbies.all())
        if hobbies:
            for hobby in hobbies:
                print(f"   • {hobby.name}")
        else:
            print("   ❌ No hobbies set")
        
        # Subjects (Interests)
        print("\n📖 SUBJECTS (Interests):")
        subjects = list(profile.subject.all())
        if subjects:
            for subject in subjects:
                print(f"   • {subject.name}")
        else:
            print("   ❌ No subjects set")
        
        # Figure Out (Interests)
        print("\n🔍 FIGURE OUT (Interests):")
        figure_outs = list(profile.figure_out.all())
        if figure_outs:
            for fo in figure_outs:
                print(f"   • {fo.name}")
        else:
            print("   ❌ No figure_out interests set")
    else:
        print("❌ No user profile found!")
    
    # Test login
    print_separator("LOGIN TEST")
    
    print("\n[2] Testing login authentication...")
    print(f"   Email: {student.email}")
    print("   Password: [Testing with Django authentication]")
    
    # If we want to set a test password and login
    print_separator("AUTOMATED TEST LOGIN")
    print("\n[3] Setting test password and attempting login...")
    
    test_password = "test123456"
    student.set_password(test_password)
    student.save()
    print(f"✓ Password set to: {test_password}")
    
    # Test authentication
    authenticated_user = authenticate(email=student.email, password=test_password)
    if authenticated_user:
        print(f"✅ Authentication SUCCESSFUL!")
        print(f"   Authenticated as: {authenticated_user.email}")
    else:
        print(f"❌ Authentication FAILED!")
    
    # Test login via Client
    client = Client()
    login_success = client.login(email=student.email, password=test_password)
    if login_success:
        print(f"✅ Client Login SUCCESSFUL!")
        
        # Test accessing a protected page
        print("\n[4] Testing access to user dashboard...")
        try:
            response = client.get('/user/dashboard/')
            print(f"   Dashboard Status Code: {response.status_code}")
            if response.status_code == 200:
                print("   ✅ Dashboard accessible")
            else:
                print(f"   ⚠️  Dashboard returned status {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error accessing dashboard: {e}")
    else:
        print(f"❌ Client Login FAILED!")
    
    # Summary
    print_separator("SUMMARY")
    print(f"\n✅ Student Email: {student.email}")
    print(f"✅ Test Password: {test_password}")
    print(f"✅ Has Profile: {hasattr(student, 'user_profile') and student.user_profile is not None}")
    print(f"✅ Has Hobbies: {len(hobbies) > 0}")
    print(f"✅ Has Subjects: {len(subjects) > 0}")
    print(f"✅ Has Figure Out: {len(figure_outs) > 0}")
    print(f"✅ Login Test: {'SUCCESS' if login_success else 'FAILED'}")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETED")
    print("=" * 80 + "\n")
    
    return {
        'student': student,
        'email': student.email,
        'password': test_password,
        'login_success': login_success,
        'has_profile': hasattr(student, 'user_profile') and student.user_profile is not None,
        'has_hobbies': len(hobbies) > 0,
        'has_subjects': len(subjects) > 0,
        'has_figure_out': len(figure_outs) > 0,
    }

if __name__ == '__main__':
    try:
        result = test_student_login()
        if result:
            print("\n✅ Test completed successfully!")
            print(f"\n📋 Login Credentials:")
            print(f"   Email: {result['email']}")
            print(f"   Password: {result['password']}")
        else:
            print("\n❌ Test failed - no student found")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

