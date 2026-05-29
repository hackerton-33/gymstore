"""
Verify Products - Check Firestore Products
This script lists all products in Firestore to verify sync
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from firestore_helper import get_products_firestore, get_firestore_client

def verify_products():
    """Check products in Firestore"""
    
    with app.app_context():
        print("="*70)
        print("PRODUCT VERIFICATION - FIRESTORE")
        print("="*70)
        print("Checking products in Firestore database...")
        print("="*70)
        
        try:
            # Get Firestore client
            db = get_firestore_client()
            
            # Get all products
            products_ref = db.collection('products')
            products = list(products_ref.stream())
            
            print(f"\n📦 Total Products in Firestore: {len(products)}")
            print("="*70)
            
            if len(products) == 0:
                print("\n⚠️  NO PRODUCTS FOUND IN FIRESTORE!")
                print("\nPossible reasons:")
                print("1. No products added on mobile app yet")
                print("2. Products are in SQL database (not synced)")
                print("3. Firestore collection name is different")
                print("\nSolution:")
                print("- Add products via mobile app first")
                print("- Or run: python migrate_products_to_firestore.py")
                return
            
            # Display products
            print("\n📋 PRODUCT LIST:")
            print("="*70)
            
            for i, product_doc in enumerate(products, 1):
                product = product_doc.to_dict()
                product_id = product_doc.id
                
                name = product.get('name', 'N/A')
                price = product.get('price', 0)
                stock = product.get('stockQuantity', 0)
                is_active = product.get('isActive', False)
                approval = product.get('approvalStatus', 'N/A')
                seller_id = product.get('sellerId', 'N/A')
                category = product.get('category', 'N/A')
                
                print(f"\n{i}. {name}")
                print(f"   ID: {product_id}")
                print(f"   Price: ₱{price}")
                print(f"   Stock: {stock}")
                print(f"   Active: {is_active}")
                print(f"   Approval: {approval}")
                print(f"   Category: {category}")
                print(f"   Seller ID: {seller_id}")
                print("-"*70)
            
            # Statistics
            print("\n📊 STATISTICS:")
            print("="*70)
            
            active_products = [p for p in products if p.to_dict().get('isActive', False)]
            approved_products = [p for p in products if p.to_dict().get('approvalStatus') == 'approved']
            in_stock = [p for p in products if p.to_dict().get('stockQuantity', 0) > 0]
            
            print(f"Total Products: {len(products)}")
            print(f"Active Products: {len(active_products)}")
            print(f"Approved Products: {len(approved_products)}")
            print(f"In Stock: {len(in_stock)}")
            print(f"Out of Stock: {len(products) - len(in_stock)}")
            
            # Categories
            categories = {}
            for product_doc in products:
                product = product_doc.to_dict()
                cat = product.get('category', 'Uncategorized')
                categories[cat] = categories.get(cat, 0) + 1
            
            print(f"\n📂 CATEGORIES:")
            for cat, count in categories.items():
                print(f"   {cat}: {count} products")
            
            # What will show on website
            print("\n🌐 WEBSITE DISPLAY:")
            print("="*70)
            
            # Get products that will show on website (active + approved)
            website_products = get_products_firestore({
                'isActive': True,
                'approvalStatus': 'approved'
            })
            
            print(f"Products visible on website: {len(website_products)}")
            
            if len(website_products) == 0:
                print("\n⚠️  NO PRODUCTS WILL SHOW ON WEBSITE!")
                print("\nReason: No products are both 'active' AND 'approved'")
                print("\nTo fix:")
                print("1. Make sure products are approved by admin")
                print("2. Make sure products are set as active")
            else:
                print("\n✅ These products will show on website:")
                for i, product in enumerate(website_products, 1):
                    print(f"   {i}. {product.get('name')} - ₱{product.get('price')}")
            
            print("\n" + "="*70)
            print("✅ VERIFICATION COMPLETE!")
            print("="*70)
            
            # Comparison instructions
            print("\n📱 TO VERIFY SYNC:")
            print("="*70)
            print("1. Open mobile app")
            print("2. Go to Shop/Products")
            print("3. Count the products")
            print(f"4. Should see {len(website_products)} products")
            print("5. Open website: http://localhost:5000/buyer/shop")
            print(f"6. Should see the same {len(website_products)} products")
            print("7. Compare product names and prices")
            print("\n✅ If they match, sync is working!")
            print("❌ If they don't match, there's an issue")
            
        except Exception as e:
            print(f"\n❌ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    verify_products()
    print("\n")
    input("Press Enter to exit...")
