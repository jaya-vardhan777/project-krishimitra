"""
DynamoDB table schemas and indexing strategies for KrishiMitra platform.

This module defines the table structures, indexes, and creation utilities
for all DynamoDB tables used in the platform.
"""

from typing import Dict, List, Any
import boto3
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


class DynamoDBSchemas:
    """DynamoDB table schemas and management utilities."""
    
    @staticmethod
    def get_farmer_profiles_table_schema() -> Dict[str, Any]:
        """Get FarmerProfiles table schema definition."""
        return {
            'TableName': 'FarmerProfiles',
            'KeySchema': [
                {
                    'AttributeName': 'farmer_id',
                    'KeyType': 'HASH'  # Partition key
                }
            ],
            'AttributeDefinitions': [
                {
                    'AttributeName': 'farmer_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'phone_number',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'state',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'district',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'created_at',
                    'AttributeType': 'S'
                }
            ],
            'GlobalSecondaryIndexes': [
                {
                    'IndexName': 'PhoneNumberIndex',
                    'KeySchema': [
                        {
                            'AttributeName': 'phone_number',
                            'KeyType': 'HASH'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    },
                    'BillingMode': 'PAY_PER_REQUEST'
                },
                {
                    'IndexName': 'LocationIndex',
                    'KeySchema': [
                        {
                            'AttributeName': 'state',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'district',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'KEYS_ONLY'
                    },
                    'BillingMode': 'PAY_PER_REQUEST'
                },
                {
                    'IndexName': 'CreatedAtIndex',
                    'KeySchema': [
                        {
                            'AttributeName': 'created_at',
                            'KeyType': 'HASH'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'KEYS_ONLY'
                    },
                    'BillingMode': 'PAY_PER_REQUEST'
                }
            ],
            'BillingMode': 'PAY_PER_REQUEST',
            'StreamSpecification': {
                'StreamEnabled': True,
                'StreamViewType': 'NEW_AND_OLD_IMAGES'
            },
            'SSESpecification': {
                'Enabled': True,
                'SSEType': 'KMS'
            },
            'Tags': [
                {
                    'Key': 'Environment',
                    'Value': 'production'
                },
                {
                    'Key': 'Application',
                    'Value': 'KrishiMitra'
                },
                {
                    'Key': 'DataType',
                    'Value': 'FarmerProfiles'
                }
            ]
        }
    
    @staticmethod
    def get_agricultural_intelligence_table_schema() -> Dict[str, Any]:
        """Get AgriculturalIntelligence table schema definition."""
        return {
            'TableName': 'AgriculturalIntelligence',
            'KeySchema': [
                {
                    'AttributeName': 'data_id',
                    'KeyType': 'HASH'  # Partition key
                }
            ],
            'AttributeDefinitions': [
                {
                    'AttributeName': 'data_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'location_hash',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'timestamp',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'data_type',
                    'AttributeType': 'S'
                }
            ],
            'GlobalSecondaryIndexes': [
                {
                    'IndexName': 'LocationTimeIndex',
                    'KeySchema': [
                        {
                            'AttributeName': 'location_hash',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'timestamp',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    },
                    'BillingMode': 'PAY_PER_REQUEST'
                },
                {
                    'IndexName': 'DataTypeIndex',
                    'KeySchema': [
                        {
                            'AttributeName': 'data_type',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'timestamp',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'KEYS_ONLY'
                    },
                    'BillingMode': 'PAY_PER_REQUEST'
                }
            ],
            'BillingMode': 'PAY_PER_REQUEST',
            'StreamSpecification': {
                'StreamEnabled': True,
                'StreamViewType': 'NEW_AND_OLD_IMAGES'
            },
            'SSESpecification': {
                'Enabled': True,
                'SSEType': 'KMS'
            },
            'TimeToLiveSpecification': {
                'AttributeName': 'ttl',
                'Enabled': True
            },
            'Tags': [
                {
                    'Key': 'Environment',
                    'Value': 'production'
                },
                {
                    'Key': 'Application',
                    'Value': 'KrishiMitra'
                },
                {
                    'Key': 'DataType',
                    'Value': 'AgriculturalIntelligence'
                }
            ]
        }
    
    @staticmethod
    def get_recommendations_table_schema() -> Dict[str, Any]:
        """Get Recommendations table schema definition."""
        return {
            'TableName': 'Recommendations',
            'KeySchema': [
                {
                    'AttributeName': 'recommendation_id',
                    'KeyType': 'HASH'  # Partition key
                }
            ],
            'AttributeDefinitions': [
                {
                    'AttributeName': 'recommendation_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'farmer_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'timestamp',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'query_type',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'is_active',
                    'AttributeType': 'S'
                }
            ],
            'GlobalSecondaryIndexes': [
                {
                    'IndexName': 'FarmerTimeIndex',
                    'KeySchema': [
                        {
                            'AttributeName': 'farmer_id',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'timestamp',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    },
                    'BillingMode': 'PAY_PER_REQUEST'
                },
                {
                    'IndexName': 'QueryTypeIndex',
                    'KeySchema': [
                        {
                            'AttributeName': 'query_type',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'timestamp',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'KEYS_ONLY'
                    },
                    'BillingMode': 'PAY_PER_REQUEST'
                },
                {
                    'IndexName': 'ActiveRecommendationsIndex',
                    'KeySchema': [
                        {
                            'AttributeName': 'is_active',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'timestamp',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'KEYS_ONLY'
                    },
                    'BillingMode': 'PAY_PER_REQUEST'
                }
            ],
            'BillingMode': 'PAY_PER_REQUEST',
            'StreamSpecification': {
                'StreamEnabled': True,
                'StreamViewType': 'NEW_AND_OLD_IMAGES'
            },
            'SSESpecification': {
                'Enabled': True,
                'SSEType': 'KMS'
            },
            'Tags': [
                {
                    'Key': 'Environment',
                    'Value': 'production'
                },
                {
                    'Key': 'Application',
                    'Value': 'KrishiMitra'
                },
                {
                    'Key': 'DataType',
                    'Value': 'Recommendations'
                }
            ]
        }
    
    @staticmethod
    def get_conversations_table_schema() -> Dict[str, Any]:
        """Get Conversations table schema definition."""
        return {
            'TableName': 'Conversations',
            'KeySchema': [
                {
                    'AttributeName': 'conversation_id',
                    'KeyType': 'HASH'  # Partition key
                },
                {
                    'AttributeName': 'message_timestamp',
                    'KeyType': 'RANGE'  # Sort key
                }
            ],
            'AttributeDefinitions': [
                {
                    'AttributeName': 'conversation_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'message_timestamp',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'farmer_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'channel',
                    'AttributeType': 'S'
                }
            ],
            'GlobalSecondaryIndexes': [
                {
                    'IndexName': 'FarmerConversationsIndex',
                    'KeySchema': [
                        {
                            'AttributeName': 'farmer_id',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'message_timestamp',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    },
                    'BillingMode': 'PAY_PER_REQUEST'
                },
                {
                    'IndexName': 'ChannelIndex',
                    'KeySchema': [
                        {
                            'AttributeName': 'channel',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'message_timestamp',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'KEYS_ONLY'
                    },
                    'BillingMode': 'PAY_PER_REQUEST'
                }
            ],
            'BillingMode': 'PAY_PER_REQUEST',
            'StreamSpecification': {
                'StreamEnabled': True,
                'StreamViewType': 'NEW_AND_OLD_IMAGES'
            },
            'SSESpecification': {
                'Enabled': True,
                'SSEType': 'KMS'
            },
            'TimeToLiveSpecification': {
                'AttributeName': 'ttl',
                'Enabled': True
            },
            'Tags': [
                {
                    'Key': 'Environment',
                    'Value': 'production'
                },
                {
                    'Key': 'Application',
                    'Value': 'KrishiMitra'
                },
                {
                    'Key': 'DataType',
                    'Value': 'Conversations'
                }
            ]
        }
    
    @staticmethod
    def get_sensor_readings_table_schema() -> Dict[str, Any]:
        """Get SensorReadings table schema definition."""
        return {
            'TableName': 'SensorReadings',
            'KeySchema': [
                {
                    'AttributeName': 'sensor_id',
                    'KeyType': 'HASH'  # Partition key
                },
                {
                    'AttributeName': 'timestamp',
                    'KeyType': 'RANGE'  # Sort key
                }
            ],
            'AttributeDefinitions': [
                {
                    'AttributeName': 'sensor_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'timestamp',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'farmer_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'sensor_type',
                    'AttributeType': 'S'
                }
            ],
            'GlobalSecondaryIndexes': [
                {
                    'IndexName': 'FarmerSensorIndex',
                    'KeySchema': [
                        {
                            'AttributeName': 'farmer_id',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'timestamp',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    },
                    'BillingMode': 'PAY_PER_REQUEST'
                },
                {
                    'IndexName': 'SensorTypeIndex',
                    'KeySchema': [
                        {
                            'AttributeName': 'sensor_type',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'timestamp',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'KEYS_ONLY'
                    },
                    'BillingMode': 'PAY_PER_REQUEST'
                }
            ],
            'BillingMode': 'PAY_PER_REQUEST',
            'StreamSpecification': {
                'StreamEnabled': True,
                'StreamViewType': 'NEW_AND_OLD_IMAGES'
            },
            'SSESpecification': {
                'Enabled': True,
                'SSEType': 'KMS'
            },
            'TimeToLiveSpecification': {
                'AttributeName': 'ttl',
                'Enabled': True
            },
            'Tags': [
                {
                    'Key': 'Environment',
                    'Value': 'production'
                },
                {
                    'Key': 'Application',
                    'Value': 'KrishiMitra'
                },
                {
                    'Key': 'DataType',
                    'Value': 'SensorReadings'
                }
            ]
        }
    
    @classmethod
    def get_all_table_schemas(cls) -> List[Dict[str, Any]]:
        """Get all table schemas for batch creation."""
        return [
            cls.get_farmer_profiles_table_schema(),
            cls.get_agricultural_intelligence_table_schema(),
            cls.get_recommendations_table_schema(),
            cls.get_conversations_table_schema(),
            cls.get_sensor_readings_table_schema()
        ]
    
    @staticmethod
    def create_table(dynamodb_client, table_schema: Dict[str, Any]) -> bool:
        """Create a single DynamoDB table."""
        try:
            table_name = table_schema['TableName']
            logger.info(f"Creating DynamoDB table: {table_name}")
            
            # Check if table already exists
            try:
                dynamodb_client.describe_table(TableName=table_name)
                logger.info(f"Table {table_name} already exists")
                return True
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceNotFoundException':
                    raise
            
            # Create the table
            response = dynamodb_client.create_table(**table_schema)
            
            # Wait for table to be created
            waiter = dynamodb_client.get_waiter('table_exists')
            waiter.wait(
                TableName=table_name,
                WaiterConfig={
                    'Delay': 5,
                    'MaxAttempts': 20
                }
            )
            
            logger.info(f"Successfully created table: {table_name}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to create table {table_schema['TableName']}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error creating table {table_schema['TableName']}: {e}")
            return False
    
    @classmethod
    def create_all_tables(cls, dynamodb_client) -> bool:
        """Create all DynamoDB tables."""
        schemas = cls.get_all_table_schemas()
        success_count = 0
        
        for schema in schemas:
            if cls.create_table(dynamodb_client, schema):
                success_count += 1
        
        logger.info(f"Successfully created {success_count}/{len(schemas)} tables")
        return success_count == len(schemas)