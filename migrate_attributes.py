#!/usr/bin/env python3
"""
Database Migration Script for Product Attributes
Run this script to add the new columns to your database
"""

from app import app, db
from sqlalchemy import text

def run_migration():
    """Run the database migration"""
    print("Starting Product Attributes Migration...")
    print("-" * 50)
    
    migrations = [
        # Products table
        "ALTER TABLE products ADD COLUMN has_size BOOLEAN DEFAULT FALSE",
        "ALTER TABLE products ADD COLUMN available_sizes TEXT",
        "ALTER TABLE products ADD COLUMN has_weight_options BOOLEAN DEFAULT FALSE",
        "ALTER TABLE products ADD COLUMN available_weights TEXT",
        
        # Order items table
        "ALTER TABLE order_items ADD COLUMN selected_size VARCHAR(20)",
        "ALTER TABLE order_items ADD COLUMN selected_weight VARCHAR(20)",
        
        # Cart table
        "ALTER TABLE cart ADD COLUMN selected_size VARCHAR(20)",
    ]
    
    with app.app_context():
        try:
            for i, migration in enumerate(migrations, 1):
                print(f"\n[{i}/{len(migrations)}] Running: {migration[:60]}...")
                try:
                    db.session.execute(text(migration))
                    db.session.commit()
                    print(f"✓ Success")
                except Exception as e:
                    if "Duplicate column name" in str(e) or "already exists" in str(e):
                        print(f"⚠ Column already exists, skipping...")
                        db.session.rollback()
                    else:
                        print(f"✗ Error: {e}")
                        db.session.rollback()
                        raise
            
            # Update cart unique constraint
            print(f"\n[{len(migrations)+1}] Updating cart unique constraint...")
            try:
                db.session.execute(text("ALTER TABLE cart DROP CONSTRAINT IF EXISTS unique_user_product"))
                db.session.execute(text("""
                    ALTER TABLE cart ADD CONSTRAINT unique_user_product 
                    UNIQUE (user_id, product_id, variant, selected_size, selected_weight)
                """))
                db.session.commit()
                print("✓ Success")
            except Exception as e:
                print(f"⚠ Constraint update: {e}")
                db.session.rollback()
            
            print("\n" + "=" * 50)
            print("✓ Migration completed successfully!")
            print("=" * 50)
            print("\nYou can now:")
            print("1. Add products with size/weight attributes")
            print("2. Buyers can select sizes/weights when purchasing")
            print("3. Attributes will be tracked in cart and orders")
            
        except Exception as e:
            print(f"\n✗ Migration failed: {e}")
            print("\nPlease check your database connection and try again.")
            return False
    
    return True

if __name__ == '__main__':
    print("""
╔════════════════════════════════════════════════════════╗
║   Product Attributes Migration Script                  ║
║   This will add size/weight columns to your database   ║
╚════════════════════════════════════════════════════════╝
    """)
    
    response = input("Do you want to proceed? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y']:
        success = run_migration()
        if success:
            print("\n✓ All done! Your database is ready for product attributes.")
        else:
            print("\n✗ Migration failed. Please check the errors above.")
    else:
        print("\nMigration cancelled.")
