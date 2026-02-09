"""
Voice processing endpoints for KrishiMitra API.

This module handles voice input and output processing for farmers.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import base64

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Depends
from pydantic import BaseModel, Field

from ...core.config import get_settings
from ...core.voice import VoiceProcessingChain, NetworkQuality

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


class VoiceRequest(BaseModel):
    """Voice processing request."""
    farmer_id: str
    language: str = "hi-IN"
    network_quality: str = Field(
        default="fair",
        description="Network quality: excellent, good, fair, poor, very_poor"
    )
    farmer_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Farmer profile context for personalized responses"
    )


class VoiceResponse(BaseModel):
    """Voice processing response."""
    farmer_id: str
    transcribed_text: str
    response_text: str
    audio_url: str
    audio_base64: Optional[str] = None
    language: str
    confidence: float
    duration_seconds: float
    timestamp: datetime
    metadata: Dict[str, Any]


# Initialize voice processing chain
voice_chain = VoiceProcessingChain(
    llm=None,  # Will be initialized with Bedrock LLM in production
    enable_compression=True,
    enable_preprocessing=True
)


@router.post("/voice/process", response_model=VoiceResponse, status_code=status.HTTP_200_OK)
async def process_voice_message(
    voice_request: VoiceRequest,
    audio_file: UploadFile = File(...)
) -> VoiceResponse:
    """
    Process a voice message from a farmer.
    
    This endpoint handles the complete voice processing workflow:
    1. Audio preprocessing and noise reduction
    2. Speech-to-text transcription with language detection
    3. Query processing (with LLM if available)
    4. Text-to-speech synthesis
    5. Adaptive compression based on network quality
    """
    
    # Validate audio file
    if not audio_file.content_type or not audio_file.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid audio file format. Must be audio/* content type."
        )
    
    try:
        # Read audio data
        audio_data = await audio_file.read()
        
        # Determine audio format from content type
        audio_format = audio_file.content_type.split("/")[-1]
        if audio_format == "mpeg":
            audio_format = "mp3"
        
        # Map network quality string to enum
        try:
            network_quality = NetworkQuality(voice_request.network_quality.lower())
        except ValueError:
            network_quality = NetworkQuality.FAIR
        
        logger.info(
            f"Processing voice message: farmer_id={voice_request.farmer_id}, "
            f"language={voice_request.language}, network={network_quality.value}"
        )
        
        # Process voice query
        result = voice_chain.process_voice_query(
            audio_data=audio_data,
            audio_format=audio_format,
            farmer_context=voice_request.farmer_context,
            network_quality=network_quality
        )
        
        # Encode audio for response
        audio_base64 = base64.b64encode(result["audio"]["data"]).decode('utf-8')
        
        # Build response
        response = VoiceResponse(
            farmer_id=voice_request.farmer_id,
            transcribed_text=result["transcription"]["text"],
            response_text=result["response"]["text"],
            audio_url=result["audio"]["url"],
            audio_base64=audio_base64,
            language=result["transcription"]["language"],
            confidence=result["transcription"]["confidence"],
            duration_seconds=result["audio"]["duration"],
            timestamp=datetime.utcnow(),
            metadata={
                "audio_size_bytes": result["audio"]["size_bytes"],
                "audio_format": result["audio"]["format"],
                "network_quality": result["metadata"]["network_quality"],
                "preprocessing_enabled": result["metadata"]["preprocessing_enabled"],
                "compression_enabled": result["metadata"]["compression_enabled"],
                "alternatives": result["transcription"].get("alternatives", [])
            }
        )
        
        if "compression" in result["metadata"]:
            response.metadata["compression"] = result["metadata"]["compression"]
        
        logger.info(
            f"Voice processing completed: transcribed='{result['transcription']['text'][:50]}...', "
            f"confidence={result['transcription']['confidence']:.2f}"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Voice processing failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Voice processing failed: {str(e)}"
        )