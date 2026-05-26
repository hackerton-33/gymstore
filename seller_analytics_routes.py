# =====================================================
# SELLER ANALYTICS ROUTES
# =====================================================

@app.route('/seller/analytics')
@login_required
def seller_analytics():
    """Seller analytics dashboard"""
    user = get_current_user()
    
    if user.role != 'seller':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    try:
        # Get monthly revenue for last 12 months
        monthly_revenue = []
        for i in range(12):
            month_start = manila_now_naive().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            month_start = month_start - timedelta(days=30 * (11 - i))
            month_end = month_start + timedelta(days=30)
            
            # Calculate revenue for this month
            revenue = db.session.query(func.sum(Order.total_amount)).join(OrderItem).join(Product).filter(
                Product.seller_id == user.id,
                Order.created_at >= month_start,
                Order.created_at < month_end,
                Order.status.in_(['processing', 'shipped', 'delivered', 'completed'])
            ).scalar() or 0
            
            monthly_revenue.append({
                'month': month_start.strftime('%b %Y'),
                'revenue': float(revenue)
            })
        
        # Get total orders
        total_orders = Order.query.join(OrderItem).join(Product).filter(
            Product.seller_id == user.id
        ).distinct().count()
        
        # Get total products
        total_products = Product.query.filter_by(seller_id=user.id).count()
        
        # Get category stats
        category_stats = db.session.query(
            Category.name.label('category'),
            func.count(Product.id).label('count'),
            func.sum(Product.price * Product.stock_quantity).label('total_value')
        ).join(Product).filter(
            Product.seller_id == user.id
        ).group_by(Category.name).all()
        
        category_stats_list = []
        for stat in category_stats:
            category_stats_list.append({
                'category': stat.category,
                'count': stat.count,
                'total_value': float(stat.total_value or 0)
            })
        
        return render_template('seller/analytics.html',
                             monthly_revenue=monthly_revenue,
                             total_orders=total_orders,
                             total_products=total_products,
                             category_stats=category_stats_list,
                             current_user=user)
                             
    except Exception as e:
        print(f"Error loading analytics: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading analytics data.', 'error')
        return redirect(url_for('seller_dashboard'))

@app.route('/seller/analytics/realtime-data')
@login_required
def seller_analytics_realtime_data():
    """Provide real-time analytics data for the last 30 days"""
    user = get_current_user()
    
    if user.role != 'seller':
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    try:
        # Get orders from last 30 days
        orders_per_day = []
        for i in range(30):
            day_start = manila_now_naive() - timedelta(days=29-i)
            day_start = day_start.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            # Count orders for this seller on this day
            order_count = Order.query.join(OrderItem).join(Product).filter(
                Product.seller_id == user.id,
                Order.created_at >= day_start,
                Order.created_at < day_end
            ).distinct().count()
            
            orders_per_day.append(order_count)
        
        return jsonify({
            'success': True,
            'orders_per_day': orders_per_day,
            'last_updated': manila_now_naive().strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        print(f"Error fetching real-time analytics: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
