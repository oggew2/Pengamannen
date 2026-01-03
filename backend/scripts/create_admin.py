#!/usr/bin/env python3
"""Create admin user for Börslabbet app."""
import sys
sys.path.insert(0, '/app')

from db import SessionLocal
from services.auth import create_admin_user

def main():
    if len(sys.argv) < 3:
        print("Usage: python create_admin.py <email> <password> [name]")
        print("Example: python create_admin.py admin@example.com MySecurePass123 Admin")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    name = sys.argv[3] if len(sys.argv) > 3 else "Admin"
    
    db = SessionLocal()
    try:
        user = create_admin_user(db, email, password, name)
        print(f"✅ Admin user created/updated:")
        print(f"   Email: {user.email}")
        print(f"   Name: {user.name}")
        print(f"   Invite code: {user.invite_code}")
        print(f"\nShare this invite code with others to let them register.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
