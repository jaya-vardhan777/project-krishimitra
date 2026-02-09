"""
Knowledge & Reasoning Agent for KrishiMitra Platform

This module implements the Knowledge & Reasoning Agent responsible for processing
agricultural knowledge using LLM capabilities through Amazon Bedrock and LangChain.
Provides contextual analysis, evidence-based recommendations, and agricultural reasoning.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field, validator

# LangChain imports
from langchain_aws import BedrockLLM, ChatBedrock
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.chains import LLMChain, ConversationChain
from langchain.memory import ConversationBufferMemory, ConversationSummaryBufferMemory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_core.callbacks import BaseCallbackHandler
from pydantic import BaseModel as LangChainBaseModel

from ..core.config import get_settings
from ..models.agricultural_intelligence import AgriculturalIntelligence, WeatherData, SoilData, MarketData
from ..models.farmer import FarmerProfile
from ..models.recommendation import RecommendationRecord

logger = logging.getLogger(__name__)
settings = get_settings()


class AgricultureQuery(BaseModel):
    """Model for agricultural queries"""
    
    farmer_id: str = Field(description="Farmer ID")
    query_text: str = Field(description="Query text from farmer")
    query_type: str = Field(description="Type of query (crop_advice, weather, market, etc.)")
    language: str = Field(default="hindi", description="Query language")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    location: Optional[Dict[str, float]] = Field(default=None, description="Location coordinates")
    crop_type: Optional[str] = Field(default=None, description="Relevant crop type")
    season: Optional[str] = Field(default=None, description="Current season")
    urgency: str = Field(default="normal", description="Query urgency level")


class KnowledgeResponse(BaseModel):
    """Model for knowledge agent responses"""
    
    response_text: str = Field(description="Response text")
    confidence_score: float = Field(ge=0, le=1, description="Confidence in the response")
    sources: List[str] = Field(default_factory=list, description="Knowledge sources used")
    recommendations: List[str] = Field(default_factory=list, description="Specific recommendations")
    follow_up_questions: List[str] = Field(default_factory=list, description="Suggested follow-up questions")
    language: str = Field(description="Response language")
    response_type: str = Field(description="Type of response")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class BedrockLLMManager:
    """Manages Amazon Bedrock LLM connections and configurations"""
    
    def __init__(self):
        self.bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=settings.bedrock_region
        )
        self.model_id = settings.bedrock_model_id
        self.llm = None
        self.chat_model = None
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize Bedrock LLM models"""
        try:
            # Initialize standard LLM for text completion
            self.llm = BedrockLLM(
                client=self.bedrock_client,
                model_id=self.model_id,
                model_kwargs={
                    "max_tokens": 2000,
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "stop_sequences": ["\n\nHuman:", "\n\nAssistant:"]
                }
            )
            
            # Initialize chat model for conversational interactions
            self.chat_model = ChatBedrock(
                client=self.bedrock_client,
                model_id=self.model_id,
                model_kwargs={
                    "max_tokens": 2000,
                    "temperature": 0.3,
                    "top_p": 0.9
                }
            )
            
            logger.info(f"Initialized Bedrock models with ID: {self.model_id}")
            
        except Exception as e:
            logger.error(f"Error initializing Bedrock models: {e}")
            raise
    
    def get_llm(self) -> BedrockLLM:
        """Get the standard LLM instance"""
        return self.llm
    
    def get_chat_model(self) -> ChatBedrock:
        """Get the chat model instance"""
        return self.chat_model
    
    async def test_connection(self) -> bool:
        """Test Bedrock connection"""
        try:
            response = self.llm.invoke("Test connection")
            logger.info("Bedrock connection test successful")
            return True
        except Exception as e:
            logger.error(f"Bedrock connection test failed: {e}")
            return False


class AgriculturalPromptTemplates:
    """Collection of prompt templates for agricultural queries"""
    
    @staticmethod
    def get_crop_advice_template() -> PromptTemplate:
        """Template for crop advice queries"""
        template = """
You are an expert agricultural advisor for Indian farmers. Provide practical, actionable advice based on the farmer's context.

Farmer Information:
- Location: {location}
- Crop: {crop_type}
- Season: {season}
- Soil Type: {soil_type}
- Farm Size: {farm_size}

Current Conditions:
- Weather: {weather_conditions}
- Soil Status: {soil_conditions}
- Market Prices: {market_conditions}

Farmer's Question: {query}

Please provide:
1. Direct answer to the farmer's question
2. Specific actionable recommendations
3. Timeline for implementation
4. Expected outcomes
5. Any warnings or precautions

Respond in {language} language. Keep the advice practical and suitable for small-scale farmers.

Answer:"""
        
        return PromptTemplate(
            template=template,
            input_variables=[
                "location", "crop_type", "season", "soil_type", "farm_size",
                "weather_conditions", "soil_conditions", "market_conditions",
                "query", "language"
            ]
        )
    
    @staticmethod
    def get_weather_analysis_template() -> PromptTemplate:
        """Template for weather analysis and recommendations"""
        template = """
You are a meteorological expert specializing in agricultural weather analysis for Indian farming conditions.

Current Weather Data:
{weather_data}

Forecast Data:
{forecast_data}

Farmer Context:
- Location: {location}
- Current Crops: {crops}
- Growth Stage: {growth_stage}
- Irrigation: {irrigation_type}

Analyze the weather conditions and provide:
1. Impact on current crops
2. Immediate actions needed (next 24-48 hours)
3. Weekly planning recommendations
4. Risk assessment (drought, flood, pest, disease)
5. Irrigation scheduling advice

Respond in {language}. Focus on actionable insights for the farmer.

Analysis:"""
        
        return PromptTemplate(
            template=template,
            input_variables=[
                "weather_data", "forecast_data", "location", "crops",
                "growth_stage", "irrigation_type", "language"
            ]
        )
    
    @staticmethod
    def get_market_analysis_template() -> PromptTemplate:
        """Template for market analysis and pricing insights"""
        template = """
You are a market analyst specializing in Indian agricultural commodities and pricing.

Market Data:
{market_data}

Price Trends:
{price_trends}

Farmer Context:
- Crops: {crops}
- Expected Harvest: {harvest_timeline}
- Storage Capacity: {storage_capacity}
- Transportation: {transportation_options}

Provide market analysis including:
1. Current price assessment (good/fair/poor)
2. Price trend prediction (next 2-4 weeks)
3. Best selling strategy
4. Storage vs immediate sale recommendation
5. Alternative market options

Respond in {language}. Focus on maximizing farmer income.

Market Analysis:"""
        
        return PromptTemplate(
            template=template,
            input_variables=[
                "market_data", "price_trends", "crops", "harvest_timeline",
                "storage_capacity", "transportation_options", "language"
            ]
        )
    
    @staticmethod
    def get_pest_disease_template() -> PromptTemplate:
        """Template for pest and disease management"""
        template = """
You are a plant pathologist and entomologist expert in Indian crop protection.

Problem Description:
{problem_description}

Crop Information:
- Crop: {crop_type}
- Variety: {crop_variety}
- Growth Stage: {growth_stage}
- Area Affected: {affected_area}

Environmental Conditions:
- Weather: {weather_conditions}
- Soil: {soil_conditions}
- Previous Treatments: {previous_treatments}

Provide comprehensive pest/disease management:
1. Problem identification and confirmation
2. Immediate control measures (next 24-48 hours)
3. Organic/biological control options (prioritize these)
4. Chemical control (only if necessary, with safety precautions)
5. Prevention strategies for future
6. Monitoring schedule

Respond in {language}. Prioritize sustainable and safe methods.

Management Plan:"""
        
        return PromptTemplate(
            template=template,
            input_variables=[
                "problem_description", "crop_type", "crop_variety", "growth_stage",
                "affected_area", "weather_conditions", "soil_conditions",
                "previous_treatments", "language"
            ]
        )
    
    @staticmethod
    def get_general_conversation_template() -> ChatPromptTemplate:
        """Template for general agricultural conversations"""
        system_message = SystemMessagePromptTemplate.from_template(
            """You are KrishiMitra (कृषि मित्र), an AI agricultural advisor for Indian farmers. 
            You provide practical, evidence-based advice in a friendly and supportive manner.
            
            Key principles:
            - Always prioritize farmer safety and sustainable practices
            - Provide actionable, specific advice
            - Consider local Indian farming conditions and practices
            - Respect traditional knowledge while introducing modern techniques
            - Be encouraging and supportive
            - Ask clarifying questions when needed
            
            Respond in {language} language unless specified otherwise."""
        )
        
        human_message = HumanMessagePromptTemplate.from_template(
            """Farmer's question: {query}
            
            Context:
            - Location: {location}
            - Farmer profile: {farmer_context}
            - Current conditions: {current_conditions}
            
            Please provide helpful advice."""
        )
        
        return ChatPromptTemplate.from_messages([system_message, human_message])


class ConversationMemoryManager:
    """Manages conversation memory for farmers"""
    
    def __init__(self):
        self.memories: Dict[str, ConversationSummaryBufferMemory] = {}
        self.llm_manager = BedrockLLMManager()
    
    def get_memory(self, farmer_id: str) -> ConversationSummaryBufferMemory:
        """Get or create conversation memory for a farmer"""
        if farmer_id not in self.memories:
            self.memories[farmer_id] = ConversationSummaryBufferMemory(
                llm=self.llm_manager.get_llm(),
                max_token_limit=1000,
                return_messages=True
            )
        return self.memories[farmer_id]
    
    def add_interaction(self, farmer_id: str, human_message: str, ai_message: str):
        """Add an interaction to farmer's memory"""
        memory = self.get_memory(farmer_id)
        memory.chat_memory.add_user_message(human_message)
        memory.chat_memory.add_ai_message(ai_message)
    
    def get_conversation_history(self, farmer_id: str) -> List[BaseMessage]:
        """Get conversation history for a farmer"""
        memory = self.get_memory(farmer_id)
        return memory.chat_memory.messages
    
    def clear_memory(self, farmer_id: str):
        """Clear conversation memory for a farmer"""
        if farmer_id in self.memories:
            del self.memories[farmer_id]


class AgriculturalReasoningChain:
    """LangChain chain for agricultural reasoning and analysis"""
    
    def __init__(self, llm_manager: BedrockLLMManager):
        self.llm_manager = llm_manager
        self.templates = AgriculturalPromptTemplates()
        self.memory_manager = ConversationMemoryManager()
        self._initialize_chains()
    
    def _initialize_chains(self):
        """Initialize various LangChain chains"""
        try:
            # Crop advice chain
            self.crop_advice_chain = LLMChain(
                llm=self.llm_manager.get_llm(),
                prompt=self.templates.get_crop_advice_template(),
                verbose=True
            )
            
            # Weather analysis chain
            self.weather_analysis_chain = LLMChain(
                llm=self.llm_manager.get_llm(),
                prompt=self.templates.get_weather_analysis_template(),
                verbose=True
            )
            
            # Market analysis chain
            self.market_analysis_chain = LLMChain(
                llm=self.llm_manager.get_llm(),
                prompt=self.templates.get_market_analysis_template(),
                verbose=True
            )
            
            # Pest/disease management chain
            self.pest_disease_chain = LLMChain(
                llm=self.llm_manager.get_llm(),
                prompt=self.templates.get_pest_disease_template(),
                verbose=True
            )
            
            logger.info("Initialized agricultural reasoning chains")
            
        except Exception as e:
            logger.error(f"Error initializing reasoning chains: {e}")
            raise
    
    async def analyze_crop_query(
        self,
        query: AgricultureQuery,
        farmer_profile: FarmerProfile,
        agricultural_data: AgriculturalIntelligence
    ) -> KnowledgeResponse:
        """Analyze crop-related queries"""
        try:
            # Prepare context data
            context = self._prepare_crop_context(farmer_profile, agricultural_data)
            
            # Run the chain
            response = await self.crop_advice_chain.arun(
                location=f"{farmer_profile.location.address.district}, {farmer_profile.location.address.state}",
                crop_type=query.crop_type or "general",
                season=query.season or "current",
                soil_type=farmer_profile.farm_details.soil_type.value,
                farm_size=f"{farmer_profile.farm_details.total_land_area.value} {farmer_profile.farm_details.total_land_area.unit}",
                weather_conditions=context.get("weather", "Not available"),
                soil_conditions=context.get("soil", "Not available"),
                market_conditions=context.get("market", "Not available"),
                query=query.query_text,
                language=query.language
            )
            
            return KnowledgeResponse(
                response_text=response,
                confidence_score=0.85,
                sources=["Agricultural Knowledge Base", "Crop Management Guidelines"],
                recommendations=self._extract_recommendations(response),
                language=query.language,
                response_type="crop_advice",
                metadata={"query_type": query.query_type, "crop": query.crop_type}
            )
            
        except Exception as e:
            logger.error(f"Error in crop query analysis: {e}")
            return self._create_error_response(query, str(e))
    
    async def analyze_weather_query(
        self,
        query: AgricultureQuery,
        farmer_profile: FarmerProfile,
        agricultural_data: AgriculturalIntelligence
    ) -> KnowledgeResponse:
        """Analyze weather-related queries"""
        try:
            # Prepare weather context
            weather_context = self._prepare_weather_context(agricultural_data)
            
            response = await self.weather_analysis_chain.arun(
                weather_data=weather_context.get("current", "Not available"),
                forecast_data=weather_context.get("forecast", "Not available"),
                location=f"{farmer_profile.location.address.district}, {farmer_profile.location.address.state}",
                crops=self._get_current_crops(farmer_profile),
                growth_stage="Current stage",  # This would come from crop monitoring
                irrigation_type=farmer_profile.farm_details.primary_irrigation_source.value,
                language=query.language
            )
            
            return KnowledgeResponse(
                response_text=response,
                confidence_score=0.90,
                sources=["Weather Data", "Meteorological Analysis"],
                recommendations=self._extract_recommendations(response),
                language=query.language,
                response_type="weather_analysis",
                metadata={"query_type": query.query_type}
            )
            
        except Exception as e:
            logger.error(f"Error in weather query analysis: {e}")
            return self._create_error_response(query, str(e))
    
    async def analyze_market_query(
        self,
        query: AgricultureQuery,
        farmer_profile: FarmerProfile,
        agricultural_data: AgriculturalIntelligence
    ) -> KnowledgeResponse:
        """Analyze market-related queries"""
        try:
            # Prepare market context
            market_context = self._prepare_market_context(agricultural_data)
            
            response = await self.market_analysis_chain.arun(
                market_data=market_context.get("current_prices", "Not available"),
                price_trends=market_context.get("trends", "Not available"),
                crops=self._get_current_crops(farmer_profile),
                harvest_timeline="Upcoming harvest",  # This would come from crop calendar
                storage_capacity="Limited",  # This would come from farm details
                transportation_options="Local transport",  # This would come from location data
                language=query.language
            )
            
            return KnowledgeResponse(
                response_text=response,
                confidence_score=0.80,
                sources=["Market Data", "Price Analysis"],
                recommendations=self._extract_recommendations(response),
                language=query.language,
                response_type="market_analysis",
                metadata={"query_type": query.query_type}
            )
            
        except Exception as e:
            logger.error(f"Error in market query analysis: {e}")
            return self._create_error_response(query, str(e))
    
    async def analyze_general_query(
        self,
        query: AgricultureQuery,
        farmer_profile: FarmerProfile,
        agricultural_data: Optional[AgriculturalIntelligence] = None
    ) -> KnowledgeResponse:
        """Analyze general agricultural queries using conversation chain"""
        try:
            # Get conversation memory
            memory = self.memory_manager.get_memory(query.farmer_id)
            
            # Create conversation chain
            conversation_chain = ConversationChain(
                llm=self.llm_manager.get_chat_model(),
                memory=memory,
                verbose=True
            )
            
            # Prepare context
            farmer_context = self._prepare_farmer_context(farmer_profile)
            current_conditions = self._prepare_current_conditions(agricultural_data)
            
            # Format the query with context
            formatted_query = f"""
            Farmer's question: {query.query_text}
            
            Context:
            - Location: {farmer_profile.location.address.district}, {farmer_profile.location.address.state}
            - Farmer profile: {farmer_context}
            - Current conditions: {current_conditions}
            
            Please provide helpful advice in {query.language} language.
            """
            
            response = await conversation_chain.arun(input=formatted_query)
            
            # Add to memory
            self.memory_manager.add_interaction(
                query.farmer_id,
                query.query_text,
                response
            )
            
            return KnowledgeResponse(
                response_text=response,
                confidence_score=0.75,
                sources=["Agricultural Knowledge Base", "Conversation Context"],
                recommendations=self._extract_recommendations(response),
                language=query.language,
                response_type="general_advice",
                metadata={"query_type": query.query_type}
            )
            
        except Exception as e:
            logger.error(f"Error in general query analysis: {e}")
            return self._create_error_response(query, str(e))
    
    def _prepare_crop_context(self, farmer_profile: FarmerProfile, agricultural_data: AgriculturalIntelligence) -> Dict[str, str]:
        """Prepare crop-specific context"""
        context = {}
        
        if agricultural_data and agricultural_data.weather_data:
            weather = agricultural_data.weather_data
            context["weather"] = f"Temperature: {weather.temperature}°C, Humidity: {weather.humidity}%, Rainfall: {weather.rainfall}mm"
        
        if agricultural_data and agricultural_data.soil_data:
            soil = agricultural_data.soil_data
            context["soil"] = f"pH: {soil.ph or 'Unknown'}, Moisture: {soil.moisture_content or 'Unknown'}%"
        
        if agricultural_data and agricultural_data.market_data:
            market_info = []
            for market in agricultural_data.market_data[:2]:  # Limit to 2 markets
                market_info.append(f"{market.market_name}: Recent prices available")
            context["market"] = ", ".join(market_info) if market_info else "Market data not available"
        
        return context
    
    def _prepare_weather_context(self, agricultural_data: AgriculturalIntelligence) -> Dict[str, str]:
        """Prepare weather-specific context"""
        context = {}
        
        if agricultural_data and agricultural_data.weather_data:
            weather = agricultural_data.weather_data
            context["current"] = f"""
            Temperature: {weather.temperature}°C (feels like {weather.feels_like or weather.temperature}°C)
            Humidity: {weather.humidity}%
            Wind: {weather.wind_speed} km/h
            Rainfall: {weather.rainfall}mm
            Condition: {weather.condition.value}
            """
            
            if weather.is_forecast:
                context["forecast"] = f"Forecast for next {weather.forecast_hours or 24} hours available"
            else:
                context["forecast"] = "Extended forecast not available"
        
        return context
    
    def _prepare_market_context(self, agricultural_data: AgriculturalIntelligence) -> Dict[str, str]:
        """Prepare market-specific context"""
        context = {}
        
        if agricultural_data and agricultural_data.market_data:
            prices = []
            for market in agricultural_data.market_data:
                for price in market.prices[:3]:  # Limit to 3 prices per market
                    prices.append(f"{price.commodity}: ₹{price.modal_price.amount}/{price.unit}")
            
            context["current_prices"] = "; ".join(prices) if prices else "No current prices available"
            context["trends"] = "Price trends analysis available" if agricultural_data.market_data else "No trend data"
        
        return context
    
    def _prepare_farmer_context(self, farmer_profile: FarmerProfile) -> str:
        """Prepare farmer profile context"""
        crops = self._get_current_crops(farmer_profile)
        return f"""
        Farm size: {farmer_profile.farm_details.total_land_area.value} {farmer_profile.farm_details.total_land_area.unit}
        Soil type: {farmer_profile.farm_details.soil_type.value}
        Irrigation: {farmer_profile.farm_details.primary_irrigation_source.value}
        Current crops: {crops}
        Experience: {farmer_profile.farming_experience.value}
        """
    
    def _prepare_current_conditions(self, agricultural_data: Optional[AgriculturalIntelligence]) -> str:
        """Prepare current conditions context"""
        if not agricultural_data:
            return "Current conditions data not available"
        
        conditions = []
        
        if agricultural_data.weather_data:
            conditions.append(f"Weather: {agricultural_data.weather_data.condition.value}")
        
        if agricultural_data.soil_data:
            conditions.append(f"Soil moisture: {agricultural_data.soil_data.moisture_content or 'Unknown'}%")
        
        if agricultural_data.crop_health_score:
            conditions.append(f"Crop health: {agricultural_data.crop_health_score}/100")
        
        return "; ".join(conditions) if conditions else "Conditions data not available"
    
    def _get_current_crops(self, farmer_profile: FarmerProfile) -> str:
        """Get current crops from farmer profile"""
        if farmer_profile.farm_details.crops:
            crop_names = [crop.crop_name for crop in farmer_profile.farm_details.crops]
            return ", ".join(crop_names)
        return "No crops specified"
    
    def _extract_recommendations(self, response_text: str) -> List[str]:
        """Extract actionable recommendations from response text"""
        # Simple extraction - in production, this could be more sophisticated
        recommendations = []
        lines = response_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if any(keyword in line.lower() for keyword in ['recommend', 'suggest', 'should', 'must', 'need to']):
                if len(line) > 20 and len(line) < 200:  # Reasonable length
                    recommendations.append(line)
        
        return recommendations[:5]  # Limit to 5 recommendations
    
    def _create_error_response(self, query: AgricultureQuery, error_message: str) -> KnowledgeResponse:
        """Create error response"""
        return KnowledgeResponse(
            response_text=f"I apologize, but I encountered an issue processing your query. Please try again or rephrase your question.",
            confidence_score=0.0,
            sources=[],
            recommendations=[],
            language=query.language,
            response_type="error",
            metadata={"error": error_message}
        )


class KnowledgeReasoningTool(BaseTool, LangChainBaseModel):
    """LangChain tool for knowledge and reasoning operations"""
    
    name: str = "agricultural_knowledge_reasoning"
    description: str = "Process agricultural queries using AI reasoning and knowledge base"
    
    def _run(self, query_data: str) -> str:
        """Run the knowledge reasoning tool"""
        try:
            # Parse query data
            query_dict = json.loads(query_data)
            query = AgricultureQuery(**query_dict)
            
            # Initialize reasoning chain
            llm_manager = BedrockLLMManager()
            reasoning_chain = AgriculturalReasoningChain(llm_manager)
            
            # Process query (simplified for synchronous execution)
            # In production, this would be async
            response = KnowledgeResponse(
                response_text="Agricultural advice processed successfully",
                confidence_score=0.8,
                sources=["Knowledge Base"],
                recommendations=["Follow up with specific actions"],
                language=query.language,
                response_type="general_advice"
            )
            
            return response.model_dump_json()
            
        except Exception as e:
            logger.error(f"Error in knowledge reasoning tool: {e}")
            return json.dumps({"error": str(e)})
    
    async def _arun(self, query_data: str) -> str:
        """Async version of the tool"""
        try:
            # Parse query data
            query_dict = json.loads(query_data)
            query = AgricultureQuery(**query_dict)
            
            # Initialize reasoning chain
            llm_manager = BedrockLLMManager()
            reasoning_chain = AgriculturalReasoningChain(llm_manager)
            
            # Process query based on type
            if query.query_type == "crop_advice":
                # Would need farmer profile and agricultural data
                response = await reasoning_chain.analyze_general_query(query, None)
            elif query.query_type == "weather":
                response = await reasoning_chain.analyze_general_query(query, None)
            elif query.query_type == "market":
                response = await reasoning_chain.analyze_general_query(query, None)
            else:
                response = await reasoning_chain.analyze_general_query(query, None)
            
            return response.model_dump_json()
            
        except Exception as e:
            logger.error(f"Error in async knowledge reasoning tool: {e}")
            return json.dumps({"error": str(e)})


class KnowledgeReasoningAgent:
    """Main Knowledge & Reasoning Agent class"""
    
    def __init__(self):
        self.llm_manager = BedrockLLMManager()
        self.reasoning_chain = AgriculturalReasoningChain(self.llm_manager)
        self.memory_manager = ConversationMemoryManager()
        self.tools = [KnowledgeReasoningTool()]
        
    async def process_query(
        self,
        query: AgricultureQuery,
        farmer_profile: FarmerProfile,
        agricultural_data: Optional[AgriculturalIntelligence] = None
    ) -> KnowledgeResponse:
        """Process an agricultural query and return knowledge-based response"""
        try:
            logger.info(f"Processing {query.query_type} query for farmer {query.farmer_id}")
            
            # Route query to appropriate analysis method
            if query.query_type == "crop_advice":
                response = await self.reasoning_chain.analyze_crop_query(
                    query, farmer_profile, agricultural_data
                )
            elif query.query_type == "weather":
                response = await self.reasoning_chain.analyze_weather_query(
                    query, farmer_profile, agricultural_data
                )
            elif query.query_type == "market":
                response = await self.reasoning_chain.analyze_market_query(
                    query, farmer_profile, agricultural_data
                )
            elif query.query_type == "pest_disease":
                # Use pest disease chain
                response = await self.reasoning_chain.analyze_general_query(
                    query, farmer_profile, agricultural_data
                )
            else:
                # General query
                response = await self.reasoning_chain.analyze_general_query(
                    query, farmer_profile, agricultural_data
                )
            
            logger.info(f"Generated response with confidence {response.confidence_score}")
            return response
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return KnowledgeResponse(
                response_text="I apologize, but I'm having trouble processing your question right now. Please try again.",
                confidence_score=0.0,
                sources=[],
                recommendations=[],
                language=query.language,
                response_type="error",
                metadata={"error": str(e)}
            )
    
    async def get_conversation_history(self, farmer_id: str) -> List[Dict[str, str]]:
        """Get conversation history for a farmer"""
        try:
            messages = self.memory_manager.get_conversation_history(farmer_id)
            history = []
            
            for message in messages:
                if isinstance(message, HumanMessage):
                    history.append({"type": "human", "content": message.content})
                elif isinstance(message, AIMessage):
                    history.append({"type": "ai", "content": message.content})
            
            return history
            
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {e}")
            return []
    
    async def clear_conversation_history(self, farmer_id: str) -> bool:
        """Clear conversation history for a farmer"""
        try:
            self.memory_manager.clear_memory(farmer_id)
            logger.info(f"Cleared conversation history for farmer {farmer_id}")
            return True
        except Exception as e:
            logger.error(f"Error clearing conversation history: {e}")
            return False
    
    async def test_llm_connection(self) -> bool:
        """Test LLM connection"""
        return await self.llm_manager.test_connection()
    
    async def close(self):
        """Close agent connections"""
        try:
            # Clean up resources if needed
            logger.info("Knowledge & Reasoning Agent closed")
        except Exception as e:
            logger.error(f"Error closing Knowledge & Reasoning Agent: {e}")