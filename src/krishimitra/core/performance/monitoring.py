"""
Performance monitoring and alerting for KrishiMitra platform.

This module implements comprehensive performance monitoring using CloudWatch
and custom metrics to track system health and performance.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of performance metrics."""
    RESPONSE_TIME = "response_time"
    REQUEST_COUNT = "request_count"
    ERROR_RATE = "error_rate"
    CPU_UTILIZATION = "cpu_utilization"
    MEMORY_UTILIZATION = "memory_utilization"
    CONCURRENT_EXECUTIONS = "concurrent_executions"
    THROTTLES = "throttles"
    CUSTOM = "custom"


@dataclass
class PerformanceAlert:
    """Performance alert configuration."""
    metric_type: MetricType
    threshold: float
    comparison: str  # GreaterThanThreshold, LessThanThreshold, etc.
    evaluation_periods: int
    alarm_name: str
    alarm_description: str


class PerformanceMonitor:
    """
    Monitors system performance and generates alerts for KrishiMitra platform.
    
    Implements CloudWatch monitoring, custom metrics, and alerting to ensure
    system performance meets requirements.
    """
    
    def __init__(
        self,
        region: str = "ap-south-1",
        namespace: str = "KrishiMitra/Performance"
    ):
        """
        Initialize performance monitor.
        
        Args:
            region: AWS region
            namespace: CloudWatch namespace for custom metrics
        """
        self.region = region
        self.namespace = namespace
        
        # AWS clients
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
        self.sns_client = boto3.client('sns', region_name=region)
    
    def put_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "None",
        dimensions: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Put a custom metric to CloudWatch.
        
        Args:
            metric_name: Metric name
            value: Metric value
            unit: Metric unit
            dimensions: Metric dimensions
            timestamp: Metric timestamp
            
        Returns:
            True if metric published successfully, False otherwise
        """
        try:
            metric_data = {
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit,
                'Timestamp': timestamp or datetime.utcnow()
            }
            
            if dimensions:
                metric_data['Dimensions'] = [
                    {'Name': k, 'Value': v} for k, v in dimensions.items()
                ]
            
            self.cloudwatch_client.put_metric_data(
                Namespace=self.namespace,
                MetricData=[metric_data]
            )
            return True
        except ClientError as e:
            logger.error(f"Failed to put metric: {e}")
            return False
    
    def put_metrics_batch(
        self,
        metrics: List[Dict]
    ) -> bool:
        """
        Put multiple metrics to CloudWatch in a batch.
        
        Args:
            metrics: List of metric dictionaries
            
        Returns:
            True if metrics published successfully, False otherwise
        """
        try:
            metric_data = []
            for metric in metrics:
                data = {
                    'MetricName': metric['name'],
                    'Value': metric['value'],
                    'Unit': metric.get('unit', 'None'),
                    'Timestamp': metric.get('timestamp', datetime.utcnow())
                }
                
                if 'dimensions' in metric:
                    data['Dimensions'] = [
                        {'Name': k, 'Value': v} for k, v in metric['dimensions'].items()
                    ]
                
                metric_data.append(data)
            
            # CloudWatch allows max 20 metrics per request
            for i in range(0, len(metric_data), 20):
                batch = metric_data[i:i+20]
                self.cloudwatch_client.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=batch
                )
            
            return True
        except ClientError as e:
            logger.error(f"Failed to put metrics batch: {e}")
            return False
    
    def create_alarm(
        self,
        alert: PerformanceAlert,
        sns_topic_arn: Optional[str] = None
    ) -> bool:
        """
        Create a CloudWatch alarm for performance monitoring.
        
        Args:
            alert: Performance alert configuration
            sns_topic_arn: SNS topic ARN for notifications
            
        Returns:
            True if alarm created successfully, False otherwise
        """
        try:
            alarm_actions = [sns_topic_arn] if sns_topic_arn else []
            
            self.cloudwatch_client.put_metric_alarm(
                AlarmName=alert.alarm_name,
                AlarmDescription=alert.alarm_description,
                ActionsEnabled=True,
                AlarmActions=alarm_actions,
                MetricName=alert.metric_type.value,
                Namespace=self.namespace,
                Statistic='Average',
                Period=300,  # 5 minutes
                EvaluationPeriods=alert.evaluation_periods,
                Threshold=alert.threshold,
                ComparisonOperator=alert.comparison
            )
            logger.info(f"Created alarm: {alert.alarm_name}")
            return True
        except ClientError as e:
            logger.error(f"Failed to create alarm: {e}")
            return False
    
    def get_metric_statistics(
        self,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        period_seconds: int = 300,
        statistics: List[str] = None,
        dimensions: Optional[Dict[str, str]] = None
    ) -> List[Dict]:
        """
        Get metric statistics from CloudWatch.
        
        Args:
            metric_name: Metric name
            start_time: Start time for query
            end_time: End time for query
            period_seconds: Period in seconds
            statistics: List of statistics to retrieve
            dimensions: Metric dimensions
            
        Returns:
            List of datapoints
        """
        try:
            if statistics is None:
                statistics = ['Average', 'Sum', 'Maximum', 'Minimum']
            
            params = {
                'Namespace': self.namespace,
                'MetricName': metric_name,
                'StartTime': start_time,
                'EndTime': end_time,
                'Period': period_seconds,
                'Statistics': statistics
            }
            
            if dimensions:
                params['Dimensions'] = [
                    {'Name': k, 'Value': v} for k, v in dimensions.items()
                ]
            
            response = self.cloudwatch_client.get_metric_statistics(**params)
            return response.get('Datapoints', [])
        except ClientError as e:
            logger.error(f"Failed to get metric statistics: {e}")
            return []
    
    def monitor_response_time(
        self,
        function_name: str,
        threshold_ms: float = 3000.0,
        period_minutes: int = 5
    ) -> Dict:
        """
        Monitor response time for a Lambda function.
        
        Args:
            function_name: Lambda function name
            threshold_ms: Response time threshold in milliseconds
            period_minutes: Monitoring period in minutes
            
        Returns:
            Dictionary with monitoring results
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=period_minutes)
        
        datapoints = self.get_metric_statistics(
            metric_name='Duration',
            start_time=start_time,
            end_time=end_time,
            dimensions={'FunctionName': function_name}
        )
        
        if not datapoints:
            return {
                "status": "no_data",
                "message": "No data available for the specified period"
            }
        
        # Calculate statistics
        avg_response_time = sum(d['Average'] for d in datapoints) / len(datapoints)
        max_response_time = max(d['Maximum'] for d in datapoints)
        
        exceeds_threshold = avg_response_time > threshold_ms
        
        return {
            "status": "warning" if exceeds_threshold else "ok",
            "average_response_time_ms": avg_response_time,
            "max_response_time_ms": max_response_time,
            "threshold_ms": threshold_ms,
            "exceeds_threshold": exceeds_threshold,
            "datapoints_count": len(datapoints),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def monitor_error_rate(
        self,
        function_name: str,
        threshold_percentage: float = 5.0,
        period_minutes: int = 5
    ) -> Dict:
        """
        Monitor error rate for a Lambda function.
        
        Args:
            function_name: Lambda function name
            threshold_percentage: Error rate threshold percentage
            period_minutes: Monitoring period in minutes
            
        Returns:
            Dictionary with monitoring results
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=period_minutes)
        
        # Get invocations
        invocations = self.get_metric_statistics(
            metric_name='Invocations',
            start_time=start_time,
            end_time=end_time,
            statistics=['Sum'],
            dimensions={'FunctionName': function_name}
        )
        
        # Get errors
        errors = self.get_metric_statistics(
            metric_name='Errors',
            start_time=start_time,
            end_time=end_time,
            statistics=['Sum'],
            dimensions={'FunctionName': function_name}
        )
        
        if not invocations or not errors:
            return {
                "status": "no_data",
                "message": "No data available for the specified period"
            }
        
        total_invocations = sum(d['Sum'] for d in invocations)
        total_errors = sum(d['Sum'] for d in errors)
        
        error_rate = (total_errors / total_invocations * 100) if total_invocations > 0 else 0
        exceeds_threshold = error_rate > threshold_percentage
        
        return {
            "status": "warning" if exceeds_threshold else "ok",
            "error_rate_percentage": error_rate,
            "total_invocations": int(total_invocations),
            "total_errors": int(total_errors),
            "threshold_percentage": threshold_percentage,
            "exceeds_threshold": exceeds_threshold,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def monitor_concurrent_executions(
        self,
        function_name: str,
        threshold: int = 100,
        period_minutes: int = 5
    ) -> Dict:
        """
        Monitor concurrent executions for a Lambda function.
        
        Args:
            function_name: Lambda function name
            threshold: Concurrent execution threshold
            period_minutes: Monitoring period in minutes
            
        Returns:
            Dictionary with monitoring results
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=period_minutes)
        
        datapoints = self.get_metric_statistics(
            metric_name='ConcurrentExecutions',
            start_time=start_time,
            end_time=end_time,
            dimensions={'FunctionName': function_name}
        )
        
        if not datapoints:
            return {
                "status": "no_data",
                "message": "No data available for the specified period"
            }
        
        avg_concurrent = sum(d['Average'] for d in datapoints) / len(datapoints)
        max_concurrent = max(d['Maximum'] for d in datapoints)
        
        exceeds_threshold = max_concurrent > threshold
        
        return {
            "status": "warning" if exceeds_threshold else "ok",
            "average_concurrent_executions": avg_concurrent,
            "max_concurrent_executions": max_concurrent,
            "threshold": threshold,
            "exceeds_threshold": exceeds_threshold,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_comprehensive_health_report(
        self,
        function_name: str,
        period_minutes: int = 5
    ) -> Dict:
        """
        Get comprehensive health report for a Lambda function.
        
        Args:
            function_name: Lambda function name
            period_minutes: Monitoring period in minutes
            
        Returns:
            Dictionary with comprehensive health metrics
        """
        response_time_report = self.monitor_response_time(function_name, period_minutes=period_minutes)
        error_rate_report = self.monitor_error_rate(function_name, period_minutes=period_minutes)
        concurrent_report = self.monitor_concurrent_executions(function_name, period_minutes=period_minutes)
        
        # Determine overall health status
        statuses = [
            response_time_report.get('status', 'unknown'),
            error_rate_report.get('status', 'unknown'),
            concurrent_report.get('status', 'unknown')
        ]
        
        if 'warning' in statuses:
            overall_status = 'warning'
        elif 'no_data' in statuses:
            overall_status = 'no_data'
        else:
            overall_status = 'ok'
        
        return {
            "function_name": function_name,
            "overall_status": overall_status,
            "response_time": response_time_report,
            "error_rate": error_rate_report,
            "concurrent_executions": concurrent_report,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def create_dashboard(
        self,
        dashboard_name: str,
        function_names: List[str]
    ) -> bool:
        """
        Create a CloudWatch dashboard for monitoring.
        
        Args:
            dashboard_name: Dashboard name
            function_names: List of Lambda function names to monitor
            
        Returns:
            True if dashboard created successfully, False otherwise
        """
        try:
            widgets = []
            
            for i, function_name in enumerate(function_names):
                # Response time widget
                widgets.append({
                    "type": "metric",
                    "x": 0,
                    "y": i * 6,
                    "width": 12,
                    "height": 6,
                    "properties": {
                        "metrics": [
                            ["AWS/Lambda", "Duration", {"stat": "Average", "label": "Avg Duration"}],
                            ["...", {"stat": "Maximum", "label": "Max Duration"}]
                        ],
                        "view": "timeSeries",
                        "stacked": False,
                        "region": self.region,
                        "title": f"{function_name} - Response Time",
                        "period": 300
                    }
                })
                
                # Error rate widget
                widgets.append({
                    "type": "metric",
                    "x": 12,
                    "y": i * 6,
                    "width": 12,
                    "height": 6,
                    "properties": {
                        "metrics": [
                            ["AWS/Lambda", "Errors", {"stat": "Sum", "label": "Errors"}],
                            [".", "Invocations", {"stat": "Sum", "label": "Invocations"}]
                        ],
                        "view": "timeSeries",
                        "stacked": False,
                        "region": self.region,
                        "title": f"{function_name} - Errors",
                        "period": 300
                    }
                })
            
            dashboard_body = {
                "widgets": widgets
            }
            
            import json
            self.cloudwatch_client.put_dashboard(
                DashboardName=dashboard_name,
                DashboardBody=json.dumps(dashboard_body)
            )
            logger.info(f"Created dashboard: {dashboard_name}")
            return True
        except ClientError as e:
            logger.error(f"Failed to create dashboard: {e}")
            return False
