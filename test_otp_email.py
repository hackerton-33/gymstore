#!/usr/bin/env python3
"""
Quick OTP Email Test
Tests the actual OTP email function
"""

from app import app, db, User, _send_otp_email

def test_otp():
    print("=" * 60)
    print("Testing OTP Email Function")
    print("=" * 60)
    print()
    
    with app.app_context():
        # Find a test user
        user = User.query.filter_by(email='danielpenalosa1313@gmail.com').first()
        
        if not user:
            user = User.query.filter_by(email='danpnlsa013@gmail.com').first()
        
        if not user:
            print("❌ No user found with your email address")
            print("Please create an account first or update the email in this script")
            return
        
        print(f"Found user: {user.username} ({user.email})")
        print()
        
        # Generate test OTP
        test_otp = "123456"
        
        print(f"Sending test OTP: {test_otp}")
        print("Please wait...")
        print()
        
        # Send OTP
        _send_otp_email(user, test_otp)
        
        print()
        print("=" * 60)
        print("Check the console output above for:")
        print("  ✅ [EMAIL] ✅ OTP sent successfully")
        print("  ❌ [ERROR] ❌ Failed to send OTP email")
        print("=" * 60)
        print()
        print("If successful, check your email inbox!")
        print()

if __name__ == '__main__':
    try:
        test_otp()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
