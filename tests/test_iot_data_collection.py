"""
Tests for IoT data collection functionality

This module tests the IoT sensor data collection, device management,
and real-time streaming capabilities.
"""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal

from src.krishimitra.agents.data_ingestion import (
    IoTSensorData, IoTDataCollector, DataIngestionAgent, IoTDataCollectionTool
)
from src.krishimitra.iot.device_manager import (
    DeviceManager, IoTDevice, DeviceStatus, DeviceType
)
from src.krishimitra.iot.streaming import (
    KinesisStreamer, StreamProcessor, AgriculturalDataStreamer
)
from src.krishimitra.models.agricultural_intelligence import SensorReading


class TestIoTSensorData:
    """Test IoT sensor data validation"""
    
    def test_valid_sensor_data(self):
        """Test creation of valid sensor data"""
        sensor_data = IoTSensorData(
            device_id="test-device-001",
            sensor_type="soil_moisture",
            value=45.5,
            unit="percent",
            location={"latitude": 28.6139, "longitude": 77.2090}
        )
        
        assert sensor_data.device_id == "test-device-001"
        assert sensor_data.sensor_type == "soil_moisture"
        assert sensor_data.value == 45.5
        assert sensor_data.unit == "percent"
        assert sensor_data.quality_score == 1.0
    
    def test_invalid_sensor_type(self):
        """Test validation of invalid sensor type"""
        with pytest.raises(ValueError, match="Sensor type must be one of"):
            IoTSensorData(
                device_id="test-device-001",
                sensor_type="invalid_type",
                value=45.5,
                unit="percent"
            )
    
    def test_invalid_ph_value(self):
        """Test validation of invalid pH value"""
        with pytest.raises(ValueError, match="pH value must be between 0 and 14"):
            IoTSensorData(
                device_id="test-device-001",
                sensor_type="ph",
                value=15.0,
                unit="pH"
            )
    
    def test_invalid_humidity_value(self):
        """Test validation of invalid humidity value"""
        with pytest.raises(ValueError, match="Humidity must be between 0 and 100 percent"):
            IoTSensorData(
                device_id="test-device-001",
                sensor_type="humidity",
                value=150.0,
                unit="percent"
            )


class TestIoTDataCollector:
    """Test IoT data collector functionality"""
    
    @pytest.fixture
    def mock_collector(self):
        """Create mock IoT data collector"""
        with patch('boto3.client'), patch('boto3.resource'):
            collector = IoTDataCollector()
            collector.iot_client = Mock()
            collector.kinesis_client = Mock()
            collector.sensor_readings_table = Mock()
            return collector
    
    @pytest.mark.asyncio
    async def test_collect_sensor_data_success(self, mock_collector):
        """Test successful sensor data collection"""
        # Mock IoT shadow response
        shadow_data = {
            'state': {
                'reported': {
                    'sensor_type': 'soil_moisture',
                    'value': 45.5,
                    'unit': 'percent',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'quality_score': 0.95
                }
            }
        }
        
        mock_payload = Mock()
        mock_payload.read.return_value = json.dumps(shadow_data)
        mock_collector.iot_client.get_thing_shadow.return_value = {'payload': mock_payload}
        
        result = await mock_collector.collect_sensor_data("test-device-001")
        
        assert result is not None
        assert result.device_id == "test-device-001"
        assert result.sensor_type == "soil_moisture"
        assert result.value == 45.5
        assert result.quality_score == 0.95
    
    @pytest.mark.asyncio
    async def test_collect_sensor_data_no_shadow(self, mock_collector):
        """Test sensor data collection with no shadow data"""
        shadow_data = {'state': {}}
        
        mock_payload = Mock()
        mock_payload.read.return_value = json.dumps(shadow_data)
        mock_collector.iot_client.get_thing_shadow.return_value = {'payload': mock_payload}
        
        result = await mock_collector.collect_sensor_data("test-device-001")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_validate_and_normalize_data(self, mock_collector):
        """Test data validation and normalization"""
        sensor_data = IoTSensorData(
            device_id="test-device-001",
            sensor_type="soil_moisture",
            value=45.5,
            unit="percent",
            quality_score=0.8
        )
        
        # Mock anomaly detection
        mock_collector._detect_anomaly = AsyncMock(return_value=False)
        
        result = await mock_collector.validate_and_normalize_data(sensor_data)
        
        assert result is not None
        assert isinstance(result, SensorReading)
        assert result.sensor_id == "test-device-001"
        assert result.value == 45.5
        assert result.quality_score == 0.8
    
    @pytest.mark.asyncio
    async def test_validate_low_quality_data(self, mock_collector):
        """Test rejection of low quality data"""
        sensor_data = IoTSensorData(
            device_id="test-device-001",
            sensor_type="soil_moisture",
            value=45.5,
            unit="percent",
            quality_score=0.3  # Below threshold
        )
        
        result = await mock_collector.validate_and_normalize_data(sensor_data)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_anomaly_detection(self, mock_collector):
        """Test anomaly detection in sensor data"""
        # Mock historical data query
        mock_collector.sensor_readings_table.query.return_value = {
            'Items': [
                {'value': Decimal('45.0')},
                {'value': Decimal('46.0')},
                {'value': Decimal('44.0')},
                {'value': Decimal('45.5')},
                {'value': Decimal('43.8')},
                {'value': Decimal('46.2')},
                {'value': Decimal('44.7')},
                {'value': Decimal('45.3')},
                {'value': Decimal('44.9')},
                {'value': Decimal('45.8')}
            ]
        }
        
        # Test normal value
        sensor_data = IoTSensorData(
            device_id="test-device-001",
            sensor_type="soil_moisture",
            value=45.0,
            unit="percent"
        )
        
        is_anomaly = await mock_collector._detect_anomaly(sensor_data)
        assert not is_anomaly
        
        # Test anomalous value (way outside normal range)
        sensor_data.value = 80.0
        is_anomaly = await mock_collector._detect_anomaly(sensor_data)
        assert is_anomaly


class TestDeviceManager:
    """Test device management functionality"""
    
    @pytest.fixture
    def mock_device_manager(self):
        """Create mock device manager"""
        with patch('boto3.client'), patch('boto3.resource'):
            manager = DeviceManager()
            manager.iot_client = Mock()
            manager.iot_data_client = Mock()
            manager.devices_table = Mock()
            return manager
    
    @pytest.mark.asyncio
    async def test_register_device_success(self, mock_device_manager):
        """Test successful device registration"""
        device = IoTDevice(
            device_id="test-device-001",
            device_name="Test Soil Sensor",
            device_type=DeviceType.SOIL_SENSOR,
            farmer_id="farmer-123",
            location={"latitude": 28.6139, "longitude": 77.2090}
        )
        
        # Mock AWS IoT responses
        mock_device_manager.iot_client.create_thing.return_value = {"thingArn": "test-arn"}
        mock_device_manager.iot_client.create_keys_and_certificate.return_value = {
            "certificateArn": "test-cert-arn"
        }
        mock_device_manager.iot_client.create_policy.return_value = {}
        mock_device_manager.iot_client.attach_policy.return_value = {}
        mock_device_manager.iot_client.attach_thing_principal.return_value = {}
        mock_device_manager.devices_table.put_item.return_value = {}
        
        result = await mock_device_manager.register_device(device)
        
        assert result is True
        mock_device_manager.iot_client.create_thing.assert_called_once()
        mock_device_manager.devices_table.put_item.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_device_success(self, mock_device_manager):
        """Test successful device retrieval"""
        mock_device_manager.devices_table.get_item.return_value = {
            'Item': {
                'device_id': 'test-device-001',
                'device_name': 'Test Soil Sensor',
                'device_type': 'soil_sensor',
                'farmer_id': 'farmer-123',
                'location': {"latitude": 28.6139, "longitude": 77.2090},
                'status': 'online',
                'configuration': {},
                'created_at': int(datetime.now(timezone.utc).timestamp()),
                'updated_at': int(datetime.now(timezone.utc).timestamp())
            }
        }
        
        result = await mock_device_manager.get_device("test-device-001")
        
        assert result is not None
        assert result.device_id == "test-device-001"
        assert result.device_type == DeviceType.SOIL_SENSOR
        assert result.status == DeviceStatus.ONLINE
    
    @pytest.mark.asyncio
    async def test_get_device_not_found(self, mock_device_manager):
        """Test device retrieval when device not found"""
        mock_device_manager.devices_table.get_item.return_value = {}
        
        result = await mock_device_manager.get_device("nonexistent-device")
        
        assert result is None


class TestKinesisStreamer:
    """Test Kinesis streaming functionality"""
    
    @pytest.fixture
    def mock_streamer(self):
        """Create mock Kinesis streamer"""
        with patch('boto3.client'):
            streamer = KinesisStreamer("test-stream")
            streamer.kinesis_client = Mock()
            return streamer
    
    @pytest.mark.asyncio
    async def test_put_record_success(self, mock_streamer):
        """Test successful record streaming"""
        mock_streamer.kinesis_client.put_record.return_value = {
            'SequenceNumber': 'test-sequence-123'
        }
        
        data = {
            'sensor_type': 'soil_moisture',
            'value': 45.5,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        result = await mock_streamer.put_record("test-partition", data)
        
        assert result == 'test-sequence-123'
        mock_streamer.kinesis_client.put_record.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_stream_if_not_exists(self, mock_streamer):
        """Test stream creation when stream doesn't exist"""
        # Mock stream doesn't exist
        from botocore.exceptions import ClientError
        mock_streamer.kinesis_client.describe_stream.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException'}}, 'DescribeStream'
        )
        
        # Mock successful creation
        mock_streamer.kinesis_client.create_stream.return_value = {}
        mock_waiter = Mock()
        mock_streamer.kinesis_client.get_waiter.return_value = mock_waiter
        
        result = await mock_streamer.create_stream_if_not_exists(2)
        
        assert result is True
        mock_streamer.kinesis_client.create_stream.assert_called_once_with(
            StreamName="test-stream",
            ShardCount=2
        )


class TestDataIngestionAgent:
    """Test data ingestion agent functionality"""
    
    @pytest.fixture
    def mock_agent(self):
        """Create mock data ingestion agent"""
        with patch('src.krishimitra.agents.data_ingestion.IoTDataCollector'):
            agent = DataIngestionAgent()
            agent.iot_collector = Mock()
            return agent
    
    @pytest.mark.asyncio
    async def test_collect_all_sensor_data(self, mock_agent):
        """Test collecting data from multiple devices"""
        # Mock sensor data
        sensor_data = IoTSensorData(
            device_id="test-device-001",
            sensor_type="soil_moisture",
            value=45.5,
            unit="percent"
        )
        
        sensor_reading = SensorReading(
            sensor_id="test-device-001",
            sensor_type="soil_moisture",
            value=45.5,
            unit="percent",
            timestamp=datetime.now(timezone.utc),
            quality_score=0.9
        )
        
        mock_agent.iot_collector.collect_sensor_data = AsyncMock(return_value=sensor_data)
        mock_agent.iot_collector.validate_and_normalize_data = AsyncMock(return_value=sensor_reading)
        mock_agent.iot_collector.store_sensor_data = AsyncMock(return_value=True)
        mock_agent.iot_collector.stream_to_kinesis = AsyncMock(return_value=True)
        
        device_ids = ["test-device-001", "test-device-002"]
        results = await mock_agent.collect_all_sensor_data(device_ids)
        
        assert len(results) == 2
        assert all(isinstance(reading, SensorReading) for reading in results)


class TestIoTDataCollectionTool:
    """Test LangChain IoT data collection tool"""
    
    @pytest.fixture
    def mock_tool(self):
        """Create mock IoT data collection tool"""
        with patch('src.krishimitra.agents.data_ingestion.IoTDataCollector'):
            tool = IoTDataCollectionTool()
            tool.collector = Mock()
            return tool
    
    def test_tool_properties(self, mock_tool):
        """Test tool properties"""
        assert mock_tool.name == "iot_data_collection"
        assert "IoT sensors" in mock_tool.description
    
    @pytest.mark.asyncio
    async def test_tool_run_success(self, mock_tool):
        """Test successful tool execution"""
        # Mock successful data collection
        sensor_data = IoTSensorData(
            device_id="test-device-001",
            sensor_type="soil_moisture",
            value=45.5,
            unit="percent"
        )
        
        sensor_reading = SensorReading(
            sensor_id="test-device-001",
            sensor_type="soil_moisture",
            value=45.5,
            unit="percent",
            timestamp=datetime.now(timezone.utc),
            quality_score=0.9
        )
        
        mock_tool.collector.collect_sensor_data = AsyncMock(return_value=sensor_data)
        mock_tool.collector.validate_and_normalize_data = AsyncMock(return_value=sensor_reading)
        mock_tool.collector.store_sensor_data = AsyncMock(return_value=True)
        mock_tool.collector.stream_to_kinesis = AsyncMock(return_value=True)
        
        result = await mock_tool._arun("test-device-001")
        
        assert "Successfully collected data" in result
        assert "soil_moisture=45.5percent" in result
    
    @pytest.mark.asyncio
    async def test_tool_run_no_data(self, mock_tool):
        """Test tool execution when no data available"""
        mock_tool.collector.collect_sensor_data = AsyncMock(return_value=None)
        
        result = await mock_tool._arun("test-device-001")
        
        assert "No data available" in result