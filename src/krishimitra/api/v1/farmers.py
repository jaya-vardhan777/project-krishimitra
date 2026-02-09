"""
Farmer management endpoints for KrishiMitra API.

This module handles farmer profile creation, retrieval, and updates
with integrated security features including encryption, access control,
and audit logging.
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
from ...core.security import (
    get_current_user, require_permission, require_farmer_access,
    get_encryption_service, get_audit_logger
)
from ...core.security.access_control import User, Permission
from ...core.security.audit import AuditAction
from ...core.security.encryption import FieldEncryption

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


def get_field_encryption():
    """Get field encryption service."""
    encryption_service = get_encryption_service()
    return FieldEncryption(encryption_service)


@router.post("/farmers", response_model=FarmerProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_farmer_profile(
    farmer_profile: FarmerProfile,
    current_user: User = Depends(get_current_user),
    dynamodb=Depends(get_dynamodb_client),
    field_encryption=Depends(get_field_encryption)
) -> FarmerProfileResponse:
    """Create a new farmer profile with encryption and audit logging."""
    
    # Check permissions
    if not current_user.has_permission(Permission.UPDATE_FARMER_PROFILE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create farmer profile"
        )
    
    farmer_id = str(uuid.uuid4())
    current_time = datetime.utcnow()
    
    # Convert to dict for encryption
    profile_data = {
        "farmer_id": farmer_id,
        "name": farmer_profile.name,
        "phone_number": farmer_profile.phone_number,
        "location": {
            "state": farmer_profile.location.state,
            "district": farmer_profile.location.district,
            "village": farmer_profile.location.village,
            "latitude": farmer_profile.location.latitude,
            "longitude": farmer_profile.location.longitude
        },
        "farm_details": {
            "total_land_area": farmer_profile.farm_details.total_land_area,
            "soil_type": farmer_profile.farm_details.soil_type,
            "irrigation_type": farmer_profile.farm_details.irrigation_type,
            "crops": [
                {
                    "crop_type": crop.crop_type,
                    "area": crop.area,
                    "planting_date": crop.planting_date.isoformat() if crop.planting_date else None,
                    "expected_harvest": crop.expected_harvest.isoformat() if crop.expected_harvest else None
                }
                for crop in farmer_profile.farm_details.crops
            ]
        },
        "preferences": {
            "organic_farming": farmer_profile.preferences.organic_farming,
            "risk_tolerance": farmer_profile.preferences.risk_tolerance,
            "preferred_language": farmer_profile.preferences.preferred_language
        }
    }
    
    # Encrypt sensitive fields
    encrypted_data = field_encryption.encrypt_farmer_profile(profile_data)
    
    # Prepare DynamoDB item with encrypted data
    item = {
        "farmerId": {"S": farmer_id},
        "name": {"S": encrypted_data["name"]},
        "phoneNumber": {"S": encrypted_data["phone_number"]},
        "location": {
            "M": {
                "state": {"S": encrypted_data["location"]["state"]},
                "district": {"S": encrypted_data["location"]["district"]},
                "village": {"S": encrypted_data["location"]["village"]}
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
        "updatedAt": {"S": current_time.isoformat()},
        "createdBy": {"S": current_user.user_id}
    }
    
    # Add optional encrypted location coordinates
    if encrypted_data["location"]["latitude"] is not None:
        item["location"]["M"]["latitude"] = {"S": encrypted_data["location"]["latitude"]}
    if encrypted_data["location"]["longitude"] is not None:
        item["location"]["M"]["longitude"] = {"S": encrypted_data["location"]["longitude"]}
    
    try:
        # Store in DynamoDB
        dynamodb.put_item(
            TableName=settings.farmer_profiles_table,
            Item=item,
            ConditionExpression="attribute_not_exists(farmerId)"
        )
        
        # Log the creation
        audit_logger = get_audit_logger()
        audit_logger.log_data_modification(
            user_id=current_user.user_id,
            user_role=current_user.role.value,
            action=AuditAction.CREATE,
            resource_type="farmer_profile",
            resource_id=farmer_id,
            new_values={"name": farmer_profile.name, "phone_number": "***masked***"}
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
    current_user: User = Depends(get_current_user),
    dynamodb=Depends(get_dynamodb_client),
    field_encryption=Depends(get_field_encryption)
) -> FarmerProfileResponse:
    """Get farmer profile by ID with access control and decryption."""
    
    # Check access permissions
    if not current_user.can_access_farmer_data(farmer_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to farmer data"
        )
    
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
        
        # Extract encrypted data
        encrypted_data = {
            "name": item["name"]["S"],
            "phone_number": item["phoneNumber"]["S"],
            "location": {
                "state": item["location"]["M"]["state"]["S"],
                "district": item["location"]["M"]["district"]["S"],
                "village": item["location"]["M"]["village"]["S"],
                "latitude": item["location"]["M"].get("latitude", {}).get("S"),
                "longitude": item["location"]["M"].get("longitude", {}).get("S")
            }
        }
        
        # Decrypt sensitive fields
        decrypted_data = field_encryption.decrypt_farmer_profile(encrypted_data)
        
        # Parse location coordinates
        latitude = None
        longitude = None
        if decrypted_data["location"]["latitude"]:
            try:
                latitude = float(decrypted_data["location"]["latitude"])
            except (ValueError, TypeError):
                pass
        if decrypted_data["location"]["longitude"]:
            try:
                longitude = float(decrypted_data["location"]["longitude"])
            except (ValueError, TypeError):
                pass
        
        # Parse DynamoDB item back to response model
        location = Location(
            state=decrypted_data["location"]["state"],
            district=decrypted_data["location"]["district"],
            village=decrypted_data["location"]["village"],
            latitude=latitude,
            longitude=longitude
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
        
        # Log the access
        audit_logger = get_audit_logger()
        audit_logger.log_data_access(
            user_id=current_user.user_id,
            user_role=current_user.role.value,
            action=AuditAction.READ,
            resource_type="farmer_profile",
            resource_id=farmer_id
        )
        
        return FarmerProfileResponse(
            farmer_id=farmer_id,
            name=decrypted_data["name"],
            phone_number=decrypted_data["phone_number"],
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
    current_user: User = Depends(get_current_user),
    dynamodb=Depends(get_dynamodb_client),
    field_encryption=Depends(get_field_encryption)
) -> List[FarmerProfileResponse]:
    """List farmer profiles with pagination and access control."""
    
    # Check permissions
    if not current_user.has_permission(Permission.LIST_FARMER_PROFILES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to list farmer profiles"
        )
    
    try:
        response = dynamodb.scan(
            TableName=settings.farmer_profiles_table,
            Limit=min(limit, 100)  # Cap at 100 items
        )
        
        profiles = []
        for item in response.get("Items", []):
            farmer_id = item["farmerId"]["S"]
            
            # Check access to each farmer's data
            if not current_user.can_access_farmer_data(farmer_id):
                continue
            
            # Extract and decrypt sensitive data
            encrypted_data = {
                "name": item["name"]["S"],
                "phone_number": item["phoneNumber"]["S"],
                "location": {
                    "state": item["location"]["M"]["state"]["S"],
                    "district": item["location"]["M"]["district"]["S"],
                    "village": item["location"]["M"]["village"]["S"],
                    "latitude": item["location"]["M"].get("latitude", {}).get("S"),
                    "longitude": item["location"]["M"].get("longitude", {}).get("S")
                }
            }
            
            decrypted_data = field_encryption.decrypt_farmer_profile(encrypted_data)
            
            # Parse location coordinates
            latitude = None
            longitude = None
            if decrypted_data["location"]["latitude"]:
                try:
                    latitude = float(decrypted_data["location"]["latitude"])
                except (ValueError, TypeError):
                    pass
            if decrypted_data["location"]["longitude"]:
                try:
                    longitude = float(decrypted_data["location"]["longitude"])
                except (ValueError, TypeError):
                    pass
            
            location = Location(
                state=decrypted_data["location"]["state"],
                district=decrypted_data["location"]["district"],
                village=decrypted_data["location"]["village"],
                latitude=latitude,
                longitude=longitude
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
                farmer_id=farmer_id,
                name=decrypted_data["name"],
                phone_number=decrypted_data["phone_number"],
                location=location,
                farm_details=farm_details,
                preferences=preferences,
                created_at=datetime.fromisoformat(item["createdAt"]["S"]),
                updated_at=datetime.fromisoformat(item["updatedAt"]["S"])
            ))
        
        # Log the list access
        audit_logger = get_audit_logger()
        audit_logger.log_data_access(
            user_id=current_user.user_id,
            user_role=current_user.role.value,
            action=AuditAction.LIST,
            resource_type="farmer_profile",
            details={"count": len(profiles), "limit": limit}
        )
        
        return profiles
        
    except ClientError as e:
        logger.error(f"Failed to list farmer profiles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve farmer profiles"
        )


@router.put("/farmers/{farmer_id}", response_model=FarmerProfileResponse)
async def update_farmer_profile(
    farmer_id: str,
    farmer_profile: FarmerProfile,
    current_user: User = Depends(get_current_user),
    dynamodb=Depends(get_dynamodb_client),
    field_encryption=Depends(get_field_encryption)
) -> FarmerProfileResponse:
    """Update farmer profile with encryption and audit logging."""
    
    # Check access permissions
    if not current_user.can_access_farmer_data(farmer_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to farmer data"
        )
    
    # Check update permissions
    if not current_user.has_permission(Permission.UPDATE_FARMER_PROFILE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update farmer profile"
        )
    
    current_time = datetime.utcnow()
    
    # Get existing profile for audit logging
    try:
        existing_response = dynamodb.get_item(
            TableName=settings.farmer_profiles_table,
            Key={"farmerId": {"S": farmer_id}}
        )
        
        if "Item" not in existing_response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Farmer profile not found"
            )
        
        existing_item = existing_response["Item"]
        
    except ClientError as e:
        logger.error(f"Failed to get existing farmer profile {farmer_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve existing farmer profile"
        )
    
    # Convert to dict for encryption
    profile_data = {
        "farmer_id": farmer_id,
        "name": farmer_profile.name,
        "phone_number": farmer_profile.phone_number,
        "location": {
            "state": farmer_profile.location.state,
            "district": farmer_profile.location.district,
            "village": farmer_profile.location.village,
            "latitude": farmer_profile.location.latitude,
            "longitude": farmer_profile.location.longitude
        },
        "farm_details": {
            "total_land_area": farmer_profile.farm_details.total_land_area,
            "soil_type": farmer_profile.farm_details.soil_type,
            "irrigation_type": farmer_profile.farm_details.irrigation_type,
            "crops": [
                {
                    "crop_type": crop.crop_type,
                    "area": crop.area,
                    "planting_date": crop.planting_date.isoformat() if crop.planting_date else None,
                    "expected_harvest": crop.expected_harvest.isoformat() if crop.expected_harvest else None
                }
                for crop in farmer_profile.farm_details.crops
            ]
        },
        "preferences": {
            "organic_farming": farmer_profile.preferences.organic_farming,
            "risk_tolerance": farmer_profile.preferences.risk_tolerance,
            "preferred_language": farmer_profile.preferences.preferred_language
        }
    }
    
    # Encrypt sensitive fields
    encrypted_data = field_encryption.encrypt_farmer_profile(profile_data)
    
    # Prepare update expression
    update_expression = "SET #name = :name, phoneNumber = :phone, #location = :location, farmDetails = :farm_details, preferences = :preferences, updatedAt = :updated_at, updatedBy = :updated_by"
    expression_attribute_names = {
        "#name": "name",
        "#location": "location"
    }
    expression_attribute_values = {
        ":name": {"S": encrypted_data["name"]},
        ":phone": {"S": encrypted_data["phone_number"]},
        ":location": {
            "M": {
                "state": {"S": encrypted_data["location"]["state"]},
                "district": {"S": encrypted_data["location"]["district"]},
                "village": {"S": encrypted_data["location"]["village"]}
            }
        },
        ":farm_details": {
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
        ":preferences": {
            "M": {
                "organicFarming": {"BOOL": farmer_profile.preferences.organic_farming},
                "riskTolerance": {"S": farmer_profile.preferences.risk_tolerance},
                "preferredLanguage": {"S": farmer_profile.preferences.preferred_language}
            }
        },
        ":updated_at": {"S": current_time.isoformat()},
        ":updated_by": {"S": current_user.user_id}
    }
    
    # Add optional encrypted location coordinates
    if encrypted_data["location"]["latitude"] is not None:
        expression_attribute_values[":location"]["M"]["latitude"] = {"S": encrypted_data["location"]["latitude"]}
    if encrypted_data["location"]["longitude"] is not None:
        expression_attribute_values[":location"]["M"]["longitude"] = {"S": encrypted_data["location"]["longitude"]}
    
    try:
        # Update in DynamoDB
        dynamodb.update_item(
            TableName=settings.farmer_profiles_table,
            Key={"farmerId": {"S": farmer_id}},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ConditionExpression="attribute_exists(farmerId)"
        )
        
        # Log the update
        audit_logger = get_audit_logger()
        audit_logger.log_data_modification(
            user_id=current_user.user_id,
            user_role=current_user.role.value,
            action=AuditAction.UPDATE,
            resource_type="farmer_profile",
            resource_id=farmer_id,
            old_values={"name": existing_item["name"]["S"], "phone_number": "***masked***"},
            new_values={"name": farmer_profile.name, "phone_number": "***masked***"}
        )
        
        logger.info(f"Updated farmer profile: {farmer_id}")
        
        return FarmerProfileResponse(
            farmer_id=farmer_id,
            name=farmer_profile.name,
            phone_number=farmer_profile.phone_number,
            location=farmer_profile.location,
            farm_details=farmer_profile.farm_details,
            preferences=farmer_profile.preferences,
            created_at=datetime.fromisoformat(existing_item["createdAt"]["S"]),
            updated_at=current_time
        )
        
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Farmer profile not found"
            )
        logger.error(f"Failed to update farmer profile {farmer_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update farmer profile"
        )


@router.delete("/farmers/{farmer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_farmer_profile(
    farmer_id: str,
    current_user: User = Depends(get_current_user),
    dynamodb=Depends(get_dynamodb_client)
):
    """Delete farmer profile with access control and audit logging."""
    
    # Check access permissions
    if not current_user.can_access_farmer_data(farmer_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to farmer data"
        )
    
    # Check delete permissions
    if not current_user.has_permission(Permission.DELETE_FARMER_PROFILE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete farmer profile"
        )
    
    try:
        # Delete from DynamoDB
        dynamodb.delete_item(
            TableName=settings.farmer_profiles_table,
            Key={"farmerId": {"S": farmer_id}},
            ConditionExpression="attribute_exists(farmerId)"
        )
        
        # Log the deletion
        audit_logger = get_audit_logger()
        audit_logger.log_data_modification(
            user_id=current_user.user_id,
            user_role=current_user.role.value,
            action=AuditAction.DELETE,
            resource_type="farmer_profile",
            resource_id=farmer_id
        )
        
        logger.info(f"Deleted farmer profile: {farmer_id}")
        
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Farmer profile not found"
            )
        logger.error(f"Failed to delete farmer profile {farmer_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete farmer profile"
        )