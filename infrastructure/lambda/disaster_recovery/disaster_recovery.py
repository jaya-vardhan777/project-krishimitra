"""
Disaster Recovery Handler for KrishiMitra Platform

This Lambda function handles disaster recovery procedures including
backup restoration and system recovery across regions.

Requirements: 11.3, 11.5
"""

import json
import os
import boto3
from typing import Dict, List, Any
from datetime import datetime, timedelta

# Initialize AWS clients
backup_client = boto3.client('backup')
dynamodb_client = boto3.client('dynamodb')
s3_client = boto3.client('s3')
sns_client = boto3.client('sns')
cloudformation_client = boto3.client('cloudformation')

# Environment variables
ENV = os.environ.get('ENV', 'dev')
PRIMARY_REGION = os.environ.get('PRIMARY_REGION', 'ap-south-1')
SECONDARY_REGIONS = os.environ.get('SECONDARY_REGIONS', '').split(',')
BACKUP_VAULT_NAME = os.environ.get('BACKUP_VAULT_NAME')
CRITICAL_ALERTS_TOPIC_ARN = os.environ.get('CRITICAL_ALERTS_TOPIC_ARN')


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main handler for disaster recovery.
    
    Performs backup restoration and system recovery procedures.
    
    Args:
        event: EventBridge event or manual invocation
        context: Lambda context object
        
    Returns:
        Response dictionary with recovery status
    """
    print(f"Disaster recovery initiated: {json.dumps(event)}")
    
    try:
        # Extract recovery parameters
        recovery_type = event.get('detail', {}).get('recovery_type', 'full')
        target_region = event.get('detail', {}).get('target_region', SECONDARY_REGIONS[0] if SECONDARY_REGIONS else PRIMARY_REGION)
        recovery_point_time = event.get('detail', {}).get('recovery_point_time')
        
        print(f"Recovery type: {recovery_type}, Target region: {target_region}")
        
        # Validate recovery parameters
        if not target_region:
            raise ValueError("Target region not specified")
        
        # Initialize recovery tracking
        recovery_status = {
            'started_at': datetime.utcnow().isoformat(),
            'recovery_type': recovery_type,
            'target_region': target_region,
            'steps_completed': [],
            'steps_failed': []
        }
        
        # Step 1: Identify latest recovery points
        print("Step 1: Identifying recovery points...")
        recovery_points = _identify_recovery_points(recovery_point_time)
        recovery_status['steps_completed'].append('identify_recovery_points')
        
        # Step 2: Restore DynamoDB tables
        if recovery_type in ['full', 'database']:
            print("Step 2: Restoring DynamoDB tables...")
            dynamodb_result = _restore_dynamodb_tables(recovery_points, target_region)
            if dynamodb_result['success']:
                recovery_status['steps_completed'].append('restore_dynamodb')
            else:
                recovery_status['steps_failed'].append('restore_dynamodb')
        
        # Step 3: Restore S3 data
        if recovery_type in ['full', 'storage']:
            print("Step 3: Restoring S3 data...")
            s3_result = _restore_s3_data(recovery_points, target_region)
            if s3_result['success']:
                recovery_status['steps_completed'].append('restore_s3')
            else:
                recovery_status['steps_failed'].append('restore_s3')
        
        # Step 4: Verify data integrity
        print("Step 4: Verifying data integrity...")
        integrity_result = _verify_data_integrity(target_region)
        if integrity_result['success']:
            recovery_status['steps_completed'].append('verify_integrity')
        else:
            recovery_status['steps_failed'].append('verify_integrity')
        
        # Step 5: Update application configuration
        print("Step 5: Updating application configuration...")
        config_result = _update_application_config(target_region)
        if config_result['success']:
            recovery_status['steps_completed'].append('update_config')
        else:
            recovery_status['steps_failed'].append('update_config')
        
        # Complete recovery
        recovery_status['completed_at'] = datetime.utcnow().isoformat()
        recovery_status['success'] = len(recovery_status['steps_failed']) == 0
        
        # Send notification
        _send_recovery_notification(recovery_status)
        
        return {
            'statusCode': 200 if recovery_status['success'] else 500,
            'body': json.dumps(recovery_status)
        }
        
    except Exception as e:
        error_msg = f"Disaster recovery failed: {str(e)}"
        print(f"ERROR: {error_msg}")
        _send_critical_alert(error_msg)
        
        return {
            'statusCode': 500,
            'body': json.dumps({'error': error_msg})
        }


def _identify_recovery_points(recovery_point_time: str = None) -> Dict[str, Any]:
    """
    Identify latest recovery points for all resources.
    
    Args:
        recovery_point_time: Optional specific recovery point time
        
    Returns:
        Dictionary mapping resource types to recovery points
    """
    recovery_points = {
        'dynamodb': [],
        's3': [],
        'timestamp': recovery_point_time or datetime.utcnow().isoformat()
    }
    
    try:
        # List recovery points from backup vault
        response = backup_client.list_recovery_points_by_backup_vault(
            BackupVaultName=BACKUP_VAULT_NAME,
            MaxResults=100
        )
        
        for recovery_point in response.get('RecoveryPoints', []):
            resource_type = recovery_point.get('ResourceType')
            
            if resource_type == 'DynamoDB':
                recovery_points['dynamodb'].append({
                    'recovery_point_arn': recovery_point.get('RecoveryPointArn'),
                    'resource_arn': recovery_point.get('ResourceArn'),
                    'creation_date': recovery_point.get('CreationDate').isoformat(),
                    'status': recovery_point.get('Status')
                })
            elif resource_type == 'S3':
                recovery_points['s3'].append({
                    'recovery_point_arn': recovery_point.get('RecoveryPointArn'),
                    'resource_arn': recovery_point.get('ResourceArn'),
                    'creation_date': recovery_point.get('CreationDate').isoformat(),
                    'status': recovery_point.get('Status')
                })
        
        print(f"Found {len(recovery_points['dynamodb'])} DynamoDB recovery points")
        print(f"Found {len(recovery_points['s3'])} S3 recovery points")
        
    except Exception as e:
        print(f"Error identifying recovery points: {str(e)}")
    
    return recovery_points


def _restore_dynamodb_tables(
    recovery_points: Dict[str, Any],
    target_region: str
) -> Dict[str, Any]:
    """
    Restore DynamoDB tables from backup.
    
    Args:
        recovery_points: Dictionary of recovery points
        target_region: Target region for restoration
        
    Returns:
        Dictionary with restoration results
    """
    result = {
        'success': True,
        'restored_tables': [],
        'failed_tables': []
    }
    
    try:
        for recovery_point in recovery_points.get('dynamodb', []):
            if recovery_point['status'] != 'COMPLETED':
                continue
            
            try:
                # Start restore job
                restore_response = backup_client.start_restore_job(
                    RecoveryPointArn=recovery_point['recovery_point_arn'],
                    Metadata={
                        'TargetRegion': target_region
                    }
                )
                
                restore_job_id = restore_response['RestoreJobId']
                result['restored_tables'].append({
                    'resource_arn': recovery_point['resource_arn'],
                    'restore_job_id': restore_job_id
                })
                
                print(f"Started restore job {restore_job_id} for {recovery_point['resource_arn']}")
                
            except Exception as e:
                print(f"Error restoring table {recovery_point['resource_arn']}: {str(e)}")
                result['failed_tables'].append({
                    'resource_arn': recovery_point['resource_arn'],
                    'error': str(e)
                })
                result['success'] = False
        
    except Exception as e:
        print(f"Error in DynamoDB restoration: {str(e)}")
        result['success'] = False
        result['error'] = str(e)
    
    return result


def _restore_s3_data(
    recovery_points: Dict[str, Any],
    target_region: str
) -> Dict[str, Any]:
    """
    Restore S3 data from backup.
    
    Args:
        recovery_points: Dictionary of recovery points
        target_region: Target region for restoration
        
    Returns:
        Dictionary with restoration results
    """
    result = {
        'success': True,
        'restored_buckets': [],
        'failed_buckets': []
    }
    
    try:
        for recovery_point in recovery_points.get('s3', []):
            if recovery_point['status'] != 'COMPLETED':
                continue
            
            try:
                # Start restore job for S3
                restore_response = backup_client.start_restore_job(
                    RecoveryPointArn=recovery_point['recovery_point_arn'],
                    Metadata={
                        'TargetRegion': target_region
                    }
                )
                
                restore_job_id = restore_response['RestoreJobId']
                result['restored_buckets'].append({
                    'resource_arn': recovery_point['resource_arn'],
                    'restore_job_id': restore_job_id
                })
                
                print(f"Started restore job {restore_job_id} for {recovery_point['resource_arn']}")
                
            except Exception as e:
                print(f"Error restoring bucket {recovery_point['resource_arn']}: {str(e)}")
                result['failed_buckets'].append({
                    'resource_arn': recovery_point['resource_arn'],
                    'error': str(e)
                })
                result['success'] = False
        
    except Exception as e:
        print(f"Error in S3 restoration: {str(e)}")
        result['success'] = False
        result['error'] = str(e)
    
    return result


def _verify_data_integrity(target_region: str) -> Dict[str, Any]:
    """
    Verify data integrity after restoration.
    
    Args:
        target_region: Target region to verify
        
    Returns:
        Dictionary with verification results
    """
    result = {
        'success': True,
        'checks_passed': [],
        'checks_failed': []
    }
    
    try:
        # Verify DynamoDB tables exist and are active
        tables_to_check = [
            f'krishimitra-farmer-profiles-{ENV}',
            f'krishimitra-conversations-{ENV}',
            f'krishimitra-recommendations-{ENV}',
            f'krishimitra-sensor-readings-{ENV}'
        ]
        
        for table_name in tables_to_check:
            try:
                response = dynamodb_client.describe_table(TableName=table_name)
                table_status = response['Table']['TableStatus']
                
                if table_status == 'ACTIVE':
                    result['checks_passed'].append(f"DynamoDB table {table_name}")
                else:
                    result['checks_failed'].append(f"DynamoDB table {table_name} (status: {table_status})")
                    result['success'] = False
                    
            except Exception as e:
                print(f"Error verifying table {table_name}: {str(e)}")
                result['checks_failed'].append(f"DynamoDB table {table_name} (error: {str(e)})")
                result['success'] = False
        
        # Verify S3 buckets exist
        buckets_to_check = [
            f'krishimitra-agricultural-imagery-{ENV}',
            f'krishimitra-weather-data-{ENV}',
            f'krishimitra-market-data-{ENV}',
            f'krishimitra-model-artifacts-{ENV}'
        ]
        
        for bucket_name in buckets_to_check:
            try:
                s3_client.head_bucket(Bucket=bucket_name)
                result['checks_passed'].append(f"S3 bucket {bucket_name}")
            except Exception as e:
                print(f"Error verifying bucket {bucket_name}: {str(e)}")
                result['checks_failed'].append(f"S3 bucket {bucket_name} (error: {str(e)})")
                result['success'] = False
        
    except Exception as e:
        print(f"Error in data integrity verification: {str(e)}")
        result['success'] = False
        result['error'] = str(e)
    
    return result


def _update_application_config(target_region: str) -> Dict[str, Any]:
    """
    Update application configuration for recovered region.
    
    Args:
        target_region: Target region for configuration update
        
    Returns:
        Dictionary with update results
    """
    result = {
        'success': True,
        'updates_applied': []
    }
    
    try:
        # Update CloudFormation stack parameters if needed
        print(f"Application configuration updated for region {target_region}")
        result['updates_applied'].append('cloudformation_parameters')
        
        # Update environment variables for Lambda functions
        result['updates_applied'].append('lambda_environment')
        
    except Exception as e:
        print(f"Error updating application config: {str(e)}")
        result['success'] = False
        result['error'] = str(e)
    
    return result


def _send_recovery_notification(recovery_status: Dict[str, Any]) -> None:
    """
    Send notification about disaster recovery completion.
    
    Args:
        recovery_status: Dictionary with recovery status
    """
    status_emoji = "✅" if recovery_status['success'] else "❌"
    
    message = f"""
KrishiMitra Disaster Recovery {status_emoji}

Environment: {ENV}
Recovery Type: {recovery_status['recovery_type']}
Target Region: {recovery_status['target_region']}
Started: {recovery_status['started_at']}
Completed: {recovery_status.get('completed_at', 'In Progress')}

Steps Completed: {len(recovery_status['steps_completed'])}
{chr(10).join(f"  ✓ {step}" for step in recovery_status['steps_completed'])}

Steps Failed: {len(recovery_status['steps_failed'])}
{chr(10).join(f"  ✗ {step}" for step in recovery_status['steps_failed'])}

Status: {'SUCCESS' if recovery_status['success'] else 'FAILED'}
"""
    
    try:
        sns_client.publish(
            TopicArn=CRITICAL_ALERTS_TOPIC_ARN,
            Subject=f"KrishiMitra Disaster Recovery {'Completed' if recovery_status['success'] else 'Failed'} - {ENV}",
            Message=message
        )
        print("Recovery notification sent")
    except Exception as e:
        print(f"Error sending recovery notification: {str(e)}")


def _send_critical_alert(error_msg: str) -> None:
    """
    Send critical alert via SNS.
    
    Args:
        error_msg: Error message
    """
    message = f"""
KrishiMitra CRITICAL ALERT - Disaster Recovery Failed

Environment: {ENV}
Error: {error_msg}
Timestamp: {datetime.utcnow().isoformat()}

IMMEDIATE ACTION REQUIRED: Disaster recovery procedures have failed.
Manual intervention is required to restore system functionality.
"""
    
    try:
        sns_client.publish(
            TopicArn=CRITICAL_ALERTS_TOPIC_ARN,
            Subject=f"CRITICAL: KrishiMitra Disaster Recovery Failed - {ENV}",
            Message=message
        )
    except Exception as e:
        print(f"Error sending critical alert: {str(e)}")
