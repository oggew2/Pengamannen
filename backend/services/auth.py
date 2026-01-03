"""Authentication service with httpOnly cookies and invite system."""
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, Depends, Request, Response
from fastapi.responses import JSONResponse
from models import User, UserSession
from db import get_db

COOKIE_NAME = "session_token"
COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days


def register_user(db: Session, email: str, password: str, invite_code: str, name: str = None) -> User:
    """Register a new user with invite code."""
    if not email or not email.strip():
        raise HTTPException(status_code=400, detail="Email is required")
    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if not invite_code:
        raise HTTPException(status_code=400, detail="Invite code is required")
    
    email = email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Validate invite code
    inviter = db.query(User).filter(User.invite_code == invite_code).first()
    if not inviter:
        raise HTTPException(status_code=400, detail="Invalid invite code")
    
    user = User(
        email=email,
        password_hash=User.hash_password(password),
        name=name or email.split('@')[0],
        invited_by=inviter.id,
        invite_code=User.generate_invite_code()  # New user gets their own invite code
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_admin_user(db: Session, email: str, password: str, name: str = None) -> User:
    """Create admin user (no invite required)."""
    if not email or not email.strip():
        raise HTTPException(status_code=400, detail="Email is required")
    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    email = email.strip().lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        # Update to admin if exists
        existing.is_admin = True
        existing.password_hash = User.hash_password(password)
        db.commit()
        return existing
    
    user = User(
        email=email,
        password_hash=User.hash_password(password),
        name=name or email.split('@')[0],
        is_admin=True,
        invite_code=User.generate_invite_code()
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login_user(db: Session, email: str, password: str) -> tuple[dict, str]:
    """Login and return user info + session token."""
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
    
    user_info = {
        "user_id": user.id,
        "email": user.email,
        "name": user.name,
        "is_admin": user.is_admin,
        "invite_code": user.invite_code
    }
    return user_info, session.token


def logout_user(db: Session, token: str):
    """Invalidate session token."""
    db.query(UserSession).filter(UserSession.token == token).delete()
    db.commit()


def get_user_from_cookie(request: Request, db: Session) -> Optional[User]:
    """Get user from httpOnly cookie."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    
    session = db.query(UserSession).filter(
        UserSession.token == token,
        UserSession.expires_at > datetime.now()
    ).first()
    
    if not session:
        return None
    
    return db.query(User).filter(User.id == session.user_id).first()


def require_auth(request: Request, db: Session = Depends(get_db)) -> User:
    """Require authentication - raises 401 if not authenticated."""
    user = get_user_from_cookie(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_admin(request: Request, db: Session = Depends(get_db)) -> User:
    """Require admin authentication."""
    user = require_auth(request, db)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def set_auth_cookie(response: Response, token: str):
    """Set httpOnly session cookie."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False  # Set True in production with HTTPS
    )


def clear_auth_cookie(response: Response):
    """Clear session cookie."""
    response.delete_cookie(key=COOKIE_NAME)
