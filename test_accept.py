from app import app, db, User, Order

with app.app_context():
    client = app.test_client()
    rider = User.query.filter_by(role='rider').first()
    if not rider:
        print("No rider found!")
        exit(1)
        
    order = Order.query.filter(Order.status.in_(['confirmed', 'preparing', 'for_pickup']), Order.rider_id == None).first()
    if not order:
        print("No order found!")
        exit(1)
        
    print(f"Testing accept for order {order.id} (status: {order.status}) by rider {rider.id}")
    
    with client.session_transaction() as sess:
        sess['user_id'] = rider.id
        sess['role'] = 'rider'
        
    res = client.post(f'/rider/orders/{order.id}/accept')
    print(f"Status Code: {res.status_code}")
    print(f"Response Data:\n{res.data.decode('utf-8')[:500]}")
