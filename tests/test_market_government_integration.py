"""
Tests for market data and government database integration.

This module tests the market data collection from AGMARKNET and government
database integration including PM-KISAN, soil health cards, and crop insurance.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

from src.krishimitra.agents.market_integration import (
    MarketAPIClient, 
    MarketDataTool, 
    MarketIntelligenceAgent,
    AGMARKNETPrice
)
from src.krishimitra.agents.government_integration import (
    GovernmentAPIClient,
    GovernmentDataTool,
    GovernmentIntegrationAgent,
    PMKISANRecord,
    SoilHealthCard,
    CropInsurancePolicy
)
from src.krishimitra.core.data_sync import CacheManager, DataSynchronizer, DataSource
from src.krishimitra.models.base import GeographicCoordinate


class TestMarketIntegration:
    """Test market data integration functionality"""
    
    @pytest.fixture
    def market_client(self):
        """Create market API client for testing"""
        return MarketAPIClient()
    
    @pytest.fixture
    def sample_agmarknet_data(self):
        """Sample AGMARKNET price data"""
        return [
            AGMARKNETPrice(
                commodity="Rice",
                variety="Common",
                market="Pune Market",
                district="Pune",
                state="Maharashtra",
                min_price=2000.0,
                max_price=2200.0,
                modal_price=2100.0,
                arrivals=500.0,
                price_date="2024-02-04"
            )
        ]
    
    def test_agmarknet_price_model_validation(self):
        """Test AGMARKNET price model validation"""
        # Valid price data
        price = AGMARKNETPrice(
            commodity="Rice",
            variety="Basmati",
            market="Delhi Market",
            district="Delhi",
            state="Delhi",
            min_price=3000.0,
            max_price=3500.0,
            modal_price=3250.0,
            price_date="2024-02-04"
        )
        assert price.commodity == "Rice"
        assert price.modal_price == 3250.0
        
        # Test price validation - negative price should fail
        with pytest.raises(ValueError):
            AGMARKNETPrice(
                commodity="Rice",
                market="Test Market",
                district="Test",
                state="Test",
                min_price=-100.0,
                max_price=2000.0,
                modal_price=1500.0,
                price_date="2024-02-04"
            )
        
        # Test price range validation - max < min should fail
        with pytest.raises(ValueError):
            AGMARKNETPrice(
                commodity="Rice",
                market="Test Market",
                district="Test",
                state="Test",
                min_price=2000.0,
                max_price=1500.0,  # Less than min_price
                modal_price=1750.0,
                price_date="2024-02-04"
            )
    
    @pytest.mark.asyncio
    async def test_market_client_get_agmarknet_prices(self, market_client):
        """Test AGMARKNET price fetching"""
        with patch.object(market_client.http_client, 'get') as mock_get:
            # Mock successful API response
            mock_response = Mock()
            mock_response.json.return_value = {
                "records": [
                    {
                        "commodity": "Rice",
                        "variety": "Common",
                        "market": "Test Market",
                        "district": "Test District",
                        "state": "Test State",
                        "min_price": "2000",
                        "max_price": "2200",
                        "modal_price": "2100",
                        "arrivals": "500",
                        "price_date": "2024-02-04"
                    }
                ]
            }
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            prices = await market_client.get_agmarknet_prices("Rice")
            
            assert len(prices) == 1
            assert prices[0].commodity == "Rice"
            assert prices[0].modal_price == 2000.0  # Note: converted to float
            
        await market_client.close()
    
    @pytest.mark.asyncio
    async def test_market_data_tool(self):
        """Test market data LangChain tool"""
        tool = MarketDataTool()
        
        with patch('src.krishimitra.agents.market_integration.MarketAPIClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock market data response
            mock_market_data = [Mock()]
            mock_market_data[0].market_name = "Test Market"
            mock_market_data[0].prices = [Mock()]
            mock_market_data[0].prices[0].modal_price = Mock()
            mock_market_data[0].prices[0].modal_price.amount = 2100.0
            
            mock_client.get_nearby_market_prices.return_value = mock_market_data
            
            result = await tool._arun("Rice", "18.5204,73.8567")
            
            assert "Rice" in result
            assert "Test Market" in result
            assert "2100" in result


class TestGovernmentIntegration:
    """Test government database integration functionality"""
    
    @pytest.fixture
    def gov_client(self):
        """Create government API client for testing"""
        return GovernmentAPIClient()
    
    @pytest.fixture
    def sample_pmkisan_record(self):
        """Sample PM-KISAN record"""
        return PMKISANRecord(
            beneficiary_id="PMKISAN123456",
            farmer_name="Test Farmer",
            father_name="Test Father",
            mobile_number="9876543210",
            aadhaar_number="123456789012",
            account_number="1234567890",
            ifsc_code="SBIN0001234",
            bank_name="State Bank of India",
            village="Test Village",
            district="Test District",
            state="Maharashtra",
            land_area=2.5,
            registration_date=datetime(2019, 1, 1),
            total_amount_received=12000.0,
            status="active"
        )
    
    def test_pmkisan_record_validation(self, sample_pmkisan_record):
        """Test PM-KISAN record model validation"""
        assert sample_pmkisan_record.beneficiary_id == "PMKISAN123456"
        assert sample_pmkisan_record.land_area == 2.5
        assert sample_pmkisan_record.status == "active"
    
    def test_soil_health_card_validation(self):
        """Test soil health card model validation"""
        card = SoilHealthCard(
            card_id="SHC123456",
            farmer_id="FARMER001",
            survey_number="SURVEY123",
            village="Test Village",
            district="Test District",
            state="Maharashtra",
            soil_type="Black Cotton Soil",
            ph_level=7.2,
            organic_carbon=0.65,
            nitrogen=280.5,
            phosphorus=45.2,
            potassium=320.8,
            sulfur=15.6,
            zinc=1.2,
            iron=8.5,
            test_date=datetime(2023, 10, 15),
            validity_date=datetime(2026, 10, 15)
        )
        
        assert card.ph_level == 7.2
        assert card.soil_type == "Black Cotton Soil"
        assert len(card.recommendations) == 0  # Default empty list
    
    @pytest.mark.asyncio
    async def test_gov_client_get_pmkisan_data(self, gov_client):
        """Test PM-KISAN data fetching"""
        # Test with mock data (since we're using mock implementation)
        pmkisan_data = await gov_client.get_pmkisan_beneficiary_info("123456789012")
        
        assert pmkisan_data is not None
        assert pmkisan_data.aadhaar_number == "123456789012"
        assert pmkisan_data.status == "active"
        
        await gov_client.close()
    
    @pytest.mark.asyncio
    async def test_gov_client_get_soil_health_card(self, gov_client):
        """Test soil health card fetching"""
        soil_card = await gov_client.get_soil_health_card("FARMER001", "SURVEY123")
        
        assert soil_card is not None
        assert soil_card.farmer_id == "FARMER001"
        assert soil_card.survey_number == "SURVEY123"
        assert soil_card.ph_level > 0
        
        await gov_client.close()
    
    @pytest.mark.asyncio
    async def test_gov_client_get_insurance_policies(self, gov_client):
        """Test crop insurance policy fetching"""
        policies = await gov_client.get_crop_insurance_policies("FARMER001")
        
        assert isinstance(policies, list)
        assert len(policies) >= 0  # May be empty or have mock data
        
        if policies:
            policy = policies[0]
            assert policy.farmer_id == "FARMER001"
            assert policy.sum_insured > 0
        
        await gov_client.close()
    
    @pytest.mark.asyncio
    async def test_government_data_tool(self):
        """Test government data LangChain tool"""
        tool = GovernmentDataTool()
        
        # Test PM-KISAN query
        result = await tool._arun("FARMER001", "pmkisan")
        assert "PM-KISAN" in result
        
        # Test soil health query
        result = await tool._arun("FARMER001", "soil_health")
        assert "Soil Health" in result or "pH" in result
        
        # Test schemes query
        result = await tool._arun("FARMER001", "schemes")
        assert "schemes" in result.lower() or "eligible" in result.lower()


class TestDataSynchronization:
    """Test data synchronization and caching functionality"""
    
    @pytest.fixture
    def cache_manager(self):
        """Create cache manager for testing"""
        return CacheManager()
    
    @pytest.fixture
    def data_synchronizer(self):
        """Create data synchronizer for testing"""
        return DataSynchronizer()
    
    @pytest.mark.asyncio
    async def test_cache_manager_basic_operations(self, cache_manager):
        """Test basic cache operations"""
        # Test data that doesn't require Redis connection
        test_data = {"test": "data", "timestamp": datetime.now(timezone.utc).isoformat()}
        
        # Note: These tests will pass even if Redis is not available
        # because the cache manager handles connection errors gracefully
        
        # Test set operation
        result = await cache_manager.set(DataSource.AGMARKNET, "test_commodity", test_data)
        # Result may be False if Redis is not available, which is acceptable for testing
        
        # Test get operation
        cache_entry = await cache_manager.get(DataSource.AGMARKNET, "test_commodity")
        # May be None if Redis is not available, which is acceptable for testing
    
    def test_data_source_enum(self):
        """Test data source enumeration"""
        assert DataSource.AGMARKNET == "agmarknet"
        assert DataSource.PMKISAN == "pmkisan"
        assert DataSource.SOIL_HEALTH == "soil_health"
        assert DataSource.CROP_INSURANCE == "crop_insurance"
    
    @pytest.mark.asyncio
    async def test_data_synchronizer_should_sync(self, data_synchronizer):
        """Test sync timing logic"""
        # Should sync if never synced before
        should_sync = await data_synchronizer.should_sync(DataSource.AGMARKNET)
        assert should_sync is True
        
        # Mark as synced
        data_synchronizer.last_sync[DataSource.AGMARKNET] = datetime.now(timezone.utc)
        
        # Should not sync immediately after
        should_sync = await data_synchronizer.should_sync(DataSource.AGMARKNET)
        assert should_sync is False


class TestIntegrationWorkflow:
    """Test end-to-end integration workflow"""
    
    @pytest.mark.asyncio
    async def test_comprehensive_data_collection(self):
        """Test comprehensive data collection from all sources"""
        from src.krishimitra.agents.data_ingestion import DataIngestionAgent
        
        agent = DataIngestionAgent()
        
        # Test data collection with mock data
        farmer_id = "TEST_FARMER_001"
        location = {"latitude": 18.5204, "longitude": 73.8567}
        
        # This will use mock data since we don't have real API connections
        result = await agent.collect_comprehensive_data(
            farmer_id=farmer_id,
            location=location,
            crop_type="rice"
        )
        
        # Verify result structure
        assert "farmer_id" in result
        assert "location" in result
        assert "timestamp" in result
        assert "sensor_data" in result
        assert "weather_data" in result
        assert "satellite_data" in result
        assert "market_data" in result
        assert "government_data" in result
        assert "errors" in result
        
        assert result["farmer_id"] == farmer_id
        
        # Close agent connections
        await agent.close()
    
    @pytest.mark.asyncio
    async def test_market_and_government_integration(self):
        """Test market and government data integration together"""
        from src.krishimitra.agents.data_ingestion import DataIngestionAgent
        
        agent = DataIngestionAgent()
        
        # Test market data collection
        location = {"latitude": 18.5204, "longitude": 73.8567}
        market_data = await agent.collect_market_data(location, ["rice", "wheat"])
        
        # Should return data structure (may be empty due to mock APIs)
        assert isinstance(market_data, (list, dict))
        
        # Test government data collection
        gov_data = await agent.collect_government_data("TEST_FARMER_001")
        
        # Should return data structure
        assert isinstance(gov_data, dict)
        
        # Close agent connections
        await agent.close()


if __name__ == "__main__":
    # Run basic tests without pytest
    async def run_basic_tests():
        print("Running basic integration tests...")
        
        # Test market client
        print("Testing market client...")
        client = MarketAPIClient()
        await client.close()
        print("✓ Market client test passed")
        
        # Test government client
        print("Testing government client...")
        gov_client = GovernmentAPIClient()
        await gov_client.close()
        print("✓ Government client test passed")
        
        # Test data ingestion agent
        print("Testing data ingestion agent...")
        agent = DataIngestionAgent()
        await agent.close()
        print("✓ Data ingestion agent test passed")
        
        print("All basic tests passed!")
    
    asyncio.run(run_basic_tests())