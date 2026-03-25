"""
Centralized logging configuration for Fault Localization framework.

Provides structured logging with support for:
- Multiple log levels (DEBUG, INFO, WARNING, ERROR)
- Environment variable configuration (FL_LOG_LEVEL, FL_LOG_FILE)
- Module-specific loggers with consistent formatting
- Optional file output for long-running processes
"""

import logging
import os
import sys
from pathlib import Path


# Log level configuration via environment variables
DEFAULT_LOG_LEVEL = os.environ.get("FL_LOG_LEVEL", "INFO").upper()
LOG_FILE_PATH = os.environ.get("FL_LOG_FILE")

# Validate log level
if DEFAULT_LOG_LEVEL not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
    DEFAULT_LOG_LEVEL = "INFO"

# Convert to logging level
LOG_LEVEL = getattr(logging, DEFAULT_LOG_LEVEL)


def _get_log_format() -> str:
    """Return the log format string."""
    return "[%(asctime)s] [%(levelname)-8s] [%(name)s] - %(message)s"


def _get_date_format() -> str:
    """Return the date format for log timestamps."""
    return "%Y-%m-%d %H:%M:%S"


def configure_root_logger() -> None:
    """Configure the root logger with handlers and formatting.
    
    Sets up:
    - Console (stdout) handler with formatting
    - Optional file handler if FL_LOG_FILE is set
    - Propagation rules to avoid duplicate messages
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers = []
    
    # Create formatter
    formatter = logging.Formatter(
        fmt=_get_log_format(),
        datefmt=_get_date_format()
    )
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LOG_LEVEL)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if configured)
    if LOG_FILE_PATH:
        try:
            log_file = Path(LOG_FILE_PATH)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(LOG_LEVEL)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except (OSError, PermissionError) as e:
            root_logger.warning(f"Could not open log file {LOG_FILE_PATH}: {e}")


def get_logger(module_name: str) -> logging.Logger:
    """Get a logger for a specific module.
    
    Args:
        module_name: Name of the module requesting the logger
                    (typically __name__ from the calling module)
    
    Returns:
        Configured logger instance for the module
    """
    logger = logging.getLogger(module_name)
    logger.setLevel(LOG_LEVEL)
    return logger


# Initialize logging configuration on module load
configure_root_logger()

# Convenience logger for this module
logger = get_logger(__name__)

if os.environ.get("FL_LOG_VERBOSE"):
    logger.debug(f"Logging configured: level={DEFAULT_LOG_LEVEL}, file={LOG_FILE_PATH if LOG_FILE_PATH else 'none'}")
