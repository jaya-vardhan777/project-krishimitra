"""
Data Synchronization and Caching Module for KrishiMitra Platform

This module implements data synchronization and caching mechanisms using Redis/ElastiCache
for market data, government database information, and other external data sources.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union
import asyncio
from dataclasses import dataclass
from enum import Enum

import redis
import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CacheStatus(str, Enum):
    """Cache status enumeration"""
    FRESH = "fresh"
    STALE = "stale"
    EXPIRED = "expired"
    MISSING = "missing"


class DataSource(str, Enum):
    """Data source enumeration"""
    AGMARKNET = "agmarknet"
    PMKISAN = "pmkisan"
    SOIL_HEALTH = "soil_health"
    CROP_INSURANCE = "crop_insurance"
    WEATHER = "weather"
    SATELLITE = "satellite"
    IOT_SENSORS = "iot_sensors"


@dataclass
class CacheEntry:
    """Cache entry metadata"""
    key: str
    data: Any
    timestamp: datetime
    ttl: int
    source: DataSource
    status: CacheStatus


class CacheManager:
    """Redis-based cache manager for external data sources"""
    
    def __init__(self):
        # Redis configuration
        self.redis_client = redis.Redis(
            host=getattr(settings, 'redis_host', 'localhost'),
            port=getattr(settings, 'redis_port', 6379),
            db=getattr(settings, 'redis_db', 0),
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        
        # Default TTL values for different data sources (in seconds)
        self.default_ttls = {
            DataSource.AGMARKNET: 3600,      # 1 hour
            DataSource.PMKISAN: 86400,       # 24 hours
            DataSource.SOIL_HEALTH: 604800,  # 7 days
            DataSource.CROP_INSURANCE: 86400, # 24 hours
            DataSource.WEATHER: 1800,        # 30 minutes
            DataSource.SATELLITE: 86400,     # 24 hours
            DataSource.IOT_SENSORS: 300      # 5 minutes
        }
        
        # Cache key prefixes
        self.key_prefixes = {
            DataSource.AGMARKNET: "market:agmarknet",
            DataSource.PMKISAN: "gov:pmkisan",
            DataSource.SOIL_HEALTH: "gov:soil_health",
            DataSource.CROP_INSURANCE: "gov:insurance",
            DataSource.WEATHER: "weather",
            DataSource.SATELLITE: "satellite",
            DataSource.IOT_SENSORS: "iot"
        }
    
    def _build_cache_key(self, source: DataSource, identifier: str) -> str:
        """Build cache key with proper prefix"""
        prefix = self.key_prefixes.get(source, "unknown")
        return f"{prefix}:{identifier}"
    
    async def get(
        self,
        source: DataSource,
        identifier: str,
        default: Any = None
    ) -> Optional[CacheEntry]:
        """Get data from cache"""
        try:
            cache_key = self._build_cache_key(source, identifier)
            
            # Get data and metadata
            pipe = self.redis_client.pipeline()
            pipe.get(cache_key)
            pipe.hgetall(f"{cache_key}:meta")
            results = pipe.execute()
            
            data_json, metadata = results
            
            if not data_json:
                return None
            
            # Parse data
            data = json.loads(data_json)
            
            # Parse metadata
            if metadata:
                timestamp = datetime.fromisoformat(metadata.get('timestamp', datetime.now(timezone.utc).isoformat()))
                ttl = int(metadata.get('ttl', self.default_ttls.get(source, 3600)))
                
                # Check if data is expired
                age = (datetime.now(timezone.utc) - timestamp).total_seconds()
                if age > ttl:
                    status = CacheStatus.EXPIRED
                elif age > ttl * 0.8:  # 80% of TTL
                    status = CacheStatus.STALE
                else:
                    status = CacheStatus.FRESH
            else:
                timestamp = datetime.now(timezone.utc)
                ttl = self.default_ttls.get(source, 3600)
                status = CacheStatus.MISSING
            
            return CacheEntry(
                key=cache_key,
                data=data,
                timestamp=timestamp,
                ttl=ttl,
                source=source,
                status=status
            )
            
        except Exception as e:
            logger.error(f"Error getting cache entry for {source}:{identifier}: {e}")
            return None
    
    async def set(
        self,
        source: DataSource,
        identifier: str,
        data: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set data in cache"""
        try:
            cache_key = self._build_cache_key(source, identifier)
            ttl = ttl or self.default_ttls.get(source, 3600)
            
            # Serialize data
            data_json = json.dumps(data, default=str)
            
            # Store data and metadata
            pipe = self.redis_client.pipeline()
            pipe.setex(cache_key, ttl, data_json)
            pipe.hset(f"{cache_key}:meta", mapping={
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'ttl': ttl,
                'source': source.value
            })
            pipe.expire(f"{cache_key}:meta", ttl)
            pipe.execute()
            
            logger.debug(f"Cached data for {source}:{identifier} with TTL {ttl}s")
            return True
            
        except Exception as e:
            logger.error(f"Error setting cache entry for {source}:{identifier}: {e}")
            return False
    
    async def delete(self, source: DataSource, identifier: str) -> bool:
        """Delete data from cache"""
        try:
            cache_key = self._build_cache_key(source, identifier)
            
            pipe = self.redis_client.pipeline()
            pipe.delete(cache_key)
            pipe.delete(f"{cache_key}:meta")
            results = pipe.execute()
            
            deleted_count = sum(results)
            logger.debug(f"Deleted {deleted_count} cache entries for {source}:{identifier}")
            return deleted_count > 0
            
        except Exception as e:
            logger.error(f"Error deleting cache entry for {source}:{identifier}: {e}")
            return False
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            info = self.redis_client.info()
            
            # Count keys by source
            key_counts = {}
            for source in DataSource:
                prefix = self.key_prefixes.get(source, "unknown")
                pattern = f"{prefix}:*"
                keys = self.redis_client.keys(pattern)
                key_counts[source.value] = len([k for k in keys if not k.endswith(':meta')])
            
            return {
                "redis_info": {
                    "used_memory": info.get('used_memory_human'),
                    "connected_clients": info.get('connected_clients'),
                    "total_commands_processed": info.get('total_commands_processed'),
                    "keyspace_hits": info.get('keyspace_hits'),
                    "keyspace_misses": info.get('keyspace_misses')
                },
                "key_counts_by_source": key_counts,
                "total_keys": sum(key_counts.values())
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}
    
    async def cleanup_expired(self) -> int:
        """Clean up expired cache entries"""
        try:
            cleaned_count = 0
            
            for source in DataSource:
                prefix = self.key_prefixes.get(source, "unknown")
                pattern = f"{prefix}:*"
                keys = self.redis_client.keys(pattern)
                
                for key in keys:
                    if key.endswith(':meta'):
                        continue
                    
                    # Check if key exists (Redis auto-expires, but we double-check)
                    if not self.redis_client.exists(key):
                        meta_key = f"{key}:meta"
                        if self.redis_client.exists(meta_key):
                            self.redis_client.delete(meta_key)
                            cleaned_count += 1
            
            logger.info(f"Cleaned up {cleaned_count} expired cache entries")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired entries: {e}")
            return 0


class DataSynchronizer:
    """Data synchronization manager for external data sources"""
    
    def __init__(self):
        self.cache_manager = CacheManager()
        
        # DynamoDB for persistent storage
        self.dynamodb = boto3.resource('dynamodb', region_name=settings.aws_region)
        
        # Sync intervals (in seconds)
        self.sync_intervals = {
            DataSource.AGMARKNET: 3600,      # 1 hour
            DataSource.PMKISAN: 86400,       # 24 hours
            DataSource.SOIL_HEALTH: 604800,  # 7 days
            DataSource.CROP_INSURANCE: 86400, # 24 hours
            DataSource.WEATHER: 1800,        # 30 minutes
            DataSource.SATELLITE: 86400,     # 24 hours
            DataSource.IOT_SENSORS: 300      # 5 minutes
        }
        
        # Last sync timestamps
        self.last_sync = {}
    
    async def should_sync(self, source: DataSource) -> bool:
        """Check if data source should be synchronized"""
        try:
            last_sync_time = self.last_sync.get(source)
            if not last_sync_time:
                return True
            
            interval = self.sync_intervals.get(source, 3600)
            time_since_sync = (datetime.now(timezone.utc) - last_sync_time).total_seconds()
            
            return time_since_sync >= interval
            
        except Exception as e:
            logger.error(f"Error checking sync status for {source}: {e}")
            return True
    
    async def sync_market_data(self, commodities: List[str]) -> Dict[str, Any]:
        """Synchronize market data from AGMARKNET"""
        try:
            from ..agents.market_integration import MarketAPIClient
            
            sync_results = {
                "source": DataSource.AGMARKNET,
                "timestamp": datetime.now(timezone.utc),
                "commodities_synced": [],
                "errors": []
            }
            
            client = MarketAPIClient()
            
            for commodity in commodities:
                try:
                    # Get fresh data from AGMARKNET
                    prices = await client.get_agmarknet_prices(commodity=commodity, limit=100)
                    
                    if prices:
                        # Cache the data
                        cache_data = [price.dict() for price in prices]
                        await self.cache_manager.set(
                            DataSource.AGMARKNET,
                            commodity,
                            cache_data
                        )
                        
                        # Store in DynamoDB for persistence
                        await self._store_market_data_persistent(commodity, cache_data)
                        
                        sync_results["commodities_synced"].append(commodity)
                        logger.info(f"Synced market data for {commodity}: {len(prices)} records")
                    
                except Exception as e:
                    error_msg = f"Error syncing {commodity}: {e}"
                    sync_results["errors"].append(error_msg)
                    logger.error(error_msg)
            
            await client.close()
            self.last_sync[DataSource.AGMARKNET] = datetime.now(timezone.utc)
            
            return sync_results
            
        except Exception as e:
            logger.error(f"Error in market data sync: {e}")
            return {"error": str(e)}
    
    async def sync_government_data(self, farmer_ids: List[str]) -> Dict[str, Any]:
        """Synchronize government data for farmers"""
        try:
            from ..agents.government_integration import GovernmentAPIClient
            
            sync_results = {
                "source": "government_databases",
                "timestamp": datetime.now(timezone.utc),
                "farmers_synced": [],
                "data_types_synced": [],
                "errors": []
            }
            
            client = GovernmentAPIClient()
            
            for farmer_id in farmer_ids:
                try:
                    # Sync PM-KISAN data
                    pmkisan_data = await client.get_pmkisan_beneficiary_info("123456789012")  # Mock Aadhaar
                    if pmkisan_data:
                        await self.cache_manager.set(
                            DataSource.PMKISAN,
                            farmer_id,
                            pmkisan_data.dict()
                        )
                        if "pmkisan" not in sync_results["data_types_synced"]:
                            sync_results["data_types_synced"].append("pmkisan")
                    
                    # Sync soil health card
                    soil_card = await client.get_soil_health_card(farmer_id, "SURVEY123")
                    if soil_card:
                        await self.cache_manager.set(
                            DataSource.SOIL_HEALTH,
                            farmer_id,
                            soil_card.dict()
                        )
                        if "soil_health" not in sync_results["data_types_synced"]:
                            sync_results["data_types_synced"].append("soil_health")
                    
                    # Sync insurance policies
                    policies = await client.get_crop_insurance_policies(farmer_id)
                    if policies:
                        policies_data = [policy.dict() for policy in policies]
                        await self.cache_manager.set(
                            DataSource.CROP_INSURANCE,
                            farmer_id,
                            policies_data
                        )
                        if "crop_insurance" not in sync_results["data_types_synced"]:
                            sync_results["data_types_synced"].append("crop_insurance")
                    
                    sync_results["farmers_synced"].append(farmer_id)
                    logger.info(f"Synced government data for farmer {farmer_id}")
                    
                except Exception as e:
                    error_msg = f"Error syncing farmer {farmer_id}: {e}"
                    sync_results["errors"].append(error_msg)
                    logger.error(error_msg)
            
            await client.close()
            
            # Update last sync times
            for data_type in [DataSource.PMKISAN, DataSource.SOIL_HEALTH, DataSource.CROP_INSURANCE]:
                self.last_sync[data_type] = datetime.now(timezone.utc)
            
            return sync_results
            
        except Exception as e:
            logger.error(f"Error in government data sync: {e}")
            return {"error": str(e)}
    
    async def _store_market_data_persistent(self, commodity: str, data: List[Dict]) -> bool:
        """Store market data in DynamoDB for persistence"""
        try:
            table = self.dynamodb.Table('MarketDataHistory')
            
            # Store as a single record with timestamp
            item = {
                'commodity': commodity,
                'timestamp': int(datetime.now(timezone.utc).timestamp()),
                'data': json.dumps(data),
                'record_count': len(data),
                'sync_date': datetime.now(timezone.utc).isoformat()
            }
            
            table.put_item(Item=item)
            logger.debug(f"Stored market data for {commodity} in DynamoDB")
            return True
            
        except ClientError as e:
            logger.error(f"DynamoDB error storing market data: {e}")
            return False
        except Exception as e:
            logger.error(f"Error storing market data persistently: {e}")
            return False
    
    async def get_sync_status(self) -> Dict[str, Any]:
        """Get synchronization status for all data sources"""
        try:
            status = {
                "last_sync_times": {},
                "next_sync_times": {},
                "sync_intervals": {},
                "cache_stats": await self.cache_manager.get_cache_stats()
            }
            
            for source in DataSource:
                last_sync = self.last_sync.get(source)
                interval = self.sync_intervals.get(source, 3600)
                
                status["last_sync_times"][source.value] = last_sync.isoformat() if last_sync else None
                status["sync_intervals"][source.value] = interval
                
                if last_sync:
                    next_sync = last_sync + timedelta(seconds=interval)
                    status["next_sync_times"][source.value] = next_sync.isoformat()
                else:
                    status["next_sync_times"][source.value] = "immediate"
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting sync status: {e}")
            return {"error": str(e)}
    
    async def force_sync_all(self) -> Dict[str, Any]:
        """Force synchronization of all data sources"""
        try:
            results = {
                "timestamp": datetime.now(timezone.utc),
                "sync_results": {},
                "errors": []
            }
            
            # Sync market data for common commodities
            common_commodities = ["Rice", "Wheat", "Cotton", "Sugarcane", "Onion", "Potato"]
            market_result = await self.sync_market_data(common_commodities)
            results["sync_results"]["market_data"] = market_result
            
            # Sync government data for sample farmers
            sample_farmers = ["FARMER001", "FARMER002", "FARMER003"]
            gov_result = await self.sync_government_data(sample_farmers)
            results["sync_results"]["government_data"] = gov_result
            
            logger.info("Completed force sync of all data sources")
            return results
            
        except Exception as e:
            logger.error(f"Error in force sync all: {e}")
            return {"error": str(e)}


# Singleton instances
cache_manager = CacheManager()
data_synchronizer = DataSynchronizer()


async def get_cached_data(
    source: DataSource,
    identifier: str,
    fetch_function: Optional[callable] = None,
    **fetch_kwargs
) -> Optional[Any]:
    """
    Get data from cache, with optional fallback to fetch function
    
    Args:
        source: Data source type
        identifier: Unique identifier for the data
        fetch_function: Optional function to fetch fresh data if cache miss
        **fetch_kwargs: Arguments for fetch function
    
    Returns:
        Cached or freshly fetched data
    """
    try:
        # Try to get from cache first
        cache_entry = await cache_manager.get(source, identifier)
        
        if cache_entry and cache_entry.status in [CacheStatus.FRESH, CacheStatus.STALE]:
            logger.debug(f"Cache hit for {source}:{identifier} (status: {cache_entry.status})")
            return cache_entry.data
        
        # Cache miss or expired - fetch fresh data if function provided
        if fetch_function:
            logger.debug(f"Cache miss for {source}:{identifier}, fetching fresh data")
            fresh_data = await fetch_function(**fetch_kwargs)
            
            if fresh_data:
                # Cache the fresh data
                await cache_manager.set(source, identifier, fresh_data)
                return fresh_data
        
        # Return stale data if available and no fetch function
        if cache_entry and cache_entry.status == CacheStatus.EXPIRED:
            logger.warning(f"Returning expired data for {source}:{identifier}")
            return cache_entry.data
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting cached data for {source}:{identifier}: {e}")
        return None