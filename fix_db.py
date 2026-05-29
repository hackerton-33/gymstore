from app import app, db
from sqlalchemy import text
import traceback

with app.app_context():
    try:
        # Check if the column exists first by trying to select it
        try:
            db.session.execute(text("SELECT firestore_order_id FROM orders LIMIT 1"))
            print("Column 'firestore_order_id' already exists.")
        except Exception as e:
            # If it fails, the column likely doesn't exist
            print("Column not found, adding it...")
            db.session.rollback()
            db.session.execute(text("ALTER TABLE orders ADD COLUMN firestore_order_id VARCHAR(255) DEFAULT NULL;"))
            db.session.execute(text("CREATE INDEX ix_orders_firestore_order_id ON orders (firestore_order_id);"))
            db.session.commit()
            print("Column 'firestore_order_id' added successfully!")
    except Exception as e:
        print(f"Failed to alter table: {e}")
        traceback.print_exc()
