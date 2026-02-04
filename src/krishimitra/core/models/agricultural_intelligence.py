"""
Agricultural intelligence data models using Pydantic.

This module defines models for weather data, soil data, market data, and satellite imagery
information used in agricultural decision making.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any, Union
from enum import Enum

from pydantic import BaseModel, Field, validator, ConfigDict
from pydantic.types import confloat, conint, constr


class WeatherCondition(str, Enum):
    """Weather condition types."""
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAINY = "rainy"
    STORMY = "stormy"
    FOGGY = "foggy"
    WINDY = "windy"


class CropHealthStatus(str, Enum):
    """Crop health status from satellite analysis."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class GrowthStage(str, Enum):
    """Crop growth stages."""
    GERMINATION = "germination"
    VEGETATIVE = "vegetative"
    FLOWERING = "flowering"
    FRUITING = "fruiting"
    MATURITY = "maturity"
    HARVEST_READY = "harvest_ready"


class Location(BaseModel):
    """Geographic location with radius for data coverage."""
    model_config = ConfigDict(validate_assignment=True)
    
    latitude: confloat(ge=-90, le=90) = Field(..., description="Latitude coordinate")
    longitude: confloat(ge=-180, le=180) = Field(..., description="Longitude coordinate")
    radius: confloat(gt=0, le=100) = Field(5.0, description="Coverage radius in kilometers")


class WeatherForecast(BaseModel):
    """Individual weather forecast entry."""
    model_config = ConfigDict(validate_assignment=True)
    
    date: datetime = Field(..., description="Forecast date")
    temperature_min: confloat(ge=-50, le=60) = Field(..., description="Minimum temperature in Celsius")
    temperature_max: confloat(ge=-50, le=60) = Field(..., description="Maximum temperature in Celsius")
    humidity: confloat(ge=0, le=100) = Field(..., description="Humidity percentage")
    rainfall: confloat(ge=0, le=1000) = Field(..., description="Expected rainfall in mm")
    wind_speed: confloat(ge=0, le=200) = Field(..., description="Wind speed in km/h")
    condition: WeatherCondition = Field(..., description="Weather condition")
    
    @validator('temperature_max')
    def validate_temperature_range(cls, v, values):
        """Ensure max temperature is greater than min temperature."""
        if 'temperature_min' in values and v <= values['temperature_min']:
            raise ValueError("Maximum temperature must be greater than minimum temperature")
        return v


class WeatherData(BaseModel):
    """Current weather data and forecasts."""
    model_config = ConfigDict(validate_assignment=True, use_enum_values=True)
    
    temperature: confloat(ge=-50, le=60) = Field(..., description="Current temperature in Celsius")
    humidity: confloat(ge=0, le=100) = Field(..., description="Current humidity percentage")
    rainfall: confloat(ge=0, le=1000) = Field(..., description="Recent rainfall in mm")
    wind_speed: confloat(ge=0, le=200) = Field(..., description="Current wind speed in km/h")
    condition: WeatherCondition = Field(..., description="Current weather condition")
    forecast: List[WeatherForecast] = Field(default_factory=list, description="Weather forecast")
    uv_index: Optional[confloat(ge=0, le=15)] = Field(None, description="UV index")
    pressure: Optional[confloat(ge=800, le=1200)] = Field(None, description="Atmospheric pressure in hPa")


class NutrientLevels(BaseModel):
    """Soil nutrient levels."""
    model_config = ConfigDict(validate_assignment=True)
    
    nitrogen: confloat(ge=0, le=1000) = Field(..., description="Nitrogen content in ppm")
    phosphorus: confloat(ge=0, le=1000) = Field(..., description="Phosphorus content in ppm")
    potassium: confloat(ge=0, le=1000) = Field(..., description="Potassium content in ppm")
    organic_matter: Optional[confloat(ge=0, le=100)] = Field(None, description="Organic matter percentage")
    sulfur: Optional[confloat(ge=0, le=100)] = Field(None, description="Sulfur content in ppm")
    calcium: Optional[confloat(ge=0, le=1000)] = Field(None, description="Calcium content in ppm")
    magnesium: Optional[confloat(ge=0, le=1000)] = Field(None, description="Magnesium content in ppm")


class SoilData(BaseModel):
    """Soil condition and health data."""
    model_config = ConfigDict(validate_assignment=True)
    
    moisture: confloat(ge=0, le=100) = Field(..., description="Soil moisture percentage")
    ph: confloat(ge=0, le=14) = Field(..., description="Soil pH level")
    nutrients: NutrientLevels = Field(..., description="Nutrient levels")
    temperature: Optional[confloat(ge=-10, le=60)] = Field(None, description="Soil temperature in Celsius")
    salinity: Optional[confloat(ge=0, le=50)] = Field(None, description="Soil salinity in dS/m")
    compaction: Optional[confloat(ge=0, le=100)] = Field(None, description="Soil compaction percentage")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last measurement time")


class MarketPrice(BaseModel):
    """Market price information for a specific crop."""
    model_config = ConfigDict(validate_assignment=True)
    
    crop_name: constr(min_length=1, max_length=50) = Field(..., description="Name of the crop")
    variety: Optional[constr(max_length=50)] = Field(None, description="Crop variety")
    price_per_quintal: confloat(gt=0, le=100000) = Field(..., description="Price per quintal in INR")
    market_name: constr(min_length=1, max_length=100) = Field(..., description="Market/mandi name")
    distance_km: confloat(ge=0, le=1000) = Field(..., description="Distance from farmer in km")
    quality_grade: Optional[constr(max_length=20)] = Field(None, description="Quality grade")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Price update time")


class DemandTrend(BaseModel):
    """Demand trend information."""
    model_config = ConfigDict(validate_assignment=True)
    
    crop_name: constr(min_length=1, max_length=50) = Field(..., description="Name of the crop")
    current_demand: constr(regex=r'^(low|medium|high)$') = Field(..., description="Current demand level")
    trend_direction: constr(regex=r'^(increasing|stable|decreasing)$') = Field(..., description="Trend direction")
    seasonal_factor: confloat(ge=0, le=5) = Field(1.0, description="Seasonal demand multiplier")
    forecast_period_days: conint(ge=1, le=365) = Field(30, description="Forecast period in days")


class MarketData(BaseModel):
    """Market intelligence and pricing data."""
    model_config = ConfigDict(validate_assignment=True)
    
    prices: List[MarketPrice] = Field(default_factory=list, description="Current market prices")
    demand: Dict[str, DemandTrend] = Field(default_factory=dict, description="Demand trends by crop")
    trends: List[Dict[str, Any]] = Field(default_factory=list, description="Historical price trends")
    transportation_costs: Dict[str, float] = Field(default_factory=dict, description="Transport costs to markets")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Data update time")


class SatelliteData(BaseModel):
    """Satellite imagery analysis data."""
    model_config = ConfigDict(validate_assignment=True, use_enum_values=True)
    
    ndvi: confloat(ge=-1, le=1) = Field(..., description="Normalized Difference Vegetation Index")
    crop_health: CropHealthStatus = Field(..., description="Overall crop health assessment")
    growth_stage: GrowthStage = Field(..., description="Current growth stage")
    field_area_hectares: confloat(gt=0, le=10000) = Field(..., description="Field area in hectares")
    vegetation_coverage: confloat(ge=0, le=100) = Field(..., description="Vegetation coverage percentage")
    water_stress_index: Optional[confloat(ge=0, le=1)] = Field(None, description="Water stress indicator")
    pest_risk_areas: List[Dict[str, Any]] = Field(default_factory=list, description="Areas with pest risk")
    image_date: datetime = Field(..., description="Satellite image capture date")
    resolution_meters: confloat(gt=0, le=100) = Field(10.0, description="Image resolution in meters")


class AgriculturalIntelligence(BaseModel):
    """Complete agricultural intelligence data package."""
    model_config = ConfigDict(
        validate_assignment=True,
        use_enum_values=True
    )
    
    data_id: constr(min_length=1, max_length=50) = Field(..., description="Unique data identifier")
    location: Location = Field(..., description="Geographic location and coverage")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Data collection timestamp")
    weather_data: WeatherData = Field(..., description="Weather information")
    soil_data: SoilData = Field(..., description="Soil conditions")
    market_data: MarketData = Field(..., description="Market intelligence")
    satellite_data: Optional[SatelliteData] = Field(None, description="Satellite imagery analysis")
    data_quality_score: confloat(ge=0, le=1) = Field(1.0, description="Overall data quality score")
    source_systems: List[str] = Field(default_factory=list, description="Data source systems")
    
    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = self.model_dump()
        
        # Convert datetime objects to ISO strings
        item['timestamp'] = self.timestamp.isoformat()
        if self.soil_data.last_updated:
            item['soil_data']['last_updated'] = self.soil_data.last_updated.isoformat()
        if self.market_data.last_updated:
            item['market_data']['last_updated'] = self.market_data.last_updated.isoformat()
        if self.satellite_data and self.satellite_data.image_date:
            item['satellite_data']['image_date'] = self.satellite_data.image_date.isoformat()
        
        # Convert forecast dates
        for forecast in item['weather_data']['forecast']:
            forecast['date'] = forecast['date'].isoformat() if isinstance(forecast['date'], datetime) else forecast['date']
        
        # Convert market price dates
        for price in item['market_data']['prices']:
            price['last_updated'] = price['last_updated'].isoformat() if isinstance(price['last_updated'], datetime) else price['last_updated']
        
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
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> 'AgriculturalIntelligence':
        """Create instance from DynamoDB item."""
        # Convert ISO strings back to datetime objects
        if 'timestamp' in item and isinstance(item['timestamp'], str):
            item['timestamp'] = datetime.fromisoformat(item['timestamp'])
        
        # Convert nested datetime fields
        if 'soil_data' in item and 'last_updated' in item['soil_data']:
            if isinstance(item['soil_data']['last_updated'], str):
                item['soil_data']['last_updated'] = datetime.fromisoformat(item['soil_data']['last_updated'])
        
        if 'market_data' in item and 'last_updated' in item['market_data']:
            if isinstance(item['market_data']['last_updated'], str):
                item['market_data']['last_updated'] = datetime.fromisoformat(item['market_data']['last_updated'])
        
        if 'satellite_data' in item and item['satellite_data'] and 'image_date' in item['satellite_data']:
            if isinstance(item['satellite_data']['image_date'], str):
                item['satellite_data']['image_date'] = datetime.fromisoformat(item['satellite_data']['image_date'])
        
        # Convert forecast dates
        if 'weather_data' in item and 'forecast' in item['weather_data']:
            for forecast in item['weather_data']['forecast']:
                if isinstance(forecast.get('date'), str):
                    forecast['date'] = datetime.fromisoformat(forecast['date'])
        
        # Convert market price dates
        if 'market_data' in item and 'prices' in item['market_data']:
            for price in item['market_data']['prices']:
                if isinstance(price.get('last_updated'), str):
                    price['last_updated'] = datetime.fromisoformat(price['last_updated'])
        
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