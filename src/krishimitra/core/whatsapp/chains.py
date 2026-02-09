"""
WhatsApp-specific LangChain chains for KrishiMitra.

This module provides specialized LangChain chains for WhatsApp
conversation management, including context handling, response formatting,
and multilingual support.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from langchain.chains import LLMChain, SequentialChain
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain_aws import ChatBedrock
from langchain.memory import ConversationBufferMemory, ConversationSummaryMemory
from langchain.output_parsers import PydanticOutputParser
from langchain.pydantic_v1 import BaseModel as LangChainBaseModel, Field

from ...core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# Output models for structured responses
class FarmerQueryAnalysis(LangChainBaseModel):
    """Analysis of farmer's query."""
    intent: str = Field(description="Primary intent of the query")
    topic: str = Field(description="Agricultural topic (crop, pest, weather, market, etc.)")
    urgency: str = Field(description="Urgency level: low, medium, high, critical")
    language: str = Field(description="Detected language code")
    requires_image: bool = Field(description="Whether query requires image analysis")
    requires_location: bool = Field(description="Whether query requires location data")


class AgricultureResponse(LangChainBaseModel):
    """Structured agriculture response."""
    response_text: str = Field(description="Main response text in farmer's language")
    recommendations: List[str] = Field(description="List of specific recommendations")
    follow_up_questions: List[str] = Field(description="Suggested follow-up questions")
    requires_expert: bool = Field(description="Whether query requires human expert")


class WhatsAppConversationChain:
    """LangChain chain for WhatsApp conversation management."""
    
    def __init__(self):
        """Initialize conversation chain."""
        self.llm = ChatBedrock(
            model_id=settings.bedrock_model_id,
            region_name=settings.bedrock_region,
            model_kwargs={
                "temperature": 0.7,
                "max_tokens": 2048
            }
        )
        
        # Initialize chains
        self.query_analysis_chain = self._create_query_analysis_chain()
        self.response_generation_chain = self._create_response_generation_chain()
        self.context_summarization_chain = self._create_context_summarization_chain()
    
    def _create_query_analysis_chain(self) -> LLMChain:
        """Create chain for analyzing farmer queries."""
        parser = PydanticOutputParser(pydantic_object=FarmerQueryAnalysis)
        
        prompt = PromptTemplate(
            input_variables=["query"],
            template="""Analyze the following farmer's query and extract key information.

Farmer's Query: {query}

Provide analysis in the following JSON format:
{format_instructions}

Analysis:""",
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )
        
        return LLMChain(
            llm=self.llm,
            prompt=prompt,
            output_parser=parser,
            verbose=True
        )
    
    def _create_response_generation_chain(self) -> LLMChain:
        """Create chain for generating agricultural responses."""
        prompt = PromptTemplate(
            input_variables=["query", "context", "farmer_profile", "language"],
            template="""You are KrishiMitra (कृषि मित्र), an expert AI agricultural advisor for Indian farmers.

Farmer Profile:
{farmer_profile}

Conversation Context:
{context}

Farmer's Query: {query}

Language: {language}

Generate a helpful, accurate, and practical response that:
1. Directly addresses the farmer's question
2. Provides specific, actionable recommendations
3. Uses simple language appropriate for rural farmers
4. Is culturally sensitive and region-appropriate
5. Stays within 300 words
6. Uses the specified language

If the query requires:
- Image analysis: Ask the farmer to send a photo
- Location data: Ask for their location
- Expert consultation: Mention that a specialist will follow up

Response:"""
        )
        
        return LLMChain(
            llm=self.llm,
            prompt=prompt,
            verbose=True
        )
    
    def _create_context_summarization_chain(self) -> LLMChain:
        """Create chain for summarizing conversation context."""
        prompt = PromptTemplate(
            input_variables=["conversation_history"],
            template="""Summarize the following conversation between a farmer and KrishiMitra agricultural advisor.
Focus on key agricultural topics discussed, recommendations given, and any pending actions.

Conversation History:
{conversation_history}

Summary (in 100 words or less):"""
        )
        
        return LLMChain(
            llm=self.llm,
            prompt=prompt,
            verbose=True
        )
    
    async def analyze_query(self, query: str) -> FarmerQueryAnalysis:
        """
        Analyze farmer's query to extract intent and requirements.
        
        Args:
            query: Farmer's query text
            
        Returns:
            Query analysis results
        """
        try:
            result = await self.query_analysis_chain.arun(query=query)
            return result
        except Exception as e:
            logger.error(f"Error analyzing query: {e}", exc_info=True)
            # Return default analysis
            return FarmerQueryAnalysis(
                intent="general_inquiry",
                topic="agriculture",
                urgency="medium",
                language="hi",
                requires_image=False,
                requires_location=False
            )
    
    async def generate_response(
        self,
        query: str,
        context: str = "",
        farmer_profile: str = "General farmer",
        language: str = "Hindi"
    ) -> str:
        """
        Generate agricultural response for farmer's query.
        
        Args:
            query: Farmer's query
            context: Conversation context
            farmer_profile: Farmer profile information
            language: Response language
            
        Returns:
            Generated response text
        """
        try:
            response = await self.response_generation_chain.arun(
                query=query,
                context=context,
                farmer_profile=farmer_profile,
                language=language
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Error generating response: {e}", exc_info=True)
            return "क्षमा करें, उत्तर उत्पन्न करने में समस्या हुई। कृपया पुनः प्रयास करें।"
    
    async def summarize_context(self, conversation_history: str) -> str:
        """
        Summarize conversation context for memory management.
        
        Args:
            conversation_history: Full conversation history
            
        Returns:
            Summarized context
        """
        try:
            summary = await self.context_summarization_chain.arun(
                conversation_history=conversation_history
            )
            return summary.strip()
        except Exception as e:
            logger.error(f"Error summarizing context: {e}", exc_info=True)
            return "Previous conversation about agricultural topics."


class WhatsAppImageAnalysisChain:
    """LangChain chain for crop image analysis."""
    
    def __init__(self):
        """Initialize image analysis chain."""
        self.llm = ChatBedrock(
            model_id=settings.bedrock_model_id,
            region_name=settings.bedrock_region,
            model_kwargs={
                "temperature": 0.5,
                "max_tokens": 1024
            }
        )
        
        self.analysis_chain = self._create_analysis_chain()
    
    def _create_analysis_chain(self) -> LLMChain:
        """Create chain for image analysis interpretation."""
        prompt = PromptTemplate(
            input_variables=["image_analysis", "farmer_query"],
            template="""You are an expert agricultural pathologist analyzing crop images for Indian farmers.

Image Analysis Results:
{image_analysis}

Farmer's Question: {farmer_query}

Based on the image analysis, provide:
1. Assessment of crop health
2. Identification of any visible issues (disease, pest, nutrient deficiency)
3. Specific recommendations for treatment or prevention
4. Next steps the farmer should take

Respond in Hindi with clear, actionable advice (max 250 words):"""
        )
        
        return LLMChain(
            llm=self.llm,
            prompt=prompt,
            verbose=True
        )
    
    async def interpret_analysis(
        self,
        image_analysis: Dict[str, Any],
        farmer_query: str = ""
    ) -> str:
        """
        Interpret image analysis results and generate farmer-friendly response.
        
        Args:
            image_analysis: Technical image analysis results
            farmer_query: Optional farmer's question about the image
            
        Returns:
            Interpreted response in farmer's language
        """
        try:
            # Format analysis results
            analysis_text = f"""
Health Status: {image_analysis.get('health_status', 'Unknown')}
Confidence: {image_analysis.get('confidence', 0)*100:.0f}%
Green Ratio: {image_analysis.get('green_ratio', 0):.2f}
Edge Density: {image_analysis.get('edge_density', 0):.2f}
"""
            
            response = await self.analysis_chain.arun(
                image_analysis=analysis_text,
                farmer_query=farmer_query or "फसल की स्थिति क्या है?"
            )
            
            return response.strip()
        except Exception as e:
            logger.error(f"Error interpreting image analysis: {e}", exc_info=True)
            return "छवि विश्लेषण पूर्ण हुआ। कृपया विस्तृत जानकारी के लिए कृषि विशेषज्ञ से संपर्क करें।"


class WhatsAppGroupChatChain:
    """LangChain chain for managing group chat conversations."""
    
    def __init__(self):
        """Initialize group chat chain."""
        self.llm = ChatBedrock(
            model_id=settings.bedrock_model_id,
            region_name=settings.bedrock_region,
            model_kwargs={
                "temperature": 0.7,
                "max_tokens": 1024
            }
        )
        
        self.group_response_chain = self._create_group_response_chain()
    
    def _create_group_response_chain(self) -> LLMChain:
        """Create chain for group chat responses."""
        prompt = PromptTemplate(
            input_variables=["group_context", "current_message", "sender_name"],
            template="""You are KrishiMitra responding in a WhatsApp group chat with multiple farmers.

Group Context:
{group_context}

Current Message from {sender_name}: {current_message}

Provide a response that:
1. Addresses the specific farmer by name if appropriate
2. Is relevant to the group discussion
3. Provides value to all group members
4. Encourages knowledge sharing among farmers
5. Is concise (max 200 words)

Response in Hindi:"""
        )
        
        return LLMChain(
            llm=self.llm,
            prompt=prompt,
            verbose=True
        )
    
    async def generate_group_response(
        self,
        current_message: str,
        sender_name: str,
        group_context: str = ""
    ) -> str:
        """
        Generate response for group chat message.
        
        Args:
            current_message: Current message in group
            sender_name: Name of message sender
            group_context: Recent group conversation context
            
        Returns:
            Generated group response
        """
        try:
            response = await self.group_response_chain.arun(
                group_context=group_context,
                current_message=current_message,
                sender_name=sender_name
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Error generating group response: {e}", exc_info=True)
            return f"धन्यवाद {sender_name}! हम आपके प्रश्न पर काम कर रहे हैं।"


class WhatsAppResponseFormatter:
    """Utility for formatting responses for WhatsApp."""
    
    @staticmethod
    def format_for_whatsapp(text: str, max_length: int = 4000) -> List[str]:
        """
        Format text for WhatsApp message limits.
        
        Args:
            text: Text to format
            max_length: Maximum message length
            
        Returns:
            List of message chunks
        """
        if len(text) <= max_length:
            return [text]
        
        # Split into chunks at sentence boundaries
        chunks = []
        current_chunk = ""
        
        sentences = text.split('. ')
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 2 <= max_length:
                current_chunk += sentence + '. '
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + '. '
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    @staticmethod
    def add_whatsapp_formatting(text: str) -> str:
        """
        Add WhatsApp text formatting.
        
        Args:
            text: Plain text
            
        Returns:
            Formatted text with WhatsApp markdown
        """
        # Add bold for headings (lines ending with :)
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            if line.strip().endswith(':'):
                formatted_lines.append(f"*{line.strip()}*")
            else:
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
    
    @staticmethod
    def create_list_message(title: str, items: List[str]) -> str:
        """
        Create formatted list message for WhatsApp.
        
        Args:
            title: List title
            items: List items
            
        Returns:
            Formatted list message
        """
        message = f"*{title}*\n\n"
        
        for i, item in enumerate(items, 1):
            message += f"{i}. {item}\n"
        
        return message.strip()
