"""
Auto-scaling management for KrishiMitra platform.

This module implements automatic resource scaling based on demand using AWS Auto Scaling
and CloudWatch metrics to ensure optimal performance and cost-effectiveness.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class ScalingAction(Enum):
    """Scaling action types."""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NO_ACTION = "no_action"


@dataclass
class ScalingMetrics:
    """Metrics for scaling decisions."""
    cpu_utilization: float
    memory_utilization: float
    request_count: int
    error_rate: float
    response_time_ms: float
    timestamp: datetime
    
    def should_scale_up(
        self,
        cpu_threshold: float = 70.0,
        memory_threshold: float = 80.0,
        response_time_threshold_ms: float = 3000.0
    ) -> bool:
        """Determine if scaling up is needed."""
        return (
            self.cpu_utilization > cpu_threshold or
            self.memory_utilization > memory_threshold or
            self.response_time_ms > response_time_threshold_ms
        )
    
    def should_scale_down(
        self,
        cpu_threshold: float = 30.0,
        memory_threshold: float = 40.0,
        response_time_threshold_ms: float = 1000.0
    ) -> bool:
        """Determine if scaling down is possible."""
        return (
            self.cpu_utilization < cpu_threshold and
            self.memory_utilization < memory_threshold and
            self.response_time_ms < response_time_threshold_ms
        )


class AutoScalingManager:
    """
    Manages automatic resource scaling for KrishiMitra platform.
    
    Implements AWS Auto Scaling policies and monitors CloudWatch metrics
    to automatically adjust compute resources based on demand.
    """
    
    def __init__(
        self,
        region: str = "ap-south-1",
        min_capacity: int = 2,
        max_capacity: int = 100,
        target_cpu_utilization: float = 70.0,
        target_memory_utilization: float = 75.0,
        scale_up_cooldown_seconds: int = 300,
        scale_down_cooldown_seconds: int = 600
    ):
        """
        Initialize auto-scaling manager.
        
        Args:
            region: AWS region
            min_capacity: Minimum number of instances
            max_capacity: Maximum number of instances
            target_cpu_utilization: Target CPU utilization percentage
            target_memory_utilization: Target memory utilization percentage
            scale_up_cooldown_seconds: Cooldown period after scaling up
            scale_down_cooldown_seconds: Cooldown period after scaling down
        """
        self.region = region
        self.min_capacity = min_capacity
        self.max_capacity = max_capacity
        self.target_cpu_utilization = target_cpu_utilization
        self.target_memory_utilization = target_memory_utilization
        self.scale_up_cooldown = timedelta(seconds=scale_up_cooldown_seconds)
        self.scale_down_cooldown = timedelta(seconds=scale_down_cooldown_seconds)
        
        # AWS clients
        self.autoscaling_client = boto3.client('application-autoscaling', region_name=region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
        self.lambda_client = boto3.client('lambda', region_name=region)
        
        # Scaling state
        self.last_scale_up_time: Optional[datetime] = None
        self.last_scale_down_time: Optional[datetime] = None
        self.current_capacity: int = min_capacity
    
    def register_scalable_target(
        self,
        resource_id: str,
        service_namespace: str = "lambda",
        scalable_dimension: str = "lambda:function:ProvisionedConcurrencyConfig:ProvisionedConcurrentExecutions"
    ) -> bool:
        """
        Register a scalable target with AWS Auto Scaling.
        
        Args:
            resource_id: Resource identifier (e.g., function:my-function:live)
            service_namespace: AWS service namespace
            scalable_dimension: Scalable dimension
            
        Returns:
            True if registration successful, False otherwise
        """
        try:
            self.autoscaling_client.register_scalable_target(
                ServiceNamespace=service_namespace,
                ResourceId=resource_id,
                ScalableDimension=scalable_dimension,
                MinCapacity=self.min_capacity,
                MaxCapacity=self.max_capacity
            )
            logger.info(f"Registered scalable target: {resource_id}")
            return True
        except ClientError as e:
            logger.error(f"Failed to register scalable target: {e}")
            return False
    
    def create_target_tracking_policy(
        self,
        resource_id: str,
        policy_name: str,
        target_value: float,
        metric_type: str = "LambdaProvisionedConcurrencyUtilization",
        service_namespace: str = "lambda",
        scalable_dimension: str = "lambda:function:ProvisionedConcurrencyConfig:ProvisionedConcurrentExecutions"
    ) -> bool:
        """
        Create a target tracking scaling policy.
        
        Args:
            resource_id: Resource identifier
            policy_name: Policy name
            target_value: Target metric value
            metric_type: Predefined metric type
            service_namespace: AWS service namespace
            scalable_dimension: Scalable dimension
            
        Returns:
            True if policy created successfully, False otherwise
        """
        try:
            self.autoscaling_client.put_scaling_policy(
                PolicyName=policy_name,
                ServiceNamespace=service_namespace,
                ResourceId=resource_id,
                ScalableDimension=scalable_dimension,
                PolicyType='TargetTrackingScaling',
                TargetTrackingScalingPolicyConfiguration={
                    'TargetValue': target_value,
                    'PredefinedMetricSpecification': {
                        'PredefinedMetricType': metric_type
                    },
                    'ScaleInCooldown': int(self.scale_down_cooldown.total_seconds()),
                    'ScaleOutCooldown': int(self.scale_up_cooldown.total_seconds())
                }
            )
            logger.info(f"Created target tracking policy: {policy_name}")
            return True
        except ClientError as e:
            logger.error(f"Failed to create scaling policy: {e}")
            return False
    
    def get_current_metrics(
        self,
        function_name: str,
        period_minutes: int = 5
    ) -> Optional[ScalingMetrics]:
        """
        Get current performance metrics from CloudWatch.
        
        Args:
            function_name: Lambda function name
            period_minutes: Metric period in minutes
            
        Returns:
            ScalingMetrics object or None if metrics unavailable
        """
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=period_minutes)
            
            # Get CPU utilization (approximated from duration)
            duration_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Duration',
                Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=period_minutes * 60,
                Statistics=['Average']
            )
            
            # Get invocation count
            invocations_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Invocations',
                Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=period_minutes * 60,
                Statistics=['Sum']
            )
            
            # Get error count
            errors_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Errors',
                Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=period_minutes * 60,
                Statistics=['Sum']
            )
            
            # Get concurrent executions
            concurrent_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='ConcurrentExecutions',
                Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=period_minutes * 60,
                Statistics=['Average']
            )
            
            # Extract metrics
            duration = duration_response['Datapoints'][0]['Average'] if duration_response['Datapoints'] else 0
            invocations = invocations_response['Datapoints'][0]['Sum'] if invocations_response['Datapoints'] else 0
            errors = errors_response['Datapoints'][0]['Sum'] if errors_response['Datapoints'] else 0
            concurrent = concurrent_response['Datapoints'][0]['Average'] if concurrent_response['Datapoints'] else 0
            
            # Calculate derived metrics
            error_rate = (errors / invocations * 100) if invocations > 0 else 0
            
            # Approximate CPU utilization from concurrent executions
            cpu_utilization = min((concurrent / self.current_capacity) * 100, 100) if self.current_capacity > 0 else 0
            
            # Approximate memory utilization (simplified)
            memory_utilization = cpu_utilization * 0.8  # Rough approximation
            
            return ScalingMetrics(
                cpu_utilization=cpu_utilization,
                memory_utilization=memory_utilization,
                request_count=int(invocations),
                error_rate=error_rate,
                response_time_ms=duration,
                timestamp=datetime.utcnow()
            )
        except (ClientError, IndexError, KeyError) as e:
            logger.error(f"Failed to get current metrics: {e}")
            return None
    
    def determine_scaling_action(
        self,
        metrics: ScalingMetrics
    ) -> ScalingAction:
        """
        Determine if scaling action is needed based on metrics.
        
        Args:
            metrics: Current performance metrics
            
        Returns:
            Scaling action to take
        """
        now = datetime.utcnow()
        
        # Check cooldown periods
        if self.last_scale_up_time and (now - self.last_scale_up_time) < self.scale_up_cooldown:
            logger.debug("Scale up cooldown period active")
            return ScalingAction.NO_ACTION
        
        if self.last_scale_down_time and (now - self.last_scale_down_time) < self.scale_down_cooldown:
            logger.debug("Scale down cooldown period active")
            return ScalingAction.NO_ACTION
        
        # Determine action based on metrics
        if metrics.should_scale_up():
            if self.current_capacity < self.max_capacity:
                logger.info(f"Scaling up recommended - CPU: {metrics.cpu_utilization}%, "
                          f"Memory: {metrics.memory_utilization}%, "
                          f"Response time: {metrics.response_time_ms}ms")
                return ScalingAction.SCALE_UP
        elif metrics.should_scale_down():
            if self.current_capacity > self.min_capacity:
                logger.info(f"Scaling down recommended - CPU: {metrics.cpu_utilization}%, "
                          f"Memory: {metrics.memory_utilization}%, "
                          f"Response time: {metrics.response_time_ms}ms")
                return ScalingAction.SCALE_DOWN
        
        return ScalingAction.NO_ACTION
    
    def scale_lambda_provisioned_concurrency(
        self,
        function_name: str,
        alias_name: str,
        desired_capacity: int
    ) -> bool:
        """
        Scale Lambda provisioned concurrency.
        
        Args:
            function_name: Lambda function name
            alias_name: Function alias name
            desired_capacity: Desired provisioned concurrency
            
        Returns:
            True if scaling successful, False otherwise
        """
        try:
            self.lambda_client.put_provisioned_concurrency_config(
                FunctionName=function_name,
                Qualifier=alias_name,
                ProvisionedConcurrentExecutions=desired_capacity
            )
            self.current_capacity = desired_capacity
            logger.info(f"Scaled {function_name}:{alias_name} to {desired_capacity} provisioned concurrency")
            return True
        except ClientError as e:
            logger.error(f"Failed to scale provisioned concurrency: {e}")
            return False
    
    def execute_scaling_action(
        self,
        action: ScalingAction,
        function_name: str,
        alias_name: str = "live",
        scale_factor: float = 1.5
    ) -> bool:
        """
        Execute a scaling action.
        
        Args:
            action: Scaling action to execute
            function_name: Lambda function name
            alias_name: Function alias name
            scale_factor: Multiplier for scaling up/down
            
        Returns:
            True if action executed successfully, False otherwise
        """
        if action == ScalingAction.NO_ACTION:
            return True
        
        if action == ScalingAction.SCALE_UP:
            new_capacity = min(int(self.current_capacity * scale_factor), self.max_capacity)
            if self.scale_lambda_provisioned_concurrency(function_name, alias_name, new_capacity):
                self.last_scale_up_time = datetime.utcnow()
                return True
        elif action == ScalingAction.SCALE_DOWN:
            new_capacity = max(int(self.current_capacity / scale_factor), self.min_capacity)
            if self.scale_lambda_provisioned_concurrency(function_name, alias_name, new_capacity):
                self.last_scale_down_time = datetime.utcnow()
                return True
        
        return False
    
    def get_scaling_activities(
        self,
        resource_id: str,
        service_namespace: str = "lambda",
        max_results: int = 10
    ) -> List[Dict]:
        """
        Get recent scaling activities.
        
        Args:
            resource_id: Resource identifier
            service_namespace: AWS service namespace
            max_results: Maximum number of results
            
        Returns:
            List of scaling activities
        """
        try:
            response = self.autoscaling_client.describe_scaling_activities(
                ServiceNamespace=service_namespace,
                ResourceId=resource_id,
                MaxResults=max_results
            )
            return response.get('ScalingActivities', [])
        except ClientError as e:
            logger.error(f"Failed to get scaling activities: {e}")
            return []
    
    def monitor_and_scale(
        self,
        function_name: str,
        alias_name: str = "live",
        check_interval_minutes: int = 5
    ) -> Dict:
        """
        Monitor metrics and execute scaling if needed.
        
        Args:
            function_name: Lambda function name
            alias_name: Function alias name
            check_interval_minutes: Interval for checking metrics
            
        Returns:
            Dictionary with scaling results
        """
        metrics = self.get_current_metrics(function_name, check_interval_minutes)
        
        if not metrics:
            return {
                "success": False,
                "error": "Failed to retrieve metrics",
                "action": ScalingAction.NO_ACTION.value
            }
        
        action = self.determine_scaling_action(metrics)
        success = self.execute_scaling_action(action, function_name, alias_name)
        
        return {
            "success": success,
            "action": action.value,
            "metrics": {
                "cpu_utilization": metrics.cpu_utilization,
                "memory_utilization": metrics.memory_utilization,
                "request_count": metrics.request_count,
                "error_rate": metrics.error_rate,
                "response_time_ms": metrics.response_time_ms
            },
            "current_capacity": self.current_capacity,
            "timestamp": metrics.timestamp.isoformat()
        }
