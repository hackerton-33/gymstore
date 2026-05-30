#!/usr/bin/env python3
"""
Daily Fitness - E-commerce Application with Database
Complete Flask application with SQLAlchemy database integration
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory, get_flashed_messages, Response
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
from flask_mail import Mail, Message as MailMessage
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from sqlalchemy import text, or_, and_, func
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
import secrets
import pytz

# Load environment variables
load_dotenv()

# -------------------- Helper Functions for Template Compatibility --------------------
def normalize_order_for_template(order):
    """
    Normalize order data for templates to work with both SQL and Firestore orders.
    SQL orders have attributes like order.order_number, order.status, etc.
    Firestore orders are dicts with keys like order['orderNumber'], order['status'], etc.
    This function converts Firestore orders to have the same attribute interface as SQL orders.
    """
    if isinstance(order, dict):
        # It's a Firestore order (dict), convert to object-like interface
        class NormalizedOrder:
            def __init__(self, data):
                self._data = data
            
            @property
            def id(self):
                return self._data.get('id')
            
            @property
            def order_number(self):
                return self._data.get('orderNumber') or 'N/A'
            
            @property
            def status(self):
                return self._data.get('status') or 'pending'
            
            @property
            def payment_status(self):
                return self._data.get('paymentStatus') or 'pending'
            
            @property
            def total_amount(self):
                total = self._data.get('totalAmount') or self._data.get('total')
                if total is None:
                    # Calculate from items if not present
                    items = self._data.get('items', [])
                    total = sum(item.get('totalPrice', 0) or 0 for item in items)
                return total or 0.0
            
            @property
            def payment_method(self):
                return self._data.get('paymentMethod', 'unknown')
                
            @property
            def shipping_address(self):
                return self._data.get('shippingAddress', 'N/A')
            
            @property
            def created_at(self):
                # Firestore stores as timestamp, convert to datetime
                timestamp = self._data.get('createdAt')
                if timestamp:
                    if hasattr(timestamp, 'to_datetime'):
                        return timestamp.to_datetime()
                    elif isinstance(timestamp, datetime):
                        return timestamp
                return datetime.utcnow()
            
            @property
            def cancellation_reason(self):
                return self._data.get('cancellationReason')
            
            @property
            def notes(self):
                return self._data.get('notes')
            
            @property
            def buyer(self):
                """Return buyer information as an object"""
                class BuyerInfo:
                    def __init__(self, data):
                        self._buyer_data = data.get('buyerInfo', {})
                        self._buyer_id = data.get('buyerId')
                        
                        # Fallback to SQL user if buyerInfo is empty
                        if not self._buyer_data and self._buyer_id:
                            try:
                                sql_id = int(self._buyer_id)
                                user = User.query.get(sql_id)
                            except ValueError:
                                user = User.query.filter_by(firebase_uid=str(self._buyer_id)).first()
                                
                            if user:
                                self._buyer_data = {
                                    'name': user.full_name,
                                    'username': user.username,
                                    'email': user.email,
                                    'phone': user.phone_number,
                                    'firstName': user.first_name,
                                    'lastName': user.last_name,
                                    'profileImage': getattr(user, 'profile_image_url', None)
                                }
                    
                    @property
                    def id(self):
                        return self._buyer_id
                    
                    @property
                    def first_name(self):
                        return self._buyer_data.get('firstName') or self._buyer_data.get('name', '').split()[0] if self._buyer_data.get('name') else 'Unknown'
                    
                    @property
                    def last_name(self):
                        last_name = self._buyer_data.get('lastName')
                        if last_name:
                            return last_name
                        name_parts = self._buyer_data.get('name', '').split()
                        return ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
                    
                    @property
                    def full_name(self):
                        """Return full name for template compatibility"""
                        first = self.first_name
                        last = self.last_name
                        if first == 'Unknown' and not last:
                            return 'Unknown'
                        return f"{first} {last}".strip()
                    
                    @property
                    def email(self):
                        return self._buyer_data.get('email') or 'N/A'
                    
                    @property
                    def username(self):
                        return self._buyer_data.get('username') or self._buyer_data.get('name') or 'Unknown'
                        
                    @property
                    def phone_number(self):
                        return self._buyer_data.get('phone') or 'N/A'
                    
                    @property
                    def profile_image(self):
                        """Return profile image if available"""
                        return self._buyer_data.get('profileImage') or None
                
                return BuyerInfo(self._data)
            
            @property
            def order_items(self):
                # Convert Firestore items to object-like interface
                items = self._data.get('items', [])
                normalized_items = []
                for item in items:
                    class NormalizedItem:
                        def __init__(self, item_data):
                            self._data = item_data
                        
                        @property
                        def product_id(self):
                            return self._data.get('productId')
                        
                        @property
                        def quantity(self):
                            return self._data.get('quantity', 1)
                        
                        @property
                        def unit_price(self):
                            # Try multiple field names and provide default
                            return self._data.get('unitPrice') or self._data.get('price') or 0.0
                        
                        @property
                        def total_price(self):
                            # Calculate if not present
                            total = self._data.get('totalPrice')
                            if total is None:
                                total = self.quantity * self.unit_price
                            return total
                        
                        @property
                        def seller_id(self):
                            return self._data.get('sellerId')
                        
                        @property
                        def product(self):
                            # Create a minimal product object
                            class MinimalProduct:
                                def __init__(self, item_data):
                                    self._data = item_data
                                
                                @property
                                def name(self):
                                    return self._data.get('productName') or 'Unknown Product'
                                
                                @property
                                def image_url(self):
                                    return self._data.get('productImage') or self._data.get('imageUrl')
                                
                                @property
                                def is_web_product(self):
                                    """Check if this is a web product (integer ID) vs mobile product (Firestore doc ID string)"""
                                    product_id = self._data.get('productId')
                                    if product_id is None:
                                        return False
                                    # Try to convert to int - if it works, it's a web product
                                    try:
                                        int(product_id)
                                        return True
                                    except (ValueError, TypeError):
                                        return False
                                
                                @property
                                def category(self):
                                    class MinimalCategory:
                                        @property
                                        def name(self):
                                            return "Category"
                                    return MinimalCategory()
                                
                                @property
                                def web_id(self):
                                    """Return the integer product ID for web products, None for mobile products"""
                                    if self.is_web_product:
                                        return int(self._data.get('productId'))
                                    return None
                                
                                @property
                                def seller(self):
                                    class MinimalSeller:
                                        def __init__(self, item_data):
                                            self._data = item_data
                                        
                                        @property
                                        def business_name(self):
                                            return "Seller"
                                            
                                        @property
                                        def full_name(self):
                                            return "Seller"
                                    return MinimalSeller(self._data)
                            
                            return MinimalProduct(self._data)
                    
                    normalized_items.append(NormalizedItem(item))
                
                # Return a list-like object that works with Jinja
                class ItemList(list):
                    def first(self):
                        return self[0] if self else None
                
                return ItemList(normalized_items)
        
        return NormalizedOrder(order)
    else:
        # It's already a SQL order object, return as-is
        return order

# -------------------- Firebase Admin SDK --------------------
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth_admin, firestore as firebase_firestore

_firebase_initialized = False
try:
    _service_account_path = os.path.join(os.path.dirname(__file__), 'gym-ecommerce-ce8ab-firebase-adminsdk-fbsvc-53b91bdae9.json')
    if os.path.exists(_service_account_path):
        cred = credentials.Certificate(_service_account_path)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        print("[OK] Firebase Admin SDK initialized")
    else:
        print("[WARNING] serviceAccountKey.json not found — Firebase Admin features disabled")
except Exception as e:
    print(f"[WARNING] Firebase Admin SDK init failed: {e}")

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'gym-store-secret-key-2024'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# Email Configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'False') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', os.getenv('MAIL_USERNAME'))
 
# Upload configuration
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PROFILE_UPLOAD_FOLDER = os.path.join('static', 'uploads', 'profile_pics')
PRODUCT_UPLOAD_FOLDER = os.path.join('static', 'uploads', 'product_images')
app.config['PROFILE_UPLOAD_FOLDER'] = os.path.join(BASE_DIR, PROFILE_UPLOAD_FOLDER)
app.config['PRODUCT_UPLOAD_FOLDER'] = os.path.join(BASE_DIR, PRODUCT_UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB
ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
ALLOWED_DOCUMENT_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg'}

# Ensure upload directories exist
os.makedirs(app.config['PROFILE_UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PRODUCT_UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'static', 'uploads', 'business_docs'), exist_ok=True)

# Database configuration
railway_db = os.getenv('DATABASE_URL')

if railway_db:
    # Railway provides mysql://, but SQLAlchemy needs mysql+pymysql://
    if railway_db.startswith("mysql://"):
        railway_db = railway_db.replace("mysql://", "mysql+pymysql://", 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = railway_db
    print("[OK] Using Database from DATABASE_URL (Railway)")
else:
    DATABASE_CONFIG = {
        'mysql': {
            'host': 'localhost',
            'port': 3306,
            'user': 'root',
            'password': '',  # Update this with your SQLyog MySQL password
            'database': 'gym_store_db',
            'charset': 'utf8mb4'
        }
    }
    
    # Try local MySQL first, fallback to SQLite
    try:
        import pymysql
        connection = pymysql.connect(
            host=DATABASE_CONFIG['mysql']['host'],
            port=DATABASE_CONFIG['mysql']['port'],
            user=DATABASE_CONFIG['mysql']['user'],
            password=DATABASE_CONFIG['mysql']['password'],
            database=DATABASE_CONFIG['mysql']['database'],
            charset=DATABASE_CONFIG['mysql']['charset']
        )
        connection.close()
        
        # MySQL connection successful
        app.config['SQLALCHEMY_DATABASE_URI'] = (
            f"mysql+pymysql://{DATABASE_CONFIG['mysql']['user']}:"
            f"{DATABASE_CONFIG['mysql']['password']}@"
            f"{DATABASE_CONFIG['mysql']['host']}:"
            f"{DATABASE_CONFIG['mysql']['port']}/"
            f"{DATABASE_CONFIG['mysql']['database']}?"
            f"charset={DATABASE_CONFIG['mysql']['charset']}"
        )
        print("[OK] Using local MySQL database")
        
    except Exception as e:
        # Fallback to SQLite
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gym_store.db'
        print(f"[WARNING] Local MySQL connection failed: {e}")
        print("[INFO] Using SQLite database as fallback")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Initialize Flask-Mail
mail = Mail(app)

# Initialize SocketIO for real-time chat
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# -------------------- OAuth Configuration --------------------
# Load environment variables
load_dotenv()

# Get base URL from environment or use default (HTTPS for OAuth compatibility)
APP_BASE_URL = os.getenv('APP_BASE_URL', 'https://localhost:5000')

# Initialize OAuth
oauth = OAuth(app)

# Configure Google OAuth
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# Configure Facebook OAuth
facebook_client_id = os.getenv('FACEBOOK_CLIENT_ID')
facebook_client_secret = os.getenv('FACEBOOK_CLIENT_SECRET')

if facebook_client_id and facebook_client_secret:
    facebook = oauth.register(
        name='facebook',
        client_id=facebook_client_id,
        client_secret=facebook_client_secret,
        access_token_url='https://graph.facebook.com/oauth/access_token',
        authorize_url='https://www.facebook.com/dialog/oauth',
        api_base_url='https://graph.facebook.com/',
        client_kwargs={'scope': 'email public_profile'},
    )
else:
    # Register with placeholder values if not configured
    facebook = oauth.register(
        name='facebook',
        client_id='not-configured',
        client_secret='not-configured',
        access_token_url='https://graph.facebook.com/oauth/access_token',
        authorize_url='https://www.facebook.com/dialog/oauth',
        api_base_url='https://graph.facebook.com/',
        client_kwargs={'scope': 'email public_profile'},
    )

# -------------------- DB Connectivity Helpers --------------------
def verify_db_connection():
    """Verify that we can connect to the configured DB and report current database name."""
    try:
        with db.engine.connect() as conn:
            # Works for MySQL; SQLite will also return a single value
            try:
                result = conn.execute(text('SELECT DATABASE()')).scalar()
            except Exception:
                result = None
            return True, result
    except Exception as e:
        return False, str(e)

# Create tables if missing
with app.app_context():
    try:
        db.create_all()
        print("[OK] Database tables created/verified successfully")
    except Exception as e:
        print(f"[ERROR] Failed to create database tables: {e}")
    ok, current_db = verify_db_connection()
    if ok:

        print(f"[DB] Connected. Current database: {current_db}")
    else:
        print(f"[ERROR] DB connection check failed: {current_db}")

# Lightweight health endpoint to confirm DB connectivity
@app.route('/health/db')
def db_health():
    ok, current_db = verify_db_connection()
    return jsonify({
        'connected': bool(ok),
        'database': current_db,
        'engine': str(db.engine.url).split('@')[0]  # hide host details
    })

# =====================================================
# HELPER FUNCTIONS (Moved up for context processor)
# =====================================================

def get_current_user():
    """Get current logged-in user"""
    if 'user_id' in session:
        return db.session.get(User, session['user_id'])
    return None

# Manila timezone configuration
MANILA_TZ = pytz.timezone('Asia/Manila')

def manila_now():
    """Get current Manila datetime (timezone-aware)"""
    return datetime.now(MANILA_TZ)

def manila_now_naive():
    """Get current Manila datetime without timezone info (for database storage)"""
    return datetime.now(MANILA_TZ).replace(tzinfo=None)

# Legacy function names for backward compatibility
def utc_now():
    """Get current Manila datetime - updated to use Manila timezone"""
    return manila_now_naive()

def utc_now_naive():
    """Get current Manila datetime without timezone info"""
    return manila_now_naive()

def generate_product_slug(product_name):
    """Generate SEO-friendly slug from product name"""
    import re
    slug = re.sub(r'[^a-zA-Z0-9\s-]', '', product_name.lower())
    slug = re.sub(r'\s+', '-', slug.strip())
    slug = re.sub(r'-+', '-', slug)  # Remove multiple consecutive dashes
    return slug.strip('-')  # Remove leading/trailing dashes

# Template filter for Manila timezone
@app.template_filter('manila_time')
def manila_time_filter(dt):
    """Convert datetime to Manila timezone for display in templates"""
    if dt is None:
        return ''
    # If datetime is naive (no timezone), assume it's already in Manila time
    if dt.tzinfo is None:
        return dt
    # If datetime has timezone info, convert to Manila time
    return dt.astimezone(MANILA_TZ)

# Context processor to make Manila time functions available in templates
@app.context_processor
def inject_manila_time():
    """Make Manila time functions available in all templates"""
    return {
        'manila_now': manila_now,
        'manila_now_naive': manila_now_naive,
        'MANILA_TZ': MANILA_TZ,
        'FIREBASE_CONFIG': {
            'apiKey': os.getenv('FIREBASE_API_KEY', ''),
            'authDomain': os.getenv('FIREBASE_AUTH_DOMAIN', ''),
            'projectId': os.getenv('FIREBASE_PROJECT_ID', ''),
            'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET', ''),
            'messagingSenderId': os.getenv('FIREBASE_MESSAGING_SENDER_ID', ''),
            'appId': os.getenv('FIREBASE_APP_ID', ''),
            'measurementId': os.getenv('FIREBASE_MEASUREMENT_ID', ''),
        }
    }

def send_automatic_message(sender_id, receiver_id, message_content, order_id=None):
    """
    Send an automatic system message between users
    Creates conversation if it doesn't exist
    """
    try:
        # Check if conversation already exists
        existing = Conversation.query.filter(
            db.or_(
                db.and_(Conversation.participant1_id == sender_id, Conversation.participant2_id == receiver_id),
                db.and_(Conversation.participant1_id == receiver_id, Conversation.participant2_id == sender_id)
            )
        ).first()
        
        if existing:
            conversation = existing
        else:
            # Create new conversation
            conversation = Conversation(
                participant1_id=sender_id,
                participant2_id=receiver_id,
                order_id=order_id
            )
            db.session.add(conversation)
            db.session.flush()
        
        # Create the message
        message = Message(
            conversation_id=conversation.id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_content=message_content,
            message_type='system'
        )
        db.session.add(message)
        
        # Update conversation timestamp
        conversation.updated_at = utc_now()
        
        db.session.commit()
        
        return True
    except Exception as e:
        print(f"Error sending automatic message: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return False

# =====================================================
# DATABASE MODELS
# =====================================================

class User(db.Model):
    """User model for buyers, sellers, and admins"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)  # Nullable for OAuth users
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(50))
    state = db.Column(db.String(50))
    zip_code = db.Column(db.String(10))
    country = db.Column(db.String(50), default='USA')
    role = db.Column(db.Enum('buyer', 'seller', 'admin', 'rider'), nullable=False, default='buyer', index=True)
    is_active = db.Column(db.Boolean, default=True)
    email_verified = db.Column(db.Boolean, default=False)
    approval_status = db.Column(db.Enum('pending', 'approved', 'rejected'), default='pending', index=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime)
    business_name = db.Column(db.String(200))  # For sellers
    business_permit = db.Column(db.String(500))  # File path for business permit
    dti_certification = db.Column(db.String(500))  # File path for DTI cert
    id_document = db.Column(db.String(500))  # File path for user's valid ID (buyers/riders)
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    profile_image = db.Column(db.String(500))
    
    # OAuth fields
    auth_type = db.Column(db.Enum('manual', 'google', 'facebook'), default='manual', nullable=False, index=True)
    oauth_provider_id = db.Column(db.String(255), unique=True, nullable=True, index=True)  # OAuth provider's user ID
    
    # Firebase cross-platform field
    firebase_uid = db.Column(db.String(255), unique=True, nullable=True, index=True)  # Firebase UID for cross-platform auth
    
    # Relationships
    products = db.relationship('Product', backref='seller', lazy='dynamic', foreign_keys='Product.seller_id')
    orders = db.relationship('Order', backref='buyer', lazy='dynamic', foreign_keys='Order.buyer_id')
    deliveries = db.relationship('Order', backref='rider', lazy='dynamic', foreign_keys='Order.rider_id')
    cart_items = db.relationship('Cart', backref='user', lazy='dynamic')
    reviews = db.relationship('Review', backref='user', lazy='dynamic')
    wishlist_items = db.relationship('Wishlist', backref='user', lazy='dynamic')
    
    @property
    def phone_number(self):
        """Alias for phone to match Firestore field name"""
        return self.phone
    
    @phone_number.setter
    def phone_number(self, value):
        """Setter for phone_number alias"""
        self.phone = value
    
    @property
    def full_name(self):
        """Get user's full name"""
        if not self.first_name and not self.last_name:
            return self.username
        return f"{self.first_name} {self.last_name}".strip()
    
    @full_name.setter
    def full_name(self, value):
        """Set full name by splitting into first and last"""
        if value:
            parts = value.strip().split(' ', 1)
            self.first_name = parts[0]
            self.last_name = parts[1] if len(parts) > 1 else ''
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        # OAuth users don't have password_hash
        if self.password_hash is None:
            return False
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Category(db.Model):
    """Product categories"""
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    image = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Relationships
    products = db.relationship('Product', backref='category', lazy='dynamic')
    
    def __repr__(self):
        return f'<Category {self.name}>'

class Product(db.Model):
    """Products model"""
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    brand = db.Column(db.String(100), index=True)
    description = db.Column(db.Text)
    short_description = db.Column(db.String(500))
    price = db.Column(db.Numeric(10, 2), nullable=False, index=True)
    compare_price = db.Column(db.Numeric(10, 2))
    cost_price = db.Column(db.Numeric(10, 2))
    sku = db.Column(db.String(100), unique=True)
    stock_quantity = db.Column(db.Integer, default=0, index=True)
    weight = db.Column(db.Numeric(8, 2))
    dimensions = db.Column(db.String(100))
    image_url = db.Column(db.String(500))
    gallery_images = db.Column(db.JSON)
    is_active = db.Column(db.Boolean, default=True, index=True)
    is_featured = db.Column(db.Boolean, default=False, index=True)
    meta_title = db.Column(db.String(200))
    meta_description = db.Column(db.Text)
    tags = db.Column(db.JSON)
    # Product approval fields
    approval_status = db.Column(db.Enum('pending', 'approved', 'rejected'), default='pending', nullable=False, index=True)
    submitted_at = db.Column(db.DateTime, default=utc_now, index=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    cart_items = db.relationship('Cart', backref='product', lazy='dynamic')
    order_items = db.relationship('OrderItem', backref='product', lazy='dynamic')
    reviews = db.relationship('Review', backref='product', lazy='dynamic')
    wishlist_items = db.relationship('Wishlist', backref='product', lazy='dynamic')
    
    @property
    def average_rating(self):
        """Calculate average rating from reviews"""
        reviews = Review.query.filter_by(product_id=self.id, is_approved=True).all()
        if reviews:
            return sum(review.rating for review in reviews) / len(reviews)
        return 0
    
    @property
    def review_count(self):
        """Get count of approved reviews"""
        return Review.query.filter_by(product_id=self.id, is_approved=True).count()
    
    @property
    def total_sold(self):
        """Calculate total quantity sold from completed orders"""
        from sqlalchemy import func
        result = db.session.query(func.sum(OrderItem.quantity)).join(Order).filter(
            OrderItem.product_id == self.id,
            Order.status.in_(['delivered', 'completed'])
        ).scalar()
        return int(result) if result else 0
    
    def __repr__(self):
        return f'<Product {self.name}>'

class ProductApprovalHistory(db.Model):
    """Product approval history for transparency"""
    __tablename__ = 'product_approval_history'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    action = db.Column(db.Enum('submitted', 'approved', 'rejected', 'resubmitted'), nullable=False, index=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reason = db.Column(db.Text, nullable=True)  # For rejection or resubmission reasons
    notes = db.Column(db.Text, nullable=True)  # Admin notes
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    
    # Relationships
    product = db.relationship('Product', backref='approval_history')
    admin = db.relationship('User', foreign_keys=[admin_id])
    
    def __repr__(self):
        return f'<ProductApprovalHistory Product:{self.product_id} {self.action}>'

class Conversation(db.Model):
    """Conversation model for tracking chat threads between users"""
    __tablename__ = 'conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    participant1_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    participant2_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Optional context linking
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True, index=True)
    
    # Status tracking
    is_active = db.Column(db.Boolean, default=True, index=True)
    is_muted_by_p1 = db.Column(db.Boolean, default=False)
    is_muted_by_p2 = db.Column(db.Boolean, default=False)
    
    # Admin moderation
    is_restricted = db.Column(db.Boolean, default=False)
    restriction_reason = db.Column(db.Text, nullable=True)
    restricted_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    restricted_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    participant1 = db.relationship('User', foreign_keys=[participant1_id], backref='conversations_as_p1')
    participant2 = db.relationship('User', foreign_keys=[participant2_id], backref='conversations_as_p2')
    product = db.relationship('Product', backref='conversations')
    order = db.relationship('Order', backref='conversations')
    messages = db.relationship('Message', backref='conversation', lazy='dynamic', cascade='all, delete-orphan')
    restrictor = db.relationship('User', foreign_keys=[restricted_by])
    
    # Unique constraint - prevent duplicate conversations
    __table_args__ = (
        db.Index('idx_participants', 'participant1_id', 'participant2_id'),
    )
    
    def get_other_participant(self, current_user_id):
        """Get the other participant in the conversation"""
        return self.participant2 if self.participant1_id == current_user_id else self.participant1
    
    def is_participant(self, user_id):
        """Check if user is a participant"""
        return user_id in [self.participant1_id, self.participant2_id]
    
    def get_unread_count(self, user_id):
        """Get unread message count for a specific user"""
        return Message.query.filter(
            Message.conversation_id == self.id,
            Message.sender_id != user_id,
            Message.is_read == False
        ).count()
    
    def get_last_message(self):
        """Get the last message in conversation"""
        return Message.query.filter_by(conversation_id=self.id).order_by(Message.created_at.desc()).first()
    
    def __repr__(self):
        return f'<Conversation {self.id}: User {self.participant1_id} ↔ User {self.participant2_id}>'

class Message(db.Model):
    """Message model for chat system"""
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    message_content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.Enum('text', 'image', 'file', 'system'), default='text')
    
    # File attachments
    attachment_url = db.Column(db.String(500), nullable=True)
    attachment_name = db.Column(db.String(255), nullable=True)
    attachment_size = db.Column(db.Integer, nullable=True)
    
    # Message status
    is_read = db.Column(db.Boolean, default=False, index=True)
    is_delivered = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    
    # Moderation flags
    is_flagged = db.Column(db.Boolean, default=False)
    flag_reason = db.Column(db.String(255), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')
    
    def mark_as_read(self):
        """Mark message as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = utc_now()
            db.session.commit()
    
    def mark_as_delivered(self):
        """Mark message as delivered"""
        if not self.is_delivered:
            self.is_delivered = True
            self.delivered_at = utc_now()
            db.session.commit()
    
    def to_dict(self):
        """Convert message to dictionary for JSON responses"""
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'sender_id': self.sender_id,
            'sender_name': self.sender.username if self.sender else 'Unknown',
            'sender_image': self.sender.profile_image if self.sender else None,
            'receiver_id': self.receiver_id,
            'message_content': self.message_content,
            'message_type': self.message_type,
            'attachment_url': self.attachment_url,
            'attachment_name': self.attachment_name,
            'is_read': self.is_read,
            'is_delivered': self.is_delivered,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None,
        }
    
    def __repr__(self):
        return f'<Message {self.id} from User {self.sender_id} to User {self.receiver_id}>'

class UserOnlineStatus(db.Model):
    """Track user online/offline status for chat"""
    __tablename__ = 'user_online_status'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False, index=True)
    is_online = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime, default=utc_now)
    socket_id = db.Column(db.String(100), nullable=True)  # For WebSocket tracking
    
    # Relationships
    user = db.relationship('User', backref=db.backref('online_status', uselist=False))
    
    def update_status(self, is_online, socket_id=None):
        """Update user's online status"""
        self.is_online = is_online
        self.last_seen = utc_now()
        if socket_id:
            self.socket_id = socket_id
        db.session.commit()
    
    def __repr__(self):
        return f'<UserOnlineStatus User {self.user_id}: {"Online" if self.is_online else "Offline"}>'

class Cart(db.Model):
    """Shopping cart model"""
    __tablename__ = 'cart'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    variant = db.Column(db.String(100))
    selected_weight = db.Column(db.String(50))
    unit_price = db.Column(db.Numeric(10, 2))
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Unique constraint
    __table_args__ = (db.UniqueConstraint('user_id', 'product_id', 'variant', 'selected_weight', name='unique_user_product'),)
    
    @property
    def subtotal(self):
        """Calculate subtotal for this cart item"""
        price = self.unit_price if self.unit_price is not None else self.product.price
        return float(price * self.quantity)
    
    def __repr__(self):
        return f'<Cart {self.user_id}:{self.product.name}>'

class Order(db.Model):
    """Orders model"""
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    rider_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)  # Delivery rider
    status = db.Column(db.Enum('pending', 'confirmed', 'preparing', 'for_pickup', 'picked_up', 'on_delivery', 'delivered', 'completed', 'cancelled', 'refunded'), 
                      default='pending', index=True)
    payment_status = db.Column(db.Enum('pending', 'paid', 'failed', 'refunded'), 
                              default='pending', index=True)
    payment_method = db.Column(db.Enum('credit_card', 'paypal', 'cash_on_delivery', 'bank_transfer'), 
                              nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(10, 2), default=0)
    shipping_amount = db.Column(db.Numeric(10, 2), default=0)
    discount_amount = db.Column(db.Numeric(10, 2), default=0)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    shipping_address = db.Column(db.Text, nullable=False)
    billing_address = db.Column(db.Text)
    delivery_latitude = db.Column(db.Float)  # For map integration
    delivery_longitude = db.Column(db.Float)  # For map integration
    notes = db.Column(db.Text)
    tracking_number = db.Column(db.String(100))
    shipped_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    auto_confirmed_at = db.Column(db.DateTime)  # Track auto-confirmation
    last_status_update = db.Column(db.DateTime)  # Track when status was last changed
    firestore_order_id = db.Column(db.String(255), unique=True, nullable=True, index=True)  # Link to Firestore
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    order_items = db.relationship('OrderItem', backref='order', lazy='dynamic')
    
    def __repr__(self):
        return f'<Order {self.order_number}>'

class OrderItem(db.Model):
    """Order items model"""
    __tablename__ = 'order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    
    def __repr__(self):
        return f'<OrderItem {self.product.name} x{self.quantity}>'

class OrderStatusLog(db.Model):
    """Activity log for order status changes"""
    __tablename__ = 'order_status_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user_role = db.Column(db.String(20), nullable=False)  # seller, rider, buyer, admin
    old_status = db.Column(db.String(50))
    new_status = db.Column(db.String(50), nullable=False)
    action = db.Column(db.String(255), nullable=False)  # Description of action
    notes = db.Column(db.Text)  # Optional notes
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    
    # Relationships
    order = db.relationship('Order', backref=db.backref('status_logs', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('order_actions', lazy='dynamic'))
    
    def __repr__(self):
        return f'<OrderStatusLog Order#{self.order_id}: {self.old_status}→{self.new_status}>'

class Review(db.Model):
    """Product reviews model"""
    __tablename__ = 'reviews'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)
    rating = db.Column(db.Integer, nullable=False, index=True)
    title = db.Column(db.String(200))
    comment = db.Column(db.Text)
    is_verified = db.Column(db.Boolean, default=False)
    is_approved = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Unique constraint
    __table_args__ = (db.UniqueConstraint('user_id', 'product_id', 'order_id', name='unique_user_product_order'),)
    
    def __repr__(self):
        return f'<Review {self.rating} stars for {self.product.name}>'

class FeaturedTestimonial(db.Model):
    """Featured testimonials for About Us page"""
    __tablename__ = 'featured_testimonials'
    
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('reviews.id'), nullable=False, unique=True, index=True)
    display_order = db.Column(db.Integer, default=0, index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    review = db.relationship('Review', backref='featured_testimonial', lazy='joined')
    admin = db.relationship('User', foreign_keys=[created_by])
    
    def __repr__(self):
        return f'<FeaturedTestimonial {self.review_id}>'

class Wishlist(db.Model):
    """Wishlist model"""
    __tablename__ = 'wishlist'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Unique constraint
    __table_args__ = (db.UniqueConstraint('user_id', 'product_id', name='unique_user_product'),)
    
    def __repr__(self):
        return f'<Wishlist {self.user.username}:{self.product.name}>'

class Follow(db.Model):
    """Follow model for users following sellers"""
    __tablename__ = 'follows'
    
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)  # The user who follows
    following_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)  # The seller being followed
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    
    # Relationships
    follower = db.relationship('User', foreign_keys=[follower_id], backref='following')
    following = db.relationship('User', foreign_keys=[following_id], backref='followers')
    
    # Unique constraint
    __table_args__ = (db.UniqueConstraint('follower_id', 'following_id', name='unique_follower_following'),)
    
    def __repr__(self):
        return f'<Follow {self.follower.username} follows {self.following.username}>'

class Coupon(db.Model):
    """Coupons model"""
    __tablename__ = 'coupons'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    type = db.Column(db.Enum('percentage', 'fixed_amount'), nullable=False)
    value = db.Column(db.Numeric(10, 2), nullable=False)
    minimum_amount = db.Column(db.Numeric(10, 2), default=0)
    maximum_discount = db.Column(db.Numeric(10, 2))
    usage_limit = db.Column(db.Integer)
    used_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True, index=True)
    starts_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def __repr__(self):
        return f'<Coupon {self.code}>'

class CouponUsage(db.Model):
    """Coupon usage tracking"""
    __tablename__ = 'coupon_usage'
    
    id = db.Column(db.Integer, primary_key=True)
    coupon_id = db.Column(db.Integer, db.ForeignKey('coupons.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, index=True)
    discount_amount = db.Column(db.Numeric(10, 2), nullable=False)
    used_at = db.Column(db.DateTime, default=utc_now)
    
    # Unique constraint
    __table_args__ = (db.UniqueConstraint('coupon_id', 'user_id', 'order_id', name='unique_coupon_user_order'),)
    
    def __repr__(self):
        return f'<CouponUsage {self.coupon.code}:{self.user.username}>'

class Notification(db.Model):
    """Enhanced notifications model"""
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    type = db.Column(db.Enum(
        'system_alert', 'registration', 'order_update', 'transaction', 
        'admin_action', 'dispute', 'financial', 'product_update', 
        'promotion', 'reminder', 'warning', 'new_delivery',
        'new_message', 'order'
    ), nullable=False, index=True)
    category = db.Column(db.Enum(
        'approval', 'order', 'payment', 'delivery', 'complaint', 
        'payout', 'stock', 'system', 'general'
    ), nullable=False, index=True)
    priority = db.Column(db.Enum('low', 'medium', 'high', 'urgent'), default='medium', index=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    action_url = db.Column(db.String(500))  # URL for action button
    action_text = db.Column(db.String(100))  # Text for action button
    is_read = db.Column(db.Boolean, default=False, index=True)
    is_email_sent = db.Column(db.Boolean, default=False)
    is_sms_sent = db.Column(db.Boolean, default=False)
    data = db.Column(db.JSON)  # Additional data (order_id, product_id, etc.)
    expires_at = db.Column(db.DateTime)  # For temporary notifications
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    read_at = db.Column(db.DateTime)
    
    @staticmethod
    def cleanup_expired():
        """Remove expired notifications"""
        try:
            expired_count = Notification.query.filter(
                Notification.expires_at.isnot(None),
                Notification.expires_at < utc_now()
            ).delete()
            db.session.commit()
            return expired_count
        except Exception as e:
            db.session.rollback()
            print(f"Error cleaning up expired notifications: {e}")
            return 0
    
    @staticmethod
    def cleanup_old_read_notifications(days=30):
        """Remove old read notifications to prevent clutter"""
        try:
            cutoff_date = utc_now() - timedelta(days=days)
            old_count = Notification.query.filter(
                Notification.is_read == True,
                Notification.read_at < cutoff_date
            ).delete()
            db.session.commit()
            return old_count
        except Exception as e:
            db.session.rollback()
            print(f"Error cleaning up old notifications: {e}")
            return 0
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.read_at = utc_now()
        db.session.commit()
    
    def get_icon(self):
        """Get icon based on notification type"""
        icons = {
            'system_alert': 'fas fa-exclamation-triangle',
            'registration': 'fas fa-user-check',
            'order_update': 'fas fa-shopping-cart',
            'transaction': 'fas fa-credit-card',
            'admin_action': 'fas fa-shield-alt',
            'dispute': 'fas fa-gavel',
            'financial': 'fas fa-money-bill-wave',
            'product_update': 'fas fa-box',
            'promotion': 'fas fa-tags',
            'reminder': 'fas fa-bell',
            'warning': 'fas fa-exclamation-circle'
        }
        return icons.get(self.type, 'fas fa-info-circle')
    
    def get_color_class(self):
        """Get color class based on priority"""
        colors = {
            'low': 'text-info',
            'medium': 'text-primary',
            'high': 'text-warning',
            'urgent': 'text-danger'
        }
        return colors.get(self.priority, 'text-primary')
    
    def to_dict(self):
        """Convert notification to dictionary for JSON responses"""
        return {
            'id': self.id,
            'type': self.type,
            'category': self.category,
            'priority': self.priority,
            'title': self.title,
            'message': self.message,
            'action_url': self.action_url,
            'action_text': self.action_text,
            'is_read': self.is_read,
            'icon': self.get_icon(),
            'color_class': self.get_color_class(),
            'created_at': self.created_at.isoformat(),
            'data': self.data
        }
    
    def __repr__(self):
        return f'<Notification {self.title}>'

class NotificationPreference(db.Model):
    """User notification preferences"""
    __tablename__ = 'notification_preferences'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    
    # Email preferences
    email_enabled = db.Column(db.Boolean, default=True)
    email_order_updates = db.Column(db.Boolean, default=True)
    email_financial = db.Column(db.Boolean, default=True)
    email_promotions = db.Column(db.Boolean, default=True)
    email_system_alerts = db.Column(db.Boolean, default=True)
    
    # In-app preferences
    app_enabled = db.Column(db.Boolean, default=True)
    app_order_updates = db.Column(db.Boolean, default=True)
    app_financial = db.Column(db.Boolean, default=True)
    app_promotions = db.Column(db.Boolean, default=True)
    app_system_alerts = db.Column(db.Boolean, default=True)
    
    # SMS preferences (for future implementation)
    sms_enabled = db.Column(db.Boolean, default=False)
    sms_critical_only = db.Column(db.Boolean, default=True)
    
    def __repr__(self):
        return f'<NotificationPreference User:{self.user_id}>'

class SellerStatistics(db.Model):
    """Seller statistics model"""
    __tablename__ = 'seller_statistics'
    
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    total_products = db.Column(db.Integer, default=0)
    total_orders = db.Column(db.Integer, default=0)
    total_revenue = db.Column(db.Numeric(12, 2), default=0)
    total_views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Unique constraint
    __table_args__ = (db.UniqueConstraint('seller_id', 'date', name='unique_seller_date'),)
    
    def __repr__(self):
        return f'<SellerStatistics {self.seller.username}:{self.date}>'

class Commission(db.Model):
    """Platform commission tracking"""
    __tablename__ = 'commissions'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    order_amount = db.Column(db.Numeric(12, 2), nullable=False)
    commission_rate = db.Column(db.Numeric(5, 2), nullable=False)  # Percentage (e.g., 5.00 for 5%)
    commission_amount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.Enum('pending', 'collected'), default='pending', index=True)
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    
    def __repr__(self):
        return f'<Commission Order:{self.order_id} ${self.commission_amount}>'

class PlatformSettings(db.Model):
    """Platform settings and configuration"""
    __tablename__ = 'platform_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def __repr__(self):
        return f'<PlatformSettings {self.key}:{self.value}>'

class Complaint(db.Model):
    """User complaints and disputes"""
    __tablename__ = 'complaints'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    complainant_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    respondent_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)
    category = db.Column(db.Enum('late_delivery', 'damaged_item', 'fraud', 'poor_service', 'other'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.Enum('open', 'in_progress', 'resolved', 'closed'), default='open', index=True)
    priority = db.Column(db.Enum('low', 'medium', 'high', 'urgent'), default='medium')
    admin_notes = db.Column(db.Text)
    resolution = db.Column(db.Text)
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    resolved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def __repr__(self):
        return f'<Complaint {self.ticket_number}>'

class UserViolation(db.Model):
    """User violation tracking system"""
    __tablename__ = 'user_violations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    violation_type = db.Column(db.Enum('warning', 'minor', 'major', 'severe'), nullable=False)
    category = db.Column(db.String(100), nullable=False)  # fraud, late_delivery, poor_service, etc.
    description = db.Column(db.Text, nullable=False)
    action_taken = db.Column(db.String(200))  # warning, 7-day suspension, permanent ban, etc.
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    expires_at = db.Column(db.DateTime)  # For temporary suspensions
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    
    def __repr__(self):
        return f'<UserViolation {self.user_id}:{self.violation_type}>'

class SellerWarning(db.Model):
    """Enhanced seller warning system with offense tracking"""
    __tablename__ = 'seller_warnings'
    
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    warning_type = db.Column(db.Enum(
        'policy_violation', 'quality_issue', 'delivery_delay', 'customer_service', 
        'pricing_issue', 'product_misrepresentation', 'communication_failure', 'other'
    ), nullable=False)
    severity = db.Column(db.Enum('low', 'medium', 'high', 'critical'), default='medium')
    offense_level = db.Column(db.Integer, default=1)  # 1st, 2nd, 3rd offense, etc.
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    policy_link = db.Column(db.String(500))  # Link to relevant policy/guidelines
    action_required = db.Column(db.Text)  # What seller needs to do
    deadline = db.Column(db.DateTime)  # Deadline for corrective action
    is_acknowledged = db.Column(db.Boolean, default=False)
    acknowledged_at = db.Column(db.DateTime)
    is_resolved = db.Column(db.Boolean, default=False)
    resolved_at = db.Column(db.DateTime)
    admin_notes = db.Column(db.Text)
    seller_response = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    
    # Relationships
    seller = db.relationship('User', foreign_keys=[seller_id], backref='received_warnings')
    admin = db.relationship('User', foreign_keys=[admin_id], backref='issued_warnings')
    
    def get_offense_label(self):
        """Get human-readable offense level"""
        if self.offense_level == 1:
            return "1st Offense"
        elif self.offense_level == 2:
            return "2nd Offense"
        elif self.offense_level == 3:
            return "Final Warning"
        else:
            return f"{self.offense_level}th Offense"
    
    def get_severity_color(self):
        """Get color class for severity"""
        colors = {
            'low': 'warning',
            'medium': 'info', 
            'high': 'danger',
            'critical': 'dark'
        }
        return colors.get(self.severity, 'secondary')
    
    def is_critical(self):
        """Check if this is a critical warning"""
        return self.severity == 'critical' or self.offense_level >= 3
    
    def __repr__(self):
        return f'<SellerWarning {self.seller_id}:{self.warning_type}:{self.offense_level}>'

class BuyerWarning(db.Model):
    """Enhanced buyer warning system with offense tracking"""
    __tablename__ = 'buyer_warnings'
    
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    warning_type = db.Column(db.Enum(
        'payment_issue', 'fraudulent_activity', 'abuse_of_system', 'inappropriate_behavior', 
        'fake_reviews', 'chargeback_abuse', 'account_misuse', 'other'
    ), nullable=False)
    severity = db.Column(db.Enum('low', 'medium', 'high', 'critical'), default='medium')
    offense_level = db.Column(db.Integer, default=1)  # 1st, 2nd, 3rd offense, etc.
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    policy_link = db.Column(db.String(500))  # Link to relevant policy/guidelines
    action_required = db.Column(db.Text)  # What buyer needs to do
    deadline = db.Column(db.DateTime)  # Deadline for corrective action
    is_acknowledged = db.Column(db.Boolean, default=False)
    acknowledged_at = db.Column(db.DateTime)
    is_resolved = db.Column(db.Boolean, default=False)
    resolved_at = db.Column(db.DateTime)
    admin_notes = db.Column(db.Text)
    buyer_response = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    
    # Relationships
    buyer = db.relationship('User', foreign_keys=[buyer_id], backref='received_buyer_warnings')
    admin = db.relationship('User', foreign_keys=[admin_id], backref='issued_buyer_warnings')
    
    def get_offense_label(self):
        """Get human-readable offense level"""
        if self.offense_level == 1:
            return "1st Offense"
        elif self.offense_level == 2:
            return "2nd Offense"
        elif self.offense_level == 3:
            return "Final Warning"
        else:
            return f"{self.offense_level}th Offense"
    
    def get_severity_color(self):
        """Get color class for severity"""
        colors = {
            'low': 'warning',
            'medium': 'info', 
            'high': 'danger',
            'critical': 'dark'
        }
        return colors.get(self.severity, 'secondary')
    
    def is_critical(self):
        """Check if this is a critical warning"""
        return self.severity == 'critical' or self.offense_level >= 3
    
    def __repr__(self):
        return f'<BuyerWarning {self.buyer_id}:{self.warning_type}:{self.offense_level}>'

class AdminAuditLog(db.Model):
    """Admin action audit trail"""
    __tablename__ = 'admin_audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    action = db.Column(db.String(100), nullable=False)  # approve_user, reject_product, etc.
    target_type = db.Column(db.String(50), nullable=False)  # user, product, order, etc.
    target_id = db.Column(db.Integer, nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    
    def __repr__(self):
        return f'<AdminAuditLog {self.admin_id}:{self.action}>'

class LoginLog(db.Model):
    """User login tracking"""
    __tablename__ = 'login_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=False)
    user_agent = db.Column(db.Text)
    login_time = db.Column(db.DateTime, default=utc_now, index=True)
    logout_time = db.Column(db.DateTime)
    session_duration = db.Column(db.Integer)  # in minutes
    
    def __repr__(self):
        return f'<LoginLog {self.user_id}:{self.login_time}>'

class SupportTicket(db.Model):
    """Support ticket system"""
    __tablename__ = 'support_tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    ticket_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    subject = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # account, order, product, technical, other
    priority = db.Column(db.String(20), default='normal')  # low, normal, high, urgent
    status = db.Column(db.String(20), default='open')  # open, in_progress, resolved, closed
    message = db.Column(db.Text, nullable=False)
    admin_response = db.Column(db.Text)
    assigned_admin_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    resolved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='support_tickets')
    assigned_admin = db.relationship('User', foreign_keys=[assigned_admin_id], backref='assigned_tickets')
    
    def __repr__(self):
        return f'<SupportTicket {self.ticket_number}>'

class SavedAddress(db.Model):
    """User saved addresses"""
    __tablename__ = 'saved_addresses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    label = db.Column(db.String(50), nullable=False)  # Home, Office, etc.
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address_line_1 = db.Column(db.String(200), nullable=False)
    address_line_2 = db.Column(db.String(200))
    city = db.Column(db.String(50), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    zip_code = db.Column(db.String(10), nullable=False)
    country = db.Column(db.String(50), default='Philippines')
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def __repr__(self):
        return f'<SavedAddress {self.label}:{self.user_id}>'

class PaymentMethod(db.Model):
    """User saved payment methods"""
    __tablename__ = 'payment_methods'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    type = db.Column(db.Enum('credit_card', 'debit_card', 'gcash', 'paymaya', 'bank_transfer'), nullable=False)
    label = db.Column(db.String(50), nullable=False)  # My Visa, GCash Account, etc.
    masked_number = db.Column(db.String(20))  # Last 4 digits for cards, phone for e-wallets
    token = db.Column(db.String(255))  # Encrypted token for secure storage
    is_default = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.Date)  # For cards
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def __repr__(self):
        return f'<PaymentMethod {self.type}:{self.user_id}>'

class TwoFactorAuth(db.Model):
    """Two-factor authentication settings"""
    __tablename__ = 'two_factor_auth'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    is_enabled = db.Column(db.Boolean, default=False)
    method = db.Column(db.Enum('email', 'sms'), default='email')
    phone_number = db.Column(db.String(20))  # For SMS 2FA
    backup_codes = db.Column(db.JSON)  # Array of backup codes
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def __repr__(self):
        return f'<TwoFactorAuth {self.user_id}:{self.method}>'


class PasswordResetToken(db.Model):
    """Password reset tokens for manual password resets"""
    __tablename__ = 'password_reset_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    token = db.Column(db.String(100), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utc_now)

    # Relationships
    user = db.relationship('User', backref=db.backref('reset_tokens', lazy='dynamic'))
    
    def __repr__(self):
        return f'<PasswordResetToken {self.token}>'

class PasswordResetOTP(db.Model):
    """OTP codes for password reset"""
    __tablename__ = 'password_reset_otps'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    otp_code = db.Column(db.String(6), nullable=False)
    delivery_method = db.Column(db.Enum('email', 'sms'), nullable=False)
    contact_info = db.Column(db.String(255), nullable=False)  # Email or phone number
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    attempts = db.Column(db.Integer, default=0)  # Track verification attempts
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('reset_otps', lazy='dynamic'))
    
    def __repr__(self):
        return f'<PasswordResetOTP {self.otp_code}>'

class ProductQuestion(db.Model):
    """Product Q&A - Buyer questions"""
    __tablename__ = 'product_questions'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    question = db.Column(db.Text, nullable=False)
    is_answered = db.Column(db.Boolean, default=False, index=True)
    is_public = db.Column(db.Boolean, default=True)  # Show publicly or private to seller
    helpful_count = db.Column(db.Integer, default=0)  # Upvotes from other buyers
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    product = db.relationship('Product', backref='questions')
    user = db.relationship('User', backref='asked_questions')
    
    def __repr__(self):
        return f'<ProductQuestion {self.id}:{self.product_id}>'

class ProductAnswer(db.Model):
    """Product Q&A - Seller answers"""
    __tablename__ = 'product_answers'
    
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('product_questions.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)  # Seller
    answer = db.Column(db.Text, nullable=False)
    helpful_count = db.Column(db.Integer, default=0)  # Upvotes from buyers
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    question = db.relationship('ProductQuestion', backref='answers')
    user = db.relationship('User', backref='provided_answers')
    
    def __repr__(self):
        return f'<ProductAnswer {self.id}:{self.question_id}>'

class ProductView(db.Model):
    """Track product views for analytics and recommendations"""
    __tablename__ = 'product_views'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)  # Null for anonymous
    session_id = db.Column(db.String(255), index=True)  # For anonymous tracking
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    referrer = db.Column(db.String(500))
    viewed_at = db.Column(db.DateTime, default=utc_now, index=True)
    
    # Relationships
    product = db.relationship('Product', backref='views')
    
    def __repr__(self):
        return f'<ProductView {self.product_id}:{self.user_id}>'

class SearchHistory(db.Model):
    """Track search queries for recommendations and analytics"""
    __tablename__ = 'search_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    session_id = db.Column(db.String(255), index=True)
    query = db.Column(db.String(200), nullable=False, index=True)
    results_count = db.Column(db.Integer, default=0)
    clicked_product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    
    def __repr__(self):
        return f'<SearchHistory {self.query}:{self.user_id}>'

class ProductRecommendation(db.Model):
    """Personalized product recommendations based on user behavior"""
    __tablename__ = 'product_recommendations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    score = db.Column(db.Float, default=0.0)  # Recommendation confidence score
    reason = db.Column(db.String(200))  # Why recommended: 'viewed_similar', 'popular_in_category', etc.
    generated_at = db.Column(db.DateTime, default=utc_now, index=True)
    clicked = db.Column(db.Boolean, default=False)
    purchased = db.Column(db.Boolean, default=False)
    
    # Relationships
    product = db.relationship('Product', backref='recommendations')
    
    __table_args__ = (db.UniqueConstraint('user_id', 'product_id', name='unique_user_product_recommendation'),)
    
    def __repr__(self):
        return f'<ProductRecommendation {self.user_id}:{self.product_id}>'

class SystemAnnouncement(db.Model):
    """System-wide announcements and broadcasts"""
    __tablename__ = 'system_announcements'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    announcement_type = db.Column(db.Enum('maintenance', 'update', 'promotion', 'warning', 'info'), nullable=False)
    target_audience = db.Column(db.Enum('all', 'buyers', 'sellers', 'riders', 'specific'), default='all')
    priority = db.Column(db.Enum('low', 'medium', 'high', 'urgent'), default='medium')
    is_active = db.Column(db.Boolean, default=True, index=True)
    show_on_dashboard = db.Column(db.Boolean, default=True)
    show_as_popup = db.Column(db.Boolean, default=False)
    icon = db.Column(db.String(50))
    color = db.Column(db.String(20))  # For styling the announcement
    start_date = db.Column(db.DateTime, nullable=False, default=utc_now)
    end_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    admin = db.relationship('User', foreign_keys=[admin_id], backref='announcements')
    
    def is_visible(self):
        """Check if announcement is currently visible"""
        now = utc_now()
        if not self.is_active:
            return False
        if now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True
    
    def __repr__(self):
        return f'<SystemAnnouncement {self.title}>'

class RiderAssignment(db.Model):
    """Track rider assignments and availability"""
    __tablename__ = 'rider_assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    rider_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, index=True)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Admin who assigned
    status = db.Column(db.Enum('assigned', 'accepted', 'declined', 'completed', 'failed'), default='assigned', index=True)
    assigned_at = db.Column(db.DateTime, default=utc_now, index=True)
    accepted_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    
    # Relationships
    rider = db.relationship('User', foreign_keys=[rider_id], backref='rider_assignments')
    order = db.relationship('Order', backref='rider_assignment')
    assigner = db.relationship('User', foreign_keys=[assigned_by])
    
    def __repr__(self):
        return f'<RiderAssignment Rider:{self.rider_id} Order:{self.order_id}>'

class DatabaseBackup(db.Model):
    """Track database backups"""
    __tablename__ = 'database_backups'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    backup_type = db.Column(db.Enum('manual', 'automatic', 'scheduled'), default='manual')
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.BigInteger)  # Size in bytes
    status = db.Column(db.Enum('in_progress', 'completed', 'failed'), default='in_progress')
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    
    # Relationships
    admin = db.relationship('User', foreign_keys=[admin_id], backref='database_backups')
    
    def __repr__(self):
        return f'<DatabaseBackup {self.backup_type}:{self.created_at}>'

class UserPreference(db.Model):
    """User UI preferences including dark mode"""
    __tablename__ = 'user_preferences'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    theme = db.Column(db.Enum('light', 'dark', 'auto'), default='light')
    language = db.Column(db.String(10), default='en')
    currency = db.Column(db.String(10), default='USD')
    timezone = db.Column(db.String(50), default='UTC')
    email_notifications = db.Column(db.Boolean, default=True)
    push_notifications = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('preference', uselist=False))
    
    def __repr__(self):
        return f'<UserPreference User:{self.user_id} Theme:{self.theme}>'

# =====================================================
# TEMPLATE CONTEXT PROCESSORS
# =====================================================

@app.context_processor
def inject_user():
    """Make current_user available in all templates"""
    try:
        current_user = get_current_user()
        context = {'current_user': current_user}
        
        # Add pending complaints count for admin users
        if current_user and current_user.role == 'admin':
            try:
                pending_complaints = Complaint.query.filter_by(status='pending').count()
                context['pending_complaints'] = pending_complaints
            except Exception:
                context['pending_complaints'] = 0
        
        return context
    except Exception:
        # If there's any error, return None
        return dict(current_user=None, pending_complaints=0)

@app.context_processor
def inject_platform_settings():
    """Make platform settings available in all templates"""
    try:
        return dict(
            site_name=get_platform_setting('site_name', 'Daily Fitness'),
            site_description=get_platform_setting('site_description', 'Your one stop shop for gym equipment and fitness gear'),
            contact_email=get_platform_setting('contact_email', 'admin@gymstore.com'),
            contact_phone=get_platform_setting('contact_phone', '+63 123 456 7890'),
            commission_rate=get_platform_setting('commission_rate', '5.00'),
            tax_rate=get_platform_setting('tax_rate', '8.00'),
            default_shipping_fee=get_platform_setting('default_shipping_fee', '0.00'),
            free_shipping_threshold=get_platform_setting('free_shipping_threshold', '1000.00'),
            support_email=get_platform_setting('support_email', 'support@gymstore.com')
        )
    except Exception as e:
        print(f"Error loading platform settings: {e}")
        return dict(
            site_name='Daily Fitness',
            site_description='Your one stop shop for gym equipment and fitness gear',
            contact_email='admin@gymstore.com',
            contact_phone='+63 123 456 7890',
            commission_rate='5.00',
            tax_rate='8.00',
            default_shipping_fee='0.00',
            free_shipping_threshold='1000.00',
            support_email='support@gymstore.com'
        )

@app.template_filter('product_slug')
def product_slug_filter(product_name):
    """Template filter to generate product slugs"""
    return generate_product_slug(product_name)

@app.template_filter('profile_image_url')
def profile_image_url_filter(profile_image_path):
    """Template filter to ensure profile images display correctly"""
    if not profile_image_path:
        return None  # Return None so template can show placeholder
    
    # If it's a full URL (OAuth images like Google/Facebook), return as is
    if profile_image_path.startswith('http://') or profile_image_path.startswith('https://'):
        return profile_image_path
    
    # If path already starts with /static, return as is
    if profile_image_path.startswith('/static'):
        return profile_image_path
    
    # If path starts with static (without /), add the /
    if profile_image_path.startswith('static'):
        return '/' + profile_image_path
    
    # Otherwise, assume it's just the filename and construct full path
    return f'/static/uploads/profile_pics/{profile_image_path}'

# =====================================================
# UTILITY FUNCTIONS
# =====================================================

def init_db():
    """Initialize database with tables"""
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")
        # Lightweight schema upgrade: add profile_image to users if missing
        try:
            engine_name = db.engine.dialect.name
            if engine_name == 'sqlite':
                # Check if column exists
                result = db.session.execute("PRAGMA table_info(users)")
                columns = [row[1] for row in result.fetchall()]
                if 'profile_image' not in columns:
                    db.session.execute("ALTER TABLE users ADD COLUMN profile_image VARCHAR(500)")
                    db.session.commit()
                # no-op
                # Cart table upgrades for variant/weight/unit_price uniqueness
                result = db.session.execute("PRAGMA table_info(cart)")
                cart_cols = [row[1] for row in result.fetchall()]
                if 'variant' not in cart_cols:
                    db.session.execute("ALTER TABLE cart ADD COLUMN variant VARCHAR(100)")
                if 'selected_weight' not in cart_cols:
                    db.session.execute("ALTER TABLE cart ADD COLUMN selected_weight VARCHAR(50)")
                if 'unit_price' not in cart_cols:
                    db.session.execute("ALTER TABLE cart ADD COLUMN unit_price NUMERIC(10,2)")
                # Category image_url
                result = db.session.execute("PRAGMA table_info(categories)")
                cat_cols = [row[1] for row in result.fetchall()]
                if 'image_url' not in cat_cols:
                    db.session.execute("ALTER TABLE categories ADD COLUMN image_url VARCHAR(500)")
                    db.session.commit()
                # Recreate unique constraint if old one exists (SQLite can't drop constraints easily; best-effort)
            elif engine_name == 'mysql':
                # Check information_schema for column existence
                current_db = db.engine.url.database
                check_sql = (
                    "SELECT COUNT(*) AS cnt FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = 'users' AND COLUMN_NAME = 'profile_image'"
                )
                res = db.session.execute(text(check_sql), {"schema": current_db}).scalar()
                if not res:
                    db.session.execute(
                        "ALTER TABLE users ADD COLUMN profile_image VARCHAR(500) NULL"
                    )
                    db.session.commit()
                # no-op
                # Add cart columns if missing
                for tbl, col, ddl in [
                    ('cart','variant', "ALTER TABLE cart ADD COLUMN variant VARCHAR(100) NULL"),
                    ('cart','selected_weight', "ALTER TABLE cart ADD COLUMN selected_weight VARCHAR(50) NULL"),
                    ('cart','unit_price', "ALTER TABLE cart ADD COLUMN unit_price DECIMAL(10,2) NULL"),
                    ('categories','image_url', "ALTER TABLE categories ADD COLUMN image_url VARCHAR(500) NULL")
                ]:
                    exists = db.session.execute(
                        text("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=:schema AND TABLE_NAME=:t AND COLUMN_NAME=:c"),
                        {"schema": current_db, "t": tbl, "c": col}
                    ).scalar()
                    if not exists:
                        db.session.execute(text(ddl))
                        db.session.commit()
                # Update unique constraint to include variant and selected_weight
                cons_exists = db.session.execute(
                    text("SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA=:schema AND TABLE_NAME='cart' AND CONSTRAINT_NAME='unique_user_product'"),
                    {"schema": current_db}
                ).scalar()
                if cons_exists:
                    try:
                        db.session.execute(text("ALTER TABLE cart DROP INDEX unique_user_product"))
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                try:
                    db.session.execute(text("ALTER TABLE cart ADD UNIQUE KEY unique_user_product (user_id,product_id,variant,selected_weight)"))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
        except Exception as e:
            db.session.rollback()
            print(f"Schema upgrade note (profile_image): {e}")

def _is_allowed_image(filename: str) -> bool:
    if not filename:
        return False
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_IMAGE_EXTENSIONS

def _is_allowed_document(filename: str) -> bool:
    if not filename:
        return False
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_DOCUMENT_EXTENSIONS

def _save_uploaded_file(file_storage, dest_folder: str, file_type: str = 'image') -> str:
    """
    Upload file to Cloudinary and return the secure URL
    
    Args:
        file_storage: Flask FileStorage object
        dest_folder: Folder name in Cloudinary (e.g., 'products', 'profiles')
        file_type: Type of file ('image' or 'document')
    
    Returns:
        str: Cloudinary secure URL or None if failed
    """
    if not file_storage or file_storage.filename == '':
        return None
    
    # Check file type
    if file_type == 'image':
        if not _is_allowed_image(file_storage.filename):
            raise ValueError('Invalid image format. Allowed: png, jpg, jpeg, gif, webp')
    elif file_type == 'document':
        if not _is_allowed_document(file_storage.filename):
            raise ValueError('Invalid document format. Allowed: pdf, png, jpg, jpeg')
    
    try:
        # Import Cloudinary upload function
        from cloudinary_config import upload_image, is_cloudinary_configured
        
        # Check if Cloudinary is configured
        if not is_cloudinary_configured():
            raise Exception("Cloudinary not configured. Please update credentials in cloudinary_config.py")
        
        # Extract folder name from dest_folder path (e.g., 'static/uploads/products' -> 'products')
        folder_name = dest_folder.split('/')[-1] if '/' in dest_folder else dest_folder
        
        # Upload to Cloudinary
        cloudinary_url = upload_image(file_storage, folder=folder_name)
        
        if cloudinary_url:
            print(f"✅ File uploaded to Cloudinary: {cloudinary_url}")
            return cloudinary_url
        else:
            raise Exception("Cloudinary upload failed")
            
    except Exception as e:
        print(f"❌ Error uploading to Cloudinary: {e}")
        # Fallback to local storage if Cloudinary fails
        print("⚠️ Falling back to local storage...")
        return _save_uploaded_file_local(file_storage, dest_folder, file_type)

def _save_uploaded_file_local(file_storage, dest_folder: str, file_type: str = 'image') -> str:
    """Fallback: Save uploaded file locally and return web-accessible path"""
    if not file_storage or file_storage.filename == '':
        return None
    
    filename = secure_filename(file_storage.filename)
    # Make filename unique
    unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{filename}"
    abs_folder = os.path.join(BASE_DIR, dest_folder)
    os.makedirs(abs_folder, exist_ok=True)
    abs_path = os.path.join(abs_folder, unique_name)
    file_storage.save(abs_path)
    # Convert to web path
    web_path = '/' + os.path.join(dest_folder.replace('\\', '/'), unique_name).replace('\\', '/').replace(BASE_DIR.replace('\\', '/'), '').lstrip('/')
    return web_path

def _compute_weight_multiplier(selected_weight: str) -> float:
    """Compute a price multiplier based on a weight/variant string like '1 lb', '5 lb', '10 lb'. Defaults to 1.0."""
    try:
        if not selected_weight:
            return 1.0
        # extract first number from string
        import re
        m = re.search(r"(\d+(?:\.\d+)?)", str(selected_weight))
        if m:
            return float(m.group(1)) if float(m.group(1)) > 0 else 1.0
    except Exception:
        pass
    return 1.0

def _get_seller_firebase_uid(seller_sql_id: int) -> str:
    """Get seller's Firebase UID from SQL ID for cross-platform sync"""
    try:
        seller = User.query.get(seller_sql_id)
        return seller.firebase_uid if seller and seller.firebase_uid else str(seller_sql_id)
    except Exception:
        return str(seller_sql_id)

def get_platform_setting(key: str, default_value: str = None):
    """Get platform setting value"""
    setting = PlatformSettings.query.filter_by(key=key).first()
    return setting.value if setting else default_value

def set_platform_setting(key: str, value: str, description: str = None):
    """Set platform setting value"""
    setting = PlatformSettings.query.filter_by(key=key).first()
    if setting:
        setting.value = value
        if description:
            setting.description = description
    else:
        setting = PlatformSettings(key=key, value=value, description=description)
        db.session.add(setting)
    db.session.commit()

def calculate_commission(order_amount: float, seller_id: int) -> tuple:
    """Calculate commission for an order"""
    commission_rate = float(get_platform_setting('commission_rate', '5.0'))  # Default 5%
    commission_amount = (order_amount * commission_rate) / 100
    return commission_rate, commission_amount

def reduce_inventory(order_items):
    """Reduce product inventory when order is placed"""
    for item in order_items:
        product = Product.query.get(item.product_id)
        if product:
            product.stock_quantity = max(0, product.stock_quantity - item.quantity)
    db.session.commit()


def send_email_notification(user, title, message, approved):
    """Send email notification (placeholder for actual email service)"""
    try:
        # This is a placeholder - implement with your preferred email service
        # Examples: Flask-Mail, SendGrid, AWS SES, etc.
        
        email_subject = f"Daily Fitness - Account {title}"
        
        if approved:
            email_body = f"""
            Dear {user.first_name} {user.last_name},
            
            Great news! Your {user.role} account has been approved by our admin team.
            
            You can now log in to your account using your credentials:
            - Username: {user.username}
            - Email: {user.email}
            
            Welcome to Daily Fitness!
            
            Best regards,
            Daily Fitness Team
            """
        else:
            email_body = f"""
            Dear {user.first_name} {user.last_name},
            
            We regret to inform you that your {user.role} account registration has been rejected.
            
            If you believe this is an error or need more information, please contact our support team.
            
            Thank you for your interest in Daily Fitness.
            
            Best regards,
            Daily Fitness Team
            """
        
        # Placeholder for actual email sending
        print(f"[EMAIL] TO: {user.email}")
        print(f"[EMAIL] SUBJECT: {email_subject}")
        print(f"[EMAIL] BODY: {email_body}")
        
        # TODO: Implement actual email sending here
        # Example with Flask-Mail:
        # msg = Message(email_subject, recipients=[user.email])
        # msg.body = email_body
        # mail.send(msg)
        
    except Exception as e:
        print(f"Error sending email notification: {e}")

def _generate_secure_token() -> str:
    import secrets
    return secrets.token_urlsafe(48)

def _send_password_reset_email(user, token):
    try:
        reset_link = url_for('reset_password', token=token, _external=True)
        subject = 'Daily Fitness - Password Reset'
        body = f"Hello {user.first_name},\n\nClick the link to reset your password: {reset_link}\nThis link will expire in 1 hour. If you did not request this, please ignore."
        print(f"[EMAIL] PASSWORD RESET TO: {user.email}\nSUBJECT: {subject}\nBODY: {body}")
    except Exception as e:
        print(f"Error sending password reset email: {e}")

def _send_otp_email(user, otp_code):
    """Send OTP code via email"""
    try:
        subject = 'Daily Fitness - Password Reset OTP'
        
        # HTML email body for better presentation
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .otp-code {{ background: white; border: 2px dashed #667eea; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #667eea; margin: 20px 0; border-radius: 8px; }}
                .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
                .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔐 Password Reset</h1>
                </div>
                <div class="content">
                    <p>Hello <strong>{user.first_name}</strong>,</p>
                    <p>You requested to reset your password. Use the OTP code below to continue:</p>
                    <div class="otp-code">{otp_code}</div>
                    <p><strong>This code will expire in 10 minutes.</strong></p>
                    <div class="warning">
                        <strong>⚠️ Security Notice:</strong><br>
                        If you did not request this password reset, please ignore this email and ensure your account is secure.
                    </div>
                    <p>Best regards,<br><strong>Daily Fitness Team</strong></p>
                </div>
                <div class="footer">
                    <p>This is an automated message, please do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text fallback
        text_body = f"""Hello {user.first_name},

Your password reset OTP code is: {otp_code}

This code will expire in 10 minutes.
If you did not request this, please ignore this message and secure your account.

- Daily Fitness Team"""
        
        # Check if email is configured
        if not app.config.get('MAIL_USERNAME'):
            print(f"[EMAIL] Email not configured. OTP Code for {user.email}: {otp_code}")
            print(f"[DEBUG] MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
            print(f"[DEBUG] MAIL_PASSWORD: {'SET' if app.config.get('MAIL_PASSWORD') else 'NOT SET'}")
            return
        
        print(f"[EMAIL] Attempting to send OTP to: {user.email}")
        print(f"[DEBUG] Using SMTP: {app.config.get('MAIL_SERVER')}:{app.config.get('MAIL_PORT')}")
        
        # Send email using Flask-Mail
        msg = MailMessage(
            subject=subject,
            recipients=[user.email],
            body=text_body,
            html=html_body
        )
        mail.send(msg)
        
        print(f"[EMAIL] ✅ OTP sent successfully to: {user.email}")
        
    except Exception as e:
        print(f"[ERROR] ❌ Failed to send OTP email: {e}")
        print(f"[ERROR] Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        # Don't raise exception - allow process to continue even if email fails

def _send_otp_sms(user, otp_code):
    """Send OTP code via SMS"""
    try:
        message = f"Daily Fitness: Your password reset OTP is {otp_code}. Valid for 10 minutes."
        
        print(f"[SMS] OTP TO: {user.phone}")
        print(f"MESSAGE: {message}")
        
        # TODO: Implement actual SMS sending with Twilio or similar service
        # Example:
        # from twilio.rest import Client
        # client = Client(account_sid, auth_token)
        # client.messages.create(
        #     body=message,
        #     from_=twilio_phone,
        #     to=user.phone
        # )
        
    except Exception as e:
        print(f"Error sending OTP SMS: {e}")

# =====================================================
# COMPREHENSIVE NOTIFICATION SYSTEM
# =====================================================

def create_notification(user_id, notification_type, category, title, message, 
                       priority='medium', action_url=None, action_text=None, 
                       data=None, expires_at=None, send_email=True):
    """
    Create a comprehensive notification for a user
    
    Args:
        user_id: Target user ID
        notification_type: Type of notification (system_alert, registration, etc.)
        category: Category (approval, order, payment, etc.)
        title: Notification title
        message: Notification message
        priority: Priority level (low, medium, high, urgent)
        action_url: URL for action button
        action_text: Text for action button
        data: Additional JSON data
        expires_at: Expiration datetime
        send_email: Whether to send email notification
    """
    try:
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            category=category,
            priority=priority,
            title=title,
            message=message,
            action_url=action_url,
            action_text=action_text,
            data=data,
            expires_at=expires_at
        )
        
        db.session.add(notification)
        db.session.commit()
        
        # Send email if requested and user preferences allow
        if send_email:
            send_notification_email(notification)
        
        return notification
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating notification: {e}")
        return None

def send_auto_chat_message(sender_id, receiver_id, message_content):
    """
    Send an automatic chat message between two users
    
    Args:
        sender_id: ID of the sender
        receiver_id: ID of the receiver
        message_content: Content of the message
    """
    try:
        # Find or create conversation
        conversation = Conversation.query.filter(
            db.or_(
                db.and_(Conversation.user1_id == sender_id, Conversation.user2_id == receiver_id),
                db.and_(Conversation.user1_id == receiver_id, Conversation.user2_id == sender_id)
            )
        ).first()
        
        if not conversation:
            conversation = Conversation(
                user1_id=sender_id,
                user2_id=receiver_id
            )
            db.session.add(conversation)
            db.session.flush()
        
        # Create message
        message = Message(
            conversation_id=conversation.id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=message_content,
            is_read=False
        )
        db.session.add(message)
        
        # Update conversation timestamp
        conversation.updated_at = utc_now()
        
        db.session.commit()
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"Error sending auto chat message: {e}")
        return False

def send_product_inquiry_message(buyer_id, seller_id, product_id, product_name):
    """
    Send an automatic product inquiry message from buyer to seller
    Creates conversation if it doesn't exist and sends an intro message
    
    Args:
        buyer_id: ID of the buyer
        seller_id: ID of the seller
        product_id: ID of the product
        product_name: Name of the product
    
    Returns:
        conversation_id if successful, None otherwise
    """
    try:
        # Find or create conversation
        conversation = Conversation.query.filter(
            db.or_(
                db.and_(Conversation.participant1_id == buyer_id, Conversation.participant2_id == seller_id),
                db.and_(Conversation.participant1_id == seller_id, Conversation.participant2_id == buyer_id)
            )
        ).first()
        
        if not conversation:
            conversation = Conversation(
                participant1_id=buyer_id,
                participant2_id=seller_id
            )
            db.session.add(conversation)
            db.session.flush()
        
        # Check if buyer already sent a message about this product
        existing_message = Message.query.filter_by(
            conversation_id=conversation.id,
            sender_id=buyer_id
        ).filter(
            Message.message_content.like(f'%{product_name}%')
        ).first()
        
        # Only send automatic message if no previous message about this product
        if not existing_message:
            # Create automatic intro message
            message_content = f"Hi! I'm interested in your product: {product_name}. Is it still available?"
            
            message = Message(
                conversation_id=conversation.id,
                sender_id=buyer_id,
                receiver_id=seller_id,
                message_content=message_content,
                message_type='text'
            )
            db.session.add(message)
            
            # Update conversation timestamp
            conversation.updated_at = utc_now()
        
        db.session.commit()
        return conversation.id
        
    except Exception as e:
        db.session.rollback()
        print(f"Error sending product inquiry message: {e}")
        import traceback
        traceback.print_exc()
        return None

def log_order_status_change(order_id, user_id, user_role, old_status, new_status, notes=None):
    """
    Log order status changes for audit trail and admin monitoring
    
    Args:
        order_id: Order ID
        user_id: User who made the change
        user_role: Role of user (seller, rider, buyer, admin)
        old_status: Previous status
        new_status: New status
        notes: Optional notes about the change
    """
    try:
        # Create action description
        action_descriptions = {
            'pending': 'Order placed',
            'confirmed': 'Order confirmed by seller',
            'preparing': 'Seller started preparing order',
            'for_pickup': 'Order ready for rider pickup',
            'picked_up': 'Rider picked up order',
            'on_the_way': 'Order is on the way to buyer',
            'delivered': 'Order delivered to buyer',
            'completed': 'Buyer confirmed receipt',
            'cancelled': 'Order cancelled',
            'refunded': 'Order refunded'
        }
        
        action = action_descriptions.get(new_status, f'Status changed to {new_status}')
        
        # Get IP address
        ip_address = request.remote_addr if request else None
        
        # Create log entry
        log = OrderStatusLog(
            order_id=order_id,
            user_id=user_id,
            user_role=user_role,
            old_status=old_status,
            new_status=new_status,
            action=action,
            notes=notes,
            ip_address=ip_address
        )
        
        db.session.add(log)
        
        # Update order's last_status_update
        order = Order.query.get(order_id)
        if order:
            order.last_status_update = utc_now()
        
        db.session.commit()
        
        return log
        
    except Exception as e:
        db.session.rollback()
        print(f"Error logging status change: {e}")
        return None

def get_user_notification_preferences(user_id):
    """Get user notification preferences, create default if not exists"""
    preferences = NotificationPreference.query.filter_by(user_id=user_id).first()
    
    if not preferences:
        # Create default preferences
        preferences = NotificationPreference(user_id=user_id)
        db.session.add(preferences)
        db.session.commit()
    
    return preferences

def should_send_email_notification(user_id, notification_type, category):
    """Check if email notification should be sent based on user preferences"""
    preferences = get_user_notification_preferences(user_id)
    
    if not preferences.email_enabled:
        return False
    
    # Check specific category preferences
    if category in ['order', 'delivery'] and not preferences.email_order_updates:
        return False
    elif category in ['payment', 'payout'] and not preferences.email_financial:
        return False
    elif category == 'general' and notification_type == 'promotion' and not preferences.email_promotions:
        return False
    elif category == 'system' and not preferences.email_system_alerts:
        return False
    
    return True

def send_notification_email(notification):
    """Send email notification based on notification object and user preferences"""
    try:
        user = User.query.get(notification.user_id)
        if not user or not user.email:
            return
        
        # Check user email preferences
        if not should_send_email_notification(notification.user_id, notification.type, notification.category):
            return
        
        # Priority-based email sending
        priority_subjects = {
            'urgent': f"🚨 URGENT - {notification.title}",
            'high': f"🔔 IMPORTANT - {notification.title}",
            'medium': f"Daily Fitness - {notification.title}",
            'low': f"Daily Fitness - {notification.title}"
        }
        
        email_subject = priority_subjects.get(notification.priority, f"Daily Fitness - {notification.title}")
        
        email_body = f"""
        Dear {user.first_name} {user.last_name},
        
        {notification.message}
        
        {f'Action Required: {notification.action_text}' if notification.action_text else ''}
        
        Priority: {notification.priority.upper()}
        Category: {notification.category.title()}
        
        Best regards,
        Daily Fitness Team
        
        ---
        You can manage your notification preferences in your account settings.
        """
        
        # Mark as email sent
        notification.is_email_sent = True
        db.session.commit()
        
        # TODO: Implement actual email sending with Flask-Mail
        print(f"[EMAIL] SENT TO: {user.email}")
        print(f"[EMAIL] SUBJECT: {email_subject}")
        print(f"[EMAIL] PRIORITY: {notification.priority}")
        print(f"[EMAIL] BODY: {email_body}")
        
    except Exception as e:
        print(f"Error sending notification email: {e}")

# =====================================================
# ROLE-SPECIFIC NOTIFICATION FUNCTIONS
# =====================================================

def notify_registration_status(user, approved=True, admin_user=None):
    """Notify user about registration approval/rejection"""
    if approved:
        title = "Registration Approved!"
        message = f"Congratulations! Your {user.role} account has been approved. You can now access all features."
        priority = 'high'
        action_url = url_for('index')
        action_text = "Login Now"
    else:
        title = "Registration Status Update"
        message = f"Your {user.role} registration requires additional review. Please contact support for more information."
        priority = 'high'
        action_url = None
        action_text = None
    
    return create_notification(
        user_id=user.id,
        notification_type='registration',
        category='approval',
        title=title,
        message=message,
        priority=priority,
        action_url=action_url,
        action_text=action_text,
        data={'admin_id': admin_user.id if admin_user else None}
    )

def notify_order_status(order, status_change, user_type='buyer'):
    """Notify about order status changes"""
    status_messages = {
        'pending': 'Your order has been placed and is awaiting seller confirmation.',
        'confirmed': 'Great news! Your order has been confirmed by the seller.',
        'preparing': 'Your order is being prepared for shipment.',
        'picked_up': 'Your order has been picked up by our delivery rider.',
        'on_delivery': 'Your order is on the way! Expected delivery soon.',
        'delivered': 'Your order has been delivered. Please confirm receipt.',
        'completed': 'Thank you! Your order has been completed.',
        'cancelled': 'Your order has been cancelled.',
        'refunded': 'Your order has been refunded.'
    }
    
    if user_type == 'buyer':
        user_id = order.user_id
        title = f"Order #{order.order_number} - {status_change.title()}"
        action_url = url_for('buyer_orders')
        action_text = "View Order"
    elif user_type == 'seller':
        # Get seller from first order item
        first_item = order.order_items.first()
        if not first_item:
            return None
        user_id = first_item.seller_id
        title = f"Order #{order.order_number} - {status_change.title()}"
        action_url = url_for('seller_orders')
        action_text = "View Order"
    else:
        return None
    
    message = status_messages.get(status_change, f"Order status updated to {status_change}")
    priority = 'high' if status_change in ['delivered', 'cancelled'] else 'medium'
    
    return create_notification(
        user_id=user_id,
        notification_type='order_update',
        category='order',
        title=title,
        message=message,
        priority=priority,
        action_url=action_url,
        action_text=action_text,
        data={'order_id': order.id, 'status': status_change}
    )

def notify_new_order(order):
    """Notify seller about new order"""
    # Get all sellers involved in this order
    seller_ids = set()
    for item in order.order_items:
        seller_ids.add(item.seller_id)
    
    notifications = []
    for seller_id in seller_ids:
        notification = create_notification(
            user_id=seller_id,
            notification_type='order_update',
            category='order',
            title=f"New Order Received - #{order.order_number}",
            message=f"You have received a new order worth ₱{order.total_amount}. Please confirm and prepare the items.",
            priority='high',
            action_url=url_for('seller_orders'),
            action_text="View Order",
            data={'order_id': order.id}
        )
        notifications.append(notification)
    
    return notifications

def notify_delivery_assignment(order, rider):
    """Notify rider about new delivery assignment"""
    return create_notification(
        user_id=rider.id,
        notification_type='order_update',
        category='delivery',
        title=f"New Delivery Assignment - #{order.order_number}",
        message=f"You have been assigned a new delivery. Pickup location and details are available.",
        priority='high',
        action_url=url_for('rider_dashboard'),
        action_text="View Delivery",
        data={'order_id': order.id}
    )

def notify_payment_released(seller, order, amount):
    """Notify seller about payment release"""
    return create_notification(
        user_id=seller.id,
        notification_type='financial',
        category='payout',
        title="Payment Released!",
        message=f"Payment of ₱{amount} for order #{order.order_number} has been released to your account.",
        priority='high',
        action_url=url_for('seller_analytics'),
        action_text="View Earnings",
        data={'order_id': order.id, 'amount': str(amount)}
    )

def notify_low_stock(seller, product):
    """Notify seller about low stock"""
    return create_notification(
        user_id=seller.id,
        notification_type='product_update',
        category='stock',
        title="Low Stock Alert",
        message=f"Your product '{product.name}' is running low on stock ({product.stock_quantity} remaining).",
        priority='medium',
        action_url=url_for('seller_products'),
        action_text="Update Stock",
        data={'product_id': product.id, 'stock': product.stock_quantity}
    )

def notify_admin_new_registration(user):
    """Notify admin about new user registration"""
    admin_users = User.query.filter_by(role='admin').all()
    notifications = []
    
    for admin in admin_users:
        notification = create_notification(
            user_id=admin.id,
            notification_type='admin_action',
            category='approval',
            title=f"New {user.role.title()} Registration",
            message=f"{user.first_name} {user.last_name} has registered as a {user.role}. Review required.",
            priority='medium',
            action_url=url_for('admin_approvals'),
            action_text="Review Registration",
            data={'user_id': user.id, 'role': user.role}
        )
        notifications.append(notification)
    
    return notifications

def notify_admin_new_complaint(complaint):
    """Notify admin about new complaint"""
    admin_users = User.query.filter_by(role='admin').all()
    notifications = []
    
    for admin in admin_users:
        notification = create_notification(
            user_id=admin.id,
            notification_type='dispute',
            category='complaint',
            title="New Complaint Received",
            message=f"A new complaint has been submitted regarding order #{complaint.order.order_number}.",
            priority='high',
            action_url=url_for('admin_complaints'),
            action_text="Review Complaint",
            data={'complaint_id': complaint.id}
        )
        notifications.append(notification)
    
    return notifications

def notify_reminder_confirm_receipt(order):
    """Remind buyer to confirm receipt"""
    return create_notification(
        user_id=order.user_id,
        notification_type='reminder',
        category='order',
        title="Confirm Order Receipt",
        message=f"Please confirm that you have received order #{order.order_number}. This helps us release payment to the seller.",
        priority='medium',
        action_url=url_for('buyer_orders'),
        action_text="Confirm Receipt",
        data={'order_id': order.id},
        expires_at=utc_now() + timedelta(days=3)
    )

# =====================================================
# COMPREHENSIVE BUYER NOTIFICATIONS
# =====================================================

def notify_buyer_order_cancelled(order, cancelled_by='seller'):
    """Notify buyer when order is cancelled"""
    if cancelled_by == 'seller':
        message = f"Your order #{order.order_number} has been cancelled by the seller. You will receive a full refund."
        priority = 'high'
    else:
        message = f"Your order #{order.order_number} has been cancelled as requested."
        priority = 'medium'
    
    return create_notification(
        user_id=order.user_id,
        notification_type='order_update',
        category='order',
        title=f"Order #{order.order_number} Cancelled",
        message=message,
        priority=priority,
        action_url=url_for('buyer_orders'),
        action_text="View Order",
        data={'order_id': order.id, 'cancelled_by': cancelled_by}
    )

def notify_buyer_refund_status(order, refund_status, amount=None):
    """Notify buyer about refund status"""
    status_messages = {
        'processing': f"Your refund request for order #{order.order_number} is being processed.",
        'approved': f"Your refund of ₱{amount} for order #{order.order_number} has been approved and will be processed within 3-5 business days.",
        'completed': f"Your refund of ₱{amount} for order #{order.order_number} has been completed.",
        'rejected': f"Your refund request for order #{order.order_number} has been rejected. Please contact support for more information."
    }
    
    priority = 'high' if refund_status in ['approved', 'completed'] else 'medium'
    
    return create_notification(
        user_id=order.user_id,
        notification_type='financial',
        category='payment',
        title=f"Refund {refund_status.title()} - Order #{order.order_number}",
        message=status_messages.get(refund_status, f"Refund status updated: {refund_status}"),
        priority=priority,
        action_url=url_for('buyer_orders'),
        action_text="View Order",
        data={'order_id': order.id, 'refund_status': refund_status, 'amount': str(amount) if amount else None}
    )

def notify_buyer_promotion(user, promotion_title, promotion_message, action_url=None):
    """Notify buyer about promotions and announcements"""
    return create_notification(
        user_id=user.id,
        notification_type='promotion',
        category='general',
        title=promotion_title,
        message=promotion_message,
        priority='low',
        action_url=action_url,
        action_text="View Promotion" if action_url else None,
        expires_at=utc_now() + timedelta(days=30)
    )

# =====================================================
# COMPREHENSIVE SELLER NOTIFICATIONS
# =====================================================

def notify_seller_order_cancelled_by_buyer(order, seller_id):
    """Notify seller when buyer cancels order"""
    return create_notification(
        user_id=seller_id,
        notification_type='order_update',
        category='order',
        title=f"Order #{order.order_number} Cancelled by Buyer",
        message=f"The buyer has cancelled order #{order.order_number} worth ₱{order.total_amount}. No action required.",
        priority='medium',
        action_url=url_for('seller_orders'),
        action_text="View Orders",
        data={'order_id': order.id}
    )

def notify_seller_buyer_confirmed_receipt(order, seller_id, profit_amount):
    """Notify seller when buyer confirms receipt and profit is released"""
    return create_notification(
        user_id=seller_id,
        notification_type='financial',
        category='payout',
        title="Payment Released - Order Completed!",
        message=f"Buyer confirmed receipt of order #{order.order_number}. Your profit of ₱{profit_amount} has been released to your account.",
        priority='high',
        action_url=url_for('seller_analytics'),
        action_text="View Earnings",
        data={'order_id': order.id, 'profit_amount': str(profit_amount)}
    )

def notify_seller_commission_deduction(seller, order, commission_amount, commission_rate):
    """Notify seller about commission deduction"""
    return create_notification(
        user_id=seller.id,
        notification_type='financial',
        category='payout',
        title="Commission Report",
        message=f"Commission of ₱{commission_amount} ({commission_rate}%) has been deducted from order #{order.order_number}.",
        priority='medium',
        action_url=url_for('seller_analytics'),
        action_text="View Report",
        data={'order_id': order.id, 'commission_amount': str(commission_amount), 'commission_rate': str(commission_rate)}
    )

def notify_seller_violation_warning(seller, violation_type, warning_message, admin_user):
    """Notify seller about violations or warnings"""
    return create_notification(
        user_id=seller.id,
        notification_type='warning',
        category='system',
        title=f"Warning: {violation_type}",
        message=warning_message,
        priority='urgent',
        action_url=url_for('seller_dashboard'),
        action_text="View Details",
        data={'violation_type': violation_type, 'admin_id': admin_user.id}
    )

def notify_seller_warning(warning):
    """Comprehensive notification for seller warnings"""
    severity_priority = {
        'low': 'medium',
        'medium': 'high', 
        'high': 'urgent',
        'critical': 'urgent'
    }
    
    # Create notification title based on offense level
    if warning.offense_level >= 3:
        title = f"🚨 FINAL WARNING: {warning.title}"
        priority = 'urgent'
    elif warning.severity == 'critical':
        title = f"🔴 CRITICAL WARNING: {warning.title}"
        priority = 'urgent'
    else:
        title = f"⚠️ Warning ({warning.get_offense_label()}): {warning.title}"
        priority = severity_priority.get(warning.severity, 'high')
    
    # Create detailed message
    message = f"""
    <strong>Warning Type:</strong> {warning.warning_type.replace('_', ' ').title()}<br>
    <strong>Severity:</strong> {warning.severity.title()}<br>
    <strong>Offense Level:</strong> {warning.get_offense_label()}<br>
    <strong>Issued by:</strong> Admin {warning.admin.first_name} {warning.admin.last_name}<br><br>
    
    <strong>Details:</strong><br>
    {warning.message}
    
    {f'<br><br><strong>Action Required:</strong><br>{warning.action_required}' if warning.action_required else ''}
    {f'<br><br><strong>Deadline:</strong> {warning.deadline.strftime("%B %d, %Y at %I:%M %p")}' if warning.deadline else ''}
    """
    
    # Determine action URL and text
    action_url = url_for('seller_warnings')
    action_text = "View Warning Details"
    
    if warning.is_critical():
        action_text = "URGENT: View Warning"
    
    return create_notification(
        user_id=warning.seller_id,
        notification_type='warning',
        category='system',
        title=title,
        message=message,
        priority=priority,
        action_url=action_url,
        action_text=action_text,
        data={
            'warning_id': warning.id,
            'warning_type': warning.warning_type,
            'severity': warning.severity,
            'offense_level': warning.offense_level,
            'admin_id': warning.admin_id,
            'is_critical': warning.is_critical()
        },
        send_email=True
    )

def create_seller_warning(seller_id, admin_id, warning_type, title, message, 
                         severity='medium', action_required=None, deadline=None, 
                         policy_link=None, admin_notes=None):
    """Create a new seller warning with automatic offense level tracking"""
    try:
        # Calculate offense level
        previous_warnings = SellerWarning.query.filter_by(
            seller_id=seller_id,
            warning_type=warning_type
        ).count()
        
        offense_level = previous_warnings + 1
        
        # Create warning record
        warning = SellerWarning(
            seller_id=seller_id,
            admin_id=admin_id,
            warning_type=warning_type,
            severity=severity,
            offense_level=offense_level,
            title=title,
            message=message,
            action_required=action_required,
            deadline=deadline,
            policy_link=policy_link,
            admin_notes=admin_notes
        )
        
        db.session.add(warning)
        db.session.commit()
        
        # Send notification
        notification = notify_seller_warning(warning)
        
        # Log admin action
        log_admin_action(
            admin_id=admin_id,
            action='issue_warning',
            target_type='seller',
            target_id=seller_id,
            details=f"Issued {severity} warning for {warning_type}: {title}"
        )
        
        return warning, notification
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating seller warning: {e}")
        return None, None

# =====================================================
# BUYER WARNING NOTIFICATION SYSTEM
# =====================================================

def notify_buyer_warning(warning):
    """Comprehensive notification for buyer warnings"""
    severity_priority = {
        'low': 'medium',
        'medium': 'high', 
        'high': 'urgent',
        'critical': 'urgent'
    }
    
    # Create notification title based on offense level
    if warning.offense_level >= 3:
        title = f"🚨 FINAL WARNING: {warning.title}"
        priority = 'urgent'
    elif warning.severity == 'critical':
        title = f"🔴 CRITICAL WARNING: {warning.title}"
        priority = 'urgent'
    else:
        title = f"⚠️ Warning ({warning.get_offense_label()}): {warning.title}"
        priority = severity_priority.get(warning.severity, 'high')
    
    # Create detailed message
    message = f"""
    <strong>Warning Type:</strong> {warning.warning_type.replace('_', ' ').title()}<br>
    <strong>Severity:</strong> {warning.severity.title()}<br>
    <strong>Offense Level:</strong> {warning.get_offense_label()}<br>
    <strong>Issued by:</strong> Admin {warning.admin.first_name} {warning.admin.last_name}<br><br>
    
    <strong>Details:</strong><br>
    {warning.message}
    
    {f'<br><br><strong>Action Required:</strong><br>{warning.action_required}' if warning.action_required else ''}
    {f'<br><br><strong>Deadline:</strong> {warning.deadline.strftime("%B %d, %Y at %I:%M %p")}' if warning.deadline else ''}
    """
    
    # Determine action URL and text
    action_url = url_for('buyer_warnings')
    action_text = "View Warning Details"
    
    if warning.is_critical():
        action_text = "URGENT: View Warning"
    
    return create_notification(
        user_id=warning.buyer_id,
        notification_type='warning',
        category='system',
        title=title,
        message=message,
        priority=priority,
        action_url=action_url,
        action_text=action_text,
        data={
            'warning_id': warning.id,
            'warning_type': warning.warning_type,
            'severity': warning.severity,
            'offense_level': warning.offense_level,
            'admin_id': warning.admin_id,
            'is_critical': warning.is_critical()
        },
        send_email=True
    )

def create_buyer_warning(buyer_id, admin_id, warning_type, title, message, 
                        severity='medium', action_required=None, deadline=None, 
                        policy_link=None, admin_notes=None):
    """Create a new buyer warning with automatic offense level tracking"""
    try:
        # Calculate offense level
        previous_warnings = BuyerWarning.query.filter_by(
            buyer_id=buyer_id,
            warning_type=warning_type
        ).count()
        
        offense_level = previous_warnings + 1
        
        # Create warning record
        warning = BuyerWarning(
            buyer_id=buyer_id,
            admin_id=admin_id,
            warning_type=warning_type,
            severity=severity,
            offense_level=offense_level,
            title=title,
            message=message,
            action_required=action_required,
            deadline=deadline,
            policy_link=policy_link,
            admin_notes=admin_notes
        )
        
        db.session.add(warning)
        db.session.commit()
        
        # Send notification
        notification = notify_buyer_warning(warning)
        
        # Log admin action
        log_admin_action(
            admin_id=admin_id,
            action='issue_buyer_warning',
            target_type='buyer',
            target_id=buyer_id,
            details=f"Issued {severity} warning for {warning_type}: {title}"
        )
        
        return warning, notification
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating buyer warning: {e}")
        return None, None

# =====================================================
# COMPREHENSIVE RIDER NOTIFICATIONS
# =====================================================

def notify_rider_pickup_available(rider, order, pickup_location):
    """Notify rider about new pickup available"""
    return create_notification(
        user_id=rider.id,
        notification_type='order_update',
        category='delivery',
        title="New Pickup Available",
        message=f"New delivery assignment for order #{order.order_number}. Pickup location: {pickup_location}",
        priority='high',
        action_url=url_for('rider_dashboard'),
        action_text="View Assignment",
        data={'order_id': order.id, 'pickup_location': pickup_location}
    )

def notify_rider_delivery_confirmed(rider, order):
    """Notify rider when delivery assignment is confirmed"""
    return create_notification(
        user_id=rider.id,
        notification_type='order_update',
        category='delivery',
        title="Delivery Assignment Confirmed",
        message=f"You have been assigned to deliver order #{order.order_number}. Please proceed to pickup location.",
        priority='high',
        action_url=url_for('rider_dashboard'),
        action_text="Start Delivery",
        data={'order_id': order.id}
    )

def notify_rider_status_update_required(rider, order, current_status):
    """Notify rider to update delivery status"""
    status_actions = {
        'picked_up': 'Mark as On the Way',
        'on_delivery': 'Mark as Delivered'
    }
    
    return create_notification(
        user_id=rider.id,
        notification_type='reminder',
        category='delivery',
        title="Status Update Required",
        message=f"Please update the status of order #{order.order_number} to the next stage.",
        priority='medium',
        action_url=url_for('rider_dashboard'),
        action_text=status_actions.get(current_status, "Update Status"),
        data={'order_id': order.id, 'current_status': current_status},
        expires_at=utc_now() + timedelta(hours=2)
    )

def notify_rider_commission_payout(rider, period, total_commission, order_count):
    """Notify rider about commission payout"""
    return create_notification(
        user_id=rider.id,
        notification_type='financial',
        category='payout',
        title="Commission Payout Summary",
        message=f"Your {period} commission of ₱{total_commission} for {order_count} deliveries has been calculated.",
        priority='high',
        action_url=url_for('rider_dashboard'),
        action_text="View Earnings",
        data={'period': period, 'total_commission': str(total_commission), 'order_count': order_count}
    )

def notify_rider_violation_warning(rider, violation_type, warning_message, admin_user):
    """Notify rider about violations or warnings"""
    return create_notification(
        user_id=rider.id,
        notification_type='warning',
        category='system',
        title=f"Warning: {violation_type}",
        message=warning_message,
        priority='urgent',
        action_url=url_for('rider_dashboard'),
        action_text="View Details",
        data={'violation_type': violation_type, 'admin_id': admin_user.id}
    )

# =====================================================
# COMPREHENSIVE ADMIN NOTIFICATIONS
# =====================================================

def notify_admin_complaint_filed(complaint, user):
    """Notify admin when a complaint is filed"""
    admin_users = User.query.filter_by(role='admin').all()
    notifications = []
    
    for admin in admin_users:
        notification = create_notification(
            user_id=admin.id,
            notification_type='dispute',
            category='complaint',
            title="New Complaint Filed",
            message=f"User {user.first_name} {user.last_name} has filed a complaint regarding order #{complaint.order.order_number}.",
            priority='high',
            action_url=url_for('admin_complaints'),
            action_text="Review Complaint",
            data={'complaint_id': complaint.id, 'user_id': user.id}
        )
        notifications.append(notification)
    
    return notifications

def notify_admin_dispute_escalation(dispute, escalated_by):
    """Notify admin about dispute escalation"""
    admin_users = User.query.filter_by(role='admin').all()
    notifications = []
    
    for admin in admin_users:
        notification = create_notification(
            user_id=admin.id,
            notification_type='dispute',
            category='complaint',
            title="Dispute Escalation Request",
            message=f"A dispute has been escalated by {escalated_by.first_name} {escalated_by.last_name}. Immediate attention required.",
            priority='urgent',
            action_url=url_for('admin_complaints'),
            action_text="Handle Dispute",
            data={'dispute_id': dispute.id, 'escalated_by': escalated_by.id}
        )
        notifications.append(notification)
    
    return notifications

def notify_admin_low_stock_alert(product, seller):
    """Notify admin about low stock from sellers"""
    admin_users = User.query.filter_by(role='admin').all()
    notifications = []
    
    for admin in admin_users:
        notification = create_notification(
            user_id=admin.id,
            notification_type='system_alert',
            category='stock',
            title="Low Stock Alert",
            message=f"Product '{product.name}' by {seller.business_name} is critically low in stock ({product.stock_quantity} remaining).",
            priority='medium',
            action_url=url_for('admin_dashboard'),
            action_text="View Products",
            data={'product_id': product.id, 'seller_id': seller.id, 'stock_quantity': product.stock_quantity}
        )
        notifications.append(notification)
    
    return notifications

def notify_admin_revenue_milestone(period, total_revenue, commission_earned, milestone_type):
    """Notify admin about revenue milestones"""
    admin_users = User.query.filter_by(role='admin').all()
    notifications = []
    
    for admin in admin_users:
        notification = create_notification(
            user_id=admin.id,
            notification_type='financial',
            category='system',
            title=f"{milestone_type} Revenue Report",
            message=f"{period} summary: Total revenue ₱{total_revenue}, Commission earned ₱{commission_earned}.",
            priority='low',
            action_url=url_for('admin_analytics'),
            action_text="View Report",
            data={'period': period, 'total_revenue': str(total_revenue), 'commission_earned': str(commission_earned)},
            expires_at=utc_now() + timedelta(days=7)
        )
        notifications.append(notification)
    
    return notifications

def notify_admin_system_error(error_type, error_message, affected_component):
    """Notify admin about system errors"""
    admin_users = User.query.filter_by(role='admin').all()
    notifications = []
    
    for admin in admin_users:
        notification = create_notification(
            user_id=admin.id,
            notification_type='system_alert',
            category='system',
            title=f"System Error: {error_type}",
            message=f"Error in {affected_component}: {error_message}",
            priority='urgent',
            action_url=url_for('admin_dashboard'),
            action_text="Check System",
            data={'error_type': error_type, 'affected_component': affected_component}
        )
        notifications.append(notification)
    
    return notifications

def log_admin_action(admin_id, action, target_type, target_id, details=None):
    """Log admin actions for audit trail"""
    try:
        audit_log = AdminAuditLog(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get('User-Agent') if request else None
        )
        db.session.add(audit_log)
        db.session.commit()
    except Exception as e:
        print(f"Error logging admin action: {e}")

def log_user_login(user_id, ip_address, user_agent):
    """Log user login for security tracking"""
    try:
        login_log = LoginLog(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.session.add(login_log)
        db.session.commit()
        return login_log.id
    except Exception as e:
        print(f"Error logging user login: {e}")
        return None

def generate_ticket_number():
    """Generate unique ticket number for complaints"""
    import random
    import string
    while True:
        ticket = 'TKT' + ''.join(random.choices(string.digits, k=7))
        if not Complaint.query.filter_by(ticket_number=ticket).first():
            return ticket

def get_user_violation_level(user_id):
    """Get user's current violation level"""
    violations = UserViolation.query.filter_by(user_id=user_id, is_active=True).all()
    
    severe_count = sum(1 for v in violations if v.violation_type == 'severe')
    major_count = sum(1 for v in violations if v.violation_type == 'major')
    minor_count = sum(1 for v in violations if v.violation_type == 'minor')
    warning_count = sum(1 for v in violations if v.violation_type == 'warning')
    
    if severe_count >= 1:
        return 'banned'
    elif major_count >= 3:
        return 'suspended'
    elif major_count >= 1 or minor_count >= 3:
        return 'warning'
    else:
        return 'good'

def get_dashboard_analytics():
    """Get comprehensive dashboard analytics"""
    from datetime import timedelta
    
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Basic stats
    total_users = User.query.filter_by(approval_status='approved').count()
    total_buyers = User.query.filter_by(role='buyer', approval_status='approved').count()
    total_sellers = User.query.filter_by(role='seller', approval_status='approved').count()
    total_riders = User.query.filter_by(role='rider', approval_status='approved').count()
    
    # Order stats
    total_orders = Order.query.count()
    completed_orders = Order.query.filter_by(status='completed').count()
    pending_orders = Order.query.filter(Order.status.in_(['pending', 'confirmed', 'preparing'])).count()
    
    # Revenue stats
    total_revenue = db.session.query(db.func.sum(Order.total_amount)).filter(Order.status == 'completed').scalar() or 0
    monthly_revenue = db.session.query(db.func.sum(Order.total_amount)).filter(
        Order.status == 'completed',
        Order.created_at >= month_ago
    ).scalar() or 0
    
    # Commission stats
    total_commissions = db.session.query(db.func.sum(Commission.commission_amount)).filter(Commission.status == 'collected').scalar() or 0
    pending_commissions = db.session.query(db.func.sum(Commission.commission_amount)).filter(Commission.status == 'pending').scalar() or 0
    
    # Product stats
    total_products = Product.query.filter_by(is_active=True).count()
    low_stock_products = Product.query.filter(Product.stock_quantity <= 5, Product.is_active == True).count()
    
    # Recent activity
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    recent_registrations = User.query.filter_by(approval_status='pending').order_by(User.created_at.desc()).limit(5).all()
    
    # Complaints
    open_complaints = Complaint.query.filter_by(status='open').count()
    urgent_complaints = Complaint.query.filter_by(status='open', priority='urgent').count()
    
    return {
        'users': {
            'total': total_users,
            'buyers': total_buyers,
            'sellers': total_sellers,
            'riders': total_riders
        },
        'orders': {
            'total': total_orders,
            'completed': completed_orders,
            'pending': pending_orders
        },
        'revenue': {
            'total': float(total_revenue),
            'monthly': float(monthly_revenue),
            'commissions_collected': float(total_commissions),
            'commissions_pending': float(pending_commissions)
        },
        'products': {
            'total': total_products,
            'low_stock': low_stock_products
        },
        'complaints': {
            'open': open_complaints,
            'urgent': urgent_complaints
        },
        'recent': {
            'orders': recent_orders,
            'registrations': recent_registrations
        }
    }

def auto_confirm_orders():
    """Auto-confirm orders that have been delivered for 7+ days without buyer confirmation"""
    from datetime import timedelta
    
    cutoff_date = utc_now() - timedelta(days=7)
    
    # Find delivered orders older than 7 days that haven't been completed
    orders_to_confirm = Order.query.filter(
        Order.status == 'delivered',
        Order.delivered_at <= cutoff_date,
        Order.auto_confirmed_at.is_(None)
    ).all()
    
    for order in orders_to_confirm:
        try:
            # Mark as completed and track auto-confirmation
            order.status = 'completed'
            order.payment_status = 'paid'
            order.auto_confirmed_at = utc_now()
            
            # Update seller statistics (same logic as manual confirmation)
            confirm_date = order.delivered_at.date()
            order_items = OrderItem.query.filter_by(order_id=order.id).all()
            seller_ids = {oi.seller_id for oi in order_items}
            
            for sid in seller_ids:
                seller_sum = sum(float(oi.total_price) for oi in order_items if oi.seller_id == sid)
                stats = SellerStatistics.query.filter_by(seller_id=sid, date=confirm_date).first()
                if not stats:
                    stats = SellerStatistics(
                        seller_id=sid,
                        date=confirm_date,
                        total_products=0,
                        total_orders=0,
                        total_revenue=0,
                        total_views=0,
                    )
                    db.session.add(stats)
                stats.total_orders = (stats.total_orders or 0) + 1
                stats.total_revenue = (stats.total_revenue or Decimal('0')) + Decimal(str(seller_sum))
            
            # Collect commissions when auto-confirmed
            commissions = Commission.query.filter_by(order_id=order.id, status='pending').all()
            for commission in commissions:
                commission.status = 'collected'
            
            db.session.commit()
            print(f"Auto-confirmed order {order.order_number}")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error auto-confirming order {order.order_number}: {e}")

def seed_database():
    """Seed database with initial data"""
    with app.app_context():
        # Create default categories only if none exist
        categories = [
            Category(name='Weights', description='Dumbbells, barbells, and weight plates'),
            Category(name='Cardio Equipment', description='Treadmills, bikes, and rowing machines'),
            Category(name='Protein Supplements', description='Protein powders, bars, and shakes'),
            Category(name='Supplements', description='Creatine, vitamins, and performance boosters'),
            Category(name='Accessories', description='Mats, bands, and workout accessories'),
            Category(name='Clothing', description='Workout clothes and athletic wear')
        ]
        
        if Category.query.count() == 0:
            for category in categories:
                db.session.add(category)
            db.session.commit()
            print("Default categories created!")
            
        # Create default admin user if none exists
        if not User.query.filter_by(role='admin').first():
            admin = User(
                username='admin',
                email='admin@gymstore.com',
                first_name='System',
                last_name='Administrator',
                role='admin',
                approval_status='approved',
                is_active=True,
                email_verified=True
            )
            admin.set_password('admin123')  # Change this in production
            db.session.add(admin)
            db.session.commit()
            print("Default admin user created! Username: admin, Password: admin123")
            
        # Create default platform settings
        default_settings = [
            ('commission_rate', '5.0', 'Platform commission percentage (default 5%)'),
            ('auto_confirm_days', '7', 'Days after delivery to auto-confirm orders'),
            ('platform_name', 'Daily Fitness', 'Platform name'),
            ('support_email', 'support@gymstore.com', 'Support contact email'),
            ('max_file_size', '10', 'Maximum file upload size in MB')
        ]
        
        for key, value, description in default_settings:
            if not PlatformSettings.query.filter_by(key=key).first():
                setting = PlatformSettings(key=key, value=value, description=description)
                db.session.add(setting)
        
        db.session.commit()
        print("Default platform settings created!")

# ==================== ROUTES ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form.get('username')
        password = request.form.get('password')
        remember_me = bool(request.form.get('remember_me'))

        # Check if input is email or username
        user = User.query.filter(
            or_(User.username == username_or_email, User.email == username_or_email)
        ).first()

        password_valid = False
        firebase_auth_used = False
        
        if user:
            try:
                password_valid = user.check_password(password)
            except ValueError as e:
                if user.role == 'admin' and "Invalid hash method ''" in str(e):
                    try:
                        print("Admin password hash is invalid. Resetting to default 'admin123'.")
                        user.set_password('admin123')
                        db.session.commit()
                        # Retry login check after password reset
                        password_valid = user.check_password(password)
                        if password_valid:
                            flash('Admin password was reset. You are now logged in.', 'info')
                    except Exception as db_e:
                        db.session.rollback()
                        flash('A database error occurred during admin password recovery. Please try again.', 'error')
                        print(f"DB error during admin password reset: {db_e}")
                else:
                    flash('An unexpected error occurred. Please try again.', 'error')
                    print(f"Login ValueError: {e}")
            
            # If SQL password check failed and user has firebase_uid, try Firebase authentication
            if not password_valid and user.firebase_uid and _firebase_initialized:
                try:
                    import requests
                    
                    # Firebase REST API endpoint for password authentication
                    firebase_api_key = "AIzaSyBR433ttG5Ly8vY1vJ4og5ujhoBGlcAO74"
                    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}"
                    
                    payload = {
                        "email": user.email,
                        "password": password,
                        "returnSecureToken": True
                    }
                    
                    response = requests.post(url, json=payload)
                    
                    if response.status_code == 200:
                        # Firebase authentication successful
                        password_valid = True
                        firebase_auth_used = True
                        print(f"✅ Firebase authentication successful for {user.email}")
                        
                        # Update SQL password hash so next login is faster
                        try:
                            user.set_password(password)
                            db.session.commit()
                            print(f"✅ Updated SQL password for {user.email}")
                        except Exception as update_error:
                            db.session.rollback()
                            print(f"⚠️ Could not update SQL password: {update_error}")
                    else:
                        print(f"❌ Firebase authentication failed for {user.email}: {response.text}")
                        
                except Exception as firebase_error:
                    print(f"⚠️ Firebase authentication error: {firebase_error}")
                    # Continue with SQL authentication result

        if user and password_valid:
            if user.approval_status != 'approved':
                if user.approval_status == 'pending':
                    flash('Your account is under review. Please wait for admin approval.', 'warning')
                elif user.approval_status == 'rejected':
                    flash('Your registration has been disapproved. Please contact support.', 'error')
                else:
                    flash('Your account status is unclear. Please contact support.', 'error')
                return render_template('index.html')

            if not user.is_active:
                flash('Your account has been deactivated. Please contact support.', 'error')
                return render_template('index.html')

            # All checks passed, proceed with login
            log_user_login(user.id, request.remote_addr, request.headers.get('User-Agent'))

            session['user_id'] = user.id
            session['user_role'] = user.role
            session.permanent = remember_me

            if not get_flashed_messages():
                flash(f'Welcome back, {user.first_name}!', 'success')

            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'seller':
                return redirect(url_for('seller_dashboard'))
            elif user.role == 'rider':
                return redirect(url_for('rider_dashboard'))
            else:  # buyer
                return redirect(url_for('buyer_home'))
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('index.html')

@app.route('/', methods=['GET', 'POST'])
def index():
    """Landing page with login form"""
    if request.method == 'POST':
        username_or_email = request.form.get('username')
        password = request.form.get('password')
        remember_me = bool(request.form.get('remember_me'))

        # Check if input is email or username
        user = User.query.filter(
            or_(User.username == username_or_email, User.email == username_or_email)
        ).first()

        password_valid = False
        firebase_auth_used = False
        
        if user:
            try:
                password_valid = user.check_password(password)
            except ValueError as e:
                if user.role == 'admin' and "Invalid hash method ''" in str(e):
                    try:
                        print("Admin password hash is invalid. Resetting to default 'admin123'.")
                        user.set_password('admin123')
                        db.session.commit()
                        # Retry login check after password reset
                        password_valid = user.check_password(password)
                        if password_valid:
                            flash('Admin password was reset. You are now logged in.', 'info')
                    except Exception as db_e:
                        db.session.rollback()
                        flash('A database error occurred during admin password recovery. Please try again.', 'error')
                        print(f"DB error during admin password reset: {db_e}")
                else:
                    flash('An unexpected error occurred. Please try again.', 'error')
                    print(f"Login ValueError: {e}")
            
            # If SQL password check failed and user has firebase_uid, try Firebase authentication
            if not password_valid and user.firebase_uid and _firebase_initialized:
                try:
                    import requests
                    
                    # Firebase REST API endpoint for password authentication
                    firebase_api_key = "AIzaSyBR433ttG5Ly8vY1vJ4og5ujhoBGlcAO74"
                    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}"
                    
                    payload = {
                        "email": user.email,
                        "password": password,
                        "returnSecureToken": True
                    }
                    
                    response = requests.post(url, json=payload)
                    
                    if response.status_code == 200:
                        # Firebase authentication successful
                        password_valid = True
                        firebase_auth_used = True
                        print(f"✅ Firebase authentication successful for {user.email}")
                        
                        # Update SQL password hash so next login is faster
                        try:
                            user.set_password(password)
                            db.session.commit()
                            print(f"✅ Updated SQL password for {user.email}")
                        except Exception as update_error:
                            db.session.rollback()
                            print(f"⚠️ Could not update SQL password: {update_error}")
                    else:
                        print(f"❌ Firebase authentication failed for {user.email}: {response.text}")
                        
                except Exception as firebase_error:
                    print(f"⚠️ Firebase authentication error: {firebase_error}")
                    # Continue with SQL authentication result

        if user and password_valid:
            if user.approval_status != 'approved':
                if user.approval_status == 'pending':
                    flash('Your account is under review. Please wait for admin approval.', 'warning')
                elif user.approval_status == 'rejected':
                    flash('Your registration has been disapproved. Please contact support.', 'error')
                else:
                    flash('Your account status is unclear. Please contact support.', 'error')
                return render_template('index.html')

            if not user.is_active:
                flash('Your account has been deactivated. Please contact support.', 'error')
                return render_template('index.html')

            # All checks passed, proceed with login
            log_user_login(user.id, request.remote_addr, request.headers.get('User-Agent'))

            session['user_id'] = user.id
            session['user_role'] = user.role
            session.permanent = remember_me

            if not get_flashed_messages():
                flash(f'Welcome back, {user.first_name}!', 'success')

            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'seller':
                return redirect(url_for('seller_dashboard'))
            elif user.role == 'rider':
                return redirect(url_for('rider_dashboard'))
            else:  # buyer
                return redirect(url_for('buyer_home'))
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('index.html')

@app.route('/terms')
def terms():
    """Terms and Conditions page"""
    commission_rate = get_platform_setting('commission_rate', '5.0')
    support_email = get_platform_setting('support_email', 'support@gymstore.com')
    current_date = datetime.now().strftime('%B %d, %Y')
    
    return render_template('terms.html', 
                         commission_rate=commission_rate,
                         support_email=support_email,
                         current_date=current_date)

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Step 1: Request OTP for password reset"""
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        delivery_method = request.form.get('delivery_method', 'email')
        
        if not identifier:
            flash('Please enter your email or username.', 'warning')
            return render_template('auth/forgot_password.html')
        
        user = User.query.filter((User.email == identifier) | (User.username == identifier)).first()
        
        if not user:
            # Security: Don't reveal if user exists
            flash('If the account exists, an OTP code will be sent.', 'info')
            return render_template('auth/forgot_password.html')
        
        try:
            # Generate 6-digit OTP
            import random
            otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            
            # Determine contact info based on delivery method
            if delivery_method == 'email':
                contact_info = user.email
            else:  # sms
                contact_info = user.phone if user.phone else user.email
                if not user.phone:
                    flash('No phone number on file. OTP will be sent to email.', 'info')
                    delivery_method = 'email'
            
            # Delete old unused OTPs for this user
            PasswordResetOTP.query.filter_by(user_id=user.id, used=False).delete()
            
            # Create new OTP
            otp = PasswordResetOTP(
                user_id=user.id,
                otp_code=otp_code,
                delivery_method=delivery_method,
                contact_info=contact_info,
                expires_at=utc_now_naive() + timedelta(minutes=10),  # 10 minute expiry
                used=False
            )
            db.session.add(otp)
            db.session.commit()
            
            # Send OTP
            if delivery_method == 'email':
                _send_otp_email(user, otp_code)
            else:
                _send_otp_sms(user, otp_code)
            
            # Store user_id in session for verification step
            session['reset_user_id'] = user.id
            session['reset_delivery_method'] = delivery_method
            
            flash(f'An OTP code has been sent to your {delivery_method}.', 'success')
            return redirect(url_for('verify_otp'))
            
        except Exception as e:
            db.session.rollback()
            flash('Could not initiate password reset. Please try again later.', 'error')
            print(f"Forgot password error: {e}")
    
    return render_template('auth/forgot_password.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    """Step 2: Verify OTP code"""
    if 'reset_user_id' not in session:
        flash('Please start the password reset process.', 'warning')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        otp_code = request.form.get('otp_code', '').strip()
        
        if not otp_code:
            flash('Please enter the OTP code.', 'warning')
            return render_template('auth/verify_otp.html')
        
        user_id = session.get('reset_user_id')
        otp = PasswordResetOTP.query.filter_by(
            user_id=user_id,
            otp_code=otp_code,
            used=False
        ).first()
        
        if not otp:
            flash('Invalid OTP code.', 'error')
            return render_template('auth/verify_otp.html')
        
        # Check if expired
        if otp.expires_at < utc_now_naive():
            flash('OTP code has expired. Please request a new one.', 'error')
            return redirect(url_for('forgot_password'))
        
        # Check attempts
        otp.attempts += 1
        if otp.attempts > 5:
            db.session.commit()
            flash('Too many failed attempts. Please request a new OTP.', 'error')
            return redirect(url_for('forgot_password'))
        
        db.session.commit()
        
        # OTP verified successfully
        session['otp_verified'] = True
        session['verified_otp_id'] = otp.id
        flash('OTP verified successfully! Please set your new password.', 'success')
        return redirect(url_for('reset_password_with_otp'))
    
    return render_template('auth/verify_otp.html')

@app.route('/reset-password-otp', methods=['GET', 'POST'])
def reset_password_with_otp():
    """Step 3: Reset password after OTP verification"""
    if not session.get('otp_verified') or 'verified_otp_id' not in session:
        flash('Please verify your OTP first.', 'warning')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not password or password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/reset_password_otp.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('auth/reset_password_otp.html')
        
        try:
            otp_id = session.get('verified_otp_id')
            otp = PasswordResetOTP.query.get(otp_id)
            
            if not otp or otp.used:
                flash('Invalid session. Please start over.', 'error')
                return redirect(url_for('forgot_password'))
            
            # Update password
            user = User.query.get(otp.user_id)
            user.set_password(password)
            otp.used = True
            
            db.session.commit()
            
            # Clear session
            session.pop('reset_user_id', None)
            session.pop('reset_delivery_method', None)
            session.pop('otp_verified', None)
            session.pop('verified_otp_id', None)
            
            flash('Password reset successfully! You can now login with your new password.', 'success')
            return redirect(url_for('index'))
            
        except Exception as e:
            db.session.rollback()
            flash('Could not reset password. Please try again.', 'error')
            print(f"Reset password error: {e}")
    
    return render_template('auth/reset_password_otp.html')

@app.route('/resend-otp', methods=['POST'])
def resend_otp():
    """Resend OTP code"""
    if 'reset_user_id' not in session:
        return jsonify({'success': False, 'message': 'Session expired'})
    
    try:
        user_id = session.get('reset_user_id')
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        # Generate new OTP
        import random
        otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        delivery_method = session.get('reset_delivery_method', 'email')
        contact_info = user.email if delivery_method == 'email' else user.phone
        
        # Delete old OTPs
        PasswordResetOTP.query.filter_by(user_id=user.id, used=False).delete()
        
        # Create new OTP
        otp = PasswordResetOTP(
            user_id=user.id,
            otp_code=otp_code,
            delivery_method=delivery_method,
            contact_info=contact_info,
            expires_at=utc_now_naive() + timedelta(minutes=10),
            used=False
        )
        db.session.add(otp)
        db.session.commit()
        
        # Send OTP
        if delivery_method == 'email':
            _send_otp_email(user, otp_code)
        else:
            _send_otp_sms(user, otp_code)
        
        return jsonify({'success': True, 'message': 'New OTP sent successfully'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Resend OTP error: {e}")
        return jsonify({'success': False, 'message': 'Failed to resend OTP'})

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    prt = PasswordResetToken.query.filter_by(token=token, used=False).first()
    if not prt or prt.expires_at < utc_now():
        flash('Reset link is invalid or has expired.', 'error')
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        if not password or password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/reset_password.html', token=token)
        try:
            user = User.query.get(prt.user_id)
            user.set_password(password)
            prt.used = True
            db.session.commit()
            flash('Your password has been reset. You can now log in.', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash('Could not reset password. Please try again.', 'error')
            print(f"Reset password error: {e}")
    return render_template('auth/reset_password.html', token=token)

@app.route('/debug/create-admin')
def debug_create_admin():
    """Debug route to manually create admin user"""
    try:
        # Check if admin already exists
        existing_admin = User.query.filter_by(username='admin').first()
        if existing_admin:
            return f"Admin user already exists! Username: admin, Email: {existing_admin.email}"
        
        # Create admin user
        admin = User(
            username='admin',
            email='admin@gymstore.com',
            first_name='System',
            last_name='Administrator',
            role='admin',
            approval_status='approved',
            is_active=True,
            email_verified=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        
        return "✅ Admin user created successfully!<br>Username: admin<br>Password: admin123<br><a href='/login'>Go to Login</a>"
        
    except Exception as e:
        return f"❌ Error creating admin user: {str(e)}"

@app.route('/debug/check-db')
def debug_check_db():
    """Debug route to check database status"""
    try:
        # Check database connection
        db.session.execute('SELECT 1')
        
        # Count users
        total_users = User.query.count()
        admin_users = User.query.filter_by(role='admin').count()
        
        # Check if admin exists
        admin_user = User.query.filter_by(username='admin').first()
        admin_info = f"Admin exists: {admin_user is not None}"
        if admin_user:
            admin_info += f"<br>Admin email: {admin_user.email}<br>Admin active: {admin_user.is_active}<br>Admin approved: {admin_user.approval_status}"
        
        return f"""
        <h3>Database Status</h3>
        <p>✅ Database connection: OK</p>
        <p>Total users: {total_users}</p>
        <p>Admin users: {admin_users}</p>
        <p>{admin_info}</p>
        <br>
        <a href="/debug/create-admin">Create Admin User</a> | 
        <a href="/login">Go to Login</a>
        """
        
    except Exception as e:
        return f"❌ Database error: {str(e)}"

# -------------------- OAuth Helper Functions --------------------
def handle_oauth_user(email, first_name, last_name, auth_type, oauth_provider_id, profile_image=None):
    """
    Handle OAuth user login or registration
    
    Args:
        email: User's email from OAuth provider
        first_name: User's first name
        last_name: User's last name
        auth_type: 'google' or 'facebook'
        oauth_provider_id: Provider's unique user ID
        profile_image: Optional profile image URL
        
    Returns:
        tuple: (user, is_new_user)
    """
    try:
        # Check if user exists with this OAuth provider ID
        user = User.query.filter_by(oauth_provider_id=oauth_provider_id).first()
        
        if user:
            # Existing OAuth user - just log them in
            return user, False
        
        # Check if user exists with this email (manual registration)
        user = User.query.filter_by(email=email).first()
        
        if user:
            # User exists with manual registration
            # Link OAuth account to existing account
            user.oauth_provider_id = oauth_provider_id
            user.auth_type = auth_type
            user.email_verified = True  # OAuth emails are verified
            db.session.commit()
            return user, False
        
        # New user - create account
        # Generate unique username from email
        base_username = email.split('@')[0]
        username = base_username
        counter = 1
        while User.query.filter_by(username=username).first():
            username = f"{base_username}{counter}"
            counter += 1
        
        # Create new user
        new_user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role='buyer',  # Default role for OAuth users
            auth_type=auth_type,
            oauth_provider_id=oauth_provider_id,
            email_verified=True,  # OAuth emails are verified
            approval_status='pending',  # Still needs admin approval
            is_active=True,
            profile_image=profile_image
        )
        # No password for OAuth users
        
        db.session.add(new_user)
        db.session.commit()
        
        return new_user, True
        
    except Exception as e:
        db.session.rollback()
        print(f"OAuth user handling error: {e}")
        raise e

# -------------------- Google OAuth Routes --------------------
@app.route('/auth/google')
def auth_google():
    """Initiate Google OAuth login"""
    try:
        # Check if OAuth is configured
        if not os.getenv('GOOGLE_CLIENT_ID') or not os.getenv('GOOGLE_CLIENT_SECRET'):
            flash('Google login is not configured. Please contact the administrator.', 'warning')
            return redirect(url_for('index'))
        
        # Generate redirect URI
        redirect_uri = url_for('auth_google_callback', _external=True)
        
        # Redirect to Google's OAuth page
        return google.authorize_redirect(redirect_uri)
        
    except Exception as e:
        print(f"Google OAuth initiation error: {e}")
        flash('Google login is temporarily unavailable. Please try again later.', 'error')
        return redirect(url_for('index'))

@app.route('/auth/google/callback')
def auth_google_callback():
    """Handle Google OAuth callback"""
    try:
        # Get the token from Google
        token = google.authorize_access_token()
        
        # Get user info from Google
        user_info = token.get('userinfo')
        
        if not user_info:
            flash('Failed to get user information from Google.', 'error')
            return redirect(url_for('index'))
        
        # Extract user details
        email = user_info.get('email')
        given_name = user_info.get('given_name', '')
        family_name = user_info.get('family_name', '')
        google_id = user_info.get('sub')  # Google's unique user ID
        picture = user_info.get('picture')
        
        if not email or not google_id:
            flash('Failed to get required information from Google.', 'error')
            return redirect(url_for('index'))
        
        # Handle user creation/login
        user, is_new = handle_oauth_user(
            email=email,
            first_name=given_name or email.split('@')[0],
            last_name=family_name or '',
            auth_type='google',
            oauth_provider_id=f'google_{google_id}',
            profile_image=picture
        )
        
        # Check approval status
        if user.approval_status != 'approved':
            if is_new:
                flash('Your account has been created and is pending admin approval. You will be notified once approved.', 'info')
            else:
                flash('Your account is pending admin approval. Please wait for verification.', 'warning')
            return redirect(url_for('index'))
        
        # Check if account is active
        if not user.is_active:
            flash('Your account has been deactivated. Please contact support.', 'error')
            return redirect(url_for('index'))
        
        # Log the user in
        log_user_login(user.id, request.remote_addr, request.headers.get('User-Agent'))
        session['user_id'] = user.id
        session['user_role'] = user.role
        session.permanent = True
        
        # Welcome message
        if is_new:
            flash(f'Welcome to Daily Fitness, {user.first_name}! Your account has been created.', 'success')
        else:
            flash(f'Welcome back, {user.first_name}!', 'success')
        
        # Redirect based on role
        if user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif user.role == 'seller':
            return redirect(url_for('seller_dashboard'))
        elif user.role == 'rider':
            return redirect(url_for('rider_dashboard'))
        else:  # buyer
            return redirect(url_for('buyer_home'))
        
    except Exception as e:
        print(f"Google OAuth callback error: {e}")
        flash('Google login failed. Please try again or use manual login.', 'error')
        return redirect(url_for('index'))

# -------------------- Facebook OAuth Routes --------------------
@app.route('/auth/facebook')
def auth_facebook():
    """Initiate Facebook OAuth login"""
    try:
        # Check if OAuth is configured
        fb_client_id = os.getenv('FACEBOOK_CLIENT_ID')
        fb_client_secret = os.getenv('FACEBOOK_CLIENT_SECRET')
        
        if not fb_client_id or not fb_client_secret or fb_client_id == 'not-configured' or fb_client_secret == 'not-configured':
            flash('Facebook login is not configured. Please contact the administrator.', 'warning')
            return redirect(url_for('index'))
        
        # Generate redirect URI
        redirect_uri = url_for('auth_facebook_callback', _external=True)
        
        # Check if the Facebook OAuth client is properly configured
        if not hasattr(facebook, 'client_id') or facebook.client_id == 'not-configured':
            flash('Facebook OAuth is not properly configured. Please restart the application.', 'warning')
            return redirect(url_for('index'))
        
        # Redirect to Facebook's OAuth page
        return facebook.authorize_redirect(redirect_uri)
        
    except Exception as e:
        print(f"Facebook OAuth initiation error: {e}")
        flash('Facebook login is temporarily unavailable. Please try again later.', 'error')
        return redirect(url_for('index'))

@app.route('/auth/facebook/callback')
def auth_facebook_callback():
    """Handle Facebook OAuth callback"""
    try:
        # Get the token from Facebook
        token = facebook.authorize_access_token()
        
        # Get user info from Facebook
        resp = facebook.get('me?fields=id,name,email,first_name,last_name,picture')
        user_info = resp.json()
        
        if not user_info:
            flash('Failed to get user information from Facebook.', 'error')
            return redirect(url_for('index'))
        
        # Extract user details
        email = user_info.get('email')
        first_name = user_info.get('first_name', '')
        last_name = user_info.get('last_name', '')
        facebook_id = user_info.get('id')
        picture_data = user_info.get('picture', {}).get('data', {})
        picture = picture_data.get('url') if picture_data else None
        
        # Facebook may not always provide email
        if not email:
            flash('Facebook login requires email permission. Please grant access to your email.', 'warning')
            return redirect(url_for('index'))
        
        if not facebook_id:
            flash('Failed to get required information from Facebook.', 'error')
            return redirect(url_for('index'))
        
        # Handle user creation/login
        user, is_new = handle_oauth_user(
            email=email,
            first_name=first_name or email.split('@')[0],
            last_name=last_name or '',
            auth_type='facebook',
            oauth_provider_id=f'facebook_{facebook_id}',
            profile_image=picture
        )
        
        # Check approval status
        if user.approval_status != 'approved':
            if is_new:
                flash('Your account has been created and is pending admin approval. You will be notified once approved.', 'info')
            else:
                flash('Your account is pending admin approval. Please wait for verification.', 'warning')
            return redirect(url_for('index'))
        
        # Check if account is active
        if not user.is_active:
            flash('Your account has been deactivated. Please contact support.', 'error')
            return redirect(url_for('index'))
        
        # Log the user in
        log_user_login(user.id, request.remote_addr, request.headers.get('User-Agent'))
        session['user_id'] = user.id
        session['user_role'] = user.role
        session.permanent = True
        
        # Welcome message
        if is_new:
            flash(f'Welcome to Daily Fitness, {user.first_name}! Your account has been created.', 'success')
        else:
            flash(f'Welcome back, {user.first_name}!', 'success')
        
        # Redirect based on role
        if user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif user.role == 'seller':
            return redirect(url_for('seller_dashboard'))
        elif user.role == 'rider':
            return redirect(url_for('rider_dashboard'))
        else:  # buyer
            return redirect(url_for('buyer_home'))
        
    except Exception as e:
        print(f"Facebook OAuth callback error: {e}")
        flash('Facebook login failed. Please try again or use manual login.', 'error')
        return redirect(url_for('index'))

# -------------------- OAuth Registration Routes --------------------
@app.route('/register/google')
def register_google():
    """Initiate Google OAuth registration"""
    try:
        # Check if OAuth is configured
        if not os.getenv('GOOGLE_CLIENT_ID') or not os.getenv('GOOGLE_CLIENT_SECRET'):
            flash('Google registration is not configured. Please contact the administrator.', 'warning')
            return redirect(url_for('register'))
        
        # Store that this is a registration flow (not login)
        session['oauth_flow'] = 'register'
        
        # Generate redirect URI (same callback as login, but we check session)
        redirect_uri = url_for('register_google_callback', _external=True)
        
        # Redirect to Google's OAuth page
        return google.authorize_redirect(redirect_uri)
        
    except Exception as e:
        print(f"Google OAuth registration initiation error: {e}")
        flash('Google registration is temporarily unavailable. Please try again later.', 'error')
        return redirect(url_for('register'))

@app.route('/register/google/callback')
def register_google_callback():
    """Handle Google OAuth registration callback"""
    try:
        # Get the token from Google
        token = google.authorize_access_token()
        
        # Get user info from Google
        user_info = token.get('userinfo')
        
        if not user_info:
            flash('Failed to get user information from Google.', 'error')
            return redirect(url_for('register'))
        
        # Extract user details
        email = user_info.get('email')
        given_name = user_info.get('given_name', '')
        family_name = user_info.get('family_name', '')
        google_id = user_info.get('sub')
        picture = user_info.get('picture')
        
        if not email or not google_id:
            flash('Failed to get required information from Google.', 'error')
            return redirect(url_for('register'))
        
        # Check if user already exists
        existing_user = User.query.filter(
            or_(
                User.email == email,
                User.oauth_provider_id == f'google_{google_id}'
            )
        ).first()
        
        if existing_user:
            flash('An account with this email or Google account already exists. Please login instead.', 'warning')
            return redirect(url_for('index'))
        
        # Generate unique username from email
        base_username = email.split('@')[0]
        username = base_username
        counter = 1
        while User.query.filter_by(username=username).first():
            username = f"{base_username}{counter}"
            counter += 1
        
        # Create new user with pending approval
        new_user = User(
            username=username,
            email=email,
            first_name=given_name or email.split('@')[0],
            last_name=family_name or '',
            role='buyer',  # Default role for OAuth registrations
            auth_type='google',
            oauth_provider_id=f'google_{google_id}',
            email_verified=True,  # Google emails are verified
            approval_status='pending',  # Requires admin approval
            is_active=False,  # Not active until approved
            profile_image=picture,
            country='Philippines'  # Default country
        )
        # No password for OAuth users
        
        db.session.add(new_user)
        db.session.commit()
        
        # Notify admins
        notify_admin_new_registration(new_user)
        
        # Clear OAuth flow session
        session.pop('oauth_flow', None)
        
        flash(f'Registration successful! Your account is under review. You will be notified once approved by our admin team.', 'success')
        return redirect(url_for('index'))
        
    except Exception as e:
        db.session.rollback()
        print(f"Google OAuth registration callback error: {e}")
        flash('Google registration failed. Please try again or use manual registration.', 'error')
        return redirect(url_for('register'))

@app.route('/register/facebook')
def register_facebook():
    """Initiate Facebook OAuth registration"""
    try:
        # Check if OAuth is configured
        fb_client_id = os.getenv('FACEBOOK_CLIENT_ID')
        fb_client_secret = os.getenv('FACEBOOK_CLIENT_SECRET')
        
        if not fb_client_id or not fb_client_secret or fb_client_id == 'not-configured' or fb_client_secret == 'not-configured':
            flash('Facebook registration is not configured. Please contact the administrator.', 'warning')
            return redirect(url_for('register'))
        
        # Store that this is a registration flow
        session['oauth_flow'] = 'register'
        
        # Generate redirect URI
        redirect_uri = url_for('register_facebook_callback', _external=True)
        
        # Check if the Facebook OAuth client is properly configured
        if not hasattr(facebook, 'client_id') or facebook.client_id == 'not-configured':
            flash('Facebook OAuth is not properly configured. Please restart the application.', 'warning')
            return redirect(url_for('register'))
        
        # Redirect to Facebook's OAuth page
        return facebook.authorize_redirect(redirect_uri)
        
    except Exception as e:
        print(f"Facebook OAuth registration initiation error: {e}")
        flash('Facebook registration is temporarily unavailable. Please try again later.', 'error')
        return redirect(url_for('register'))

@app.route('/register/facebook/callback')
def register_facebook_callback():
    """Handle Facebook OAuth registration callback"""
    try:
        # Get the token from Facebook
        token = facebook.authorize_access_token()
        
        # Get user info from Facebook
        resp = facebook.get('me?fields=id,name,email,first_name,last_name,picture')
        user_info = resp.json()
        
        if not user_info:
            flash('Failed to get user information from Facebook.', 'error')
            return redirect(url_for('register'))
        
        # Extract user details
        email = user_info.get('email')
        first_name = user_info.get('first_name', '')
        last_name = user_info.get('last_name', '')
        facebook_id = user_info.get('id')
        picture_data = user_info.get('picture', {}).get('data', {})
        picture = picture_data.get('url') if picture_data else None
        
        # Facebook may not always provide email
        if not email:
            flash('Facebook registration requires email permission. Please grant access to your email.', 'warning')
            return redirect(url_for('register'))
        
        if not facebook_id:
            flash('Failed to get required information from Facebook.', 'error')
            return redirect(url_for('register'))
        
        # Check if user already exists
        existing_user = User.query.filter(
            or_(
                User.email == email,
                User.oauth_provider_id == f'facebook_{facebook_id}'
            )
        ).first()
        
        if existing_user:
            flash('An account with this email or Facebook account already exists. Please login instead.', 'warning')
            return redirect(url_for('index'))
        
        # Generate unique username from email
        base_username = email.split('@')[0]
        username = base_username
        counter = 1
        while User.query.filter_by(username=username).first():
            username = f"{base_username}{counter}"
            counter += 1
        
        # Create new user with pending approval
        new_user = User(
            username=username,
            email=email,
            first_name=first_name or email.split('@')[0],
            last_name=last_name or '',
            role='buyer',  # Default role for OAuth registrations
            auth_type='facebook',
            oauth_provider_id=f'facebook_{facebook_id}',
            email_verified=True,  # Facebook emails are verified
            approval_status='pending',  # Requires admin approval
            is_active=False,  # Not active until approved
            profile_image=picture,
            country='Philippines'  # Default country
        )
        # No password for OAuth users
        
        db.session.add(new_user)
        db.session.commit()
        
        # Notify admins
        notify_admin_new_registration(new_user)
        
        # Clear OAuth flow session
        session.pop('oauth_flow', None)
        
        flash(f'Registration successful! Your account is under review. You will be notified once approved by our admin team.', 'success')
        return redirect(url_for('index'))
        
    except Exception as e:
        db.session.rollback()
        print(f"Facebook OAuth registration callback error: {e}")
        flash('Facebook registration failed. Please try again or use manual registration.', 'error')
        return redirect(url_for('register'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        print("=== REGISTER POST REQUEST RECEIVED ===")
        print(f"Form data: {request.form}")
        print(f"Files: {request.files}")
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role')
        profile_image = None
        
        # Document paths
        valid_id_path = None
        business_permit_path = None
        dti_cert_path = None
        
        try:
            if 'profile_image' in request.files:
                profile_image = _save_uploaded_file(
                    request.files['profile_image'], 
                    os.path.join('static', 'uploads', 'profile_pics'),
                    'image'
                )
            
            # Handle documents based on role
            if role == 'seller':
                # Seller documents (optional - admin will verify)
                if 'valid_id' in request.files and request.files['valid_id'].filename:
                    try:
                        valid_id_path = _save_uploaded_file(
                            request.files['valid_id'],
                            os.path.join('static', 'uploads', 'business_docs'),
                            'document'
                        )
                    except Exception as e:
                        print(f"Valid ID upload warning: {e}")
                        valid_id_path = None
                else:
                    valid_id_path = None
                
                if 'business_permit' in request.files and request.files['business_permit'].filename:
                    try:
                        business_permit_path = _save_uploaded_file(
                            request.files['business_permit'],
                            os.path.join('static', 'uploads', 'business_docs'),
                            'document'
                        )
                    except Exception as e:
                        print(f"Business permit upload warning: {e}")
                        business_permit_path = None
                else:
                    business_permit_path = None
                
                if 'dti_certification' in request.files and request.files['dti_certification'].filename:
                    try:
                        dti_cert_path = _save_uploaded_file(
                            request.files['dti_certification'],
                            os.path.join('static', 'uploads', 'business_docs'),
                            'document'
                        )
                    except Exception as e:
                        print(f"DTI certification upload warning: {e}")
                        dti_cert_path = None
                else:
                    dti_cert_path = None
                    
            elif role == 'rider':
                # Rider requires 1 document (optional - admin will verify)
                if 'valid_id' in request.files and request.files['valid_id'].filename:
                    try:
                        valid_id_path = _save_uploaded_file(
                            request.files['valid_id'],
                            os.path.join('static', 'uploads', 'business_docs'),
                            'document'
                        )
                    except Exception as e:
                        # If file upload fails, continue anyway - admin will request later
                        print(f"File upload warning: {e}")
                        valid_id_path = None
                else:
                    # Allow registration without document - admin will verify
                    valid_id_path = None
                
        except Exception as e:
            import traceback
            error_msg = f"Registration error: {str(e)}"
            print(f"Registration error: {e}")
            print(traceback.format_exc())
            flash(error_msg, 'error')
            return render_template('auth/register.html')
        
        # Confirm password check
        if password != confirm_password:
            flash('Passwords do not match. Please re-enter.', 'error')
            return render_template('auth/register.html')

        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose another.', 'error')
            return render_template('auth/register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please use another email.', 'error')
            return render_template('auth/register.html')
        
        # Get address fields
        region = request.form.get('region')
        province = request.form.get('province')
        municipality = request.form.get('municipality')
        barangay = request.form.get('barangay')
        street_address = request.form.get('street_address')
        zip_code = request.form.get('zip_code')
        
        # Get additional fields based on role
        phone = request.form.get('phone')
        business_name = request.form.get('business_name')
        business_type = request.form.get('business_type')
        business_address = request.form.get('business_address')
        business_phone = request.form.get('business_phone')
        business_email = request.form.get('business_email')
        tin_number = request.form.get('tin_number')
        sss_number = request.form.get('sss_number')
        pagibig_number = request.form.get('pagibig_number')
        
        # Construct full address
        full_address = f"{street_address}, {barangay}, {municipality}, {province}, {region}"
        if zip_code:
            full_address += f" {zip_code}"
        
        # Get business info for sellers
        business_name = request.form.get('business_name') if role == 'seller' else None
        
        # Create new user with role-based approval
        if role == 'buyer':
            # Buyers: Auto-approved, no documents
            user = User(
                first_name=first_name,
                last_name=last_name,
                username=username,
                email=email,
                phone=phone,
                address=full_address,
                city=municipality,
                state=province,
                zip_code=zip_code,
                country='Philippines',
                role=role,
                is_active=True,
                approval_status='approved',
                email_verified=False,
                profile_image=profile_image
            )
        elif role == 'seller':
            # Sellers: Pending approval, 3 documents required
            user = User(
                first_name=first_name,
                last_name=last_name,
                username=username,
                email=email,
                phone=phone,
                address=full_address,
                city=municipality,
                state=province,
                zip_code=zip_code,
                country='Philippines',
                role=role,
                is_active=False,
                approval_status='pending',
                email_verified=False,
                business_name=business_name,
                id_document=valid_id_path,
                business_permit=business_permit_path,
                dti_certification=dti_cert_path,
                profile_image=profile_image
            )
        else:  # rider
            # Riders: Pending approval, documents optional (admin will verify)
            user = User(
                first_name=first_name,
                last_name=last_name,
                username=username,
                email=email,
                phone=phone,
                address=full_address,
                city=municipality,
                state=province,
                zip_code=zip_code,
                country='Philippines',
                role='rider',  # Normalize any variant to 'rider'
                is_active=False,
                approval_status='pending',
                email_verified=False,
                id_document=valid_id_path if valid_id_path else None,
                profile_image=profile_image
            )
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.commit()
            
            if role == 'buyer':
                # Auto-login for buyers
                session['user_id'] = user.id
                session['username'] = user.username
                session['role'] = user.role
                session.permanent = True
                
                flash(f'✅ Registration Successful! Welcome to Daily Fitness, {user.first_name}! Your account is now active and you can start shopping.', 'success')
                return redirect(url_for('buyer_home'))
            else:
                # Sellers and riders need approval
                role_display = 'Rider' if role == 'rider' else role.capitalize()
                flash(f'✅ Registration Successful! Your {role_display} account has been created. Please wait for admin approval before you can access your dashboard. You will be notified via email once approved.', 'info')
                return redirect(url_for('index'))
                
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'error')
            print(f"Registration error: {e}")
    
    return render_template('auth/register.html')

@app.route('/register/seller', methods=['GET', 'POST'])
def register_seller():
    """Separate seller registration with business documents"""
    if request.method == 'POST':
        # Get basic user info
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        phone = request.form.get('phone')
        
        # Get business info
        business_name = request.form.get('business_name')
        business_type = request.form.get('business_type')
        business_address = request.form.get('business_address')
        business_phone = request.form.get('business_phone')
        business_email = request.form.get('business_email')
        
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose another.', 'error')
            return render_template('auth/register_seller.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please use another email.', 'error')
            return render_template('auth/register_seller.html')
        
        # Confirm password
        if password != confirm_password:
            flash('Passwords do not match. Please re-enter.', 'error')
            return render_template('auth/register_seller.html')

        # Handle file uploads - 3 documents required for sellers
        business_permit_path = None
        dti_cert_path = None
        valid_id_path = None
        profile_image_path = None
        
        try:
            # Valid ID upload (REQUIRED)
            if 'valid_id' in request.files and request.files['valid_id'].filename:
                valid_id_path = _save_uploaded_file(
                    request.files['valid_id'], 
                    os.path.join('static', 'uploads', 'business_docs'),
                    'document'
                )
            else:
                flash('Please upload a valid ID document.', 'error')
                return render_template('auth/register_seller.html')
            
            # Business permit upload (REQUIRED)
            if 'business_permit' in request.files and request.files['business_permit'].filename:
                business_permit_path = _save_uploaded_file(
                    request.files['business_permit'], 
                    os.path.join('static', 'uploads', 'business_docs'),
                    'document'
                )
            else:
                flash('Please upload your business permit.', 'error')
                return render_template('auth/register_seller.html')
            
            # Tax Registration/DTI certification upload (REQUIRED)
            if 'dti_certification' in request.files and request.files['dti_certification'].filename:
                dti_cert_path = _save_uploaded_file(
                    request.files['dti_certification'], 
                    os.path.join('static', 'uploads', 'business_docs'),
                    'document'
                )
            else:
                flash('Please upload your Tax Registration or DTI certification.', 'error')
                return render_template('auth/register_seller.html')
            
            # Profile image upload (optional)
            if 'profile_image' in request.files and request.files['profile_image'].filename:
                profile_image_path = _save_uploaded_file(
                    request.files['profile_image'], 
                    os.path.join('static', 'uploads', 'profile_pics'),
                    'image'
                )
                
        except Exception as e:
            flash(f'File upload error: {str(e)}', 'error')
            return render_template('auth/register_seller.html')
        
        # Get address fields
        region = request.form.get('region')
        province = request.form.get('province')
        municipality = request.form.get('municipality')
        barangay = request.form.get('barangay')
        street_address = request.form.get('street_address')
        zip_code = request.form.get('zip_code')
        
        # Construct full address
        full_address = f"{street_address}, {barangay}, {municipality}, {province}, {region}"
        if zip_code:
            full_address += f" {zip_code}"
        
        # Create seller user
        user = User(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email,
            phone=phone,
            address=full_address,
            city=municipality,
            state=province,
            zip_code=zip_code,
            country='Philippines',
            role='seller',
            approval_status='pending',  # Requires admin approval
            is_active=False,  # Inactive until approved
            email_verified=False,
            business_name=business_name,
            id_document=valid_id_path,  # Valid ID
            business_permit=business_permit_path,  # Business Permit
            dti_certification=dti_cert_path,  # Tax Registration/DTI
            profile_image=profile_image_path
        )
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.commit()
            
            flash('Seller registration submitted successfully! Please wait for admin approval. You will be notified via email/phone.', 'success')
            return redirect(url_for('index'))
                
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'error')
            print(f"Seller registration error: {e}")
    
    return render_template('auth/register_seller.html')

@app.route('/register/rider', methods=['GET', 'POST'])
def register_rider():
    """Separate rider registration"""
    if request.method == 'POST':
        # Get basic user info
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        phone = request.form.get('phone')
        
        # Get rider-specific info
        vehicle_type = request.form.get('vehicle_type')
        vehicle_plate = request.form.get('vehicle_plate')
        license_number = request.form.get('license_number')
        
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose another.', 'error')
            return render_template('auth/register_rider.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please use another email.', 'error')
            return render_template('auth/register_rider.html')
        
        # Confirm password
        if password != confirm_password:
            flash('Passwords do not match. Please re-enter.', 'error')
            return render_template('auth/register_rider.html')

        # Handle uploads
        profile_image_path = None
        id_document_path = None
        try:
            if 'profile_image' in request.files and request.files['profile_image'].filename:
                profile_image_path = _save_uploaded_file(
                    request.files['profile_image'], 
                    os.path.join('static', 'uploads', 'profile_pics')
                )
            # Required rider valid ID
            if 'valid_id' in request.files and request.files['valid_id'].filename:
                id_document_path = _save_uploaded_file(
                    request.files['valid_id'],
                    os.path.join('static', 'uploads', 'business_docs'),
                    'document'
                )
            else:
                flash('Please upload a clear photo of your valid ID.', 'error')
                return render_template('auth/register_rider.html')
        except Exception as e:
            flash(f'File upload error: {str(e)}', 'error')
            return render_template('auth/register_rider.html')
        
        # Get address fields
        region = request.form.get('region')
        province = request.form.get('province')
        municipality = request.form.get('municipality')
        barangay = request.form.get('barangay')
        street_address = request.form.get('street_address')
        zip_code = request.form.get('zip_code')
        
        # Construct full address
        full_address = f"{street_address}, {barangay}, {municipality}, {province}, {region}"
        if zip_code:
            full_address += f" {zip_code}"
        
        # Create rider user
        user = User(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email,
            phone=phone,
            address=full_address,
            city=municipality,
            state=province,
            zip_code=zip_code,
            country='Philippines',
            role='rider',
            approval_status='pending',  # Requires admin approval
            is_active=False,  # Inactive until approved
            email_verified=False,
            profile_image=profile_image_path,
            id_document=id_document_path
        )
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.commit()
            
            flash('Rider registration submitted successfully! Please wait for admin approval. You will be notified via email/phone.', 'success')
            return redirect(url_for('index'))
                
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'error')
            print(f"Rider registration error: {e}")
    
    return render_template('auth/register_rider.html')

@app.route('/logout')
def logout():
    """Logout user and redirect to home page"""
    session.clear()
    # Don't flash message - it causes toast notification to appear after redirect
    return redirect(url_for('index'))

# =====================================================
# HELPER FUNCTIONS
# =====================================================

def login_required(f):
    """Decorator to require login for certain routes"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(required_role):
    """Decorator to require specific role for certain routes"""
    from functools import wraps
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('index'))
            
            user = get_current_user()
            if not user or user.role != required_role:
                flash('You do not have permission to access this page.', 'error')
                return redirect(url_for('index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/buyer/home')
def buyer_home():
    """Buyer home page - accessible to guests and logged-in users"""
    user = get_current_user()
    
    # Category filter - only show approved products
    current_category = request.args.get('category', '')
    query = Product.query.filter_by(is_active=True, approval_status='approved')
    if current_category:
        query = query.join(Category).filter(Category.name == current_category)
    products = query.order_by(Product.created_at.desc()).all()
    
    # Best Sellers - products with most orders
    best_sellers = db.session.query(Product, func.count(OrderItem.id).label('order_count'))\
        .join(OrderItem, Product.id == OrderItem.product_id)\
        .filter(Product.is_active == True, Product.approval_status == 'approved')\
        .group_by(Product.id)\
        .order_by(func.count(OrderItem.id).desc())\
        .limit(8)\
        .all()
    # Extract just the Product objects
    best_sellers = [item[0] for item in best_sellers] if best_sellers else []
    
    # If no best sellers (no orders yet), show products with most reviews
    if not best_sellers:
        best_sellers = db.session.query(Product, func.count(Review.id).label('review_count'))\
            .outerjoin(Review, Product.id == Review.product_id)\
            .filter(Product.is_active == True, Product.approval_status == 'approved')\
            .group_by(Product.id)\
            .order_by(func.count(Review.id).desc())\
            .limit(8)\
            .all()
        best_sellers = [item[0] for item in best_sellers] if best_sellers else []
    
    # If still no best sellers, show featured products
    if not best_sellers:
        best_sellers = Product.query.filter_by(is_active=True, approval_status='approved')\
            .order_by(Product.created_at.desc()).limit(8).all()
    
    # Featured/Recommended products - only approved
    featured_products = Product.query.filter_by(is_featured=True, is_active=True, approval_status='approved').order_by(Product.created_at.desc()).limit(8).all()
    
    # New Arrivals - recently added approved products (last 30 days)
    from datetime import timedelta
    thirty_days_ago = manila_now_naive() - timedelta(days=30)
    new_arrivals = Product.query.filter(
        Product.is_active == True,
        Product.approval_status == 'approved',
        Product.created_at >= thirty_days_ago
    ).order_by(Product.created_at.desc()).limit(8).all()
    
    # Get categories
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    
    return render_template('buyer/home.html', 
                         products=products,
                         best_sellers=best_sellers,
                         featured_products=featured_products,
                         new_arrivals=new_arrivals,
                         categories=categories,
                         current_category=current_category,
                         current_user=user)

@app.route('/api/search/autocomplete')
def search_autocomplete():
    """API endpoint for search autocomplete suggestions"""
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({'suggestions': []})
    
    # Search products (minimum 1 character)
    products = Product.query.filter(
        Product.is_active == True,
        Product.approval_status == 'approved',
        or_(
            Product.name.ilike(f'%{query}%'),
            Product.brand.ilike(f'%{query}%'),
            Product.description.ilike(f'%{query}%')
        )
    ).limit(10).all()
    
    # Search categories
    categories = Category.query.filter(
        Category.is_active == True,
        Category.name.ilike(f'%{query}%')
    ).limit(5).all()
    
    suggestions = []
    
    # Add product suggestions
    for product in products:
        suggestions.append({
            'type': 'product',
            'name': product.name,
            'brand': product.brand,
            'category': product.category.name if product.category else 'Uncategorized',
            'price': float(product.price),
            'image_url': product.image_url,
            'url': url_for('product_detail', product_id=product.id)
        })
    
    # Add category suggestions
    for category in categories:
        suggestions.append({
            'type': 'category',
            'name': category.name,
            'url': url_for('buyer_shop', category=category.name)
        })
    
    return jsonify({'suggestions': suggestions})

@app.route('/api/search/history')
def search_history():
    """API endpoint for search history"""
    # Return empty for now - can be implemented with user search history tracking
    return jsonify({'searches': []})

@app.route('/api/search/trending')
def search_trending():
    """API endpoint for trending searches"""
    # Get most searched products in the last 7 days
    trending = []
    
    # Get top selling products as trending
    top_products = Product.query.filter(
        Product.is_active == True,
        Product.approval_status == 'approved'
    ).order_by(Product.total_sold.desc()).limit(5).all()
    
    for product in top_products:
        trending.append({
            'query': product.name,
            'count': product.total_sold or 0
        })
    
    return jsonify({'trending': trending})

@app.route('/api/search/recommendations')
def search_recommendations():
    """API endpoint for search recommendations"""
    # Return popular categories as recommendations
    recommendations = []
    
    categories = Category.query.filter_by(is_active=True).limit(5).all()
    
    for category in categories:
        product_count = Product.query.filter_by(
            category_id=category.id,
            is_active=True,
            approval_status='approved'
        ).count()
        
        if product_count > 0:
            recommendations.append({
                'query': category.name,
                'reason': f'{product_count} products available'
            })
    
    return jsonify({'recommendations': recommendations})

@app.route('/api/search/save', methods=['POST'])
def search_save():
    """API endpoint to save search query"""
    # For now, just return success
    # Can be implemented to track user search history
    return jsonify({'success': True})

@app.route('/api/search/history/clear', methods=['POST'])
def search_history_clear():
    """API endpoint to clear search history"""
    # For now, just return success
    return jsonify({'success': True})

# =====================================================
# FIREBASE AUTHENTICATION API
# =====================================================

@app.route('/api/auth/verify-token', methods=['POST'])
def verify_firebase_token():
    """Verify Firebase ID token and create session for cross-platform login"""
    try:
        # Check if Firebase Admin SDK is initialized
        if not _firebase_initialized:
            print("❌ Firebase Admin SDK not initialized")
            return jsonify({
                'success': False, 
                'message': 'Firebase Admin SDK not initialized'
            }), 500

        # Get token from request
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False, 
                'message': 'No data provided'
            }), 400
            
        id_token = data.get('idToken')
        if not id_token:
            return jsonify({
                'success': False, 
                'message': 'No token provided'
            }), 400

        # Verify the token using Firebase Admin SDK
        decoded_token = firebase_auth_admin.verify_id_token(id_token)
        uid = decoded_token['uid']
        email = decoded_token.get('email')
        print(f"✅ Token verified for user: {email} (UID: {uid})")

        # Get user data from Firestore
        db_client = firebase_firestore.client()
        user_doc = db_client.collection('users').document(uid).get()
        
        if not user_doc.exists:
            print(f"❌ User not found in Firestore: {uid}")
            return jsonify({
                'success': False, 
                'message': 'User not found in database'
            }), 404

        user_data = user_doc.to_dict()

        # Check approval status
        approval_status = user_data.get('approval_status', 'pending')
        if approval_status != 'approved':
            print(f"⚠️ User not approved: {email} (status: {approval_status})")
            return jsonify({
                'success': False, 
                'message': f'Your account is {approval_status}. Please wait for admin approval.'
            }), 403

        # Create Flask session
        session['user_id'] = uid
        session['email'] = email
        session['role'] = user_data.get('role', 'buyer')
        session['first_name'] = user_data.get('first_name', '')
        session['last_name'] = user_data.get('last_name', '')
        session['firebase_uid'] = uid  # Store Firebase UID
        session.permanent = True
        
        print(f"✅ Session created for {email} with role: {session['role']}")

        # Determine redirect URL based on role
        role = user_data.get('role', 'buyer')
        redirect_urls = {
            'admin': '/admin/dashboard',
            'seller': '/seller/dashboard',
            'rider': '/rider/dashboard',
            'buyer': '/buyer/home'
        }

        return jsonify({
            'success': True,
            'message': 'Login successful',
            'redirect_url': redirect_urls.get(role, '/buyer/home'),
            'user': {
                'uid': uid,
                'email': email,
                'role': role,
                'name': f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}"
            }
        })

    except firebase_auth_admin.InvalidIdTokenError:
        print("❌ Invalid Firebase token")
        return jsonify({
            'success': False, 
            'message': 'Invalid authentication token'
        }), 401
    except Exception as e:
        print(f"❌ Token verification error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'message': f'Authentication error: {str(e)}'
        }), 500

@app.route('/buyer/shop')
def buyer_shop():
    """Shop page - now using Firestore for real-time product sync"""
    from firestore_helper import get_products_firestore, search_products_firestore, count_products_firestore
    
    # Get query parameters
    category_filter = request.args.get('category', '').strip()
    search_query = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'name')
    page = request.args.get('page', 1, type=int)
    max_price = request.args.get('max_price', type=int)
    in_stock_only = request.args.get('in_stock', '0') == '1'
    
    per_page = 12
    offset = (page - 1) * per_page
    
    # Build filters for Firestore
    filters = {
        'isActive': True,
        'approvalStatus': 'approved'
    }
    
    if max_price and max_price < 10000:
        filters['maxPrice'] = max_price
    
    if in_stock_only:
        filters['inStockOnly'] = True
    
    # Get products from Firestore
    if search_query:
        # Use search function for text search
        all_products = search_products_firestore(search_query, filters, limit=100)
        
        # Apply category filter if specified
        if category_filter:
            all_products = [p for p in all_products if p.get('category') == category_filter]
        
        # Apply sorting
        if sort_by == 'latest':
            all_products.sort(key=lambda x: x.get('createdAt', 0), reverse=True)
        elif sort_by == 'price_low':
            all_products.sort(key=lambda x: x.get('price', 0))
        elif sort_by == 'price_high':
            all_products.sort(key=lambda x: x.get('price', 0), reverse=True)
        elif sort_by == 'top_sales':
            all_products.sort(key=lambda x: x.get('totalSold', 0), reverse=True)
        else:  # name
            all_products.sort(key=lambda x: x.get('name', ''))
        
        # Manual pagination
        total_products = len(all_products)
        products_list = all_products[offset:offset + per_page]
    else:
        # Use filtered query
        if category_filter:
            filters['category'] = category_filter
        
        # Get products with sorting and pagination
        products_list = get_products_firestore(
            filters=filters,
            sort_by=sort_by,
            limit=per_page,
            offset=offset
        )
        
        # Get total count for pagination
        total_products = count_products_firestore(filters)
    
    # Create pagination object (mimicking Flask-SQLAlchemy pagination)
    class PaginationAdapter:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page if total > 0 else 1
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None
        
        def iter_pages(self, left_edge=2, left_current=2, right_current=3, right_edge=2):
            """Generate page numbers for pagination"""
            last = 0
            for num in range(1, self.pages + 1):
                if num <= left_edge or \
                   (num > self.page - left_current - 1 and num < self.page + right_current) or \
                   num > self.pages - right_edge:
                    if last + 1 != num:
                        yield None
                    yield num
                    last = num
    
    # Convert Firestore products to objects for template compatibility
    class ProductAdapter:
        def __init__(self, fs_product):
            self.id = fs_product.get('id')
            self.name = fs_product.get('name', '')
            self.brand = fs_product.get('brand', '')
            self.price = Decimal(str(fs_product.get('price', 0)))
            self.image_url = fs_product.get('imageUrl', '')
            self.stock_quantity = fs_product.get('stockQuantity', 0)
            self.category_name = fs_product.get('category', 'Uncategorized')
            self.seller_id = fs_product.get('sellerId', '')
            self.total_sold = fs_product.get('totalSold', 0)
            self.rating = fs_product.get('rating', 0)
            self.average_rating = self.rating
            self.review_count = fs_product.get('reviewCount', 0)
            self.is_active = fs_product.get('isActive', True)
            
            # Create category object
            class CategoryAdapter:
                def __init__(self, name):
                    self.name = name
            
            self.category = CategoryAdapter(self.category_name)
    
    product_objects = [ProductAdapter(p) for p in products_list]
    
    products = PaginationAdapter(
        items=product_objects,
        page=page,
        per_page=per_page,
        total=total_products
    )
    
    # Get categories for filter - get unique categories from Firestore
    all_categories_data = get_products_firestore(filters={'isActive': True, 'approvalStatus': 'approved'})
    categories = sorted(list(set(p.get('category', 'Uncategorized') for p in all_categories_data)))
    
    user = get_current_user()
    
    return render_template('buyer/shop.html', 
                         products=products,
                         categories=categories,
                         current_category=category_filter,
                         current_search=search_query,
                         current_sort=sort_by,
                         max_price=max_price,
                         in_stock_only=in_stock_only,
                         current_user=user)

@app.route('/buyer/cart')
def buyer_cart():
    """Shopping cart - accessible to guests but shows empty cart - FIRESTORE VERSION"""
    user = get_current_user()
    
    if user:
        from firestore_helper import get_cart_items_firestore
        
        # Get cart items from Firestore using Firebase UID for cross-platform sync
        user_id = user.firebase_uid if user.firebase_uid else str(user.id)
        firestore_items = get_cart_items_firestore(user_id)
        
        # Convert Firestore items to objects with properties for template compatibility
        class CartItemAdapter:
            def __init__(self, fs_item):
                self.id = fs_item.get('id')
                # Handle both string (Firestore doc ID from mobile) and int (SQL ID from web)
                raw_product_id = fs_item.get('productId', 0)
                self.product_id = raw_product_id  # Keep as-is (string or int)
                self.quantity = fs_item.get('quantity', 0)
                self.variant = fs_item.get('variant')
                self.selected_weight = fs_item.get('selectedWeight')
                self.unit_price = Decimal(str(fs_item.get('price', 0)))
                
                # Create a product-like object
                class ProductAdapter:
                    def __init__(self, fs_item, product_id):
                        # Keep product_id as-is (string or int)
                        self.id = product_id
                        self.name = fs_item.get('productName', '')
                        self.image_url = fs_item.get('productImage', '')
                        self.price = Decimal(str(fs_item.get('price', 0)))
                        self.stock_quantity = fs_item.get('maxStock', 0)
                        self.brand = fs_item.get('brand', 'No Brand')
                        
                        # Check if this is a web product (has integer SQL ID) or mobile product (Firestore doc ID)
                        self.is_web_product = isinstance(product_id, int) or (isinstance(product_id, str) and product_id.isdigit())
                        # For templates: only web products have detail pages
                        self.web_id = int(product_id) if self.is_web_product else None
                        
                        # Try to get full product data from Firestore for category info
                        try:
                            from firestore_helper import get_product_firestore
                            full_product = get_product_firestore(str(product_id))
                            if full_product:
                                self.brand = full_product.get('brand', 'No Brand')
                                category_name = full_product.get('category', 'Uncategorized')
                            else:
                                category_name = 'Uncategorized'
                        except:
                            category_name = 'Uncategorized'
                        
                        # Create category object
                        class CategoryAdapter:
                            def __init__(self, name='Uncategorized'):
                                self.name = name
                        
                        self.category = CategoryAdapter(category_name)
                
                self.product = ProductAdapter(fs_item, self.product_id)
            
            @property
            def subtotal(self):
                return float(self.unit_price * self.quantity)
        
        cart_items = [CartItemAdapter(item) for item in firestore_items]
        total = sum(item.subtotal for item in cart_items)
    else:
        # Guest user - show empty cart
        cart_items = []
        total = 0
    
    return render_template('buyer/cart.html', 
                         cart_products=cart_items,
                         total=total)

@app.route('/product/<product_id>')
@app.route('/product/<product_id>/<slug>')
def product_detail(product_id, slug=None):
    """Product detail page with SEO-friendly URLs - HYBRID: Firestore + SQL"""
    from firestore_helper import get_product_firestore, get_reviews_firestore
    
    # Try to get product from Firestore first
    fs_product = get_product_firestore(str(product_id))
    
    if fs_product:
        # Product found in Firestore - use it
        class ProductAdapter:
            def __init__(self, fs_prod):
                self.id = int(fs_prod.get('id', product_id))
                self.name = fs_prod.get('name', '')
                self.brand = fs_prod.get('brand', '')
                self.price = Decimal(str(fs_prod.get('price', 0)))
                self.image_url = fs_prod.get('imageUrl', '')
                self.description = fs_prod.get('description', '')
                self.stock_quantity = fs_prod.get('stockQuantity', 0)
                self.category_name = fs_prod.get('category', 'Uncategorized')
                self.seller_id = int(fs_prod.get('sellerId', 0))
                self.rating = fs_prod.get('rating', 0)
                self.average_rating = self.rating
                self.review_count = fs_prod.get('reviewCount', 0)
                self.total_sold = fs_prod.get('totalSold', 0)
                self.is_active = fs_prod.get('isActive', True)
                self.approval_status = fs_prod.get('approvalStatus', 'approved')
                self.gallery_images = fs_prod.get('galleryImages', [])
                
                # Create category object
                class CategoryAdapter:
                    def __init__(self, name, cat_id):
                        self.name = name
                        self.id = cat_id
                
                self.category = CategoryAdapter(self.category_name, fs_prod.get('categoryId', 0))
                
                # Create seller object
                class SellerAdapter:
                    def __init__(self, seller_id):
                        self.id = seller_id
                        # Try to get seller from SQL
                        sql_seller = User.query.get(seller_id)
                        if sql_seller:
                            self.username = sql_seller.username
                            self.full_name = sql_seller.full_name
                        else:
                            self.username = 'Unknown'
                            self.full_name = 'Unknown Seller'
                
                self.seller = SellerAdapter(self.seller_id)
        
        product = ProductAdapter(fs_product)
        
        # Get reviews from Firestore
        fs_reviews = get_reviews_firestore(str(product_id))
        
        class ReviewAdapter:
            def __init__(self, fs_review):
                self.id = fs_review.get('id')
                self.rating = fs_review.get('rating', 0)
                self.comment = fs_review.get('comment', '')
                self.created_at = fs_review.get('createdAt')
                self.is_approved = fs_review.get('isApproved', True)
                
                # Get user info
                user_id = fs_review.get('userId')
                sql_user = User.query.get(user_id) if user_id else None
                
                class UserAdapter:
                    def __init__(self, sql_user):
                        if sql_user:
                            self.username = sql_user.username
                            self.full_name = sql_user.full_name
                        else:
                            self.username = 'Anonymous'
                            self.full_name = 'Anonymous User'
                
                self.user = UserAdapter(sql_user)
        
        reviews = [ReviewAdapter(r) for r in fs_reviews[:10]]
        
        # Get related products from Firestore (same category)
        from firestore_helper import get_products_firestore
        related_fs = get_products_firestore(
            filters={
                'category': product.category_name,
                'isActive': True,
                'approvalStatus': 'approved'
            },
            limit=5
        )
        
        # Filter out current product
        related_fs = [p for p in related_fs if int(p.get('id', 0)) != product_id][:4]
        related_products = [ProductAdapter(p) for p in related_fs]
        
    else:
        # Fallback to SQL if not in Firestore
        try:
            sql_product_id = int(product_id)
        except ValueError:
            from flask import abort
            abort(404)
            
        product = Product.query.get_or_404(sql_product_id)
        
        # Get product reviews from SQL
        reviews = Review.query.filter_by(product_id=sql_product_id, is_approved=True).order_by(Review.created_at.desc()).limit(10).all()
        
        # Get related products from SQL
        related_products = Product.query.filter(
            Product.category_id == product.category_id,
            Product.id != sql_product_id,
            Product.is_active == True,
            Product.approval_status == 'approved'
        ).limit(4).all()
    
    # Generate SEO-friendly slug if not provided
    if not slug:
        generated_slug = generate_product_slug(product.name)
        return redirect(url_for('product_detail', product_id=product_id, slug=generated_slug))
    
    # Check if user has this product in cart (for logged-in users)
    in_cart = False
    cart_quantity = 0
    if 'user_id' in session:
        from firestore_helper import get_cart_items_firestore
        
        # Get cart items from Firestore
        cart_items = get_cart_items_firestore(str(session['user_id']))
        
        # Check if this product is in cart
        for item in cart_items:
            # Handle both string (Firestore doc ID) and int (SQL ID) productId
            item_product_id = item.get('productId', 0)
            # Convert both to string for comparison to handle mixed types
            if str(item_product_id) == str(product_id):
                in_cart = True
                cart_quantity = item.get('quantity', 0)
                break
    
    user = get_current_user()
    
    # Parse gallery images
    gallery_images = []
    if hasattr(product, 'gallery_images') and product.gallery_images:
        import json
        if isinstance(product.gallery_images, str):
            try:
                gallery_images = json.loads(product.gallery_images)
            except:
                gallery_images = []
        elif isinstance(product.gallery_images, list):
            gallery_images = product.gallery_images
    
    return render_template('buyer/product_detail.html',
                         product=product,
                         reviews=reviews,
                         related_products=related_products,
                         in_cart=in_cart,
                         cart_quantity=cart_quantity,
                         gallery_images=gallery_images,
                         current_user=user)

@app.route('/seller/<int:seller_id>/shop')
@app.route('/seller/<int:seller_id>/shop/<username>')
def seller_shop(seller_id, username=None):
    """Seller shop page showing all products from a specific seller"""
    seller = User.query.filter_by(id=seller_id, role='seller').first_or_404()
    
    # Get query parameters
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort', 'name')
    category_filter = request.args.get('category', '')
    page = request.args.get('page', 1, type=int)
    
    # Build query - only show approved and active products
    query = Product.query.filter_by(
        seller_id=seller_id,
        is_active=True,
        approval_status='approved'
    )
    
    if category_filter:
        query = query.filter_by(category_id=category_filter)
    
    if search_query:
        query = query.filter(Product.name.contains(search_query))
    
    # Apply sorting
    if sort_by == 'price_low':
        query = query.order_by(Product.price.asc())
    elif sort_by == 'price_high':
        query = query.order_by(Product.price.desc())
    elif sort_by == 'newest':
        query = query.order_by(Product.created_at.desc())
    else:
        query = query.order_by(Product.name.asc())
    
    # Paginate results
    products = query.paginate(page=page, per_page=12, error_out=False)
    
    # Get categories for this seller's products
    categories = db.session.query(Category).join(Product).filter(
        Product.seller_id == seller_id,
        Product.is_active == True,
        Product.approval_status == 'approved'
    ).distinct().all()
    
    # Get seller stats
    total_products = Product.query.filter_by(
        seller_id=seller_id,
        is_active=True,
        approval_status='approved'
    ).count()
    
    total_reviews = db.session.query(Review).join(Product).filter(
        Product.seller_id == seller_id,
        Review.is_approved == True
    ).count()
    
    avg_rating = db.session.query(db.func.avg(Review.rating)).join(Product).filter(
        Product.seller_id == seller_id,
        Review.is_approved == True
    ).scalar() or 0
    
    # Check if current user is following this seller
    is_following = False
    if 'user_id' in session:
        follow = Follow.query.filter_by(
            follower_id=session['user_id'],
            following_id=seller_id
        ).first()
        is_following = follow is not None
    
    # Get follower count
    follower_count = Follow.query.filter_by(following_id=seller_id).count()
    
    user = get_current_user()
    
    return render_template('buyer/seller_shop.html',
                         seller=seller,
                         products=products,
                         categories=categories,
                         total_products=total_products,
                         total_reviews=total_reviews,
                         avg_rating=avg_rating,
                         is_following=is_following,
                         follower_count=follower_count,
                         current_search=search_query,
                         current_sort=sort_by,
                         current_category=category_filter,
                         current_user=user)

@app.route('/api/follow_seller/<int:seller_id>', methods=['POST'])
@login_required
def follow_seller(seller_id):
    """Follow or unfollow a seller"""
    user = get_current_user()
    seller = User.query.filter_by(id=seller_id, role='seller').first_or_404()
    
    # Check if already following
    follow = Follow.query.filter_by(
        follower_id=user.id,
        following_id=seller_id
    ).first()
    
    if follow:
        # Unfollow
        db.session.delete(follow)
        db.session.commit()
        return jsonify({
            'success': True,
            'action': 'unfollowed',
            'message': f'You unfollowed {seller.business_name or seller.full_name}',
            'follower_count': Follow.query.filter_by(following_id=seller_id).count()
        })
    else:
        # Follow
        new_follow = Follow(
            follower_id=user.id,
            following_id=seller_id
        )
        db.session.add(new_follow)
        db.session.commit()
        return jsonify({
            'success': True,
            'action': 'followed',
            'message': f'You are now following {seller.business_name or seller.full_name}',
            'follower_count': Follow.query.filter_by(following_id=seller_id).count()
        })

@app.route('/buyer/checkout', methods=['GET', 'POST'])
@login_required
def buyer_checkout():
    user = get_current_user()
    from firestore_helper import get_cart_items_firestore, clear_cart_firestore
    
    # Use Firebase UID for cross-platform sync
    user_id = user.firebase_uid if user.firebase_uid else str(user.id)
    
    # Get cart items from Firestore
    firestore_items = get_cart_items_firestore(user_id)
    
    # Support checking out selected items only
    selected_ids_param = request.args.get('selected_ids') if request.method == 'GET' else request.form.get('selected_ids')
    selected_ids = []
    if selected_ids_param:
        try:
            selected_ids = selected_ids_param.split(',')
        except Exception:
            selected_ids = []
    
    # Filter by selected IDs if provided
    if selected_ids:
        firestore_items = [item for item in firestore_items if item.get('id') in selected_ids]
    
    if not firestore_items:
        flash('Your cart is empty!', 'warning')
        return redirect(url_for('buyer_shop'))
    
    # Convert Firestore items to cart item adapters
    class CartItemAdapter:
        def __init__(self, fs_item):
            self.id = fs_item.get('id')
            # Handle both string (Firestore doc ID from mobile) and int (SQL ID from web)
            raw_product_id = fs_item.get('productId', 0)
            self.product_id = raw_product_id
            self.quantity = int(fs_item.get('quantity', 0))
            self.variant = fs_item.get('variant')
            self.selected_weight = fs_item.get('selectedWeight')
            self.unit_price = Decimal(str(fs_item.get('price', 0)))
            
            # Fetch actual product from SQL for stock checking (only if it's an integer ID)
            self.product = None
            if isinstance(raw_product_id, int) or (isinstance(raw_product_id, str) and raw_product_id.isdigit()):
                try:
                    self.product = Product.query.get(int(raw_product_id))
                except:
                    pass
        
        @property
        def subtotal(self):
            return float(self.unit_price * self.quantity)
    
    cart_items = [CartItemAdapter(item) for item in firestore_items]
    
    # Calculate total
    total = sum(item.subtotal for item in cart_items)
    
    # Get saved addresses for the user
    saved_addresses = SavedAddress.query.filter_by(user_id=user.id).order_by(SavedAddress.is_default.desc(), SavedAddress.created_at.desc()).all()
    
    if request.method == 'POST':
        # Process the order
        shipping_address = request.form.get('shipping_address')
        payment_method = request.form.get('payment_method')
        
        if not shipping_address:
            flash('Please provide a shipping address.', 'error')
            return render_template('buyer/checkout.html', 
                                 cart_products=cart_items,
                                 total=total,
                                 saved_addresses=saved_addresses,
                                 current_user=user,
                                 selected_ids=selected_ids)
        
        # Create order in Firestore
        from firestore_helper import create_order_firestore
        
        # Use Firebase UID for cross-platform sync
        buyer_id = user.firebase_uid if user.firebase_uid else str(user.id)
        
        order_data = {
            'orderNumber': f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'buyerId': buyer_id,  # ✅ Use Firebase UID
            'paymentMethod': payment_method,
            'subtotal': float(total),
            'taxAmount': float(total * 0.08),  # 8% tax
            'shippingAmount': 0.0,  # Free shipping
            'totalAmount': float(total * 1.08),
            'shippingAddress': shipping_address,
            'status': 'pending',
            'paymentStatus': 'pending',
            'items': []  # Will be populated below
        }
        
        try:
            # Create order items and check inventory
            order_items = []
            skipped_items = []
            items_to_remove = []
            seller_totals = {}
            
            for cart_item in cart_items:
                # Check if product exists (web products only have SQL records)
                if cart_item.product is None:
                    # Mobile product - skip inventory check (managed in Firestore)
                    # Get product details from Firestore
                    product_id_str = str(cart_item.product_id)
                    
                    # Try to get product from Firestore
                    from firestore_helper import get_product_firestore
                    fs_product = get_product_firestore(product_id_str)
                    
                    if not fs_product:
                        skipped_items.append({
                            'name': f'Product {product_id_str}',
                            'requested': cart_item.quantity,
                            'available': 0
                        })
                        items_to_remove.append(cart_item.id)
                        continue
                    
                    # Check Firestore stock
                    fs_stock = fs_product.get('stock', 0)
                    if fs_stock < cart_item.quantity:
                        skipped_items.append({
                            'name': fs_product.get('name', f'Product {product_id_str}'),
                            'requested': cart_item.quantity,
                            'available': fs_stock
                        })
                        items_to_remove.append(cart_item.id)
                        continue
                    
                    # Add item to order data (Firestore product)
                    item_data = {
                        'productId': product_id_str,
                        'productName': fs_product.get('name', 'Unknown Product'),
                        'productImage': fs_product.get('imageUrl', ''),
                        'sellerId': fs_product.get('sellerId', ''),
                        'sqlSellerId': None,
                        'quantity': cart_item.quantity,
                        'unitPrice': float(cart_item.unit_price),
                        'totalPrice': float(cart_item.subtotal)
                    }
                    order_data['items'].append(item_data)
                    order_items.append(item_data)
                    
                    # Try to map Firestore seller to SQL seller for commissions
                    try:
                        seller_str = fs_product.get('sellerId', '')
                        if seller_str.isdigit():
                            s_id = int(seller_str)
                            if s_id not in seller_totals:
                                seller_totals[s_id] = 0
                            seller_totals[s_id] += float(cart_item.subtotal)
                            item_data['sqlSellerId'] = s_id
                        else:
                            # Find user by firebase_uid
                            seller_user = User.query.filter_by(firebase_uid=seller_str).first()
                            if seller_user:
                                if seller_user.id not in seller_totals:
                                    seller_totals[seller_user.id] = 0
                                seller_totals[seller_user.id] += float(cart_item.subtotal)
                                item_data['sqlSellerId'] = seller_user.id
                    except:
                        pass
                        
                    continue
                
                # Web product - check SQL inventory
                if cart_item.product.stock_quantity < cart_item.quantity:
                    # Skip this item and notify user
                    skipped_items.append({
                        'name': cart_item.product.name,
                        'requested': cart_item.quantity,
                        'available': cart_item.product.stock_quantity
                    })
                    items_to_remove.append(cart_item.id)
                    continue
                
                # Get seller's Firebase UID for cross-platform sync
                seller = User.query.get(cart_item.product.seller_id)
                seller_firebase_uid = seller.firebase_uid if seller and seller.firebase_uid else str(cart_item.product.seller_id)
                
                # Add item to order data (Firestore)
                item_data = {
                    'productId': str(cart_item.product_id),
                    'productName': cart_item.product.name,
                    'productImage': cart_item.product.image_url if hasattr(cart_item.product, 'image_url') else '',
                    'sellerId': seller_firebase_uid,  # ✅ Use Firebase UID
                    'sqlSellerId': cart_item.product.seller_id,
                    'quantity': cart_item.quantity,
                    'unitPrice': float(cart_item.unit_price if cart_item.unit_price is not None else cart_item.product.price),
                    'totalPrice': float(cart_item.subtotal)
                }
                order_data['items'].append(item_data)
                order_items.append(item_data)
                
                # Track seller totals for commissions
                if cart_item.product.seller_id not in seller_totals:
                    seller_totals[cart_item.product.seller_id] = 0
                seller_totals[cart_item.product.seller_id] += float(cart_item.subtotal)
            
            # If no items can be ordered, cancel the order
            if not order_items:
                flash('None of the items in your cart are available. Please remove out-of-stock items and try again.', 'error')
                for item in skipped_items:
                    flash(f"{item['name']}: Requested {item['requested']}, but only {item['available']} available", 'warning')
                return render_template('buyer/checkout.html', 
                                     cart_products=cart_items,
                                     total=total,
                                     current_user=user,
                                     selected_ids=selected_ids)
            
            # Recalculate total for available items only
            actual_total = sum(item['totalPrice'] for item in order_items)
            order_data['subtotal'] = actual_total
            order_data['taxAmount'] = actual_total * 0.08
            order_data['totalAmount'] = actual_total * 1.08
            
            # Create order in Firestore
            order_id = create_order_firestore(order_data)
            
            # Reduce inventory after order placement (still use SQL for inventory)
            # Create SQL order for inventory tracking and commissions
            sql_order = Order(
                order_number=order_data['orderNumber'],
                buyer_id=user.id,
                payment_method=payment_method,
                subtotal=actual_total,
                tax_amount=actual_total * 0.08,
                shipping_amount=0,
                total_amount=actual_total * 1.08,
                shipping_address=shipping_address,
                status='pending',
                payment_status='pending',
                firestore_order_id=order_id  # Link to Firestore
            )
            db.session.add(sql_order)
            db.session.flush()
            
            # Create SQL order items for inventory tracking (only for web products with SQL IDs)
            sql_order_items = []
            for item in order_items:
                product_id = item['productId']
                # Only create SQL order item if productId is a valid integer (web products)
                # Mobile products use Firestore doc IDs (strings) and don't need SQL tracking
                if isinstance(product_id, int) or (isinstance(product_id, str) and product_id.isdigit()):
                    try:
                        sql_seller_id = item.get('sqlSellerId')
                        if sql_seller_id is None:
                            continue
                            
                        sql_order_item = OrderItem(
                            order_id=sql_order.id,
                            product_id=int(product_id),
                            seller_id=sql_seller_id,
                            quantity=item['quantity'],
                            unit_price=item['unitPrice'],
                            total_price=item['totalPrice']
                        )
                        db.session.add(sql_order_item)
                        sql_order_items.append(sql_order_item)
                    except (ValueError, TypeError):
                        # Skip if conversion fails (mobile product)
                        pass
            
            # Reduce inventory
            if sql_order_items:
                reduce_inventory(sql_order_items)
            
            # Create commission records for each seller (still use SQL)
            for seller_id, seller_total in seller_totals.items():
                commission_rate, commission_amount = calculate_commission(seller_total, seller_id)
                commission = Commission(
                    order_id=sql_order.id,
                    seller_id=seller_id,
                    order_amount=seller_total,
                    commission_rate=commission_rate,
                    commission_amount=commission_amount,
                    status='pending'
                )
                db.session.add(commission)
            
            # Clear checked out items and remove out-of-stock items from Firestore
            from firestore_helper import remove_from_cart_firestore
            
            cart_ids_to_remove = []
            if selected_ids:
                # Remove selected items that were successfully ordered
                for cart_item in cart_items:
                    if cart_item.id not in [str(x) for x in items_to_remove]:  # Successfully ordered
                        cart_ids_to_remove.append(cart_item.id)
            else:
                # Remove all items that were successfully ordered
                for cart_item in cart_items:
                    if cart_item.id not in [str(x) for x in items_to_remove]:
                        cart_ids_to_remove.append(cart_item.id)
            
            # Remove items from Firestore
            for cart_id in cart_ids_to_remove:
                remove_from_cart_firestore(user_id, cart_id)
            
            # Also remove out-of-stock items from Firestore
            for item_id in items_to_remove:
                remove_from_cart_firestore(user_id, str(item_id))
            
            db.session.commit()
            
            # Send automatic messages from buyer to each seller about the order
            for seller_id in seller_totals.keys():
                seller = User.query.get(seller_id)
                if seller:
                    # Get products from this seller in the order
                    seller_products = [item['productName'] for item in order_items if item.get('sqlSellerId') == seller_id]
                    if not seller_products:
                        continue
                        
                    products_list = ", ".join(seller_products[:3])  # Show first 3 products
                    if len(seller_products) > 3:
                        products_list += f" and {len(seller_products) - 3} more"
                    
                    # Buyer sends message to seller
                    buyer_message = f"Hi! I just placed an order #{order_data['orderNumber']} for {products_list}. Total: ${seller_totals[seller_id]:.2f}. Looking forward to receiving my items!"
                    send_automatic_message(user.id, seller_id, buyer_message, sql_order.id)
                    
                    # Seller auto-replies to buyer
                    seller_reply = f"Thank you for your order #{order_data['orderNumber']}! We've received your order for {products_list}. We'll start preparing your items and keep you updated. If you have any questions, feel free to message us!"
                    send_automatic_message(seller_id, user.id, seller_reply, sql_order.id)
            
            # Show success message with warnings for skipped items
            flash('Order placed successfully!', 'success')
            if skipped_items:
                flash(f'{len(skipped_items)} item(s) were removed from your cart due to insufficient stock:', 'warning')
                for item in skipped_items:
                    flash(f"• {item['name']} (requested: {item['requested']}, available: {item['available']})", 'info')
            
            return redirect(url_for('order_confirmation'))
            
        except Exception as e:
            db.session.rollback()
            flash('Error processing order. Please try again.', 'error')
            import traceback
            with open('checkout_error.log', 'w') as f:
                f.write(f"Order processing error: {e}\n")
                f.write(traceback.format_exc())
            print(f"Order processing error: {e}")
    
    return render_template('buyer/checkout.html', 
                         cart_products=cart_items,
                         total=total,
                         saved_addresses=saved_addresses,
                         current_user=user,
                         selected_ids=selected_ids)

@app.route('/api/buyer/order-updates')
@login_required
def api_buyer_order_updates():
    """API endpoint to check for order status updates"""
    try:
        user = get_current_user()
        
        # Get all orders for this buyer
        orders = Order.query.filter_by(buyer_id=user.id).all()
        
        order_data = [{
            'id': order.id,
            'order_number': order.order_number,
            'status': order.status,
            'updated_at': order.updated_at.isoformat() if order.updated_at else None
        } for order in orders]
        
        return jsonify({
            'success': True,
            'orders': order_data
        })
        
    except Exception as e:
        print(f"Error fetching order updates: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        })

@app.route('/buyer/collections')
def buyer_collections():
    # Get sort parameter
    sort_by = request.args.get('sort', 'relevance')
    
    # Get featured products for collections - only approved
    query = Product.query.filter_by(is_featured=True, is_active=True, approval_status='approved')
    
    # Apply sorting
    if sort_by == 'latest':
        query = query.order_by(Product.created_at.desc())
    elif sort_by == 'top_sales':
        query = query.order_by(Product.id.desc())
    elif sort_by == 'price':
        query = query.order_by(Product.price.asc())
    else:  # relevance
        query = query.order_by(Product.name.asc())
    
    featured_products = query.limit(20).all()
    user = get_current_user()
    return render_template('buyer/collections.html', featured_products=featured_products, current_user=user)

@app.route('/buyer/occasions')
def buyer_occasions():
    # Get sort parameter
    sort_by = request.args.get('sort', 'relevance')
    
    # Get products for special occasions - only approved
    query = Product.query.filter_by(is_active=True, approval_status='approved')
    
    # Apply sorting
    if sort_by == 'latest':
        query = query.order_by(Product.created_at.desc())
    elif sort_by == 'top_sales':
        query = query.order_by(Product.id.desc())
    elif sort_by == 'price':
        query = query.order_by(Product.price.asc())
    else:  # relevance
        query = query.order_by(Product.name.asc())
    
    products = query.limit(20).all()
    user = get_current_user()
    return render_template('buyer/occasions.html', products=products, current_user=user)

@app.route('/buyer/about')
def buyer_about():
    user = get_current_user()
    
    # Fetch featured testimonials
    featured_testimonials = FeaturedTestimonial.query.filter_by(is_active=True).order_by(FeaturedTestimonial.display_order).limit(3).all()
    
    return render_template('buyer/about.html', current_user=user, featured_testimonials=featured_testimonials)

@app.route('/buyer/order_confirmation')
@login_required
def order_confirmation():
    # Get the latest order for the user from Firestore
    user = get_current_user()
    from firestore_helper import get_orders_firestore
    
    orders = get_orders_firestore(str(user.id), 'buyer')
    latest_order = orders[0] if orders else None
    
    # If no Firestore orders, fall back to SQL
    if not latest_order:
        latest_order = Order.query.filter_by(buyer_id=user.id).order_by(Order.created_at.desc()).first()
    
    # Normalize order for template compatibility
    normalized_order = normalize_order_for_template(latest_order) if latest_order else None
    
    return render_template('buyer/order_confirmation.html', order=normalized_order)

@app.route('/buyer/orders')
@login_required
def buyer_orders():
    """Buyer orders list with statuses"""
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status')
    
    # Try to get orders from Firestore first
    from firestore_helper import get_orders_firestore
    # Use Firebase UID for cross-platform sync
    user_id = user.firebase_uid if user.firebase_uid else str(user.id)
    orders = get_orders_firestore(user_id, 'buyer')
    
    # Apply status filter if provided
    if status_filter:
        orders = [o for o in orders if o.get('status') == status_filter]
    
    # Manual pagination for Firestore orders
    per_page = 10
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_orders = orders[start_idx:end_idx]
    
    # Normalize orders for template compatibility
    normalized_orders = [normalize_order_for_template(order) for order in paginated_orders]
    
    # Create a simple pagination object
    class SimplePagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None
    
    orders_paginated = SimplePagination(normalized_orders, page, per_page, len(orders))
    
    # Build reviewed set to mark items that already have reviews
    # Note: This will need to be updated when reviews are migrated to Firestore
    order_ids = [o.get('id') for o in paginated_orders]
    reviewed_pairs = set()
    # For now, skip review checking since reviews are still in SQL
    # This will be updated in Phase 4 (Review Sync)
    
    return render_template('buyer/orders.html', orders=orders_paginated, current_status=status_filter, reviewed_pairs=reviewed_pairs)

@app.route('/buyer/order/<order_id>')
@login_required
def buyer_order_detail(order_id):
    """View detailed order information"""
    user = get_current_user()
    
    # Try to get order from Firestore first
    from firestore_helper import get_order_firestore
    order = get_order_firestore(order_id)
    
    # If not in Firestore, fall back to SQL
    if not order:
        # Try to parse as integer for SQL fallback
        try:
            order_id_int = int(order_id)
            order = Order.query.filter_by(id=order_id_int, buyer_id=user.id).first_or_404()
        except ValueError:
            return render_template('errors/404.html'), 404
    else:
        # Verify the order belongs to this user
        if order.get('buyerId') != str(user.id):
            return render_template('errors/404.html'), 404
    
    # Normalize order for template compatibility
    normalized_order = normalize_order_for_template(order)
    
    return render_template('buyer/order_detail.html', order=normalized_order)

@app.route('/buyer/orders/<order_id>/confirm', methods=['POST'])
@login_required
def confirm_order_receipt(order_id):
    """Buyer confirms receipt of a delivered order. Only then update sellers' sales records."""
    user = get_current_user()
    
    # Try to get order from Firestore first
    from firestore_helper import get_order_firestore, update_order_status_firestore
    order = get_order_firestore(order_id)
    
    # If not in Firestore, fall back to SQL
    if not order:
        try:
            order_id_int = int(order_id)
            order = Order.query.filter_by(id=order_id_int, buyer_id=user.id).first_or_404()
            is_firestore = False
        except ValueError:
            return render_template('errors/404.html'), 404
    else:
        # Verify the order belongs to this user
        if order.get('buyerId') != str(user.id):
            return render_template('errors/404.html'), 404
        is_firestore = True
    
    # Check status based on data source
    order_status = order.get('status') if is_firestore else order.status
    if order_status != 'delivered':
        flash('Order must be delivered before confirmation.', 'error')
        return redirect(url_for('buyer_orders'))
    
    # Store old status for logging
    old_status = order_status
    
    try:
        # Update order status to completed
        if is_firestore:
            update_order_status_firestore(order_id, 'completed', str(user.id))
            # Also update SQL order if it exists
            try:
                sql_order = Order.query.filter_by(firestore_order_id=order_id).first()
                if sql_order:
                    sql_order.status = 'completed'
                    sql_order.payment_status = 'paid'
                    sql_order.auto_confirmed_at = utc_now()
            except:
                pass
        else:
            order.status = 'completed'
            order.payment_status = 'paid'
            order.auto_confirmed_at = utc_now()
            db.session.commit()
        
        # Log the status change (only for SQL orders)
        if not is_firestore:
            log_order_status_change(
                order_id=order.id,
                user_id=user.id,
                user_role='buyer',
                old_status=old_status,
                new_status='completed',
                notes='Buyer confirmed receipt of order'
            )
        
        # Update seller statistics for each item in the order (SQL only)
        if not is_firestore:
            for item in order.order_items:
                seller = User.query.get(item.seller_id)
                if seller:
                    # Get or create seller statistics for today
                    today = utc_now().date()
                    stats = SellerStatistics.query.filter_by(seller_id=seller.id, date=today).first()
                    if not stats:
                        stats = SellerStatistics(seller_id=seller.id, date=today)
                        db.session.add(stats)
                    
                    # Update statistics
                    stats.total_orders = (stats.total_orders or 0) + 1
                    stats.total_revenue = (stats.total_revenue or Decimal('0')) + Decimal(str(item.total_price))
            
            # Collect commissions when buyer confirms receipt
            commissions = Commission.query.filter_by(order_id=order.id, status='pending').all()
            for commission in commissions:
                commission.status = 'collected'
            
            db.session.commit()
        
        flash('✅ Order confirmed successfully!', 'success')
        
        # Notify sellers that order is completed (SQL only for now)
        if not is_firestore:
            notified_sellers = set()
            for item in order.order_items:
                if item.seller_id not in notified_sellers:
                    create_notification(
                        user_id=item.seller_id,
                        notification_type='order_update',
                        category='order',
                        title='✅ Order Completed!',
                        message=f'Buyer confirmed receipt of order #{order.order_number}. Payment will be released.',
                        priority='high',
                        action_url=url_for('seller_orders'),
                        action_text='View Orders'
                    )
                    notified_sellers.add(item.seller_id)
            
            # Notify rider that order is completed
            if order.rider_id:
                create_notification(
                    user_id=order.rider_id,
                    notification_type='order_update',
                    category='delivery',
                    title='✅ Delivery Completed!',
                    message=f'Buyer confirmed receipt of order #{order.order_number}. Your commission will be released.',
                    priority='high',
                    action_url=url_for('rider_orders'),
                    action_text='View Orders'
                )
            
            # Create notification for the buyer
            notification = Notification(
                user_id=user.id,
                type='order_update',
                category='order',
                priority='medium',
                title='Order Confirmed',
                message=f'You have successfully confirmed receipt of order #{order.order_number}.',
                data={'order_id': order.id, 'order_number': order.order_number}
            )
            db.session.add(notification)
            db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        flash('Error confirming order. Please try again.', 'error')
        print(f"Confirm receipt error: {e}")
    
    return redirect(url_for('buyer_orders'))

# =====================================================
# BUYER PROFILE ROUTES
# =====================================================

@app.route('/buyer/profile')
@login_required
def buyer_profile():
    """Buyer profile dashboard"""
    user = get_current_user()
    if user.role != 'buyer':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    # Get user statistics
    total_orders = Order.query.filter_by(buyer_id=user.id).count()
    completed_orders = Order.query.filter_by(buyer_id=user.id, status='confirmed').count()
    pending_orders = Order.query.filter_by(buyer_id=user.id).filter(Order.status.in_(['pending', 'confirmed', 'preparing', 'for_pickup', 'on_delivery'])).count()
    
    # Get recent orders
    recent_orders = Order.query.filter_by(buyer_id=user.id).order_by(Order.created_at.desc()).limit(5).all()
    
    # Get wishlist count from Firestore
    from firestore_helper import get_wishlist_items_firestore
    # Use Firebase UID for cross-platform sync
    user_id = user.firebase_uid if user.firebase_uid else str(user.id)
    wishlist_items = get_wishlist_items_firestore(user_id)
    wishlist_count = len(wishlist_items)
    
    # Get unread notifications count
    unread_notifications = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    
    return render_template('buyer/profile/dashboard.html',
                         user=user,
                         total_orders=total_orders,
                         completed_orders=completed_orders,
                         pending_orders=pending_orders,
                         recent_orders=recent_orders,
                         wishlist_count=wishlist_count,
                         unread_notifications=unread_notifications)

@app.route('/buyer/profile/personal', methods=['GET', 'POST'])
@login_required
def buyer_profile_personal():
    """Manage personal information"""
    user = get_current_user()
    if user.role != 'buyer':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            # Update personal information
            user.first_name = request.form.get('first_name', user.first_name)
            user.last_name = request.form.get('last_name', user.last_name)
            user.email = request.form.get('email', user.email)
            user.phone = request.form.get('phone', user.phone)
            user.address = request.form.get('address', user.address)
            user.city = request.form.get('city', user.city)
            user.state = request.form.get('state', user.state)
            user.zip_code = request.form.get('zip_code', user.zip_code)
            
            # Handle profile image upload
            if 'profile_image' in request.files and request.files['profile_image'].filename:
                profile_path = _save_uploaded_file(
                    request.files['profile_image'], 
                    os.path.join('static', 'uploads', 'profile_pics')
                )
                user.profile_image = profile_path
            
            user.updated_at = utc_now()
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'error')
        
        return redirect(url_for('buyer_profile_personal'))
    
    return render_template('buyer/profile/personal.html', user=user)

@app.route('/buyer/profile/password', methods=['GET', 'POST'])
@login_required
def buyer_profile_password():
    """Change password"""
    user = get_current_user()
    if user.role != 'buyer':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not user.check_password(current_password):
            flash('Current password is incorrect.', 'error')
            return redirect(url_for('buyer_profile_personal'))
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('buyer_profile_personal'))
        
        if len(new_password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return redirect(url_for('buyer_profile_personal'))
        
        try:
            user.set_password(new_password)
            user.updated_at = utc_now()
            db.session.commit()
            flash('Password changed successfully!', 'success')
            
            # Log the password change
            login_log = LoginLog(
                user_id=user.id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                login_time=utc_now()
            )
            db.session.add(login_log)
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error changing password: {str(e)}', 'error')
        
        return redirect(url_for('buyer_profile_personal'))
    
    # For GET requests, redirect to personal page
    return redirect(url_for('buyer_profile_personal'))

@app.route('/buyer/profile/addresses')
@login_required
def buyer_profile_addresses():
    """Manage saved addresses"""
    user = get_current_user()
    if user.role != 'buyer':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    addresses = SavedAddress.query.filter_by(user_id=user.id).order_by(SavedAddress.is_default.desc(), SavedAddress.created_at.desc()).all()
    return render_template('buyer/profile/addresses.html', addresses=addresses)

@app.route('/buyer/profile/wishlist')
@login_required
def buyer_profile_wishlist():
    """Manage wishlist - FIRESTORE VERSION"""
    user = get_current_user()
    if user.role != 'buyer':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    from firestore_helper import get_wishlist_items_firestore
    
    # Use Firebase UID for cross-platform sync
    user_id = user.firebase_uid if user.firebase_uid else str(user.id)
    
    # Get wishlist items from Firestore
    firestore_items = get_wishlist_items_firestore(user_id)
    
    # Convert to objects for template compatibility
    class WishlistItemAdapter:
        def __init__(self, fs_item):
            self.id = fs_item.get('id')
            # Handle both string (Firestore doc ID from mobile) and int (SQL ID from web)
            raw_product_id = fs_item.get('productId', 0)
            self.product_id = raw_product_id
            self.created_at = fs_item.get('addedAt')
            
            # Create a product-like object
            class ProductAdapter:
                def __init__(self, fs_item, product_id):
                    # Keep product_id as-is (string or int)
                    self.id = product_id
                    self.name = fs_item.get('productName', 'Unknown Product')
                    self.image_url = fs_item.get('productImage', '')
                    self.price = Decimal(str(fs_item.get('price', 0)))
                    
                    # Check if this is a web product (has integer SQL ID) or mobile product (Firestore doc ID)
                    self.is_web_product = isinstance(product_id, int) or (isinstance(product_id, str) and product_id.isdigit())
                    # For templates: only web products have detail pages
                    self.web_id = int(product_id) if self.is_web_product else None
                    
                    # Try to get full product data from SQL if it's a web product
                    if self.is_web_product:
                        try:
                            sql_product = Product.query.get(int(product_id))
                            if sql_product:
                                self.name = sql_product.name
                                self.image_url = sql_product.image_url or ''
                                self.price = sql_product.price
                                self.stock_quantity = sql_product.stock_quantity
                                self.brand = sql_product.brand
                                if sql_product.category:
                                    self.category = sql_product.category
                        except:
                            pass
            
            self.product = ProductAdapter(fs_item, self.product_id)
    
    wishlist_items = [WishlistItemAdapter(item) for item in firestore_items]
    return render_template('buyer/profile/wishlist.html', wishlist_items=wishlist_items)

@app.route('/buyer/profile/security')
@login_required
def buyer_security_settings():
    """Security and privacy settings page"""
    user = get_current_user()
    if user.role != 'buyer':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    return render_template('buyer/profile/security.html', user=user)

@app.route('/buyer/profile/change-password', methods=['POST'])
@login_required
def buyer_change_password():
    """Change user password"""
    user = get_current_user()
    if user.role != 'buyer':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    # Check if user is OAuth user (no password)
    if user.auth_type in ['google', 'facebook']:
        flash('You signed in with Google/Facebook. Password change is not available for social login accounts.', 'warning')
        return redirect(url_for('buyer_security_settings'))
    
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not user.check_password(current_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('buyer_security_settings'))
    
    if new_password != confirm_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('buyer_security_settings'))
    
    if len(new_password) < 8:
        flash('Password must be at least 8 characters long.', 'error')
        return redirect(url_for('buyer_security_settings'))
    
    try:
        user.set_password(new_password)
        user.updated_at = utc_now()
        db.session.commit()
        flash('Password changed successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error changing password: {str(e)}', 'error')
    
    return redirect(url_for('buyer_security_settings'))

@app.route('/buyer/profile/notification-settings', methods=['POST'])
@login_required
def buyer_update_notification_settings():
    """Update email notification preferences"""
    user = get_current_user()
    if user.role != 'buyer':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    try:
        user.email_order_updates = 'email_order_updates' in request.form
        user.email_promotions = 'email_promotions' in request.form
        user.email_newsletter = 'email_newsletter' in request.form
        user.updated_at = utc_now()
        db.session.commit()
        flash('Notification preferences updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating preferences: {str(e)}', 'error')
    
    return redirect(url_for('buyer_security_settings'))

@app.route('/buyer/profile/privacy-settings', methods=['POST'])
@login_required
def buyer_update_privacy_settings():
    """Update privacy settings"""
    user = get_current_user()
    if user.role != 'buyer':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    try:
        user.profile_public = 'profile_public' in request.form
        user.show_purchase_history = 'show_purchase_history' in request.form
        user.updated_at = utc_now()
        db.session.commit()
        flash('Privacy settings updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating settings: {str(e)}', 'error')
    
    return redirect(url_for('buyer_security_settings'))

@app.route('/buyer/profile/deactivate', methods=['POST'])
@login_required
def buyer_deactivate_account():
    """Deactivate user account"""
    user = get_current_user()
    if user.role != 'buyer':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    try:
        # Mark account as inactive instead of deleting
        user.is_active = False
        user.updated_at = utc_now()
        db.session.commit()
        
        # Clear session and logout
        session.clear()
        flash('Your account has been deactivated.', 'info')
        return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deactivating account: {str(e)}', 'error')
        return redirect(url_for('buyer_security_settings'))

# ==================== SUPPORT TICKETS ====================

@app.route('/support', methods=['GET', 'POST'])
@login_required
def support_tickets():
    """Support ticket system"""
    user = get_current_user()
    
    if request.method == 'POST':
        subject = request.form.get('subject')
        category = request.form.get('category')
        message = request.form.get('message')
        priority = request.form.get('priority', 'normal')
        
        if not subject or not category or not message:
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('support_tickets'))
        
        # Generate unique ticket number
        import random
        ticket_number = f"TKT-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        while SupportTicket.query.filter_by(ticket_number=ticket_number).first():
            ticket_number = f"TKT-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        
        # Create ticket
        ticket = SupportTicket(
            user_id=user.id,
            ticket_number=ticket_number,
            subject=subject,
            category=category,
            priority=priority,
            message=message,
            status='open'
        )
        
        db.session.add(ticket)
        db.session.commit()
        
        # Notify all admins
        admins = User.query.filter_by(role='admin', is_active=True).all()
        for admin in admins:
            notification = Notification(
                user_id=admin.id,
                title='New Support Ticket',
                message=f'New ticket #{ticket_number} from {user.full_name}: {subject}',
                type='system_alert',
                category='general',
                priority='high',
                action_url=f'/admin/support/{ticket.id}',
                action_text='View Ticket'
            )
            db.session.add(notification)
        
        db.session.commit()
        
        flash(f'Support ticket #{ticket_number} created successfully! We will respond soon.', 'success')
        return redirect(url_for('support_tickets'))
    
    # Get user's tickets
    tickets = SupportTicket.query.filter_by(user_id=user.id).order_by(SupportTicket.created_at.desc()).all()
    return render_template('support/tickets.html', tickets=tickets)

@app.route('/support/<int:ticket_id>')
@login_required
def view_support_ticket(ticket_id):
    """View specific support ticket"""
    user = get_current_user()
    ticket = SupportTicket.query.get_or_404(ticket_id)
    
    # Check access
    if ticket.user_id != user.id and user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('support_tickets'))
    
    return render_template('support/ticket_detail.html', ticket=ticket)

# ==================== REVIEWS API ====================

@app.route('/api/reviews', methods=['POST'])
@login_required
def api_submit_review():
    """Submit or update a product review for a delivered order item"""
    try:
        data = request.get_json() or {}
        product_id = data.get('product_id')
        order_id = data.get('order_id')
        rating = int(data.get('rating', 0))
        title = data.get('title', '')
        comment = data.get('comment', '')
        
        if rating < 1 or rating > 5:
            return jsonify({'success': False, 'message': 'Rating must be between 1 and 5.'}), 400
        
        user = get_current_user()
        order = Order.query.get_or_404(order_id)
        if order.buyer_id != user.id:
            return jsonify({'success': False, 'message': 'You cannot review this order.'}), 403
        if order.status != 'completed':
            return jsonify({'success': False, 'message': 'You can only review products after confirming receipt of completed orders.'}), 400
        
        # Ensure the product is part of the order
        item = OrderItem.query.filter_by(order_id=order.id, product_id=product_id).first()
        if not item:
            return jsonify({'success': False, 'message': 'Product not found in this order.'}), 400
        
        # Upsert review based on unique constraint (user_id, product_id, order_id)
        review = Review.query.filter_by(user_id=user.id, product_id=product_id, order_id=order.id).first()
        if review:
            review.rating = rating
            review.title = title
            review.comment = comment
            review.is_verified = True
            review.is_approved = True
        else:
            review = Review(
                product_id=product_id,
                user_id=user.id,
                order_id=order.id,
                rating=rating,
                title=title,
                comment=comment,
                is_verified=True,
                is_approved=True
            )
            db.session.add(review)
        
        db.session.commit()
        
        # ✅ SYNC TO FIRESTORE - Add/update review in Firestore for mobile app
        try:
            from firestore_helper import add_review_firestore, get_firestore_client
            
            review_data = {
                'productId': str(product_id),
                'userId': str(user.id),
                'buyerId': str(user.id),
                'buyerName': user.full_name if hasattr(user, 'full_name') else user.username,
                'orderId': str(order_id),
                'rating': rating,
                'title': title or '',
                'comment': comment or '',
                'isVerified': True,
                'isApproved': True,
                'sqlReviewId': str(review.id),  # Link to SQL for reference
                'helpfulCount': 0
            }
            
            # Check if review already exists in Firestore (by sqlReviewId)
            db_firestore = get_firestore_client()
            existing_reviews = db_firestore.collection('reviews').where('sqlReviewId', '==', str(review.id)).limit(1).stream()
            
            review_exists = False
            for fs_review in existing_reviews:
                # Update existing review
                fs_review.reference.update({
                    'rating': rating,
                    'title': title or '',
                    'comment': comment or '',
                    'updatedAt': firestore.SERVER_TIMESTAMP
                })
                print(f"✅ Review updated in Firestore: {fs_review.id}")
                review_exists = True
                break
            
            if not review_exists:
                # Create new review
                firestore_review_id = add_review_firestore(review_data)
                print(f"✅ Review synced to Firestore: {firestore_review_id}")
        except Exception as firestore_error:
            print(f"⚠️ Firestore sync failed (review still saved in SQL): {firestore_error}")
            # Don't fail the whole operation if Firestore sync fails
        
        return jsonify({'success': True, 'message': 'Review submitted successfully.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/seller/dashboard')
@role_required('seller')
def seller_dashboard():
    user = get_current_user()
    from datetime import timedelta
    
    # === PRODUCT STATISTICS ===
    total_products = Product.query.filter_by(seller_id=user.id).count()
    approved_products = Product.query.filter_by(seller_id=user.id, approval_status='approved').count()
    pending_approval = Product.query.filter_by(seller_id=user.id, approval_status='pending').count()
    
    # Low stock products (< 10 units)
    low_stock_products = Product.query.filter(
        Product.seller_id == user.id,
        Product.stock_quantity < 10,
        Product.approval_status == 'approved'
    ).order_by(Product.stock_quantity).limit(5).all()
    
    # === ORDER STATISTICS ===  
    # 1. Get SQL order items for this seller
    sql_order_items = OrderItem.query.filter_by(seller_id=user.id).all()
    
    # 2. Get Firestore orders for this seller
    from firestore_helper import get_orders_firestore
    user_firebase_id = user.firebase_uid if user.firebase_uid else str(user.id)
    all_fs_orders = get_orders_firestore(None, 'admin')
    
    fs_seller_orders = []
    fs_order_items = []
    for order in all_fs_orders:
        has_seller_item = False
        order_seller_id = str(order.get('sellerId'))
        items = order.get('items', [])
        for item in items:
            item_seller_id = str(item.get('sellerId'))
            item_sql_seller_id = str(item.get('sqlSellerId'))
            if (item_seller_id == str(user_firebase_id) or 
                item_seller_id == str(user.id) or
                item_sql_seller_id == str(user.id) or
                order_seller_id == str(user_firebase_id) or 
                order_seller_id == str(user.id)):
                has_seller_item = True
                fs_order_items.append(item)
        if has_seller_item:
            fs_seller_orders.append(normalize_order_for_template(order))
    
    total_orders = len(set([item.order_id for item in sql_order_items])) + len(fs_seller_orders)
    
    # Calculate revenue
    sql_revenue = sum(float(item.total_price) for item in sql_order_items)
    fs_revenue = sum(float(item.get('totalPrice', item.get('price', 0) * item.get('quantity', 1))) for item in fs_order_items)
    total_revenue = sql_revenue + fs_revenue
    
    # Commission calculation (10% to admin)
    admin_commission_rate = 0.10
    admin_commission = total_revenue * admin_commission_rate
    net_earnings = total_revenue - admin_commission
    
    # Orders by status
    sql_pending = Order.query.join(OrderItem).filter(OrderItem.seller_id == user.id, Order.status.in_(['pending', 'confirmed'])).distinct().count()
    fs_pending = sum(1 for o in fs_seller_orders if o.status in ['pending', 'confirmed'])
    pending_orders = sql_pending + fs_pending
    
    sql_preparing = Order.query.join(OrderItem).filter(OrderItem.seller_id == user.id, Order.status == 'preparing').distinct().count()
    fs_preparing = sum(1 for o in fs_seller_orders if o.status == 'preparing')
    preparing_orders = sql_preparing + fs_preparing
    
    sql_ready = Order.query.join(OrderItem).filter(OrderItem.seller_id == user.id, Order.status == 'for_pickup').distinct().count()
    fs_ready = sum(1 for o in fs_seller_orders if o.status == 'for_pickup')
    ready_for_pickup = sql_ready + fs_ready
    
    sql_completed = Order.query.join(OrderItem).filter(OrderItem.seller_id == user.id, Order.status.in_(['delivered', 'completed'])).distinct().count()
    fs_completed = sum(1 for o in fs_seller_orders if o.status in ['delivered', 'completed'])
    completed_orders = sql_completed + fs_completed
    
    # Recent orders (last 10)
    sql_recent = Order.query.join(OrderItem).filter(OrderItem.seller_id == user.id).order_by(Order.created_at.desc()).limit(10).distinct().all()
    
    # Combine and sort recent orders
    def get_order_time(order):
        dt = getattr(order, 'created_at', None) or getattr(order, 'createdAt', None)
        if dt is None:
            return datetime.min
        if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
            return dt.replace(tzinfo=None)
        return dt
        
    all_recent = list(sql_recent) + fs_seller_orders
    all_recent.sort(key=get_order_time, reverse=True)
    recent_orders = all_recent[:10]
    
    # === SALES CHART DATA (Last 7 Days) ===
    sales_chart_data = []
    for i in range(6, -1, -1):
        date = datetime.now() - timedelta(days=i)
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        sql_daily_revenue = db.session.query(
            db.func.sum(OrderItem.total_price)
        ).join(Order).filter(
            OrderItem.seller_id == user.id,
            Order.created_at >= day_start,
            Order.created_at <= day_end,
            Order.status.in_(['delivered', 'completed'])
        ).scalar() or 0
        
        fs_daily_revenue = 0
        for o in fs_seller_orders:
            if o.status in ['delivered', 'completed'] and day_start <= o.created_at <= day_end:
                # Sum items belonging to this seller
                order_seller_id = str(o._data.get('sellerId'))
                for item in o._data.get('items', []):
                    item_seller_id = str(item.get('sellerId'))
                    item_sql_seller_id = str(item.get('sqlSellerId'))
                    if (item_seller_id == str(user_firebase_id) or 
                        item_seller_id == str(user.id) or
                        item_sql_seller_id == str(user.id) or
                        order_seller_id == str(user_firebase_id) or
                        order_seller_id == str(user.id)):
                        fs_daily_revenue += float(item.get('totalPrice', item.get('price', 0) * item.get('quantity', 1)))
        
        daily_revenue = float(sql_daily_revenue) + float(fs_daily_revenue)
        
        sales_chart_data.append({
            'date': date.strftime('%a'),
            'revenue': float(daily_revenue)
        })
    
    # === MONTHLY SALES (Current Month) ===
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_revenue = db.session.query(
        db.func.sum(OrderItem.total_price)
    ).join(Order).filter(
        OrderItem.seller_id == user.id,
        Order.created_at >= month_start,
        Order.status.in_(['delivered', 'completed'])
    ).scalar() or 0
    
    monthly_commission = float(monthly_revenue) * admin_commission_rate
    monthly_earnings = float(monthly_revenue) - monthly_commission
    
    # === TOP PRODUCTS (Last 30 Days) ===
    thirty_days_ago = datetime.now() - timedelta(days=30)
    top_products = db.session.query(
        Product.name,
        Product.id,
        db.func.sum(OrderItem.quantity).label('total_sold'),
        db.func.sum(OrderItem.total_price).label('total_revenue')
    ).join(OrderItem).join(Order).filter(
        Product.seller_id == user.id,
        Order.created_at >= thirty_days_ago,
        Order.status.in_(['delivered', 'completed'])
    ).group_by(Product.id, Product.name).order_by(
        db.func.sum(OrderItem.quantity).desc()
    ).limit(5).all()
    
    # === REVIEWS & RATINGS ===
    seller_products = Product.query.filter_by(seller_id=user.id).all()
    product_ids = [p.id for p in seller_products] if seller_products else [0]
    
    # Recent reviews
    recent_reviews = Review.query.filter(
        Review.product_id.in_(product_ids),
        Review.is_approved == True
    ).order_by(Review.created_at.desc()).limit(5).all()
    
    # Calculate average rating
    all_reviews = Review.query.filter(
        Review.product_id.in_(product_ids),
        Review.is_approved == True
    ).all()
    
    avg_rating = 0
    total_reviews = len(all_reviews)
    if total_reviews > 0:
        avg_rating = sum(review.rating for review in all_reviews) / total_reviews
    
    # === NOTIFICATIONS ===
    notifications = Notification.query.filter_by(
        user_id=user.id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    unread_notifications = Notification.query.filter_by(
        user_id=user.id,
        is_read=False
    ).count()
    
    # === MESSAGES ===
    unread_messages = Message.query.filter_by(
        receiver_id=user.id,
        is_read=False
    ).count()
    
    # === PRODUCT INSIGHTS ===
    # Most viewed products (if you have views tracking)
    # For now, using top sold as proxy
    
    return render_template('seller/dashboard.html',
                         # Products
                         total_products=total_products,
                         approved_products=approved_products,
                         pending_approval=pending_approval,
                         low_stock_products=low_stock_products,
                         # Orders
                         total_orders=total_orders,
                         pending_orders=pending_orders,
                         preparing_orders=preparing_orders,
                         ready_for_pickup=ready_for_pickup,
                         completed_orders=completed_orders,
                         recent_orders=recent_orders,
                         # Revenue & Earnings
                         total_revenue=total_revenue,
                         admin_commission=admin_commission,
                         admin_commission_rate=admin_commission_rate,
                         net_earnings=net_earnings,
                         monthly_revenue=monthly_revenue,
                         monthly_commission=monthly_commission,
                         monthly_earnings=monthly_earnings,
                         # Analytics
                         sales_chart_data=sales_chart_data,
                         top_products=top_products,
                         # Reviews
                         recent_reviews=recent_reviews,
                         avg_rating=avg_rating,
                         total_reviews=total_reviews,
                         # Notifications & Messages
                         notifications=notifications,
                         unread_notifications=unread_notifications,
                         unread_messages=unread_messages,
                         # Followers
                         total_followers=Follow.query.filter_by(following_id=user.id).count())

@app.route('/seller/followers')
@role_required('seller')
def seller_followers():
    """View list of followers for the seller"""
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    
    # Get all followers with pagination
    followers_query = Follow.query.filter_by(following_id=user.id).order_by(Follow.created_at.desc())
    followers = followers_query.paginate(page=page, per_page=20, error_out=False)
    
    # Get follower stats
    total_followers = Follow.query.filter_by(following_id=user.id).count()
    
    # Get recent followers (last 7 days)
    seven_days_ago = datetime.now() - timedelta(days=7)
    recent_followers = Follow.query.filter(
        Follow.following_id == user.id,
        Follow.created_at >= seven_days_ago
    ).count()
    
    # Get follower growth data (last 30 days)
    follower_growth = []
    for i in range(29, -1, -1):
        date = datetime.now() - timedelta(days=i)
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        daily_followers = Follow.query.filter(
            Follow.following_id == user.id,
            Follow.created_at >= day_start,
            Follow.created_at <= day_end
        ).count()
        
        follower_growth.append({
            'date': date.strftime('%m/%d'),
            'count': daily_followers
        })
    
    return render_template('seller/followers.html',
                         followers=followers,
                         total_followers=total_followers,
                         recent_followers=recent_followers,
                         follower_growth=follower_growth)

@app.route('/seller/products')
@role_required('seller')
def seller_products():
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    
    # Get filter parameters
    search_query = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '').strip()
    status_filter = request.args.get('status', '').strip()
    stock_filter = request.args.get('stock', '').strip()
    sort_by = request.args.get('sort', 'newest')
    
    # Build query - start with seller's products
    query = Product.query.filter_by(seller_id=user.id)
    
    # Apply search filter
    if search_query:
        query = query.filter(Product.name.ilike(f'%{search_query}%'))
    
    # Apply category filter
    if category_filter:
        query = query.filter_by(category_id=int(category_filter))
    
    # Apply status filter
    if status_filter:
        query = query.filter_by(approval_status=status_filter)
    
    # Apply stock filter
    if stock_filter == 'in_stock':
        query = query.filter(Product.stock_quantity > 10)
    elif stock_filter == 'low_stock':
        query = query.filter(Product.stock_quantity <= 10, Product.stock_quantity > 0)
    elif stock_filter == 'out_of_stock':
        query = query.filter(Product.stock_quantity == 0)
    
    # Apply sorting
    if sort_by == 'newest':
        query = query.order_by(Product.created_at.desc())
    elif sort_by == 'oldest':
        query = query.order_by(Product.created_at.asc())
    elif sort_by == 'name':
        query = query.order_by(Product.name.asc())
    elif sort_by == 'price_low':
        query = query.order_by(Product.price.asc())
    elif sort_by == 'price_high':
        query = query.order_by(Product.price.desc())
    elif sort_by == 'stock':
        query = query.order_by(Product.stock_quantity.desc())
    else:
        query = query.order_by(Product.created_at.desc())
    
    # Paginate results
    products = query.paginate(
        page=page, per_page=12, error_out=False
    )
    
    # Get categories for filter dropdown
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    
    # Get unread notifications count
    unread_notifications = Notification.query.filter_by(
        user_id=user.id,
        is_read=False
    ).count()
    
    return render_template('seller/products.html', 
                         products=products, 
                         categories=categories,
                         unread_notifications=unread_notifications)

@app.route('/seller/products/add', methods=['GET', 'POST'])
@role_required('seller')
def add_product():
    if request.method == 'POST':
        user = get_current_user()
        
        # Get form data
        name = request.form.get('name')
        brand = request.form.get('brand')
        description = request.form.get('description')
        category_id = request.form.get('category')
        price = float(request.form.get('price'))
        stock = int(request.form.get('stock'))
        weight = request.form.get('weight')
        dimensions = request.form.get('dimensions')
        
        # Get category by ID
        category = Category.query.get(category_id)
        if not category:
            flash('Invalid category selected.', 'error')
            categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
            return render_template('seller/add_product.html', categories=categories)
        
        # Create product (automatically set to pending approval)
        product = Product(
            seller_id=user.id,
            category_id=category.id,
            name=name,
            brand=brand,
            description=description,
            price=price,
            stock_quantity=stock,
            weight=float(weight) if weight else None,
            dimensions=dimensions,
            is_active=True,
            approval_status='pending',  # New products require admin approval
            submitted_at=utc_now()
        )
        # Handle main image upload
        try:
            if 'image' in request.files and request.files['image'].filename:
                image_url = _save_uploaded_file(
                    request.files['image'], os.path.join('static', 'uploads', 'product_images')
                )
                product.image_url = image_url
        except Exception as e:
            flash(str(e), 'error')
            return render_template('seller/add_product.html')
        
        # Handle gallery images upload
        gallery_images = []
        if 'gallery_images' in request.files:
            gallery_files = request.files.getlist('gallery_images')
            for gallery_file in gallery_files[:5]:  # Limit to 5 images
                if gallery_file and gallery_file.filename:
                    try:
                        gallery_url = _save_uploaded_file(
                            gallery_file, os.path.join('static', 'uploads', 'product_images')
                        )
                        gallery_images.append(gallery_url)
                    except Exception as e:
                        print(f"Error uploading gallery image: {e}")
        
        # Store gallery images as JSON array
        if gallery_images:
            import json
            product.gallery_images = json.dumps(gallery_images)
        
        try:
            db.session.add(product)
            db.session.flush()  # Get product ID before creating history
            
            # Create approval history entry
            approval_history = ProductApprovalHistory(
                product_id=product.id,
                action='submitted',
                admin_id=None,
                notes='Product submitted for admin approval'
            )
            db.session.add(approval_history)
            db.session.commit()
            
            # ✅ SYNC TO FIRESTORE - Add product to Firestore for mobile app
            try:
                from firestore_helper import create_product_firestore
                
                # Use Firebase UID for cross-platform sync (same as cart fix)
                seller_id = user.firebase_uid if user.firebase_uid else str(user.id)
                
                product_data = {
                    'sellerId': seller_id,  # ✅ Use Firebase UID for mobile sync
                    'sellerName': user.full_name if hasattr(user, 'full_name') else user.username,
                    'categoryId': str(category.id),
                    'category': category.name,
                    'name': name,
                    'brand': brand or '',
                    'description': description or '',
                    'price': float(price),
                    'stockQuantity': stock,
                    'stock': stock,  # Add both for compatibility
                    'weight': float(weight) if weight else 0.0,
                    'dimensions': dimensions or '',
                    'imageUrl': product.image_url or '',
                    'galleryImages': gallery_images,
                    'images': gallery_images,  # Add both for compatibility
                    'isActive': True,
                    'approvalStatus': 'pending',  # ✅ Requires admin approval
                    'sqlProductId': str(product.id),  # Link to SQL for reference
                    'totalSold': 0,
                    'averageRating': 0.0,
                    'reviewCount': 0
                }
                
                firestore_product_id = create_product_firestore(product_data)
                print(f"✅ Product synced to Firestore: {firestore_product_id}")
                print(f"✅ Seller ID used: {seller_id}")
                print(f"⏳ Product pending admin approval")
            except Exception as firestore_error:
                print(f"⚠️ Firestore sync failed (product still created in SQL): {firestore_error}")
                # Don't fail the whole operation if Firestore sync fails
            
            flash('Product submitted successfully! It will be visible to buyers once approved by admin.', 'success')
            return redirect(url_for('seller_products'))
        except Exception as e:
            db.session.rollback()
            flash('Error adding product. Please try again.', 'error')
            print(f"Product creation error: {e}")
    
    # Get categories for dropdown
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    return render_template('seller/add_product.html', categories=categories)

@app.route('/seller/products/edit/<int:product_id>', methods=['GET', 'POST'])
@role_required('seller')
def edit_product(product_id):
    user = get_current_user()
    product = Product.query.filter_by(id=product_id, seller_id=user.id).first_or_404()
    
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        brand = request.form.get('brand')
        description = request.form.get('description')
        category_id = request.form.get('category')
        price = float(request.form.get('price'))
        stock = int(request.form.get('stock'))
        weight = request.form.get('weight')
        dimensions = request.form.get('dimensions')
        
        # Get category by ID
        category = Category.query.get(category_id)
        if not category:
            flash('Invalid category selected.', 'error')
            categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
            return render_template('seller/edit_product.html', product=product, categories=categories)
        
        # Update product
        product.name = name
        product.brand = brand
        product.description = description
        product.category_id = category.id
        product.price = price
        product.stock_quantity = stock
        product.weight = float(weight) if weight else None
        product.dimensions = dimensions
        # Optional product image replacement
        try:
            if 'image' in request.files and request.files['image'].filename:
                image_url = _save_uploaded_file(
                    request.files['image'], os.path.join('static', 'uploads', 'product_images')
                )
                product.image_url = image_url
        except Exception as e:
            flash(str(e), 'error')
            return render_template('seller/edit_product.html', product=product)
        
        # Handle gallery images upload
        if 'gallery_images' in request.files:
            gallery_files = request.files.getlist('gallery_images')
            if gallery_files and gallery_files[0].filename:  # Check if files were actually uploaded
                gallery_images = []
                for gallery_file in gallery_files[:5]:  # Limit to 5 images
                    if gallery_file and gallery_file.filename:
                        try:
                            gallery_url = _save_uploaded_file(
                                gallery_file, os.path.join('static', 'uploads', 'product_images')
                            )
                            gallery_images.append(gallery_url)
                        except Exception as e:
                            print(f"Error uploading gallery image: {e}")
                
                # Store gallery images as JSON array
                if gallery_images:
                    import json
                    product.gallery_images = json.dumps(gallery_images)
        
        try:
            db.session.commit()
            
            # ✅ SYNC TO FIRESTORE - Update product in Firestore for mobile app
            try:
                from firestore_helper import update_product_firestore
                
                product_data = {
                    'name': name,
                    'brand': brand or '',
                    'description': description or '',
                    'categoryId': str(category.id),
                    'category': category.name,
                    'price': float(price),
                    'stockQuantity': stock,
                    'weight': float(weight) if weight else 0.0,
                    'dimensions': dimensions or '',
                }
                
                # Add image URL if updated
                if 'image' in request.files and request.files['image'].filename:
                    product_data['imageUrl'] = product.image_url
                
                # Add gallery images if updated
                if 'gallery_images' in request.files:
                    gallery_files = request.files.getlist('gallery_images')
                    if gallery_files and gallery_files[0].filename:
                        import json
                        if product.gallery_images:
                            product_data['galleryImages'] = json.loads(product.gallery_images)
                
                # Find Firestore product by SQL ID
                from firestore_helper import get_firestore_client
                db_firestore = get_firestore_client()
                products = db_firestore.collection('products').where('sqlProductId', '==', str(product_id)).limit(1).stream()
                
                for fs_product in products:
                    update_product_firestore(fs_product.id, product_data)
                    print(f"✅ Product updated in Firestore: {fs_product.id}")
                    break
            except Exception as firestore_error:
                print(f"⚠️ Firestore sync failed (product still updated in SQL): {firestore_error}")
                # Don't fail the whole operation if Firestore sync fails
            
            flash('Product updated successfully!', 'success')
            return redirect(url_for('seller_products'))
        except Exception as e:
            db.session.rollback()
            flash('Error updating product. Please try again.', 'error')
            print(f"Product update error: {e}")
    
    # Get categories for dropdown
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    return render_template('seller/edit_product.html', product=product, categories=categories)

@app.route('/seller/products/delete/<int:product_id>')
@role_required('seller')
def delete_product(product_id):
    user = get_current_user()
    product = Product.query.filter_by(id=product_id, seller_id=user.id).first_or_404()
    
    try:
        from firestore_helper import delete_cart_items_by_product_firestore, delete_wishlist_items_by_product_firestore, get_firestore_client
        
        # Delete related records first to avoid foreign key constraints
        # Delete cart items from Firestore
        delete_cart_items_by_product_firestore(str(product_id))
        
        # Delete wishlist items from Firestore
        delete_wishlist_items_by_product_firestore(str(product_id))
        
        # ✅ SYNC TO FIRESTORE - Delete product from Firestore
        try:
            db_firestore = get_firestore_client()
            products = db_firestore.collection('products').where('sqlProductId', '==', str(product_id)).limit(1).stream()
            
            for fs_product in products:
                fs_product.reference.delete()
                print(f"✅ Product deleted from Firestore: {fs_product.id}")
                break
        except Exception as firestore_error:
            print(f"⚠️ Firestore delete failed (product still deleted from SQL): {firestore_error}")
        
        # Delete order items (if any) - still in SQL
        OrderItem.query.filter_by(product_id=product_id).delete()
        
        # Delete reviews - still in SQL
        Review.query.filter_by(product_id=product_id).delete()
        
        # Delete product approval history
        db.session.execute(text("DELETE FROM product_approval_history WHERE product_id = :pid"), {"pid": product_id})
        
        # Now delete the product
        db.session.delete(product)
        db.session.commit()
        flash('Product deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting product: {str(e)}', 'error')
        print(f"Product deletion error: {e}")
    
    return redirect(url_for('seller_products'))

@app.route('/seller/orders')
@role_required('seller')
def seller_orders():
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    
    # Try to get orders from Firestore first
    from firestore_helper import get_orders_firestore
    # Use Firebase UID for cross-platform sync
    user_firebase_id = user.firebase_uid if user.firebase_uid else str(user.id)
    all_orders = get_orders_firestore(None, 'admin')
    
    # Filter orders that contain products from this seller
    fs_seller_orders = []
    for order in all_orders:
        has_seller_item = False
        order_seller_id = str(order.get('sellerId'))
        for item in order.get('items', []):
            item_seller_id = str(item.get('sellerId'))
            item_sql_seller_id = str(item.get('sqlSellerId'))
            if (item_seller_id == str(user_firebase_id) or 
                item_seller_id == str(user.id) or
                item_sql_seller_id == str(user.id) or
                order_seller_id == str(user_firebase_id) or
                order_seller_id == str(user.id)):
                has_seller_item = True
                break
        if has_seller_item:
            fs_seller_orders.append(order)
            
    # Normalize Firestore orders
    normalized_fs_orders = [normalize_order_for_template(order) for order in fs_seller_orders]
    
    # Get SQL orders
    sql_orders = Order.query.join(OrderItem).join(Product).filter(Product.seller_id == user.id).all()
    
    # Combine both
    combined_orders = list(sql_orders) + normalized_fs_orders
    
    # Sort combined orders
    def get_order_time(order):
        dt = getattr(order, 'created_at', None) or getattr(order, 'createdAt', None)
        if dt is None:
            return datetime.min
        if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
            return dt.replace(tzinfo=None)
        return dt
        
    combined_orders.sort(key=get_order_time, reverse=True)
    
    # Manual pagination
    per_page = 10
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_orders = combined_orders[start_idx:end_idx]
    
    # Create a simple pagination object
    class SimplePagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None
    
    orders_paginated = SimplePagination(paginated_orders, page, per_page, len(combined_orders))
    
    return render_template('seller/orders.html', orders=orders_paginated)

@app.route('/seller/orders/<order_id>/status', methods=['POST'])
@role_required('seller')
def update_order_status(order_id):
    """
    Professional order status management with activity logging and notifications
    Supports both AJAX and form submissions
    """
    user = get_current_user()
    
    # Get new status from request (supports both JSON and form data)
    if request.is_json:
        new_status = request.json.get('status')
        notes = request.json.get('notes', '')
    else:
        new_status = request.form.get('status')
        notes = request.form.get('notes', '')
    
    # Seller can only update to these statuses
    seller_allowed_statuses = {'confirmed', 'preparing', 'for_pickup', 'cancelled'}
    if new_status not in seller_allowed_statuses:
        error_msg = 'Invalid status. Sellers can only confirm, prepare, or mark orders ready for pickup.'
        if request.is_json:
            return jsonify({'success': False, 'message': error_msg}), 400
        flash(error_msg, 'error')
        return redirect(url_for('seller_orders'))
    
    # Try to get order from Firestore first
    from firestore_helper import get_order_firestore, update_order_status_firestore
    order = get_order_firestore(order_id)
    
    # If not in Firestore, fall back to SQL
    if not order:
        try:
            order_id_int = int(order_id)
            order = Order.query.get_or_404(order_id_int)
            has_seller_item = OrderItem.query.filter_by(order_id=order.id, seller_id=user.id).first() is not None
            is_firestore = False
        except ValueError:
            error_msg = 'Order not found.'
            if request.is_json:
                return jsonify({'success': False, 'message': error_msg}), 404
            flash(error_msg, 'error')
            return redirect(url_for('seller_orders'))
    else:
        # Verify the order belongs to this seller
        has_seller_item = any(item.get('sellerId') == str(user.id) for item in order.get('items', []))
        is_firestore = True
    
    if not has_seller_item:
        error_msg = 'You cannot update this order.'
        if request.is_json:
            return jsonify({'success': False, 'message': error_msg}), 403
        flash(error_msg, 'error')
        return redirect(url_for('seller_orders'))
    
    try:
        # Get old status based on data source
        old_status = order.get('status') if is_firestore else order.status
        
        # Update status
        if is_firestore:
            update_order_status_firestore(order_id, new_status, str(user.id))
            # Also update SQL order if it exists
            try:
                sql_order = Order.query.filter_by(firestore_order_id=order_id).first()
                if sql_order:
                    sql_order.status = new_status
                    if new_status == 'for_pickup' and not sql_order.shipped_at:
                        sql_order.shipped_at = utc_now()
                    db.session.commit()
            except:
                pass
        else:
            order.status = new_status
            # Track timestamps
            if new_status == 'for_pickup' and not order.shipped_at:
                order.shipped_at = utc_now()
            
            # Sync status to Firestore so mobile riders can see it
            if getattr(order, 'firestore_order_id', None):
                try:
                    update_order_status_firestore(order.firestore_order_id, new_status, str(user.id))
                except Exception as e:
                    print(f"Failed to sync status to Firestore: {e}")
            elif new_status == 'for_pickup':
                # Sync new SQL order to Firestore so mobile riders can see and pick it up
                try:
                    from firestore_helper import create_order_firestore
                    fs_items = []
                    for item in order.order_items:
                        product = Product.query.get(item.product_id)
                        fs_items.append({
                            'productId': str(item.product_id),
                            'productName': product.name if product else 'Unknown',
                            'productImage': product.image_url if product else '',
                            'price': float(item.unit_price),
                            'quantity': item.quantity,
                            'sellerId': str(item.seller_id),
                            'sqlSellerId': str(item.seller_id)
                        })
                    
                    buyer = User.query.get(order.buyer_id)
                    fs_order_data = {
                        'buyerId': str(order.buyer_id),
                        'sellerId': str(user.firebase_uid) if getattr(user, 'firebase_uid', None) else str(user.id),
                        'riderId': None,
                        'name': buyer.full_name if buyer else 'Unknown',
                        'address': order.shipping_address or 'Unknown Address',
                        'phone': buyer.phone if buyer and buyer.phone else '00000000000',
                        'items': fs_items,
                        'total': float(order.total_amount),
                        'totalAmount': float(order.total_amount),
                        'status': new_status,
                        'paymentStatus': order.payment_status or 'pending',
                        'sqlOrderId': str(order.id)
                    }
                    fs_order_id = create_order_firestore(fs_order_data)
                    order.firestore_order_id = fs_order_id
                    print(f"Synced SQL order {order.id} to Firestore: {fs_order_id}")
                except Exception as e:
                    print(f"Failed to create order in Firestore: {e}")
            
            # Log the status change (SQL only)
            log_order_status_change(
                order_id=order.id,
                user_id=user.id,
                user_role='seller',
                old_status=old_status,
                new_status=new_status,
                notes=notes
            )
            db.session.commit()
        
        # Get order details for notifications
        order_number = order.get('orderNumber') if is_firestore else order.order_number
        buyer_id = int(order.get('buyerId')) if is_firestore else order.buyer_id
        total_amount = order.get('totalAmount') if is_firestore else order.total_amount
        
        # Send notifications based on status (SQL only for now)
        if not is_firestore:
            if new_status == 'confirmed':
                # Notify buyer
                create_notification(
                    user_id=buyer_id,
                    notification_type='order_update',
                    category='order',
                    title='🎉 Order Confirmed!',
                    message=f'Your order #{order_number} has been confirmed by the seller.',
                    priority='medium',
                    action_url=url_for('buyer_orders'),
                    action_text='View Orders'
                )
                
            elif new_status == 'preparing':
                # Notify buyer
                create_notification(
                    user_id=buyer_id,
                    notification_type='order_update',
                    category='order',
                    title='📦 Order Being Prepared',
                    message=f'Your order #{order_number} is now being prepared.',
                    priority='medium',
                    action_url=url_for('buyer_orders'),
                    action_text='View Orders'
                )
                
            elif new_status == 'for_pickup':
                # Notify buyer
                create_notification(
                    user_id=buyer_id,
                    notification_type='order_update',
                    category='order',
                    title='🚚 Order Ready for Pickup',
                    message=f'Your order #{order_number} is ready and waiting for rider pickup.',
                    priority='medium',
                    action_url=url_for('buyer_orders'),
                    action_text='View Orders'
                )
                
                # Notify all approved riders
                approved_riders = User.query.filter_by(
                    role='rider', 
                    approval_status='approved', 
                    is_active=True
                ).all()
                
                for rider in approved_riders:
                    create_notification(
                        user_id=rider.id,
                        notification_type='order_update',
                        category='delivery',
                        title='🆕 New Delivery Available',
                        message=f'Order #{order_number} ready for pickup. Earn: ₱{float(total_amount) * 0.05:.2f}',
                        priority='medium',
                        action_url=url_for('rider_orders'),
                        action_text='View Order'
                    )
                    
            elif new_status == 'cancelled':
                # Notify buyer
                create_notification(
                    user_id=buyer_id,
                    notification_type='order_update',
                    category='order',
                    title='❌ Order Cancelled',
                    message=f'Your order #{order_number} has been cancelled by the seller.',
                    priority='high',
                    action_url=url_for('buyer_orders'),
                    action_text='View Orders'
                )
        
        # Send automatic message to buyer about status update (SQL only for now)
        if not is_firestore:
            status_messages_chat = {
                'confirmed': f"Hello! Your order #{order_number} has been confirmed. We'll start preparing your items shortly. Thank you for your purchase!",
                'preparing': f"Good news! We're now preparing your order #{order_number}. Your items will be ready for pickup soon!",
                'for_pickup': f"Your order #{order_number} is now ready for pickup! Our delivery rider will collect it soon and bring it to you.",
            'cancelled': f"We regret to inform you that your order #{order.order_number} has been cancelled. {notes if notes else 'Please contact us if you have any questions or concerns.'}"
        }
        
        if new_status in status_messages_chat:
            try:
                send_automatic_message(
                    sender_id=user.id,
                    receiver_id=order.buyer_id,
                    message_content=status_messages_chat[new_status],
                    order_id=order.id
                )
            except Exception as e:
                print(f"Error sending automatic message: {e}")
        
        # Success messages
        status_messages = {
            'confirmed': '✅ Order confirmed successfully!',
            'preparing': '📦 Order marked as preparing.',
            'for_pickup': '🚚 Order ready for pickup. Riders have been notified!',
            'cancelled': '❌ Order cancelled.'
        }
        
        success_msg = status_messages.get(new_status, 'Order status updated.')
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': success_msg,
                'new_status': new_status,
                'old_status': old_status,
                'updated_at': order.last_status_update.isoformat() if order.last_status_update else None
            })
        
        flash(success_msg, 'success')
        return redirect(url_for('seller_orders'))
        
    except Exception as e:
        db.session.rollback()
        error_msg = f'Failed to update order status: {str(e)}'
        print(f"Update order status error: {e}")
        
        if request.is_json:
            return jsonify({'success': False, 'message': 'Failed to update status'}), 500
        
        flash('Failed to update order status.', 'error')
        return redirect(url_for('seller_orders'))

# ==================== ADMIN ROUTES ====================

@app.route('/admin/dashboard')
@role_required('admin')
def admin_dashboard():
    """Enhanced admin dashboard with comprehensive analytics"""
    user = get_current_user()
    
    # Get comprehensive analytics
    analytics = get_dashboard_analytics()
    
    # Get pending approvals
    pending_buyers = User.query.filter_by(role='buyer', approval_status='pending').count()
    pending_sellers = User.query.filter_by(role='seller', approval_status='pending').count()
    pending_riders = User.query.filter_by(role='rider', approval_status='pending').count()
    pending_products = Product.query.filter_by(approval_status='pending').count()
    
    # Get platform settings
    commission_rate = get_platform_setting('commission_rate', '5.0')
    
    # Get recent activity for quick overview
    recent_orders = Order.query.join(User, Order.buyer_id == User.id).order_by(Order.created_at.desc()).limit(5).all()
    recent_complaints = Complaint.query.filter_by(status='open').order_by(Complaint.created_at.desc()).limit(5).all()
    
    # Get top performing sellers
    top_sellers = db.session.query(
        User.id, User.first_name, User.last_name, User.business_name,
        db.func.sum(Commission.order_amount).label('total_sales'),
        db.func.count(Commission.id).label('order_count')
    ).join(Commission).filter(
        Commission.status == 'collected'
    ).group_by(User.id).order_by(db.desc('total_sales')).limit(5).all()
    
    # Get best selling products
    best_products = db.session.query(
        Product.id, Product.name, Product.price,
        db.func.sum(OrderItem.quantity).label('total_sold'),
        db.func.sum(OrderItem.total_price).label('total_revenue')
    ).join(OrderItem).join(Order).filter(
        Order.status == 'completed'
    ).group_by(Product.id).order_by(db.desc('total_sold')).limit(5).all()
    
    return render_template('admin/dashboard_enhanced.html',
                         analytics=analytics,
                         pending_buyers=pending_buyers,
                         pending_sellers=pending_sellers,
                         pending_riders=pending_riders,
                         pending_products=pending_products,
                         commission_rate=commission_rate,
                         recent_orders=recent_orders,
                         recent_complaints=recent_complaints,
                         top_sellers=top_sellers,
                         best_products=best_products)

@app.route('/admin/analytics/realtime-data')
@role_required('admin')
def admin_analytics_realtime():
    """API endpoint for real-time analytics data"""
    try:
        # Get orders per day for last 30 days
        from datetime import datetime, timedelta
        
        orders_per_day = []
        today = datetime.now().date()
        
        for i in range(29, -1, -1):
            date = today - timedelta(days=i)
            day_start = datetime.combine(date, datetime.min.time())
            day_end = datetime.combine(date, datetime.max.time())
            
            # Count orders for this day
            order_count = Order.query.filter(
                Order.created_at >= day_start,
                Order.created_at <= day_end
            ).count()
            
            orders_per_day.append(order_count)
        
        return jsonify({
            'success': True,
            'orders_per_day': orders_per_day
        })
    except Exception as e:
        print(f"Error in realtime analytics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/admin/approvals')
@role_required('admin')
def admin_approvals():
    """Enhanced admin approval management page with search and pagination"""
    # Get filter parameters
    role_filter = request.args.get('role', 'all')
    status_filter = request.args.get('status', 'pending')
    search_query = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'created_at')
    sort_order = request.args.get('order', 'desc')
    page = request.args.get('page', 1, type=int)
    
    # Build query
    query = User.query.filter(User.role != 'admin')  # Exclude admin users
    
    # Apply role filter
    if role_filter != 'all':
        query = query.filter_by(role=role_filter)
    
    # Apply status filter
    if status_filter != 'all':
        query = query.filter_by(approval_status=status_filter)
    
    # Apply search filter
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            db.or_(
                User.first_name.ilike(search_pattern),
                User.last_name.ilike(search_pattern),
                User.username.ilike(search_pattern),
                User.email.ilike(search_pattern),
                User.business_name.ilike(search_pattern)
            )
        )
    
    # Apply sorting
    if sort_by == 'name':
        if sort_order == 'asc':
            query = query.order_by(User.first_name.asc(), User.last_name.asc())
        else:
            query = query.order_by(User.first_name.desc(), User.last_name.desc())
    elif sort_by == 'role':
        if sort_order == 'asc':
            query = query.order_by(User.role.asc())
        else:
            query = query.order_by(User.role.desc())
    elif sort_by == 'status':
        if sort_order == 'asc':
            query = query.order_by(User.approval_status.asc())
        else:
            query = query.order_by(User.approval_status.desc())
    else:  # created_at
        if sort_order == 'asc':
            query = query.order_by(User.created_at.asc())
        else:
            query = query.order_by(User.created_at.desc())
    
    # Paginate results
    users = query.paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Get summary statistics
    stats = {
        'total_pending': User.query.filter_by(approval_status='pending').filter(User.role != 'admin').count(),
        'pending_buyers': User.query.filter_by(role='buyer', approval_status='pending').count(),
        'pending_sellers': User.query.filter_by(role='seller', approval_status='pending').count(),
        'pending_riders': User.query.filter_by(role='rider', approval_status='pending').count(),
        'total_approved': User.query.filter_by(approval_status='approved').filter(User.role != 'admin').count(),
        'total_rejected': User.query.filter_by(approval_status='rejected').filter(User.role != 'admin').count()
    }
    
    return render_template('admin/approvals.html', 
                         users=users,
                         stats=stats,
                         current_role=role_filter, 
                         current_status=status_filter,
                         search_query=search_query,
                         sort_by=sort_by,
                         sort_order=sort_order)

@app.route('/admin/user/<int:user_id>/details')
@role_required('admin')
def view_user_details(user_id):
    """View detailed user information for approval review"""
    user = User.query.get_or_404(user_id)
    
    # Get user's uploaded documents
    documents = {
        'id_document': user.id_document,
        'business_permit': user.business_permit,
        'dti_certification': user.dti_certification,
        'profile_image': user.profile_image
    }
    
    # Get approval history if any
    approval_history = None
    if user.approved_by:
        approver = User.query.get(user.approved_by)
        approval_history = {
            'approver': approver,
            'approved_at': user.approved_at,
            'status': user.approval_status
        }
    
    return render_template('admin/user_details.html', 
                         user=user, 
                         documents=documents,
                         approval_history=approval_history)

@app.route('/admin/user/<int:user_id>/document/<document_type>')
@role_required('admin')
def view_document(user_id, document_type):
    """View or download user uploaded documents"""
    user = User.query.get_or_404(user_id)
    
    document_path = None
    if document_type == 'id_document' and user.id_document:
        document_path = user.id_document
    elif document_type == 'business_permit' and user.business_permit:
        document_path = user.business_permit
    elif document_type == 'dti_certification' and user.dti_certification:
        document_path = user.dti_certification
    elif document_type == 'profile_image' and user.profile_image:
        document_path = user.profile_image
    
    if document_path:
        try:
            # Document path is stored as web path like "/static/uploads/business_docs/file.pdf"
            # Remove leading slash and "static/" to get the relative path
            if document_path.startswith('/'):
                document_path = document_path[1:]
            if document_path.startswith('static/'):
                document_path = document_path[7:]  # Remove "static/"
            
            # Now document_path should be like "uploads/business_docs/file.pdf"
            # Split to get directory and filename
            directory = os.path.dirname(document_path)
            filename = os.path.basename(document_path)
            
            # Construct full directory path from BASE_DIR
            full_directory = os.path.join(BASE_DIR, 'static', directory)
            
            print(f"[DEBUG] Serving document:")
            print(f"  Original path: {user.id_document if document_type == 'id_document' else user.business_permit if document_type == 'business_permit' else user.dti_certification if document_type == 'dti_certification' else user.profile_image}")
            print(f"  Directory: {full_directory}")
            print(f"  Filename: {filename}")
            
            # Serve the file
            return send_from_directory(full_directory, filename)
        except Exception as e:
            print(f"[ERROR] Error serving document: {e}")
            flash(f'Document not found or cannot be accessed.', 'error')
            return redirect(url_for('view_user_details', user_id=user_id))
    else:
        flash('Document not available.', 'warning')
        return redirect(url_for('view_user_details', user_id=user_id))

@app.route('/admin/approve/<int:user_id>', methods=['POST'])
@role_required('admin')
def approve_user(user_id):
    """Approve a user registration"""
    user = User.query.get_or_404(user_id)
    admin_user = get_current_user()
    
    try:
        user.approval_status = 'approved'
        user.is_active = True  # Activate the account
        user.approved_by = admin_user.id
        user.approved_at = utc_now()
        
        # Send approval notification using new system
        notify_registration_status(user, approved=True, admin_user=admin_user)
        
        # Log admin action
        log_admin_action(admin_user.id, 'approve_user', 'user', user.id, 
                        f"Approved {user.role} registration for {user.email}")
        
        db.session.commit()
        flash(f'{user.role.title()} {user.first_name} {user.last_name} has been approved.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Error approving user.', 'error')
        print(f"Approve user error: {e}")
    
    return redirect(url_for('admin_approvals'))

@app.route('/admin/users/bulk-approve', methods=['POST'])
@role_required('admin')
def bulk_approve_users():
    """Bulk approve multiple users"""
    admin_user = get_current_user()
    user_ids = request.form.getlist('user_ids')
    
    if not user_ids:
        flash('No users selected for approval.', 'error')
        return redirect(url_for('admin_approvals'))
    
    try:
        approved_count = 0
        for user_id in user_ids:
            user = User.query.get(user_id)
            if user and user.approval_status == 'pending':
                user.approval_status = 'approved'
                user.is_active = True
                user.approved_by = admin_user.id
                user.approved_at = utc_now()
                
                # Send approval notification using new system
                notify_registration_status(user, approved=True, admin_user=admin_user)
                
                # Log admin action
                log_admin_action(admin_user.id, 'bulk_approve_user', 'user', user.id,
                                f"Bulk approved {user.role}: {user.username}")
                approved_count += 1
        
        db.session.commit()
        flash(f'Successfully approved {approved_count} users.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Error during bulk approval. Please try again.', 'error')
        print(f"Bulk approval error: {e}")
    
    return redirect(url_for('admin_approvals'))

@app.route('/admin/reject_user/<int:user_id>', methods=['POST'])
@role_required('admin')
def reject_user(user_id):
    """Reject a user registration"""
    user = User.query.get_or_404(user_id)
    admin_user = get_current_user()
    
    try:
        user.approval_status = 'rejected'
        user.is_active = False  # Ensure account remains inactive
        user.approved_by = admin_user.id
        user.approved_at = utc_now()
        
        # Send rejection notification using new system
        notify_registration_status(user, approved=False, admin_user=admin_user)
        
        # Log admin action
        log_admin_action(admin_user.id, 'reject_user', 'user', user.id, 
                        f"Rejected {user.role} registration for {user.email}")
        
        db.session.commit()
        flash(f'{user.role.title()} {user.first_name} {user.last_name} has been rejected.', 'warning')
        
    except Exception as e:
        db.session.rollback()
        flash('Error rejecting user.', 'error')
        print(f"Reject user error: {e}")
    
    return redirect(url_for('admin_approvals'))

@app.route('/admin/auto-confirm')
@role_required('admin')
def run_auto_confirm():
    """Manually trigger auto-confirmation of orders"""
    try:
        auto_confirm_orders()
        flash('Auto-confirmation process completed.', 'success')
    except Exception as e:
        flash(f'Error running auto-confirmation: {e}', 'error')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/settings', methods=['GET', 'POST'])
@role_required('admin')
def admin_settings():
    """Admin platform settings management"""
    if request.method == 'POST':
        try:
            # Site Information
            set_platform_setting('site_name', request.form.get('site_name', 'Daily Fitness'), 'Site name')
            set_platform_setting('site_description', request.form.get('site_description', ''), 'Site description')
            set_platform_setting('contact_email', request.form.get('contact_email', ''), 'Contact email')
            set_platform_setting('contact_phone', request.form.get('contact_phone', ''), 'Contact phone')
            
            # Business Settings
            set_platform_setting('commission_rate', request.form.get('commission_rate', '5.0'), 'Platform commission percentage')
            set_platform_setting('tax_rate', request.form.get('tax_rate', '12.0'), 'Tax rate percentage')
            set_platform_setting('shipping_fee', request.form.get('shipping_fee', '50.00'), 'Default shipping fee')
            set_platform_setting('free_shipping_threshold', request.form.get('free_shipping_threshold', '1000.00'), 'Free shipping threshold')
            
            # System Preferences
            set_platform_setting('auto_approve_buyers', '1' if request.form.get('auto_approve_buyers') else '0', 'Auto-approve buyer registrations')
            set_platform_setting('require_email_verification', '1' if request.form.get('require_email_verification') else '0', 'Require email verification')
            set_platform_setting('enable_notifications', '1' if request.form.get('enable_notifications') else '0', 'Enable system notifications')
            
            # Order Settings
            set_platform_setting('auto_confirm_hours', request.form.get('auto_confirm_hours', '24'), 'Auto-confirm orders after hours')
            set_platform_setting('max_order_items', request.form.get('max_order_items', '20'), 'Maximum items per order')
            set_platform_setting('allow_cod', '1' if request.form.get('allow_cod') else '0', 'Allow Cash on Delivery')
            
            flash('Settings updated successfully!', 'success')
        except Exception as e:
            flash('Error updating settings. Please try again.', 'error')
            print(f"Settings update error: {e}")
    
    # Get current settings
    settings = {
        # Site Information
        'site_name': get_platform_setting('site_name', 'Daily Fitness'),
        'site_description': get_platform_setting('site_description', 'Your one-stop shop for gym equipment and fitness gear'),
        'contact_email': get_platform_setting('contact_email', 'admin@gymstore.com'),
        'contact_phone': get_platform_setting('contact_phone', '+63 123 456 7890'),
        
        # Business Settings
        'commission_rate': get_platform_setting('commission_rate', '5.0'),
        'tax_rate': get_platform_setting('tax_rate', '12.0'),
        'shipping_fee': get_platform_setting('shipping_fee', '50.00'),
        'free_shipping_threshold': get_platform_setting('free_shipping_threshold', '1000.00'),
        
        # System Preferences
        'auto_approve_buyers': get_platform_setting('auto_approve_buyers', '0') == '1',
        'require_email_verification': get_platform_setting('require_email_verification', '1') == '1',
        'enable_notifications': get_platform_setting('enable_notifications', '1') == '1',
        
        # Order Settings
        'auto_confirm_hours': get_platform_setting('auto_confirm_hours', '24'),
        'max_order_items': get_platform_setting('max_order_items', '20'),
        'allow_cod': get_platform_setting('allow_cod', '1') == '1'
    }
    
    return render_template('admin/settings.html', settings=settings)

# =====================================================
# ADMIN TESTIMONIALS MANAGEMENT ROUTES
# =====================================================

@app.route('/admin/testimonials')
@role_required('admin')
def admin_testimonials():
    """Admin testimonials management"""
    # Get featured testimonials
    featured = FeaturedTestimonial.query.order_by(FeaturedTestimonial.display_order).all()
    
    # Get available reviews (5-star reviews not already featured)
    available_reviews = Review.query.filter(
        Review.rating == 5,
        ~Review.id.in_([ft.review_id for ft in featured])
    ).order_by(Review.created_at.desc()).limit(50).all()
    
    return render_template('admin/testimonials.html', 
                         featured_testimonials=featured, 
                         available_reviews=available_reviews)

@app.route('/admin/testimonials/add', methods=['POST'])
@role_required('admin')
def admin_add_testimonial():
    """Add a review as featured testimonial"""
    try:
        review_id = request.form.get('review_id', type=int)
        display_order = request.form.get('display_order', type=int) or 0
        
        if not review_id:
            flash('Review ID is required', 'error')
            return redirect(url_for('admin_testimonials'))
        
        # Check if review exists and is 5-star
        review = Review.query.get(review_id)
        if not review or review.rating < 5:
            flash('Only 5-star reviews can be featured', 'error')
            return redirect(url_for('admin_testimonials'))
        
        # Check if already featured
        existing = FeaturedTestimonial.query.filter_by(review_id=review_id).first()
        if existing:
            flash('This review is already featured', 'error')
            return redirect(url_for('admin_testimonials'))
        
        # Add as featured testimonial
        user = get_current_user()
        testimonial = FeaturedTestimonial(
            review_id=review_id,
            display_order=display_order,
            created_by=user.id
        )
        
        db.session.add(testimonial)
        db.session.commit()
        
        flash('Testimonial added successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding testimonial: {str(e)}', 'error')
    
    return redirect(url_for('admin_testimonials'))

@app.route('/admin/testimonials/remove/<int:testimonial_id>', methods=['POST'])
@role_required('admin')
def admin_remove_testimonial(testimonial_id):
    """Remove a featured testimonial"""
    try:
        testimonial = FeaturedTestimonial.query.get_or_404(testimonial_id)
        db.session.delete(testimonial)
        db.session.commit()
        
        flash('Testimonial removed successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error removing testimonial: {str(e)}', 'error')
    
    return redirect(url_for('admin_testimonials'))

@app.route('/admin/testimonials/toggle/<int:testimonial_id>', methods=['POST'])
@role_required('admin')
def admin_toggle_testimonial(testimonial_id):
    """Toggle testimonial active status"""
    try:
        testimonial = FeaturedTestimonial.query.get_or_404(testimonial_id)
        testimonial.is_active = not testimonial.is_active
        db.session.commit()
        
        status = 'activated' if testimonial.is_active else 'deactivated'
        flash(f'Testimonial {status} successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating testimonial: {str(e)}', 'error')
    
    return redirect(url_for('admin_testimonials'))

@app.route('/admin/testimonials/reorder', methods=['POST'])
@role_required('admin')
def admin_reorder_testimonials():
    """Reorder testimonials"""
    try:
        order_data = request.get_json()
        
        for item in order_data:
            testimonial_id = item.get('id')
            new_order = item.get('order')
            
            testimonial = FeaturedTestimonial.query.get(testimonial_id)
            if testimonial:
                testimonial.display_order = new_order
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Order updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# =====================================================
# ADMIN CATEGORIES MANAGEMENT ROUTES
# =====================================================

@app.route('/admin/categories')
@role_required('admin')
def admin_categories():
    """Admin categories management"""
    categories = Category.query.order_by(Category.name).all()
    
    # Get product count for each category
    for category in categories:
        category.product_count = Product.query.filter_by(category_id=category.id).count()
    
    return render_template('admin/categories.html', categories=categories)

@app.route('/admin/categories/add', methods=['POST'])
@role_required('admin')
def admin_add_category():
    """Add new category"""
    print("DEBUG: Add category route called")
    try:
        name = request.form.get('name')
        description = request.form.get('description')
        image_url = request.form.get('image_url')
        
        print(f"DEBUG: name={name}, description={description}, image_url={image_url}")
        
        if not name:
            print("DEBUG: No name provided")
            flash('Category name is required', 'error')
            return redirect(url_for('admin_categories'))
        
        # Handle image upload
        if 'image' in request.files:
            file = request.files['image']
            print(f"DEBUG: File uploaded: {file.filename}")
            if file and file.filename:
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"category_{timestamp}_{filename}"
                
                # Use static/uploads folder
                upload_folder = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
                os.makedirs(upload_folder, exist_ok=True)  # Create folder if it doesn't exist
                
                filepath = os.path.join(upload_folder, filename)
                file.save(filepath)
                image_url = f"/static/uploads/{filename}"
                print(f"DEBUG: Image saved to {filepath}")
        
        print(f"DEBUG: Creating category with image={image_url}")
        category = Category(name=name, description=description, image=image_url, is_active=True)
        db.session.add(category)
        db.session.commit()
        
        print(f"DEBUG: Category added successfully! ID={category.id}")
        flash('Category added successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding category: {str(e)}', 'error')
        print(f"ERROR adding category: {e}")
        import traceback
        traceback.print_exc()
    
    return redirect(url_for('admin_categories'))

@app.route('/admin/categories/edit/<int:category_id>', methods=['POST'])
@role_required('admin')
def admin_edit_category(category_id):
    """Edit category"""
    try:
        category = Category.query.get_or_404(category_id)
        category.name = request.form.get('name')
        category.description = request.form.get('description')
        
        # Handle image upload
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"category_{timestamp}_{filename}"
                
                # Use static/uploads folder
                upload_folder = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
                os.makedirs(upload_folder, exist_ok=True)
                
                filepath = os.path.join(upload_folder, filename)
                file.save(filepath)
                category.image = f"/static/uploads/{filename}"
        
        # Or use image URL if provided
        image_url = request.form.get('image_url')
        if image_url:
            category.image = image_url
        
        db.session.commit()
        flash('Category updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating category: {str(e)}', 'error')
    
    return redirect(url_for('admin_categories'))

@app.route('/admin/categories/delete/<int:category_id>', methods=['POST'])
@role_required('admin')
def admin_delete_category(category_id):
    """Delete category"""
    try:
        category = Category.query.get_or_404(category_id)
        
        # Check if category has products
        product_count = Product.query.filter_by(category_id=category_id).count()
        if product_count > 0:
            flash(f'Cannot delete category with {product_count} products', 'error')
            return redirect(url_for('admin_categories'))
        
        db.session.delete(category)
        db.session.commit()
        flash('Category deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting category: {str(e)}', 'error')
    
    return redirect(url_for('admin_categories'))

# =====================================================
# ADMIN REVIEWS MANAGEMENT ROUTES
# =====================================================

@app.route('/admin/reviews')
@role_required('admin')
def admin_reviews():
    """Admin reviews management"""
    page = request.args.get('page', 1, type=int)
    rating_filter = request.args.get('rating', type=int)
    per_page = 20
    
    query = Review.query
    
    if rating_filter:
        query = query.filter_by(rating=rating_filter)
    
    reviews = query.order_by(Review.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get statistics
    total_reviews = Review.query.count()
    five_star = Review.query.filter_by(rating=5).count()
    four_star = Review.query.filter_by(rating=4).count()
    three_star = Review.query.filter_by(rating=3).count()
    two_star = Review.query.filter_by(rating=2).count()
    one_star = Review.query.filter_by(rating=1).count()
    
    return render_template('admin/reviews.html',
                         reviews=reviews,
                         total_reviews=total_reviews,
                         five_star=five_star,
                         four_star=four_star,
                         three_star=three_star,
                         two_star=two_star,
                         one_star=one_star,
                         rating_filter=rating_filter)

@app.route('/admin/reviews/delete/<int:review_id>', methods=['POST'])
@role_required('admin')
def admin_delete_review(review_id):
    """Delete review"""
    try:
        review = Review.query.get_or_404(review_id)
        db.session.delete(review)
        db.session.commit()
        flash('Review deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting review: {str(e)}', 'error')
    
    return redirect(url_for('admin_reviews'))

# =====================================================
# ADMIN REPORTS ROUTES
# =====================================================

@app.route('/admin/reports')
@role_required('admin')
def admin_reports():
    """Admin reports and analytics"""
    from datetime import datetime, timedelta
    from sqlalchemy import func
    
    # Date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # Sales report - include both delivered and completed orders
    total_sales = db.session.query(func.sum(Order.total_amount)).filter(
        Order.status.in_(['delivered', 'completed']),
        Order.created_at >= start_date
    ).scalar() or 0
    
    # Orders report
    total_orders = Order.query.filter(Order.created_at >= start_date).count()
    
    # Top products - simplified without OrderItem
    top_products = []
    
    # Top customers - simplified query
    try:
        # First, let's get all completed/delivered orders with buyer info
        completed_orders = Order.query.filter(
            Order.status.in_(['delivered', 'completed']),
            Order.created_at >= start_date,
            Order.buyer_id.isnot(None)
        ).all()
        
        print(f"DEBUG: Found {len(completed_orders)} completed orders in last 30 days")
        
        # Group by customer manually
        customer_stats = {}
        for order in completed_orders:
            buyer_id = order.buyer_id
            print(f"DEBUG: Processing order {order.id}, buyer_id={buyer_id}, amount={order.total_amount}")
            
            if buyer_id is None:
                print(f"  WARNING: Order {order.id} has no buyer_id!")
                continue
                
            if buyer_id not in customer_stats:
                buyer = User.query.get(buyer_id)
                if buyer:
                    print(f"  Found buyer: {buyer.first_name} {buyer.last_name}")
                    customer_stats[buyer_id] = {
                        'name': f"{buyer.first_name} {buyer.last_name}",
                        'orders': 0,
                        'total': 0
                    }
                else:
                    print(f"  WARNING: No user found for buyer_id {buyer_id}")
            
            if buyer_id in customer_stats:
                customer_stats[buyer_id]['orders'] += 1
                customer_stats[buyer_id]['total'] += float(order.total_amount or 0)
        
        # Convert to list and sort
        top_customers = []
        for buyer_id, stats in customer_stats.items():
            top_customers.append((
                stats['name'].split()[0],  # first name
                ' '.join(stats['name'].split()[1:]),  # last name
                stats['orders'],
                stats['total']
            ))
        
        top_customers.sort(key=lambda x: x[3], reverse=True)
        top_customers = top_customers[:10]
        
        print(f"DEBUG: Found {len(top_customers)} unique customers")
        for customer in top_customers:
            print(f"  - {customer[0]} {customer[1]}: {customer[2]} orders, ₱{customer[3]:.2f}")
            
    except Exception as e:
        print(f"ERROR in top customers query: {e}")
        top_customers = []
    
    return render_template('admin/reports.html',
                         total_sales=total_sales,
                         total_orders=total_orders,
                         top_products=top_products,
                         top_customers=top_customers,
                         start_date=start_date,
                         end_date=end_date)

# =====================================================
# ADMIN ACTIVITY LOGS ROUTES
# =====================================================

@app.route('/admin/activity-logs')
@role_required('admin')
def admin_activity_logs():
    """Admin activity logs"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Get recent orders as activity
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(50).all()
    
    # Get recent user registrations
    recent_users = User.query.order_by(User.created_at.desc()).limit(20).all()
    
    # Get recent reviews
    recent_reviews = Review.query.order_by(Review.created_at.desc()).limit(20).all()
    
    return render_template('admin/activity_logs.html',
                         recent_orders=recent_orders,
                         recent_users=recent_users,
                         recent_reviews=recent_reviews)

# =====================================================
# ADMIN WARNING MANAGEMENT ROUTES
# =====================================================

@app.route('/admin/warnings')
@role_required('admin')
def admin_warnings():
    """Admin warning management page"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    seller_id = request.args.get('seller_id', type=int)
    
    # Base query
    query = SellerWarning.query
    
    # Apply filters
    if seller_id:
        query = query.filter_by(seller_id=seller_id)
    
    if status_filter == 'unacknowledged':
        query = query.filter_by(is_acknowledged=False)
    elif status_filter == 'acknowledged':
        query = query.filter_by(is_acknowledged=True)
    elif status_filter == 'resolved':
        query = query.filter_by(is_resolved=True)
    elif status_filter == 'critical':
        query = query.filter(
            (SellerWarning.severity == 'critical') | 
            (SellerWarning.offense_level >= 3)
        )
    
    # Get paginated warnings
    warnings = query.order_by(SellerWarning.created_at.desc()).paginate(
        page=page, per_page=15, error_out=False
    )
    
    # Get statistics
    total_warnings = SellerWarning.query.count()
    unacknowledged_warnings = SellerWarning.query.filter_by(is_acknowledged=False).count()
    critical_warnings = SellerWarning.query.filter(
        (SellerWarning.severity == 'critical') | 
        (SellerWarning.offense_level >= 3)
    ).count()
    
    # Get sellers for filter dropdown
    sellers = User.query.filter_by(role='seller').order_by(User.first_name, User.last_name).all()
    
    return render_template('admin/warnings.html',
                         warnings=warnings,
                         total_warnings=total_warnings,
                         unacknowledged_warnings=unacknowledged_warnings,
                         critical_warnings=critical_warnings,
                         sellers=sellers,
                         current_status=status_filter,
                         selected_seller=seller_id)

@app.route('/admin/warnings/create', methods=['GET', 'POST'])
@role_required('admin')
def admin_create_warning():
    """Create a new seller warning"""
    if request.method == 'POST':
        try:
            seller_id = request.form.get('seller_id', type=int)
            warning_type = request.form.get('warning_type')
            severity = request.form.get('severity', 'medium')
            title = request.form.get('title')
            message = request.form.get('message')
            action_required = request.form.get('action_required')
            policy_link = request.form.get('policy_link')
            admin_notes = request.form.get('admin_notes')
            
            # Parse deadline if provided
            deadline = None
            deadline_str = request.form.get('deadline')
            if deadline_str:
                try:
                    deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    pass
            
            # Validate required fields
            if not all([seller_id, warning_type, title, message]):
                flash('Please fill in all required fields.', 'error')
                return redirect(url_for('admin_create_warning'))
            
            # Create warning
            admin_user = get_current_user()
            warning, notification = create_seller_warning(
                seller_id=seller_id,
                admin_id=admin_user.id,
                warning_type=warning_type,
                title=title,
                message=message,
                severity=severity,
                action_required=action_required,
                deadline=deadline,
                policy_link=policy_link,
                admin_notes=admin_notes
            )
            
            if warning:
                flash(f'Warning issued successfully to seller. Notification sent.', 'success')
                return redirect(url_for('admin_warnings'))
            else:
                flash('Error creating warning. Please try again.', 'error')
                
        except Exception as e:
            flash('Error creating warning. Please try again.', 'error')
            print(f"Warning creation error: {e}")
    
    # Get sellers for dropdown
    sellers = User.query.filter_by(role='seller', is_active=True).order_by(User.first_name, User.last_name).all()
    
    return render_template('admin/create_warning.html', sellers=sellers)

@app.route('/admin/warnings/<int:warning_id>')
@role_required('admin')
def admin_warning_details(warning_id):
    """View warning details"""
    warning = SellerWarning.query.get_or_404(warning_id)
    return render_template('admin/warning_details.html', warning=warning)

@app.route('/admin/warnings/<int:warning_id>/resolve', methods=['POST'])
@role_required('admin')
def admin_resolve_warning(warning_id):
    """Mark warning as resolved"""
    warning = SellerWarning.query.get_or_404(warning_id)
    admin_user = get_current_user()
    
    if not warning.is_resolved:
        warning.is_resolved = True
        warning.resolved_at = utc_now()
        
        # Add admin notes if provided
        admin_notes = request.json.get('notes') if request.is_json else request.form.get('notes')
        if admin_notes:
            existing_notes = warning.admin_notes or ''
            warning.admin_notes = f"{existing_notes}\n\n[RESOLVED] {admin_notes}".strip()
        
        db.session.commit()
        
        # Notify seller
        create_notification(
            user_id=warning.seller_id,
            notification_type='admin_action',
            category='system',
            title=f"Warning Resolved: {warning.title}",
            message=f"Your warning has been marked as resolved by admin. Thank you for addressing the issue.",
            priority='medium',
            data={'warning_id': warning.id, 'admin_id': admin_user.id}
        )
        
        flash('Warning marked as resolved.', 'success')
    
    if request.is_json:
        return jsonify({'success': True, 'message': 'Warning resolved'})
    
    return redirect(url_for('admin_warning_details', warning_id=warning_id))

# =====================================================
# ADMIN PRODUCT APPROVAL ROUTES
# =====================================================

@app.route('/admin/product-approvals')
@role_required('admin')
def admin_product_approvals():
    """Admin product approval management page with search and pagination"""
    # Get filter parameters
    status_filter = request.args.get('status', 'pending')
    search_query = request.args.get('search', '').strip()
    seller_filter = request.args.get('seller', '')
    sort_by = request.args.get('sort', 'submitted_at')
    sort_order = request.args.get('order', 'desc')
    page = request.args.get('page', 1, type=int)
    
    # Build query
    query = Product.query
    
    # Apply status filter
    if status_filter != 'all':
        query = query.filter_by(approval_status=status_filter)
    
    # Apply search filter
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Product.name.ilike(search_pattern),
                Product.brand.ilike(search_pattern),
                Product.description.ilike(search_pattern)
            )
        )
    
    # Apply seller filter
    if seller_filter:
        query = query.join(User, Product.seller_id == User.id).filter(
            db.or_(
                User.username.ilike(f"%{seller_filter}%"),
                User.business_name.ilike(f"%{seller_filter}%")
            )
        )
    
    # Apply sorting
    if sort_by == 'name':
        query = query.order_by(Product.name.asc() if sort_order == 'asc' else Product.name.desc())
    elif sort_by == 'price':
        query = query.order_by(Product.price.asc() if sort_order == 'asc' else Product.price.desc())
    elif sort_by == 'seller':
        query = query.join(User, Product.seller_id == User.id).order_by(
            User.business_name.asc() if sort_order == 'asc' else User.business_name.desc()
        )
    else:  # submitted_at
        query = query.order_by(Product.submitted_at.asc() if sort_order == 'asc' else Product.submitted_at.desc())
    
    # Paginate results
    products = query.paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Get summary statistics
    stats = {
        'total_pending': Product.query.filter_by(approval_status='pending').count(),
        'total_approved': Product.query.filter_by(approval_status='approved').count(),
        'total_rejected': Product.query.filter_by(approval_status='rejected').count(),
        'pending_today': Product.query.filter(
            Product.approval_status == 'pending',
            Product.submitted_at >= datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        ).count()
    }
    
    return render_template('admin/product_approvals.html',
                         products=products,
                         stats=stats,
                         current_status=status_filter,
                         search_query=search_query,
                         seller_filter=seller_filter,
                         sort_by=sort_by,
                         sort_order=sort_order)

@app.route('/admin/products/<int:product_id>/approve', methods=['POST'])
@role_required('admin')
def approve_product(product_id):
    """Approve a product"""
    product = Product.query.get_or_404(product_id)
    admin_user = get_current_user()
    
    if product.approval_status == 'pending':
        product.approval_status = 'approved'
        product.approved_by = admin_user.id
        product.approved_at = utc_now()
        product.rejection_reason = None
        
        # Create approval history entry
        approval_history = ProductApprovalHistory(
            product_id=product.id,
            action='approved',
            admin_id=admin_user.id,
            notes='Product approved by admin'
        )
        db.session.add(approval_history)
        
        # Send notification to seller
        create_notification(
            user_id=product.seller_id,
            notification_type='product_update',
            category='approval',
            title='Product Approved!',
            message=f'Your product "{product.name}" has been approved and is now visible to buyers.',
            priority='high',
            action_url=url_for('seller_products'),
            action_text='View Products',
            data={'product_id': product.id, 'admin_id': admin_user.id}
        )
        
        db.session.commit()
        flash(f'Product "{product.name}" approved successfully!', 'success')
    else:
        flash(f'Product is already {product.approval_status}.', 'warning')
    
    if request.is_json:
        return jsonify({'success': True, 'message': 'Product approved', 'status': product.approval_status})
    
    return redirect(url_for('admin_product_approvals'))

@app.route('/admin/products/<int:product_id>/reject', methods=['POST'])
@role_required('admin')
def reject_product(product_id):
    """Reject a product with reason"""
    product = Product.query.get_or_404(product_id)
    admin_user = get_current_user()
    
    # Get rejection reason
    rejection_reason = request.json.get('reason') if request.is_json else request.form.get('reason')
    
    if not rejection_reason or len(rejection_reason.strip()) < 10:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Rejection reason must be at least 10 characters.'}), 400
        flash('Rejection reason must be at least 10 characters.', 'error')
        return redirect(url_for('admin_product_approvals'))
    
    if product.approval_status == 'pending':
        product.approval_status = 'rejected'
        product.approved_by = admin_user.id
        product.approved_at = utc_now()
        product.rejection_reason = rejection_reason
        
        # Create approval history entry
        approval_history = ProductApprovalHistory(
            product_id=product.id,
            action='rejected',
            admin_id=admin_user.id,
            reason=rejection_reason,
            notes='Product rejected by admin'
        )
        db.session.add(approval_history)
        
        # Send notification to seller
        create_notification(
            user_id=product.seller_id,
            notification_type='product_update',
            category='approval',
            title='Product Rejected',
            message=f'Your product "{product.name}" was rejected. Reason: {rejection_reason}',
            priority='high',
            action_url=url_for('seller_products'),
            action_text='View Products',
            data={'product_id': product.id, 'admin_id': admin_user.id, 'reason': rejection_reason}
        )
        
        db.session.commit()
        flash(f'Product "{product.name}" rejected.', 'success')
    else:
        flash(f'Product is already {product.approval_status}.', 'warning')
    
    if request.is_json:
        return jsonify({'success': True, 'message': 'Product rejected', 'status': product.approval_status})
    
    return redirect(url_for('admin_product_approvals'))

@app.route('/admin/products/bulk-approve', methods=['POST'])
@role_required('admin')
def bulk_approve_products():
    """Bulk approve multiple products"""
    admin_user = get_current_user()
    
    # Get product IDs
    product_ids = request.json.get('product_ids', []) if request.is_json else request.form.getlist('product_ids[]')
    
    if not product_ids:
        if request.is_json:
            return jsonify({'success': False, 'message': 'No products selected'}), 400
        flash('No products selected.', 'error')
        return redirect(url_for('admin_product_approvals'))
    
    approved_count = 0
    for product_id in product_ids:
        try:
            product = Product.query.get(int(product_id))
            if product and product.approval_status == 'pending':
                product.approval_status = 'approved'
                product.approved_by = admin_user.id
                product.approved_at = utc_now()
                product.rejection_reason = None
                
                # Create approval history entry
                approval_history = ProductApprovalHistory(
                    product_id=product.id,
                    action='approved',
                    admin_id=admin_user.id,
                    notes='Product bulk approved by admin'
                )
                db.session.add(approval_history)
                
                # Send notification to seller
                create_notification(
                    user_id=product.seller_id,
                    notification_type='product_update',
                    category='approval',
                    title='Product Approved!',
                    message=f'Your product "{product.name}" has been approved and is now visible to buyers.',
                    priority='high',
                    action_url=url_for('seller_products'),
                    action_text='View Products',
                    data={'product_id': product.id, 'admin_id': admin_user.id}
                )
                
                approved_count += 1
        except Exception as e:
            print(f"Error approving product {product_id}: {e}")
            continue
    
    db.session.commit()
    
    if request.is_json:
        return jsonify({'success': True, 'message': f'{approved_count} products approved', 'count': approved_count})
    
    flash(f'{approved_count} product(s) approved successfully!', 'success')
    return redirect(url_for('admin_product_approvals'))

@app.route('/admin/products/bulk-reject', methods=['POST'])
@role_required('admin')
def bulk_reject_products():
    """Bulk reject multiple products"""
    admin_user = get_current_user()
    
    # Get product IDs and reason
    product_ids = request.json.get('product_ids', []) if request.is_json else request.form.getlist('product_ids[]')
    rejection_reason = request.json.get('reason') if request.is_json else request.form.get('reason')
    
    if not product_ids:
        if request.is_json:
            return jsonify({'success': False, 'message': 'No products selected'}), 400
        flash('No products selected.', 'error')
        return redirect(url_for('admin_product_approvals'))
    
    if not rejection_reason or len(rejection_reason.strip()) < 10:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Rejection reason must be at least 10 characters.'}), 400
        flash('Rejection reason must be at least 10 characters.', 'error')
        return redirect(url_for('admin_product_approvals'))
    
    rejected_count = 0
    for product_id in product_ids:
        try:
            product = Product.query.get(int(product_id))
            if product and product.approval_status == 'pending':
                product.approval_status = 'rejected'
                product.approved_by = admin_user.id
                product.approved_at = utc_now()
                product.rejection_reason = rejection_reason
                
                # Create approval history entry
                approval_history = ProductApprovalHistory(
                    product_id=product.id,
                    action='rejected',
                    admin_id=admin_user.id,
                    reason=rejection_reason,
                    notes='Product bulk rejected by admin'
                )
                db.session.add(approval_history)
                
                # Send notification to seller
                create_notification(
                    user_id=product.seller_id,
                    notification_type='product_update',
                    category='approval',
                    title='Product Rejected',
                    message=f'Your product "{product.name}" was rejected. Reason: {rejection_reason}',
                    priority='high',
                    action_url=url_for('seller_products'),
                    action_text='View Products',
                    data={'product_id': product.id, 'admin_id': admin_user.id, 'reason': rejection_reason}
                )
                
                rejected_count += 1
        except Exception as e:
            print(f"Error rejecting product {product_id}: {e}")
            continue
    
    db.session.commit()
    
    if request.is_json:
        return jsonify({'success': True, 'message': f'{rejected_count} products rejected', 'count': rejected_count})
    
    flash(f'{rejected_count} product(s) rejected.', 'success')
    return redirect(url_for('admin_product_approvals'))

@app.route('/admin/products/<int:product_id>/history')
@role_required('admin')
def product_approval_history(product_id):
    """View product approval history"""
    product = Product.query.get_or_404(product_id)
    history = ProductApprovalHistory.query.filter_by(product_id=product_id).order_by(
        ProductApprovalHistory.created_at.desc()
    ).all()
    
    return render_template('admin/product_approval_history.html', 
                         product=product, 
                         history=history)

# =====================================================
# BUYER WARNING ROUTES
# =====================================================

@app.route('/buyer/warnings')
@role_required('buyer')
def buyer_warnings():
    """Buyer warnings and violations page - includes both BuyerWarning and Notification warnings"""
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    
    # Get BuyerWarning records
    buyer_warning_query = BuyerWarning.query.filter_by(buyer_id=user.id)
    
    # Get Notification warnings (from admin warning feature)
    notification_warning_query = Notification.query.filter_by(
        user_id=user.id,
        type='warning'
    )
    
    # Apply status filter to BuyerWarning
    if status_filter == 'unread':
        buyer_warning_query = buyer_warning_query.filter_by(is_acknowledged=False)
        notification_warning_query = notification_warning_query.filter_by(is_read=False)
    elif status_filter == 'acknowledged':
        buyer_warning_query = buyer_warning_query.filter_by(is_acknowledged=True)
        notification_warning_query = notification_warning_query.filter_by(is_read=True)
    elif status_filter == 'resolved':
        buyer_warning_query = buyer_warning_query.filter_by(is_resolved=True)
        notification_warning_query = notification_warning_query.filter_by(is_read=True)
    elif status_filter == 'critical':
        buyer_warning_query = buyer_warning_query.filter(
            (BuyerWarning.severity == 'critical') | 
            (BuyerWarning.offense_level >= 3)
        )
        notification_warning_query = notification_warning_query.filter(
            Notification.priority.in_(['urgent', 'high'])
        )
    
    # Get all warnings (both types)
    buyer_warnings_list = buyer_warning_query.order_by(BuyerWarning.created_at.desc()).all()
    notification_warnings = notification_warning_query.order_by(Notification.created_at.desc()).all()
    
    # Combine and sort by date
    all_warnings = []
    
    # Add BuyerWarning records
    for bw in buyer_warnings_list:
        all_warnings.append({
            'type': 'buyer_warning',
            'id': bw.id,
            'title': bw.title or 'Warning',
            'message': bw.description,
            'category': bw.warning_type,
            'priority': bw.severity,
            'is_read': bw.is_acknowledged,
            'is_resolved': bw.is_resolved,
            'created_at': bw.created_at,
            'admin_id': bw.admin_id,
            'offense_level': bw.offense_level,
            'object': bw
        })
    
    # Add Notification warnings
    for nw in notification_warnings:
        all_warnings.append({
            'type': 'notification_warning',
            'id': nw.id,
            'title': nw.title,
            'message': nw.message,
            'category': nw.category,
            'priority': nw.priority,
            'is_read': nw.is_read,
            'is_resolved': nw.is_read,
            'created_at': nw.created_at,
            'admin_id': nw.data.get('admin_id') if nw.data else None,
            'offense_level': None,
            'object': nw
        })
    
    # Sort by created_at descending
    all_warnings.sort(key=lambda x: x['created_at'], reverse=True)
    
    # Manual pagination
    per_page = 10
    start = (page - 1) * per_page
    end = start + per_page
    paginated_warnings = all_warnings[start:end]
    
    # Create pagination object
    class PaginationHelper:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None
        
        def iter_pages(self, left_edge=2, left_current=2, right_current=3, right_edge=2):
            last = 0
            for num in range(1, self.pages + 1):
                if num <= left_edge or \
                   (num > self.page - left_current - 1 and num < self.page + right_current) or \
                   num > self.pages - right_edge:
                    if last + 1 != num:
                        yield None
                    yield num
                    last = num
    
    warnings = PaginationHelper(paginated_warnings, page, per_page, len(all_warnings))
    
    # Get warning statistics (combined)
    total_warnings = len(all_warnings)
    unread_warnings = sum(1 for w in all_warnings if not w['is_read'])
    critical_warnings = sum(1 for w in all_warnings if w['priority'] in ['critical', 'urgent', 'high'])
    resolved_warnings = sum(1 for w in all_warnings if w['is_resolved'])
    
    return render_template('buyer/warnings.html',
                         warnings=warnings,
                         total_warnings=total_warnings,
                         unread_warnings=unread_warnings,
                         critical_warnings=critical_warnings,
                         resolved_warnings=resolved_warnings,
                         current_status=status_filter)

@app.route('/admin/buyer-warnings/create', methods=['GET', 'POST'])
@role_required('admin')
def admin_create_buyer_warning():
    """Create a new buyer warning"""
    if request.method == 'POST':
        try:
            buyer_id = request.form.get('buyer_id', type=int)
            warning_type = request.form.get('warning_type')
            severity = request.form.get('severity', 'medium')
            title = request.form.get('title')
            message = request.form.get('message')
            action_required = request.form.get('action_required')
            policy_link = request.form.get('policy_link')
            admin_notes = request.form.get('admin_notes')
            
            # Parse deadline if provided
            deadline = None
            deadline_str = request.form.get('deadline')
            if deadline_str:
                try:
                    deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    pass
            
            # Validate required fields
            if not all([buyer_id, warning_type, title, message]):
                flash('Please fill in all required fields.', 'error')
                return redirect(url_for('admin_create_buyer_warning'))
            
            # Create warning
            admin_user = get_current_user()
            warning, notification = create_buyer_warning(
                buyer_id=buyer_id,
                admin_id=admin_user.id,
                warning_type=warning_type,
                title=title,
                message=message,
                severity=severity,
                action_required=action_required,
                deadline=deadline,
                policy_link=policy_link,
                admin_notes=admin_notes
            )
            
            if warning:
                flash(f'Warning issued successfully to buyer. Notification sent.', 'success')
                return redirect(url_for('admin_warnings'))
            else:
                flash('Error creating warning. Please try again.', 'error')
                
        except Exception as e:
            flash('Error creating warning. Please try again.', 'error')
            print(f"Buyer warning creation error: {e}")
    
    # Get buyers for dropdown
    buyers = User.query.filter_by(role='buyer', is_active=True).order_by(User.first_name, User.last_name).all()
    
    return render_template('admin/create_buyer_warning.html', buyers=buyers)

@app.route('/buyer/warnings/<int:warning_id>/acknowledge', methods=['POST'])
@role_required('buyer')
def acknowledge_buyer_warning(warning_id):
    """Acknowledge a buyer warning"""
    user = get_current_user()
    warning = BuyerWarning.query.filter_by(id=warning_id, buyer_id=user.id).first()
    
    if not warning:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Warning not found'}), 404
        flash('Warning not found.', 'error')
        return redirect(url_for('buyer_warnings'))
    
    if warning.is_acknowledged:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Warning already acknowledged'})
        flash('Warning already acknowledged.', 'info')
        return redirect(url_for('buyer_warnings'))
    
    try:
        warning.is_acknowledged = True
        warning.acknowledged_at = utc_now()
        db.session.commit()
        
        # Log the acknowledgment
        log_admin_action(
            admin_id=warning.admin_id,
            action='buyer_warning_acknowledged',
            target_type='buyer',
            target_id=user.id,
            details=f"Buyer acknowledged warning: {warning.title}"
        )
        
        if request.is_json:
            return jsonify({'success': True, 'message': 'Warning acknowledged'})
        
        flash('Warning acknowledged successfully.', 'success')
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'success': False, 'message': str(e)}), 500
        flash('Error acknowledging warning.', 'error')
    
    return redirect(url_for('buyer_warnings'))

@app.route('/buyer/warnings/<int:warning_id>/respond', methods=['POST'])
@role_required('buyer')
def respond_buyer_warning(warning_id):
    """Submit response to buyer warning"""
    user = get_current_user()
    warning = BuyerWarning.query.filter_by(id=warning_id, buyer_id=user.id).first()
    
    if not warning:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Warning not found'}), 404
        flash('Warning not found.', 'error')
        return redirect(url_for('buyer_warnings'))
    
    try:
        data = request.get_json() if request.is_json else request.form
        response_text = data.get('response', '').strip()
        
        if not response_text:
            if request.is_json:
                return jsonify({'success': False, 'message': 'Response cannot be empty'})
            flash('Response cannot be empty.', 'error')
            return redirect(url_for('buyer_warnings'))
        
        # Update warning with response
        warning.buyer_response = response_text
        warning.is_acknowledged = True
        warning.acknowledged_at = utc_now()
        
        db.session.commit()
        
        # Notify admin about the response
        create_notification(
            user_id=warning.admin_id,
            notification_type='system_alert',
            category='admin',
            title=f"Buyer Response to Warning: {warning.title}",
            message=f"""
            Buyer {user.first_name} {user.last_name} has responded to warning:<br><br>
            <strong>Response:</strong><br>
            {response_text}
            """,
            priority='medium',
            action_url=url_for('admin_warning_details', warning_id=warning.id),
            action_text="View Warning Details",
            data={'warning_id': warning.id, 'buyer_id': user.id}
        )
        
        # Log the response
        log_admin_action(
            admin_id=warning.admin_id,
            action='buyer_warning_response',
            target_type='buyer',
            target_id=user.id,
            details=f"Buyer responded to warning: {warning.title}"
        )
        
        if request.is_json:
            return jsonify({'success': True, 'message': 'Response submitted successfully'})
        
        flash('Response submitted successfully.', 'success')
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'success': False, 'message': str(e)}), 500
        flash('Error submitting response.', 'error')
    
    return redirect(url_for('buyer_warnings'))

# =====================================================
# NOTIFICATION ROUTES AND API
# =====================================================

@app.route('/notifications')
@login_required
def notification_center():
    """Notification center page"""
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    filter_type = request.args.get('filter', 'all')
    
    query = Notification.query.filter_by(user_id=user.id)
    
    # Apply filters
    if filter_type == 'unread':
        query = query.filter_by(is_read=False)
    elif filter_type == 'today':
        today = utc_now().date()
        query = query.filter(Notification.created_at >= today)
    elif filter_type == 'week':
        week_ago = utc_now() - timedelta(days=7)
        query = query.filter(Notification.created_at >= week_ago)
    elif filter_type != 'all':
        query = query.filter_by(type=filter_type)
    
    # Remove expired notifications
    query = query.filter(
        db.or_(
            Notification.expires_at.is_(None),
            Notification.expires_at > utc_now()
        )
    )
    
    notifications = query.order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Get notification counts
    counts = {
        'total': Notification.query.filter_by(user_id=user.id).count(),
        'unread': Notification.query.filter_by(user_id=user.id, is_read=False).count(),
        'today': Notification.query.filter_by(user_id=user.id).filter(
            Notification.created_at >= utc_now().date()
        ).count()
    }
    
    return render_template('notifications/center.html', 
                         notifications=notifications, 
                         counts=counts,
                         current_filter=filter_type)

@app.route('/api/notifications')
@login_required
def api_notifications():
    """API endpoint for notifications (for AJAX/real-time updates)"""
    user = get_current_user()
    limit = request.args.get('limit', 10, type=int)
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    
    query = Notification.query.filter_by(user_id=user.id)
    
    if unread_only:
        query = query.filter_by(is_read=False)
    
    # Remove expired notifications
    query = query.filter(
        db.or_(
            Notification.expires_at.is_(None),
            Notification.expires_at > utc_now()
        )
    )
    
    notifications = query.order_by(Notification.created_at.desc()).limit(limit).all()
    
    return jsonify({
        'notifications': [n.to_dict() for n in notifications],
        'unread_count': Notification.query.filter_by(user_id=user.id, is_read=False).count(),
        'total_count': Notification.query.filter_by(user_id=user.id).count()
    })

@app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    user = get_current_user()
    notification = Notification.query.filter_by(id=notification_id, user_id=user.id).first_or_404()
    
    notification.mark_as_read()
    
    return jsonify({'success': True, 'message': 'Notification marked as read'})

@app.route('/api/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read for current user"""
    user = get_current_user()
    
    try:
        Notification.query.filter_by(user_id=user.id, is_read=False).update({
            'is_read': True,
            'read_at': utc_now()
        })
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'All notifications marked as read'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Error marking notifications as read'}), 500

@app.route('/api/notifications/<int:notification_id>/delete', methods=['DELETE'])
@login_required
def delete_notification(notification_id):
    """Delete a notification"""
    user = get_current_user()
    notification = Notification.query.filter_by(id=notification_id, user_id=user.id).first_or_404()
    
    try:
        db.session.delete(notification)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Notification deleted'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Error deleting notification'}), 500

@app.route('/api/notifications/clear-all', methods=['POST'])
@login_required
def clear_all_notifications():
    """Clear all notifications for current user"""
    user = get_current_user()
    
    try:
        Notification.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        return jsonify({'success': True, 'message': 'All notifications cleared'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Error clearing notifications'}), 500

@app.route('/notification-preferences')
@login_required
def notification_preferences():
    """User notification preferences page"""
    user = get_current_user()
    preferences = get_user_notification_preferences(user.id)
    return render_template('notifications/preferences.html', preferences=preferences)

@app.route('/notification-preferences', methods=['POST'])
@login_required
def update_notification_preferences():
    """Update user notification preferences"""
    user = get_current_user()
    preferences = get_user_notification_preferences(user.id)
    
    try:
        # Email preferences
        preferences.email_enabled = 'email_enabled' in request.form
        preferences.email_order_updates = 'email_order_updates' in request.form
        preferences.email_financial = 'email_financial' in request.form
        preferences.email_promotions = 'email_promotions' in request.form
        preferences.email_system_alerts = 'email_system_alerts' in request.form
        
        # In-app preferences
        preferences.app_enabled = 'app_enabled' in request.form
        preferences.app_order_updates = 'app_order_updates' in request.form
        preferences.app_financial = 'app_financial' in request.form
        preferences.app_promotions = 'app_promotions' in request.form
        preferences.app_system_alerts = 'app_system_alerts' in request.form
        
        # SMS preferences
        preferences.sms_enabled = 'sms_enabled' in request.form
        preferences.sms_critical_only = 'sms_critical_only' in request.form
        
        preferences.updated_at = utc_now()
        db.session.commit()
        
        flash('Notification preferences updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error updating preferences. Please try again.', 'error')
        print(f"Error updating notification preferences: {e}")
    
    return redirect(url_for('notification_preferences'))

@app.route('/api/notifications/cleanup', methods=['POST'])
@role_required('admin')
def cleanup_notifications():
    """Admin endpoint to cleanup expired and old notifications"""
    try:
        expired_count = Notification.cleanup_expired()
        old_count = Notification.cleanup_old_read_notifications()
        
        return jsonify({
            'success': True,
            'message': f'Cleanup completed. Removed {expired_count} expired and {old_count} old notifications.',
            'expired_removed': expired_count,
            'old_removed': old_count
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Cleanup failed: {str(e)}'}), 500

@app.route('/api/notifications/test', methods=['POST'])
@login_required
def test_notifications():
    """Test endpoint to create sample notifications (for development)"""
    user = get_current_user()
    
    try:
        # Create sample notifications based on user role
        if user.role == 'admin':
            # Admin test notifications
            create_notification(
                user_id=user.id,
                notification_type='system_alert',
                category='system',
                title="System Status Update",
                message="All systems are running normally. Daily backup completed successfully.",
                priority='low',
                action_url=url_for('admin_dashboard'),
                action_text="View Dashboard"
            )
            
            create_notification(
                user_id=user.id,
                notification_type='admin_action',
                category='approval',
                title="New User Registration",
                message="A new seller has registered and requires approval.",
                priority='medium',
                action_url=url_for('admin_approvals'),
                action_text="Review Registration"
            )
            
        elif user.role == 'seller':
            # Seller test notifications
            create_notification(
                user_id=user.id,
                notification_type='order_update',
                category='order',
                title="New Order Received - #ORD001",
                message="You have received a new order worth ₱1,250. Please confirm and prepare the items.",
                priority='high',
                action_url=url_for('seller_dashboard'),
                action_text="View Order"
            )
            
            create_notification(
                user_id=user.id,
                notification_type='financial',
                category='payout',
                title="Payment Released!",
                message="Payment of ₱950 for order #ORD001 has been released to your account.",
                priority='high',
                action_url=url_for('seller_dashboard'),
                action_text="View Earnings"
            )
            
        elif user.role == 'rider':
            # Rider test notifications
            create_notification(
                user_id=user.id,
                notification_type='order_update',
                category='delivery',
                title="New Delivery Assignment",
                message="You have been assigned to deliver order #ORD001. Pickup location: Daily Fitness Warehouse.",
                priority='high',
                action_url=url_for('rider_dashboard'),
                action_text="Start Delivery"
            )
            
            create_notification(
                user_id=user.id,
                notification_type='financial',
                category='payout',
                title="Weekly Commission Summary",
                message="Your weekly commission of ₱450 for 15 deliveries has been calculated.",
                priority='medium',
                action_url=url_for('rider_dashboard'),
                action_text="View Earnings"
            )
            
        else:  # buyer
            # Buyer test notifications
            create_notification(
                user_id=user.id,
                notification_type='order_update',
                category='order',
                title="Order Confirmed - #ORD001",
                message="Great news! Your order has been confirmed by the seller and is being prepared.",
                priority='medium',
                action_url=url_for('buyer_home'),
                action_text="Track Order"
            )
            
            create_notification(
                user_id=user.id,
                notification_type='promotion',
                category='general',
                title="Special Offer: 20% Off Gym Equipment",
                message="Limited time offer! Get 20% off all gym equipment. Use code GYM20 at checkout.",
                priority='low',
                action_url=url_for('buyer_home'),
                action_text="Shop Now",
                expires_at=utc_now() + timedelta(days=7)
            )
        
        return jsonify({'success': True, 'message': 'Test notifications created successfully!'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error creating test notifications: {str(e)}'}), 500

@app.route('/admin/commissions')
@role_required('admin')
def admin_commissions():
    """Admin commission management and reports"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    
    query = Commission.query.join(Order).join(User)
    if status_filter != 'all':
        query = query.filter(Commission.status == status_filter)
    
    commissions = query.order_by(Commission.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Get commission summary
    total_collected = db.session.query(db.func.sum(Commission.commission_amount)).filter(Commission.status == 'collected').scalar() or 0
    total_pending = db.session.query(db.func.sum(Commission.commission_amount)).filter(Commission.status == 'pending').scalar() or 0
    
    return render_template('admin/commissions.html', 
                         commissions=commissions,
                         total_collected=total_collected,
                         total_pending=total_pending,
                         current_status=status_filter)

@app.route('/admin/users')
@role_required('admin')
def admin_users():
    """User management page"""
    role_filter = request.args.get('role', 'all')
    status_filter = request.args.get('status', 'all')
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    
    query = User.query
    
    if role_filter != 'all':
        query = query.filter(User.role == role_filter)
    
    if status_filter != 'all':
        query = query.filter(User.approval_status == status_filter)
    
    if search:
        query = query.filter(
            db.or_(
                User.username.contains(search),
                User.email.contains(search),
                User.first_name.contains(search),
                User.last_name.contains(search)
            )
        )
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/users.html', 
                         users=users,
                         current_role=role_filter,
                         current_status=status_filter,
                         search=search)

@app.route('/admin/user/<int:user_id>')
@role_required('admin')
def admin_user_detail(user_id):
    """User detail page with violation history"""
    user = User.query.get_or_404(user_id)
    
    # Get user's orders
    orders = Order.query.filter_by(buyer_id=user_id).order_by(Order.created_at.desc()).limit(10).all()
    
    # Get user's violations
    violations = UserViolation.query.filter_by(user_id=user_id).order_by(UserViolation.created_at.desc()).all()
    
    # Get user's complaints (as complainant or respondent)
    complaints = Complaint.query.filter(
        db.or_(Complaint.complainant_id == user_id, Complaint.respondent_id == user_id)
    ).order_by(Complaint.created_at.desc()).limit(10).all()
    
    # Get violation level
    violation_level = get_user_violation_level(user_id)
    
    # Get seller stats if user is a seller
    seller_stats = None
    if user.role == 'seller':
        seller_stats = db.session.query(
            db.func.sum(Commission.order_amount).label('total_sales'),
            db.func.count(Commission.id).label('total_orders'),
            db.func.sum(Commission.commission_amount).label('total_commissions')
        ).filter(Commission.seller_id == user_id, Commission.status == 'collected').first()
    
    # Prepare documents object for template
    documents = {
        'profile_image': user.profile_image,
        'business_permit': user.business_permit,
        'dti_certification': user.dti_certification,
        'id_document': user.id_document
    }
    
    return render_template('admin/user_details.html',
                         user=user,
                         documents=documents,
                         orders=orders,
                         violations=violations,
                         complaints=complaints,
                         violation_level=violation_level,
                         seller_stats=seller_stats)

@app.route('/admin/user/<int:user_id>/toggle-ban', methods=['POST'])
@role_required('admin')
def admin_toggle_user_ban(user_id):
    """Ban or unban a user account"""
    try:
        user = User.query.get_or_404(user_id)
        admin = get_current_user()
        
        # Prevent admin from banning themselves
        if user.id == admin.id:
            return jsonify({'success': False, 'message': 'You cannot ban yourself!'}), 400
        
        # Prevent banning other admins
        if user.role == 'admin':
            return jsonify({'success': False, 'message': 'You cannot ban other administrators!'}), 403
        
        # Toggle ban status
        user.is_active = not user.is_active
        action = 'unbanned' if user.is_active else 'banned'
        
        # Log the action
        reason = request.json.get('reason', 'No reason provided') if request.is_json else 'Admin action'
        
        # Create a notification for the user
        notification = Notification(
            user_id=user.id,
            type='admin_action',
            category='system',
            title=f'Account {action.capitalize()}',
            message=f'Your account has been {action} by an administrator. Reason: {reason}',
            priority='high',
            action_url=None
        )
        db.session.add(notification)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'User {action} successfully',
            'is_active': user.is_active,
            'action': action
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/user/<int:user_id>/send-warning', methods=['POST'])
@role_required('admin')
def admin_send_warning(user_id):
    """Send a warning to a user (seller or buyer)"""
    try:
        user = User.query.get_or_404(user_id)
        admin = get_current_user()
        
        # Prevent admin from warning themselves
        if user.id == admin.id:
            return jsonify({'success': False, 'message': 'You cannot warn yourself!'}), 400
        
        # Prevent warning other admins
        if user.role == 'admin':
            return jsonify({'success': False, 'message': 'You cannot warn other administrators!'}), 403
        
        # Get warning details from request
        data = request.get_json()
        warning_title = data.get('title', 'Warning from Administrator')
        warning_message = data.get('message', '')
        warning_category = data.get('category', 'general')
        priority = data.get('priority', 'high')
        
        if not warning_message:
            return jsonify({'success': False, 'message': 'Warning message is required!'}), 400
        
        # Create a notification for the user
        notification = create_notification(
            user_id=user.id,
            notification_type='warning',
            category=warning_category,
            title=warning_title,
            message=warning_message,
            priority=priority,
            action_url=None,
            action_text=None,
            data={
                'admin_id': admin.id,
                'admin_name': admin.full_name,
                'warning_date': utc_now().isoformat()
            },
            send_email=True
        )
        
        if not notification:
            return jsonify({'success': False, 'message': 'Failed to create notification'}), 500
        
        # Log the warning action
        violation = UserViolation(
            user_id=user.id,
            violation_type='warning',
            category=warning_category,
            description=warning_message,
            action_taken=f'Warning sent by {admin.full_name}',
            admin_id=admin.id
        )
        db.session.add(violation)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Warning sent successfully to {user.full_name}',
            'notification_id': notification.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/support')
@role_required('admin')
def admin_support_tickets():
    """Admin support ticket management"""
    status_filter = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)
    
    query = SupportTicket.query
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    tickets = query.order_by(SupportTicket.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/support_tickets.html', 
                         tickets=tickets,
                         current_status=status_filter)

@app.route('/admin/support/<int:ticket_id>', methods=['GET', 'POST'])
@role_required('admin')
def admin_support_ticket_detail(ticket_id):
    """Admin view and respond to support ticket"""
    admin = get_current_user()
    ticket = SupportTicket.query.get_or_404(ticket_id)
    
    if request.method == 'POST':
        response = request.form.get('response')
        action = request.form.get('action')
        
        if response:
            ticket.admin_response = response
            ticket.assigned_admin_id = admin.id
            
            if action == 'resolve':
                ticket.status = 'resolved'
                ticket.resolved_at = utc_now()
            elif action == 'in_progress':
                ticket.status = 'in_progress'
            
            ticket.updated_at = utc_now()
            
            # Notify user
            notification = Notification(
                user_id=ticket.user_id,
                title=f'Response to Ticket #{ticket.ticket_number}',
                message=f'Admin has responded to your support ticket: {ticket.subject}',
                type='system_alert',
                category='general',
                priority='medium',
                action_url=f'/support/{ticket.id}',
                action_text='View Ticket'
            )
            db.session.add(notification)
            db.session.commit()
            
            flash('Response sent successfully!', 'success')
            return redirect(url_for('admin_support_tickets'))
    
    return render_template('admin/support_ticket_detail.html', ticket=ticket)

@app.route('/admin/complaints')
@role_required('admin')
def admin_complaints():
    """Complaint management page"""
    status_filter = request.args.get('status', 'open')
    priority_filter = request.args.get('priority', 'all')
    category_filter = request.args.get('category', 'all')
    page = request.args.get('page', 1, type=int)
    
    query = Complaint.query
    
    if status_filter != 'all':
        query = query.filter(Complaint.status == status_filter)
    
    if priority_filter != 'all':
        query = query.filter(Complaint.priority == priority_filter)
    
    if category_filter != 'all':
        query = query.filter(Complaint.category == category_filter)
    
    complaints = query.order_by(Complaint.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/complaints.html',
                         complaints=complaints,
                         current_status=status_filter,
                         current_priority=priority_filter,
                         current_category=category_filter)

@app.route('/admin/complaint/<int:complaint_id>')
@role_required('admin')
def admin_complaint_detail(complaint_id):
    """Complaint detail and resolution page"""
    complaint = Complaint.query.get_or_404(complaint_id)
    return render_template('admin/complaint_detail.html', complaint=complaint)

@app.route('/admin/complaint/<int:complaint_id>/resolve', methods=['POST'])
@role_required('admin')
def resolve_complaint(complaint_id):
    """Resolve a complaint"""
    complaint = Complaint.query.get_or_404(complaint_id)
    admin_user = get_current_user()
    
    resolution = request.form.get('resolution')
    action = request.form.get('action')  # resolved, closed
    
    try:
        complaint.resolution = resolution
        complaint.status = action
        complaint.resolved_by = admin_user.id
        complaint.resolved_at = utc_now()
        
        # Log admin action
        log_admin_action(admin_user.id, 'resolve_complaint', 'complaint', complaint.id, 
                        f"Status: {action}, Resolution: {resolution}")
        
        db.session.commit()
        flash('Complaint resolved successfully.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Error resolving complaint.', 'error')
        print(f"Resolve complaint error: {e}")
    
    return redirect(url_for('admin_complaint_detail', complaint_id=complaint_id))

@app.route('/admin/products')
@role_required('admin')
def admin_products():
    """Product oversight page"""
    status_filter = request.args.get('status', 'all')
    category_filter = request.args.get('category', 'all')
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    
    # Explicitly specify the join condition for seller
    query = Product.query.join(User, Product.seller_id == User.id).join(Category)
    
    if status_filter == 'active':
        query = query.filter(Product.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(Product.is_active == False)
    elif status_filter == 'low_stock':
        query = query.filter(Product.stock_quantity <= 5)
    
    if category_filter != 'all':
        query = query.filter(Product.category_id == category_filter)
    
    if search:
        query = query.filter(
            or_(
                Product.name.contains(search),
                Product.brand.contains(search),
                User.business_name.contains(search)
            )
        )
    
    products = query.order_by(Product.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    categories = Category.query.all()
    
    return render_template('admin/products.html',
                         products=products,
                         categories=categories,
                         current_status=status_filter,
                         current_category=category_filter,
                         search=search)

@app.route('/admin/product/<int:product_id>')
@role_required('admin')
def admin_view_product(product_id):
    """View product details as admin"""
    product = Product.query.get_or_404(product_id)
    
    # Get product statistics
    total_orders = OrderItem.query.filter_by(product_id=product_id).count()
    total_revenue = db.session.query(func.sum(OrderItem.total_price)).filter(
        OrderItem.product_id == product_id
    ).scalar() or 0
    
    # Get recent orders
    recent_orders = OrderItem.query.filter_by(product_id=product_id).order_by(
        OrderItem.created_at.desc()
    ).limit(10).all()
    
    return render_template('admin/product_view.html',
                         product=product,
                         total_orders=total_orders,
                         total_revenue=total_revenue,
                         recent_orders=recent_orders)

@app.route('/admin/analytics')
@role_required('admin')
def admin_analytics():
    """Advanced analytics and reports page"""
    # Get comprehensive analytics
    analytics = get_dashboard_analytics()
    
    # Get monthly revenue trend (last 12 months)
    from datetime import timedelta
    monthly_revenue = []
    for i in range(12):
        month_start = datetime.now().replace(day=1) - timedelta(days=30*i)
        month_end = month_start + timedelta(days=30)
        
        revenue = db.session.query(db.func.sum(Order.total_amount)).filter(
            Order.status == 'completed',
            Order.created_at >= month_start,
            Order.created_at < month_end
        ).scalar() or 0
        
        monthly_revenue.append({
            'month': month_start.strftime('%b %Y'),
            'revenue': float(revenue)
        })
    
    monthly_revenue.reverse()
    
    # Get category performance
    category_stats = db.session.query(
        Category.name,
        db.func.sum(OrderItem.total_price).label('revenue'),
        db.func.sum(OrderItem.quantity).label('quantity_sold')
    ).select_from(Category).join(
        Product, Category.id == Product.category_id
    ).join(
        OrderItem, Product.id == OrderItem.product_id
    ).join(
        Order, OrderItem.order_id == Order.id
    ).filter(
        Order.status == 'completed'
    ).group_by(Category.id, Category.name).order_by(db.desc('revenue')).all()
    
    return render_template('admin/analytics.html',
                         analytics=analytics,
                         monthly_revenue=monthly_revenue,
                         category_stats=category_stats)

@app.route('/admin/audit-logs')
@role_required('admin')
def admin_audit_logs():
    """Admin audit trail page"""
    page = request.args.get('page', 1, type=int)
    action_filter = request.args.get('action', 'all')
    
    query = AdminAuditLog.query.join(User)
    
    if action_filter != 'all':
        query = query.filter(AdminAuditLog.action == action_filter)
    
    logs = query.order_by(AdminAuditLog.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    return render_template('admin/audit_logs.html',
                         logs=logs,
                         current_action=action_filter)

# ==================== RIDER ROUTES ====================

@app.route('/rider/dashboard')
@role_required('rider')
def rider_dashboard():
    """Rider dashboard with comprehensive stats and order management"""
    rider = get_current_user()
    
    # Only allow approved riders
    if rider.approval_status != 'approved':
        flash('Your account is pending admin approval. Please wait for verification.', 'warning')
        return render_template('rider/pending_approval.html', rider=rider)
    
    # Get today's deliveries
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_deliveries = Order.query.filter(
        Order.rider_id == rider.id,
        Order.updated_at >= today_start,
        Order.status.in_(['picked_up', 'on_delivery', 'delivered'])
    ).count()
    
    # Get ongoing deliveries
    ongoing_deliveries = Order.query.filter(
        Order.rider_id == rider.id,
        Order.status.in_(['picked_up', 'on_delivery'])
    ).all()
    
    # Get completed deliveries this month (delivered or completed status)
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    completed_this_month = Order.query.filter(
        Order.rider_id == rider.id,
        Order.status.in_(['delivered', 'completed']),
        Order.delivered_at >= month_start
    ).count()
    
    # Calculate earnings this month (5% commission per delivery)
    # Count both 'delivered' and 'completed' orders
    completed_orders = Order.query.filter(
        Order.rider_id == rider.id,
        Order.status.in_(['delivered', 'completed']),
        Order.delivered_at >= month_start,
        Order.delivered_at.isnot(None)
    ).all()
    
    month_earnings = sum(float(order.total_amount) * 0.05 for order in completed_orders)
    
    # Get available orders for pickup (not assigned to any rider)
    # Include confirmed, preparing, and for_pickup statuses
    available_orders = Order.query.filter(
        Order.status.in_(['confirmed', 'preparing', 'for_pickup']),
        Order.rider_id == None
    ).order_by(Order.created_at.desc()).limit(10).all()
    
    # Get unread messages count
    unread_messages = Message.query.filter_by(
        receiver_id=rider.id,
        is_read=False
    ).count()
    
    # Get recent notifications
    notifications = Notification.query.filter_by(
        user_id=rider.id
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template('rider/dashboard.html',
                         today_deliveries=today_deliveries,
                         ongoing_deliveries=ongoing_deliveries,
                         completed_this_month=completed_this_month,
                         month_earnings=month_earnings,
                         available_orders=available_orders,
                         unread_messages=unread_messages,
                         notifications=notifications)

@app.route('/rider/map')
@role_required('rider')
def rider_map():
    """Interactive map view for rider deliveries"""
    rider = get_current_user()
    
    if rider.approval_status != 'approved':
        flash('Account pending verification.', 'warning')
        return redirect(url_for('rider_dashboard'))
    
    # Get active deliveries (picked up or on the way)
    active_deliveries_query = Order.query.filter(
        Order.rider_id == rider.id,
        Order.status.in_(['picked_up', 'on_the_way'])
    ).order_by(Order.created_at.desc()).all()
    
    # Format deliveries as JSON-serializable dictionaries
    active_deliveries = [
        {
            'id': order.id,
            'order_number': order.order_number,
            'lat': order.delivery_latitude or 14.5995,
            'lng': order.delivery_longitude or 120.9842,
            'address': order.shipping_address,
            'buyer': order.buyer.full_name,
            'status': order.status
        }
        for order in active_deliveries_query
    ]
    
    return render_template('rider/map.html', active_deliveries=active_deliveries)

@app.route('/rider/api/active-deliveries')
@role_required('rider')
def rider_api_active_deliveries():
    """API endpoint for fetching active deliveries in real-time"""
    rider = get_current_user()
    
    try:
        # Get active deliveries (picked up or on the way)
        active_deliveries_query = Order.query.filter(
            Order.rider_id == rider.id,
            Order.status.in_(['picked_up', 'on_the_way'])
        ).order_by(Order.created_at.desc()).all()
        
        # Format deliveries as JSON
        deliveries = []
        for order in active_deliveries_query:
            deliveries.append({
                'id': order.id,
                'order_number': order.order_number,
                'lat': float(order.delivery_latitude) if order.delivery_latitude else 14.5995,
                'lng': float(order.delivery_longitude) if order.delivery_longitude else 120.9842,
                'address': order.shipping_address or 'No address provided',
                'buyer': order.buyer.full_name if order.buyer else 'Unknown',
                'buyer_phone': order.buyer.phone_number if order.buyer and order.buyer.phone_number else 'N/A',
                'status': order.status,
                'total_amount': float(order.total_amount),
                'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S') if order.created_at else None
            })
        
        return jsonify({
            'success': True,
            'deliveries': deliveries,
            'count': len(deliveries)
        })
    except Exception as e:
        print(f"Error fetching active deliveries: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'deliveries': [],
            'count': 0
        }), 500

@app.route('/rider/orders')
@role_required('rider')
def rider_orders():
    """View all rider orders with filtering"""
    rider = get_current_user()
    
    if rider.approval_status != 'approved':
        flash('Account pending verification.', 'warning')
        return redirect(url_for('rider_dashboard'))
    
    status_filter = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)
    
    # Try to get orders from Firestore first
    from firestore_helper import get_orders_firestore
    # Use Firebase UID for cross-platform sync
    rider_id = rider.firebase_uid if rider.firebase_uid else str(rider.id)
    all_orders = get_orders_firestore(rider_id, 'rider')
    
    # Apply status filter if provided
    if status_filter != 'all':
        all_orders = [o for o in all_orders if o.get('status') == status_filter]
    
    # Manual pagination
    per_page = 20
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_orders = all_orders[start_idx:end_idx]
    
    # Normalize orders for template compatibility
    normalized_orders = [normalize_order_for_template(order) for order in paginated_orders]
    
    # Create a simple pagination object
    class SimplePagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None
    
    orders_paginated = SimplePagination(normalized_orders, page, per_page, len(all_orders))
    
    return render_template('rider/orders.html',
                         orders=orders_paginated,
                         status_filter=status_filter)

@app.route('/rider/orders/<order_id>')
@role_required('rider')
def rider_order_detail(order_id):
    """View detailed order information"""
    rider = get_current_user()
    
    # Try to get order from Firestore first
    from firestore_helper import get_order_firestore
    order = get_order_firestore(order_id)
    
    # If not in Firestore, fall back to SQL
    if not order:
        try:
            order_id_int = int(order_id)
            order = Order.query.get_or_404(order_id_int)
            is_firestore = False
        except ValueError:
            return render_template('errors/404.html'), 404
    else:
        is_firestore = True
    
    # Verify rider has access to this order
    rider_id = order.get('riderId') if is_firestore else order.rider_id
    order_status = order.get('status') if is_firestore else order.status
    
    if str(rider_id) != str(rider.id) and order_status != 'for_pickup':
        flash('Access denied.', 'error')
        return redirect(url_for('rider_orders'))
    
    # Normalize order for template compatibility
    normalized_order = normalize_order_for_template(order)
    
    return render_template('rider/order_detail.html', order=normalized_order)

@app.route('/rider/orders/<order_id>/accept', methods=['POST'])
@role_required('rider')
def rider_accept_order(order_id):
    """Accept an order for delivery"""
    rider = get_current_user()
    
    if rider.approval_status != 'approved':
        return jsonify({'success': False, 'message': 'Account not verified'})
    
    # Try to get order from Firestore first
    from firestore_helper import get_order_firestore, update_order_status_firestore
    order = get_order_firestore(order_id)
    
    # If not in Firestore, fall back to SQL
    if not order:
        try:
            order_id_int = int(order_id)
            order = Order.query.get_or_404(order_id_int)
            is_firestore = False
        except ValueError:
            return jsonify({'success': False, 'message': 'Order not found'}), 404
    else:
        is_firestore = True
    
    # Check order status based on data source
    order_status = order.get('status') if is_firestore else order.status
    order_rider_id = order.get('riderId') if is_firestore else order.rider_id
    
    if order_status != 'for_pickup' or order_rider_id is not None:
        return jsonify({'success': False, 'message': 'Order not available'})
    
    try:
        # Update order with rider assignment
        if is_firestore:
            # Update Firestore order
            from firestore_helper import update_order_status_firestore
            update_order_status_firestore(order_id, 'picked_up', str(rider.id))
            # Also update riderId in Firestore
            fs_db = firestore.client()
            fs_db.collection('orders').document(order_id).update({
                'riderId': str(rider.id),
                'riderName': f"{rider.first_name} {rider.last_name}"
            })
            # Also update SQL order if it exists
            try:
                sql_order = Order.query.filter_by(firestore_order_id=order_id).first()
                if sql_order:
                    sql_order.rider_id = rider.id
                    sql_order.status = 'picked_up'
                    db.session.commit()
            except:
                pass
        else:
            order.rider_id = rider.id
            order.status = 'picked_up'
            db.session.commit()
        
        # Get order details for notifications
        order_number = order.get('orderNumber') if is_firestore else order.order_number
        buyer_id = int(order.get('buyerId')) if is_firestore else order.buyer_id
        
        # Notify buyer (SQL only for now)
        if not is_firestore:
            create_notification(
                user_id=buyer_id,
                notification_type='order_update',
                category='order',
                title='Order Picked Up',
                message=f'Your order #{order_number} has been picked up by rider {rider.first_name} {rider.last_name}.',
                priority='medium',
                action_url=url_for('buyer_orders'),
                action_text='View Orders'
            )
            
            # Send automatic chat message to buyer
            buyer_message = f"Hello! I'm {rider.first_name} {rider.last_name}, your delivery rider. I've picked up your order #{order_number} and I'm on my way to deliver it to you. Thank you!"
            send_automatic_message(
                sender_id=rider.id,
                receiver_id=buyer_id,
                message_content=buyer_message,
                order_id=order.id
            )
            
            # Get all sellers from order items and send messages to each unique seller
            seller_ids = set()
            for item in order.order_items:
                seller_ids.add(item.product.seller_id)
            
            for seller_id in seller_ids:
                # Notify seller
                create_notification(
                    user_id=seller_id,
                    notification_type='order_update',
                    category='order',
                    title='Order Picked Up',
                    message=f'Order #{order_number} has been picked up by rider {rider.first_name} {rider.last_name}.',
                    priority='medium',
                    action_url=url_for('seller_orders'),
                    action_text='View Orders'
                )
                
                # Send automatic chat message to seller
                seller_message = f"Hello! I'm {rider.first_name} {rider.last_name}, the delivery rider. I've picked up order #{order_number} containing your products and will deliver it to the customer. Thank you!"
                send_automatic_message(
                    sender_id=rider.id,
                    receiver_id=seller_id,
                    message_content=seller_message,
                    order_id=order.id
                )
        
        flash('Order accepted successfully!', 'success')
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error accepting order: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/rider/orders/<order_id>/update-status', methods=['POST'])
@role_required('rider')
def rider_update_order_status(order_id):
    """Update delivery status"""
    rider = get_current_user()
    
    # Try to get order from Firestore first
    from firestore_helper import get_order_firestore, update_order_status_firestore
    order = get_order_firestore(order_id)
    
    # If not in Firestore, fall back to SQL
    if not order:
        try:
            order_id_int = int(order_id)
            order = Order.query.get_or_404(order_id_int)
            is_firestore = False
        except ValueError:
            return jsonify({'success': False, 'message': 'Order not found'}), 404
    else:
        is_firestore = True
    
    # Verify rider has access to this order
    rider_id = order.get('riderId') if is_firestore else order.rider_id
    if str(rider_id) != str(rider.id):
        return jsonify({'success': False, 'message': 'Access denied'})
    
    new_status = request.json.get('status')
    proof_image = request.json.get('proof_image')
    notes = request.json.get('notes', '')
    
    if new_status not in ['on_delivery', 'delivered']:
        return jsonify({'success': False, 'message': 'Invalid status'})
    
    try:
        # Update order status
        if is_firestore:
            update_order_status_firestore(order_id, new_status, str(rider.id))
            # Also update SQL order if it exists
            try:
                sql_order = Order.query.filter_by(firestore_order_id=order_id).first()
                if sql_order:
                    sql_order.status = new_status
                    sql_order.last_status_update = utc_now()
                    if new_status == 'delivered' and not sql_order.delivered_at:
                        sql_order.delivered_at = utc_now()
                    if notes:
                        sql_order.notes = (sql_order.notes or '') + f"\n[Rider] {notes}"
                    db.session.commit()
            except:
                pass
        else:
            order.status = new_status
            order.last_status_update = utc_now()
            
            # Set delivered_at timestamp when marking as delivered
            if new_status == 'delivered' and not order.delivered_at:
                order.delivered_at = utc_now()
            
            if notes:
                order.notes = (order.notes or '') + f"\n[Rider] {notes}"
            
            db.session.commit()
        
        # Get order details for notifications
        order_number = order.get('orderNumber') if is_firestore else order.order_number
        buyer_id = int(order.get('buyerId')) if is_firestore else order.buyer_id
        
        # Create notifications (SQL only for now)
        if not is_firestore:
            notification_messages = {
                'on_delivery': 'Your order is now on the way!',
                'delivered': 'Your order has been delivered!'
            }
            
            create_notification(
                user_id=buyer_id,
                notification_type='order_update',
                category='order',
                title=f'Order {new_status.replace("_", " ").title()}',
                message=notification_messages.get(new_status, 'Order status updated'),
                priority='high' if new_status == 'delivered' else 'medium',
                action_url=url_for('buyer_orders'),
                action_text='View Order'
            )
            
            # Send automatic message from seller to buyer about delivery status
            # Get the seller from the first order item
            first_item = order.order_items.first()
            if first_item:
                seller_id = first_item.seller_id
                rider_messages = {
                    'on_delivery': f"Good news! Your order #{order_number} is now on the way to you. Our rider is en route to your delivery address.",
                    'delivered': f"Your order #{order_number} has been delivered! We hope you enjoy your purchase. Thank you for shopping with us!"
                }
                
                if new_status in rider_messages:
                    send_automatic_message(seller_id, buyer_id, rider_messages[new_status], order.id)
        
        return jsonify({'success': True, 'message': 'Status updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/rider/earnings')
@role_required('rider')
def rider_earnings():
    """View earnings and generate reports"""
    rider = get_current_user()
    
    # Get filter parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Query for delivered and completed orders (both count as earnings)
    query = Order.query.filter(
        Order.rider_id == rider.id,
        Order.status.in_(['delivered', 'completed']),
        Order.delivered_at.isnot(None)
    )
    
    if start_date:
        query = query.filter(Order.delivered_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        query = query.filter(Order.delivered_at <= end_datetime)
    
    completed_deliveries = query.order_by(Order.delivered_at.desc()).all()
    
    # Calculate earnings (5% commission per delivery)
    total_earnings = sum(float(order.total_amount) * 0.05 for order in completed_deliveries)
    total_deliveries = len(completed_deliveries)
    
    # Get monthly breakdown (use delivered_at for accurate monthly grouping)
    monthly_data = {}
    for order in completed_deliveries:
        if order.delivered_at:
            month_key = order.delivered_at.strftime('%Y-%m')
            if month_key not in monthly_data:
                monthly_data[month_key] = {'count': 0, 'earnings': 0}
            monthly_data[month_key]['count'] += 1
            monthly_data[month_key]['earnings'] += float(order.total_amount) * 0.05
    
    return render_template('rider/earnings.html',
                         completed_deliveries=completed_deliveries,
                         total_earnings=total_earnings,
                         total_deliveries=total_deliveries,
                         monthly_data=monthly_data,
                         start_date=start_date,
                         end_date=end_date)

@app.route('/rider/earnings/export/<format>')
@role_required('rider')
def rider_export_earnings(format):
    """Export earnings report as PDF or Excel"""
    rider = get_current_user()
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Query for delivered and completed orders
    query = Order.query.filter(
        Order.rider_id == rider.id,
        Order.status.in_(['delivered', 'completed']),
        Order.delivered_at.isnot(None)
    )
    
    if start_date:
        query = query.filter(Order.delivered_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        query = query.filter(Order.delivered_at <= end_datetime)
    
    orders = query.order_by(Order.delivered_at.desc()).all()
    
    if format == 'excel':
        # Create CSV response
        from io import StringIO
        import csv
        
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Order Number', 'Delivered Date', 'Amount', 'Commission (5%)', 'Status'])
        
        for order in orders:
            writer.writerow([
                order.order_number,
                order.delivered_at.strftime('%Y-%m-%d %H:%M') if order.delivered_at else 'N/A',
                f"${order.total_amount}",
                f"${float(order.total_amount) * 0.05:.2f}",
                order.status.title()
            ])
        
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=earnings_{datetime.now().strftime("%Y%m%d")}.csv'}
        )
    
    flash('PDF export coming soon!', 'info')
    return redirect(url_for('rider_earnings'))

@app.route('/rider/profile', methods=['GET', 'POST'])
@role_required('rider')
def rider_profile():
    """Rider profile management"""
    rider = get_current_user()
    
    if request.method == 'POST':
        try:
            # Update basic info
            rider.username = request.form.get('username', rider.username)
            rider.email = request.form.get('email', rider.email)
            phone_value = request.form.get('phone_number', '')
            if phone_value:
                rider.phone = phone_value
            address_value = request.form.get('address', '')
            if address_value:
                rider.address = address_value
            
            # Handle profile image upload
            if 'profile_image' in request.files:
                file = request.files['profile_image']
                if file and file.filename:
                    try:
                        profile_path = _save_uploaded_file(
                            file,
                            os.path.join('static', 'uploads', 'profile_pics'),
                            'image'
                        )
                        rider.profile_image = profile_path
                    except Exception as e:
                        flash(f'Error uploading profile image: {str(e)}', 'warning')
            
            # Handle ID/License upload
            if 'id_document' in request.files:
                file = request.files['id_document']
                if file and file.filename:
                    try:
                        id_path = _save_uploaded_file(
                            file,
                            os.path.join('static', 'uploads', 'business_docs'),
                            'document'
                        )
                        rider.id_document = id_path
                    except Exception as e:
                        flash(f'Error uploading ID document: {str(e)}', 'warning')
            
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('rider_profile'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'error')
            import traceback
            print(f"Profile update error: {traceback.format_exc()}")
    
    # Get performance stats (count both delivered and completed orders)
    total_deliveries = Order.query.filter(
        Order.rider_id == rider.id,
        Order.status.in_(['delivered', 'completed']),
        Order.delivered_at.isnot(None)
    ).count()
    
    total_earnings = sum(
        float(order.total_amount) * 0.05
        for order in Order.query.filter(
            Order.rider_id == rider.id,
            Order.status.in_(['delivered', 'completed']),
            Order.delivered_at.isnot(None)
        ).all()
    )
    
    return render_template('rider/profile.html',
                         rider=rider,
                         total_deliveries=total_deliveries,
                         total_earnings=total_earnings)

@app.route('/rider/complaints', methods=['GET', 'POST'])
@role_required('rider')
def rider_complaints():
    """Submit and view complaints"""
    rider = get_current_user()
    
    if request.method == 'POST':
        try:
            ticket_number = f"TICKET-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            complaint = Complaint(
                ticket_number=ticket_number,
                complainant_id=rider.id,
                category=request.form.get('category'),
                subject=request.form.get('subject'),
                description=request.form.get('description'),
                status='open',
                priority='medium'
            )
            
            db.session.add(complaint)
            db.session.commit()
            
            flash(f'Complaint submitted successfully! Ticket: {ticket_number}', 'success')
            return redirect(url_for('rider_complaints'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error submitting complaint: {str(e)}', 'error')
    
    # Get rider's complaints
    complaints = Complaint.query.filter_by(complainant_id=rider.id).order_by(
        Complaint.created_at.desc()
    ).all()
    
    return render_template('rider/complaints.html', complaints=complaints)

@app.route('/seller/settings', methods=['GET', 'POST'])
@role_required('seller')
def seller_settings():
    user = get_current_user()
    
    if request.method == 'POST':
        section = request.form.get('section', 'profile')
        
        try:
            if section == 'profile':
                # Profile Settings
                user.first_name = request.form.get('first_name', user.first_name)
                user.last_name = request.form.get('last_name', user.last_name)
                user.email = request.form.get('email', user.email)
                user.phone = request.form.get('phone', user.phone)
                user.business_name = request.form.get('business_name', user.business_name)
                user.address = request.form.get('address', user.address)
                
                # Handle profile image
                if 'profile_image' in request.files and request.files['profile_image'].filename:
                    profile_path = _save_uploaded_file(
                        request.files['profile_image'], os.path.join('static', 'uploads', 'profile_pics')
                    )
                    user.profile_image = profile_path
                
                flash('Profile updated successfully!', 'success')
                
            elif section == 'store':
                # Store Customization
                user.business_name = request.form.get('business_name', user.business_name)
                
                # Handle store banner
                if 'store_banner' in request.files and request.files['store_banner'].filename:
                    banner_path = _save_uploaded_file(
                        request.files['store_banner'], os.path.join('static', 'uploads', 'store_banners')
                    )
                    # Add store_banner field to user if needed
                
                # Handle store logo
                if 'store_logo' in request.files and request.files['store_logo'].filename:
                    logo_path = _save_uploaded_file(
                        request.files['store_logo'], os.path.join('static', 'uploads', 'store_logos')
                    )
                    # Add store_logo field to user if needed
                
                flash('Store settings updated successfully!', 'success')
                
            elif section == 'payments':
                # Payment & Payout Settings
                # Add payment fields to user model if needed
                flash('Payment settings updated successfully!', 'success')
                
            elif section == 'notifications':
                # Notification Preferences
                # Add notification preferences if needed
                flash('Notification preferences updated successfully!', 'success')
            
            db.session.commit()
            
            # Check if it's an AJAX request
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Settings saved!'})
            else:
                return redirect(url_for('seller_settings'))
            
        except Exception as e:
            db.session.rollback()
            flash('Error updating settings. Please try again.', 'error')
            print(f"Settings update error: {e}")
            
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': str(e)}), 400
            else:
                return redirect(url_for('seller_settings'))
    
    return render_template('seller/settings.html', user=user)

@app.route('/seller/change-password', methods=['POST'])
@role_required('seller')
def seller_change_password():
    """Handle password change for seller"""
    user = get_current_user()
    
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not all([current_password, new_password, confirm_password]):
        flash('All fields are required', 'error')
        return redirect(url_for('seller_settings'))
    
    if not check_password_hash(user.password, current_password):
        flash('Current password is incorrect', 'error')
        return redirect(url_for('seller_settings'))
    
    if new_password != confirm_password:
        flash('New passwords do not match', 'error')
        return redirect(url_for('seller_settings'))
    
    if len(new_password) < 8:
        flash('Password must be at least 8 characters long', 'error')
        return redirect(url_for('seller_settings'))
    
    try:
        user.password = generate_password_hash(new_password)
        db.session.commit()
        flash('Password changed successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error changing password', 'error')
        print(f"Password change error: {e}")
    
    return redirect(url_for('seller_settings'))

@app.route('/seller/reviews')
@role_required('seller')
def seller_reviews():
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    
    # Get seller's products
    seller_products = Product.query.filter_by(seller_id=user.id).all()
    product_ids = [p.id for p in seller_products]
    
    # Get all reviews for seller's products (no server-side filtering)
    query = Review.query.filter(
        Review.product_id.in_(product_ids),
        Review.is_approved == True
    )
    
    # Order by most recent
    reviews = query.order_by(Review.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False  # Increased per_page for client-side filtering
    )
    
    # Get rating distribution
    rating_distribution = {}
    for rating in range(1, 6):
        count = Review.query.filter(
            Review.product_id.in_(product_ids),
            Review.is_approved == True,
            Review.rating == rating
        ).count()
        rating_distribution[rating] = count
    
    # Calculate average rating
    all_reviews = Review.query.filter(
        Review.product_id.in_(product_ids),
        Review.is_approved == True
    ).all()
    
    avg_rating = 0
    total_reviews = len(all_reviews)
    if total_reviews > 0:
        avg_rating = sum(review.rating for review in all_reviews) / total_reviews
    
    # Get unread notifications count
    unread_notifications = Notification.query.filter_by(
        user_id=user.id,
        is_read=False
    ).count()
    
    return render_template('seller/reviews.html',
                         reviews=reviews,
                         seller_products=seller_products,
                         rating_distribution=rating_distribution,
                         avg_rating=avg_rating,
                         total_reviews=total_reviews,
                         unread_notifications=unread_notifications)

@app.route('/seller/warnings')
@role_required('seller')
def seller_warnings():
    """Seller warnings and violations page - includes both SellerWarning and Notification warnings"""
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    
    # Get SellerWarning records
    seller_warning_query = SellerWarning.query.filter_by(seller_id=user.id)
    
    # Get Notification warnings (from admin warning feature)
    notification_warning_query = Notification.query.filter_by(
        user_id=user.id,
        type='warning'
    )
    
    # Apply status filter to SellerWarning
    if status_filter == 'unread':
        seller_warning_query = seller_warning_query.filter_by(is_acknowledged=False)
        notification_warning_query = notification_warning_query.filter_by(is_read=False)
    elif status_filter == 'acknowledged':
        seller_warning_query = seller_warning_query.filter_by(is_acknowledged=True)
        notification_warning_query = notification_warning_query.filter_by(is_read=True)
    elif status_filter == 'resolved':
        seller_warning_query = seller_warning_query.filter_by(is_resolved=True)
        # Notifications don't have resolved status, so we'll consider read as resolved
        notification_warning_query = notification_warning_query.filter_by(is_read=True)
    elif status_filter == 'critical':
        seller_warning_query = seller_warning_query.filter(
            (SellerWarning.severity == 'critical') | 
            (SellerWarning.offense_level >= 3)
        )
        notification_warning_query = notification_warning_query.filter(
            Notification.priority.in_(['urgent', 'high'])
        )
    
    # Get all warnings (both types)
    seller_warnings = seller_warning_query.order_by(SellerWarning.created_at.desc()).all()
    notification_warnings = notification_warning_query.order_by(Notification.created_at.desc()).all()
    
    # Combine and sort by date
    all_warnings = []
    
    # Add SellerWarning records
    for sw in seller_warnings:
        all_warnings.append({
            'type': 'seller_warning',
            'id': sw.id,
            'title': sw.title or 'Warning',
            'message': sw.description,
            'category': sw.warning_type,
            'priority': sw.severity,
            'is_read': sw.is_acknowledged,
            'is_resolved': sw.is_resolved,
            'created_at': sw.created_at,
            'admin_id': sw.admin_id,
            'offense_level': sw.offense_level,
            'object': sw
        })
    
    # Add Notification warnings
    for nw in notification_warnings:
        all_warnings.append({
            'type': 'notification_warning',
            'id': nw.id,
            'title': nw.title,
            'message': nw.message,
            'category': nw.category,
            'priority': nw.priority,
            'is_read': nw.is_read,
            'is_resolved': nw.is_read,  # Consider read as resolved for notifications
            'created_at': nw.created_at,
            'admin_id': nw.data.get('admin_id') if nw.data else None,
            'offense_level': None,
            'object': nw
        })
    
    # Sort by created_at descending
    all_warnings.sort(key=lambda x: x['created_at'], reverse=True)
    
    # Manual pagination
    per_page = 10
    start = (page - 1) * per_page
    end = start + per_page
    paginated_warnings = all_warnings[start:end]
    total_pages = (len(all_warnings) + per_page - 1) // per_page
    
    # Create pagination object
    class PaginationHelper:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None
        
        def iter_pages(self, left_edge=2, left_current=2, right_current=3, right_edge=2):
            last = 0
            for num in range(1, self.pages + 1):
                if num <= left_edge or \
                   (num > self.page - left_current - 1 and num < self.page + right_current) or \
                   num > self.pages - right_edge:
                    if last + 1 != num:
                        yield None
                    yield num
                    last = num
    
    warnings = PaginationHelper(paginated_warnings, page, per_page, len(all_warnings))
    
    # Get warning statistics (combined)
    total_warnings = len(all_warnings)
    unread_warnings = sum(1 for w in all_warnings if not w['is_read'])
    critical_warnings = sum(1 for w in all_warnings if w['priority'] in ['critical', 'urgent', 'high'])
    resolved_warnings = sum(1 for w in all_warnings if w['is_resolved'])
    
    # Get recent warning types for insights (combined)
    warning_type_counts = {}
    for w in all_warnings:
        category = w['category'] or 'general'
        warning_type_counts[category] = warning_type_counts.get(category, 0) + 1
    
    warning_types = [(k, v) for k, v in warning_type_counts.items()]
    
    return render_template('seller/warnings.html',
                         warnings=warnings,
                         total_warnings=total_warnings,
                         unread_warnings=unread_warnings,
                         critical_warnings=critical_warnings,
                         resolved_warnings=resolved_warnings,
                         warning_types=warning_types,
                         current_status=status_filter)

@app.route('/seller/warnings/<int:warning_id>/acknowledge', methods=['POST'])
@role_required('seller')
def acknowledge_warning(warning_id):
    """Acknowledge a warning"""
    user = get_current_user()
    warning = SellerWarning.query.filter_by(id=warning_id, seller_id=user.id).first_or_404()
    
    if not warning.is_acknowledged:
        warning.is_acknowledged = True
        warning.acknowledged_at = utc_now()
        
        # Add seller response if provided
        seller_response = request.json.get('response', '') if request.is_json else request.form.get('response', '')
        if seller_response:
            warning.seller_response = seller_response
        
        db.session.commit()
        
        # Create acknowledgment notification for admin
        create_notification(
            user_id=warning.admin_id,
            notification_type='admin_action',
            category='system',
            title=f"Warning Acknowledged by {user.first_name} {user.last_name}",
            message=f"Seller has acknowledged the warning: {warning.title}",
            priority='medium',
            data={'warning_id': warning.id, 'seller_id': user.id}
        )
        
        flash('Warning acknowledged successfully.', 'success')
    
    if request.is_json:
        return jsonify({'success': True, 'message': 'Warning acknowledged'})
    
    return redirect(url_for('seller_warnings'))

@app.route('/seller/warnings/<int:warning_id>/respond', methods=['POST'])
@role_required('seller')
def respond_to_warning(warning_id):
    """Respond to a warning with corrective action details"""
    user = get_current_user()
    warning = SellerWarning.query.filter_by(id=warning_id, seller_id=user.id).first_or_404()
    
    response = request.json.get('response') if request.is_json else request.form.get('response')
    
    if response:
        warning.seller_response = response
        if not warning.is_acknowledged:
            warning.is_acknowledged = True
            warning.acknowledged_at = utc_now()
        
        db.session.commit()
        
        # Notify admin of seller response
        create_notification(
            user_id=warning.admin_id,
            notification_type='admin_action',
            category='system',
            title=f"Seller Response to Warning",
            message=f"{user.first_name} {user.last_name} has responded to warning: {warning.title}",
            priority='medium',
            action_url=url_for('admin_warning_details', warning_id=warning.id),
            action_text="View Response",
            data={'warning_id': warning.id, 'seller_id': user.id}
        )
        
        flash('Response submitted successfully.', 'success')
    
    if request.is_json:
        return jsonify({'success': True, 'message': 'Response submitted'})
    
    return redirect(url_for('seller_warnings'))

@app.route('/seller/profile')
@role_required('seller')
def seller_profile():
    user = get_current_user()
    
    # Get seller statistics
    total_products = Product.query.filter_by(seller_id=user.id).count()
    total_orders = OrderItem.query.filter_by(seller_id=user.id).count()
    
    # Calculate revenue
    order_items = OrderItem.query.filter_by(seller_id=user.id).all()
    total_revenue = sum(float(item.total_price) for item in order_items)
    
    # Get user's products and orders as lists for template
    user_products = user.products.all()
    user_orders = user.orders.all()
    
    # Get followers count
    total_followers = Follow.query.filter_by(following_id=user.id).count()
    
    # Get followers list (recent 10)
    recent_followers = Follow.query.filter_by(following_id=user.id)\
        .order_by(Follow.created_at.desc())\
        .limit(10)\
        .all()
    
    # Get average rating and total reviews
    total_reviews = db.session.query(Review).join(Product).filter(
        Product.seller_id == user.id,
        Review.is_approved == True
    ).count()
    
    avg_rating = db.session.query(db.func.avg(Review.rating)).join(Product).filter(
        Product.seller_id == user.id,
        Review.is_approved == True
    ).scalar() or 0
    
    return render_template('seller/profile.html',
                         user=user,
                         total_products=total_products,
                         total_orders=total_orders,
                         total_revenue=total_revenue,
                         user_products=user_products,
                         user_orders=user_orders,
                         total_followers=total_followers,
                         recent_followers=recent_followers,
                         avg_rating=avg_rating,
                         total_reviews=total_reviews)

# ==================== RAIDER ROUTES ====================

@app.route('/raider/dashboard')
@role_required('raider')
def raider_dashboard():
    """Render Raider Dashboard (mobile-first)"""
    user = get_current_user()

    # Basic placeholders; replace with real queries when backend ready
    raider_profile = {
        'total_deliveries': 0,
        'average_rating': 0.0,
        'total_earnings': 0.0,
        'vehicle_type': 'motorcycle',
        'vehicle_plate': 'N/A',
        'is_online': False,
    }
    today_earnings = 0.0
    week_earnings = 0.0
    available_orders = []
    available_orders_count = 0
    my_orders = []

    return render_template(
        'raider/raider_dashboard.html',
        raider_profile=raider_profile,
        today_earnings=today_earnings,
        week_earnings=week_earnings,
        available_orders=available_orders,
        available_orders_count=available_orders_count,
        my_orders=my_orders,
        current_user=user,
    )

# =====================================================
# API ROUTES
# =====================================================

@app.route('/api/add_to_cart', methods=['POST'])
@login_required
def api_add_to_cart():
    """API endpoint to add product to cart - FIRESTORE VERSION"""
    try:
        from firestore_helper import add_to_cart_firestore
        
        data = request.get_json()
        product_id = data.get('product_id')
        quantity = data.get('quantity', 1)
        variant = data.get('variant')
        selected_weight = data.get('selected_weight')
        
        user = get_current_user()
        product = Product.query.get_or_404(product_id)
        
        # Check if product has sufficient stock
        if product.stock_quantity <= 0:
            return jsonify({'success': False, 'message': 'This product is out of stock'})
        
        # Compute unit price considering weight
        multiplier = _compute_weight_multiplier(selected_weight)
        computed_unit_price = float(product.price) * multiplier
        
        # Use Firebase UID for cross-platform sync
        user_id = user.firebase_uid if user.firebase_uid else str(user.id)
        
        # Add to Firestore
        result = add_to_cart_firestore(
            user_id=user_id,
            product_id=str(product_id),
            quantity=quantity,
            product_name=product.name,
            product_image=product.image_url or '',
            price=computed_unit_price,
            variant=variant,
            selected_weight=selected_weight,
            seller_id=_get_seller_firebase_uid(product.seller_id) if product.seller_id else None,
            max_stock=product.stock_quantity
        )
        
        return jsonify(result)
        
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)})
    except Exception as e:
        print(f"Error adding to cart: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/remove_from_cart', methods=['POST'])
@login_required
def api_remove_from_cart():
    """API endpoint to remove product from cart - FIRESTORE VERSION"""
    try:
        from firestore_helper import remove_from_cart_firestore
        
        data = request.get_json()
        item_id = data.get('item_id')  # Firestore document ID
        
        user = get_current_user()
        # Use Firebase UID for cross-platform sync
        user_id = user.firebase_uid if user.firebase_uid else str(user.id)
        result = remove_from_cart_firestore(user_id, item_id)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
        variant = data.get('variant')
        selected_weight = data.get('selected_weight')
        
        user = get_current_user()
        cart_item = Cart.query.filter_by(
            user_id=user.id, product_id=product_id, variant=variant, selected_weight=selected_weight
        ).first()
        
        if cart_item:
            db.session.delete(cart_item)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Product removed from cart'})
        else:
            return jsonify({'success': False, 'message': 'Item not found in cart'})
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/update_cart', methods=['POST'])
@login_required
def api_update_cart():
    """API endpoint to update cart item quantity - FIRESTORE VERSION"""
    try:
        from firestore_helper import update_cart_quantity_firestore
        
        data = request.get_json()
        item_id = data.get('item_id')
        quantity = data.get('quantity', 1)
        
        user = get_current_user()
        # Use Firebase UID for cross-platform sync
        user_id = user.firebase_uid if user.firebase_uid else str(user.id)
        result = update_cart_quantity_firestore(user_id, item_id, quantity)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/address/provinces/<region>')
def api_get_provinces(region):
    """Get provinces by region"""
    # Sample Philippine address data (replace with actual database or API)
    address_data = {
        'NCR': ['Metro Manila'],
        'CAR': ['Abra', 'Apayao', 'Benguet', 'Ifugao', 'Kalinga', 'Mountain Province'],
        'Region I': ['Ilocos Norte', 'Ilocos Sur', 'La Union', 'Pangasinan'],
        'Region II': ['Batanes', 'Cagayan', 'Isabela', 'Nueva Vizcaya', 'Quirino'],
        'Region III': ['Aurora', 'Bataan', 'Bulacan', 'Nueva Ecija', 'Pampanga', 'Tarlac', 'Zambales'],
        'Region IV-A': ['Batangas', 'Cavite', 'Laguna', 'Quezon', 'Rizal'],
        'Region IV-B': ['Marinduque', 'Occidental Mindoro', 'Oriental Mindoro', 'Palawan', 'Romblon'],
        'Region V': ['Albay', 'Camarines Norte', 'Camarines Sur', 'Catanduanes', 'Masbate', 'Sorsogon'],
        'Region VI': ['Aklan', 'Antique', 'Capiz', 'Guimaras', 'Iloilo', 'Negros Occidental'],
        'Region VII': ['Bohol', 'Cebu', 'Negros Oriental', 'Siquijor'],
        'Region VIII': ['Biliran', 'Eastern Samar', 'Leyte', 'Northern Samar', 'Samar', 'Southern Leyte'],
        'Region IX': ['Zamboanga del Norte', 'Zamboanga del Sur', 'Zamboanga Sibugay'],
        'Region X': ['Bukidnon', 'Camiguin', 'Lanao del Norte', 'Misamis Occidental', 'Misamis Oriental'],
        'Region XI': ['Davao de Oro', 'Davao del Norte', 'Davao del Sur', 'Davao Occidental', 'Davao Oriental'],
        'Region XII': ['Cotabato', 'Sarangani', 'South Cotabato', 'Sultan Kudarat'],
        'Region XIII': ['Agusan del Norte', 'Agusan del Sur', 'Dinagat Islands', 'Surigao del Norte', 'Surigao del Sur'],
        'BARMM': ['Basilan', 'Lanao del Sur', 'Maguindanao', 'Sulu', 'Tawi-Tawi']
    }
    
    provinces = address_data.get(region, [])
    return jsonify(provinces)

@app.route('/api/address/municipalities/<province>')
def api_get_municipalities(province):
    """Get municipalities by province"""
    # Sample data for major provinces (replace with actual database)
    municipality_data = {
        'Metro Manila': ['Caloocan', 'Las Piñas', 'Makati', 'Malabon', 'Mandaluyong', 'Manila', 'Marikina', 'Muntinlupa', 'Navotas', 'Parañaque', 'Pasay', 'Pasig', 'Pateros', 'Quezon City', 'San Juan', 'Taguig', 'Valenzuela'],
        'Bulacan': ['Angat', 'Balagtas', 'Baliuag', 'Bocaue', 'Bulakan', 'Bustos', 'Calumpit', 'Doña Remedios Trinidad', 'Guiguinto', 'Hagonoy', 'Marilao', 'Meycauayan', 'Norzagaray', 'Obando', 'Pandi', 'Paombong', 'Plaridel', 'Pulilan', 'San Ildefonso', 'San Miguel', 'San Rafael', 'Santa Maria', 'Malolos'],
        'Cavite': ['Alfonso', 'Amadeo', 'Bacoor', 'Carmona', 'Cavite City', 'Dasmariñas', 'General Emilio Aguinaldo', 'General Mariano Alvarez', 'General Trias', 'Imus', 'Indang', 'Kawit', 'Magallanes', 'Maragondon', 'Mendez', 'Naic', 'Noveleta', 'Rosario', 'Silang', 'Tagaytay', 'Tanza', 'Ternate', 'Trece Martires'],
        'Laguna': ['Alaminos', 'Bay', 'Biñan', 'Cabuyao', 'Calamba', 'Calauan', 'Cavinti', 'Famy', 'Kalayaan', 'Liliw', 'Los Baños', 'Luisiana', 'Lumban', 'Mabitac', 'Magdalena', 'Majayjay', 'Nagcarlan', 'Paete', 'Pagsanjan', 'Pakil', 'Pangil', 'Pila', 'Rizal', 'San Pablo', 'San Pedro', 'Santa Cruz', 'Santa Maria', 'Santa Rosa', 'Siniloan', 'Victoria']
    }
    
    municipalities = municipality_data.get(province, [])
    return jsonify(municipalities)

@app.route('/api/address/barangays/<municipality>')
def api_get_barangays(municipality):
    """Get barangays by municipality"""
    # Sample data for major cities (replace with actual database)
    barangay_data = {
        'Manila': ['Binondo', 'Ermita', 'Intramuros', 'Malate', 'Paco', 'Pandacan', 'Port Area', 'Quiapo', 'Sampaloc', 'San Andres', 'San Miguel', 'San Nicolas', 'Santa Ana', 'Santa Cruz', 'Santa Mesa', 'Tondo'],
        'Quezon City': ['Bagong Pag-asa', 'Bahay Toro', 'Balingasa', 'Bungad', 'Damar', 'Damayan', 'Del Monte', 'Gulod', 'Lourdes', 'Maharlika', 'Manresa', 'Mariblo', 'Nagkaisang Nayon', 'Pag-ibig sa Nayon', 'Paraiso', 'Phil-Am', 'Project 6', 'Sacred Heart', 'Sienna', 'Talayan', 'Tandang Sora', 'Ugong Norte', 'Villa Maria Clara'],
        'Makati': ['Bel-Air', 'Cembo', 'Comembo', 'Dasmariñas', 'Forbes Park', 'Guadalupe Nuevo', 'Guadalupe Viejo', 'Kasilawan', 'La Paz', 'Magallanes', 'Olympia', 'Palanan', 'Pembo', 'Pinagkaisahan', 'Pio del Pilar', 'Poblacion', 'Post Proper Northside', 'Post Proper Southside', 'Rizal', 'San Antonio', 'San Isidro', 'San Lorenzo', 'Santa Cruz', 'Singkamas', 'Tejeros', 'Urdaneta', 'Valenzuela'],
        'Malolos': ['Anilao', 'Atlag', 'Babatnin', 'Bagna', 'Bagong Nayon', 'Bangkal', 'Barihan', 'Bulihan', 'Bungahan', 'Caingin', 'Calero', 'Caliligawan', 'Canalate', 'Caniogan', 'Catmon', 'Guinhawa', 'Ligas', 'Longos', 'Look 1st', 'Look 2nd', 'Lugam', 'Mabolo', 'Masile', 'Mojon', 'Namayan', 'Niugan', 'Pamarawan', 'Panasahan', 'Pinagbakahan', 'San Agustin', 'San Gabriel', 'San Juan', 'San Pablo', 'San Vicente', 'Santiago', 'Santisima Trinidad', 'Santo Cristo', 'Santo Niño', 'Santo Rosario', 'Sumapang Bata', 'Sumapang Matanda', 'Taal', 'Tikay']
    }
    
    barangays = barangay_data.get(municipality, [])
    return jsonify(barangays)

@app.route('/api/cart_count')
@login_required
def api_cart_count():
    """API endpoint to get cart item count - FIRESTORE VERSION"""
    try:
        from firestore_helper import get_cart_items_firestore
        
        user = get_current_user()
        cart_items = get_cart_items_firestore(str(user.id))
        count = len(cart_items)
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# =====================================================
# WISHLIST API ROUTES
# =====================================================

@app.route('/api/wishlist/add', methods=['POST'])
@login_required
def api_add_to_wishlist():
    """Add product to wishlist - FIRESTORE VERSION"""
    try:
        from firestore_helper import add_to_wishlist_firestore
        
        user = get_current_user()
        data = request.get_json()
        product_id = data.get('product_id')
        
        if not product_id:
            return jsonify({'success': False, 'message': 'Product ID is required'})
        
        # Check if product exists
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'success': False, 'message': 'Product not found'})
        
        # Use Firebase UID for cross-platform sync
        user_id = user.firebase_uid if user.firebase_uid else str(user.id)
        
        # Add to Firestore wishlist
        result = add_to_wishlist_firestore(
            user_id=user_id,
            product_id=str(product_id),
            product_name=product.name,
            product_image=product.image_url or '',
            price=float(product.price)
        )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/wishlist/remove', methods=['POST'])
@login_required
def api_remove_from_wishlist():
    """Remove product from wishlist - FIRESTORE VERSION"""
    try:
        from firestore_helper import remove_from_wishlist_firestore
        
        user = get_current_user()
        data = request.get_json()
        product_id = data.get('product_id')
        
        if not product_id:
            return jsonify({'success': False, 'message': 'Product ID is required'})
        
        # Use Firebase UID for cross-platform sync
        user_id = user.firebase_uid if user.firebase_uid else str(user.id)
        
        result = remove_from_wishlist_firestore(user_id, str(product_id))
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/wishlist/toggle', methods=['POST'])
@login_required
def api_toggle_wishlist():
    """Toggle product in/out of wishlist - FIRESTORE VERSION"""
    try:
        from firestore_helper import is_in_wishlist_firestore, add_to_wishlist_firestore, remove_from_wishlist_firestore
        
        user = get_current_user()
        data = request.get_json()
        product_id = data.get('product_id')
        
        if not product_id:
            return jsonify({'success': False, 'message': 'Product ID is required'})
        
        # Use Firebase UID for cross-platform sync
        user_id = user.firebase_uid if user.firebase_uid else str(user.id)
        
        # Check if already in wishlist
        in_wishlist = is_in_wishlist_firestore(user_id, str(product_id))
        
        if in_wishlist:
            # Remove from wishlist
            result = remove_from_wishlist_firestore(user_id, str(product_id))
            return jsonify({'success': True, 'message': 'Removed from wishlist', 'in_wishlist': False})
        else:
            # Add to wishlist
            product = Product.query.get(product_id)
            if not product:
                return jsonify({'success': False, 'message': 'Product not found'})
            
            result = add_to_wishlist_firestore(
                user_id=user_id,
                product_id=str(product_id),
                product_name=product.name,
                product_image=product.image_url or '',
                price=float(product.price)
            )
            return jsonify({'success': True, 'message': 'Added to wishlist', 'in_wishlist': True})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# =====================================================
# FOLLOW/UNFOLLOW API ROUTES
# =====================================================

@app.route('/api/follow_seller/<int:seller_id>', methods=['POST'])
@login_required
def api_follow_seller(seller_id):
    """Follow or unfollow a seller"""
    try:
        user = get_current_user()
        
        # Check if seller exists and is actually a seller
        seller = User.query.get(seller_id)
        if not seller:
            return jsonify({'success': False, 'message': 'Seller not found'})
        
        if seller.role != 'seller':
            return jsonify({'success': False, 'message': 'User is not a seller'})
        
        # Check if user is trying to follow themselves
        if user.id == seller_id:
            return jsonify({'success': False, 'message': 'You cannot follow yourself'})
        
        # Check if already following
        existing_follow = Follow.query.filter_by(
            follower_id=user.id,
            following_id=seller_id
        ).first()
        
        if existing_follow:
            # Unfollow
            db.session.delete(existing_follow)
            db.session.commit()
            
            # Get updated follower count
            follower_count = Follow.query.filter_by(following_id=seller_id).count()
            
            return jsonify({
                'success': True,
                'action': 'unfollowed',
                'message': f'You unfollowed {seller.business_name or seller.full_name}',
                'follower_count': follower_count
            })
        else:
            # Follow
            new_follow = Follow(
                follower_id=user.id,
                following_id=seller_id
            )
            db.session.add(new_follow)
            db.session.commit()
            
            # Get updated follower count
            follower_count = Follow.query.filter_by(following_id=seller_id).count()
            
            return jsonify({
                'success': True,
                'action': 'followed',
                'message': f'You are now following {seller.business_name or seller.full_name}',
                'follower_count': follower_count
            })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in follow_seller: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/check_following/<int:seller_id>', methods=['GET'])
@login_required
def api_check_following(seller_id):
    """Check if current user is following a seller"""
    try:
        user = get_current_user()
        
        is_following = Follow.query.filter_by(
            follower_id=user.id,
            following_id=seller_id
        ).first() is not None
        
        follower_count = Follow.query.filter_by(following_id=seller_id).count()
        
        return jsonify({
            'success': True,
            'is_following': is_following,
            'follower_count': follower_count
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# =====================================================
# ADDRESS MANAGEMENT API ROUTES
# =====================================================

@app.route('/api/addresses/get/<int:address_id>', methods=['GET'])
@login_required
def api_get_address(address_id):
    """Get single address data"""
    try:
        user = get_current_user()
        address = SavedAddress.query.filter_by(id=address_id, user_id=user.id).first()
        
        if not address:
            return jsonify({'success': False, 'message': 'Address not found'})
        
        return jsonify({
            'success': True,
            'address': {
                'id': address.id,
                'label': address.label,
                'full_name': address.full_name,
                'phone': address.phone,
                'address_line_1': address.address_line_1,
                'address_line_2': address.address_line_2,
                'city': address.city,
                'state': address.state,
                'zip_code': address.zip_code,
                'country': address.country,
                'is_default': address.is_default
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/addresses/update/<int:address_id>', methods=['POST'])
@login_required
def api_update_address(address_id):
    """Update saved address"""
    try:
        user = get_current_user()
        address = SavedAddress.query.filter_by(id=address_id, user_id=user.id).first()
        
        if not address:
            return jsonify({'success': False, 'message': 'Address not found'})
        
        # Update address fields
        address.label = request.form.get('label', address.label)
        address.full_name = request.form.get('full_name', address.full_name)
        address.phone = request.form.get('phone', address.phone)
        address.address_line_1 = request.form.get('address_line_1', address.address_line_1)
        address.address_line_2 = request.form.get('address_line_2', address.address_line_2)
        address.city = request.form.get('city', address.city)
        address.state = request.form.get('state', address.state)
        address.zip_code = request.form.get('zip_code', address.zip_code)
        address.country = request.form.get('country', address.country)
        
        # Handle default address
        is_default = request.form.get('is_default') == 'true'
        if is_default and not address.is_default:
            # Unset other defaults
            SavedAddress.query.filter_by(user_id=user.id, is_default=True).update({'is_default': False})
            address.is_default = True
        elif not is_default and address.is_default:
            address.is_default = False
        
        address.updated_at = utc_now()
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Address updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/addresses/delete/<int:address_id>', methods=['DELETE'])
@login_required
def api_delete_address(address_id):
    """Delete saved address"""
    try:
        user = get_current_user()
        address = SavedAddress.query.filter_by(id=address_id, user_id=user.id).first()
        
        if not address:
            return jsonify({'success': False, 'message': 'Address not found'})
        
        db.session.delete(address)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Address deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/addresses/add', methods=['POST'])
@login_required
def add_saved_address():
    """Add new saved address"""
    try:
        user = get_current_user()
        
        # Get form data
        label = request.form.get('label', 'Home')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        address_line_1 = request.form.get('address_line_1')
        address_line_2 = request.form.get('address_line_2', '')
        city = request.form.get('city')
        state = request.form.get('state')
        country = request.form.get('country', 'Philippines')
        zip_code = request.form.get('zip_code')
        is_default = request.form.get('is_default') == 'true'
        
        # If this is set as default, unset all other defaults
        if is_default:
            SavedAddress.query.filter_by(user_id=user.id, is_default=True).update({'is_default': False})
        
        # Create new address
        new_address = SavedAddress(
            user_id=user.id,
            label=label,
            full_name=full_name,
            phone=phone,
            address_line_1=address_line_1,
            address_line_2=address_line_2,
            city=city,
            state=state,
            country=country,
            zip_code=zip_code,
            is_default=is_default
        )
        
        db.session.add(new_address)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Address added successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/addresses/set-default/<int:address_id>', methods=['POST'])
@login_required
def api_set_default_address(address_id):
    """Set address as default"""
    try:
        user = get_current_user()
        address = SavedAddress.query.filter_by(id=address_id, user_id=user.id).first()
        
        if not address:
            return jsonify({'success': False, 'message': 'Address not found'})
        
        # Unset all other defaults
        SavedAddress.query.filter_by(user_id=user.id, is_default=True).update({'is_default': False})
        
        # Set this as default
        address.is_default = True
        address.updated_at = utc_now()
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Default address updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

# =====================================================
# REORDER FUNCTIONALITY
# =====================================================

@app.route('/api/reorder/<order_id>', methods=['POST'])
@login_required
def api_reorder(order_id):
    """Reorder items from a previous order"""
    try:
        user = get_current_user()
        order = Order.query.filter_by(id=order_id, buyer_id=user.id).first()
        
        if not order:
            return jsonify({'success': False, 'message': 'Order not found'})
        
        added_items = 0
        unavailable_items = []
        
        for item in order.order_items:
            product = Product.query.get(item.product_id)
            if product and product.is_active and product.stock_quantity > 0:
                # Check if item already in cart
                existing_cart_item = Cart.query.filter_by(
                    user_id=user.id, 
                    product_id=product.id
                ).first()
                
                if existing_cart_item:
                    # Update quantity
                    existing_cart_item.quantity += item.quantity
                    existing_cart_item.updated_at = utc_now()
                else:
                    # Add new cart item
                    cart_item = Cart(
                        user_id=user.id,
                        product_id=product.id,
                        quantity=item.quantity,
                        unit_price=product.price
                    )
                    db.session.add(cart_item)
                
                added_items += 1
            else:
                unavailable_items.append(product.name if product else 'Unknown Product')
        
        db.session.commit()
        
        message = f'{added_items} items added to cart'
        if unavailable_items:
            message += f'. {len(unavailable_items)} items unavailable: {", ".join(unavailable_items[:3])}'
            if len(unavailable_items) > 3:
                message += f' and {len(unavailable_items) - 3} more'
        
        return jsonify({
            'success': True, 
            'message': message,
            'added_items': added_items,
            'unavailable_items': len(unavailable_items)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

# =====================================================
# CHAT & MESSAGING API
# =====================================================

@app.route('/api/chat/send-product-inquiry', methods=['POST'])
def api_send_product_inquiry():
    """Send automatic product inquiry message from buyer to seller"""
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': 'Please log in to message sellers'}), 401
    
    try:
        data = request.get_json()
        seller_id = data.get('seller_id')
        product_id = data.get('product_id')
        product_name = data.get('product_name')
        
        if not all([seller_id, product_id, product_name]):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        # Verify seller exists
        seller = User.query.get(seller_id)
        if not seller or seller.role != 'seller':
            return jsonify({'success': False, 'message': 'Seller not found'}), 404
        
        # Verify product exists
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'success': False, 'message': 'Product not found'}), 404
        
        # Send automatic inquiry message
        conversation_id = send_product_inquiry_message(
            buyer_id=user.id,
            seller_id=seller_id,
            product_id=product_id,
            product_name=product_name
        )
        
        if conversation_id:
            return jsonify({
                'success': True,
                'message': 'Chat opened successfully',
                'conversation_id': conversation_id
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to open chat'}), 500
            
    except Exception as e:
        print(f"Error in api_send_product_inquiry: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'An error occurred'}), 500

# =====================================================
# SEARCH & AUTOCOMPLETE API
# =====================================================

@app.route('/api/search/autocomplete', methods=['GET'])
def api_search_autocomplete():
    """Smart search autocomplete with product suggestions"""
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify({'suggestions': []})
    
    try:
        # Search in product names, brands, and categories
        products = Product.query.filter(
            and_(
                Product.is_active == True,
                Product.approval_status == 'approved',
                or_(
                    Product.name.ilike(f'%{query}%'),
                    Product.brand.ilike(f'%{query}%'),
                    Product.description.ilike(f'%{query}%')
                )
            )
        ).limit(10).all()
        
        # Get category suggestions
        categories = Category.query.filter(
            Category.name.ilike(f'%{query}%')
        ).limit(5).all()
        
        # Get seller/store suggestions
        sellers = User.query.filter(
            and_(
                User.role == 'seller',
                User.approval_status == 'approved',
                User.is_active == True,
                or_(
                    User.business_name.ilike(f'%{query}%'),
                    User.username.ilike(f'%{query}%'),
                    User.first_name.ilike(f'%{query}%'),
                    User.last_name.ilike(f'%{query}%')
                )
            )
        ).limit(5).all()
        
        suggestions = []
        
        # Add product suggestions
        for product in products:
            suggestions.append({
                'type': 'product',
                'id': product.id,
                'name': product.name,
                'brand': product.brand,
                'price': float(product.price),
                'image_url': product.image_url,
                'category': product.category.name,
                'url': url_for('product_detail', product_id=product.id)
            })
        
        # Add seller/store suggestions
        for seller in sellers:
            # Count seller's products
            product_count = Product.query.filter_by(
                seller_id=seller.id,
                is_active=True,
                approval_status='approved'
            ).count()
            
            suggestions.append({
                'type': 'seller',
                'id': seller.id,
                'name': seller.business_name or f"{seller.first_name} {seller.last_name}",
                'username': seller.username,
                'product_count': product_count,
                'profile_image': seller.profile_image,
                'url': url_for('seller_shop', seller_id=seller.id, username=seller.username)
            })
        
        # Add category suggestions
        for category in categories:
            suggestions.append({
                'type': 'category',
                'id': category.id,
                'name': category.name,
                'url': url_for('buyer_shop', category=category.id)
            })
        
        # Track search if user is logged in
        user = get_current_user()
        if user:
            search_record = SearchHistory(
                user_id=user.id,
                query=query,
                results_count=len(suggestions)
            )
            db.session.add(search_record)
            db.session.commit()
        
        return jsonify({'suggestions': suggestions, 'query': query})
        
    except Exception as e:
        return jsonify({'suggestions': [], 'error': str(e)})

@app.route('/api/search/popular', methods=['GET'])
def api_popular_searches():
    """Get popular search queries"""
    try:
        # Get most common searches from last 30 days
        thirty_days_ago = utc_now() - timedelta(days=30)
        
        popular = db.session.query(
            SearchHistory.query,
            db.func.count(SearchHistory.id).label('count')
        ).filter(
            SearchHistory.created_at >= thirty_days_ago
        ).group_by(SearchHistory.query).order_by(
            db.desc('count')
        ).limit(10).all()
        
        return jsonify({
            'popular_searches': [{'query': q, 'count': c} for q, c in popular]
        })
        
    except Exception as e:
        return jsonify({'popular_searches': [], 'error': str(e)})

@app.route('/api/search/history', methods=['GET'])
@login_required
def api_search_history():
    """Get user's recent search history"""
    try:
        user = get_current_user()
        
        # Get last 10 unique searches
        recent_searches = db.session.query(SearchHistory.query).filter(
            SearchHistory.user_id == user.id
        ).distinct().order_by(
            SearchHistory.created_at.desc()
        ).limit(10).all()
        
        return jsonify({
            'success': True,
            'searches': [{'query': search[0]} for search in recent_searches]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/search/history/clear', methods=['POST'])
@login_required
def api_clear_search_history():
    """Clear user's search history"""
    try:
        user = get_current_user()
        
        SearchHistory.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Search history cleared successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/search/trending', methods=['GET'])
def api_trending_searches():
    """Get trending searches based on recent activity"""
    try:
        # Get searches from last 7 days
        seven_days_ago = utc_now() - timedelta(days=7)
        
        trending = db.session.query(
            SearchHistory.query,
            db.func.count(SearchHistory.id).label('count')
        ).filter(
            SearchHistory.created_at >= seven_days_ago,
            SearchHistory.results_count > 0
        ).group_by(SearchHistory.query).order_by(
            db.desc('count')
        ).limit(5).all()
        
        return jsonify({
            'success': True,
            'trending': [{'query': q, 'count': c} for q, c in trending]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'trending': [], 'error': str(e)})

@app.route('/api/search/recommendations', methods=['GET'])
@login_required
def api_search_recommendations():
    """Get personalized search recommendations based on user behavior"""
    try:
        user = get_current_user()
        
        # Get user's recent purchases
        recent_orders = Order.query.filter_by(
            user_id=user.id
        ).order_by(Order.created_at.desc()).limit(5).all()
        
        recommendations = []
        
        # Get categories from recent purchases
        purchased_categories = set()
        for order in recent_orders:
            for item in order.order_items:
                if item.product and item.product.category:
                    purchased_categories.add(item.product.category.name)
        
        # Suggest related searches
        if purchased_categories:
            for category in list(purchased_categories)[:3]:
                recommendations.append({
                    'type': 'related',
                    'query': category,
                    'reason': f'Based on your recent purchase'
                })
        
        # Get user's most searched categories
        user_searches = SearchHistory.query.filter_by(
            user_id=user.id
        ).order_by(SearchHistory.created_at.desc()).limit(20).all()
        
        if user_searches:
            # Add popular products from searched categories
            for search in user_searches[:2]:
                recommendations.append({
                    'type': 'suggestion',
                    'query': search.query,
                    'reason': 'You searched for this recently'
                })
        
        return jsonify({
            'success': True,
            'recommendations': recommendations[:5]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'recommendations': [], 'error': str(e)})

@app.route('/api/search/save', methods=['POST'])
@login_required
def api_save_search():
    """Save a search query to history"""
    try:
        user = get_current_user()
        data = request.get_json()
        query = data.get('query', '').strip()
        results_count = data.get('results_count', 0)
        
        if not query:
            return jsonify({'success': False, 'message': 'Query is required'})
        
        # Save search
        search_record = SearchHistory(
            user_id=user.id,
            query=query,
            results_count=results_count
        )
        db.session.add(search_record)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Search saved successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

# =====================================================
# PRODUCT Q&A API
# =====================================================

@app.route('/api/product/<int:product_id>/questions', methods=['GET'])
def api_get_product_questions(product_id):
    """Get all questions for a product"""
    try:
        questions = ProductQuestion.query.filter_by(
            product_id=product_id,
            is_public=True
        ).order_by(ProductQuestion.created_at.desc()).all()
        
        result = []
        for q in questions:
            answers = ProductAnswer.query.filter_by(question_id=q.id).all()
            result.append({
                'id': q.id,
                'question': q.question,
                'user_name': q.user.first_name,
                'is_answered': q.is_answered,
                'helpful_count': q.helpful_count,
                'created_at': q.created_at.isoformat(),
                'answers': [{
                    'id': a.id,
                    'answer': a.answer,
                    'seller_name': a.user.business_name or a.user.full_name,
                    'helpful_count': a.helpful_count,
                    'created_at': a.created_at.isoformat()
                } for a in answers]
            })
        
        return jsonify({'questions': result})
        
    except Exception as e:
        return jsonify({'questions': [], 'error': str(e)})

@app.route('/api/product/<int:product_id>/ask-question', methods=['POST'])
@login_required
def api_ask_product_question(product_id):
    """Buyer asks a question about a product"""
    try:
        user = get_current_user()
        data = request.get_json()
        question_text = data.get('question', '').strip()
        
        if not question_text:
            return jsonify({'success': False, 'message': 'Question cannot be empty'})
        
        product = Product.query.get_or_404(product_id)
        
        question = ProductQuestion(
            product_id=product_id,
            user_id=user.id,
            question=question_text,
            is_public=data.get('is_public', True)
        )
        db.session.add(question)
        
        # Notify seller
        notification = Notification(
            user_id=product.seller_id,
            type='product_update',
            category='general',
            priority='medium',
            title='New Product Question',
            message=f'{user.full_name} asked about {product.name}: {question_text[:100]}',
            action_url=url_for('seller_product_questions', product_id=product_id),
            action_text='Answer Question'
        )
        db.session.add(notification)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Question posted successfully', 'question_id': question.id})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/question/<int:question_id>/answer', methods=['POST'])
@login_required
def api_answer_product_question(question_id):
    """Seller answers a product question"""
    try:
        user = get_current_user()
        question = ProductQuestion.query.get_or_404(question_id)
        
        # Verify user is the seller
        if user.id != question.product.seller_id:
            return jsonify({'success': False, 'message': 'Only the seller can answer this question'})
        
        data = request.get_json()
        answer_text = data.get('answer', '').strip()
        
        if not answer_text:
            return jsonify({'success': False, 'message': 'Answer cannot be empty'})
        
        answer = ProductAnswer(
            question_id=question_id,
            user_id=user.id,
            answer=answer_text
        )
        db.session.add(answer)
        
        # Mark question as answered
        question.is_answered = True
        
        # Notify buyer
        notification = Notification(
            user_id=question.user_id,
            type='product_update',
            category='general',
            priority='medium',
            title='Your Question Was Answered',
            message=f'Seller answered your question about {question.product.name}',
            action_url=url_for('product_detail', product_id=question.product_id),
            action_text='View Answer'
        )
        db.session.add(notification)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Answer posted successfully', 'answer_id': answer.id})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/question/<int:question_id>/helpful', methods=['POST'])
@login_required
def api_mark_question_helpful(question_id):
    """Mark a question as helpful"""
    try:
        question = ProductQuestion.query.get_or_404(question_id)
        question.helpful_count += 1
        db.session.commit()
        
        return jsonify({'success': True, 'helpful_count': question.helpful_count})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/answer/<int:answer_id>/helpful', methods=['POST'])
@login_required
def api_mark_answer_helpful(answer_id):
    """Mark an answer as helpful"""
    try:
        answer = ProductAnswer.query.get_or_404(answer_id)
        answer.helpful_count += 1
        db.session.commit()
        
        return jsonify({'success': True, 'helpful_count': answer.helpful_count})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

# =====================================================
# PRODUCT RECOMMENDATIONS API
# =====================================================

@app.route('/api/recommendations', methods=['GET'])
@login_required
def api_get_recommendations():
    """Get personalized product recommendations"""
    try:
        user = get_current_user()
        
        # Get existing recommendations
        recommendations = ProductRecommendation.query.filter_by(
            user_id=user.id
        ).order_by(ProductRecommendation.score.desc()).limit(12).all()
        
        # If no recommendations, generate based on popular products
        if not recommendations:
            popular_products = Product.query.filter_by(
                is_active=True,
                approval_status='approved'
            ).order_by(Product.created_at.desc()).limit(12).all()
            
            return jsonify({
                'recommendations': [{
                    'product_id': p.id,
                    'name': p.name,
                    'price': float(p.price),
                    'image_url': p.image_url,
                    'rating': p.average_rating,
                    'reason': 'Popular product'
                } for p in popular_products]
            })
        
        result = []
        for rec in recommendations:
            product = rec.product
            if product.is_active and product.approval_status == 'approved':
                result.append({
                    'product_id': product.id,
                    'name': product.name,
                    'price': float(product.price),
                    'image_url': product.image_url,
                    'rating': product.average_rating,
                    'reason': rec.reason,
                    'score': rec.score
                })
        
        return jsonify({'recommendations': result})
        
    except Exception as e:
        return jsonify({'recommendations': [], 'error': str(e)})

@app.route('/api/product/<int:product_id>/track-view', methods=['POST'])
def api_track_product_view(product_id):
    """Track product view for analytics and recommendations"""
    try:
        user = get_current_user()
        
        view = ProductView(
            product_id=product_id,
            user_id=user.id if user else None,
            session_id=session.get('session_id', request.cookies.get('session')),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', ''),
            referrer=request.referrer
        )
        db.session.add(view)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/product/<int:product_id>/toggle-featured', methods=['POST'])
@role_required('admin')
def api_toggle_featured(product_id):
    """Toggle featured status of a product (Admin only)"""
    try:
        product = Product.query.get_or_404(product_id)
        product.is_featured = not product.is_featured
        db.session.commit()
        
        return jsonify({
            'success': True,
            'is_featured': product.is_featured,
            'message': f'Product {"added to" if product.is_featured else "removed from"} featured collection'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

# =====================================================
# COUPON VALIDATION API
# =====================================================

@app.route('/api/coupon/validate', methods=['POST'])
@login_required
def api_validate_coupon():
    """Validate coupon code and calculate discount"""
    try:
        user = get_current_user()
        data = request.get_json()
        coupon_code = data.get('code', '').strip().upper()
        cart_total = float(data.get('cart_total', 0))
        
        if not coupon_code:
            return jsonify({'valid': False, 'message': 'Please enter a coupon code'})
        
        # Find coupon
        coupon = Coupon.query.filter_by(code=coupon_code, is_active=True).first()
        
        if not coupon:
            return jsonify({'valid': False, 'message': 'Invalid coupon code'})
        
        # Check expiration
        now = utc_now()
        if coupon.starts_at and coupon.starts_at > now:
            return jsonify({'valid': False, 'message': 'Coupon not yet active'})
        if coupon.expires_at and coupon.expires_at < now:
            return jsonify({'valid': False, 'message': 'Coupon has expired'})
        
        # Check usage limit
        if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
            return jsonify({'valid': False, 'message': 'Coupon usage limit reached'})
        
        # Check minimum amount
        if cart_total < float(coupon.minimum_amount):
            return jsonify({
                'valid': False,
                'message': f'Minimum order amount ${coupon.minimum_amount} required'
            })
        
        # Calculate discount
        if coupon.type == 'percentage':
            discount = cart_total * (float(coupon.value) / 100)
            if coupon.maximum_discount:
                discount = min(discount, float(coupon.maximum_discount))
        else:  # fixed_amount
            discount = float(coupon.value)
        
        discount = min(discount, cart_total)  # Don't exceed cart total
        
        return jsonify({
            'valid': True,
            'message': 'Coupon applied successfully',
            'discount_amount': discount,
            'coupon_id': coupon.id,
            'coupon_name': coupon.name,
            'final_total': cart_total - discount
        })
        
    except Exception as e:
        return jsonify({'valid': False, 'message': str(e)})

# =====================================================
# CHAT SYSTEM ROUTES
# =====================================================

@app.route('/chat')
@login_required
def chat_index():
    """Redirect to home - use floating chat widget instead"""
    user = get_current_user()
    flash('Use the floating chat button to access your messages!', 'info')
    
    if user.role == 'buyer':
        return redirect(url_for('buyer_home'))
    elif user.role == 'seller':
        return redirect(url_for('seller_dashboard'))
    elif user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('index'))

@app.route('/chat/<int:other_user_id>')
@login_required  
def chat_conversation(other_user_id):
    """Open chat widget with conversation"""
    user = get_current_user()
    
    # Redirect to home page with a script to open chat widget
    if user.role == 'buyer':
        redirect_url = url_for('buyer_home')
    elif user.role == 'seller':
        redirect_url = url_for('seller_dashboard')
    elif user.role == 'rider':
        redirect_url = url_for('rider_dashboard')
    else:
        redirect_url = url_for('index')
    
    # Return HTML that opens the chat widget
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Opening Chat...</title>
    </head>
    <body>
        <script>
            window.location.href = "{redirect_url}";
            setTimeout(function() {{
                if (typeof toggleChatWidget === 'function') {{
                    toggleChatWidget();
                    setTimeout(function() {{
                        if (typeof openConversation === 'function') {{
                            openConversation({other_user_id});
                        }}
                    }}, 300);
                }}
            }}, 100);
        </script>
    </body>
    </html>
    """
    return html_content

@app.route('/chat/api/get-or-create-conversation/<int:other_user_id>')
@login_required
def api_get_or_create_conversation(other_user_id):
    """Get or create conversation and return messages"""
    try:
        user = get_current_user()
        other_user = User.query.get_or_404(other_user_id)
        
        # Find or create conversation
        conversation = Conversation.query.filter(
            db.or_(
                db.and_(
                    Conversation.participant1_id == user.id,
                    Conversation.participant2_id == other_user_id
                ),
                db.and_(
                    Conversation.participant1_id == other_user_id,
                    Conversation.participant2_id == user.id
                )
            )
        ).first()
        
        # Create new conversation if doesn't exist
        if not conversation:
            conversation = Conversation(
                participant1_id=user.id,
                participant2_id=other_user_id
            )
            db.session.add(conversation)
            db.session.commit()
        
        # Get all messages
        messages = Message.query.filter_by(
            conversation_id=conversation.id
        ).order_by(Message.created_at.asc()).all()
        
        # Mark messages as read
        unread_messages = Message.query.filter_by(
            conversation_id=conversation.id,
            receiver_id=user.id,
            is_read=False
        ).all()
        
        for msg in unread_messages:
            msg.mark_as_read()
        
        if unread_messages:
            db.session.commit()
        
        # Check online status
        online_status = UserOnlineStatus.query.filter_by(user_id=other_user_id).first()
        is_online = online_status.is_online if online_status else False
        
        return jsonify({
            'success': True,
            'conversation_id': conversation.id,
            'other_user_name': other_user.business_name or other_user.full_name,
            'is_online': is_online,
            'messages': [{
                'id': msg.id,
                'sender_id': msg.sender_id,
                'message_content': msg.message_content,
                'created_at': msg.created_at.isoformat(),
                'is_read': msg.is_read
            } for msg in messages]
        })
        
    except Exception as e:
        print(f"Error in get_or_create_conversation: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/chat/api/send', methods=['POST'])
@login_required
def api_send_message():
    """API endpoint to send a message"""
    try:
        user = get_current_user()
        data = request.get_json()
        
        conversation_id = data.get('conversation_id')
        message_content = data.get('content') or data.get('message')
        
        if not conversation_id or not message_content:
            return jsonify({'success': False, 'message': 'Missing required fields'})
        
        conversation = Conversation.query.get(conversation_id)
        if not conversation or not conversation.is_participant(user.id):
            return jsonify({'success': False, 'message': 'Invalid conversation'})
        
        # Check if conversation is restricted
        if conversation.is_restricted:
            return jsonify({'success': False, 'message': 'This conversation has been restricted by admin'})
        
        # Get receiver
        receiver = conversation.get_other_participant(user.id)
        
        # Create message
        message = Message(
            conversation_id=conversation_id,
            sender_id=user.id,
            receiver_id=receiver.id,
            message_content=message_content.strip(),
            message_type='text'
        )
        db.session.add(message)
        
        # Update conversation timestamp
        conversation.updated_at = utc_now()
        db.session.commit()
        
        # Create notification for receiver
        # Note: Users should use the floating chat widget to view messages
        create_notification(
            user_id=receiver.id,
            notification_type='system_alert',
            category='chat',
            title=f'New message from {user.username}',
            message=message_content[:100],
            priority='medium',
            action_url=None,  # No URL - use floating chat widget
            action_text='Open Chat',
            data={'conversation_id': conversation_id, 'sender_id': user.id}
        )
        
        # Emit real-time message via SocketIO
        socketio.emit('new_message', message.to_dict(), room=f'user_{receiver.id}')
        
        return jsonify({'success': True, 'message_data': message.to_dict()})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/chat/api/mark-read/<int:conversation_id>', methods=['POST'])
@login_required
def api_mark_conversation_read(conversation_id):
    """Mark all messages in conversation as read"""
    try:
        user = get_current_user()
        conversation = Conversation.query.get_or_404(conversation_id)
        
        if not conversation.is_participant(user.id):
            return jsonify({'success': False, 'message': 'Access denied'})
        
        Message.query.filter_by(
            conversation_id=conversation_id,
            receiver_id=user.id,
            is_read=False
        ).update({'is_read': True, 'read_at': utc_now()})
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/chat/api/online-users')
@login_required
def api_online_users():
    """Get list of online users"""
    online_statuses = UserOnlineStatus.query.filter_by(is_online=True).all()
    online_user_ids = [status.user_id for status in online_statuses]
    
    return jsonify({
        'success': True,
        'online_users': online_user_ids
    })

@app.route('/chat/api/unread-count')
@login_required
def api_unread_message_count():
    """Get unread message count for current user"""
    user = get_current_user()
    
    # Count unread messages where user is the receiver
    unread_count = Message.query.filter(
        Message.receiver_id == user.id,
        Message.is_read == False
    ).count()
    
    return jsonify({
        'success': True,
        'unread_count': unread_count
    })

@app.route('/chat/api/messages/<int:conversation_id>')
@login_required
def api_get_conversation_messages(conversation_id):
    """Get all messages for a specific conversation"""
    try:
        user = get_current_user()
        
        # Verify user is part of this conversation
        conversation = Conversation.query.get_or_404(conversation_id)
        if conversation.participant1_id != user.id and conversation.participant2_id != user.id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        # Get messages
        messages = Message.query.filter_by(conversation_id=conversation_id, is_deleted=False).order_by(Message.created_at.asc()).all()
        
        result = []
        for msg in messages:
            result.append({
                'id': msg.id,
                'content': msg.message_content,
                'sender_id': msg.sender_id,
                'is_sent_by_me': msg.sender_id == user.id,
                'is_read': msg.is_read,
                'created_at': msg.created_at.isoformat()
            })
        
        # Mark messages as read
        Message.query.filter(
            Message.conversation_id == conversation_id,
            Message.receiver_id == user.id,
            Message.is_read == False
        ).update({'is_read': True})
        db.session.commit()
        
        return jsonify({
            'success': True,
            'messages': result
        })
        
    except Exception as e:
        print(f"Error loading messages: {e}")
        return jsonify({
            'success': False,
            'message': str(e),
            'messages': []
        })

@app.route('/chat/api/conversations')
@login_required
def api_get_conversations():
    """Get all conversations for current user with last message and unread count"""
    try:
        user = get_current_user()
        
        # Get all conversations where user is participant
        conversations = Conversation.query.filter(
            db.or_(
                Conversation.participant1_id == user.id,
                Conversation.participant2_id == user.id
            )
        ).order_by(Conversation.updated_at.desc()).all()
        
        result = []
        for conv in conversations:
            # Determine the other user
            other_user = conv.participant2 if conv.participant1_id == user.id else conv.participant1
            
            # Get last message
            last_message = Message.query.filter_by(conversation_id=conv.id).order_by(Message.created_at.desc()).first()
            
            # Count unread messages for current user
            unread_count = Message.query.filter(
                Message.conversation_id == conv.id,
                Message.receiver_id == user.id,
                Message.is_read == False
            ).count()
            
            result.append({
                'conversation_id': conv.id,
                'other_user_id': other_user.id,
                'other_user_name': other_user.full_name,
                'other_user_role': other_user.role,
                'other_user_profile_image': other_user.profile_image,
                'last_message': last_message.message_content if last_message else None,
                'last_message_time': last_message.created_at.isoformat() if last_message else None,
                'unread_count': unread_count,
                'updated_at': conv.updated_at.isoformat()
            })
        
        # Calculate total unread count
        total_unread = sum(conv['unread_count'] for conv in result)
        
        return jsonify({
            'success': True,
            'conversations': result,
            'total_unread': total_unread
        })
        
    except Exception as e:
        print(f"Error loading conversations: {e}")
        return jsonify({
            'success': False,
            'message': str(e),
            'conversations': []
        })

# =====================================================
# ADMIN CHAT MODERATION ROUTES
# =====================================================

@app.route('/admin/chat-logs')
@role_required('admin')
def admin_chat_logs():
    """Admin view of all chat conversations"""
    search_query = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    
    # Build query
    query = Conversation.query
    
    if search_query:
        # Search by participant names
        query = query.join(User, or_(
            Conversation.participant1_id == User.id,
            Conversation.participant2_id == User.id
        )).filter(User.username.ilike(f'%{search_query}%'))
    
    conversations = query.order_by(Conversation.updated_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Get statistics
    stats = {
        'total_conversations': Conversation.query.count(),
        'active_conversations': Conversation.query.filter_by(is_active=True).count(),
        'restricted_conversations': Conversation.query.filter_by(is_restricted=True).count(),
        'total_messages': Message.query.count(),
        'flagged_messages': Message.query.filter_by(is_flagged=True).count()
    }
    
    return render_template('admin/chat_logs.html',
                         conversations=conversations,
                         stats=stats,
                         search_query=search_query)

@app.route('/admin/chat/restrict/<int:conversation_id>', methods=['POST'])
@role_required('admin')
def admin_restrict_conversation(conversation_id):
    """Restrict a conversation"""
    conversation = Conversation.query.get_or_404(conversation_id)
    admin_user = get_current_user()
    
    reason = request.json.get('reason') if request.is_json else request.form.get('reason')
    
    if not reason:
        flash('Restriction reason is required.', 'error')
        return redirect(url_for('admin_chat_logs'))
    
    conversation.is_restricted = True
    conversation.restriction_reason = reason
    conversation.restricted_by = admin_user.id
    conversation.restricted_at = utc_now()
    
    db.session.commit()
    
    # Notify both participants
    for user_id in [conversation.participant1_id, conversation.participant2_id]:
        create_notification(
            user_id=user_id,
            notification_type='admin_action',
            category='system',
            title='Conversation Restricted',
            message=f'Your conversation has been restricted. Reason: {reason}',
            priority='high',
            data={'conversation_id': conversation_id, 'admin_id': admin_user.id}
        )
    
    flash('Conversation restricted successfully.', 'success')
    
    if request.is_json:
        return jsonify({'success': True})
    
    return redirect(url_for('admin_chat_logs'))

@app.route('/admin/chat/unrestrict/<int:conversation_id>', methods=['POST'])
@role_required('admin')
def admin_unrestrict_conversation(conversation_id):
    """Remove restriction from a conversation"""
    conversation = Conversation.query.get_or_404(conversation_id)
    
    conversation.is_restricted = False
    conversation.restriction_reason = None
    
    db.session.commit()
    flash('Conversation restriction removed.', 'success')
    
    if request.is_json:
        return jsonify({'success': True})
    
    return redirect(url_for('admin_chat_logs'))

# =====================================================
# WEBSOCKET EVENT HANDLERS
# =====================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    if 'user_id' in session:
        user_id = session['user_id']
        join_room(f'user_{user_id}')
        
        # Update online status
        online_status = UserOnlineStatus.query.filter_by(user_id=user_id).first()
        if not online_status:
            online_status = UserOnlineStatus(user_id=user_id)
            db.session.add(online_status)
        
        online_status.update_status(is_online=True, socket_id=request.sid)
        
        # Broadcast online status to relevant users
        emit('user_online', {'user_id': user_id}, broadcast=True)
        
        print(f"[WEBSOCKET] User {user_id} connected")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    if 'user_id' in session:
        user_id = session['user_id']
        leave_room(f'user_{user_id}')
        
        # Update online status
        online_status = UserOnlineStatus.query.filter_by(user_id=user_id).first()
        if online_status:
            online_status.update_status(is_online=False)
        
        # Broadcast offline status
        emit('user_offline', {'user_id': user_id}, broadcast=True)
        
        print(f"[WEBSOCKET] User {user_id} disconnected")

@socketio.on('send_message')
def handle_send_message(data):
    """Handle real-time message sending"""
    if 'user_id' not in session:
        return
    
    user_id = session['user_id']
    conversation_id = data.get('conversation_id')
    message_content = data.get('message')
    
    if not conversation_id or not message_content:
        emit('error', {'message': 'Missing required fields'})
        return
    
    try:
        conversation = Conversation.query.get(conversation_id)
        if not conversation or not conversation.is_participant(user_id):
            emit('error', {'message': 'Invalid conversation'})
            return
        
        if conversation.is_restricted:
            emit('error', {'message': 'Conversation is restricted'})
            return
        
        receiver = conversation.get_other_participant(user_id)
        user = User.query.get(user_id)
        
        # Create message
        message = Message(
            conversation_id=conversation_id,
            sender_id=user_id,
            receiver_id=receiver.id,
            message_content=message_content.strip(),
            message_type='text'
        )
        db.session.add(message)
        conversation.updated_at = utc_now()
        db.session.commit()
        
        message_data = message.to_dict()
        
        # Send to receiver
        emit('new_message', message_data, room=f'user_{receiver.id}')
        
        # Confirm to sender
        emit('message_sent', message_data)
        
        # Create notification
        create_notification(
            user_id=receiver.id,
            notification_type='system_alert',
            category='chat',
            title=f'New message from {user.username}',
            message=message_content[:100],
            priority='medium',
            action_url=url_for('chat_conversation', conversation_id=conversation_id),
            action_text='View Message',
            data={'conversation_id': conversation_id, 'sender_id': user_id}
        )
        
    except Exception as e:
        db.session.rollback()
        emit('error', {'message': str(e)})

@socketio.on('typing')
def handle_typing(data):
    """Handle typing indicator"""
    if 'user_id' not in session:
        return
    
    user_id = session['user_id']
    conversation_id = data.get('conversation_id')
    is_typing = data.get('is_typing', False)
    
    try:
        conversation = Conversation.query.get(conversation_id)
        if conversation and conversation.is_participant(user_id):
            receiver = conversation.get_other_participant(user_id)
            emit('user_typing', {
                'user_id': user_id,
                'conversation_id': conversation_id,
                'is_typing': is_typing
            }, room=f'user_{receiver.id}')
    except Exception as e:
        print(f"Typing indicator error: {e}")

@socketio.on('mark_delivered')
def handle_mark_delivered(data):
    """Mark message as delivered"""
    if 'user_id' not in session:
        return
    
    message_id = data.get('message_id')
    
    try:
        message = Message.query.get(message_id)
        if message and message.receiver_id == session['user_id']:
            message.mark_as_delivered()
            emit('message_delivered', {'message_id': message_id}, room=f'user_{message.sender_id}')
    except Exception as e:
        print(f"Mark delivered error: {e}")

# =====================================================
# ENHANCED ADMIN ROUTES - ORDERS & DELIVERY MONITORING
# =====================================================

@app.route('/admin/orders')
@role_required('admin')
def admin_orders():
    """Comprehensive order monitoring with delivery tracking"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    search = request.args.get('search', '')
    per_page = 20
    
    # Get orders from both SQL and Firestore
    from firestore_helper import get_orders_firestore
    
    # Get SQL orders
    query = Order.query
    
    # Apply filters for SQL
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if search:
        query = query.join(User, Order.buyer_id == User.id).filter(
            or_(
                Order.order_number.like(f'%{search}%'),
                User.username.like(f'%{search}%'),
                User.email.like(f'%{search}%')
            )
        )
    
    sql_orders = query.order_by(Order.created_at.desc()).all()
    
    # Get Firestore orders
    firestore_orders = get_orders_firestore(None, 'admin')  # Get all orders
    
    # Filter Firestore orders
    if status_filter != 'all':
        firestore_orders = [o for o in firestore_orders if o.get('status') == status_filter]
    
    if search:
        search_lower = search.lower()
        firestore_orders = [o for o in firestore_orders 
                          if search_lower in o.get('orderNumber', '').lower() 
                          or search_lower in o.get('buyerInfo', {}).get('email', '').lower()
                          or search_lower in o.get('buyerInfo', {}).get('name', '').lower()]
    
    # Normalize Firestore orders for template
    normalized_firestore_orders = [normalize_order_for_template(o) for o in firestore_orders]
    
    # Combine and sort all orders
    all_orders = list(sql_orders) + normalized_firestore_orders
    
    def get_order_time(order):
        dt = getattr(order, 'created_at', None) or getattr(order, 'createdAt', None)
        if dt is None:
            return datetime.min
        if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
            return dt.replace(tzinfo=None)
        return dt
        
    all_orders.sort(key=get_order_time, reverse=True)
    
    # Manual pagination
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_orders = all_orders[start_idx:end_idx]
    
    # Create pagination object
    class SimplePagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None
    
    orders = SimplePagination(paginated_orders, page, per_page, len(all_orders))
    
    # Get statistics (combine SQL and Firestore)
    total_orders = len(all_orders)
    pending_orders = len([o for o in all_orders if (hasattr(o, 'status') and o.status == 'pending') or (hasattr(o, 'status_value') and o.status_value == 'pending')])
    on_delivery = len([o for o in all_orders if (hasattr(o, 'status') and o.status == 'on_delivery') or (hasattr(o, 'status_value') and o.status_value == 'on_delivery')])
    completed_orders = len([o for o in all_orders if (hasattr(o, 'status') and o.status == 'completed') or (hasattr(o, 'status_value') and o.status_value == 'completed')])
    
    # Get available riders
    available_riders = User.query.filter_by(role='rider', is_active=True, approval_status='approved').all()
    
    return render_template('admin/orders.html',
                         orders=orders,
                         total_orders=total_orders,
                         pending_orders=pending_orders,
                         on_delivery=on_delivery,
                         completed_orders=completed_orders,
                         available_riders=available_riders,
                         current_status=status_filter,
                         search=search)

@app.route('/admin/orders/<order_id>')
@role_required('admin')
def admin_order_detail(order_id):
    """View detailed order information"""
    # Check if order exists in SQL
    try:
        sql_order_id = int(order_id)
        order = Order.query.get(sql_order_id)
    except ValueError:
        order = None
    
    if not order:
        from firestore_helper import get_order_firestore
        order = get_order_firestore(str(order_id))
        if not order:
            abort(404)
        # Normalize Firestore order
        order = normalize_order_for_template(order)
    
    rider_assignment = RiderAssignment.query.filter_by(order_id=order_id).first()
    available_riders = User.query.filter_by(role='rider', is_active=True, approval_status='approved').all()
    
    return render_template('admin/order_detail.html',
                         order=order,
                         rider_assignment=rider_assignment,
                         available_riders=available_riders)

@app.route('/admin/orders/<order_id>/assign-rider', methods=['POST'])
@role_required('admin')
def admin_assign_rider(order_id):
    """Assign a rider to an order"""
    order = Order.query.get_or_404(order_id)
    rider_id = request.form.get('rider_id', type=int)
    notes = request.form.get('notes', '')
    
    if not rider_id:
        flash('Please select a rider.', 'error')
        return redirect(url_for('admin_order_detail', order_id=order_id))
    
    rider = User.query.filter_by(id=rider_id, role='rider').first()
    if not rider:
        flash('Invalid rider selected.', 'error')
        return redirect(url_for('admin_order_detail', order_id=order_id))
    
    try:
        # Update order rider
        order.rider_id = rider_id
        
        # Create rider assignment record
        assignment = RiderAssignment(
            rider_id=rider_id,
            order_id=order_id,
            assigned_by=session['user_id'],
            notes=notes
        )
        db.session.add(assignment)
        
        # Create notifications
        create_notification(
            user_id=rider_id,
            notification_type='order_update',
            category='delivery',
            title='New Delivery Assignment',
            message=f'You have been assigned to deliver order #{order.order_number}',
            priority='high',
            action_url=url_for('rider_orders'),
            action_text='View Order'
        )
        
        create_notification(
            user_id=order.buyer_id,
            notification_type='order_update',
            category='delivery',
            title='Rider Assigned',
            message=f'A rider has been assigned to your order #{order.order_number}',
            priority='medium',
            action_url=url_for('buyer_orders'),
            action_text='View Orders'
        )
        
        # Log admin action
        log = AdminAuditLog(
            admin_id=session['user_id'],
            action='assign_rider',
            target_type='order',
            target_id=order_id,
            details=f'Assigned rider {rider.username} (ID: {rider_id}) to order #{order.order_number}'
        )
        db.session.add(log)
        
        db.session.commit()
        flash(f'Rider {rider.username} assigned successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error assigning rider: {str(e)}', 'error')
    
    return redirect(url_for('admin_order_detail', order_id=order_id))

@app.route('/admin/orders/<order_id>/update-status', methods=['POST'])
@role_required('admin')
def admin_update_order_status(order_id):
    """Update order status - Admin can only handle special cases (cancelled, refunded, completed)"""
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    
    # Admin should only handle special cases, not normal order flow
    # Normal flow: Seller manages (confirmed→preparing→for_pickup), Rider manages (picked_up→on_delivery→delivered)
    allowed_statuses = ['cancelled', 'refunded', 'completed']
    
    if new_status not in allowed_statuses:
        flash('Admins can only cancel, refund, or complete orders. Sellers manage order preparation, riders manage delivery.', 'error')
        return redirect(url_for('admin_order_detail', order_id=order_id))
    
    try:
        old_status = order.status
        order.status = new_status
        
        if new_status == 'delivered' and not order.delivered_at:
            order.delivered_at = utc_now()
        
        # Update payment status when order is completed
        if new_status == 'completed':
            order.payment_status = 'paid'
        
        # Create notification
        create_notification(
            user_id=order.buyer_id,
            notification_type='order_update',
            category='order',
            title='Order Status Updated',
            message=f'Your order #{order.order_number} status changed from {old_status} to {new_status}',
            priority='high',
            action_url=url_for('buyer_order_detail', order_id=order.id),
            action_text='View Order'
        )
        
        # Log admin action
        log = AdminAuditLog(
            admin_id=session['user_id'],
            action='update_order_status',
            target_type='order',
            target_id=order_id,
            details=f'Changed status from {old_status} to {new_status}'
        )
        db.session.add(log)
        
        db.session.commit()
        flash('Order status updated successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating order status: {str(e)}', 'error')
    
    return redirect(url_for('admin_order_detail', order_id=order_id))

# =====================================================
# SYSTEM ANNOUNCEMENTS
# =====================================================

@app.route('/admin/announcements')
@role_required('admin')
def admin_announcements():
    """Manage system announcements"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    
    query = SystemAnnouncement.query
    
    if status_filter == 'active':
        query = query.filter_by(is_active=True)
    elif status_filter == 'inactive':
        query = query.filter_by(is_active=False)
    
    announcements = query.order_by(SystemAnnouncement.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/announcements.html',
                         announcements=announcements,
                         current_status=status_filter)

@app.route('/admin/announcements/create', methods=['GET', 'POST'])
@role_required('admin')
def admin_create_announcement():
    """Create new system announcement"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        message = request.form.get('message', '').strip()
        announcement_type = request.form.get('announcement_type')
        target_audience = request.form.get('target_audience', 'all')
        priority = request.form.get('priority', 'medium')
        show_on_dashboard = request.form.get('show_on_dashboard') == 'on'
        show_as_popup = request.form.get('show_as_popup') == 'on'
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        
        if not title or not message:
            flash('Title and message are required.', 'error')
            return render_template('admin/create_announcement.html')
        
        try:
            announcement = SystemAnnouncement(
                admin_id=session['user_id'],
                title=title,
                message=message,
                announcement_type=announcement_type,
                target_audience=target_audience,
                priority=priority,
                show_on_dashboard=show_on_dashboard,
                show_as_popup=show_as_popup
            )
            
            if start_date_str:
                announcement.start_date = datetime.strptime(start_date_str, '%Y-%m-%dT%H:%M')
            
            if end_date_str:
                announcement.end_date = datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M')
            
            db.session.add(announcement)
            
            # Create notifications for target audience
            users_query = User.query.filter_by(is_active=True)
            if target_audience != 'all':
                users_query = users_query.filter_by(role=target_audience)
            
            users = users_query.all()
            for user in users:
                create_notification(
                    user_id=user.id,
                    notification_type='system_alert',
                    category='system',
                    title=title,
                    message=message,
                    priority=priority,
                    data={'announcement_id': announcement.id}
                )
            
            # Log admin action
            log = AdminAuditLog(
                admin_id=session['user_id'],
                action='create_announcement',
                target_type='announcement',
                target_id=announcement.id,
                details=f'Created announcement: {title}'
            )
            db.session.add(log)
            
            db.session.commit()
            flash(f'Announcement created and sent to {len(users)} users!', 'success')
            return redirect(url_for('admin_announcements'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating announcement: {str(e)}', 'error')
    
    return render_template('admin/create_announcement.html')

@app.route('/admin/announcements/<int:announcement_id>/toggle', methods=['POST'])
@role_required('admin')
def admin_toggle_announcement(announcement_id):
    """Toggle announcement active status"""
    announcement = SystemAnnouncement.query.get_or_404(announcement_id)
    
    announcement.is_active = not announcement.is_active
    db.session.commit()
    
    status = 'activated' if announcement.is_active else 'deactivated'
    flash(f'Announcement {status} successfully!', 'success')
    
    return redirect(url_for('admin_announcements'))

@app.route('/admin/announcements/<int:announcement_id>/delete', methods=['POST'])
@role_required('admin')
def admin_delete_announcement(announcement_id):
    """Delete announcement"""
    announcement = SystemAnnouncement.query.get_or_404(announcement_id)
    
    try:
        db.session.delete(announcement)
        db.session.commit()
        flash('Announcement deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting announcement: {str(e)}', 'error')
    
    return redirect(url_for('admin_announcements'))

# =====================================================
# SYSTEM LOGS & AUDIT TRAIL
# =====================================================

@app.route('/admin/logs')
@role_required('admin')
def admin_logs():
    """View system audit logs"""
    page = request.args.get('page', 1, type=int)
    action_filter = request.args.get('action', 'all')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    query = AdminAuditLog.query
    
    if action_filter != 'all':
        query = query.filter_by(action=action_filter)
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(AdminAuditLog.created_at >= from_date)
        except:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d')
            to_date = to_date.replace(hour=23, minute=59, second=59)
            query = query.filter(AdminAuditLog.created_at <= to_date)
        except:
            pass
    
    logs = query.order_by(AdminAuditLog.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    # Get unique actions for filter
    unique_actions = db.session.query(AdminAuditLog.action).distinct().all()
    actions = [action[0] for action in unique_actions]
    
    return render_template('admin/logs.html',
                         logs=logs,
                         actions=actions,
                         current_action=action_filter,
                         date_from=date_from,
                         date_to=date_to)

# =====================================================
# COMMISSION REPORTS WITH EXPORT
# =====================================================

@app.route('/admin/reports/commissions')
@role_required('admin')
def admin_commission_reports():
    """Detailed commission reports"""
    period = request.args.get('period', 'month')
    export_format = request.args.get('export', '')
    
    # Calculate date range
    today = datetime.now()
    if period == 'week':
        start_date = today - timedelta(days=7)
    elif period == 'month':
        start_date = today - timedelta(days=30)
    elif period == 'year':
        start_date = today - timedelta(days=365)
    else:
        start_date = today - timedelta(days=30)
    
    # Get commission data
    commissions = Commission.query.filter(
        Commission.created_at >= start_date
    ).order_by(Commission.created_at.desc()).all()
    
    # Calculate totals
    total_commission = sum(float(c.commission_amount) for c in commissions)
    total_orders = len(set(c.order_id for c in commissions))
    total_sales = sum(float(c.order_amount) for c in commissions)
    
    # Get seller breakdown
    seller_stats = db.session.query(
        User.id, User.username, User.business_name,
        db.func.count(Commission.id).label('order_count'),
        db.func.sum(Commission.order_amount).label('total_sales'),
        db.func.sum(Commission.commission_amount).label('total_commission')
    ).join(Commission, User.id == Commission.seller_id).filter(
        Commission.created_at >= start_date
    ).group_by(User.id).all()
    
    # Export functionality
    if export_format == 'csv':
        return export_commission_csv(commissions, seller_stats, period)
    elif export_format == 'pdf':
        return export_commission_pdf(commissions, seller_stats, period)
    
    return render_template('admin/commission_reports.html',
                         commissions=commissions,
                         seller_stats=seller_stats,
                         total_commission=total_commission,
                         total_orders=total_orders,
                         total_sales=total_sales,
                         period=period,
                         start_date=start_date)

def export_commission_csv(commissions, seller_stats, period):
    """Export commission data as CSV"""
    import csv
    from io import StringIO
    from flask import make_response
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(['Order ID', 'Seller', 'Order Amount', 'Commission Rate', 'Commission Amount', 'Status', 'Date'])
    
    # Write data
    for comm in commissions:
        writer.writerow([
            comm.order_id,
            comm.seller.username if comm.seller else 'N/A',
            float(comm.order_amount),
            float(comm.commission_rate),
            float(comm.commission_amount),
            comm.status,
            comm.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    # Create response
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=commissions_{period}_{datetime.now().strftime("%Y%m%d")}.csv'
    
    return response

def export_commission_pdf(commissions, seller_stats, period):
    """Export commission data as PDF (placeholder)"""
    flash('PDF export coming soon!', 'info')
    return redirect(url_for('admin_commission_reports'))

# =====================================================
# BACKUP & RESTORE
# =====================================================

@app.route('/admin/backup')
@role_required('admin')
def admin_backup():
    """Database backup management"""
    backups = DatabaseBackup.query.order_by(DatabaseBackup.created_at.desc()).all()
    
    return render_template('admin/backup.html', backups=backups)

@app.route('/admin/backup/create', methods=['POST'])
@role_required('admin')
def admin_create_backup():
    """Create database backup"""
    try:
        # Create backup directory if not exists
        backup_dir = os.path.join(BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Generate backup filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'gym_store_backup_{timestamp}.sql'
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Create backup record
        backup = DatabaseBackup(
            admin_id=session['user_id'],
            backup_type='manual',
            file_path=backup_path,
            status='in_progress'
        )
        db.session.add(backup)
        db.session.commit()
        
        # Perform backup (MySQL)
        if 'mysql' in app.config['SQLALCHEMY_DATABASE_URI']:
            import subprocess
            db_config = DATABASE_CONFIG['mysql']
            
            cmd = [
                'mysqldump',
                '-h', db_config['host'],
                '-u', db_config['user'],
                f'-p{db_config["password"]}' if db_config['password'] else '--skip-password',
                db_config['database']
            ]
            
            with open(backup_path, 'w') as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
            
            if result.returncode == 0:
                # Get file size
                backup.file_size = os.path.getsize(backup_path)
                backup.status = 'completed'
                db.session.commit()
                
                # Log action
                log = AdminAuditLog(
                    admin_id=session['user_id'],
                    action='create_backup',
                    target_type='database',
                    target_id=backup.id,
                    details=f'Manual backup created: {backup_filename}'
                )
                db.session.add(log)
                db.session.commit()
                
                flash('Database backup created successfully!', 'success')
            else:
                backup.status = 'failed'
                backup.error_message = result.stderr
                db.session.commit()
                flash(f'Backup failed: {result.stderr}', 'error')
        else:
            # SQLite backup
            import shutil
            sqlite_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
            shutil.copy2(sqlite_path, backup_path)
            
            backup.file_size = os.path.getsize(backup_path)
            backup.status = 'completed'
            db.session.commit()
            
            flash('Database backup created successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating backup: {str(e)}', 'error')
    
    return redirect(url_for('admin_backup'))

# =====================================================
# API ENDPOINTS FOR CHARTS & REAL-TIME DATA
# =====================================================

@app.route('/api/admin/dashboard/stats')
@role_required('admin')
def api_admin_dashboard_stats():
    """Real-time dashboard statistics API"""
    stats = {
        'total_users': User.query.count(),
        'pending_approvals': User.query.filter_by(approval_status='pending').count(),
        'total_orders': Order.query.count(),
        'pending_orders': Order.query.filter_by(status='pending').count(),
        'total_products': Product.query.count(),
        'pending_products': Product.query.filter_by(approval_status='pending').count(),
        'open_complaints': Complaint.query.filter_by(status='open').count(),
        'total_revenue': float(db.session.query(db.func.sum(Order.total_amount)).filter(
            Order.status.in_(['completed', 'delivered'])
        ).scalar() or 0),
        'total_commission': float(db.session.query(db.func.sum(Commission.commission_amount)).scalar() or 0)
    }
    
    return jsonify(stats)

@app.route('/api/admin/charts/revenue')
@role_required('admin')
def api_admin_revenue_chart():
    """Revenue chart data"""
    period = request.args.get('period', 'week')
    
    if period == 'week':
        days = 7
    elif period == 'month':
        days = 30
    elif period == 'year':
        days = 365
    else:
        days = 7
    
    start_date = datetime.now() - timedelta(days=days)
    
    # Get daily revenue
    revenue_data = db.session.query(
        db.func.date(Order.created_at).label('date'),
        db.func.sum(Order.total_amount).label('revenue')
    ).filter(
        Order.created_at >= start_date,
        Order.status.in_(['completed', 'delivered'])
    ).group_by(db.func.date(Order.created_at)).all()
    
    labels = [str(item.date) for item in revenue_data]
    data = [float(item.revenue) for item in revenue_data]
    
    return jsonify({
        'labels': labels,
        'data': data
    })

@app.route('/api/admin/charts/user-growth')
@role_required('admin')
def api_admin_user_growth_chart():
    """User growth chart data"""
    period = request.args.get('period', 'month')
    
    if period == 'month':
        days = 30
    elif period == 'year':
        days = 365
    else:
        days = 30
    
    start_date = datetime.now() - timedelta(days=days)
    
    # Get daily user registrations
    user_data = db.session.query(
        db.func.date(User.created_at).label('date'),
        db.func.count(User.id).label('count')
    ).filter(
        User.created_at >= start_date
    ).group_by(db.func.date(User.created_at)).all()
    
    labels = [str(item.date) for item in user_data]
    data = [item.count for item in user_data]
    
    return jsonify({
        'labels': labels,
        'data': data
    })

# =====================================================
# USER PREFERENCES & THEME
# =====================================================

@app.route('/api/user/preferences', methods=['GET', 'POST'])
def api_user_preferences():
    """Get or update user preferences"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    
    if request.method == 'POST':
        data = request.get_json()
        theme = data.get('theme', 'light')
        
        preference = UserPreference.query.filter_by(user_id=user_id).first()
        if not preference:
            preference = UserPreference(user_id=user_id)
            db.session.add(preference)
        
        preference.theme = theme
        db.session.commit()
        
        return jsonify({'success': True, 'theme': theme})
    
    else:
        preference = UserPreference.query.filter_by(user_id=user_id).first()
        if not preference:
            return jsonify({'theme': 'light'})
        
        return jsonify({'theme': preference.theme})

# =====================================================
# ORDER CANCELLATION API
# =====================================================

@app.route('/api/orders/<order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    """Cancel an order (only for pending/confirmed status)"""
    try:
        user = get_current_user()
        
        # Try SQL first
        try:
            sql_order_id = int(order_id)
            order = Order.query.get_or_404(sql_order_id)
        except ValueError:
            from flask import abort
            abort(404)
        
        # Get cancellation reason from request
        data = request.get_json() or {}
        cancel_reason = data.get('reason', '').strip()
        
        # Check if order belongs to user
        # Try both user_id and buyer_id as field names
        order_user_id = getattr(order, 'user_id', None) or getattr(order, 'buyer_id', None)
        if order_user_id != user.id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        # Check if order can be cancelled
        if order.status not in ['pending', 'confirmed']:
            return jsonify({'success': False, 'message': f'Cannot cancel order with status: {order.status}'}), 400
        
        # Update order status
        order.status = 'cancelled'
        order.updated_at = manila_now_naive()
        
        # Get seller from order items
        seller_ids = set()
        for item in order.order_items:
            if item.product and item.product.seller_id:
                seller_ids.add(item.product.seller_id)
        
        # Store cancellation reason if provided
        if cancel_reason:
            order.cancellation_reason = cancel_reason
        
        # Send notification and automatic chat message to each seller
        for seller_id in seller_ids:
            try:
                # Build cancellation message
                notif_message = f'Buyer {user.full_name} cancelled order {order.order_number}. Total: ₱{order.total_amount:.2f}'
                if cancel_reason:
                    notif_message += f'. Reason: {cancel_reason}'
                
                # Create notification for seller
                notification = Notification(
                    user_id=seller_id,
                    notification_type='order_update',
                    title='Order Cancelled',
                    message=notif_message,
                    action_url=url_for('seller_order_detail', order_id=order.id),
                    created_at=manila_now_naive()
                )
                db.session.add(notification)
                
                # Send automatic chat message to seller
                chat_message = f"Hello! I've cancelled my order #{order.order_number}."
                if cancel_reason:
                    chat_message += f" Reason: {cancel_reason}"
                else:
                    chat_message += " I apologize for any inconvenience."
                
                # Use send_automatic_message function
                send_automatic_message(
                    sender_id=user.id,
                    receiver_id=seller_id,
                    message_content=chat_message,
                    order_id=order.id
                )
                
            except Exception as e:
                print(f"Error sending notification/message to seller {seller_id}: {e}")
                # Continue even if notification fails
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Order cancelled successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error cancelling order: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

# =====================================================
# SEARCH API ENDPOINTS
# =====================================================

@app.route('/api/search/categories')
def api_search_categories():
    """Get all categories with product counts for search suggestions"""
    try:
        categories = db.session.query(
            Category.name,
            func.count(Product.id).label('product_count')
        ).join(Product).filter(
            Product.approval_status == 'approved',
            Product.stock_quantity > 0
        ).group_by(Category.name).order_by(func.count(Product.id).desc()).limit(10).all()
        
        category_list = []
        for cat in categories:
            category_list.append({
                'name': cat.name,
                'product_count': cat.product_count
            })
        
        return jsonify({'categories': category_list})
    except Exception as e:
        print(f"Error fetching categories: {e}")
        return jsonify({'categories': []})



# =====================================================
# ERROR HANDLERS
# =====================================================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    import traceback
    traceback.print_exc()
    db.session.rollback()
    return render_template('errors/500.html'), 500

# ==================== APPLICATION INITIALIZATION ====================

if __name__ == '__main__':
    print("\n" + "="*50)
    print("GYM STORE - E-COMMERCE WEBSITE")
    print("="*50)
    
    # Initialize database
    try:
        init_db()
        seed_database()
        print("[OK] Database initialized successfully!")
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}")
        print("Please check your database configuration and ensure MySQL is running.")
        print("Update the DATABASE_CONFIG in app.py with your MySQL credentials.")
    
    # Check if SSL certificates exist
    import os
    cert_file = "localhost.crt"
    key_file = "localhost.key"
    
    if os.path.exists(cert_file) and os.path.exists(key_file):
        print("[SERVER] Running with HTTPS at: https://localhost:5000")
        print("[CHAT] WebSocket enabled")
        print("="*50)
        print("WARNING: Browser will show a security warning - click 'Advanced' then 'Proceed to localhost'")
        print("="*50)
        
        # Run with HTTPS
        socketio.run(
            app, 
            debug=True, 
            host='0.0.0.0', 
            port=5000, 
            allow_unsafe_werkzeug=True,
            ssl_context=(cert_file, key_file)
        )
    else:
        print("[SERVER] Running at: http://localhost:5000")
        print("[CHAT] WebSocket enabled")
        print("[WARNING] HTTPS certificates not found - Facebook OAuth may not work")
        print("[INFO] Run 'python generate_cert.py' to generate certificates")
        print("="*50)
        
        socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)

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
        
        # Get unread notifications count
        unread_notifications = Notification.query.filter_by(
            user_id=user.id,
            is_read=False
        ).count()
        
        return render_template('seller/analytics.html',
                             monthly_revenue=monthly_revenue,
                             total_orders=total_orders,
                             total_products=total_products,
                             category_stats=category_stats_list,
                             current_user=user,
                             unread_notifications=unread_notifications)
                             
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


# =====================================================
# ADMIN ANALYTICS ROUTES
# =====================================================

@app.route('/admin/analytics/realtime-data')
@login_required
def admin_analytics_realtime_data():
    """Provide real-time analytics data for admin (all platform orders)"""
    user = get_current_user()
    
    if user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    try:
        # Get all orders from last 30 days
        orders_per_day = []
        for i in range(30):
            day_start = manila_now_naive() - timedelta(days=29-i)
            day_start = day_start.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            # Count all orders on this day
            order_count = Order.query.filter(
                Order.created_at >= day_start,
                Order.created_at < day_end
            ).count()
            
            orders_per_day.append(order_count)
        
        return jsonify({
            'success': True,
            'orders_per_day': orders_per_day,
            'last_updated': manila_now_naive().strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        print(f"Error fetching admin real-time analytics: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# =====================================================
# RIDER MAP ROUTES
# =====================================================

# =====================================================
# CHAT API ENDPOINTS
# =====================================================

@app.route('/api/chat/send-product-inquiry', methods=['POST'])
def send_product_inquiry():
    """Send automatic product inquiry message to seller"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login first'}), 401
    
    try:
        data = request.get_json()
        seller_id = data.get('seller_id')
        product_id = data.get('product_id')
        product_name = data.get('product_name')
        buyer_id = session['user_id']
        
        # Validate inputs
        if not seller_id or not product_id:
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        # Check if seller exists
        seller = User.query.get(seller_id)
        if not seller:
            return jsonify({'success': False, 'message': 'Seller not found'}), 404
        
        # Check if product exists
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'success': False, 'message': 'Product not found'}), 404
        
        # Check if conversation already exists
        existing_conversation = Conversation.query.filter(
            db.or_(
                db.and_(Conversation.participant1_id == buyer_id, Conversation.participant2_id == seller_id),
                db.and_(Conversation.participant1_id == seller_id, Conversation.participant2_id == buyer_id)
            )
        ).first()
        
        if existing_conversation:
            conversation = existing_conversation
        else:
            # Create new conversation
            conversation = Conversation(
                participant1_id=buyer_id,
                participant2_id=seller_id,
                product_id=product_id
            )
            db.session.add(conversation)
            db.session.flush()
        
        # Create automatic intro message
        message_content = f"Hi! I'm interested in your product: {product_name}"
        
        message = Message(
            conversation_id=conversation.id,
            sender_id=buyer_id,
            receiver_id=seller_id,
            message_content=message_content,
            message_type='text'
        )
        db.session.add(message)
        
        # Update conversation timestamp
        conversation.updated_at = utc_now()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Message sent successfully',
            'conversation_id': conversation.id
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error sending product inquiry: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Failed to send message'}), 500


# =====================================================
# RIDER API ENDPOINTS
# =====================================================

@app.route('/rider/api/active-deliveries', methods=['GET'])
def rider_active_deliveries_api():
    """Get active deliveries for the logged-in rider"""
    try:
        # Check authentication
        if 'user_id' not in session:
            print("[DEBUG] No user_id in session")
            return jsonify({'success': False, 'message': 'Not logged in', 'deliveries': []}), 401
        
        if session.get('role') != 'rider':
            print(f"[DEBUG] User role is {session.get('role')}, not rider")
            return jsonify({'success': False, 'message': 'Not a rider', 'deliveries': []}), 401
        
        rider_id = session['user_id']
        print(f"[DEBUG] Fetching deliveries for rider ID: {rider_id}")
        
        # Get ALL orders assigned to this rider (for debugging)
        all_orders = Order.query.filter(Order.rider_id == rider_id).all()
        print(f"[DEBUG] Rider {rider_id} has {len(all_orders)} total orders assigned")
        
        if all_orders:
            for o in all_orders:
                print(f"[DEBUG] Order {o.order_number}: status={o.status}, rider_id={o.rider_id}")
        
        # Get orders assigned to this rider that are in active delivery statuses
        orders = Order.query.filter(
            Order.rider_id == rider_id,
            Order.status.in_(['confirmed', 'preparing', 'for_pickup', 'picked_up', 'on_delivery'])
        ).order_by(Order.created_at.desc()).all()
        
        print(f"[DEBUG] Found {len(orders)} active deliveries")
        
        deliveries = []
        for order in orders:
            try:
                # Get buyer info
                buyer = User.query.get(order.buyer_id)
                
                # Count items
                item_count = OrderItem.query.filter_by(order_id=order.id).count()
                
                delivery_data = {
                    'id': order.id,
                    'order_number': order.order_number,
                    'status': order.status,
                    'buyer_name': buyer.full_name if buyer else 'Unknown',
                    'buyer_phone': buyer.phone if buyer else None,
                    'address': order.shipping_address,
                    'latitude': float(order.delivery_latitude) if order.delivery_latitude else 14.5995,
                    'longitude': float(order.delivery_longitude) if order.delivery_longitude else 120.9842,
                    'item_count': item_count,
                    'total_amount': float(order.total_amount)
                }
                deliveries.append(delivery_data)
                print(f"[DEBUG] Added delivery: Order {order.order_number}")
            except Exception as e:
                print(f"[DEBUG] Error processing order {order.id}: {e}")
                continue
        
        print(f"[DEBUG] Returning {len(deliveries)} deliveries")
        return jsonify({
            'success': True,
            'deliveries': deliveries
        })
        
    except Exception as e:
        print(f"[ERROR] Exception in active-deliveries API: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e), 'deliveries': []}), 500

