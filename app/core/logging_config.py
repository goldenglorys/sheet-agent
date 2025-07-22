"""
Logging configuration module for the SheetAgent application.

This module provides a centralized way to configure logging for the application,
ensuring consistent log formatting and behavior across all components.
"""

import logging
import sys
from typing import Optional


def configure_logging(level: Optional[str] = None, force: bool = False) -> None:
    """
    Configure the logging system for the application.
    
    This function sets up the root logger with appropriate handlers and formatters,
    ensuring consistent log output across the application. It is safe to call
    multiple times; it will only configure logging if it hasn't been configured yet
    or if force=True.
    
    Args:
        level: The logging level to use. If None, defaults to INFO.
        force: If True, reconfigure logging even if it's already configured.
    """
    # Convert string level to logging level constant
    if level is None:
        log_level = logging.INFO
    else:
        log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Get the root logger
    root_logger = logging.getLogger()
    
    # Remove existing handlers if forcing reconfiguration
    if force and root_logger.handlers:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
    
    # Only configure if the root logger has no handlers or if forcing
    if force or not root_logger.handlers:
        # Configure the root logger
        # Create a formatter
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        
        # Create a handler that writes to stdout
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        
        # Set the log level on the root logger
        root_logger.setLevel(log_level)
        
        # Add the handler to the root logger
        root_logger.addHandler(handler)
        
        # Set levels for specific loggers
        # This helps control verbosity of third-party libraries
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("uvicorn").setLevel(logging.INFO)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        
        # Log that logging has been configured
        logging.getLogger(__name__).info(f"Logging configured at level {logging.getLevelName(log_level)}")
    else:
        # If already configured, just update the level
        root_logger.setLevel(log_level)
        logging.getLogger(__name__).info(f"Logging level updated to {logging.getLevelName(log_level)}")
        
    # Ensure that the logging system is not being filtered by parent loggers
    for name in ["app", "app.services", "app.core", "app.api"]:
        logger = logging.getLogger(name)
        logger.setLevel(log_level)
        logger.propagate = True