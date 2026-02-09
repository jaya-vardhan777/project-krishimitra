"""
Agent State Management for LangGraph Multi-Agent System

This module defines the shared state structure used across all agents in the
KrishiMitra multi-agent orchestration system.
"""

from typing import Dict, List, Optional, Any, Annotated
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field
from langgraph.graph import MessagesState
from langchain_core.messages import BaseMessage


class AgentType(str, Enum):
    """Types of agents in the system"""
    DATA_INGESTION = "data_ingestion"
    KNOWLEDGE_REASONING = "knowledge_reasoning"
    ADVISORY = "advisory"
    SUSTAINABILITY = "sustainability"
    FEEDBACK = "feedback"
    ORCHESTRATOR = "orchestrator"


class QueryType(str, Enum):
    """Types of queries that can be processed"""
    CROP_ADVICE = "crop_advice"
    WEATHER_ANALYSIS = "weather_analysis"
    MARKET_INTELLIGENCE = "market_intelligence"
    PEST_DISEASE = "pest_disease"
    IRRIGATION = "irrigation"
    SUSTAINABILITY = "sustainability"
    GENERAL = "general"


class ProcessingStatus(str, Enum):
    """Status of query processing"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REQUIRES_CLARIFICATION = "requires_clarification"


class AgentResponse(BaseModel):
    """Response from an individual agent"""
    agent_type: AgentType
    response_data: Dict[str, Any]
    confidence_score: float = Field(ge=0.0, le=1.0)
    processing_time_ms: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    errors: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class KrishiMitraState(MessagesState):
    """
    Shared state for the KrishiMitra multi-agent system.
    Extends LangGraph's MessagesState to include agricultural-specific data.
    """
    
    # Query information
    farmer_id: str
    query_text: str
    query_type: QueryType
    language: str = "hindi"
    
    # Processing status
    status: ProcessingStatus = ProcessingStatus.PENDING
    current_agent: Optional[AgentType] = None
    agents_completed: List[AgentType] = Field(default_factory=list)
    
    # Farmer context
    farmer_profile: Optional[Dict[str, Any]] = None
    location: Optional[Dict[str, float]] = None
    
    # Agricultural data
    agricultural_intelligence: Optional[Dict[str, Any]] = None
    sensor_data: List[Dict[str, Any]] = Field(default_factory=list)
    weather_data: Optional[Dict[str, Any]] = None
    market_data: List[Dict[str, Any]] = Field(default_factory=list)
    satellite_data: Optional[Dict[str, Any]] = None
    
    # Agent responses
    agent_responses: Dict[AgentType, AgentResponse] = Field(default_factory=dict)
    
    # Final recommendation
    final_recommendation: Optional[Dict[str, Any]] = None
    confidence_score: float = 0.0
    
    # Error handling
    errors: List[str] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    
    # Metadata
    session_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processing_time_ms: float = 0.0
    
    # Conversation context
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    follow_up_questions: List[str] = Field(default_factory=list)
    
    # Routing information
    next_agent: Optional[AgentType] = None
    requires_human_review: bool = False
    
    class Config:
        arbitrary_types_allowed = True


def create_initial_state(
    farmer_id: str,
    query_text: str,
    query_type: QueryType,
    session_id: str,
    language: str = "hindi",
    farmer_profile: Optional[Dict[str, Any]] = None,
    location: Optional[Dict[str, float]] = None
) -> KrishiMitraState:
    """Create initial state for a new query"""
    return KrishiMitraState(
        farmer_id=farmer_id,
        query_text=query_text,
        query_type=query_type,
        language=language,
        session_id=session_id,
        farmer_profile=farmer_profile,
        location=location,
        messages=[]
    )


def update_agent_response(
    state: KrishiMitraState,
    agent_type: AgentType,
    response: AgentResponse
) -> KrishiMitraState:
    """Update state with agent response"""
    state.agent_responses[agent_type] = response
    if agent_type not in state.agents_completed:
        state.agents_completed.append(agent_type)
    state.updated_at = datetime.now(timezone.utc)
    return state


def add_error(state: KrishiMitraState, error_message: str) -> KrishiMitraState:
    """Add error to state"""
    state.errors.append(error_message)
    state.updated_at = datetime.now(timezone.utc)
    return state


def increment_retry(state: KrishiMitraState) -> KrishiMitraState:
    """Increment retry count"""
    state.retry_count += 1
    state.updated_at = datetime.now(timezone.utc)
    return state
