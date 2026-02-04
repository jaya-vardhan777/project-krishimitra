"""
Tests for the farmers API endpoints.

This module contains tests for farmer profile creation, retrieval, and management.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime

# Mock AWS services before importing the app
with patch('boto3.Session'), patch('boto3.client'):
    from src.krishimitra.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def sample_farmer_profile():
    """Sample farmer profile data for testing."""
    return {
        "name": "राम कुमार",
        "phone_number": "+919876543210",
        "location": {
            "state": "उत्तर प्रदेश",
            "district": "लखनऊ",
            "village": "रामनगर",
            "latitude": 26.8467,
            "longitude": 80.9462
        },
        "farm_details": {
            "total_land_area": 5.0,
            "soil_type": "दोमट मिट्टी",
            "irrigation_type": "ट्यूबवेल",
            "crops": [
                {
                    "crop_type": "गेहूं",
                    "area": 3.0
                },
                {
                    "crop_type": "चना",
                    "area": 2.0
                }
            ]
        },
        "preferences": {
            "organic_farming": True,
            "risk_tolerance": "medium",
            "preferred_language": "hi"
        }
    }


@patch('boto3.client')
def test_create_farmer_profile(mock_boto_client, client, sample_farmer_profile):
    """Test creating a new farmer profile."""
    # Mock DynamoDB client
    mock_dynamodb = MagicMock()
    mock_boto_client.return_value = mock_dynamodb
    
    # Mock successful put_item
    mock_dynamodb.put_item.return_value = {}
    
    response = client.post("/api/v1/farmers", json=sample_farmer_profile)
    
    assert response.status_code == 201
    data = response.json()
    
    assert "farmer_id" in data
    assert data["name"] == sample_farmer_profile["name"]
    assert data["phone_number"] == sample_farmer_profile["phone_number"]
    assert data["location"]["state"] == sample_farmer_profile["location"]["state"]
    assert "created_at" in data
    assert "updated_at" in data
    
    # Verify DynamoDB put_item was called
    mock_dynamodb.put_item.assert_called_once()


@patch('boto3.client')
def test_get_farmer_profile(mock_boto_client, client):
    """Test retrieving a farmer profile."""
    # Mock DynamoDB client
    mock_dynamodb = MagicMock()
    mock_boto_client.return_value = mock_dynamodb
    
    # Mock DynamoDB response
    mock_response = {
        "Item": {
            "farmerId": {"S": "test-farmer-id"},
            "name": {"S": "राम कुमार"},
            "phoneNumber": {"S": "+919876543210"},
            "location": {
                "M": {
                    "state": {"S": "उत्तर प्रदेश"},
                    "district": {"S": "लखनऊ"},
                    "village": {"S": "रामनगर"},
                    "latitude": {"N": "26.8467"},
                    "longitude": {"N": "80.9462"}
                }
            },
            "farmDetails": {
                "M": {
                    "totalLandArea": {"N": "5.0"},
                    "soilType": {"S": "दोमट मिट्टी"},
                    "irrigationType": {"S": "ट्यूबवेल"},
                    "crops": {
                        "L": [
                            {
                                "M": {
                                    "cropType": {"S": "गेहूं"},
                                    "area": {"N": "3.0"}
                                }
                            }
                        ]
                    }
                }
            },
            "preferences": {
                "M": {
                    "organicFarming": {"BOOL": True},
                    "riskTolerance": {"S": "medium"},
                    "preferredLanguage": {"S": "hi"}
                }
            },
            "createdAt": {"S": datetime.utcnow().isoformat()},
            "updatedAt": {"S": datetime.utcnow().isoformat()}
        }
    }
    
    mock_dynamodb.get_item.return_value = mock_response
    
    response = client.get("/api/v1/farmers/test-farmer-id")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["farmer_id"] == "test-farmer-id"
    assert data["name"] == "राम कुमार"
    assert data["location"]["state"] == "उत्तर प्रदेश"
    
    # Verify DynamoDB get_item was called
    mock_dynamodb.get_item.assert_called_once()


@patch('boto3.client')
def test_get_farmer_profile_not_found(mock_boto_client, client):
    """Test retrieving a non-existent farmer profile."""
    # Mock DynamoDB client
    mock_dynamodb = MagicMock()
    mock_boto_client.return_value = mock_dynamodb
    
    # Mock empty response (farmer not found)
    mock_dynamodb.get_item.return_value = {}
    
    response = client.get("/api/v1/farmers/nonexistent-id")
    
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


def test_create_farmer_profile_validation_error(client):
    """Test creating a farmer profile with invalid data."""
    invalid_profile = {
        "name": "",  # Empty name should fail validation
        "phone_number": "invalid-phone",  # Invalid phone format
        "location": {},  # Missing required fields
        "farm_details": {},  # Missing required fields
        "preferences": {}  # Missing required fields
    }
    
    response = client.post("/api/v1/farmers", json=invalid_profile)
    
    assert response.status_code == 422  # Validation error
    data = response.json()
    assert "detail" in data


@patch('boto3.client')
def test_list_farmer_profiles(mock_boto_client, client):
    """Test listing farmer profiles."""
    # Mock DynamoDB client
    mock_dynamodb = MagicMock()
    mock_boto_client.return_value = mock_dynamodb
    
    # Mock scan response with empty results
    mock_dynamodb.scan.return_value = {"Items": []}
    
    response = client.get("/api/v1/farmers")
    
    assert response.status_code == 200
    data = response.json()
    
    assert isinstance(data, list)
    
    # Verify DynamoDB scan was called
    mock_dynamodb.scan.assert_called_once()