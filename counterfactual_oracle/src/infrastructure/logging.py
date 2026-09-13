"""
Structured logging configuration using structlog.
Provides JSON-formatted logs for production and readable logs for development.
"""

import logging
import sys
from typing import Any
import structlog
from pythonjsonlogger import jsonlogger

from ..config import settings


def configure_logging():
    """Configure structured logging for the application."""
    
    shared_processors: list[Any] = [
        # Add timestamp
        structlog.processors.TimeStamper(fmt="iso"),
        # Add log level
        structlog.stdlib.add_log_level,
        # Add logger name
        structlog.stdlib.add_logger_name,
        # Format exceptions
        structlog.processors.format_exc_info,
    ]
    
    if settings.log_format == "json":
        # Production: JSON logs
        structlog.configure(
            processors=shared_processors + [
                structlog.processors.dict_tracebacks,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
        
        # Configure standard library logging to output JSON
        log_handler = logging.StreamHandler(sys.stdout)
        formatter = jsonlogger.JsonFormatter(
            '%(timestamp)s %(levelname)s %(name)s %(message)s'
        )
        log_handler.setFormatter(formatter)
        
        root_logger = logging.getLogger()
        root_logger.handlers = [log_handler]
        root_logger.setLevel(getattr(logging, settings.log_level.upper()))
        
    else:
        # Development: Pretty console logs
        structlog.configure(
            processors=shared_processors + [
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
        
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=getattr(logging, settings.log_level.upper()),
        )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
