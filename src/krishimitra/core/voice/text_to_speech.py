"""
Text-to-speech processing using Amazon Polly.

This module handles multilingual speech synthesis for Indian languages
including Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, and Punjabi.
"""

import logging
import uuid
from typing import Dict, Optional, List
from datetime import datetime
import io

import boto3
from botocore.exceptions import ClientError

from ..config import get_settings

logger = logging.getLogger(__name__)


class TextToSpeechProcessor:
    """
    Processes text to speech using Amazon Polly.
    
    Supports multiple Indian languages with natural-sounding voices
    and dynamic language switching capabilities.
    """
    
    # Supported voices for Indian languages
    LANGUAGE_VOICES = {
        "hi-IN": {
            "neural": ["Kajal"],  # Hindi Neural voice
            "standard": ["Aditi"],  # Hindi Standard voice
            "default": "Kajal"
        },
        "ta-IN": {
            "neural": [],  # Tamil neural voices (if available)
            "standard": [],  # Tamil standard voices
            "default": "Aditi"  # Fallback to Hindi
        },
        "te-IN": {
            "neural": [],  # Telugu neural voices (if available)
            "standard": [],
            "default": "Aditi"  # Fallback to Hindi
        },
        "bn-IN": {
            "neural": [],  # Bengali neural voices (if available)
            "standard": [],
            "default": "Aditi"  # Fallback to Hindi
        },
        "mr-IN": {
            "neural": [],  # Marathi neural voices (if available)
            "standard": [],
            "default": "Aditi"  # Fallback to Hindi
        },
        "gu-IN": {
            "neural": [],  # Gujarati neural voices (if available)
            "standard": [],
            "default": "Aditi"  # Fallback to Hindi
        },
        "pa-IN": {
            "neural": [],  # Punjabi neural voices (if available)
            "standard": [],
            "default": "Aditi"  # Fallback to Hindi
        },
        "en-IN": {
            "neural": ["Kajal"],  # English (Indian) Neural
            "standard": ["Aditi", "Raveena"],  # English (Indian) Standard
            "default": "Kajal"
        }
    }
    
    # Voice engine types
    ENGINE_TYPES = {
        "neural": "neural",  # Higher quality, more natural
        "standard": "standard",  # Lower cost, good quality
    }
    
    # Audio formats supported by Polly
    AUDIO_FORMATS = {
        "mp3": {"content_type": "audio/mpeg", "extension": "mp3"},
        "ogg_vorbis": {"content_type": "audio/ogg", "extension": "ogg"},
        "pcm": {"content_type": "audio/pcm", "extension": "pcm"},
        "json": {"content_type": "application/json", "extension": "json"},  # Speech marks
    }
    
    # Speech rate and pitch adjustments
    PROSODY_RATES = ["x-slow", "slow", "medium", "fast", "x-fast"]
    PROSODY_PITCHES = ["x-low", "low", "medium", "high", "x-high"]
    
    def __init__(self):
        """Initialize the text-to-speech processor."""
        self.settings = get_settings()
        self.polly_client = boto3.client(
            'polly',
            region_name=self.settings.AWS_REGION
        )
        self.s3_client = boto3.client(
            's3',
            region_name=self.settings.AWS_REGION
        )
        self.bucket_name = self.settings.AUDIO_BUCKET_NAME
    
    def synthesize_speech(
        self,
        text: str,
        language_code: str = "hi-IN",
        voice_id: Optional[str] = None,
        engine: str = "neural",
        output_format: str = "mp3",
        speech_rate: str = "medium",
        pitch: str = "medium",
        save_to_s3: bool = True
    ) -> Dict:
        """
        Synthesize speech from text using Amazon Polly.
        
        Args:
            text: Text to convert to speech
            language_code: Language code (e.g., 'hi-IN', 'ta-IN')
            voice_id: Specific voice ID (optional, uses default if not provided)
            engine: Voice engine ('neural' or 'standard')
            output_format: Audio format ('mp3', 'ogg_vorbis', 'pcm')
            speech_rate: Speech rate ('x-slow', 'slow', 'medium', 'fast', 'x-fast')
            pitch: Voice pitch ('x-low', 'low', 'medium', 'high', 'x-high')
            save_to_s3: Whether to save audio to S3
            
        Returns:
            Dictionary containing:
                - audio_data: Raw audio bytes
                - audio_url: S3 URL if saved
                - duration: Estimated duration in seconds
                - format: Audio format
                - voice_id: Voice used
                - language: Language code
                
        Raises:
            ValueError: If language or format not supported
            RuntimeError: If synthesis fails
        """
        # Validate language
        if language_code not in self.LANGUAGE_VOICES:
            raise ValueError(
                f"Unsupported language: {language_code}. "
                f"Supported languages: {list(self.LANGUAGE_VOICES.keys())}"
            )
        
        # Validate format
        if output_format not in self.AUDIO_FORMATS:
            raise ValueError(
                f"Unsupported format: {output_format}. "
                f"Supported formats: {list(self.AUDIO_FORMATS.keys())}"
            )
        
        # Select voice
        if voice_id is None:
            voice_id = self._select_voice(language_code, engine)
        
        # Validate voice availability
        if not self._is_voice_available(voice_id, engine):
            logger.warning(
                f"Voice {voice_id} not available with {engine} engine, "
                f"falling back to standard"
            )
            engine = "standard"
            voice_id = self._select_voice(language_code, "standard")
        
        try:
            # Apply SSML for prosody control
            ssml_text = self._apply_prosody(text, speech_rate, pitch)
            
            logger.info(
                f"Synthesizing speech: language={language_code}, "
                f"voice={voice_id}, engine={engine}"
            )
            
            # Synthesize speech
            response = self.polly_client.synthesize_speech(
                Text=ssml_text,
                TextType="ssml",
                OutputFormat=output_format,
                VoiceId=voice_id,
                Engine=engine,
                LanguageCode=language_code
            )
            
            # Get audio stream
            audio_stream = response.get("AudioStream")
            if not audio_stream:
                raise RuntimeError("No audio stream in Polly response")
            
            # Read audio data
            audio_data = audio_stream.read()
            
            # Estimate duration (rough estimate based on text length)
            # Average speaking rate: ~150 words per minute
            word_count = len(text.split())
            estimated_duration = (word_count / 150.0) * 60.0
            
            # Adjust for speech rate
            rate_multipliers = {
                "x-slow": 0.5,
                "slow": 0.75,
                "medium": 1.0,
                "fast": 1.25,
                "x-fast": 1.5
            }
            estimated_duration /= rate_multipliers.get(speech_rate, 1.0)
            
            result = {
                "audio_data": audio_data,
                "duration": estimated_duration,
                "format": output_format,
                "voice_id": voice_id,
                "language": language_code,
                "engine": engine,
                "size_bytes": len(audio_data),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Save to S3 if requested
            if save_to_s3:
                audio_url = self._save_to_s3(
                    audio_data,
                    output_format,
                    language_code,
                    voice_id
                )
                result["audio_url"] = audio_url
            
            logger.info(
                f"Speech synthesis successful: {len(audio_data)} bytes, "
                f"~{estimated_duration:.1f}s"
            )
            
            return result
            
        except ClientError as e:
            logger.error(f"AWS Polly error: {str(e)}")
            raise RuntimeError(f"Speech synthesis failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during synthesis: {str(e)}")
            raise RuntimeError(f"Speech synthesis failed: {str(e)}")
    
    def synthesize_with_fallback(
        self,
        text: str,
        language_code: str = "hi-IN",
        preferred_engine: str = "neural",
        output_format: str = "mp3"
    ) -> Dict:
        """
        Synthesize speech with automatic fallback to standard engine.
        
        Tries neural engine first, falls back to standard if unavailable.
        
        Args:
            text: Text to synthesize
            language_code: Language code
            preferred_engine: Preferred engine type
            output_format: Audio format
            
        Returns:
            Synthesis result dictionary
        """
        try:
            # Try preferred engine
            return self.synthesize_speech(
                text=text,
                language_code=language_code,
                engine=preferred_engine,
                output_format=output_format
            )
        except Exception as e:
            logger.warning(
                f"Synthesis with {preferred_engine} engine failed: {str(e)}"
            )
            
            # Fallback to standard engine
            if preferred_engine != "standard":
                logger.info("Falling back to standard engine")
                return self.synthesize_speech(
                    text=text,
                    language_code=language_code,
                    engine="standard",
                    output_format=output_format
                )
            
            raise
    
    def synthesize_multilingual(
        self,
        text_segments: List[Dict[str, str]],
        output_format: str = "mp3"
    ) -> Dict:
        """
        Synthesize speech from multiple text segments in different languages.
        
        Enables dynamic language switching within a single response.
        
        Args:
            text_segments: List of dicts with 'text' and 'language_code' keys
            output_format: Audio format
            
        Returns:
            Dictionary with combined audio and metadata
        """
        if not text_segments:
            raise ValueError("No text segments provided")
        
        audio_segments = []
        total_duration = 0.0
        languages_used = set()
        
        try:
            for i, segment in enumerate(text_segments):
                text = segment.get("text", "")
                language_code = segment.get("language_code", "hi-IN")
                
                if not text.strip():
                    continue
                
                logger.info(
                    f"Synthesizing segment {i+1}/{len(text_segments)}: "
                    f"{language_code}"
                )
                
                # Synthesize segment
                result = self.synthesize_with_fallback(
                    text=text,
                    language_code=language_code,
                    output_format=output_format
                )
                
                audio_segments.append(result["audio_data"])
                total_duration += result["duration"]
                languages_used.add(language_code)
            
            # Combine audio segments
            combined_audio = b"".join(audio_segments)
            
            # Save combined audio to S3
            audio_url = self._save_to_s3(
                combined_audio,
                output_format,
                "multilingual",
                "combined"
            )
            
            return {
                "audio_data": combined_audio,
                "audio_url": audio_url,
                "duration": total_duration,
                "format": output_format,
                "languages": list(languages_used),
                "segment_count": len(audio_segments),
                "size_bytes": len(combined_audio),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Multilingual synthesis failed: {str(e)}")
            raise RuntimeError(f"Multilingual synthesis failed: {str(e)}")
    
    def optimize_for_network(
        self,
        text: str,
        language_code: str = "hi-IN",
        network_quality: str = "high"
    ) -> Dict:
        """
        Optimize speech synthesis for different network conditions.
        
        Args:
            text: Text to synthesize
            language_code: Language code
            network_quality: Network quality ('high', 'medium', 'low')
            
        Returns:
            Optimized synthesis result
        """
        # Select format and engine based on network quality
        if network_quality == "low":
            output_format = "mp3"
            engine = "standard"
            speech_rate = "fast"  # Faster speech = smaller file
        elif network_quality == "medium":
            output_format = "mp3"
            engine = "neural"
            speech_rate = "medium"
        else:  # high
            output_format = "mp3"
            engine = "neural"
            speech_rate = "medium"
        
        logger.info(
            f"Optimizing for {network_quality} network: "
            f"format={output_format}, engine={engine}"
        )
        
        return self.synthesize_with_fallback(
            text=text,
            language_code=language_code,
            preferred_engine=engine,
            output_format=output_format
        )
    
    def get_available_voices(
        self,
        language_code: Optional[str] = None,
        engine: Optional[str] = None
    ) -> List[Dict]:
        """
        Get list of available voices.
        
        Args:
            language_code: Filter by language code
            engine: Filter by engine type
            
        Returns:
            List of voice information dictionaries
        """
        try:
            response = self.polly_client.describe_voices(
                LanguageCode=language_code if language_code else None,
                Engine=engine if engine else None
            )
            
            voices = response.get("Voices", [])
            
            # Filter for Indian languages
            indian_voices = [
                voice for voice in voices
                if voice.get("LanguageCode", "").endswith("-IN")
            ]
            
            return indian_voices
            
        except Exception as e:
            logger.error(f"Failed to get available voices: {str(e)}")
            return []
    
    def _select_voice(self, language_code: str, engine: str) -> str:
        """
        Select appropriate voice for language and engine.
        
        Args:
            language_code: Language code
            engine: Engine type
            
        Returns:
            Voice ID
        """
        lang_voices = self.LANGUAGE_VOICES.get(language_code, {})
        
        # Try to get voice for specified engine
        voices = lang_voices.get(engine, [])
        if voices:
            return voices[0]
        
        # Fallback to default voice
        return lang_voices.get("default", "Aditi")
    
    def _is_voice_available(self, voice_id: str, engine: str) -> bool:
        """
        Check if voice is available with specified engine.
        
        Args:
            voice_id: Voice ID
            engine: Engine type
            
        Returns:
            True if available, False otherwise
        """
        try:
            response = self.polly_client.describe_voices(Engine=engine)
            voices = response.get("Voices", [])
            
            return any(voice.get("Id") == voice_id for voice in voices)
            
        except Exception as e:
            logger.warning(f"Failed to check voice availability: {str(e)}")
            return False
    
    def _apply_prosody(
        self,
        text: str,
        rate: str = "medium",
        pitch: str = "medium"
    ) -> str:
        """
        Apply SSML prosody tags to text.
        
        Args:
            text: Plain text
            rate: Speech rate
            pitch: Voice pitch
            
        Returns:
            SSML-formatted text
        """
        # Escape special XML characters
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        
        # Build SSML
        ssml = f'<speak><prosody rate="{rate}" pitch="{pitch}">{text}</prosody></speak>'
        
        return ssml
    
    def _save_to_s3(
        self,
        audio_data: bytes,
        audio_format: str,
        language_code: str,
        voice_id: str
    ) -> str:
        """
        Save audio to S3 and return URL.
        
        Args:
            audio_data: Audio bytes
            audio_format: Audio format
            language_code: Language code
            voice_id: Voice ID
            
        Returns:
            S3 URL
        """
        try:
            # Generate unique key
            audio_id = str(uuid.uuid4())
            extension = self.AUDIO_FORMATS[audio_format]["extension"]
            key = f"tts-output/{language_code}/{voice_id}/{audio_id}.{extension}"
            
            # Upload to S3
            content_type = self.AUDIO_FORMATS[audio_format]["content_type"]
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=audio_data,
                ContentType=content_type,
                Metadata={
                    "language": language_code,
                    "voice": voice_id,
                    "format": audio_format
                }
            )
            
            # Generate URL
            url = f"https://{self.bucket_name}.s3.{self.settings.AWS_REGION}.amazonaws.com/{key}"
            
            logger.debug(f"Audio saved to S3: {url}")
            
            return url
            
        except Exception as e:
            logger.error(f"Failed to save audio to S3: {str(e)}")
            # Return empty string on failure - audio_data is still available
            return ""
