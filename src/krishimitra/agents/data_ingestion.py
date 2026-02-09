"""
Data Ingestion Agent for KrishiMitra Platform

This module implements the Data Ingestion Agent responsible for collecting
real-time data from IoT sensors, weather APIs, satellite imagery, and market databases.
Uses LangChain tools for API integrations and data validation.
"""

import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field, validator
from langchain.tools import BaseTool
from pydantic import BaseModel as LangChainBaseModel

from ..core.config import get_settings
from ..models.agricultural_intelligence import AgriculturalIntelligence, SensorReading
from .weather_integration import WeatherAPIClient, WeatherDataTool, WeatherAnalysisChain
from .satellite_processing import SatelliteImageProcessor, SatelliteAnalysisTool
from .market_integration import MarketAPIClient, MarketDataTool, MarketIntelligenceAgent
from .government_integration import GovernmentAPIClient, GovernmentDataTool, GovernmentIntegrationAgent

logger = logging.getLogger(__name__)
settings = get_settings()


class IoTSensorData(BaseModel):
    """Model for IoT sensor data validation"""
    device_id: str = Field(..., description="Unique identifier for the IoT device")
    sensor_type: str = Field(..., description="Type of sensor (soil_moisture, ph, temperature, humidity)")
    value: float = Field(..., description="Sensor reading value")
    unit: str = Field(..., description="Unit of measurement")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    location: Optional[Dict[str, float]] = Field(None, description="GPS coordinates")
    quality_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Data quality score")

    @validator('sensor_type')
    def validate_sensor_type(cls, v):
        allowed_types = ['soil_moisture', 'ph', 'temperature', 'humidity', 'light', 'rainfall']
        if v not in allowed_types:
            raise ValueError(f'Sensor type must be one of {allowed_types}')
        return v

    @validator('value')
    def validate_sensor_value(cls, v, values):
        """Validate sensor values based on type"""
        sensor_type = values.get('sensor_type')
        if sensor_type == 'ph' and not (0 <= v <= 14):
            raise ValueError('pH value must be between 0 and 14')
        elif sensor_type == 'humidity' and not (0 <= v <= 100):
            raise ValueError('Humidity must be between 0 and 100 percent')
        elif sensor_type == 'temperature' and not (-50 <= v <= 70):
            raise ValueError('Temperature must be between -50 and 70 Celsius')
        elif sensor_type == 'soil_moisture' and not (0 <= v <= 100):
            raise ValueError('Soil moisture must be between 0 and 100 percent')
        return v


class IoTDataCollector:
    """Handles IoT sensor data collection using AWS IoT Core"""
    
    def __init__(self):
        self.iot_client = boto3.client('iot-data', region_name=settings.aws_region)
        self.kinesis_client = boto3.client('kinesis', region_name=settings.aws_region)
        self.dynamodb = boto3.resource('dynamodb', region_name=settings.aws_region)
        self.sensor_readings_table = self.dynamodb.Table('SensorReadings')
        
    async def collect_sensor_data(self, device_id: str) -> Optional[IoTSensorData]:
        """Collect data from a specific IoT device"""
        try:
            # Get the latest shadow document for the device
            response = self.iot_client.get_thing_shadow(thingName=device_id)
            shadow_data = json.loads(response['payload'].read())
            
            # Extract sensor data from shadow
            reported_state = shadow_data.get('state', {}).get('reported', {})
            
            if not reported_state:
                logger.warning(f"No reported state found for device {device_id}")
                return None
                
            # Create IoTSensorData from shadow data
            sensor_data = IoTSensorData(
                device_id=device_id,
                sensor_type=reported_state.get('sensor_type', 'unknown'),
                value=reported_state.get('value', 0.0),
                unit=reported_state.get('unit', ''),
                timestamp=datetime.fromisoformat(reported_state.get('timestamp', datetime.now(timezone.utc).isoformat())),
                location=reported_state.get('location'),
                quality_score=reported_state.get('quality_score', 1.0)
            )
            
            return sensor_data
            
        except ClientError as e:
            logger.error(f"Error collecting data from device {device_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error collecting sensor data: {e}")
            return None
    
    async def validate_and_normalize_data(self, sensor_data: IoTSensorData) -> Optional[SensorReading]:
        """Validate and normalize sensor data"""
        try:
            # Perform data quality checks
            if sensor_data.quality_score < 0.5:
                logger.warning(f"Low quality data from device {sensor_data.device_id}, score: {sensor_data.quality_score}")
                return None
            
            # Check for anomalies based on historical data
            is_anomaly = await self._detect_anomaly(sensor_data)
            if is_anomaly:
                logger.warning(f"Anomaly detected in data from device {sensor_data.device_id}")
                sensor_data.quality_score *= 0.7  # Reduce quality score for anomalous data
            
            # Convert to normalized SensorReading model
            sensor_reading = SensorReading(
                device_id=sensor_data.device_id,
                sensor_type=sensor_data.sensor_type,
                location=sensor_data.location or {"latitude": 0.0, "longitude": 0.0},
                value=sensor_data.value,
                unit=sensor_data.unit,
                timestamp=sensor_data.timestamp,
                quality=sensor_data.quality_score * 100  # Convert to percentage
            )
            
            return sensor_reading
            
        except Exception as e:
            logger.error(f"Error validating sensor data: {e}")
            return None
    
    async def _detect_anomaly(self, sensor_data: IoTSensorData) -> bool:
        """Detect anomalies in sensor data using statistical methods"""
        try:
            # Query recent readings for the same sensor type and location
            response = self.sensor_readings_table.query(
                IndexName='SensorTypeTimestampIndex',
                KeyConditionExpression='sensor_type = :sensor_type AND #ts > :start_time',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':sensor_type': sensor_data.sensor_type,
                    ':start_time': (datetime.now(timezone.utc).timestamp() - 86400)  # Last 24 hours
                },
                Limit=100
            )
            
            if len(response['Items']) < 10:
                return False  # Not enough data for anomaly detection
            
            # Calculate statistical measures
            values = [float(item['value']) for item in response['Items']]
            mean_value = sum(values) / len(values)
            variance = sum((x - mean_value) ** 2 for x in values) / len(values)
            std_dev = variance ** 0.5
            
            # Check if current value is more than 3 standard deviations from mean
            z_score = abs(sensor_data.value - mean_value) / std_dev if std_dev > 0 else 0
            
            return z_score > 3.0
            
        except Exception as e:
            logger.error(f"Error in anomaly detection: {e}")
            return False
    
    async def store_sensor_data(self, sensor_reading: SensorReading) -> bool:
        """Store validated sensor data in DynamoDB"""
        try:
            item = {
                'device_id': sensor_reading.device_id,
                'timestamp': int(sensor_reading.timestamp.timestamp()),
                'sensor_type': sensor_reading.sensor_type.value,
                'value': Decimal(str(sensor_reading.value)),
                'unit': sensor_reading.unit,
                'quality': Decimal(str(sensor_reading.quality or 100)),
                'location': {
                    'latitude': sensor_reading.location.latitude,
                    'longitude': sensor_reading.location.longitude
                },
                'created_at': int(datetime.now(timezone.utc).timestamp())
            }
            
            self.sensor_readings_table.put_item(Item=item)
            logger.info(f"Stored sensor reading from {sensor_reading.device_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing sensor data: {e}")
            return False
    
    async def stream_to_kinesis(self, sensor_reading: SensorReading) -> bool:
        """Stream sensor data to Kinesis for real-time processing"""
        try:
            record = {
                'device_id': sensor_reading.device_id,
                'sensor_type': sensor_reading.sensor_type.value,
                'value': sensor_reading.value,
                'unit': sensor_reading.unit,
                'timestamp': sensor_reading.timestamp.isoformat(),
                'location': {
                    'latitude': sensor_reading.location.latitude,
                    'longitude': sensor_reading.location.longitude
                },
                'quality': sensor_reading.quality or 100
            }
            
            response = self.kinesis_client.put_record(
                StreamName='agricultural-sensor-stream',
                Data=json.dumps(record),
                PartitionKey=sensor_reading.device_id
            )
            
            logger.info(f"Streamed sensor data to Kinesis: {response['SequenceNumber']}")
            return True
            
        except Exception as e:
            logger.error(f"Error streaming to Kinesis: {e}")
            return False


class IoTDataCollectionTool(BaseTool, LangChainBaseModel):
    """LangChain tool for IoT data collection"""
    
    name: str = "iot_data_collection"
    description: str = "Collect and process data from IoT sensors in agricultural fields"
    
    def _run(self, device_id: str) -> str:
        """Run the IoT data collection tool"""
        async def collect_data():
            collector = IoTDataCollector()
            # Collect sensor data
            sensor_data = await collector.collect_sensor_data(device_id)
            if not sensor_data:
                return f"No data available from device {device_id}"
            
            # Validate and normalize
            sensor_reading = await collector.validate_and_normalize_data(sensor_data)
            if not sensor_reading:
                return f"Data validation failed for device {device_id}"
            
            # Store data
            stored = await collector.store_sensor_data(sensor_reading)
            streamed = await collector.stream_to_kinesis(sensor_reading)
            
            return f"Successfully collected data from {device_id}: {sensor_reading.sensor_type.value}={sensor_reading.value}{sensor_reading.unit}, quality={sensor_reading.quality}"
        
        return asyncio.run(collect_data())
    
    async def _arun(self, device_id: str) -> str:
        """Async version of the tool"""
        collector = IoTDataCollector()
        # Collect sensor data
        sensor_data = await collector.collect_sensor_data(device_id)
        if not sensor_data:
            return f"No data available from device {device_id}"
        
        # Validate and normalize
        sensor_reading = await collector.validate_and_normalize_data(sensor_data)
        if not sensor_reading:
            return f"Data validation failed for device {device_id}"
        
        # Store data
        stored = await collector.store_sensor_data(sensor_reading)
        streamed = await collector.stream_to_kinesis(sensor_reading)
        
        return f"Successfully collected data from {device_id}: {sensor_reading.sensor_type.value}={sensor_reading.value}{sensor_reading.unit}, quality={sensor_reading.quality}"


class DataIngestionAgent:
    """Main Data Ingestion Agent class"""
    
    def __init__(self):
        self.iot_collector = IoTDataCollector()
        self.weather_client = WeatherAPIClient()
        self.satellite_processor = SatelliteImageProcessor()
        self.market_agent = MarketIntelligenceAgent()
        self.government_agent = GovernmentIntegrationAgent()
        self.tools = [
            IoTDataCollectionTool(),
            WeatherDataTool(),
            SatelliteAnalysisTool(),
            MarketDataTool(),
            GovernmentDataTool()
        ]
    
    async def collect_all_sensor_data(self, device_ids: List[str]) -> List[SensorReading]:
        """Collect data from multiple IoT devices"""
        sensor_readings = []
        
        for device_id in device_ids:
            try:
                sensor_data = await self.iot_collector.collect_sensor_data(device_id)
                if sensor_data:
                    sensor_reading = await self.iot_collector.validate_and_normalize_data(sensor_data)
                    if sensor_reading:
                        # Store and stream data
                        await self.iot_collector.store_sensor_data(sensor_reading)
                        await self.iot_collector.stream_to_kinesis(sensor_reading)
                        sensor_readings.append(sensor_reading)
                        
            except Exception as e:
                logger.error(f"Error processing device {device_id}: {e}")
                continue
        
        logger.info(f"Collected data from {len(sensor_readings)} devices")
        return sensor_readings
    
    async def get_recent_sensor_data(self, sensor_type: str, hours: int = 24) -> List[SensorReading]:
        """Get recent sensor data for a specific sensor type"""
        try:
            start_time = datetime.now(timezone.utc).timestamp() - (hours * 3600)
            
            response = self.iot_collector.sensor_readings_table.query(
                IndexName='SensorTypeTimestampIndex',
                KeyConditionExpression='sensor_type = :sensor_type AND #ts > :start_time',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':sensor_type': sensor_type,
                    ':start_time': start_time
                }
            )
            
            sensor_readings = []
            for item in response['Items']:
                sensor_reading = SensorReading(
                    device_id=item['device_id'],
                    sensor_type=item['sensor_type'],
                    value=float(item['value']),
                    unit=item['unit'],
                    timestamp=datetime.fromtimestamp(item['timestamp'], tz=timezone.utc),
                    location=item.get('location', {"latitude": 0.0, "longitude": 0.0}),
                    quality=float(item.get('quality', 100))
                )
                sensor_readings.append(sensor_reading)
            
            return sensor_readings
            
        except Exception as e:
            logger.error(f"Error retrieving sensor data: {e}")
    async def collect_weather_data(self, latitude: float, longitude: float) -> Optional[Any]:
        """Collect weather data for a location"""
        try:
            weather_data = await self.weather_client.get_agricultural_weather_data(latitude, longitude)
            if weather_data:
                logger.info(f"Collected weather data for {latitude}, {longitude}")
                return weather_data
            else:
                logger.warning(f"No weather data available for {latitude}, {longitude}")
                return None
        except Exception as e:
            logger.error(f"Error collecting weather data: {e}")
            return None
    
    async def collect_satellite_data(self, field_boundary: List[Dict[str, float]], crop_type: str = "unknown") -> Optional[Any]:
        """Collect and analyze satellite data for a field"""
        try:
            from ..models.agricultural_intelligence import GeographicCoordinate
            
            # Convert field boundary to GeographicCoordinate objects
            boundary_coords = [
                GeographicCoordinate(latitude=coord["latitude"], longitude=coord["longitude"])
                for coord in field_boundary
            ]
            
            analysis = await self.satellite_processor.analyze_crop_health(boundary_coords, crop_type)
            if analysis:
                logger.info(f"Completed satellite analysis for field with {len(field_boundary)} boundary points")
                return analysis
            else:
                logger.warning("No satellite analysis results available")
                return None
        except Exception as e:
            logger.error(f"Error collecting satellite data: {e}")
            return None
    
    async def collect_comprehensive_data(
        self, 
        farmer_id: str, 
        location: Dict[str, float], 
        field_boundary: Optional[List[Dict[str, float]]] = None,
        crop_type: str = "unknown"
    ) -> Dict[str, Any]:
        """Collect comprehensive agricultural data from all sources"""
        results = {
            "farmer_id": farmer_id,
            "location": location,
            "timestamp": datetime.now(timezone.utc),
            "sensor_data": [],
            "weather_data": None,
            "satellite_data": None,
            "market_data": [],
            "government_data": {},
            "errors": []
        }
        
        try:
            # Collect IoT sensor data
            try:
                devices = await self._get_farmer_devices(farmer_id)
                if devices:
                    sensor_readings = await self.collect_all_sensor_data(devices)
                    results["sensor_data"] = sensor_readings
            except Exception as e:
                results["errors"].append(f"Sensor data collection failed: {e}")
            
            # Collect weather data
            try:
                weather_data = await self.collect_weather_data(
                    location["latitude"], 
                    location["longitude"]
                )
                results["weather_data"] = weather_data
            except Exception as e:
                results["errors"].append(f"Weather data collection failed: {e}")
            
            # Collect satellite data if field boundary is provided
            if field_boundary:
                try:
                    satellite_data = await self.collect_satellite_data(field_boundary, crop_type)
                    results["satellite_data"] = satellite_data
                except Exception as e:
                    results["errors"].append(f"Satellite data collection failed: {e}")
            
            # Collect market data
            try:
                market_data = await self.collect_market_data(location, [crop_type])
                results["market_data"] = market_data
            except Exception as e:
                results["errors"].append(f"Market data collection failed: {e}")
            
            # Collect government data
            try:
                government_data = await self.collect_government_data(farmer_id)
                results["government_data"] = government_data
            except Exception as e:
                results["errors"].append(f"Government data collection failed: {e}")
            
            logger.info(f"Completed comprehensive data collection for farmer {farmer_id}")
            return results
            
        except Exception as e:
            logger.error(f"Error in comprehensive data collection: {e}")
            results["errors"].append(f"General collection error: {e}")
            return results
    
    async def collect_market_data(
        self, 
        location: Dict[str, float], 
        commodities: List[str]
    ) -> List[Any]:
        """Collect market data for specified commodities"""
        try:
            from ..models.base import GeographicCoordinate
            
            farmer_location = GeographicCoordinate(
                latitude=location["latitude"],
                longitude=location["longitude"]
            )
            
            market_data = await self.market_agent.get_comprehensive_market_data(
                farmer_location=farmer_location,
                commodities=commodities,
                radius_km=100
            )
            
            logger.info(f"Collected market data for {len(commodities)} commodities")
            return market_data
            
        except Exception as e:
            logger.error(f"Error collecting market data: {e}")
            return []
    
    async def collect_government_data(self, farmer_id: str) -> Dict[str, Any]:
        """Collect government database information for a farmer"""
        try:
            # Create a mock farmer profile for government data collection
            from ..models.farmer import FarmerProfile, PersonalInfo, FarmDetails, Location, Field
            from ..models.base import GeographicCoordinate
            
            mock_profile = FarmerProfile(
                farmer_id=farmer_id,
                personal_info=PersonalInfo(
                    name="Demo Farmer",
                    phone_number="9876543210",
                    preferred_language="hindi"
                ),
                location=Location(
                    state="Maharashtra",
                    district="Pune",
                    village="Demo Village",
                    coordinates=GeographicCoordinate(latitude=18.5204, longitude=73.8567)
                ),
                farm_details=FarmDetails(
                    total_land_area=1.5,
                    soil_type="black_cotton",
                    irrigation_type="drip",
                    fields=[
                        Field(
                            field_id="F001",
                            area=1.5,
                            soil_type="black_cotton",
                            current_crop="cotton"
                        )
                    ]
                )
            )
            
            government_data = await self.government_agent.get_comprehensive_farmer_data(mock_profile)
            
            logger.info(f"Collected government data for farmer {farmer_id}")
            return government_data
            
        except Exception as e:
            logger.error(f"Error collecting government data: {e}")
            return {}
    
    async def close(self):
        """Close all agent connections"""
        try:
            await self.market_agent.close()
            await self.government_agent.close()
        except Exception as e:
            logger.error(f"Error closing agent connections: {e}")
    
    async def _get_farmer_devices(self, farmer_id: str) -> List[str]:
        """Get device IDs for a farmer (placeholder implementation)"""
        # In production, this would query the device database
        # For now, return empty list
        return []