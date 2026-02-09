"""
Tests for Advisory Agent with personalized recommendation engine.

This module tests the Advisory Agent's ability to generate personalized
recommendations using LangChain agents, decision trees, and custom tools.
"""

import pytest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock

from src.krishimitra.agents.advisory import (
    AdvisoryAgent,
    FarmerProfileAnalyzer,
    CropRecommendationScorer,
    CropTimingOptimizer
)
from src.krishimitra.models.farmer import (
    FarmerProfile, FarmDetails, ContactInfo, Location, Preferences,
    CropInfo, SoilType, IrrigationType, FarmingExperience,
    CropCategory, CropSeason
)
from src.krishimitra.models.base import Address, GeographicCoordinate, Measurement, MonetaryAmount, LanguageCode, Currency
from src.krishimitra.models.agricultural_intelligence import (
    AgriculturalIntelligence, WeatherData, SoilData, MarketData,
    WeatherCondition, MarketPrice
)
from src.krishimitra.models.recommendation import (
    RecommendationRequest, RecommendationType, Priority
)


@pytest.fixture
def sample_farmer_profile():
    """Create a sample farmer profile for testing"""
    return FarmerProfile(
        id="farmer_test_001",
        name="Test Farmer",
        farming_experience=FarmingExperience.INTERMEDIATE,
        contact_info=ContactInfo(
            primary_phone="+919876543210"
        ),
        location=Location(
            address=Address(
                village="Test Village",
                district="Test District",
                state="Maharashtra",
                pincode="411001",
                country="India",
                coordinates=GeographicCoordinate(latitude=18.5204, longitude=73.8567)
            )
        ),
        farm_details=FarmDetails(
            total_land_area=Measurement(value=Decimal("2.5"), unit="hectares"),
            soil_type=SoilType.BLACK_COTTON,
            primary_irrigation_source=IrrigationType.DRIP,
            crops=[
                CropInfo(
                    crop_name="wheat",
                    category=CropCategory.CEREALS,
                    season=CropSeason.RABI,
                    area=Measurement(value=Decimal("1.5"), unit="hectares")
                )
            ]
        ),
        preferences=Preferences(
            organic_farming_interest=True,
            budget_constraints=MonetaryAmount(amount=50000, currency=Currency())
        )
    )


@pytest.fixture
def sample_agricultural_data():
    """Create sample agricultural intelligence data"""
    return AgriculturalIntelligence(
        location_id="loc_test_001",
        timestamp=datetime.now(),
        weather_data=WeatherData(
            location_id="loc_test_001",
            timestamp=datetime.now(),
            temperature=25.0,
            humidity=65.0,
            rainfall=10.0,
            wind_speed=15.0,
            condition=WeatherCondition.PARTLY_CLOUDY
        ),
        soil_data=SoilData(
            location_id="loc_test_001",
            timestamp=datetime.now(),
            ph=7.2,
            moisture_content=45.0,
            nitrogen=250.0,
            phosphorus=30.0,
            potassium=180.0
        ),
        market_data=[
            MarketData(
                market_id="market_001",
                market_name="Test Mandi",
                location="Test District",
                timestamp=datetime.now(),
                prices=[
                    MarketPrice(
                        commodity="wheat",
                        variety="general",
                        modal_price=MonetaryAmount(amount=2500, currency=Currency()),
                        unit="quintal"
                    )
                ]
            )
        ]
    )


class TestFarmerProfileAnalyzer:
    """Test FarmerProfileAnalyzer functionality"""
    
    def test_analyze_profile(self, sample_farmer_profile):
        """Test farmer profile analysis"""
        analyzer = FarmerProfileAnalyzer()
        analysis = analyzer.analyze_profile(sample_farmer_profile)
        
        assert analysis["farmer_id"] == "farmer_test_001"
        assert analysis["experience_level"] == "intermediate"
        assert analysis["soil_type"] == "black_cotton"
        assert analysis["irrigation_type"] == "drip"
        assert analysis["organic_interest"] is True
        assert "wheat" in analysis["current_crops"]
        assert analysis["location"]["state"] == "Maharashtra"
    
    def test_convert_to_hectares(self, sample_farmer_profile):
        """Test land area conversion to hectares"""
        analyzer = FarmerProfileAnalyzer()
        
        # Test hectares
        hectares = analyzer._convert_to_hectares(
            Measurement(value=2.5, unit="hectares")
        )
        assert hectares == 2.5
        
        # Test acres
        acres = analyzer._convert_to_hectares(
            Measurement(value=1.0, unit="acres")
        )
        assert abs(acres - 0.404686) < 0.001
    
    def test_calculate_similarity_score(self, sample_farmer_profile):
        """Test similarity score calculation between profiles"""
        analyzer = FarmerProfileAnalyzer()
        
        profile1 = analyzer.analyze_profile(sample_farmer_profile)
        profile2 = profile1.copy()
        
        # Identical profiles should have high similarity
        score = analyzer.calculate_similarity_score(profile1, profile2)
        assert score > 0.8
        
        # Different profiles should have lower similarity
        profile2["soil_type"] = "alluvial"
        profile2["current_crops"] = ["rice"]
        score = analyzer.calculate_similarity_score(profile1, profile2)
        assert score < 0.8


class TestCropRecommendationScorer:
    """Test CropRecommendationScorer functionality"""
    
    def test_score_crop_recommendation(self, sample_farmer_profile, sample_agricultural_data):
        """Test crop recommendation scoring"""
        scorer = CropRecommendationScorer()
        analyzer = FarmerProfileAnalyzer()
        
        profile_analysis = analyzer.analyze_profile(sample_farmer_profile)
        
        score, breakdown = scorer.score_crop_recommendation(
            "wheat",
            profile_analysis,
            sample_agricultural_data,
            "rabi"
        )
        
        assert 0.0 <= score <= 1.0
        assert "soil_suitability" in breakdown
        assert "climate_suitability" in breakdown
        assert "market_demand" in breakdown
        assert "water_availability" in breakdown
        assert "farmer_experience" in breakdown
        assert "input_cost" in breakdown
    
    def test_soil_suitability(self):
        """Test soil suitability calculation"""
        scorer = CropRecommendationScorer()
        
        # Wheat on alluvial soil should be highly suitable
        score = scorer._calculate_soil_suitability("wheat", "alluvial")
        assert score >= 0.8
        
        # Rice on black cotton should be moderately suitable
        score = scorer._calculate_soil_suitability("rice", "black_cotton")
        assert 0.5 <= score < 0.9
    
    def test_climate_suitability(self, sample_agricultural_data):
        """Test climate suitability calculation"""
        scorer = CropRecommendationScorer()
        
        # Wheat in cool weather should be suitable
        weather = sample_agricultural_data.weather_data
        weather.temperature = 20.0
        score = scorer._calculate_climate_suitability("wheat", weather, "rabi")
        assert score >= 0.5
    
    def test_water_availability(self):
        """Test water availability scoring"""
        scorer = CropRecommendationScorer()
        
        # Rice with drip irrigation should have good score
        score = scorer._calculate_water_availability("rice", "drip")
        assert score >= 0.7
        
        # Pulses with rainfed should still be acceptable
        score = scorer._calculate_water_availability("pulses", "rainfed")
        assert score >= 0.5


class TestCropTimingOptimizer:
    """Test CropTimingOptimizer functionality"""
    
    def test_get_optimal_planting_time(self):
        """Test optimal planting time determination"""
        optimizer = CropTimingOptimizer()
        
        # Test wheat in November (optimal for rabi)
        result = optimizer.get_optimal_planting_time(
            "wheat",
            date(2024, 11, 15),
            None
        )
        
        assert "optimal" in result
        assert "season" in result
        assert result["season"] == "rabi"
    
    def test_get_season_from_month(self):
        """Test season determination from month"""
        optimizer = CropTimingOptimizer()
        
        assert optimizer._get_season_from_month("july") == "kharif"
        assert optimizer._get_season_from_month("december") == "rabi"
        assert optimizer._get_season_from_month("may") == "zaid"
    
    def test_generate_crop_calendar(self, sample_farmer_profile, sample_agricultural_data):
        """Test crop calendar generation"""
        optimizer = CropTimingOptimizer()
        analyzer = FarmerProfileAnalyzer()
        
        profile_analysis = analyzer.analyze_profile(sample_farmer_profile)
        calendar = optimizer.generate_crop_calendar(profile_analysis, sample_agricultural_data)
        
        assert len(calendar) == 12  # 12 months
        assert all("month" in entry for entry in calendar)
        assert all("season" in entry for entry in calendar)
        assert all("suitable_crops" in entry for entry in calendar)


@pytest.mark.asyncio
class TestAdvisoryAgent:
    """Test AdvisoryAgent functionality"""
    
    @patch('src.krishimitra.agents.advisory.boto3.client')
    async def test_agent_initialization(self, mock_boto_client):
        """Test Advisory Agent initialization"""
        mock_boto_client.return_value = Mock()
        
        agent = AdvisoryAgent()
        
        assert agent.profile_analyzer is not None
        assert agent.crop_scorer is not None
        assert agent.timing_optimizer is not None
        assert len(agent.tools) > 0
    
    @patch('src.krishimitra.agents.advisory.boto3.client')
    async def test_generate_crop_recommendations(
        self,
        mock_boto_client,
        sample_farmer_profile,
        sample_agricultural_data
    ):
        """Test crop recommendation generation"""
        mock_boto_client.return_value = Mock()
        
        agent = AdvisoryAgent()
        
        request = RecommendationRequest(
            farmer_id="farmer_test_001",
            query_type=RecommendationType.CROP_SELECTION,
            language=LanguageCode.ENGLISH,
            max_recommendations=3
        )
        
        recommendations = await agent._generate_crop_recommendations(
            request,
            agent.profile_analyzer.analyze_profile(sample_farmer_profile),
            sample_agricultural_data
        )
        
        assert len(recommendations) > 0
        assert all(rec.recommendation_type == RecommendationType.CROP_SELECTION for rec in recommendations)
        assert all(rec.farmer_id == "farmer_test_001" for rec in recommendations)
        assert all(len(rec.action_items) > 0 for rec in recommendations)
    
    @patch('src.krishimitra.agents.advisory.boto3.client')
    async def test_generate_irrigation_recommendations(
        self,
        mock_boto_client,
        sample_farmer_profile,
        sample_agricultural_data
    ):
        """Test irrigation recommendation generation"""
        mock_boto_client.return_value = Mock()
        
        agent = AdvisoryAgent()
        
        request = RecommendationRequest(
            farmer_id="farmer_test_001",
            query_type=RecommendationType.IRRIGATION,
            language=LanguageCode.ENGLISH
        )
        
        recommendations = await agent._generate_irrigation_recommendations(
            request,
            agent.profile_analyzer.analyze_profile(sample_farmer_profile),
            sample_agricultural_data
        )
        
        assert len(recommendations) > 0
        assert all(rec.recommendation_type == RecommendationType.IRRIGATION for rec in recommendations)
        # Check for water-saving recommendations
        assert any("water" in rec.description.lower() for rec in recommendations)
    
    @patch('src.krishimitra.agents.advisory.boto3.client')
    async def test_generate_pest_management_recommendations(
        self,
        mock_boto_client,
        sample_farmer_profile,
        sample_agricultural_data
    ):
        """Test pest management recommendation generation"""
        mock_boto_client.return_value = Mock()
        
        agent = AdvisoryAgent()
        
        request = RecommendationRequest(
            farmer_id="farmer_test_001",
            query_type=RecommendationType.PEST_MANAGEMENT,
            language=LanguageCode.ENGLISH
        )
        
        recommendations = await agent._generate_pest_management_recommendations(
            request,
            agent.profile_analyzer.analyze_profile(sample_farmer_profile),
            sample_agricultural_data
        )
        
        assert len(recommendations) > 0
        assert all(rec.recommendation_type == RecommendationType.PEST_MANAGEMENT for rec in recommendations)
        # Check for organic methods
        assert any("organic" in rec.description.lower() or "neem" in rec.description.lower() for rec in recommendations)
    
    @patch('src.krishimitra.agents.advisory.boto3.client')
    async def test_calculate_personalization_score(self, mock_boto_client):
        """Test personalization score calculation"""
        mock_boto_client.return_value = Mock()
        
        agent = AdvisoryAgent()
        
        # Complete profile
        complete_profile = {
            "farm_size_hectares": 2.5,
            "soil_type": "black_cotton",
            "current_crops": ["wheat"],
            "experience_level": "intermediate",
            "location": {"state": "Maharashtra"},
            "irrigation_type": "drip"
        }
        
        score = agent._calculate_personalization_score(complete_profile)
        assert score == 100.0
        
        # Incomplete profile
        incomplete_profile = {
            "farm_size_hectares": 2.5,
            "soil_type": "black_cotton"
        }
        
        score = agent._calculate_personalization_score(incomplete_profile)
        assert 0.0 < score < 100.0


def test_langchain_tools_exist():
    """Test that LangChain tools are properly defined"""
    from src.krishimitra.agents.advisory import (
        analyze_farmer_profile_tool,
        recommend_crops_tool,
        optimize_irrigation_schedule_tool,
        analyze_market_timing_tool,
        generate_pest_management_plan_tool
    )
    
    # Check that tools are callable
    assert callable(analyze_farmer_profile_tool)
    assert callable(recommend_crops_tool)
    assert callable(optimize_irrigation_schedule_tool)
    assert callable(analyze_market_timing_tool)
    assert callable(generate_pest_management_plan_tool)
    
    # Check tool metadata
    assert hasattr(analyze_farmer_profile_tool, 'name')
    assert hasattr(recommend_crops_tool, 'name')
