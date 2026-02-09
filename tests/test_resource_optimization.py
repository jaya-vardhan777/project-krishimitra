"""
Tests for Resource Optimization Module

Tests irrigation optimization, fertilizer reduction, and IPM plan generation.
"""

import pytest
import numpy as np
from decimal import Decimal
from datetime import date

from src.krishimitra.agents.resource_optimization import (
    WaterOptimizationModel,
    FertilizerOptimizationModel,
    PesticideReductionModel,
    IrrigationMethod,
    CropWaterRequirement,
    optimize_irrigation_tool,
    optimize_fertilizer_tool,
    generate_ipm_plan_tool
)


class TestCropWaterRequirement:
    """Test crop water requirement calculations"""
    
    def test_get_crop_coefficient(self):
        """Test crop coefficient retrieval"""
        # Test known crop
        kc = CropWaterRequirement.get_crop_coefficient("rice", "mid")
        assert kc == 1.20
        
        # Test different stage
        kc_initial = CropWaterRequirement.get_crop_coefficient("wheat", "initial")
        assert kc_initial == 0.40
        
        # Test unknown crop returns default
        kc_unknown = CropWaterRequirement.get_crop_coefficient("unknown_crop", "mid")
        assert kc_unknown == 1.0
    
    def test_get_seasonal_requirement(self):
        """Test seasonal water requirement retrieval"""
        # Test known crop
        req = CropWaterRequirement.get_seasonal_requirement("rice")
        assert req == 1200
        
        # Test unknown crop returns default
        req_unknown = CropWaterRequirement.get_seasonal_requirement("unknown")
        assert req_unknown == 500


class TestWaterOptimizationModel:
    """Test water optimization model"""
    
    def test_calculate_evapotranspiration(self):
        """Test ET0 calculation"""
        model = WaterOptimizationModel()
        
        # Test with typical values
        et0 = model.calculate_evapotranspiration(
            temperature=28.0,
            humidity=65.0,
            wind_speed=2.5
        )
        
        assert et0 > 0
        assert et0 < 20  # Reasonable range for ET0
    
    def test_calculate_evapotranspiration_with_solar_radiation(self):
        """Test ET0 calculation with solar radiation"""
        model = WaterOptimizationModel()
        
        et0 = model.calculate_evapotranspiration(
            temperature=28.0,
            humidity=65.0,
            wind_speed=2.5,
            solar_radiation=20.0
        )
        
        assert et0 > 0
        assert et0 < 20
    
    def test_calculate_crop_water_need(self):
        """Test crop water need calculation"""
        model = WaterOptimizationModel()
        
        water_need = model.calculate_crop_water_need(
            crop_name="rice",
            growth_stage="mid",
            et0=5.0,
            rainfall=0.0,
            soil_moisture=50.0
        )
        
        assert water_need > 0
        # Rice in mid-stage with Kc=1.20 should need about 6mm/day
        assert 4.0 < water_need < 8.0
    
    def test_calculate_crop_water_need_with_rainfall(self):
        """Test water need calculation with rainfall"""
        model = WaterOptimizationModel()
        
        water_need = model.calculate_crop_water_need(
            crop_name="wheat",
            growth_stage="mid",
            et0=5.0,
            rainfall=10.0,  # Significant rainfall
            soil_moisture=70.0  # High soil moisture
        )
        
        # Should be reduced due to rainfall and high soil moisture
        assert water_need >= 0
        assert water_need < 3.0
    
    def test_optimize_irrigation_schedule(self):
        """Test irrigation schedule optimization"""
        model = WaterOptimizationModel()
        
        # Create weather forecast
        weather_forecast = [
            {"temperature": 28, "humidity": 65, "wind_speed": 2.5, "rainfall": 0}
            for _ in range(7)
        ]
        
        result = model.optimize_irrigation_schedule(
            crop_name="wheat",
            field_area_hectares=2.0,
            irrigation_method=IrrigationMethod.DRIP,
            weather_forecast=weather_forecast,
            soil_moisture=50.0,
            growth_stage="mid"
        )
        
        assert result["success"] is True
        assert "baseline_water_m3" in result
        assert "optimized_water_m3" in result
        assert "water_saved_m3" in result
        assert "reduction_percentage" in result
        assert "irrigation_schedule" in result
        
        # Check that water is actually reduced
        assert result["optimized_water_m3"] < result["baseline_water_m3"]
        
        # Check reduction is close to target (15-25% range)
        assert 10 <= result["reduction_percentage"] <= 30
    
    def test_optimize_irrigation_schedule_different_methods(self):
        """Test optimization with different irrigation methods"""
        model = WaterOptimizationModel()
        
        weather_forecast = [
            {"temperature": 28, "humidity": 65, "wind_speed": 2.5, "rainfall": 0}
            for _ in range(7)
        ]
        
        # Test drip irrigation
        result_drip = model.optimize_irrigation_schedule(
            crop_name="maize",
            field_area_hectares=1.0,
            irrigation_method=IrrigationMethod.DRIP,
            weather_forecast=weather_forecast,
            soil_moisture=50.0
        )
        
        # Test flood irrigation
        result_flood = model.optimize_irrigation_schedule(
            crop_name="maize",
            field_area_hectares=1.0,
            irrigation_method=IrrigationMethod.FLOOD,
            weather_forecast=weather_forecast,
            soil_moisture=50.0
        )
        
        # Both should succeed
        assert result_drip["success"] is True
        assert result_flood["success"] is True
        
        # Baseline water for drip should be less than flood due to efficiency
        assert result_drip["baseline_water_m3"] < result_flood["baseline_water_m3"]


class TestFertilizerOptimizationModel:
    """Test fertilizer optimization model"""
    
    def test_calculate_fertilizer_requirement(self):
        """Test fertilizer requirement calculation"""
        model = FertilizerOptimizationModel()
        
        result = model.calculate_fertilizer_requirement(
            crop_name="wheat",
            field_area_hectares=2.0,
            soil_data=None,
            organic_preference=False
        )
        
        assert result["success"] is True
        assert "nutrients" in result
        assert "nitrogen_kg" in result["nutrients"]
        assert "phosphorus_kg" in result["nutrients"]
        assert "potassium_kg" in result["nutrients"]
        assert "reduction_percentage" in result
        assert result["reduction_percentage"] == 15.0
        assert "application_schedule" in result
        assert len(result["application_schedule"]) > 0
    
    def test_fertilizer_reduction_achieved(self):
        """Test that 15% reduction is achieved"""
        model = FertilizerOptimizationModel()
        
        # Get base NPK for wheat
        base_npk = model.npk_requirements["wheat"]
        field_area = 2.0
        
        # Calculate expected baseline
        baseline_total = (base_npk["N"] + base_npk["P"] + base_npk["K"]) * field_area
        
        result = model.calculate_fertilizer_requirement(
            crop_name="wheat",
            field_area_hectares=field_area,
            soil_data=None,
            organic_preference=False
        )
        
        # Calculate optimized total
        optimized_total = (
            result["nutrients"]["nitrogen_kg"] +
            result["nutrients"]["phosphorus_kg"] +
            result["nutrients"]["potassium_kg"]
        )
        
        # Check reduction is approximately 15%
        reduction = (baseline_total - optimized_total) / baseline_total * 100
        assert 14 <= reduction <= 16  # Allow small tolerance
    
    def test_organic_alternatives_provided(self):
        """Test organic alternatives are provided when requested"""
        model = FertilizerOptimizationModel()
        
        result = model.calculate_fertilizer_requirement(
            crop_name="rice",
            field_area_hectares=1.0,
            soil_data=None,
            organic_preference=True
        )
        
        assert result["success"] is True
        assert "organic_options" in result
        assert len(result["organic_options"]) > 0
        
        # Check organic options have required fields
        for option in result["organic_options"]:
            assert "name" in option
            assert "npk_content" in option
            assert "application_rate" in option
    
    def test_application_schedule_split_doses(self):
        """Test that fertilizer is split into multiple applications"""
        model = FertilizerOptimizationModel()
        
        result = model.calculate_fertilizer_requirement(
            crop_name="maize",
            field_area_hectares=1.5,
            soil_data=None,
            organic_preference=False
        )
        
        assert result["success"] is True
        schedule = result["application_schedule"]
        
        # Should have multiple applications
        assert len(schedule) >= 2
        
        # Check each application has required fields
        for application in schedule:
            assert "stage" in application
            assert "timing" in application
            assert "nitrogen_kg" in application
            assert "application_method" in application


class TestPesticideReductionModel:
    """Test pesticide reduction and IPM model"""
    
    def test_generate_ipm_plan(self):
        """Test IPM plan generation"""
        model = PesticideReductionModel()
        
        result = model.generate_ipm_plan(
            crop_name="rice",
            pest_issue="stem borer",
            severity="moderate",
            organic_priority=True
        )
        
        assert result["success"] is True
        assert result["crop"] == "rice"
        assert result["target_pest"] == "stem borer"
        assert "phases" in result
        assert len(result["phases"]) >= 3  # Should have multiple phases
    
    def test_ipm_plan_phases_order(self):
        """Test that IPM phases are in correct priority order"""
        model = PesticideReductionModel()
        
        result = model.generate_ipm_plan(
            crop_name="cotton",
            severity="moderate",
            organic_priority=True
        )
        
        assert result["success"] is True
        phases = result["phases"]
        
        # First phase should be prevention
        assert "prevention" in phases[0]["name"].lower() or "cultural" in phases[0]["name"].lower()
        
        # Should include monitoring
        phase_names = [p["name"].lower() for p in phases]
        assert any("monitor" in name for name in phase_names)
        
        # Should include biological control before chemical
        bio_phase_idx = next((i for i, p in enumerate(phases) if "biological" in p["name"].lower()), None)
        chem_phase_idx = next((i for i, p in enumerate(phases) if "chemical" in p["name"].lower()), None)
        
        if bio_phase_idx is not None and chem_phase_idx is not None:
            assert bio_phase_idx < chem_phase_idx
    
    def test_ipm_plan_organic_priority(self):
        """Test that organic methods are prioritized"""
        model = PesticideReductionModel()
        
        result = model.generate_ipm_plan(
            crop_name="vegetables",
            severity="low",
            organic_priority=True
        )
        
        assert result["success"] is True
        
        # Should have biological/organic phase
        phase_names = [p["name"].lower() for p in result["phases"]]
        assert any("biological" in name or "organic" in name for name in phase_names)
        
        # Expected outcomes should mention pesticide reduction
        outcomes = result.get("expected_outcomes", {})
        assert "pesticide_reduction" in outcomes
    
    def test_ipm_plan_high_severity(self):
        """Test IPM plan for high severity includes chemical control"""
        model = PesticideReductionModel()
        
        result = model.generate_ipm_plan(
            crop_name="cotton",
            pest_issue="bollworm",
            severity="high",
            organic_priority=False
        )
        
        assert result["success"] is True
        
        # Should include chemical control phase for high severity
        phase_names = [p["name"].lower() for p in result["phases"]]
        assert any("chemical" in name for name in phase_names)
        
        # Should have safety precautions
        chem_phase = next((p for p in result["phases"] if "chemical" in p["name"].lower()), None)
        if chem_phase:
            assert "safety_precautions" in chem_phase or "warning" in chem_phase


class TestLangChainTools:
    """Test LangChain tool integrations"""
    
    def test_optimize_irrigation_tool(self):
        """Test irrigation optimization tool"""
        import json
        
        result_str = optimize_irrigation_tool.invoke({
            "crop_name": "wheat",
            "field_area_hectares": 2.0,
            "irrigation_method": "drip",
            "growth_stage": "mid"
        })
        
        result = json.loads(result_str)
        assert result["success"] is True
        assert "optimized_water_m3" in result
        assert "reduction_percentage" in result
    
    def test_optimize_fertilizer_tool(self):
        """Test fertilizer optimization tool"""
        import json
        
        result_str = optimize_fertilizer_tool.invoke({
            "crop_name": "rice",
            "field_area_hectares": 1.5,
            "organic_preference": True
        })
        
        result = json.loads(result_str)
        assert result["success"] is True
        assert "nutrients" in result
        assert "organic_options" in result
        assert len(result["organic_options"]) > 0
    
    def test_generate_ipm_plan_tool(self):
        """Test IPM plan generation tool"""
        import json
        
        result_str = generate_ipm_plan_tool.invoke({
            "crop_name": "cotton",
            "pest_issue": "whitefly",
            "severity": "moderate",
            "organic_priority": True
        })
        
        result = json.loads(result_str)
        assert result["success"] is True
        assert result["crop"] == "cotton"
        assert "phases" in result
        assert len(result["phases"]) > 0


class TestIntegration:
    """Integration tests for resource optimization"""
    
    def test_complete_resource_optimization_workflow(self):
        """Test complete workflow: irrigation + fertilizer + IPM"""
        # Initialize models
        water_model = WaterOptimizationModel()
        fertilizer_model = FertilizerOptimizationModel()
        ipm_model = PesticideReductionModel()
        
        crop = "wheat"
        field_area = 2.0
        
        # Get irrigation plan
        weather_forecast = [
            {"temperature": 25, "humidity": 60, "wind_speed": 2.0, "rainfall": 0}
            for _ in range(7)
        ]
        
        irrigation_result = water_model.optimize_irrigation_schedule(
            crop_name=crop,
            field_area_hectares=field_area,
            irrigation_method=IrrigationMethod.DRIP,
            weather_forecast=weather_forecast,
            soil_moisture=50.0
        )
        
        # Get fertilizer plan
        fertilizer_result = fertilizer_model.calculate_fertilizer_requirement(
            crop_name=crop,
            field_area_hectares=field_area,
            soil_data=None,
            organic_preference=True
        )
        
        # Get IPM plan
        ipm_result = ipm_model.generate_ipm_plan(
            crop_name=crop,
            severity="moderate",
            organic_priority=True
        )
        
        # Verify all plans generated successfully
        assert irrigation_result["success"] is True
        assert fertilizer_result["success"] is True
        assert ipm_result["success"] is True
        
        # Verify resource reductions
        assert irrigation_result["reduction_percentage"] >= 15
        assert fertilizer_result["reduction_percentage"] == 15.0
        
        # Verify organic/sustainable approach
        assert len(fertilizer_result["organic_options"]) > 0
        assert "biological" in str(ipm_result["phases"]).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
