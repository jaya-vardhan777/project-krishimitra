"""
Feedback Agent for KrishiMitra Platform.

This module implements the Feedback Agent responsible for:
- Collecting farmer feedback on recommendations
- Tracking recommendation outcomes and effectiveness
- Analyzing feedback patterns for continuous improvement
- Building LangChain tools for feedback processing
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from uuid import uuid4

import pandas as pd
from langchain.tools import Tool
from langchain_core.pydantic_v1 import BaseModel as LangChainBaseModel, Field as LangChainField

from ..models.recommendation import (
    RecommendationFeedback,
    FeedbackRating,
    ImplementationStatus,
    RecommendationType
)
from .continuous_learning import ContinuousLearningSystem


class FeedbackAnalysisInput(LangChainBaseModel):
    """Input schema for feedback analysis tool."""
    farmer_id: str = LangChainField(description="Farmer ID to analyze feedback for")
    time_period_days: int = LangChainField(default=30, description="Time period in days to analyze")


class FeedbackCorrelationInput(LangChainBaseModel):
    """Input schema for feedback correlation tool."""
    recommendation_id: str = LangChainField(description="Recommendation ID to correlate")
    outcome_data: dict = LangChainField(description="Outcome data to correlate with recommendation")


class FeedbackAgent:
    """
    Feedback Agent for continuous learning and improvement.
    
    This agent collects farmer feedback, tracks outcomes, and uses
    the data to improve recommendation accuracy over time.
    """
    
    def __init__(self, feedback_storage=None):
        """
        Initialize the Feedback Agent.
        
        Args:
            feedback_storage: Storage backend for feedback data (DynamoDB, etc.)
        """
        self.feedback_storage = feedback_storage or {}
        self.outcome_storage = {}
        self.effectiveness_metrics = {}
        self.learning_system = ContinuousLearningSystem()
        
    def collect_feedback(
        self,
        recommendation_id: str,
        farmer_id: str,
        feedback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Collect and store farmer feedback on a recommendation.
        
        Args:
            recommendation_id: ID of the recommendation
            farmer_id: ID of the farmer providing feedback
            feedback_data: Feedback data including ratings and comments
            
        Returns:
            Processed feedback record with metadata
        """
        feedback_id = str(uuid4())
        
        feedback_record = {
            "feedback_id": feedback_id,
            "recommendation_id": recommendation_id,
            "farmer_id": farmer_id,
            "timestamp": datetime.utcnow().isoformat(),
            "overall_rating": feedback_data.get("overall_rating"),
            "usefulness_rating": feedback_data.get("usefulness_rating"),
            "clarity_rating": feedback_data.get("clarity_rating"),
            "feasibility_rating": feedback_data.get("feasibility_rating"),
            "implementation_status": feedback_data.get("implementation_status"),
            "implementation_challenges": feedback_data.get("implementation_challenges", []),
            "implementation_notes": feedback_data.get("implementation_notes"),
            "outcome_achieved": feedback_data.get("outcome_achieved"),
            "outcome_description": feedback_data.get("outcome_description"),
            "yield_impact": feedback_data.get("yield_impact"),
            "cost_impact": feedback_data.get("cost_impact"),
            "time_impact": feedback_data.get("time_impact"),
            "suggestions_for_improvement": feedback_data.get("suggestions_for_improvement"),
            "would_recommend_to_others": feedback_data.get("would_recommend_to_others"),
            "additional_comments": feedback_data.get("additional_comments"),
            "needs_follow_up": feedback_data.get("needs_follow_up", False),
            "follow_up_reason": feedback_data.get("follow_up_reason")
        }
        
        # Store feedback
        if recommendation_id not in self.feedback_storage:
            self.feedback_storage[recommendation_id] = []
        self.feedback_storage[recommendation_id].append(feedback_record)
        
        # Update effectiveness metrics
        self._update_effectiveness_metrics(recommendation_id, feedback_record)
        
        return feedback_record
    
    def track_outcome(
        self,
        recommendation_id: str,
        farmer_id: str,
        outcome_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Track the actual outcome of implementing a recommendation.
        
        Args:
            recommendation_id: ID of the recommendation
            farmer_id: ID of the farmer
            outcome_data: Actual outcome data (yield, cost, etc.)
            
        Returns:
            Outcome record with correlation analysis
        """
        outcome_id = str(uuid4())
        
        outcome_record = {
            "outcome_id": outcome_id,
            "recommendation_id": recommendation_id,
            "farmer_id": farmer_id,
            "timestamp": datetime.utcnow().isoformat(),
            "actual_yield": outcome_data.get("actual_yield"),
            "expected_yield": outcome_data.get("expected_yield"),
            "yield_variance": self._calculate_variance(
                outcome_data.get("actual_yield"),
                outcome_data.get("expected_yield")
            ),
            "actual_cost": outcome_data.get("actual_cost"),
            "expected_cost": outcome_data.get("expected_cost"),
            "cost_variance": self._calculate_variance(
                outcome_data.get("actual_cost"),
                outcome_data.get("expected_cost")
            ),
            "implementation_time": outcome_data.get("implementation_time"),
            "quality_metrics": outcome_data.get("quality_metrics", {}),
            "environmental_impact": outcome_data.get("environmental_impact", {}),
            "farmer_satisfaction": outcome_data.get("farmer_satisfaction")
        }
        
        # Store outcome
        if recommendation_id not in self.outcome_storage:
            self.outcome_storage[recommendation_id] = []
        self.outcome_storage[recommendation_id].append(outcome_record)
        
        return outcome_record
    
    def analyze_effectiveness(
        self,
        recommendation_id: Optional[str] = None,
        farmer_id: Optional[str] = None,
        recommendation_type: Optional[str] = None,
        time_period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze recommendation effectiveness based on feedback and outcomes.
        
        Args:
            recommendation_id: Specific recommendation to analyze (optional)
            farmer_id: Analyze recommendations for specific farmer (optional)
            recommendation_type: Analyze specific type of recommendations (optional)
            time_period_days: Time period to analyze (default 30 days)
            
        Returns:
            Effectiveness analysis with metrics and insights
        """
        cutoff_date = datetime.utcnow() - timedelta(days=time_period_days)
        
        # Collect relevant feedback
        feedback_data = []
        for rec_id, feedbacks in self.feedback_storage.items():
            if recommendation_id and rec_id != recommendation_id:
                continue
            
            for feedback in feedbacks:
                feedback_date = datetime.fromisoformat(feedback["timestamp"])
                if feedback_date >= cutoff_date:
                    if farmer_id and feedback["farmer_id"] != farmer_id:
                        continue
                    feedback_data.append(feedback)
        
        if not feedback_data:
            return {
                "total_feedback": 0,
                "message": "No feedback data available for the specified criteria"
            }
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(feedback_data)
        
        # Calculate metrics
        analysis = {
            "total_feedback": len(df),
            "time_period_days": time_period_days,
            "average_overall_rating": df["overall_rating"].mean() if "overall_rating" in df else None,
            "average_usefulness_rating": df["usefulness_rating"].mean() if "usefulness_rating" in df else None,
            "average_clarity_rating": df["clarity_rating"].mean() if "clarity_rating" in df else None,
            "average_feasibility_rating": df["feasibility_rating"].mean() if "feasibility_rating" in df else None,
            "implementation_rate": (df["implementation_status"] == "completed").sum() / len(df) * 100,
            "outcome_achieved_rate": df["outcome_achieved"].sum() / len(df) * 100 if "outcome_achieved" in df else None,
            "would_recommend_rate": df["would_recommend_to_others"].sum() / len(df) * 100 if "would_recommend_to_others" in df else None,
            "average_yield_impact": df["yield_impact"].mean() if "yield_impact" in df else None,
            "average_cost_impact": df["cost_impact"].mean() if "cost_impact" in df else None,
            "needs_follow_up_count": df["needs_follow_up"].sum() if "needs_follow_up" in df else 0
        }
        
        # Implementation status breakdown
        if "implementation_status" in df:
            analysis["implementation_status_breakdown"] = df["implementation_status"].value_counts().to_dict()
        
        # Common challenges
        if "implementation_challenges" in df:
            all_challenges = []
            for challenges in df["implementation_challenges"]:
                if challenges:
                    all_challenges.extend(challenges)
            if all_challenges:
                challenge_counts = pd.Series(all_challenges).value_counts()
                analysis["common_challenges"] = challenge_counts.head(5).to_dict()
        
        return analysis
    
    def correlate_outcomes(
        self,
        recommendation_id: str
    ) -> Dict[str, Any]:
        """
        Correlate recommendation with actual outcomes for accuracy improvement.
        
        Args:
            recommendation_id: ID of the recommendation to analyze
            
        Returns:
            Correlation analysis between expected and actual outcomes
        """
        if recommendation_id not in self.outcome_storage:
            return {
                "recommendation_id": recommendation_id,
                "message": "No outcome data available for this recommendation"
            }
        
        outcomes = self.outcome_storage[recommendation_id]
        df = pd.DataFrame(outcomes)
        
        correlation_analysis = {
            "recommendation_id": recommendation_id,
            "total_outcomes": len(df),
            "yield_accuracy": self._calculate_accuracy(df, "yield_variance"),
            "cost_accuracy": self._calculate_accuracy(df, "cost_variance"),
            "average_satisfaction": df["farmer_satisfaction"].mean() if "farmer_satisfaction" in df else None,
            "variance_analysis": {
                "yield": {
                    "mean_variance": df["yield_variance"].mean() if "yield_variance" in df else None,
                    "std_variance": df["yield_variance"].std() if "yield_variance" in df else None
                },
                "cost": {
                    "mean_variance": df["cost_variance"].mean() if "cost_variance" in df else None,
                    "std_variance": df["cost_variance"].std() if "cost_variance" in df else None
                }
            }
        }
        
        return correlation_analysis
    
    def get_improvement_insights(
        self,
        recommendation_type: Optional[str] = None,
        time_period_days: int = 90
    ) -> Dict[str, Any]:
        """
        Generate insights for improving recommendation accuracy.
        
        Args:
            recommendation_type: Specific type to analyze (optional)
            time_period_days: Time period to analyze (default 90 days)
            
        Returns:
            Insights and suggestions for improvement
        """
        effectiveness = self.analyze_effectiveness(
            recommendation_type=recommendation_type,
            time_period_days=time_period_days
        )
        
        insights = {
            "time_period_days": time_period_days,
            "recommendation_type": recommendation_type,
            "overall_performance": self._categorize_performance(
                effectiveness.get("average_overall_rating", 0)
            ),
            "strengths": [],
            "areas_for_improvement": [],
            "recommendations": []
        }
        
        # Identify strengths
        if effectiveness.get("average_usefulness_rating", 0) >= 4:
            insights["strengths"].append("High usefulness ratings indicate relevant recommendations")
        if effectiveness.get("implementation_rate", 0) >= 70:
            insights["strengths"].append("High implementation rate shows feasible recommendations")
        if effectiveness.get("would_recommend_rate", 0) >= 80:
            insights["strengths"].append("High recommendation rate indicates farmer satisfaction")
        
        # Identify areas for improvement
        if effectiveness.get("average_clarity_rating", 0) < 3.5:
            insights["areas_for_improvement"].append("Clarity of recommendations needs improvement")
            insights["recommendations"].append("Simplify language and provide more detailed step-by-step instructions")
        
        if effectiveness.get("average_feasibility_rating", 0) < 3.5:
            insights["areas_for_improvement"].append("Feasibility concerns from farmers")
            insights["recommendations"].append("Better assess farmer resources and constraints before recommendations")
        
        if effectiveness.get("implementation_rate", 0) < 50:
            insights["areas_for_improvement"].append("Low implementation rate")
            insights["recommendations"].append("Investigate barriers to implementation and provide more support")
        
        # Common challenges
        if "common_challenges" in effectiveness:
            insights["common_challenges"] = effectiveness["common_challenges"]
            insights["recommendations"].append("Address common challenges in future recommendations")
        
        return insights
    
    def _update_effectiveness_metrics(
        self,
        recommendation_id: str,
        feedback_record: Dict[str, Any]
    ) -> None:
        """Update effectiveness metrics based on new feedback."""
        if recommendation_id not in self.effectiveness_metrics:
            self.effectiveness_metrics[recommendation_id] = {
                "total_feedback": 0,
                "total_rating": 0,
                "implementation_count": 0,
                "success_count": 0
            }
        
        metrics = self.effectiveness_metrics[recommendation_id]
        metrics["total_feedback"] += 1
        
        if feedback_record.get("overall_rating"):
            metrics["total_rating"] += feedback_record["overall_rating"]
        
        if feedback_record.get("implementation_status") == "completed":
            metrics["implementation_count"] += 1
        
        if feedback_record.get("outcome_achieved"):
            metrics["success_count"] += 1
    
    def _calculate_variance(
        self,
        actual: Optional[float],
        expected: Optional[float]
    ) -> Optional[float]:
        """Calculate variance between actual and expected values."""
        if actual is None or expected is None or expected == 0:
            return None
        return ((actual - expected) / expected) * 100
    
    def _calculate_accuracy(
        self,
        df: pd.DataFrame,
        variance_column: str
    ) -> Optional[float]:
        """Calculate accuracy based on variance."""
        if variance_column not in df or df[variance_column].isna().all():
            return None
        
        # Accuracy is inverse of absolute variance
        mean_abs_variance = df[variance_column].abs().mean()
        accuracy = max(0, 100 - mean_abs_variance)
        return accuracy
    
    def _categorize_performance(self, rating: float) -> str:
        """Categorize performance based on rating."""
        if rating >= 4.5:
            return "Excellent"
        elif rating >= 4.0:
            return "Good"
        elif rating >= 3.0:
            return "Average"
        elif rating >= 2.0:
            return "Below Average"
        else:
            return "Poor"
    
    def get_langchain_tools(self) -> List[Tool]:
        """
        Get LangChain tools for feedback processing.
        
        Returns:
            List of LangChain Tool objects for feedback operations
        """
        tools = [
            Tool(
                name="collect_feedback",
                description="Collect farmer feedback on a recommendation. Input should be a JSON with recommendation_id, farmer_id, and feedback_data.",
                func=lambda x: self.collect_feedback(**eval(x))
            ),
            Tool(
                name="track_outcome",
                description="Track the actual outcome of implementing a recommendation. Input should be a JSON with recommendation_id, farmer_id, and outcome_data.",
                func=lambda x: self.track_outcome(**eval(x))
            ),
            Tool(
                name="analyze_effectiveness",
                description="Analyze recommendation effectiveness. Input should be a JSON with optional recommendation_id, farmer_id, recommendation_type, and time_period_days.",
                func=lambda x: self.analyze_effectiveness(**eval(x))
            ),
            Tool(
                name="correlate_outcomes",
                description="Correlate recommendation with actual outcomes. Input should be a JSON with recommendation_id.",
                func=lambda x: self.correlate_outcomes(**eval(x))
            ),
            Tool(
                name="get_improvement_insights",
                description="Get insights for improving recommendations. Input should be a JSON with optional recommendation_type and time_period_days.",
                func=lambda x: self.get_improvement_insights(**eval(x))
            )
        ]
        
        return tools
    
    def get_learning_callback(self):
        """Get LangChain callback for continuous learning."""
        return self.learning_system.get_learning_callback()
    
    def recognize_seasonal_patterns(self, time_window_days: int = 365) -> Dict[str, Any]:
        """
        Recognize seasonal patterns from feedback data.
        
        Args:
            time_window_days: Time window for pattern analysis
            
        Returns:
            Identified seasonal patterns
        """
        # Collect all feedback data
        all_feedback = []
        for feedbacks in self.feedback_storage.values():
            all_feedback.extend(feedbacks)
        
        return self.learning_system.recognize_seasonal_patterns(
            all_feedback,
            time_window_days
        )
    
    def share_successful_techniques(
        self,
        success_threshold: float = 4.0,
        min_implementations: int = 3
    ) -> Dict[str, Any]:
        """
        Identify and share successful farming techniques.
        
        Args:
            success_threshold: Minimum rating for success
            min_implementations: Minimum implementations to consider
            
        Returns:
            Successful techniques with sharing recommendations
        """
        # Collect all feedback data
        all_feedback = []
        for feedbacks in self.feedback_storage.values():
            all_feedback.extend(feedbacks)
        
        return self.learning_system.share_successful_techniques(
            all_feedback,
            success_threshold,
            min_implementations
        )
    
    def train_models(self) -> Dict[str, Any]:
        """
        Train ML models for continuous improvement.
        
        Returns:
            Training results for both models
        """
        # Collect training data
        all_feedback = []
        for feedbacks in self.feedback_storage.values():
            all_feedback.extend(feedbacks)
        
        # Train recommendation model
        recommendation_results = self.learning_system.train_recommendation_model(all_feedback)
        
        # Train outcome predictor
        all_outcomes = []
        for outcomes in self.outcome_storage.values():
            all_outcomes.extend(outcomes)
        
        outcome_results = self.learning_system.train_outcome_predictor(all_outcomes)
        
        return {
            "recommendation_model": recommendation_results,
            "outcome_predictor": outcome_results,
            "timestamp": datetime.utcnow().isoformat()
        }
