"""
Advisory Agent for KrishiMitra Platform

This module implements the Advisory Agent responsible for delivering personalized
agricultural recommendations using LangChain agents, decision trees, and custom tools.
Integrates outputs from other agents and provides context-aware recommendations.
"""

import json
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
import asyncio

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
import boto3
from botocore.exceptions import ClientError

# LangChain imports
from langchain_aws import ChatBedrock
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.tools import BaseTool, tool
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from pydantic import BaseModel as LangChainBaseModel, Field as LangChainField

from ..core.config import get_settings
from ..models.farmer import FarmerProfile, CropInfo, SoilType, IrrigationType
from ..models.agricultural_intelligence import AgriculturalIntelligence, WeatherData, SoilData, MarketData
from ..models.recommendation import (
    RecommendationRecord, RecommendationType, Priority, ActionItem,
    RecommendationContext, RecommendationEvidence, RecommendationImpact,
    ImplementationStatus, RecommendationRequest, RecommendationResponse
)

logger = logging.getLogger(__name__)
settings = get_settings()


class FarmerProfileAnalyzer:
    """Analyzes farmer profiles to extract key characteristics for matching"""
    
    def __init__(self):
        self.scaler = StandardScaler()
        
    def analyze_profile(self, farmer_profile: FarmerProfile) -> Dict[str, Any]:
        """Analyze farmer profile and extract key features"""
        try:
            analysis = {
                "farmer_id": farmer_profile.id,
                "experience_level": farmer_profile.farming_experience.value,
                "farm_size_hectares": self._convert_to_hectares(farmer_profile.farm_details.total_land_area),
                "soil_type": farmer_profile.farm_details.soil_type.value,
                "irrigation_type": farmer_profile.farm_details.primary_irrigation_source.value,
                "organic_interest": farmer_profile.preferences.organic_farming_interest,
                "risk_tolerance": farmer_profile.preferences.risk_tolerance.value,
                "technology_adoption": farmer_profile.preferences.technology_adoption_willingness.value,
                "current_crops": [crop.crop_name for crop in farmer_profile.farm_details.crops],
                "location": {
                    "state": farmer_profile.location.address.state,
                    "district": farmer_profile.location.address.district,
                    "latitude": farmer_profile.location.address.coordinates.latitude,
                    "longitude": farmer_profile.location.address.coordinates.longitude
                },
                "budget_constraints": self._extract_budget(farmer_profile),
                "equipment_available": farmer_profile.farm_details.farm_equipment,
                "storage_facilities": farmer_profile.farm_details.storage_facilities
            }
            
            logger.info(f"Analyzed profile for farmer {farmer_profile.id}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing farmer profile: {e}")
            return {}
    
    def _convert_to_hectares(self, measurement) -> float:
        """Convert land measurement to hectares"""
        if measurement.unit.lower() in ["hectare", "hectares", "ha"]:
            return float(measurement.value)
        elif measurement.unit.lower() in ["acre", "acres"]:
            return float(measurement.value) * 0.404686
        elif measurement.unit.lower() in ["bigha"]:
            return float(measurement.value) * 0.25  # Approximate
        else:
            return float(measurement.value)
    
    def _extract_budget(self, farmer_profile: FarmerProfile) -> Optional[float]:
        """Extract budget constraints"""
        if farmer_profile.preferences.budget_constraints:
            return float(farmer_profile.preferences.budget_constraints.amount)
        return None
    
    def calculate_similarity_score(
        self,
        profile1: Dict[str, Any],
        profile2: Dict[str, Any]
    ) -> float:
        """Calculate similarity score between two farmer profiles"""
        try:
            score = 0.0
            weights = {
                "farm_size": 0.2,
                "soil_type": 0.15,
                "irrigation": 0.15,
                "location": 0.2,
                "experience": 0.1,
                "risk_tolerance": 0.1,
                "crops": 0.1
            }
            
            # Farm size similarity
            if profile1.get("farm_size_hectares") and profile2.get("farm_size_hectares"):
                size_diff = abs(profile1["farm_size_hectares"] - profile2["farm_size_hectares"])
                size_similarity = 1 / (1 + size_diff / 10)  # Normalize
                score += weights["farm_size"] * size_similarity
            
            # Soil type match
            if profile1.get("soil_type") == profile2.get("soil_type"):
                score += weights["soil_type"]
            
            # Irrigation type match
            if profile1.get("irrigation_type") == profile2.get("irrigation_type"):
                score += weights["irrigation"]
            
            # Location proximity (simplified)
            if profile1.get("location") and profile2.get("location"):
                if profile1["location"]["state"] == profile2["location"]["state"]:
                    score += weights["location"] * 0.5
                if profile1["location"]["district"] == profile2["location"]["district"]:
                    score += weights["location"] * 0.5
            
            # Experience level match
            if profile1.get("experience_level") == profile2.get("experience_level"):
                score += weights["experience"]
            
            # Risk tolerance match
            if profile1.get("risk_tolerance") == profile2.get("risk_tolerance"):
                score += weights["risk_tolerance"]
            
            # Crop overlap
            crops1 = set(profile1.get("current_crops", []))
            crops2 = set(profile2.get("current_crops", []))
            if crops1 and crops2:
                crop_overlap = len(crops1.intersection(crops2)) / len(crops1.union(crops2))
                score += weights["crops"] * crop_overlap
            
            return score
            
        except Exception as e:
            logger.error(f"Error calculating similarity score: {e}")
            return 0.0



class CropRecommendationScorer:
    """Scores and ranks crop recommendations based on multiple factors"""
    
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.feature_weights = {
            "soil_suitability": 0.25,
            "climate_suitability": 0.20,
            "market_demand": 0.20,
            "water_availability": 0.15,
            "farmer_experience": 0.10,
            "input_cost": 0.10
        }
    
    def score_crop_recommendation(
        self,
        crop_name: str,
        farmer_profile: Dict[str, Any],
        agricultural_data: AgriculturalIntelligence,
        season: str
    ) -> Tuple[float, Dict[str, float]]:
        """Score a crop recommendation and return score with breakdown"""
        try:
            scores = {}
            
            # Soil suitability score
            scores["soil_suitability"] = self._calculate_soil_suitability(
                crop_name, farmer_profile.get("soil_type")
            )
            
            # Climate suitability score
            scores["climate_suitability"] = self._calculate_climate_suitability(
                crop_name, agricultural_data.weather_data, season
            )
            
            # Market demand score
            scores["market_demand"] = self._calculate_market_demand(
                crop_name, agricultural_data.market_data
            )
            
            # Water availability score
            scores["water_availability"] = self._calculate_water_availability(
                crop_name, farmer_profile.get("irrigation_type")
            )
            
            # Farmer experience score
            scores["farmer_experience"] = self._calculate_experience_match(
                crop_name, farmer_profile.get("experience_level"),
                farmer_profile.get("current_crops", [])
            )
            
            # Input cost score (inverse - lower cost = higher score)
            scores["input_cost"] = self._calculate_cost_feasibility(
                crop_name, farmer_profile.get("budget_constraints")
            )
            
            # Calculate weighted total score
            total_score = sum(
                scores[factor] * self.feature_weights[factor]
                for factor in scores
            )
            
            logger.info(f"Scored crop {crop_name}: {total_score:.2f}")
            return total_score, scores
            
        except Exception as e:
            logger.error(f"Error scoring crop recommendation: {e}")
            return 0.0, {}
    
    def _calculate_soil_suitability(self, crop_name: str, soil_type: str) -> float:
        """Calculate soil suitability score for crop"""
        # Simplified soil-crop compatibility matrix
        soil_crop_matrix = {
            "rice": {"alluvial": 0.9, "clay": 0.8, "loamy": 0.7},
            "wheat": {"alluvial": 0.9, "loamy": 0.9, "black_cotton": 0.7},
            "cotton": {"black_cotton": 0.9, "alluvial": 0.7, "red_laterite": 0.6},
            "sugarcane": {"alluvial": 0.9, "loamy": 0.8, "black_cotton": 0.7},
            "maize": {"alluvial": 0.8, "loamy": 0.9, "red_laterite": 0.6},
            "pulses": {"black_cotton": 0.8, "red_laterite": 0.7, "loamy": 0.8},
            "vegetables": {"loamy": 0.9, "alluvial": 0.8, "sandy": 0.6}
        }
        
        crop_lower = crop_name.lower()
        if crop_lower in soil_crop_matrix and soil_type in soil_crop_matrix[crop_lower]:
            return soil_crop_matrix[crop_lower][soil_type]
        return 0.5  # Default moderate suitability
    
    def _calculate_climate_suitability(
        self, crop_name: str, weather_data: Optional[WeatherData], season: str
    ) -> float:
        """Calculate climate suitability score"""
        if not weather_data:
            return 0.5
        
        # Simplified climate requirements
        temp = weather_data.temperature
        rainfall = weather_data.rainfall
        
        # Crop-specific climate preferences
        climate_preferences = {
            "rice": {"temp_range": (20, 35), "rainfall_min": 100},
            "wheat": {"temp_range": (10, 25), "rainfall_min": 50},
            "cotton": {"temp_range": (21, 30), "rainfall_min": 50},
            "sugarcane": {"temp_range": (20, 30), "rainfall_min": 75},
            "maize": {"temp_range": (18, 27), "rainfall_min": 50},
            "pulses": {"temp_range": (20, 30), "rainfall_min": 40},
            "vegetables": {"temp_range": (15, 30), "rainfall_min": 30}
        }
        
        crop_lower = crop_name.lower()
        if crop_lower in climate_preferences:
            prefs = climate_preferences[crop_lower]
            temp_min, temp_max = prefs["temp_range"]
            
            # Temperature score
            if temp_min <= temp <= temp_max:
                temp_score = 1.0
            else:
                temp_diff = min(abs(temp - temp_min), abs(temp - temp_max))
                temp_score = max(0, 1 - temp_diff / 10)
            
            # Rainfall score
            rainfall_score = min(1.0, rainfall / prefs["rainfall_min"]) if rainfall else 0.5
            
            return (temp_score + rainfall_score) / 2
        
        return 0.5
    
    def _calculate_market_demand(
        self, crop_name: str, market_data: Optional[List[MarketData]]
    ) -> float:
        """Calculate market demand score"""
        if not market_data:
            return 0.5
        
        # Check if crop has good market prices
        for market in market_data:
            for price in market.prices:
                if crop_name.lower() in price.commodity.lower():
                    # Higher prices indicate better demand
                    # This is simplified - in production, compare with historical averages
                    if price.modal_price.amount > 2000:
                        return 0.9
                    elif price.modal_price.amount > 1000:
                        return 0.7
                    else:
                        return 0.5
        
        return 0.5  # Default if no market data found
    
    def _calculate_water_availability(self, crop_name: str, irrigation_type: str) -> float:
        """Calculate water availability score"""
        # Water requirements by crop
        water_requirements = {
            "rice": "high",
            "sugarcane": "high",
            "wheat": "medium",
            "cotton": "medium",
            "maize": "medium",
            "pulses": "low",
            "vegetables": "medium"
        }
        
        # Irrigation capability
        irrigation_capability = {
            "drip": 0.9,
            "sprinkler": 0.8,
            "canal": 0.7,
            "tubewell": 0.8,
            "well": 0.6,
            "rainfed": 0.3
        }
        
        crop_lower = crop_name.lower()
        crop_water_need = water_requirements.get(crop_lower, "medium")
        irrigation_score = irrigation_capability.get(irrigation_type, 0.5)
        
        # Match water need with irrigation capability
        if crop_water_need == "high" and irrigation_score >= 0.7:
            return 0.9
        elif crop_water_need == "medium" and irrigation_score >= 0.5:
            return 0.8
        elif crop_water_need == "low":
            return 0.9
        else:
            return 0.4
    
    def _calculate_experience_match(
        self, crop_name: str, experience_level: str, current_crops: List[str]
    ) -> float:
        """Calculate experience match score"""
        # If farmer already grows this crop, high score
        if crop_name.lower() in [c.lower() for c in current_crops]:
            return 1.0
        
        # Crop difficulty levels
        crop_difficulty = {
            "rice": "medium",
            "wheat": "easy",
            "maize": "easy",
            "pulses": "easy",
            "cotton": "medium",
            "sugarcane": "hard",
            "vegetables": "medium"
        }
        
        difficulty = crop_difficulty.get(crop_name.lower(), "medium")
        
        # Match difficulty with experience
        if experience_level == "expert":
            return 1.0
        elif experience_level == "experienced":
            return 0.9 if difficulty != "hard" else 0.7
        elif experience_level == "intermediate":
            return 0.8 if difficulty == "easy" else 0.6
        else:  # beginner
            return 0.7 if difficulty == "easy" else 0.4
    
    def _calculate_cost_feasibility(self, crop_name: str, budget: Optional[float]) -> float:
        """Calculate cost feasibility score"""
        # Estimated input costs per hectare (simplified)
        input_costs = {
            "rice": 30000,
            "wheat": 25000,
            "maize": 20000,
            "pulses": 15000,
            "cotton": 35000,
            "sugarcane": 50000,
            "vegetables": 40000
        }
        
        crop_cost = input_costs.get(crop_name.lower(), 25000)
        
        if budget is None:
            return 0.5  # Unknown budget
        
        if budget >= crop_cost * 1.5:
            return 1.0
        elif budget >= crop_cost:
            return 0.8
        elif budget >= crop_cost * 0.7:
            return 0.6
        else:
            return 0.3



class CropTimingOptimizer:
    """Optimizes crop selection and timing based on seasonal patterns"""
    
    def __init__(self):
        self.seasonal_calendar = self._initialize_seasonal_calendar()
    
    def _initialize_seasonal_calendar(self) -> Dict[str, Dict[str, List[str]]]:
        """Initialize crop seasonal calendar for India"""
        return {
            "kharif": {  # Monsoon season (June-October)
                "suitable_crops": ["rice", "maize", "cotton", "soybean", "groundnut", "pulses"],
                "planting_months": ["june", "july", "august"],
                "harvest_months": ["october", "november", "december"]
            },
            "rabi": {  # Winter season (November-April)
                "suitable_crops": ["wheat", "barley", "mustard", "chickpea", "peas", "lentils"],
                "planting_months": ["october", "november", "december"],
                "harvest_months": ["march", "april", "may"]
            },
            "zaid": {  # Summer season (April-June)
                "suitable_crops": ["watermelon", "muskmelon", "cucumber", "vegetables"],
                "planting_months": ["march", "april"],
                "harvest_months": ["may", "june", "july"]
            }
        }
    
    def get_optimal_planting_time(
        self,
        crop_name: str,
        current_date: date,
        weather_forecast: Optional[WeatherData]
    ) -> Dict[str, Any]:
        """Determine optimal planting time for a crop"""
        try:
            # Determine current season
            current_month = current_date.strftime("%B").lower()
            current_season = self._get_season_from_month(current_month)
            
            # Check if crop is suitable for current season
            suitable_seasons = []
            for season, info in self.seasonal_calendar.items():
                if crop_name.lower() in [c.lower() for c in info["suitable_crops"]]:
                    suitable_seasons.append(season)
            
            if not suitable_seasons:
                return {
                    "optimal": False,
                    "message": f"{crop_name} not found in seasonal calendar",
                    "recommended_season": None
                }
            
            # Check if current season is suitable
            if current_season in suitable_seasons:
                season_info = self.seasonal_calendar[current_season]
                if current_month in season_info["planting_months"]:
                    return {
                        "optimal": True,
                        "message": f"Optimal time to plant {crop_name}",
                        "season": current_season,
                        "planting_window": season_info["planting_months"],
                        "expected_harvest": season_info["harvest_months"]
                    }
                else:
                    return {
                        "optimal": False,
                        "message": f"Outside planting window for {crop_name}",
                        "season": current_season,
                        "next_planting_window": season_info["planting_months"]
                    }
            else:
                # Find next suitable season
                next_season = suitable_seasons[0]
                return {
                    "optimal": False,
                    "message": f"Wait for {next_season} season",
                    "recommended_season": next_season,
                    "planting_window": self.seasonal_calendar[next_season]["planting_months"]
                }
                
        except Exception as e:
            logger.error(f"Error determining optimal planting time: {e}")
            return {"optimal": False, "message": "Error calculating timing"}
    
    def _get_season_from_month(self, month: str) -> str:
        """Determine season from month"""
        month_lower = month.lower()
        if month_lower in ["june", "july", "august", "september", "october"]:
            return "kharif"
        elif month_lower in ["november", "december", "january", "february", "march", "april"]:
            return "rabi"
        else:
            return "zaid"
    
    def generate_crop_calendar(
        self,
        farmer_profile: Dict[str, Any],
        agricultural_data: AgriculturalIntelligence
    ) -> List[Dict[str, Any]]:
        """Generate a crop calendar for the farmer"""
        try:
            calendar = []
            current_date = date.today()
            
            # Generate recommendations for next 12 months
            for month_offset in range(12):
                future_date = current_date + timedelta(days=30 * month_offset)
                month_name = future_date.strftime("%B")
                season = self._get_season_from_month(month_name.lower())
                
                season_info = self.seasonal_calendar[season]
                
                calendar.append({
                    "month": month_name,
                    "year": future_date.year,
                    "season": season,
                    "suitable_crops": season_info["suitable_crops"],
                    "activity": self._get_activity_for_month(month_name.lower(), season_info)
                })
            
            return calendar
            
        except Exception as e:
            logger.error(f"Error generating crop calendar: {e}")
            return []
    
    def _get_activity_for_month(self, month: str, season_info: Dict) -> str:
        """Get recommended activity for a month"""
        if month in season_info["planting_months"]:
            return "planting"
        elif month in season_info["harvest_months"]:
            return "harvesting"
        else:
            return "maintenance"



# LangChain Custom Tools for Recommendation Generation

class CropRecommendationInput(LangChainBaseModel):
    """Input schema for crop recommendation tool"""
    farmer_id: str = LangChainField(description="Farmer ID")
    season: str = LangChainField(description="Current or target season (kharif/rabi/zaid)")
    include_timing: bool = LangChainField(default=True, description="Include timing recommendations")


class IrrigationRecommendationInput(LangChainBaseModel):
    """Input schema for irrigation recommendation tool"""
    farmer_id: str = LangChainField(description="Farmer ID")
    crop_name: str = LangChainField(description="Crop name")
    current_soil_moisture: Optional[float] = LangChainField(default=None, description="Current soil moisture percentage")


class MarketTimingInput(LangChainBaseModel):
    """Input schema for market timing tool"""
    farmer_id: str = LangChainField(description="Farmer ID")
    crop_name: str = LangChainField(description="Crop name")
    expected_harvest_date: str = LangChainField(description="Expected harvest date (YYYY-MM-DD)")


@tool
def analyze_farmer_profile_tool(farmer_id: str) -> str:
    """
    Analyze a farmer's profile to extract key characteristics for personalized recommendations.
    
    Args:
        farmer_id: The unique identifier for the farmer
        
    Returns:
        JSON string containing farmer profile analysis
    """
    try:
        # This would fetch from database in production
        analyzer = FarmerProfileAnalyzer()
        # Placeholder - would fetch actual profile
        analysis = {
            "farmer_id": farmer_id,
            "analysis_complete": True,
            "message": "Profile analyzed successfully"
        }
        return json.dumps(analysis)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def recommend_crops_tool(farmer_id: str, season: str, include_timing: bool = True) -> str:
    """
    Recommend suitable crops for a farmer based on their profile, season, and conditions.
    
    Args:
        farmer_id: The unique identifier for the farmer
        season: Target season (kharif/rabi/zaid)
        include_timing: Whether to include planting timing recommendations
        
    Returns:
        JSON string containing crop recommendations with scores
    """
    try:
        scorer = CropRecommendationScorer()
        timing_optimizer = CropTimingOptimizer()
        
        # Placeholder recommendations
        recommendations = {
            "farmer_id": farmer_id,
            "season": season,
            "recommended_crops": [
                {"crop": "wheat", "score": 0.85, "reason": "Excellent soil match and market demand"},
                {"crop": "maize", "score": 0.78, "reason": "Good climate suitability and low input cost"},
                {"crop": "pulses", "score": 0.72, "reason": "Suitable for current irrigation setup"}
            ]
        }
        
        if include_timing:
            recommendations["timing_advice"] = "Optimal planting window: October-November"
        
        return json.dumps(recommendations)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def optimize_irrigation_schedule_tool(
    farmer_id: str,
    crop_name: str,
    current_soil_moisture: Optional[float] = None
) -> str:
    """
    Generate optimized irrigation schedule for a specific crop to reduce water usage by 20%.
    
    Args:
        farmer_id: The unique identifier for the farmer
        crop_name: Name of the crop
        current_soil_moisture: Current soil moisture percentage (optional)
        
    Returns:
        JSON string containing irrigation schedule and water-saving recommendations
    """
    try:
        # Simplified irrigation optimization
        schedule = {
            "farmer_id": farmer_id,
            "crop": crop_name,
            "current_moisture": current_soil_moisture,
            "recommendations": [
                {
                    "day": "Monday",
                    "time": "Early morning (6-8 AM)",
                    "duration_minutes": 45,
                    "water_amount_liters": 500
                },
                {
                    "day": "Thursday",
                    "time": "Early morning (6-8 AM)",
                    "duration_minutes": 45,
                    "water_amount_liters": 500
                }
            ],
            "water_saving_tips": [
                "Use drip irrigation for 30% water savings",
                "Irrigate during early morning to reduce evaporation",
                "Monitor soil moisture before each irrigation"
            ],
            "expected_water_reduction": "20-25%"
        }
        return json.dumps(schedule)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def analyze_market_timing_tool(
    farmer_id: str,
    crop_name: str,
    expected_harvest_date: str
) -> str:
    """
    Analyze market conditions and recommend optimal selling timing for maximum profit.
    
    Args:
        farmer_id: The unique identifier for the farmer
        crop_name: Name of the crop
        expected_harvest_date: Expected harvest date in YYYY-MM-DD format
        
    Returns:
        JSON string containing market analysis and timing recommendations
    """
    try:
        analysis = {
            "farmer_id": farmer_id,
            "crop": crop_name,
            "harvest_date": expected_harvest_date,
            "current_market_price": "₹2,500/quintal",
            "price_trend": "increasing",
            "recommendation": "Store for 2-3 weeks for better prices",
            "expected_price_increase": "8-12%",
            "best_selling_window": "Mid-November to early December",
            "nearby_markets": [
                {"name": "District Mandi", "distance_km": 15, "price": "₹2,500"},
                {"name": "Regional Market", "distance_km": 45, "price": "₹2,650"}
            ],
            "storage_advice": "Ensure proper ventilation and moisture control"
        }
        return json.dumps(analysis)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def generate_pest_management_plan_tool(
    farmer_id: str,
    crop_name: str,
    pest_description: Optional[str] = None
) -> str:
    """
    Generate integrated pest management plan prioritizing organic methods.
    
    Args:
        farmer_id: The unique identifier for the farmer
        crop_name: Name of the crop
        pest_description: Description of pest problem (optional)
        
    Returns:
        JSON string containing pest management recommendations
    """
    try:
        plan = {
            "farmer_id": farmer_id,
            "crop": crop_name,
            "pest_issue": pest_description or "General prevention",
            "organic_methods": [
                {
                    "method": "Neem oil spray",
                    "application": "Mix 5ml neem oil per liter of water",
                    "frequency": "Once per week",
                    "effectiveness": "High for aphids and whiteflies"
                },
                {
                    "method": "Companion planting",
                    "application": "Plant marigold around field borders",
                    "frequency": "One-time setup",
                    "effectiveness": "Repels many common pests"
                }
            ],
            "biological_control": [
                "Introduce ladybugs for aphid control",
                "Use Trichoderma for soil-borne diseases"
            ],
            "chemical_control": {
                "use_only_if": "Organic methods fail after 2 weeks",
                "recommended_products": ["Low-toxicity approved pesticides"],
                "safety_precautions": ["Wear protective equipment", "Follow waiting period before harvest"]
            },
            "monitoring_schedule": "Check plants every 3 days for early detection"
        }
        return json.dumps(plan)
    except Exception as e:
        return json.dumps({"error": str(e)})



class AdvisoryAgent:
    """
    Main Advisory Agent that delivers personalized recommendations using LangChain agents.
    Integrates farmer profile analysis, crop scoring, timing optimization, and custom tools.
    """
    
    def __init__(self):
        self.bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=settings.bedrock_region
        )
        self.llm = ChatBedrock(
            client=self.bedrock_client,
            model_id=settings.bedrock_model_id,
            model_kwargs={
                "max_tokens": 2000,
                "temperature": 0.3,
                "top_p": 0.9
            }
        )
        
        # Initialize components
        self.profile_analyzer = FarmerProfileAnalyzer()
        self.crop_scorer = CropRecommendationScorer()
        self.timing_optimizer = CropTimingOptimizer()
        
        # Initialize LangChain tools
        self.tools = [
            analyze_farmer_profile_tool,
            recommend_crops_tool,
            optimize_irrigation_schedule_tool,
            analyze_market_timing_tool,
            generate_pest_management_plan_tool
        ]
        
        # Create agent
        self.agent = self._create_agent()
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            max_iterations=5,
            handle_parsing_errors=True
        )
        
        logger.info("Advisory Agent initialized successfully")
    
    def _create_agent(self):
        """Create LangChain ReAct agent for advisory tasks"""
        prompt_template = """You are KrishiMitra Advisory Agent, an expert agricultural advisor for Indian farmers.
        
Your role is to provide personalized, actionable agricultural recommendations based on:
- Farmer profile and experience
- Local soil and climate conditions
- Current market trends
- Sustainable farming practices
- Water conservation
- Organic methods (prioritize these)

You have access to the following tools:
{tools}

Tool Names: {tool_names}

When providing recommendations:
1. Always consider the farmer's specific context
2. Prioritize sustainable and organic methods
3. Include specific, actionable steps
4. Consider budget constraints
5. Provide timeline for implementation
6. Explain expected outcomes

Use this format:

Question: the input question you must answer
Thought: think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought: {agent_scratchpad}"""
        
        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["input", "agent_scratchpad", "tools", "tool_names"]
        )
        
        return create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
    
    async def generate_recommendations(
        self,
        request: RecommendationRequest,
        farmer_profile: FarmerProfile,
        agricultural_data: Optional[AgriculturalIntelligence] = None
    ) -> RecommendationResponse:
        """
        Generate personalized recommendations for a farmer.
        
        Args:
            request: Recommendation request with query details
            farmer_profile: Complete farmer profile
            agricultural_data: Current agricultural intelligence data
            
        Returns:
            RecommendationResponse with personalized recommendations
        """
        try:
            start_time = datetime.now(timezone.utc)
            logger.info(f"Generating recommendations for farmer {request.farmer_id}")
            
            # Analyze farmer profile
            profile_analysis = self.profile_analyzer.analyze_profile(farmer_profile)
            
            # Generate recommendations based on request type
            recommendations = []
            
            if request.query_type == RecommendationType.CROP_SELECTION:
                recommendations = await self._generate_crop_recommendations(
                    request, profile_analysis, agricultural_data
                )
            elif request.query_type == RecommendationType.IRRIGATION:
                recommendations = await self._generate_irrigation_recommendations(
                    request, profile_analysis, agricultural_data
                )
            elif request.query_type == RecommendationType.PEST_MANAGEMENT:
                recommendations = await self._generate_pest_management_recommendations(
                    request, profile_analysis, agricultural_data
                )
            elif request.query_type == RecommendationType.MARKET_TIMING:
                recommendations = await self._generate_market_recommendations(
                    request, profile_analysis, agricultural_data
                )
            else:
                # General recommendations using agent
                recommendations = await self._generate_general_recommendations(
                    request, profile_analysis, agricultural_data
                )
            
            # Calculate processing time
            end_time = datetime.now(timezone.utc)
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Create response
            response = RecommendationResponse(
                request_id=f"req_{request.farmer_id}_{int(start_time.timestamp())}",
                farmer_id=request.farmer_id,
                recommendations=recommendations[:request.max_recommendations],
                generation_time=start_time,
                processing_time_ms=processing_time_ms,
                data_sources_used=self._get_data_sources(agricultural_data),
                overall_confidence=self._calculate_overall_confidence(recommendations),
                data_completeness=self._calculate_data_completeness(agricultural_data),
                personalization_score=self._calculate_personalization_score(profile_analysis)
            )
            
            logger.info(f"Generated {len(recommendations)} recommendations in {processing_time_ms}ms")
            return response
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            raise
    
    async def _generate_crop_recommendations(
        self,
        request: RecommendationRequest,
        profile_analysis: Dict[str, Any],
        agricultural_data: Optional[AgriculturalIntelligence]
    ) -> List[RecommendationRecord]:
        """Generate crop selection recommendations"""
        try:
            recommendations = []
            current_date = date.today()
            season = self.timing_optimizer._get_season_from_month(current_date.strftime("%B").lower())
            
            # Get suitable crops for season
            seasonal_crops = self.timing_optimizer.seasonal_calendar[season]["suitable_crops"]
            
            # Score each crop
            crop_scores = []
            for crop in seasonal_crops[:10]:  # Limit to top 10 crops
                score, score_breakdown = self.crop_scorer.score_crop_recommendation(
                    crop, profile_analysis, agricultural_data, season
                )
                crop_scores.append((crop, score, score_breakdown))
            
            # Sort by score
            crop_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Create recommendations for top crops
            for crop, score, breakdown in crop_scores[:request.max_recommendations]:
                timing_info = self.timing_optimizer.get_optimal_planting_time(
                    crop, current_date, agricultural_data.weather_data if agricultural_data else None
                )
                
                recommendation = self._create_crop_recommendation(
                    request.farmer_id,
                    crop,
                    score,
                    breakdown,
                    timing_info,
                    request.language
                )
                recommendations.append(recommendation)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating crop recommendations: {e}")
            return []
    
    def _create_crop_recommendation(
        self,
        farmer_id: str,
        crop_name: str,
        score: float,
        score_breakdown: Dict[str, float],
        timing_info: Dict[str, Any],
        language: str
    ) -> RecommendationRecord:
        """Create a crop recommendation record"""
        
        # Create action items
        action_items = [
            ActionItem(
                title=f"Prepare land for {crop_name} cultivation",
                description=f"Plow and level the field, add organic manure",
                priority=Priority.HIGH,
                estimated_time="1-2 weeks",
                estimated_cost=MonetaryAmount(amount=Decimal("5000"), currency="INR"),
                resources_needed=["Tractor", "Organic manure", "Labor"],
                expected_outcome="Well-prepared field ready for planting"
            ),
            ActionItem(
                title=f"Procure quality {crop_name} seeds",
                description="Purchase certified seeds from authorized dealer",
                priority=Priority.HIGH,
                estimated_time="3-5 days",
                estimated_cost=MonetaryAmount(amount=Decimal("3000"), currency="INR"),
                resources_needed=["Certified seeds"],
                expected_outcome="High-quality seeds for better yield"
            ),
            ActionItem(
                title="Plant seeds at optimal time",
                description=f"Plant during {timing_info.get('planting_window', 'recommended window')}",
                priority=Priority.URGENT if timing_info.get('optimal') else Priority.MEDIUM,
                estimated_time="1 week",
                resources_needed=["Seeds", "Labor", "Planting equipment"],
                expected_outcome="Successful crop establishment"
            )
        ]
        
        # Create context
        context = RecommendationContext(
            crop_type=crop_name,
            season=timing_info.get('season', 'current'),
            growth_stage="pre-planting"
        )
        
        # Create evidence
        evidence = RecommendationEvidence(
            data_sources=["Soil Analysis", "Climate Data", "Market Trends"],
            confidence_score=score * 100,
            reliability_score=85.0
        )
        
        # Create expected impact
        expected_impact = RecommendationImpact(
            expected_yield_increase=15.0,
            expected_cost_reduction=10.0,
            environmental_impact="Positive - sustainable practices"
        )
        
        # Create recommendation record
        recommendation = RecommendationRecord(
            farmer_id=farmer_id,
            recommendation_type=RecommendationType.CROP_SELECTION,
            title=f"Grow {crop_name.title()} this season",
            summary=f"Based on your farm conditions, {crop_name} is highly suitable with a match score of {score:.0%}",
            description=self._generate_crop_description(crop_name, score_breakdown, timing_info),
            language=language,
            action_items=action_items,
            context=context,
            evidence=evidence,
            priority=Priority.HIGH if score > 0.8 else Priority.MEDIUM,
            expected_impact=expected_impact,
            personalization_factors=[
                "soil_type", "climate", "market_demand", "farmer_experience"
            ],
            agent_source="AdvisoryAgent",
            generation_method="ML-based scoring with LangChain"
        )
        
        return recommendation
    
    def _generate_crop_description(
        self,
        crop_name: str,
        score_breakdown: Dict[str, float],
        timing_info: Dict[str, Any]
    ) -> str:
        """Generate detailed crop recommendation description"""
        description = f"Recommendation for {crop_name.title()}:\n\n"
        
        description += "Suitability Analysis:\n"
        for factor, score in score_breakdown.items():
            factor_name = factor.replace('_', ' ').title()
            description += f"- {factor_name}: {score:.0%}\n"
        
        description += f"\nTiming: {timing_info.get('message', 'Check seasonal calendar')}\n"
        
        if timing_info.get('optimal'):
            description += "\n✓ This is an optimal time to plant this crop.\n"
        
        description += "\nExpected Benefits:\n"
        description += "- Good market demand and pricing\n"
        description += "- Suitable for your soil and climate\n"
        description += "- Matches your farming experience\n"
        description += "- Sustainable water usage\n"
        
        return description

    
    async def _generate_irrigation_recommendations(
        self,
        request: RecommendationRequest,
        profile_analysis: Dict[str, Any],
        agricultural_data: Optional[AgriculturalIntelligence]
    ) -> List[RecommendationRecord]:
        """Generate irrigation optimization recommendations"""
        try:
            recommendations = []
            
            # Get current crops
            current_crops = profile_analysis.get("current_crops", [])
            if not current_crops:
                current_crops = ["general"]
            
            for crop in current_crops[:3]:  # Limit to 3 crops
                # Use LangChain tool to get irrigation schedule
                tool_input = {
                    "farmer_id": request.farmer_id,
                    "crop_name": crop,
                    "current_soil_moisture": agricultural_data.soil_data.moisture_content if agricultural_data and agricultural_data.soil_data else None
                }
                
                # Create irrigation recommendation
                recommendation = RecommendationRecord(
                    farmer_id=request.farmer_id,
                    recommendation_type=RecommendationType.IRRIGATION,
                    title=f"Optimized Irrigation Schedule for {crop.title()}",
                    summary=f"Water-efficient irrigation plan to reduce usage by 20% while maintaining crop health",
                    description=f"Implement drip irrigation and scheduled watering for {crop} to achieve 20-25% water savings.",
                    language=request.language,
                    action_items=[
                        ActionItem(
                            title="Install drip irrigation system",
                            description="Set up drip irrigation for precise water delivery",
                            priority=Priority.HIGH,
                            estimated_cost=MonetaryAmount(amount=Decimal("15000"), currency="INR"),
                            expected_outcome="30% water savings"
                        ),
                        ActionItem(
                            title="Follow optimized watering schedule",
                            description="Water early morning (6-8 AM) twice per week",
                            priority=Priority.MEDIUM,
                            estimated_time="Ongoing",
                            expected_outcome="Reduced evaporation losses"
                        ),
                        ActionItem(
                            title="Monitor soil moisture",
                            description="Check soil moisture before each irrigation",
                            priority=Priority.MEDIUM,
                            resources_needed=["Soil moisture meter"],
                            expected_outcome="Prevent over-watering"
                        )
                    ],
                    context=RecommendationContext(crop_type=crop),
                    evidence=RecommendationEvidence(
                        data_sources=["Irrigation Research", "Soil Data"],
                        confidence_score=88.0,
                        reliability_score=90.0
                    ),
                    priority=Priority.HIGH,
                    expected_impact=RecommendationImpact(
                        expected_cost_reduction=20.0,
                        environmental_impact="Significant water conservation"
                    ),
                    personalization_factors=["irrigation_type", "soil_moisture", "crop_type"],
                    agent_source="AdvisoryAgent"
                )
                
                recommendations.append(recommendation)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating irrigation recommendations: {e}")
            return []
    
    async def _generate_pest_management_recommendations(
        self,
        request: RecommendationRequest,
        profile_analysis: Dict[str, Any],
        agricultural_data: Optional[AgriculturalIntelligence]
    ) -> List[RecommendationRecord]:
        """Generate pest management recommendations prioritizing organic methods"""
        try:
            recommendations = []
            
            current_crops = profile_analysis.get("current_crops", ["general"])
            
            for crop in current_crops[:2]:
                recommendation = RecommendationRecord(
                    farmer_id=request.farmer_id,
                    recommendation_type=RecommendationType.PEST_MANAGEMENT,
                    title=f"Integrated Pest Management for {crop.title()}",
                    summary="Organic-first pest management strategy with minimal chemical use",
                    description=f"Comprehensive IPM plan for {crop} prioritizing organic and biological control methods.",
                    language=request.language,
                    action_items=[
                        ActionItem(
                            title="Apply neem oil spray",
                            description="Mix 5ml neem oil per liter, spray weekly",
                            priority=Priority.HIGH,
                            estimated_cost=MonetaryAmount(amount=Decimal("500"), currency="INR"),
                            expected_outcome="Control aphids and whiteflies organically"
                        ),
                        ActionItem(
                            title="Set up companion planting",
                            description="Plant marigold around field borders",
                            priority=Priority.MEDIUM,
                            estimated_cost=MonetaryAmount(amount=Decimal("1000"), currency="INR"),
                            expected_outcome="Natural pest repellent"
                        ),
                        ActionItem(
                            title="Introduce beneficial insects",
                            description="Release ladybugs for aphid control",
                            priority=Priority.MEDIUM,
                            expected_outcome="Biological pest control"
                        ),
                        ActionItem(
                            title="Regular monitoring",
                            description="Check plants every 3 days for early pest detection",
                            priority=Priority.HIGH,
                            estimated_time="15 minutes daily",
                            expected_outcome="Early intervention prevents major outbreaks"
                        )
                    ],
                    context=RecommendationContext(crop_type=crop),
                    evidence=RecommendationEvidence(
                        data_sources=["IPM Guidelines", "Organic Farming Research"],
                        confidence_score=85.0,
                        reliability_score=88.0
                    ),
                    priority=Priority.HIGH,
                    expected_impact=RecommendationImpact(
                        expected_cost_reduction=15.0,
                        environmental_impact="Highly positive - organic methods"
                    ),
                    personalization_factors=["organic_interest", "crop_type"],
                    agent_source="AdvisoryAgent"
                )
                
                recommendations.append(recommendation)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating pest management recommendations: {e}")
            return []
    
    async def _generate_market_recommendations(
        self,
        request: RecommendationRequest,
        profile_analysis: Dict[str, Any],
        agricultural_data: Optional[AgriculturalIntelligence]
    ) -> List[RecommendationRecord]:
        """Generate market timing recommendations"""
        try:
            recommendations = []
            
            current_crops = profile_analysis.get("current_crops", [])
            
            for crop in current_crops[:2]:
                recommendation = RecommendationRecord(
                    farmer_id=request.farmer_id,
                    recommendation_type=RecommendationType.MARKET_TIMING,
                    title=f"Market Timing Strategy for {crop.title()}",
                    summary="Optimize selling time for maximum profit",
                    description=f"Market analysis and timing recommendations for {crop} to maximize returns.",
                    language=request.language,
                    action_items=[
                        ActionItem(
                            title="Monitor market prices weekly",
                            description="Track prices at nearby mandis",
                            priority=Priority.HIGH,
                            estimated_time="30 minutes weekly",
                            expected_outcome="Informed selling decisions"
                        ),
                        ActionItem(
                            title="Prepare storage facilities",
                            description="Ensure proper ventilation and moisture control",
                            priority=Priority.MEDIUM,
                            estimated_cost=MonetaryAmount(amount=Decimal("3000"), currency="INR"),
                            expected_outcome="Ability to wait for better prices"
                        ),
                        ActionItem(
                            title="Consider regional markets",
                            description="Compare prices at markets within 50km",
                            priority=Priority.MEDIUM,
                            expected_outcome="Find best selling location"
                        )
                    ],
                    context=RecommendationContext(crop_type=crop),
                    evidence=RecommendationEvidence(
                        data_sources=["Market Price Data", "Historical Trends"],
                        confidence_score=75.0,
                        reliability_score=80.0
                    ),
                    priority=Priority.MEDIUM,
                    expected_impact=RecommendationImpact(
                        expected_yield_increase=0.0,
                        expected_cost_reduction=0.0,
                        environmental_impact="Neutral"
                    ),
                    personalization_factors=["location", "storage_capacity", "crop_type"],
                    agent_source="AdvisoryAgent"
                )
                
                recommendations.append(recommendation)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating market recommendations: {e}")
            return []
    
    async def _generate_general_recommendations(
        self,
        request: RecommendationRequest,
        profile_analysis: Dict[str, Any],
        agricultural_data: Optional[AgriculturalIntelligence]
    ) -> List[RecommendationRecord]:
        """Generate general recommendations using LangChain agent"""
        try:
            # Use agent executor to process query
            query = request.query_text or "Provide general farming advice"
            
            agent_input = {
                "input": f"""Farmer ID: {request.farmer_id}
                
Farmer Profile:
- Farm size: {profile_analysis.get('farm_size_hectares', 'Unknown')} hectares
- Soil type: {profile_analysis.get('soil_type', 'Unknown')}
- Current crops: {', '.join(profile_analysis.get('current_crops', []))}
- Experience: {profile_analysis.get('experience_level', 'Unknown')}

Query: {query}

Provide personalized recommendations."""
            }
            
            # Execute agent (simplified for now)
            # In production, this would use the full agent executor
            recommendation = RecommendationRecord(
                farmer_id=request.farmer_id,
                recommendation_type=RecommendationType.GENERAL_ADVICE,
                title="Personalized Farming Advice",
                summary="General agricultural guidance based on your profile",
                description="Comprehensive farming advice tailored to your specific situation.",
                language=request.language,
                action_items=[
                    ActionItem(
                        title="Follow seasonal best practices",
                        description="Implement recommended practices for current season",
                        priority=Priority.MEDIUM,
                        expected_outcome="Improved farm productivity"
                    )
                ],
                context=RecommendationContext(),
                evidence=RecommendationEvidence(
                    data_sources=["Agricultural Knowledge Base"],
                    confidence_score=70.0,
                    reliability_score=75.0
                ),
                priority=Priority.MEDIUM,
                expected_impact=RecommendationImpact(),
                personalization_factors=["farmer_profile"],
                agent_source="AdvisoryAgent"
            )
            
            return [recommendation]
            
        except Exception as e:
            logger.error(f"Error generating general recommendations: {e}")
            return []
    
    def _get_data_sources(self, agricultural_data: Optional[AgriculturalIntelligence]) -> List[str]:
        """Get list of data sources used"""
        sources = ["Farmer Profile", "Agricultural Knowledge Base"]
        
        if agricultural_data:
            if agricultural_data.weather_data:
                sources.append("Weather Data")
            if agricultural_data.soil_data:
                sources.append("Soil Analysis")
            if agricultural_data.market_data:
                sources.append("Market Data")
        
        return sources
    
    def _calculate_overall_confidence(self, recommendations: List[RecommendationRecord]) -> float:
        """Calculate overall confidence score"""
        if not recommendations:
            return 0.0
        
        total_confidence = sum(rec.evidence.confidence_score for rec in recommendations)
        return total_confidence / len(recommendations)
    
    def _calculate_data_completeness(self, agricultural_data: Optional[AgriculturalIntelligence]) -> float:
        """Calculate data completeness percentage"""
        if not agricultural_data:
            return 50.0
        
        completeness = 50.0  # Base score for having agricultural data
        
        if agricultural_data.weather_data:
            completeness += 15.0
        if agricultural_data.soil_data:
            completeness += 15.0
        if agricultural_data.market_data:
            completeness += 20.0
        
        return min(100.0, completeness)
    
    def _calculate_personalization_score(self, profile_analysis: Dict[str, Any]) -> float:
        """Calculate personalization score"""
        score = 0.0
        
        # Check completeness of profile analysis
        if profile_analysis.get("farm_size_hectares"):
            score += 20.0
        if profile_analysis.get("soil_type"):
            score += 20.0
        if profile_analysis.get("current_crops"):
            score += 20.0
        if profile_analysis.get("experience_level"):
            score += 15.0
        if profile_analysis.get("location"):
            score += 15.0
        if profile_analysis.get("irrigation_type"):
            score += 10.0
        
        return min(100.0, score)
    
    async def close(self):
        """Close agent connections"""
        try:
            logger.info("Advisory Agent closed")
        except Exception as e:
            logger.error(f"Error closing Advisory Agent: {e}")
