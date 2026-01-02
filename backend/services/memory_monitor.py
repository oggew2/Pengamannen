"""
Production memory monitoring and leak detection system.
Monitors memory usage and automatically triggers cleanup when needed.
"""
import logging
import psutil
import gc
import os
from datetime import datetime
from typing import Dict, Optional
import threading
import time

logger = logging.getLogger(__name__)

class MemoryMonitor:
    """Production-grade memory monitoring and leak detection."""
    
    def __init__(self, warning_threshold_mb: int = 3000, critical_threshold_mb: int = 3500):
        self.warning_threshold = warning_threshold_mb * 1024 * 1024  # Convert to bytes
        self.critical_threshold = critical_threshold_mb * 1024 * 1024
        self.process = psutil.Process()
        self.monitoring = False
        self.monitor_thread = None
        
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage statistics."""
        memory_info = self.process.memory_info()
        memory_percent = self.process.memory_percent()
        
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,
            'vms_mb': memory_info.vms / 1024 / 1024,
            'percent': memory_percent,
            'available_mb': psutil.virtual_memory().available / 1024 / 1024,
            'total_mb': psutil.virtual_memory().total / 1024 / 1024
        }
    
    def check_memory_status(self) -> Dict[str, any]:
        """Check current memory status and return recommendations."""
        stats = self.get_memory_usage()
        current_usage = stats['rss_mb'] * 1024 * 1024  # Convert back to bytes
        
        status = {
            'usage_mb': stats['rss_mb'],
            'percent': stats['percent'],
            'available_mb': stats['available_mb'],
            'status': 'OK',
            'action_needed': False,
            'recommendations': []
        }
        
        if current_usage > self.critical_threshold:
            status['status'] = 'CRITICAL'
            status['action_needed'] = True
            status['recommendations'].extend([
                'Immediate garbage collection required',
                'Consider restarting application',
                'Check for memory leaks in recent operations'
            ])
        elif current_usage > self.warning_threshold:
            status['status'] = 'WARNING'
            status['action_needed'] = True
            status['recommendations'].extend([
                'Trigger garbage collection',
                'Monitor for continued growth',
                'Review recent large operations'
            ])
        
        return status
    
    def force_cleanup(self) -> Dict[str, any]:
        """Force aggressive memory cleanup."""
        logger.info("Starting aggressive memory cleanup...")
        
        before_stats = self.get_memory_usage()
        
        # Multiple garbage collection passes
        for i in range(3):
            collected = gc.collect()
            logger.debug(f"GC pass {i+1}: collected {collected} objects")
        
        # Force cleanup of specific modules
        try:
            import pandas as pd
            # Clear pandas caches
            if hasattr(pd, '_config'):
                pd._config.config._global_config.clear()
        except:
            pass
        
        after_stats = self.get_memory_usage()
        
        freed_mb = before_stats['rss_mb'] - after_stats['rss_mb']
        
        result = {
            'before_mb': before_stats['rss_mb'],
            'after_mb': after_stats['rss_mb'],
            'freed_mb': freed_mb,
            'success': freed_mb > 0
        }
        
        logger.info(f"Memory cleanup complete: freed {freed_mb:.1f}MB")
        return result
    
    def start_monitoring(self, check_interval: int = 30):
        """Start background memory monitoring."""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, args=(check_interval,))
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        logger.info(f"Memory monitoring started (check every {check_interval}s)")
    
    def stop_monitoring(self):
        """Stop background memory monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Memory monitoring stopped")
    
    def _monitor_loop(self, check_interval: int):
        """Background monitoring loop."""
        while self.monitoring:
            try:
                status = self.check_memory_status()
                
                if status['status'] == 'CRITICAL':
                    logger.error(f"CRITICAL memory usage: {status['usage_mb']:.1f}MB ({status['percent']:.1f}%)")
                    self.force_cleanup()
                elif status['status'] == 'WARNING':
                    logger.warning(f"High memory usage: {status['usage_mb']:.1f}MB ({status['percent']:.1f}%)")
                    gc.collect()  # Light cleanup
                
                time.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Memory monitoring error: {e}")
                time.sleep(check_interval)

# Global memory monitor instance
memory_monitor = MemoryMonitor(warning_threshold_mb=2800, critical_threshold_mb=3200)

def monitor_memory_usage(func):
    """Decorator to monitor memory usage of functions."""
    def wrapper(*args, **kwargs):
        before = memory_monitor.get_memory_usage()
        
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            after = memory_monitor.get_memory_usage()
            memory_increase = after['rss_mb'] - before['rss_mb']
            
            if memory_increase > 100:  # More than 100MB increase
                logger.warning(f"Function {func.__name__} increased memory by {memory_increase:.1f}MB")
                
                # Auto-cleanup if significant increase
                if memory_increase > 500:  # More than 500MB
                    logger.info(f"Auto-triggering cleanup after {func.__name__}")
                    memory_monitor.force_cleanup()
    
    return wrapper

def get_memory_status() -> Dict[str, any]:
    """Get current memory status for API endpoints."""
    return memory_monitor.check_memory_status()

def cleanup_memory() -> Dict[str, any]:
    """Manual memory cleanup for API endpoints."""
    return memory_monitor.force_cleanup()
