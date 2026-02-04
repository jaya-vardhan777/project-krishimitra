"""
Pytest configuration and fixtures for KrishiMitra Platform tests.

This module provides common test fixtures and configuration for all tests.
"""

import pytest
from fastapi.testclient import TestClient
from hypothesis import settings
from unittest.mock import patch

# Mock AWS services before importing the app
with patch('boto3.Session'), patch('boto3.client'):
    from src.krishimitra.main import app


# Configure Hypothesis for property-based testing
settings.register_profile("ci", max_examples=50, deadline=None)
settings.register_profile("dev", max_examples=10, deadline=None)
settings.register_profile("debug", max_examples=5, deadline=None, verbosity=2)


@pytest.fixture
def client():
    """Create test client for FastAPI application."""
    return TestClient(app)


@pytest.fixture
def sample_farmer_profile():
    """Sample farmer profile for testing."""
    return {
        "name": "राम कुमार",
        "phone_number": "+919876543210",
        "preferred_language": "hi-IN",
        "location": {
            "state": "उत्तर प्रदेश",
            "district": "मेरठ",
            "village": "सरधना",
            "pincode": "250342",
            "latitude": 29.1492,
            "longitude": 77.6130
        },
        "farm_details": {
            "total_land_area": 2.5,
            "soil_type": "दोमट मिट्टी",
            "irrigation_type": "ट्यूबवेल",
            "water_source": "भूजल",
            "crops": [
                {
                    "crop_type": "गेहूं",
                    "area": 1.5,
                    "planting_date": "2023-11-15",
                    "expected_harvest": "2024-04-15",
                    "variety": "HD-2967"
                },
                {
                    "crop_type": "सरसों",
                    "area": 1.0,
                    "planting_date": "2023-10-20",
                    "expected_harvest": "2024-03-20",
                    "variety": "पूसा बोल्ड"
                }
            ]
        },
        "preferences": {
            "organic_farming": False,
            "risk_tolerance": "medium",
            "budget_constraints": {
                "max_investment": 50000,
                "currency": "INR"
            },
            "communication_preference": "voice"
        }
    }


@pytest.fixture
def sample_weather_data():
    """Sample weather data for testing."""
    return {
        "location": {
            "latitude": 29.1492,
            "longitude": 77.6130,
            "radius": 5
        },
        "current": {
            "temperature": 25.5,
            "humidity": 65,
            "rainfall": 0,
            "wind_speed": 8.2,
            "pressure": 1013.2
        },
        "forecast": [
            {
                "date": "2024-01-15",
                "temperature_max": 28,
                "temperature_min": 12,
                "humidity": 70,
                "rainfall_probability": 10,
                "wind_speed": 6.5
            },
            {
                "date": "2024-01-16",
                "temperature_max": 26,
                "temperature_min": 10,
                "humidity": 75,
                "rainfall_probability": 20,
                "wind_speed": 7.2
            }
        ]
    }


@pytest.fixture
def sample_soil_data():
    """Sample soil data for testing."""
    return {
        "location": {
            "latitude": 29.1492,
            "longitude": 77.6130
        },
        "moisture": 45.2,
        "ph": 7.2,
        "nutrients": {
            "nitrogen": 280,
            "phosphorus": 45,
            "potassium": 320,
            "organic_carbon": 0.65
        },
        "temperature": 18.5,
        "conductivity": 0.8,
        "last_updated": "2024-01-14T10:30:00Z"
    }