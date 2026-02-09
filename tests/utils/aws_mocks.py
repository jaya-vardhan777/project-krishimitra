"""
AWS Service Mocking Utilities using Moto.

This module provides utilities for mocking AWS services in tests using the moto library.
It includes context managers and fixtures for common AWS services used in KrishiMitra.
"""

from contextlib import contextmanager
from typing import Dict, Any, Optional
import boto3
from moto import mock_dynamodb, mock_s3, mock_iot, mock_cognitoidp, mock_bedrock


@contextmanager
def mock_aws_services():
    """
    Context manager that mocks all AWS services used by KrishiMitra.
    
    Usage:
        with mock_aws_services():
            # Your test code here
            # All AWS services will be mocked
    """
    with mock_dynamodb(), mock_s3(), mock_iot(), mock_cognitoidp():
        yield


@contextmanager
def mock_dynamodb_tables(table_configs: Optional[Dict[str, Dict[str, Any]]] = None):
    """
    Context manager that mocks DynamoDB and creates tables.
    
    Args:
        table_configs: Dictionary mapping table names to their configurations.
                      If None, creates default KrishiMitra tables.
    
    Usage:
        with mock_dynamodb_tables():
            # DynamoDB tables are now available for testing
    """
    with mock_dynamodb():
        dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
        
        if table_configs is None:
            # Create default KrishiMitra tables
            table_configs = get_default_table_configs()
        
        for table_name, config in table_configs.items():
            dynamodb.create_table(
                TableName=table_name,
                KeySchema=config['KeySchema'],
                AttributeDefinitions=config['AttributeDefinitions'],
                BillingMode='PAY_PER_REQUEST'
            )
        
        yield dynamodb


@contextmanager
def mock_s3_buckets(bucket_names: Optional[list] = None):
    """
    Context manager that mocks S3 and creates buckets.
    
    Args:
        bucket_names: List of bucket names to create.
                     If None, creates default KrishiMitra buckets.
    
    Usage:
        with mock_s3_buckets():
            # S3 buckets are now available for testing
    """
    with mock_s3():
        s3 = boto3.client('s3', region_name='ap-south-1')
        
        if bucket_names is None:
            bucket_names = [
                'test-agricultural-imagery',
                'test-weather-data',
                'test-market-data',
                'test-model-artifacts',
                'test-audio-files'
            ]
        
        for bucket_name in bucket_names:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': 'ap-south-1'}
            )
        
        yield s3


def get_default_table_configs() -> Dict[str, Dict[str, Any]]:
    """
    Get default DynamoDB table configurations for KrishiMitra.
    
    Returns:
        Dictionary mapping table names to their configurations.
    """
    return {
        'test-farmer-profiles': {
            'KeySchema': [
                {'AttributeName': 'farmerId', 'KeyType': 'HASH'}
            ],
            'AttributeDefinitions': [
                {'AttributeName': 'farmerId', 'AttributeType': 'S'}
            ]
        },
        'test-conversations': {
            'KeySchema': [
                {'AttributeName': 'conversationId', 'KeyType': 'HASH'},
                {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
            ],
            'AttributeDefinitions': [
                {'AttributeName': 'conversationId', 'AttributeType': 'S'},
                {'AttributeName': 'timestamp', 'AttributeType': 'N'}
            ]
        },
        'test-recommendations': {
            'KeySchema': [
                {'AttributeName': 'recommendationId', 'KeyType': 'HASH'}
            ],
            'AttributeDefinitions': [
                {'AttributeName': 'recommendationId', 'AttributeType': 'S'},
                {'AttributeName': 'farmerId', 'AttributeType': 'S'},
                {'AttributeName': 'timestamp', 'AttributeType': 'N'}
            ],
            'GlobalSecondaryIndexes': [
                {
                    'IndexName': 'FarmerIndex',
                    'KeySchema': [
                        {'AttributeName': 'farmerId', 'KeyType': 'HASH'},
                        {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                }
            ]
        },
        'test-sensor-readings': {
            'KeySchema': [
                {'AttributeName': 'deviceId', 'KeyType': 'HASH'},
                {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
            ],
            'AttributeDefinitions': [
                {'AttributeName': 'deviceId', 'AttributeType': 'S'},
                {'AttributeName': 'timestamp', 'AttributeType': 'N'}
            ]
        }
    }


class MockAWSEnvironment:
    """
    Class for managing a complete mock AWS environment for testing.
    
    This class provides a convenient way to set up and tear down
    a complete mock AWS environment with all necessary services.
    
    Usage:
        env = MockAWSEnvironment()
        env.setup()
        # Run tests
        env.teardown()
        
    Or use as a context manager:
        with MockAWSEnvironment() as env:
            # Run tests
    """
    
    def __init__(self):
        self.mocks = []
        self.dynamodb = None
        self.s3 = None
    
    def __enter__(self):
        self.setup()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.teardown()
    
    def setup(self):
        """Set up all mock AWS services."""
        # Start mocks
        self.dynamodb_mock = mock_dynamodb()
        self.s3_mock = mock_s3()
        self.iot_mock = mock_iot()
        self.cognito_mock = mock_cognitoidp()
        
        self.dynamodb_mock.start()
        self.s3_mock.start()
        self.iot_mock.start()
        self.cognito_mock.start()
        
        # Create resources
        self._create_dynamodb_tables()
        self._create_s3_buckets()
    
    def teardown(self):
        """Tear down all mock AWS services."""
        self.cognito_mock.stop()
        self.iot_mock.stop()
        self.s3_mock.stop()
        self.dynamodb_mock.stop()
    
    def _create_dynamodb_tables(self):
        """Create DynamoDB tables."""
        self.dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
        table_configs = get_default_table_configs()
        
        for table_name, config in table_configs.items():
            # Handle tables with GSI
            if 'GlobalSecondaryIndexes' in config:
                self.dynamodb.create_table(
                    TableName=table_name,
                    KeySchema=config['KeySchema'],
                    AttributeDefinitions=config['AttributeDefinitions'],
                    GlobalSecondaryIndexes=config['GlobalSecondaryIndexes'],
                    BillingMode='PAY_PER_REQUEST'
                )
            else:
                self.dynamodb.create_table(
                    TableName=table_name,
                    KeySchema=config['KeySchema'],
                    AttributeDefinitions=config['AttributeDefinitions'],
                    BillingMode='PAY_PER_REQUEST'
                )
    
    def _create_s3_buckets(self):
        """Create S3 buckets."""
        self.s3 = boto3.client('s3', region_name='ap-south-1')
        bucket_names = [
            'test-agricultural-imagery',
            'test-weather-data',
            'test-market-data',
            'test-model-artifacts',
            'test-audio-files'
        ]
        
        for bucket_name in bucket_names:
            self.s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': 'ap-south-1'}
            )
