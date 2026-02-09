"""
Bandwidth detection and adaptive content delivery utilities.

This module provides bandwidth monitoring and adaptive content delivery
for optimal performance in low-bandwidth rural environments.
"""

import time
from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta


class BandwidthTier(Enum):
    """Network bandwidth tiers."""
    OFFLINE = 0  # No connectivity
    VERY_LOW = 1  # < 32 kbps (2G)
    LOW = 2  # 32-64 kbps (2G)
    MEDIUM = 3  # 64-256 kbps (2.5G/3G)
    HIGH = 4  # 256-1000 kbps (3G)
    VERY_HIGH = 5  # > 1000 kbps (4G+)


@dataclass
class BandwidthMeasurement:
    """Represents a bandwidth measurement."""
    timestamp: datetime
    bandwidth_kbps: float
    latency_ms: float
    packet_loss: float
    tier: BandwidthTier


class BandwidthDetector:
    """
    Detects and monitors network bandwidth conditions.
    
    Provides adaptive content delivery based on real-time bandwidth measurements.
    """
    
    def __init__(self, measurement_window: int = 10):
        """
        Initialize bandwidth detector.
        
        Args:
            measurement_window: Number of recent measurements to consider
        """
        self.measurement_window = measurement_window
        self.measurements: list[BandwidthMeasurement] = []
        self._last_measurement_time: Optional[datetime] = None
    
    def measure_bandwidth(
        self,
        data_size_bytes: int,
        transfer_time_seconds: float
    ) -> float:
        """
        Calculate bandwidth from a data transfer.
        
        Args:
            data_size_bytes: Size of transferred data in bytes
            transfer_time_seconds: Time taken for transfer
            
        Returns:
            Bandwidth in kbps
        """
        if transfer_time_seconds <= 0:
            return 0.0
        
        # Convert to kilobits per second
        bandwidth_kbps = (data_size_bytes * 8) / (transfer_time_seconds * 1000)
        return bandwidth_kbps
    
    def add_measurement(
        self,
        bandwidth_kbps: float,
        latency_ms: float = 0.0,
        packet_loss: float = 0.0
    ):
        """
        Add a bandwidth measurement.
        
        Args:
            bandwidth_kbps: Measured bandwidth in kbps
            latency_ms: Network latency in milliseconds
            packet_loss: Packet loss percentage (0-100)
        """
        tier = self.classify_bandwidth(bandwidth_kbps)
        
        measurement = BandwidthMeasurement(
            timestamp=datetime.utcnow(),
            bandwidth_kbps=bandwidth_kbps,
            latency_ms=latency_ms,
            packet_loss=packet_loss,
            tier=tier
        )
        
        self.measurements.append(measurement)
        
        # Keep only recent measurements
        if len(self.measurements) > self.measurement_window:
            self.measurements = self.measurements[-self.measurement_window:]
        
        self._last_measurement_time = datetime.utcnow()
    
    def get_current_bandwidth(self) -> Optional[float]:
        """
        Get current estimated bandwidth.
        
        Returns:
            Current bandwidth in kbps or None if no measurements
        """
        if not self.measurements:
            return None
        
        # Use weighted average with recent measurements having more weight
        total_weight = 0
        weighted_sum = 0
        
        for i, measurement in enumerate(self.measurements):
            weight = i + 1  # More recent = higher weight
            weighted_sum += measurement.bandwidth_kbps * weight
            total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else None
    
    def get_current_tier(self) -> BandwidthTier:
        """
        Get current bandwidth tier.
        
        Returns:
            Current bandwidth tier
        """
        bandwidth = self.get_current_bandwidth()
        
        if bandwidth is None:
            return BandwidthTier.MEDIUM  # Default assumption
        
        return self.classify_bandwidth(bandwidth)
    
    @staticmethod
    def classify_bandwidth(bandwidth_kbps: float) -> BandwidthTier:
        """
        Classify bandwidth into tiers.
        
        Args:
            bandwidth_kbps: Bandwidth in kbps
            
        Returns:
            Bandwidth tier
        """
        if bandwidth_kbps <= 0:
            return BandwidthTier.OFFLINE
        elif bandwidth_kbps < 32:
            return BandwidthTier.VERY_LOW
        elif bandwidth_kbps < 64:
            return BandwidthTier.LOW
        elif bandwidth_kbps < 256:
            return BandwidthTier.MEDIUM
        elif bandwidth_kbps < 1000:
            return BandwidthTier.HIGH
        else:
            return BandwidthTier.VERY_HIGH
    
    def should_compress_data(self) -> bool:
        """
        Determine if data should be compressed based on bandwidth.
        
        Returns:
            True if compression is recommended
        """
        tier = self.get_current_tier()
        return tier in [
            BandwidthTier.VERY_LOW,
            BandwidthTier.LOW,
            BandwidthTier.MEDIUM
        ]
    
    def get_recommended_image_quality(self) -> int:
        """
        Get recommended image quality based on bandwidth.
        
        Returns:
            Image quality (1-100)
        """
        tier = self.get_current_tier()
        
        quality_map = {
            BandwidthTier.OFFLINE: 30,
            BandwidthTier.VERY_LOW: 40,
            BandwidthTier.LOW: 50,
            BandwidthTier.MEDIUM: 65,
            BandwidthTier.HIGH: 80,
            BandwidthTier.VERY_HIGH: 90
        }
        
        return quality_map.get(tier, 65)
    
    def get_recommended_max_image_size(self) -> tuple[int, int]:
        """
        Get recommended maximum image dimensions based on bandwidth.
        
        Returns:
            Tuple of (width, height) in pixels
        """
        tier = self.get_current_tier()
        
        size_map = {
            BandwidthTier.OFFLINE: (320, 240),
            BandwidthTier.VERY_LOW: (480, 360),
            BandwidthTier.LOW: (640, 480),
            BandwidthTier.MEDIUM: (800, 600),
            BandwidthTier.HIGH: (1024, 768),
            BandwidthTier.VERY_HIGH: (1920, 1080)
        }
        
        return size_map.get(tier, (800, 600))
    
    def is_suitable_for_voice(self) -> bool:
        """
        Check if bandwidth is suitable for voice communication.
        
        Returns:
            True if voice communication is feasible
        """
        tier = self.get_current_tier()
        return tier != BandwidthTier.OFFLINE
    
    def is_suitable_for_video(self) -> bool:
        """
        Check if bandwidth is suitable for video communication.
        
        Returns:
            True if video communication is feasible
        """
        tier = self.get_current_tier()
        return tier in [
            BandwidthTier.HIGH,
            BandwidthTier.VERY_HIGH
        ]


class AdaptiveContentDelivery:
    """
    Adaptive content delivery based on bandwidth conditions.
    
    Automatically adjusts content quality and delivery strategy based on
    real-time network conditions.
    """
    
    def __init__(self, bandwidth_detector: Optional[BandwidthDetector] = None):
        """
        Initialize adaptive content delivery.
        
        Args:
            bandwidth_detector: Bandwidth detector instance
        """
        self.bandwidth_detector = bandwidth_detector or BandwidthDetector()
    
    def adapt_response_data(
        self,
        data: Dict[str, Any],
        include_optional: bool = True
    ) -> Dict[str, Any]:
        """
        Adapt response data based on bandwidth.
        
        Args:
            data: Original response data
            include_optional: Whether to include optional fields
            
        Returns:
            Adapted response data
        """
        tier = self.bandwidth_detector.get_current_tier()
        
        # For very low bandwidth, strip optional fields
        if tier in [BandwidthTier.VERY_LOW, BandwidthTier.LOW]:
            return self._strip_optional_fields(data)
        
        return data
    
    def _strip_optional_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove optional fields from response data.
        
        Args:
            data: Original data
            
        Returns:
            Data with optional fields removed
        """
        # Define essential fields that should always be included
        essential_fields = {
            'id', 'farmerId', 'recommendation', 'title', 'description',
            'actionItems', 'timestamp', 'queryType', 'status'
        }
        
        if isinstance(data, dict):
            return {
                key: value for key, value in data.items()
                if key in essential_fields or not key.startswith('_')
            }
        
        return data
    
    def get_pagination_size(self) -> int:
        """
        Get recommended pagination size based on bandwidth.
        
        Returns:
            Number of items per page
        """
        tier = self.bandwidth_detector.get_current_tier()
        
        size_map = {
            BandwidthTier.OFFLINE: 5,
            BandwidthTier.VERY_LOW: 10,
            BandwidthTier.LOW: 15,
            BandwidthTier.MEDIUM: 20,
            BandwidthTier.HIGH: 30,
            BandwidthTier.VERY_HIGH: 50
        }
        
        return size_map.get(tier, 20)
    
    def should_use_progressive_loading(self) -> bool:
        """
        Determine if progressive loading should be used.
        
        Returns:
            True if progressive loading is recommended
        """
        tier = self.bandwidth_detector.get_current_tier()
        return tier in [
            BandwidthTier.VERY_LOW,
            BandwidthTier.LOW,
            BandwidthTier.MEDIUM
        ]
    
    def get_cache_strategy(self) -> str:
        """
        Get recommended caching strategy based on bandwidth.
        
        Returns:
            Cache strategy ('aggressive', 'moderate', 'minimal')
        """
        tier = self.bandwidth_detector.get_current_tier()
        
        if tier in [BandwidthTier.OFFLINE, BandwidthTier.VERY_LOW]:
            return 'aggressive'
        elif tier in [BandwidthTier.LOW, BandwidthTier.MEDIUM]:
            return 'moderate'
        else:
            return 'minimal'
