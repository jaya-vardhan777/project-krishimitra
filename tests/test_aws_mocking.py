"""
Tests for AWS service mocking utilities.

This module tests the moto-based AWS service mocking utilities to ensure
they work correctly for testing KrishiMitra components.
"""

import pytest
import boto3
from tests.utils.aws_mocks import (
    mock_aws_services,
    mock_dynamodb_tables,
    mock_s3_buckets,
    MockAWSEnvironment
)


def test_mock_dynamodb_tables():
    """Test that DynamoDB tables can be mocked and created."""
    with mock_dynamodb_tables() as dynamodb:
        # List tables
        tables = list(dynamodb.tables.all())
        table_names = [table.name for table in tables]
        
        # Verify all expected tables exist
        assert 'test-farmer-profiles' in table_names
        assert 'test-conversations' in table_names
        assert 'test-recommendations' in table_names
        assert 'test-sensor-readings' in table_names
        
        # Test writing to a table
        table = dynamodb.Table('test-farmer-profiles')
        table.put_item(
            Item={
                'farmerId': 'test-farmer-1',
                'name': 'Test Farmer',
                'phone': '+919876543210'
            }
        )
        
        # Test reading from the table
        response = table.get_item(Key={'farmerId': 'test-farmer-1'})
        assert response['Item']['name'] == 'Test Farmer'


def test_mock_s3_buckets():
    """Test that S3 buckets can be mocked and created."""
    with mock_s3_buckets() as s3:
        # List buckets
        response = s3.list_buckets()
        bucket_names = [bucket['Name'] for bucket in response['Buckets']]
        
        # Verify all expected buckets exist
        assert 'test-agricultural-imagery' in bucket_names
        assert 'test-weather-data' in bucket_names
        assert 'test-market-data' in bucket_names
        assert 'test-model-artifacts' in bucket_names
        assert 'test-audio-files' in bucket_names
        
        # Test uploading to a bucket
        s3.put_object(
            Bucket='test-agricultural-imagery',
            Key='test-image.jpg',
            Body=b'test image data'
        )
        
        # Test reading from the bucket
        response = s3.get_object(
            Bucket='test-agricultural-imagery',
            Key='test-image.jpg'
        )
        assert response['Body'].read() == b'test image data'


def test_mock_aws_environment_context_manager():
    """Test MockAWSEnvironment as a context manager."""
    with MockAWSEnvironment() as env:
        # Test DynamoDB
        assert env.dynamodb is not None
        tables = list(env.dynamodb.tables.all())
        assert len(tables) == 4
        
        # Test S3
        assert env.s3 is not None
        response = env.s3.list_buckets()
        assert len(response['Buckets']) == 5


def test_mock_aws_environment_setup_teardown():
    """Test MockAWSEnvironment with explicit setup/teardown."""
    env = MockAWSEnvironment()
    env.setup()
    
    try:
        # Test that services are available
        assert env.dynamodb is not None
        assert env.s3 is not None
        
        # Test DynamoDB operation
        table = env.dynamodb.Table('test-farmer-profiles')
        table.put_item(
            Item={
                'farmerId': 'test-farmer-2',
                'name': 'Another Test Farmer'
            }
        )
        
        response = table.get_item(Key={'farmerId': 'test-farmer-2'})
        assert response['Item']['name'] == 'Another Test Farmer'
        
        # Test S3 operation
        env.s3.put_object(
            Bucket='test-weather-data',
            Key='test-weather.json',
            Body=b'{"temperature": 25}'
        )
        
        response = env.s3.get_object(
            Bucket='test-weather-data',
            Key='test-weather.json'
        )
        assert b'temperature' in response['Body'].read()
        
    finally:
        env.teardown()


def test_dynamodb_table_with_gsi():
    """Test that DynamoDB tables with Global Secondary Indexes work correctly."""
    with mock_dynamodb_tables() as dynamodb:
        table = dynamodb.Table('test-recommendations')
        
        # Put items
        table.put_item(
            Item={
                'recommendationId': 'rec-1',
                'farmerId': 'farmer-1',
                'timestamp': 1234567890,
                'recommendation': 'Plant wheat'
            }
        )
        
        table.put_item(
            Item={
                'recommendationId': 'rec-2',
                'farmerId': 'farmer-1',
                'timestamp': 1234567900,
                'recommendation': 'Irrigate field'
            }
        )
        
        # Query using GSI
        response = table.query(
            IndexName='FarmerIndex',
            KeyConditionExpression='farmerId = :farmer_id',
            ExpressionAttributeValues={
                ':farmer_id': 'farmer-1'
            }
        )
        
        assert response['Count'] == 2
        assert len(response['Items']) == 2


def test_custom_table_configs():
    """Test creating DynamoDB tables with custom configurations."""
    custom_config = {
        'custom-table': {
            'KeySchema': [
                {'AttributeName': 'id', 'KeyType': 'HASH'}
            ],
            'AttributeDefinitions': [
                {'AttributeName': 'id', 'AttributeType': 'S'}
            ]
        }
    }
    
    with mock_dynamodb_tables(custom_config) as dynamodb:
        tables = list(dynamodb.tables.all())
        table_names = [table.name for table in tables]
        
        assert 'custom-table' in table_names
        assert len(table_names) == 1


def test_custom_bucket_names():
    """Test creating S3 buckets with custom names."""
    custom_buckets = ['custom-bucket-1', 'custom-bucket-2']
    
    with mock_s3_buckets(custom_buckets) as s3:
        response = s3.list_buckets()
        bucket_names = [bucket['Name'] for bucket in response['Buckets']]
        
        assert 'custom-bucket-1' in bucket_names
        assert 'custom-bucket-2' in bucket_names
        assert len(bucket_names) == 2
