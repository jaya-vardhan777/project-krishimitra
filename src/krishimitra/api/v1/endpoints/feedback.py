"""
Feedback endpoints for KrishiMitra Platform.

This module handles feedback collection, outcome tracking,
and effectiveness analysis for recommendations.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field

from ....agents.feedback import FeedbackAgent
from ....models.recommendation import (
    RecommendationFeedback,
    FeedbackRating,
    ImplementationStatus
)

router = APIRouter()

# Initialize feedback agent (in production, this would use DynamoDB)
feedback_agent = FeedbackAgent()


class FeedbackSubmission(BaseModel):
    """Model for submitting feedback."""
    
    recommendation_id: str = Field(description="Recommendation ID")
    farmer_id: str = Field(description="Farmer ID")
    overall_rating: int = Field(ge=1, le=5, description="Overall rating (1-5)")
    usefulness_rating: int = Field(ge=1, le=5, description="Usefulness rating (1-5)")
    clarity_rating: int = Field(ge=1, le=5, description="Clarity rating (1-5)")
    feasibility_rating: int = Field(ge=1, le=5, description="Feasibility rating (1-5)")
    implementation_status: str = Field(description="Implementation status")
    implementation_challenges: List[str] = Field(default=[], description="Implementation challenges")
    implementation_notes: Optional[str] = Field(default=None, description="Implementation notes")
    outcome_achieved: Optional[bool] = Field(default=None, description="Whether outcome was achieved")
    outcome_description: Optional[str] = Field(default=None, description="Outcome description")
    yield_impact: Optional[float] = Field(default=None, description="Yield impact percentage")
    cost_impact: Optional[float] = Field(default=None, description="Cost impact percentage")
    time_impact: Optional[str] = Field(default=None, description="Time impact")
    suggestions_for_improvement: Optional[str] = Field(default=None, description="Suggestions")
    would_recommend_to_others: Optional[bool] = Field(default=None, description="Would recommend to others")
    additional_comments: Optional[str] = Field(default=None, description="Additional comments")
    needs_follow_up: bool = Field(default=False, description="Needs follow-up")
    follow_up_reason: Optional[str] = Field(default=None, description="Follow-up reason")


class OutcomeSubmission(BaseModel):
    """Model for submitting outcome data."""
    
    recommendation_id: str = Field(description="Recommendation ID")
    farmer_id: str = Field(description="Farmer ID")
    actual_yield: Optional[float] = Field(default=None, description="Actual yield")
    expected_yield: Optional[float] = Field(default=None, description="Expected yield")
    actual_cost: Optional[float] = Field(default=None, description="Actual cost")
    expected_cost: Optional[float] = Field(default=None, description="Expected cost")
    implementation_time: Optional[str] = Field(default=None, description="Implementation time")
    quality_metrics: Dict[str, Any] = Field(default={}, description="Quality metrics")
    environmental_impact: Dict[str, Any] = Field(default={}, description="Environmental impact")
    farmer_satisfaction: Optional[int] = Field(default=None, ge=1, le=5, description="Satisfaction rating")


class EffectivenessAnalysisRequest(BaseModel):
    """Model for requesting effectiveness analysis."""
    
    recommendation_id: Optional[str] = Field(default=None, description="Specific recommendation ID")
    farmer_id: Optional[str] = Field(default=None, description="Specific farmer ID")
    recommendation_type: Optional[str] = Field(default=None, description="Recommendation type")
    time_period_days: int = Field(default=30, ge=1, le=365, description="Time period in days")


class FeedbackResponse(BaseModel):
    """Response model for feedback submission."""
    
    feedback_id: str = Field(description="Feedback ID")
    recommendation_id: str = Field(description="Recommendation ID")
    farmer_id: str = Field(description="Farmer ID")
    timestamp: str = Field(description="Submission timestamp")
    message: str = Field(description="Confirmation message")


class OutcomeResponse(BaseModel):
    """Response model for outcome submission."""
    
    outcome_id: str = Field(description="Outcome ID")
    recommendation_id: str = Field(description="Recommendation ID")
    farmer_id: str = Field(description="Farmer ID")
    timestamp: str = Field(description="Submission timestamp")
    message: str = Field(description="Confirmation message")


@router.post("/submit", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(feedback: FeedbackSubmission) -> FeedbackResponse:
    """
    Submit feedback for a recommendation.
    
    This endpoint collects farmer feedback on recommendation effectiveness,
    implementation challenges, and actual outcomes.
    
    Args:
        feedback: Feedback submission data
        
    Returns:
        Feedback confirmation with ID
        
    Raises:
        HTTPException: If feedback submission fails
    """
    try:
        feedback_data = feedback.model_dump()
        recommendation_id = feedback_data.pop("recommendation_id")
        farmer_id = feedback_data.pop("farmer_id")
        
        feedback_record = feedback_agent.collect_feedback(
            recommendation_id=recommendation_id,
            farmer_id=farmer_id,
            feedback_data=feedback_data
        )
        
        return FeedbackResponse(
            feedback_id=feedback_record["feedback_id"],
            recommendation_id=feedback_record["recommendation_id"],
            farmer_id=feedback_record["farmer_id"],
            timestamp=feedback_record["timestamp"],
            message="Feedback submitted successfully"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit feedback: {str(e)}"
        )


@router.post("/outcomes", response_model=OutcomeResponse, status_code=status.HTTP_201_CREATED)
async def submit_outcome(outcome: OutcomeSubmission) -> OutcomeResponse:
    """
    Submit outcome data for a recommendation.
    
    This endpoint tracks actual outcomes (yield, cost, etc.) after
    implementing a recommendation for correlation analysis.
    
    Args:
        outcome: Outcome submission data
        
    Returns:
        Outcome confirmation with ID
        
    Raises:
        HTTPException: If outcome submission fails
    """
    try:
        outcome_data = outcome.model_dump()
        recommendation_id = outcome_data.pop("recommendation_id")
        farmer_id = outcome_data.pop("farmer_id")
        
        outcome_record = feedback_agent.track_outcome(
            recommendation_id=recommendation_id,
            farmer_id=farmer_id,
            outcome_data=outcome_data
        )
        
        return OutcomeResponse(
            outcome_id=outcome_record["outcome_id"],
            recommendation_id=outcome_record["recommendation_id"],
            farmer_id=outcome_record["farmer_id"],
            timestamp=outcome_record["timestamp"],
            message="Outcome data submitted successfully"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit outcome: {str(e)}"
        )


@router.post("/analyze")
async def analyze_effectiveness(request: EffectivenessAnalysisRequest) -> Dict[str, Any]:
    """
    Analyze recommendation effectiveness based on feedback and outcomes.
    
    This endpoint provides analytics on recommendation performance,
    implementation rates, and farmer satisfaction.
    
    Args:
        request: Analysis request parameters
        
    Returns:
        Effectiveness analysis with metrics
        
    Raises:
        HTTPException: If analysis fails
    """
    try:
        analysis = feedback_agent.analyze_effectiveness(
            recommendation_id=request.recommendation_id,
            farmer_id=request.farmer_id,
            recommendation_type=request.recommendation_type,
            time_period_days=request.time_period_days
        )
        
        return analysis
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze effectiveness: {str(e)}"
        )


@router.get("/correlate/{recommendation_id}")
async def correlate_outcomes(recommendation_id: str) -> Dict[str, Any]:
    """
    Correlate recommendation with actual outcomes.
    
    This endpoint analyzes the correlation between expected and actual
    outcomes to improve recommendation accuracy.
    
    Args:
        recommendation_id: Recommendation ID to analyze
        
    Returns:
        Correlation analysis
        
    Raises:
        HTTPException: If correlation analysis fails
    """
    try:
        correlation = feedback_agent.correlate_outcomes(recommendation_id)
        return correlation
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to correlate outcomes: {str(e)}"
        )


@router.get("/insights")
async def get_improvement_insights(
    recommendation_type: Optional[str] = Query(default=None, description="Recommendation type to analyze"),
    time_period_days: int = Query(default=90, ge=1, le=365, description="Time period in days")
) -> Dict[str, Any]:
    """
    Get insights for improving recommendation accuracy.
    
    This endpoint provides actionable insights based on feedback patterns,
    common challenges, and performance metrics.
    
    Args:
        recommendation_type: Specific type to analyze (optional)
        time_period_days: Time period to analyze (default 90 days)
        
    Returns:
        Improvement insights and recommendations
        
    Raises:
        HTTPException: If insight generation fails
    """
    try:
        insights = feedback_agent.get_improvement_insights(
            recommendation_type=recommendation_type,
            time_period_days=time_period_days
        )
        
        return insights
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate insights: {str(e)}"
        )


@router.get("/farmer/{farmer_id}/history")
async def get_farmer_feedback_history(
    farmer_id: str,
    time_period_days: int = Query(default=90, ge=1, le=365, description="Time period in days")
) -> Dict[str, Any]:
    """
    Get feedback history for a specific farmer.
    
    Args:
        farmer_id: Farmer ID
        time_period_days: Time period to retrieve (default 90 days)
        
    Returns:
        Farmer's feedback history with analytics
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        analysis = feedback_agent.analyze_effectiveness(
            farmer_id=farmer_id,
            time_period_days=time_period_days
        )
        
        return {
            "farmer_id": farmer_id,
            "time_period_days": time_period_days,
            "analytics": analysis
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve feedback history: {str(e)}"
        )


@router.get("/recommendation/{recommendation_id}/feedback")
async def get_recommendation_feedback(recommendation_id: str) -> Dict[str, Any]:
    """
    Get all feedback for a specific recommendation.
    
    Args:
        recommendation_id: Recommendation ID
        
    Returns:
        All feedback for the recommendation
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        if recommendation_id not in feedback_agent.feedback_storage:
            return {
                "recommendation_id": recommendation_id,
                "feedback_count": 0,
                "feedback": []
            }
        
        feedback_list = feedback_agent.feedback_storage[recommendation_id]
        
        return {
            "recommendation_id": recommendation_id,
            "feedback_count": len(feedback_list),
            "feedback": feedback_list
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve feedback: {str(e)}"
        )


@router.get("/patterns/seasonal")
async def get_seasonal_patterns(
    time_window_days: int = Query(default=365, ge=30, le=730, description="Time window in days")
) -> Dict[str, Any]:
    """
    Get seasonal patterns from feedback data.
    
    This endpoint analyzes feedback to identify seasonal trends
    and patterns for different crops and recommendations.
    
    Args:
        time_window_days: Time window for analysis (default 365 days)
        
    Returns:
        Seasonal patterns with confidence scores
        
    Raises:
        HTTPException: If pattern recognition fails
    """
    try:
        patterns = feedback_agent.recognize_seasonal_patterns(time_window_days)
        return patterns
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to recognize seasonal patterns: {str(e)}"
        )


@router.get("/techniques/successful")
async def get_successful_techniques(
    success_threshold: float = Query(default=4.0, ge=1.0, le=5.0, description="Success threshold"),
    min_implementations: int = Query(default=3, ge=1, le=100, description="Minimum implementations")
) -> Dict[str, Any]:
    """
    Get successful farming techniques for knowledge sharing.
    
    This endpoint identifies highly successful techniques that can be
    shared with other farmers in similar conditions.
    
    Args:
        success_threshold: Minimum rating for success (default 4.0)
        min_implementations: Minimum implementations to consider (default 3)
        
    Returns:
        Successful techniques with sharing recommendations
        
    Raises:
        HTTPException: If technique identification fails
    """
    try:
        techniques = feedback_agent.share_successful_techniques(
            success_threshold,
            min_implementations
        )
        return techniques
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to identify successful techniques: {str(e)}"
        )


@router.post("/models/train")
async def train_models() -> Dict[str, Any]:
    """
    Train ML models for continuous improvement.
    
    This endpoint triggers training of recommendation and outcome
    prediction models using accumulated feedback data.
    
    Returns:
        Training results for both models
        
    Raises:
        HTTPException: If training fails
    """
    try:
        results = feedback_agent.train_models()
        return results
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to train models: {str(e)}"
        )
