"""
Data sync configuration and scheduling system.
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class DataSyncConfig:
    """Configuration for data sync intervals and behavior."""
    
    def __init__(self, config_path: str = "data_sync_config.json"):
        self.config_path = config_path
        self.default_config = {
            "auto_sync_enabled": True,
            "sync_interval_hours": 24,  # Daily by default
            "sync_on_visit": True,
            "visit_threshold_minutes": 30,  # Only sync if last visit was >30min ago
            "cache_ttl_minutes": 300,  # 5 hours cache TTL
            "max_concurrent_requests": 3,
            "request_delay_seconds": 2,
            "retry_failed_after_minutes": 60,
            "last_sync": None,
            "last_visit": None
        }
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                # Merge with defaults for any missing keys
                merged = self.default_config.copy()
                merged.update(config)
                return merged
            else:
                return self.default_config.copy()
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self.default_config.copy()
    
    def save_config(self):
        """Save current configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def update_config(self, updates: Dict[str, Any]):
        """Update configuration with new values."""
        self.config.update(updates)
        self.save_config()
    
    def should_sync_now(self) -> bool:
        """Check if sync should run now based on configuration."""
        if not self.config["auto_sync_enabled"]:
            return False
        
        last_sync = self.config.get("last_sync")
        if not last_sync:
            return True  # Never synced before
        
        try:
            last_sync_time = datetime.fromisoformat(last_sync)
            sync_interval = timedelta(hours=self.config["sync_interval_hours"])
            return datetime.now() - last_sync_time >= sync_interval
        except:
            return True  # Invalid timestamp, sync now
    
    def should_sync_on_visit(self) -> bool:
        """Check if sync should run due to user visit."""
        if not self.config["sync_on_visit"]:
            return False
        
        last_visit = self.config.get("last_visit")
        if not last_visit:
            return True  # First visit
        
        try:
            last_visit_time = datetime.fromisoformat(last_visit)
            visit_threshold = timedelta(minutes=self.config["visit_threshold_minutes"])
            return datetime.now() - last_visit_time >= visit_threshold
        except:
            return True  # Invalid timestamp, sync now
    
    def record_sync(self):
        """Record that a sync has completed."""
        self.config["last_sync"] = datetime.now().isoformat()
        self.save_config()
    
    def record_visit(self):
        """Record a user visit."""
        self.config["last_visit"] = datetime.now().isoformat()
        self.save_config()
    
    def get_next_sync_time(self) -> str:
        """Get the next scheduled sync time."""
        last_sync = self.config.get("last_sync")
        if not last_sync:
            return "Now (never synced)"
        
        try:
            last_sync_time = datetime.fromisoformat(last_sync)
            next_sync = last_sync_time + timedelta(hours=self.config["sync_interval_hours"])
            
            if next_sync <= datetime.now():
                return "Now (overdue)"
            else:
                return next_sync.strftime("%Y-%m-%d %H:%M")
        except:
            return "Now (invalid timestamp)"

# Global config instance
sync_config = DataSyncConfig()
