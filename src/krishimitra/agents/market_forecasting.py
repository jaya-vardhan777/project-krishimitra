"""
Market Price Forecasting and Trend Analysis for KrishiMitra Platform

This module implements price trend analysis, demand prediction, and seasonal pattern
recognition using machine learning and time series analysis.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import redis

from ..core.config import get_settings
from ..models.agricultural_intelligence import GeographicCoordinate, MonetaryAmount

logger = logging.getLogger(__name__)
settings = get_settings()


class PriceForecastingEngine:
    """Engine for price forecasting and trend analysis"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=True
        )
        self.cache_ttl = 3600  # 1 hour cache
        
        # Forecasting parameters
        self.min_data_points = 10  # Minimum data points for forecasting
        self.forecast_horizon_days = 7  # Default forecast horizon
        self.seasonal_period = 30  # Monthly seasonality
    
    def analyze_historical_prices(
        self,
        prices: List[Dict[str, Any]],
        commodity: str
    ) -> Dict[str, Any]:
        """
        Analyze historical price data to identify trends and patterns
        
        Args:
            prices: List of price dictionaries with 'date' and 'price' keys
            commodity: Commodity name
        
        Returns:
            Dictionary with trend analysis results
        """
        try:
            if len(prices) < self.min_data_points:
                return {
                    "status": "insufficient_data",
                    "message": f"Need at least {self.min_data_points} data points for analysis",
                    "data_points": len(prices)
                }
            
            # Convert to DataFrame
            df = pd.DataFrame(prices)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            df.set_index('date', inplace=True)
            
            # Calculate basic statistics
            price_values = df['price'].values
            
            analysis = {
                "commodity": commodity,
                "data_points": len(prices),
                "date_range": {
                    "start": df.index.min().strftime("%Y-%m-%d"),
                    "end": df.index.max().strftime("%Y-%m-%d")
                },
                "statistics": {
                    "mean": float(np.mean(price_values)),
                    "median": float(np.median(price_values)),
                    "std": float(np.std(price_values)),
                    "min": float(np.min(price_values)),
                    "max": float(np.max(price_values)),
                    "range": float(np.max(price_values) - np.min(price_values))
                }
            }
            
            # Calculate trend
            if len(price_values) >= 2:
                # Linear regression for trend
                X = np.arange(len(price_values)).reshape(-1, 1)
                y = price_values
                
                model = LinearRegression()
                model.fit(X, y)
                
                trend_slope = model.coef_[0]
                trend_direction = "increasing" if trend_slope > 0 else "decreasing"
                
                if abs(trend_slope) < 0.01 * np.mean(price_values):
                    trend_direction = "stable"
                
                analysis["trend"] = {
                    "direction": trend_direction,
                    "slope": float(trend_slope),
                    "strength": abs(float(trend_slope)) / np.mean(price_values) * 100
                }
                
                # Calculate price change
                price_change = price_values[-1] - price_values[0]
                price_change_percent = (price_change / price_values[0]) * 100
                
                analysis["price_change"] = {
                    "absolute": float(price_change),
                    "percent": float(price_change_percent),
                    "period_days": (df.index[-1] - df.index[0]).days
                }
            
            # Calculate volatility
            if len(price_values) >= 5:
                returns = np.diff(price_values) / price_values[:-1]
                volatility = np.std(returns) * 100
                
                volatility_level = "low"
                if volatility > 10:
                    volatility_level = "high"
                elif volatility > 5:
                    volatility_level = "moderate"
                
                analysis["volatility"] = {
                    "value": float(volatility),
                    "level": volatility_level
                }
            
            # Detect seasonal patterns if enough data
            if len(price_values) >= self.seasonal_period * 2:
                try:
                    # Resample to daily frequency if needed
                    df_resampled = df.resample('D').mean().interpolate()
                    
                    if len(df_resampled) >= self.seasonal_period * 2:
                        decomposition = seasonal_decompose(
                            df_resampled['price'],
                            model='additive',
                            period=self.seasonal_period
                        )
                        
                        seasonal_strength = np.std(decomposition.seasonal) / np.std(df_resampled['price'])
                        
                        analysis["seasonality"] = {
                            "detected": seasonal_strength > 0.1,
                            "strength": float(seasonal_strength),
                            "period_days": self.seasonal_period
                        }
                except Exception as e:
                    logger.warning(f"Error detecting seasonality: {e}")
                    analysis["seasonality"] = {"detected": False}
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing historical prices: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def forecast_prices(
        self,
        prices: List[Dict[str, Any]],
        commodity: str,
        forecast_days: int = 7
    ) -> Dict[str, Any]:
        """
        Forecast future prices using time series analysis
        
        Args:
            prices: Historical price data
            commodity: Commodity name
            forecast_days: Number of days to forecast
        
        Returns:
            Dictionary with forecast results
        """
        try:
            if len(prices) < self.min_data_points:
                return {
                    "status": "insufficient_data",
                    "message": f"Need at least {self.min_data_points} data points for forecasting"
                }
            
            # Convert to DataFrame
            df = pd.DataFrame(prices)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            df.set_index('date', inplace=True)
            
            # Resample to daily frequency
            df_daily = df.resample('D').mean().interpolate()
            
            forecast_result = {
                "commodity": commodity,
                "forecast_horizon_days": forecast_days,
                "base_date": df_daily.index[-1].strftime("%Y-%m-%d"),
                "current_price": float(df_daily['price'].iloc[-1]),
                "forecasts": []
            }
            
            # Use Exponential Smoothing for forecasting
            try:
                model = ExponentialSmoothing(
                    df_daily['price'],
                    seasonal_periods=self.seasonal_period if len(df_daily) >= self.seasonal_period * 2 else None,
                    trend='add',
                    seasonal='add' if len(df_daily) >= self.seasonal_period * 2 else None
                )
                fitted_model = model.fit()
                
                # Generate forecasts
                forecast_values = fitted_model.forecast(steps=forecast_days)
                
                for i, forecast_value in enumerate(forecast_values):
                    forecast_date = df_daily.index[-1] + timedelta(days=i+1)
                    forecast_result["forecasts"].append({
                        "date": forecast_date.strftime("%Y-%m-%d"),
                        "price": float(forecast_value),
                        "confidence": "medium"  # Simplified confidence level
                    })
                
                # Calculate forecast trend
                if len(forecast_values) >= 2:
                    forecast_trend = "increasing" if forecast_values[-1] > forecast_values[0] else "decreasing"
                    if abs(forecast_values[-1] - forecast_values[0]) / forecast_values[0] < 0.05:
                        forecast_trend = "stable"
                    
                    forecast_result["forecast_trend"] = forecast_trend
                    forecast_result["expected_change_percent"] = float(
                        (forecast_values[-1] - df_daily['price'].iloc[-1]) / df_daily['price'].iloc[-1] * 100
                    )
                
                forecast_result["status"] = "success"
                
            except Exception as e:
                logger.warning(f"Exponential smoothing failed, using simple linear forecast: {e}")
                
                # Fallback to simple linear regression
                X = np.arange(len(df_daily)).reshape(-1, 1)
                y = df_daily['price'].values
                
                model = LinearRegression()
                model.fit(X, y)
                
                for i in range(forecast_days):
                    forecast_date = df_daily.index[-1] + timedelta(days=i+1)
                    forecast_x = len(df_daily) + i
                    forecast_value = model.predict([[forecast_x]])[0]
                    
                    forecast_result["forecasts"].append({
                        "date": forecast_date.strftime("%Y-%m-%d"),
                        "price": float(forecast_value),
                        "confidence": "low"
                    })
                
                forecast_result["status"] = "success"
                forecast_result["method"] = "linear_regression"
            
            return forecast_result
            
        except Exception as e:
            logger.error(f"Error forecasting prices: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def predict_demand(
        self,
        commodity: str,
        historical_arrivals: List[Dict[str, Any]],
        season: str,
        region: str
    ) -> Dict[str, Any]:
        """
        Predict demand patterns for a commodity
        
        Args:
            commodity: Commodity name
            historical_arrivals: Historical arrival data
            season: Current season
            region: Geographic region
        
        Returns:
            Demand prediction results
        """
        try:
            if len(historical_arrivals) < 5:
                return {
                    "status": "insufficient_data",
                    "demand_level": "unknown"
                }
            
            # Convert to DataFrame
            df = pd.DataFrame(historical_arrivals)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            
            # Calculate average arrivals
            avg_arrivals = df['arrivals'].mean()
            recent_arrivals = df['arrivals'].tail(5).mean()
            
            # Determine demand level based on arrivals trend
            demand_level = "moderate"
            if recent_arrivals > avg_arrivals * 1.2:
                demand_level = "high"
            elif recent_arrivals < avg_arrivals * 0.8:
                demand_level = "low"
            
            # Calculate trend
            if len(df) >= 2:
                X = np.arange(len(df)).reshape(-1, 1)
                y = df['arrivals'].values
                
                model = LinearRegression()
                model.fit(X, y)
                
                trend_slope = model.coef_[0]
                demand_trend = "increasing" if trend_slope > 0 else "decreasing"
                
                if abs(trend_slope) < 0.01 * avg_arrivals:
                    demand_trend = "stable"
            else:
                demand_trend = "stable"
            
            prediction = {
                "commodity": commodity,
                "region": region,
                "season": season,
                "demand_level": demand_level,
                "demand_trend": demand_trend,
                "average_arrivals": float(avg_arrivals),
                "recent_arrivals": float(recent_arrivals),
                "change_percent": float((recent_arrivals - avg_arrivals) / avg_arrivals * 100) if avg_arrivals > 0 else 0,
                "status": "success"
            }
            
            # Add seasonal insights
            seasonal_factors = {
                "kharif": {"rice": "high", "cotton": "high", "soybean": "high"},
                "rabi": {"wheat": "high", "mustard": "high", "chickpea": "high"},
                "zaid": {"watermelon": "high", "cucumber": "high", "muskmelon": "high"}
            }
            
            if season.lower() in seasonal_factors:
                if commodity.lower() in seasonal_factors[season.lower()]:
                    prediction["seasonal_demand"] = seasonal_factors[season.lower()][commodity.lower()]
            
            return prediction
            
        except Exception as e:
            logger.error(f"Error predicting demand: {e}")
            return {
                "status": "error",
                "message": str(e),
                "demand_level": "unknown"
            }
    
    def recognize_seasonal_patterns(
        self,
        commodity: str,
        multi_year_prices: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Recognize seasonal price patterns across multiple years
        
        Args:
            commodity: Commodity name
            multi_year_prices: Price data spanning multiple years
        
        Returns:
            Seasonal pattern analysis
        """
        try:
            if len(multi_year_prices) < 365:  # Need at least 1 year of data
                return {
                    "status": "insufficient_data",
                    "message": "Need at least 1 year of data for seasonal analysis"
                }
            
            # Convert to DataFrame
            df = pd.DataFrame(multi_year_prices)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            df.set_index('date', inplace=True)
            
            # Extract month and calculate monthly averages
            df['month'] = df.index.month
            monthly_avg = df.groupby('month')['price'].mean()
            monthly_std = df.groupby('month')['price'].std()
            
            # Identify peak and low months
            peak_month = monthly_avg.idxmax()
            low_month = monthly_avg.idxmin()
            
            month_names = [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]
            
            pattern_analysis = {
                "commodity": commodity,
                "data_span_years": (df.index[-1] - df.index[0]).days / 365,
                "seasonal_pattern_detected": True,
                "peak_price_month": month_names[peak_month - 1],
                "peak_price": float(monthly_avg[peak_month]),
                "low_price_month": month_names[low_month - 1],
                "low_price": float(monthly_avg[low_month]),
                "price_variation_percent": float((monthly_avg[peak_month] - monthly_avg[low_month]) / monthly_avg[low_month] * 100),
                "monthly_averages": {
                    month_names[i]: {
                        "average_price": float(monthly_avg[i+1]),
                        "std_deviation": float(monthly_std[i+1]) if not pd.isna(monthly_std[i+1]) else 0
                    }
                    for i in range(12)
                },
                "status": "success"
            }
            
            # Add recommendations based on patterns
            current_month = datetime.now().month
            current_month_avg = monthly_avg[current_month]
            
            recommendations = []
            
            # Check if current month is near peak
            if current_month in [peak_month, (peak_month - 1) % 12 + 1, (peak_month + 1) % 12 + 1]:
                recommendations.append(f"Prices typically peak in {month_names[peak_month - 1]}. Consider selling soon.")
            
            # Check if current month is near low
            if current_month in [low_month, (low_month - 1) % 12 + 1, (low_month + 1) % 12 + 1]:
                recommendations.append(f"Prices typically lowest in {month_names[low_month - 1]}. Consider holding if possible.")
            
            pattern_analysis["recommendations"] = recommendations
            
            return pattern_analysis
            
        except Exception as e:
            logger.error(f"Error recognizing seasonal patterns: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def calculate_transportation_cost(
        self,
        distance_km: float,
        commodity_weight_quintals: float,
        transport_mode: str = "truck"
    ) -> Dict[str, Any]:
        """
        Calculate transportation cost based on distance and weight
        
        Args:
            distance_km: Distance to market in kilometers
            commodity_weight_quintals: Weight in quintals
            transport_mode: Mode of transport (truck, tractor, etc.)
        
        Returns:
            Transportation cost breakdown
        """
        try:
            # Base rates per quintal per km (in INR)
            transport_rates = {
                "truck": 1.5,      # ₹1.5 per quintal per km
                "tractor": 1.0,    # ₹1.0 per quintal per km
                "mini_truck": 1.2  # ₹1.2 per quintal per km
            }
            
            rate_per_quintal_km = transport_rates.get(transport_mode, transport_rates["truck"])
            
            # Calculate base cost
            base_cost = distance_km * commodity_weight_quintals * rate_per_quintal_km
            
            # Add fixed costs
            loading_unloading_cost = 50 * commodity_weight_quintals  # ₹50 per quintal
            
            # Add distance-based surcharges
            distance_surcharge = 0
            if distance_km > 100:
                distance_surcharge = (distance_km - 100) * 0.5 * commodity_weight_quintals
            
            total_cost = base_cost + loading_unloading_cost + distance_surcharge
            cost_per_quintal = total_cost / commodity_weight_quintals if commodity_weight_quintals > 0 else 0
            
            return {
                "distance_km": distance_km,
                "weight_quintals": commodity_weight_quintals,
                "transport_mode": transport_mode,
                "costs": {
                    "base_transport": float(base_cost),
                    "loading_unloading": float(loading_unloading_cost),
                    "distance_surcharge": float(distance_surcharge),
                    "total": float(total_cost),
                    "per_quintal": float(cost_per_quintal)
                },
                "rate_per_quintal_km": rate_per_quintal_km,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Error calculating transportation cost: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def optimize_net_returns(
        self,
        commodity: str,
        quantity_quintals: float,
        farmer_location: GeographicCoordinate,
        market_options: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Optimize net returns by comparing different market options
        
        Args:
            commodity: Commodity name
            quantity_quintals: Quantity to sell
            farmer_location: Farmer's location
            market_options: List of market options with prices and distances
        
        Returns:
            Sorted list of market options by net return
        """
        try:
            optimized_options = []
            
            for market in market_options:
                market_name = market.get("market_name", "Unknown")
                price_per_quintal = market.get("price_per_quintal", 0)
                distance_km = market.get("distance_km", 0)
                
                # Calculate gross revenue
                gross_revenue = price_per_quintal * quantity_quintals
                
                # Calculate transportation cost
                transport_cost_data = self.calculate_transportation_cost(
                    distance_km=distance_km,
                    commodity_weight_quintals=quantity_quintals
                )
                
                total_transport_cost = transport_cost_data["costs"]["total"]
                
                # Calculate net return
                net_revenue = gross_revenue - total_transport_cost
                profit_margin = (net_revenue / gross_revenue * 100) if gross_revenue > 0 else 0
                
                optimized_options.append({
                    "market_name": market_name,
                    "distance_km": distance_km,
                    "price_per_quintal": price_per_quintal,
                    "quantity_quintals": quantity_quintals,
                    "gross_revenue": float(gross_revenue),
                    "transport_cost": float(total_transport_cost),
                    "net_revenue": float(net_revenue),
                    "profit_margin_percent": float(profit_margin),
                    "recommendation_score": float(net_revenue)  # Higher is better
                })
            
            # Sort by net revenue (descending)
            optimized_options.sort(key=lambda x: x["net_revenue"], reverse=True)
            
            # Add rankings
            for i, option in enumerate(optimized_options):
                option["rank"] = i + 1
                
                if i == 0:
                    option["recommendation"] = "Best option - highest net return"
                elif option["profit_margin_percent"] < 10:
                    option["recommendation"] = "Low profit margin - consider alternatives"
                else:
                    option["recommendation"] = "Viable option"
            
            return optimized_options
            
        except Exception as e:
            logger.error(f"Error optimizing net returns: {e}")
            return []
