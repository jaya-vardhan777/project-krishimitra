"""
Performance Monitoring and Resource Optimization

This module implements performance profiling, monitoring, and
resource optimization for data processing pipelines.
"""

import cProfile
import pstats
import io
import logging
import time
import psutil
import tracemalloc
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
import boto3

from src.krishimitra.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for a function or operation"""
    function_name: str
    execution_time_seconds: float
    memory_usage_mb: float
    cpu_percent: float
    timestamp: datetime = field(default_factory=datetime.now)
    additional_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceThresholds:
    """Thresholds for resource alerts"""
    max_memory_mb: float = 1024.0
    max_cpu_percent: float = 80.0
    max_execution_time_seconds: float = 300.0
    alert_callback: Optional[Callable] = None


class PerformanceMonitor:
    """
    Monitors performance and resource usage of data processing operations
    
    Provides profiling, metrics collection, and performance analysis
    for optimization and troubleshooting.
    """
    
    def __init__(self):
        self.metrics_history: List[PerformanceMetrics] = []
        self.cloudwatch = boto3.client('cloudwatch', region_name=settings.aws_region)
        self._profiler = None
        self._memory_tracker_active = False
    
    def profile_function(self, func: Callable) -> Callable:
        """
        Decorator to profile function execution
        
        Usage:
            @monitor.profile_function
            def my_function():
                pass
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Start profiling
            profiler = cProfile.Profile()
            profiler.enable()
            
            # Start memory tracking
            tracemalloc.start()
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            start_cpu = psutil.cpu_percent(interval=0.1)
            start_time = time.time()
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Stop profiling
                profiler.disable()
                
                # Calculate metrics
                end_time = time.time()
                end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
                end_cpu = psutil.cpu_percent(interval=0.1)
                
                execution_time = end_time - start_time
                memory_used = end_memory - start_memory
                cpu_used = (start_cpu + end_cpu) / 2
                
                # Get memory peak
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                
                # Create metrics
                metrics = PerformanceMetrics(
                    function_name=func.__name__,
                    execution_time_seconds=execution_time,
                    memory_usage_mb=memory_used,
                    cpu_percent=cpu_used,
                    additional_metrics={
                        'peak_memory_mb': peak / 1024 / 1024,
                        'current_memory_mb': current / 1024 / 1024
                    }
                )
                
                # Store metrics
                self.metrics_history.append(metrics)
                
                # Log performance stats
                s = io.StringIO()
                ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
                ps.print_stats(10)  # Top 10 functions
                
                logger.info(
                    f"Performance metrics for {func.__name__}: "
                    f"Time={execution_time:.2f}s, Memory={memory_used:.2f}MB, CPU={cpu_used:.1f}%"
                )
                logger.debug(f"Profiling details:\n{s.getvalue()}")
                
                # Send to CloudWatch
                self._send_metrics_to_cloudwatch(metrics)
                
                return result
                
            except Exception as e:
                profiler.disable()
                tracemalloc.stop()
                logger.error(f"Error profiling function {func.__name__}: {e}")
                raise
        
        return wrapper
    
    def monitor_resources(self, thresholds: ResourceThresholds) -> Callable:
        """
        Decorator to monitor resource usage and alert on threshold violations
        
        Usage:
            @monitor.monitor_resources(ResourceThresholds(max_memory_mb=512))
            def my_function():
                pass
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                start_memory = psutil.Process().memory_info().rss / 1024 / 1024
                
                try:
                    result = func(*args, **kwargs)
                    
                    # Check thresholds
                    execution_time = time.time() - start_time
                    memory_used = psutil.Process().memory_info().rss / 1024 / 1024 - start_memory
                    cpu_percent = psutil.cpu_percent(interval=0.1)
                    
                    violations = []
                    
                    if execution_time > thresholds.max_execution_time_seconds:
                        violations.append(
                            f"Execution time {execution_time:.2f}s exceeds threshold "
                            f"{thresholds.max_execution_time_seconds}s"
                        )
                    
                    if memory_used > thresholds.max_memory_mb:
                        violations.append(
                            f"Memory usage {memory_used:.2f}MB exceeds threshold "
                            f"{thresholds.max_memory_mb}MB"
                        )
                    
                    if cpu_percent > thresholds.max_cpu_percent:
                        violations.append(
                            f"CPU usage {cpu_percent:.1f}% exceeds threshold "
                            f"{thresholds.max_cpu_percent}%"
                        )
                    
                    if violations:
                        alert_message = f"Resource threshold violations in {func.__name__}:\n" + \
                                      "\n".join(violations)
                        logger.warning(alert_message)
                        
                        if thresholds.alert_callback:
                            thresholds.alert_callback(alert_message)
                    
                    return result
                    
                except Exception as e:
                    logger.error(f"Error monitoring resources for {func.__name__}: {e}")
                    raise
            
            return wrapper
        return decorator
    
    def _send_metrics_to_cloudwatch(self, metrics: PerformanceMetrics):
        """Send performance metrics to CloudWatch"""
        try:
            metric_data = [
                {
                    'MetricName': 'ExecutionTime',
                    'Value': metrics.execution_time_seconds,
                    'Unit': 'Seconds',
                    'Timestamp': metrics.timestamp,
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': metrics.function_name}
                    ]
                },
                {
                    'MetricName': 'MemoryUsage',
                    'Value': metrics.memory_usage_mb,
                    'Unit': 'Megabytes',
                    'Timestamp': metrics.timestamp,
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': metrics.function_name}
                    ]
                },
                {
                    'MetricName': 'CPUUsage',
                    'Value': metrics.cpu_percent,
                    'Unit': 'Percent',
                    'Timestamp': metrics.timestamp,
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': metrics.function_name}
                    ]
                }
            ]
            
            self.cloudwatch.put_metric_data(
                Namespace='KrishiMitra/DataProcessing',
                MetricData=metric_data
            )
            
        except Exception as e:
            logger.error(f"Error sending metrics to CloudWatch: {e}")
    
    def get_metrics_summary(self, function_name: Optional[str] = None,
                           hours: int = 24) -> Dict[str, Any]:
        """
        Get summary of performance metrics
        
        Args:
            function_name: Optional function name to filter
            hours: Number of hours to look back
            
        Returns:
            Dictionary with metrics summary
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Filter metrics
        filtered_metrics = [
            m for m in self.metrics_history
            if m.timestamp >= cutoff_time and
            (function_name is None or m.function_name == function_name)
        ]
        
        if not filtered_metrics:
            return {}
        
        # Calculate statistics
        execution_times = [m.execution_time_seconds for m in filtered_metrics]
        memory_usages = [m.memory_usage_mb for m in filtered_metrics]
        cpu_usages = [m.cpu_percent for m in filtered_metrics]
        
        return {
            'function_name': function_name or 'all',
            'total_executions': len(filtered_metrics),
            'execution_time': {
                'avg': sum(execution_times) / len(execution_times),
                'min': min(execution_times),
                'max': max(execution_times),
                'total': sum(execution_times)
            },
            'memory_usage_mb': {
                'avg': sum(memory_usages) / len(memory_usages),
                'min': min(memory_usages),
                'max': max(memory_usages)
            },
            'cpu_usage_percent': {
                'avg': sum(cpu_usages) / len(cpu_usages),
                'min': min(cpu_usages),
                'max': max(cpu_usages)
            }
        }
    
    def identify_bottlenecks(self) -> List[Dict[str, Any]]:
        """
        Identify performance bottlenecks
        
        Returns:
            List of bottleneck issues with recommendations
        """
        bottlenecks = []
        
        # Analyze recent metrics
        summary = self.get_metrics_summary(hours=1)
        
        if not summary:
            return bottlenecks
        
        # Check for slow execution
        if summary['execution_time']['avg'] > 10:
            bottlenecks.append({
                'type': 'slow_execution',
                'severity': 'high',
                'metric': 'execution_time',
                'value': summary['execution_time']['avg'],
                'recommendation': 'Consider optimizing algorithm or using parallel processing'
            })
        
        # Check for high memory usage
        if summary['memory_usage_mb']['avg'] > 512:
            bottlenecks.append({
                'type': 'high_memory',
                'severity': 'medium',
                'metric': 'memory_usage',
                'value': summary['memory_usage_mb']['avg'],
                'recommendation': 'Consider processing data in batches or using generators'
            })
        
        # Check for high CPU usage
        if summary['cpu_usage_percent']['avg'] > 80:
            bottlenecks.append({
                'type': 'high_cpu',
                'severity': 'medium',
                'metric': 'cpu_usage',
                'value': summary['cpu_usage_percent']['avg'],
                'recommendation': 'Consider distributing workload across multiple instances'
            })
        
        return bottlenecks


class ResourceOptimizer:
    """
    Optimizes resource allocation and usage for data processing
    
    Provides recommendations and automatic adjustments for
    optimal performance and cost efficiency.
    """
    
    def __init__(self):
        self.cloudwatch = boto3.client('cloudwatch', region_name=settings.aws_region)
        self.autoscaling = boto3.client('application-autoscaling', region_name=settings.aws_region)
    
    async def analyze_resource_utilization(self, resource_id: str,
                                          service_namespace: str) -> Dict[str, Any]:
        """
        Analyze resource utilization patterns
        
        Args:
            resource_id: Resource identifier
            service_namespace: AWS service namespace
            
        Returns:
            Dictionary with utilization analysis
        """
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=24)
            
            # Get CPU utilization
            cpu_response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/ECS',  # Example for ECS
                MetricName='CPUUtilization',
                Dimensions=[
                    {'Name': 'ServiceName', 'Value': resource_id}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Average', 'Maximum']
            )
            
            # Get memory utilization
            memory_response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/ECS',
                MetricName='MemoryUtilization',
                Dimensions=[
                    {'Name': 'ServiceName', 'Value': resource_id}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Average', 'Maximum']
            )
            
            # Analyze patterns
            cpu_datapoints = cpu_response.get('Datapoints', [])
            memory_datapoints = memory_response.get('Datapoints', [])
            
            if not cpu_datapoints or not memory_datapoints:
                return {'status': 'insufficient_data'}
            
            avg_cpu = sum(d['Average'] for d in cpu_datapoints) / len(cpu_datapoints)
            max_cpu = max(d['Maximum'] for d in cpu_datapoints)
            avg_memory = sum(d['Average'] for d in memory_datapoints) / len(memory_datapoints)
            max_memory = max(d['Maximum'] for d in memory_datapoints)
            
            return {
                'resource_id': resource_id,
                'cpu_utilization': {
                    'average': avg_cpu,
                    'maximum': max_cpu
                },
                'memory_utilization': {
                    'average': avg_memory,
                    'maximum': max_memory
                },
                'recommendations': self._generate_recommendations(avg_cpu, max_cpu, avg_memory, max_memory)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing resource utilization: {e}")
            return {}
    
    def _generate_recommendations(self, avg_cpu: float, max_cpu: float,
                                 avg_memory: float, max_memory: float) -> List[str]:
        """Generate optimization recommendations based on utilization"""
        recommendations = []
        
        # CPU recommendations
        if avg_cpu < 30 and max_cpu < 50:
            recommendations.append(
                "CPU utilization is low. Consider reducing instance size to save costs."
            )
        elif avg_cpu > 70 or max_cpu > 90:
            recommendations.append(
                "CPU utilization is high. Consider scaling up or out to improve performance."
            )
        
        # Memory recommendations
        if avg_memory < 30 and max_memory < 50:
            recommendations.append(
                "Memory utilization is low. Consider reducing memory allocation."
            )
        elif avg_memory > 70 or max_memory > 90:
            recommendations.append(
                "Memory utilization is high. Consider increasing memory allocation."
            )
        
        # General recommendations
        if avg_cpu < 30 and avg_memory < 30:
            recommendations.append(
                "Overall utilization is low. Consider consolidating workloads or using spot instances."
            )
        
        return recommendations
    
    async def optimize_batch_size(self, processing_function: Callable,
                                 test_sizes: List[int] = None) -> int:
        """
        Determine optimal batch size for processing
        
        Args:
            processing_function: Function to test with different batch sizes
            test_sizes: List of batch sizes to test
            
        Returns:
            Optimal batch size
        """
        if test_sizes is None:
            test_sizes = [10, 50, 100, 500, 1000]
        
        results = []
        
        for batch_size in test_sizes:
            try:
                start_time = time.time()
                start_memory = psutil.Process().memory_info().rss / 1024 / 1024
                
                # Test processing with this batch size
                processing_function(batch_size)
                
                execution_time = time.time() - start_time
                memory_used = psutil.Process().memory_info().rss / 1024 / 1024 - start_memory
                
                # Calculate efficiency score (lower is better)
                efficiency_score = execution_time * memory_used / batch_size
                
                results.append({
                    'batch_size': batch_size,
                    'execution_time': execution_time,
                    'memory_used': memory_used,
                    'efficiency_score': efficiency_score
                })
                
            except Exception as e:
                logger.warning(f"Error testing batch size {batch_size}: {e}")
                continue
        
        if not results:
            return test_sizes[0]  # Return default
        
        # Find batch size with best efficiency
        optimal = min(results, key=lambda x: x['efficiency_score'])
        
        logger.info(
            f"Optimal batch size: {optimal['batch_size']} "
            f"(time: {optimal['execution_time']:.2f}s, memory: {optimal['memory_used']:.2f}MB)"
        )
        
        return optimal['batch_size']
