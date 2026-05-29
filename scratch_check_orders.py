import os, sys
sys.path.insert(0, os.getcwd())
from app import app
from firestore_helper import get_orders_firestore

with app.app_context():
    orders = get_orders_firestore(None, 'admin')
    print('Total orders:', len(orders))
    for o in orders[:5]:
        print(f"Order ID: {o['id']}")
        print(f"  Root sellerId: {o.get('sellerId')}")
        items = o.get('items', [])
        for i in items:
            print(f"    Item: {i.get('productName')}, sellerId: {i.get('sellerId')}, sqlSellerId: {i.get('sqlSellerId')}")
