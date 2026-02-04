"""
Recommendation record data models using Pydantic.

This module defines models for storing agricultural recommendations, context,
and farmer feedback for continuous learning.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any, Union
from enum import Enum

from pydantic import BaseModel, Field, validator, ConfigDict
from pydantic.types import confloat, conint, constr


class QueryType(str, Enum):
    """Types of farmer queries."""
    CROP_SELECTION = "crop_selection"
    IRRIGATION = "irrigation"
    FERTILIZER = "fertilizer"
    PEST_CONTROL = "pest_control"
    DISEASE_MANAGEMENT = "disease_management"
    HARVEST_TIMING = "harvest_timing"
    MARKET_ADVICE = "market_advice"
    WEATHER_GUIDANCE = "weather_guidance"
    SOIL_MANAGEMENT = "soil_management"
    GENERAL_ADVICE = "general_advice"


class Season(str, Enum):
    """Agricultural seasons in India."""
    KHARIF = "kharif"  # Monsoon season (June-October)
    RABI = "rabi"      # Winter season (November-April)
    ZAID = "zaid"      # Summer season (April-June)


class RecommendationPriority(str, Enum):
    """Priority levels for recommendations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ImplementationStatus(str, Enum):
    """Status of recommendation implementation."""
    NOT_IMPLEMENTED = "not_implemented"
    PARTIALLY_IMPLEMENTED = "partially_implemented"
    FULLY_IMPLEMENTED = "fully_implemented"
    CANNOT_IMPLEMENT = "cannot_implement"


class RecommendationContext(BaseModel):
    """Context information for the recommendation."""
    model_config = ConfigDict(
        validate_assignment=True,
        use_enum_values=True
    )
    
    crop_type: Optional[constr(min_length=1, max_length=50)] = Field(None, description="Primary crop type")
    season: Season = Field(..., description="Agricultural season")
    weather_conditions: Dict[str, Any] = Field(default_factory=dict, description="Current weather context")
    soil_conditions: Dict[str, Any] = Field(default_factory=dict, description="Current soil context")
    market_conditions: Dict[str, Any] = Field(default_factory=dict, description="Market context")
    farm_size_acres: Optional[confloat(gt=0, le=10000)] = Field(None, description="Farm size in acres")
    budget_range: Optional[constr(max_length=50)] = Field(None, description="Budget range category")
    urgency_level: RecommendationPriority = Field(RecommendationPriority.MEDIUM, description="Urgency level")


class ActionItem(BaseModel):
    """Individual action item within a recommendation."""
    model_config = ConfigDict(validate_assignment=True)
    
    action_id: constr(min_length=1, max_length=50) = Field(..., description="Unique action identifier")
    description: constr(min_length=1, max_length=500) = Field(..., description="Action description")
    timeline: constr(min_length=1, max_length=100) = Field(..., description="Recommended timeline")
    cost_estimate: Optional[confloat(ge=0, le=1000000)] = Field(None, description="Estimated cost in INR")
    materials_needed: List[str] = Field(default_factory=list, description="Required materials")
    difficulty_level: constr(regex=r'^(easy|medium|hard)$') = Field("medium", description="Implementation difficulty")
    expected_benefit: Optional[constr(max_length=200)] = Field(None, description="Expected benefit")


class Recommendation(BaseModel):
    """Agricultural recommendation details."""
    model_config = ConfigDict(validate_assignment=True)
    
    title: constr(min_length=1, max_length=200) = Field(..., description="Recommendation title")
    description: constr(min_length=1, max_length=1000) = Field(..., description="Detailed description")
    action_items: List[ActionItem] = Field(default_factory=list, description="Specific action items")
    expected_outcome: constr(min_length=1, max_length=500) = Field(..., description="Expected outcome")
    confidence: confloat(ge=0, le=1) = Field(..., description="Confidence score (0-1)")
    priority: RecommendationPriority = Field(RecommendationPriority.MEDIUM, description="Priority level")
    category: QueryType = Field(..., description="Recommendation category")
    scientific_basis: Optional[constr(max_length=500)] = Field(None, description="Scientific justification")
    local_adaptation: Optional[constr(max_length=300)] = Field(None, description="Local adaptation notes")
    
    @validator('action_items')
    def validate_action_items(cls, v):
        """Ensure action items have unique IDs."""
        if v:
            action_ids = [item.action_id for item in v]
            if len(action_ids) != len(set(action_ids)):
                raise ValueError("Action items must have unique IDs")
        return v


class OutcomeMetrics(BaseModel):
    """Quantitative outcome measurements."""
    model_config = ConfigDict(validate_assignment=True)
    
    yield_change_percent: Optional[confloat(ge=-100, le=1000)] = Field(None, description="Yield change percentage")
    cost_savings_inr: Optional[confloat(ge=0, le=1000000)] = Field(None, description="Cost savings in INR")
    time_saved_hours: Optional[confloat(ge=0, le=1000)] = Field(None, description="Time saved in hours")
    water_savings_percent: Optional[confloat(ge=0, le=100)] = Field(None, description="Water savings percentage")
    quality_improvement: Optional[constr(regex=r'^(none|slight|moderate|significant)$')] = Field(None, description="Quality improvement level")
    environmental_impact: Optional[constr(regex=r'^(negative|neutral|positive)$')] = Field(None, description="Environmental impact")


class Feedback(BaseModel):
    """Farmer feedback on recommendation implementation and outcomes."""
    model_config = ConfigDict(
        validate_assignment=True,
        use_enum_values=True
    )
    
    implemented: ImplementationStatus = Field(ImplementationStatus.NOT_IMPLEMENTED, description="Implementation status")
    effectiveness_rating: Optional[conint(ge=1, le=5)] = Field(None, description="Effectiveness rating (1-5)")
    ease_of_implementation: Optional[conint(ge=1, le=5)] = Field(None, description="Implementation ease (1-5)")
    comments: Optional[constr(max_length=1000)] = Field(None, description="Farmer comments")
    outcome_metrics: Optional[OutcomeMetrics] = Field(None, description="Quantitative outcomes")
    challenges_faced: List[str] = Field(default_factory=list, description="Implementation challenges")
    suggestions: Optional[constr(max_length=500)] = Field(None, description="Farmer suggestions")
    would_recommend: Optional[bool] = Field(None, description="Would recommend to others")
    follow_up_needed: bool = Field(False, description="Whether follow-up is needed")
    feedback_date: datetime = Field(default_factory=datetime.utcnow, description="Feedback submission date")
    
    @validator('effectiveness_rating')
    def validate_effectiveness_with_implementation(cls, v, values):
        """Effectiveness rating should only be provided if implemented."""
        if v is not None and values.get('implemented') == ImplementationStatus.NOT_IMPLEMENTED:
            raise ValueError("Cannot rate effectiveness without implementation")
        return v


class RecommendationRecord(BaseModel):
    """Complete recommendation record with context and feedback."""
    model_config = ConfigDict(
        validate_assignment=True,
        use_enum_values=True
    )
    
    recommendation_id: constr(min_length=1, max_length=50) = Field(..., description="Unique recommendation identifier")
    farmer_id: constr(min_length=1, max_length=50) = Field(..., description="Farmer identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Recommendation creation time")
    query_type: QueryType = Field(..., description="Type of farmer query")
    original_query: Optional[constr(max_length=1000)] = Field(None, description="Original farmer query text")
    context: RecommendationContext = Field(..., description="Recommendation context")
    recommendation: Recommendation = Field(..., description="The recommendation details")
    feedback: Optional[Feedback] = Field(None, description="Farmer feedback")
    agent_version: constr(min_length=1, max_length=20) = Field("1.0.0", description="AI agent version")
    data_sources: List[str] = Field(default_factory=list, description="Data sources used")
    processing_time_ms: Optional[conint(ge=0, le=60000)] = Field(None, description="Processing time in milliseconds")
    is_active: bool = Field(True, description="Whether recommendation is active")
    
    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = self.model_dump()
        
        # Convert datetime objects to ISO strings
        item['timestamp'] = self.timestamp.isoformat()
        if self.feedback and self.feedback.feedback_date:
            item['feedback']['feedback_date'] = self.feedback.feedback_date.isoformat()
        
        # Convert floats to Decimal for DynamoDB
        def convert_floats_to_decimal(obj):
            if isinstance(obj, dict):
                return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_floats_to_decimal(item) for item in obj]
            elif isinstance(obj, float):
                return Decimal(str(obj))
            return obj
        
        return convert_floats_to_decimal(item)
    
    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> 'RecommendationRecord':
        """Create instance from DynamoDB item."""
        # Convert ISO strings back to datetime objects
        if 'timestamp' in item and isinstance(item['timestamp'], str):
            item['timestamp'] = datetime.fromisoformat(item['timestamp'])
        
        if 'feedback' in item and item['feedback'] and 'feedback_date' in item['feedback']:
            if isinstance(item['feedback']['feedback_date'], str):
                item['feedback']['feedback_date'] = datetime.fromisoformat(item['feedback']['feedback_date'])
        
        # Convert Decimal back to float
        def convert_decimal_to_float(obj):
            if isinstance(obj, dict):
                return {k: convert_decimal_to_float(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_decimal_to_float(item) for item in obj]
            elif isinstance(obj, Decimal):
                return float(obj)
            return obj
        
        item = convert_decimal_to_float(item)
        return cls(**item)
    
    def add_feedback(self, feedback: Feedback) -> None:
        """Add or update feedback for this recommendation."""
        self.feedback = feedback
    
    def get_effectiveness_score(self) -> Optional[float]:
        """Calculate overall effectiveness score from feedback."""
        if not self.feedback or self.feedback.effectiveness_rating is None:
            return None
        
        # Base score from effectiveness rating (1-5 scale converted to 0-1)
        base_score = (self.feedback.effectiveness_rating - 1) / 4
        
        # Adjust based on implementation status
        if self.feedback.implemented == ImplementationStatus.FULLY_IMPLEMENTED:
            implementation_factor = 1.0
        elif self.feedback.implemented == ImplementationStatus.PARTIALLY_IMPLEMENTED:
            implementation_factor = 0.7
        else:
            implementation_factor = 0.3
        
        return base_score * implementation_factor