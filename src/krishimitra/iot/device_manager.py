"""
IoT Device Management for KrishiMitra Platform

This module handles IoT device connectivity, message routing, and device fleet management
using AWS IoT Core services.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from enum import Enum

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

from ..core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class DeviceStatus(str, Enum):
    """Device status enumeration"""
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    ERROR = "error"


class DeviceType(str, Enum):
    """Device type enumeration"""
    SOIL_SENSOR = "soil_sensor"
    WEATHER_STATION = "weather_station"
    IRRIGATION_CONTROLLER = "irrigation_controller"
    CAMERA = "camera"
    GATEWAY = "gateway"


class IoTDevice(BaseModel):
    """IoT Device model"""
    device_id: str = Field(..., description="Unique device identifier")
    device_name: str = Field(..., description="Human-readable device name")
    device_type: DeviceType = Field(..., description="Type of IoT device")
    farmer_id: str = Field(..., description="Associated farmer ID")
    location: Dict[str, float] = Field(..., description="GPS coordinates")
    status: DeviceStatus = Field(default=DeviceStatus.OFFLINE)
    last_seen: Optional[datetime] = Field(None, description="Last communication timestamp")
    firmware_version: Optional[str] = Field(None, description="Device firmware version")
    battery_level: Optional[float] = Field(None, ge=0.0, le=100.0, description="Battery percentage")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Device configuration")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DeviceManager:
    """Manages IoT devices using AWS IoT Core"""
    
    def __init__(self):
        self.iot_client = boto3.client('iot', region_name=settings.aws_region)
        self.iot_data_client = boto3.client('iot-data', region_name=settings.aws_region)
        self.dynamodb = boto3.resource('dynamodb', region_name=settings.aws_region)
        self.devices_table = self.dynamodb.Table('IoTDevices')
    
    async def register_device(self, device: IoTDevice) -> bool:
        """Register a new IoT device with AWS IoT Core"""
        try:
            # Create thing in AWS IoT Core
            thing_response = self.iot_client.create_thing(
                thingName=device.device_id,
                thingTypeName=device.device_type.value,
                attributePayload={
                    'attributes': {
                        'device_name': device.device_name,
                        'farmer_id': device.farmer_id,
                        'location': json.dumps(device.location),
                        'device_type': device.device_type.value
                    }
                }
            )
            
            # Create and attach certificate
            cert_response = self.iot_client.create_keys_and_certificate(setAsActive=True)
            certificate_arn = cert_response['certificateArn']
            
            # Create policy for the device
            policy_name = f"{device.device_id}-policy"
            policy_document = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "iot:Connect",
                            "iot:Publish",
                            "iot:Subscribe",
                            "iot:Receive"
                        ],
                        "Resource": [
                            f"arn:aws:iot:{settings.aws_region}:{settings.aws_account_id}:client/{device.device_id}",
                            f"arn:aws:iot:{settings.aws_region}:{settings.aws_account_id}:topic/krishimitra/sensors/{device.device_id}/*",
                            f"arn:aws:iot:{settings.aws_region}:{settings.aws_account_id}:topicfilter/krishimitra/sensors/{device.device_id}/*"
                        ]
                    }
                ]
            }
            
            self.iot_client.create_policy(
                policyName=policy_name,
                policyDocument=json.dumps(policy_document)
            )
            
            # Attach policy to certificate
            self.iot_client.attach_policy(
                policyName=policy_name,
                target=certificate_arn
            )
            
            # Attach certificate to thing
            self.iot_client.attach_thing_principal(
                thingName=device.device_id,
                principal=certificate_arn
            )
            
            # Store device information in DynamoDB
            device_item = {
                'device_id': device.device_id,
                'device_name': device.device_name,
                'device_type': device.device_type.value,
                'farmer_id': device.farmer_id,
                'location': device.location,
                'status': device.status.value,
                'certificate_arn': certificate_arn,
                'configuration': device.configuration,
                'created_at': int(device.created_at.timestamp()),
                'updated_at': int(device.updated_at.timestamp())
            }
            
            if device.firmware_version:
                device_item['firmware_version'] = device.firmware_version
            if device.battery_level is not None:
                device_item['battery_level'] = device.battery_level
            if device.last_seen:
                device_item['last_seen'] = int(device.last_seen.timestamp())
            
            self.devices_table.put_item(Item=device_item)
            
            logger.info(f"Successfully registered device {device.device_id}")
            return True
            
        except ClientError as e:
            logger.error(f"Error registering device {device.device_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error registering device: {e}")
            return False
    
    async def get_device(self, device_id: str) -> Optional[IoTDevice]:
        """Get device information by ID"""
        try:
            response = self.devices_table.get_item(Key={'device_id': device_id})
            
            if 'Item' not in response:
                return None
            
            item = response['Item']
            device = IoTDevice(
                device_id=item['device_id'],
                device_name=item['device_name'],
                device_type=DeviceType(item['device_type']),
                farmer_id=item['farmer_id'],
                location=item['location'],
                status=DeviceStatus(item['status']),
                configuration=item.get('configuration', {}),
                created_at=datetime.fromtimestamp(item['created_at'], tz=timezone.utc),
                updated_at=datetime.fromtimestamp(item['updated_at'], tz=timezone.utc)
            )
            
            if 'firmware_version' in item:
                device.firmware_version = item['firmware_version']
            if 'battery_level' in item:
                device.battery_level = float(item['battery_level'])
            if 'last_seen' in item:
                device.last_seen = datetime.fromtimestamp(item['last_seen'], tz=timezone.utc)
            
            return device
            
        except Exception as e:
            logger.error(f"Error retrieving device {device_id}: {e}")
            return None
    
    async def get_farmer_devices(self, farmer_id: str) -> List[IoTDevice]:
        """Get all devices for a specific farmer"""
        try:
            response = self.devices_table.query(
                IndexName='FarmerIdIndex',
                KeyConditionExpression='farmer_id = :farmer_id',
                ExpressionAttributeValues={':farmer_id': farmer_id}
            )
            
            devices = []
            for item in response['Items']:
                device = IoTDevice(
                    device_id=item['device_id'],
                    device_name=item['device_name'],
                    device_type=DeviceType(item['device_type']),
                    farmer_id=item['farmer_id'],
                    location=item['location'],
                    status=DeviceStatus(item['status']),
                    configuration=item.get('configuration', {}),
                    created_at=datetime.fromtimestamp(item['created_at'], tz=timezone.utc),
                    updated_at=datetime.fromtimestamp(item['updated_at'], tz=timezone.utc)
                )
                
                if 'firmware_version' in item:
                    device.firmware_version = item['firmware_version']
                if 'battery_level' in item:
                    device.battery_level = float(item['battery_level'])
                if 'last_seen' in item:
                    device.last_seen = datetime.fromtimestamp(item['last_seen'], tz=timezone.utc)
                
                devices.append(device)
            
            return devices
            
        except Exception as e:
            logger.error(f"Error retrieving devices for farmer {farmer_id}: {e}")
            return []
    
    async def update_device_status(self, device_id: str, status: DeviceStatus, 
                                 battery_level: Optional[float] = None) -> bool:
        """Update device status and battery level"""
        try:
            update_expression = "SET #status = :status, updated_at = :updated_at, last_seen = :last_seen"
            expression_values = {
                ':status': status.value,
                ':updated_at': int(datetime.now(timezone.utc).timestamp()),
                ':last_seen': int(datetime.now(timezone.utc).timestamp())
            }
            expression_names = {'#status': 'status'}
            
            if battery_level is not None:
                update_expression += ", battery_level = :battery_level"
                expression_values[':battery_level'] = battery_level
            
            self.devices_table.update_item(
                Key={'device_id': device_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values,
                ExpressionAttributeNames=expression_names
            )
            
            logger.info(f"Updated status for device {device_id} to {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating device status: {e}")
            return False
    
    async def send_command_to_device(self, device_id: str, command: Dict[str, Any]) -> bool:
        """Send command to IoT device via shadow update"""
        try:
            shadow_update = {
                "state": {
                    "desired": command
                }
            }
            
            self.iot_data_client.update_thing_shadow(
                thingName=device_id,
                payload=json.dumps(shadow_update)
            )
            
            logger.info(f"Sent command to device {device_id}: {command}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending command to device {device_id}: {e}")
            return False
    
    async def get_device_shadow(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get current device shadow state"""
        try:
            response = self.iot_data_client.get_thing_shadow(thingName=device_id)
            shadow_data = json.loads(response['payload'].read())
            return shadow_data
            
        except Exception as e:
            logger.error(f"Error getting shadow for device {device_id}: {e}")
            return None
    
    async def delete_device(self, device_id: str) -> bool:
        """Delete device from AWS IoT Core and DynamoDB"""
        try:
            # Get device info first
            device = await self.get_device(device_id)
            if not device:
                logger.warning(f"Device {device_id} not found")
                return False
            
            # Detach and delete certificate
            try:
                # List principals attached to thing
                principals_response = self.iot_client.list_thing_principals(thingName=device_id)
                
                for principal in principals_response['principals']:
                    # Detach certificate from thing
                    self.iot_client.detach_thing_principal(
                        thingName=device_id,
                        principal=principal
                    )
                    
                    # Get certificate ID from ARN
                    cert_id = principal.split('/')[-1]
                    
                    # Detach policies from certificate
                    policies_response = self.iot_client.list_attached_policies(target=principal)
                    for policy in policies_response['policies']:
                        self.iot_client.detach_policy(
                            policyName=policy['policyName'],
                            target=principal
                        )
                        
                        # Delete policy if it's device-specific
                        if policy['policyName'].startswith(device_id):
                            self.iot_client.delete_policy(policyName=policy['policyName'])
                    
                    # Deactivate and delete certificate
                    self.iot_client.update_certificate(
                        certificateId=cert_id,
                        newStatus='INACTIVE'
                    )
                    self.iot_client.delete_certificate(certificateId=cert_id)
                    
            except ClientError as e:
                logger.warning(f"Error cleaning up certificates for device {device_id}: {e}")
            
            # Delete thing from IoT Core
            self.iot_client.delete_thing(thingName=device_id)
            
            # Delete from DynamoDB
            self.devices_table.delete_item(Key={'device_id': device_id})
            
            logger.info(f"Successfully deleted device {device_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting device {device_id}: {e}")
            return False


class MessageRouter:
    """Routes IoT messages to appropriate handlers"""
    
    def __init__(self):
        self.device_manager = DeviceManager()
        self.message_handlers = {}
    
    def register_handler(self, message_type: str, handler_func):
        """Register a message handler for a specific message type"""
        self.message_handlers[message_type] = handler_func
        logger.info(f"Registered handler for message type: {message_type}")
    
    async def route_message(self, topic: str, payload: Dict[str, Any]) -> bool:
        """Route incoming IoT message to appropriate handler"""
        try:
            # Extract device ID and message type from topic
            # Expected topic format: krishimitra/sensors/{device_id}/{message_type}
            topic_parts = topic.split('/')
            if len(topic_parts) < 4:
                logger.warning(f"Invalid topic format: {topic}")
                return False
            
            device_id = topic_parts[2]
            message_type = topic_parts[3]
            
            # Update device last seen timestamp
            await self.device_manager.update_device_status(
                device_id, 
                DeviceStatus.ONLINE
            )
            
            # Route to appropriate handler
            if message_type in self.message_handlers:
                handler = self.message_handlers[message_type]
                await handler(device_id, payload)
                logger.info(f"Routed message from {device_id} to {message_type} handler")
                return True
            else:
                logger.warning(f"No handler registered for message type: {message_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error routing message: {e}")
            return False
    
    async def handle_sensor_data(self, device_id: str, payload: Dict[str, Any]):
        """Default handler for sensor data messages"""
        logger.info(f"Received sensor data from {device_id}: {payload}")
        # This would typically trigger the data ingestion agent
        # Implementation depends on the specific sensor data processing pipeline
    
    async def handle_device_status(self, device_id: str, payload: Dict[str, Any]):
        """Handler for device status messages"""
        status = payload.get('status', 'online')
        battery_level = payload.get('battery_level')
        
        device_status = DeviceStatus(status) if status in DeviceStatus.__members__.values() else DeviceStatus.ONLINE
        
        await self.device_manager.update_device_status(
            device_id, 
            device_status, 
            battery_level
        )
        
        logger.info(f"Updated status for device {device_id}: {status}")
    
    async def handle_alert(self, device_id: str, payload: Dict[str, Any]):
        """Handler for device alert messages"""
        alert_type = payload.get('alert_type', 'unknown')
        message = payload.get('message', '')
        severity = payload.get('severity', 'info')
        
        logger.warning(f"Alert from device {device_id}: {alert_type} - {message} (severity: {severity})")
        
        # Here you would typically:
        # 1. Store the alert in a database
        # 2. Notify relevant farmers or administrators
        # 3. Trigger automated responses if needed