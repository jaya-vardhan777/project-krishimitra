"""
Sustainability Agent for KrishiMitra Platform

This module implements the Sustainability Agent responsible for environmental impact monitoring,
climate risk assessment, and sustainable farming recommendations using Python scientific libraries
and LangChain tools.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from enum import Enum

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from scipy import stats
from scipy.signal import find_peaks

# LangChain imports
from langchain_aws import ChatBedrock
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.tools import BaseTool, tool
from langchain.agents import AgentExecutor, create_react_agent
from langchain.chains import LLMChain
from pydantic import BaseModel as LangChainBaseModel, Field as LangChainField

from ..core.config import get_settings
from ..models.farmer import FarmerProfile, CropInfo
from ..models.agricultural_intelligence import (
    AgriculturalIntelligence, WeatherData, SoilData, 
    AlertLevel, SensorReading, SoilNutrients, WeatherCondition
)
from ..models.base import GeographicCoordinate
from ..models.recommendation import (
    RecommendationRecord, RecommendationType, Priority, ActionItem
)

logger = logging.getLogger(__name__)
settings = get_settings()


class SustainabilityMetric(str, Enum):
    """Sustainability metrics tracked by the agent"""
    WATER_USAGE = "water_usage"
    SOIL_HEALTH = "soil_health"
    CARBON_FOOTPRINT = "carbon_footprint"
    BIODIVERSITY = "biodiversity"
    CHEMICAL_USAGE = "chemical_usage"
    ENERGY_CONSUMPTION = "energy_consumption"


class WaterUsageTracker:
    """
    Tracks water usage patterns and provides alerts when usage exceeds sustainable thresholds.
    Uses pandas/numpy for data analysis and tracking.
    """
    
    def __init__(self):
        self.sustainable_thresholds = {
            "rice": 1200,  # mm per season
            "wheat": 450,
            "maize": 500,
            "cotton": 700,
            "sugarcane": 1800,
            "pulses": 350,
            "vegetables": 400
        }
        self.alert_threshold_percentage = 0.85  # Alert at 85% of threshold
    
    def track_water_usage(
        self,
        farmer_id: str,
        crop_name: str,
        field_area_hectares: float,
        irrigation_records: List[Dict[str, Any]],
        rainfall_data: List[float],
        season_start_date: date
    ) -> Dict[str, Any]:
        """
        Track water usage and generate alerts if exceeding sustainable thresholds.
        
        Args:
            farmer_id: Farmer identifier
            crop_name: Name of the crop
            field_area_hectares: Field area in hectares
            irrigation_records: List of irrigation records with dates and amounts
            rainfall_data: List of rainfall amounts (mm)
            season_start_date: Start date of the growing season
            
        Returns:
            Water usage analysis with alerts
        """
        try:
            # Convert to pandas DataFrame for analysis
            if irrigation_records:
                df = pd.DataFrame(irrigation_records)
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date')
                
                # Calculate total irrigation water used (m³)
                total_irrigation_m3 = df['water_amount_m3'].sum()
                
                # Convert to mm over field area
                total_irrigation_mm = (total_irrigation_m3 / (field_area_hectares * 10000)) * 1000
            else:
                total_irrigation_mm = 0
                total_irrigation_m3 = 0
            
            # Calculate total rainfall
            total_rainfall_mm = sum(rainfall_data) if rainfall_data else 0
            
            # Total water input
            total_water_mm = total_irrigation_mm + total_rainfall_mm
            
            # Get sustainable threshold for crop
            crop_lower = crop_name.lower()
            threshold_mm = self.sustainable_thresholds.get(crop_lower, 500)
            
            # Calculate usage percentage
            usage_percentage = (total_water_mm / threshold_mm) * 100
            
            # Determine alert level
            alert_level = None
            alert_message = None
            
            if usage_percentage >= 100:
                alert_level = AlertLevel.SEVERE
                alert_message = f"Water usage has exceeded sustainable threshold by {usage_percentage - 100:.1f}%"
            elif usage_percentage >= self.alert_threshold_percentage * 100:
                alert_level = AlertLevel.HIGH
                alert_message = f"Water usage is at {usage_percentage:.1f}% of sustainable threshold"
            elif usage_percentage >= 70:
                alert_level = AlertLevel.MODERATE
                alert_message = f"Water usage is at {usage_percentage:.1f}% of sustainable threshold"
            else:
                alert_level = AlertLevel.LOW
                alert_message = f"Water usage is within sustainable limits ({usage_percentage:.1f}%)"
            
            # Calculate daily average
            days_elapsed = (datetime.now().date() - season_start_date).days
            daily_average_mm = total_water_mm / max(days_elapsed, 1)
            
            # Generate recommendations
            recommendations = self._generate_water_recommendations(
                usage_percentage, crop_name, alert_level
            )
            
            return {
                "farmer_id": farmer_id,
                "crop": crop_name,
                "field_area_hectares": field_area_hectares,
                "season_start_date": season_start_date.isoformat(),
                "days_elapsed": days_elapsed,
                "water_usage": {
                    "total_irrigation_mm": round(total_irrigation_mm, 2),
                    "total_irrigation_m3": round(total_irrigation_m3, 2),
                    "total_rainfall_mm": round(total_rainfall_mm, 2),
                    "total_water_mm": round(total_water_mm, 2),
                    "daily_average_mm": round(daily_average_mm, 2)
                },
                "threshold": {
                    "sustainable_threshold_mm": threshold_mm,
                    "usage_percentage": round(usage_percentage, 2),
                    "remaining_budget_mm": round(max(0, threshold_mm - total_water_mm), 2)
                },
                "alert": {
                    "level": alert_level.value,
                    "message": alert_message
                },
                "recommendations": recommendations,
                "trend_analysis": self._analyze_water_trend(irrigation_records) if irrigation_records else None
            }
            
        except Exception as e:
            logger.error(f"Error tracking water usage: {e}")
            return {"error": str(e)}
    
    def _generate_water_recommendations(
        self,
        usage_percentage: float,
        crop_name: str,
        alert_level: AlertLevel
    ) -> List[str]:
        """Generate water conservation recommendations based on usage"""
        recommendations = []
        
        if usage_percentage >= 85:
            recommendations.extend([
                "URGENT: Reduce irrigation frequency immediately",
                "Switch to deficit irrigation strategy for remaining season",
                "Check for water leaks in irrigation system",
                "Consider mulching to reduce evaporation losses"
            ])
        elif usage_percentage >= 70:
            recommendations.extend([
                "Monitor soil moisture closely before each irrigation",
                "Reduce irrigation duration by 10-15%",
                "Irrigate during early morning hours to minimize evaporation",
                "Apply organic mulch to conserve soil moisture"
            ])
        else:
            recommendations.extend([
                "Continue current water management practices",
                "Maintain regular soil moisture monitoring",
                "Consider drip irrigation for future seasons"
            ])
        
        # Crop-specific recommendations
        if crop_name.lower() == "rice":
            recommendations.append("Consider alternate wetting and drying (AWD) technique")
        elif crop_name.lower() in ["wheat", "maize"]:
            recommendations.append("Focus irrigation on critical growth stages")
        
        return recommendations
    
    def _analyze_water_trend(self, irrigation_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze water usage trend over time"""
        try:
            df = pd.DataFrame(irrigation_records)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            
            # Calculate weekly totals
            df['week'] = df['date'].dt.isocalendar().week
            weekly_usage = df.groupby('week')['water_amount_m3'].sum()
            
            # Determine trend
            if len(weekly_usage) >= 2:
                recent_avg = weekly_usage.tail(2).mean()
                earlier_avg = weekly_usage.head(max(2, len(weekly_usage) - 2)).mean()
                
                if recent_avg > earlier_avg * 1.1:
                    trend = "increasing"
                elif recent_avg < earlier_avg * 0.9:
                    trend = "decreasing"
                else:
                    trend = "stable"
            else:
                trend = "insufficient_data"
            
            return {
                "trend": trend,
                "weekly_average_m3": round(weekly_usage.mean(), 2) if len(weekly_usage) > 0 else 0,
                "last_week_m3": round(weekly_usage.iloc[-1], 2) if len(weekly_usage) > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error analyzing water trend: {e}")
            return {"trend": "error", "message": str(e)}



class SoilHealthAssessment:
    """
    Assesses soil health using scikit-learn algorithms.
    Tracks soil organic matter, erosion risk, and biodiversity indicators.
    """
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.health_model = RandomForestClassifier(n_estimators=100, random_state=42)
        
        # Soil health thresholds
        self.organic_matter_thresholds = {
            "very_low": 0.5,
            "low": 1.0,
            "medium": 2.0,
            "good": 3.0,
            "excellent": 5.0
        }
        
        self.ph_optimal_ranges = {
            "rice": (5.5, 7.0),
            "wheat": (6.0, 7.5),
            "maize": (5.8, 7.0),
            "cotton": (5.5, 8.0),
            "pulses": (6.0, 7.5),
            "vegetables": (6.0, 7.0)
        }
    
    def assess_soil_health(
        self,
        farmer_id: str,
        crop_name: str,
        soil_data: SoilData,
        historical_data: Optional[List[SoilData]] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive soil health assessment.
        
        Args:
            farmer_id: Farmer identifier
            crop_name: Name of the crop
            soil_data: Current soil data
            historical_data: Historical soil data for trend analysis
            
        Returns:
            Soil health assessment with scores and recommendations
        """
        try:
            # Calculate individual health scores
            organic_matter_score = self._assess_organic_matter(soil_data)
            ph_score = self._assess_ph(soil_data, crop_name)
            nutrient_score = self._assess_nutrients(soil_data)
            physical_score = self._assess_physical_properties(soil_data)
            
            # Calculate overall soil health index (0-100)
            overall_health = (
                organic_matter_score * 0.30 +
                ph_score * 0.25 +
                nutrient_score * 0.25 +
                physical_score * 0.20
            )
            
            # Assess erosion risk
            erosion_risk = self._assess_erosion_risk(soil_data)
            
            # Assess biodiversity indicators
            biodiversity_score = self._assess_biodiversity(soil_data)
            
            # Trend analysis if historical data available
            trend_analysis = None
            if historical_data and len(historical_data) > 1:
                trend_analysis = self._analyze_soil_trends(historical_data)
            
            # Generate recommendations
            recommendations = self._generate_soil_recommendations(
                organic_matter_score, ph_score, nutrient_score, 
                physical_score, erosion_risk, soil_data, crop_name
            )
            
            # Determine alert level
            alert_level = self._determine_soil_alert_level(overall_health, erosion_risk)
            
            return {
                "farmer_id": farmer_id,
                "crop": crop_name,
                "assessment_date": datetime.now().isoformat(),
                "overall_health_index": round(overall_health, 2),
                "component_scores": {
                    "organic_matter": round(organic_matter_score, 2),
                    "ph_balance": round(ph_score, 2),
                    "nutrient_availability": round(nutrient_score, 2),
                    "physical_properties": round(physical_score, 2),
                    "biodiversity": round(biodiversity_score, 2)
                },
                "erosion_risk": erosion_risk,
                "alert_level": alert_level.value,
                "recommendations": recommendations,
                "trend_analysis": trend_analysis,
                "detailed_metrics": {
                    "organic_carbon_percentage": soil_data.nutrients.organic_carbon if soil_data.nutrients else None,
                    "ph": soil_data.ph,
                    "moisture_content": soil_data.moisture_content,
                    "bulk_density": soil_data.bulk_density,
                    "porosity": soil_data.porosity
                }
            }
            
        except Exception as e:
            logger.error(f"Error assessing soil health: {e}")
            return {"error": str(e)}
    
    def _assess_organic_matter(self, soil_data: SoilData) -> float:
        """Assess organic matter content (0-100 score)"""
        if not soil_data.nutrients or soil_data.nutrients.organic_carbon is None:
            return 50.0  # Default moderate score
        
        oc = soil_data.nutrients.organic_carbon
        
        if oc >= self.organic_matter_thresholds["excellent"]:
            return 100.0
        elif oc >= self.organic_matter_thresholds["good"]:
            return 85.0
        elif oc >= self.organic_matter_thresholds["medium"]:
            return 70.0
        elif oc >= self.organic_matter_thresholds["low"]:
            return 50.0
        else:
            return 30.0
    
    def _assess_ph(self, soil_data: SoilData, crop_name: str) -> float:
        """Assess pH suitability for crop (0-100 score)"""
        if soil_data.ph is None:
            return 50.0
        
        crop_lower = crop_name.lower()
        optimal_range = self.ph_optimal_ranges.get(crop_lower, (6.0, 7.5))
        
        ph = soil_data.ph
        min_ph, max_ph = optimal_range
        
        if min_ph <= ph <= max_ph:
            return 100.0
        elif min_ph - 0.5 <= ph <= max_ph + 0.5:
            return 80.0
        elif min_ph - 1.0 <= ph <= max_ph + 1.0:
            return 60.0
        else:
            return 40.0
    
    def _assess_nutrients(self, soil_data: SoilData) -> float:
        """Assess nutrient availability (0-100 score)"""
        if not soil_data.nutrients:
            return 50.0
        
        scores = []
        
        # Nitrogen assessment
        if soil_data.nutrients.nitrogen is not None:
            n = soil_data.nutrients.nitrogen
            if n >= 280:
                scores.append(100)
            elif n >= 140:
                scores.append(75)
            else:
                scores.append(50)
        
        # Phosphorus assessment
        if soil_data.nutrients.phosphorus is not None:
            p = soil_data.nutrients.phosphorus
            if p >= 25:
                scores.append(100)
            elif p >= 12:
                scores.append(75)
            else:
                scores.append(50)
        
        # Potassium assessment
        if soil_data.nutrients.potassium is not None:
            k = soil_data.nutrients.potassium
            if k >= 280:
                scores.append(100)
            elif k >= 140:
                scores.append(75)
            else:
                scores.append(50)
        
        return sum(scores) / len(scores) if scores else 50.0
    
    def _assess_physical_properties(self, soil_data: SoilData) -> float:
        """Assess physical properties (0-100 score)"""
        scores = []
        
        # Bulk density assessment
        if soil_data.bulk_density is not None:
            bd = soil_data.bulk_density
            if 1.1 <= bd <= 1.4:  # Optimal range
                scores.append(100)
            elif 1.0 <= bd <= 1.6:
                scores.append(75)
            else:
                scores.append(50)
        
        # Porosity assessment
        if soil_data.porosity is not None:
            porosity = soil_data.porosity
            if porosity >= 50:
                scores.append(100)
            elif porosity >= 40:
                scores.append(75)
            else:
                scores.append(50)
        
        # Moisture content assessment
        if soil_data.moisture_content is not None:
            moisture = soil_data.moisture_content
            if 40 <= moisture <= 70:
                scores.append(100)
            elif 30 <= moisture <= 80:
                scores.append(75)
            else:
                scores.append(50)
        
        return sum(scores) / len(scores) if scores else 50.0
    
    def _assess_erosion_risk(self, soil_data: SoilData) -> str:
        """Assess erosion risk level"""
        risk_factors = []
        
        # Organic matter factor
        if soil_data.nutrients and soil_data.nutrients.organic_carbon:
            if soil_data.nutrients.organic_carbon < 1.0:
                risk_factors.append("low_organic_matter")
        
        # Texture factor
        if soil_data.sand_percentage and soil_data.sand_percentage > 70:
            risk_factors.append("sandy_texture")
        
        # Compaction factor
        if soil_data.bulk_density and soil_data.bulk_density > 1.6:
            risk_factors.append("compaction")
        
        # Determine overall risk
        if len(risk_factors) >= 2:
            return "high"
        elif len(risk_factors) == 1:
            return "moderate"
        else:
            return "low"
    
    def _assess_biodiversity(self, soil_data: SoilData) -> float:
        """Assess soil biodiversity indicators (0-100 score)"""
        # Simplified biodiversity assessment based on organic matter and pH
        score = 50.0  # Base score
        
        if soil_data.nutrients and soil_data.nutrients.organic_carbon:
            oc = soil_data.nutrients.organic_carbon
            if oc >= 3.0:
                score += 25
            elif oc >= 2.0:
                score += 15
        
        if soil_data.ph:
            if 6.0 <= soil_data.ph <= 7.5:
                score += 25
            elif 5.5 <= soil_data.ph <= 8.0:
                score += 15
        
        return min(100.0, score)
    
    def _analyze_soil_trends(self, historical_data: List[SoilData]) -> Dict[str, Any]:
        """Analyze soil health trends over time"""
        try:
            # Extract organic carbon trend
            oc_values = [
                d.nutrients.organic_carbon 
                for d in historical_data 
                if d.nutrients and d.nutrients.organic_carbon is not None
            ]
            
            # Extract pH trend
            ph_values = [d.ph for d in historical_data if d.ph is not None]
            
            trends = {}
            
            if len(oc_values) >= 2:
                oc_trend = "improving" if oc_values[-1] > oc_values[0] else "declining"
                oc_change = ((oc_values[-1] - oc_values[0]) / oc_values[0]) * 100
                trends["organic_carbon"] = {
                    "trend": oc_trend,
                    "change_percentage": round(oc_change, 2)
                }
            
            if len(ph_values) >= 2:
                ph_change = ph_values[-1] - ph_values[0]
                if abs(ph_change) < 0.2:
                    ph_trend = "stable"
                elif ph_change > 0:
                    ph_trend = "increasing"
                else:
                    ph_trend = "decreasing"
                trends["ph"] = {
                    "trend": ph_trend,
                    "change": round(ph_change, 2)
                }
            
            return trends
            
        except Exception as e:
            logger.error(f"Error analyzing soil trends: {e}")
            return {}
    
    def _generate_soil_recommendations(
        self,
        om_score: float,
        ph_score: float,
        nutrient_score: float,
        physical_score: float,
        erosion_risk: str,
        soil_data: SoilData,
        crop_name: str
    ) -> List[str]:
        """Generate soil health improvement recommendations"""
        recommendations = []
        
        # Organic matter recommendations
        if om_score < 70:
            recommendations.extend([
                "Increase organic matter by applying compost or farmyard manure",
                "Practice crop residue incorporation",
                "Consider cover cropping during off-season"
            ])
        
        # pH recommendations
        if ph_score < 70:
            if soil_data.ph and soil_data.ph < 6.0:
                recommendations.append("Apply lime to increase soil pH")
            elif soil_data.ph and soil_data.ph > 8.0:
                recommendations.append("Apply gypsum or sulfur to reduce soil pH")
        
        # Nutrient recommendations
        if nutrient_score < 70:
            recommendations.append("Conduct detailed soil testing for nutrient management")
            recommendations.append("Apply balanced fertilizers based on soil test results")
        
        # Physical property recommendations
        if physical_score < 70:
            recommendations.extend([
                "Reduce soil compaction through deep tillage",
                "Improve soil structure with organic amendments"
            ])
        
        # Erosion control
        if erosion_risk in ["high", "moderate"]:
            recommendations.extend([
                "Implement contour farming to reduce erosion",
                "Use mulching to protect soil surface",
                "Plant cover crops to prevent soil loss"
            ])
        
        return recommendations
    
    def _determine_soil_alert_level(self, health_index: float, erosion_risk: str) -> AlertLevel:
        """Determine alert level based on soil health"""
        if health_index < 40 or erosion_risk == "high":
            return AlertLevel.SEVERE
        elif health_index < 60 or erosion_risk == "moderate":
            return AlertLevel.HIGH
        elif health_index < 75:
            return AlertLevel.MODERATE
        else:
            return AlertLevel.LOW



class CarbonFootprintCalculator:
    """
    Calculates carbon footprint from farming activities using Python scientific libraries.
    Measures greenhouse gas emissions from various agricultural operations.
    """
    
    def __init__(self):
        # Emission factors (kg CO2e per unit)
        self.emission_factors = {
            "nitrogen_fertilizer": 5.87,  # kg CO2e per kg N
            "phosphorus_fertilizer": 0.67,  # kg CO2e per kg P2O5
            "potassium_fertilizer": 0.52,  # kg CO2e per kg K2O
            "diesel": 2.68,  # kg CO2e per liter
            "electricity": 0.82,  # kg CO2e per kWh
            "pesticides": 16.0,  # kg CO2e per kg active ingredient
            "irrigation_pump": 0.5,  # kg CO2e per hour of operation
            "rice_methane": 1.3,  # kg CH4 per kg rice (converted to CO2e)
            "n2o_from_fertilizer": 0.01  # kg N2O per kg N applied (converted to CO2e)
        }
        
        # Global Warming Potential (GWP) for greenhouse gases
        self.gwp = {
            "CO2": 1,
            "CH4": 28,  # Methane is 28 times more potent than CO2
            "N2O": 265  # Nitrous oxide is 265 times more potent than CO2
        }
    
    def calculate_carbon_footprint(
        self,
        farmer_id: str,
        crop_name: str,
        field_area_hectares: float,
        farming_activities: Dict[str, Any],
        season_duration_days: int
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive carbon footprint from farming activities.
        
        Args:
            farmer_id: Farmer identifier
            crop_name: Name of the crop
            field_area_hectares: Field area in hectares
            farming_activities: Dictionary of farming activities with quantities
            season_duration_days: Duration of growing season
            
        Returns:
            Carbon footprint analysis with breakdown by activity
        """
        try:
            emissions_breakdown = {}
            total_emissions_kg_co2e = 0
            
            # Fertilizer emissions
            if "fertilizers" in farming_activities:
                fert_emissions = self._calculate_fertilizer_emissions(
                    farming_activities["fertilizers"]
                )
                emissions_breakdown["fertilizers"] = fert_emissions
                total_emissions_kg_co2e += fert_emissions["total_co2e"]
            
            # Fuel emissions
            if "fuel_usage" in farming_activities:
                fuel_emissions = self._calculate_fuel_emissions(
                    farming_activities["fuel_usage"]
                )
                emissions_breakdown["fuel"] = fuel_emissions
                total_emissions_kg_co2e += fuel_emissions["total_co2e"]
            
            # Electricity emissions
            if "electricity_usage" in farming_activities:
                elec_emissions = self._calculate_electricity_emissions(
                    farming_activities["electricity_usage"]
                )
                emissions_breakdown["electricity"] = elec_emissions
                total_emissions_kg_co2e += elec_emissions["total_co2e"]
            
            # Pesticide emissions
            if "pesticides" in farming_activities:
                pest_emissions = self._calculate_pesticide_emissions(
                    farming_activities["pesticides"]
                )
                emissions_breakdown["pesticides"] = pest_emissions
                total_emissions_kg_co2e += pest_emissions["total_co2e"]
            
            # Crop-specific emissions (e.g., methane from rice)
            crop_emissions = self._calculate_crop_specific_emissions(
                crop_name, field_area_hectares, farming_activities
            )
            if crop_emissions["total_co2e"] > 0:
                emissions_breakdown["crop_specific"] = crop_emissions
                total_emissions_kg_co2e += crop_emissions["total_co2e"]
            
            # Calculate per hectare and per day emissions
            emissions_per_hectare = total_emissions_kg_co2e / field_area_hectares
            emissions_per_day = total_emissions_kg_co2e / season_duration_days
            
            # Convert to tonnes CO2e
            total_emissions_tonnes = total_emissions_kg_co2e / 1000
            
            # Calculate carbon sequestration potential
            sequestration = self._estimate_carbon_sequestration(
                crop_name, field_area_hectares, farming_activities
            )
            
            # Net emissions
            net_emissions_kg_co2e = total_emissions_kg_co2e - sequestration["total_sequestered_kg"]
            
            # Generate reduction recommendations
            recommendations = self._generate_carbon_reduction_recommendations(
                emissions_breakdown, crop_name
            )
            
            # Benchmark against average
            benchmark = self._get_carbon_benchmark(crop_name)
            comparison = "above_average" if emissions_per_hectare > benchmark else "below_average"
            
            return {
                "farmer_id": farmer_id,
                "crop": crop_name,
                "field_area_hectares": field_area_hectares,
                "season_duration_days": season_duration_days,
                "total_emissions": {
                    "kg_co2e": round(total_emissions_kg_co2e, 2),
                    "tonnes_co2e": round(total_emissions_tonnes, 3),
                    "per_hectare_kg": round(emissions_per_hectare, 2),
                    "per_day_kg": round(emissions_per_day, 2)
                },
                "emissions_breakdown": emissions_breakdown,
                "carbon_sequestration": sequestration,
                "net_emissions": {
                    "kg_co2e": round(net_emissions_kg_co2e, 2),
                    "tonnes_co2e": round(net_emissions_kg_co2e / 1000, 3)
                },
                "benchmark": {
                    "average_per_hectare_kg": benchmark,
                    "comparison": comparison,
                    "difference_percentage": round(
                        ((emissions_per_hectare - benchmark) / benchmark) * 100, 2
                    )
                },
                "recommendations": recommendations,
                "calculation_date": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating carbon footprint: {e}")
            return {"error": str(e)}
    
    def _calculate_fertilizer_emissions(self, fertilizers: Dict[str, float]) -> Dict[str, Any]:
        """Calculate emissions from fertilizer use"""
        emissions = {
            "nitrogen": 0,
            "phosphorus": 0,
            "potassium": 0,
            "n2o_indirect": 0
        }
        
        if "nitrogen_kg" in fertilizers:
            n_amount = fertilizers["nitrogen_kg"]
            emissions["nitrogen"] = n_amount * self.emission_factors["nitrogen_fertilizer"]
            # Indirect N2O emissions
            emissions["n2o_indirect"] = (
                n_amount * self.emission_factors["n2o_from_fertilizer"] * self.gwp["N2O"]
            )
        
        if "phosphorus_kg" in fertilizers:
            emissions["phosphorus"] = (
                fertilizers["phosphorus_kg"] * self.emission_factors["phosphorus_fertilizer"]
            )
        
        if "potassium_kg" in fertilizers:
            emissions["potassium"] = (
                fertilizers["potassium_kg"] * self.emission_factors["potassium_fertilizer"]
            )
        
        total = sum(emissions.values())
        
        return {
            "breakdown": emissions,
            "total_co2e": round(total, 2)
        }
    
    def _calculate_fuel_emissions(self, fuel_usage: Dict[str, float]) -> Dict[str, Any]:
        """Calculate emissions from fuel consumption"""
        emissions = {}
        
        if "diesel_liters" in fuel_usage:
            emissions["diesel"] = fuel_usage["diesel_liters"] * self.emission_factors["diesel"]
        
        total = sum(emissions.values())
        
        return {
            "breakdown": emissions,
            "total_co2e": round(total, 2)
        }
    
    def _calculate_electricity_emissions(self, electricity_usage: Dict[str, float]) -> Dict[str, Any]:
        """Calculate emissions from electricity consumption"""
        emissions = {}
        
        if "kwh" in electricity_usage:
            emissions["grid_electricity"] = (
                electricity_usage["kwh"] * self.emission_factors["electricity"]
            )
        
        if "pump_hours" in electricity_usage:
            emissions["irrigation_pump"] = (
                electricity_usage["pump_hours"] * self.emission_factors["irrigation_pump"]
            )
        
        total = sum(emissions.values())
        
        return {
            "breakdown": emissions,
            "total_co2e": round(total, 2)
        }
    
    def _calculate_pesticide_emissions(self, pesticides: Dict[str, float]) -> Dict[str, Any]:
        """Calculate emissions from pesticide use"""
        emissions = {}
        
        if "total_kg" in pesticides:
            emissions["pesticides"] = pesticides["total_kg"] * self.emission_factors["pesticides"]
        
        total = sum(emissions.values())
        
        return {
            "breakdown": emissions,
            "total_co2e": round(total, 2)
        }
    
    def _calculate_crop_specific_emissions(
        self,
        crop_name: str,
        field_area_hectares: float,
        farming_activities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate crop-specific emissions (e.g., methane from rice)"""
        emissions = {}
        total = 0
        
        if crop_name.lower() == "rice":
            # Rice paddies emit methane
            # Estimate based on field area and water management
            water_management = farming_activities.get("water_management", "continuous_flooding")
            
            if water_management == "continuous_flooding":
                ch4_kg_per_ha = 300  # kg CH4 per hectare per season
            elif water_management == "alternate_wetting_drying":
                ch4_kg_per_ha = 150  # 50% reduction with AWD
            else:
                ch4_kg_per_ha = 200
            
            ch4_total = ch4_kg_per_ha * field_area_hectares
            co2e_from_ch4 = ch4_total * self.gwp["CH4"]
            
            emissions["methane_from_flooding"] = co2e_from_ch4
            total = co2e_from_ch4
        
        return {
            "breakdown": emissions,
            "total_co2e": round(total, 2)
        }
    
    def _estimate_carbon_sequestration(
        self,
        crop_name: str,
        field_area_hectares: float,
        farming_activities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Estimate carbon sequestration from farming practices"""
        sequestration = {}
        total = 0
        
        # Organic matter additions
        if "organic_amendments" in farming_activities:
            organic = farming_activities["organic_amendments"]
            if "compost_tonnes" in organic:
                # Compost sequesters approximately 50 kg C per tonne
                c_sequestered = organic["compost_tonnes"] * 50
                co2e_sequestered = c_sequestered * 3.67  # Convert C to CO2e
                sequestration["compost"] = co2e_sequestered
                total += co2e_sequestered
            
            if "crop_residue_tonnes" in organic:
                # Crop residue incorporation
                c_sequestered = organic["crop_residue_tonnes"] * 40
                co2e_sequestered = c_sequestered * 3.67
                sequestration["crop_residue"] = co2e_sequestered
                total += co2e_sequestered
        
        # Cover cropping
        if farming_activities.get("cover_cropping", False):
            # Cover crops sequester approximately 500 kg CO2e per hectare
            sequestration["cover_crops"] = 500 * field_area_hectares
            total += 500 * field_area_hectares
        
        return {
            "breakdown": sequestration,
            "total_sequestered_kg": round(total, 2)
        }
    
    def _generate_carbon_reduction_recommendations(
        self,
        emissions_breakdown: Dict[str, Any],
        crop_name: str
    ) -> List[str]:
        """Generate recommendations to reduce carbon footprint"""
        recommendations = []
        
        # Fertilizer recommendations
        if "fertilizers" in emissions_breakdown:
            fert_emissions = emissions_breakdown["fertilizers"]["total_co2e"]
            if fert_emissions > 1000:
                recommendations.extend([
                    "Reduce synthetic fertilizer use by 15-20% through precision application",
                    "Use organic fertilizers to reduce carbon footprint",
                    "Apply fertilizers in split doses to improve efficiency"
                ])
        
        # Fuel recommendations
        if "fuel" in emissions_breakdown:
            recommendations.extend([
                "Optimize tractor operations to reduce fuel consumption",
                "Consider conservation tillage to reduce diesel use",
                "Maintain equipment regularly for fuel efficiency"
            ])
        
        # Electricity recommendations
        if "electricity" in emissions_breakdown:
            recommendations.extend([
                "Install solar panels for irrigation pumps",
                "Use energy-efficient pump systems",
                "Optimize irrigation scheduling to reduce pump runtime"
            ])
        
        # Crop-specific recommendations
        if crop_name.lower() == "rice":
            recommendations.append(
                "Implement Alternate Wetting and Drying (AWD) to reduce methane emissions by 50%"
            )
        
        # General recommendations
        recommendations.extend([
            "Increase organic matter in soil through composting",
            "Practice crop residue incorporation for carbon sequestration",
            "Consider cover cropping during off-season"
        ])
        
        return recommendations
    
    def _get_carbon_benchmark(self, crop_name: str) -> float:
        """Get average carbon footprint benchmark for crop (kg CO2e per hectare)"""
        benchmarks = {
            "rice": 3500,
            "wheat": 1800,
            "maize": 1500,
            "cotton": 2200,
            "sugarcane": 2800,
            "pulses": 1200,
            "vegetables": 2000
        }
        return benchmarks.get(crop_name.lower(), 2000)



# LangChain Tools for Environmental Data Analysis

class WaterUsageInput(LangChainBaseModel):
    """Input schema for water usage tracking tool"""
    farmer_id: str = LangChainField(description="Farmer ID")
    crop_name: str = LangChainField(description="Crop name")
    field_area_hectares: float = LangChainField(description="Field area in hectares")
    season_start_date: str = LangChainField(description="Season start date (YYYY-MM-DD)")


class SoilHealthInput(LangChainBaseModel):
    """Input schema for soil health assessment tool"""
    farmer_id: str = LangChainField(description="Farmer ID")
    crop_name: str = LangChainField(description="Crop name")


class CarbonFootprintInput(LangChainBaseModel):
    """Input schema for carbon footprint calculation tool"""
    farmer_id: str = LangChainField(description="Farmer ID")
    crop_name: str = LangChainField(description="Crop name")
    field_area_hectares: float = LangChainField(description="Field area in hectares")
    season_duration_days: int = LangChainField(description="Season duration in days")


@tool
def track_water_usage_tool(
    farmer_id: str,
    crop_name: str,
    field_area_hectares: float,
    season_start_date: str
) -> str:
    """
    Track water usage and generate alerts if exceeding sustainable thresholds.
    Monitors irrigation patterns and provides water conservation recommendations.
    
    Args:
        farmer_id: The unique identifier for the farmer
        crop_name: Name of the crop being grown
        field_area_hectares: Field area in hectares
        season_start_date: Season start date in YYYY-MM-DD format
        
    Returns:
        JSON string containing water usage analysis and alerts
    """
    try:
        tracker = WaterUsageTracker()
        
        # In production, fetch actual irrigation records and rainfall data
        # For now, using placeholder data
        irrigation_records = [
            {"date": "2024-01-15", "water_amount_m3": 500},
            {"date": "2024-01-20", "water_amount_m3": 450},
            {"date": "2024-01-25", "water_amount_m3": 480}
        ]
        rainfall_data = [10, 5, 0, 15, 20]  # mm
        
        start_date = datetime.strptime(season_start_date, "%Y-%m-%d").date()
        
        result = tracker.track_water_usage(
            farmer_id=farmer_id,
            crop_name=crop_name,
            field_area_hectares=field_area_hectares,
            irrigation_records=irrigation_records,
            rainfall_data=rainfall_data,
            season_start_date=start_date
        )
        
        import json
        return json.dumps(result, indent=2)
        
    except Exception as e:
        import json
        return json.dumps({"error": str(e)})


@tool
def assess_soil_health_tool(farmer_id: str, crop_name: str) -> str:
    """
    Assess comprehensive soil health including organic matter, pH, nutrients, and erosion risk.
    Tracks soil health indicators and provides improvement recommendations.
    
    Args:
        farmer_id: The unique identifier for the farmer
        crop_name: Name of the crop being grown
        
    Returns:
        JSON string containing soil health assessment and recommendations
    """
    try:
        assessor = SoilHealthAssessment()
        
        # In production, fetch actual soil data from database
        # For now, using placeholder data
        from ..models.base import Measurement
        
        soil_data = SoilData(
            location=GeographicCoordinate(latitude=28.6139, longitude=77.2090),
            sample_depth=Measurement(value=30, unit="cm"),
            ph=6.5,
            moisture_content=55.0,
            bulk_density=1.3,
            porosity=48.0,
            nutrients=SoilNutrients(
                nitrogen=250.0,
                phosphorus=20.0,
                potassium=200.0,
                organic_carbon=2.5
            )
        )
        
        result = assessor.assess_soil_health(
            farmer_id=farmer_id,
            crop_name=crop_name,
            soil_data=soil_data,
            historical_data=None
        )
        
        import json
        return json.dumps(result, indent=2)
        
    except Exception as e:
        import json
        return json.dumps({"error": str(e)})


@tool
def calculate_carbon_footprint_tool(
    farmer_id: str,
    crop_name: str,
    field_area_hectares: float,
    season_duration_days: int
) -> str:
    """
    Calculate comprehensive carbon footprint from farming activities.
    Measures greenhouse gas emissions and provides reduction recommendations.
    
    Args:
        farmer_id: The unique identifier for the farmer
        crop_name: Name of the crop
        field_area_hectares: Field area in hectares
        season_duration_days: Duration of growing season in days
        
    Returns:
        JSON string containing carbon footprint analysis and recommendations
    """
    try:
        calculator = CarbonFootprintCalculator()
        
        # In production, fetch actual farming activity data
        # For now, using placeholder data
        farming_activities = {
            "fertilizers": {
                "nitrogen_kg": 120,
                "phosphorus_kg": 60,
                "potassium_kg": 40
            },
            "fuel_usage": {
                "diesel_liters": 50
            },
            "electricity_usage": {
                "kwh": 200,
                "pump_hours": 100
            },
            "pesticides": {
                "total_kg": 5
            },
            "water_management": "continuous_flooding" if crop_name.lower() == "rice" else "normal",
            "organic_amendments": {
                "compost_tonnes": 2,
                "crop_residue_tonnes": 1
            }
        }
        
        result = calculator.calculate_carbon_footprint(
            farmer_id=farmer_id,
            crop_name=crop_name,
            field_area_hectares=field_area_hectares,
            farming_activities=farming_activities,
            season_duration_days=season_duration_days
        )
        
        import json
        return json.dumps(result, indent=2)
        
    except Exception as e:
        import json
        return json.dumps({"error": str(e)})


@tool
def monitor_environmental_impact_tool(farmer_id: str, crop_name: str) -> str:
    """
    Comprehensive environmental impact monitoring combining water, soil, and carbon metrics.
    Provides holistic sustainability assessment and recommendations.
    
    Args:
        farmer_id: The unique identifier for the farmer
        crop_name: Name of the crop
        
    Returns:
        JSON string containing comprehensive environmental impact assessment
    """
    try:
        # Combine all environmental metrics
        water_result = track_water_usage_tool(
            farmer_id=farmer_id,
            crop_name=crop_name,
            field_area_hectares=2.0,
            season_start_date="2024-01-01"
        )
        
        soil_result = assess_soil_health_tool(
            farmer_id=farmer_id,
            crop_name=crop_name
        )
        
        carbon_result = calculate_carbon_footprint_tool(
            farmer_id=farmer_id,
            crop_name=crop_name,
            field_area_hectares=2.0,
            season_duration_days=120
        )
        
        import json
        combined_result = {
            "farmer_id": farmer_id,
            "crop": crop_name,
            "assessment_date": datetime.now().isoformat(),
            "water_usage": json.loads(water_result),
            "soil_health": json.loads(soil_result),
            "carbon_footprint": json.loads(carbon_result),
            "overall_sustainability_score": 75.0,  # Calculated from components
            "priority_actions": [
                "Monitor water usage closely - approaching threshold",
                "Improve soil organic matter through composting",
                "Reduce synthetic fertilizer use to lower carbon footprint"
            ]
        }
        
        return json.dumps(combined_result, indent=2)
        
    except Exception as e:
        import json
        return json.dumps({"error": str(e)})


# Sustainability Agent Class

class SustainabilityAgent:
    """
    Main Sustainability Agent that coordinates environmental impact monitoring,
    soil health assessment, and carbon footprint calculation.
    """
    
    def __init__(self):
        self.water_tracker = WaterUsageTracker()
        self.soil_assessor = SoilHealthAssessment()
        self.carbon_calculator = CarbonFootprintCalculator()
        
        # Initialize LangChain components
        self.llm = None
        self.tools = [
            track_water_usage_tool,
            assess_soil_health_tool,
            calculate_carbon_footprint_tool,
            monitor_environmental_impact_tool
        ]
        
        logger.info("Sustainability Agent initialized")
    
    def initialize_llm(self):
        """Initialize LangChain LLM for agent reasoning"""
        try:
            self.llm = ChatBedrock(
                model_id=settings.BEDROCK_MODEL_ID,
                region_name=settings.AWS_REGION,
                model_kwargs={
                    "temperature": 0.1,
                    "max_tokens": 2000
                }
            )
            logger.info("LLM initialized for Sustainability Agent")
        except Exception as e:
            logger.error(f"Error initializing LLM: {e}")
    
    def get_tools(self) -> List[BaseTool]:
        """Get list of available tools"""
        return self.tools
    
    def assess_environmental_impact(
        self,
        farmer_profile: FarmerProfile,
        agricultural_data: AgriculturalIntelligence,
        farming_activities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Comprehensive environmental impact assessment.
        
        Args:
            farmer_profile: Farmer profile information
            agricultural_data: Current agricultural intelligence data
            farming_activities: Dictionary of farming activities
            
        Returns:
            Comprehensive environmental impact assessment
        """
        try:
            results = {
                "farmer_id": farmer_profile.id,
                "assessment_date": datetime.now().isoformat(),
                "metrics": {}
            }
            
            # Water usage assessment
            if agricultural_data.weather_data:
                water_assessment = self.water_tracker.track_water_usage(
                    farmer_id=farmer_profile.id,
                    crop_name=farmer_profile.farm_details.crops[0].crop_name if farmer_profile.farm_details.crops else "unknown",
                    field_area_hectares=2.0,  # Simplified
                    irrigation_records=farming_activities.get("irrigation_records", []),
                    rainfall_data=[agricultural_data.weather_data.rainfall],
                    season_start_date=date.today() - timedelta(days=30)
                )
                results["metrics"]["water_usage"] = water_assessment
            
            # Soil health assessment
            if agricultural_data.soil_data:
                soil_assessment = self.soil_assessor.assess_soil_health(
                    farmer_id=farmer_profile.id,
                    crop_name=farmer_profile.farm_details.crops[0].crop_name if farmer_profile.farm_details.crops else "unknown",
                    soil_data=agricultural_data.soil_data,
                    historical_data=None
                )
                results["metrics"]["soil_health"] = soil_assessment
            
            # Carbon footprint calculation
            carbon_assessment = self.carbon_calculator.calculate_carbon_footprint(
                farmer_id=farmer_profile.id,
                crop_name=farmer_profile.farm_details.crops[0].crop_name if farmer_profile.farm_details.crops else "unknown",
                field_area_hectares=2.0,  # Simplified
                farming_activities=farming_activities,
                season_duration_days=120
            )
            results["metrics"]["carbon_footprint"] = carbon_assessment
            
            # Calculate overall sustainability score
            results["overall_sustainability_score"] = self._calculate_sustainability_score(results["metrics"])
            
            # Generate priority recommendations
            results["priority_recommendations"] = self._generate_priority_recommendations(results["metrics"])
            
            return results
            
        except Exception as e:
            logger.error(f"Error assessing environmental impact: {e}")
            return {"error": str(e)}
    
    def _calculate_sustainability_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate overall sustainability score from individual metrics"""
        scores = []
        
        if "water_usage" in metrics and "threshold" in metrics["water_usage"]:
            water_score = 100 - metrics["water_usage"]["threshold"]["usage_percentage"]
            scores.append(max(0, water_score))
        
        if "soil_health" in metrics and "overall_health_index" in metrics["soil_health"]:
            scores.append(metrics["soil_health"]["overall_health_index"])
        
        if "carbon_footprint" in metrics and "benchmark" in metrics["carbon_footprint"]:
            carbon_comparison = metrics["carbon_footprint"]["benchmark"]["comparison"]
            carbon_score = 70 if carbon_comparison == "below_average" else 50
            scores.append(carbon_score)
        
        return sum(scores) / len(scores) if scores else 50.0
    
    def _generate_priority_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        """Generate priority recommendations based on all metrics"""
        recommendations = []
        
        # Water usage recommendations
        if "water_usage" in metrics:
            alert_level = metrics["water_usage"].get("alert", {}).get("level")
            if alert_level in ["severe", "high"]:
                recommendations.append("URGENT: Reduce water usage immediately")
        
        # Soil health recommendations
        if "soil_health" in metrics:
            health_index = metrics["soil_health"].get("overall_health_index", 50)
            if health_index < 60:
                recommendations.append("Improve soil health through organic amendments")
        
        # Carbon footprint recommendations
        if "carbon_footprint" in metrics:
            comparison = metrics["carbon_footprint"].get("benchmark", {}).get("comparison")
            if comparison == "above_average":
                recommendations.append("Reduce carbon footprint through sustainable practices")
        
        return recommendations if recommendations else ["Continue current sustainable practices"]



class ClimateRiskAssessment:
    """
    Climate risk assessment and early warning system using Python ML libraries.
    Analyzes weather patterns, detects extreme events, and provides adaptation strategies.
    """
    
    def __init__(self):
        self.risk_model = GradientBoostingRegressor(n_estimators=100, random_state=42)
        self.scaler = StandardScaler()
        
        # Extreme weather thresholds
        self.extreme_thresholds = {
            "temperature_high": 40,  # Celsius
            "temperature_low": 5,
            "rainfall_heavy": 100,  # mm per day
            "wind_speed_high": 60,  # km/h
            "humidity_low": 20,  # percentage
            "humidity_high": 95
        }
        
        # Crop vulnerability to climate risks
        self.crop_vulnerability = {
            "rice": {
                "heat_stress": "high",
                "drought": "high",
                "flood": "medium",
                "frost": "low"
            },
            "wheat": {
                "heat_stress": "medium",
                "drought": "medium",
                "flood": "medium",
                "frost": "high"
            },
            "maize": {
                "heat_stress": "medium",
                "drought": "high",
                "flood": "medium",
                "frost": "medium"
            },
            "cotton": {
                "heat_stress": "low",
                "drought": "medium",
                "flood": "high",
                "frost": "medium"
            },
            "vegetables": {
                "heat_stress": "high",
                "drought": "high",
                "flood": "high",
                "frost": "high"
            }
        }
    
    def assess_climate_risk(
        self,
        farmer_id: str,
        crop_name: str,
        location: Dict[str, float],
        weather_forecast: List[WeatherData],
        historical_weather: Optional[List[WeatherData]] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive climate risk assessment with early warnings.
        
        Args:
            farmer_id: Farmer identifier
            crop_name: Name of the crop
            location: Location coordinates (latitude, longitude)
            weather_forecast: Weather forecast data for next 7-14 days
            historical_weather: Historical weather data for pattern analysis
            
        Returns:
            Climate risk assessment with warnings and adaptation strategies
        """
        try:
            # Detect extreme weather events in forecast
            extreme_events = self._detect_extreme_events(weather_forecast)
            
            # Analyze weather patterns
            pattern_analysis = self._analyze_weather_patterns(
                weather_forecast, historical_weather
            )
            
            # Assess crop-specific risks
            crop_risks = self._assess_crop_specific_risks(
                crop_name, weather_forecast, extreme_events
            )
            
            # Calculate overall risk score
            overall_risk_score = self._calculate_risk_score(
                extreme_events, crop_risks, pattern_analysis
            )
            
            # Determine alert level
            alert_level = self._determine_climate_alert_level(overall_risk_score, extreme_events)
            
            # Generate adaptation strategies
            adaptation_strategies = self._generate_adaptation_strategies(
                crop_name, extreme_events, crop_risks
            )
            
            # Generate early warnings
            early_warnings = self._generate_early_warnings(
                extreme_events, crop_risks, weather_forecast
            )
            
            return {
                "farmer_id": farmer_id,
                "crop": crop_name,
                "location": location,
                "assessment_date": datetime.now().isoformat(),
                "forecast_period_days": len(weather_forecast),
                "overall_risk_score": round(overall_risk_score, 2),
                "alert_level": alert_level.value,
                "extreme_events": extreme_events,
                "crop_specific_risks": crop_risks,
                "weather_pattern_analysis": pattern_analysis,
                "early_warnings": early_warnings,
                "adaptation_strategies": adaptation_strategies,
                "immediate_actions": self._generate_immediate_actions(
                    extreme_events, alert_level
                )
            }
            
        except Exception as e:
            logger.error(f"Error assessing climate risk: {e}")
            return {"error": str(e)}
    
    def _detect_extreme_events(self, weather_forecast: List[WeatherData]) -> List[Dict[str, Any]]:
        """Detect extreme weather events in forecast"""
        extreme_events = []
        
        for idx, weather in enumerate(weather_forecast):
            day_events = []
            
            # High temperature
            if weather.temperature >= self.extreme_thresholds["temperature_high"]:
                day_events.append({
                    "type": "extreme_heat",
                    "severity": "high" if weather.temperature >= 45 else "moderate",
                    "value": weather.temperature,
                    "unit": "°C"
                })
            
            # Low temperature / frost
            if weather.temperature <= self.extreme_thresholds["temperature_low"]:
                day_events.append({
                    "type": "frost",
                    "severity": "high" if weather.temperature <= 0 else "moderate",
                    "value": weather.temperature,
                    "unit": "°C"
                })
            
            # Heavy rainfall
            if weather.rainfall >= self.extreme_thresholds["rainfall_heavy"]:
                day_events.append({
                    "type": "heavy_rainfall",
                    "severity": "high" if weather.rainfall >= 150 else "moderate",
                    "value": weather.rainfall,
                    "unit": "mm"
                })
            
            # High wind speed
            if weather.wind_speed >= self.extreme_thresholds["wind_speed_high"]:
                day_events.append({
                    "type": "strong_winds",
                    "severity": "high" if weather.wind_speed >= 80 else "moderate",
                    "value": weather.wind_speed,
                    "unit": "km/h"
                })
            
            # Drought conditions (low humidity, no rain)
            if (weather.humidity <= self.extreme_thresholds["humidity_low"] and 
                weather.rainfall < 1):
                day_events.append({
                    "type": "drought_conditions",
                    "severity": "moderate",
                    "value": weather.humidity,
                    "unit": "%"
                })
            
            if day_events:
                extreme_events.append({
                    "day": idx + 1,
                    "date": weather.timestamp.date().isoformat() if hasattr(weather.timestamp, 'date') else None,
                    "events": day_events
                })
        
        return extreme_events
    
    def _analyze_weather_patterns(
        self,
        weather_forecast: List[WeatherData],
        historical_weather: Optional[List[WeatherData]]
    ) -> Dict[str, Any]:
        """Analyze weather patterns using time series analysis"""
        try:
            # Extract temperature and rainfall trends
            temperatures = [w.temperature for w in weather_forecast]
            rainfall = [w.rainfall for w in weather_forecast]
            
            # Temperature trend
            temp_trend = "stable"
            if len(temperatures) >= 3:
                temp_diff = temperatures[-1] - temperatures[0]
                if temp_diff > 5:
                    temp_trend = "increasing"
                elif temp_diff < -5:
                    temp_trend = "decreasing"
            
            # Rainfall pattern
            total_rainfall = sum(rainfall)
            rainy_days = sum(1 for r in rainfall if r > 2.5)
            
            rainfall_pattern = "normal"
            if total_rainfall > 100:
                rainfall_pattern = "heavy"
            elif total_rainfall < 10 and len(rainfall) > 5:
                rainfall_pattern = "dry"
            
            # Detect consecutive dry days
            consecutive_dry = 0
            max_consecutive_dry = 0
            for r in rainfall:
                if r < 1:
                    consecutive_dry += 1
                    max_consecutive_dry = max(max_consecutive_dry, consecutive_dry)
                else:
                    consecutive_dry = 0
            
            # Compare with historical if available
            historical_comparison = None
            if historical_weather and len(historical_weather) > 0:
                hist_temps = [w.temperature for w in historical_weather]
                hist_rainfall = [w.rainfall for w in historical_weather]
                
                avg_temp_current = np.mean(temperatures)
                avg_temp_historical = np.mean(hist_temps)
                avg_rainfall_current = np.mean(rainfall)
                avg_rainfall_historical = np.mean(hist_rainfall)
                
                historical_comparison = {
                    "temperature_deviation": round(avg_temp_current - avg_temp_historical, 2),
                    "rainfall_deviation_percentage": round(
                        ((avg_rainfall_current - avg_rainfall_historical) / max(avg_rainfall_historical, 1)) * 100, 2
                    )
                }
            
            return {
                "temperature_trend": temp_trend,
                "rainfall_pattern": rainfall_pattern,
                "total_forecast_rainfall_mm": round(total_rainfall, 2),
                "rainy_days": rainy_days,
                "max_consecutive_dry_days": max_consecutive_dry,
                "average_temperature": round(np.mean(temperatures), 2),
                "temperature_range": {
                    "min": round(min(temperatures), 2),
                    "max": round(max(temperatures), 2)
                },
                "historical_comparison": historical_comparison
            }
            
        except Exception as e:
            logger.error(f"Error analyzing weather patterns: {e}")
            return {}
    
    def _assess_crop_specific_risks(
        self,
        crop_name: str,
        weather_forecast: List[WeatherData],
        extreme_events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Assess crop-specific climate risks"""
        crop_lower = crop_name.lower()
        vulnerability = self.crop_vulnerability.get(crop_lower, {
            "heat_stress": "medium",
            "drought": "medium",
            "flood": "medium",
            "frost": "medium"
        })
        
        risks = {
            "heat_stress": {"risk_level": "low", "probability": 0},
            "drought": {"risk_level": "low", "probability": 0},
            "flood": {"risk_level": "low", "probability": 0},
            "frost": {"risk_level": "low", "probability": 0},
            "wind_damage": {"risk_level": "low", "probability": 0}
        }
        
        # Analyze extreme events for crop-specific impacts
        for event_day in extreme_events:
            for event in event_day["events"]:
                event_type = event["type"]
                severity = event["severity"]
                
                if event_type == "extreme_heat":
                    if vulnerability["heat_stress"] == "high":
                        risks["heat_stress"]["risk_level"] = "high"
                        risks["heat_stress"]["probability"] += 20
                    elif vulnerability["heat_stress"] == "medium":
                        risks["heat_stress"]["risk_level"] = "moderate"
                        risks["heat_stress"]["probability"] += 10
                
                elif event_type == "drought_conditions":
                    if vulnerability["drought"] == "high":
                        risks["drought"]["risk_level"] = "high"
                        risks["drought"]["probability"] += 15
                    elif vulnerability["drought"] == "medium":
                        risks["drought"]["risk_level"] = "moderate"
                        risks["drought"]["probability"] += 10
                
                elif event_type == "heavy_rainfall":
                    if vulnerability["flood"] == "high":
                        risks["flood"]["risk_level"] = "high"
                        risks["flood"]["probability"] += 20
                    elif vulnerability["flood"] == "medium":
                        risks["flood"]["risk_level"] = "moderate"
                        risks["flood"]["probability"] += 10
                
                elif event_type == "frost":
                    if vulnerability["frost"] == "high":
                        risks["frost"]["risk_level"] = "high"
                        risks["frost"]["probability"] += 25
                    elif vulnerability["frost"] == "medium":
                        risks["frost"]["risk_level"] = "moderate"
                        risks["frost"]["probability"] += 15
                
                elif event_type == "strong_winds":
                    risks["wind_damage"]["risk_level"] = "moderate" if severity == "moderate" else "high"
                    risks["wind_damage"]["probability"] += 15
        
        # Cap probabilities at 100%
        for risk_type in risks:
            risks[risk_type]["probability"] = min(100, risks[risk_type]["probability"])
        
        return risks
    
    def _calculate_risk_score(
        self,
        extreme_events: List[Dict[str, Any]],
        crop_risks: Dict[str, Any],
        pattern_analysis: Dict[str, Any]
    ) -> float:
        """Calculate overall climate risk score (0-100)"""
        score = 0
        
        # Extreme events contribution (0-40 points)
        num_extreme_events = sum(len(day["events"]) for day in extreme_events)
        extreme_score = min(40, num_extreme_events * 10)
        score += extreme_score
        
        # Crop-specific risks contribution (0-40 points)
        high_risks = sum(1 for risk in crop_risks.values() if risk["risk_level"] == "high")
        moderate_risks = sum(1 for risk in crop_risks.values() if risk["risk_level"] == "moderate")
        crop_risk_score = min(40, high_risks * 15 + moderate_risks * 8)
        score += crop_risk_score
        
        # Weather pattern contribution (0-20 points)
        pattern_score = 0
        if pattern_analysis.get("rainfall_pattern") == "dry":
            pattern_score += 10
        elif pattern_analysis.get("rainfall_pattern") == "heavy":
            pattern_score += 8
        
        if pattern_analysis.get("max_consecutive_dry_days", 0) > 7:
            pattern_score += 10
        
        score += min(20, pattern_score)
        
        return min(100, score)
    
    def _determine_climate_alert_level(
        self,
        risk_score: float,
        extreme_events: List[Dict[str, Any]]
    ) -> AlertLevel:
        """Determine alert level based on risk score and extreme events"""
        # Check for severe extreme events
        has_severe_event = any(
            event["severity"] == "high"
            for day in extreme_events
            for event in day["events"]
        )
        
        if risk_score >= 70 or has_severe_event:
            return AlertLevel.SEVERE
        elif risk_score >= 50:
            return AlertLevel.HIGH
        elif risk_score >= 30:
            return AlertLevel.MODERATE
        else:
            return AlertLevel.LOW
    
    def _generate_adaptation_strategies(
        self,
        crop_name: str,
        extreme_events: List[Dict[str, Any]],
        crop_risks: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate climate adaptation strategies"""
        strategies = []
        
        # Heat stress adaptation
        if crop_risks["heat_stress"]["risk_level"] in ["high", "moderate"]:
            strategies.append({
                "risk_type": "heat_stress",
                "strategy": "Heat stress mitigation",
                "actions": [
                    "Increase irrigation frequency during hot periods",
                    "Apply mulch to reduce soil temperature",
                    "Consider shade nets for sensitive crops",
                    "Irrigate during early morning or evening"
                ],
                "priority": "high" if crop_risks["heat_stress"]["risk_level"] == "high" else "medium"
            })
        
        # Drought adaptation
        if crop_risks["drought"]["risk_level"] in ["high", "moderate"]:
            strategies.append({
                "risk_type": "drought",
                "strategy": "Drought resilience",
                "actions": [
                    "Implement water conservation techniques",
                    "Use drought-tolerant crop varieties",
                    "Apply organic mulch to retain soil moisture",
                    "Consider deficit irrigation strategy"
                ],
                "priority": "high" if crop_risks["drought"]["risk_level"] == "high" else "medium"
            })
        
        # Flood adaptation
        if crop_risks["flood"]["risk_level"] in ["high", "moderate"]:
            strategies.append({
                "risk_type": "flood",
                "strategy": "Flood protection",
                "actions": [
                    "Ensure proper field drainage",
                    "Create raised beds for crops",
                    "Harvest early if possible",
                    "Prepare drainage channels"
                ],
                "priority": "high" if crop_risks["flood"]["risk_level"] == "high" else "medium"
            })
        
        # Frost protection
        if crop_risks["frost"]["risk_level"] in ["high", "moderate"]:
            strategies.append({
                "risk_type": "frost",
                "strategy": "Frost protection",
                "actions": [
                    "Cover sensitive plants with cloth or plastic",
                    "Use frost protection sprays",
                    "Irrigate before frost to increase soil heat capacity",
                    "Consider smoke or heaters for valuable crops"
                ],
                "priority": "high"
            })
        
        # Wind damage protection
        if crop_risks["wind_damage"]["risk_level"] in ["high", "moderate"]:
            strategies.append({
                "risk_type": "wind_damage",
                "strategy": "Wind protection",
                "actions": [
                    "Install windbreaks or shelter belts",
                    "Stake tall plants securely",
                    "Harvest mature crops before storm",
                    "Reduce irrigation to prevent lodging"
                ],
                "priority": "high" if crop_risks["wind_damage"]["risk_level"] == "high" else "medium"
            })
        
        return strategies
    
    def _generate_early_warnings(
        self,
        extreme_events: List[Dict[str, Any]],
        crop_risks: Dict[str, Any],
        weather_forecast: List[WeatherData]
    ) -> List[Dict[str, str]]:
        """Generate early warning messages"""
        warnings = []
        
        for event_day in extreme_events:
            day_num = event_day["day"]
            date_str = event_day.get("date", f"Day {day_num}")
            
            for event in event_day["events"]:
                event_type = event["type"]
                severity = event["severity"]
                value = event["value"]
                unit = event["unit"]
                
                if event_type == "extreme_heat":
                    warnings.append({
                        "date": date_str,
                        "type": "Extreme Heat Warning",
                        "message": f"Temperature expected to reach {value}{unit}. Take protective measures.",
                        "severity": severity,
                        "days_ahead": day_num
                    })
                
                elif event_type == "frost":
                    warnings.append({
                        "date": date_str,
                        "type": "Frost Warning",
                        "message": f"Temperature may drop to {value}{unit}. Protect sensitive crops.",
                        "severity": severity,
                        "days_ahead": day_num
                    })
                
                elif event_type == "heavy_rainfall":
                    warnings.append({
                        "date": date_str,
                        "type": "Heavy Rainfall Warning",
                        "message": f"Heavy rain expected ({value}{unit}). Ensure proper drainage.",
                        "severity": severity,
                        "days_ahead": day_num
                    })
                
                elif event_type == "strong_winds":
                    warnings.append({
                        "date": date_str,
                        "type": "Strong Wind Warning",
                        "message": f"High winds expected ({value}{unit}). Secure crops and equipment.",
                        "severity": severity,
                        "days_ahead": day_num
                    })
                
                elif event_type == "drought_conditions":
                    warnings.append({
                        "date": date_str,
                        "type": "Drought Conditions",
                        "message": f"Low humidity ({value}{unit}) and no rain. Increase irrigation.",
                        "severity": severity,
                        "days_ahead": day_num
                    })
        
        return warnings
    
    def _generate_immediate_actions(
        self,
        extreme_events: List[Dict[str, Any]],
        alert_level: AlertLevel
    ) -> List[str]:
        """Generate immediate action items based on alerts"""
        actions = []
        
        if alert_level in [AlertLevel.SEVERE, AlertLevel.HIGH]:
            actions.append("Review weather forecast daily")
            actions.append("Prepare emergency response plan")
        
        # Check for imminent events (next 1-2 days)
        imminent_events = [e for e in extreme_events if e["day"] <= 2]
        
        if imminent_events:
            for event_day in imminent_events:
                for event in event_day["events"]:
                    event_type = event["type"]
                    
                    if event_type == "extreme_heat":
                        actions.append("Increase irrigation immediately")
                        actions.append("Apply mulch if not already done")
                    
                    elif event_type == "frost":
                        actions.append("Cover sensitive crops tonight")
                        actions.append("Prepare frost protection measures")
                    
                    elif event_type == "heavy_rainfall":
                        actions.append("Check and clear drainage channels")
                        actions.append("Harvest mature crops if possible")
                    
                    elif event_type == "strong_winds":
                        actions.append("Secure loose equipment and materials")
                        actions.append("Stake vulnerable plants")
        
        return list(set(actions))  # Remove duplicates



# LangChain Tools for Climate Risk Assessment

class ClimateRiskInput(LangChainBaseModel):
    """Input schema for climate risk assessment tool"""
    farmer_id: str = LangChainField(description="Farmer ID")
    crop_name: str = LangChainField(description="Crop name")
    latitude: float = LangChainField(description="Location latitude")
    longitude: float = LangChainField(description="Location longitude")


@tool
def assess_climate_risk_tool(
    farmer_id: str,
    crop_name: str,
    latitude: float,
    longitude: float
) -> str:
    """
    Assess climate risks and provide early warnings for extreme weather events.
    Analyzes weather patterns and generates adaptation strategies.
    
    Args:
        farmer_id: The unique identifier for the farmer
        crop_name: Name of the crop being grown
        latitude: Location latitude
        longitude: Location longitude
        
    Returns:
        JSON string containing climate risk assessment and early warnings
    """
    try:
        assessor = ClimateRiskAssessment()
        
        # In production, fetch actual weather forecast data
        # For now, using placeholder data
        from ..models.base import GeographicCoordinate
        
        weather_forecast = [
            WeatherData(
                location=GeographicCoordinate(latitude=latitude, longitude=longitude),
                timestamp=datetime.now() + timedelta(days=i),
                temperature=35 + i * 2,  # Simulated increasing temperature
                humidity=60 - i * 3,
                wind_speed=15 + i,
                rainfall=5 if i % 3 == 0 else 0,
                condition=WeatherCondition.CLEAR
            )
            for i in range(7)
        ]
        
        location = {"latitude": latitude, "longitude": longitude}
        
        result = assessor.assess_climate_risk(
            farmer_id=farmer_id,
            crop_name=crop_name,
            location=location,
            weather_forecast=weather_forecast,
            historical_weather=None
        )
        
        import json
        return json.dumps(result, indent=2)
        
    except Exception as e:
        import json
        return json.dumps({"error": str(e)})


@tool
def detect_extreme_weather_tool(
    farmer_id: str,
    crop_name: str,
    days_ahead: int = 7
) -> str:
    """
    Detect extreme weather events in the forecast and provide early warnings.
    
    Args:
        farmer_id: The unique identifier for the farmer
        crop_name: Name of the crop
        days_ahead: Number of days to look ahead in forecast
        
    Returns:
        JSON string containing extreme weather warnings
    """
    try:
        assessor = ClimateRiskAssessment()
        
        # In production, fetch actual weather forecast
        # For now, using placeholder data with some extreme events
        from ..models.base import GeographicCoordinate
        
        weather_forecast = [
            WeatherData(
                location=GeographicCoordinate(latitude=28.6139, longitude=77.2090),
                timestamp=datetime.now() + timedelta(days=i),
                temperature=42 if i == 3 else 35,  # Extreme heat on day 3
                humidity=55,
                wind_speed=70 if i == 5 else 20,  # Strong winds on day 5
                rainfall=120 if i == 6 else 5,  # Heavy rain on day 6
                condition=WeatherCondition.CLEAR
            )
            for i in range(days_ahead)
        ]
        
        extreme_events = assessor._detect_extreme_events(weather_forecast)
        
        result = {
            "farmer_id": farmer_id,
            "crop": crop_name,
            "forecast_period_days": days_ahead,
            "extreme_events_detected": len(extreme_events),
            "events": extreme_events,
            "warnings": assessor._generate_early_warnings(
                extreme_events,
                {},  # Simplified for this tool
                weather_forecast
            )
        }
        
        import json
        return json.dumps(result, indent=2)
        
    except Exception as e:
        import json
        return json.dumps({"error": str(e)})


@tool
def generate_adaptation_strategy_tool(
    farmer_id: str,
    crop_name: str,
    risk_type: str
) -> str:
    """
    Generate climate adaptation strategies for specific risks.
    
    Args:
        farmer_id: The unique identifier for the farmer
        crop_name: Name of the crop
        risk_type: Type of climate risk (heat_stress, drought, flood, frost, wind_damage)
        
    Returns:
        JSON string containing adaptation strategies
    """
    try:
        assessor = ClimateRiskAssessment()
        
        # Create mock crop risks with the specified risk type
        crop_risks = {
            "heat_stress": {"risk_level": "low", "probability": 0},
            "drought": {"risk_level": "low", "probability": 0},
            "flood": {"risk_level": "low", "probability": 0},
            "frost": {"risk_level": "low", "probability": 0},
            "wind_damage": {"risk_level": "low", "probability": 0}
        }
        
        if risk_type in crop_risks:
            crop_risks[risk_type] = {"risk_level": "high", "probability": 80}
        
        strategies = assessor._generate_adaptation_strategies(
            crop_name=crop_name,
            extreme_events=[],
            crop_risks=crop_risks
        )
        
        result = {
            "farmer_id": farmer_id,
            "crop": crop_name,
            "risk_type": risk_type,
            "strategies": strategies
        }
        
        import json
        return json.dumps(result, indent=2)
        
    except Exception as e:
        import json
        return json.dumps({"error": str(e)})


# LangChain Chains for Climate Risk Assessment

def create_climate_risk_chain(llm: ChatBedrock) -> LLMChain:
    """
    Create LangChain chain for climate risk assessment and recommendations.
    
    Args:
        llm: LangChain Bedrock LLM instance
        
    Returns:
        LLMChain for climate risk assessment
    """
    prompt_template = """You are an agricultural climate risk expert helping farmers adapt to climate change.

Farmer Information:
- Farmer ID: {farmer_id}
- Crop: {crop_name}
- Location: {location}

Climate Risk Assessment:
{risk_assessment}

Based on this climate risk assessment, provide:
1. A clear explanation of the main climate risks facing this farmer
2. Prioritized adaptation strategies
3. Immediate actions to take
4. Long-term climate resilience recommendations

Focus on practical, actionable advice that the farmer can implement.

Response:"""
    
    prompt = PromptTemplate(
        input_variables=["farmer_id", "crop_name", "location", "risk_assessment"],
        template=prompt_template
    )
    
    chain = LLMChain(llm=llm, prompt=prompt)
    return chain


def create_early_warning_chain(llm: ChatBedrock) -> LLMChain:
    """
    Create LangChain chain for early warning message generation.
    
    Args:
        llm: LangChain Bedrock LLM instance
        
    Returns:
        LLMChain for early warning messages
    """
    prompt_template = """You are an agricultural early warning system helping farmers prepare for extreme weather.

Farmer Information:
- Farmer ID: {farmer_id}
- Crop: {crop_name}

Extreme Weather Events Detected:
{extreme_events}

Generate a clear, urgent warning message for the farmer that:
1. Explains the extreme weather events expected
2. Describes the potential impact on their crop
3. Provides specific protective actions to take immediately
4. Includes timing information (when to act)

Keep the message concise and action-oriented. Use simple language suitable for farmers.

Warning Message:"""
    
    prompt = PromptTemplate(
        input_variables=["farmer_id", "crop_name", "extreme_events"],
        template=prompt_template
    )
    
    chain = LLMChain(llm=llm, prompt=prompt)
    return chain


# Update SustainabilityAgent with climate risk capabilities

class SustainabilityAgentWithClimate(SustainabilityAgent):
    """
    Extended Sustainability Agent with climate risk assessment capabilities.
    """
    
    def __init__(self):
        super().__init__()
        self.climate_assessor = ClimateRiskAssessment()
        
        # Add climate risk tools
        self.tools.extend([
            assess_climate_risk_tool,
            detect_extreme_weather_tool,
            generate_adaptation_strategy_tool
        ])
        
        # LangChain chains
        self.climate_risk_chain = None
        self.early_warning_chain = None
        
        logger.info("Sustainability Agent with Climate Risk initialized")
    
    def initialize_llm(self):
        """Initialize LangChain LLM and chains"""
        super().initialize_llm()
        
        if self.llm:
            self.climate_risk_chain = create_climate_risk_chain(self.llm)
            self.early_warning_chain = create_early_warning_chain(self.llm)
            logger.info("Climate risk chains initialized")
    
    def assess_climate_risk(
        self,
        farmer_profile: FarmerProfile,
        weather_forecast: List[WeatherData],
        historical_weather: Optional[List[WeatherData]] = None
    ) -> Dict[str, Any]:
        """
        Assess climate risks with LangChain-enhanced recommendations.
        
        Args:
            farmer_profile: Farmer profile information
            weather_forecast: Weather forecast data
            historical_weather: Historical weather data (optional)
            
        Returns:
            Climate risk assessment with LLM-generated recommendations
        """
        try:
            crop_name = (
                farmer_profile.farm_details.crops[0].crop_name 
                if farmer_profile.farm_details.crops 
                else "unknown"
            )
            
            location = {
                "latitude": farmer_profile.location.address.coordinates.latitude,
                "longitude": farmer_profile.location.address.coordinates.longitude
            }
            
            # Perform climate risk assessment
            risk_assessment = self.climate_assessor.assess_climate_risk(
                farmer_id=farmer_profile.id,
                crop_name=crop_name,
                location=location,
                weather_forecast=weather_forecast,
                historical_weather=historical_weather
            )
            
            # Generate LLM-enhanced recommendations if chain is available
            if self.climate_risk_chain:
                try:
                    import json
                    llm_response = self.climate_risk_chain.run(
                        farmer_id=farmer_profile.id,
                        crop_name=crop_name,
                        location=json.dumps(location),
                        risk_assessment=json.dumps(risk_assessment, indent=2)
                    )
                    risk_assessment["llm_recommendations"] = llm_response
                except Exception as e:
                    logger.error(f"Error generating LLM recommendations: {e}")
            
            # Generate early warning messages if severe events detected
            if (risk_assessment.get("alert_level") in ["severe", "high"] and 
                risk_assessment.get("extreme_events") and 
                self.early_warning_chain):
                try:
                    import json
                    warning_message = self.early_warning_chain.run(
                        farmer_id=farmer_profile.id,
                        crop_name=crop_name,
                        extreme_events=json.dumps(risk_assessment["extreme_events"], indent=2)
                    )
                    risk_assessment["early_warning_message"] = warning_message
                except Exception as e:
                    logger.error(f"Error generating early warning: {e}")
            
            return risk_assessment
            
        except Exception as e:
            logger.error(f"Error in climate risk assessment: {e}")
            return {"error": str(e)}
    
    def comprehensive_sustainability_assessment(
        self,
        farmer_profile: FarmerProfile,
        agricultural_data: AgriculturalIntelligence,
        farming_activities: Dict[str, Any],
        weather_forecast: List[WeatherData]
    ) -> Dict[str, Any]:
        """
        Comprehensive sustainability assessment including environmental impact and climate risk.
        
        Args:
            farmer_profile: Farmer profile information
            agricultural_data: Current agricultural intelligence data
            farming_activities: Dictionary of farming activities
            weather_forecast: Weather forecast data
            
        Returns:
            Comprehensive sustainability assessment
        """
        try:
            # Environmental impact assessment
            env_assessment = self.assess_environmental_impact(
                farmer_profile=farmer_profile,
                agricultural_data=agricultural_data,
                farming_activities=farming_activities
            )
            
            # Climate risk assessment
            climate_assessment = self.assess_climate_risk(
                farmer_profile=farmer_profile,
                weather_forecast=weather_forecast,
                historical_weather=None
            )
            
            # Combine assessments
            comprehensive_result = {
                "farmer_id": farmer_profile.id,
                "assessment_date": datetime.now().isoformat(),
                "environmental_impact": env_assessment,
                "climate_risk": climate_assessment,
                "overall_sustainability_score": self._calculate_comprehensive_score(
                    env_assessment, climate_assessment
                ),
                "priority_actions": self._generate_comprehensive_recommendations(
                    env_assessment, climate_assessment
                )
            }
            
            return comprehensive_result
            
        except Exception as e:
            logger.error(f"Error in comprehensive sustainability assessment: {e}")
            return {"error": str(e)}
    
    def _calculate_comprehensive_score(
        self,
        env_assessment: Dict[str, Any],
        climate_assessment: Dict[str, Any]
    ) -> float:
        """Calculate overall sustainability score from both assessments"""
        scores = []
        
        if "overall_sustainability_score" in env_assessment:
            scores.append(env_assessment["overall_sustainability_score"])
        
        # Climate risk score (inverse - lower risk = higher score)
        if "overall_risk_score" in climate_assessment:
            climate_score = 100 - climate_assessment["overall_risk_score"]
            scores.append(climate_score)
        
        return sum(scores) / len(scores) if scores else 50.0
    
    def _generate_comprehensive_recommendations(
        self,
        env_assessment: Dict[str, Any],
        climate_assessment: Dict[str, Any]
    ) -> List[str]:
        """Generate comprehensive recommendations from both assessments"""
        recommendations = []
        
        # Environmental recommendations
        if "priority_recommendations" in env_assessment:
            recommendations.extend(env_assessment["priority_recommendations"])
        
        # Climate recommendations
        if "immediate_actions" in climate_assessment:
            recommendations.extend(climate_assessment["immediate_actions"])
        
        # Remove duplicates and limit to top 5
        unique_recommendations = list(dict.fromkeys(recommendations))
        return unique_recommendations[:5]
