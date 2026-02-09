"""
Apache Spark Data Processor on AWS EMR

This module implements distributed data processing using Apache Spark
on Amazon EMR for large-scale agricultural data analytics.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

from src.krishimitra.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EMRClusterConfig:
    """Configuration for EMR cluster"""
    cluster_name: str
    release_label: str = "emr-6.15.0"  # Latest EMR version with Spark 3.4
    instance_type: str = "m5.xlarge"
    instance_count: int = 3
    master_instance_type: str = "m5.xlarge"
    core_instance_type: str = "m5.xlarge"
    core_instance_count: int = 2
    task_instance_type: Optional[str] = "m5.xlarge"
    task_instance_count: int = 0
    auto_scaling_enabled: bool = True
    min_capacity: int = 2
    max_capacity: int = 10
    log_uri: Optional[str] = None
    applications: List[str] = None
    
    def __post_init__(self):
        if self.applications is None:
            self.applications = ['Spark', 'Hadoop', 'Hive', 'Livy']
        if self.log_uri is None:
            self.log_uri = f's3://{settings.s3_bucket}/emr-logs/'


@dataclass
class SparkJobConfig:
    """Configuration for Spark job"""
    job_name: str
    script_location: str
    arguments: List[str]
    spark_submit_parameters: Optional[str] = None
    action_on_failure: str = "CONTINUE"
    
    def __post_init__(self):
        if self.spark_submit_parameters is None:
            self.spark_submit_parameters = (
                "--conf spark.dynamicAllocation.enabled=true "
                "--conf spark.shuffle.service.enabled=true "
                "--conf spark.sql.adaptive.enabled=true "
                "--conf spark.sql.adaptive.coalescePartitions.enabled=true"
            )


class EMRClusterManager:
    """
    Manages AWS EMR clusters for Spark processing
    
    Handles cluster lifecycle, auto-scaling, and cost optimization
    for distributed data processing workloads.
    """
    
    def __init__(self):
        self.emr_client = boto3.client('emr', region_name=settings.aws_region)
        self.cloudwatch = boto3.client('cloudwatch', region_name=settings.aws_region)
    
    async def create_cluster(self, config: EMRClusterConfig) -> Optional[str]:
        """
        Create EMR cluster with specified configuration
        
        Args:
            config: EMR cluster configuration
            
        Returns:
            Cluster ID if successful, None otherwise
        """
        try:
            # Build instance groups configuration
            instance_groups = [
                {
                    'Name': 'Master',
                    'InstanceRole': 'MASTER',
                    'InstanceType': config.master_instance_type,
                    'InstanceCount': 1
                },
                {
                    'Name': 'Core',
                    'InstanceRole': 'CORE',
                    'InstanceType': config.core_instance_type,
                    'InstanceCount': config.core_instance_count
                }
            ]
            
            # Add task instances if configured
            if config.task_instance_count > 0:
                instance_groups.append({
                    'Name': 'Task',
                    'InstanceRole': 'TASK',
                    'InstanceType': config.task_instance_type,
                    'InstanceCount': config.task_instance_count
                })
            
            # Build applications list
            applications = [{'Name': app} for app in config.applications]
            
            # Create cluster
            cluster_params = {
                'Name': config.cluster_name,
                'ReleaseLabel': config.release_label,
                'Instances': {
                    'InstanceGroups': instance_groups,
                    'KeepJobFlowAliveWhenNoSteps': True,
                    'TerminationProtected': False
                },
                'Applications': applications,
                'LogUri': config.log_uri,
                'ServiceRole': 'EMR_DefaultRole',
                'JobFlowRole': 'EMR_EC2_DefaultRole',
                'VisibleToAllUsers': True,
                'Tags': [
                    {'Key': 'Project', 'Value': 'KrishiMitra'},
                    {'Key': 'Environment', 'Value': settings.environment}
                ]
            }
            
            # Add auto-scaling if enabled
            if config.auto_scaling_enabled:
                cluster_params['AutoScalingRole'] = 'EMR_AutoScaling_DefaultRole'
            
            response = self.emr_client.run_job_flow(**cluster_params)
            cluster_id = response['JobFlowId']
            
            # Configure auto-scaling for core instances
            if config.auto_scaling_enabled:
                await self._configure_auto_scaling(
                    cluster_id, 
                    config.min_capacity, 
                    config.max_capacity
                )
            
            logger.info(f"Created EMR cluster: {cluster_id}")
            return cluster_id
            
        except Exception as e:
            logger.error(f"Error creating EMR cluster: {e}")
            return None
    
    async def _configure_auto_scaling(self, cluster_id: str, 
                                     min_capacity: int, max_capacity: int):
        """Configure auto-scaling policy for cluster"""
        try:
            # Get instance group ID for core instances
            response = self.emr_client.list_instance_groups(ClusterId=cluster_id)
            core_group = next(
                (g for g in response['InstanceGroups'] if g['InstanceGroupType'] == 'CORE'),
                None
            )
            
            if not core_group:
                return
            
            instance_group_id = core_group['Id']
            
            # Create auto-scaling policy
            auto_scaling_policy = {
                'Constraints': {
                    'MinCapacity': min_capacity,
                    'MaxCapacity': max_capacity
                },
                'Rules': [
                    {
                        'Name': 'ScaleOutOnYARNMemory',
                        'Action': {
                            'SimpleScalingPolicyConfiguration': {
                                'AdjustmentType': 'CHANGE_IN_CAPACITY',
                                'ScalingAdjustment': 1,
                                'CoolDown': 300
                            }
                        },
                        'Trigger': {
                            'CloudWatchAlarmDefinition': {
                                'ComparisonOperator': 'LESS_THAN',
                                'EvaluationPeriods': 1,
                                'MetricName': 'YARNMemoryAvailablePercentage',
                                'Namespace': 'AWS/ElasticMapReduce',
                                'Period': 300,
                                'Statistic': 'AVERAGE',
                                'Threshold': 15.0,
                                'Unit': 'PERCENT'
                            }
                        }
                    },
                    {
                        'Name': 'ScaleInOnYARNMemory',
                        'Action': {
                            'SimpleScalingPolicyConfiguration': {
                                'AdjustmentType': 'CHANGE_IN_CAPACITY',
                                'ScalingAdjustment': -1,
                                'CoolDown': 300
                            }
                        },
                        'Trigger': {
                            'CloudWatchAlarmDefinition': {
                                'ComparisonOperator': 'GREATER_THAN',
                                'EvaluationPeriods': 1,
                                'MetricName': 'YARNMemoryAvailablePercentage',
                                'Namespace': 'AWS/ElasticMapReduce',
                                'Period': 300,
                                'Statistic': 'AVERAGE',
                                'Threshold': 75.0,
                                'Unit': 'PERCENT'
                            }
                        }
                    }
                ]
            }
            
            self.emr_client.put_auto_scaling_policy(
                ClusterId=cluster_id,
                InstanceGroupId=instance_group_id,
                AutoScalingPolicy=auto_scaling_policy
            )
            
            logger.info(f"Configured auto-scaling for cluster {cluster_id}")
            
        except Exception as e:
            logger.error(f"Error configuring auto-scaling: {e}")
    
    async def get_cluster_status(self, cluster_id: str) -> Dict[str, Any]:
        """Get cluster status and details"""
        try:
            response = self.emr_client.describe_cluster(ClusterId=cluster_id)
            cluster = response['Cluster']
            
            return {
                'cluster_id': cluster_id,
                'name': cluster['Name'],
                'state': cluster['Status']['State'],
                'state_change_reason': cluster['Status'].get('StateChangeReason', {}),
                'created_at': cluster['Status']['Timeline'].get('CreationDateTime'),
                'ready_at': cluster['Status']['Timeline'].get('ReadyDateTime'),
                'master_public_dns': cluster.get('MasterPublicDnsName'),
                'normalized_instance_hours': cluster.get('NormalizedInstanceHours')
            }
            
        except Exception as e:
            logger.error(f"Error getting cluster status: {e}")
            return {'state': 'UNKNOWN', 'error': str(e)}
    
    async def terminate_cluster(self, cluster_id: str) -> bool:
        """Terminate EMR cluster"""
        try:
            self.emr_client.terminate_job_flows(JobFlowIds=[cluster_id])
            logger.info(f"Terminated EMR cluster: {cluster_id}")
            return True
        except Exception as e:
            logger.error(f"Error terminating cluster: {e}")
            return False
    
    async def list_active_clusters(self) -> List[Dict[str, Any]]:
        """List all active EMR clusters"""
        try:
            response = self.emr_client.list_clusters(
                ClusterStates=['STARTING', 'BOOTSTRAPPING', 'RUNNING', 'WAITING']
            )
            
            clusters = []
            for cluster in response.get('Clusters', []):
                clusters.append({
                    'cluster_id': cluster['Id'],
                    'name': cluster['Name'],
                    'state': cluster['Status']['State'],
                    'created_at': cluster['Status']['Timeline'].get('CreationDateTime')
                })
            
            return clusters
            
        except Exception as e:
            logger.error(f"Error listing clusters: {e}")
            return []


class SparkDataProcessor:
    """
    Distributed data processing using Apache Spark on EMR
    
    Implements data partitioning, transformation, and aggregation
    for large-scale agricultural datasets.
    """
    
    def __init__(self, cluster_manager: EMRClusterManager):
        self.cluster_manager = cluster_manager
        self.emr_client = boto3.client('emr', region_name=settings.aws_region)
        self.s3_client = boto3.client('s3', region_name=settings.aws_region)
    
    async def submit_spark_job(self, cluster_id: str, 
                               config: SparkJobConfig) -> Optional[str]:
        """
        Submit Spark job to EMR cluster
        
        Args:
            cluster_id: EMR cluster ID
            config: Spark job configuration
            
        Returns:
            Step ID if successful, None otherwise
        """
        try:
            step_config = {
                'Name': config.job_name,
                'ActionOnFailure': config.action_on_failure,
                'HadoopJarStep': {
                    'Jar': 'command-runner.jar',
                    'Args': [
                        'spark-submit',
                        config.spark_submit_parameters,
                        config.script_location
                    ] + config.arguments
                }
            }
            
            response = self.emr_client.add_job_flow_steps(
                JobFlowId=cluster_id,
                Steps=[step_config]
            )
            
            step_id = response['StepIds'][0]
            logger.info(f"Submitted Spark job: {config.job_name} (Step ID: {step_id})")
            return step_id
            
        except Exception as e:
            logger.error(f"Error submitting Spark job: {e}")
            return None
    
    async def get_step_status(self, cluster_id: str, step_id: str) -> Dict[str, Any]:
        """Get Spark job step status"""
        try:
            response = self.emr_client.describe_step(
                ClusterId=cluster_id,
                StepId=step_id
            )
            
            step = response['Step']
            
            return {
                'step_id': step_id,
                'name': step['Name'],
                'state': step['Status']['State'],
                'state_change_reason': step['Status'].get('StateChangeReason', {}),
                'created_at': step['Status']['Timeline'].get('CreationDateTime'),
                'started_at': step['Status']['Timeline'].get('StartDateTime'),
                'ended_at': step['Status']['Timeline'].get('EndDateTime')
            }
            
        except Exception as e:
            logger.error(f"Error getting step status: {e}")
            return {'state': 'UNKNOWN', 'error': str(e)}
    
    async def create_partitioned_dataset(self, input_path: str, output_path: str,
                                        partition_columns: List[str],
                                        cluster_id: str) -> Optional[str]:
        """
        Create partitioned dataset using Spark
        
        Args:
            input_path: S3 input path
            output_path: S3 output path
            partition_columns: Columns to partition by
            cluster_id: EMR cluster ID
            
        Returns:
            Step ID if successful
        """
        # Generate Spark script for partitioning
        script_content = f"""
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("DataPartitioning").getOrCreate()

# Read input data
df = spark.read.parquet("{input_path}")

# Write partitioned data
df.write.mode("overwrite").partitionBy({partition_columns}).parquet("{output_path}")

spark.stop()
"""
        
        # Upload script to S3
        script_key = f"spark-scripts/partition_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
        script_location = f"s3://{settings.s3_bucket}/{script_key}"
        
        self.s3_client.put_object(
            Bucket=settings.s3_bucket,
            Key=script_key,
            Body=script_content.encode('utf-8')
        )
        
        # Submit job
        job_config = SparkJobConfig(
            job_name="DataPartitioning",
            script_location=script_location,
            arguments=[]
        )
        
        return await self.submit_spark_job(cluster_id, job_config)
    
    async def aggregate_sensor_data(self, input_path: str, output_path: str,
                                   aggregation_window: str,
                                   cluster_id: str) -> Optional[str]:
        """
        Aggregate sensor data using Spark
        
        Args:
            input_path: S3 input path
            output_path: S3 output path
            aggregation_window: Time window for aggregation (e.g., "1 hour")
            cluster_id: EMR cluster ID
            
        Returns:
            Step ID if successful
        """
        script_content = f"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import window, avg, max, min, count

spark = SparkSession.builder.appName("SensorDataAggregation").getOrCreate()

# Read sensor data
df = spark.read.parquet("{input_path}")

# Aggregate by time window
aggregated = df.groupBy(
    window("timestamp", "{aggregation_window}"),
    "device_id",
    "sensor_type"
).agg(
    avg("value").alias("avg_value"),
    max("value").alias("max_value"),
    min("value").alias("min_value"),
    count("*").alias("reading_count")
)

# Write aggregated data
aggregated.write.mode("overwrite").partitionBy("sensor_type").parquet("{output_path}")

spark.stop()
"""
        
        # Upload script to S3
        script_key = f"spark-scripts/aggregate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
        script_location = f"s3://{settings.s3_bucket}/{script_key}"
        
        self.s3_client.put_object(
            Bucket=settings.s3_bucket,
            Key=script_key,
            Body=script_content.encode('utf-8')
        )
        
        # Submit job
        job_config = SparkJobConfig(
            job_name="SensorDataAggregation",
            script_location=script_location,
            arguments=[]
        )
        
        return await self.submit_spark_job(cluster_id, job_config)
