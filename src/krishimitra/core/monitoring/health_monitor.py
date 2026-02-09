"""
System health monitoring for KrishiMitra platform.

This module implements comprehensive health checks for all system components
including API endpoints, agents, databases, and external services.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class SystemHealthStatus(Enum):
    """System health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentType(Enum):
    """Types of system components."""
    API_GATEWAY = "api_gateway"
    LAMBDA_FUNCTION = "lambda_function"
    DATABASE = "database"
    CACHE = "cache"
    STORAGE = "storage"
    AI_SERVICE = "ai_service"
    IOT_SERVICE = "iot_service"
    EXTERNAL_API = "external_api"


@dataclass
class ComponentHealth:
    """Health status of a system component."""
    component_name: str
    component_type: ComponentType
    status: SystemHealthStatus
    response_time_ms: Optional[float] = None
    error_rate: Optional[float] = None
    last_check: datetime = field(default_factory=datetime.utcnow)
    message: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemHealth:
    """Overall system health status."""
    overall_status: SystemHealthStatus
    components: List[ComponentHealth]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    healthy_count: int = 0
    degraded_count: int = 0
    unhealthy_count: int = 0
    
    def __post_init__(self):
        """Calculate component counts."""
        self.healthy_count = sum(
            1 for c in self.components 
            if c.status == SystemHealthStatus.HEALTHY
        )
        self.degraded_count = sum(
            1 for c in self.components 
            if c.status == SystemHealthStatus.DEGRADED
        )
        self.unhealthy_count = sum(
            1 for c in self.components 
            if c.status == SystemHealthStatus.UNHEALTHY
        )


class HealthMonitor:
    """
    Monitors health of all KrishiMitra system components.
    
    Implements comprehensive health checks, performance monitoring,
    and availability tracking for all services.
    """
    
    def __init__(
        self,
        region: str = "ap-south-1",
        check_interval_seconds: int = 60
    ):
        """
        Initialize health monitor.
        
        Args:
            region: AWS region
            check_interval_seconds: Interval between health checks
        """
        self.region = region
        self.check_interval_seconds = check_interval_seconds
        
        # AWS clients
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.dynamodb_client = boto3.client('dynamodb', region_name=region)
        self.s3_client = boto3.client('s3', region_name=region)
        self.elasticache_client = boto3.client('elasticache', region_name=region)
        
        # Health check thresholds
        self.thresholds = {
            'response_time_ms': 3000,  # 3 seconds
            'error_rate_percent': 5.0,  # 5%
            'cpu_utilization_percent': 80.0,  # 80%
            'memory_utilization_percent': 85.0,  # 85%
        }
    
    def check_lambda_health(
        self,
        function_name: str,
        period_minutes: int = 5
    ) -> ComponentHealth:
        """
        Check health of a Lambda function.
        
        Args:
            function_name: Lambda function name
            period_minutes: Period for metrics analysis
            
        Returns:
            Component health status
        """
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=period_minutes)
            
            # Get function metrics
            metrics = self._get_lambda_metrics(
                function_name,
                start_time,
                end_time
            )
            
            # Determine health status
            status = SystemHealthStatus.HEALTHY
            message = "Function operating normally"
            
            if metrics['error_rate'] > self.thresholds['error_rate_percent']:
                status = SystemHealthStatus.UNHEALTHY
                message = f"High error rate: {metrics['error_rate']:.2f}%"
            elif metrics['avg_duration'] > self.thresholds['response_time_ms']:
                status = SystemHealthStatus.DEGRADED
                message = f"Slow response time: {metrics['avg_duration']:.0f}ms"
            elif metrics['throttles'] > 0:
                status = SystemHealthStatus.DEGRADED
                message = f"Function throttled {metrics['throttles']} times"
            
            return ComponentHealth(
                component_name=function_name,
                component_type=ComponentType.LAMBDA_FUNCTION,
                status=status,
                response_time_ms=metrics['avg_duration'],
                error_rate=metrics['error_rate'],
                message=message,
                metrics=metrics
            )
        except Exception as e:
            logger.error(f"Failed to check Lambda health: {e}")
            return ComponentHealth(
                component_name=function_name,
                component_type=ComponentType.LAMBDA_FUNCTION,
                status=SystemHealthStatus.UNKNOWN,
                message=f"Health check failed: {str(e)}"
            )
    
    def check_dynamodb_health(
        self,
        table_name: str
    ) -> ComponentHealth:
        """
        Check health of a DynamoDB table.
        
        Args:
            table_name: DynamoDB table name
            
        Returns:
            Component health status
        """
        try:
            # Describe table
            response = self.dynamodb_client.describe_table(
                TableName=table_name
            )
            
            table = response['Table']
            table_status = table['TableStatus']
            
            # Check table status
            if table_status == 'ACTIVE':
                status = SystemHealthStatus.HEALTHY
                message = "Table active and available"
            elif table_status in ['CREATING', 'UPDATING']:
                status = SystemHealthStatus.DEGRADED
                message = f"Table in {table_status} state"
            else:
                status = SystemHealthStatus.UNHEALTHY
                message = f"Table in {table_status} state"
            
            # Get table metrics
            metrics = {
                'table_status': table_status,
                'item_count': table.get('ItemCount', 0),
                'table_size_bytes': table.get('TableSizeBytes', 0),
            }
            
            return ComponentHealth(
                component_name=table_name,
                component_type=ComponentType.DATABASE,
                status=status,
                message=message,
                metrics=metrics
            )
        except Exception as e:
            logger.error(f"Failed to check DynamoDB health: {e}")
            return ComponentHealth(
                component_name=table_name,
                component_type=ComponentType.DATABASE,
                status=SystemHealthStatus.UNKNOWN,
                message=f"Health check failed: {str(e)}"
            )
    
    def check_s3_health(
        self,
        bucket_name: str
    ) -> ComponentHealth:
        """
        Check health of an S3 bucket.
        
        Args:
            bucket_name: S3 bucket name
            
        Returns:
            Component health status
        """
        try:
            # Check bucket exists and is accessible
            self.s3_client.head_bucket(Bucket=bucket_name)
            
            # Get bucket metrics
            try:
                response = self.s3_client.get_bucket_location(
                    Bucket=bucket_name
                )
                location = response.get('LocationConstraint', 'us-east-1')
            except:
                location = 'unknown'
            
            return ComponentHealth(
                component_name=bucket_name,
                component_type=ComponentType.STORAGE,
                status=SystemHealthStatus.HEALTHY,
                message="Bucket accessible",
                metrics={'location': location}
            )
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                status = SystemHealthStatus.UNHEALTHY
                message = "Bucket not found"
            elif error_code == '403':
                status = SystemHealthStatus.UNHEALTHY
                message = "Access denied"
            else:
                status = SystemHealthStatus.UNKNOWN
                message = f"Error: {error_code}"
            
            return ComponentHealth(
                component_name=bucket_name,
                component_type=ComponentType.STORAGE,
                status=status,
                message=message
            )
        except Exception as e:
            logger.error(f"Failed to check S3 health: {e}")
            return ComponentHealth(
                component_name=bucket_name,
                component_type=ComponentType.STORAGE,
                status=SystemHealthStatus.UNKNOWN,
                message=f"Health check failed: {str(e)}"
            )
    
    def check_elasticache_health(
        self,
        cluster_id: str
    ) -> ComponentHealth:
        """
        Check health of an ElastiCache cluster.
        
        Args:
            cluster_id: ElastiCache cluster ID
            
        Returns:
            Component health status
        """
        try:
            response = self.elasticache_client.describe_cache_clusters(
                CacheClusterId=cluster_id,
                ShowCacheNodeInfo=True
            )
            
            if not response['CacheClusters']:
                return ComponentHealth(
                    component_name=cluster_id,
                    component_type=ComponentType.CACHE,
                    status=SystemHealthStatus.UNHEALTHY,
                    message="Cluster not found"
                )
            
            cluster = response['CacheClusters'][0]
            cluster_status = cluster['CacheClusterStatus']
            
            # Check cluster status
            if cluster_status == 'available':
                status = SystemHealthStatus.HEALTHY
                message = "Cluster available"
            elif cluster_status in ['creating', 'modifying', 'snapshotting']:
                status = SystemHealthStatus.DEGRADED
                message = f"Cluster {cluster_status}"
            else:
                status = SystemHealthStatus.UNHEALTHY
                message = f"Cluster {cluster_status}"
            
            metrics = {
                'status': cluster_status,
                'engine': cluster.get('Engine', 'unknown'),
                'num_nodes': cluster.get('NumCacheNodes', 0),
            }
            
            return ComponentHealth(
                component_name=cluster_id,
                component_type=ComponentType.CACHE,
                status=status,
                message=message,
                metrics=metrics
            )
        except Exception as e:
            logger.error(f"Failed to check ElastiCache health: {e}")
            return ComponentHealth(
                component_name=cluster_id,
                component_type=ComponentType.CACHE,
                status=SystemHealthStatus.UNKNOWN,
                message=f"Health check failed: {str(e)}"
            )
    
    def check_system_health(
        self,
        components: Dict[str, Dict[str, str]]
    ) -> SystemHealth:
        """
        Check health of all system components.
        
        Args:
            components: Dictionary of components to check
                Format: {
                    'lambda_functions': ['func1', 'func2'],
                    'dynamodb_tables': ['table1', 'table2'],
                    's3_buckets': ['bucket1', 'bucket2'],
                    'elasticache_clusters': ['cluster1']
                }
            
        Returns:
            Overall system health status
        """
        component_healths = []
        
        # Check Lambda functions
        for func_name in components.get('lambda_functions', []):
            health = self.check_lambda_health(func_name)
            component_healths.append(health)
        
        # Check DynamoDB tables
        for table_name in components.get('dynamodb_tables', []):
            health = self.check_dynamodb_health(table_name)
            component_healths.append(health)
        
        # Check S3 buckets
        for bucket_name in components.get('s3_buckets', []):
            health = self.check_s3_health(bucket_name)
            component_healths.append(health)
        
        # Check ElastiCache clusters
        for cluster_id in components.get('elasticache_clusters', []):
            health = self.check_elasticache_health(cluster_id)
            component_healths.append(health)
        
        # Determine overall health
        overall_status = self._determine_overall_health(component_healths)
        
        return SystemHealth(
            overall_status=overall_status,
            components=component_healths
        )
    
    def _get_lambda_metrics(
        self,
        function_name: str,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, float]:
        """Get Lambda function metrics from CloudWatch."""
        try:
            # Get invocations
            invocations = self._get_metric_sum(
                'AWS/Lambda',
                'Invocations',
                start_time,
                end_time,
                {'FunctionName': function_name}
            )
            
            # Get errors
            errors = self._get_metric_sum(
                'AWS/Lambda',
                'Errors',
                start_time,
                end_time,
                {'FunctionName': function_name}
            )
            
            # Get duration
            duration = self._get_metric_average(
                'AWS/Lambda',
                'Duration',
                start_time,
                end_time,
                {'FunctionName': function_name}
            )
            
            # Get throttles
            throttles = self._get_metric_sum(
                'AWS/Lambda',
                'Throttles',
                start_time,
                end_time,
                {'FunctionName': function_name}
            )
            
            error_rate = (errors / invocations * 100) if invocations > 0 else 0
            
            return {
                'invocations': invocations,
                'errors': errors,
                'error_rate': error_rate,
                'avg_duration': duration,
                'throttles': throttles
            }
        except Exception as e:
            logger.error(f"Failed to get Lambda metrics: {e}")
            return {
                'invocations': 0,
                'errors': 0,
                'error_rate': 0,
                'avg_duration': 0,
                'throttles': 0
            }
    
    def _get_metric_sum(
        self,
        namespace: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        dimensions: Dict[str, str]
    ) -> float:
        """Get sum of a CloudWatch metric."""
        try:
            response = self.cloudwatch_client.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=[
                    {'Name': k, 'Value': v} for k, v in dimensions.items()
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Sum']
            )
            
            datapoints = response.get('Datapoints', [])
            return sum(d['Sum'] for d in datapoints)
        except Exception:
            return 0.0
    
    def _get_metric_average(
        self,
        namespace: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        dimensions: Dict[str, str]
    ) -> float:
        """Get average of a CloudWatch metric."""
        try:
            response = self.cloudwatch_client.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=[
                    {'Name': k, 'Value': v} for k, v in dimensions.items()
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Average']
            )
            
            datapoints = response.get('Datapoints', [])
            if not datapoints:
                return 0.0
            return sum(d['Average'] for d in datapoints) / len(datapoints)
        except Exception:
            return 0.0
    
    def _determine_overall_health(
        self,
        component_healths: List[ComponentHealth]
    ) -> SystemHealthStatus:
        """Determine overall system health from component healths."""
        if not component_healths:
            return SystemHealthStatus.UNKNOWN
        
        # Count statuses
        unhealthy_count = sum(
            1 for c in component_healths 
            if c.status == SystemHealthStatus.UNHEALTHY
        )
        degraded_count = sum(
            1 for c in component_healths 
            if c.status == SystemHealthStatus.DEGRADED
        )
        
        # Determine overall status
        if unhealthy_count > 0:
            return SystemHealthStatus.UNHEALTHY
        elif degraded_count > 0:
            return SystemHealthStatus.DEGRADED
        else:
            return SystemHealthStatus.HEALTHY
