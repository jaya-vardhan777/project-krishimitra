"""
Progressive data loading and streaming utilities for FastAPI.

This module provides streaming response capabilities for efficient data delivery
in low-bandwidth scenarios.
"""

import json
from typing import AsyncIterator, Any, Dict, List, Optional
from fastapi.responses import StreamingResponse

from .compression import DataCompressor, CompressionAlgorithm
from .bandwidth import BandwidthDetector, BandwidthTier


async def stream_json_array(
    items: List[Dict[str, Any]],
    chunk_size: int = 10,
    compress: bool = False
) -> AsyncIterator[bytes]:
    """
    Stream JSON array in chunks.
    
    Args:
        items: List of items to stream
        chunk_size: Number of items per chunk
        compress: Whether to compress chunks
        
    Yields:
        Bytes of JSON data
    """
    compressor = DataCompressor() if compress else None
    
    # Start array
    yield b'['
    
    for i in range(0, len(items), chunk_size):
        chunk = items[i:i + chunk_size]
        
        # Serialize chunk
        chunk_json = json.dumps(chunk, separators=(',', ':'))[1:-1]  # Remove outer brackets
        chunk_bytes = chunk_json.encode('utf-8')
        
        # Compress if enabled
        if compress and compressor:
            chunk_bytes = compressor.compress_bytes(chunk_bytes)
        
        # Add comma separator if not first chunk
        if i > 0:
            yield b','
        
        yield chunk_bytes
    
    # End array
    yield b']'


async def stream_agricultural_data(
    data: Dict[str, Any],
    bandwidth_detector: Optional[BandwidthDetector] = None
) -> AsyncIterator[bytes]:
    """
    Stream agricultural data with adaptive compression.
    
    Args:
        data: Agricultural data to stream
        bandwidth_detector: Bandwidth detector for adaptive delivery
        
    Yields:
        Bytes of data
    """
    # Determine if compression should be used
    should_compress = False
    if bandwidth_detector:
        tier = bandwidth_detector.get_current_tier()
        should_compress = tier in [
            BandwidthTier.VERY_LOW,
            BandwidthTier.LOW,
            BandwidthTier.MEDIUM
        ]
    
    compressor = DataCompressor() if should_compress else None
    
    # Serialize data
    json_str = json.dumps(data, separators=(',', ':'))
    data_bytes = json_str.encode('utf-8')
    
    # Compress if needed
    if should_compress and compressor:
        data_bytes = compressor.compress_bytes(data_bytes)
    
    # Stream in chunks
    chunk_size = 8192  # 8KB chunks
    for i in range(0, len(data_bytes), chunk_size):
        yield data_bytes[i:i + chunk_size]


def create_streaming_response(
    data: Any,
    compress: bool = False,
    media_type: str = "application/json"
) -> StreamingResponse:
    """
    Create a streaming response for FastAPI.
    
    Args:
        data: Data to stream
        compress: Whether to compress data
        media_type: Response media type
        
    Returns:
        StreamingResponse instance
    """
    async def generate():
        if isinstance(data, list):
            async for chunk in stream_json_array(data, compress=compress):
                yield chunk
        else:
            async for chunk in stream_agricultural_data(data):
                yield chunk
    
    headers = {}
    if compress:
        headers['Content-Encoding'] = 'gzip'
    
    return StreamingResponse(
        generate(),
        media_type=media_type,
        headers=headers
    )


class ProgressiveDataLoader:
    """
    Progressive data loading for large datasets.
    
    Loads data incrementally to reduce initial load time and bandwidth usage.
    """
    
    def __init__(
        self,
        page_size: int = 20,
        bandwidth_detector: Optional[BandwidthDetector] = None
    ):
        """
        Initialize progressive data loader.
        
        Args:
            page_size: Number of items per page
            bandwidth_detector: Bandwidth detector for adaptive loading
        """
        self.page_size = page_size
        self.bandwidth_detector = bandwidth_detector
    
    def get_adaptive_page_size(self) -> int:
        """
        Get adaptive page size based on bandwidth.
        
        Returns:
            Recommended page size
        """
        if not self.bandwidth_detector:
            return self.page_size
        
        tier = self.bandwidth_detector.get_current_tier()
        
        size_map = {
            BandwidthTier.OFFLINE: 5,
            BandwidthTier.VERY_LOW: 10,
            BandwidthTier.LOW: 15,
            BandwidthTier.MEDIUM: 20,
            BandwidthTier.HIGH: 30,
            BandwidthTier.VERY_HIGH: 50
        }
        
        return size_map.get(tier, self.page_size)
    
    async def load_page(
        self,
        items: List[Any],
        page: int = 1
    ) -> Dict[str, Any]:
        """
        Load a page of data.
        
        Args:
            items: Full list of items
            page: Page number (1-indexed)
            
        Returns:
            Page data with metadata
        """
        page_size = self.get_adaptive_page_size()
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        page_items = items[start_idx:end_idx]
        total_pages = (len(items) + page_size - 1) // page_size
        
        return {
            'items': page_items,
            'page': page,
            'page_size': page_size,
            'total_items': len(items),
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_previous': page > 1
        }
    
    async def stream_pages(
        self,
        items: List[Any]
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream all pages of data.
        
        Args:
            items: Full list of items
            
        Yields:
            Page data
        """
        page_size = self.get_adaptive_page_size()
        total_pages = (len(items) + page_size - 1) // page_size
        
        for page in range(1, total_pages + 1):
            yield await self.load_page(items, page)


class ChunkedUploadHandler:
    """
    Handle chunked uploads for large files in low-bandwidth scenarios.
    
    Allows resumable uploads and progress tracking.
    """
    
    def __init__(self, chunk_size: int = 1024 * 1024):  # 1MB default
        """
        Initialize chunked upload handler.
        
        Args:
            chunk_size: Size of each chunk in bytes
        """
        self.chunk_size = chunk_size
        self.uploads: Dict[str, Dict[str, Any]] = {}
    
    def start_upload(self, upload_id: str, total_size: int) -> Dict[str, Any]:
        """
        Start a new chunked upload.
        
        Args:
            upload_id: Unique upload identifier
            total_size: Total file size in bytes
            
        Returns:
            Upload metadata
        """
        total_chunks = (total_size + self.chunk_size - 1) // self.chunk_size
        
        self.uploads[upload_id] = {
            'total_size': total_size,
            'total_chunks': total_chunks,
            'received_chunks': set(),
            'data': bytearray(total_size)
        }
        
        return {
            'upload_id': upload_id,
            'chunk_size': self.chunk_size,
            'total_chunks': total_chunks
        }
    
    def upload_chunk(
        self,
        upload_id: str,
        chunk_number: int,
        chunk_data: bytes
    ) -> Dict[str, Any]:
        """
        Upload a chunk of data.
        
        Args:
            upload_id: Upload identifier
            chunk_number: Chunk number (0-indexed)
            chunk_data: Chunk data bytes
            
        Returns:
            Upload progress
        """
        if upload_id not in self.uploads:
            raise ValueError(f"Upload {upload_id} not found")
        
        upload = self.uploads[upload_id]
        
        # Write chunk data
        start_idx = chunk_number * self.chunk_size
        end_idx = start_idx + len(chunk_data)
        upload['data'][start_idx:end_idx] = chunk_data
        
        # Mark chunk as received
        upload['received_chunks'].add(chunk_number)
        
        # Calculate progress
        progress = len(upload['received_chunks']) / upload['total_chunks']
        is_complete = len(upload['received_chunks']) == upload['total_chunks']
        
        return {
            'upload_id': upload_id,
            'progress': progress,
            'received_chunks': len(upload['received_chunks']),
            'total_chunks': upload['total_chunks'],
            'is_complete': is_complete
        }
    
    def get_upload_data(self, upload_id: str) -> Optional[bytes]:
        """
        Get complete upload data.
        
        Args:
            upload_id: Upload identifier
            
        Returns:
            Complete file data or None if not complete
        """
        if upload_id not in self.uploads:
            return None
        
        upload = self.uploads[upload_id]
        
        # Check if all chunks received
        if len(upload['received_chunks']) != upload['total_chunks']:
            return None
        
        return bytes(upload['data'])
    
    def cancel_upload(self, upload_id: str) -> bool:
        """
        Cancel an upload.
        
        Args:
            upload_id: Upload identifier
            
        Returns:
            True if cancelled, False if not found
        """
        if upload_id in self.uploads:
            del self.uploads[upload_id]
            return True
        return False
