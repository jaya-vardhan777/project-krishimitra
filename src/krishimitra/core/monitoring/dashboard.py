"""
Dashboard management for KrishiMitra platform.

This module creates and manages CloudWatch dashboards for
system health monitoring and analytics visualization.
"""

import json
import logging
from typing import Dict, List, Optional, Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class DashboardManager:
    """
    Manages CloudWatch dashboards for KrishiMitra platform.
    
    Creates comprehensive dashboards for system health, performance,
    and farmer engagement analytics.
    """
    
    def __init__(
        self,
        region: str = "ap-south-1"
    ):
        """
        Initialize dashboard manager.
        
        Args:
            region: AWS region
        """
        self.region = region
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
    
    def create_system_health_dashboard(
        self,
        dashboard_name: str,
        components: Dict[str, List[str]]
    ) -> bool:
        """
        Create comprehensive system health dashboard.
        
        Args:
            dashboard_name: Dashboard name
            components: Dictionary of components to monitor
                Format: {
                    'lambda_functions': ['func1', 'func2'],
                    'dynamodb_tables': ['table1', 'table2'],
                    's3_buckets': ['bucket1'],
                    'api_endpoints': ['endpoint1']
                }
            
        Returns:
            True if dashboard created successfully
        """
        try:
            widgets = []
            y_position = 0
            
            # Add overview widget
            widgets.append(self._create_text_widget(
                "System Health Overview",
                "Comprehensive health monitoring for KrishiMitra platform",
                0, y_position, 24, 2
            ))
            y_position += 2
            
            # Lambda function metrics
            if components.get('lambda_functions'):
                widgets.extend(self._create_lambda_widgets(
                    components['lambda_functions'],
                    0, y_position
                ))
                y_position += 12
            
            # DynamoDB metrics
            if components.get('dynamodb_tables'):
                widgets.extend(self._create_dynamodb_widgets(
                    components['dynamodb_tables'],
                    0, y_position
                ))
                y_position += 6
            
            # API Gateway metrics
            if components.get('api_endpoints'):
                widgets.extend(self._create_api_gateway_widgets(
                    0, y_position
                ))
                y_position += 6
            
            # System-wide metrics
            widgets.extend(self._create_system_widgets(
                0, y_position
            ))
            
            dashboard_body = {
                "widgets": widgets
            }
            
            self.cloudwatch_client.put_dashboard(
                DashboardName=dashboard_name,
                DashboardBody=json.dumps(dashboard_body)
            )
            
            logger.info(f"Created system health dashboard: {dashboard_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create system health dashboard: {e}")
            return False
    
    def create_performance_dashboard(
        self,
        dashboard_name: str,
        function_names: List[str]
    ) -> bool:
        """
        Create performance monitoring dashboard.
        
        Args:
            dashboard_name: Dashboard name
            function_names: List of Lambda function names
            
        Returns:
            True if dashboard created successfully
        """
        try:
            widgets = []
            y_position = 0
            
            # Title
            widgets.append(self._create_text_widget(
                "Performance Monitoring",
                "Response times, throughput, and error rates",
                0, y_position, 24, 2
            ))
            y_position += 2
            
            # Response time metrics
            widgets.append(self._create_metric_widget(
                "Response Times",
                [
                    ["AWS/Lambda", "Duration", {"stat": "Average"}]
                ],
                0, y_position, 12, 6
            ))
            
            # Throughput metrics
            widgets.append(self._create_metric_widget(
                "Request Throughput",
                [
                    ["AWS/Lambda", "Invocations", {"stat": "Sum"}]
                ],
                12, y_position, 12, 6
            ))
            y_position += 6
            
            # Error rate metrics
            widgets.append(self._create_metric_widget(
                "Error Rates",
                [
                    ["AWS/Lambda", "Errors", {"stat": "Sum"}],
                    [".", "Throttles", {"stat": "Sum"}]
                ],
                0, y_position, 12, 6
            ))
            
            # Concurrent executions
            widgets.append(self._create_metric_widget(
                "Concurrent Executions",
                [
                    ["AWS/Lambda", "ConcurrentExecutions", {"stat": "Maximum"}]
                ],
                12, y_position, 12, 6
            ))
            
            dashboard_body = {
                "widgets": widgets
            }
            
            self.cloudwatch_client.put_dashboard(
                DashboardName=dashboard_name,
                DashboardBody=json.dumps(dashboard_body)
            )
            
            logger.info(f"Created performance dashboard: {dashboard_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create performance dashboard: {e}")
            return False
    
    def create_farmer_engagement_dashboard(
        self,
        dashboard_name: str
    ) -> bool:
        """
        Create farmer engagement analytics dashboard.
        
        Args:
            dashboard_name: Dashboard name
            
        Returns:
            True if dashboard created successfully
        """
        try:
            widgets = []
            y_position = 0
            
            # Title
            widgets.append(self._create_text_widget(
                "Farmer Engagement Analytics",
                "User activity, recommendations, and satisfaction metrics",
                0, y_position, 24, 2
            ))
            y_position += 2
            
            # Active users
            widgets.append(self._create_metric_widget(
                "Active Farmers",
                [
                    ["KrishiMitra/Engagement", "ActiveFarmers", {"stat": "Sum"}]
                ],
                0, y_position, 8, 6
            ))
            
            # Recommendations delivered
            widgets.append(self._create_metric_widget(
                "Recommendations Delivered",
                [
                    ["KrishiMitra/Recommendations", "Delivered", {"stat": "Sum"}]
                ],
                8, y_position, 8, 6
            ))
            
            # Satisfaction score
            widgets.append(self._create_metric_widget(
                "Satisfaction Score",
                [
                    ["KrishiMitra/Feedback", "SatisfactionScore", {"stat": "Average"}]
                ],
                16, y_position, 8, 6
            ))
            y_position += 6
            
            # Recommendation effectiveness
            widgets.append(self._create_metric_widget(
                "Recommendation Effectiveness",
                [
                    ["KrishiMitra/Recommendations", "ImplementationRate", {"stat": "Average"}],
                    [".", "SuccessRate", {"stat": "Average"}]
                ],
                0, y_position, 12, 6
            ))
            
            # Language distribution
            widgets.append(self._create_metric_widget(
                "Language Usage",
                [
                    ["KrishiMitra/Engagement", "Hindi", {"stat": "Sum"}],
                    [".", "Tamil", {"stat": "Sum"}],
                    [".", "Telugu", {"stat": "Sum"}],
                    [".", "Bengali", {"stat": "Sum"}]
                ],
                12, y_position, 12, 6
            ))
            
            dashboard_body = {
                "widgets": widgets
            }
            
            self.cloudwatch_client.put_dashboard(
                DashboardName=dashboard_name,
                DashboardBody=json.dumps(dashboard_body)
            )
            
            logger.info(f"Created farmer engagement dashboard: {dashboard_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create farmer engagement dashboard: {e}")
            return False
    
    def _create_lambda_widgets(
        self,
        function_names: List[str],
        x: int,
        y: int
    ) -> List[Dict]:
        """Create Lambda function monitoring widgets."""
        widgets = []
        
        # Duration widget
        widgets.append(self._create_metric_widget(
            "Lambda Duration",
            [
                ["AWS/Lambda", "Duration", {"stat": "Average", "label": "Avg"}],
                ["...", {"stat": "Maximum", "label": "Max"}]
            ],
            x, y, 12, 6
        ))
        
        # Invocations widget
        widgets.append(self._create_metric_widget(
            "Lambda Invocations",
            [
                ["AWS/Lambda", "Invocations", {"stat": "Sum"}]
            ],
            x + 12, y, 12, 6
        ))
        
        # Errors widget
        widgets.append(self._create_metric_widget(
            "Lambda Errors",
            [
                ["AWS/Lambda", "Errors", {"stat": "Sum", "label": "Errors"}],
                [".", "Throttles", {"stat": "Sum", "label": "Throttles"}]
            ],
            x, y + 6, 12, 6
        ))
        
        # Concurrent executions widget
        widgets.append(self._create_metric_widget(
            "Concurrent Executions",
            [
                ["AWS/Lambda", "ConcurrentExecutions", {"stat": "Maximum"}]
            ],
            x + 12, y + 6, 12, 6
        ))
        
        return widgets
    
    def _create_dynamodb_widgets(
        self,
        table_names: List[str],
        x: int,
        y: int
    ) -> List[Dict]:
        """Create DynamoDB monitoring widgets."""
        widgets = []
        
        # Read/Write capacity
        widgets.append(self._create_metric_widget(
            "DynamoDB Capacity",
            [
                ["AWS/DynamoDB", "ConsumedReadCapacityUnits", {"stat": "Sum"}],
                [".", "ConsumedWriteCapacityUnits", {"stat": "Sum"}]
            ],
            x, y, 12, 6
        ))
        
        # Latency
        widgets.append(self._create_metric_widget(
            "DynamoDB Latency",
            [
                ["AWS/DynamoDB", "SuccessfulRequestLatency", {"stat": "Average"}]
            ],
            x + 12, y, 12, 6
        ))
        
        return widgets
    
    def _create_api_gateway_widgets(
        self,
        x: int,
        y: int
    ) -> List[Dict]:
        """Create API Gateway monitoring widgets."""
        widgets = []
        
        # Request count
        widgets.append(self._create_metric_widget(
            "API Requests",
            [
                ["AWS/ApiGateway", "Count", {"stat": "Sum"}]
            ],
            x, y, 12, 6
        ))
        
        # Latency
        widgets.append(self._create_metric_widget(
            "API Latency",
            [
                ["AWS/ApiGateway", "Latency", {"stat": "Average"}]
            ],
            x + 12, y, 12, 6
        ))
        
        return widgets
    
    def _create_system_widgets(
        self,
        x: int,
        y: int
    ) -> List[Dict]:
        """Create system-wide monitoring widgets."""
        widgets = []
        
        # Overall health status
        widgets.append(self._create_metric_widget(
            "System Health Status",
            [
                ["KrishiMitra/Health", "OverallStatus", {"stat": "Average"}]
            ],
            x, y, 12, 6
        ))
        
        # Active alerts
        widgets.append(self._create_metric_widget(
            "Active Alerts",
            [
                ["KrishiMitra/Alerts", "ActiveAlerts", {"stat": "Sum"}]
            ],
            x + 12, y, 12, 6
        ))
        
        return widgets
    
    def _create_metric_widget(
        self,
        title: str,
        metrics: List[List],
        x: int,
        y: int,
        width: int,
        height: int
    ) -> Dict:
        """Create a metric widget."""
        return {
            "type": "metric",
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "properties": {
                "metrics": metrics,
                "view": "timeSeries",
                "stacked": False,
                "region": self.region,
                "title": title,
                "period": 300,
                "yAxis": {
                    "left": {
                        "showUnits": False
                    }
                }
            }
        }
    
    def _create_text_widget(
        self,
        title: str,
        content: str,
        x: int,
        y: int,
        width: int,
        height: int
    ) -> Dict:
        """Create a text widget."""
        return {
            "type": "text",
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "properties": {
                "markdown": f"# {title}\n\n{content}"
            }
        }
