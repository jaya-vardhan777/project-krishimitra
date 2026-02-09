"""
S3 Lifecycle Management and Data Archiving

This module implements data archiving and lifecycle management
using S3 Intelligent Tiering and lifecycle policies.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError

from src.krishimitra.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LifecycleRule:
    """Configuration for S3 lifecycle rule"""
    rule_id: str
    prefix: str
    enabled: bool = True
    transition_to_ia_days: int = 30  # Transition to Infrequent Access
    transition_to_glacier_days: int = 90  # Transition to Glacier
    transition_to_deep_archive_days: int = 180  # Transition to Deep Archive
    expiration_days: Optional[int] = None  # Delete after days
    noncurrent_version_expiration_days: int = 30
    abort_incomplete_multipart_days: int = 7


@dataclass
class IntelligentTieringConfig:
    """Configuration for S3 Intelligent Tiering"""
    config_id: str
    prefix: str
    archive_access_tier_days: int = 90
    deep_archive_access_tier_days: int = 180
    tags: Optional[Dict[str, str]] = None


class S3LifecycleManager:
    """
    Manages S3 lifecycle policies and storage optimization
    
    Implements automatic data tiering and archiving based on
    access patterns and retention requirements.
    """
    
    def __init__(self, bucket_name: Optional[str] = None):
        self.bucket_name = bucket_name or settings.s3_bucket
        self.s3_client = boto3.client('s3', region_name=settings.aws_region)
    
    async def create_lifecycle_policy(self, rules: List[LifecycleRule]) -> bool:
        """
        Create or update S3 lifecycle policy
        
        Args:
            rules: List of lifecycle rules
            
        Returns:
            True if policy created successfully
        """
        try:
            lifecycle_rules = []
            
            for rule in rules:
                rule_config = {
                    'ID': rule.rule_id,
                    'Status': 'Enabled' if rule.enabled else 'Disabled',
                    'Filter': {'Prefix': rule.prefix},
                    'Transitions': [],
                    'NoncurrentVersionTransitions': [],
                    'AbortIncompleteMultipartUpload': {
                        'DaysAfterInitiation': rule.abort_incomplete_multipart_days
                    }
                }
                
                # Add transitions
                if rule.transition_to_ia_days:
                    rule_config['Transitions'].append({
                        'Days': rule.transition_to_ia_days,
                        'StorageClass': 'STANDARD_IA'
                    })
                
                if rule.transition_to_glacier_days:
                    rule_config['Transitions'].append({
                        'Days': rule.transition_to_glacier_days,
                        'StorageClass': 'GLACIER'
                    })
                
                if rule.transition_to_deep_archive_days:
                    rule_config['Transitions'].append({
                        'Days': rule.transition_to_deep_archive_days,
                        'StorageClass': 'DEEP_ARCHIVE'
                    })
                
                # Add expiration
                if rule.expiration_days:
                    rule_config['Expiration'] = {'Days': rule.expiration_days}
                
                # Add noncurrent version expiration
                rule_config['NoncurrentVersionExpiration'] = {
                    'NoncurrentDays': rule.noncurrent_version_expiration_days
                }
                
                lifecycle_rules.append(rule_config)
            
            # Apply lifecycle configuration
            self.s3_client.put_bucket_lifecycle_configuration(
                Bucket=self.bucket_name,
                LifecycleConfiguration={'Rules': lifecycle_rules}
            )
            
            logger.info(f"Created lifecycle policy for bucket {self.bucket_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating lifecycle policy: {e}")
            return False
    
    async def enable_intelligent_tiering(self, config: IntelligentTieringConfig) -> bool:
        """
        Enable S3 Intelligent Tiering for automatic cost optimization
        
        Args:
            config: Intelligent Tiering configuration
            
        Returns:
            True if enabled successfully
        """
        try:
            tiering_config = {
                'Id': config.config_id,
                'Status': 'Enabled',
                'Filter': {'Prefix': config.prefix},
                'Tierings': [
                    {
                        'Days': config.archive_access_tier_days,
                        'AccessTier': 'ARCHIVE_ACCESS'
                    },
                    {
                        'Days': config.deep_archive_access_tier_days,
                        'AccessTier': 'DEEP_ARCHIVE_ACCESS'
                    }
                ]
            }
            
            # Add tag filter if provided
            if config.tags:
                tiering_config['Filter']['And'] = {
                    'Prefix': config.prefix,
                    'Tags': [{'Key': k, 'Value': v} for k, v in config.tags.items()]
                }
            
            self.s3_client.put_bucket_intelligent_tiering_configuration(
                Bucket=self.bucket_name,
                Id=config.config_id,
                IntelligentTieringConfiguration=tiering_config
            )
            
            logger.info(f"Enabled Intelligent Tiering for {self.bucket_name}/{config.prefix}")
            return True
            
        except Exception as e:
            logger.error(f"Error enabling Intelligent Tiering: {e}")
            return False
    
    async def get_storage_metrics(self, prefix: Optional[str] = None) -> Dict[str, Any]:
        """
        Get storage metrics for bucket or prefix
        
        Args:
            prefix: Optional prefix to filter objects
            
        Returns:
            Dictionary with storage metrics
        """
        try:
            metrics = {
                'total_objects': 0,
                'total_size_bytes': 0,
                'storage_classes': {},
                'oldest_object': None,
                'newest_object': None
            }
            
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=prefix or ''
            )
            
            for page in page_iterator:
                if 'Contents' not in page:
                    continue
                
                for obj in page['Contents']:
                    metrics['total_objects'] += 1
                    metrics['total_size_bytes'] += obj['Size']
                    
                    # Track storage classes
                    storage_class = obj.get('StorageClass', 'STANDARD')
                    metrics['storage_classes'][storage_class] = \
                        metrics['storage_classes'].get(storage_class, 0) + 1
                    
                    # Track oldest and newest
                    last_modified = obj['LastModified']
                    if metrics['oldest_object'] is None or last_modified < metrics['oldest_object']:
                        metrics['oldest_object'] = last_modified
                    if metrics['newest_object'] is None or last_modified > metrics['newest_object']:
                        metrics['newest_object'] = last_modified
            
            # Convert to human-readable sizes
            metrics['total_size_gb'] = metrics['total_size_bytes'] / (1024 ** 3)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting storage metrics: {e}")
            return {}
    
    async def optimize_storage_costs(self) -> Dict[str, Any]:
        """
        Analyze and optimize storage costs
        
        Returns:
            Dictionary with optimization recommendations
        """
        try:
            recommendations = {
                'total_potential_savings': 0,
                'recommendations': []
            }
            
            # Get current storage metrics
            metrics = await self.get_storage_metrics()
            
            # Analyze objects that could be moved to cheaper storage
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=self.bucket_name)
            
            now = datetime.now(tz=metrics.get('oldest_object', datetime.now()).tzinfo)
            
            for page in page_iterator:
                if 'Contents' not in page:
                    continue
                
                for obj in page['Contents']:
                    storage_class = obj.get('StorageClass', 'STANDARD')
                    last_modified = obj['LastModified']
                    age_days = (now - last_modified).days
                    size_gb = obj['Size'] / (1024 ** 3)
                    
                    # Check if object should be in cheaper storage
                    if storage_class == 'STANDARD' and age_days > 30:
                        # Calculate potential savings
                        standard_cost = size_gb * 0.023  # $0.023 per GB/month
                        ia_cost = size_gb * 0.0125  # $0.0125 per GB/month
                        monthly_savings = standard_cost - ia_cost
                        
                        if monthly_savings > 0.01:  # Only recommend if savings > $0.01
                            recommendations['recommendations'].append({
                                'key': obj['Key'],
                                'current_class': storage_class,
                                'recommended_class': 'STANDARD_IA',
                                'age_days': age_days,
                                'size_gb': size_gb,
                                'monthly_savings': monthly_savings
                            })
                            recommendations['total_potential_savings'] += monthly_savings
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error optimizing storage costs: {e}")
            return {}


class DataArchiver:
    """
    Handles data archiving and retrieval operations
    
    Manages archiving of historical data to cost-effective storage
    and retrieval when needed for analysis.
    """
    
    def __init__(self, bucket_name: Optional[str] = None):
        self.bucket_name = bucket_name or settings.s3_bucket
        self.s3_client = boto3.client('s3', region_name=settings.aws_region)
        self.glacier_client = boto3.client('glacier', region_name=settings.aws_region)
    
    async def archive_old_data(self, prefix: str, age_days: int,
                              target_storage_class: str = 'GLACIER') -> Dict[str, int]:
        """
        Archive data older than specified age
        
        Args:
            prefix: S3 prefix to archive
            age_days: Archive data older than this many days
            target_storage_class: Target storage class (GLACIER or DEEP_ARCHIVE)
            
        Returns:
            Dictionary with archived object count and total size
        """
        try:
            archived_count = 0
            archived_size = 0
            
            cutoff_date = datetime.now() - timedelta(days=age_days)
            
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            for page in page_iterator:
                if 'Contents' not in page:
                    continue
                
                for obj in page['Contents']:
                    # Check if object is old enough
                    if obj['LastModified'].replace(tzinfo=None) < cutoff_date:
                        current_class = obj.get('StorageClass', 'STANDARD')
                        
                        # Skip if already in target class or cheaper
                        if current_class in [target_storage_class, 'DEEP_ARCHIVE']:
                            continue
                        
                        # Copy object to new storage class
                        self.s3_client.copy_object(
                            Bucket=self.bucket_name,
                            CopySource={'Bucket': self.bucket_name, 'Key': obj['Key']},
                            Key=obj['Key'],
                            StorageClass=target_storage_class,
                            MetadataDirective='COPY'
                        )
                        
                        archived_count += 1
                        archived_size += obj['Size']
            
            logger.info(f"Archived {archived_count} objects ({archived_size / (1024**3):.2f} GB)")
            
            return {
                'archived_count': archived_count,
                'archived_size_bytes': archived_size,
                'archived_size_gb': archived_size / (1024 ** 3)
            }
            
        except Exception as e:
            logger.error(f"Error archiving data: {e}")
            return {'archived_count': 0, 'archived_size_bytes': 0}
    
    async def restore_archived_data(self, key: str, days: int = 7,
                                   tier: str = 'Standard') -> bool:
        """
        Restore archived data from Glacier
        
        Args:
            key: S3 object key to restore
            days: Number of days to keep restored copy
            tier: Retrieval tier (Expedited, Standard, or Bulk)
            
        Returns:
            True if restore initiated successfully
        """
        try:
            self.s3_client.restore_object(
                Bucket=self.bucket_name,
                Key=key,
                RestoreRequest={
                    'Days': days,
                    'GlacierJobParameters': {
                        'Tier': tier
                    }
                }
            )
            
            logger.info(f"Initiated restore for {key} (tier: {tier}, days: {days})")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'RestoreAlreadyInProgress':
                logger.info(f"Restore already in progress for {key}")
                return True
            logger.error(f"Error restoring archived data: {e}")
            return False
    
    async def check_restore_status(self, key: str) -> Dict[str, Any]:
        """
        Check restore status of archived object
        
        Args:
            key: S3 object key
            
        Returns:
            Dictionary with restore status information
        """
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )
            
            restore_status = response.get('Restore', '')
            
            if not restore_status:
                return {'status': 'not_archived', 'available': True}
            
            if 'ongoing-request="true"' in restore_status:
                return {'status': 'in_progress', 'available': False}
            
            if 'ongoing-request="false"' in restore_status:
                # Extract expiry date
                import re
                expiry_match = re.search(r'expiry-date="([^"]+)"', restore_status)
                expiry_date = expiry_match.group(1) if expiry_match else None
                
                return {
                    'status': 'restored',
                    'available': True,
                    'expiry_date': expiry_date
                }
            
            return {'status': 'unknown', 'available': False}
            
        except Exception as e:
            logger.error(f"Error checking restore status: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def cleanup_expired_data(self, prefix: str, retention_days: int) -> Dict[str, int]:
        """
        Delete data older than retention period
        
        Args:
            prefix: S3 prefix to clean up
            retention_days: Delete data older than this many days
            
        Returns:
            Dictionary with deleted object count
        """
        try:
            deleted_count = 0
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            objects_to_delete = []
            
            for page in page_iterator:
                if 'Contents' not in page:
                    continue
                
                for obj in page['Contents']:
                    if obj['LastModified'].replace(tzinfo=None) < cutoff_date:
                        objects_to_delete.append({'Key': obj['Key']})
                        
                        # Delete in batches of 1000
                        if len(objects_to_delete) >= 1000:
                            self.s3_client.delete_objects(
                                Bucket=self.bucket_name,
                                Delete={'Objects': objects_to_delete}
                            )
                            deleted_count += len(objects_to_delete)
                            objects_to_delete = []
            
            # Delete remaining objects
            if objects_to_delete:
                self.s3_client.delete_objects(
                    Bucket=self.bucket_name,
                    Delete={'Objects': objects_to_delete}
                )
                deleted_count += len(objects_to_delete)
            
            logger.info(f"Deleted {deleted_count} expired objects from {prefix}")
            
            return {'deleted_count': deleted_count}
            
        except Exception as e:
            logger.error(f"Error cleaning up expired data: {e}")
            return {'deleted_count': 0}
