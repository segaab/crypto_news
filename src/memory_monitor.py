import psutil
import os
from loguru import logger

class MemoryMonitor:
    def __init__(self, threshold_mb=450):  # Set threshold below 512MB
        self.threshold_bytes = threshold_mb * 1024 * 1024
        self.process = psutil.Process(os.getpid())
    
    def check_memory(self) -> bool:
        """Check if memory usage is below threshold"""
        memory_info = self.process.memory_info()
        current_usage = memory_info.rss
        
        if current_usage > self.threshold_bytes:
            logger.warning(f"High memory usage: {current_usage / 1024 / 1024:.1f}MB")
            return False
        return True
    
    def get_usage(self) -> float:
        """Get current memory usage in MB"""
        return self.process.memory_info().rss / 1024 / 1024 