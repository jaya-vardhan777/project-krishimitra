"""
KrishiMitra FastAPI Application

Main entry point for the KrishiMitra AI-powered agricultural platform.
This module sets up the FastAPI application with all necessary middleware,
routers, and AWS Lambda handler integration.
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum

from .core.config import get_settings
from .core.logging import setup_logging
from .api.v1 import health, farmers, recommendations, chat, voice, whatsapp

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Get application settings
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info(f"Starting KrishiMitra API in {settings.environment} environment")
    
    # Initialize AWS services connections
    try:
        # Test AWS connectivity
        import boto3
        session = boto3.Session()
        logger.info(f"AWS session initialized for region: {session.region_name}")
    except Exception as e:
        logger.error(f"Failed to initialize AWS session: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down KrishiMitra API")


# Create FastAPI application
app = FastAPI(
    title="KrishiMitra API",
    description="AI-powered agricultural advisory platform for rural farmers in India",
    version="1.0.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_hosts
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
            "request_id": getattr(request.state, "request_id", None)
        }
    )


# Include API routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(farmers.router, prefix="/api/v1", tags=["farmers"])
app.include_router(recommendations.router, prefix="/api/v1", tags=["recommendations"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(voice.router, prefix="/api/v1", tags=["voice"])
app.include_router(whatsapp.router, prefix="/api/v1", tags=["whatsapp"])


@app.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint providing API information."""
    return {
        "name": "KrishiMitra API",
        "version": "1.0.0",
        "description": "AI-powered agricultural advisory platform",
        "environment": settings.environment,
        "status": "healthy"
    }


# AWS Lambda handler
handler = Mangum(app, lifespan="off")


# For local development
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )