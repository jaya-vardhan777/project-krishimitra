"""
Agent Coordinator for KrishiMitra Multi-Agent System

This module implements the coordination logic for managing communication between
specialized agents using LangGraph workflows.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timezone
import time

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from .agent_state import (
    KrishiMitraState, AgentType, QueryType, ProcessingStatus,
    AgentResponse, create_initial_state, update_agent_response,
    add_error, increment_retry
)
from ..agents.data_ingestion import DataIngestionAgent
from ..agents.knowledge_reasoning import BedrockLLMManager, AgriculturalReasoningChain, AgricultureQuery
from ..agents.advisory import FarmerProfileAnalyzer, CropRecommendationScorer
from ..agents.sustainability import SustainabilityAgent
from ..agents.feedback import FeedbackAgent
from ..models.farmer import FarmerProfile
from ..models.agricultural_intelligence import AgriculturalIntelligence

logger = logging.getLogger(__name__)


class AgentCoordinator:
    """
    Coordinates communication and workflow between specialized agents using LangGraph.
    Implements inter-agent messaging, state management, and error handling.
    """
    
    def __init__(self):
        self.graph = None
        self.checkpointer = MemorySaver()
        self.agents = self._initialize_agents()
        self._build_graph()
        logger.info("AgentCoordinator initialized with LangGraph workflow")
    
    def _initialize_agents(self) -> Dict[AgentType, Any]:
        """Initialize all specialized agents"""
        try:
            agents = {
                AgentType.DATA_INGESTION: DataIngestionAgent(),
                AgentType.KNOWLEDGE_REASONING: None,  # Initialized on demand
                AgentType.ADVISORY: None,  # Initialized on demand
                AgentType.SUSTAINABILITY: SustainabilityAgent(),
                AgentType.FEEDBACK: FeedbackAgent()
            }
            logger.info("Initialized all specialized agents")
            return agents
        except Exception as e:
            logger.error(f"Error initializing agents: {e}")
            raise
    
    def _build_graph(self):
        """Build the LangGraph workflow for agent coordination"""
        try:
            # Create the state graph
            workflow = StateGraph(KrishiMitraState)
            
            # Add nodes for each agent
            workflow.add_node("orchestrator", self._orchestrator_node)
            workflow.add_node("data_ingestion", self._data_ingestion_node)
            workflow.add_node("knowledge_reasoning", self._know