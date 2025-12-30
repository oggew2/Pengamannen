"""
User storage service for persistent data management.
"""
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from models.user_storage import UserProfile, UserPortfolio, AvanzaImport, UserSession

class UserStorageService:
    """Service for managing user persistent storage."""
    
    @staticmethod
    def create_user_profile(db: Session, name: str, email: str = None) -> str:
        """Create a new user profile and return user_id."""
        user_id = str(uuid.uuid4())
        
        profile = UserProfile(
            user_id=user_id,
            name=name,
            email=email,
            preferences=json.dumps({
                "default_region": "sweden",
                "default_market_cap": "large",
                "preferred_sync_method": "ultimate",
                "theme": "light"
            })
        )
        
        db.add(profile)
        db.commit()
        db.refresh(profile)
        
        return user_id
    
    @staticmethod
    def get_user_profile(db: Session, user_id: str) -> Optional[Dict]:
        """Get user profile by user_id."""
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            return None
        
        return {
            "user_id": profile.user_id,
            "name": profile.name,
            "email": profile.email,
            "created_at": profile.created_at,
            "preferences": json.loads(profile.preferences) if profile.preferences else {}
        }
    
    @staticmethod
    def save_avanza_import(db: Session, user_id: str, filename: str, 
                          transactions_count: int, holdings_data: Dict, raw_data: str) -> int:
        """Save Avanza CSV import data."""
        import_record = AvanzaImport(
            user_id=user_id,
            filename=filename,
            transactions_count=transactions_count,
            holdings_data=json.dumps(holdings_data),
            raw_data=raw_data
        )
        
        db.add(import_record)
        db.commit()
        db.refresh(import_record)
        
        return import_record.id
    
    @staticmethod
    def get_user_avanza_imports(db: Session, user_id: str) -> List[Dict]:
        """Get all Avanza imports for a user."""
        imports = db.query(AvanzaImport).filter(
            AvanzaImport.user_id == user_id,
            AvanzaImport.status == "active"
        ).order_by(AvanzaImport.import_date.desc()).all()
        
        return [
            {
                "id": imp.id,
                "filename": imp.filename,
                "import_date": imp.import_date,
                "transactions_count": imp.transactions_count,
                "holdings": json.loads(imp.holdings_data) if imp.holdings_data else {}
            }
            for imp in imports
        ]
    
    @staticmethod
    def save_user_portfolio(db: Session, user_id: str, name: str, 
                           description: str, holdings: Dict) -> int:
        """Save user portfolio."""
        portfolio = UserPortfolio(
            user_id=user_id,
            name=name,
            description=description,
            holdings=json.dumps(holdings)
        )
        
        db.add(portfolio)
        db.commit()
        db.refresh(portfolio)
        
        return portfolio.id
    
    @staticmethod
    def get_user_portfolios(db: Session, user_id: str) -> List[Dict]:
        """Get all portfolios for a user."""
        portfolios = db.query(UserPortfolio).filter(
            UserPortfolio.user_id == user_id,
            UserPortfolio.is_active == True
        ).order_by(UserPortfolio.updated_at.desc()).all()
        
        return [
            {
                "id": portfolio.id,
                "name": portfolio.name,
                "description": portfolio.description,
                "holdings": json.loads(portfolio.holdings) if portfolio.holdings else {},
                "created_at": portfolio.created_at,
                "updated_at": portfolio.updated_at
            }
            for portfolio in portfolios
        ]
    
    @staticmethod
    def create_session(db: Session, user_id: str, session_data: Dict) -> str:
        """Create a user session."""
        session = UserSession(
            user_id=user_id,
            session_data=json.dumps(session_data),
            expires_at=datetime.utcnow() + timedelta(days=30)  # 30 day sessions
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        return str(session.id)
    
    @staticmethod
    def get_session(db: Session, session_id: str) -> Optional[Dict]:
        """Get session data."""
        session = db.query(UserSession).filter(
            UserSession.id == int(session_id),
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).first()
        
        if not session:
            return None
        
        return {
            "user_id": session.user_id,
            "session_data": json.loads(session.session_data) if session.session_data else {},
            "created_at": session.created_at,
            "expires_at": session.expires_at
        }
