#!/usr/bin/env python3
"""
Email Test Script
Run this to verify your email configuration is working
"""

from app import app, mail
from flask_mail import Message as MailMessage

def test_email():
    print("=" * 60)
    print("Testing Email Configuration")
    print("=" * 60)
    print()
    
    # Check configuration
    print("Current Configuration:")
    print(f"  MAIL_SERVER: {app.config.get('MAIL_SERVER')}")
    print(f"  MAIL_PORT: {app.config.get('MAIL_PORT')}")
    print(f"  MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS')}")
    print(f"  MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
    print(f"  MAIL_PASSWORD: {'*' * 16 if app.config.get('MAIL_PASSWORD') else 'NOT SET'}")
    print()
    
    if not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'):
        print("❌ Email not configured!")
        print("Please set MAIL_USERNAME and MAIL_PASSWORD in your .env file")
        return
    
    # Send test email
    recipient = input("Enter email address to send test to (press Enter for sender): ").strip()
    if not recipient:
        recipient = app.config.get('MAIL_USERNAME')
    
    print()
    print(f"Sending test email to: {recipient}")
    print("Please wait...")
    print()
    
    try:
        with app.app_context():
            msg = MailMessage(
                subject="Daily Fitness - Email Test",
                recipients=[recipient],
                body="This is a test email from Daily Fitness.\n\nIf you received this, your email configuration is working correctly!",
                html="""
                <html>
                <body style="font-family: Arial, sans-serif; padding: 20px;">
                    <div style="max-width: 600px; margin: 0 auto; background: #f9f9f9; padding: 30px; border-radius: 10px;">
                        <h2 style="color: #667eea;">✅ Email Test Successful!</h2>
                        <p>This is a test email from <strong>Daily Fitness</strong>.</p>
                        <p>If you received this, your email configuration is working correctly!</p>
                        <hr style="border: 1px solid #e2e8f0; margin: 20px 0;">
                        <p style="color: #666; font-size: 12px;">
                            This is an automated test message. You can safely ignore or delete this email.
                        </p>
                    </div>
                </body>
                </html>
                """
            )
            mail.send(msg)
        
        print("=" * 60)
        print("✅ Email sent successfully!")
        print("=" * 60)
        print()
        print("Check your inbox (and spam folder) for the test email.")
        print()
        print("If you received it, your OTP system is ready to use!")
        print()
        
    except Exception as e:
        print("=" * 60)
        print("❌ Failed to send email")
        print("=" * 60)
        print()
        print(f"Error: {e}")
        print()
        print("Common issues:")
        print("1. App Password is incorrect - Generate a new one")
        print("2. 2FA is not enabled on Gmail")
        print("3. Network/firewall blocking SMTP")
        print("4. Spaces in password - Remove all spaces")
        print()

if __name__ == '__main__':
    try:
        test_email()
    except KeyboardInterrupt:
        print("\n\nTest cancelled.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
