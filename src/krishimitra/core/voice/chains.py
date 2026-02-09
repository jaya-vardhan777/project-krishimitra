"""
LangChain chains for voice processing workflows.

This module provides pre-built chains for common voice processing
workflows including speech-to-text, text-to-speech, and multilingual
conversation handling.
"""

import logging
from typing import Dict, Any, Optional, List
import base64

from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_core.language_models import BaseLanguageModel

from .speech_to_text import SpeechToTextProcessor
from .text_to_speech import TextToSpeechProcessor
from .audio_processing import AudioProcessor
from .language_detector import LanguageDetector
from .compression import VoiceCompressor, BandwidthDetector, NetworkQuality

logger = logging.getLogger(__name__)


class VoiceProcessingChain:
    """
    Complete voice processing chain for farmer interactions.
    
    Handles the full workflow: audio input -> transcription -> 
    LLM processing -> text-to-speech output.
    """
    
    def __init__(
        self,
        llm: Optional[BaseLanguageModel] = None,
        enable_compression: bool = True,
        enable_preprocessing: bool = True
    ):
        """
        Initialize the voice processing chain.
        
        Args:
            llm: Language model for processing queries
            enable_compression: Enable adaptive compression
            enable_preprocessing: Enable audio preprocessing
        """
        self.stt_processor = SpeechToTextProcessor()
        self.tts_processor = TextToSpeechProcessor()
        self.audio_processor = AudioProcessor()
        self.language_detector = LanguageDetector()
        self.compressor = VoiceCompressor()
        self.bandwidth_detector = BandwidthDetector()
        
        self.llm = llm
        self.enable_compression = enable_compression
        self.enable_preprocessing = enable_preprocessing
        
        # Create LLM chain if LLM provided
        if llm:
            self.llm_chain = self._create_llm_chain(llm)
        else:
            self.llm_chain = None
    
    def process_voice_query(
        self,
        audio_data: bytes,
        audio_format: str = "mp3",
        farmer_context: Optional[Dict] = None,
        network_quality: NetworkQuality = NetworkQuality.FAIR
    ) -> Dict[str, Any]:
        """
        Process a complete voice query from farmer.
        
        Args:
            audio_data: Raw audio bytes
            audio_format: Audio format
            farmer_context: Farmer profile and context
            network_quality: Network quality for optimization
            
        Returns:
            Dictionary with transcription, response, and audio output
        """
        try:
            logger.info("Starting voice query processing")
            
            # Step 1: Preprocess audio if enabled
            if self.enable_preprocessing:
                audio_data, audio_format = self.audio_processor.preprocess_audio(
                    audio_data=audio_data,
                    input_format=audio_format,
                    output_format=audio_format,
                    reduce_noise=True,
                    normalize_audio=True
                )
            
            # Step 2: Detect language
            detected_lang, lang_confidence = self.stt_processor.detect_language(
                audio_data=audio_data,
                audio_format=audio_format
            )
            
            logger.info(
                f"Detected language: {detected_lang} "
                f"(confidence: {lang_confidence:.2f})"
            )
            
            # Step 3: Transcribe speech to text
            transcription_result = self.stt_processor.transcribe_with_retry(
                audio_data=audio_data,
                language_code=detected_lang,
                audio_format=audio_format,
                max_attempts=2
            )
            
            transcribed_text = transcription_result["transcribed_text"]
            logger.info(f"Transcribed: '{transcribed_text[:100]}...'")
            
            # Step 4: Process with LLM if available
            if self.llm_chain and farmer_context:
                response_text = self._process_with_llm(
                    query=transcribed_text,
                    language=detected_lang,
                    farmer_context=farmer_context
                )
            else:
                # Fallback response
                response_text = self._generate_fallback_response(
                    transcribed_text,
                    detected_lang
                )
            
            logger.info(f"Generated response: '{response_text[:100]}...'")
            
            # Step 5: Synthesize response to speech
            tts_result = self.tts_processor.optimize_for_network(
                text=response_text,
                language_code=detected_lang,
                network_quality=network_quality.value
            )
            
            # Step 6: Compress audio if enabled
            if self.enable_compression:
                compressed_audio, compression_metadata = self.compressor.adaptive_compress(
                    audio_data=tts_result["audio_data"],
                    input_format=tts_result["format"],
                    network_quality=network_quality
                )
                tts_result["audio_data"] = compressed_audio
                tts_result["compression"] = compression_metadata
            
            # Prepare result
            result = {
                "transcription": {
                    "text": transcribed_text,
                    "language": detected_lang,
                    "confidence": transcription_result["confidence"],
                    "alternatives": transcription_result.get("alternatives", [])
                },
                "response": {
                    "text": response_text,
                    "language": detected_lang
                },
                "audio": {
                    "data": tts_result["audio_data"],
                    "url": tts_result.get("audio_url", ""),
                    "format": tts_result["format"],
                    "duration": tts_result["duration"],
                    "size_bytes": len(tts_result["audio_data"])
                },
                "metadata": {
                    "network_quality": network_quality.value,
                    "preprocessing_enabled": self.enable_preprocessing,
                    "compression_enabled": self.enable_compression
                }
            }
            
            if self.enable_compression:
                result["metadata"]["compression"] = tts_result.get("compression", {})
            
            logger.info("Voice query processing completed successfully")
            
            return result
            
        except Exception as e:
            logger.error(f"Voice query processing failed: {str(e)}")
            raise RuntimeError(f"Voice query processing failed: {str(e)}")
    
    def process_multilingual_response(
        self,
        text_segments: List[Dict[str, str]],
        network_quality: NetworkQuality = NetworkQuality.FAIR
    ) -> Dict[str, Any]:
        """
        Process multilingual response with dynamic language switching.
        
        Args:
            text_segments: List of text segments with language codes
            network_quality: Network quality
            
        Returns:
            Dictionary with multilingual audio output
        """
        try:
            # Synthesize multilingual speech
            result = self.tts_processor.synthesize_multilingual(
                text_segments=text_segments,
                output_format="mp3"
            )
            
            # Compress if enabled
            if self.enable_compression:
                compressed_audio, compression_metadata = self.compressor.adaptive_compress(
                    audio_data=result["audio_data"],
                    input_format=result["format"],
                    network_quality=network_quality
                )
                result["audio_data"] = compressed_audio
                result["compression"] = compression_metadata
            
            return {
                "audio": {
                    "data": result["audio_data"],
                    "url": result.get("audio_url", ""),
                    "format": result["format"],
                    "duration": result["duration"],
                    "size_bytes": len(result["audio_data"])
                },
                "languages": result["languages"],
                "segment_count": result["segment_count"],
                "metadata": {
                    "network_quality": network_quality.value,
                    "compression_enabled": self.enable_compression
                }
            }
            
        except Exception as e:
            logger.error(f"Multilingual response processing failed: {str(e)}")
            raise RuntimeError(f"Multilingual response processing failed: {str(e)}")
    
    def _create_llm_chain(self, llm: BaseLanguageModel) -> LLMChain:
        """
        Create LLM chain for processing farmer queries.
        
        Args:
            llm: Language model
            
        Returns:
            LLM chain
        """
        prompt_template = """You are KrishiMitra, an AI agricultural advisor for Indian farmers.

Farmer Context:
{farmer_context}

Language: {language}

Farmer Query: {query}

Provide a helpful, accurate response in {language} language. Keep the response concise and actionable.

Response:"""
        
        prompt = PromptTemplate(
            input_variables=["farmer_context", "language", "query"],
            template=prompt_template
        )
        
        return LLMChain(llm=llm, prompt=prompt)
    
    def _process_with_llm(
        self,
        query: str,
        language: str,
        farmer_context: Dict
    ) -> str:
        """
        Process query with LLM.
        
        Args:
            query: Farmer query
            language: Language code
            farmer_context: Farmer context
            
        Returns:
            LLM response text
        """
        if not self.llm_chain:
            return self._generate_fallback_response(query, language)
        
        try:
            # Format farmer context
            context_str = self._format_farmer_context(farmer_context)
            
            # Get language name
            lang_info = self.language_detector.get_language_info(
                self.language_detector.normalize_language_code(language)
            )
            language_name = lang_info.get("name", "Hindi") if lang_info else "Hindi"
            
            # Run LLM chain
            response = self.llm_chain.run(
                farmer_context=context_str,
                language=language_name,
                query=query
            )
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"LLM processing failed: {str(e)}")
            return self._generate_fallback_response(query, language)
    
    def _format_farmer_context(self, context: Dict) -> str:
        """Format farmer context for LLM prompt."""
        parts = []
        
        if "name" in context:
            parts.append(f"Name: {context['name']}")
        if "location" in context:
            parts.append(f"Location: {context['location']}")
        if "crops" in context:
            parts.append(f"Crops: {', '.join(context['crops'])}")
        if "land_size" in context:
            parts.append(f"Land Size: {context['land_size']} acres")
        
        return "\n".join(parts) if parts else "No context available"
    
    def _generate_fallback_response(self, query: str, language: str) -> str:
        """Generate fallback response when LLM is not available."""
        # Simple fallback responses in different languages
        fallback_responses = {
            "hi-IN": "धन्यवाद। हम आपकी मदद करने की कोशिश कर रहे हैं।",
            "ta-IN": "நன்றி. நாங்கள் உங்களுக்கு உதவ முயற்சிக்கிறோம்.",
            "te-IN": "ధన్యవాదాలు. మేము మీకు సహాయం చేయడానికి ప్రయత్నిస్తున్నాము.",
            "bn-IN": "ধন্যবাদ। আমরা আপনাকে সাহায্য করার চেষ্টা করছি।",
            "mr-IN": "धन्यवाद. आम्ही तुम्हाला मदत करण्याचा प्रयत्न करत आहोत.",
            "gu-IN": "આભાર. અમે તમને મદદ કરવાનો પ્રયાસ કરી રહ્યા છીએ.",
            "pa-IN": "ਧੰਨਵਾਦ। ਅਸੀਂ ਤੁਹਾਡੀ ਮਦਦ ਕਰਨ ਦੀ ਕੋਸ਼ਿਸ਼ ਕਰ ਰਹੇ ਹਾਂ।",
            "en-IN": "Thank you. We are trying to help you."
        }
        
        return fallback_responses.get(language, fallback_responses["hi-IN"])


class StreamingVoiceChain:
    """
    Streaming voice processing chain for real-time interactions.
    
    Processes audio in chunks for low-latency responses
    over poor network connections.
    """
    
    def __init__(self, chunk_size_kb: int = 32):
        """
        Initialize streaming voice chain.
        
        Args:
            chunk_size_kb: Audio chunk size in KB
        """
        self.compressor = VoiceCompressor()
        self.chunk_size_kb = chunk_size_kb
    
    def stream_audio(
        self,
        audio_data: bytes,
        audio_format: str = "mp3"
    ) -> List[bytes]:
        """
        Stream audio in compressed chunks.
        
        Args:
            audio_data: Raw audio bytes
            audio_format: Audio format
            
        Returns:
            List of compressed audio chunks
        """
        return self.compressor.compress_for_streaming(
            audio_data=audio_data,
            input_format=audio_format,
            chunk_size_kb=self.chunk_size_kb
        )
