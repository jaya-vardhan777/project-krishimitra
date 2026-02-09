"""
IoT Device Management API endpoints for KrishiMitra Platform

This module provides REST API endpoints for managing IoT devices,
collecting sensor data, and monitoring device status.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from ...core.security.access_control import get_current_user, require_permission, Permission, User
from ...core.security.audit import log_data_modification, AuditAction
from ...iot.device_manager import DeviceManager, IoTDevice, DeviceStatus, DeviceType
from ...agents.data_ingestion import DataIngestionAgent
from ...models.farmer import FarmerProfile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/iot", tags=["IoT Devices"])


# Request/Response Models
class DeviceRegistrationRequest(BaseModel):
    """Request model for device registration"""
    device_name: str = Field(..., description="Human-readable device name")
    device_type: DeviceType = Field(..., description="Type of IoT device")
    farmer_id: str = Field(..., description="Associated farmer ID")
    location: Dict[str, float] = Field(..., description="GPS coordinates with lat/lng")
    firmware_version: Optional[str] = Field(None, description="Device firmware version")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Device configuration")


class DeviceResponse(BaseModel):
    """Response model for device information"""
    device_id: str
    device_name: str
    device_type: str
    farmer_id: str
    location: Dict[str, float]
    status: str
    last_seen: Optional[datetime]
    firmware_version: Optional[str]
    battery_level: Optional[float]
    configuration: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class DeviceStatusUpdate(BaseModel):
    """Request model for device status updates"""
    status: DeviceStatus = Field(..., description="New device status")
    battery_level: Optional[float] = Field(None, ge=0.0, le=100.0, description="Battery percentage")


class DeviceCommand(BaseModel):
    """Request model for sending commands to devices"""
    command_type: str = Field(..., description="Type of command")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Command parameters")


class SensorDataResponse(BaseModel):
    """Response model for sensor data"""
    sensor_id: str
    sensor_type: str
    value: float
    unit: str
    timestamp: datetime
    location: Optional[Dict[str, float]]
    quality_score: float


# Initialize services
device_manager = DeviceManager()
data_ingestion_agent = DataIngestionAgent()


@router.post("/devices", response_model=DeviceResponse)
@require_permission(Permission.MANAGE_SYSTEM)
async def register_device(
    request: DeviceRegistrationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Register a new IoT device"""
    try:
        # Generate unique device ID
        device_id = f"krishimitra-{request.device_type.value}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Create device object
        device = IoTDevice(
            device_id=device_id,
            device_name=request.device_name,
            device_type=request.device_type,
            farmer_id=request.farmer_id,
            location=request.location,
            firmware_version=request.firmware_version,
            configuration=request.configuration
        )
        
        # Register device
        success = await device_manager.register_device(device)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to register device")
        
        # Audit log
        background_tasks.add_task(
            log_data_modification,
            user_id=current_user.user_id,
            user_role=current_user.role.value,
            action=AuditAction.CREATE,
            resource_type="iot_device",
            resource_id=device_id,
            new_values={"device_type": request.device_type.value, "farmer_id": request.farmer_id}
        )
        
        # Convert to response model
        return DeviceResponse(
            device_id=device.device_id,
            device_name=device.device_name,
            device_type=device.device_type.value,
            farmer_id=device.farmer_id,
            location=device.location,
            status=device.status.value,
            last_seen=device.last_seen,
            firmware_version=device.firmware_version,
            battery_level=device.battery_level,
            configuration=device.configuration,
            created_at=device.created_at,
            updated_at=device.updated_at
        )
        
    except Exception as e:
        logger.error(f"Error registering device: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/devices/{device_id}", response_model=DeviceResponse)
@require_permission(Permission.READ_AGRICULTURAL_DATA)
async def get_device(
    device_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get device information by ID"""
    try:
        device = await device_manager.get_device(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        return DeviceResponse(
            device_id=device.device_id,
            device_name=device.device_name,
            device_type=device.device_type.value,
            farmer_id=device.farmer_id,
            location=device.location,
            status=device.status.value,
            last_seen=device.last_seen,
            firmware_version=device.firmware_version,
            battery_level=device.battery_level,
            configuration=device.configuration,
            created_at=device.created_at,
            updated_at=device.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/farmers/{farmer_id}/devices", response_model=List[DeviceResponse])
@require_permission(Permission.READ_AGRICULTURAL_DATA)
async def get_farmer_devices(
    farmer_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get all devices for a specific farmer"""
    try:
        devices = await device_manager.get_farmer_devices(farmer_id)
        
        return [
            DeviceResponse(
                device_id=device.device_id,
                device_name=device.device_name,
                device_type=device.device_type.value,
                farmer_id=device.farmer_id,
                location=device.location,
                status=device.status.value,
                last_seen=device.last_seen,
                firmware_version=device.firmware_version,
                battery_level=device.battery_level,
                configuration=device.configuration,
                created_at=device.created_at,
                updated_at=device.updated_at
            )
            for device in devices
        ]
        
    except Exception as e:
        logger.error(f"Error retrieving devices for farmer {farmer_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/devices/{device_id}/status")
@require_permission(Permission.UPDATE_AGRICULTURAL_DATA)
async def update_device_status(
    device_id: str,
    request: DeviceStatusUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Update device status and battery level"""
    try:
        success = await device_manager.update_device_status(
            device_id, 
            request.status, 
            request.battery_level
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update device status")
        
        # Audit log
        background_tasks.add_task(
            log_data_modification,
            user_id=current_user.user_id,
            user_role=current_user.role.value,
            action=AuditAction.UPDATE,
            resource_type="iot_device",
            resource_id=device_id,
            new_values={"status": request.status.value, "battery_level": request.battery_level}
        )
        
        return {"message": "Device status updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating device status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/devices/{device_id}/commands")
@require_permission(Permission.MANAGE_SYSTEM)
async def send_device_command(
    device_id: str,
    command: DeviceCommand,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Send command to IoT device"""
    try:
        # Prepare command payload
        command_payload = {
            "command_type": command.command_type,
            "parameters": command.parameters,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "issued_by": current_user.user_id
        }
        
        success = await device_manager.send_command_to_device(device_id, command_payload)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to send command to device")
        
        # Audit log
        background_tasks.add_task(
            log_data_modification,
            user_id=current_user.user_id,
            user_role=current_user.role.value,
            action=AuditAction.UPDATE,
            resource_type="iot_device",
            resource_id=device_id,
            new_values={"command_type": command.command_type, "parameters": command.parameters}
        )
        
        return {"message": "Command sent successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending command to device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/devices/{device_id}/shadow")
@require_permission(Permission.READ_AGRICULTURAL_DATA)
async def get_device_shadow(
    device_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get current device shadow state"""
    try:
        shadow = await device_manager.get_device_shadow(device_id)
        if not shadow:
            raise HTTPException(status_code=404, detail="Device shadow not found")
        
        return shadow
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving device shadow: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/devices/{device_id}")
@require_permission(Permission.MANAGE_SYSTEM)
async def delete_device(
    device_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Delete IoT device"""
    try:
        success = await device_manager.delete_device(device_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete device")
        
        # Audit log
        background_tasks.add_task(
            log_data_modification,
            user_id=current_user.user_id,
            user_role=current_user.role.value,
            action=AuditAction.DELETE,
            resource_type="iot_device",
            resource_id=device_id
        )
        
        return {"message": "Device deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/devices/{device_id}/sensor-data", response_model=List[SensorDataResponse])
@require_permission(Permission.READ_AGRICULTURAL_DATA)
async def get_device_sensor_data(
    device_id: str,
    hours: int = 24,
    current_user: User = Depends(get_current_user)
):
    """Get recent sensor data from a specific device"""
    try:
        # Get device info first to verify it exists
        device = await device_manager.get_device(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        # Get sensor data based on device type
        sensor_readings = await data_ingestion_agent.get_recent_sensor_data(
            device.device_type.value, 
            hours
        )
        
        # Filter by device ID
        device_readings = [
            reading for reading in sensor_readings 
            if reading.device_id == device_id
        ]
        
        return [
            SensorDataResponse(
                sensor_id=reading.device_id,
                sensor_type=reading.sensor_type.value,
                value=reading.value,
                unit=reading.unit,
                timestamp=reading.timestamp,
                location={
                    'latitude': reading.location.latitude,
                    'longitude': reading.location.longitude
                },
                quality_score=reading.quality or 100
            )
            for reading in device_readings
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving sensor data for device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/data/collect/{device_id}")
@require_permission(Permission.UPDATE_AGRICULTURAL_DATA)
async def trigger_data_collection(
    device_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Manually trigger data collection from a specific device"""
    try:
        # Verify device exists
        device = await device_manager.get_device(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        # Trigger data collection in background
        async def collect_data():
            try:
                sensor_readings = await data_ingestion_agent.collect_all_sensor_data([device_id])
                logger.info(f"Collected {len(sensor_readings)} readings from device {device_id}")
            except Exception as e:
                logger.error(f"Error in background data collection: {e}")
        
        background_tasks.add_task(collect_data)
        
        # Audit log
        background_tasks.add_task(
            log_data_modification,
            user_id=current_user.user_id,
            user_role=current_user.role.value,
            action=AuditAction.UPDATE,
            resource_type="iot_device",
            resource_id=device_id,
            new_values={"action": "data_collection_triggered"}
        )
        
        return {"message": "Data collection triggered successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering data collection: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")