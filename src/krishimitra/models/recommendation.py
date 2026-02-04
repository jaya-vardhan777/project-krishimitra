"""
Recommendation models for KrishiMitra platform.

This module contains models for agricultural recommendations, feedback,
and recommendation tracking.
"""

from datetime import datetime, date
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from decimal import Decimal

from pydantic import Field, validator

from .base import BaseModel, TimestampedModel, MonetaryAmount, Measurement, LanguageCode


class RecommendationType(str, Enum):
    """Types of agricultural recommendations."""
    CROP_SELECTION = "crop_selection"
    PLANTING_TIMING = "planting_timing"
    IRRIGATION = "irrigation"
    FERTILIZATION = "fertilization"
    PEST_MANAGEMENT = "pest_management"
    DISEASE_MANAGEMENT = "disease_management"
    HARVESTING = "harvesting"
    POST_HARVEST = "post_harvest"
    MARKET_TIMING = "market_timing"
    WEATHER_ADVISORY = "weather_advisory"
    SOIL_MANAGEMENT = "soil_management"
    EQUIPMENT_USAGE = "equipment_usage"
    FINANCIAL_PLANNING = "financial_planning"
    GOVERNMENT_SCHEMES = "government_schemes"
    SUSTAINABILITY = "sustainability"
    GENERAL_ADVICE = "general_advice"


class Priority(str, Enum):
    """Recommendation priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ImplementationStatus(str, Enum):
    """Implementation status of recommendations."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    PARTIALLY_COMPLETED = "partially_completed"


class FeedbackRating(int, Enum):
    """Feedback rating scale."""
    VERY_POOR = 1
    POOR = 2
    AVERAGE = 3
    GOOD = 4
    EXCELLENT = 5


class ActionItem(BaseModel):
    """Individual action item within a recommendation."""
    
    title: str = Field(description="Action item title")
    description: str = Field(description="Detailed description")
    priority: Priority = Field(description="Action priority")
    estimated_time: Optional[str] = Field(default=None, description="Estimated time to complete")
    estimated_cost: Optional[MonetaryAmount] = Field(default=None, description="Estimated cost")
    deadline: Optional[date] = Field(default=None, description="Recommended deadline")
    prerequisites: List[str] = Field(default_factory=list, description="Prerequisites for this action")
    resources_needed: List[str] = Field(default_factory=list, description="Resources needed")
    expected_outcome: Optional[str] = Field(default=None, description="Expected outcome")
    
    # Implementation tracking
    status: ImplementationStatus = Field(default=ImplementationStatus.NOT_STARTED, description="Implementation status")
    started_date: Optional[date] = Field(default=None, description="Date when implementation started")
    completed_date: Optional[date] = Field(default=None, description="Date when completed")
    notes: Optional[str] = Field(default=None, description="Implementation notes")


class RecommendationContext(BaseModel):
    """Context information for the recommendation."""
    
    crop_type: Optional[str] = Field(default=None, description="Relevant crop type")
    season: Optional[str] = Field(default=None, description="Relevant season")
    growth_stage: Optional[str] = Field(default=None, description="Crop growth stage")
    weather_conditions: Optional[Dict[str, Any]] = Field(default=None, description="Weather context")
    soil_conditions: Optional[Dict[str, Any]] = Field(default=None, description="Soil context")
    market_conditions: Optional[Dict[str, Any]] = Field(default=None, description="Market context")
    farm_size: Optional[Measurement] = Field(default=None, description="Relevant farm area")
    budget_range: Optional[MonetaryAmount] = Field(default=None, description="Budget considerations")
    farmer_experience: Optional[str] = Field(default=None, description="Farmer experience level")
    technology_adoption: Optional[str] = Field(default=None, description="Technology adoption willingness")


class RecommendationEvidence(BaseModel):
    """Evidence and sources supporting the recommendation."""
    
    data_sources: List[str] = Field(description="Data sources used")
    research_papers: List[str] = Field(default_factory=list, description="Supporting research papers")
    expert_opinions: List[str] = Field(default_factory=list, description="Expert opinions")
    local_success_stories: List[str] = Field(default_factory=list, description="Local success stories")
    government_guidelines: List[str] = Field(default_factory=list, description="Government guidelines")
    confidence_score: float = Field(ge=0, le=100, description="Confidence in the recommendation")
    reliability_score: float = Field(ge=0, le=100, description="Reliability score")


class RecommendationImpact(BaseModel):
    """Expected and actual impact of the recommendation."""
    
    # Expected impact
    expected_yield_increase: Optional[float] = Field(default=None, description="Expected yield increase percentage")
    expected_cost_reduction: Optional[float] = Field(default=None, description="Expected cost reduction percentage")
    expected_time_saving: Optional[str] = Field(default=None, description="Expected time saving")
    expected_quality_improvement: Optional[str] = Field(default=None, description="Expected quality improvement")
    environmental_impact: Optional[str] = Field(default=None, description="Environmental impact")
    
    # Actual impact (filled after implementation)
    actual_yield_change: Optional[float] = Field(default=None, description="Actual yield change percentage")
    actual_cost_change: Optional[float] = Field(default=None, description="Actual cost change percentage")
    actual_time_impact: Optional[str] = Field(default=None, description="Actual time impact")
    actual_quality_change: Optional[str] = Field(default=None, description="Actual quality change")
    farmer_satisfaction: Optional[FeedbackRating] = Field(default=None, description="Farmer satisfaction rating")


class RecommendationRecord(TimestampedModel):
    """Complete recommendation record."""
    
    farmer_id: str = Field(description="Associated farmer ID")
    recommendation_type: RecommendationType = Field(description="Type of recommendation")
    
    # Content
    title: str = Field(description="Recommendation title")
    summary: str = Field(description="Brief summary")
    description: str = Field(description="Detailed description")
    language: LanguageCode = Field(description="Language of the recommendation")
    
    # Structure
    action_items: List[ActionItem] = Field(description="List of action items")
    context: RecommendationContext = Field(description="Recommendation context")
    evidence: RecommendationEvidence = Field(description="Supporting evidence")
    
    # Metadata
    priority: Priority = Field(description="Overall priority")
    urgency_deadline: Optional[date] = Field(default=None, description="Urgency deadline")
    seasonal_relevance: Optional[str] = Field(default=None, description="Seasonal relevance")
    geographic_relevance: Optional[str] = Field(default=None, description="Geographic relevance")
    
    # AI/ML metadata
    model_version: Optional[str] = Field(default=None, description="AI model version used")
    agent_source: Optional[str] = Field(default=None, description="Source agent that generated this")
    generation_method: Optional[str] = Field(default=None, description="Generation method")
    personalization_factors: List[str] = Field(default_factory=list, description="Personalization factors used")
    
    # Impact and tracking
    expected_impact: RecommendationImpact = Field(description="Expected impact")
    actual_impact: Optional[RecommendationImpact] = Field(default=None, description="Actual impact after implementation")
    
    # Status
    overall_status: ImplementationStatus = Field(default=ImplementationStatus.NOT_STARTED, description="Overall implementation status")
    completion_percentage: float = Field(default=0, ge=0, le=100, description="Completion percentage")
    
    # Feedback
    farmer_feedback: Optional[str] = Field(default=None, description="Farmer feedback")
    feedback_rating: Optional[FeedbackRating] = Field(default=None, description="Overall feedback rating")
    feedback_date: Optional[datetime] = Field(default=None, description="Feedback submission date")
    
    # Follow-up
    follow_up_needed: bool = Field(default=False, description="Whether follow-up is needed")
    follow_up_date: Optional[date] = Field(default=None, description="Scheduled follow-up date")
    follow_up_notes: Optional[str] = Field(default=None, description="Follow-up notes")
    
    # Related recommendations
    related_recommendations: List[str] = Field(default_factory=list, description="Related recommendation IDs")
    superseded_by: Optional[str] = Field(default=None, description="ID of recommendation that supersedes this one")
    supersedes: List[str] = Field(default_factory=list, description="IDs of recommendations this supersedes")


class RecommendationRequest(BaseModel):
    """Request for generating recommendations."""
    
    farmer_id: str = Field(description="Farmer ID")
    query_type: Optional[RecommendationType] = Field(default=None, description="Specific type of recommendation requested")
    query_text: Optional[str] = Field(default=None, description="Natural language query")
    language: LanguageCode = Field(default_factory=LanguageCode.hindi, description="Preferred language")
    
    # Context
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    location: Optional[Dict[str, float]] = Field(default=None, description="Specific location if different from profile")
    urgency: Optional[Priority] = Field(default=Priority.MEDIUM, description="Urgency level")
    
    # Preferences
    include_cost_analysis: bool = Field(default=True, description="Include cost analysis")
    include_timeline: bool = Field(default=True, description="Include implementation timeline")
    max_recommendations: int = Field(default=5, ge=1, le=20, description="Maximum number of recommendations")
    
    # Filters
    budget_limit: Optional[MonetaryAmount] = Field(default=None, description="Budget limit")
    time_constraint: Optional[str] = Field(default=None, description="Time constraints")
    exclude_types: List[RecommendationType] = Field(default_factory=list, description="Recommendation types to exclude")


class RecommendationResponse(BaseModel):
    """Response containing recommendations."""
    
    request_id: str = Field(description="Request ID")
    farmer_id: str = Field(description="Farmer ID")
    recommendations: List[RecommendationRecord] = Field(description="Generated recommendations")
    
    # Metadata
    generation_time: datetime = Field(default_factory=datetime.utcnow, description="Generation timestamp")
    processing_time_ms: Optional[int] = Field(default=None, description="Processing time in milliseconds")
    data_sources_used: List[str] = Field(description="Data sources used for generation")
    
    # Quality metrics
    overall_confidence: float = Field(ge=0, le=100, description="Overall confidence in recommendations")
    data_completeness: float = Field(ge=0, le=100, description="Data completeness percentage")
    personalization_score: float = Field(ge=0, le=100, description="Personalization score")
    
    # Additional information
    weather_alerts: List[str] = Field(default_factory=list, description="Relevant weather alerts")
    market_insights: List[str] = Field(default_factory=list, description="Market insights")
    seasonal_reminders: List[str] = Field(default_factory=list, description="Seasonal reminders")


class RecommendationFeedback(BaseModel):
    """Feedback on a recommendation."""
    
    recommendation_id: str = Field(description="Recommendation ID")
    farmer_id: str = Field(description="Farmer ID")
    
    # Overall feedback
    overall_rating: FeedbackRating = Field(description="Overall rating")
    usefulness_rating: FeedbackRating = Field(description="Usefulness rating")
    clarity_rating: FeedbackRating = Field(description="Clarity rating")
    feasibility_rating: FeedbackRating = Field(description="Feasibility rating")
    
    # Implementation feedback
    implementation_status: ImplementationStatus = Field(description="Implementation status")
    implementation_challenges: List[str] = Field(default_factory=list, description="Implementation challenges")
    implementation_notes: Optional[str] = Field(default=None, description="Implementation notes")
    
    # Outcome feedback
    outcome_achieved: Optional[bool] = Field(default=None, description="Whether expected outcome was achieved")
    outcome_description: Optional[str] = Field(default=None, description="Description of actual outcome")
    yield_impact: Optional[float] = Field(default=None, description="Yield impact percentage")
    cost_impact: Optional[float] = Field(default=None, description="Cost impact percentage")
    time_impact: Optional[str] = Field(default=None, description="Time impact")
    
    # Suggestions
    suggestions_for_improvement: Optional[str] = Field(default=None, description="Suggestions for improvement")
    would_recommend_to_others: Optional[bool] = Field(default=None, description="Would recommend to other farmers")
    
    # Additional feedback
    additional_comments: Optional[str] = Field(default=None, description="Additional comments")
    feedback_date: datetime = Field(default_factory=datetime.utcnow, description="Feedback submission date")
    
    # Follow-up
    needs_follow_up: bool = Field(default=False, description="Whether follow-up is needed")
    follow_up_reason: Optional[str] = Field(default=None, description="Reason for follow-up")


class RecommendationAnalytics(BaseModel):
    """Analytics data for recommendations."""
    
    farmer_id: str = Field(description="Farmer ID")
    time_period: str = Field(description="Time period for analytics")
    
    # Volume metrics
    total_recommendations: int = Field(description="Total recommendations received")
    recommendations_by_type: Dict[str, int] = Field(description="Recommendations by type")
    recommendations_by_priority: Dict[str, int] = Field(description="Recommendations by priority")
    
    # Implementation metrics
    implementation_rate: float = Field(ge=0, le=100, description="Implementation rate percentage")
    completion_rate: float = Field(ge=0, le=100, description="Completion rate percentage")
    average_implementation_time: Optional[float] = Field(default=None, description="Average implementation time in days")
    
    # Satisfaction metrics
    average_rating: Optional[float] = Field(default=None, ge=1, le=5, description="Average satisfaction rating")
    satisfaction_by_type: Dict[str, float] = Field(default_factory=dict, description="Satisfaction by recommendation type")
    
    # Impact metrics
    total_yield_impact: Optional[float] = Field(default=None, description="Total yield impact percentage")
    total_cost_impact: Optional[float] = Field(default=None, description="Total cost impact percentage")
    successful_recommendations: int = Field(description="Number of successful recommendations")
    
    # Engagement metrics
    feedback_rate: float = Field(ge=0, le=100, description="Feedback submission rate")
    follow_up_rate: float = Field(ge=0, le=100, description="Follow-up completion rate")
    recommendation_sharing_rate: float = Field(ge=0, le=100, description="Rate of sharing recommendations with others")