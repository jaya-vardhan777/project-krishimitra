"""
Tests for the main FastAPI application.

This module contains basic tests to validate the FastAPI application setup
and core functionality.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Mock AWS services before importing the app
with patch('boto3.Session'), patch('boto3.client'):
    from src.krishimitra.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)


def test_root_endpoint(client):
    """Test the root endpoint returns correct information."""
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["name"] == "KrishiMitra API"
    assert data["version"] == "1.0.0"
    assert data["description"] == "AI-powered agricultural advisory platform"
    assert "status" in data
    assert "environment" in data


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/api/v1/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "environment" in data
    assert "version" in data


@patch('boto3.client')
def test_detailed_health_check(mock_boto_client, client):
    """Test the detailed health check endpoint."""
    # Mock AWS service responses
    mock_dynamodb = MagicMock()
    mock_s3 = MagicMock()
    mock_bedrock = MagicMock()
    
    mock_boto_client.side_effect = lambda service, **kwargs: {
        'dynamodb': mock_dynamodb,
        's3': mock_s3,
        'bedrock-runtime': mock_bedrock
    }[service]
    
    response = client.get("/api/v1/health/detailed")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "status" in data
    assert "services" in data
    assert "timestamp" in data


def test_invalid_endpoint(client):
    """Test that invalid endpoints return 404."""
    response = client.get("/api/v1/nonexistent")
    
    assert response.status_code == 404