"""
Audio preprocessing and noise reduction for voice processing.

This module handles audio quality improvement, format conversion,
and noise reduction using librosa and pydub.
"""

import logging
import io
from typing import Optional, Tuple
import numpy as np

try:
    import librosa
    import soundfile as sf
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    logging.warning("librosa not available - advanced audio processing disabled")

try:
    from pydub import AudioSegment
    from pydub.effects import normalize, compress_dynamic_range
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    logging.warning("pydub not available - audio format conversion disabled")

logger = logging.getLogger(__name__)


class AudioProcessor:
    """
    Processes and enhances audio for speech recognition.
    
    Provides noise reduction, normalization, and format conversion
    to improve transcription accuracy.
    """
    
    # Supported audio formats
    SUPPORTED_FORMATS = ["mp3", "wav", "flac", "ogg", "m4a", "webm", "amr"]
    
    # Audio quality presets
    QUALITY_PRESETS = {
        "high": {"sample_rate": 16000, "bitrate": "128k"},
        "medium": {"sample_rate": 16000, "bitrate": "64k"},
        "low": {"sample_rate": 8000, "bitrate": "32k"},
    }
    
    def __init__(self):
        """Initialize the audio processor."""
        if not LIBROSA_AVAILABLE:
            logger.warning("Librosa not available - noise reduction disabled")
        if not PYDUB_AVAILABLE:
            logger.warning("Pydub not available - format conversion limited")
    
    def preprocess_audio(
        self,
        audio_data: bytes,
        input_format: str = "mp3",
        output_format: str = "mp3",
        reduce_noise: bool = True,
        normalize_audio: bool = True,
        target_sample_rate: int = 16000
    ) -> Tuple[bytes, str]:
        """
        Preprocess audio for optimal speech recognition.
        
        Args:
            audio_data: Raw audio bytes
            input_format: Input audio format
            output_format: Desired output format
            reduce_noise: Apply noise reduction
            normalize_audio: Normalize audio levels
            target_sample_rate: Target sample rate in Hz
            
        Returns:
            Tuple of (processed_audio_bytes, output_format)
        """
        try:
            if not PYDUB_AVAILABLE:
                logger.warning("Pydub not available - returning original audio")
                return audio_data, input_format
            
            # Load audio
            audio = AudioSegment.from_file(
                io.BytesIO(audio_data),
                format=input_format
            )
            
            # Normalize audio levels
            if normalize_audio:
                audio = normalize(audio)
                logger.debug("Audio normalized")
            
            # Apply dynamic range compression
            audio = compress_dynamic_range(audio)
            
            # Resample if needed
            if audio.frame_rate != target_sample_rate:
                audio = audio.set_frame_rate(target_sample_rate)
                logger.debug(f"Audio resampled to {target_sample_rate}Hz")
            
            # Convert to mono if stereo
            if audio.channels > 1:
                audio = audio.set_channels(1)
                logger.debug("Audio converted to mono")
            
            # Apply noise reduction if requested and available
            if reduce_noise and LIBROSA_AVAILABLE:
                audio_data_processed = self._reduce_noise_librosa(audio)
                if audio_data_processed:
                    # Convert back to AudioSegment
                    audio = AudioSegment(
                        audio_data_processed.tobytes(),
                        frame_rate=target_sample_rate,
                        sample_width=2,  # 16-bit
                        channels=1
                    )
                    logger.debug("Noise reduction applied")
            
            # Export to desired format
            output_buffer = io.BytesIO()
            audio.export(
                output_buffer,
                format=output_format,
                parameters=["-q:a", "0"]  # Highest quality
            )
            
            processed_audio = output_buffer.getvalue()
            logger.info(
                f"Audio preprocessed: {len(audio_data)} -> {len(processed_audio)} bytes"
            )
            
            return processed_audio, output_format
            
        except Exception as e:
            logger.error(f"Audio preprocessing failed: {str(e)}")
            # Return original audio on error
            return audio_data, input_format
    
    def _reduce_noise_librosa(
        self,
        audio: AudioSegment
    ) -> Optional[np.ndarray]:
        """
        Apply noise reduction using librosa.
        
        Args:
            audio: AudioSegment to process
            
        Returns:
            Processed audio as numpy array or None on failure
        """
        if not LIBROSA_AVAILABLE:
            return None
        
        try:
            # Convert AudioSegment to numpy array
            samples = np.array(audio.get_array_of_samples())
            
            # Normalize to float
            if audio.sample_width == 2:  # 16-bit
                samples = samples.astype(np.float32) / 32768.0
            elif audio.sample_width == 4:  # 32-bit
                samples = samples.astype(np.float32) / 2147483648.0
            
            # Apply spectral gating for noise reduction
            # This is a simple approach - production would use more sophisticated methods
            
            # Compute short-time Fourier transform
            stft = librosa.stft(samples)
            
            # Estimate noise profile from first 0.5 seconds
            noise_sample_frames = int(0.5 * audio.frame_rate / 512)  # 512 is hop length
            noise_profile = np.median(
                np.abs(stft[:, :noise_sample_frames]),
                axis=1,
                keepdims=True
            )
            
            # Apply spectral gating
            mask = np.abs(stft) > (noise_profile * 1.5)  # Threshold
            stft_cleaned = stft * mask
            
            # Inverse STFT
            samples_cleaned = librosa.istft(stft_cleaned)
            
            # Convert back to int16
            samples_cleaned = (samples_cleaned * 32768.0).astype(np.int16)
            
            return samples_cleaned
            
        except Exception as e:
            logger.warning(f"Noise reduction failed: {str(e)}")
            return None
    
    def convert_format(
        self,
        audio_data: bytes,
        input_format: str,
        output_format: str,
        quality: str = "high"
    ) -> bytes:
        """
        Convert audio from one format to another.
        
        Args:
            audio_data: Raw audio bytes
            input_format: Input format
            output_format: Output format
            quality: Quality preset ('high', 'medium', 'low')
            
        Returns:
            Converted audio bytes
        """
        if not PYDUB_AVAILABLE:
            raise RuntimeError("Pydub not available for format conversion")
        
        if output_format not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported output format: {output_format}. "
                f"Supported: {self.SUPPORTED_FORMATS}"
            )
        
        try:
            # Load audio
            audio = AudioSegment.from_file(
                io.BytesIO(audio_data),
                format=input_format
            )
            
            # Get quality settings
            preset = self.QUALITY_PRESETS.get(quality, self.QUALITY_PRESETS["high"])
            
            # Resample if needed
            if audio.frame_rate != preset["sample_rate"]:
                audio = audio.set_frame_rate(preset["sample_rate"])
            
            # Export with quality settings
            output_buffer = io.BytesIO()
            export_params = ["-b:a", preset["bitrate"]]
            
            audio.export(
                output_buffer,
                format=output_format,
                parameters=export_params
            )
            
            converted_audio = output_buffer.getvalue()
            logger.info(
                f"Audio converted: {input_format} -> {output_format} "
                f"({len(audio_data)} -> {len(converted_audio)} bytes)"
            )
            
            return converted_audio
            
        except Exception as e:
            logger.error(f"Format conversion failed: {str(e)}")
            raise RuntimeError(f"Format conversion failed: {str(e)}")
    
    def get_audio_info(
        self,
        audio_data: bytes,
        audio_format: str
    ) -> dict:
        """
        Get information about audio file.
        
        Args:
            audio_data: Raw audio bytes
            audio_format: Audio format
            
        Returns:
            Dictionary with audio information
        """
        if not PYDUB_AVAILABLE:
            return {
                "error": "Pydub not available",
                "size_bytes": len(audio_data)
            }
        
        try:
            audio = AudioSegment.from_file(
                io.BytesIO(audio_data),
                format=audio_format
            )
            
            return {
                "duration_seconds": len(audio) / 1000.0,
                "sample_rate": audio.frame_rate,
                "channels": audio.channels,
                "sample_width": audio.sample_width,
                "frame_count": audio.frame_count(),
                "size_bytes": len(audio_data),
                "format": audio_format
            }
            
        except Exception as e:
            logger.error(f"Failed to get audio info: {str(e)}")
            return {
                "error": str(e),
                "size_bytes": len(audio_data)
            }
    
    def validate_audio(
        self,
        audio_data: bytes,
        audio_format: str,
        min_duration: float = 0.5,
        max_duration: float = 300.0,
        max_size_mb: float = 50.0
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate audio file for processing.
        
        Args:
            audio_data: Raw audio bytes
            audio_format: Audio format
            min_duration: Minimum duration in seconds
            max_duration: Maximum duration in seconds
            max_size_mb: Maximum file size in MB
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check file size
        size_mb = len(audio_data) / (1024 * 1024)
        if size_mb > max_size_mb:
            return False, f"Audio file too large: {size_mb:.1f}MB (max: {max_size_mb}MB)"
        
        # Check format
        if audio_format not in self.SUPPORTED_FORMATS:
            return False, f"Unsupported format: {audio_format}"
        
        # Get audio info
        info = self.get_audio_info(audio_data, audio_format)
        
        if "error" in info:
            return False, f"Invalid audio file: {info['error']}"
        
        # Check duration
        duration = info.get("duration_seconds", 0)
        if duration < min_duration:
            return False, f"Audio too short: {duration:.1f}s (min: {min_duration}s)"
        if duration > max_duration:
            return False, f"Audio too long: {duration:.1f}s (max: {max_duration}s)"
        
        return True, None
