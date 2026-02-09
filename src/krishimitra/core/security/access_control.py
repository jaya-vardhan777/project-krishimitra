"""
Access control utilities for KrishiMitra platform.

This module provides role-based access control (RBAC) and permission management
for protecting farmer data and ensuring proper authorization.
"""

from enum import Enum
from typing import List, Optional, Dict, Any, Set
from functools import wraps
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class Role(str, Enum):
    """User roles in the KrishiMitra platform."""
    
    FARMER = "farmer"
    AGENT = "agent"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"
    SYSTEM = "system"


class Permission(str, Enum):
    """Permissions for different operations."""
    
    # Farmer profile permissions
    READ_OWN_PROFILE = "read_own_profile"
    UPDATE_OWN_PROFILE = "update_own_profile"
    DELETE_OWN_PROFILE = "delete_own_profile"
    
    # Other farmers' profiles
    READ_FARMER_PROFILE = "read_farmer_profile"
    UPDATE_FARMER_PROFILE = "update_farmer_profile"
    DELETE_FARMER_PROFILE = "delete_farmer_profile"
    LIST_FARMER_PROFILES = "list_farmer_profiles"
    
    # Recommendations
    READ_OWN_RECOMMENDATIONS = "read_own_recommendations"
    CREATE_RECOMMENDATIONS = "create_recommendations"
    READ_ALL_RECOMMENDATIONS = "read_all_recommendations"
    
    # Agricultural data
    READ_AGRICULTURAL_DATA = "read_agricultural_data"
    UPDATE_AGRICULTURAL_DATA = "update_agricultural_data"
    
    # System administration
    MANAGE_USERS = "manage_users"
    MANAGE_SYSTEM = "manage_system"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    
    # Data export and analytics
    EXPORT_DATA = "export_data"
    VIEW_ANALYTICS = "view_analytics"


class User:
    """User model for access control."""
    
    def __init__(
        self,
        user_id: str,
        role: Role,
        farmer_id: Optional[str] = None,
        permissions: Optional[Set[Permission]] = None
    ):
        self.user_id = user_id
        self.role = role
        self.farmer_id = farmer_id  # For farmers, this is their own farmer_id
        self.permissions = permissions or set()
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions
    
    def can_access_farmer_data(self, farmer_id: str) -> bool:
        """Check if user can access specific farmer's data."""
        # Farmers can only access their own data
        if self.role == Role.FARMER:
            return self.farmer_id == farmer_id
        
        # Agents, supervisors, and admins can access farmer data based on permissions
        if self.role in [Role.AGENT, Role.SUPERVISOR, Role.ADMIN]:
            return self.has_permission(Permission.READ_FARMER_PROFILE)
        
        # System role has full access
        if self.role == Role.SYSTEM:
            return True
        
        return False


class AccessControl:
    """Access control service for managing permissions and authorization."""
    
    def __init__(self):
        """Initialize access control with default role permissions."""
        self.role_permissions = self._setup_default_permissions()
        self.security = HTTPBearer()
    
    def _setup_default_permissions(self) -> Dict[Role, Set[Permission]]:
        """Set up default permissions for each role."""
        return {
            Role.FARMER: {
                Permission.READ_OWN_PROFILE,
                Permission.UPDATE_OWN_PROFILE,
                Permission.DELETE_OWN_PROFILE,
                Permission.READ_OWN_RECOMMENDATIONS,
            },
            Role.AGENT: {
                Permission.READ_FARMER_PROFILE,
                Permission.UPDATE_FARMER_PROFILE,
                Permission.LIST_FARMER_PROFILES,
                Permission.CREATE_RECOMMENDATIONS,
                Permission.READ_ALL_RECOMMENDATIONS,
                Permission.READ_AGRICULTURAL_DATA,
                Permission.UPDATE_AGRICULTURAL_DATA,
            },
            Role.SUPERVISOR: {
                Permission.READ_FARMER_PROFILE,
                Permission.UPDATE_FARMER_PROFILE,
                Permission.LIST_FARMER_PROFILES,
                Permission.CREATE_RECOMMENDATIONS,
                Permission.READ_ALL_RECOMMENDATIONS,
                Permission.READ_AGRICULTURAL_DATA,
                Permission.UPDATE_AGRICULTURAL_DATA,
                Permission.VIEW_ANALYTICS,
                Permission.EXPORT_DATA,
            },
            Role.ADMIN: {
                Permission.READ_FARMER_PROFILE,
                Permission.UPDATE_FARMER_PROFILE,
                Permission.DELETE_FARMER_PROFILE,
                Permission.LIST_FARMER_PROFILES,
                Permission.CREATE_RECOMMENDATIONS,
                Permission.READ_ALL_RECOMMENDATIONS,
                Permission.READ_AGRICULTURAL_DATA,
                Permission.UPDATE_AGRICULTURAL_DATA,
                Permission.MANAGE_USERS,
                Permission.VIEW_AUDIT_LOGS,
                Permission.VIEW_ANALYTICS,
                Permission.EXPORT_DATA,
            },
            Role.SYSTEM: set(Permission),  # System has all permissions
        }
    
    def get_user_permissions(self, role: Role) -> Set[Permission]:
        """Get permissions for a role."""
        return self.role_permissions.get(role, set())
    
    def create_user(
        self,
        user_id: str,
        role: Role,
        farmer_id: Optional[str] = None,
        additional_permissions: Optional[Set[Permission]] = None
    ) -> User:
        """Create a user with role-based permissions."""
        permissions = self.get_user_permissions(role)
        if additional_permissions:
            permissions.update(additional_permissions)
        
        return User(
            user_id=user_id,
            role=role,
            farmer_id=farmer_id,
            permissions=permissions
        )
    
    def check_permission(self, user: User, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        return user.has_permission(permission)
    
    def check_farmer_access(self, user: User, farmer_id: str) -> bool:
        """Check if user can access specific farmer's data."""
        return user.can_access_farmer_data(farmer_id)
    
    def generate_token(self, user: User, secret_key: str, expires_in_hours: int = 24) -> str:
        """Generate JWT token for user authentication."""
        payload = {
            "user_id": user.user_id,
            "role": user.role.value,
            "farmer_id": user.farmer_id,
            "permissions": [p.value for p in user.permissions],
            "exp": datetime.utcnow() + timedelta(hours=expires_in_hours),
            "iat": datetime.utcnow()
        }
        
        return jwt.encode(payload, secret_key, algorithm="HS256")
    
    def verify_token(self, token: str, secret_key: str) -> Optional[User]:
        """Verify JWT token and return user."""
        try:
            payload = jwt.decode(token, secret_key, algorithms=["HS256"])
            
            permissions = {Permission(p) for p in payload.get("permissions", [])}
            
            return User(
                user_id=payload["user_id"],
                role=Role(payload["role"]),
                farmer_id=payload.get("farmer_id"),
                permissions=permissions
            )
        
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None


# Global access control instance
_access_control = None


def get_access_control() -> AccessControl:
    """Get global access control instance."""
    global _access_control
    if _access_control is None:
        _access_control = AccessControl()
    return _access_control


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    access_control: AccessControl = Depends(get_access_control)
) -> User:
    """
    FastAPI dependency to get current authenticated user.
    
    Args:
        credentials: HTTP Bearer token credentials
        access_control: Access control service
        
    Returns:
        Current authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
    import os
    secret_key = os.getenv("JWT_SECRET_KEY", "dev-secret-key")
    
    user = access_control.verify_token(credentials.credentials, secret_key)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


def require_permission(permission: Permission):
    """
    Decorator to require specific permission for endpoint access.
    
    Args:
        permission: Required permission
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get current user from kwargs (should be injected by FastAPI dependency)
            current_user = kwargs.get("current_user")
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            if not current_user.has_permission(permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission required: {permission.value}"
                )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_farmer_access(farmer_id_param: str = "farmer_id"):
    """
    Decorator to require access to specific farmer's data.
    
    Args:
        farmer_id_param: Name of the parameter containing farmer_id
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get current user from kwargs
            current_user = kwargs.get("current_user")
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Get farmer_id from kwargs
            farmer_id = kwargs.get(farmer_id_param)
            if not farmer_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing parameter: {farmer_id_param}"
                )
            
            if not current_user.can_access_farmer_data(farmer_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to farmer data"
                )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


class DataAccessPolicy:
    """
    Policy for controlling data access based on user context.
    
    Provides methods to filter and transform data based on user permissions
    and access rights.
    """
    
    @staticmethod
    def filter_farmer_profile_fields(profile_data: Dict[str, Any], user: User) -> Dict[str, Any]:
        """
        Filter farmer profile fields based on user permissions.
        
        Args:
            profile_data: Complete farmer profile data
            user: Current user
            
        Returns:
            Filtered profile data based on user permissions
        """
        # System and admin users get full access
        if user.role in [Role.SYSTEM, Role.ADMIN]:
            return profile_data
        
        # Agents and supervisors get most fields but not highly sensitive ones
        if user.role in [Role.AGENT, Role.SUPERVISOR]:
            filtered_data = profile_data.copy()
            # Remove highly sensitive fields
            sensitive_fields = ["aadhaar_number", "pan_number", "bank_account_details"]
            for field in sensitive_fields:
                filtered_data.pop(field, None)
            return filtered_data
        
        # Farmers get their own full data, limited data for others
        if user.role == Role.FARMER:
            if user.farmer_id == profile_data.get("farmer_id"):
                return profile_data
            else:
                # Very limited data for other farmers
                return {
                    "farmer_id": profile_data.get("farmer_id"),
                    "name": profile_data.get("name"),
                    "location": {
                        "state": profile_data.get("location", {}).get("state"),
                        "district": profile_data.get("location", {}).get("district")
                    }
                }
        
        # Default: no access
        return {}
    
    @staticmethod
    def can_export_data(user: User, data_type: str) -> bool:
        """
        Check if user can export specific type of data.
        
        Args:
            user: Current user
            data_type: Type of data to export
            
        Returns:
            True if user can export the data type
        """
        if not user.has_permission(Permission.EXPORT_DATA):
            return False
        
        # Additional checks based on data type
        if data_type == "farmer_profiles":
            return user.role in [Role.ADMIN, Role.SUPERVISOR]
        elif data_type == "recommendations":
            return user.role in [Role.ADMIN, Role.SUPERVISOR, Role.AGENT]
        elif data_type == "agricultural_data":
            return user.role in [Role.ADMIN, Role.SUPERVISOR]
        
        return False