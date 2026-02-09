"""
Real-time data streaming for KrishiMitra Platform

This module handles real-time data streaming using Amazon Kinesis
for processing IoT sensor data and other agricultural intelligence.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import asyncio

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

from ..core.config import get_settings
from ..models.agricultural_intelligence import SensorReading

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class StreamRecord:
    """Represents a record in the data stream"""
    partition_key: str
    data: Dict[str, Any]
    timestamp: datetime
    sequence_number: Optional[str] = None


class KinesisStreamer:
    """Handles streaming data to Amazon Kinesis"""
    
    def __init__(self, stream_name: str = "agricultural-sensor-stream"):
        self.kinesis_client = boto3.client('kinesis', region_name=settings.aws_region)
        self.stream_name = stream_name
        self.batch_size = 500  # Maximum records per batch
        self.batch_timeout = 5.0  # Seconds to wait before sending partial batch
        self._record_buffer = []
        self._last_flush = datetime.now(timezone.utc)
    
    async def create_stream_if_not_exists(self, shard_count: int = 1) -> bool:
        """Create Kinesis stream if it doesn't exist"""
        try:
            # Check if stream exists
            try:
                response = self.kinesis_client.describe_stream(StreamName=self.stream_name)
                logger.info(f"Stream {self.stream_name} already exists")
                return True
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceNotFoundException':
                    raise e
            
            # Create stream
            self.kinesis_client.create_stream(
                StreamName=self.stream_name,
                ShardCount=shard_count
            )
            
            # Wait for stream to become active
            waiter = self.kinesis_client.get_waiter('stream_exists')
            waiter.wait(StreamName=self.stream_name)
            
            logger.info(f"Created Kinesis stream: {self.stream_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating Kinesis stream: {e}")
            return False
    
    async def put_record(self, partition_key: str, data: Dict[str, Any]) -> Optional[str]:
        """Put a single record to the stream"""
        try:
            record_data = json.dumps(data, default=str)
            
            response = self.kinesis_client.put_record(
                StreamName=self.stream_name,
                Data=record_data,
                PartitionKey=partition_key
            )
            
            sequence_number = response['SequenceNumber']
            logger.debug(f"Put record to stream: {sequence_number}")
            return sequence_number
            
        except Exception as e:
            logger.error(f"Error putting record to stream: {e}")
            return None
    
    async def put_records_batch(self, records: List[StreamRecord]) -> Dict[str, Any]:
        """Put multiple records to the stream in batch"""
        try:
            kinesis_records = []
            for record in records:
                kinesis_records.append({
                    'Data': json.dumps(record.data, default=str),
                    'PartitionKey': record.partition_key
                })
            
            response = self.kinesis_client.put_records(
                Records=kinesis_records,
                StreamName=self.stream_name
            )
            
            failed_count = response['FailedRecordCount']
            if failed_count > 0:
                logger.warning(f"Failed to put {failed_count} records to stream")
            
            logger.info(f"Put {len(records) - failed_count} records to stream")
            return response
            
        except Exception as e:
            logger.error(f"Error putting batch records to stream: {e}")
            return {'FailedRecordCount': len(records)}
    
    async def add_to_buffer(self, partition_key: str, data: Dict[str, Any]):
        """Add record to buffer for batch processing"""
        record = StreamRecord(
            partition_key=partition_key,
            data=data,
            timestamp=datetime.now(timezone.utc)
        )
        
        self._record_buffer.append(record)
        
        # Check if we should flush the buffer
        should_flush = (
            len(self._record_buffer) >= self.batch_size or
            (datetime.now(timezone.utc) - self._last_flush).total_seconds() >= self.batch_timeout
        )
        
        if should_flush:
            await self.flush_buffer()
    
    async def flush_buffer(self):
        """Flush the record buffer to Kinesis"""
        if not self._record_buffer:
            return
        
        records_to_send = self._record_buffer.copy()
        self._record_buffer.clear()
        self._last_flush = datetime.now(timezone.utc)
        
        await self.put_records_batch(records_to_send)


class StreamProcessor:
    """Processes records from Kinesis streams"""
    
    def __init__(self, stream_name: str = "agricultural-sensor-stream"):
        self.kinesis_client = boto3.client('kinesis', region_name=settings.aws_region)
        self.stream_name = stream_name
        self.processors = {}
        self.is_running = False
    
    def register_processor(self, record_type: str, processor_func: Callable):
        """Register a processor function for a specific record type"""
        self.processors[record_type] = processor_func
        logger.info(f"Registered processor for record type: {record_type}")
    
    async def start_processing(self, shard_id: str = None):
        """Start processing records from the stream"""
        try:
            self.is_running = True
            
            # Get shard iterator
            if not shard_id:
                # Get the first shard
                response = self.kinesis_client.describe_stream(StreamName=self.stream_name)
                shard_id = response['StreamDescription']['Shards'][0]['ShardId']
            
            shard_iterator_response = self.kinesis_client.get_shard_iterator(
                StreamName=self.stream_name,
                ShardId=shard_id,
                ShardIteratorType='LATEST'
            )
            
            shard_iterator = shard_iterator_response['ShardIterator']
            
            logger.info(f"Started processing stream {self.stream_name}, shard {shard_id}")
            
            while self.is_running:
                try:
                    # Get records from stream
                    response = self.kinesis_client.get_records(
                        ShardIterator=shard_iterator,
                        Limit=100
                    )
                    
                    records = response['Records']
                    shard_iterator = response.get('NextShardIterator')
                    
                    if not shard_iterator:
                        logger.warning("Shard iterator is None, stopping processing")
                        break
                    
                    # Process records
                    for record in records:
                        await self._process_record(record)
                    
                    # Wait a bit before next poll if no records
                    if not records:
                        await asyncio.sleep(1.0)
                        
                except Exception as e:
                    logger.error(f"Error processing stream records: {e}")
                    await asyncio.sleep(5.0)  # Wait before retrying
                    
        except Exception as e:
            logger.error(f"Error starting stream processing: {e}")
        finally:
            self.is_running = False
    
    async def _process_record(self, record: Dict[str, Any]):
        """Process a single record from the stream"""
        try:
            # Decode record data
            data = json.loads(record['Data'])
            
            # Determine record type
            record_type = data.get('type', 'sensor_data')
            
            # Route to appropriate processor
            if record_type in self.processors:
                processor = self.processors[record_type]
                await processor(data, record)
            else:
                logger.warning(f"No processor registered for record type: {record_type}")
                
        except Exception as e:
            logger.error(f"Error processing record: {e}")
    
    def stop_processing(self):
        """Stop processing records"""
        self.is_running = False
        logger.info("Stopped stream processing")


class AgriculturalDataStreamer:
    """Specialized streamer for agricultural data"""
    
    def __init__(self):
        self.sensor_streamer = KinesisStreamer("agricultural-sensor-stream")
        self.weather_streamer = KinesisStreamer("weather-data-stream")
        self.market_streamer = KinesisStreamer("market-data-stream")
        self.alert_streamer = KinesisStreamer("agricultural-alerts-stream")
    
    async def initialize_streams(self):
        """Initialize all required streams"""
        streams = [
            (self.sensor_streamer, 2),  # 2 shards for sensor data
            (self.weather_streamer, 1),  # 1 shard for weather data
            (self.market_streamer, 1),   # 1 shard for market data
            (self.alert_streamer, 1)     # 1 shard for alerts
        ]
        
        for streamer, shard_count in streams:
            await streamer.create_stream_if_not_exists(shard_count)
    
    async def stream_sensor_data(self, sensor_reading: SensorReading):
        """Stream sensor data to Kinesis"""
        data = {
            'type': 'sensor_data',
            'sensor_id': sensor_reading.sensor_id,
            'sensor_type': sensor_reading.sensor_type,
            'value': sensor_reading.value,
            'unit': sensor_reading.unit,
            'timestamp': sensor_reading.timestamp.isoformat(),
            'location': sensor_reading.location,
            'quality_score': sensor_reading.quality_score
        }
        
        partition_key = f"{sensor_reading.sensor_type}_{sensor_reading.sensor_id}"
        await self.sensor_streamer.add_to_buffer(partition_key, data)
    
    async def stream_weather_data(self, location: Dict[str, float], weather_data: Dict[str, Any]):
        """Stream weather data to Kinesis"""
        data = {
            'type': 'weather_data',
            'location': location,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            **weather_data
        }
        
        partition_key = f"weather_{location['latitude']}_{location['longitude']}"
        await self.weather_streamer.add_to_buffer(partition_key, data)
    
    async def stream_market_data(self, market_data: Dict[str, Any]):
        """Stream market data to Kinesis"""
        data = {
            'type': 'market_data',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            **market_data
        }
        
        partition_key = f"market_{market_data.get('commodity', 'unknown')}"
        await self.market_streamer.add_to_buffer(partition_key, data)
    
    async def stream_alert(self, alert_type: str, message: str, severity: str = 'info', 
                          metadata: Optional[Dict[str, Any]] = None):
        """Stream alert to Kinesis"""
        data = {
            'type': 'alert',
            'alert_type': alert_type,
            'message': message,
            'severity': severity,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'metadata': metadata or {}
        }
        
        partition_key = f"alert_{alert_type}"
        await self.alert_streamer.add_to_buffer(partition_key, data)
    
    async def flush_all_buffers(self):
        """Flush all stream buffers"""
        await asyncio.gather(
            self.sensor_streamer.flush_buffer(),
            self.weather_streamer.flush_buffer(),
            self.market_streamer.flush_buffer(),
            self.alert_streamer.flush_buffer()
        )


# Default processors for different data types
async def process_sensor_data(data: Dict[str, Any], record: Dict[str, Any]):
    """Default processor for sensor data"""
    logger.info(f"Processing sensor data: {data['sensor_type']} = {data['value']}")
    # Here you would typically:
    # 1. Validate the data
    # 2. Store in appropriate database
    # 3. Trigger alerts if thresholds are exceeded
    # 4. Update real-time dashboards


async def process_weather_data(data: Dict[str, Any], record: Dict[str, Any]):
    """Default processor for weather data"""
    logger.info(f"Processing weather data for location: {data['location']}")
    # Here you would typically:
    # 1. Update weather forecasts
    # 2. Trigger weather-based recommendations
    # 3. Alert farmers of severe weather


async def process_market_data(data: Dict[str, Any], record: Dict[str, Any]):
    """Default processor for market data"""
    logger.info(f"Processing market data: {data.get('commodity', 'unknown')}")
    # Here you would typically:
    # 1. Update price databases
    # 2. Trigger price alerts
    # 3. Update market trend analysis


async def process_alert(data: Dict[str, Any], record: Dict[str, Any]):
    """Default processor for alerts"""
    logger.warning(f"Processing alert: {data['alert_type']} - {data['message']}")
    # Here you would typically:
    # 1. Store alert in database
    # 2. Send notifications to relevant farmers
    # 3. Trigger automated responses