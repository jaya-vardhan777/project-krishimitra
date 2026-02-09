"""
Voice processing module for KrishiMitra.

This module provides speech-to-text and text-to-speech capabilities
for multilingual voice interactions with farmers.
"""

from .speech_to_text import SpeechToTextProcessor
from .text_to_speech import TextToSpeechProcessor
from .audio_processing import AudioProcessor
from .language_detector import LanguageDetector
from .compression import VoiceCompressor, BandwidthDetector, NetworkQuality, CompressionLevel
from .chains import VoiceProcessingChain, StreamingVoiceChain
from .langchain_tools import (
    TranscribeAudioTool,
    DetectLanguageTool,
    PreprocessAudioTool,
    SynthesizeSpeechTool,
    MultilingualSpeechTool,
    get_speech_processing_tools
)

__all__ = [
    "SpeechToTextProcessor",
    "TextToSpeechProcessor",
    "AudioProcessor",
    "LanguageDetector",
    "VoiceCompressor",
    "BandwidthDetector",
    "NetworkQuality",
    "CompressionLevel",
    "VoiceProcessingChain",
    "StreamingVoiceChain",
    "TranscribeAudioTool",
    "DetectLanguageTool",
    "PreprocessAudioTool",
    "SynthesizeSpeechTool",
    "MultilingualSpeechTool",
    "get_speech_processing_tools",
]
