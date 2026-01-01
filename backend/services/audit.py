"""Audit logging for sensitive operations."""
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

logger = logging.getLogger("audit")
logger.setLevel(logging.INFO)

# File handler for audit logs
handler = logging.FileHandler("audit.log")
handler.setFormatter(logging.Formatter("%(asctime)s|%(levelname)s|%(message)s"))
logger.addHandler(handler)


def log_auth(action: str, user_id: Optional[int], email: str, success: bool, ip: str = None):
    """Log authentication events."""
    status = "SUCCESS" if success else "FAILED"
    logger.info(f"AUTH|{action}|{status}|user_id={user_id}|email={email}|ip={ip}")


def log_data_sync(action: str, details: str, user_id: Optional[int] = None):
    """Log data sync operations."""
    logger.info(f"SYNC|{action}|user_id={user_id}|{details}")


def log_portfolio(action: str, user_id: int, details: str):
    """Log portfolio changes."""
    logger.info(f"PORTFOLIO|{action}|user_id={user_id}|{details}")


def log_admin(action: str, user_id: int, details: str):
    """Log admin operations."""
    logger.warning(f"ADMIN|{action}|user_id={user_id}|{details}")
