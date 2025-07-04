"""Logging configuration and utilities."""

import sys
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from ..config import get_settings


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[Path] = None,
    rotation: Optional[str] = None,
    retention: Optional[str] = None,
) -> None:
    """
    Configure logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file
        rotation: Log rotation setting (e.g., "10 MB", "1 day")
        retention: Log retention setting (e.g., "30 days")
    """
    settings = get_settings()
    
    # Remove default logger
    logger.remove()
    
    # Get configuration
    log_level = log_level or settings.logging.level
    rotation = rotation or settings.logging.rotation
    retention = retention or settings.logging.retention
    log_format = settings.logging.format
    
    # Console logger
    logger.add(
        sys.stdout,
        format=log_format,
        level=log_level,
        colorize=True,
        backtrace=settings.logging.backtrace,
        diagnose=settings.logging.diagnose,
    )
    
    # File logger
    if log_file is None:
        log_dir = settings.project_root / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"{settings.app_name}.log"
    
    logger.add(
        log_file,
        format=log_format,
        level=log_level,
        rotation=rotation,
        retention=retention,
        compression="zip",
        backtrace=settings.logging.backtrace,
        diagnose=settings.logging.diagnose,
    )
    
    # Add context
    logger.configure(
        extra={
            "app": settings.app_name,
            "environment": settings.environment,
            "version": settings.version,
        }
    )
    
    logger.info(
        f"Logging initialized - Level: {log_level}, "
        f"File: {log_file}, Environment: {settings.environment}"
    )


def get_logger(name: str) -> "logger":
    """
    Get a logger instance with context.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return logger.bind(module=name)


class LoggerMixin:
    """Mixin class to add logging capabilities to any class."""
    
    @property
    def logger(self) -> "logger":
        """Get logger for the class."""
        if not hasattr(self, "_logger"):
            self._logger = get_logger(self.__class__.__module__)
        return self._logger


def log_execution_time(func):
    """Decorator to log function execution time."""
    import time
    from functools import wraps
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        logger.debug(f"Starting {func.__name__}")
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.debug(
                f"Completed {func.__name__} in {execution_time:.2f}s"
            )
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Failed {func.__name__} after {execution_time:.2f}s: {str(e)}"
            )
            raise
    
    return wrapper


def log_memory_usage(func):
    """Decorator to log memory usage of a function."""
    import psutil
    import os
    from functools import wraps
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / 1024 / 1024  # MB
        
        result = func(*args, **kwargs)
        
        mem_after = process.memory_info().rss / 1024 / 1024  # MB
        mem_used = mem_after - mem_before
        
        logger.debug(
            f"{func.__name__} memory usage: {mem_used:.2f} MB "
            f"(before: {mem_before:.2f} MB, after: {mem_after:.2f} MB)"
        )
        
        return result
    
    return wrapper


class ProgressLogger:
    """Context manager for logging progress of long-running operations."""
    
    def __init__(self, total: int, description: str = "Processing"):
        self.total = total
        self.description = description
        self.current = 0
        self.start_time = None
        
    def __enter__(self):
        self.start_time = time.time()
        logger.info(f"{self.description}: Starting {self.total} items")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time if self.start_time else 0
        if exc_type is None:
            logger.info(
                f"{self.description}: Completed {self.current}/{self.total} "
                f"items in {elapsed:.2f}s"
            )
        else:
            logger.error(
                f"{self.description}: Failed after {self.current}/{self.total} "
                f"items in {elapsed:.2f}s: {exc_val}"
            )
        
    def update(self, count: int = 1):
        """Update progress counter."""
        self.current += count
        if self.current % 10 == 0 or self.current == self.total:
            elapsed = time.time() - self.start_time if self.start_time else 0
            rate = self.current / elapsed if elapsed > 0 else 0
            eta = (self.total - self.current) / rate if rate > 0 else 0
            
            logger.info(
                f"{self.description}: {self.current}/{self.total} "
                f"({self.current/self.total*100:.1f}%) - "
                f"Rate: {rate:.1f}/s, ETA: {eta:.1f}s"
            )


# Initialize logging on import
if __name__ != "__main__":
    setup_logging()