"""
Configuration management for KrishiMitra application.

This module handles all application configuration including environment variables,
AWS service configurations, and environment-specific settings.
"""

import os
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings and configuration."""
    
    # Environment
    environment: str = Field(default="development", env="ENV")
    debug: bool = Field(default=False, env="DEBUG")
    
    # API Configuration
    api_title: str = "KrishiMitra API"
    api_version: str = "1.0.0"
    allowed_origins: List[str] = Field(default=["*"], env="ALLOWED_ORIGINS")
    allowed_hosts: List[str] = Field(default=["*"], env="ALLOWED_HOSTS")
    
    # AWS Configuration
    aws_region: str = Field(default="ap-south-1", env="AWS_REGION")
    
    # DynamoDB Tables
    farmer_profiles_table: str = Field(default="test-farmer-profiles", env="FARMER_PROFILES_TABLE")
    conversations_table: str = Field(default="test-conversations", env="CONVERSATIONS_TABLE")
    recommendations_table: str = Field(default="test-recommendations", env="RECOMMENDATIONS_TABLE")
    sensor_readings_table: str = Field(default="test-sensor-readings", env="SENSOR_READINGS_TABLE")
    
    # S3 Buckets
    agricultural_imagery_bucket: str = Field(default="test-agricultural-imagery", env="AGRICULTURAL_IMAGERY_BUCKET")
    weather_data_bucket: str = Field(default="test-weather-data", env="WEATHER_DATA_BUCKET")
    market_data_bucket: str = Field(default="test-market-data", env="MARKET_DATA_BUCKET")
    model_artifacts_bucket: str = Field(default="test-model-artifacts", env="MODEL_ARTIFACTS_BUCKET")
    
    # Cognito Configuration
    user_pool_id: str = Field(default="test-user-pool", env="USER_POOL_ID")
    user_pool_client_id: str = Field(default="test-user-pool-client", env="USER_POOL_CLIENT_ID")
    
    # Bedrock Configuration
    bedrock_model_id: str = Field(
        default="anthropic.claude-3-5-sonnet-20241022-v2:0",
        env="BEDROCK_MODEL_ID"
    )
    bedrock_region: str = Field(default="us-east-1", env="BEDROCK_REGION")
    
    # Voice Processing Configuration
    transcribe_language_codes: List[str] = Field(
        default=[
            "hi-IN",  # Hindi
            "ta-IN",  # Tamil
            "te-IN",  # Telugu
            "bn-IN",  # Bengali
            "mr-IN",  # Marathi
            "gu-IN",  # Gujarati
            "pa-IN"   # Punjabi
        ],
        env="TRANSCRIBE_LANGUAGE_CODES"
    )
    
    # WhatsApp Configuration
    whatsapp_verify_token: Optional[str] = Field(default=None, env="WHATSAPP_VERIFY_TOKEN")
    whatsapp_access_token: Optional[str] = Field(default=None, env="WHATSAPP_ACCESS_TOKEN")
    whatsapp_phone_number_id: Optional[str] = Field(default=None, env="WHATSAPP_PHONE_NUMBER_ID")
    
    # External API Configuration
    weather_api_key: Optional[str] = Field(default=None, env="WEATHER_API_KEY")
    market_api_key: Optional[str] = Field(default=None, env="MARKET_API_KEY")
    
    # Logging Configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()