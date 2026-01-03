#!/usr/bin/env python3
"""Add auth columns to users table."""
import sqlite3

conn = sqlite3.connect('backend/app.db')
cur = conn.cursor()

# Add new columns if they don't exist
try:
    cur.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0")
    print("Added is_admin column")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("is_admin column already exists")
    else:
        raise

try:
    cur.execute("ALTER TABLE users ADD COLUMN invited_by INTEGER")
    print("Added invited_by column")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("invited_by column already exists")
    else:
        raise

try:
    cur.execute("ALTER TABLE users ADD COLUMN invite_code TEXT")
    print("Added invite_code column")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("invite_code column already exists")
    else:
        raise

conn.commit()
conn.close()
print("Migration complete!")
