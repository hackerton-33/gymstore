#!/usr/bin/env python3
"""
Configuration Check Script
Verify that environment variables are loaded correctly
"""

from app import app
import os

print("=" * 60)
print("Configuration Check")
print("=" * 60)
print()

print("Environment Variables (.env file):")
print(f"  MAIL_SERVER: {os.getenv('MAIL_SERVER')}")
print(f"  MAIL_PORT: {os.getenv('MAIL_PORT')}")
print(f"  MAIL_USE_TLS: {os.getenv('MAIL_USE_TLS')}")
print(f"  MAIL_USERNAME: {os.getenv('MAIL_USERNAME')}")
print(f"  MAIL_PASSWORD: {'*' * 16 if os.getenv('MAIL_PASSWORD') else 'NOT SET'}")
print()

print("Flask App Configuration:")
print(f"  MAIL_SERVER: {app.config.get('MAIL_SERVER')}")
print(f"  MAIL_PORT: {app.config.get('MAIL_PORT')}")
print(f"  MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS')}")
print(f"  MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
print(f"  MAIL_PASSWORD: {'*' * 16 if app.config.get('MAIL_PASSWORD') else 'NOT SET'}")
print()

if not app.config.get('MAIL_USERNAME'):
    print("❌ MAIL_USERNAME is not set!")
    print()
    print("Possible issues:")
    print("1. .env file doesn't exist")
    print("2. .env file is not in the correct location (should be in Gym/ folder)")
    print("3. Flask app needs to be restarted")
    print()
elif not app.config.get('MAIL_PASSWORD'):
    print("❌ MAIL_PASSWORD is not set!")
    print()
    print("Please set MAIL_PASSWORD in your .env file")
    print()
else:
    print("✅ Email configuration looks good!")
    print()
    print("If emails still don't work:")
    print("1. Restart your Flask application")
    print("2. Check the console output when you try to send OTP")
    print("3. Look for error messages")
    print()
