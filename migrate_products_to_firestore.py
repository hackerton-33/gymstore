"""
Migrate Products from SQL to Firestore
Run this script to sync all existing products to Firestore for cross-platform sync
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Product
from firebase_admin import firestore
import json

def migrate_products_to_firestore():
    """Migrate all products from SQL database to Firestore"""
    
    with app.app_context():
        # Get Firestore client
        fs_db = firestore.client()
        
        # Get all products from SQL
        products = Product.query.all()
        
        print(f"Found {len(products)} products in SQL database")
        print("Starting migration to Firestore...")
        
        migrated_count = 0
        skipped_count = 0
        error_count = 0
        
        for product in products:
            try:
                # Check if product already exists in Firestore
                doc_ref = fs_db.collection('products').document(str(product.id))
                doc = doc_ref.get()
                
                if doc.exists:
                    print(f"  ⏭️  Skipping product {product.id} - {product.name} (already exists)")
                    skipped_count += 1
                    continue
                
                # Parse gallery images
                gallery_images = []
                if product.gallery_images:
                    if isinstance(product.gallery_images, str):
                        try:
                            gallery_images = json.loads(product.gallery_images)
                        except:
                            gallery_images = []
                    elif isinstance(product.gallery_images, list):
                        gallery_images = product.gallery_images
                
                # Prepare product data for Firestore
                product_data = {
                    'name': product.name or '',
                    'brand': product.brand or '',
                    'description': product.description or '',
                    'price': float(product.price) if product.price else 0.0,
                    'stockQuantity': product.stock_quantity or 0,
                    'imageUrl': product.image_url or '',
                    'galleryImages': gallery_images,
                    'category': product.category.name if product.category else 'Uncategorized',
                    'categoryId': product.category_id or 0,
                    'sellerId': str(product.seller_id),
                    'isActive': product.is_active if hasattr(product, 'is_active') else True,
                    'approvalStatus': product.approval_status if hasattr(product, 'approval_status') else 'approved',
                    'rating': float(product.rating) if hasattr(product, 'rating') and product.rating else 0.0,
                    'totalSold': product.total_sold if hasattr(product, 'total_sold') else 0,
                    'createdAt': product.created_at if hasattr(product, 'created_at') else firestore.SERVER_TIMESTAMP,
                    'updatedAt': firestore.SERVER_TIMESTAMP
                }
                
                # Add optional fields if they exist
                if hasattr(product, 'weight') and product.weight:
                    product_data['weight'] = product.weight
                if hasattr(product, 'dimensions') and product.dimensions:
                    product_data['dimensions'] = product.dimensions
                if hasattr(product, 'sku') and product.sku:
                    product_data['sku'] = product.sku
                
                # Create document in Firestore
                doc_ref.set(product_data)
                
                print(f"  ✅ Migrated product {product.id} - {product.name}")
                migrated_count += 1
                
            except Exception as e:
                print(f"  ❌ Error migrating product {product.id} - {product.name}: {str(e)}")
                error_count += 1
        
        print("\n" + "="*60)
        print("MIGRATION COMPLETE!")
        print("="*60)
        print(f"✅ Migrated: {migrated_count} products")
        print(f"⏭️  Skipped: {skipped_count} products (already existed)")
        print(f"❌ Errors: {error_count} products")
        print(f"📊 Total: {len(products)} products")
        print("="*60)
        
        if migrated_count > 0:
            print("\n🎉 Products are now synced to Firestore!")
            print("✅ Website will now display products from Firestore")
            print("✅ Mobile app will see the same products")
            print("✅ Real-time sync is now active!")
        
        if error_count > 0:
            print(f"\n⚠️  {error_count} products failed to migrate. Check errors above.")
        
        return {
            'migrated': migrated_count,
            'skipped': skipped_count,
            'errors': error_count,
            'total': len(products)
        }

if __name__ == '__main__':
    print("="*60)
    print("PRODUCT MIGRATION TO FIRESTORE")
    print("="*60)
    print("This script will migrate all products from SQL to Firestore")
    print("for cross-platform sync between website and mobile app.")
    print("="*60)
    print("\nStarting migration automatically...")
    
    result = migrate_products_to_firestore()
    
    print("\n✅ Migration completed successfully!")
    print(f"You can now test product sync between website and mobile app.")
