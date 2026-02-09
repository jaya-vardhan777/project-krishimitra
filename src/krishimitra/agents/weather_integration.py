"""
Weather API Integration for KrishiMitra Platform

This module integrates with India Meteorological Department APIs and other weather services
to provide real-time weather data and forecasts for agricultural decision making.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
import asyncio

import httpx
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

from ..core.config import get_settings
from ..models.agricultural_intelligence import WeatherData, WeatherCondition, AlertLevel

logger = logging.getLogger(__name__)
settings = get_settings()


class WeatherAPIConfig(BaseModel):
    """Configuration for weather API services"""
    imd_api_key: Optional[str] = Field(default=None, description="India Meteorological Department API key")
    openweather_api_key: Optional[str] = Field(default=None, description="OpenWeatherMap API key")
    weatherapi_key: Optional[str] = Field(default=None, description="WeatherAPI.com key")
    base_urls: Dict[str, str] = Field(
        default_factory=lambda: {
            "imd": "https://api.imd.gov.in/v1",
            "openweather": "https://api.openweathermap.org/data/2.5",
            "weatherapi": "https://api.weatherapi.com/v1"
        }
    )


class WeatherAPIClient:
    """Client for integrating with multiple weather APIs"""
    
    def __init__(self, config: Optional[WeatherAPIConfig] = None):
        self.config = config or WeatherAPIConfig()
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get_current_weather_imd(self, latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
        """Get current weather from India Meteorological Department"""
        try:
            # IMD API endpoint (this is a placeholder - actual IMD API structure may vary)
            url = f"{self.config.base_urls['imd']}/weather/current"
            params = {
                "lat": latitude,
                "lon": longitude,
                "key": self.config.imd_api_key
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Retrieved IMD weather data for {latitude}, {longitude}")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching IMD weather data: {e}")
            return None
    
    async def get_current_weather_openweather(self, latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
        """Get current weather from OpenWeatherMap"""
        try:
            url = f"{self.config.base_urls['openweather']}/weather"
            params = {
                "lat": latitude,
                "lon": longitude,
                "appid": self.config.openweather_api_key,
                "units": "metric"
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Retrieved OpenWeatherMap data for {latitude}, {longitude}")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching OpenWeatherMap data: {e}")
            return None
    
    async def get_weather_forecast(self, latitude: float, longitude: float, days: int = 7) -> Optional[List[Dict[str, Any]]]:
        """Get weather forecast for specified days"""
        try:
            url = f"{self.config.base_urls['weatherapi']}/forecast.json"
            params = {
                "key": self.config.weatherapi_key,
                "q": f"{latitude},{longitude}",
                "days": min(days, 10),  # API limit
                "aqi": "yes",
                "alerts": "yes"
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Retrieved weather forecast for {latitude}, {longitude}")
            return data.get("forecast", {}).get("forecastday", [])
            
        except Exception as e:
            logger.error(f"Error fetching weather forecast: {e}")
            return None
    
    async def get_agricultural_weather_data(self, latitude: float, longitude: float) -> Optional[WeatherData]:
        """Get comprehensive weather data optimized for agriculture"""
        try:
            # Try multiple sources and combine the best data
            current_data = None
            
            # Try IMD first (preferred for India)
            if self.config.imd_api_key:
                current_data = await self.get_current_weather_imd(latitude, longitude)
            
            # Fallback to OpenWeatherMap
            if not current_data and self.config.openweather_api_key:
                current_data = await self.get_current_weather_openweather(latitude, longitude)
            
            if not current_data:
                logger.warning("No weather data available from any source")
                return None
            
            # Convert to standardized WeatherData model
            weather_data = self._convert_to_weather_data(current_data, latitude, longitude)
            return weather_data
            
        except Exception as e:
            logger.error(f"Error getting agricultural weather data: {e}")
            return None
    
    def _convert_to_weather_data(self, raw_data: Dict[str, Any], latitude: float, longitude: float) -> WeatherData:
        """Convert raw API data to standardized WeatherData model"""
        try:
            # This is a simplified conversion - actual implementation would depend on API structure
            if "main" in raw_data:  # OpenWeatherMap format
                return WeatherData(
                    location={"latitude": latitude, "longitude": longitude},
                    timestamp=datetime.now(timezone.utc),
                    temperature=raw_data["main"]["temp"],
                    feels_like=raw_data["main"].get("feels_like"),
                    humidity=raw_data["main"]["humidity"],
                    pressure=raw_data["main"].get("pressure"),
                    wind_speed=raw_data.get("wind", {}).get("speed", 0) * 3.6,  # Convert m/s to km/h
                    wind_direction=raw_data.get("wind", {}).get("deg"),
                    rainfall=raw_data.get("rain", {}).get("1h", 0),
                    condition=self._map_weather_condition(raw_data.get("weather", [{}])[0].get("main", "Clear")),
                    cloud_cover=raw_data.get("clouds", {}).get("all", 0),
                    visibility=raw_data.get("visibility", 10000) / 1000,  # Convert m to km
                    weather_alerts=[]
                )
            else:
                # Generic format or IMD format
                return WeatherData(
                    location={"latitude": latitude, "longitude": longitude},
                    timestamp=datetime.now(timezone.utc),
                    temperature=raw_data.get("temperature", 25.0),
                    humidity=raw_data.get("humidity", 60.0),
                    wind_speed=raw_data.get("wind_speed", 5.0),
                    rainfall=raw_data.get("rainfall", 0.0),
                    condition=WeatherCondition.CLEAR,
                    weather_alerts=[]
                )
                
        except Exception as e:
            logger.error(f"Error converting weather data: {e}")
            # Return default weather data
            return WeatherData(
                location={"latitude": latitude, "longitude": longitude},
                timestamp=datetime.now(timezone.utc),
                temperature=25.0,
                humidity=60.0,
                wind_speed=5.0,
                rainfall=0.0,
                condition=WeatherCondition.CLEAR,
                weather_alerts=[]
            )
    
    def _map_weather_condition(self, condition_str: str) -> WeatherCondition:
        """Map API weather condition to our enum"""
        condition_mapping = {
            "Clear": WeatherCondition.CLEAR,
            "Clouds": WeatherCondition.CLOUDY,
            "Rain": WeatherCondition.MODERATE_RAIN,
            "Drizzle": WeatherCondition.LIGHT_RAIN,
            "Thunderstorm": WeatherCondition.THUNDERSTORM,
            "Snow": WeatherCondition.CLEAR,  # Rare in India
            "Mist": WeatherCondition.FOG,
            "Fog": WeatherCondition.FOG,
            "Haze": WeatherCondition.HAZE,
            "Dust": WeatherCondition.DUST_STORM
        }
        return condition_mapping.get(condition_str, WeatherCondition.CLEAR)
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


class WeatherDataTool(BaseTool):
    """LangChain tool for weather data collection"""
    
    name: str = "weather_data_collection"
    description: str = "Collect current weather data and forecasts for agricultural locations"
    
    def _run(self, latitude: float, longitude: float) -> str:
        """Run the weather data collection tool"""
        async def get_weather():
            weather_client = WeatherAPIClient()
            try:
                weather_data = await weather_client.get_agricultural_weather_data(latitude, longitude)
                if weather_data:
                    return f"Weather data for {latitude}, {longitude}: {weather_data.temperature}°C, {weather_data.condition.value}, humidity {weather_data.humidity}%, wind {weather_data.wind_speed} km/h"
                else:
                    return f"Unable to retrieve weather data for {latitude}, {longitude}"
            finally:
                await weather_client.close()
        
        return asyncio.run(get_weather())
    
    async def _arun(self, latitude: float, longitude: float) -> str:
        """Async version of the tool"""
        weather_client = WeatherAPIClient()
        try:
            weather_data = await weather_client.get_agricultural_weather_data(latitude, longitude)
            if weather_data:
                return f"Weather data for {latitude}, {longitude}: {weather_data.temperature}°C, {weather_data.condition.value}, humidity {weather_data.humidity}%, wind {weather_data.wind_speed} km/h"
            else:
                return f"Unable to retrieve weather data for {latitude}, {longitude}"
        finally:
            await weather_client.close()


class WeatherAnalysisChain:
    """LangChain chain for weather data analysis and agricultural insights"""
    
    def __init__(self, llm=None):
        self.llm = llm
        self.weather_client = WeatherAPIClient()
        
        # Create prompt template for weather analysis
        self.analysis_prompt = PromptTemplate(
            input_variables=["weather_data", "crop_type", "growth_stage"],
            template="""
            Analyze the following weather data for agricultural implications:
            
            Weather Data: {weather_data}
            Crop Type: {crop_type}
            Growth Stage: {growth_stage}
            
            Provide analysis on:
            1. Impact on crop growth and development
            2. Irrigation requirements
            3. Disease and pest risk assessment
            4. Recommended actions for the farmer
            5. Weather-related alerts or warnings
            
            Analysis:
            """
        )
        
        if self.llm:
            self.analysis_chain = LLMChain(
                llm=self.llm,
                prompt=self.analysis_prompt
            )
    
    async def analyze_weather_for_crop(
        self, 
        latitude: float, 
        longitude: float, 
        crop_type: str, 
        growth_stage: str
    ) -> Dict[str, Any]:
        """Analyze weather data for specific crop and growth stage"""
        try:
            # Get current weather data
            weather_data = await self.weather_client.get_agricultural_weather_data(latitude, longitude)
            if not weather_data:
                return {"error": "Unable to retrieve weather data"}
            
            # Prepare weather summary for analysis
            weather_summary = f"""
            Temperature: {weather_data.temperature}°C (feels like {weather_data.feels_like or 'N/A'}°C)
            Humidity: {weather_data.humidity}%
            Wind: {weather_data.wind_speed} km/h
            Rainfall: {weather_data.rainfall} mm
            Condition: {weather_data.condition.value}
            Pressure: {weather_data.pressure or 'N/A'} hPa
            """
            
            analysis_result = {
                "weather_data": weather_data,
                "location": {"latitude": latitude, "longitude": longitude},
                "crop_analysis": {
                    "crop_type": crop_type,
                    "growth_stage": growth_stage,
                    "temperature_impact": self._analyze_temperature_impact(weather_data.temperature, crop_type),
                    "moisture_status": self._analyze_moisture_status(weather_data.humidity, weather_data.rainfall),
                    "wind_impact": self._analyze_wind_impact(weather_data.wind_speed),
                    "recommendations": self._generate_weather_recommendations(weather_data, crop_type, growth_stage)
                }
            }
            
            # If LLM is available, get detailed analysis
            if self.llm and self.analysis_chain:
                try:
                    llm_analysis = await self.analysis_chain.arun(
                        weather_data=weather_summary,
                        crop_type=crop_type,
                        growth_stage=growth_stage
                    )
                    analysis_result["llm_analysis"] = llm_analysis
                except Exception as e:
                    logger.warning(f"LLM analysis failed: {e}")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error analyzing weather for crop: {e}")
            return {"error": str(e)}
    
    def _analyze_temperature_impact(self, temperature: float, crop_type: str) -> Dict[str, Any]:
        """Analyze temperature impact on crop"""
        # Simplified temperature analysis - would be more sophisticated in production
        optimal_ranges = {
            "rice": {"min": 20, "max": 35},
            "wheat": {"min": 15, "max": 25},
            "cotton": {"min": 21, "max": 30},
            "sugarcane": {"min": 20, "max": 30},
            "maize": {"min": 18, "max": 27}
        }
        
        crop_range = optimal_ranges.get(crop_type.lower(), {"min": 15, "max": 35})
        
        if temperature < crop_range["min"]:
            status = "too_cold"
            impact = "Growth may be slowed due to low temperature"
        elif temperature > crop_range["max"]:
            status = "too_hot"
            impact = "Heat stress possible, increased water requirement"
        else:
            status = "optimal"
            impact = "Temperature is within optimal range for growth"
        
        return {
            "status": status,
            "impact": impact,
            "optimal_range": crop_range,
            "current_temperature": temperature
        }
    
    def _analyze_moisture_status(self, humidity: float, rainfall: float) -> Dict[str, Any]:
        """Analyze moisture conditions"""
        if humidity < 40:
            moisture_status = "low"
            recommendation = "Consider irrigation, monitor for drought stress"
        elif humidity > 80:
            moisture_status = "high"
            recommendation = "Monitor for fungal diseases, ensure good drainage"
        else:
            moisture_status = "moderate"
            recommendation = "Moisture levels are adequate"
        
        if rainfall > 10:
            rainfall_status = "heavy"
        elif rainfall > 2:
            rainfall_status = "moderate"
        else:
            rainfall_status = "light"
        
        return {
            "humidity_status": moisture_status,
            "rainfall_status": rainfall_status,
            "recommendation": recommendation,
            "values": {"humidity": humidity, "rainfall": rainfall}
        }
    
    def _analyze_wind_impact(self, wind_speed: float) -> Dict[str, Any]:
        """Analyze wind impact"""
        if wind_speed > 40:
            status = "high"
            impact = "Strong winds may cause lodging or physical damage"
        elif wind_speed > 20:
            status = "moderate"
            impact = "Moderate winds, good for air circulation"
        else:
            status = "low"
            impact = "Calm conditions, monitor for stagnant air issues"
        
        return {
            "status": status,
            "impact": impact,
            "wind_speed": wind_speed
        }
    
    def _generate_weather_recommendations(self, weather_data: WeatherData, crop_type: str, growth_stage: str) -> List[str]:
        """Generate weather-based recommendations"""
        recommendations = []
        
        # Temperature-based recommendations
        if weather_data.temperature > 35:
            recommendations.append("Provide shade or increase irrigation frequency due to high temperature")
        elif weather_data.temperature < 10:
            recommendations.append("Protect crops from cold stress, consider covering if possible")
        
        # Humidity-based recommendations
        if weather_data.humidity > 85:
            recommendations.append("Monitor for fungal diseases due to high humidity")
            recommendations.append("Ensure good air circulation around plants")
        elif weather_data.humidity < 30:
            recommendations.append("Increase irrigation frequency due to low humidity")
        
        # Rainfall-based recommendations
        if weather_data.rainfall > 20:
            recommendations.append("Ensure proper drainage to prevent waterlogging")
            recommendations.append("Delay fertilizer application until conditions improve")
        elif weather_data.rainfall == 0 and weather_data.humidity < 50:
            recommendations.append("Consider irrigation as no rainfall and low humidity detected")
        
        # Wind-based recommendations
        if weather_data.wind_speed > 30:
            recommendations.append("Provide windbreaks or support for tall crops")
        
        # Weather condition-based recommendations
        if weather_data.condition in [WeatherCondition.THUNDERSTORM, WeatherCondition.HEAVY_RAIN]:
            recommendations.append("Avoid field operations during severe weather")
        
        return recommendations if recommendations else ["Weather conditions are favorable for normal farming operations"]