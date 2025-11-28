#!/usr/bin/env python
"""
Utility script to update verification status in checklist CSV

Usage:
    python scripts/update_verification_status.py --student-id 2298 --status Passed
    python scripts/update_verification_status.py --student-id 2298 --status Failed --reason "Code mismatch"
    python scripts/update_verification_status.py --student-name st1-ria-pcm --status Passed
"""

import os
import sys
import django
import argparse

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteens.settings')
django.setup()

from scripts.checklist_manager import ChecklistManager


def update_status(student_id=None, student_name=None, status=None, reason='', specific_check=None, test_verification=None):
    """Update verification status for a checklist item"""
    
    if status and status not in ['Passed', 'Failed', 'Pending']:
        print(f"❌ Invalid status: {status}")
        print("   Valid values: Passed, Failed, Pending")
        return False
    
    if test_verification and test_verification not in ['pass', 'fail']:
        print(f"❌ Invalid test_verification: {test_verification}")
        print("   Valid values: pass, fail")
        return False
    
    manager = ChecklistManager()
    manager.load_checklist()
    
    if not manager.checklist_items:
        print("❌ No checklist items found")
        return False
    
    # Find matching items
    updated_count = 0
    for item in manager.checklist_items:
        match = False
        
        if student_id and item.get('Student ID') == str(student_id):
            match = True
        elif student_name and item.get('Student Name') == student_name:
            match = True
        
        if match:
            # If specific_check is provided, match that too
            if specific_check and item.get('Specific Check') != specific_check:
                continue
            
            # Update Verification Status if provided
            if status:
                old_status = item.get('Verification Status', 'Pending')
                item['Verification Status'] = status
                if reason:
                    item['Failure Reason'] = reason
                elif status == 'Passed':
                    item['Failure Reason'] = ''  # Clear failure reason if passed
                print(f"✅ Updated Verification Status: {old_status} → {status}")
            
            # Update Test Verification if provided
            if test_verification:
                old_test_verification = item.get('Test Verification', '')
                # Set to 'fail' if failed, empty string '' if passed
                item['Test Verification'] = 'fail' if test_verification == 'fail' else ''
                print(f"✅ Updated Test Verification: '{old_test_verification}' → '{item['Test Verification']}'")
            
            updated_count += 1
            print(f"   Student: {item.get('Student Name')} - {item.get('Specific Check')}")
            if reason:
                print(f"   Reason: {reason}")
    
    if updated_count == 0:
        print(f"❌ No matching items found")
        if student_id:
            print(f"   Student ID: {student_id}")
        if student_name:
            print(f"   Student Name: {student_name}")
        if specific_check:
            print(f"   Specific Check: {specific_check}")
        return False
    
    # Save updated checklist
    manager.write_checklist()
    print(f"\n✅ Updated {updated_count} item(s)")
    print(f"   Checklist saved: {manager.checklist_file}")
    return True


def list_items(student_id=None, student_name=None):
    """List checklist items"""
    manager = ChecklistManager()
    manager.load_checklist()
    
    if not manager.checklist_items:
        print("No checklist items found")
        return
    
    print(f"\n📋 Checklist Items ({len(manager.checklist_items)} total)\n")
    print(f"{'ID':<8} {'Name':<20} {'Check':<20} {'Status':<12} {'Test Verif':<12} {'URL':<50}")
    print("-" * 120)
    
    for item in manager.checklist_items:
        if student_id and item.get('Student ID') != str(student_id):
            continue
        if student_name and item.get('Student Name') != student_name:
            continue
        
        student_id_val = item.get('Student ID', '')[:8]
        name = item.get('Student Name', '')[:20]
        check = item.get('Specific Check', '')[:20]
        status = item.get('Verification Status', 'Pending')[:12]
        test_verif = item.get('Test Verification', '')[:12] or '(empty)'
        url = item.get('Report URL', '')[:50]
        
        print(f"{student_id_val:<8} {name:<20} {check:<20} {status:<12} {test_verif:<12} {url:<50}")


def main():
    parser = argparse.ArgumentParser(description='Update verification status in checklist CSV')
    parser.add_argument('--student-id', type=str, help='Student ID to update')
    parser.add_argument('--student-name', type=str, help='Student name to update')
    parser.add_argument('--status', type=str, choices=['Passed', 'Failed', 'Pending'], 
                       help='Verification status (Passed/Failed/Pending)')
    parser.add_argument('--test-verification', type=str, choices=['pass', 'fail'],
                       help='Test verification (pass/fail) - shows "fail" if failed, empty "" if passed')
    parser.add_argument('--reason', type=str, default='', 
                       help='Failure reason (optional, required if status is Failed)')
    parser.add_argument('--specific-check', type=str, 
                       help='Specific check to update (if multiple items match)')
    parser.add_argument('--list', action='store_true', 
                       help='List all checklist items')
    
    args = parser.parse_args()
    
    if args.list:
        list_items(student_id=args.student_id, student_name=args.student_name)
        return
    
    if not args.status and not args.test_verification:
        print("❌ Error: Either --status or --test-verification is required (use --list to view items)")
        parser.print_help()
        return
    
    if not args.student_id and not args.student_name:
        print("❌ Error: Either --student-id or --student-name is required")
        parser.print_help()
        return
    
    if args.status == 'Failed' and not args.reason:
        print("⚠️  Warning: Status is 'Failed' but no reason provided")
        print("   Use --reason to add failure reason")
    
    update_status(
        student_id=args.student_id,
        student_name=args.student_name,
        status=args.status,
        test_verification=args.test_verification,
        reason=args.reason,
        specific_check=args.specific_check
    )


if __name__ == '__main__':
    main()

