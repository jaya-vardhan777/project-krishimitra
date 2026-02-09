"""
Middleware for KrishiMitra platform.

This module provides middleware for authentication, authorization,
and security features.
"""

import logging
from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime

from .security.access_control import User, Role, get_access_control
from .security.audit import get_audit_logger, AuditAction
from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class JWTAuthenticationMiddleware:
    """
    JWT Authentication middleware for FastAPI.
    
    Validates JWT tokens and sets user context for requests.
    """
    
    def __init__(self):
        self.access_control = get_access_control()
        self.audit_logger = get_audit_logger()
        self.security = HTTPBearer()
    
    async def authenticate_request(self, request: Request) -> Optional[User]:
        """
        Authenticate request using JWT token.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Authenticated user or None if no valid token
        """
        # Get authorization header
        authorization = request.headers.get("Authorization")
        if not authorization:
            return None
        
        # Extract token
        try:
            scheme, token = authorization.split(" ", 1)
            if scheme.lower() != "bearer":
                return None
        except ValueError:
            return None
        
        # Verify token
        secret_key = settings.jwt_secret_key
        user = self.access_control.verify_token(token, secret_key)
        
        if user:
            # Log successful authentication
            self.audit_logger.log_security_event(
                user_id=user.user_id,
                user_role=user.role.value,
                action=AuditAction.LOGIN,
                success=True,
                details={"ip_address": request.client.host if request.client else None}
            )
        else:
            # Log failed authentication
            self.audit_logger.log_security_event(
                user_id="unknown",
                user_role="unknown",
                action=AuditAction.LOGIN,
                success=False,
                error_message="Invalid or expired token",
                details={"ip_address": request.client.host if request.client else None}
            )
        
        return user


class AuthenticationService:
    """
    Service for handling authentication operations.
    """
    
    def __init__(self):
        self.access_control = get_access_control()
        self.audit_logger = get_audit_logger()
    
    def create_user_token(
        self,
        user_id: str,
        role: Role,
        farmer_id: Optional[str] = None,
        expires_in_hours: int = 24
    ) -> str:
        """
        Create JWT token for user.
        
        Args:
            user_id: User identifier
            role: User role
            farmer_id: Farmer ID (for farmer users)
            expires_in_hours: Token expiration time in hours
            
        Returns:
            JWT token string
        """
        user = self.access_control.create_user(
            user_id=user_id,
            role=role,
            farmer_id=farmer_id
        )
        
        secret_key = settings.jwt_secret_key
        token = self.access_control.generate_token(
            user=user,
            secret_key=secret_key,
            expires_in_hours=expires_in_hours
        )
        
        # Log token creation
        self.audit_logger.log_security_event(
            user_id=user_id,
            user_role=role.value,
            action=AuditAction.TOKEN_REFRESH,
            success=True,
            details={"expires_in_hours": expires_in_hours}
        )
        
        return token
    
    def authenticate_farmer(
        self,
        phone_number: str,
        farmer_id: str
    ) -> str:
        """
        Authenticate farmer and create token.
        
        Args:
            phone_number: Farmer's phone number
            farmer_id: Farmer's ID
            
        Returns:
            JWT token string
        """
        # In a real implementation, this would verify the farmer's credentials
        # For now, we'll create a token assuming valid credentials
        
        return self.create_user_token(
            user_id=farmer_id,
            role=Role.FARMER,
            farmer_id=farmer_id
        )
    
    def authenticate_agent(
        self,
        agent_id: str,
        credentials: str
    ) -> str:
        """
        Authenticate agent and create token.
        
        Args:
            agent_id: Agent's ID
            credentials: Agent's credentials
            
        Returns:
            JWT token string
        """
        # In a real implementation, this would verify the agent's credentials
        # For now, we'll create a token assuming valid credentials
        
        return self.create_user_token(
            user_id=agent_id,
            role=Role.AGENT
        )
    
    def authenticate_admin(
        self,
        admin_id: str,
        credentials: str
    ) -> str:
        """
        Authenticate admin and create token.
        
        Args:
            admin_id: Admin's ID
            credentials: Admin's credentials
            
        Returns:
            JWT token string
        """
        # In a real implementation, this would verify the admin's credentials
        # For now, we'll create a token assuming valid credentials
        
        return self.create_user_token(
            user_id=admin_id,
            role=Role.ADMIN
        )


# Global authentication service instance
_auth_service = None


def get_auth_service() -> AuthenticationService:
    """Get global authentication service instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthenticationService()
    return _auth_service