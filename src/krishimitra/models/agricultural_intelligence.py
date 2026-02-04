"""
Agricultural intelligence models for KrishiMitra platform.

This module contains models for weather data, soil information, market data,
satellite imagery analysis, and sensor readings.
"""

from datetime import datetime, date
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from decimal import Decimal

from pydantic import Field, field_validator

from .base import BaseModel, TimestampedModel, GeographicCoordinate, MonetaryAmount, Measurement


class WeatherCondition(str, Enum):
    """Weather conditions."""
    CLEAR = "clear"
    PARTLY_CLOUDY = "partly_cloudy"
    CLOUDY = "cloudy"
    OVERCAST = "overcast"
    LIGHT_RAIN = "light_rain"
    MODERATE_RAIN = "moderate_rain"
    HEAVY_RAIN = "heavy_rain"
    THUNDERSTORM = "thunderstorm"
    FOG = "fog"
    HAZE = "haze"
    DUST_STORM = "dust_storm"
    CYCLONE = "cyclone"


class AlertLevel(str, Enum):
    """Alert levels for weather and other warnings."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"
    EXTREME = "extreme"


class WeatherData(TimestampedModel):
    """Weather data model."""
    
    location: GeographicCoordinate = Field(description="Location coordinates")
    timestamp: datetime = Field(description="Weather data timestamp")
    
    # Current conditions
    temperature: float = Field(description="Temperature in Celsius")
    feels_like: Optional[float] = Field(default=None, description="Feels like temperature in Celsius")
    humidity: float = Field(ge=0, le=100, description="Relative humidity percentage")
    pressure: Optional[float] = Field(default=None, description="Atmospheric pressure in hPa")
    visibility: Optional[float] = Field(default=None, description="Visibility in kilometers")
    uv_index: Optional[float] = Field(default=None, ge=0, le=15, description="UV index")
    
    # Wind information
    wind_speed: float = Field(ge=0, description="Wind speed in km/h")
    wind_direction: Optional[float] = Field(default=None, ge=0, le=360, description="Wind direction in degrees")
    wind_gust: Optional[float] = Field(default=None, ge=0, description="Wind gust speed in km/h")
    
    # Precipitation
    rainfall: float = Field(ge=0, description="Rainfall in mm")
    rainfall_probability: Optional[float] = Field(default=None, ge=0, le=100, description="Probability of rainfall")
    
    # Conditions
    condition: WeatherCondition = Field(description="Weather condition")
    cloud_cover: Optional[float] = Field(default=None, ge=0, le=100, description="Cloud cover percentage")
    
    # Forecast data (if applicable)
    is_forecast: bool = Field(default=False, description="Whether this is forecast data")
    forecast_hours: Optional[int] = Field(default=None, description="Hours ahead for forecast")
    
    # Agricultural relevance
    heat_index: Optional[float] = Field(default=None, description="Heat index in Celsius")
    dew_point: Optional[float] = Field(default=None, description="Dew point in Celsius")
    evapotranspiration: Optional[float] = Field(default=None, description="Reference evapotranspiration in mm")
    
    # Alerts and warnings
    weather_alerts: List[str] = Field(default_factory=list, description="Weather alerts and warnings")
    alert_level: Optional[AlertLevel] = Field(default=None, description="Alert level")


class SoilNutrients(BaseModel):
    """Soil nutrient information."""
    
    nitrogen: Optional[float] = Field(default=None, ge=0, description="Nitrogen content in kg/ha")
    phosphorus: Optional[float] = Field(default=None, ge=0, description="Phosphorus content in kg/ha")
    potassium: Optional[float] = Field(default=None, ge=0, description="Potassium content in kg/ha")
    organic_carbon: Optional[float] = Field(default=None, ge=0, le=100, description="Organic carbon percentage")
    sulfur: Optional[float] = Field(default=None, ge=0, description="Sulfur content in ppm")
    zinc: Optional[float] = Field(default=None, ge=0, description="Zinc content in ppm")
    iron: Optional[float] = Field(default=None, ge=0, description="Iron content in ppm")
    manganese: Optional[float] = Field(default=None, ge=0, description="Manganese content in ppm")
    copper: Optional[float] = Field(default=None, ge=0, description="Copper content in ppm")
    boron: Optional[float] = Field(default=None, ge=0, description="Boron content in ppm")


class SoilData(TimestampedModel):
    """Soil data model."""
    
    location: GeographicCoordinate = Field(description="Location coordinates")
    sample_depth: Measurement = Field(description="Soil sample depth")
    
    # Physical properties
    ph: Optional[float] = Field(default=None, ge=0, le=14, description="Soil pH")
    electrical_conductivity: Optional[float] = Field(default=None, ge=0, description="Electrical conductivity in dS/m")
    moisture_content: Optional[float] = Field(default=None, ge=0, le=100, description="Moisture content percentage")
    temperature: Optional[float] = Field(default=None, description="Soil temperature in Celsius")
    bulk_density: Optional[float] = Field(default=None, ge=0, description="Bulk density in g/cm³")
    porosity: Optional[float] = Field(default=None, ge=0, le=100, description="Porosity percentage")
    
    # Texture
    sand_percentage: Optional[float] = Field(default=None, ge=0, le=100, description="Sand percentage")
    silt_percentage: Optional[float] = Field(default=None, ge=0, le=100, description="Silt percentage")
    clay_percentage: Optional[float] = Field(default=None, ge=0, le=100, description="Clay percentage")
    texture_class: Optional[str] = Field(default=None, description="Soil texture class")
    
    # Chemical properties
    nutrients: Optional[SoilNutrients] = Field(default=None, description="Soil nutrients")
    cation_exchange_capacity: Optional[float] = Field(default=None, ge=0, description="CEC in cmol/kg")
    base_saturation: Optional[float] = Field(default=None, ge=0, le=100, description="Base saturation percentage")
    
    # Health indicators
    soil_health_index: Optional[float] = Field(default=None, ge=0, le=100, description="Overall soil health index")
    erosion_risk: Optional[str] = Field(default=None, description="Erosion risk level")
    compaction_level: Optional[str] = Field(default=None, description="Soil compaction level")
    
    # Recommendations
    lime_requirement: Optional[Measurement] = Field(default=None, description="Lime requirement")
    fertilizer_recommendations: Optional[Dict[str, Measurement]] = Field(default=None, description="Fertilizer recommendations")
    
    @field_validator('sand_percentage', 'silt_percentage', 'clay_percentage')
    @classmethod
    def validate_texture_percentages(cls, v, info):
        """Validate that texture percentages sum to 100."""
        if v is not None:
            total = 0
            field_name = info.field_name
            for texture_field in ['sand_percentage', 'silt_percentage', 'clay_percentage']:
                if texture_field in info.data and info.data[texture_field] is not None:
                    total += info.data[texture_field]
                elif texture_field == field_name:
                    total += v
            
            if total > 100:
                raise ValueError('Total texture percentages cannot exceed 100%')
        return v


class MarketPrice(BaseModel):
    """Market price information for a commodity."""
    
    commodity: str = Field(description="Commodity name")
    variety: Optional[str] = Field(default=None, description="Commodity variety")
    unit: str = Field(description="Price unit (per kg, per quintal, etc.)")
    min_price: MonetaryAmount = Field(description="Minimum price")
    max_price: MonetaryAmount = Field(description="Maximum price")
    modal_price: MonetaryAmount = Field(description="Modal/average price")
    price_date: date = Field(description="Price date")
    market_name: str = Field(description="Market/mandi name")
    market_location: str = Field(description="Market location")
    arrivals: Optional[Measurement] = Field(default=None, description="Commodity arrivals")
    
    @field_validator('max_price')
    @classmethod
    def validate_price_range(cls, v, info):
        if 'min_price' in info.data and v.amount < info.data['min_price'].amount:
            raise ValueError('Maximum price cannot be less than minimum price')
        return v


class MarketData(TimestampedModel):
    """Market data model."""
    
    location: GeographicCoordinate = Field(description="Market location")
    market_name: str = Field(description="Market name")
    market_type: str = Field(description="Market type (mandi, wholesale, retail)")
    
    # Price information
    prices: List[MarketPrice] = Field(description="Commodity prices")
    
    # Market conditions
    market_condition: Optional[str] = Field(default=None, description="Overall market condition")
    demand_level: Optional[str] = Field(default=None, description="Demand level")
    supply_level: Optional[str] = Field(default=None, description="Supply level")
    
    # Trends
    price_trend: Optional[str] = Field(default=None, description="Price trend (increasing, decreasing, stable)")
    seasonal_factor: Optional[float] = Field(default=None, description="Seasonal price factor")
    
    # Transportation
    transportation_cost: Optional[MonetaryAmount] = Field(default=None, description="Transportation cost per unit")
    distance_from_farm: Optional[Measurement] = Field(default=None, description="Distance from farm")


class VegetationIndex(BaseModel):
    """Vegetation indices from satellite imagery."""
    
    ndvi: Optional[float] = Field(default=None, ge=-1, le=1, description="Normalized Difference Vegetation Index")
    evi: Optional[float] = Field(default=None, description="Enhanced Vegetation Index")
    savi: Optional[float] = Field(default=None, description="Soil Adjusted Vegetation Index")
    ndwi: Optional[float] = Field(default=None, ge=-1, le=1, description="Normalized Difference Water Index")
    lai: Optional[float] = Field(default=None, ge=0, description="Leaf Area Index")


class CropHealthAnalysis(BaseModel):
    """Crop health analysis from satellite/drone imagery."""
    
    overall_health_score: float = Field(ge=0, le=100, description="Overall crop health score")
    vegetation_indices: VegetationIndex = Field(description="Vegetation indices")
    
    # Growth stage
    growth_stage: Optional[str] = Field(default=None, description="Crop growth stage")
    maturity_percentage: Optional[float] = Field(default=None, ge=0, le=100, description="Crop maturity percentage")
    
    # Health indicators
    stress_indicators: List[str] = Field(default_factory=list, description="Crop stress indicators")
    disease_probability: Optional[float] = Field(default=None, ge=0, le=100, description="Disease probability")
    pest_probability: Optional[float] = Field(default=None, ge=0, le=100, description="Pest probability")
    nutrient_deficiency: List[str] = Field(default_factory=list, description="Nutrient deficiency indicators")
    
    # Yield prediction
    yield_prediction: Optional[Measurement] = Field(default=None, description="Predicted yield")
    yield_confidence: Optional[float] = Field(default=None, ge=0, le=100, description="Yield prediction confidence")
    
    # Recommendations
    immediate_actions: List[str] = Field(default_factory=list, description="Immediate action recommendations")
    long_term_recommendations: List[str] = Field(default_factory=list, description="Long-term recommendations")


class SatelliteData(TimestampedModel):
    """Satellite imagery data and analysis."""
    
    location: GeographicCoordinate = Field(description="Location coordinates")
    field_boundary: List[GeographicCoordinate] = Field(description="Field boundary coordinates")
    
    # Image metadata
    satellite_name: str = Field(description="Satellite name")
    image_date: datetime = Field(description="Image capture date")
    cloud_cover: float = Field(ge=0, le=100, description="Cloud cover percentage")
    resolution: Measurement = Field(description="Image resolution")
    
    # Analysis results
    crop_analysis: Optional[CropHealthAnalysis] = Field(default=None, description="Crop health analysis")
    land_use_classification: Optional[Dict[str, float]] = Field(default=None, description="Land use classification")
    
    # Change detection
    change_detection: Optional[Dict[str, Any]] = Field(default=None, description="Change detection results")
    historical_comparison: Optional[Dict[str, Any]] = Field(default=None, description="Historical comparison data")


class SensorType(str, Enum):
    """IoT sensor types."""
    SOIL_MOISTURE = "soil_moisture"
    SOIL_TEMPERATURE = "soil_temperature"
    SOIL_PH = "soil_ph"
    AIR_TEMPERATURE = "air_temperature"
    AIR_HUMIDITY = "air_humidity"
    LIGHT_INTENSITY = "light_intensity"
    RAINFALL = "rainfall"
    WIND_SPEED = "wind_speed"
    LEAF_WETNESS = "leaf_wetness"
    CO2_LEVEL = "co2_level"


class SensorReading(TimestampedModel):
    """IoT sensor reading model."""
    
    device_id: str = Field(description="Sensor device ID")
    sensor_type: SensorType = Field(description="Type of sensor")
    location: GeographicCoordinate = Field(description="Sensor location")
    
    # Reading data
    value: float = Field(description="Sensor reading value")
    unit: str = Field(description="Unit of measurement")
    quality: Optional[float] = Field(default=None, ge=0, le=100, description="Reading quality score")
    
    # Device information
    battery_level: Optional[float] = Field(default=None, ge=0, le=100, description="Device battery level")
    signal_strength: Optional[float] = Field(default=None, description="Signal strength")
    
    # Calibration
    calibration_date: Optional[datetime] = Field(default=None, description="Last calibration date")
    is_calibrated: bool = Field(default=True, description="Whether the sensor is calibrated")
    
    # Alerts
    is_anomaly: bool = Field(default=False, description="Whether this reading is anomalous")
    alert_level: Optional[AlertLevel] = Field(default=None, description="Alert level if applicable")


class AgriculturalIntelligence(TimestampedModel):
    """Comprehensive agricultural intelligence data."""
    
    farmer_id: str = Field(description="Associated farmer ID")
    location: GeographicCoordinate = Field(description="Location coordinates")
    
    # Data sources
    weather_data: Optional[WeatherData] = Field(default=None, description="Weather information")
    soil_data: Optional[SoilData] = Field(default=None, description="Soil information")
    market_data: List[MarketData] = Field(default_factory=list, description="Market information")
    satellite_data: Optional[SatelliteData] = Field(default=None, description="Satellite imagery analysis")
    sensor_readings: List[SensorReading] = Field(default_factory=list, description="IoT sensor readings")
    
    # Derived insights
    crop_health_score: Optional[float] = Field(default=None, ge=0, le=100, description="Overall crop health score")
    risk_assessment: Dict[str, str] = Field(default_factory=dict, description="Risk assessment by category")
    opportunity_score: Optional[float] = Field(default=None, ge=0, le=100, description="Opportunity score")
    
    # Recommendations
    immediate_actions: List[str] = Field(default_factory=list, description="Immediate action recommendations")
    weekly_tasks: List[str] = Field(default_factory=list, description="Weekly task recommendations")
    seasonal_planning: List[str] = Field(default_factory=list, description="Seasonal planning recommendations")
    
    # Confidence and reliability
    data_completeness: float = Field(ge=0, le=100, description="Data completeness percentage")
    confidence_score: float = Field(ge=0, le=100, description="Overall confidence in the intelligence")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    # Alerts and notifications
    active_alerts: List[str] = Field(default_factory=list, description="Active alerts")
    alert_level: Optional[AlertLevel] = Field(default=None, description="Highest alert level")