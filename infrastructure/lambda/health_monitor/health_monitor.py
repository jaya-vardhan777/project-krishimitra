"""
Health Monitoring Handler for KrishiMitra Platform

This Lambda function performs periodic health checks across all regions
and publishes custom CloudWatch metrics for monitoring.

Requirements: 11.3, 11.5
"""

import json
import os
import boto3
from typing import Dict, List, Any
from datetime import datetime, timedelta

# Initialize AWS clients
route53_client = boto3.client('route53')
cloudwatch_client = boto3.client('cloudwatch')
sns_client = boto3.client('sns')

# Environment variables
ENV = os.environ.get('ENV', 'dev')
PRIMARY_REGION = os.environ.get('PRIMARY_REGION', 'ap-south-1')
SECONDARY_REGIONS = os.environ.get('SECONDARY_REGIONS', '').split(',')
PRIMARY_HEALTH_CHECK_ID = os.environ.get('PRIMARY_HEALTH_CHECK_ID')
OPERATIONAL_ALERTS_TOPIC_ARN = os.environ.get('OPERATIONAL_ALERTS_TOPIC_ARN')


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main handler for health monitoring.
    
    Performs periodic health checks and publishes metrics to CloudWatch.
    
    Args:
        event: EventBridge scheduled event
        context: Lambda context object
        
    Returns:
        Response dictionary with health status
    """
    print(f"Health monitor triggered at {datetime.utcnow().isoformat()}")
    
    try:
        # Check health of all regions
        health_status = _check_all_regions_health()
        
        # Publish metrics to CloudWatch
        _publish_health_metrics(health_status)
        
        # Check for degraded performance
        degraded_regions = _check_for_degradation(health_status)
        
        if degraded_regions:
            _send_degradation_alert(degraded_regions)
        
        # Calculate overall system health
        overall_health = _calculate_overall_health(health_status)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'timestamp': datetime.utcnow().isoformat(),
                'health_status': health_status,
                'overall_health': overall_health,
                'degraded_regions': degraded_regions
            })
        }
        
    except Exception as e:
        error_msg = f"Health monitoring failed: {str(e)}"
        print(f"ERROR: {error_msg}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({'error': error_msg})
        }


def _check_all_regions_health() -> Dict[str, Dict[str, Any]]:
    """
    Check health status of all regions.
    
    Returns:
        Dictionary mapping region to health status
    """
    health_status = {}
    
    # Check primary region
    health_status[PRIMARY_REGION] = _check_region_health(
        PRIMARY_REGION,
        PRIMARY_HEALTH_CHECK_ID
    )
    
    # Check secondary regions
    for region in SECONDARY_REGIONS:
        if region:  # Skip empty strings
            health_check_id = _get_health_check_id_for_region(region)
            health_status[region] = _check_region_health(region, health_check_id)
    
    return health_status


def _check_region_health(region: str, health_check_id: str) -> Dict[str, Any]:
    """
    Check health status for a specific region.
    
    Args:
        region: AWS region identifier
        health_check_id: Route 53 health check ID
        
    Returns:
        Dictionary with health status details
    """
    try:
        # Get health check status from Route 53
        response = route53_client.get_health_check_status(
            HealthCheckId=health_check_id
        )
        
        checkers = response.get('HealthCheckObservations', [])
        
        if not checkers:
            return {
                'status': 'UNKNOWN',
                'healthy_checkers': 0,
                'total_checkers': 0,
                'latency_ms': None,
                'error': 'No health check data available'
            }
        
        # Count healthy checkers
        healthy_count = sum(1 for c in checkers if c.get('StatusReport', {}).get('Status') == 'Success')
        total_count = len(checkers)
        
        # Calculate average latency
        latencies = [
            c.get('StatusReport', {}).get('CheckedTime')
            for c in checkers
            if c.get('StatusReport', {}).get('CheckedTime')
        ]
        avg_latency = sum(latencies) / len(latencies) if latencies else None
        
        # Determine overall status
        health_percentage = (healthy_count / total_count) * 100 if total_count > 0 else 0
        
        if health_percentage >= 75:
            status = 'HEALTHY'
        elif health_percentage >= 50:
            status = 'DEGRADED'
        else:
            status = 'UNHEALTHY'
        
        return {
            'status': status,
            'healthy_checkers': healthy_count,
            'total_checkers': total_count,
            'health_percentage': health_percentage,
            'latency_ms': avg_latency,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        print(f"Error checking health for region {region}: {str(e)}")
        return {
            'status': 'ERROR',
            'healthy_checkers': 0,
            'total_checkers': 0,
            'latency_ms': None,
            'error': str(e)
        }


def _get_health_check_id_for_region(region: str) -> str:
    """
    Get Route 53 health check ID for a specific region.
    
    Args:
        region: AWS region identifier
        
    Returns:
        Health check ID
    """
    # In production, this would query Route 53 or use stored mappings
    return f"health-check-{region}-{ENV}"


def _publish_health_metrics(health_status: Dict[str, Dict[str, Any]]) -> None:
    """
    Publish health metrics to CloudWatch.
    
    Args:
        health_status: Dictionary of region health statuses
    """
    metric_data = []
    
    for region, status in health_status.items():
        # Health status metric (1 = healthy, 0.5 = degraded, 0 = unhealthy)
        health_value = {
            'HEALTHY': 1.0,
            'DEGRADED': 0.5,
            'UNHEALTHY': 0.0,
            'ERROR': 0.0,
            'UNKNOWN': 0.0
        }.get(status['status'], 0.0)
        
        metric_data.append({
            'MetricName': 'RegionHealth',
            'Value': health_value,
            'Unit': 'None',
            'Timestamp': datetime.utcnow(),
            'Dimensions': [
                {'Name': 'Environment', 'Value': ENV},
                {'Name': 'Region', 'Value': region}
            ]
        })
        
        # Health percentage metric
        if status.get('health_percentage') is not None:
            metric_data.append({
                'MetricName': 'HealthPercentage',
                'Value': status['health_percentage'],
                'Unit': 'Percent',
                'Timestamp': datetime.utcnow(),
                'Dimensions': [
                    {'Name': 'Environment', 'Value': ENV},
                    {'Name': 'Region', 'Value': region}
                ]
            })
        
        # Latency metric
        if status.get('latency_ms') is not None:
            metric_data.append({
                'MetricName': 'HealthCheckLatency',
                'Value': status['latency_ms'],
                'Unit': 'Milliseconds',
                'Timestamp': datetime.utcnow(),
                'Dimensions': [
                    {'Name': 'Environment', 'Value': ENV},
                    {'Name': 'Region', 'Value': region}
                ]
            })
    
    # Publish metrics in batches of 20 (CloudWatch limit)
    for i in range(0, len(metric_data), 20):
        batch = metric_data[i:i+20]
        try:
            cloudwatch_client.put_metric_data(
                Namespace='KrishiMitra/Health',
                MetricData=batch
            )
            print(f"Published {len(batch)} health metrics")
        except Exception as e:
            print(f"Error publishing metrics: {str(e)}")


def _check_for_degradation(health_status: Dict[str, Dict[str, Any]]) -> List[str]:
    """
    Check for regions with degraded performance.
    
    Args:
        health_status: Dictionary of region health statuses
        
    Returns:
        List of degraded region identifiers
    """
    degraded_regions = []
    
    for region, status in health_status.items():
        if status['status'] in ['DEGRADED', 'UNHEALTHY', 'ERROR']:
            degraded_regions.append(region)
            print(f"Region {region} is degraded: {status['status']}")
    
    return degraded_regions


def _send_degradation_alert(degraded_regions: List[str]) -> None:
    """
    Send alert for degraded regions.
    
    Args:
        degraded_regions: List of degraded region identifiers
    """
    message = f"""
KrishiMitra Performance Degradation Alert

Environment: {ENV}
Degraded Regions: {', '.join(degraded_regions)}
Timestamp: {datetime.utcnow().isoformat()}

The following regions are experiencing degraded performance or health issues.
Please investigate and take corrective action if necessary.

Regions affected: {len(degraded_regions)}
"""
    
    try:
        sns_client.publish(
            TopicArn=OPERATIONAL_ALERTS_TOPIC_ARN,
            Subject=f"KrishiMitra Performance Degradation - {ENV}",
            Message=message
        )
        print(f"Degradation alert sent for {len(degraded_regions)} regions")
    except Exception as e:
        print(f"Error sending degradation alert: {str(e)}")


def _calculate_overall_health(health_status: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate overall system health across all regions.
    
    Args:
        health_status: Dictionary of region health statuses
        
    Returns:
        Dictionary with overall health metrics
    """
    total_regions = len(health_status)
    healthy_regions = sum(1 for s in health_status.values() if s['status'] == 'HEALTHY')
    degraded_regions = sum(1 for s in health_status.values() if s['status'] == 'DEGRADED')
    unhealthy_regions = sum(1 for s in health_status.values() if s['status'] in ['UNHEALTHY', 'ERROR'])
    
    overall_health_percentage = (healthy_regions / total_regions * 100) if total_regions > 0 else 0
    
    # Determine overall status
    if overall_health_percentage >= 90:
        overall_status = 'HEALTHY'
    elif overall_health_percentage >= 70:
        overall_status = 'DEGRADED'
    else:
        overall_status = 'CRITICAL'
    
    # Publish overall health metric
    try:
        cloudwatch_client.put_metric_data(
            Namespace='KrishiMitra/Health',
            MetricData=[
                {
                    'MetricName': 'OverallSystemHealth',
                    'Value': overall_health_percentage,
                    'Unit': 'Percent',
                    'Timestamp': datetime.utcnow(),
                    'Dimensions': [
                        {'Name': 'Environment', 'Value': ENV}
                    ]
                }
            ]
        )
    except Exception as e:
        print(f"Error publishing overall health metric: {str(e)}")
    
    return {
        'status': overall_status,
        'health_percentage': overall_health_percentage,
        'total_regions': total_regions,
        'healthy_regions': healthy_regions,
        'degraded_regions': degraded_regions,
        'unhealthy_regions': unhealthy_regions
    }
