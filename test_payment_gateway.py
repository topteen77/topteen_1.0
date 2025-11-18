#!/usr/bin/env python
"""
Test script to verify payment gateway configuration and fallback logic.
Run this script to test the payment gateway functionality.
"""
import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'topteens.settings')
django.setup()

from django.conf import settings
from core import choices
from core.utils import get_preferred_payment_gateway, is_gateway_available

def test_payment_gateway_configuration():
    """Test payment gateway configuration"""
    print("=" * 60)
    print("Payment Gateway Configuration Test")
    print("=" * 60)
    
    # Test 1: Check environment mode
    print("\n1. Checking Environment Mode:")
    razorpay_env = getattr(settings, 'RAZORPAY_ENVIRONMENT', 'sandbox')
    eazypay_env = getattr(settings, 'ICICI_EAZYPAY_ENVIRONMENT', 'sandbox')
    print(f"   RAZORPAY_ENVIRONMENT: {razorpay_env}")
    print(f"   ICICI_EAZYPAY_ENVIRONMENT: {eazypay_env}")
    
    # Test 2: Check environment variables
    print("\n2. Checking Environment Variables:")
    print(f"   PAYMENT_GATEWAY_PREFERENCE: {getattr(settings, 'PAYMENT_GATEWAY_PREFERENCE', 'Not set')}")
    
    # Razorpay keys
    razorpay_key = getattr(settings, 'RAZORPAY_KEY', '')
    razorpay_secret = getattr(settings, 'RAZORPAY_SECRET', '')
    print(f"   RAZORPAY_KEY: {'Set' if razorpay_key else 'Not set'}")
    if razorpay_key:
        key_type = "Production" if razorpay_key.startswith('rzp_live_') else "Sandbox/Test"
        print(f"     Key Type: {key_type} ({'rzp_live_' if razorpay_key.startswith('rzp_live_') else 'rzp_test_'}*)")
    print(f"   RAZORPAY_SECRET: {'Set' if razorpay_secret else 'Not set'}")
    
    # ICICI Eazypay
    print(f"   ICICI_EAZYPAY_MERCHANT_ID: {'Set' if getattr(settings, 'ICICI_EAZYPAY_MERCHANT_ID', '') else 'Not set'}")
    print(f"   ICICI_EAZYPAY_ENCRYPTION_KEY: {'Set' if getattr(settings, 'ICICI_EAZYPAY_ENCRYPTION_KEY', '') else 'Not set'}")
    print(f"   ICICI_EAZYPAY_BASE_URL: {getattr(settings, 'ICICI_EAZYPAY_DEFAULT_BASE_URL', 'Not set')}")
    
    # Test 3: Check gateway availability
    print("\n3. Checking Gateway Availability:")
    razorpay_available = is_gateway_available(choices.GatewayChoices.RAZORPAY)
    eazypay_available = is_gateway_available(choices.GatewayChoices.ICICIEAZYPAY)
    print(f"   Razorpay Available: {razorpay_available}")
    print(f"   ICICI Eazypay Available: {eazypay_available}")
    
    # Test 4: Test preferred gateway selection
    print("\n4. Testing Preferred Gateway Selection:")
    preferred_gateway = get_preferred_payment_gateway()
    gateway_name = dict(choices.GatewayChoices.CHOICES).get(preferred_gateway, 'Unknown')
    print(f"   Preferred Gateway: {gateway_name} (ID: {preferred_gateway})")
    
    # Test 5: Test fallback logic
    print("\n5. Testing Fallback Logic:")
    if preferred_gateway == choices.GatewayChoices.ICICIEAZYPAY:
        if eazypay_available:
            print("   ✓ ICICI Eazypay is preferred and available")
        else:
            print("   ⚠ ICICI Eazypay is preferred but not configured - should fallback to Razorpay")
            if razorpay_available:
                print("   ✓ Razorpay is available as fallback")
            else:
                print("   ✗ Razorpay is also not available!")
    elif preferred_gateway == choices.GatewayChoices.RAZORPAY:
        print("   ✓ Razorpay is selected")
        if not eazypay_available:
            print("   ℹ ICICI Eazypay is not configured (expected if preference is Razorpay)")
    
    # Test 6: Environment Mode Verification
    print("\n6. Environment Mode Verification:")
    print(f"   Razorpay Mode: {razorpay_env.upper()}")
    if razorpay_env == 'sandbox':
        print("     ✓ Using Sandbox/Test keys (rzp_test_*)")
    elif razorpay_env == 'production':
        print("     ⚠ Using Production keys (rzp_live_*)")
        if not razorpay_key.startswith('rzp_live_'):
            print("     ⚠ WARNING: Production mode selected but test key detected!")
    
    print(f"   ICICI Eazypay Mode: {eazypay_env.upper()}")
    if eazypay_env == 'sandbox':
        print("     ✓ Using Sandbox/Test configuration")
    elif eazypay_env == 'production':
        print("     ⚠ Using Production configuration")
    
    # Test 7: Configuration summary
    print("\n7. Configuration Summary:")
    print(f"   Gateway Preference Setting: {getattr(settings, 'PAYMENT_GATEWAY_PREFERENCE', 'Not set')}")
    print(f"   Expected Behavior:")
    if getattr(settings, 'PAYMENT_GATEWAY_PREFERENCE', 1) == 1:
        print("     - Try ICICI Eazypay first")
        print("     - Fallback to Razorpay if ICICI Eazypay is not configured")
    else:
        print("     - Use Razorpay")
    print(f"   Environment Modes:")
    print(f"     - Razorpay: {razorpay_env}")
    print(f"     - ICICI Eazypay: {eazypay_env}")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)
    
    return {
        'preferred_gateway': preferred_gateway,
        'razorpay_available': razorpay_available,
        'eazypay_available': eazypay_available,
    }

if __name__ == '__main__':
    try:
        result = test_payment_gateway_configuration()
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

