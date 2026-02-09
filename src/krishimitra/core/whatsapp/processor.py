"""
WhatsApp message processor for KrishiMitra.

This module handles processing of incoming WhatsApp messages including
text analysis, image processing for crop photos, voice message transcription,
and response generation using LangChain.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import io

from PIL import Image
import cv2
import numpy as np
import boto3
from botocore.exceptions import ClientError

from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_aws import ChatBedrock
from langchain.memory import ConversationBufferMemory

from ...core.config import get_settings
from .models import (
    WhatsAppIncomingMessage,
    WhatsAppOutgoingMessage,
    WhatsAppMessageType,
    WhatsAppMessageStatus
)
from .client import WhatsAppClient

logger = logging.getLogger(__name__)
settings = get_settings()


class WhatsAppMessageProcessor:
    """Processor for WhatsApp messages with AI integration."""
    
    def __init__(self):
        """Initialize message processor."""
        self.settings = settings
        self.whatsapp_client = WhatsAppClient()
        
        # Initialize AWS services
        self.s3_client = boto3.client('s3', region_name=settings.aws_region)
        self.transcribe_client = boto3.client('transcribe', region_name=settings.aws_region)
        self.translate_client = boto3.client('translate', region_name=settings.aws_region)
        
        # Initialize LangChain LLM
        self.llm = ChatBedrock(
            model_id=settings.bedrock_model_id,
            region_name=settings.bedrock_region,
            model_kwargs={
                "temperature": 0.7,
                "max_tokens": 2048
            }
        )
        
        # Conversation memory (in production, use DynamoDB)
        self.conversation_memories: Dict[str, ConversationBufferMemory] = {}
    
    async def process_message(self, message: WhatsAppIncomingMessage) -> Optional[WhatsAppOutgoingMessage]:
        """
        Process incoming WhatsApp message and generate response.
        
        Args:
            message: Incoming WhatsApp message
            
        Returns:
            Outgoing response message or None
        """
        try:
            logger.info(f"Processing {message.message_type.value} message from {message.from_number}")
            
            # Check if this is a group message
            # Group IDs typically end with @g.us
            is_group = message.from_number.endswith("@g.us") if message.from_number else False
            
            if is_group:
                # Handle group message
                from .group_chat import GroupChatManager
                group_manager = GroupChatManager()
                return await group_manager.process_group_message(message, message.from_number)
            
            # Route to appropriate handler based on message type
            if message.message_type == WhatsAppMessageType.TEXT:
                return await self.process_text_message(message)
            
            elif message.message_type == WhatsAppMessageType.IMAGE:
                return await self.process_image_message(message)
            
            elif message.message_type == WhatsAppMessageType.AUDIO:
                return await self.process_audio_message(message)
            
            elif message.message_type == WhatsAppMessageType.LOCATION:
                return await self.process_location_message(message)
            
            else:
                logger.warning(f"Unsupported message type: {message.message_type}")
                return await self._create_text_response(
                    message.from_number,
                    "क्षमा करें, इस प्रकार का संदेश अभी समर्थित नहीं है। कृपया टेक्स्ट, छवि या ऑडियो संदेश भेजें।",
                    message.message_id
                )
        
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return await self._create_error_response(message.from_number, message.message_id)
    
    async def process_text_message(self, message: WhatsAppIncomingMessage) -> WhatsAppOutgoingMessage:
        """
        Process text message using LangChain for analysis and response generation.
        
        Args:
            message: Incoming text message
            
        Returns:
            Response message
        """
        text = message.text or ""
        from_number = message.from_number
        
        logger.info(f"Processing text: {text[:100]}...")
        
        # Get or create conversation memory
        memory = self._get_conversation_memory(from_number)
        
        # Create LangChain prompt for agricultural advisory
        prompt = PromptTemplate(
            input_variables=["farmer_query", "chat_history"],
            template="""You are KrishiMitra (कृषि मित्र), an AI agricultural advisor for Indian farmers.
You provide helpful, accurate, and practical farming advice in a friendly manner.

Chat History:
{chat_history}

Farmer's Question: {farmer_query}

Provide a helpful response in Hindi (or the farmer's preferred language) that:
1. Addresses their specific question or concern
2. Provides actionable agricultural advice
3. Is concise and easy to understand (max 300 words)
4. Uses simple language suitable for rural farmers
5. Includes specific recommendations when applicable

Response:"""
        )
        
        # Create LangChain chain
        chain = LLMChain(
            llm=self.llm,
            prompt=prompt,
            memory=memory,
            verbose=True
        )
        
        try:
            # Generate response using LangChain
            response = await chain.arun(farmer_query=text)
            
            # Clean up response
            response_text = response.strip()
            
            # Ensure response fits WhatsApp limits (4096 characters)
            if len(response_text) > 4000:
                response_text = response_text[:3997] + "..."
            
            logger.info(f"Generated response: {response_text[:100]}...")
            
            return await self._create_text_response(
                from_number,
                response_text,
                message.message_id
            )
        
        except Exception as e:
            logger.error(f"Error generating text response: {e}", exc_info=True)
            return await self._create_error_response(from_number, message.message_id)
    
    async def process_image_message(self, message: WhatsAppIncomingMessage) -> WhatsAppOutgoingMessage:
        """
        Process image message for crop photo analysis using PIL/OpenCV.
        
        Args:
            message: Incoming image message
            
        Returns:
            Response message with analysis results
        """
        if not message.media or not message.media.id:
            return await self._create_text_response(
                message.from_number,
                "क्षमा करें, छवि प्राप्त नहीं हो सकी। कृपया पुनः प्रयास करें।",
                message.message_id
            )
        
        try:
            # Download image from WhatsApp
            image_bytes = await self.whatsapp_client.download_media(message.media.id)
            
            if not image_bytes:
                return await self._create_text_response(
                    message.from_number,
                    "क्षमा करें, छवि डाउनलोड नहीं हो सकी। कृपया पुनः प्रयास करें।",
                    message.message_id
                )
            
            # Analyze image
            analysis_result = await self._analyze_crop_image(image_bytes)
            
            # Generate response based on analysis
            response_text = self._format_image_analysis_response(analysis_result)
            
            return await self._create_text_response(
                message.from_number,
                response_text,
                message.message_id
            )
        
        except Exception as e:
            logger.error(f"Error processing image: {e}", exc_info=True)
            return await self._create_text_response(
                message.from_number,
                "क्षमा करें, छवि विश्लेषण में त्रुटि हुई। कृपया पुनः प्रयास करें।",
                message.message_id
            )
    
    async def process_audio_message(self, message: WhatsAppIncomingMessage) -> WhatsAppOutgoingMessage:
        """
        Process audio message with transcription and response generation.
        
        Args:
            message: Incoming audio message
            
        Returns:
            Response message
        """
        if not message.media or not message.media.id:
            return await self._create_text_response(
                message.from_number,
                "क्षमा करें, ऑडियो प्राप्त नहीं हो सका। कृपया पुनः प्रयास करें।",
                message.message_id
            )
        
        try:
            # Download audio from WhatsApp
            audio_bytes = await self.whatsapp_client.download_media(message.media.id)
            
            if not audio_bytes:
                return await self._create_text_response(
                    message.from_number,
                    "क्षमा करें, ऑडियो डाउनलोड नहीं हो सका। कृपया पुनः प्रयास करें।",
                    message.message_id
                )
            
            # Transcribe audio
            transcribed_text = await self._transcribe_audio(audio_bytes, message.from_number)
            
            if not transcribed_text:
                return await self._create_text_response(
                    message.from_number,
                    "क्षमा करें, ऑडियो को समझने में समस्या हुई। कृपया स्पष्ट रूप से बोलें और पुनः प्रयास करें।",
                    message.message_id
                )
            
            # Process transcribed text as a text message
            text_message = WhatsAppIncomingMessage(
                message_id=message.message_id,
                from_number=message.from_number,
                timestamp=message.timestamp,
                message_type=WhatsAppMessageType.TEXT,
                text=transcribed_text
            )
            
            return await self.process_text_message(text_message)
        
        except Exception as e:
            logger.error(f"Error processing audio: {e}", exc_info=True)
            return await self._create_text_response(
                message.from_number,
                "क्षमा करें, ऑडियो प्रोसेसिंग में त्रुटि हुई। कृपया पुनः प्रयास करें।",
                message.message_id
            )
    
    async def process_location_message(self, message: WhatsAppIncomingMessage) -> WhatsAppOutgoingMessage:
        """
        Process location message for location-based recommendations.
        
        Args:
            message: Incoming location message
            
        Returns:
            Response message
        """
        if not message.location:
            return await self._create_text_response(
                message.from_number,
                "क्षमा करें, स्थान प्राप्त नहीं हो सका।",
                message.message_id
            )
        
        location = message.location
        
        response_text = f"""आपका स्थान प्राप्त हुआ:
अक्षांश: {location.latitude}
देशांतर: {location.longitude}

हम आपके स्थान के आधार पर मौसम, मिट्टी और बाजार की जानकारी प्रदान कर सकते हैं। 
कृपया बताएं कि आप क्या जानना चाहते हैं?"""
        
        return await self._create_text_response(
            message.from_number,
            response_text,
            message.message_id
        )
    
    async def _analyze_crop_image(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Analyze crop image using PIL and OpenCV.
        
        Args:
            image_bytes: Image file bytes
            
        Returns:
            Analysis results dictionary
        """
        try:
            # Load image with PIL
            image = Image.open(io.BytesIO(image_bytes))
            
            # Convert to OpenCV format
            image_array = np.array(image)
            if len(image_array.shape) == 2:
                # Grayscale image
                image_cv = image_array
            else:
                # Color image - convert RGB to BGR for OpenCV
                image_cv = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
            
            # Basic image analysis
            height, width = image_cv.shape[:2]
            
            # Calculate average color (simple health indicator)
            if len(image_cv.shape) == 3:
                avg_color = image_cv.mean(axis=(0, 1))
                green_ratio = avg_color[1] / (avg_color.sum() + 1e-6)
            else:
                green_ratio = 0.33
            
            # Detect edges (can indicate disease or pest damage)
            gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY) if len(image_cv.shape) == 3 else image_cv
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / (height * width)
            
            # Simple health assessment
            if green_ratio > 0.4 and edge_density < 0.1:
                health_status = "स्वस्थ (Healthy)"
                confidence = 0.7
            elif green_ratio > 0.3:
                health_status = "सामान्य (Normal)"
                confidence = 0.6
            else:
                health_status = "चिंताजनक (Concerning)"
                confidence = 0.5
            
            return {
                "health_status": health_status,
                "confidence": confidence,
                "green_ratio": float(green_ratio),
                "edge_density": float(edge_density),
                "image_size": (width, height),
                "analysis_type": "basic_visual"
            }
        
        except Exception as e:
            logger.error(f"Error analyzing image: {e}", exc_info=True)
            return {
                "health_status": "विश्लेषण विफल (Analysis Failed)",
                "confidence": 0.0,
                "error": str(e)
            }
    
    def _format_image_analysis_response(self, analysis: Dict[str, Any]) -> str:
        """Format image analysis results into response text."""
        health_status = analysis.get("health_status", "अज्ञात")
        confidence = analysis.get("confidence", 0.0)
        
        response = f"""🌾 फसल छवि विश्लेषण:

स्थिति: {health_status}
विश्वास स्तर: {confidence*100:.0f}%

"""
        
        if "error" in analysis:
            response += "नोट: विस्तृत विश्लेषण उपलब्ध नहीं है।\n"
        else:
            green_ratio = analysis.get("green_ratio", 0)
            if green_ratio > 0.4:
                response += "✅ फसल में अच्छी हरियाली दिख रही है।\n"
            elif green_ratio > 0.3:
                response += "⚠️ फसल की हरियाली सामान्य है।\n"
            else:
                response += "❌ फसल में हरियाली कम दिख रही है।\n"
        
        response += "\nअधिक सटीक विश्लेषण के लिए, कृपया:\n"
        response += "1. दिन के उजाले में फोटो लें\n"
        response += "2. पत्तियों का क्लोज-अप लें\n"
        response += "3. प्रभावित क्षेत्र को स्पष्ट रूप से दिखाएं\n"
        
        return response
    
    async def _transcribe_audio(self, audio_bytes: bytes, phone_number: str) -> Optional[str]:
        """
        Transcribe audio using Amazon Transcribe.
        
        Args:
            audio_bytes: Audio file bytes
            phone_number: Phone number for unique job naming
            
        Returns:
            Transcribed text or None
        """
        try:
            # Upload audio to S3
            audio_key = f"whatsapp_audio/{phone_number}/{datetime.utcnow().timestamp()}.ogg"
            self.s3_client.put_object(
                Bucket=settings.audio_bucket_name,
                Key=audio_key,
                Body=audio_bytes
            )
            
            # Start transcription job
            job_name = f"whatsapp_{phone_number}_{int(datetime.utcnow().timestamp())}"
            
            self.transcribe_client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={
                    'MediaFileUri': f"s3://{settings.audio_bucket_name}/{audio_key}"
                },
                MediaFormat='ogg',
                LanguageCode='hi-IN',  # Default to Hindi, can be made dynamic
                Settings={
                    'ShowSpeakerLabels': False
                }
            )
            
            # Wait for transcription to complete (simplified - in production use async polling)
            import time
            max_wait = 60  # 60 seconds max
            wait_time = 0
            
            while wait_time < max_wait:
                response = self.transcribe_client.get_transcription_job(
                    TranscriptionJobName=job_name
                )
                
                status = response['TranscriptionJob']['TranscriptionJobStatus']
                
                if status == 'COMPLETED':
                    # Get transcript
                    transcript_uri = response['TranscriptionJob']['Transcript']['TranscriptFileUri']
                    
                    # Download and parse transcript (simplified)
                    import httpx
                    async with httpx.AsyncClient() as client:
                        transcript_response = await client.get(transcript_uri)
                        transcript_data = transcript_response.json()
                        
                        transcribed_text = transcript_data['results']['transcripts'][0]['transcript']
                        return transcribed_text
                
                elif status == 'FAILED':
                    logger.error(f"Transcription job failed: {job_name}")
                    return None
                
                time.sleep(2)
                wait_time += 2
            
            logger.warning(f"Transcription job timed out: {job_name}")
            return None
        
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}", exc_info=True)
            return None
    
    async def _create_text_response(
        self,
        to_number: str,
        text: str,
        reply_to_message_id: Optional[str] = None
    ) -> WhatsAppOutgoingMessage:
        """Create a text response message."""
        return WhatsAppOutgoingMessage(
            to_number=to_number,
            message_type=WhatsAppMessageType.TEXT,
            text=text,
            context_message_id=reply_to_message_id,
            priority=3  # High priority for responses
        )
    
    async def _create_error_response(
        self,
        to_number: str,
        reply_to_message_id: Optional[str] = None
    ) -> WhatsAppOutgoingMessage:
        """Create an error response message."""
        error_text = """क्षमा करें, आपके संदेश को प्रोसेस करने में समस्या हुई। 

कृपया पुनः प्रयास करें या हमारी सहायता टीम से संपर्क करें।

धन्यवाद,
कृषि मित्र टीम"""
        
        return await self._create_text_response(to_number, error_text, reply_to_message_id)
    
    def _get_conversation_memory(self, phone_number: str) -> ConversationBufferMemory:
        """Get or create conversation memory for a phone number."""
        if phone_number not in self.conversation_memories:
            self.conversation_memories[phone_number] = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                max_token_limit=1000
            )
        
        return self.conversation_memories[phone_number]
    
    async def close(self):
        """Close connections."""
        await self.whatsapp_client.close()
