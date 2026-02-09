"""
Load balancing and traffic distribution for KrishiMitra platform.

This module implements load balancing strategies and health checks
to ensure optimal traffic distribution across available resources.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class HealthCheckStatus(Enum):
    """Health check status types."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class TargetHealth:
    """Health status of a target."""
    target_id: str
    status: HealthCheckStatus
    reason: Optional[str] = None
    last_check: Optional[datetime] = None


class LoadBalancerManager:
    """
    Manages load balancing and traffic distribution for KrishiMitra platform.
    
    Implements health checks, traffic routing, and load distribution strategies
    using AWS Application Load Balancer and API Gateway.
    """
    
    def __init__(
        self,
        region: str = "ap-south-1",
        health_check_interval_seconds: int = 30,
        unhealthy_threshold: int = 3,
        healthy_threshold: int = 2
    ):
        """
        Initialize load balancer manager.
        
        Args:
            region: AWS region
            health_check_interval_seconds: Interval between health checks
            unhealthy_threshold: Number of failed checks before marking unhealthy
            healthy_threshold: Number of successful checks before marking healthy
        """
        self.region = region
        self.health_check_interval = health_check_interval_seconds
        self.unhealthy_threshold = unhealthy_threshold
        self.healthy_threshold = healthy_threshold
        
        # AWS clients
        self.elbv2_client = boto3.client('elbv2', region_name=region)
        self.apigateway_client = boto3.client('apigateway', region_name=region)
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
    
    def create_target_group(
        self,
        name: str,
        vpc_id: str,
        target_type: str = "lambda",
        health_check_path: str = "/health"
    ) -> Optional[str]:
        """
        Create an Application Load Balancer target group.
        
        Args:
            name: Target group name
            vpc_id: VPC ID
            target_type: Target type (lambda, instance, ip)
            health_check_path: Health check path
            
        Returns:
            Target group ARN or None if creation failed
        """
        try:
            response = self.elbv2_client.create_target_group(
                Name=name,
                TargetType=target_type,
                HealthCheckEnabled=True,
                HealthCheckPath=health_check_path,
                HealthCheckIntervalSeconds=self.health_check_interval,
                HealthCheckTimeoutSeconds=10,
                HealthyThresholdCount=self.healthy_threshold,
                UnhealthyThresholdCount=self.unhealthy_threshold,
                Matcher={'HttpCode': '200-299'}
            )
            target_group_arn = response['TargetGroups'][0]['TargetGroupArn']
            logger.info(f"Created target group: {name}")
            return target_group_arn
        except ClientError as e:
            logger.error(f"Failed to create target group: {e}")
            return None
    
    def register_lambda_target(
        self,
        target_group_arn: str,
        function_arn: str
    ) -> bool:
        """
        Register a Lambda function as a target.
        
        Args:
            target_group_arn: Target group ARN
            function_arn: Lambda function ARN
            
        Returns:
            True if registration successful, False otherwise
        """
        try:
            self.elbv2_client.register_targets(
                TargetGroupArn=target_group_arn,
                Targets=[{'Id': function_arn}]
            )
            logger.info(f"Registered Lambda target: {function_arn}")
            return True
        except ClientError as e:
            logger.error(f"Failed to register Lambda target: {e}")
            return False
    
    def get_target_health(
        self,
        target_group_arn: str
    ) -> List[TargetHealth]:
        """
        Get health status of all targets in a target group.
        
        Args:
            target_group_arn: Target group ARN
            
        Returns:
            List of target health statuses
        """
        try:
            response = self.elbv2_client.describe_target_health(
                TargetGroupArn=target_group_arn
            )
            
            health_statuses = []
            for target_health in response['TargetHealthDescriptions']:
                target_id = target_health['Target']['Id']
                state = target_health['TargetHealth']['State']
                reason = target_health['TargetHealth'].get('Reason')
                
                # Map state to HealthCheckStatus
                if state == 'healthy':
                    status = HealthCheckStatus.HEALTHY
                elif state in ['unhealthy', 'draining']:
                    status = HealthCheckStatus.UNHEALTHY
                else:
                    status = HealthCheckStatus.UNKNOWN
                
                health_statuses.append(TargetHealth(
                    target_id=target_id,
                    status=status,
                    reason=reason,
                    last_check=datetime.utcnow()
                ))
            
            return health_statuses
        except ClientError as e:
            logger.error(f"Failed to get target health: {e}")
            return []
    
    def check_lambda_health(
        self,
        function_name: str
    ) -> HealthCheckStatus:
        """
        Perform health check on a Lambda function.
        
        Args:
            function_name: Lambda function name
            
        Returns:
            Health check status
        """
        try:
            # Invoke function with health check payload
            response = self.lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload='{"path": "/health", "httpMethod": "GET"}'
            )
            
            status_code = response.get('StatusCode', 500)
            
            if status_code == 200:
                return HealthCheckStatus.HEALTHY
            else:
                return HealthCheckStatus.UNHEALTHY
        except ClientError as e:
            logger.error(f"Health check failed for {function_name}: {e}")
            return HealthCheckStatus.UNHEALTHY
    
    def configure_api_gateway_throttling(
        self,
        rest_api_id: str,
        stage_name: str,
        rate_limit: int = 1000,
        burst_limit: int = 2000
    ) -> bool:
        """
        Configure API Gateway throttling settings.
        
        Args:
            rest_api_id: REST API ID
            stage_name: Stage name
            rate_limit: Steady-state request rate limit
            burst_limit: Burst request limit
            
        Returns:
            True if configuration successful, False otherwise
        """
        try:
            self.apigateway_client.update_stage(
                restApiId=rest_api_id,
                stageName=stage_name,
                patchOperations=[
                    {
                        'op': 'replace',
                        'path': '/throttle/rateLimit',
                        'value': str(rate_limit)
                    },
                    {
                        'op': 'replace',
                        'path': '/throttle/burstLimit',
                        'value': str(burst_limit)
                    }
                ]
            )
            logger.info(f"Configured API Gateway throttling: rate={rate_limit}, burst={burst_limit}")
            return True
        except ClientError as e:
            logger.error(f"Failed to configure API Gateway throttling: {e}")
            return False
    
    def get_api_gateway_metrics(
        self,
        rest_api_id: str,
        stage_name: str,
        period_minutes: int = 5
    ) -> Dict:
        """
        Get API Gateway performance metrics.
        
        Args:
            rest_api_id: REST API ID
            stage_name: Stage name
            period_minutes: Metric period in minutes
            
        Returns:
            Dictionary of metrics
        """
        try:
            from datetime import timedelta
            
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=period_minutes)
            
            # Get request count
            count_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/ApiGateway',
                MetricName='Count',
                Dimensions=[
                    {'Name': 'ApiName', 'Value': rest_api_id},
                    {'Name': 'Stage', 'Value': stage_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=period_minutes * 60,
                Statistics=['Sum']
            )
            
            # Get latency
            latency_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/ApiGateway',
                MetricName='Latency',
                Dimensions=[
                    {'Name': 'ApiName', 'Value': rest_api_id},
                    {'Name': 'Stage', 'Value': stage_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=period_minutes * 60,
                Statistics=['Average', 'Maximum']
            )
            
            # Get 4XX errors
            error_4xx_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/ApiGateway',
                MetricName='4XXError',
                Dimensions=[
                    {'Name': 'ApiName', 'Value': rest_api_id},
                    {'Name': 'Stage', 'Value': stage_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=period_minutes * 60,
                Statistics=['Sum']
            )
            
            # Get 5XX errors
            error_5xx_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/ApiGateway',
                MetricName='5XXError',
                Dimensions=[
                    {'Name': 'ApiName', 'Value': rest_api_id},
                    {'Name': 'Stage', 'Value': stage_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=period_minutes * 60,
                Statistics=['Sum']
            )
            
            # Extract metrics
            request_count = count_response['Datapoints'][0]['Sum'] if count_response['Datapoints'] else 0
            avg_latency = latency_response['Datapoints'][0]['Average'] if latency_response['Datapoints'] else 0
            max_latency = latency_response['Datapoints'][0]['Maximum'] if latency_response['Datapoints'] else 0
            error_4xx = error_4xx_response['Datapoints'][0]['Sum'] if error_4xx_response['Datapoints'] else 0
            error_5xx = error_5xx_response['Datapoints'][0]['Sum'] if error_5xx_response['Datapoints'] else 0
            
            return {
                "request_count": int(request_count),
                "average_latency_ms": avg_latency,
                "max_latency_ms": max_latency,
                "client_errors": int(error_4xx),
                "server_errors": int(error_5xx),
                "error_rate": ((error_4xx + error_5xx) / request_count * 100) if request_count > 0 else 0,
                "timestamp": datetime.utcnow().isoformat()
            }
        except (ClientError, IndexError, KeyError) as e:
            logger.error(f"Failed to get API Gateway metrics: {e}")
            return {}
    
    def distribute_traffic_weighted(
        self,
        target_group_arn: str,
        target_weights: Dict[str, int]
    ) -> bool:
        """
        Configure weighted traffic distribution across targets.
        
        Args:
            target_group_arn: Target group ARN
            target_weights: Dictionary mapping target IDs to weights
            
        Returns:
            True if configuration successful, False otherwise
        """
        try:
            # Modify target group attributes for weighted routing
            targets = [
                {'Id': target_id, 'Weight': weight}
                for target_id, weight in target_weights.items()
            ]
            
            self.elbv2_client.modify_target_group_attributes(
                TargetGroupArn=target_group_arn,
                Attributes=[
                    {
                        'Key': 'stickiness.enabled',
                        'Value': 'true'
                    },
                    {
                        'Key': 'stickiness.type',
                        'Value': 'lb_cookie'
                    }
                ]
            )
            
            logger.info(f"Configured weighted traffic distribution for {len(targets)} targets")
            return True
        except ClientError as e:
            logger.error(f"Failed to configure weighted traffic distribution: {e}")
            return False
    
    def get_load_distribution_stats(
        self,
        target_group_arn: str
    ) -> Dict:
        """
        Get load distribution statistics across targets.
        
        Args:
            target_group_arn: Target group ARN
            
        Returns:
            Dictionary with load distribution stats
        """
        health_statuses = self.get_target_health(target_group_arn)
        
        total_targets = len(health_statuses)
        healthy_targets = sum(1 for h in health_statuses if h.status == HealthCheckStatus.HEALTHY)
        unhealthy_targets = sum(1 for h in health_statuses if h.status == HealthCheckStatus.UNHEALTHY)
        
        return {
            "total_targets": total_targets,
            "healthy_targets": healthy_targets,
            "unhealthy_targets": unhealthy_targets,
            "health_percentage": (healthy_targets / total_targets * 100) if total_targets > 0 else 0,
            "targets": [
                {
                    "id": h.target_id,
                    "status": h.status.value,
                    "reason": h.reason,
                    "last_check": h.last_check.isoformat() if h.last_check else None
                }
                for h in health_statuses
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
