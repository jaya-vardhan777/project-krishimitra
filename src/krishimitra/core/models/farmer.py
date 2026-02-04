"""
Farmer profile data models using Pydantic.

This module defines the FarmerProfile model and related sub-models for storing
farmer information, farm details, and preferences in DynamoDB.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field, validator, ConfigDict
from pydantic.types import constr, confloat, conint


class IrrigationType(str, Enum):
    """Enumeration of irrigation types."""
    DRIP = "drip"
    SPRINKLER = "sprinkler"
    FLOOD = "flood"
    RAINFED = "rainfed"
    CANAL = "canal"
    BOREWELL = "borewell"


class SoilType(str, Enum):
    """Enumeration of soil types common in India."""
    ALLUVIAL = "alluvial"
    BLACK_COTTON = "black_cotton"
    RED_LATERITE = "red_laterite"
    SANDY = "sandy"
    CLAY = "clay"
    LOAMY = "loamy"
    SALINE = "saline"


class RiskTolerance(str, Enum):
    """Farmer's risk tolerance levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Location(BaseModel):
    """Geographic location information."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True
    )
    
    state: constr(min_length=1, max_length=50) = Field(..., description="Indian state name")
    district: constr(min_length=1, max_length=50) = Field(..., description="District name")
    village: constr(min_length=1, max_length=100) = Field(..., description="Village name")
    latitude: confloat(ge=-90, le=90) = Field(..., description="Latitude coordinate")
    longitude: confloat(ge=-180, le=180) = Field(..., description="Longitude coordinate")
    
    @validator('state', 'district', 'village')
    def validate_location_names(cls, v):
        """Validate location names are not empty after stripping."""
        if not v or not v.strip():
            raise ValueError("Location names cannot be empty")
        return v.strip()


class CropInfo(BaseModel):
    """Information about a specific crop."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    crop_type: constr(min_length=1, max_length=50) = Field(..., description="Type of crop (e.g., rice, wheat)")
    area: confloat(gt=0, le=10000) = Field(..., description="Area in acres")
    planting_date: Optional[date] = Field(None, description="Date when crop was planted")
    expected_harvest: Optional[date] = Field(None, description="Expected harvest date")
    variety: Optional[constr(max_length=100)] = Field(None, description="Crop variety")
    
    @validator('expected_harvest')
    def validate_harvest_date(cls, v, values):
        """Ensure harvest date is after planting date."""
        if v and 'planting_date' in values and values['planting_date']:
            if v <= values['planting_date']:
                raise ValueError("Harvest date must be after planting date")
        return v


class Preferences(BaseModel):
    """Farmer preferences and constraints."""
    model_config = ConfigDict(validate_assignment=True)
    
    organic_farming: bool = Field(False, description="Preference for organic farming methods")
    risk_tolerance: RiskTolerance = Field(RiskTolerance.MEDIUM, description="Risk tolerance level")
    budget_constraints: Dict[str, Any] = Field(default_factory=dict, description="Budget limitations")
    preferred_language: constr(min_length=2, max_length=10) = Field("hi", description="ISO language code")
    notification_preferences: Dict[str, bool] = Field(
        default_factory=lambda: {
            "weather_alerts": True,
            "market_updates": True,
            "scheme_notifications": True,
            "pest_warnings": True
        },
        description="Notification preferences"
    )


class FarmDetails(BaseModel):
    """Detailed information about the farm."""
    model_config = ConfigDict(validate_assignment=True)
    
    total_land_area: confloat(gt=0, le=10000) = Field(..., description="Total land area in acres")
    soil_type: SoilType = Field(..., description="Primary soil type")
    irrigation_type: IrrigationType = Field(..., description="Primary irrigation method")
    crops: List[CropInfo] = Field(default_factory=list, description="List of crops grown")
    water_source: Optional[constr(max_length=100)] = Field(None, description="Primary water source")
    farm_equipment: List[str] = Field(default_factory=list, description="Available farm equipment")
    
    @validator('crops')
    def validate_total_crop_area(cls, v, values):
        """Ensure total crop area doesn't exceed farm area."""
        if v and 'total_land_area' in values:
            total_crop_area = sum(crop.area for crop in v)
            if total_crop_area > values['total_land_area']:
                raise ValueError("Total crop area cannot exceed farm area")
        return v


class PersonalInfo(BaseModel):
    """Personal information of the farmer."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    name: constr(min_length=1, max_length=100) = Field(..., description="Farmer's full name")
    phone_number: constr(regex=r'^\+91[6-9]\d{9}$') = Field(..., description="Indian mobile number with country code")
    preferred_language: constr(min_length=2, max_length=10) = Field("hi", description="ISO language code")
    location: Location = Field(..., description="Geographic location")
    age: Optional[conint(ge=18, le=100)] = Field(None, description="Age in years")
    education_level: Optional[constr(max_length=50)] = Field(None, description="Education level")
    
    @validator('name')
    def validate_name(cls, v):
        """Validate name is not empty after stripping."""
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()


class FarmerProfile(BaseModel):
    """Complete farmer profile model."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True
    )
    
    farmer_id: constr(min_length=1, max_length=50) = Field(..., description="Unique farmer identifier")
    personal_info: PersonalInfo = Field(..., description="Personal information")
    farm_details: FarmDetails = Field(..., description="Farm details")
    preferences: Preferences = Field(default_factory=Preferences, description="Farmer preferences")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Profile creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    is_active: bool = Field(True, description="Whether the profile is active")
    
    @validator('updated_at', always=True)
    def set_updated_at(cls, v):
        """Always set updated_at to current time."""
        return datetime.utcnow()
    
    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = self.model_dump()
        
        # Convert datetime objects to ISO strings for DynamoDB
        item['created_at'] = self.created_at.isoformat()
        item['updated_at'] = self.updated_at.isoformat()
        
        # Convert Decimal fields for DynamoDB compatibility
        def convert_floats_to_decimal(obj):
            if isinstance(obj, dict):
                return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_floats_to_decimal(item) for item in obj]
            elif isinstance(obj, float):
                return Decimal(str(obj))
            return obj
        
        return convert_floats_to_decimal(item)
    
    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> 'FarmerProfile':
        """Create instance from DynamoDB item."""
        # Convert ISO strings back to datetime objects
        if 'created_at' in item and isinstance(item['created_at'], str):
            item['created_at'] = datetime.fromisoformat(item['created_at'])
        if 'updated_at' in item and isinstance(item['updated_at'], str):
            item['updated_at'] = datetime.fromisoformat(item['updated_at'])
        
        # Convert Decimal back to float
        def convert_decimal_to_float(obj):
            if isinstance(obj, dict):
                return {k: convert_decimal_to_float(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_decimal_to_float(item) for item in obj]
            elif isinstance(obj, Decimal):
                return float(obj)
            return obj
        
        item = convert_decimal_to_float(item)
        return cls(**item)