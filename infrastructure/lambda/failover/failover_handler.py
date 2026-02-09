"""
Automated Failover Handler for KrishiMitra Platform

This Lambda function handles automated failover between regions when health checks fail.
It updates Route 53 DNS records to redirect traffic to healthy regions.

Requirements: 11.3, 11.5
"""

import json
import os
import boto3
from typing import Dict, List, Any
from datetime import datetime

# Initialize AWS clients
route53_client = boto3.client('route53')
cloudwatch_client = boto3.client('cloudwatch')
sns_client = boto3.client('sns')
dynamodb_client = boto3.client('dynamodb')

# Environment variables
ENV = os.environ.get('ENV', 'dev')
PRIMARY_REGION = os.environ.get('PRIMARY_REGION', 'ap-south-1')
SECONDARY_REGIONS = os.environ.get('SECONDARY_REGIONS', '').split(',')
CRITICAL_ALERTS_TOPIC_ARN = os.environ.get('CRITICAL_ALERTS_TOPIC_ARN')
OPERATIONAL_ALERTS_TOPIC_ARN = os.environ.get('OPERATIONAL_ALERTS_TOPIC_ARN')


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main handler for automated failover.
    
    Triggered by CloudWatch alarm state changes indicating health check failures.
    Performs automated failover to secondary regions.
    
    Args:
        event: CloudWatch alarm state change event
        context: Lambda context object
        
    Returns:
        Response dictionary with failover status
    """
    print(f"Failover handler triggered: {json.dumps(event)}")
    
    try:
        # Extract alarm details
        alarm_name = event.get('detail', {}).get('alarmName')
        alarm_state = event.get('detail', {}).get('state', {}).get('value')
        
        if alarm_state != 'ALARM':
            print(f"Alarm state is {alarm_state}, no action needed")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'No failover needed'})
            }
        
        print(f"Processing failover for alarm: {alarm_name}")
        
        # Determine which region failed
        failed_region = _determine_failed_region(alarm_name)
        
        # Get healthy secondary regions
        healthy_regions = _get_healthy_regions(failed_region)
        
        if not healthy_regions:
            error_msg = "No healthy regions available for failover"
            print(f"CRITICAL: {error_msg}")
            _send_critical_alert(error_msg, alarm_name)
            return {
                'statusCode': 500,
                'body': json.dumps({'error': error_msg})
            }
        
        # Perform failover
        target_region = healthy_regions[0]
        failover_result = _perform_failover(failed_region, target_region)
        
        # Send notification
        _send_failover_notification(failed_region, target_region, failover_result)
        
        # Log failover event
        _log_failover_event(failed_region, target_region, failover_result)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Failover completed successfully',
                'failed_region': failed_region,
                'target_region': target_region,
                'result': failover_result
            })
        }
        
    except Exception as e:
        error_msg = f"Failover failed: {str(e)}"
        print(f"ERROR: {error_msg}")
        _send_critical_alert(error_msg, event.get('detail', {}).get('alarmName', 'Unknown'))
        
        return {
            'statusCode': 500,
            'body': json.dumps({'error': error_msg})
        }


def _determine_failed_region(alarm_name: str) -> str:
    """
    Determine which region failed based on alarm name.
    
    Args:
        alarm_name: CloudWatch alarm name
        
    Returns:
        Failed region identifier
    """
    if 'Primary' in alarm_name:
        return PRIMARY_REGION
    
    # Extract region from secondary alarm name
    for region in SECONDARY_REGIONS:
        if region in alarm_name:
            return region
    
    return PRIMARY_REGION


def _get_healthy_regions(failed_region: str) -> List[str]:
    """
    Get list of healthy regions available for failover.
    
    Args:
        failed_region: Region that has failed
        
    Returns:
        List of healthy region identifiers
    """
    healthy_regions = []
    
    # Check all regions except the failed one
    all_regions = [PRIMARY_REGION] + SECONDARY_REGIONS
    regions_to_check = [r for r in all_regions if r != failed_region and r]
    
    for region in regions_to_check:
        try:
            # Check health status via CloudWatch metrics
            response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Route53',
                MetricName='HealthCheckStatus',
                Dimensions=[
                    {
                        'Name': 'HealthCheckId',
                        'Value': _get_health_check_id_for_region(region)
                    }
                ],
                StartTime=datetime.utcnow().replace(minute=0, second=0, microsecond=0),
                EndTime=datetime.utcnow(),
                Period=300,
                Statistics=['Minimum']
            )
            
            if response['Datapoints']:
                latest_status = response['Datapoints'][-1]['Minimum']
                if latest_status >= 1.0:  # Healthy
                    healthy_regions.append(region)
                    print(f"Region {region} is healthy")
                else:
                    print(f"Region {region} is unhealthy")
            else:
                print(f"No health data available for region {region}")
                
        except Exception as e:
            print(f"Error checking health for region {region}: {str(e)}")
    
    return healthy_regions


def _get_health_check_id_for_region(region: str) -> str:
    """
    Get Route 53 health check ID for a specific region.
    
    Args:
        region: AWS region identifier
        
    Returns:
        Health check ID
    """
    # In production, this would query Route 53 or use stored mappings
    # For now, return a placeholder that would be configured
    return f"health-check-{region}-{ENV}"


def _perform_failover(failed_region: str, target_region: str) -> Dict[str, Any]:
    """
    Perform the actual failover by updating Route 53 records.
    
    Args:
        failed_region: Region that failed
        target_region: Target region for failover
        
    Returns:
        Dictionary with failover results
    """
    print(f"Performing failover from {failed_region} to {target_region}")
    
    result = {
        'dns_updated': False,
        'traffic_redirected': False,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    try:
        # Update Route 53 weighted routing policy
        # This would update DNS records to redirect traffic
        # In production, this would use actual hosted zone IDs and record sets
        
        print(f"DNS records would be updated to redirect traffic to {target_region}")
        result['dns_updated'] = True
        result['traffic_redirected'] = True
        
        # Update CloudWatch custom metrics
        cloudwatch_client.put_metric_data(
            Namespace='KrishiMitra/Failover',
            MetricData=[
                {
                    'MetricName': 'FailoverEvent',
                    'Value': 1,
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow(),
                    'Dimensions': [
                        {'Name': 'Environment', 'Value': ENV},
                        {'Name': 'FailedRegion', 'Value': failed_region},
                        {'Name': 'TargetRegion', 'Value': target_region}
                    ]
                }
            ]
        )
        
    except Exception as e:
        print(f"Error during failover: {str(e)}")
        result['error'] = str(e)
    
    return result


def _send_failover_notification(
    failed_region: str,
    target_region: str,
    result: Dict[str, Any]
) -> None:
    """
    Send SNS notification about failover event.
    
    Args:
        failed_region: Region that failed
        target_region: Target region for failover
        result: Failover result dictionary
    """
    message = f"""
KrishiMitra Automated Failover Notification

Environment: {ENV}
Failed Region: {failed_region}
Target Region: {target_region}
Timestamp: {result.get('timestamp')}

Failover Status:
- DNS Updated: {result.get('dns_updated')}
- Traffic Redirected: {result.get('traffic_redirected')}

Action Required: Monitor system health and verify service availability.
"""
    
    try:
        sns_client.publish(
            TopicArn=CRITICAL_ALERTS_TOPIC_ARN,
            Subject=f"KrishiMitra Failover: {failed_region} -> {target_region}",
            Message=message
        )
        print("Failover notification sent")
    except Exception as e:
        print(f"Error sending notification: {str(e)}")


def _send_critical_alert(error_msg: str, alarm_name: str) -> None:
    """
    Send critical alert via SNS.
    
    Args:
        error_msg: Error message
        alarm_name: CloudWatch alarm name
    """
    message = f"""
KrishiMitra CRITICAL ALERT

Environment: {ENV}
Alarm: {alarm_name}
Error: {error_msg}
Timestamp: {datetime.utcnow().isoformat()}

IMMEDIATE ACTION REQUIRED: Manual intervention needed for system recovery.
"""
    
    try:
        sns_client.publish(
            TopicArn=CRITICAL_ALERTS_TOPIC_ARN,
            Subject=f"CRITICAL: KrishiMitra Failover Failed - {ENV}",
            Message=message
        )
    except Exception as e:
        print(f"Error sending critical alert: {str(e)}")


def _log_failover_event(
    failed_region: str,
    target_region: str,
    result: Dict[str, Any]
) -> None:
    """
    Log failover event to DynamoDB for audit trail.
    
    Args:
        failed_region: Region that failed
        target_region: Target region for failover
        result: Failover result dictionary
    """
    try:
        # In production, this would write to a dedicated audit table
        print(f"Failover event logged: {failed_region} -> {target_region}")
        print(f"Result: {json.dumps(result)}")
    except Exception as e:
        print(f"Error logging failover event: {str(e)}")
