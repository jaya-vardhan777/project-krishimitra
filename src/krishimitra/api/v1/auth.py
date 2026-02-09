"""
Authentication endpoints for KrishiMitra API.

This module handles user authentication, token generation,
and security-related operations.
"""

import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field

from ...core.middleware import get_auth_service, AuthenticationService
from ...core.security.access_control import Role, User, get_current_user
from ...core.security.audit import get_audit_logger, AuditAction

logger = logging.getLogger(__name__)
router = APIRouter()


class LoginRequest(BaseModel):
    """Login request model."""
    user_type: str = Field(pattern="^(farmer|agent|admin)$", description="Type of user")
    identifier: str = Field(description="User identifier (phone number, email, etc.)")
    credentials: str = Field(description="User credentials (password, OTP, etc.)")


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # 24 hours in seconds
    user_id: str
    role: str
    farmer_id: Optional[str] = None


class FarmerLoginRequest(BaseModel):
    """Farmer-specific login request."""
    phone_number: str = Field(pattern=r"^\+91[6-9]\d{9}$", description="Farmer's phone number")
    otp: str = Field(min_length=4, max_length=6, description="OTP for verification")


class AgentLoginRequest(BaseModel):
    """Agent-specific login request."""
    agent_id: str = Field(description="Agent identifier")
    password: str = Field(min_length=8, description="Agent password")


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    auth_service: AuthenticationService = Depends(get_auth_service)
) -> TokenResponse:
    """
    General login endpoint for all user types.
    
    This endpoint handles authentication for farmers, agents, and admins
    with appropriate credential validation and token generation.
    """
    try:
        if request.user_type == "farmer":
            # For farmers, identifier is phone number and credentials is OTP
            # In a real implementation, we would verify the OTP
            token = auth_service.authenticate_farmer(
                phone_number=request.identifier,
                farmer_id=request.identifier  # Using phone as farmer_id for simplicity
            )
            
            return TokenResponse(
                access_token=token,
                user_id=request.identifier,
                role="farmer",
                farmer_id=request.identifier
            )
            
        elif request.user_type == "agent":
            # For agents, identifier is agent_id and credentials is password
            token = auth_service.authenticate_agent(
                agent_id=request.identifier,
                credentials=request.credentials
            )
            
            return TokenResponse(
                access_token=token,
                user_id=request.identifier,
                role="agent"
            )
            
        elif request.user_type == "admin":
            # For admins, identifier is admin_id and credentials is password
            token = auth_service.authenticate_admin(
                admin_id=request.identifier,
                credentials=request.credentials
            )
            
            return TokenResponse(
                access_token=token,
                user_id=request.identifier,
                role="admin"
            )
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user type"
            )
    
    except Exception as e:
        logger.error(f"Login failed for {request.user_type} {request.identifier}: {e}")
        
        # Log failed login attempt
        audit_logger = get_audit_logger()
        audit_logger.log_security_event(
            user_id=request.identifier,
            user_role=request.user_type,
            action=AuditAction.LOGIN,
            success=False,
            error_message=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


@router.post("/auth/farmer/login", response_model=TokenResponse)
async def farmer_login(
    request: FarmerLoginRequest,
    auth_service: AuthenticationService = Depends(get_auth_service)
) -> TokenResponse:
    """
    Farmer-specific login endpoint with OTP verification.
    
    This endpoint is optimized for farmer authentication using
    phone number and OTP verification.
    """
    try:
        # In a real implementation, we would:
        # 1. Verify the OTP against what was sent to the phone number
        # 2. Check if the farmer exists in the database
        # 3. Create or update the farmer's session
        
        # For now, we'll simulate successful OTP verification
        if len(request.otp) < 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP"
            )
        
        token = auth_service.authenticate_farmer(
            phone_number=request.phone_number,
            farmer_id=request.phone_number  # Using phone as farmer_id for simplicity
        )
        
        return TokenResponse(
            access_token=token,
            user_id=request.phone_number,
            role="farmer",
            farmer_id=request.phone_number
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Farmer login failed for {request.phone_number}: {e}")
        
        # Log failed login attempt
        audit_logger = get_audit_logger()
        audit_logger.log_security_event(
            user_id=request.phone_number,
            user_role="farmer",
            action=AuditAction.LOGIN,
            success=False,
            error_message=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


@router.post("/auth/agent/login", response_model=TokenResponse)
async def agent_login(
    request: AgentLoginRequest,
    auth_service: AuthenticationService = Depends(get_auth_service)
) -> TokenResponse:
    """
    Agent-specific login endpoint with password authentication.
    
    This endpoint handles authentication for agricultural agents
    and extension officers.
    """
    try:
        # In a real implementation, we would:
        # 1. Hash and verify the password
        # 2. Check agent credentials against the database
        # 3. Validate agent permissions and status
        
        token = auth_service.authenticate_agent(
            agent_id=request.agent_id,
            credentials=request.password
        )
        
        return TokenResponse(
            access_token=token,
            user_id=request.agent_id,
            role="agent"
        )
    
    except Exception as e:
        logger.error(f"Agent login failed for {request.agent_id}: {e}")
        
        # Log failed login attempt
        audit_logger = get_audit_logger()
        audit_logger.log_security_event(
            user_id=request.agent_id,
            user_role="agent",
            action=AuditAction.LOGIN,
            success=False,
            error_message=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


@router.post("/auth/logout")
async def logout(
    current_user: User = Depends(get_current_user)
):
    """
    Logout endpoint to invalidate user session.
    
    In a real implementation, this would invalidate the JWT token
    by adding it to a blacklist or revoking it.
    """
    # Log the logout
    audit_logger = get_audit_logger()
    audit_logger.log_security_event(
        user_id=current_user.user_id,
        user_role=current_user.role.value,
        action=AuditAction.LOGOUT,
        success=True
    )
    
    logger.info(f"User {current_user.user_id} logged out")
    
    return {"message": "Successfully logged out"}


@router.get("/auth/me", response_model=dict)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Get current user information.
    
    Returns information about the currently authenticated user
    including their role and permissions.
    """
    return {
        "user_id": current_user.user_id,
        "role": current_user.role.value,
        "farmer_id": current_user.farmer_id,
        "permissions": [p.value for p in current_user.permissions]
    }


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(
    current_user: User = Depends(get_current_user),
    auth_service: AuthenticationService = Depends(get_auth_service)
) -> TokenResponse:
    """
    Refresh JWT token for authenticated user.
    
    Generates a new token with extended expiration time
    for the current user.
    """
    try:
        token = auth_service.create_user_token(
            user_id=current_user.user_id,
            role=current_user.role,
            farmer_id=current_user.farmer_id
        )
        
        return TokenResponse(
            access_token=token,
            user_id=current_user.user_id,
            role=current_user.role.value,
            farmer_id=current_user.farmer_id
        )
    
    except Exception as e:
        logger.error(f"Token refresh failed for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh token"
        )