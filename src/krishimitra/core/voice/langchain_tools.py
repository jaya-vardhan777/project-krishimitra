"""
LangChain tools for speech processing workflows.

This module provides LangChain tool wrappers for integrating
voice processing capabilities into agent workflows.
"""

import logging
from typing import Optional, Dict, Any, List
import base64

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from .speech_to_text import SpeechToTextProcessor
from .text_to_speech import TextToSpeechProcessor
from .audio_processing import AudioProcessor
from .language_detector import LanguageDetector

logger = logging.getLogger(__name__)


class TranscribeAudioInput(BaseModel):
    """Input schema for transcribe audio tool."""
    audio_data_base64: str = Field(
        description="Base64-encoded audio data"
    )
    language_code: str = Field(
        default="hi-IN",
        description="Language code (e.g., 'hi-IN', 'ta-IN')"
    )
    audio_format: str = Field(
        default="mp3",
        description="Audio format (mp3, wav, flac, etc.)"
    )
    enable_preprocessing: bool = Field(
        default=True,
        description="Enable audio preprocessing and noise reduction"
    )


class TranscribeAudioTool(BaseTool):
    """
    LangChain tool for transcribing audio to text.
    
    This tool integrates Amazon Transcribe with LangChain workflows
    for speech-to-text processing in agent chains.
    """
    
    name: str = "transcribe_audio"
    description: str = (
        "Transcribe audio to text using Amazon Transcribe. "
        "Supports Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, and Punjabi. "
        "Input should be base64-encoded audio data with language code and format."
    )
    args_schema: type[BaseModel] = TranscribeAudioInput
    
    def __init__(self):
        """Initialize the transcribe audio tool."""
        super().__init__()
        self.stt_processor = SpeechToTextProcessor()
        self.audio_processor = AudioProcessor()
    
    def _run(
        self,
        audio_data_base64: str,
        language_code: str = "hi-IN",
        audio_format: str = "mp3",
        enable_preprocessing: bool = True
    ) -> str:
        """
        Run the transcription tool.
        
        Args:
            audio_data_base64: Base64-encoded audio data
            language_code: Language code
            audio_format: Audio format
            enable_preprocessing: Enable preprocessing
            
        Returns:
            Transcribed text as string
        """
        try:
            # Decode audio data
            audio_data = base64.b64decode(audio_data_base64)
            
            # Preprocess audio if enabled
            if enable_preprocessing:
                audio_data, audio_format = self.audio_processor.preprocess_audio(
                    audio_data=audio_data,
                    input_format=audio_format,
                    output_format=audio_format,
                    reduce_noise=True,
                    normalize_audio=True
                )
            
            # Transcribe with retry
            result = self.stt_processor.transcribe_with_retry(
                audio_data=audio_data,
                language_code=language_code,
                audio_format=audio_format,
                max_attempts=2
            )
            
            # Return transcribed text
            transcribed_text = result["transcribed_text"]
            confidence = result["confidence"]
            
            logger.info(
                f"Transcription successful: '{transcribed_text[:50]}...' "
                f"(confidence: {confidence:.2f})"
            )
            
            return transcribed_text
            
        except Exception as e:
            error_msg = f"Transcription failed: {str(e)}"
            logger.error(error_msg)
            return f"Error: {error_msg}"
    
    async def _arun(
        self,
        audio_data_base64: str,
        language_code: str = "hi-IN",
        audio_format: str = "mp3",
        enable_preprocessing: bool = True
    ) -> str:
        """Async version of run."""
        # For now, use sync version
        # In production, would implement true async
        return self._run(
            audio_data_base64,
            language_code,
            audio_format,
            enable_preprocessing
        )


class DetectLanguageInput(BaseModel):
    """Input schema for detect language tool."""
    text: Optional[str] = Field(
        default=None,
        description="Text to analyze for language detection"
    )
    audio_data_base64: Optional[str] = Field(
        default=None,
        description="Base64-encoded audio data for language detection"
    )
    audio_format: str = Field(
        default="mp3",
        description="Audio format if audio_data is provided"
    )


class DetectLanguageTool(BaseTool):
    """
    LangChain tool for detecting language from text or audio.
    
    This tool identifies the language of input text or audio
    to enable dynamic language switching in agent workflows.
    """
    
    name: str = "detect_language"
    description: str = (
        "Detect the language of text or audio input. "
        "Supports Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Punjabi, and English. "
        "Returns language code and confidence score."
    )
    args_schema: type[BaseModel] = DetectLanguageInput
    
    def __init__(self):
        """Initialize the detect language tool."""
        super().__init__()
        self.language_detector = LanguageDetector()
        self.stt_processor = SpeechToTextProcessor()
    
    def _run(
        self,
        text: Optional[str] = None,
        audio_data_base64: Optional[str] = None,
        audio_format: str = "mp3"
    ) -> str:
        """
        Run the language detection tool.
        
        Args:
            text: Text to analyze
            audio_data_base64: Base64-encoded audio data
            audio_format: Audio format
            
        Returns:
            Language detection result as string
        """
        try:
            if text:
                # Detect from text
                lang_code, confidence = self.language_detector.detect_language_from_text(text)
                lang_info = self.language_detector.get_language_info(lang_code)
                
                result = (
                    f"Detected language: {lang_info['name']} ({lang_code}) "
                    f"with confidence: {confidence:.2f}"
                )
                
            elif audio_data_base64:
                # Detect from audio
                audio_data = base64.b64decode(audio_data_base64)
                
                lang_code, confidence = self.stt_processor.detect_language(
                    audio_data=audio_data,
                    audio_format=audio_format
                )
                
                lang_info = self.language_detector.get_language_info(
                    self.language_detector.normalize_language_code(lang_code)
                )
                
                result = (
                    f"Detected language: {lang_info['name']} ({lang_code}) "
                    f"with confidence: {confidence:.2f}"
                )
            else:
                result = "Error: Either text or audio_data must be provided"
            
            logger.info(f"Language detection: {result}")
            return result
            
        except Exception as e:
            error_msg = f"Language detection failed: {str(e)}"
            logger.error(error_msg)
            return f"Error: {error_msg}"
    
    async def _arun(
        self,
        text: Optional[str] = None,
        audio_data_base64: Optional[str] = None,
        audio_format: str = "mp3"
    ) -> str:
        """Async version of run."""
        return self._run(text, audio_data_base64, audio_format)


class PreprocessAudioInput(BaseModel):
    """Input schema for preprocess audio tool."""
    audio_data_base64: str = Field(
        description="Base64-encoded audio data"
    )
    input_format: str = Field(
        default="mp3",
        description="Input audio format"
    )
    output_format: str = Field(
        default="mp3",
        description="Desired output format"
    )
    reduce_noise: bool = Field(
        default=True,
        description="Apply noise reduction"
    )
    normalize_audio: bool = Field(
        default=True,
        description="Normalize audio levels"
    )


class PreprocessAudioTool(BaseTool):
    """
    LangChain tool for preprocessing audio.
    
    This tool enhances audio quality through noise reduction,
    normalization, and format conversion.
    """
    
    name: str = "preprocess_audio"
    description: str = (
        "Preprocess audio for optimal speech recognition. "
        "Applies noise reduction, normalization, and format conversion. "
        "Returns base64-encoded processed audio."
    )
    args_schema: type[BaseModel] = PreprocessAudioInput
    
    def __init__(self):
        """Initialize the preprocess audio tool."""
        super().__init__()
        self.audio_processor = AudioProcessor()
    
    def _run(
        self,
        audio_data_base64: str,
        input_format: str = "mp3",
        output_format: str = "mp3",
        reduce_noise: bool = True,
        normalize_audio: bool = True
    ) -> str:
        """
        Run the audio preprocessing tool.
        
        Args:
            audio_data_base64: Base64-encoded audio data
            input_format: Input format
            output_format: Output format
            reduce_noise: Apply noise reduction
            normalize_audio: Normalize audio
            
        Returns:
            Base64-encoded processed audio
        """
        try:
            # Decode audio
            audio_data = base64.b64decode(audio_data_base64)
            
            # Preprocess
            processed_audio, actual_format = self.audio_processor.preprocess_audio(
                audio_data=audio_data,
                input_format=input_format,
                output_format=output_format,
                reduce_noise=reduce_noise,
                normalize_audio=normalize_audio
            )
            
            # Encode result
            processed_base64 = base64.b64encode(processed_audio).decode('utf-8')
            
            logger.info(
                f"Audio preprocessed: {len(audio_data)} -> {len(processed_audio)} bytes"
            )
            
            return processed_base64
            
        except Exception as e:
            error_msg = f"Audio preprocessing failed: {str(e)}"
            logger.error(error_msg)
            return f"Error: {error_msg}"
    
    async def _arun(
        self,
        audio_data_base64: str,
        input_format: str = "mp3",
        output_format: str = "mp3",
        reduce_noise: bool = True,
        normalize_audio: bool = True
    ) -> str:
        """Async version of run."""
        return self._run(
            audio_data_base64,
            input_format,
            output_format,
            reduce_noise,
            normalize_audio
        )


def get_speech_processing_tools() -> list[BaseTool]:
    """
    Get all speech processing tools for LangChain agents.
    
    Returns:
        List of speech processing tools
    """
    return [
        TranscribeAudioTool(),
        DetectLanguageTool(),
        PreprocessAudioTool(),
        SynthesizeSpeechTool(),
        MultilingualSpeechTool(),
    ]


class SynthesizeSpeechInput(BaseModel):
    """Input schema for synthesize speech tool."""
    text: str = Field(
        description="Text to convert to speech"
    )
    language_code: str = Field(
        default="hi-IN",
        description="Language code (e.g., 'hi-IN', 'ta-IN')"
    )
    voice_id: Optional[str] = Field(
        default=None,
        description="Specific voice ID (optional)"
    )
    output_format: str = Field(
        default="mp3",
        description="Audio format (mp3, ogg_vorbis, pcm)"
    )
    network_quality: str = Field(
        default="high",
        description="Network quality for optimization (high, medium, low)"
    )


class SynthesizeSpeechTool(BaseTool):
    """
    LangChain tool for synthesizing speech from text.
    
    This tool integrates Amazon Polly with LangChain workflows
    for text-to-speech processing in agent chains.
    """
    
    name: str = "synthesize_speech"
    description: str = (
        "Convert text to speech using Amazon Polly. "
        "Supports Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, and Punjabi. "
        "Returns base64-encoded audio data and S3 URL."
    )
    args_schema: type[BaseModel] = SynthesizeSpeechInput
    
    def __init__(self):
        """Initialize the synthesize speech tool."""
        super().__init__()
        self.tts_processor = TextToSpeechProcessor()
    
    def _run(
        self,
        text: str,
        language_code: str = "hi-IN",
        voice_id: Optional[str] = None,
        output_format: str = "mp3",
        network_quality: str = "high"
    ) -> str:
        """
        Run the speech synthesis tool.
        
        Args:
            text: Text to synthesize
            language_code: Language code
            voice_id: Voice ID
            output_format: Audio format
            network_quality: Network quality
            
        Returns:
            JSON string with audio data and metadata
        """
        try:
            # Synthesize with network optimization
            result = self.tts_processor.optimize_for_network(
                text=text,
                language_code=language_code,
                network_quality=network_quality
            )
            
            # Encode audio data
            audio_base64 = base64.b64encode(result["audio_data"]).decode('utf-8')
            
            # Return result
            import json
            return json.dumps({
                "audio_base64": audio_base64,
                "audio_url": result.get("audio_url", ""),
                "duration": result["duration"],
                "format": result["format"],
                "voice_id": result["voice_id"],
                "language": result["language"],
                "size_bytes": result["size_bytes"]
            })
            
        except Exception as e:
            error_msg = f"Speech synthesis failed: {str(e)}"
            logger.error(error_msg)
            return f"Error: {error_msg}"
    
    async def _arun(
        self,
        text: str,
        language_code: str = "hi-IN",
        voice_id: Optional[str] = None,
        output_format: str = "mp3",
        network_quality: str = "high"
    ) -> str:
        """Async version of run."""
        return self._run(text, language_code, voice_id, output_format, network_quality)


class MultilingualSpeechInput(BaseModel):
    """Input schema for multilingual speech tool."""
    text_segments: List[Dict[str, str]] = Field(
        description="List of text segments with language codes"
    )
    output_format: str = Field(
        default="mp3",
        description="Audio format"
    )


class MultilingualSpeechTool(BaseTool):
    """
    LangChain tool for multilingual speech synthesis.
    
    This tool enables dynamic language switching within a single
    audio response for multilingual conversations.
    """
    
    name: str = "synthesize_multilingual_speech"
    description: str = (
        "Synthesize speech from multiple text segments in different languages. "
        "Enables dynamic language switching. Input should be a list of dicts "
        "with 'text' and 'language_code' keys."
    )
    args_schema: type[BaseModel] = MultilingualSpeechInput
    
    def __init__(self):
        """Initialize the multilingual speech tool."""
        super().__init__()
        self.tts_processor = TextToSpeechProcessor()
    
    def _run(
        self,
        text_segments: List[Dict[str, str]],
        output_format: str = "mp3"
    ) -> str:
        """
        Run the multilingual synthesis tool.
        
        Args:
            text_segments: List of text segments with languages
            output_format: Audio format
            
        Returns:
            JSON string with combined audio and metadata
        """
        try:
            # Synthesize multilingual
            result = self.tts_processor.synthesize_multilingual(
                text_segments=text_segments,
                output_format=output_format
            )
            
            # Encode audio data
            audio_base64 = base64.b64encode(result["audio_data"]).decode('utf-8')
            
            # Return result
            import json
            return json.dumps({
                "audio_base64": audio_base64,
                "audio_url": result.get("audio_url", ""),
                "duration": result["duration"],
                "format": result["format"],
                "languages": result["languages"],
                "segment_count": result["segment_count"],
                "size_bytes": result["size_bytes"]
            })
            
        except Exception as e:
            error_msg = f"Multilingual synthesis failed: {str(e)}"
            logger.error(error_msg)
            return f"Error: {error_msg}"
    
    async def _arun(
        self,
        text_segments: List[Dict[str, str]],
        output_format: str = "mp3"
    ) -> str:
        """Async version of run."""
        return self._run(text_segments, output_format)
