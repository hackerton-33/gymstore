"""
Migration script to add featured_testimonials table
Run this script to create the database table for testimonials management
"""

import sqlite3
import os
from datetime import datetime

def run_migration():
    """Run the featured testimonials migration"""
    
    # Database path
    db_path = os.path.join('instance', 'gym_store.db')
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        print("Please ensure the database exists before running migration.")
        return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔄 Running featured testimonials migration...")
        
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='featured_testimonials'
        """)
        
        if cursor.fetchone():
            print("⚠️  Table 'featured_testimonials' already exists!")
            response = input("Do you want to recreate it? (yes/no): ").lower()
            if response != 'yes':
                print("Migration cancelled.")
                conn.close()
                return False
            
            # Drop existing table
            cursor.execute("DROP TABLE IF EXISTS featured_testimonials")
            print("🗑️  Dropped existing table")
        
        # Create featured_testimonials table
        cursor.execute("""
            CREATE TABLE featured_testimonials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id INTEGER UNIQUE NOT NULL,
                display_order INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER NOT NULL,
                FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        """)
        print("✅ Created 'featured_testimonials' table")
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX idx_featured_testimonials_display_order 
            ON featured_testimonials(display_order)
        """)
        print("✅ Created index on display_order")
        
        cursor.execute("""
            CREATE INDEX idx_featured_testimonials_is_active 
            ON featured_testimonials(is_active)
        """)
        print("✅ Created index on is_active")
        
        # Check for existing 5-star reviews
        cursor.execute("""
            SELECT COUNT(*) FROM reviews WHERE rating = 5
        """)
        review_count = cursor.fetchone()[0]
        
        if review_count > 0:
            print(f"\n📊 Found {review_count} five-star reviews available for featuring")
            print("💡 Admins can now feature these reviews from /admin/testimonials")
        else:
            print("\n📊 No five-star reviews found yet")
            print("💡 Encourage customers to leave reviews!")
        
        # Commit changes
        conn.commit()
        conn.close()
        
        print("\n✅ Migration completed successfully!")
        print("\n🎯 Next steps:")
        print("1. Restart your Flask application")
        print("2. Login as admin")
        print("3. Go to /admin/testimonials")
        print("4. Start featuring customer reviews!")
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        if conn:
            conn.close()
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("Featured Testimonials Migration")
    print("=" * 60)
    print()
    
    success = run_migration()
    
    if success:
        print("\n" + "=" * 60)
        print("Migration completed! 🎉")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("Migration failed! ❌")
        print("=" * 60)
