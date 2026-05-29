import os, sys
sys.path.insert(0, os.getcwd())
from app import app
from app import User

with app.app_context():
    sellers = User.query.filter_by(role='seller').all()
    for s in sellers:
        print(f"Seller SQL ID: {s.id}, Username: {s.username}, Firebase UID: {s.firebase_uid}")
