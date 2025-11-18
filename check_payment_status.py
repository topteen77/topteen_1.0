#!/usr/bin/env python
"""
Script to check payment status in database
Usage: python check_payment_status.py [user_id] [test_id]
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteens.settings')
django.setup()

from psychometric_tests.models import PsychometricTestPayment
from payments.models import Payment
from core import choices
from django.contrib.auth import get_user_model

User = get_user_model()

def check_payment_status(user_id=None, test_id=None):
    """Check payment status for a user or specific test"""
    print("=" * 80)
    print("PAYMENT STATUS CHECK")
    print("=" * 80)
    
    if test_id:
        # Check specific test payment
        try:
            test_payment = PsychometricTestPayment.objects.get(id=test_id)
            print(f"\nTest Payment ID: {test_payment.id}")
            print(f"User: {test_payment.user.email} (ID: {test_payment.user.id})")
            print(f"Test Type: {test_payment.get_test_type_display()}")
            print(f"Amount: ₹{test_payment.amount}")
            print(f"Payment Status: {'SUCCESS' if test_payment.is_success == choices.YesNoChoices.YES else 'FAILED/PENDING'}")
            print(f"Is Success Value: {test_payment.is_success}")
            print(f"Gateway Receipt: {test_payment.gateway_receipt}")
            print(f"Created: {test_payment.created}")
            print(f"Modified: {test_payment.modified}")
            
            # Check related Payment record
            payments = Payment.objects.filter(
                obj_id=test_payment.id,
                obj_type=choices.PaymentObjectType.PYSCHOMETRICTESTDETAIL,
                gateway_receipt=test_payment.gateway_receipt
            )
            
            if payments.exists():
                payment = payments.first()
                print(f"\n--- Related Payment Record ---")
                print(f"Payment ID: {payment.id}")
                print(f"Gateway: {payment.get_gateway_display()}")
                print(f"Payment Status: {'SUCCESS' if payment.is_success == choices.YesNoChoices.YES else 'FAILED/PENDING'}")
                print(f"Is Success Value: {payment.is_success}")
                print(f"Gateway Payment ID: {payment.gateway_payment_id or 'Not set'}")
                print(f"Gateway Order ID: {payment.gateway_order_id or 'Not set'}")
                print(f"Created: {payment.created}")
                print(f"Modified: {payment.modified}")
            else:
                print("\n--- No Payment record found ---")
                
        except PsychometricTestPayment.DoesNotExist:
            print(f"Test Payment with ID {test_id} not found")
    
    elif user_id:
        # Check all payments for a user
        try:
            user = User.objects.get(id=user_id)
            print(f"\nUser: {user.email} (ID: {user.id})")
            
            test_payments = PsychometricTestPayment.objects.filter(user=user).order_by('-created')
            print(f"\nTotal Test Payments: {test_payments.count()}")
            print("\n" + "-" * 80)
            
            for test_payment in test_payments[:10]:  # Show last 10
                print(f"\nTest Payment ID: {test_payment.id}")
                print(f"Test Type: {test_payment.get_test_type_display()}")
                print(f"Amount: ₹{test_payment.amount}")
                print(f"Status: {'SUCCESS' if test_payment.is_success == choices.YesNoChoices.YES else 'FAILED/PENDING'}")
                print(f"Gateway Receipt: {test_payment.gateway_receipt}")
                print(f"Created: {test_payment.created}")
                
                # Check related payment
                payment = Payment.objects.filter(
                    obj_id=test_payment.id,
                    obj_type=choices.PaymentObjectType.PYSCHOMETRICTESTDETAIL
                ).first()
                
                if payment:
                    print(f"  → Payment ID: {payment.id}, Status: {'SUCCESS' if payment.is_success == choices.YesNoChoices.YES else 'FAILED/PENDING'}, Gateway: {payment.get_gateway_display()}")
                else:
                    print(f"  → No Payment record found")
                print("-" * 80)
                
        except User.DoesNotExist:
            print(f"User with ID {user_id} not found")
    
    else:
        # Show recent payments
        print("\nRecent Test Payments (Last 10):")
        print("-" * 80)
        
        recent_payments = PsychometricTestPayment.objects.all().order_by('-created')[:10]
        
        for test_payment in recent_payments:
            print(f"\nTest Payment ID: {test_payment.id}")
            print(f"User: {test_payment.user.email} (ID: {test_payment.user.id})")
            print(f"Test Type: {test_payment.get_test_type_display()}")
            print(f"Amount: ₹{test_payment.amount}")
            print(f"Status: {'✓ SUCCESS' if test_payment.is_success == choices.YesNoChoices.YES else '✗ FAILED/PENDING'}")
            print(f"Gateway Receipt: {test_payment.gateway_receipt}")
            print(f"Created: {test_payment.created}")
            
            # Check related payment
            payment = Payment.objects.filter(
                obj_id=test_payment.id,
                obj_type=choices.PaymentObjectType.PYSCHOMETRICTESTDETAIL
            ).first()
            
            if payment:
                print(f"  → Payment ID: {payment.id}, Status: {'✓ SUCCESS' if payment.is_success == choices.YesNoChoices.YES else '✗ FAILED/PENDING'}, Gateway: {payment.get_gateway_display()}")
                if payment.gateway_payment_id:
                    print(f"  → Gateway Payment ID: {payment.gateway_payment_id}")
            else:
                print(f"  → No Payment record found")
            print("-" * 80)
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if len(sys.argv) > 2:
            # Check specific test payment
            check_payment_status(test_id=int(sys.argv[2]))
        else:
            # Check user payments
            check_payment_status(user_id=int(sys.argv[1]))
    else:
        # Show recent payments
        check_payment_status()

