# Order Items Bug Fix

## Issue
**Error Message**: `'Order' object has no attribute 'items'`

**Symptom**: Error appears when accepting/processing orders, but the action completes successfully after clicking OK and refreshing.

## Root Cause
The code was trying to access `order.items` but the Order model uses `order_items` as the relationship name to OrderItem.

## Locations Fixed

### 1. Line 8285 - Order Pickup Notification
**Before:**
```python
for item in order.items:
    seller_ids.add(item.seller_id)
```

**After:**
```python
for item in order.order_items:
    seller_ids.add(item.product.seller_id)
```

**Context**: When a rider picks up an order, the system notifies all sellers. The code was trying to get seller IDs from order items.

### 2. Line 9836 - Purchase Recommendations
**Before:**
```python
for order in recent_orders:
    for item in order.items:
        if item.product and item.product.category:
            purchased_categories.add(item.product.category.name)
```

**After:**
```python
for order in recent_orders:
    for item in order.order_items:
        if item.product and item.product.category:
            purchased_categories.add(item.product.category.name)
```

**Context**: When generating product recommendations based on purchase history.

## Why It Appeared to Work

1. Database commit happened **before** the error
2. Order status was successfully updated
3. Error occurred during **post-processing** (notifications/recommendations)
4. User saw error message but order was already saved
5. Refresh showed the updated order status

## Testing

After this fix:
1. ✅ Accept an order - No error should appear
2. ✅ Rider picks up order - Sellers get notified without error
3. ✅ View recommendations - Works without error
4. ✅ Order status updates immediately without needing refresh

## Related Information

### Order Model Relationships
```python
class Order(db.Model):
    # Correct relationship name
    order_items = db.relationship('OrderItem', backref='order', lazy='dynamic')
    
    # NOT: items = db.relationship(...)
```

### OrderItem Model
```python
class OrderItem(db.Model):
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    # ...
```

## Prevention

Always use the correct relationship name:
- ✅ `order.order_items` - Correct
- ❌ `order.items` - Wrong

## Status
✅ **FIXED** - Both occurrences corrected

---
**Date Fixed**: November 24, 2025
**Files Modified**: app.py (2 locations)
