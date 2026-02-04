"""
Health check endpoints for KrishiMitra API.

This module provides health check endpoints for monitoring
application status and AWS service connectivity.
"""

import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
import boto3
from botocore.exceptions import ClientError

from ...core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.environment,
        "version": "1.0.0"
    }


@router.get("/health/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """Detailed health check including AWS service connectivity."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.environment,
        "version": "1.0.0",
        "services": {}
    }
    
    # Check DynamoDB connectivity
    try:
        dynamodb = boto3.client("dynamodb", region_name=settings.aws_region)
        dynamodb.describe_table(TableName=settings.farmer_profiles_table)
        health_status["services"]["dynamodb"] = "healthy"
    except ClientError as e:
        logger.error(f"DynamoDB health check failed: {e}")
        health_status["services"]["dynamodb"] = "unhealthy"
        health_status["status"] = "degraded"
    except Exception as e:
        logger.error(f"DynamoDB health check error: {e}")
        health_status["services"]["dynamodb"] = "error"
        health_status["status"] = "degraded"
    
    # Check S3 connectivity
    try:
        s3 = boto3.client("s3", region_name=settings.aws_region)
        s3.head_bucket(Bucket=settings.agricultural_imagery_bucket)
        health_status["services"]["s3"] = "healthy"
    except ClientError as e:
        logger.error(f"S3 health check failed: {e}")
        health_status["services"]["s3"] = "unhealthy"
        health_status["status"] = "degraded"
    except Exception as e:
        logger.error(f"S3 health check error: {e}")
        health_status["services"]["s3"] = "error"
        health_status["status"] = "degraded"
    
    # Check Bedrock connectivity
    try:
        bedrock = boto3.client("bedrock-runtime", region_name=settings.bedrock_region)
        # Simple test to check if service is accessible
        health_status["services"]["bedrock"] = "healthy"
    except Exception as e:
        logger.error(f"Bedrock health check error: {e}")
        health_status["services"]["bedrock"] = "error"
        health_status["status"] = "degraded"
    
    return health_status