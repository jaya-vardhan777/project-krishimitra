"""
Database utilities and connection management for KrishiMitra platform.

This module provides utilities for working with DynamoDB, including
connection management, table operations, and data serialization.
"""

import json
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError, BotoCoreError
from pydantic import BaseModel

from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

T = TypeVar('T', bound=BaseModel)


class DynamoDBError(Exception):
    """Base exception for DynamoDB operations."""
    pass


class ItemNotFoundError(DynamoDBError):
    """Exception raised when an item is not found."""
    pass


class ValidationError(DynamoDBError):
    """Exception raised when data validation fails."""
    pass


class DynamoDBSerializer:
    """Utility class for serializing/deserializing data for DynamoDB."""
    
    @staticmethod
    def serialize_value(value: Any) -> Dict[str, Any]:
        """Serialize a Python value to DynamoDB format."""
        if value is None:
            return {"NULL": True}
        elif isinstance(value, bool):
            return {"BOOL": value}
        elif isinstance(value, (int, float, Decimal)):
            return {"N": str(value)}
        elif isinstance(value, str):
            return {"S": value}
        elif isinstance(value, bytes):
            return {"B": value}
        elif isinstance(value, (list, tuple)):
            return {"L": [DynamoDBSerializer.serialize_value(item) for item in value]}
        elif isinstance(value, dict):
            return {"M": {k: DynamoDBSerializer.serialize_value(v) for k, v in value.items()}}
        elif isinstance(value, set):
            if all(isinstance(item, str) for item in value):
                return {"SS": list(value)}
            elif all(isinstance(item, (int, float, Decimal)) for item in value):
                return {"NS": [str(item) for item in value]}
            elif all(isinstance(item, bytes) for item in value):
                return {"BS": list(value)}
            else:
                raise ValueError(f"Unsupported set type: {type(next(iter(value)))}")
        elif isinstance(value, datetime):
            return {"S": value.isoformat()}
        elif isinstance(value, date):
            return {"S": value.isoformat()}
        elif isinstance(value, BaseModel):
            return DynamoDBSerializer.serialize_value(value.model_dump())
        else:
            # Try to serialize as JSON string
            try:
                return {"S": json.dumps(value, default=str)}
            except (TypeError, ValueError):
                raise ValueError(f"Cannot serialize value of type {type(value)}")
    
    @staticmethod
    def deserialize_value(value: Dict[str, Any]) -> Any:
        """Deserialize a DynamoDB value to Python format."""
        if "NULL" in value:
            return None
        elif "BOOL" in value:
            return value["BOOL"]
        elif "N" in value:
            num_str = value["N"]
            try:
                return int(num_str)
            except ValueError:
                return float(num_str)
        elif "S" in value:
            return value["S"]
        elif "B" in value:
            return value["B"]
        elif "L" in value:
            return [DynamoDBSerializer.deserialize_value(item) for item in value["L"]]
        elif "M" in value:
            return {k: DynamoDBSerializer.deserialize_value(v) for k, v in value["M"].items()}
        elif "SS" in value:
            return set(value["SS"])
        elif "NS" in value:
            return {float(item) for item in value["NS"]}
        elif "BS" in value:
            return set(value["BS"])
        else:
            raise ValueError(f"Unknown DynamoDB type: {value}")
    
    @staticmethod
    def serialize_item(item: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize a complete item for DynamoDB."""
        return {k: DynamoDBSerializer.serialize_value(v) for k, v in item.items()}
    
    @staticmethod
    def deserialize_item(item: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize a complete item from DynamoDB."""
        return {k: DynamoDBSerializer.deserialize_value(v) for k, v in item.items()}


class DynamoDBClient:
    """DynamoDB client wrapper with utility methods."""
    
    def __init__(self):
        """Initialize the DynamoDB client."""
        self.client = boto3.client('dynamodb', region_name=settings.aws_region)
        self.resource = boto3.resource('dynamodb', region_name=settings.aws_region)
    
    def get_table(self, table_name: str):
        """Get a DynamoDB table resource."""
        return self.resource.Table(table_name)
    
    def put_item(
        self,
        table_name: str,
        item: Dict[str, Any],
        condition_expression: Optional[str] = None
    ) -> bool:
        """Put an item into a DynamoDB table."""
        try:
            serialized_item = DynamoDBSerializer.serialize_item(item)
            
            put_params = {
                'TableName': table_name,
                'Item': serialized_item
            }
            
            if condition_expression:
                put_params['ConditionExpression'] = condition_expression
            
            self.client.put_item(**put_params)
            logger.debug(f"Successfully put item in table {table_name}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ConditionalCheckFailedException':
                logger.warning(f"Conditional check failed for table {table_name}")
                return False
            else:
                logger.error(f"Error putting item in table {table_name}: {e}")
                raise DynamoDBError(f"Failed to put item: {e}")
        except Exception as e:
            logger.error(f"Unexpected error putting item in table {table_name}: {e}")
            raise DynamoDBError(f"Unexpected error: {e}")
    
    def get_item(
        self,
        table_name: str,
        key: Dict[str, Any],
        consistent_read: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get an item from a DynamoDB table."""
        try:
            serialized_key = DynamoDBSerializer.serialize_item(key)
            
            response = self.client.get_item(
                TableName=table_name,
                Key=serialized_key,
                ConsistentRead=consistent_read
            )
            
            if 'Item' in response:
                return DynamoDBSerializer.deserialize_item(response['Item'])
            else:
                return None
                
        except ClientError as e:
            logger.error(f"Error getting item from table {table_name}: {e}")
            raise DynamoDBError(f"Failed to get item: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting item from table {table_name}: {e}")
            raise DynamoDBError(f"Unexpected error: {e}")
    
    def update_item(
        self,
        table_name: str,
        key: Dict[str, Any],
        update_expression: str,
        expression_attribute_values: Optional[Dict[str, Any]] = None,
        expression_attribute_names: Optional[Dict[str, str]] = None,
        condition_expression: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an item in a DynamoDB table."""
        try:
            serialized_key = DynamoDBSerializer.serialize_item(key)
            
            update_params = {
                'TableName': table_name,
                'Key': serialized_key,
                'UpdateExpression': update_expression,
                'ReturnValues': 'ALL_NEW'
            }
            
            if expression_attribute_values:
                update_params['ExpressionAttributeValues'] = DynamoDBSerializer.serialize_item(
                    expression_attribute_values
                )
            
            if expression_attribute_names:
                update_params['ExpressionAttributeNames'] = expression_attribute_names
            
            if condition_expression:
                update_params['ConditionExpression'] = condition_expression
            
            response = self.client.update_item(**update_params)
            
            return DynamoDBSerializer.deserialize_item(response['Attributes'])
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ConditionalCheckFailedException':
                logger.warning(f"Conditional check failed for update in table {table_name}")
                raise ValidationError("Conditional check failed")
            else:
                logger.error(f"Error updating item in table {table_name}: {e}")
                raise DynamoDBError(f"Failed to update item: {e}")
        except Exception as e:
            logger.error(f"Unexpected error updating item in table {table_name}: {e}")
            raise DynamoDBError(f"Unexpected error: {e}")
    
    def delete_item(
        self,
        table_name: str,
        key: Dict[str, Any],
        condition_expression: Optional[str] = None
    ) -> bool:
        """Delete an item from a DynamoDB table."""
        try:
            serialized_key = DynamoDBSerializer.serialize_item(key)
            
            delete_params = {
                'TableName': table_name,
                'Key': serialized_key
            }
            
            if condition_expression:
                delete_params['ConditionExpression'] = condition_expression
            
            self.client.delete_item(**delete_params)
            logger.debug(f"Successfully deleted item from table {table_name}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ConditionalCheckFailedException':
                logger.warning(f"Conditional check failed for delete in table {table_name}")
                return False
            else:
                logger.error(f"Error deleting item from table {table_name}: {e}")
                raise DynamoDBError(f"Failed to delete item: {e}")
        except Exception as e:
            logger.error(f"Unexpected error deleting item from table {table_name}: {e}")
            raise DynamoDBError(f"Unexpected error: {e}")
    
    def query(
        self,
        table_name: str,
        key_condition_expression: str,
        expression_attribute_values: Optional[Dict[str, Any]] = None,
        expression_attribute_names: Optional[Dict[str, str]] = None,
        filter_expression: Optional[str] = None,
        index_name: Optional[str] = None,
        limit: Optional[int] = None,
        scan_index_forward: bool = True
    ) -> List[Dict[str, Any]]:
        """Query items from a DynamoDB table."""
        try:
            query_params = {
                'TableName': table_name,
                'KeyConditionExpression': key_condition_expression,
                'ScanIndexForward': scan_index_forward
            }
            
            if expression_attribute_values:
                query_params['ExpressionAttributeValues'] = DynamoDBSerializer.serialize_item(
                    expression_attribute_values
                )
            
            if expression_attribute_names:
                query_params['ExpressionAttributeNames'] = expression_attribute_names
            
            if filter_expression:
                query_params['FilterExpression'] = filter_expression
            
            if index_name:
                query_params['IndexName'] = index_name
            
            if limit:
                query_params['Limit'] = limit
            
            response = self.client.query(**query_params)
            
            items = []
            for item in response.get('Items', []):
                items.append(DynamoDBSerializer.deserialize_item(item))
            
            return items
            
        except ClientError as e:
            logger.error(f"Error querying table {table_name}: {e}")
            raise DynamoDBError(f"Failed to query: {e}")
        except Exception as e:
            logger.error(f"Unexpected error querying table {table_name}: {e}")
            raise DynamoDBError(f"Unexpected error: {e}")
    
    def scan(
        self,
        table_name: str,
        filter_expression: Optional[str] = None,
        expression_attribute_values: Optional[Dict[str, Any]] = None,
        expression_attribute_names: Optional[Dict[str, str]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Scan items from a DynamoDB table."""
        try:
            scan_params = {
                'TableName': table_name
            }
            
            if filter_expression:
                scan_params['FilterExpression'] = filter_expression
            
            if expression_attribute_values:
                scan_params['ExpressionAttributeValues'] = DynamoDBSerializer.serialize_item(
                    expression_attribute_values
                )
            
            if expression_attribute_names:
                scan_params['ExpressionAttributeNames'] = expression_attribute_names
            
            if limit:
                scan_params['Limit'] = limit
            
            response = self.client.scan(**scan_params)
            
            items = []
            for item in response.get('Items', []):
                items.append(DynamoDBSerializer.deserialize_item(item))
            
            return items
            
        except ClientError as e:
            logger.error(f"Error scanning table {table_name}: {e}")
            raise DynamoDBError(f"Failed to scan: {e}")
        except Exception as e:
            logger.error(f"Unexpected error scanning table {table_name}: {e}")
            raise DynamoDBError(f"Unexpected error: {e}")


class BaseRepository:
    """Base repository class for DynamoDB operations."""
    
    def __init__(self, table_name: str, model_class: Type[T]):
        """Initialize the repository."""
        self.table_name = table_name
        self.model_class = model_class
        self.db = DynamoDBClient()
    
    def create(self, item: T) -> T:
        """Create a new item."""
        item_dict = item.model_dump()
        
        # Add timestamps if not present
        if hasattr(item, 'created_at') and not item_dict.get('created_at'):
            item_dict['created_at'] = datetime.utcnow().isoformat()
        if hasattr(item, 'updated_at'):
            item_dict['updated_at'] = datetime.utcnow().isoformat()
        
        success = self.db.put_item(
            self.table_name,
            item_dict,
            condition_expression="attribute_not_exists(id)"
        )
        
        if not success:
            raise ValidationError("Item already exists")
        
        return self.model_class(**item_dict)
    
    def get_by_id(self, item_id: str) -> Optional[T]:
        """Get an item by ID."""
        item_dict = self.db.get_item(
            self.table_name,
            {'id': item_id}
        )
        
        if item_dict:
            return self.model_class(**item_dict)
        return None
    
    def update(self, item_id: str, updates: Dict[str, Any]) -> T:
        """Update an item."""
        # Add updated timestamp
        updates['updated_at'] = datetime.utcnow().isoformat()
        
        # Build update expression
        update_expression_parts = []
        expression_attribute_values = {}
        expression_attribute_names = {}
        
        for key, value in updates.items():
            attr_name = f"#{key}"
            attr_value = f":{key}"
            
            update_expression_parts.append(f"{attr_name} = {attr_value}")
            expression_attribute_names[attr_name] = key
            expression_attribute_values[attr_value] = value
        
        update_expression = "SET " + ", ".join(update_expression_parts)
        
        updated_item = self.db.update_item(
            self.table_name,
            {'id': item_id},
            update_expression,
            expression_attribute_values,
            expression_attribute_names,
            condition_expression="attribute_exists(id)"
        )
        
        return self.model_class(**updated_item)
    
    def delete(self, item_id: str) -> bool:
        """Delete an item."""
        return self.db.delete_item(
            self.table_name,
            {'id': item_id},
            condition_expression="attribute_exists(id)"
        )
    
    def list_items(self, limit: Optional[int] = None) -> List[T]:
        """List all items."""
        items = self.db.scan(self.table_name, limit=limit)
        return [self.model_class(**item) for item in items]


# Global database client instance
db_client = DynamoDBClient()