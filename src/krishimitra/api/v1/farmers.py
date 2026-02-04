"""
Farmer management endpoints for KrishiMitra API.

This module handles farmer profile creation, retrieval, and updates.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
import boto3
from botocore.exceptions import ClientError

from ...core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


class Location(BaseModel):
    """Farmer location information."""
    state: str
    district: str
    village: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class CropInfo(BaseModel):
    """Crop information."""
    crop_type: str
    area: float = Field(gt=0, description="Area in acres")
    planting_date: Optional[datetime] = None
    expected_harvest: Optional[datetime] = None


class FarmDetails(BaseModel):
    """Farm details information."""
    total_land_area: float = Field(gt=0, description="Total land area in acres")
    soil_type: str
    irrigation_type: str
    crops: List[CropInfo] = []


class Preferences(BaseModel):
    """Farmer preferences."""
    organic_farming: bool = False
    risk_tolerance: str = Field(default="medium", pattern="^(low|medium|high)$")
    preferred_language: str = Field(default="hi", pattern="^(hi|ta|te|bn|mr|gu|pa)$")


class FarmerProfile(BaseModel):
    """Complete farmer profile."""
    name: str
    phone_number: str = Field(pattern="^[+]?[1-9]\\d{1,14}$")
    location: Location
    farm_details: FarmDetails
    preferences: Preferences


class FarmerProfileResponse(BaseModel):
    """Farmer profile response."""
    farmer_id: str
    name: str
    phone_number: str
    location: Location
    farm_details: FarmDetails
    preferences: Preferences
    created_at: datetime
    updated_at: datetime


def get_dynamodb_client():
    """Get DynamoDB client."""
    return boto3.client("dynamodb", region_name=settings.aws_region)


@router.post("/farmers", response_model=FarmerProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_farmer_profile(
    farmer_profile: FarmerProfile,
    dynamodb=Depends(get_dynamodb_client)
) -> FarmerProfileResponse:
    """Create a new farmer profile."""
    
    farmer_id = str(uuid.uuid4())
    current_time = datetime.utcnow()
    
    # Prepare DynamoDB item
    item = {
        "farmerId": {"S": farmer_id},
        "name": {"S": farmer_profile.name},
        "phoneNumber": {"S": farmer_profile.phone_number},
        "location": {
            "M": {
                "state": {"S": farmer_profile.location.state},
                "district": {"S": farmer_profile.location.district},
                "village": {"S": farmer_profile.location.village}
            }
        },
        "farmDetails": {
            "M": {
                "totalLandArea": {"N": str(farmer_profile.farm_details.total_land_area)},
                "soilType": {"S": farmer_profile.farm_details.soil_type},
                "irrigationType": {"S": farmer_profile.farm_details.irrigation_type},
                "crops": {
                    "L": [
                        {
                            "M": {
                                "cropType": {"S": crop.crop_type},
                                "area": {"N": str(crop.area)}
                            }
                        }
                        for crop in farmer_profile.farm_details.crops
                    ]
                }
            }
        },
        "preferences": {
            "M": {
                "organicFarming": {"BOOL": farmer_profile.preferences.organic_farming},
                "riskTolerance": {"S": farmer_profile.preferences.risk_tolerance},
                "preferredLanguage": {"S": farmer_profile.preferences.preferred_language}
            }
        },
        "createdAt": {"S": current_time.isoformat()},
        "updatedAt": {"S": current_time.isoformat()}
    }
    
    # Add optional location coordinates
    if farmer_profile.location.latitude is not None:
        item["location"]["M"]["latitude"] = {"N": str(farmer_profile.location.latitude)}
    if farmer_profile.location.longitude is not None:
        item["location"]["M"]["longitude"] = {"N": str(farmer_profile.location.longitude)}
    
    try:
        # Store in DynamoDB
        dynamodb.put_item(
            TableName=settings.farmer_profiles_table,
            Item=item,
            ConditionExpression="attribute_not_exists(farmerId)"
        )
        
        logger.info(f"Created farmer profile: {farmer_id}")
        
        return FarmerProfileResponse(
            farmer_id=farmer_id,
            name=farmer_profile.name,
            phone_number=farmer_profile.phone_number,
            location=farmer_profile.location,
            farm_details=farmer_profile.farm_details,
            preferences=farmer_profile.preferences,
            created_at=current_time,
            updated_at=current_time
        )
        
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Farmer profile already exists"
            )
        logger.error(f"Failed to create farmer profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create farmer profile"
        )


@router.get("/farmers/{farmer_id}", response_model=FarmerProfileResponse)
async def get_farmer_profile(
    farmer_id: str,
    dynamodb=Depends(get_dynamodb_client)
) -> FarmerProfileResponse:
    """Get farmer profile by ID."""
    
    try:
        response = dynamodb.get_item(
            TableName=settings.farmer_profiles_table,
            Key={"farmerId": {"S": farmer_id}}
        )
        
        if "Item" not in response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Farmer profile not found"
            )
        
        item = response["Item"]
        
        # Parse DynamoDB item back to response model
        location = Location(
            state=item["location"]["M"]["state"]["S"],
            district=item["location"]["M"]["district"]["S"],
            village=item["location"]["M"]["village"]["S"],
            latitude=float(item["location"]["M"]["latitude"]["N"]) if "latitude" in item["location"]["M"] else None,
            longitude=float(item["location"]["M"]["longitude"]["N"]) if "longitude" in item["location"]["M"] else None
        )
        
        crops = [
            CropInfo(
                crop_type=crop["M"]["cropType"]["S"],
                area=float(crop["M"]["area"]["N"])
            )
            for crop in item["farmDetails"]["M"]["crops"]["L"]
        ]
        
        farm_details = FarmDetails(
            total_land_area=float(item["farmDetails"]["M"]["totalLandArea"]["N"]),
            soil_type=item["farmDetails"]["M"]["soilType"]["S"],
            irrigation_type=item["farmDetails"]["M"]["irrigationType"]["S"],
            crops=crops
        )
        
        preferences = Preferences(
            organic_farming=item["preferences"]["M"]["organicFarming"]["BOOL"],
            risk_tolerance=item["preferences"]["M"]["riskTolerance"]["S"],
            preferred_language=item["preferences"]["M"]["preferredLanguage"]["S"]
        )
        
        return FarmerProfileResponse(
            farmer_id=farmer_id,
            name=item["name"]["S"],
            phone_number=item["phoneNumber"]["S"],
            location=location,
            farm_details=farm_details,
            preferences=preferences,
            created_at=datetime.fromisoformat(item["createdAt"]["S"]),
            updated_at=datetime.fromisoformat(item["updatedAt"]["S"])
        )
        
    except ClientError as e:
        logger.error(f"Failed to get farmer profile {farmer_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve farmer profile"
        )


@router.get("/farmers", response_model=List[FarmerProfileResponse])
async def list_farmer_profiles(
    limit: int = 10,
    dynamodb=Depends(get_dynamodb_client)
) -> List[FarmerProfileResponse]:
    """List farmer profiles with pagination."""
    
    try:
        response = dynamodb.scan(
            TableName=settings.farmer_profiles_table,
            Limit=min(limit, 100)  # Cap at 100 items
        )
        
        profiles = []
        for item in response.get("Items", []):
            # Parse each item (similar to get_farmer_profile)
            location = Location(
                state=item["location"]["M"]["state"]["S"],
                district=item["location"]["M"]["district"]["S"],
                village=item["location"]["M"]["village"]["S"],
                latitude=float(item["location"]["M"]["latitude"]["N"]) if "latitude" in item["location"]["M"] else None,
                longitude=float(item["location"]["M"]["longitude"]["N"]) if "longitude" in item["location"]["M"] else None
            )
            
            crops = [
                CropInfo(
                    crop_type=crop["M"]["cropType"]["S"],
                    area=float(crop["M"]["area"]["N"])
                )
                for crop in item["farmDetails"]["M"]["crops"]["L"]
            ]
            
            farm_details = FarmDetails(
                total_land_area=float(item["farmDetails"]["M"]["totalLandArea"]["N"]),
                soil_type=item["farmDetails"]["M"]["soilType"]["S"],
                irrigation_type=item["farmDetails"]["M"]["irrigationType"]["S"],
                crops=crops
            )
            
            preferences = Preferences(
                organic_farming=item["preferences"]["M"]["organicFarming"]["BOOL"],
                risk_tolerance=item["preferences"]["M"]["riskTolerance"]["S"],
                preferred_language=item["preferences"]["M"]["preferredLanguage"]["S"]
            )
            
            profiles.append(FarmerProfileResponse(
                farmer_id=item["farmerId"]["S"],
                name=item["name"]["S"],
                phone_number=item["phoneNumber"]["S"],
                location=location,
                farm_details=farm_details,
                preferences=preferences,
                created_at=datetime.fromisoformat(item["createdAt"]["S"]),
                updated_at=datetime.fromisoformat(item["updatedAt"]["S"])
            ))
        
        return profiles
        
    except ClientError as e:
        logger.error(f"Failed to list farmer profiles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve farmer profiles"
        )