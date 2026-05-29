"""
Add firebase_uid column to users table
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db

def add_firebase_uid_column():
    """Add firebase_uid column to users table"""
    
    with app.app_context():
        try:
            # Try to add the column
            with db.engine.connect() as conn:
                # Check if column already exists
                result = conn.execute(db.text("PRAGMA table_info(users)"))
                columns = [row[1] for row in result]
                
                if 'firebase_uid' in columns:
                    print("✅ firebase_uid column already exists!")
                    return True
                
                # Add the column
                conn.execute(db.text("ALTER TABLE users ADD COLUMN firebase_uid VARCHAR(255)"))
                conn.commit()
                
                print("✅ Successfully added firebase_uid column to users table!")
                return True
                
        except Exception as e:
            print(f"❌ Error adding column: {e}")
            return False

if __name__ == '__main__':
    print("="*60)
    print("ADD FIREBASE_UID COLUMN TO USERS TABLE")
    print("="*60)
    
    if add_firebase_uid_column():
        print("\n✅ Migration completed successfully!")
        print("You can now run the user sync script.")
    else:
        print("\n❌ Migration failed.")
