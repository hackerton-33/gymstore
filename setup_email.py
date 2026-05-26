#!/usr/bin/env python3
"""
Email Configuration Setup Script
Run this to configure email settings for OTP system
"""

import os
from pathlib import Path

def setup_email():
    print("=" * 60)
    print("Daily Fitness - Email Configuration Setup")
    print("=" * 60)
    print()
    
    # Check if .env exists
    env_path = Path('.env')
    env_example_path = Path('.env.example')
    
    if not env_path.exists() and env_example_path.exists():
        print("Creating .env file from .env.example...")
        with open(env_example_path, 'r') as f:
            content = f.read()
        with open(env_path, 'w') as f:
            f.write(content)
        print("✓ .env file created")
        print()
    
    print("Please provide your email configuration:")
    print()
    print("For Gmail:")
    print("1. Enable 2-Factor Authentication")
    print("2. Generate App Password at: https://myaccount.google.com/apppasswords")
    print()
    
    # Get email configuration
    mail_server = input("SMTP Server (default: smtp.gmail.com): ").strip() or "smtp.gmail.com"
    mail_port = input("SMTP Port (default: 587): ").strip() or "587"
    mail_username = input("Email Address: ").strip()
    mail_password = input("App Password (16 characters): ").strip()
    
    if not mail_username or not mail_password:
        print("\n❌ Email and password are required!")
        return
    
    # Read current .env content
    env_content = []
    if env_path.exists():
        with open(env_path, 'r') as f:
            env_content = f.readlines()
    
    # Remove existing email config
    new_content = []
    skip_next = False
    for line in env_content:
        if line.startswith('MAIL_'):
            continue
        if '# Email Configuration' in line:
            skip_next = True
            continue
        if skip_next and line.strip() == '':
            skip_next = False
            continue
        new_content.append(line)
    
    # Add new email configuration
    email_config = f"""
# Email Configuration (for OTP and notifications)
MAIL_SERVER={mail_server}
MAIL_PORT={mail_port}
MAIL_USE_TLS=True
MAIL_USERNAME={mail_username}
MAIL_PASSWORD={mail_password}
MAIL_DEFAULT_SENDER={mail_username}
"""
    
    # Write updated .env
    with open(env_path, 'w') as f:
        f.write(''.join(new_content))
        f.write(email_config)
    
    print()
    print("=" * 60)
    print("✓ Email configuration saved to .env")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Restart your Flask application")
    print("2. Test the forgot password feature")
    print("3. Check your email for the OTP code")
    print()
    print("If you don't receive emails, check:")
    print("- Your spam/junk folder")
    print("- Console output for error messages")
    print("- That 2FA is enabled and App Password is correct")
    print()

if __name__ == '__main__':
    try:
        setup_email()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
