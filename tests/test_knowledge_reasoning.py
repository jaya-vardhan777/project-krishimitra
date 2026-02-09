"""
Tests for Knowledge & Reasoning Agent

This module contains unit tests for the Knowledge & Reasoning Agent,
including Bedrock integration, prompt templates, and reasoning chains.
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

from src.krishimitra.agents.knowledge_reasoning import (
    KnowledgeReasoningAgent,
    BedrockLLMManager,
    AgriculturalReasoningChain,
    AgricultureQuery,
    KnowledgeResponse,
    AgriculturalPromptTemplates,
    ConversationMemoryManager
)
from src.krishimitra.models.farmer import (
    FarmerProfile, ContactInfo, Location, FarmDetails, 
    CommunicationPreference, SoilType, IrrigationType, FarmingExperience
)
from src.krishimitra.models.base import Address, GeographicCoordinate, Measurement
from src.krishimitra.models.agricultural_intelligence import AgriculturalIntelligence, WeatherData, WeatherCondition


class TestBedrockLLMManager:
    """Test Bedrock LLM Manager"""
    
    @pytest.fixture
    def mock_bedrock_client(self):
        """Mock Bedrock client"""
        with patch('boto3.client') as mock_client:
            mock_bedrock = Mock()
            mock_client.return_value = mock_bedrock
            yield mock_bedrock
    
    @pytest.fixture
    def llm_manager(self, mock_bedrock_client):
        """Create LLM manager with mocked Bedrock"""
        with patch('src.krishimitra.agents.knowledge_reasoning.BedrockLLM') as mock_bedrock_class, \
             patch('src.krishimitra.agents.knowledge_reasoning.ChatBedrock') as mock_chat_class:
            
            mock_llm = Mock()
            mock_chat = Mock()
            mock_bedrock_class.return_value = mock_llm
            mock_chat_class.return_value = mock_chat
            
            manager = BedrockLLMManager()
            return manager
    
    def test_initialization(self, llm_manager):
        """Test LLM manager initialization"""
        assert llm_manager.model_id == "anthropic.claude-3-5-sonnet-20241022-v2:0"
        assert llm_manager.llm is not None
        assert llm_manager.chat_model is not None
    
    @pytest.mark.asyncio
    async def test_connection_test_success(self, llm_manager):
        """Test successful connection test"""
        llm_manager.llm.invoke = Mock(return_value="Test response")
        
        result = await llm_manager.test_connection()
        assert result is True
        llm_manager.llm.invoke.assert_called_once_with("Test connection")
    
    @pytest.mark.asyncio
    async def test_connection_test_failure(self, llm_manager):
        """Test failed connection test"""
        llm_manager.llm.invoke = Mock(side_effect=Exception("Connection failed"))
        
        result = await llm_manager.test_connection()
        assert result is False


class TestAgriculturalPromptTemplates:
    """Test agricultural prompt templates"""
    
    def test_crop_advice_template(self):
        """Test crop advice template creation"""
        template = AgriculturalPromptTemplates.get_crop_advice_template()
        
        assert template is not None
        assert "location" in template.input_variables
        assert "crop_type" in template.input_variables
        assert "query" in template.input_variables
        assert "language" in template.input_variables
    
    def test_weather_analysis_template(self):
        """Test weather analysis template creation"""
        template = AgriculturalPromptTemplates.get_weather_analysis_template()
        
        assert template is not None
        assert "weather_data" in template.input_variables
        assert "forecast_data" in template.input_variables
        assert "location" in template.input_variables
    
    def test_market_analysis_template(self):
        """Test market analysis template creation"""
        template = AgriculturalPromptTemplates.get_market_analysis_template()
        
        assert template is not None
        assert "market_data" in template.input_variables
        assert "price_trends" in template.input_variables
        assert "crops" in template.input_variables
    
    def test_general_conversation_template(self):
        """Test general conversation template creation"""
        template = AgriculturalPromptTemplates.get_general_conversation_template()
        
        assert template is not None
        assert len(template.messages) == 2  # System and human messages


class TestConversationMemoryManager:
    """Test conversation memory manager"""
    
    @pytest.fixture
    def memory_manager(self):
        """Create memory manager with mocked LLM"""
        with patch('src.krishimitra.agents.knowledge_reasoning.BedrockLLMManager') as mock_manager_class:
            mock_manager = Mock()
            mock_llm = Mock()
            mock_manager.get_llm.return_value = mock_llm
            mock_manager_class.return_value = mock_manager
            
            return ConversationMemoryManager()
    
    def test_get_memory_creates_new(self, memory_manager):
        """Test that get_memory creates new memory for new farmer"""
        farmer_id = "farmer_123"
        
        memory = memory_manager.get_memory(farmer_id)
        
        assert memory is not None
        assert farmer_id in memory_manager.memories
    
    def test_get_memory_returns_existing(self, memory_manager):
        """Test that get_memory returns existing memory"""
        farmer_id = "farmer_123"
        
        memory1 = memory_manager.get_memory(farmer_id)
        memory2 = memory_manager.get_memory(farmer_id)
        
        assert memory1 is memory2
    
    def test_add_interaction(self, memory_manager):
        """Test adding interaction to memory"""
        farmer_id = "farmer_123"
        human_msg = "What should I plant this season?"
        ai_msg = "Based on your location and soil type, I recommend..."
        
        memory_manager.add_interaction(farmer_id, human_msg, ai_msg)
        
        memory = memory_manager.get_memory(farmer_id)
        messages = memory.chat_memory.messages
        
        # Should have 2 messages (human and AI)
        assert len(messages) >= 2
    
    def test_clear_memory(self, memory_manager):
        """Test clearing farmer memory"""
        farmer_id = "farmer_123"
        
        # Create memory
        memory_manager.get_memory(farmer_id)
        assert farmer_id in memory_manager.memories
        
        # Clear memory
        memory_manager.clear_memory(farmer_id)
        assert farmer_id not in memory_manager.memories


class TestAgriculturalReasoningChain:
    """Test agricultural reasoning chain"""
    
    @pytest.fixture
    def mock_llm_manager(self):
        """Mock LLM manager"""
        manager = Mock()
        mock_llm = Mock()
        mock_chat = Mock()
        manager.get_llm.return_value = mock_llm
        manager.get_chat_model.return_value = mock_chat
        return manager
    
    @pytest.fixture
    def reasoning_chain(self, mock_llm_manager):
        """Create reasoning chain with mocked LLM"""
        with patch('src.krishimitra.agents.knowledge_reasoning.LLMChain') as mock_chain_class, \
             patch('src.krishimitra.agents.knowledge_reasoning.ConversationChain') as mock_conv_class:
            
            mock_chain = Mock()
            mock_chain.arun = AsyncMock(return_value="Mocked agricultural advice")
            mock_chain_class.return_value = mock_chain
            
            mock_conv = Mock()
            mock_conv.arun = AsyncMock(return_value="Mocked conversation response")
            mock_conv_class.return_value = mock_conv
            
            chain = AgriculturalReasoningChain(mock_llm_manager)
            return chain
    
    @pytest.fixture
    def sample_query(self):
        """Sample agriculture query"""
        return AgricultureQuery(
            farmer_id="farmer_123",
            query_text="What should I plant this season?",
            query_type="crop_advice",
            language="hindi",
            crop_type="wheat",
            season="rabi"
        )
    
    @pytest.fixture
    def sample_farmer_profile(self):
        """Sample farmer profile"""
        return FarmerProfile(
            name="Test Farmer",
            contact_info=ContactInfo(
                primary_phone="+919876543210",
                preferred_contact_method=CommunicationPreference.WHATSAPP
            ),
            location=Location(
                address=Address(
                    street="Test Village",
                    city="Test City",
                    district="Test District",
                    state="Maharashtra",
                    postal_code="411001",
                    country="India",
                    coordinates=GeographicCoordinate(latitude=18.5204, longitude=73.8567)
                )
            ),
            farm_details=FarmDetails(
                total_land_area=Measurement(value=2.5, unit="acres"),
                soil_type=SoilType.BLACK_COTTON,
                primary_irrigation_source=IrrigationType.DRIP
            ),
            farming_experience=FarmingExperience.INTERMEDIATE
        )
    
    @pytest.fixture
    def sample_agricultural_data(self):
        """Sample agricultural intelligence data"""
        return AgriculturalIntelligence(
            farmer_id="farmer_123",
            location=GeographicCoordinate(latitude=18.5204, longitude=73.8567),
            weather_data=WeatherData(
                location=GeographicCoordinate(latitude=18.5204, longitude=73.8567),
                timestamp=datetime.now(timezone.utc),
                temperature=25.0,
                humidity=65.0,
                wind_speed=10.0,
                rainfall=0.0,
                condition=WeatherCondition.CLEAR
            )
        )
    
    @pytest.mark.asyncio
    async def test_analyze_crop_query(self, reasoning_chain, sample_query, sample_farmer_profile, sample_agricultural_data):
        """Test crop query analysis"""
        response = await reasoning_chain.analyze_crop_query(
            sample_query, sample_farmer_profile, sample_agricultural_data
        )
        
        assert isinstance(response, KnowledgeResponse)
        assert response.response_type == "crop_advice"
        assert response.language == "hindi"
        assert response.confidence_score > 0
    
    @pytest.mark.asyncio
    async def test_analyze_weather_query(self, reasoning_chain, sample_farmer_profile, sample_agricultural_data):
        """Test weather query analysis"""
        query = AgricultureQuery(
            farmer_id="farmer_123",
            query_text="Will it rain tomorrow?",
            query_type="weather",
            language="hindi"
        )
        
        response = await reasoning_chain.analyze_weather_query(
            query, sample_farmer_profile, sample_agricultural_data
        )
        
        assert isinstance(response, KnowledgeResponse)
        assert response.response_type == "weather_analysis"
        assert response.language == "hindi"
    
    @pytest.mark.asyncio
    async def test_analyze_general_query(self, reasoning_chain, sample_farmer_profile):
        """Test general query analysis"""
        query = AgricultureQuery(
            farmer_id="farmer_123",
            query_text="How can I improve my soil health?",
            query_type="general",
            language="hindi"
        )
        
        response = await reasoning_chain.analyze_general_query(
            query, sample_farmer_profile
        )
        
        assert isinstance(response, KnowledgeResponse)
        assert response.response_type == "general_advice"
        assert response.language == "hindi"


class TestKnowledgeReasoningAgent:
    """Test main Knowledge & Reasoning Agent"""
    
    @pytest.fixture
    def mock_agent_dependencies(self):
        """Mock agent dependencies"""
        with patch('src.krishimitra.agents.knowledge_reasoning.BedrockLLMManager') as mock_llm_manager, \
             patch('src.krishimitra.agents.knowledge_reasoning.AgriculturalReasoningChain') as mock_reasoning_chain, \
             patch('src.krishimitra.agents.knowledge_reasoning.ConversationMemoryManager') as mock_memory_manager:
            
            # Mock LLM manager
            mock_llm = Mock()
            mock_llm.test_connection = AsyncMock(return_value=True)
            mock_llm_manager.return_value = mock_llm
            
            # Mock reasoning chain
            mock_chain = Mock()
            mock_response = KnowledgeResponse(
                response_text="Test agricultural advice",
                confidence_score=0.85,
                sources=["Test Source"],
                recommendations=["Test recommendation"],
                language="hindi",
                response_type="crop_advice"
            )
            mock_chain.analyze_crop_query = AsyncMock(return_value=mock_response)
            mock_chain.analyze_weather_query = AsyncMock(return_value=mock_response)
            mock_chain.analyze_market_query = AsyncMock(return_value=mock_response)
            mock_chain.analyze_general_query = AsyncMock(return_value=mock_response)
            mock_reasoning_chain.return_value = mock_chain
            
            # Mock memory manager
            mock_memory = Mock()
            mock_memory.get_conversation_history = Mock(return_value=[])
            mock_memory.clear_memory = Mock()
            mock_memory_manager.return_value = mock_memory
            
            yield {
                'llm_manager': mock_llm,
                'reasoning_chain': mock_chain,
                'memory_manager': mock_memory
            }
    
    @pytest.fixture
    def agent(self, mock_agent_dependencies):
        """Create knowledge reasoning agent with mocked dependencies"""
        return KnowledgeReasoningAgent()
    
    @pytest.fixture
    def sample_query(self):
        """Sample agriculture query"""
        return AgricultureQuery(
            farmer_id="farmer_123",
            query_text="What should I plant this season?",
            query_type="crop_advice",
            language="hindi",
            crop_type="wheat"
        )
    
    @pytest.fixture
    def sample_farmer_profile(self):
        """Sample farmer profile"""
        return FarmerProfile(
            name="Test Farmer",
            contact_info=ContactInfo(
                primary_phone="+919876543210",
                preferred_contact_method=CommunicationPreference.WHATSAPP
            ),
            location=Location(
                address=Address(
                    street="Test Village",
                    city="Test City",
                    district="Test District",
                    state="Maharashtra",
                    postal_code="411001",
                    country="India",
                    coordinates=GeographicCoordinate(latitude=18.5204, longitude=73.8567)
                )
            ),
            farm_details=FarmDetails(
                total_land_area=Measurement(value=2.5, unit="acres"),
                soil_type=SoilType.BLACK_COTTON,
                primary_irrigation_source=IrrigationType.DRIP
            ),
            farming_experience=FarmingExperience.INTERMEDIATE
        )
    
    def test_agent_initialization(self, agent):
        """Test agent initialization"""
        assert agent.llm_manager is not None
        assert agent.reasoning_chain is not None
        assert agent.memory_manager is not None
        assert len(agent.tools) > 0
    
    @pytest.mark.asyncio
    async def test_process_crop_advice_query(self, agent, sample_query, sample_farmer_profile):
        """Test processing crop advice query"""
        response = await agent.process_query(sample_query, sample_farmer_profile)
        
        assert isinstance(response, KnowledgeResponse)
        assert response.response_text is not None
        assert response.confidence_score >= 0
        assert response.language == "hindi"
    
    @pytest.mark.asyncio
    async def test_process_weather_query(self, agent, sample_farmer_profile):
        """Test processing weather query"""
        query = AgricultureQuery(
            farmer_id="farmer_123",
            query_text="Will it rain tomorrow?",
            query_type="weather",
            language="hindi"
        )
        
        response = await agent.process_query(query, sample_farmer_profile)
        
        assert isinstance(response, KnowledgeResponse)
        assert response.language == "hindi"
    
    @pytest.mark.asyncio
    async def test_process_market_query(self, agent, sample_farmer_profile):
        """Test processing market query"""
        query = AgricultureQuery(
            farmer_id="farmer_123",
            query_text="What are current wheat prices?",
            query_type="market",
            language="hindi"
        )
        
        response = await agent.process_query(query, sample_farmer_profile)
        
        assert isinstance(response, KnowledgeResponse)
        assert response.language == "hindi"
    
    @pytest.mark.asyncio
    async def test_process_general_query(self, agent, sample_farmer_profile):
        """Test processing general query"""
        query = AgricultureQuery(
            farmer_id="farmer_123",
            query_text="How can I improve my farming?",
            query_type="general",
            language="hindi"
        )
        
        response = await agent.process_query(query, sample_farmer_profile)
        
        assert isinstance(response, KnowledgeResponse)
        assert response.language == "hindi"
    
    @pytest.mark.asyncio
    async def test_get_conversation_history(self, agent):
        """Test getting conversation history"""
        farmer_id = "farmer_123"
        
        history = await agent.get_conversation_history(farmer_id)
        
        assert isinstance(history, list)
    
    @pytest.mark.asyncio
    async def test_clear_conversation_history(self, agent):
        """Test clearing conversation history"""
        farmer_id = "farmer_123"
        
        result = await agent.clear_conversation_history(farmer_id)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_llm_connection_test(self, agent):
        """Test LLM connection test"""
        result = await agent.test_llm_connection()
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_agent_close(self, agent):
        """Test agent close"""
        await agent.close()
        # Should not raise any exceptions


class TestAgricultureQuery:
    """Test AgricultureQuery model"""
    
    def test_valid_query_creation(self):
        """Test creating valid agriculture query"""
        query = AgricultureQuery(
            farmer_id="farmer_123",
            query_text="What should I plant?",
            query_type="crop_advice",
            language="hindi"
        )
        
        assert query.farmer_id == "farmer_123"
        assert query.query_text == "What should I plant?"
        assert query.query_type == "crop_advice"
        assert query.language == "hindi"
        assert query.urgency == "normal"  # Default value
    
    def test_query_with_optional_fields(self):
        """Test query with optional fields"""
        query = AgricultureQuery(
            farmer_id="farmer_123",
            query_text="What should I plant?",
            query_type="crop_advice",
            language="hindi",
            location={"latitude": 18.5204, "longitude": 73.8567},
            crop_type="wheat",
            season="rabi",
            urgency="high"
        )
        
        assert query.location is not None
        assert query.crop_type == "wheat"
        assert query.season == "rabi"
        assert query.urgency == "high"


class TestKnowledgeResponse:
    """Test KnowledgeResponse model"""
    
    def test_valid_response_creation(self):
        """Test creating valid knowledge response"""
        response = KnowledgeResponse(
            response_text="Plant wheat in November",
            confidence_score=0.85,
            sources=["Agricultural Guidelines"],
            recommendations=["Prepare soil", "Buy seeds"],
            language="hindi",
            response_type="crop_advice"
        )
        
        assert response.response_text == "Plant wheat in November"
        assert response.confidence_score == 0.85
        assert len(response.sources) == 1
        assert len(response.recommendations) == 2
        assert response.language == "hindi"
        assert response.response_type == "crop_advice"
    
    def test_response_with_metadata(self):
        """Test response with metadata"""
        response = KnowledgeResponse(
            response_text="Test response",
            confidence_score=0.9,
            language="hindi",
            response_type="test",
            metadata={"test_key": "test_value", "number": 42}
        )
        
        assert response.metadata["test_key"] == "test_value"
        assert response.metadata["number"] == 42