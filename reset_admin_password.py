#!/usr/bin/env python3
"""Reset admin password to admin123"""

from app import app, db, User
from werkzeug.security import generate_password_hash

def reset_admin_password():
    with app.app_context():
        # Find admin user
        admin = User.query.filter_by(username='admin').first()
        
        if admin:
            # Reset password to admin123
            admin.password_hash = generate_password_hash('admin123')
            db.session.commit()
            print("✓ Admin password reset successfully!")
            print("Username: admin")
            print("Password: admin123")
        else:
            print("✗ Admin user not found!")
            print("Creating new admin user...")
            admin = User(
                username='admin',
                email='admin@gymstore.com',
                first_name='System',
                last_name='Administrator',
                role='admin',
                approval_status='approved',
                is_active=True,
                email_verified=True
            )
            admin.password_hash = generate_password_hash('admin123')
            db.session.add(admin)
            db.session.commit()
            print("✓ Admin user created!")
            print("Username: admin")
            print("Password: admin123")

if __name__ == '__main__':
    reset_admin_password()
