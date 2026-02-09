"""
Data Processing Pipeline Orchestrator

This module orchestrates the complete data processing pipeline
integrating Kinesis, Glue, Spark, and lifecycle management.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from .kinesis_pipeline import KinesisDataPipeline, StreamConfig, DataPartitioner, PartitionConfig
from .glue_etl import GlueETLManager, ETLJobConfig
from .spark_processor import SparkDataProcessor, EMRClusterManager, EMRClusterConfig, SparkJobConfig
from .lifecycle_manager import S3LifecycleManager, DataArchiver, LifecycleRule, IntelligentTieringConfig
from .performance_monitor import PerformanceMonitor, ResourceOptimizer, ResourceThresholds

from src.krishimitra.core.config import settings

logger = logging.getLogger(__name__)


class DataProcessingPipeline:
    """
    Orchestrates end-to-end data processing pipeline
    
    Manages data ingestion, transformation, storage optimization,
    and performance monitoring for agricultural data.
    """
    
    def __init__(self):
        # Initialize components
        self.kinesis_pipeline = None
        self.glue_manager = GlueETLManager()
        self.emr_manager = EMRClusterManager()
        self.spark_processor = None
        self.lifecycle_manager = S3LifecycleManager()
        self.data_archiver = DataArchiver()
        self.performance_monitor = PerformanceMonitor()
        self.resource_optimizer = ResourceOptimizer()
        
        self.cluster_id = None
    
    async def initialize_pipeline(self) -> bool:
        """
        Initialize all pipeline components
        
        Returns:
            True if initialization successful
        """
        try:
            logger.info("Initializing data processing pipeline...")
            
            # 1. Create Kinesis streams for data ingestion
            await self._setup_kinesis_streams()
            
            # 2. Create Glue catalog and ETL jobs
            await self._setup_glue_catalog()
            
            # 3. Setup S3 lifecycle policies
            await self._setup_lifecycle_policies()
            
            # 4. Enable Intelligent Tiering
            await self._enable_intelligent_tiering()
            
            logger.info("Data processing pipeline initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing pipeline: {e}")
            return False
    
    async def _setup_kinesis_streams(self):
        """Setup Kinesis streams for different data types"""
        # Sensor data stream
        sensor_config = StreamConfig(
            stream_name="agricultural-sensor-stream",
            shard_count=2,
            retention_hours=24,
            enhanced_monitoring=True
        )
        self.kinesis_pipeline = KinesisDataPipeline(sensor_config)
        await self.kinesis_pipeline.create_stream()
        
        # Weather data stream
        weather_config = StreamConfig(
            stream_name="weather-data-stream",
            shard_count=1,
            retention_hours=24
        )
        weather_pipeline = KinesisDataPipeline(weather_config)
        await weather_pipeline.create_stream()
        
        # Market data stream
        market_config = StreamConfig(
            stream_name="market-data-stream",
            shard_count=1,
            retention_hours=48
        )
        market_pipeline = KinesisDataPipeline(market_config)
        await market_pipeline.create_stream()
        
        logger.info("Kinesis streams created successfully")
    
    async def _setup_glue_catalog(self):
        """Setup Glue data catalog and ETL jobs"""
        # Create database
        await self.glue_manager.create_database(
            database_name="agricultural_data",
            description="Agricultural data catalog for KrishiMitra"
        )
        
        # Create sensor data table
        sensor_columns = [
            {'Name': 'device_id', 'Type': 'string'},
            {'Name': 'sensor_type', 'Type': 'string'},
            {'Name': 'timestamp', 'Type': 'timestamp'},
            {'Name': 'value', 'Type': 'double'},
            {'Name': 'unit', 'Type': 'string'},
            {'Name': 'location_lat', 'Type': 'double'},
            {'Name': 'location_lon', 'Type': 'double'}
        ]
        
        partition_keys = [
            {'Name': 'year', 'Type': 'string'},
            {'Name': 'month', 'Type': 'string'},
            {'Name': 'day', 'Type': 'string'}
        ]
        
        await self.glue_manager.create_table(
            database_name="agricultural_data",
            table_name="sensor_readings",
            s3_location=f"s3://{settings.s3_bucket}/sensor-data/",
            columns=sensor_columns,
            partition_keys=partition_keys
        )
        
        # Create crawler for automatic schema discovery
        await self.glue_manager.create_crawler(
            crawler_name="agricultural-data-crawler",
            database_name="agricultural_data",
            s3_targets=[
                f"s3://{settings.s3_bucket}/sensor-data/",
                f"s3://{settings.s3_bucket}/weather-data/",
                f"s3://{settings.s3_bucket}/market-data/"
            ],
            role_arn=f"arn:aws:iam::{settings.aws_account_id}:role/GlueServiceRole",
            schedule="cron(0 2 * * ? *)"  # Daily at 2 AM
        )
        
        logger.info("Glue catalog setup completed")
    
    async def _setup_lifecycle_policies(self):
        """Setup S3 lifecycle policies for cost optimization"""
        rules = [
            # Sensor data lifecycle
            LifecycleRule(
                rule_id="sensor-data-lifecycle",
                prefix="sensor-data/",
                transition_to_ia_days=30,
                transition_to_glacier_days=90,
                transition_to_deep_archive_days=365,
                expiration_days=1825  # 5 years
            ),
            # Weather data lifecycle
            LifecycleRule(
                rule_id="weather-data-lifecycle",
                prefix="weather-data/",
                transition_to_ia_days=60,
                transition_to_glacier_days=180,
                expiration_days=730  # 2 years
            ),
            # Market data lifecycle
            LifecycleRule(
                rule_id="market-data-lifecycle",
                prefix="market-data/",
                transition_to_ia_days=90,
                transition_to_glacier_days=365,
                expiration_days=1095  # 3 years
            ),
            # Logs lifecycle
            LifecycleRule(
                rule_id="logs-lifecycle",
                prefix="logs/",
                transition_to_ia_days=7,
                transition_to_glacier_days=30,
                expiration_days=90
            )
        ]
        
        await self.lifecycle_manager.create_lifecycle_policy(rules)
        logger.info("S3 lifecycle policies created")
    
    async def _enable_intelligent_tiering(self):
        """Enable S3 Intelligent Tiering for automatic optimization"""
        configs = [
            IntelligentTieringConfig(
                config_id="sensor-data-tiering",
                prefix="sensor-data/",
                archive_access_tier_days=90,
                deep_archive_access_tier_days=180
            ),
            IntelligentTieringConfig(
                config_id="processed-data-tiering",
                prefix="processed-data/",
                archive_access_tier_days=180,
                deep_archive_access_tier_days=365
            )
        ]
        
        for config in configs:
            await self.lifecycle_manager.enable_intelligent_tiering(config)
        
        logger.info("Intelligent Tiering enabled")
    
    @PerformanceMonitor().profile_function
    async def ingest_sensor_data(self, sensor_data: List[Dict[str, Any]]) -> bool:
        """
        Ingest sensor data through Kinesis pipeline
        
        Args:
            sensor_data: List of sensor readings
            
        Returns:
            True if ingestion successful
        """
        try:
            # Partition data
            partitioner = DataPartitioner(
                PartitionConfig(
                    partition_keys=['sensor_type', 'device_id'],
                    time_based=True
                )
            )
            
            partitioned_data = partitioner.partition_records(sensor_data)
            
            # Stream to Kinesis
            for partition_path, records in partitioned_data.items():
                for record in records:
                    await self.kinesis_pipeline.buffer_record(
                        data=record,
                        partition_key=record.get('device_id', 'unknown')
                    )
            
            # Flush buffer
            await self.kinesis_pipeline.flush_buffer()
            
            logger.info(f"Ingested {len(sensor_data)} sensor readings")
            return True
            
        except Exception as e:
            logger.error(f"Error ingesting sensor data: {e}")
            return False
    
    async def process_with_spark(self, input_path: str, output_path: str,
                                job_type: str = "aggregate") -> Optional[str]:
        """
        Process data using Spark on EMR
        
        Args:
            input_path: S3 input path
            output_path: S3 output path
            job_type: Type of processing (aggregate, partition, etc.)
            
        Returns:
            Step ID if successful
        """
        try:
            # Create EMR cluster if not exists
            if not self.cluster_id:
                cluster_config = EMRClusterConfig(
                    cluster_name="krishimitra-data-processing",
                    core_instance_count=2,
                    auto_scaling_enabled=True,
                    min_capacity=2,
                    max_capacity=10
                )
                self.cluster_id = await self.emr_manager.create_cluster(cluster_config)
                
                if not self.cluster_id:
                    logger.error("Failed to create EMR cluster")
                    return None
                
                # Wait for cluster to be ready
                await asyncio.sleep(300)  # Wait 5 minutes
            
            # Initialize Spark processor
            if not self.spark_processor:
                self.spark_processor = SparkDataProcessor(self.emr_manager)
            
            # Submit appropriate Spark job
            if job_type == "aggregate":
                script_location = f"s3://{settings.s3_bucket}/spark-scripts/sensor_data_aggregation.py"
                job_config = SparkJobConfig(
                    job_name="SensorDataAggregation",
                    script_location=script_location,
                    arguments=[input_path, output_path, "1 hour"]
                )
            elif job_type == "partition":
                script_location = f"s3://{settings.s3_bucket}/spark-scripts/data_partitioning.py"
                job_config = SparkJobConfig(
                    job_name="DataPartitioning",
                    script_location=script_location,
                    arguments=[input_path, output_path, "year,month,sensor_type"]
                )
            else:
                logger.error(f"Unknown job type: {job_type}")
                return None
            
            step_id = await self.spark_processor.submit_spark_job(self.cluster_id, job_config)
            
            logger.info(f"Submitted Spark job: {job_type} (Step ID: {step_id})")
            return step_id
            
        except Exception as e:
            logger.error(f"Error processing with Spark: {e}")
            return None
    
    async def archive_old_data(self, days: int = 90) -> Dict[str, int]:
        """
        Archive data older than specified days
        
        Args:
            days: Archive data older than this many days
            
        Returns:
            Dictionary with archiving statistics
        """
        try:
            results = {}
            
            # Archive sensor data
            sensor_result = await self.data_archiver.archive_old_data(
                prefix="sensor-data/",
                age_days=days,
                target_storage_class="GLACIER"
            )
            results['sensor_data'] = sensor_result
            
            # Archive weather data
            weather_result = await self.data_archiver.archive_old_data(
                prefix="weather-data/",
                age_days=days,
                target_storage_class="GLACIER"
            )
            results['weather_data'] = weather_result
            
            # Archive market data
            market_result = await self.data_archiver.archive_old_data(
                prefix="market-data/",
                age_days=days,
                target_storage_class="GLACIER"
            )
            results['market_data'] = market_result
            
            total_archived = sum(r['archived_count'] for r in results.values())
            total_size_gb = sum(r['archived_size_gb'] for r in results.values())
            
            logger.info(f"Archived {total_archived} objects ({total_size_gb:.2f} GB)")
            
            return results
            
        except Exception as e:
            logger.error(f"Error archiving data: {e}")
            return {}
    
    async def optimize_resources(self) -> Dict[str, Any]:
        """
        Optimize resource usage and costs
        
        Returns:
            Dictionary with optimization results
        """
        try:
            results = {}
            
            # Get storage metrics
            storage_metrics = await self.lifecycle_manager.get_storage_metrics()
            results['storage_metrics'] = storage_metrics
            
            # Get cost optimization recommendations
            cost_recommendations = await self.lifecycle_manager.optimize_storage_costs()
            results['cost_recommendations'] = cost_recommendations
            
            # Get performance bottlenecks
            bottlenecks = self.performance_monitor.identify_bottlenecks()
            results['performance_bottlenecks'] = bottlenecks
            
            # Get performance summary
            perf_summary = self.performance_monitor.get_metrics_summary(hours=24)
            results['performance_summary'] = perf_summary
            
            logger.info("Resource optimization analysis completed")
            
            return results
            
        except Exception as e:
            logger.error(f"Error optimizing resources: {e}")
            return {}
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            # Terminate EMR cluster if exists
            if self.cluster_id:
                await self.emr_manager.terminate_cluster(self.cluster_id)
                logger.info(f"Terminated EMR cluster: {self.cluster_id}")
            
            # Flush any remaining buffered data
            if self.kinesis_pipeline:
                await self.kinesis_pipeline.flush_buffer()
            
            logger.info("Pipeline cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
