"""
Centralized logging configuration for the Flask application.

This module provides a unified logging setup that works across:
- Flask routes and blueprints
- Background scheduler tasks
- Services and utilities
- Both console and file outputs
"""

import json
import logging
import logging.handlers
import os
from datetime import datetime, timezone
from pathlib import Path


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for console output"""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        # Add color to the level name
        if record.levelname in self.COLORS:
            record.levelname_colored = (
                f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
            )
        else:
            record.levelname_colored = record.levelname

        return super().format(record)


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logs (Docker-friendly)."""

    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def setup_logging(app=None, log_level=None, log_dir=None):
    """
    Configure logging for the entire application.

    Args:
        app: Flask application instance (optional)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory to store log files (default: ./logs)

    Returns:
        logging.Logger: Configured root logger
    """

    # Determine log level
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Determine log directory
    if log_dir is None:
        log_dir = os.getenv("LOG_DIR", "./logs")

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_format = os.getenv("LOG_FORMAT", "text").lower()
    max_bytes = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
    backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))
    error_backup_count = int(os.getenv("LOG_ERROR_BACKUP_COUNT", "5"))
    scheduler_backup_count = int(os.getenv("LOG_SCHEDULER_BACKUP_COUNT", "3"))

    # Create formatters
    detailed_format = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    console_format = "[%(asctime)s] [%(levelname_colored)s] [%(name)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Console formatter with colors
    console_formatter = ColoredFormatter(fmt=console_format, datefmt=date_format)

    # File formatter (no colors)
    file_formatter = logging.Formatter(fmt=detailed_format, datefmt=date_format)

    # JSON formatter (structured)
    json_formatter = JsonFormatter()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Console Handler (stdout)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(json_formatter if log_format == "json" else console_formatter)
    root_logger.addHandler(console_handler)

    # File Handler - Main application log
    app_log_file = log_dir / "app.log"
    file_handler = logging.handlers.RotatingFileHandler(
        app_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",  # 10MB
    )
    file_handler.setLevel(getattr(logging, log_level))
    file_handler.setFormatter(json_formatter if log_format == "json" else file_formatter)
    root_logger.addHandler(file_handler)

    # File Handler - Error log (ERROR and above only)
    error_log_file = log_dir / "error.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=max_bytes,
        backupCount=error_backup_count,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(json_formatter if log_format == "json" else file_formatter)
    root_logger.addHandler(error_handler)

    # File Handler - Scheduler log (separate file for scheduler events)
    scheduler_log_file = log_dir / "scheduler.log"
    scheduler_handler = logging.handlers.RotatingFileHandler(
        scheduler_log_file,
        maxBytes=max_bytes,
        backupCount=scheduler_backup_count,
        encoding="utf-8",
    )
    scheduler_handler.setLevel(logging.INFO)
    scheduler_handler.setFormatter(json_formatter if log_format == "json" else file_formatter)

    # Add scheduler handler only to scheduler loggers
    scheduler_logger = logging.getLogger("app.scheduler")
    scheduler_logger.addHandler(scheduler_handler)
    scheduler_logger.propagate = False

    service_logger = logging.getLogger("app.services")
    service_logger.setLevel(getattr(logging, log_level))

    # Configure Flask's logger if app is provided
    if app:
        app.logger.handlers.clear()
        app.logger.setLevel(getattr(logging, log_level))

        # Flask app uses the same handlers as root logger
        for handler in root_logger.handlers:
            app.logger.addHandler(handler)

        # Prevent propagation to avoid duplicate logs
        app.logger.propagate = False

    # Suppress noisy third-party loggers
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("apscheduler.scheduler").setLevel(logging.INFO)
    logging.getLogger("apscheduler.executors").setLevel(logging.WARNING)

    # Log the initialization
    root_logger.info("=" * 60)
    root_logger.info("Logging system initialised")
    root_logger.info(f"Log Level: {log_level}")
    root_logger.info(f"Log Directory: {log_dir.absolute()}")
    root_logger.info(f"Log Format: {log_format}")
    root_logger.info(f"Max Bytes: {max_bytes}, Backup Count: {backup_count}")
    root_logger.info(f"Application Log: {app_log_file}")
    root_logger.info(f"Error Log: {error_log_file}")
    root_logger.info(f"Scheduler Log: {scheduler_log_file}")
    root_logger.info("=" * 60)

    return root_logger


def get_logger(name):
    """
    Get a logger instance for a module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        logging.Logger: Logger instance
    """
    return logging.getLogger(name)


# Utility function for logging function calls (decorator)
def log_function_call(logger=None):
    """
    Decorator to log function entry and exit.

    Usage:
        @log_function_call()
        def my_function(arg1, arg2):
            pass
    """

    def decorator(func):
        nonlocal logger
        if logger is None:
            logger = logging.getLogger(func.__module__)

        def wrapper(*args, **kwargs):
            logger.debug(f"Entering {func.__name__}(args={args}, kwargs={kwargs})")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"Exiting {func.__name__}() -> {result}")
                return result
            except Exception as e:
                logger.exception(f"Exception in {func.__name__}(): {e}")
                raise

        return wrapper

    return decorator
