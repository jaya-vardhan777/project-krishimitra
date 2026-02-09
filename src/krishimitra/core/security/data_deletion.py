"""
Data deletion and right-to-be-forgotten implementation for KrishiMitra platform.

This module provides capabilities for farmers to request deletion of their personal data,
ensuring compliance with privacy regulations and data protection requirements.
"""

import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pydantic import BaseModel, Field
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class DeletionStatus(str, Enum):
    """Status of data deletion request."""
    
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeletionScope(str, Enum):
    """Scope of data deletion."""
    
    PROFILE_ONLY = "profile_only"
    RECOMMENDATIONS = "recommendations"
    CONVERSATIONS = "conversations"
    ALL_DATA = "all_data"
    SPECIFIC_CATEGORIES = "specific_categories"


class DeletionRequest(BaseModel):
    """Model for data deletion request."""
    
    request_id: str = Field(..., description="Unique deletion request ID")
    farmer_id: str = Field(..., description="Farmer ID")
    scope: DeletionScope = Field(..., description="Scope of deletion")
    data_categories: List[str] = Field(default_factory=list, description="Specific data categories to delete")
    reason: Optional[str] = Field(None, description="Reason for deletion")
    requested_at: datetime = Field(default_factory=datetime.utcnow, description="When request was made")
    scheduled_for: datetime = Field(..., description="When deletion should be executed")
    status: DeletionStatus = Field(default=DeletionStatus.PENDING, description="Current status")
    completed_at: Optional[datetime] = Field(None, description="When deletion was completed")
    deleted_items: Dict[str, int] = Field(default_factory=dict, description="Count of deleted items by type")
    error_message: Optional[str] = Field(None, description="Error message if deletion failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class DataDeletionManager:
    """
    Manager for handling data deletion requests and right-to-be-forgotten.
    
    Provides methods to request, schedule, and execute data deletion across
    all storage systems while maintaining audit trails.
    """
    
    def __init__(
        self,
        deletion_table_name: str = "DataDeletionRequests",
        grace_period_days: int = 30
    ):
        """
        Initialize data deletion manager.
        
        Args:
            deletion_table_name: DynamoDB table for deletion requests
            grace_period_days: Grace period before actual deletion (default 30 days)
        """
        self.deletion_table_name = deletion_table_name
        self.grace_period_days = grace_period_days
        
        # Initialize AWS clients
        self.dynamodb = boto3.resource('dynamodb')
        self.s3 = boto3.client('s3')
        
        self.deletion_table = None
        try:
            self.deletion_table = self.dynamodb.Table(self.deletion_table_name)
        except Exception as e:
            logger.warning(f"Could not connect to deletion table: {e}")
        
        # Define data storage locations
        self.data_locations = {
            "profile": {
                "dynamodb_table": "FarmerProfiles",
                "s3_bucket": None
            },
            "recommendations": {
                "dynamodb_table": "Recommendations",
                "s3_bucket": None
            },
            "conversations": {
                "dynamodb_table": "Conversations",
                "s3_bucket": None
            },
            "sensor_data": {
                "dynamodb_table": "SensorReadings",
                "s3_bucket": "krishimitra-sensor-data"
            },
            "images": {
                "dynamodb_table": None,
                "s3_bucket": "krishimitra-farmer-images"
            },
            "audit_logs": {
                "dynamodb_table": "AuditLogs",
                "s3_bucket": None
            }
        }
    
    def _generate_request_id(self, farmer_id: str) -> str:
        """Generate unique deletion request ID."""
        import uuid
        return f"DEL_{farmer_id}_{uuid.uuid4().hex[:8]}"
    
    def create_deletion_request(
        self,
        farmer_id: str,
        scope: DeletionScope = DeletionScope.ALL_DATA,
        data_categories: Optional[List[str]] = None,
        reason: Optional[str] = None,
        immediate: bool = False
    ) -> DeletionRequest:
        """
        Create a data deletion request.
        
        Args:
            farmer_id: Farmer ID
            scope: Scope of deletion
            data_categories: Specific categories to delete (if scope is SPECIFIC_CATEGORIES)
            reason: Reason for deletion
            immediate: If True, schedule for immediate deletion (skip grace period)
            
        Returns:
            Deletion request record
        """
        request_id = self._generate_request_id(farmer_id)
        
        # Calculate scheduled deletion time
        if immediate:
            scheduled_for = datetime.utcnow()
        else:
            scheduled_for = datetime.utcnow() + timedelta(days=self.grace_period_days)
        
        deletion_request = DeletionRequest(
            request_id=request_id,
            farmer_id=farmer_id,
            scope=scope,
            data_categories=data_categories or [],
            reason=reason,
            scheduled_for=scheduled_for,
            status=DeletionStatus.PENDING
        )
        
        # Store in DynamoDB
        if self.deletion_table:
            try:
                self.deletion_table.put_item(Item=json.loads(deletion_request.json()))
                logger.info(f"Created deletion request {request_id} for farmer {farmer_id}")
            except ClientError as e:
                logger.error(f"Failed to store deletion request: {e}")
        
        return deletion_request
    
    def cancel_deletion_request(
        self,
        request_id: str,
        farmer_id: str
    ) -> Optional[DeletionRequest]:
        """
        Cancel a pending deletion request.
        
        Args:
            request_id: Deletion request ID
            farmer_id: Farmer ID (for verification)
            
        Returns:
            Updated deletion request or None if not found
        """
        if not self.deletion_table:
            logger.error("Deletion table not available")
            return None
        
        try:
            # Get existing request
            response = self.deletion_table.get_item(Key={"request_id": request_id})
            
            if "Item" not in response:
                logger.warning(f"Deletion request {request_id} not found")
                return None
            
            item = response["Item"]
            
            # Verify farmer_id matches
            if item.get("farmer_id") != farmer_id:
                logger.warning(f"Farmer ID mismatch for deletion request {request_id}")
                return None
            
            # Check if request can be cancelled
            if item.get("status") not in [DeletionStatus.PENDING.value, DeletionStatus.IN_PROGRESS.value]:
                logger.warning(f"Cannot cancel deletion request in status {item.get('status')}")
                return None
            
            # Update status
            self.deletion_table.update_item(
                Key={"request_id": request_id},
                UpdateExpression="SET #status = :status",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": DeletionStatus.CANCELLED.value}
            )
            
            logger.info(f"Cancelled deletion request {request_id}")
            
            item["status"] = DeletionStatus.CANCELLED.value
            return DeletionRequest(**item)
        
        except ClientError as e:
            logger.error(f"Failed to cancel deletion request: {e}")
            return None
    
    def _delete_from_dynamodb(
        self,
        table_name: str,
        farmer_id: str,
        partition_key: str = "farmer_id"
    ) -> int:
        """
        Delete all items for a farmer from a DynamoDB table.
        
        Args:
            table_name: Name of DynamoDB table
            farmer_id: Farmer ID
            partition_key: Name of partition key field
            
        Returns:
            Number of items deleted
        """
        try:
            table = self.dynamodb.Table(table_name)
            
            # Query all items for farmer
            response = table.query(
                KeyConditionExpression=f"{partition_key} = :farmer_id",
                ExpressionAttributeValues={":farmer_id": farmer_id}
            )
            
            items = response.get("Items", [])
            deleted_count = 0
            
            # Delete each item
            for item in items:
                # Get primary key
                key = {partition_key: item[partition_key]}
                
                # Add sort key if present
                if "sort_key" in item:
                    key["sort_key"] = item["sort_key"]
                elif "timestamp" in item:
                    key["timestamp"] = item["timestamp"]
                elif "recommendation_id" in item:
                    key["recommendation_id"] = item["recommendation_id"]
                
                table.delete_item(Key=key)
                deleted_count += 1
            
            logger.info(f"Deleted {deleted_count} items from {table_name} for farmer {farmer_id}")
            return deleted_count
        
        except ClientError as e:
            logger.error(f"Failed to delete from {table_name}: {e}")
            return 0
    
    def _delete_from_s3(
        self,
        bucket_name: str,
        farmer_id: str,
        prefix: Optional[str] = None
    ) -> int:
        """
        Delete all objects for a farmer from an S3 bucket.
        
        Args:
            bucket_name: Name of S3 bucket
            farmer_id: Farmer ID
            prefix: Optional prefix for objects
            
        Returns:
            Number of objects deleted
        """
        try:
            # List all objects with farmer_id prefix
            object_prefix = f"{prefix}/{farmer_id}" if prefix else farmer_id
            
            response = self.s3.list_objects_v2(
                Bucket=bucket_name,
                Prefix=object_prefix
            )
            
            objects = response.get("Contents", [])
            deleted_count = 0
            
            # Delete each object
            for obj in objects:
                self.s3.delete_object(
                    Bucket=bucket_name,
                    Key=obj["Key"]
                )
                deleted_count += 1
            
            logger.info(f"Deleted {deleted_count} objects from s3://{bucket_name}/{object_prefix}")
            return deleted_count
        
        except ClientError as e:
            logger.error(f"Failed to delete from S3 bucket {bucket_name}: {e}")
            return 0
    
    def execute_deletion(
        self,
        request_id: str
    ) -> Optional[DeletionRequest]:
        """
        Execute a scheduled deletion request.
        
        Args:
            request_id: Deletion request ID
            
        Returns:
            Updated deletion request or None if not found
        """
        if not self.deletion_table:
            logger.error("Deletion table not available")
            return None
        
        try:
            # Get deletion request
            response = self.deletion_table.get_item(Key={"request_id": request_id})
            
            if "Item" not in response:
                logger.warning(f"Deletion request {request_id} not found")
                return None
            
            item = response["Item"]
            deletion_request = DeletionRequest(**item)
            
            # Check if request is ready for execution
            if deletion_request.status != DeletionStatus.PENDING:
                logger.warning(f"Deletion request {request_id} is not pending")
                return deletion_request
            
            if deletion_request.scheduled_for > datetime.utcnow():
                logger.warning(f"Deletion request {request_id} is not yet scheduled")
                return deletion_request
            
            # Update status to in_progress
            self.deletion_table.update_item(
                Key={"request_id": request_id},
                UpdateExpression="SET #status = :status",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": DeletionStatus.IN_PROGRESS.value}
            )
            
            farmer_id = deletion_request.farmer_id
            deleted_items = {}
            
            # Determine what to delete based on scope
            categories_to_delete = []
            
            if deletion_request.scope == DeletionScope.ALL_DATA:
                categories_to_delete = list(self.data_locations.keys())
            elif deletion_request.scope == DeletionScope.SPECIFIC_CATEGORIES:
                categories_to_delete = deletion_request.data_categories
            elif deletion_request.scope == DeletionScope.PROFILE_ONLY:
                categories_to_delete = ["profile"]
            elif deletion_request.scope == DeletionScope.RECOMMENDATIONS:
                categories_to_delete = ["recommendations"]
            elif deletion_request.scope == DeletionScope.CONVERSATIONS:
                categories_to_delete = ["conversations"]
            
            # Execute deletion for each category
            for category in categories_to_delete:
                if category not in self.data_locations:
                    logger.warning(f"Unknown data category: {category}")
                    continue
                
                location = self.data_locations[category]
                count = 0
                
                # Delete from DynamoDB
                if location["dynamodb_table"]:
                    count += self._delete_from_dynamodb(
                        location["dynamodb_table"],
                        farmer_id
                    )
                
                # Delete from S3
                if location["s3_bucket"]:
                    count += self._delete_from_s3(
                        location["s3_bucket"],
                        farmer_id
                    )
                
                deleted_items[category] = count
            
            # Update deletion request with results
            now = datetime.utcnow()
            self.deletion_table.update_item(
                Key={"request_id": request_id},
                UpdateExpression="SET #status = :status, completed_at = :completed, deleted_items = :items",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": DeletionStatus.COMPLETED.value,
                    ":completed": now.isoformat(),
                    ":items": deleted_items
                }
            )
            
            logger.info(f"Completed deletion request {request_id} for farmer {farmer_id}")
            
            deletion_request.status = DeletionStatus.COMPLETED
            deletion_request.completed_at = now
            deletion_request.deleted_items = deleted_items
            
            return deletion_request
        
        except Exception as e:
            logger.error(f"Failed to execute deletion request {request_id}: {e}")
            
            # Update status to failed
            if self.deletion_table:
                self.deletion_table.update_item(
                    Key={"request_id": request_id},
                    UpdateExpression="SET #status = :status, error_message = :error",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":status": DeletionStatus.FAILED.value,
                        ":error": str(e)
                    }
                )
            
            return None
    
    def get_deletion_requests(
        self,
        farmer_id: str,
        status: Optional[DeletionStatus] = None
    ) -> List[DeletionRequest]:
        """
        Get deletion requests for a farmer.
        
        Args:
            farmer_id: Farmer ID
            status: Filter by status
            
        Returns:
            List of deletion requests
        """
        if not self.deletion_table:
            logger.error("Deletion table not available")
            return []
        
        try:
            # Query by farmer_id
            query_params = {
                "IndexName": "farmer_id-index",
                "KeyConditionExpression": "farmer_id = :farmer_id",
                "ExpressionAttributeValues": {":farmer_id": farmer_id}
            }
            
            if status:
                query_params["FilterExpression"] = "#status = :status"
                query_params["ExpressionAttributeNames"] = {"#status": "status"}
                query_params["ExpressionAttributeValues"][":status"] = status.value
            
            response = self.deletion_table.query(**query_params)
            
            requests = []
            for item in response.get("Items", []):
                try:
                    requests.append(DeletionRequest(**item))
                except Exception as e:
                    logger.warning(f"Failed to parse deletion request: {e}")
            
            return requests
        
        except ClientError as e:
            logger.error(f"Failed to query deletion requests: {e}")
            return []
    
    def process_scheduled_deletions(self) -> int:
        """
        Process all scheduled deletions that are due.
        
        This method should be called periodically (e.g., daily) to execute
        scheduled deletions.
        
        Returns:
            Number of deletions processed
        """
        if not self.deletion_table:
            logger.error("Deletion table not available")
            return 0
        
        try:
            # Scan for pending deletions that are due
            now = datetime.utcnow()
            
            response = self.deletion_table.scan(
                FilterExpression="#status = :status AND scheduled_for <= :now",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": DeletionStatus.PENDING.value,
                    ":now": now.isoformat()
                }
            )
            
            processed = 0
            for item in response.get("Items", []):
                request_id = item.get("request_id")
                if request_id:
                    result = self.execute_deletion(request_id)
                    if result and result.status == DeletionStatus.COMPLETED:
                        processed += 1
            
            logger.info(f"Processed {processed} scheduled deletions")
            return processed
        
        except ClientError as e:
            logger.error(f"Failed to process scheduled deletions: {e}")
            return 0


# Global data deletion manager instance
_deletion_manager = None


def get_deletion_manager() -> DataDeletionManager:
    """Get global data deletion manager instance."""
    global _deletion_manager
    if _deletion_manager is None:
        _deletion_manager = DataDeletionManager()
    return _deletion_manager
