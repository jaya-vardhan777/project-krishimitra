"""
Data models for KrishiMitra platform.

This module contains all Pydantic models used throughout the application
for data validation, serialization, and API documentation.
"""

from .farmer import (
    FarmerProfile,
    FarmerProfileCreate,
    FarmerProfileUpdate,
    FarmerProfileResponse,
    Location,
    CropInfo,
    FarmDetails,
    Preferences,
    ContactInfo
)

from .agricultural_intelligence import (
    AgriculturalIntelligence,
    WeatherData,
    SoilData,
    MarketData,
    SatelliteData,
    SensorReading,
    CropHealthAnalysis
)

from .recommendation import (
    RecommendationRecord,
    RecommendationRequest,
    RecommendationResponse,
    RecommendationFeedback,
    ActionItem,
    RecommendationType
)

from .conversation import (
    ConversationMessage,
    ConversationHistory,
    MessageType,
    MessageContent,
    VoiceMessage,
    ImageMessage,
    TextMessage
)

from .base import (
    BaseModel,
    TimestampedModel,
    PaginatedResponse,
    ErrorResponse
)

__all__ = [
    # Farmer models
    "FarmerProfile",
    "FarmerProfileCreate", 
    "FarmerProfileUpdate",
    "FarmerProfileResponse",
    "Location",
    "CropInfo",
    "FarmDetails",
    "Preferences",
    "ContactInfo",
    
    # Agricultural intelligence models
    "AgriculturalIntelligence",
    "WeatherData",
    "SoilData", 
    "MarketData",
    "SatelliteData",
    "SensorReading",
    "CropHealthAnalysis",
    
    # Recommendation models
    "RecommendationRecord",
    "RecommendationRequest",
    "RecommendationResponse", 
    "RecommendationFeedback",
    "ActionItem",
    "RecommendationType",
    
    # Conversation models
    "ConversationMessage",
    "ConversationHistory",
    "MessageType",
    "MessageContent",
    "VoiceMessage",
    "ImageMessage", 
    "TextMessage",
    
    # Base models
    "BaseModel",
    "TimestampedModel",
    "PaginatedResponse",
    "ErrorResponse"
]