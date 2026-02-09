"""
Data compression utilities for low-bandwidth optimization.

This module provides intelligent data compression algorithms using gzip and lz4
to optimize data transmission for rural farmers with limited connectivity.
"""

import gzip
import json
import zlib
from typing import Any, Dict, Optional, Union
from enum import Enum

try:
    import lz4.frame
    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False


class CompressionLevel(Enum):
    """Compression level options."""
    NONE = 0
    LOW = 1
    MEDIUM = 5
    HIGH = 9


class CompressionAlgorithm(Enum):
    """Supported compression algorithms."""
    GZIP = "gzip"
    LZ4 = "lz4"
    ZLIB = "zlib"


class DataCompressor:
    """
    Intelligent data compression for low-bandwidth scenarios.
    
    Automatically selects optimal compression algorithm and level based on
    data characteristics and bandwidth constraints.
    """
    
    def __init__(
        self,
        algorithm: CompressionAlgorithm = CompressionAlgorithm.GZIP,
        level: CompressionLevel = CompressionLevel.MEDIUM
    ):
        """
        Initialize data compressor.
        
        Args:
            algorithm: Compression algorithm to use
            level: Compression level (higher = better compression, slower)
        """
        self.algorithm = algorithm
        self.level = level
        
        if algorithm == CompressionAlgorithm.LZ4 and not HAS_LZ4:
            raise ImportError("lz4 library not installed. Install with: pip install lz4")
    
    def compress_json(self, data: Union[Dict, list]) -> bytes:
        """
        Compress JSON data.
        
        Args:
            data: Dictionary or list to compress
            
        Returns:
            Compressed bytes
        """
        json_str = json.dumps(data, separators=(',', ':'))
        json_bytes = json_str.encode('utf-8')
        return self.compress_bytes(json_bytes)
    
    def decompress_json(self, compressed_data: bytes) -> Union[Dict, list]:
        """
        Decompress JSON data.
        
        Args:
            compressed_data: Compressed bytes
            
        Returns:
            Decompressed dictionary or list
        """
        decompressed_bytes = self.decompress_bytes(compressed_data)
        json_str = decompressed_bytes.decode('utf-8')
        return json.loads(json_str)
    
    def compress_bytes(self, data: bytes) -> bytes:
        """
        Compress raw bytes.
        
        Args:
            data: Bytes to compress
            
        Returns:
            Compressed bytes
        """
        if self.algorithm == CompressionAlgorithm.GZIP:
            return gzip.compress(data, compresslevel=self.level.value)
        elif self.algorithm == CompressionAlgorithm.LZ4:
            return lz4.frame.compress(data, compression_level=self.level.value)
        elif self.algorithm == CompressionAlgorithm.ZLIB:
            return zlib.compress(data, level=self.level.value)
        else:
            raise ValueError(f"Unsupported algorithm: {self.algorithm}")
    
    def decompress_bytes(self, compressed_data: bytes) -> bytes:
        """
        Decompress raw bytes.
        
        Args:
            compressed_data: Compressed bytes
            
        Returns:
            Decompressed bytes
        """
        if self.algorithm == CompressionAlgorithm.GZIP:
            return gzip.decompress(compressed_data)
        elif self.algorithm == CompressionAlgorithm.LZ4:
            return lz4.frame.decompress(compressed_data)
        elif self.algorithm == CompressionAlgorithm.ZLIB:
            return zlib.decompress(compressed_data)
        else:
            raise ValueError(f"Unsupported algorithm: {self.algorithm}")
    
    def get_compression_ratio(self, original_size: int, compressed_size: int) -> float:
        """
        Calculate compression ratio.
        
        Args:
            original_size: Original data size in bytes
            compressed_size: Compressed data size in bytes
            
        Returns:
            Compression ratio (original/compressed)
        """
        if compressed_size == 0:
            return 0.0
        return original_size / compressed_size
    
    @staticmethod
    def select_optimal_algorithm(
        data_size: int,
        bandwidth_kbps: Optional[float] = None
    ) -> CompressionAlgorithm:
        """
        Select optimal compression algorithm based on data characteristics.
        
        Args:
            data_size: Size of data in bytes
            bandwidth_kbps: Available bandwidth in kbps (if known)
            
        Returns:
            Recommended compression algorithm
        """
        # For very low bandwidth (< 64 kbps), use LZ4 for speed
        if bandwidth_kbps and bandwidth_kbps < 64 and HAS_LZ4:
            return CompressionAlgorithm.LZ4
        
        # For small data (< 1KB), compression overhead may not be worth it
        if data_size < 1024:
            return CompressionAlgorithm.ZLIB  # Fast for small data
        
        # For medium data (1KB - 100KB), use GZIP for good balance
        if data_size < 102400:
            return CompressionAlgorithm.GZIP
        
        # For large data, use LZ4 if available for speed, otherwise GZIP
        if HAS_LZ4:
            return CompressionAlgorithm.LZ4
        return CompressionAlgorithm.GZIP


def compress_agricultural_data(
    data: Dict[str, Any],
    bandwidth_kbps: Optional[float] = None
) -> bytes:
    """
    Compress agricultural data with automatic algorithm selection.
    
    Args:
        data: Agricultural data dictionary
        bandwidth_kbps: Available bandwidth in kbps
        
    Returns:
        Compressed data bytes
    """
    json_str = json.dumps(data, separators=(',', ':'))
    data_size = len(json_str.encode('utf-8'))
    
    algorithm = DataCompressor.select_optimal_algorithm(data_size, bandwidth_kbps)
    compressor = DataCompressor(algorithm=algorithm, level=CompressionLevel.MEDIUM)
    
    return compressor.compress_json(data)


def decompress_agricultural_data(
    compressed_data: bytes,
    algorithm: CompressionAlgorithm = CompressionAlgorithm.GZIP
) -> Dict[str, Any]:
    """
    Decompress agricultural data.
    
    Args:
        compressed_data: Compressed bytes
        algorithm: Algorithm used for compression
        
    Returns:
        Decompressed data dictionary
    """
    compressor = DataCompressor(algorithm=algorithm)
    return compressor.decompress_json(compressed_data)
