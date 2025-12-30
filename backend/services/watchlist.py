"""Watchlist service - track stocks and alert on ranking changes."""
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from models import Watchlist, WatchlistItem, StrategySignal


def create_watchlist(db: Session, name: str = "Default") -> int:
    """Create a new watchlist."""
    watchlist = Watchlist(name=name)
    db.add(watchlist)
    db.commit()
    return watchlist.id


def add_to_watchlist(
    db: Session,
    watchlist_id: int,
    ticker: str,
    notes: str = None,
    alert_on_ranking_change: bool = True
) -> int:
    """Add a stock to watchlist."""
    # Check if already exists
    existing = db.query(WatchlistItem).filter(
        WatchlistItem.watchlist_id == watchlist_id,
        WatchlistItem.ticker == ticker
    ).first()
    
    if existing:
        return existing.id
    
    item = WatchlistItem(
        watchlist_id=watchlist_id,
        ticker=ticker,
        notes=notes,
        alert_on_ranking_change=1 if alert_on_ranking_change else 0
    )
    db.add(item)
    db.commit()
    return item.id


def remove_from_watchlist(db: Session, watchlist_id: int, ticker: str) -> bool:
    """Remove a stock from watchlist."""
    item = db.query(WatchlistItem).filter(
        WatchlistItem.watchlist_id == watchlist_id,
        WatchlistItem.ticker == ticker
    ).first()
    
    if item:
        db.delete(item)
        db.commit()
        return True
    return False


def get_watchlist(db: Session, watchlist_id: int) -> Dict:
    """Get watchlist with items and current rankings."""
    watchlist = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
    if not watchlist:
        return {"error": "Watchlist not found"}
    
    items = db.query(WatchlistItem).filter(
        WatchlistItem.watchlist_id == watchlist_id
    ).all()
    
    # Get current rankings for each stock
    result_items = []
    for item in items:
        rankings = db.query(StrategySignal).filter(
            StrategySignal.ticker == item.ticker
        ).order_by(StrategySignal.calculated_date.desc()).all()
        
        current_rankings = {}
        for r in rankings:
            if r.strategy_name not in current_rankings:
                current_rankings[r.strategy_name] = {
                    "rank": r.rank,
                    "score": r.score,
                    "date": r.calculated_date.isoformat() if r.calculated_date else None
                }
        
        result_items.append({
            "ticker": item.ticker,
            "added_at": item.added_at.isoformat() if item.added_at else None,
            "notes": item.notes,
            "alert_enabled": item.alert_on_ranking_change == 1,
            "rankings": current_rankings
        })
    
    return {
        "id": watchlist.id,
        "name": watchlist.name,
        "items": result_items,
        "count": len(result_items)
    }


def check_ranking_changes(
    db: Session,
    watchlist_id: int,
    strategy_name: str,
    threshold_enter: int = 10,
    threshold_exit: int = 20
) -> List[Dict]:
    """
    Check for stocks entering or exiting top rankings.
    
    Args:
        threshold_enter: Alert when stock enters top N
        threshold_exit: Alert when stock exits top N
    """
    items = db.query(WatchlistItem).filter(
        WatchlistItem.watchlist_id == watchlist_id,
        WatchlistItem.alert_on_ranking_change == 1
    ).all()
    
    alerts = []
    
    for item in items:
        # Get last two rankings
        rankings = db.query(StrategySignal).filter(
            StrategySignal.ticker == item.ticker,
            StrategySignal.strategy_name == strategy_name
        ).order_by(StrategySignal.calculated_date.desc()).limit(2).all()
        
        if len(rankings) < 2:
            continue
        
        current_rank = rankings[0].rank
        previous_rank = rankings[1].rank
        
        # Check for entry into top N
        if previous_rank > threshold_enter and current_rank <= threshold_enter:
            alerts.append({
                "ticker": item.ticker,
                "type": "ENTERED_TOP",
                "strategy": strategy_name,
                "previous_rank": previous_rank,
                "current_rank": current_rank,
                "threshold": threshold_enter,
                "message": f"{item.ticker} entered top {threshold_enter} (rank {previous_rank} → {current_rank})"
            })
        
        # Check for exit from top N
        elif previous_rank <= threshold_exit and current_rank > threshold_exit:
            alerts.append({
                "ticker": item.ticker,
                "type": "EXITED_TOP",
                "strategy": strategy_name,
                "previous_rank": previous_rank,
                "current_rank": current_rank,
                "threshold": threshold_exit,
                "message": f"{item.ticker} exited top {threshold_exit} (rank {previous_rank} → {current_rank})"
            })
        
        # Significant rank change
        elif abs(current_rank - previous_rank) >= 5:
            direction = "improved" if current_rank < previous_rank else "dropped"
            alerts.append({
                "ticker": item.ticker,
                "type": "RANK_CHANGE",
                "strategy": strategy_name,
                "previous_rank": previous_rank,
                "current_rank": current_rank,
                "message": f"{item.ticker} {direction} (rank {previous_rank} → {current_rank})"
            })
    
    return alerts


def get_all_watchlists(db: Session) -> List[Dict]:
    """Get all watchlists."""
    watchlists = db.query(Watchlist).all()
    return [{
        "id": w.id,
        "name": w.name,
        "created_at": w.created_at.isoformat() if w.created_at else None
    } for w in watchlists]
