"""
Resource optimization for cost-effective scaling in KrishiMitra platform.

This module implements algorithms for optimizing resource allocation
to balance performance and cost.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class OptimizationStrategy(Enum):
    """Resource optimization strategies."""
    COST_OPTIMIZED = "cost_optimized"
    PERFORMANCE_OPTIMIZED = "performance_optimized"
    BALANCED = "balanced"


@dataclass
class ResourceRecommendation:
    """Resource optimization recommendation."""
    resource_type: str
    current_configuration: Dict
    recommended_configuration: Dict
    estimated_cost_savings: float
    estimated_performance_impact: str
    confidence: float


class ResourceOptimizer:
    """
    Optimizes resource allocation for cost-effectiveness in KrishiMitra platform.
    
    Analyzes usage patterns and provides recommendations for optimal
    resource configuration balancing cost and performance.
    """
    
    def __init__(
        self,
        region: str = "ap-south-1",
        strategy: OptimizationStrategy = OptimizationStrategy.BALANCED
    ):
        """
        Initialize resource optimizer.
        
        Args:
            region: AWS region
            strategy: Optimization strategy
        """
        self.region = region
        self.strategy = strategy
        
        # AWS clients
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.dynamodb_client = boto3.client('dynamodb', region_name=region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
        self.ce_client = boto3.client('ce', region_name=region)  # Cost Explorer
    
    def analyze_lambda_utilization(
        self,
        function_name: str,
        period_days: int = 7
    ) -> Dict:
        """
        Analyze Lambda function utilization patterns.
        
        Args:
            function_name: Lambda function name
            period_days: Analysis period in days
            
        Returns:
            Dictionary with utilization analysis
        """
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=period_days)
            
            # Get function configuration
            config = self.lambda_client.get_function_configuration(
                FunctionName=function_name
            )
            
            current_memory = config['MemorySize']
            current_timeout = config['Timeout']
            
            # Get duration metrics
            duration_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Duration',
                Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour
                Statistics=['Average', 'Maximum', 'Minimum']
            )
            
            if not duration_response['Datapoints']:
                return {
                    "status": "no_data",
                    "message": "Insufficient data for analysis"
                }
            
            # Calculate utilization statistics
            avg_duration = sum(d['Average'] for d in duration_response['Datapoints']) / len(duration_response['Datapoints'])
            max_duration = max(d['Maximum'] for d in duration_response['Datapoints'])
            min_duration = min(d['Minimum'] for d in duration_response['Datapoints'])
            
            # Calculate memory utilization (approximation)
            memory_utilization_pct = (avg_duration / (current_timeout * 1000)) * 100
            
            return {
                "function_name": function_name,
                "current_memory_mb": current_memory,
                "current_timeout_seconds": current_timeout,
                "average_duration_ms": avg_duration,
                "max_duration_ms": max_duration,
                "min_duration_ms": min_duration,
                "estimated_memory_utilization_pct": memory_utilization_pct,
                "analysis_period_days": period_days,
                "datapoints_count": len(duration_response['Datapoints'])
            }
        except ClientError as e:
            logger.error(f"Failed to analyze Lambda utilization: {e}")
            return {"status": "error", "message": str(e)}
    
    def recommend_lambda_configuration(
        self,
        function_name: str,
        period_days: int = 7
    ) -> Optional[ResourceRecommendation]:
        """
        Recommend optimal Lambda configuration.
        
        Args:
            function_name: Lambda function name
            period_days: Analysis period in days
            
        Returns:
            Resource recommendation or None
        """
        analysis = self.analyze_lambda_utilization(function_name, period_days)
        
        if analysis.get('status') in ['no_data', 'error']:
            return None
        
        current_memory = analysis['current_memory_mb']
        avg_duration = analysis['average_duration_ms']
        max_duration = analysis['max_duration_ms']
        current_timeout = analysis['current_timeout_seconds']
        
        # Determine optimal memory based on strategy
        if self.strategy == OptimizationStrategy.COST_OPTIMIZED:
            # Reduce memory if utilization is low
            if avg_duration < (current_timeout * 1000 * 0.5):
                recommended_memory = max(128, int(current_memory * 0.75))
            else:
                recommended_memory = current_memory
        elif self.strategy == OptimizationStrategy.PERFORMANCE_OPTIMIZED:
            # Increase memory if duration is high
            if avg_duration > (current_timeout * 1000 * 0.7):
                recommended_memory = min(10240, int(current_memory * 1.5))
            else:
                recommended_memory = current_memory
        else:  # BALANCED
            # Optimize for 60-70% utilization
            target_utilization = 0.65
            current_utilization = avg_duration / (current_timeout * 1000)
            if current_utilization < 0.5:
                recommended_memory = max(128, int(current_memory * 0.85))
            elif current_utilization > 0.8:
                recommended_memory = min(10240, int(current_memory * 1.2))
            else:
                recommended_memory = current_memory
        
        # Determine optimal timeout
        recommended_timeout = max(3, int((max_duration / 1000) * 1.5))
        
        # Estimate cost savings (simplified)
        # Lambda pricing: $0.0000166667 per GB-second
        current_cost_per_invocation = (current_memory / 1024) * (avg_duration / 1000) * 0.0000166667
        recommended_cost_per_invocation = (recommended_memory / 1024) * (avg_duration / 1000) * 0.0000166667
        cost_savings_pct = ((current_cost_per_invocation - recommended_cost_per_invocation) / current_cost_per_invocation * 100) if current_cost_per_invocation > 0 else 0
        
        # Determine performance impact
        if recommended_memory > current_memory:
            performance_impact = "improved"
        elif recommended_memory < current_memory:
            performance_impact = "minimal_degradation"
        else:
            performance_impact = "no_change"
        
        return ResourceRecommendation(
            resource_type="lambda_function",
            current_configuration={
                "memory_mb": current_memory,
                "timeout_seconds": current_timeout
            },
            recommended_configuration={
                "memory_mb": recommended_memory,
                "timeout_seconds": recommended_timeout
            },
            estimated_cost_savings=cost_savings_pct,
            estimated_performance_impact=performance_impact,
            confidence=0.8 if len(analysis.get('datapoints_count', 0)) > 100 else 0.6
        )
    
    def analyze_dynamodb_utilization(
        self,
        table_name: str,
        period_days: int = 7
    ) -> Dict:
        """
        Analyze DynamoDB table utilization patterns.
        
        Args:
            table_name: DynamoDB table name
            period_days: Analysis period in days
            
        Returns:
            Dictionary with utilization analysis
        """
        try:
            # Get table description
            table_info = self.dynamodb_client.describe_table(
                TableName=table_name
            )
            
            billing_mode = table_info['Table']['BillingModeSummary']['BillingMode']
            
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=period_days)
            
            # Get consumed read capacity
            read_capacity_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/DynamoDB',
                MetricName='ConsumedReadCapacityUnits',
                Dimensions=[{'Name': 'TableName', 'Value': table_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Sum', 'Average']
            )
            
            # Get consumed write capacity
            write_capacity_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/DynamoDB',
                MetricName='ConsumedWriteCapacityUnits',
                Dimensions=[{'Name': 'TableName', 'Value': table_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Sum', 'Average']
            )
            
            if not read_capacity_response['Datapoints'] or not write_capacity_response['Datapoints']:
                return {
                    "status": "no_data",
                    "message": "Insufficient data for analysis"
                }
            
            avg_read_capacity = sum(d['Average'] for d in read_capacity_response['Datapoints']) / len(read_capacity_response['Datapoints'])
            avg_write_capacity = sum(d['Average'] for d in write_capacity_response['Datapoints']) / len(write_capacity_response['Datapoints'])
            
            return {
                "table_name": table_name,
                "billing_mode": billing_mode,
                "average_read_capacity_units": avg_read_capacity,
                "average_write_capacity_units": avg_write_capacity,
                "analysis_period_days": period_days
            }
        except ClientError as e:
            logger.error(f"Failed to analyze DynamoDB utilization: {e}")
            return {"status": "error", "message": str(e)}
    
    def recommend_dynamodb_billing_mode(
        self,
        table_name: str,
        period_days: int = 7
    ) -> Optional[ResourceRecommendation]:
        """
        Recommend optimal DynamoDB billing mode.
        
        Args:
            table_name: DynamoDB table name
            period_days: Analysis period in days
            
        Returns:
            Resource recommendation or None
        """
        analysis = self.analyze_dynamodb_utilization(table_name, period_days)
        
        if analysis.get('status') in ['no_data', 'error']:
            return None
        
        current_billing_mode = analysis['billing_mode']
        avg_read_capacity = analysis['average_read_capacity_units']
        avg_write_capacity = analysis['average_write_capacity_units']
        
        # Determine optimal billing mode
        # On-demand is better for unpredictable workloads
        # Provisioned is better for consistent workloads
        
        # Calculate cost for both modes (simplified)
        # On-demand: $1.25 per million read requests, $1.25 per million write requests
        # Provisioned: $0.00013 per RCU-hour, $0.00065 per WCU-hour
        
        hours_per_month = 730
        on_demand_cost = (avg_read_capacity * hours_per_month * 1.25 / 1000000) + \
                        (avg_write_capacity * hours_per_month * 1.25 / 1000000)
        
        provisioned_cost = (avg_read_capacity * hours_per_month * 0.00013) + \
                          (avg_write_capacity * hours_per_month * 0.00065)
        
        if self.strategy == OptimizationStrategy.COST_OPTIMIZED:
            recommended_mode = "PROVISIONED" if provisioned_cost < on_demand_cost else "PAY_PER_REQUEST"
        elif self.strategy == OptimizationStrategy.PERFORMANCE_OPTIMIZED:
            recommended_mode = "PROVISIONED"  # More predictable performance
        else:  # BALANCED
            # Use on-demand if cost difference is small or workload is variable
            cost_difference_pct = abs(provisioned_cost - on_demand_cost) / max(provisioned_cost, on_demand_cost) * 100
            recommended_mode = "PAY_PER_REQUEST" if cost_difference_pct < 20 else \
                             ("PROVISIONED" if provisioned_cost < on_demand_cost else "PAY_PER_REQUEST")
        
        cost_savings = max(0, (on_demand_cost - provisioned_cost) if recommended_mode == "PROVISIONED" else (provisioned_cost - on_demand_cost))
        cost_savings_pct = (cost_savings / max(on_demand_cost, provisioned_cost) * 100) if max(on_demand_cost, provisioned_cost) > 0 else 0
        
        return ResourceRecommendation(
            resource_type="dynamodb_table",
            current_configuration={
                "billing_mode": current_billing_mode
            },
            recommended_configuration={
                "billing_mode": recommended_mode
            },
            estimated_cost_savings=cost_savings_pct,
            estimated_performance_impact="improved" if recommended_mode == "PROVISIONED" else "no_change",
            confidence=0.75
        )
    
    def get_cost_optimization_report(
        self,
        function_names: List[str],
        table_names: List[str],
        period_days: int = 7
    ) -> Dict:
        """
        Generate comprehensive cost optimization report.
        
        Args:
            function_names: List of Lambda function names
            table_names: List of DynamoDB table names
            period_days: Analysis period in days
            
        Returns:
            Dictionary with optimization recommendations
        """
        recommendations = []
        total_estimated_savings = 0.0
        
        # Analyze Lambda functions
        for function_name in function_names:
            recommendation = self.recommend_lambda_configuration(function_name, period_days)
            if recommendation:
                recommendations.append({
                    "resource_type": "lambda",
                    "resource_name": function_name,
                    "recommendation": recommendation
                })
                if recommendation.estimated_cost_savings > 0:
                    total_estimated_savings += recommendation.estimated_cost_savings
        
        # Analyze DynamoDB tables
        for table_name in table_names:
            recommendation = self.recommend_dynamodb_billing_mode(table_name, period_days)
            if recommendation:
                recommendations.append({
                    "resource_type": "dynamodb",
                    "resource_name": table_name,
                    "recommendation": recommendation
                })
                if recommendation.estimated_cost_savings > 0:
                    total_estimated_savings += recommendation.estimated_cost_savings
        
        return {
            "optimization_strategy": self.strategy.value,
            "analysis_period_days": period_days,
            "total_resources_analyzed": len(function_names) + len(table_names),
            "recommendations_count": len(recommendations),
            "estimated_total_savings_pct": total_estimated_savings / len(recommendations) if recommendations else 0,
            "recommendations": recommendations,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def apply_lambda_recommendation(
        self,
        function_name: str,
        recommendation: ResourceRecommendation
    ) -> bool:
        """
        Apply Lambda configuration recommendation.
        
        Args:
            function_name: Lambda function name
            recommendation: Resource recommendation to apply
            
        Returns:
            True if applied successfully, False otherwise
        """
        try:
            recommended_config = recommendation.recommended_configuration
            
            self.lambda_client.update_function_configuration(
                FunctionName=function_name,
                MemorySize=recommended_config['memory_mb'],
                Timeout=recommended_config['timeout_seconds']
            )
            logger.info(f"Applied optimization to {function_name}: "
                       f"Memory={recommended_config['memory_mb']}MB, "
                       f"Timeout={recommended_config['timeout_seconds']}s")
            return True
        except ClientError as e:
            logger.error(f"Failed to apply Lambda recommendation: {e}")
            return False
    
    def apply_dynamodb_recommendation(
        self,
        table_name: str,
        recommendation: ResourceRecommendation
    ) -> bool:
        """
        Apply DynamoDB billing mode recommendation.
        
        Args:
            table_name: DynamoDB table name
            recommendation: Resource recommendation to apply
            
        Returns:
            True if applied successfully, False otherwise
        """
        try:
            recommended_config = recommendation.recommended_configuration
            billing_mode = recommended_config['billing_mode']
            
            update_params = {
                'TableName': table_name,
                'BillingMode': billing_mode
            }
            
            self.dynamodb_client.update_table(**update_params)
            logger.info(f"Applied optimization to {table_name}: BillingMode={billing_mode}")
            return True
        except ClientError as e:
            logger.error(f"Failed to apply DynamoDB recommendation: {e}")
            return False
