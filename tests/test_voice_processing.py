"""
Unit tests for voice processing modules.

Tests the core voice processing functionality including
language detection, audio processing, and compression.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import io

from src.krishimitra.core.voice import (
    LanguageDetector,
    AudioProcessor,
    VoiceCompressor,
    BandwidthDetector,
    NetworkQuality,
    CompressionLevel
)


class TestLanguageDetector:
    """Test language detection functionality."""
    
    def test_detect_language_from_hindi_text(self):
        """Test Hindi language detection from text."""
        detector = LanguageDetector()
        
        hindi_text = "मुझे अपनी फसल के बारे में सलाह चाहिए"
        lang_code, confidence = detector.detect_language_from_text(hindi_text)
        
        assert lang_code == "hi"
        assert confidence > 0.5
    
    def test_detect_language_from_tamil_text(self):
        """Test Tamil language detection from text."""
        detector = LanguageDetector()
        
        tamil_text = "எனக்கு என் பயிர் பற்றி ஆலோசனை வேண்டும்"
        lang_code, confidence = detector.detect_language_from_text(tamil_text)
        
        assert lang_code == "ta"
        assert confidence > 0.5
    
    def test_detect_language_from_english_text(self):
        """Test English language detection from text."""
        detector = LanguageDetector()
        
        english_text = "I need advice about my crops"
        lang_code, confidence = detector.detect_language_from_text(english_text)
        
        assert lang_code == "en"
        assert confidence > 0.5
    
    def test_is_supported_language(self):
        """Test supported language check."""
        detector = LanguageDetector()
        
        assert detector.is_supported_language("hi")
        assert detector.is_supported_language("ta")
        assert detector.is_supported_language("te")
        assert not detector.is_supported_language("fr")
    
    def test_normalize_language_code(self):
        """Test language code normalization."""
        detector = LanguageDetector()
        
        assert detector.normalize_language_code("hi-IN") == "hi"
        assert detector.normalize_language_code("hin") == "hi"
        assert detector.normalize_language_code("HI") == "hi"
    
    def test_format_language_code_for_aws(self):
        """Test AWS language code formatting."""
        detector = LanguageDetector()
        
        assert detector.format_language_code_for_aws("hi") == "hi-IN"
        assert detector.format_language_code_for_aws("ta") == "ta-IN"
        assert detector.format_language_code_for_aws("en") == "en-IN"
    
    def test_get_supported_languages(self):
        """Test getting supported languages list."""
        detector = LanguageDetector()
        
        languages = detector.get_supported_languages()
        
        assert "hi" in languages
        assert "ta" in languages
        assert "te" in languages
        assert "bn" in languages
        assert len(languages) >= 7


class TestAudioProcessor:
    """Test audio processing functionality."""
    
    def test_audio_processor_initialization(self):
        """Test audio processor initialization."""
        processor = AudioProcessor()
        
        assert processor is not None
        assert "mp3" in processor.SUPPORTED_FORMATS
        assert "wav" in processor.SUPPORTED_FORMATS
    
    def test_validate_audio_format(self):
        """Test audio format validation."""
        processor = AudioProcessor()
        
        # Create dummy audio data
        audio_data = b"dummy audio data"
        
        # Test with mock audio info
        with patch.object(processor, 'get_audio_info') as mock_info:
            mock_info.return_value = {
                "duration_seconds": 5.0,
                "size_bytes": len(audio_data)
            }
            
            is_valid, error = processor.validate_audio(
                audio_data=audio_data,
                audio_format="mp3",
                min_duration=1.0,
                max_duration=300.0
            )
            
            assert is_valid
            assert error is None
    
    def test_validate_audio_too_large(self):
        """Test audio validation with file too large."""
        processor = AudioProcessor()
        
        # Create large dummy audio data (> 50MB)
        audio_data = b"x" * (51 * 1024 * 1024)
        
        is_valid, error = processor.validate_audio(
            audio_data=audio_data,
            audio_format="mp3",
            max_size_mb=50.0
        )
        
        assert not is_valid
        assert "too large" in error.lower()
    
    def test_validate_audio_unsupported_format(self):
        """Test audio validation with unsupported format."""
        processor = AudioProcessor()
        
        audio_data = b"dummy audio data"
        
        is_valid, error = processor.validate_audio(
            audio_data=audio_data,
            audio_format="xyz"
        )
        
        assert not is_valid
        assert "unsupported format" in error.lower()


class TestVoiceCompressor:
    """Test voice compression functionality."""
    
    def test_compressor_initialization(self):
        """Test compressor initialization."""
        compressor = VoiceCompressor()
        
        assert compressor is not None
        assert CompressionLevel.NONE in compressor.COMPRESSION_PRESETS
        assert CompressionLevel.MAXIMUM in compressor.COMPRESSION_PRESETS
    
    def test_network_compression_mapping(self):
        """Test network quality to compression level mapping."""
        compressor = VoiceCompressor()
        
        assert compressor.NETWORK_COMPRESSION_MAP[NetworkQuality.EXCELLENT] == CompressionLevel.NONE
        assert compressor.NETWORK_COMPRESSION_MAP[NetworkQuality.GOOD] == CompressionLevel.LOW
        assert compressor.NETWORK_COMPRESSION_MAP[NetworkQuality.FAIR] == CompressionLevel.MEDIUM
        assert compressor.NETWORK_COMPRESSION_MAP[NetworkQuality.POOR] == CompressionLevel.HIGH
        assert compressor.NETWORK_COMPRESSION_MAP[NetworkQuality.VERY_POOR] == CompressionLevel.MAXIMUM
    
    def test_determine_compression_for_target_size(self):
        """Test compression level determination for target size."""
        compressor = VoiceCompressor()
        
        # Test different compression ratios
        original_size = 1000000  # 1MB
        
        # 80% of original -> LOW compression
        level = compressor._determine_compression_for_target_size(original_size, 800)
        assert level == CompressionLevel.LOW
        
        # 50% of original -> MEDIUM compression
        level = compressor._determine_compression_for_target_size(original_size, 500)
        assert level == CompressionLevel.MEDIUM
        
        # 30% of original -> HIGH compression
        level = compressor._determine_compression_for_target_size(original_size, 300)
        assert level == CompressionLevel.HIGH
        
        # 20% of original -> MAXIMUM compression
        level = compressor._determine_compression_for_target_size(original_size, 200)
        assert level == CompressionLevel.MAXIMUM


class TestBandwidthDetector:
    """Test bandwidth detection functionality."""
    
    def test_bandwidth_detector_initialization(self):
        """Test bandwidth detector initialization."""
        detector = BandwidthDetector()
        
        assert detector is not None
        assert detector.bandwidth_history == []
        assert detector.max_history_size == 10
    
    def test_detect_bandwidth(self):
        """Test bandwidth detection from transfer."""
        detector = BandwidthDetector()
        
        # Simulate 1MB transfer in 10 seconds
        transfer_size = 1024 * 1024  # 1MB
        transfer_time = 10.0  # seconds
        
        bandwidth = detector.detect_bandwidth(transfer_size, transfer_time)
        
        # Expected: (1024*1024*8) / (10*1000) = 838.8608 kbps
        assert bandwidth > 800
        assert bandwidth < 900
        assert len(detector.bandwidth_history) == 1
    
    def test_get_average_bandwidth(self):
        """Test average bandwidth calculation."""
        detector = BandwidthDetector()
        
        # Add multiple measurements
        detector.detect_bandwidth(1024 * 1024, 10.0)  # ~838 kbps
        detector.detect_bandwidth(512 * 1024, 5.0)    # ~838 kbps
        detector.detect_bandwidth(2048 * 1024, 20.0)  # ~838 kbps
        
        avg_bandwidth = detector.get_average_bandwidth()
        
        assert avg_bandwidth > 800
        assert avg_bandwidth < 900
    
    def test_classify_network_quality(self):
        """Test network quality classification."""
        detector = BandwidthDetector()
        
        # Test different bandwidth levels
        assert detector.classify_network_quality(1500) == NetworkQuality.EXCELLENT
        assert detector.classify_network_quality(750) == NetworkQuality.GOOD
        assert detector.classify_network_quality(300) == NetworkQuality.FAIR
        assert detector.classify_network_quality(100) == NetworkQuality.POOR
        assert detector.classify_network_quality(50) == NetworkQuality.VERY_POOR
    
    def test_recommend_compression(self):
        """Test compression recommendation based on bandwidth."""
        detector = BandwidthDetector()
        
        # Add bandwidth measurement
        detector.detect_bandwidth(512 * 1024, 5.0)  # ~838 kbps (GOOD)
        
        compression = detector.recommend_compression()
        
        assert compression == CompressionLevel.LOW
    
    def test_estimate_transfer_time(self):
        """Test transfer time estimation."""
        detector = BandwidthDetector()
        
        # Set bandwidth to 1000 kbps
        detector.detect_bandwidth(1024 * 1024, 8.192)  # ~1000 kbps
        
        # Estimate time for 1MB transfer
        transfer_time = detector.estimate_transfer_time(1024 * 1024)
        
        # Expected: (1024*1024*8) / (1000*1000) = 8.388608 seconds
        assert transfer_time > 8.0
        assert transfer_time < 9.0
    
    def test_bandwidth_history_limit(self):
        """Test bandwidth history size limit."""
        detector = BandwidthDetector()
        
        # Add more than max_history_size measurements
        for i in range(15):
            detector.detect_bandwidth(1024 * 1024, 10.0)
        
        # Should only keep last 10
        assert len(detector.bandwidth_history) == detector.max_history_size


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
