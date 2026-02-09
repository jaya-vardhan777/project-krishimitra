"""
Voice compression and low-bandwidth optimization.

This module provides adaptive audio compression algorithms
and bandwidth detection for optimal voice processing in rural areas.
"""

import logging
import io
from typing import Dict, Optional, Tuple
from enum import Enum

try:
    from pydub import AudioSegment
    from pydub.effects import normalize
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    logging.warning("pydub not available - compression features limited")

logger = logging.getLogger(__name__)


class NetworkQuality(str, Enum):
    """Network quality levels."""
    EXCELLENT = "excellent"  # > 1 Mbps
    GOOD = "good"  # 512 kbps - 1 Mbps
    FAIR = "fair"  # 128 kbps - 512 kbps
    POOR = "poor"  # 64 kbps - 128 kbps
    VERY_POOR = "very_poor"  # < 64 kbps


class CompressionLevel(str, Enum):
    """Audio compression levels."""
    NONE = "none"  # No compression
    LOW = "low"  # Minimal compression, high quality
    MEDIUM = "medium"  # Balanced compression
    HIGH = "high"  # Aggressive compression, lower quality
    MAXIMUM = "maximum"  # Maximum compression for very poor networks


class VoiceCompressor:
    """
    Compresses voice audio for low-bandwidth scenarios.
    
    Provides adaptive compression based on network conditions
    while maintaining acceptable quality for speech recognition.
    """
    
    # Compression presets
    COMPRESSION_PRESETS = {
        CompressionLevel.NONE: {
            "sample_rate": 16000,
            "bitrate": "128k",
            "channels": 1,
            "codec_params": []
        },
        CompressionLevel.LOW: {
            "sample_rate": 16000,
            "bitrate": "96k",
            "channels": 1,
            "codec_params": ["-q:a", "2"]
        },
        CompressionLevel.MEDIUM: {
            "sample_rate": 16000,
            "bitrate": "64k",
            "channels": 1,
            "codec_params": ["-q:a", "4"]
        },
        CompressionLevel.HIGH: {
            "sample_rate": 12000,
            "bitrate": "32k",
            "channels": 1,
            "codec_params": ["-q:a", "6"]
        },
        CompressionLevel.MAXIMUM: {
            "sample_rate": 8000,
            "bitrate": "24k",
            "channels": 1,
            "codec_params": ["-q:a", "8"]
        }
    }
    
    # Network quality to compression level mapping
    NETWORK_COMPRESSION_MAP = {
        NetworkQuality.EXCELLENT: CompressionLevel.NONE,
        NetworkQuality.GOOD: CompressionLevel.LOW,
        NetworkQuality.FAIR: CompressionLevel.MEDIUM,
        NetworkQuality.POOR: CompressionLevel.HIGH,
        NetworkQuality.VERY_POOR: CompressionLevel.MAXIMUM,
    }
    
    def __init__(self):
        """Initialize the voice compressor."""
        if not PYDUB_AVAILABLE:
            logger.warning("Pydub not available - compression features disabled")
    
    def compress_audio(
        self,
        audio_data: bytes,
        input_format: str = "mp3",
        compression_level: CompressionLevel = CompressionLevel.MEDIUM,
        output_format: str = "mp3"
    ) -> Tuple[bytes, Dict]:
        """
        Compress audio with specified compression level.
        
        Args:
            audio_data: Raw audio bytes
            input_format: Input audio format
            compression_level: Compression level
            output_format: Output format
            
        Returns:
            Tuple of (compressed_audio_bytes, metadata_dict)
        """
        if not PYDUB_AVAILABLE:
            logger.warning("Pydub not available - returning original audio")
            return audio_data, {"compression": "none", "error": "pydub unavailable"}
        
        try:
            # Load audio
            audio = AudioSegment.from_file(
                io.BytesIO(audio_data),
                format=input_format
            )
            
            original_size = len(audio_data)
            original_duration = len(audio) / 1000.0
            
            # Get compression preset
            preset = self.COMPRESSION_PRESETS[compression_level]
            
            # Apply compression settings
            # Resample
            if audio.frame_rate != preset["sample_rate"]:
                audio = audio.set_frame_rate(preset["sample_rate"])
            
            # Convert to mono
            if audio.channels != preset["channels"]:
                audio = audio.set_channels(preset["channels"])
            
            # Normalize to prevent clipping
            audio = normalize(audio)
            
            # Export with compression
            output_buffer = io.BytesIO()
            export_params = ["-b:a", preset["bitrate"]] + preset["codec_params"]
            
            audio.export(
                output_buffer,
                format=output_format,
                parameters=export_params
            )
            
            compressed_audio = output_buffer.getvalue()
            compressed_size = len(compressed_audio)
            
            # Calculate compression ratio
            compression_ratio = (1 - compressed_size / original_size) * 100
            
            metadata = {
                "compression_level": compression_level.value,
                "original_size_bytes": original_size,
                "compressed_size_bytes": compressed_size,
                "compression_ratio_percent": round(compression_ratio, 2),
                "duration_seconds": original_duration,
                "sample_rate": preset["sample_rate"],
                "bitrate": preset["bitrate"],
                "format": output_format
            }
            
            logger.info(
                f"Audio compressed: {original_size} -> {compressed_size} bytes "
                f"({compression_ratio:.1f}% reduction)"
            )
            
            return compressed_audio, metadata
            
        except Exception as e:
            logger.error(f"Audio compression failed: {str(e)}")
            # Return original audio on error
            return audio_data, {
                "compression": "failed",
                "error": str(e),
                "original_size_bytes": len(audio_data)
            }
    
    def adaptive_compress(
        self,
        audio_data: bytes,
        input_format: str = "mp3",
        network_quality: NetworkQuality = NetworkQuality.FAIR,
        target_size_kb: Optional[int] = None
    ) -> Tuple[bytes, Dict]:
        """
        Adaptively compress audio based on network quality or target size.
        
        Args:
            audio_data: Raw audio bytes
            input_format: Input format
            network_quality: Detected network quality
            target_size_kb: Target size in KB (optional)
            
        Returns:
            Tuple of (compressed_audio, metadata)
        """
        # Determine compression level
        if target_size_kb:
            compression_level = self._determine_compression_for_target_size(
                len(audio_data),
                target_size_kb
            )
        else:
            compression_level = self.NETWORK_COMPRESSION_MAP[network_quality]
        
        logger.info(
            f"Adaptive compression: network={network_quality.value}, "
            f"level={compression_level.value}"
        )
        
        return self.compress_audio(
            audio_data=audio_data,
            input_format=input_format,
            compression_level=compression_level
        )
    
    def compress_for_streaming(
        self,
        audio_data: bytes,
        input_format: str = "mp3",
        chunk_size_kb: int = 32
    ) -> list[bytes]:
        """
        Compress and chunk audio for streaming over low bandwidth.
        
        Args:
            audio_data: Raw audio bytes
            input_format: Input format
            chunk_size_kb: Target chunk size in KB
            
        Returns:
            List of compressed audio chunks
        """
        if not PYDUB_AVAILABLE:
            logger.warning("Pydub not available - returning single chunk")
            return [audio_data]
        
        try:
            # Load and compress audio
            compressed_audio, _ = self.compress_audio(
                audio_data=audio_data,
                input_format=input_format,
                compression_level=CompressionLevel.HIGH
            )
            
            # Split into chunks
            chunk_size_bytes = chunk_size_kb * 1024
            chunks = []
            
            for i in range(0, len(compressed_audio), chunk_size_bytes):
                chunk = compressed_audio[i:i + chunk_size_bytes]
                chunks.append(chunk)
            
            logger.info(
                f"Audio chunked for streaming: {len(chunks)} chunks "
                f"of ~{chunk_size_kb}KB each"
            )
            
            return chunks
            
        except Exception as e:
            logger.error(f"Streaming compression failed: {str(e)}")
            return [audio_data]
    
    def _determine_compression_for_target_size(
        self,
        original_size: int,
        target_size_kb: int
    ) -> CompressionLevel:
        """
        Determine compression level needed to reach target size.
        
        Args:
            original_size: Original size in bytes
            target_size_kb: Target size in KB
            
        Returns:
            Appropriate compression level
        """
        target_size_bytes = target_size_kb * 1024
        required_ratio = target_size_bytes / original_size
        
        # Select compression level based on required ratio
        if required_ratio >= 0.8:
            return CompressionLevel.LOW
        elif required_ratio >= 0.5:
            return CompressionLevel.MEDIUM
        elif required_ratio >= 0.3:
            return CompressionLevel.HIGH
        else:
            return CompressionLevel.MAXIMUM


class BandwidthDetector:
    """
    Detects network bandwidth and quality for adaptive compression.
    
    Provides bandwidth estimation and quality classification
    for optimizing voice processing.
    """
    
    # Bandwidth thresholds in kbps
    BANDWIDTH_THRESHOLDS = {
        NetworkQuality.EXCELLENT: 1000,  # > 1 Mbps
        NetworkQuality.GOOD: 512,  # 512 kbps - 1 Mbps
        NetworkQuality.FAIR: 128,  # 128 kbps - 512 kbps
        NetworkQuality.POOR: 64,  # 64 kbps - 128 kbps
        NetworkQuality.VERY_POOR: 0,  # < 64 kbps
    }
    
    def __init__(self):
        """Initialize the bandwidth detector."""
        self.bandwidth_history = []
        self.max_history_size = 10
    
    def detect_bandwidth(
        self,
        transfer_size_bytes: int,
        transfer_time_seconds: float
    ) -> float:
        """
        Detect bandwidth from a data transfer.
        
        Args:
            transfer_size_bytes: Size of transferred data
            transfer_time_seconds: Time taken for transfer
            
        Returns:
            Estimated bandwidth in kbps
        """
        if transfer_time_seconds <= 0:
            return 0.0
        
        # Calculate bandwidth in kbps
        bandwidth_kbps = (transfer_size_bytes * 8) / (transfer_time_seconds * 1000)
        
        # Add to history
        self.bandwidth_history.append(bandwidth_kbps)
        if len(self.bandwidth_history) > self.max_history_size:
            self.bandwidth_history.pop(0)
        
        logger.debug(f"Detected bandwidth: {bandwidth_kbps:.2f} kbps")
        
        return bandwidth_kbps
    
    def get_average_bandwidth(self) -> float:
        """
        Get average bandwidth from recent measurements.
        
        Returns:
            Average bandwidth in kbps
        """
        if not self.bandwidth_history:
            return 0.0
        
        return sum(self.bandwidth_history) / len(self.bandwidth_history)
    
    def classify_network_quality(
        self,
        bandwidth_kbps: Optional[float] = None
    ) -> NetworkQuality:
        """
        Classify network quality based on bandwidth.
        
        Args:
            bandwidth_kbps: Bandwidth in kbps (uses average if not provided)
            
        Returns:
            Network quality classification
        """
        if bandwidth_kbps is None:
            bandwidth_kbps = self.get_average_bandwidth()
        
        # Classify based on thresholds
        if bandwidth_kbps >= self.BANDWIDTH_THRESHOLDS[NetworkQuality.EXCELLENT]:
            quality = NetworkQuality.EXCELLENT
        elif bandwidth_kbps >= self.BANDWIDTH_THRESHOLDS[NetworkQuality.GOOD]:
            quality = NetworkQuality.GOOD
        elif bandwidth_kbps >= self.BANDWIDTH_THRESHOLDS[NetworkQuality.FAIR]:
            quality = NetworkQuality.FAIR
        elif bandwidth_kbps >= self.BANDWIDTH_THRESHOLDS[NetworkQuality.POOR]:
            quality = NetworkQuality.POOR
        else:
            quality = NetworkQuality.VERY_POOR
        
        logger.info(
            f"Network quality: {quality.value} ({bandwidth_kbps:.2f} kbps)"
        )
        
        return quality
    
    def recommend_compression(
        self,
        bandwidth_kbps: Optional[float] = None
    ) -> CompressionLevel:
        """
        Recommend compression level based on network quality.
        
        Args:
            bandwidth_kbps: Bandwidth in kbps
            
        Returns:
            Recommended compression level
        """
        quality = self.classify_network_quality(bandwidth_kbps)
        return VoiceCompressor.NETWORK_COMPRESSION_MAP[quality]
    
    def estimate_transfer_time(
        self,
        data_size_bytes: int,
        bandwidth_kbps: Optional[float] = None
    ) -> float:
        """
        Estimate transfer time for given data size.
        
        Args:
            data_size_bytes: Size of data to transfer
            bandwidth_kbps: Bandwidth (uses average if not provided)
            
        Returns:
            Estimated transfer time in seconds
        """
        if bandwidth_kbps is None:
            bandwidth_kbps = self.get_average_bandwidth()
        
        if bandwidth_kbps <= 0:
            return float('inf')
        
        # Calculate transfer time
        transfer_time = (data_size_bytes * 8) / (bandwidth_kbps * 1000)
        
        return transfer_time
