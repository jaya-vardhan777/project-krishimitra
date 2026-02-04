"""
Data models for KrishiMitra platform.

This module contains Pydantic models for farmer profiles, agricultural intelligence,
and recommendation records, along with DynamoDB schema definitions.
"""

from .farmer import FarmerProfile, PersonalInfo, FarmDetails, Location, CropInfo, Preferences
from .agricultural_intelligence import AgriculturalIntelligence, WeatherData, SoilData, MarketData, SatelliteData
from .recommendation import RecommendationRecord, RecommendationContext, Recommendation, Feedback

__all__ = [
    "FarmerProfile",
    "PersonalInfo", 
    "FarmDetails",
    "Location",
    "CropInfo",
    "Preferences",
    "AgriculturalIntelligence",
    "WeatherData",
    "SoilData", 
    "MarketData",
    "SatelliteData",
    "RecommendationRecord",
    "RecommendationContext",
    "Recommendation",
    "Feedback",
]