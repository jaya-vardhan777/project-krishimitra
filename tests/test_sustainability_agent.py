"""
Tests for Sustainability Agent

This module contains tests for the Sustainability Agent including water usage tracking,
soil health assessment, carbon footprint calculation, and climate risk assessment.
"""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal

from src.krishimitra.agents.sustainability import (
    WaterUsageTracker,
    SoilHealthAssessment,
    CarbonFootprintCalculator,
    ClimateRiskAssessment,
    SustainabilityAgent,
    SustainabilityAgentWithClimate
)
from src.krishimitra.models.agricultural_intelligence import (
    WeatherData, SoilData, SoilNutrients, AlertLevel, WeatherCondition
)
from src.krishimitra.models.base import GeographicCoordinate, Measurement


class TestWaterUsageTracker:
    """Test water usage tracking functionality"""
    
    def test_track_water_usage_basic(self):
        """Test basic water usage tracking"""
        tracker = WaterUsageTracker()
        
        irrigation_records = [
            {"date": "2024-01-15", "water_amount_m3": 500},
            {"date": "2024-01-20", "water_amount_m3": 450}
        ]
        rainfall_data = [10, 5, 0, 15]
        
        result = tracker.track_water_usage(
            farmer_id="F001",
            crop_name="wheat",
            field_area_hectares=2.0,
            irrigation_records=irrigation_records,
            rainfall_data=rainfall_data,
            season_start_date=date(2024, 1, 1)
        )
        
        assert "farmer_id" in result
        assert result["farmer_id"] == "F001"
        assert "water_usage" in result
        assert "threshold" in result
        assert "alert" in result
        assert result["alert"]["level"] in ["low", "moderate", "high", "severe"]
    
    def test_water_usage_alert_threshold(self):
        """Test water usage alert when exceeding threshold"""
        tracker = WaterUsageTracker()
        
        # High water usage
        irrigation_records = [
            {"date": "2024-01-15", "water_amount_m3": 5000},
            {"date": "2024-01-20", "water_amount_m3": 4500}
        ]
        rainfall_data = [0, 0, 0]
        
        result = tracker.track_water_usage(
            farmer_id="F001",
            crop_name="wheat",
            field_area_hectares=2.0,
            irrigation_records=irrigation_records,
            rainfall_data=rainfall_data,
            season_start_date=date(2024, 1, 1)
        )
        
        # Should trigger high or severe alert
        assert result["alert"]["level"] in ["high", "severe"]
        assert result["threshold"]["usage_percentage"] > 70


class TestSoilHealthAssessment:
    """Test soil health assessment functionality"""
    
    def test_assess_soil_health_basic(self):
        """Test basic soil health assessment"""
        assessor = SoilHealthAssessment()
        
        soil_data = SoilData(
            location=GeographicCoordinate(latitude=28.6139, longitude=77.2090),
            sample_depth=Measurement(value=30, unit="cm"),
            ph=6.5,
            moisture_content=55.0,
            bulk_density=1.3,
            porosity=48.0,
            nutrients=SoilNutrients(
                nitrogen=250.0,
                phosphorus=20.0,
                potassium=200.0,
                organic_carbon=2.5
            )
        )
        
        result = assessor.assess_soil_health(
            farmer_id="F001",
            crop_name="wheat",
            soil_data=soil_data,
            historical_data=None
        )
        
        assert "farmer_id" in result
        assert "overall_health_index" in result
        assert 0 <= result["overall_health_index"] <= 100
        assert "component_scores" in result
        assert "erosion_risk" in result
        assert "recommendations" in result
    
    def test_soil_health_scoring(self):
        """Test soil health scoring components"""
        assessor = SoilHealthAssessment()
        
        # Good soil data
        soil_data = SoilData(
            location=GeographicCoordinate(latitude=28.6139, longitude=77.2090),
            sample_depth=Measurement(value=30, unit="cm"),
            ph=6.8,
            moisture_content=60.0,
            bulk_density=1.2,
            porosity=52.0,
            nutrients=SoilNutrients(
                nitrogen=300.0,
                phosphorus=30.0,
                potassium=300.0,
                organic_carbon=3.5
            )
        )
        
        result = assessor.assess_soil_health(
            farmer_id="F001",
            crop_name="wheat",
            soil_data=soil_data,
            historical_data=None
        )
        
        # Should have high health index with good soil data
        assert result["overall_health_index"] > 70
        assert result["erosion_risk"] == "low"


class TestCarbonFootprintCalculator:
    """Test carbon footprint calculation functionality"""
    
    def test_calculate_carbon_footprint_basic(self):
        """Test basic carbon footprint calculation"""
        calculator = CarbonFootprintCalculator()
        
        farming_activities = {
            "fertilizers": {
                "nitrogen_kg": 120,
                "phosphorus_kg": 60,
                "potassium_kg": 40
            },
            "fuel_usage": {
                "diesel_liters": 50
            },
            "electricity_usage": {
                "kwh": 200
            }
        }
        
        result = calculator.calculate_carbon_footprint(
            farmer_id="F001",
            crop_name="wheat",
            field_area_hectares=2.0,
            farming_activities=farming_activities,
            season_duration_days=120
        )
        
        assert "farmer_id" in result
        assert "total_emissions" in result
        assert "emissions_breakdown" in result
        assert "recommendations" in result
        assert result["total_emissions"]["kg_co2e"] > 0
    
    def test_carbon_footprint_with_rice(self):
        """Test carbon footprint calculation for rice (includes methane)"""
        calculator = CarbonFootprintCalculator()
        
        farming_activities = {
            "fertilizers": {
                "nitrogen_kg": 120,
                "phosphorus_kg": 60,
                "potassium_kg": 40
            },
            "water_management": "continuous_flooding"
        }
        
        result = calculator.calculate_carbon_footprint(
            farmer_id="F001",
            crop_name="rice",
            field_area_hectares=2.0,
            farming_activities=farming_activities,
            season_duration_days=120
        )
        
        # Rice should have crop-specific emissions (methane)
        assert "crop_specific" in result["emissions_breakdown"]
        assert result["emissions_breakdown"]["crop_specific"]["total_co2e"] > 0


class TestClimateRiskAssessment:
    """Test climate risk assessment functionality"""
    
    def test_assess_climate_risk_basic(self):
        """Test basic climate risk assessment"""
        assessor = ClimateRiskAssessment()
        
        weather_forecast = [
            WeatherData(
                location=GeographicCoordinate(latitude=28.6139, longitude=77.2090),
                timestamp=datetime.now() + timedelta(days=i),
                temperature=35 + i,
                humidity=60,
                wind_speed=15,
                rainfall=5,
                condition=WeatherCondition.CLEAR
            )
            for i in range(7)
        ]
        
        location = {"latitude": 28.6139, "longitude": 77.2090}
        
        result = assessor.assess_climate_risk(
            farmer_id="F001",
            crop_name="wheat",
            location=location,
            weather_forecast=weather_forecast,
            historical_weather=None
        )
        
        assert "farmer_id" in result
        assert "overall_risk_score" in result
        assert "alert_level" in result
        assert "extreme_events" in result
        assert "adaptation_strategies" in result
    
    def test_detect_extreme_heat(self):
        """Test detection of extreme heat events"""
        assessor = ClimateRiskAssessment()
        
        weather_forecast = [
            WeatherData(
                location=GeographicCoordinate(latitude=28.6139, longitude=77.2090),
                timestamp=datetime.now() + timedelta(days=i),
                temperature=42,  # Extreme heat
                humidity=60,
                wind_speed=15,
                rainfall=0,
                condition=WeatherCondition.CLEAR
            )
            for i in range(3)
        ]
        
        extreme_events = assessor._detect_extreme_events(weather_forecast)
        
        assert len(extreme_events) > 0
        assert any(
            event["type"] == "extreme_heat"
            for day in extreme_events
            for event in day["events"]
        )
    
    def test_generate_adaptation_strategies(self):
        """Test generation of adaptation strategies"""
        assessor = ClimateRiskAssessment()
        
        crop_risks = {
            "heat_stress": {"risk_level": "high", "probability": 80},
            "drought": {"risk_level": "moderate", "probability": 60},
            "flood": {"risk_level": "low", "probability": 10},
            "frost": {"risk_level": "low", "probability": 5},
            "wind_damage": {"risk_level": "low", "probability": 10}
        }
        
        strategies = assessor._generate_adaptation_strategies(
            crop_name="wheat",
            extreme_events=[],
            crop_risks=crop_risks
        )
        
        assert len(strategies) > 0
        # Should have strategies for heat stress and drought
        risk_types = [s["risk_type"] for s in strategies]
        assert "heat_stress" in risk_types
        assert "drought" in risk_types


class TestSustainabilityAgent:
    """Test main Sustainability Agent"""
    
    def test_agent_initialization(self):
        """Test agent initialization"""
        agent = SustainabilityAgent()
        
        assert agent.water_tracker is not None
        assert agent.soil_assessor is not None
        assert agent.carbon_calculator is not None
        assert len(agent.tools) > 0
    
    def test_agent_with_climate_initialization(self):
        """Test agent with climate capabilities initialization"""
        agent = SustainabilityAgentWithClimate()
        
        assert agent.water_tracker is not None
        assert agent.soil_assessor is not None
        assert agent.carbon_calculator is not None
        assert agent.climate_assessor is not None
        assert len(agent.tools) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
