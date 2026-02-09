"""
Tests for low-bandwidth optimization and offline capabilities.

Tests compression, caching, bandwidth detection, and image optimization.
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime
import numpy as np
from PIL import Image
import io

from src.krishimitra.core.utils.compression import (
    DataCompressor,
    CompressionAlgorithm,
    CompressionLevel,
    compress_agricultural_data,
    decompress_agricultural_data
)
from src.krishimitra.core.utils.caching import (
    SQLiteCache,
    HybridCache,
    CacheBackend
)
from src.krishimitra.core.utils.bandwidth import (
    BandwidthDetector,
    BandwidthTier,
    AdaptiveContentDelivery
)
from src.krishimitra.core.utils.image_optimization import (
    ImageOptimizer,
    ImageFormat,
    CropImageAnalyzer,
    optimize_crop_image
)
from src.krishimitra.core.offline import (
    OfflineStorage,
    DataType,
    SyncStatus,
    OfflineRecommendationEngine
)


class TestDataCompressor:
    """Test data compression functionality."""
    
    def test_compressor_initialization(self):
        """Test compressor initialization with different algorithms."""
        compressor = DataCompressor(
            algorithm=CompressionAlgorithm.GZIP,
            level=CompressionLevel.MEDIUM
        )
        assert compressor.algorithm == CompressionAlgorithm.GZIP
        assert compressor.level == CompressionLevel.MEDIUM
    
    def test_compress_decompress_json(self):
        """Test JSON compression and decompression."""
        compressor = DataCompressor()
        
        # Use larger data to ensure compression is beneficial
        test_data = {
            'farmerId': 'F123',
            'cropType': 'rice',
            'recommendations': ['water', 'fertilize', 'monitor'] * 10,  # Repeat for larger data
            'details': 'This is additional data to make compression worthwhile' * 5
        }
        
        # Compress
        compressed = compressor.compress_json(test_data)
        assert isinstance(compressed, bytes)
        # For larger data, compression should reduce size
        assert len(compressed) < len(json.dumps(test_data))
        
        # Decompress
        decompressed = compressor.decompress_json(compressed)
        assert decompressed == test_data
    
    def test_compress_bytes(self):
        """Test raw bytes compression."""
        compressor = DataCompressor()
        
        test_bytes = b"This is test data " * 100
        compressed = compressor.compress_bytes(test_bytes)
        
        assert isinstance(compressed, bytes)
        assert len(compressed) < len(test_bytes)
        
        decompressed = compressor.decompress_bytes(compressed)
        assert decompressed == test_bytes
    
    def test_compression_ratio(self):
        """Test compression ratio calculation."""
        compressor = DataCompressor()
        
        original_size = 1000
        compressed_size = 300
        
        ratio = compressor.get_compression_ratio(original_size, compressed_size)
        assert ratio == pytest.approx(3.33, rel=0.01)
    
    def test_optimal_algorithm_selection(self):
        """Test optimal algorithm selection based on data size."""
        # Small data
        algo = DataCompressor.select_optimal_algorithm(500)
        assert algo == CompressionAlgorithm.ZLIB
        
        # Medium data
        algo = DataCompressor.select_optimal_algorithm(50000)
        assert algo == CompressionAlgorithm.GZIP
        
        # Large data with low bandwidth
        algo = DataCompressor.select_optimal_algorithm(200000, bandwidth_kbps=50)
        assert algo in [CompressionAlgorithm.LZ4, CompressionAlgorithm.GZIP]


class TestSQLiteCache:
    """Test SQLite caching functionality."""
    
    @pytest.fixture
    def temp_cache(self):
        """Create temporary cache for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            cache_path = f.name
        
        cache = SQLiteCache(db_path=cache_path, enable_compression=True)
        yield cache
        
        # Cleanup
        Path(cache_path).unlink(missing_ok=True)
    
    def test_cache_set_get(self, temp_cache):
        """Test setting and getting cache values."""
        test_data = {'key': 'value', 'number': 42}
        
        # Set value
        success = temp_cache.set('test_key', test_data, ttl=3600)
        assert success
        
        # Get value
        retrieved = temp_cache.get('test_key')
        assert retrieved == test_data
    
    def test_cache_expiration(self, temp_cache):
        """Test cache expiration."""
        test_data = {'expires': 'soon'}
        
        # Set with very short TTL (1 second)
        temp_cache.set('expire_key', test_data, ttl=1)
        
        # Should be expired after waiting
        import time
        time.sleep(1.5)  # Wait longer than TTL
        retrieved = temp_cache.get('expire_key')
        assert retrieved is None
    
    def test_cache_delete(self, temp_cache):
        """Test cache deletion."""
        temp_cache.set('delete_key', {'data': 'test'})
        
        # Verify exists
        assert temp_cache.exists('delete_key')
        
        # Delete
        deleted = temp_cache.delete('delete_key')
        assert deleted
        
        # Verify deleted
        assert not temp_cache.exists('delete_key')
    
    def test_cache_clear(self, temp_cache):
        """Test clearing all cache entries."""
        temp_cache.set('key1', {'data': 1})
        temp_cache.set('key2', {'data': 2})
        
        # Clear cache
        success = temp_cache.clear()
        assert success
        
        # Verify cleared
        assert not temp_cache.exists('key1')
        assert not temp_cache.exists('key2')


class TestBandwidthDetector:
    """Test bandwidth detection functionality."""
    
    def test_bandwidth_measurement(self):
        """Test bandwidth calculation."""
        detector = BandwidthDetector()
        
        # Simulate 1MB transfer in 10 seconds
        bandwidth = detector.measure_bandwidth(1024 * 1024, 10.0)
        
        # Should be approximately 819.2 kbps (allow 5% tolerance for calculation variance)
        assert bandwidth == pytest.approx(819.2, rel=0.05)
    
    def test_bandwidth_classification(self):
        """Test bandwidth tier classification."""
        assert BandwidthDetector.classify_bandwidth(0) == BandwidthTier.OFFLINE
        assert BandwidthDetector.classify_bandwidth(20) == BandwidthTier.VERY_LOW
        assert BandwidthDetector.classify_bandwidth(50) == BandwidthTier.LOW
        assert BandwidthDetector.classify_bandwidth(150) == BandwidthTier.MEDIUM
        assert BandwidthDetector.classify_bandwidth(500) == BandwidthTier.HIGH
        assert BandwidthDetector.classify_bandwidth(2000) == BandwidthTier.VERY_HIGH
    
    def test_add_measurement(self):
        """Test adding bandwidth measurements."""
        detector = BandwidthDetector(measurement_window=5)
        
        # Add measurements
        detector.add_measurement(100, latency_ms=50)
        detector.add_measurement(150, latency_ms=45)
        detector.add_measurement(120, latency_ms=48)
        
        # Get current bandwidth (weighted average)
        current = detector.get_current_bandwidth()
        assert current is not None
        assert 100 <= current <= 150
    
    def test_compression_recommendation(self):
        """Test compression recommendation based on bandwidth."""
        detector = BandwidthDetector()
        
        # Low bandwidth - should compress
        detector.add_measurement(50)
        assert detector.should_compress_data()
        
        # High bandwidth - may not need compression
        detector.add_measurement(2000)
        # Note: depends on weighted average, so may still recommend compression
    
    def test_image_quality_recommendation(self):
        """Test image quality recommendation."""
        detector = BandwidthDetector()
        
        # Very low bandwidth
        detector.add_measurement(20)
        quality = detector.get_recommended_image_quality()
        assert quality <= 50
        
        # High bandwidth
        detector.add_measurement(1500)
        quality = detector.get_recommended_image_quality()
        assert quality >= 80


class TestImageOptimizer:
    """Test image optimization functionality."""
    
    @pytest.fixture
    def sample_image(self):
        """Create a sample test image."""
        # Create a simple RGB image
        img_array = np.random.randint(0, 255, (600, 800, 3), dtype=np.uint8)
        img = Image.fromarray(img_array, 'RGB')
        
        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        return buffer.getvalue()
    
    def test_image_optimization(self, sample_image):
        """Test basic image optimization."""
        optimizer = ImageOptimizer()
        
        optimized = optimizer.optimize_image(
            sample_image,
            max_size=(400, 300),
            quality=70
        )
        
        assert isinstance(optimized, bytes)
        assert len(optimized) < len(sample_image)
    
    def test_adaptive_optimization(self, sample_image):
        """Test adaptive optimization based on bandwidth."""
        detector = BandwidthDetector()
        detector.add_measurement(50)  # Low bandwidth
        
        optimizer = ImageOptimizer(bandwidth_detector=detector)
        
        optimized = optimizer.optimize_image(sample_image)
        
        # Should be significantly compressed for low bandwidth
        assert len(optimized) < len(sample_image) * 0.5
    
    def test_image_resize(self, sample_image):
        """Test image resizing."""
        optimizer = ImageOptimizer()
        
        # Load original image
        original = Image.open(io.BytesIO(sample_image))
        original_size = original.size
        
        # Resize
        resized = optimizer._resize_image(original, (400, 300))
        
        # Check dimensions
        assert resized.size[0] <= 400
        assert resized.size[1] <= 300


class TestOfflineStorage:
    """Test offline storage functionality."""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary offline storage."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        storage = OfflineStorage(db_path=db_path)
        yield storage
        
        # Cleanup
        Path(db_path).unlink(missing_ok=True)
    
    def test_store_retrieve(self, temp_storage):
        """Test storing and retrieving offline data."""
        test_data = {
            'recommendation': 'Apply fertilizer',
            'crop': 'rice',
            'confidence': 0.85
        }
        
        # Store
        success = temp_storage.store(
            'rec_001',
            DataType.RECOMMENDATION,
            test_data
        )
        assert success
        
        # Retrieve
        record = temp_storage.retrieve('rec_001')
        assert record is not None
        assert record.data == test_data
        assert record.data_type == DataType.RECOMMENDATION
        assert record.sync_status == SyncStatus.PENDING
    
    def test_list_by_type(self, temp_storage):
        """Test listing records by type."""
        # Store multiple records
        for i in range(5):
            temp_storage.store(
                f'rec_{i}',
                DataType.RECOMMENDATION,
                {'id': i}
            )
        
        # List recommendations
        records = temp_storage.list_by_type(DataType.RECOMMENDATION, limit=3)
        assert len(records) == 3
        assert all(r.data_type == DataType.RECOMMENDATION for r in records)
    
    def test_sync_status_update(self, temp_storage):
        """Test updating sync status."""
        temp_storage.store('rec_001', DataType.RECOMMENDATION, {'test': 'data'})
        
        # Update status
        success = temp_storage.update_sync_status(
            'rec_001',
            SyncStatus.COMPLETED
        )
        assert success
        
        # Verify update
        record = temp_storage.retrieve('rec_001')
        assert record.sync_status == SyncStatus.COMPLETED
        assert record.sync_attempts == 1
    
    def test_pending_sync_records(self, temp_storage):
        """Test getting pending sync records."""
        # Store records with different statuses
        temp_storage.store('rec_1', DataType.RECOMMENDATION, {'id': 1})
        temp_storage.store('rec_2', DataType.RECOMMENDATION, {'id': 2})
        
        # Mark one as completed
        temp_storage.update_sync_status('rec_1', SyncStatus.COMPLETED)
        
        # Get pending
        pending = temp_storage.get_pending_sync_records()
        assert len(pending) == 1
        assert pending[0].id == 'rec_2'


class TestOfflineRecommendationEngine:
    """Test offline recommendation engine."""
    
    @pytest.fixture
    def temp_engine(self):
        """Create temporary recommendation engine."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        storage = OfflineStorage(db_path=db_path)
        engine = OfflineRecommendationEngine(storage)
        yield engine
        
        # Cleanup
        Path(db_path).unlink(missing_ok=True)
    
    def test_cache_recommendations(self, temp_engine):
        """Test caching recommendations."""
        recommendations = [
            {'id': 'rec_1', 'title': 'Water crops'},
            {'id': 'rec_2', 'title': 'Apply fertilizer'}
        ]
        
        temp_engine.cache_recommendations('farmer_001', recommendations)
        
        # Retrieve
        cached = temp_engine.get_offline_recommendations('farmer_001')
        assert len(cached) == 2
        assert cached[0]['title'] == 'Water crops'
    
    def test_basic_recommendation_generation(self, temp_engine):
        """Test basic recommendation generation."""
        rec = temp_engine.generate_basic_recommendation('rice', 'monsoon')
        
        assert 'title' in rec
        assert 'description' in rec
        assert 'actionItems' in rec
        assert 'confidence' in rec
        assert rec['confidence'] > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
