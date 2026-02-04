"""
Farmer profile models for KrishiMitra platform.

This module contains all models related to farmer profiles, including
personal information, farm details, preferences, and contact information.
"""

from datetime import date, datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from decimal import Decimal

from pydantic import Field, field_validator, model_validator

from .base import BaseModel, TimestampedModel, Address, LanguageCode, MonetaryAmount, Measurement


class FarmingExperience(str, Enum):
    """Farming experience levels."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERIENCED = "experienced"
    EXPERT = "expert"


class SoilType(str, Enum):
    """Soil types common in India."""
    ALLUVIAL = "alluvial"
    BLACK_COTTON = "black_cotton"
    RED_LATERITE = "red_laterite"
    SANDY = "sandy"
    CLAY = "clay"
    LOAMY = "loamy"
    SALINE = "saline"
    PEATY = "peaty"
    MOUNTAIN = "mountain"


class IrrigationType(str, Enum):
    """Irrigation types."""
    RAINFED = "rainfed"
    CANAL = "canal"
    TUBEWELL = "tubewell"
    WELL = "well"
    DRIP = "drip"
    SPRINKLER = "sprinkler"
    FLOOD = "flood"
    FURROW = "furrow"


class CropCategory(str, Enum):
    """Crop categories."""
    CEREALS = "cereals"
    PULSES = "pulses"
    OILSEEDS = "oilseeds"
    CASH_CROPS = "cash_crops"
    VEGETABLES = "vegetables"
    FRUITS = "fruits"
    SPICES = "spices"
    FODDER = "fodder"
    FLOWERS = "flowers"


class CropSeason(str, Enum):
    """Crop seasons in India."""
    KHARIF = "kharif"  # Monsoon season (June-October)
    RABI = "rabi"      # Winter season (November-April)
    ZAID = "zaid"      # Summer season (April-June)
    PERENNIAL = "perennial"  # Year-round crops


class RiskTolerance(str, Enum):
    """Risk tolerance levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CommunicationPreference(str, Enum):
    """Communication preferences."""
    VOICE = "voice"
    TEXT = "text"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    CALL = "call"


class ContactInfo(BaseModel):
    """Contact information for farmers."""
    
    primary_phone: str = Field(pattern=r"^\+91[6-9]\d{9}$", description="Primary phone number with country code")
    secondary_phone: Optional[str] = Field(default=None, pattern=r"^\+91[6-9]\d{9}$", description="Secondary phone number")
    whatsapp_number: Optional[str] = Field(default=None, pattern=r"^\+91[6-9]\d{9}$", description="WhatsApp number")
    email: Optional[str] = Field(default=None, pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", description="Email address")
    preferred_contact_method: CommunicationPreference = Field(default=CommunicationPreference.WHATSAPP, description="Preferred contact method")
    preferred_contact_time: Optional[str] = Field(default=None, description="Preferred contact time (e.g., 'morning', 'evening')")


class Location(BaseModel):
    """Location information for farmers."""
    
    address: Address = Field(description="Postal address")
    nearest_town: Optional[str] = Field(default=None, description="Nearest town or city")
    distance_to_town: Optional[Measurement] = Field(default=None, description="Distance to nearest town")
    connectivity: Optional[str] = Field(default=None, description="Internet/mobile connectivity quality")


class CropInfo(BaseModel):
    """Information about a specific crop."""
    
    crop_name: str = Field(description="Crop name (in local language or English)")
    crop_variety: Optional[str] = Field(default=None, description="Specific variety of the crop")
    category: CropCategory = Field(description="Crop category")
    season: CropSeason = Field(description="Growing season")
    area: Measurement = Field(description="Area under cultivation")
    planting_date: Optional[date] = Field(default=None, description="Planting/sowing date")
    expected_harvest_date: Optional[date] = Field(default=None, description="Expected harvest date")
    yield_expectation: Optional[Measurement] = Field(default=None, description="Expected yield")
    input_cost: Optional[MonetaryAmount] = Field(default=None, description="Input cost for this crop")
    market_price_expectation: Optional[MonetaryAmount] = Field(default=None, description="Expected market price")
    is_organic: bool = Field(default=False, description="Whether the crop is grown organically")
    irrigation_method: Optional[IrrigationType] = Field(default=None, description="Irrigation method for this crop")
    
    @field_validator('expected_harvest_date')
    @classmethod
    def validate_harvest_date(cls, v, info):
        if v and 'planting_date' in info.data and info.data['planting_date']:
            if v <= info.data['planting_date']:
                raise ValueError('Harvest date must be after planting date')
        return v


class FarmDetails(BaseModel):
    """Detailed information about the farm."""
    
    total_land_area: Measurement = Field(description="Total land area")
    cultivable_area: Optional[Measurement] = Field(default=None, description="Cultivable land area")
    irrigated_area: Optional[Measurement] = Field(default=None, description="Irrigated land area")
    soil_type: SoilType = Field(description="Primary soil type")
    soil_ph: Optional[float] = Field(default=None, ge=0, le=14, description="Soil pH level")
    soil_health_card_number: Optional[str] = Field(default=None, description="Soil health card number")
    primary_irrigation_source: IrrigationType = Field(description="Primary irrigation source")
    water_availability: Optional[str] = Field(default=None, description="Water availability status")
    farm_equipment: List[str] = Field(default_factory=list, description="Available farm equipment")
    storage_facilities: List[str] = Field(default_factory=list, description="Storage facilities available")
    crops: List[CropInfo] = Field(default_factory=list, description="Current and planned crops")
    livestock: Optional[Dict[str, int]] = Field(default=None, description="Livestock count by type")
    farm_certification: List[str] = Field(default_factory=list, description="Farm certifications (organic, etc.)")
    
    @field_validator('cultivable_area')
    @classmethod
    def validate_cultivable_area(cls, v, info):
        if v and 'total_land_area' in info.data:
            if v.value > info.data['total_land_area'].value:
                raise ValueError('Cultivable area cannot exceed total land area')
        return v
    
    @field_validator('irrigated_area')
    @classmethod
    def validate_irrigated_area(cls, v, info):
        if v and 'cultivable_area' in info.data and info.data['cultivable_area']:
            if v.value > info.data['cultivable_area'].value:
                raise ValueError('Irrigated area cannot exceed cultivable area')
        elif v and 'total_land_area' in info.data:
            if v.value > info.data['total_land_area'].value:
                raise ValueError('Irrigated area cannot exceed total land area')
        return v


class Preferences(BaseModel):
    """Farmer preferences and settings."""
    
    preferred_language: LanguageCode = Field(default_factory=LanguageCode.hindi, description="Preferred language")
    secondary_languages: List[LanguageCode] = Field(default_factory=list, description="Secondary languages")
    organic_farming_interest: bool = Field(default=False, description="Interest in organic farming")
    sustainable_practices_interest: bool = Field(default=True, description="Interest in sustainable practices")
    technology_adoption_willingness: RiskTolerance = Field(default=RiskTolerance.MEDIUM, description="Willingness to adopt new technology")
    risk_tolerance: RiskTolerance = Field(default=RiskTolerance.MEDIUM, description="Risk tolerance for farming decisions")
    budget_constraints: Optional[MonetaryAmount] = Field(default=None, description="Budget constraints for investments")
    preferred_communication_time: List[str] = Field(default_factory=lambda: ["morning", "evening"], description="Preferred communication times")
    notification_preferences: Dict[str, bool] = Field(
        default_factory=lambda: {
            "weather_alerts": True,
            "market_prices": True,
            "pest_warnings": True,
            "government_schemes": True,
            "seasonal_advice": True
        },
        description="Notification preferences"
    )
    privacy_settings: Dict[str, bool] = Field(
        default_factory=lambda: {
            "share_data_for_research": False,
            "share_success_stories": False,
            "allow_contact_from_buyers": True,
            "allow_contact_from_ngos": True
        },
        description="Privacy settings"
    )


class FarmerProfile(TimestampedModel):
    """Complete farmer profile model."""
    
    # Personal Information
    name: str = Field(min_length=2, max_length=100, description="Farmer's full name")
    father_name: Optional[str] = Field(default=None, max_length=100, description="Father's name")
    date_of_birth: Optional[date] = Field(default=None, description="Date of birth")
    gender: Optional[str] = Field(default=None, pattern=r"^(male|female|other)$", description="Gender")
    education_level: Optional[str] = Field(default=None, description="Education level")
    farming_experience: FarmingExperience = Field(default=FarmingExperience.INTERMEDIATE, description="Farming experience level")
    
    # Contact and Location
    contact_info: ContactInfo = Field(description="Contact information")
    location: Location = Field(description="Location information")
    
    # Farm Details
    farm_details: FarmDetails = Field(description="Farm details")
    
    # Preferences
    preferences: Preferences = Field(default_factory=Preferences, description="Farmer preferences")
    
    # Government IDs and Registrations
    aadhaar_number: Optional[str] = Field(default=None, pattern=r"^\d{12}$", description="12-digit Aadhaar number")
    pan_number: Optional[str] = Field(default=None, pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", description="PAN number")
    kisan_credit_card: Optional[str] = Field(default=None, description="Kisan Credit Card number")
    pm_kisan_beneficiary_id: Optional[str] = Field(default=None, description="PM-KISAN beneficiary ID")
    
    # Financial Information
    annual_income: Optional[MonetaryAmount] = Field(default=None, description="Annual income from farming")
    bank_account_details: Optional[Dict[str, str]] = Field(default=None, description="Bank account details")
    insurance_policies: List[str] = Field(default_factory=list, description="Insurance policies")
    
    # Platform-specific
    registration_source: Optional[str] = Field(default=None, description="How the farmer registered (WhatsApp, web, etc.)")
    verification_status: str = Field(default="pending", pattern=r"^(pending|verified|rejected)$", description="Verification status")
    last_active: Optional[datetime] = Field(default=None, description="Last activity timestamp")
    total_interactions: int = Field(default=0, ge=0, description="Total interactions with the platform")
    
    @field_validator('date_of_birth')
    @classmethod
    def validate_age(cls, v):
        if v:
            today = date.today()
            age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
            if age < 18 or age > 100:
                raise ValueError('Farmer must be between 18 and 100 years old')
        return v
    
    @model_validator(mode='after')
    def validate_profile_completeness(self):
        """Validate that essential information is provided."""
        required_fields = ['name', 'contact_info', 'location', 'farm_details']
        for field in required_fields:
            if not getattr(self, field, None):
                raise ValueError(f'{field} is required for farmer profile')
        return self


class FarmerProfileCreate(BaseModel):
    """Model for creating a new farmer profile."""
    
    name: str = Field(min_length=2, max_length=100, description="Farmer's full name")
    contact_info: ContactInfo = Field(description="Contact information")
    location: Location = Field(description="Location information")
    farm_details: FarmDetails = Field(description="Farm details")
    preferences: Optional[Preferences] = Field(default=None, description="Farmer preferences")
    
    # Optional fields
    father_name: Optional[str] = Field(default=None, max_length=100, description="Father's name")
    date_of_birth: Optional[date] = Field(default=None, description="Date of birth")
    gender: Optional[str] = Field(default=None, pattern=r"^(male|female|other)$", description="Gender")
    education_level: Optional[str] = Field(default=None, description="Education level")
    farming_experience: Optional[FarmingExperience] = Field(default=None, description="Farming experience level")
    registration_source: Optional[str] = Field(default=None, description="Registration source")


class FarmerProfileUpdate(BaseModel):
    """Model for updating farmer profile."""
    
    name: Optional[str] = Field(default=None, min_length=2, max_length=100, description="Farmer's full name")
    contact_info: Optional[ContactInfo] = Field(default=None, description="Contact information")
    location: Optional[Location] = Field(default=None, description="Location information")
    farm_details: Optional[FarmDetails] = Field(default=None, description="Farm details")
    preferences: Optional[Preferences] = Field(default=None, description="Farmer preferences")
    
    # Optional fields
    father_name: Optional[str] = Field(default=None, max_length=100, description="Father's name")
    date_of_birth: Optional[date] = Field(default=None, description="Date of birth")
    gender: Optional[str] = Field(default=None, pattern=r"^(male|female|other)$", description="Gender")
    education_level: Optional[str] = Field(default=None, description="Education level")
    farming_experience: Optional[FarmingExperience] = Field(default=None, description="Farming experience level")


class FarmerProfileResponse(FarmerProfile):
    """Model for farmer profile API responses."""
    
    # Hide sensitive information in responses
    aadhaar_number: Optional[str] = Field(default=None, exclude=True)
    pan_number: Optional[str] = Field(default=None, exclude=True)
    bank_account_details: Optional[Dict[str, str]] = Field(default=None, exclude=True)
    
    class Config:
        # Include computed fields
        fields = {
            'aadhaar_number': {'write_only': True},
            'pan_number': {'write_only': True},
            'bank_account_details': {'write_only': True}
        }