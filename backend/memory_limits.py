"""
Emergency memory limit fix for Docker container.
Forces Python to respect Docker memory limits to prevent OOM kills.
"""
import resource
import os
import logging

logger = logging.getLogger(__name__)

def set_memory_limits():
    """
    Set Python memory limits based on Docker container limits.
    Prevents Python from trying to use more memory than allocated.
    """
    try:
        # Check if running in Docker container
        if os.path.isfile('/sys/fs/cgroup/memory/memory.limit_in_bytes'):
            with open('/sys/fs/cgroup/memory/memory.limit_in_bytes') as limit_file:
                mem_limit = int(limit_file.read().strip())
                
                # Only set limit if it's reasonable (not the default huge value)
                if mem_limit < (1024 ** 4):  # Less than 1TB (reasonable container limit)
                    # Set to 90% of container limit to leave room for other processes
                    safe_limit = int(mem_limit * 0.9)
                    resource.setrlimit(resource.RLIMIT_AS, (safe_limit, safe_limit))
                    
                    logger.info(f"Set Python memory limit to {safe_limit / (1024**3):.1f}GB "
                               f"(90% of container limit {mem_limit / (1024**3):.1f}GB)")
                    return True
                    
    except Exception as e:
        logger.warning(f"Could not set memory limits: {e}")
    
    return False

# Apply memory limits immediately when module is imported
if __name__ != "__main__":
    set_memory_limits()
