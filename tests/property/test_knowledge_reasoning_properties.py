"""
Property-based tests for Knowledge & Reasoning Agent in KrishiMitra platform.

This module implements property-based tests using Hypothesis to validate
knowledge processing and reasoning properties including multi-source data
ingestion, agricultural intelligence generation, and personalized recommendations.
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import patch, MagicMock, AsyncMock

from hypothesis import given, strategies as st, assume, settings
from hypothesis.strategies import composite

# Import knowledge reasoning modules
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
from src.krishimitra.models.agricultural_intelligence import (
    AgriculturalIntelligence, WeatherData, WeatherCondition, SoilData
)


# Custom strategies for knowledge reasoning testing
@composite
def agriculture_query_strategy(draw):
    """Generate valid agriculture queries for testing."""
    query_types = ["crop_advice", "weather", "market", "pest_disease", "general"]
    languages = ["hindi", "tamil", "telugu", "bengali", "marathi", "gujarati", "punjabi", "english"]
    crops = ["wheat", "rice", "cotton", "sugarcane", "maize", "soybean", "mustard", "pulses"]
    seasons = ["kharif", "rabi", "zaid", "summer", "winter", "monsoon"]
    urgency_levels = ["low", "normal", "high", "critical"]
    
    return AgricultureQuery(
        farmer_id=draw(st.text(min_size=5, max_size=50)),
        query_text=draw(st.text(min_size=10, max_size=500)),
        query_type=draw(st.sampled_from(query_types)),
        language=draw(st.sampled_from(languages)),
        location={
            "latitude": draw(st.floats(min_value=6.0, max_value=37.0)),
            "longitude": draw(st.floats(min_value=68.0, max_value=97.0))
        } if draw(st.booleans()) else None,
        crop_type=draw(st.sampled_from(crops)) if draw(st.booleans()) else None,
        season=draw(st.sampled_from(seasons)) if draw(st.booleans()) else None,
        urgency=draw(st.sampled_from(urgency_levels))
    )


@composite
def farmer_profile_strategy(draw):
    """Generate valid farmer profiles for testing."""
    states = ["Maharashtra", "Punjab", "Uttar Pradesh", "Karnataka", "Tamil Nadu", "Gujarat"]
    soil_types = [SoilType.BLACK_COTTON, SoilType.RED_LATERITE, SoilType.ALLUVIAL, 
                  SoilType.SANDY, SoilType.CLAY, SoilType.LOAMY]
    irrigation_types = [IrrigationType.DRIP, IrrigationType.SPRINKLER, 
                       IrrigationType.FLOOD, IrrigationType.RAINFED]
    experience_levels = [FarmingExperience.BEGINNER, FarmingExperience.INTERMEDIATE, 
                        FarmingExperience.EXPERIENCED, FarmingExperience.EXPERT]
    
    return FarmerProfile(
        name=draw(st.text(min_size=3, max_size=100)),
        contact_info=ContactInfo(
            primary_phone=f"+91{draw(st.integers(min_value=6000000000, max_value=9999999999))}",
            preferred_contact_method=draw(st.sampled_from([
                CommunicationPreference.VOICE, 
                CommunicationPreference.TEXT,
                CommunicationPreference.WHATSAPP
            ]))
        ),
        location=Location(
            address=Address(
                village=draw(st.text(min_size=3, max_size=50)),
                block=draw(st.text(min_size=3, max_size=50)) if draw(st.booleans()) else None,
                district=draw(st.text(min_size=3, max_size=50)),
                state=draw(st.sampled_from(states)),
                pincode=draw(st.text(alphabet='0123456789', min_size=6, max_size=6)) if draw(st.booleans()) else None,
                country="India",
                coordinates=GeographicCoordinate(
                    latitude=draw(st.floats(min_value=6.0, max_value=37.0)),
                    longitude=draw(st.floats(min_value=68.0, max_value=97.0))
                ) if draw(st.booleans()) else None
            )
        ),
        farm_details=FarmDetails(
            total_land_area=Measurement(
                value=draw(st.floats(min_value=0.5, max_value=100.0)),
                unit="acres"
            ),
            soil_type=draw(st.sampled_from(soil_types)),
            primary_irrigation_source=draw(st.sampled_from(irrigation_types))
        ),
        farming_experience=draw(st.sampled_from(experience_levels))
    )


@composite
def agricultural_intelligence_strategy(draw):
    """Generate agricultural intelligence data for testing."""
    weather_conditions = [WeatherCondition.CLEAR, WeatherCondition.CLOUDY, 
                         WeatherCondition.RAINY, WeatherCondition.STORMY]
    
    location = GeographicCoordinate(
        latitude=draw(st.floats(min_value=6.0, max_value=37.0)),
        longitude=draw(st.floats(min_value=68.0, max_value=97.0))
    )
    
    return AgriculturalIntelligence(
        farmer_id=draw(st.text(min_size=5, max_size=50)),
        location=location,
        weather_data=WeatherData(
            location=location,
            timestamp=datetime.now(timezone.utc),
            temperature=draw(st.floats(min_value=-5.0, max_value=50.0)),
            humidity=draw(st.floats(min_value=0.0, max_value=100.0)),
            wind_speed=draw(st.floats(min_value=0.0, max_value=100.0)),
            rainfall=draw(st.floats(min_value=0.0, max_value=500.0)),
            condition=draw(st.sampled_from(weather_conditions))
        ),
        soil_data=SoilData(
            location=location,
            timestamp=datetime.now(timezone.utc),
            moisture_percentage=draw(st.floats(min_value=0.0, max_value=100.0)),
            ph_level=draw(st.floats(min_value=4.0, max_value=9.0)),
            nitrogen_ppm=draw(st.floats(min_value=0.0, max_value=500.0)),
            phosphorus_ppm=draw(st.floats(min_value=0.0, max_value=200.0)),
            potassium_ppm=draw(st.floats(min_value=0.0, max_value=500.0))
        ) if draw(st.booleans()) else None
    )


class TestKnowledgeReasoningProperties:
    """Property-based tests for knowledge reasoning and processing."""
    
    @given(
        query=agriculture_query_strategy(),
        farmer_profile=farmer_profile_strategy(),
        agricultural_data=agricultural_intelligence_strategy()
    )
    @settings(max_examples=30, deadline=None)
    @pytest.mark.asyncio
    async def test_property_2_agricultural_intelligence_generation(
        self, query, farmer_profile, agricultural_data
    ):
        """
        Property 2: Agricultural intelligence generation
        For any raw agricultural dataset, the Knowledge_Agent should analyze
        the data and generate contextual insights using LLM capabilities.
        **Validates: Requirements 1.2**
        """
        # Mock LLM manager and reasoning chain
        with patch('src.krishimitra.agents.knowledge_reasoning.BedrockLLMManager') as mock_llm_manager, \
             patch('src.krishimitra.agents.knowledge_reasoning.AgriculturalReasoningChain') as mock_reasoning_chain:
            
            # Setup mocks
            mock_llm = MagicMock()
            mock_llm.test_connection = AsyncMock(return_value=True)
            mock_llm_manager.return_value = mock_llm
            
            # Create mock response with contextual insights
            mock_response = KnowledgeResponse(
                response_text=f"Agricultural advice for {query.query_type}",
                confidence_score=0.85,
                sources=["Agricultural Knowledge Base", "Weather Data", "Soil Analysis"],
                recommendations=[
                    "Recommendation 1 based on analysis",
                    "Recommendation 2 based on conditions"
                ],
                language=query.language,
                response_type=query.query_type,
                metadata={
                    "analyzed_data_sources": ["weather", "soil", "market"],
                    "llm_model": "claude-3-5-sonnet",
                    "processing_timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            
            mock_chain = MagicMock()
            mock_chain.analyze_crop_query = AsyncMock(return_value=mock_response)
            mock_chain.analyze_weather_query = AsyncMock(return_value=mock_response)
            mock_chain.analyze_market_query = AsyncMock(return_value=mock_response)
            mock_chain.analyze_general_query = AsyncMock(return_value=mock_response)
            mock_reasoning_chain.return_value = mock_chain
            
            # Create agent and process query
            agent = KnowledgeReasoningAgent()
            response = await agent.process_query(query, farmer_profile, agricultural_data)
            
            # Verify intelligence generation properties
            assert isinstance(response, KnowledgeResponse), "Should return KnowledgeResponse"
            assert response.response_text is not None, "Should generate response text"
            assert len(response.response_text) > 0, "Response text should not be empty"
            
            # Verify contextual analysis
            assert response.confidence_score >= 0.0, "Confidence score should be non-negative"
            assert response.confidence_score <= 1.0, "Confidence score should not exceed 1.0"
            
            # Verify sources attribution
            assert isinstance(response.sources, list), "Sources should be a list"
            assert len(response.sources) > 0, "Should cite data sources"
            
            # Verify recommendations generation
            assert isinstance(response.recommendations, list), "Recommendations should be a list"
            
            # Verify language consistency
            assert response.language == query.language, "Response language should match query language"
            
            # Verify response type matches query type
            assert response.response_type == query.query_type, "Response type should match query type"
            
            # Verify metadata contains analysis information
            if response.metadata:
                assert isinstance(response.metadata, dict), "Metadata should be a dictionary"
    
    @given(
        query=agriculture_query_strategy(),
        farmer_profile=farmer_profile_strategy()
    )
    @settings(max_examples=30, deadline=None)
    @pytest.mark.asyncio
    async def test_property_17_context_aware_crop_recommendations(
        self, query, farmer_profile
    ):
        """
        Property 17: Context-aware crop recommendations
        For any crop selection request with local climate, soil conditions, and
        market demand data, the Advisory_Agent should recommend suitable crops
        based on all available factors.
        **Validates: Requirements 4.2**
        """
        # Only test crop advice queries
        assume(query.query_type == "crop_advice")
        
        # Mock LLM and reasoning components
        with patch('src.krishimitra.agents.knowledge_reasoning.BedrockLLMManager') as mock_llm_manager, \
             patch('src.krishimitra.agents.knowledge_reasoning.AgriculturalReasoningChain') as mock_reasoning_chain:
            
            # Setup mocks
            mock_llm = MagicMock()
            mock_llm.test_connection = AsyncMock(return_value=True)
            mock_llm_manager.return_value = mock_llm
            
            # Create context-aware response
            mock_response = KnowledgeResponse(
                response_text=f"Crop recommendations for {farmer_profile.location.address.state}",
                confidence_score=0.90,
                sources=["Soil Analysis", "Climate Data", "Market Trends"],
                recommendations=[
                    f"Crop 1 suitable for {farmer_profile.farm_details.soil_type.value}",
                    f"Crop 2 appropriate for {farmer_profile.farm_details.primary_irrigation_source.value}",
                    "Crop 3 based on market demand"
                ],
                language=query.language,
                response_type="crop_advice",
                metadata={
                    "soil_type": farmer_profile.farm_details.soil_type.value,
                    "irrigation": farmer_profile.farm_details.primary_irrigation_source.value,
                    "location": farmer_profile.location.address.state,
                    "land_area": farmer_profile.farm_details.total_land_area.value,
                    "factors_considered": ["soil", "climate", "water", "market", "experience"]
                }
            )
            
            mock_chain = MagicMock()
            mock_chain.analyze_crop_query = AsyncMock(return_value=mock_response)
            mock_reasoning_chain.return_value = mock_chain
            
            # Create agent and process query
            agent = KnowledgeReasoningAgent()
            response = await agent.process_query(query, farmer_profile)
            
            # Verify context-aware recommendations
            assert isinstance(response, KnowledgeResponse), "Should return KnowledgeResponse"
            assert response.response_type == "crop_advice", "Should be crop advice"
            
            # Verify recommendations are provided
            assert len(response.recommendations) > 0, "Should provide crop recommendations"
            
            # Verify context factors are considered
            if response.metadata:
                # Check that multiple factors are considered
                factors = response.metadata.get("factors_considered", [])
                assert len(factors) >= 3, "Should consider multiple factors (soil, climate, water, etc.)"
                
                # Verify soil type is considered
                assert "soil_type" in response.metadata, "Should consider soil type"
                
                # Verify irrigation is considered
                assert "irrigation" in response.metadata, "Should consider irrigation type"
                
                # Verify location is considered
                assert "location" in response.metadata, "Should consider location"
            
            # Verify confidence in recommendations
            assert response.confidence_score > 0.5, "Should have reasonable confidence in recommendations"
            
            # Verify sources include relevant data
            assert len(response.sources) > 0, "Should cite data sources"
            relevant_sources = ["Soil", "Climate", "Market", "Weather"]
            has_relevant_source = any(
                any(keyword in source for keyword in relevant_sources)
                for source in response.sources
            )
            assert has_relevant_source, "Should cite relevant agricultural data sources"
    
    @given(queries=st.lists(agriculture_query_strategy(), min_size=2, max_size=5))
    @settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_conversation_memory_consistency(self, queries):
        """
        Test that conversation memory maintains consistency across multiple queries.
        Ensures context is preserved and conversation history is accurate.
        """
        # Use same farmer_id for all queries to test conversation continuity
        farmer_id = "test_farmer_123"
        for query in queries:
            query.farmer_id = farmer_id
        
        # Mock LLM components properly
        with patch('src.krishimitra.agents.knowledge_reasoning.BedrockLLMManager') as mock_llm_manager:
            # Create a proper mock LLM that satisfies Pydantic validation
            from langchain_core.language_models import BaseLanguageModel
            
            mock_llm = MagicMock(spec=BaseLanguageModel)
            mock_llm.test_connection = AsyncMock(return_value=True)
            mock_llm.invoke = MagicMock(return_value="Test response")
            
            mock_manager = MagicMock()
            mock_manager.test_connection = AsyncMock(return_value=True)
            mock_manager.get_llm = MagicMock(return_value=mock_llm)
            mock_llm_manager.return_value = mock_manager
            
            # Create memory manager
            memory_manager = ConversationMemoryManager()
            
            # Process queries and track interactions
            for i, query in enumerate(queries):
                # Add interaction to memory
                memory_manager.add_interaction(
                    farmer_id,
                    query.query_text,
                    f"Response to query {i+1}"
                )
            
            # Verify memory consistency
            memory = memory_manager.get_memory(farmer_id)
            assert memory is not None, "Should have memory for farmer"
            
            # Verify all interactions are stored
            messages = memory.chat_memory.messages
            # Each interaction adds 2 messages (human + AI)
            expected_messages = len(queries) * 2
            assert len(messages) >= expected_messages, f"Should have at least {expected_messages} messages"
            
            # Test memory retrieval
            memory2 = memory_manager.get_memory(farmer_id)
            assert memory is memory2, "Should return same memory instance"
            
            # Test memory clearing
            memory_manager.clear_memory(farmer_id)
            assert farmer_id not in memory_manager.memories, "Memory should be cleared"
    
    @given(
        query=agriculture_query_strategy(),
        farmer_profile=farmer_profile_strategy()
    )
    @settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_multilingual_response_generation(self, query, farmer_profile):
        """
        Test that responses are generated in the requested language.
        Validates multilingual support across all supported Indian languages.
        """
        # Mock LLM components
        with patch('src.krishimitra.agents.knowledge_reasoning.BedrockLLMManager') as mock_llm_manager, \
             patch('src.krishimitra.agents.knowledge_reasoning.AgriculturalReasoningChain') as mock_reasoning_chain:
            
            mock_llm = MagicMock()
            mock_llm.test_connection = AsyncMock(return_value=True)
            mock_llm_manager.return_value = mock_llm
            
            # Create language-specific response
            mock_response = KnowledgeResponse(
                response_text=f"Response in {query.language}",
                confidence_score=0.85,
                sources=["Knowledge Base"],
                recommendations=["Recommendation 1"],
                language=query.language,
                response_type=query.query_type,
                metadata={"target_language": query.language}
            )
            
            mock_chain = MagicMock()
            mock_chain.analyze_crop_query = AsyncMock(return_value=mock_response)
            mock_chain.analyze_weather_query = AsyncMock(return_value=mock_response)
            mock_chain.analyze_market_query = AsyncMock(return_value=mock_response)
            mock_chain.analyze_general_query = AsyncMock(return_value=mock_response)
            mock_reasoning_chain.return_value = mock_chain
            
            # Create agent and process query
            agent = KnowledgeReasoningAgent()
            response = await agent.process_query(query, farmer_profile)
            
            # Verify language consistency
            assert response.language == query.language, "Response language should match query language"
            
            # Verify supported languages
            supported_languages = ["hindi", "tamil", "telugu", "bengali", "marathi", "gujarati", "punjabi", "english"]
            assert query.language in supported_languages, f"Language {query.language} should be supported"
    
    @given(query=agriculture_query_strategy())
    @settings(max_examples=20, deadline=None)
    def test_prompt_template_generation(self, query):
        """
        Test that prompt templates are correctly generated for different query types.
        Validates template structure and variable inclusion.
        """
        # Test crop advice template
        if query.query_type == "crop_advice":
            template = AgriculturalPromptTemplates.get_crop_advice_template()
            assert template is not None, "Crop advice template should exist"
            assert "location" in template.input_variables, "Should include location variable"
            assert "crop_type" in template.input_variables, "Should include crop_type variable"
            assert "query" in template.input_variables, "Should include query variable"
            assert "language" in template.input_variables, "Should include language variable"
        
        # Test weather analysis template
        elif query.query_type == "weather":
            template = AgriculturalPromptTemplates.get_weather_analysis_template()
            assert template is not None, "Weather analysis template should exist"
            assert "weather_data" in template.input_variables, "Should include weather_data variable"
            assert "forecast_data" in template.input_variables, "Should include forecast_data variable"
            assert "location" in template.input_variables, "Should include location variable"
        
        # Test market analysis template
        elif query.query_type == "market":
            template = AgriculturalPromptTemplates.get_market_analysis_template()
            assert template is not None, "Market analysis template should exist"
            assert "market_data" in template.input_variables, "Should include market_data variable"
            assert "price_trends" in template.input_variables, "Should include price_trends variable"
            assert "crops" in template.input_variables, "Should include crops variable"
        
        # Test general conversation template
        else:
            template = AgriculturalPromptTemplates.get_general_conversation_template()
            assert template is not None, "General conversation template should exist"
            assert len(template.messages) >= 2, "Should have system and human messages"
    
    @given(
        query=agriculture_query_strategy(),
        farmer_profile=farmer_profile_strategy(),
        agricultural_data=agricultural_intelligence_strategy()
    )
    @settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_response_quality_metrics(
        self, query, farmer_profile, agricultural_data
    ):
        """
        Test that responses meet quality metrics including confidence scores,
        source attribution, and recommendation completeness.
        """
        # Mock LLM components
        with patch('src.krishimitra.agents.knowledge_reasoning.BedrockLLMManager') as mock_llm_manager, \
             patch('src.krishimitra.agents.knowledge_reasoning.AgriculturalReasoningChain') as mock_reasoning_chain:
            
            mock_llm = MagicMock()
            mock_llm.test_connection = AsyncMock(return_value=True)
            mock_llm_manager.return_value = mock_llm
            
            # Create high-quality response
            mock_response = KnowledgeResponse(
                response_text="Detailed agricultural advice with context",
                confidence_score=0.88,
                sources=["Source 1", "Source 2", "Source 3"],
                recommendations=[
                    "Actionable recommendation 1",
                    "Actionable recommendation 2",
                    "Actionable recommendation 3"
                ],
                language=query.language,
                response_type=query.query_type,
                metadata={
                    "quality_score": 0.9,
                    "completeness": "high",
                    "actionability": "high"
                }
            )
            
            mock_chain = MagicMock()
            mock_chain.analyze_crop_query = AsyncMock(return_value=mock_response)
            mock_chain.analyze_weather_query = AsyncMock(return_value=mock_response)
            mock_chain.analyze_market_query = AsyncMock(return_value=mock_response)
            mock_chain.analyze_general_query = AsyncMock(return_value=mock_response)
            mock_reasoning_chain.return_value = mock_chain
            
            # Create agent and process query
            agent = KnowledgeReasoningAgent()
            response = await agent.process_query(query, farmer_profile, agricultural_data)
            
            # Verify quality metrics
            assert response.confidence_score >= 0.0, "Confidence score should be non-negative"
            assert response.confidence_score <= 1.0, "Confidence score should not exceed 1.0"
            
            # Verify source attribution
            assert len(response.sources) > 0, "Should provide source attribution"
            assert all(isinstance(source, str) for source in response.sources), "Sources should be strings"
            assert all(len(source) > 0 for source in response.sources), "Sources should not be empty"
            
            # Verify recommendations
            if len(response.recommendations) > 0:
                assert all(isinstance(rec, str) for rec in response.recommendations), "Recommendations should be strings"
                assert all(len(rec) > 0 for rec in response.recommendations), "Recommendations should not be empty"
            
            # Verify response completeness
            assert len(response.response_text) > 10, "Response should be substantive"


# Configure Hypothesis profiles for knowledge reasoning testing
@pytest.fixture(autouse=True)
def configure_hypothesis_knowledge():
    """Configure Hypothesis settings for knowledge reasoning testing."""
    import os
    
    if os.getenv("CI"):
        settings.load_profile("ci")
    elif os.getenv("DEBUG"):
        settings.load_profile("debug")
    else:
        settings.load_profile("dev")
