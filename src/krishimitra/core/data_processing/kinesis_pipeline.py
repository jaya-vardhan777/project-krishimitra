"""
Scalable Data Ingestion Pipeline using AWS Kinesis

This module implements scalable data ingestion and processing pipelines
for agricultural data using Amazon Kinesis Data Streams and Kinesis Data Firehose.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
import boto3
from botocore.exceptions import ClientError

from src.krishimitra.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class StreamConfig:
    """Configuration for Kinesis stream"""
    stream_name: str
    shard_count: int = 1
    retention_hours: int = 24
    enhanced_monitoring: bool = True
    encryption_enabled: bool = True


@dataclass
class PartitionConfig:
    """Configuration for data partitioning"""
    partition_keys: List[str]
    time_based: bool = True
    time_format: str = "year=%Y/month=%m/day=%d/hour=%H"
    custom_partitioner: Optional[Callable] = None


class KinesisDataPipeline:
    """
    Scalable data ingestion pipeline using AWS Kinesis
    
    Handles high-throughput data ingestion with automatic scaling,
    data partitioning, and integration with downstream processing.
    """
    
    def __init__(self, config: StreamConfig):
        self.config = config
        self.kinesis_client = boto3.client('kinesis', region_name=settings.aws_region)
        self.firehose_client = boto3.client('firehose', region_name=settings.aws_region)
        self.cloudwatch = boto3.client('cloudwatch', region_name=settings.aws_region)
        
        self._record_buffer: List[Dict[str, Any]] = []
        self._buffer_size_limit = 500  # Maximum records per batch
        self._buffer_time_limit = 5  # Seconds before auto-flush
        self._last_flush_time = datetime.now()
    
    async def create_stream(self) -> bool:
        """Create Kinesis stream with specified configuration"""
        try:
            # Check if stream exists
            try:
                response = self.kinesis_client.describe_stream(
                    StreamName=self.config.stream_name
                )
                logger.info(f"Stream {self.config.stream_name} already exists")
                return True
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceNotFoundException':
                    raise
            
            # Create stream with sharding
            self.kinesis_client.create_stream(
                StreamName=self.config.stream_name,
                ShardCount=self.config.shard_count
            )
            
            # Wait for stream to become active
            waiter = self.kinesis_client.get_waiter('stream_exists')
            waiter.wait(StreamName=self.config.stream_name)
            
            # Configure retention period
            self.kinesis_client.increase_stream_retention_period(
                StreamName=self.config.stream_name,
                RetentionPeriodHours=self.config.retention_hours
            )
            
            # Enable encryption if configured
            if self.config.encryption_enabled:
                self.kinesis_client.start_stream_encryption(
                    StreamName=self.config.stream_name,
                    EncryptionType='KMS',
                    KeyId='alias/aws/kinesis'
                )
            
            # Enable enhanced monitoring if configured
            if self.config.enhanced_monitoring:
                self.kinesis_client.enable_enhanced_monitoring(
                    StreamName=self.config.stream_name,
                    ShardLevelMetrics=['ALL']
                )
            
            logger.info(f"Created Kinesis stream: {self.config.stream_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating Kinesis stream: {e}")
            return False
    
    async def put_record(self, data: Dict[str, Any], partition_key: str) -> Optional[str]:
        """
        Put a single record to the stream
        
        Args:
            data: Record data to stream
            partition_key: Key for shard distribution
            
        Returns:
            Sequence number if successful, None otherwise
        """
        try:
            record_data = json.dumps(data, default=str)
            
            response = self.kinesis_client.put_record(
                StreamName=self.config.stream_name,
                Data=record_data,
                PartitionKey=partition_key
            )
            
            return response['SequenceNumber']
            
        except Exception as e:
            logger.error(f"Error putting record to Kinesis: {e}")
            return None
    
    async def put_records_batch(self, records: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Put multiple records in batch for better throughput
        
        Args:
            records: List of records with 'data' and 'partition_key' fields
            
        Returns:
            Dictionary with success and failure counts
        """
        try:
            kinesis_records = []
            for record in records:
                kinesis_records.append({
                    'Data': json.dumps(record['data'], default=str),
                    'PartitionKey': record['partition_key']
                })
            
            # Split into batches of 500 (Kinesis limit)
            batch_size = 500
            total_success = 0
            total_failed = 0
            
            for i in range(0, len(kinesis_records), batch_size):
                batch = kinesis_records[i:i + batch_size]
                
                response = self.kinesis_client.put_records(
                    Records=batch,
                    StreamName=self.config.stream_name
                )
                
                total_success += len(batch) - response['FailedRecordCount']
                total_failed += response['FailedRecordCount']
                
                # Retry failed records
                if response['FailedRecordCount'] > 0:
                    failed_records = [
                        batch[idx] for idx, record in enumerate(response['Records'])
                        if 'ErrorCode' in record
                    ]
                    if failed_records:
                        await self._retry_failed_records(failed_records)
            
            return {
                'success_count': total_success,
                'failed_count': total_failed
            }
            
        except Exception as e:
            logger.error(f"Error putting batch records to Kinesis: {e}")
            return {'success_count': 0, 'failed_count': len(records)}
    
    async def _retry_failed_records(self, failed_records: List[Dict[str, Any]], 
                                   max_retries: int = 3):
        """Retry failed records with exponential backoff"""
        import asyncio
        
        for attempt in range(max_retries):
            if not failed_records:
                break
            
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
            
            response = self.kinesis_client.put_records(
                Records=failed_records,
                StreamName=self.config.stream_name
            )
            
            if response['FailedRecordCount'] == 0:
                break
            
            failed_records = [
                failed_records[idx] for idx, record in enumerate(response['Records'])
                if 'ErrorCode' in record
            ]
    
    async def buffer_record(self, data: Dict[str, Any], partition_key: str):
        """
        Buffer record for batch processing
        
        Automatically flushes when buffer is full or time limit is reached
        """
        self._record_buffer.append({
            'data': data,
            'partition_key': partition_key
        })
        
        # Check if we should flush
        time_since_flush = (datetime.now() - self._last_flush_time).total_seconds()
        
        if (len(self._record_buffer) >= self._buffer_size_limit or 
            time_since_flush >= self._buffer_time_limit):
            await self.flush_buffer()
    
    async def flush_buffer(self):
        """Flush buffered records to Kinesis"""
        if not self._record_buffer:
            return
        
        records_to_send = self._record_buffer.copy()
        self._record_buffer.clear()
        self._last_flush_time = datetime.now()
        
        result = await self.put_records_batch(records_to_send)
        logger.info(f"Flushed {result['success_count']} records to Kinesis")
    
    async def scale_stream(self, target_shard_count: int) -> bool:
        """
        Scale stream by adjusting shard count
        
        Args:
            target_shard_count: Desired number of shards
            
        Returns:
            True if scaling initiated successfully
        """
        try:
            # Get current shard count
            response = self.kinesis_client.describe_stream(
                StreamName=self.config.stream_name
            )
            current_shards = len(response['StreamDescription']['Shards'])
            
            if current_shards == target_shard_count:
                logger.info(f"Stream already has {target_shard_count} shards")
                return True
            
            # Update shard count
            self.kinesis_client.update_shard_count(
                StreamName=self.config.stream_name,
                TargetShardCount=target_shard_count,
                ScalingType='UNIFORM_SCALING'
            )
            
            logger.info(f"Scaling stream from {current_shards} to {target_shard_count} shards")
            return True
            
        except Exception as e:
            logger.error(f"Error scaling stream: {e}")
            return False
    
    async def get_stream_metrics(self) -> Dict[str, Any]:
        """Get stream performance metrics from CloudWatch"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=5)
            
            metrics = {}
            
            # Get incoming records metric
            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/Kinesis',
                MetricName='IncomingRecords',
                Dimensions=[
                    {'Name': 'StreamName', 'Value': self.config.stream_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Sum', 'Average']
            )
            
            if response['Datapoints']:
                metrics['incoming_records'] = response['Datapoints'][0]
            
            # Get incoming bytes metric
            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/Kinesis',
                MetricName='IncomingBytes',
                Dimensions=[
                    {'Name': 'StreamName', 'Value': self.config.stream_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Sum', 'Average']
            )
            
            if response['Datapoints']:
                metrics['incoming_bytes'] = response['Datapoints'][0]
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting stream metrics: {e}")
            return {}


class DataPartitioner:
    """
    Handles data partitioning for efficient storage and querying
    
    Implements time-based and custom partitioning strategies
    for optimal data organization in S3.
    """
    
    def __init__(self, config: PartitionConfig):
        self.config = config
    
    def get_partition_path(self, data: Dict[str, Any], timestamp: Optional[datetime] = None) -> str:
        """
        Generate partition path for data record
        
        Args:
            data: Data record to partition
            timestamp: Optional timestamp for time-based partitioning
            
        Returns:
            Partition path string
        """
        if self.config.custom_partitioner:
            return self.config.custom_partitioner(data, timestamp)
        
        path_parts = []
        
        # Add time-based partitioning
        if self.config.time_based:
            ts = timestamp or datetime.now()
            time_path = ts.strftime(self.config.time_format)
            path_parts.append(time_path)
        
        # Add key-based partitioning
        for key in self.config.partition_keys:
            if key in data:
                value = data[key]
                # Sanitize value for path
                sanitized_value = str(value).replace('/', '_').replace(' ', '_')
                path_parts.append(f"{key}={sanitized_value}")
        
        return '/'.join(path_parts)
    
    def partition_records(self, records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Partition multiple records into groups
        
        Args:
            records: List of records to partition
            
        Returns:
            Dictionary mapping partition paths to record lists
        """
        partitioned = {}
        
        for record in records:
            timestamp = record.get('timestamp')
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            
            partition_path = self.get_partition_path(record, timestamp)
            
            if partition_path not in partitioned:
                partitioned[partition_path] = []
            
            partitioned[partition_path].append(record)
        
        return partitioned
    
    def get_partition_filter(self, start_date: datetime, end_date: datetime) -> List[str]:
        """
        Generate partition paths for date range query
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            List of partition path prefixes
        """
        if not self.config.time_based:
            return []
        
        partitions = []
        current_date = start_date
        
        while current_date <= end_date:
            partition_path = current_date.strftime(self.config.time_format)
            partitions.append(partition_path)
            current_date += timedelta(days=1)
        
        return partitions
