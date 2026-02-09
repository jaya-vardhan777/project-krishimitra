"""
Audit logging utilities for KrishiMitra platform.

This module provides comprehensive audit logging for data access and modifications
to ensure compliance with privacy regulations and security requirements.
"""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from functools import wraps
import inspect

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    """Types of actions that can be audited."""
    
    # Data access actions
    READ = "read"
    LIST = "list"
    SEARCH = "search"
    
    # Data modification actions
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    
    # Authentication actions
    LOGIN = "login"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    
    # Administrative actions
    EXPORT = "export"
    IMPORT = "import"
    BACKUP = "backup"
    RESTORE = "restore"
    
    # Security actions
    PERMISSION_GRANT = "permission_grant"
    PERMISSION_REVOKE = "permission_revoke"
    ACCESS_DENIED = "access_denied"


class AuditLevel(str, Enum):
    """Audit logging levels."""
    
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Audit event data structure."""
    
    timestamp: datetime
    user_id: str
    user_role: str
    action: AuditAction
    resource_type: str
    resource_id: Optional[str]
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    level: AuditLevel = AuditLevel.INFO
    success: bool = True
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert audit event to dictionary."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert audit event to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class AuditLogger:
    """
    Audit logger for tracking data access and modifications.
    
    Provides structured logging of security-relevant events with
    proper formatting and storage options.
    """
    
    def __init__(self, logger_name: str = "krishimitra.audit"):
        """
        Initialize audit logger.
        
        Args:
            logger_name: Name of the logger to use
        """
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)
        
        # Ensure audit logger has a handler
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def log_event(self, event: AuditEvent) -> None:
        """
        Log an audit event.
        
        Args:
            event: Audit event to log
        """
        log_level = getattr(logging, event.level.upper())
        self.logger.log(log_level, event.to_json())
    
    def log_data_access(
        self,
        user_id: str,
        user_role: str,
        action: AuditAction,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        """
        Log data access event.
        
        Args:
            user_id: ID of the user performing the action
            user_role: Role of the user
            action: Type of action performed
            resource_type: Type of resource accessed
            resource_id: ID of the specific resource
            details: Additional details about the access
            **kwargs: Additional audit event fields
        """
        event = AuditEvent(
            timestamp=datetime.utcnow(),
            user_id=user_id,
            user_role=user_role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            **kwargs
        )
        self.log_event(event)
    
    def log_data_modification(
        self,
        user_id: str,
        user_role: str,
        action: AuditAction,
        resource_type: str,
        resource_id: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        """
        Log data modification event.
        
        Args:
            user_id: ID of the user performing the modification
            user_role: Role of the user
            action: Type of modification performed
            resource_type: Type of resource modified
            resource_id: ID of the specific resource
            old_values: Previous values (for updates)
            new_values: New values (for creates/updates)
            **kwargs: Additional audit event fields
        """
        details = {}
        if old_values:
            details["old_values"] = old_values
        if new_values:
            details["new_values"] = new_values
        
        event = AuditEvent(
            timestamp=datetime.utcnow(),
            user_id=user_id,
            user_role=user_role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            level=AuditLevel.INFO,
            **kwargs
        )
        self.log_event(event)
    
    def log_security_event(
        self,
        user_id: str,
        user_role: str,
        action: AuditAction,
        success: bool = True,
        error_message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        """
        Log security-related event.
        
        Args:
            user_id: ID of the user
            user_role: Role of the user
            action: Security action performed
            success: Whether the action was successful
            error_message: Error message if action failed
            details: Additional details
            **kwargs: Additional audit event fields
        """
        level = AuditLevel.INFO if success else AuditLevel.WARNING
        if action == AuditAction.ACCESS_DENIED:
            level = AuditLevel.WARNING
        
        event = AuditEvent(
            timestamp=datetime.utcnow(),
            user_id=user_id,
            user_role=user_role,
            action=action,
            resource_type="security",
            resource_id=None,
            details=details or {},
            level=level,
            success=success,
            error_message=error_message,
            **kwargs
        )
        self.log_event(event)
    
    def search_audit_logs(
        self,
        user_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        resource_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search audit logs (placeholder implementation).
        
        In a production system, this would query a database or log aggregation system.
        
        Args:
            user_id: Filter by user ID
            action: Filter by action type
            resource_type: Filter by resource type
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum number of results
            
        Returns:
            List of audit log entries
        """
        # Placeholder implementation
        # In production, this would query a database or log storage system
        logger.info(f"Searching audit logs with filters: user_id={user_id}, action={action}, "
                   f"resource_type={resource_type}, start_time={start_time}, end_time={end_time}")
        
        return []


# Global audit logger instance
_audit_logger = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def log_data_access(
    user_id: str,
    user_role: str,
    action: AuditAction,
    resource_type: str,
    resource_id: Optional[str] = None,
    **kwargs
) -> None:
    """
    Convenience function to log data access.
    
    Args:
        user_id: ID of the user performing the action
        user_role: Role of the user
        action: Type of action performed
        resource_type: Type of resource accessed
        resource_id: ID of the specific resource
        **kwargs: Additional audit fields
    """
    get_audit_logger().log_data_access(
        user_id=user_id,
        user_role=user_role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        **kwargs
    )


def log_data_modification(
    user_id: str,
    user_role: str,
    action: AuditAction,
    resource_type: str,
    resource_id: Optional[str] = None,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    **kwargs
) -> None:
    """
    Convenience function to log data modification.
    
    Args:
        user_id: ID of the user performing the modification
        user_role: Role of the user
        action: Type of modification performed
        resource_type: Type of resource modified
        resource_id: ID of the specific resource
        old_values: Previous values (for updates)
        new_values: New values (for creates/updates)
        **kwargs: Additional audit fields
    """
    get_audit_logger().log_data_modification(
        user_id=user_id,
        user_role=user_role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        old_values=old_values,
        new_values=new_values,
        **kwargs
    )


def audit_data_access(
    action: AuditAction,
    resource_type: str,
    resource_id_param: Optional[str] = None
):
    """
    Decorator to automatically audit data access operations.
    
    Args:
        action: Type of action being performed
        resource_type: Type of resource being accessed
        resource_id_param: Name of parameter containing resource ID
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get current user from kwargs (should be injected by FastAPI dependency)
            current_user = kwargs.get("current_user")
            if current_user:
                resource_id = None
                if resource_id_param:
                    resource_id = kwargs.get(resource_id_param)
                
                log_data_access(
                    user_id=current_user.user_id,
                    user_role=current_user.role.value,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    details={"function": func.__name__}
                )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def audit_data_modification(
    action: AuditAction,
    resource_type: str,
    resource_id_param: Optional[str] = None
):
    """
    Decorator to automatically audit data modification operations.
    
    Args:
        action: Type of modification being performed
        resource_type: Type of resource being modified
        resource_id_param: Name of parameter containing resource ID
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get current user from kwargs
            current_user = kwargs.get("current_user")
            if current_user:
                resource_id = None
                if resource_id_param:
                    resource_id = kwargs.get(resource_id_param)
                
                # For updates, we could capture old values here
                # This would require additional logic to fetch current state
                
                result = func(*args, **kwargs)
                
                log_data_modification(
                    user_id=current_user.user_id,
                    user_role=current_user.role.value,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    details={"function": func.__name__}
                )
                
                return result
            
            return func(*args, **kwargs)
        return wrapper
    return decorator