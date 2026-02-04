"""
DynamoDB client and connection management for KrishiMitra platform.

This module provides a centralized DynamoDB client with connection pooling,
retry logic, and error handling for all database operations.
"""

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError
from typing import Dict, List, Any, Optional, Union
import logging
import time
from decimal import Decimal
import json

from ..config import get_settings

logger = logging.getLogger(__name__)


class DynamoDBClient:
    """
    Centralized DynamoDB client with connection management and utilities.
    
    Provides methods for CRUD operations, batch operations, and query utilities
    with built-in retry logic and error handling.
    """
    
    def __init__(self, region_name: Optional[str] = None):
        """Initialize DynamoDB client with configuration."""
        settings = get_settings()
        
        # Configure boto3 client with retry and connection settings
        config = Config(
            region_name=region_name or settings.aws_region,
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            },
            max_pool_connections=50,
            connect_timeout=10,
            read_timeout=30
        )
        
        self.dynamodb = boto3.client('dynamodb', config=config)
        self.resource = boto3.resource('dynamodb', config=config)
        
        # Table name mappings
        self.table_names = {
            'farmer_profiles': 'FarmerProfiles',
            'agricultural_intelligence': 'AgriculturalIntelligence', 
            'recommendations': 'Recommendations',
            'conversations': 'Conversations',
            'sensor_readings': 'SensorReadings'
        }
        
        logger.info(f"DynamoDB client initialized for region: {config.region_name}")
    
    def get_table(self, table_key: str):
        """Get DynamoDB table resource by key."""
        if table_key not in self.table_names:
            raise ValueError(f"Unknown table key: {table_key}")
        
        table_name = self.table_names[table_key]
        return self.resource.Table(table_name)
    
    def put_item(self, table_key: str, item: Dict[str, Any]) -> bool:
        """Put an item into DynamoDB table."""
        try:
            table = self.get_table(table_key)
            
            # Convert floats to Decimal for DynamoDB compatibility
            item = self._convert_floats_to_decimal(item)
            
            table.put_item(Item=item)
            logger.debug(f"Successfully put item in {table_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to put item in {table_key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error putting item in {table_key}: {e}")
            return False
    
    def get_item(self, table_key: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get an item from DynamoDB table."""
        try:
            table = self.get_table(table_key)
            
            response = table.get_item(Key=key)
            item = response.get('Item')
            
            if item:
                # Convert Decimal back to float
                item = self._convert_decimal_to_float(item)
                logger.debug(f"Successfully retrieved item from {table_key}")
                return item
            else:
                logger.debug(f"Item not found in {table_key}")
                return None
                
        except ClientError as e:
            logger.error(f"Failed to get item from {table_key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting item from {table_key}: {e}")
            return None
    
    def update_item(self, table_key: str, key: Dict[str, Any], 
                   update_expression: str, expression_attribute_values: Dict[str, Any],
                   expression_attribute_names: Optional[Dict[str, str]] = None) -> bool:
        """Update an item in DynamoDB table."""
        try:
            table = self.get_table(table_key)
            
            # Convert floats to Decimal
            expression_attribute_values = self._convert_floats_to_decimal(expression_attribute_values)
            
            update_params = {
                'Key': key,
                'UpdateExpression': update_expression,
                'ExpressionAttributeValues': expression_attribute_values,
                'ReturnValues': 'UPDATED_NEW'
            }
            
            if expression_attribute_names:
                update_params['ExpressionAttributeNames'] = expression_attribute_names
            
            table.update_item(**update_params)
            logger.debug(f"Successfully updated item in {table_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to update item in {table_key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error updating item in {table_key}: {e}")
            return False
    
    def delete_item(self, table_key: str, key: Dict[str, Any]) -> bool:
        """Delete an item from DynamoDB table."""
        try:
            table = self.get_table(table_key)
            
            table.delete_item(Key=key)
            logger.debug(f"Successfully deleted item from {table_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete item from {table_key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting item from {table_key}: {e}")
            return False
    
    def query_items(self, table_key: str, key_condition_expression: str,
                   expression_attribute_values: Dict[str, Any],
                   expression_attribute_names: Optional[Dict[str, str]] = None,
                   index_name: Optional[str] = None,
                   limit: Optional[int] = None,
                   scan_index_forward: bool = True) -> List[Dict[str, Any]]:
        """Query items from DynamoDB table."""
        try:
            table = self.get_table(table_key)
            
            # Convert floats to Decimal
            expression_attribute_values = self._convert_floats_to_decimal(expression_attribute_values)
            
            query_params = {
                'KeyConditionExpression': key_condition_expression,
                'ExpressionAttributeValues': expression_attribute_values,
                'ScanIndexForward': scan_index_forward
            }
            
            if expression_attribute_names:
                query_params['ExpressionAttributeNames'] = expression_attribute_names
            if index_name:
                query_params['IndexName'] = index_name
            if limit:
                query_params['Limit'] = limit
            
            response = table.query(**query_params)
            items = response.get('Items', [])
            
            # Convert Decimal back to float
            items = [self._convert_decimal_to_float(item) for item in items]
            
            logger.debug(f"Successfully queried {len(items)} items from {table_key}")
            return items
            
        except ClientError as e:
            logger.error(f"Failed to query items from {table_key}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error querying items from {table_key}: {e}")
            return []
    
    def scan_items(self, table_key: str, 
                  filter_expression: Optional[str] = None,
                  expression_attribute_values: Optional[Dict[str, Any]] = None,
                  expression_attribute_names: Optional[Dict[str, str]] = None,
                  limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Scan items from DynamoDB table."""
        try:
            table = self.get_table(table_key)
            
            scan_params = {}
            
            if filter_expression:
                scan_params['FilterExpression'] = filter_expression
            if expression_attribute_values:
                scan_params['ExpressionAttributeValues'] = self._convert_floats_to_decimal(expression_attribute_values)
            if expression_attribute_names:
                scan_params['ExpressionAttributeNames'] = expression_attribute_names
            if limit:
                scan_params['Limit'] = limit
            
            response = table.scan(**scan_params)
            items = response.get('Items', [])
            
            # Convert Decimal back to float
            items = [self._convert_decimal_to_float(item) for item in items]
            
            logger.debug(f"Successfully scanned {len(items)} items from {table_key}")
            return items
            
        except ClientError as e:
            logger.error(f"Failed to scan items from {table_key}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error scanning items from {table_key}: {e}")
            return []
    
    def batch_write_items(self, table_key: str, items: List[Dict[str, Any]]) -> bool:
        """Batch write items to DynamoDB table."""
        try:
            table = self.get_table(table_key)
            table_name = self.table_names[table_key]
            
            # DynamoDB batch write limit is 25 items
            batch_size = 25
            success_count = 0
            
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                
                # Convert floats to Decimal
                batch = [self._convert_floats_to_decimal(item) for item in batch]
                
                # Prepare batch write request
                request_items = {
                    table_name: [
                        {'PutRequest': {'Item': item}} for item in batch
                    ]
                }
                
                response = self.dynamodb.batch_write_item(RequestItems=request_items)
                
                # Handle unprocessed items
                unprocessed = response.get('UnprocessedItems', {})
                retry_count = 0
                max_retries = 3
                
                while unprocessed and retry_count < max_retries:
                    time.sleep(2 ** retry_count)  # Exponential backoff
                    response = self.dynamodb.batch_write_item(RequestItems=unprocessed)
                    unprocessed = response.get('UnprocessedItems', {})
                    retry_count += 1
                
                if not unprocessed:
                    success_count += len(batch)
                else:
                    logger.warning(f"Failed to process {len(unprocessed.get(table_name, []))} items in batch")
            
            logger.info(f"Successfully batch wrote {success_count}/{len(items)} items to {table_key}")
            return success_count == len(items)
            
        except ClientError as e:
            logger.error(f"Failed to batch write items to {table_key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error batch writing items to {table_key}: {e}")
            return False
    
    def _convert_floats_to_decimal(self, obj: Any) -> Any:
        """Convert float values to Decimal for DynamoDB compatibility."""
        if isinstance(obj, dict):
            return {k: self._convert_floats_to_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_floats_to_decimal(item) for item in obj]
        elif isinstance(obj, float):
            return Decimal(str(obj))
        return obj
    
    def _convert_decimal_to_float(self, obj: Any) -> Any:
        """Convert Decimal values back to float."""
        if isinstance(obj, dict):
            return {k: self._convert_decimal_to_float(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_decimal_to_float(item) for item in obj]
        elif isinstance(obj, Decimal):
            return float(obj)
        return obj
    
    def health_check(self) -> bool:
        """Perform health check on DynamoDB connection."""
        try:
            # Try to list tables to verify connection
            response = self.dynamodb.list_tables(Limit=1)
            logger.debug("DynamoDB health check passed")
            return True
        except Exception as e:
            logger.error(f"DynamoDB health check failed: {e}")
            return False