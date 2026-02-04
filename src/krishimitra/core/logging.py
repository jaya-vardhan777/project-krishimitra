"""
Logging configuration for KrishiMitra application.

This module sets up structured logging with appropriate formatters
and handlers for different environments.
"""

import logging
import logging.config
import sys
from typing import Dict, Any

from .config import get_settings

settings = get_settings()


def setup_logging() -> None:
    """Set up application logging configuration."""
    
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    # Logging configuration
    logging_config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "default",
                "stream": sys.stdout
            }
        },
        "loggers": {
            "krishimitra": {
                "level": log_level,
                "handlers": ["console"],
                "propagate": False
            },
            "uvicorn": {
                "level": log_level,
                "handlers": ["console"],
                "propagate": False
            },
            "fastapi": {
                "level": log_level,
                "handlers": ["console"],
                "propagate": False
            }
        },
        "root": {
            "level": log_level,
            "handlers": ["console"]
        }
    }
    
    # Apply logging configuration
    logging.config.dictConfig(logging_config)
    
    # Set third-party library log levels
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured for {settings.environment} environment at {settings.log_level} level")