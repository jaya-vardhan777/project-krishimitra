"""
Health check endpoints for KrishiMitra Platform.

This module provides health check endpoints for monitoring and load balancing.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""
    
    status: str
    service: str
    version: str
    environment: str


@router.get("/", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Basic health check endpoint.
    
    Returns:
        Health status information
    """
    return HealthResponse(
        status="healthy",
        service="krishimitra-platform",
        version="1.0.0",
        environment="development",  # This should come from settings
    )


@router.get("/ready", response_model=HealthResponse)
async def readiness_check() -> HealthResponse:
    """
    Readiness check endpoint for Kubernetes deployments.
    
    This endpoint should verify that all dependencies are available
    (database connections, external APIs, etc.).
    
    Returns:
        Readiness status information
    """
    # TODO: Add actual dependency checks
    # - Database connectivity
    # - AWS services availability
    # - Redis connectivity
    # - External API availability
    
    return HealthResponse(
        status="ready",
        service="krishimitra-platform",
        version="1.0.0",
        environment="development",
    )


@router.get("/live", response_model=HealthResponse)
async def liveness_check() -> HealthResponse:
    """
    Liveness check endpoint for Kubernetes deployments.
    
    This endpoint should only fail if the application is completely broken
    and needs to be restarted.
    
    Returns:
        Liveness status information
    """
    return HealthResponse(
        status="alive",
        service="krishimitra-platform",
        version="1.0.0",
        environment="development",
    )