#!/usr/bin/env python3
"""Create admin user for Börslabbet app."""
import sys
sys.path.insert(0, '/app')

from db import SessionLocal
from services.auth import create_admin_user

def main():
    email = sys.argv[1] if len(sys.argv) > 1 else "admin@borslabbet.local"
    password = sys.argv[2] if len(sys.argv) > 2 else "admin123"
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
