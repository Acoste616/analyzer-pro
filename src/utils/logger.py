import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from ..config.settings import settings_manager


class ColorFormatter(logging.Formatter):
    """Custom formatter with color support for console output"""
    
    # Color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def format(self, record):
        # Add color to level name
        if record.levelname in self.COLORS:
            record.levelname_color = (
                f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"
            )
        else:
            record.levelname_color = record.levelname
        
        # Use colored levelname in format
        original_levelname = record.levelname
        record.levelname = record.levelname_color
        
        # Format the message
        formatted = super().format(record)
        
        # Restore original levelname
        record.levelname = original_levelname
        
        return formatted


class StructuredLogger:
    """Enhanced logger with structured logging capabilities"""
    
    def __init__(self, name: str, enable_structured: bool = False):
        self.name = name
        self.enable_structured = enable_structured
        self.logger = logging.getLogger(name)
        self._extra_context = {}
    
    def add_context(self, **kwargs):
        """Add persistent context to all log messages"""
        self._extra_context.update(kwargs)
    
    def remove_context(self, *keys):
        """Remove context keys"""
        for key in keys:
            self._extra_context.pop(key, None)
    
    def clear_context(self):
        """Clear all context"""
        self._extra_context.clear()
    
    def _log_with_context(self, level: int, msg: str, *args, **kwargs):
        """Log with added context"""
        extra = kwargs.get('extra', {})
        extra.update(self._extra_context)
        kwargs['extra'] = extra
        
        if self.enable_structured:
            # Add structured data
            structured_data = {
                'timestamp': datetime.now().isoformat(),
                'logger': self.name,
                'level': logging.getLevelName(level),
                'message': msg % args if args else msg,
                'context': extra
            }
            
            # Log as JSON for structured logging
            import json
            self.logger.log(level, json.dumps(structured_data), **kwargs)
        else:
            self.logger.log(level, msg, *args, **kwargs)
    
    def debug(self, msg: str, *args, **kwargs):
        self._log_with_context(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        self._log_with_context(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        self._log_with_context(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        self._log_with_context(logging.ERROR, msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        self._log_with_context(logging.CRITICAL, msg, *args, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs):
        kwargs['exc_info'] = True
        self.error(msg, *args, **kwargs)


class LogManager:
    """Central log management"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.settings = settings_manager.settings
            self.loggers: Dict[str, StructuredLogger] = {}
            self._setup_logging()
            LogManager._initialized = True
    
    def _setup_logging(self):
        """Setup logging configuration"""
        
        # Get logging configuration
        log_config = self.settings.logging
        
        # Create logs directory
        log_file = Path(log_config.file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Root logger configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_config.level.upper()))
        
        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Console handler with color formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = ColorFormatter(
            fmt='%(asctime)s - %(name)s - %(levelname_color)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)  # Console shows INFO and above
        
        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_config.file,
            maxBytes=log_config.max_size,
            backupCount=log_config.backup_count,
            encoding='utf-8'
        )
        file_formatter = logging.Formatter(
            fmt=log_config.format,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(getattr(logging, log_config.level.upper()))
        
        # Add handlers to root logger
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        
        # Setup application logger
        app_logger = logging.getLogger('bookmark_analyzer')
        app_logger.setLevel(getattr(logging, log_config.level.upper()))
        
        # Prevent duplicate logs
        app_logger.propagate = False
        app_logger.addHandler(console_handler)
        app_logger.addHandler(file_handler)
    
    def get_logger(self, name: str, enable_structured: bool = False) -> StructuredLogger:
        """Get or create a logger"""
        
        if name not in self.loggers:
            self.loggers[name] = StructuredLogger(name, enable_structured)
        
        return self.loggers[name]
    
    def set_level(self, level: str):
        """Set logging level for all loggers"""
        
        log_level = getattr(logging, level.upper())
        
        # Update root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Update all handlers
        for handler in root_logger.handlers:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                handler.setLevel(log_level)
    
    def add_file_handler(self, logger_name: str, file_path: str, level: str = 'INFO'):
        """Add additional file handler to a specific logger"""
        
        logger = logging.getLogger(logger_name)
        
        # Create file handler
        handler = logging.handlers.RotatingFileHandler(
            filename=file_path,
            maxBytes=self.settings.logging.max_size,
            backupCount=self.settings.logging.backup_count,
            encoding='utf-8'
        )
        
        formatter = logging.Formatter(
            fmt=self.settings.logging.format,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        handler.setLevel(getattr(logging, level.upper()))
        
        logger.addHandler(handler)
    
    def create_performance_logger(self) -> StructuredLogger:
        """Create a specialized logger for performance metrics"""
        
        perf_logger = self.get_logger('performance', enable_structured=True)
        
        # Add separate file handler for performance logs
        perf_log_path = Path(self.settings.logging.file).parent / 'performance.log'
        self.add_file_handler('performance', str(perf_log_path), 'DEBUG')
        
        return perf_logger
    
    def create_audit_logger(self) -> StructuredLogger:
        """Create a specialized logger for audit trail"""
        
        audit_logger = self.get_logger('audit', enable_structured=True)
        
        # Add separate file handler for audit logs
        audit_log_path = Path(self.settings.logging.file).parent / 'audit.log'
        self.add_file_handler('audit', str(audit_log_path), 'INFO')
        
        return audit_logger
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """Get logging statistics"""
        
        log_file = Path(self.settings.logging.file)
        stats = {
            'log_file': str(log_file),
            'log_file_exists': log_file.exists(),
            'log_file_size': 0,
            'backup_files_count': 0,
            'current_level': logging.getLevelName(logging.getLogger().level),
            'active_loggers': list(self.loggers.keys())
        }
        
        if log_file.exists():
            stats['log_file_size'] = log_file.stat().st_size
            
            # Count backup files
            backup_pattern = f"{log_file.name}.*"
            backup_files = list(log_file.parent.glob(backup_pattern))
            stats['backup_files_count'] = len(backup_files)
        
        return stats


# Initialize log manager
_log_manager = LogManager()


def get_logger(name: str, enable_structured: bool = False) -> StructuredLogger:
    """Get a logger instance"""
    return _log_manager.get_logger(name, enable_structured)


def get_performance_logger() -> StructuredLogger:
    """Get performance logger"""
    return _log_manager.create_performance_logger()


def get_audit_logger() -> StructuredLogger:
    """Get audit logger"""
    return _log_manager.create_audit_logger()


def set_log_level(level: str):
    """Set global logging level"""
    _log_manager.set_level(level)


def get_log_statistics() -> Dict[str, Any]:
    """Get logging statistics"""
    return _log_manager.get_log_statistics()


class LogContext:
    """Context manager for temporary logging context"""
    
    def __init__(self, logger: StructuredLogger, **context):
        self.logger = logger
        self.context = context
        self.original_context = {}
    
    def __enter__(self):
        # Save original context
        self.original_context = self.logger._extra_context.copy()
        # Add new context
        self.logger.add_context(**self.context)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original context
        self.logger.clear_context()
        self.logger.add_context(**self.original_context)


class PerformanceTimer:
    """Context manager for performance timing"""
    
    def __init__(self, logger: StructuredLogger, operation: str, **context):
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.debug(f"Starting {self.operation}", extra=self.context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        context = self.context.copy()
        context.update({
            'operation': self.operation,
            'duration_seconds': duration,
            'start_time': self.start_time.isoformat(),
            'end_time': end_time.isoformat()
        })
        
        if exc_type is None:
            self.logger.info(f"Completed {self.operation} in {duration:.3f}s", extra=context)
        else:
            context['error'] = str(exc_val) if exc_val else 'Unknown error'
            self.logger.error(f"Failed {self.operation} after {duration:.3f}s", extra=context)


# Convenience functions for common logging patterns
def log_function_call(logger: StructuredLogger):
    """Decorator to log function calls"""
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            
            with PerformanceTimer(logger, f"function_{func_name}"):
                try:
                    result = func(*args, **kwargs)
                    logger.debug(f"Function {func_name} completed successfully")
                    return result
                except Exception as e:
                    logger.error(f"Function {func_name} failed: {str(e)}")
                    raise
        
        return wrapper
    return decorator


def log_async_function_call(logger: StructuredLogger):
    """Decorator to log async function calls"""
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            func_name = func.__name__
            
            start_time = datetime.now()
            logger.debug(f"Starting async function {func_name}")
            
            try:
                result = await func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()
                logger.debug(f"Async function {func_name} completed in {duration:.3f}s")
                return result
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error(f"Async function {func_name} failed after {duration:.3f}s: {str(e)}")
                raise
        
        return wrapper
    return decorator