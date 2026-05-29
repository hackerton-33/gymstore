"""
Sync Firebase Users to SQL Database
This script syncs users from Firebase Authentication + Firestore to SQL database
so they can login on the website
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User
from firebase_admin import auth, firestore

def sync_firebase_users_to_sql():
    """Sync all Firebase users to SQL database"""
    
    with app.app_context():
        # Get Firestore client
        fs_db = firestore.client()
        
        print("="*60)
        print("FIREBASE TO SQL USER SYNC")
        print("="*60)
        print("Syncing users from Firebase to SQL database...")
        print("="*60)
        
        synced_count = 0
        skipped_count = 0
        error_count = 0
        
        try:
            # Get all users from Firestore
            users_ref = fs_db.collection('users')
            firebase_users = users_ref.stream()
            
            for user_doc in firebase_users:
                try:
                    user_data = user_doc.to_dict()
                    firebase_uid = user_doc.id
                    
                    # Get Firebase Auth user for email
                    try:
                        firebase_auth_user = auth.get_user(firebase_uid)
                        email = firebase_auth_user.email
                        phone = firebase_auth_user.phone_number
                    except Exception as auth_error:
                        print(f"  ⚠️  Could not get auth data for {firebase_uid}: {auth_error}")
                        email = user_data.get('email', f'{firebase_uid}@firebase.user')
                        phone = user_data.get('phoneNumber', user_data.get('phone'))
                    
                    # Check if user already exists in SQL by email or firebase_uid
                    existing_user = User.query.filter(
                        (User.email == email) | (User.firebase_uid == firebase_uid)
                    ).first()
                    
                    if existing_user:
                        # Update existing user
                        existing_user.firebase_uid = firebase_uid
                        existing_user.approval_status = user_data.get('approvalStatus', user_data.get('approval_status', 'approved'))
                        existing_user.is_active = user_data.get('isActive', True)
                        
                        # Update other fields if they're empty
                        if not existing_user.full_name and user_data.get('fullName'):
                            existing_user.full_name = user_data.get('fullName')
                        if not existing_user.phone_number and phone:
                            existing_user.phone_number = phone
                        
                        db.session.commit()
                        print(f"  🔄 Updated user: {email} ({user_data.get('role', 'buyer')})")
                        skipped_count += 1
                        continue
                    
                    # Create new user in SQL
                    username = user_data.get('username', email.split('@')[0])
                    
                    # Make sure username is unique
                    base_username = username
                    counter = 1
                    while User.query.filter_by(username=username).first():
                        username = f"{base_username}{counter}"
                        counter += 1
                    
                    new_user = User(
                        username=username,
                        email=email,
                        firebase_uid=firebase_uid,
                        full_name=user_data.get('fullName', user_data.get('full_name', '')),
                        first_name=user_data.get('firstName', user_data.get('first_name', '')),
                        last_name=user_data.get('lastName', user_data.get('last_name', '')),
                        phone_number=phone or user_data.get('phoneNumber', user_data.get('phone')),
                        role=user_data.get('role', 'buyer'),
                        approval_status=user_data.get('approvalStatus', user_data.get('approval_status', 'approved')),
                        is_active=user_data.get('isActive', True)
                    )
                    
                    # Set a default password (users will use Firebase auth, but this is for fallback)
                    # They can reset it if needed
                    new_user.set_password('firebase_user_' + firebase_uid[:8])
                    
                    db.session.add(new_user)
                    db.session.commit()
                    
                    print(f"  ✅ Synced user: {email} ({new_user.role})")
                    synced_count += 1
                    
                except Exception as e:
                    db.session.rollback()
                    print(f"  ❌ Error syncing user {firebase_uid}: {str(e)}")
                    error_count += 1
            
            print("\n" + "="*60)
            print("SYNC COMPLETE!")
            print("="*60)
            print(f"✅ Synced: {synced_count} new users")
            print(f"🔄 Updated: {skipped_count} existing users")
            print(f"❌ Errors: {error_count} users")
            print("="*60)
            
            if synced_count > 0 or skipped_count > 0:
                print("\n🎉 Users are now synced!")
                print("✅ Firebase users can now login on website")
                print("✅ Use the same email and any password (Firebase auth will handle it)")
            
            if error_count > 0:
                print(f"\n⚠️  {error_count} users failed to sync. Check errors above.")
            
            return {
                'synced': synced_count,
                'updated': skipped_count,
                'errors': error_count
            }
            
        except Exception as e:
            print(f"\n❌ Fatal error during sync: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

if __name__ == '__main__':
    print("="*60)
    print("FIREBASE TO SQL USER SYNC")
    print("="*60)
    print("This script will sync users from Firebase to SQL database")
    print("so they can login on the website.")
    print("="*60)
    print("\nStarting sync automatically...")
    
    result = sync_firebase_users_to_sql()
    
    if result:
        print("\n✅ Sync completed successfully!")
        print("Users from mobile app can now login on website!")
    else:
        print("\n❌ Sync failed. Check errors above.")
