# Data Processing Scalability and Optimization Module

This module provides comprehensive data processing scalability and optimization capabilities for the KrishiMitra platform using AWS services including Kinesis, Glue, EMR with Apache Spark, and S3 lifecycle management.

## Overview

The data processing module implements:

1. **Scalable Data Ingestion** - High-throughput data ingestion using AWS Kinesis Data Streams
2. **ETL Processing** - Data transformation and cataloging using AWS Glue
3. **Distributed Processing** - Large-scale data processing using Apache Spark on Amazon EMR
4. **Storage Optimization** - Automated data archiving and lifecycle management using S3 Intelligent Tiering
5. **Performance Monitoring** - Comprehensive performance profiling and resource optimization

## Components

### 1. Kinesis Data Pipeline (`kinesis_pipeline.py`)

Handles real-time data ingestion with automatic scaling and partitioning.

```python
from src.krishimitra.core.data_processing import KinesisDataPipeline, StreamConfig

# Create stream configuration
config = StreamConfig(
    stream_name="agricultural-sensor-stream",
    shard_count=2,
    retention_hours=24,
    enhanced_monitoring=True,
    encryption_enabled=True
)

# Initialize pipeline
pipeline = KinesisDataPipeline(config)
await pipeline.create_stream()

# Ingest data
await pipeline.put_record(
    data={"sensor_id": "S001", "value": 25.5, "timestamp": "2024-01-01T10:00:00Z"},
    partition_key="S001"
)

# Batch ingestion for better throughput
records = [
    {"data": {...}, "partition_key": "S001"},
    {"data": {...}, "partition_key": "S002"}
]
result = await pipeline.put_records_batch(records)
```

**Features:**
- Automatic stream creation with encryption
- Batch processing for high throughput
- Automatic retry with exponential backoff
- Buffer management with auto-flush
- Dynamic shard scaling
- CloudWatch metrics integration

### 2. Data Partitioner (`kinesis_pipeline.py`)

Implements intelligent data partitioning for optimal storage and query performance.

```python
from src.krishimitra.core.data_processing import DataPartitioner, PartitionConfig

# Configure partitioning
config = PartitionConfig(
    partition_keys=['sensor_type', 'location'],
    time_based=True,
    time_format="year=%Y/month=%m/day=%d/hour=%H"
)

partitioner = DataPartitioner(config)

# Partition records
partitioned = partitioner.partition_records(sensor_readings)

# Get partition path for a record
path = partitioner.get_partition_path(record, timestamp)
# Returns: "year=2024/month=01/day=15/hour=10/sensor_type=temperature/location=farm1"
```

### 3. Glue ETL Manager (`glue_etl.py`)

Manages AWS Glue ETL jobs for data transformation and cataloging.

```python
from src.krishimitra.core.data_processing import GlueETLManager, ETLJobConfig

manager = GlueETLManager()

# Create database
await manager.create_database("agricultural_data")

# Create table
columns = [
    {'Name': 'device_id', 'Type': 'string'},
    {'Name': 'value', 'Type': 'double'},
    {'Name': 'timestamp', 'Type': 'timestamp'}
]

await manager.create_table(
    database_name="agricultural_data",
    table_name="sensor_readings",
    s3_location="s3://bucket/sensor-data/",
    columns=columns,
    partition_keys=[{'Name': 'year', 'Type': 'string'}]
)

# Create ETL job
job_config = ETLJobConfig(
    job_name="sensor-data-etl",
    script_location="s3://bucket/scripts/etl.py",
    role_arn="arn:aws:iam::account:role/GlueRole",
    worker_type="G.1X",
    number_of_workers=2
)

await manager.create_etl_job(job_config)

# Run job
job_run_id = await manager.start_job_run("sensor-data-etl")

# Check status
status = await manager.get_job_run_status("sensor-data-etl", job_run_id)
```

### 4. Spark Data Processor (`spark_processor.py`)

Implements distributed data processing using Apache Spark on Amazon EMR.

```python
from src.krishimitra.core.data_processing import (
    SparkDataProcessor, EMRClusterManager, EMRClusterConfig, SparkJobConfig
)

# Create EMR cluster
cluster_manager = EMRClusterManager()
cluster_config = EMRClusterConfig(
    cluster_name="data-processing-cluster",
    core_instance_count=3,
    auto_scaling_enabled=True,
    min_capacity=2,
    max_capacity=10
)

cluster_id = await cluster_manager.create_cluster(cluster_config)

# Initialize Spark processor
processor = SparkDataProcessor(cluster_manager)

# Submit Spark job
job_config = SparkJobConfig(
    job_name="SensorDataAggregation",
    script_location="s3://bucket/scripts/aggregate.py",
    arguments=["s3://input/", "s3://output/", "1 hour"]
)

step_id = await processor.submit_spark_job(cluster_id, job_config)

# Check job status
status = await processor.get_step_status(cluster_id, step_id)

# Aggregate sensor data
step_id = await processor.aggregate_sensor_data(
    input_path="s3://bucket/raw-data/",
    output_path="s3://bucket/aggregated/",
    aggregation_window="1 hour",
    cluster_id=cluster_id
)
```

### 5. S3 Lifecycle Manager (`lifecycle_manager.py`)

Manages S3 lifecycle policies and Intelligent Tiering for cost optimization.

```python
from src.krishimitra.core.data_processing import (
    S3LifecycleManager, LifecycleRule, IntelligentTieringConfig
)

manager = S3LifecycleManager()

# Create lifecycle policy
rules = [
    LifecycleRule(
        rule_id="sensor-data-lifecycle",
        prefix="sensor-data/",
        transition_to_ia_days=30,
        transition_to_glacier_days=90,
        transition_to_deep_archive_days=180,
        expiration_days=1825  # 5 years
    )
]

await manager.create_lifecycle_policy(rules)

# Enable Intelligent Tiering
config = IntelligentTieringConfig(
    config_id="auto-tiering",
    prefix="sensor-data/",
    archive_access_tier_days=90,
    deep_archive_access_tier_days=180
)

await manager.enable_intelligent_tiering(config)

# Get storage metrics
metrics = await manager.get_storage_metrics(prefix="sensor-data/")
print(f"Total objects: {metrics['total_objects']}")
print(f"Total size: {metrics['total_size_gb']:.2f} GB")

# Optimize costs
recommendations = await manager.optimize_storage_costs()
print(f"Potential savings: ${recommendations['total_potential_savings']:.2f}/month")
```

### 6. Data Archiver (`lifecycle_manager.py`)

Handles data archiving and retrieval from Glacier storage.

```python
from src.krishimitra.core.data_processing import DataArchiver

archiver = DataArchiver()

# Archive old data
result = await archiver.archive_old_data(
    prefix="sensor-data/",
    age_days=90,
    target_storage_class="GLACIER"
)
print(f"Archived {result['archived_count']} objects")

# Restore archived data
await archiver.restore_archived_data(
    key="sensor-data/2023/01/data.parquet",
    days=7,
    tier="Standard"  # or "Expedited" for faster retrieval
)

# Check restore status
status = await archiver.check_restore_status("sensor-data/2023/01/data.parquet")
if status['available']:
    print("Data is available for access")

# Cleanup expired data
result = await archiver.cleanup_expired_data(
    prefix="logs/",
    retention_days=90
)
```

### 7. Performance Monitor (`performance_monitor.py`)

Provides performance profiling and monitoring capabilities.

```python
from src.krishimitra.core.data_processing import (
    PerformanceMonitor, ResourceThresholds
)

monitor = PerformanceMonitor()

# Profile function execution
@monitor.profile_function
def process_data(data):
    # Your processing logic
    return processed_data

# Monitor resources with thresholds
@monitor.monitor_resources(ResourceThresholds(
    max_memory_mb=512,
    max_cpu_percent=80,
    max_execution_time_seconds=60
))
def heavy_processing(data):
    # Your processing logic
    return result

# Get metrics summary
summary = monitor.get_metrics_summary(function_name="process_data", hours=24)
print(f"Average execution time: {summary['execution_time']['avg']:.2f}s")
print(f"Average memory usage: {summary['memory_usage_mb']['avg']:.2f}MB")

# Identify bottlenecks
bottlenecks = monitor.identify_bottlenecks()
for bottleneck in bottlenecks:
    print(f"{bottleneck['type']}: {bottleneck['recommendation']}")
```

### 8. Resource Optimizer (`performance_monitor.py`)

Optimizes resource allocation and usage.

```python
from src.krishimitra.core.data_processing import ResourceOptimizer

optimizer = ResourceOptimizer()

# Analyze resource utilization
analysis = await optimizer.analyze_resource_utilization(
    resource_id="my-service",
    service_namespace="ecs"
)

print(f"CPU utilization: {analysis['cpu_utilization']['average']:.1f}%")
print(f"Recommendations: {analysis['recommendations']}")

# Optimize batch size
def process_batch(batch_size):
    # Your batch processing logic
    pass

optimal_size = await optimizer.optimize_batch_size(
    processing_function=process_batch,
    test_sizes=[10, 50, 100, 500, 1000]
)
print(f"Optimal batch size: {optimal_size}")
```

### 9. Pipeline Orchestrator (`pipeline_orchestrator.py`)

Orchestrates the complete data processing pipeline.

```python
from src.krishimitra.core.data_processing.pipeline_orchestrator import DataProcessingPipeline

# Initialize pipeline
pipeline = DataProcessingPipeline()
await pipeline.initialize_pipeline()

# Ingest sensor data
sensor_data = [
    {"device_id": "S001", "sensor_type": "temperature", "value": 25.5, "timestamp": "2024-01-01T10:00:00Z"},
    {"device_id": "S002", "sensor_type": "humidity", "value": 65.0, "timestamp": "2024-01-01T10:00:00Z"}
]
await pipeline.ingest_sensor_data(sensor_data)

# Process with Spark
step_id = await pipeline.process_with_spark(
    input_path="s3://bucket/raw-data/",
    output_path="s3://bucket/processed/",
    job_type="aggregate"
)

# Archive old data
results = await pipeline.archive_old_data(days=90)

# Optimize resources
optimization = await pipeline.optimize_resources()
print(f"Storage metrics: {optimization['storage_metrics']}")
print(f"Cost savings: ${optimization['cost_recommendations']['total_potential_savings']:.2f}")

# Cleanup
await pipeline.cleanup()
```

## Spark Scripts

The module includes pre-built Spark scripts for common operations:

### Sensor Data Aggregation (`spark_scripts/sensor_data_aggregation.py`)

Aggregates sensor data by time windows:

```bash
spark-submit sensor_data_aggregation.py \
  s3://bucket/raw-data/ \
  s3://bucket/aggregated/ \
  "1 hour"
```

### Data Partitioning (`spark_scripts/data_partitioning.py`)

Repartitions data for optimal storage:

```bash
spark-submit data_partitioning.py \
  s3://bucket/input/ \
  s3://bucket/output/ \
  "year,month,sensor_type"
```

## Best Practices

### 1. Data Ingestion

- Use batch ingestion for better throughput (500 records per batch)
- Implement proper partition keys for even shard distribution
- Enable enhanced monitoring for production workloads
- Use buffering to reduce API calls

### 2. ETL Processing

- Partition data by time and frequently queried dimensions
- Use Glue crawlers for automatic schema discovery
- Monitor job metrics and optimize worker allocation
- Implement proper error handling and retry logic

### 3. Spark Processing

- Enable adaptive query execution for better performance
- Use appropriate partition sizes (128MB recommended)
- Leverage auto-scaling for variable workloads
- Cache frequently accessed datasets

### 4. Storage Optimization

- Implement lifecycle policies for all data types
- Use Intelligent Tiering for automatic cost optimization
- Archive historical data to Glacier/Deep Archive
- Monitor storage metrics and optimize regularly

### 5. Performance Monitoring

- Profile critical functions in development
- Set appropriate resource thresholds
- Monitor CloudWatch metrics regularly
- Identify and address bottlenecks proactively

## Cost Optimization

The module implements several cost optimization strategies:

1. **Automatic Data Tiering** - Moves infrequently accessed data to cheaper storage classes
2. **Lifecycle Policies** - Automatically archives and expires old data
3. **Auto-Scaling** - Scales EMR clusters based on workload
4. **Batch Processing** - Reduces API calls and improves throughput
5. **Resource Monitoring** - Identifies underutilized resources

Expected cost savings:
- 50-70% reduction in storage costs through tiering
- 30-40% reduction in compute costs through auto-scaling
- 20-30% reduction in data transfer costs through optimization

## Monitoring and Alerts

The module integrates with CloudWatch for comprehensive monitoring:

- **Stream Metrics**: Incoming records, bytes, iterator age
- **Job Metrics**: Execution time, success rate, DPU usage
- **Storage Metrics**: Object count, size, storage class distribution
- **Performance Metrics**: Function execution time, memory usage, CPU utilization

## Requirements

- Python 3.9+
- boto3
- psutil
- Apache Spark 3.4+ (for EMR jobs)
- AWS credentials with appropriate permissions

## AWS Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "kinesis:*",
        "glue:*",
        "emr:*",
        "s3:*",
        "cloudwatch:*",
        "iam:PassRole"
      ],
      "Resource": "*"
    }
  ]
}
```

## Testing

Run tests with pytest:

```bash
pytest tests/test_data_processing.py -v
```

## Support

For issues or questions, please refer to the main KrishiMitra documentation or contact the development team.
