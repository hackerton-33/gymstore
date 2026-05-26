"""
Quick script to create/reset admin user with proper password hash
Run this: python create_admin.py
"""
from werkzeug.security import generate_password_hash
import pymysql

# Database config
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '',  # Your MySQL password
    'database': 'gym_store_db',
    'charset': 'utf8mb4'
}

# Admin credentials
USERNAME = 'admin'
EMAIL = 'admin@gymstore.com'
PASSWORD = 'admin123'
FIRST_NAME = 'Admin'
LAST_NAME = 'User'

# Generate proper password hash
password_hash = generate_password_hash(PASSWORD)

print("=" * 60)
print("CREATING ADMIN USER")
print("=" * 60)
print(f"Username: {USERNAME}")
print(f"Email: {EMAIL}")
print(f"Password: {PASSWORD}")
print(f"Hash: {password_hash}")
print("=" * 60)

try:
    # Connect to database
    connection = pymysql.connect(**DB_CONFIG)
    cursor = connection.cursor()
    
    # Delete existing admin
    cursor.execute("DELETE FROM users WHERE username = %s OR email = %s", (USERNAME, EMAIL))
    print(f"✓ Deleted existing admin user (if any)")
    
    # Insert new admin
    sql = """
    INSERT INTO users (
        username, email, password_hash, first_name, last_name,
        role, is_active, email_verified, approval_status
    ) VALUES (
        %s, %s, %s, %s, %s, 'admin', TRUE, TRUE, 'approved'
    )
    """
    
    cursor.execute(sql, (USERNAME, EMAIL, password_hash, FIRST_NAME, LAST_NAME))
    connection.commit()
    
    print(f"✓ Admin user created successfully!")
    print("\n" + "=" * 60)
    print("LOGIN CREDENTIALS:")
    print("=" * 60)
    print(f"Username: {USERNAME}")
    print(f"Password: {PASSWORD}")
    print("=" * 60)
    
    cursor.close()
    connection.close()
    
except Exception as e:
    print(f"✗ Error: {e}")
    print("\nMake sure:")
    print("1. MySQL is running")
    print("2. Database 'gym_store_db' exists")
    print("3. Update DB_CONFIG password if needed")
