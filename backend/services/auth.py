"""Authentication service for multi-user support."""
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, Depends, Header
from models import User, UserSession
from db import get_db

def register_user(db: Session, email: str, password: str, name: str = None) -> User:
    """Register a new user."""
    # Validate inputs
    if not email or not email.strip():
        raise HTTPException(status_code=400, detail="Email is required")
    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    email = email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = User(
        email=email,
        password_hash=User.hash_password(password),
        name=name or email.split('@')[0]
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def login_user(db: Session, email: str, password: str) -> dict:
    """Login and return session token."""
    if not email or not password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.verify_password(password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account disabled")
    
    # Create session
    session = UserSession(
        user_id=user.id,
        token=UserSession.generate_token(),
        expires_at=datetime.now() + timedelta(days=30)
    )
    db.add(session)
    db.commit()
    
    return {"token": session.token, "user_id": user.id, "email": user.email, "name": user.name}

def logout_user(db: Session, token: str):
    """Invalidate session token."""
    db.query(UserSession).filter(UserSession.token == token).delete()
    db.commit()

def get_current_user(db: Session = Depends(get_db), authorization: str = Header(None)) -> Optional[User]:
    """Get current user from token. Returns None if no auth (allows anonymous access)."""
    if not authorization:
        return None
    
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    session = db.query(UserSession).filter(
        UserSession.token == token,
        UserSession.expires_at > datetime.now()
    ).first()
    
    if not session:
        return None
    
    return db.query(User).filter(User.id == session.user_id).first()

def require_auth(db: Session = Depends(get_db), authorization: str = Header(...)) -> User:
    """Require authentication - raises 401 if not authenticated."""
    user = get_current_user(db, authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user

def update_user_market_filter(db: Session, user: User, market_filter: str) -> User:
    """Update user's market filter preference."""
    if market_filter not in ["stockholmsborsen", "first_north", "both"]:
        raise HTTPException(status_code=400, detail="Invalid market filter")
    user.market_filter = market_filter
    db.commit()
    return user
