"""
Market Data Integration Agent for KrishiMitra Platform

This module implements market data collection from AGMARKNET and other market sources,
providing real-time price information and market intelligence for farmers.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
import asyncio
import math

import httpx
import redis
import numpy as np
import pandas as pd
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from pydantic import BaseModel, Field, validator
from langchain.tools import BaseTool
from pydantic import BaseModel as LangChainBaseModel

from ..core.config import get_settings
from ..models.agricultural_intelligence import MarketData, MarketPrice, GeographicCoordinate, MonetaryAmount, Measurement
from .market_forecasting import PriceForecastingEngine

logger = logging.getLogger(__name__)
settings = get_settings()


class AGMARKNETPrice(BaseModel):
    """Model for AGMARKNET price data"""
    commodity: str = Field(..., description="Commodity name")
    variety: Optional[str] = Field(None, description="Commodity variety")
    market: str = Field(..., description="Market name")
    district: str = Field(..., description="District name")
    state: str = Field(..., description="State name")
    min_price: float = Field(..., description="Minimum price per quintal")
    max_price: float = Field(..., description="Maximum price per quintal")
    modal_price: float = Field(..., description="Modal price per quintal")
    arrivals: Optional[float] = Field(None, description="Arrivals in quintals")
    price_date: str = Field(..., description="Price date in YYYY-MM-DD format")
    
    @validator('min_price', 'max_price', 'modal_price')
    def validate_prices(cls, v):
        if v < 0:
            raise ValueError('Price cannot be negative')
        return v
    
    @validator('max_price')
    def validate_price_range(cls, v, values):
        if 'min_price' in values and v < values['min_price']:
            raise ValueError('Maximum price cannot be less than minimum price')
        return v


class MarketAPIClient:
    """Client for connecting to various market data APIs"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host='localhost',  # In production, use ElastiCache endpoint
            port=6379,
            decode_responses=True
        )
        self.cache_ttl = 3600  # 1 hour cache
        
        # AGMARKNET API configuration
        self.agmarknet_base_url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
        self.agmarknet_api_key = settings.market_api_key or "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"
        
        # HTTP client configuration
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
        
        # Geocoder for location services
        self.geocoder = Nominatim(user_agent="krishimitra_market_agent")
        
        # Price validation thresholds
        self.price_anomaly_threshold = 2.5  # Standard deviations for anomaly detection
        self.max_price_change_percent = 50  # Maximum acceptable price change percentage
    
    def validate_price_data(self, price: AGMARKNETPrice, historical_prices: List[AGMARKNETPrice]) -> Tuple[bool, Optional[str]]:
        """
        Validate price data and detect anomalies
        
        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        try:
            # Basic validation
            if price.min_price <= 0 or price.max_price <= 0 or price.modal_price <= 0:
                return False, "Price values must be positive"
            
            if price.max_price < price.min_price:
                return False, "Maximum price cannot be less than minimum price"
            
            if price.modal_price < price.min_price or price.modal_price > price.max_price:
                return False, "Modal price must be between min and max prices"
            
            # Anomaly detection using historical data
            if historical_prices and len(historical_prices) >= 5:
                historical_modal_prices = [p.modal_price for p in historical_prices]
                mean_price = np.mean(historical_modal_prices)
                std_price = np.std(historical_modal_prices)
                
                if std_price > 0:
                    z_score = abs((price.modal_price - mean_price) / std_price)
                    if z_score > self.price_anomaly_threshold:
                        return False, f"Price anomaly detected: {z_score:.2f} standard deviations from mean"
                
                # Check for extreme price changes
                if historical_prices:
                    latest_historical = historical_prices[-1]
                    price_change_percent = abs((price.modal_price - latest_historical.modal_price) / latest_historical.modal_price * 100)
                    
                    if price_change_percent > self.max_price_change_percent:
                        return False, f"Extreme price change detected: {price_change_percent:.1f}%"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error validating price data: {e}")
            return False, f"Validation error: {str(e)}"
    
    def calculate_distance(self, loc1: GeographicCoordinate, loc2: GeographicCoordinate) -> float:
        """Calculate distance between two coordinates in kilometers"""
        try:
            return geodesic(
                (loc1.latitude, loc1.longitude),
                (loc2.latitude, loc2.longitude)
            ).kilometers
        except Exception as e:
            logger.error(f"Error calculating distance: {e}")
            return float('inf')
    
    async def get_location_coordinates(self, location_name: str) -> Optional[GeographicCoordinate]:
        """Get coordinates for a location name using geocoding"""
        try:
            cache_key = f"geocode:{location_name}"
            cached_coords = self.redis_client.get(cache_key)
            
            if cached_coords:
                coords_data = json.loads(cached_coords)
                return GeographicCoordinate(**coords_data)
            
            # Geocode the location
            location = self.geocoder.geocode(f"{location_name}, India")
            
            if location:
                coords = GeographicCoordinate(
                    latitude=location.latitude,
                    longitude=location.longitude
                )
                
                # Cache for 7 days
                self.redis_client.setex(
                    cache_key,
                    7 * 24 * 3600,
                    json.dumps(coords.dict())
                )
                
                return coords
            
            return None
            
        except Exception as e:
            logger.error(f"Error geocoding location {location_name}: {e}")
            return None
    
    async def get_agmarknet_prices(
        self, 
        commodity: str, 
        state: Optional[str] = None,
        district: Optional[str] = None,
        limit: int = 100,
        validate: bool = True
    ) -> List[AGMARKNETPrice]:
        """Fetch commodity prices from AGMARKNET with validation"""
        try:
            # Build cache key
            cache_key = f"agmarknet:{commodity}:{state or 'all'}:{district or 'all'}"
            
            # Check cache first
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                logger.info(f"Retrieved cached AGMARKNET data for {commodity}")
                data = json.loads(cached_data)
                return [AGMARKNETPrice(**item) for item in data]
            
            # Build API parameters
            params = {
                "api-key": self.agmarknet_api_key,
                "format": "json",
                "limit": limit,
                "filters[commodity]": commodity
            }
            
            if state:
                params["filters[state]"] = state
            if district:
                params["filters[district]"] = district
            
            # Make API request
            response = await self.http_client.get(
                self.agmarknet_base_url,
                params=params
            )
            response.raise_for_status()
            
            api_data = response.json()
            
            if not api_data.get("records"):
                logger.warning(f"No AGMARKNET data found for commodity: {commodity}")
                return []
            
            # Get historical data for validation
            historical_prices = []
            if validate:
                historical_cache_key = f"agmarknet_history:{commodity}:{state or 'all'}"
                historical_data = self.redis_client.get(historical_cache_key)
                if historical_data:
                    historical_prices = [AGMARKNETPrice(**item) for item in json.loads(historical_data)]
            
            # Parse and validate data
            prices = []
            invalid_count = 0
            
            for record in api_data["records"]:
                try:
                    price_data = AGMARKNETPrice(
                        commodity=record.get("commodity", ""),
                        variety=record.get("variety"),
                        market=record.get("market", ""),
                        district=record.get("district", ""),
                        state=record.get("state", ""),
                        min_price=float(record.get("min_price", 0)),
                        max_price=float(record.get("max_price", 0)),
                        modal_price=float(record.get("modal_price", 0)),
                        arrivals=float(record.get("arrivals", 0)) if record.get("arrivals") else None,
                        price_date=record.get("price_date", datetime.now().strftime("%Y-%m-%d"))
                    )
                    
                    # Validate price data
                    if validate:
                        is_valid, reason = self.validate_price_data(price_data, historical_prices)
                        if not is_valid:
                            logger.warning(f"Invalid price data for {commodity} at {price_data.market}: {reason}")
                            invalid_count += 1
                            continue
                    
                    prices.append(price_data)
                    
                except Exception as e:
                    logger.warning(f"Error parsing AGMARKNET record: {e}")
                    continue
            
            if invalid_count > 0:
                logger.info(f"Filtered out {invalid_count} invalid price records for {commodity}")
            
            # Cache the results
            cache_data = [price.dict() for price in prices]
            self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(cache_data))
            
            # Update historical data cache
            if validate and prices:
                historical_cache_key = f"agmarknet_history:{commodity}:{state or 'all'}"
                self.redis_client.setex(
                    historical_cache_key,
                    7 * 24 * 3600,  # 7 days
                    json.dumps(cache_data[-30:])  # Keep last 30 records
                )
            
            logger.info(f"Retrieved {len(prices)} validated price records from AGMARKNET for {commodity}")
            return prices
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching AGMARKNET data: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching AGMARKNET data: {e}")
            return []
    
    async def get_nearby_market_prices(
        self,
        location: GeographicCoordinate,
        commodity: str,
        radius_km: float = 100
    ) -> List[MarketData]:
        """Get market prices within specified radius of location with geographic filtering"""
        try:
            # Get all available prices for the commodity
            all_agmarknet_prices = await self.get_agmarknet_prices(
                commodity=commodity,
                limit=500  # Get more records for better geographic coverage
            )
            
            if not all_agmarknet_prices:
                logger.warning(f"No prices found for {commodity}")
                return []
            
            # Calculate distances and filter by radius
            markets_with_distance = []
            
            for price_data in all_agmarknet_prices:
                # Get market coordinates
                market_location_str = f"{price_data.market}, {price_data.district}, {price_data.state}"
                market_coords = await self.get_location_coordinates(market_location_str)
                
                if market_coords:
                    distance = self.calculate_distance(location, market_coords)
                    
                    if distance <= radius_km:
                        markets_with_distance.append({
                            'price_data': price_data,
                            'coordinates': market_coords,
                            'distance': distance
                        })
            
            # Sort by distance
            markets_with_distance.sort(key=lambda x: x['distance'])
            
            # Convert to MarketData format
            market_data_list = []
            for market_info in markets_with_distance[:20]:  # Return top 20 nearest markets
                market_data = self._convert_agmarknet_to_market_data(
                    market_info['price_data'],
                    location,
                    market_info['coordinates'],
                    market_info['distance']
                )
                if market_data:
                    market_data_list.append(market_data)
            
            logger.info(f"Found {len(market_data_list)} markets within {radius_km}km for {commodity}")
            return market_data_list
            
        except Exception as e:
            logger.error(f"Error getting nearby market prices: {e}")
            return []
    
    def _convert_agmarknet_to_market_data(
        self, 
        agmarknet_price: AGMARKNETPrice,
        farmer_location: GeographicCoordinate,
        market_location: Optional[GeographicCoordinate] = None,
        distance_km: Optional[float] = None
    ) -> Optional[MarketData]:
        """Convert AGMARKNET price data to MarketData model with distance information"""
        try:
            # Create market price
            market_price = MarketPrice(
                commodity=agmarknet_price.commodity,
                variety=agmarknet_price.variety,
                unit="per quintal",
                min_price=MonetaryAmount(amount=agmarknet_price.min_price, currency="INR"),
                max_price=MonetaryAmount(amount=agmarknet_price.max_price, currency="INR"),
                modal_price=MonetaryAmount(amount=agmarknet_price.modal_price, currency="INR"),
                price_date=datetime.strptime(agmarknet_price.price_date, "%Y-%m-%d").date(),
                market_name=agmarknet_price.market,
                market_location=f"{agmarknet_price.district}, {agmarknet_price.state}",
                arrivals=Measurement(
                    value=agmarknet_price.arrivals or 0,
                    unit="quintals"
                ) if agmarknet_price.arrivals else None
            )
            
            # Create market data
            market_data = MarketData(
                location=market_location or GeographicCoordinate(latitude=0.0, longitude=0.0),
                market_name=agmarknet_price.market,
                market_type="mandi",
                prices=[market_price],
                market_condition="normal",  # Default value
                demand_level="moderate",   # Default value
                supply_level="moderate",   # Default value
                price_trend="stable",      # Default value
                distance_from_farm=Measurement(
                    value=distance_km or 0,
                    unit="km"
                ) if distance_km is not None else None
            )
            
            return market_data
            
        except Exception as e:
            logger.error(f"Error converting AGMARKNET data: {e}")
            return None
    
    async def get_price_trends(
        self,
        commodity: str,
        market: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get price trends for a commodity over specified days"""
        try:
            cache_key = f"price_trends:{commodity}:{market}:{days}"
            
            # Check cache
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
            
            # Get historical data (simplified - in production use time series data)
            prices = await self.get_agmarknet_prices(commodity=commodity, limit=days)
            
            if not prices:
                return {"trend": "no_data", "prices": []}
            
            # Calculate trend
            price_values = [p.modal_price for p in prices]
            if len(price_values) > 1:
                trend = "increasing" if price_values[-1] > price_values[0] else "decreasing"
                if abs(price_values[-1] - price_values[0]) / price_values[0] < 0.05:
                    trend = "stable"
            else:
                trend = "stable"
            
            trend_data = {
                "trend": trend,
                "current_price": price_values[-1] if price_values else 0,
                "avg_price": sum(price_values) / len(price_values) if price_values else 0,
                "min_price": min(price_values) if price_values else 0,
                "max_price": max(price_values) if price_values else 0,
                "price_change_percent": ((price_values[-1] - price_values[0]) / price_values[0] * 100) if len(price_values) > 1 and price_values[0] > 0 else 0,
                "data_points": len(price_values)
            }
            
            # Cache results
            self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(trend_data))
            
            return trend_data
            
        except Exception as e:
            logger.error(f"Error getting price trends: {e}")
            return {"trend": "error", "prices": []}
    
    async def create_price_alert(
        self,
        farmer_id: str,
        commodity: str,
        target_price: float,
        alert_type: str = "above",  # "above" or "below"
        markets: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a price alert for a farmer
        
        Args:
            farmer_id: Farmer's unique ID
            commodity: Commodity to monitor
            target_price: Price threshold for alert
            alert_type: "above" or "below" threshold
            markets: Optional list of specific markets to monitor
        
        Returns:
            Alert configuration dictionary
        """
        try:
            alert_id = f"alert:{farmer_id}:{commodity}:{datetime.now().timestamp()}"
            
            alert_config = {
                "alert_id": alert_id,
                "farmer_id": farmer_id,
                "commodity": commodity,
                "target_price": target_price,
                "alert_type": alert_type,
                "markets": markets or [],
                "created_at": datetime.now().isoformat(),
                "is_active": True,
                "triggered_count": 0
            }
            
            # Store alert in Redis
            self.redis_client.setex(
                alert_id,
                30 * 24 * 3600,  # 30 days expiry
                json.dumps(alert_config)
            )
            
            # Add to farmer's alert list
            farmer_alerts_key = f"farmer_alerts:{farmer_id}"
            self.redis_client.sadd(farmer_alerts_key, alert_id)
            
            logger.info(f"Created price alert {alert_id} for farmer {farmer_id}")
            return alert_config
            
        except Exception as e:
            logger.error(f"Error creating price alert: {e}")
            return {}
    
    async def check_price_alerts(self, farmer_id: str) -> List[Dict[str, Any]]:
        """
        Check all active price alerts for a farmer
        
        Returns:
            List of triggered alerts with current price information
        """
        try:
            triggered_alerts = []
            
            # Get farmer's alerts
            farmer_alerts_key = f"farmer_alerts:{farmer_id}"
            alert_ids = self.redis_client.smembers(farmer_alerts_key)
            
            for alert_id in alert_ids:
                alert_data = self.redis_client.get(alert_id)
                if not alert_data:
                    continue
                
                alert_config = json.loads(alert_data)
                
                if not alert_config.get("is_active"):
                    continue
                
                # Get current prices
                commodity = alert_config["commodity"]
                target_price = alert_config["target_price"]
                alert_type = alert_config["alert_type"]
                markets = alert_config.get("markets", [])
                
                # Fetch current prices
                if markets:
                    # Check specific markets
                    for market in markets:
                        prices = await self.get_agmarknet_prices(
                            commodity=commodity,
                            limit=10
                        )
                        
                        for price in prices:
                            if price.market in markets:
                                current_price = price.modal_price
                                
                                # Check if alert should trigger
                                should_trigger = False
                                if alert_type == "above" and current_price >= target_price:
                                    should_trigger = True
                                elif alert_type == "below" and current_price <= target_price:
                                    should_trigger = True
                                
                                if should_trigger:
                                    triggered_alerts.append({
                                        "alert_id": alert_id,
                                        "commodity": commodity,
                                        "market": price.market,
                                        "target_price": target_price,
                                        "current_price": current_price,
                                        "alert_type": alert_type,
                                        "price_date": price.price_date,
                                        "message": f"{commodity} price at {price.market} is {alert_type} ₹{target_price}: Current price ₹{current_price}"
                                    })
                                    
                                    # Update triggered count
                                    alert_config["triggered_count"] += 1
                                    self.redis_client.setex(
                                        alert_id,
                                        30 * 24 * 3600,
                                        json.dumps(alert_config)
                                    )
                else:
                    # Check all markets
                    prices = await self.get_agmarknet_prices(
                        commodity=commodity,
                        limit=50
                    )
                    
                    for price in prices:
                        current_price = price.modal_price
                        
                        should_trigger = False
                        if alert_type == "above" and current_price >= target_price:
                            should_trigger = True
                        elif alert_type == "below" and current_price <= target_price:
                            should_trigger = True
                        
                        if should_trigger:
                            triggered_alerts.append({
                                "alert_id": alert_id,
                                "commodity": commodity,
                                "market": price.market,
                                "target_price": target_price,
                                "current_price": current_price,
                                "alert_type": alert_type,
                                "price_date": price.price_date,
                                "message": f"{commodity} price at {price.market} is {alert_type} ₹{target_price}: Current price ₹{current_price}"
                            })
                            
                            # Update triggered count
                            alert_config["triggered_count"] += 1
                            self.redis_client.setex(
                                alert_id,
                                30 * 24 * 3600,
                                json.dumps(alert_config)
                            )
                            break  # Only trigger once per check
            
            logger.info(f"Checked alerts for farmer {farmer_id}: {len(triggered_alerts)} triggered")
            return triggered_alerts
            
        except Exception as e:
            logger.error(f"Error checking price alerts: {e}")
            return []
    
    async def deactivate_price_alert(self, alert_id: str) -> bool:
        """Deactivate a price alert"""
        try:
            alert_data = self.redis_client.get(alert_id)
            if not alert_data:
                return False
            
            alert_config = json.loads(alert_data)
            alert_config["is_active"] = False
            
            self.redis_client.setex(
                alert_id,
                30 * 24 * 3600,
                json.dumps(alert_config)
            )
            
            logger.info(f"Deactivated price alert {alert_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deactivating price alert: {e}")
            return False
    
    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()


class MarketDataTool(BaseTool, LangChainBaseModel):
    """LangChain tool for market data collection"""
    
    name: str = "market_data_collection"
    description: str = "Collect real-time market prices and trends from AGMARKNET and other sources"
    
    def _run(self, commodity: str, location: str = None) -> str:
        """Run the market data collection tool"""
        async def collect_market_data():
            client = MarketAPIClient()
            try:
                # Parse location if provided
                farmer_location = GeographicCoordinate(latitude=0.0, longitude=0.0)
                if location:
                    # In production, parse actual coordinates
                    pass
                
                # Get market prices
                market_data = await client.get_nearby_market_prices(
                    location=farmer_location,
                    commodity=commodity
                )
                
                if not market_data:
                    return f"No market data found for {commodity}"
                
                # Format response
                response = f"Market prices for {commodity}:\n"
                for market in market_data[:3]:  # Show top 3 markets
                    if market.prices:
                        price = market.prices[0]
                        response += f"- {market.market_name}: ₹{price.modal_price.amount}/quintal\n"
                
                return response
                
            finally:
                await client.close()
        
        return asyncio.run(collect_market_data())
    
    async def _arun(self, commodity: str, location: str = None) -> str:
        """Async version of the tool"""
        client = MarketAPIClient()
        try:
            # Parse location if provided
            farmer_location = GeographicCoordinate(latitude=0.0, longitude=0.0)
            if location:
                # In production, parse actual coordinates
                pass
            
            # Get market prices
            market_data = await client.get_nearby_market_prices(
                location=farmer_location,
                commodity=commodity
            )
            
            if not market_data:
                return f"No market data found for {commodity}"
            
            # Format response
            response = f"Market prices for {commodity}:\n"
            for market in market_data[:3]:  # Show top 3 markets
                if market.prices:
                    price = market.prices[0]
                    response += f"- {market.market_name}: ₹{price.modal_price.amount}/quintal\n"
            
            return response
            
        finally:
            await client.close()


class MarketIntelligenceAgent:
    """Market Intelligence Agent for comprehensive market analysis"""
    
    def __init__(self):
        self.market_client = MarketAPIClient()
        self.forecasting_engine = PriceForecastingEngine()
        self.tools = [MarketDataTool()]
    
    async def get_comprehensive_market_data(
        self,
        farmer_location: GeographicCoordinate,
        commodities: List[str],
        radius_km: float = 100
    ) -> Dict[str, List[MarketData]]:
        """Get comprehensive market data for multiple commodities"""
        results = {}
        
        for commodity in commodities:
            try:
                market_data = await self.market_client.get_nearby_market_prices(
                    location=farmer_location,
                    commodity=commodity,
                    radius_km=radius_km
                )
                results[commodity] = market_data
                logger.info(f"Retrieved market data for {commodity}: {len(market_data)} markets")
                
            except Exception as e:
                logger.error(f"Error getting market data for {commodity}: {e}")
                results[commodity] = []
        
        return results
    
    async def analyze_price_trends(
        self,
        commodity: str,
        markets: List[str],
        days: int = 30
    ) -> Dict[str, Any]:
        """Analyze price trends across multiple markets"""
        trend_analysis = {
            "commodity": commodity,
            "analysis_period_days": days,
            "market_trends": {},
            "overall_trend": "stable",
            "price_volatility": "low",
            "recommendations": []
        }
        
        all_trends = []
        
        for market in markets:
            try:
                trend_data = await self.market_client.get_price_trends(
                    commodity=commodity,
                    market=market,
                    days=days
                )
                trend_analysis["market_trends"][market] = trend_data
                
                if trend_data.get("trend") != "no_data":
                    all_trends.append(trend_data)
                    
            except Exception as e:
                logger.error(f"Error analyzing trends for {market}: {e}")
        
        # Calculate overall trend
        if all_trends:
            increasing_count = sum(1 for t in all_trends if t.get("trend") == "increasing")
            decreasing_count = sum(1 for t in all_trends if t.get("trend") == "decreasing")
            
            if increasing_count > decreasing_count:
                trend_analysis["overall_trend"] = "increasing"
            elif decreasing_count > increasing_count:
                trend_analysis["overall_trend"] = "decreasing"
            
            # Calculate volatility
            price_changes = [abs(t.get("price_change_percent", 0)) for t in all_trends]
            avg_volatility = sum(price_changes) / len(price_changes) if price_changes else 0
            
            if avg_volatility > 10:
                trend_analysis["price_volatility"] = "high"
            elif avg_volatility > 5:
                trend_analysis["price_volatility"] = "moderate"
            
            # Generate recommendations
            if trend_analysis["overall_trend"] == "increasing":
                trend_analysis["recommendations"].append("Consider selling soon to capitalize on rising prices")
            elif trend_analysis["overall_trend"] == "decreasing":
                trend_analysis["recommendations"].append("Consider holding inventory if possible, prices may recover")
            
            if trend_analysis["price_volatility"] == "high":
                trend_analysis["recommendations"].append("Monitor prices closely due to high volatility")
        
        return trend_analysis
    
    async def calculate_net_returns(
        self,
        commodity: str,
        quantity: float,
        farmer_location: GeographicCoordinate,
        markets: List[str]
    ) -> List[Dict[str, Any]]:
        """Calculate net returns for different markets considering transportation costs"""
        returns_analysis = []
        
        for market in markets:
            try:
                # Get current prices
                market_data = await self.market_client.get_nearby_market_prices(
                    location=farmer_location,
                    commodity=commodity
                )
                
                # Find matching market
                market_info = None
                for md in market_data:
                    if md.market_name.lower() == market.lower():
                        market_info = md
                        break
                
                if not market_info or not market_info.prices:
                    continue
                
                price = market_info.prices[0]
                
                # Calculate transportation cost (simplified)
                # In production, use actual distance and transportation rates
                base_transport_cost = 50  # ₹50 per quintal base cost
                distance_factor = 1.0  # Placeholder for actual distance calculation
                transport_cost = base_transport_cost * distance_factor
                
                # Calculate net return
                gross_revenue = price.modal_price.amount * quantity
                net_revenue = gross_revenue - (transport_cost * quantity)
                
                returns_analysis.append({
                    "market": market,
                    "price_per_quintal": price.modal_price.amount,
                    "quantity": quantity,
                    "gross_revenue": gross_revenue,
                    "transport_cost_per_quintal": transport_cost,
                    "total_transport_cost": transport_cost * quantity,
                    "net_revenue": net_revenue,
                    "profit_margin": (net_revenue / gross_revenue * 100) if gross_revenue > 0 else 0
                })
                
            except Exception as e:
                logger.error(f"Error calculating returns for {market}: {e}")
        
        # Sort by net revenue
        returns_analysis.sort(key=lambda x: x["net_revenue"], reverse=True)
        
        return returns_analysis
    
    async def calculate_net_returns(
        self,
        commodity: str,
        quantity: float,
        farmer_location: GeographicCoordinate,
        markets: List[str]
    ) -> List[Dict[str, Any]]:
        """Calculate net returns for different markets considering transportation costs"""
        try:
            returns_analysis = []
            
            for market in markets:
                try:
                    # Get current prices
                    market_data = await self.market_client.get_nearby_market_prices(
                        location=farmer_location,
                        commodity=commodity
                    )
                    
                    # Find matching market
                    market_info = None
                    for md in market_data:
                        if md.market_name.lower() == market.lower():
                            market_info = md
                            break
                    
                    if not market_info or not market_info.prices:
                        continue
                    
                    price = market_info.prices[0]
                    
                    # Calculate transportation cost (simplified)
                    # In production, use actual distance and transportation rates
                    base_transport_cost = 50  # ₹50 per quintal base cost
                    distance_factor = 1.0  # Placeholder for actual distance calculation
                    transport_cost = base_transport_cost * distance_factor
                    
                    # Calculate net return
                    gross_revenue = price.modal_price.amount * quantity
                    net_revenue = gross_revenue - (transport_cost * quantity)
                    
                    returns_analysis.append({
                        "market": market,
                        "price_per_quintal": price.modal_price.amount,
                        "quantity": quantity,
                        "gross_revenue": gross_revenue,
                        "transport_cost_per_quintal": transport_cost,
                        "total_transport_cost": transport_cost * quantity,
                        "net_revenue": net_revenue,
                        "profit_margin": (net_revenue / gross_revenue * 100) if gross_revenue > 0 else 0
                    })
                    
                except Exception as e:
                    logger.error(f"Error calculating returns for {market}: {e}")
            
            # Sort by net revenue
            returns_analysis.sort(key=lambda x: x["net_revenue"], reverse=True)
            
            return returns_analysis
            
        except Exception as e:
            logger.error(f"Error in calculate_net_returns: {e}")
            return []
    
    async def get_price_forecast(
        self,
        commodity: str,
        market: str,
        forecast_days: int = 7
    ) -> Dict[str, Any]:
        """Get price forecast for a commodity"""
        try:
            # Get historical prices
            historical_prices = await self.market_client.get_agmarknet_prices(
                commodity=commodity,
                limit=90  # 90 days of history
            )
            
            if not historical_prices:
                return {
                    "status": "no_data",
                    "message": f"No historical data available for {commodity}"
                }
            
            # Convert to format expected by forecasting engine
            price_data = [
                {
                    "date": price.price_date,
                    "price": price.modal_price
                }
                for price in historical_prices
            ]
            
            # Generate forecast
            forecast = self.forecasting_engine.forecast_prices(
                prices=price_data,
                commodity=commodity,
                forecast_days=forecast_days
            )
            
            return forecast
            
        except Exception as e:
            logger.error(f"Error getting price forecast: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def analyze_seasonal_patterns(
        self,
        commodity: str
    ) -> Dict[str, Any]:
        """Analyze seasonal price patterns for a commodity"""
        try:
            # Get multi-year historical data
            historical_prices = await self.market_client.get_agmarknet_prices(
                commodity=commodity,
                limit=1000  # Get as much history as possible
            )
            
            if not historical_prices:
                return {
                    "status": "no_data",
                    "message": f"No historical data available for {commodity}"
                }
            
            # Convert to format expected by forecasting engine
            price_data = [
                {
                    "date": price.price_date,
                    "price": price.modal_price
                }
                for price in historical_prices
            ]
            
            # Analyze seasonal patterns
            pattern_analysis = self.forecasting_engine.recognize_seasonal_patterns(
                commodity=commodity,
                multi_year_prices=price_data
            )
            
            return pattern_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing seasonal patterns: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def predict_demand(
        self,
        commodity: str,
        season: str,
        region: str
    ) -> Dict[str, Any]:
        """Predict demand for a commodity"""
        try:
            # Get historical arrival data
            historical_prices = await self.market_client.get_agmarknet_prices(
                commodity=commodity,
                limit=100
            )
            
            if not historical_prices:
                return {
                    "status": "no_data",
                    "demand_level": "unknown"
                }
            
            # Convert to format expected by forecasting engine
            arrival_data = [
                {
                    "date": price.price_date,
                    "arrivals": price.arrivals or 0
                }
                for price in historical_prices
                if price.arrivals is not None
            ]
            
            # Predict demand
            demand_prediction = self.forecasting_engine.predict_demand(
                commodity=commodity,
                historical_arrivals=arrival_data,
                season=season,
                region=region
            )
            
            return demand_prediction
            
        except Exception as e:
            logger.error(f"Error predicting demand: {e}")
            return {
                "status": "error",
                "message": str(e),
                "demand_level": "unknown"
            }
    
    async def optimize_market_selection(
        self,
        commodity: str,
        quantity_quintals: float,
        farmer_location: GeographicCoordinate
    ) -> List[Dict[str, Any]]:
        """Optimize market selection for maximum net returns"""
        try:
            # Get nearby markets
            market_data = await self.market_client.get_nearby_market_prices(
                location=farmer_location,
                commodity=commodity,
                radius_km=150
            )
            
            if not market_data:
                return []
            
            # Prepare market options
            market_options = []
            for market in market_data:
                if market.prices:
                    price = market.prices[0]
                    distance = market.distance_from_farm.value if market.distance_from_farm else 0
                    
                    market_options.append({
                        "market_name": market.market_name,
                        "price_per_quintal": price.modal_price.amount,
                        "distance_km": distance
                    })
            
            # Optimize using forecasting engine
            optimized_options = self.forecasting_engine.optimize_net_returns(
                commodity=commodity,
                quantity_quintals=quantity_quintals,
                farmer_location=farmer_location,
                market_options=market_options
            )
            
            return optimized_options
            
        except Exception as e:
            logger.error(f"Error optimizing market selection: {e}")
            return []
    
    async def close(self):
        """Close market client"""
        await self.market_client.close()