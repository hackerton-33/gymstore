"""
Firestore Helper Module
Provides utility functions for Firestore operations
"""
from firebase_admin import firestore
from datetime import datetime
from typing import Dict, List, Optional, Any

def get_firestore_client():
    """Get Firestore client instance"""
    return firestore.client()

# ==================== CART OPERATIONS ====================

def add_to_cart_firestore(user_id: str, product_id: str, quantity: int, 
                          product_name: str, product_image: str, price: float,
                          variant: Optional[str] = None, selected_weight: Optional[str] = None,
                          seller_id: Optional[str] = None, max_stock: int = 0) -> Dict:
    """Add item to cart in Firestore"""
    db = get_firestore_client()
    cart_ref = db.collection('carts').document(user_id).collection('items')
    
    # Check if item already exists
    query = cart_ref.where('productId', '==', product_id)
    if variant:
        query = query.where('variant', '==', variant)
    if selected_weight:
        query = query.where('selectedWeight', '==', selected_weight)
    
    existing = list(query.stream())
    
    if existing:
        # Update quantity
        doc = existing[0]
        current_qty = doc.to_dict().get('quantity', 0)
        new_qty = current_qty + quantity
        
        if new_qty > max_stock:
            raise ValueError(f'Cannot add more than available stock ({max_stock} available)')
        
        doc.reference.update({
            'quantity': new_qty,
            'maxStock': max_stock,
            'updatedAt': firestore.SERVER_TIMESTAMP
        })
        return {'success': True, 'message': 'Cart updated', 'item_id': doc.id}
    else:
        # Add new item
        if quantity > max_stock:
            raise ValueError(f'Cannot add more than available stock ({max_stock} available)')
        
        cart_item = {
            'productId': product_id,
            'productName': product_name,
            'productImage': product_image,
            'price': price,
            'quantity': quantity,
            'maxStock': max_stock,
            'variant': variant,
            'selectedWeight': selected_weight,
            'sellerId': seller_id,
            'addedAt': firestore.SERVER_TIMESTAMP,
            'updatedAt': firestore.SERVER_TIMESTAMP
        }
        
        doc_ref = cart_ref.add(cart_item)
        return {'success': True, 'message': 'Added to cart', 'item_id': doc_ref[1].id}

def get_cart_items_firestore(user_id: str) -> List[Dict]:
    """Get all cart items for a user"""
    db = get_firestore_client()
    cart_ref = db.collection('carts').document(user_id).collection('items')
    items = cart_ref.order_by('addedAt', direction=firestore.Query.DESCENDING).stream()
    
    cart_items = []
    for item in items:
        data = item.to_dict()
        data['id'] = item.id
        cart_items.append(data)
    
    return cart_items

def update_cart_quantity_firestore(user_id: str, item_id: str, quantity: int) -> Dict:
    """Update cart item quantity"""
    db = get_firestore_client()
    item_ref = db.collection('carts').document(user_id).collection('items').document(item_id)
    
    if quantity <= 0:
        item_ref.delete()
        return {'success': True, 'message': 'Item removed'}
    
    item_ref.update({
        'quantity': quantity,
        'updatedAt': firestore.SERVER_TIMESTAMP
    })
    return {'success': True, 'message': 'Quantity updated'}

def remove_from_cart_firestore(user_id: str, item_id: str) -> Dict:
    """Remove item from cart"""
    db = get_firestore_client()
    db.collection('carts').document(user_id).collection('items').document(item_id).delete()
    return {'success': True, 'message': 'Item removed'}

def clear_cart_firestore(user_id: str) -> Dict:
    """Clear all items from cart"""
    db = get_firestore_client()
    cart_ref = db.collection('carts').document(user_id).collection('items')
    
    batch = db.batch()
    for item in cart_ref.stream():
        batch.delete(item.reference)
    
    batch.commit()
    return {'success': True, 'message': 'Cart cleared'}

def get_cart_count_firestore(user_id: str) -> int:
    """Get total item count in cart"""
    items = get_cart_items_firestore(user_id)
    return sum(item.get('quantity', 0) for item in items)

def delete_cart_items_by_product_firestore(product_id: str) -> Dict:
    """Delete all cart items for a specific product across all users"""
    db = get_firestore_client()
    
    # Get all user carts
    carts_ref = db.collection('carts')
    carts = carts_ref.stream()
    
    deleted_count = 0
    for cart in carts:
        # Get items in this user's cart
        items_ref = cart.reference.collection('items')
        items = items_ref.where('productId', '==', product_id).stream()
        
        # Delete matching items
        for item in items:
            item.reference.delete()
            deleted_count += 1
    
    return {'success': True, 'message': f'Deleted {deleted_count} cart items', 'count': deleted_count}

# ==================== WISHLIST OPERATIONS ====================

def add_to_wishlist_firestore(user_id: str, product_id: str, product_name: str,
                               product_image: str, price: float) -> Dict:
    """Add item to wishlist"""
    db = get_firestore_client()
    wishlist_ref = db.collection('wishlist')
    
    # Check if already in wishlist
    existing = wishlist_ref.where('userId', '==', user_id).where('productId', '==', product_id).stream()
    if list(existing):
        return {'success': False, 'message': 'Already in wishlist'}
    
    wishlist_item = {
        'userId': user_id,
        'productId': product_id,
        'productName': product_name,
        'productImage': product_image,
        'price': price,
        'addedAt': firestore.SERVER_TIMESTAMP
    }
    
    wishlist_ref.add(wishlist_item)
    return {'success': True, 'message': 'Added to wishlist'}

def get_wishlist_items_firestore(user_id: str) -> List[Dict]:
    """Get all wishlist items for a user"""
    db = get_firestore_client()
    items = db.collection('wishlist').where('userId', '==', user_id).order_by('addedAt', direction=firestore.Query.DESCENDING).stream()
    
    wishlist_items = []
    for item in items:
        data = item.to_dict()
        data['id'] = item.id
        wishlist_items.append(data)
    
    return wishlist_items

def remove_from_wishlist_firestore(user_id: str, product_id: str) -> Dict:
    """Remove item from wishlist"""
    db = get_firestore_client()
    items = db.collection('wishlist').where('userId', '==', user_id).where('productId', '==', product_id).stream()
    
    for item in items:
        item.reference.delete()
    
    return {'success': True, 'message': 'Removed from wishlist'}

def is_in_wishlist_firestore(user_id: str, product_id: str) -> bool:
    """Check if product is in wishlist"""
    db = get_firestore_client()
    items = db.collection('wishlist').where('userId', '==', user_id).where('productId', '==', product_id).limit(1).stream()
    return len(list(items)) > 0

def delete_wishlist_items_by_product_firestore(product_id: str) -> Dict:
    """Delete all wishlist items for a specific product across all users"""
    db = get_firestore_client()
    
    # Get all wishlist items for this product
    items = db.collection('wishlist').where('productId', '==', product_id).stream()
    
    deleted_count = 0
    for item in items:
        item.reference.delete()
        deleted_count += 1
    
    return {'success': True, 'message': f'Deleted {deleted_count} wishlist items', 'count': deleted_count}

# ==================== ORDER OPERATIONS ====================

def create_order_firestore(order_data: Dict) -> str:
    """Create order in Firestore"""
    db = get_firestore_client()
    order_data['createdAt'] = firestore.SERVER_TIMESTAMP
    order_data['updatedAt'] = firestore.SERVER_TIMESTAMP
    
    doc_ref = db.collection('orders').add(order_data)
    return doc_ref[1].id

def get_orders_firestore(user_id: str, role: str = 'buyer') -> List[Dict]:
    """Get orders for a user based on role"""
    db = get_firestore_client()
    orders_ref = db.collection('orders')
    
    if role == 'buyer':
        query = orders_ref.where('buyerId', '==', user_id)
    elif role == 'seller':
        query = orders_ref.where('sellerId', '==', user_id)
    elif role == 'rider':
        query = orders_ref.where('riderId', '==', user_id)
    else:
        query = orders_ref
    
    orders = query.order_by('createdAt', direction=firestore.Query.DESCENDING).stream()
    
    order_list = []
    for order in orders:
        data = order.to_dict()
        data['id'] = order.id
        order_list.append(data)
    
    return order_list

def get_order_firestore(order_id: str) -> Optional[Dict]:
    """Get single order by ID"""
    db = get_firestore_client()
    doc = db.collection('orders').document(order_id).get()
    
    if doc.exists:
        data = doc.to_dict()
        data['id'] = doc.id
        return data
    return None

def update_order_status_firestore(order_id: str, status: str, updated_by: str) -> Dict:
    """Update order status"""
    db = get_firestore_client()
    db.collection('orders').document(order_id).update({
        'status': status,
        'updatedAt': firestore.SERVER_TIMESTAMP,
        'updatedBy': updated_by
    })
    return {'success': True, 'message': 'Order status updated'}

# ==================== PRODUCT OPERATIONS ====================

def get_products_firestore(filters: Optional[Dict] = None, sort_by: str = 'name', 
                          limit: Optional[int] = None, offset: int = 0) -> List[Dict]:
    """Get products with optional filters, sorting, and pagination"""
    db = get_firestore_client()
    query = db.collection('products')
    
    # Apply filters
    if filters:
        if 'isActive' in filters:
            query = query.where('isActive', '==', filters['isActive'])
        if 'approvalStatus' in filters:
            query = query.where('approvalStatus', '==', filters['approvalStatus'])
        if 'category' in filters:
            query = query.where('category', '==', filters['category'])
        if 'categoryId' in filters:
            query = query.where('categoryId', '==', filters['categoryId'])
        if 'sellerId' in filters:
            query = query.where('sellerId', '==', filters['sellerId'])
        if 'maxPrice' in filters:
            query = query.where('price', '<=', filters['maxPrice'])
        if 'inStockOnly' in filters and filters['inStockOnly']:
            query = query.where('stockQuantity', '>', 0)
    
    # Apply sorting
    if sort_by == 'latest':
        query = query.order_by('createdAt', direction=firestore.Query.DESCENDING)
    elif sort_by == 'price_low':
        query = query.order_by('price', direction=firestore.Query.ASCENDING)
    elif sort_by == 'price_high':
        query = query.order_by('price', direction=firestore.Query.DESCENDING)
    elif sort_by == 'top_sales':
        query = query.order_by('totalSold', direction=firestore.Query.DESCENDING)
    elif sort_by == 'name':
        query = query.order_by('name', direction=firestore.Query.ASCENDING)
    
    # Apply pagination
    if offset > 0:
        # Get all results up to offset + limit
        all_results = list(query.stream())
        products = all_results[offset:offset + limit] if limit else all_results[offset:]
    else:
        if limit:
            query = query.limit(limit)
        products = query.stream()
    
    product_list = []
    for product in products:
        data = product.to_dict()
        data['id'] = product.id
        product_list.append(data)
    
    return product_list

def get_product_firestore(product_id: str) -> Optional[Dict]:
    """Get single product by ID"""
    db = get_firestore_client()
    doc = db.collection('products').document(product_id).get()
    
    if doc.exists:
        data = doc.to_dict()
        data['id'] = doc.id
        return data
    return None

def search_products_firestore(search_query: str, filters: Optional[Dict] = None, 
                              limit: int = 50) -> List[Dict]:
    """Search products by name or brand"""
    db = get_firestore_client()
    
    # Get all products (Firestore doesn't support full-text search natively)
    # In production, consider using Algolia or Elasticsearch for better search
    query = db.collection('products')
    
    # Apply basic filters
    if filters:
        if 'isActive' in filters:
            query = query.where('isActive', '==', filters['isActive'])
        if 'approvalStatus' in filters:
            query = query.where('approvalStatus', '==', filters['approvalStatus'])
    
    products = query.limit(limit * 2).stream()  # Get more to filter client-side
    
    # Filter by search query (case-insensitive)
    search_lower = search_query.lower()
    product_list = []
    
    for product in products:
        data = product.to_dict()
        data['id'] = product.id
        
        # Check if search query matches name or brand
        name = data.get('name', '').lower()
        brand = data.get('brand', '').lower()
        
        if search_lower in name or search_lower in brand:
            product_list.append(data)
            
            if len(product_list) >= limit:
                break
    
    return product_list

def count_products_firestore(filters: Optional[Dict] = None) -> int:
    """Count products with optional filters"""
    db = get_firestore_client()
    query = db.collection('products')
    
    if filters:
        if 'isActive' in filters:
            query = query.where('isActive', '==', filters['isActive'])
        if 'approvalStatus' in filters:
            query = query.where('approvalStatus', '==', filters['approvalStatus'])
        if 'category' in filters:
            query = query.where('category', '==', filters['category'])
        if 'sellerId' in filters:
            query = query.where('sellerId', '==', filters['sellerId'])
    
    # Count documents
    products = list(query.stream())
    return len(products)

def create_product_firestore(product_data: Dict) -> str:
    """Create product in Firestore"""
    db = get_firestore_client()
    product_data['createdAt'] = firestore.SERVER_TIMESTAMP
    product_data['updatedAt'] = firestore.SERVER_TIMESTAMP
    
    doc_ref = db.collection('products').add(product_data)
    return doc_ref[1].id

def update_product_firestore(product_id: str, product_data: Dict) -> Dict:
    """Update product in Firestore"""
    db = get_firestore_client()
    product_data['updatedAt'] = firestore.SERVER_TIMESTAMP
    
    db.collection('products').document(product_id).update(product_data)
    return {'success': True, 'message': 'Product updated'}

def delete_product_firestore(product_id: str) -> Dict:
    """Delete product from Firestore"""
    db = get_firestore_client()
    db.collection('products').document(product_id).delete()
    return {'success': True, 'message': 'Product deleted'}

# ==================== REVIEW OPERATIONS ====================

def add_review_firestore(review_data: Dict) -> str:
    """Add review to Firestore"""
    db = get_firestore_client()
    review_data['createdAt'] = firestore.SERVER_TIMESTAMP
    review_data['updatedAt'] = firestore.SERVER_TIMESTAMP
    
    doc_ref = db.collection('reviews').add(review_data)
    return doc_ref[1].id

def get_reviews_firestore(product_id: str) -> List[Dict]:
    """Get reviews for a product"""
    db = get_firestore_client()
    reviews = db.collection('reviews').where('productId', '==', product_id).order_by('createdAt', direction=firestore.Query.DESCENDING).stream()
    
    review_list = []
    for review in reviews:
        data = review.to_dict()
        data['id'] = review.id
        review_list.append(data)
    
    return review_list
