"""
Speech-to-text processing using Amazon Transcribe.

This module handles multilingual speech recognition for Indian languages
including Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, and Punjabi.
"""

import logging
import time
import uuid
from typing import Dict, Optional, Tuple
from datetime import datetime
import io

import boto3
from botocore.exceptions import ClientError

from ..config import get_settings

logger = logging.getLogger(__name__)


class SpeechToTextProcessor:
    """
    Processes speech audio to text using Amazon Transcribe.
    
    Supports multiple Indian languages with dialect recognition and
    confidence scoring for error handling.
    """
    
    # Supported languages with their Transcribe language codes
    SUPPORTED_LANGUAGES = {
        "hi": "hi-IN",  # Hindi
        "ta": "ta-IN",  # Tamil
        "te": "te-IN",  # Telugu
        "bn": "bn-IN",  # Bengali
        "mr": "mr-IN",  # Marathi
        "gu": "gu-IN",  # Gujarati
        "pa": "pa-IN",  # Punjabi (Gurmukhi script)
        "en": "en-IN",  # English (Indian)
    }
    
    # Dialect variations for regional adaptation
    DIALECT_REGIONS = {
        "hi-IN": ["delhi", "mumbai", "lucknow", "jaipur"],
        "ta-IN": ["chennai", "madurai", "coimbatore"],
        "te-IN": ["hyderabad", "vijayawada", "visakhapatnam"],
        "bn-IN": ["kolkata", "dhaka"],
        "mr-IN": ["mumbai", "pune", "nagpur"],
        "gu-IN": ["ahmedabad", "surat", "vadodara"],
        "pa-IN": ["amritsar", "ludhiana", "chandigarh"],
    }
    
    def __init__(self):
        """Initialize the speech-to-text processor."""
        self.settings = get_settings()
        self.transcribe_client = boto3.client(
            'transcribe',
            region_name=self.settings.AWS_REGION
        )
        self.s3_client = boto3.client(
            's3',
            region_name=self.settings.AWS_REGION
        )
        self.bucket_name = self.settings.AUDIO_BUCKET_NAME
        
    def transcribe_audio(
        self,
        audio_data: bytes,
        language_code: str = "hi-IN",
        audio_format: str = "mp3",
        enable_dialect_detection: bool = True,
        min_confidence: float = 0.7
    ) -> Dict:
        """
        Transcribe audio to text using Amazon Transcribe.
        
        Args:
            audio_data: Raw audio bytes
            language_code: Language code (e.g., 'hi-IN', 'ta-IN')
            audio_format: Audio format ('mp3', 'wav', 'flac', 'ogg')
            enable_dialect_detection: Enable regional dialect recognition
            min_confidence: Minimum confidence threshold for transcription
            
        Returns:
            Dictionary containing:
                - transcribed_text: The transcribed text
                - confidence: Overall confidence score
                - language: Detected language code
                - dialect: Detected dialect/region (if enabled)
                - alternatives: Alternative transcriptions
                - word_timestamps: Word-level timing information
                
        Raises:
            ValueError: If language not supported or audio format invalid
            RuntimeError: If transcription fails
        """
        # Validate language
        if language_code not in self.SUPPORTED_LANGUAGES.values():
            raise ValueError(
                f"Unsupported language: {language_code}. "
                f"Supported languages: {list(self.SUPPORTED_LANGUAGES.values())}"
            )
        
        # Validate audio format
        valid_formats = ["mp3", "mp4", "wav", "flac", "ogg", "amr", "webm"]
        if audio_format.lower() not in valid_formats:
            raise ValueError(
                f"Unsupported audio format: {audio_format}. "
                f"Supported formats: {valid_formats}"
            )
        
        try:
            # Generate unique job name
            job_name = f"transcribe-{uuid.uuid4()}"
            
            # Upload audio to S3
            audio_key = f"transcribe-input/{job_name}.{audio_format}"
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=audio_key,
                Body=audio_data,
                ContentType=f"audio/{audio_format}"
            )
            
            audio_uri = f"s3://{self.bucket_name}/{audio_key}"
            
            # Start transcription job
            transcription_config = {
                "TranscriptionJobName": job_name,
                "LanguageCode": language_code,
                "MediaFormat": audio_format,
                "Media": {"MediaFileUri": audio_uri},
                "OutputBucketName": self.bucket_name,
                "OutputKey": f"transcribe-output/{job_name}.json",
                "Settings": {
                    "ShowAlternatives": True,
                    "MaxAlternatives": 3,
                    "ShowSpeakerLabels": False,
                    "ChannelIdentification": False,
                }
            }
            
            # Enable dialect identification if requested
            if enable_dialect_detection and language_code in self.DIALECT_REGIONS:
                transcription_config["IdentifyLanguage"] = False
                transcription_config["IdentifyMultipleLanguages"] = False
            
            logger.info(f"Starting transcription job: {job_name} for language: {language_code}")
            
            self.transcribe_client.start_transcription_job(**transcription_config)
            
            # Wait for job completion
            result = self._wait_for_transcription(job_name)
            
            # Clean up S3 objects
            self._cleanup_s3_objects(audio_key, f"transcribe-output/{job_name}.json")
            
            # Parse and validate results
            parsed_result = self._parse_transcription_result(
                result, 
                min_confidence,
                enable_dialect_detection
            )
            
            return parsed_result
            
        except ClientError as e:
            logger.error(f"AWS Transcribe error: {str(e)}")
            raise RuntimeError(f"Transcription failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during transcription: {str(e)}")
            raise RuntimeError(f"Transcription failed: {str(e)}")
    
    def transcribe_with_retry(
        self,
        audio_data: bytes,
        language_code: str = "hi-IN",
        audio_format: str = "mp3",
        max_attempts: int = 3,
        confidence_threshold: float = 0.7
    ) -> Dict:
        """
        Transcribe audio with automatic retry on low confidence.
        
        Implements error handling strategy with multiple attempts
        and progressively lower confidence thresholds.
        
        Args:
            audio_data: Raw audio bytes
            language_code: Language code
            audio_format: Audio format
            max_attempts: Maximum number of retry attempts
            confidence_threshold: Initial confidence threshold
            
        Returns:
            Transcription result dictionary
        """
        last_error = None
        best_result = None
        best_confidence = 0.0
        
        for attempt in range(max_attempts):
            try:
                # Adjust confidence threshold for retries
                current_threshold = confidence_threshold * (0.9 ** attempt)
                
                logger.info(
                    f"Transcription attempt {attempt + 1}/{max_attempts} "
                    f"with confidence threshold: {current_threshold:.2f}"
                )
                
                result = self.transcribe_audio(
                    audio_data=audio_data,
                    language_code=language_code,
                    audio_format=audio_format,
                    min_confidence=current_threshold
                )
                
                # Track best result
                if result["confidence"] > best_confidence:
                    best_confidence = result["confidence"]
                    best_result = result
                
                # Return if confidence is acceptable
                if result["confidence"] >= confidence_threshold:
                    logger.info(
                        f"Transcription successful with confidence: {result['confidence']:.2f}"
                    )
                    return result
                    
            except Exception as e:
                last_error = e
                logger.warning(f"Transcription attempt {attempt + 1} failed: {str(e)}")
                
                # Wait before retry (exponential backoff)
                if attempt < max_attempts - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
        
        # Return best result if available, otherwise raise error
        if best_result:
            logger.warning(
                f"Returning best result with confidence: {best_confidence:.2f} "
                f"(below threshold: {confidence_threshold:.2f})"
            )
            best_result["low_confidence_warning"] = True
            return best_result
        
        raise RuntimeError(
            f"Transcription failed after {max_attempts} attempts. "
            f"Last error: {str(last_error)}"
        )
    
    def detect_language(
        self,
        audio_data: bytes,
        audio_format: str = "mp3",
        candidate_languages: Optional[list] = None
    ) -> Tuple[str, float]:
        """
        Detect the language of spoken audio.
        
        Args:
            audio_data: Raw audio bytes
            audio_format: Audio format
            candidate_languages: List of candidate language codes to consider
            
        Returns:
            Tuple of (detected_language_code, confidence)
        """
        if candidate_languages is None:
            candidate_languages = list(self.SUPPORTED_LANGUAGES.values())
        
        try:
            job_name = f"lang-detect-{uuid.uuid4()}"
            audio_key = f"transcribe-input/{job_name}.{audio_format}"
            
            # Upload audio
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=audio_key,
                Body=audio_data,
                ContentType=f"audio/{audio_format}"
            )
            
            audio_uri = f"s3://{self.bucket_name}/{audio_key}"
            
            # Start language identification job
            self.transcribe_client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={"MediaFileUri": audio_uri},
                MediaFormat=audio_format,
                IdentifyLanguage=True,
                LanguageOptions=candidate_languages,
                OutputBucketName=self.bucket_name
            )
            
            # Wait for completion
            result = self._wait_for_transcription(job_name)
            
            # Extract language detection results
            if "LanguageCode" in result:
                detected_lang = result["LanguageCode"]
                confidence = result.get("IdentifiedLanguageScore", 0.0)
                
                logger.info(
                    f"Detected language: {detected_lang} "
                    f"with confidence: {confidence:.2f}"
                )
                
                # Cleanup
                self._cleanup_s3_objects(audio_key, f"transcribe-output/{job_name}.json")
                
                return detected_lang, confidence
            
            raise RuntimeError("Language detection failed: No language identified")
            
        except Exception as e:
            logger.error(f"Language detection error: {str(e)}")
            raise RuntimeError(f"Language detection failed: {str(e)}")
    
    def _wait_for_transcription(
        self,
        job_name: str,
        max_wait_time: int = 300,
        poll_interval: int = 5
    ) -> Dict:
        """
        Wait for transcription job to complete.
        
        Args:
            job_name: Transcription job name
            max_wait_time: Maximum time to wait in seconds
            poll_interval: Polling interval in seconds
            
        Returns:
            Transcription job result
        """
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            response = self.transcribe_client.get_transcription_job(
                TranscriptionJobName=job_name
            )
            
            status = response["TranscriptionJob"]["TranscriptionJobStatus"]
            
            if status == "COMPLETED":
                return response["TranscriptionJob"]
            elif status == "FAILED":
                failure_reason = response["TranscriptionJob"].get(
                    "FailureReason", "Unknown error"
                )
                raise RuntimeError(f"Transcription job failed: {failure_reason}")
            
            # Still in progress
            time.sleep(poll_interval)
        
        raise TimeoutError(
            f"Transcription job {job_name} did not complete within {max_wait_time}s"
        )
    
    def _parse_transcription_result(
        self,
        job_result: Dict,
        min_confidence: float,
        include_dialect: bool
    ) -> Dict:
        """
        Parse transcription job result into structured format.
        
        Args:
            job_result: Raw transcription job result
            min_confidence: Minimum confidence threshold
            include_dialect: Whether to include dialect information
            
        Returns:
            Parsed transcription result
        """
        # Get transcript URI
        transcript_uri = job_result.get("Transcript", {}).get("TranscriptFileUri")
        
        if not transcript_uri:
            raise RuntimeError("No transcript URI in job result")
        
        # Download transcript from S3
        # Extract bucket and key from URI
        uri_parts = transcript_uri.replace("s3://", "").split("/", 1)
        bucket = uri_parts[0]
        key = uri_parts[1]
        
        transcript_obj = self.s3_client.get_object(Bucket=bucket, Key=key)
        transcript_data = transcript_obj["Body"].read().decode("utf-8")
        
        import json
        transcript_json = json.loads(transcript_data)
        
        # Extract results
        results = transcript_json.get("results", {})
        transcripts = results.get("transcripts", [])
        items = results.get("items", [])
        
        if not transcripts:
            raise RuntimeError("No transcription results found")
        
        # Get primary transcript
        primary_transcript = transcripts[0].get("transcript", "")
        
        # Calculate average confidence
        confidences = [
            float(item.get("alternatives", [{}])[0].get("confidence", 0))
            for item in items
            if item.get("type") == "pronunciation"
        ]
        
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Get alternatives
        alternatives = []
        for transcript in transcripts[1:]:
            alternatives.append({
                "text": transcript.get("transcript", ""),
                "confidence": avg_confidence * 0.9  # Estimate lower confidence
            })
        
        # Extract word-level timestamps
        word_timestamps = []
        for item in items:
            if item.get("type") == "pronunciation":
                word_timestamps.append({
                    "word": item.get("alternatives", [{}])[0].get("content", ""),
                    "start_time": float(item.get("start_time", 0)),
                    "end_time": float(item.get("end_time", 0)),
                    "confidence": float(
                        item.get("alternatives", [{}])[0].get("confidence", 0)
                    )
                })
        
        result = {
            "transcribed_text": primary_transcript,
            "confidence": avg_confidence,
            "language": job_result.get("LanguageCode", "unknown"),
            "alternatives": alternatives,
            "word_timestamps": word_timestamps,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Add dialect information if available
        if include_dialect:
            result["dialect"] = self._detect_dialect(
                primary_transcript,
                result["language"]
            )
        
        # Add warning if confidence is low
        if avg_confidence < min_confidence:
            result["low_confidence_warning"] = True
            logger.warning(
                f"Transcription confidence ({avg_confidence:.2f}) "
                f"below threshold ({min_confidence:.2f})"
            )
        
        return result
    
    def _detect_dialect(self, text: str, language_code: str) -> Optional[str]:
        """
        Detect regional dialect from transcribed text.
        
        This is a placeholder for dialect detection logic.
        In production, this would use linguistic analysis or ML models.
        
        Args:
            text: Transcribed text
            language_code: Language code
            
        Returns:
            Detected dialect/region or None
        """
        # Placeholder - would implement actual dialect detection
        # using linguistic markers, vocabulary analysis, etc.
        return None
    
    def _cleanup_s3_objects(self, *keys: str):
        """
        Clean up temporary S3 objects.
        
        Args:
            keys: S3 object keys to delete
        """
        try:
            for key in keys:
                self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=key
                )
            logger.debug(f"Cleaned up S3 objects: {keys}")
        except Exception as e:
            logger.warning(f"Failed to cleanup S3 objects: {str(e)}")
