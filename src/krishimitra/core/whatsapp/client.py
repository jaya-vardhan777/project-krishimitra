"""
WhatsApp Business API client for KrishiMitra.

This module provides a client for interacting with WhatsApp Business API
through AWS End User Messaging Social service.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

import httpx
import boto3
from botocore.exceptions import ClientError

from ...core.config import get_settings
from .models import (
    WhatsAppOutgoingMessage,
    WhatsAppMessageStatus,
    WhatsAppMessageType,
    WhatsAppMessageDeliveryReport
)

logger = logging.getLogger(__name__)
settings = get_settings()


class WhatsAppClient:
    """Client for WhatsApp Business API operations."""
    
    def __init__(self):
        """Initialize WhatsApp client."""
        self.settings = settings
        self.access_token = settings.whatsapp_access_token
        self.phone_number_id = settings.whatsapp_phone_number_id
        self.base_url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}"
        
        # Initialize AWS End User Messaging Social client if available
        try:
            self.social_messaging_client = boto3.client(
                'socialmessaging',
                region_name=settings.aws_region
            )
            logger.info("AWS End User Messaging Social client initialized")
        except Exception as e:
            logger.warning(f"Could not initialize AWS Social Messaging client: {e}")
            self.social_messaging_client = None
        
        # HTTP client for direct API calls
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
        )
    
    async def send_text_message(
        self,
        to_number: str,
        text: str,
        context_message_id: Optional[str] = None
    ) -> WhatsAppOutgoingMessage:
        """
        Send a text message via WhatsApp.
        
        Args:
            to_number: Recipient phone number (with country code)
            text: Message text (max 4096 characters)
            context_message_id: Optional message ID to reply to
            
        Returns:
            WhatsAppOutgoingMessage with delivery tracking
        """
        message = WhatsAppOutgoingMessage(
            to_number=to_number,
            message_type=WhatsAppMessageType.TEXT,
            text=text,
            context_message_id=context_message_id
        )
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "text",
            "text": {"body": text}
        }
        
        if context_message_id:
            payload["context"] = {"message_id": context_message_id}
        
        try:
            response = await self.http_client.post(
                f"{self.base_url}/messages",
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            message.whatsapp_message_id = result.get("messages", [{}])[0].get("id")
            message.status = WhatsAppMessageStatus.SENT
            message.sent_at = datetime.utcnow()
            
            logger.info(f"Text message sent to {to_number}: {message.whatsapp_message_id}")
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to send text message to {to_number}: {e}")
            message.status = WhatsAppMessageStatus.FAILED
            message.failed_at = datetime.utcnow()
            message.error_message = str(e)
            
        return message
    
    async def send_image_message(
        self,
        to_number: str,
        image_url: Optional[str] = None,
        image_id: Optional[str] = None,
        caption: Optional[str] = None,
        context_message_id: Optional[str] = None
    ) -> WhatsAppOutgoingMessage:
        """
        Send an image message via WhatsApp.
        
        Args:
            to_number: Recipient phone number
            image_url: URL of image to send
            image_id: WhatsApp media ID (alternative to URL)
            caption: Optional image caption
            context_message_id: Optional message ID to reply to
            
        Returns:
            WhatsAppOutgoingMessage with delivery tracking
        """
        message = WhatsAppOutgoingMessage(
            to_number=to_number,
            message_type=WhatsAppMessageType.IMAGE,
            media_url=image_url,
            media_id=image_id,
            caption=caption,
            context_message_id=context_message_id
        )
        
        image_data = {}
        if image_id:
            image_data["id"] = image_id
        elif image_url:
            image_data["link"] = image_url
        else:
            raise ValueError("Either image_url or image_id must be provided")
        
        if caption:
            image_data["caption"] = caption
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "image",
            "image": image_data
        }
        
        if context_message_id:
            payload["context"] = {"message_id": context_message_id}
        
        try:
            response = await self.http_client.post(
                f"{self.base_url}/messages",
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            message.whatsapp_message_id = result.get("messages", [{}])[0].get("id")
            message.status = WhatsAppMessageStatus.SENT
            message.sent_at = datetime.utcnow()
            
            logger.info(f"Image message sent to {to_number}: {message.whatsapp_message_id}")
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to send image message to {to_number}: {e}")
            message.status = WhatsAppMessageStatus.FAILED
            message.failed_at = datetime.utcnow()
            message.error_message = str(e)
            
        return message
    
    async def send_audio_message(
        self,
        to_number: str,
        audio_url: Optional[str] = None,
        audio_id: Optional[str] = None,
        context_message_id: Optional[str] = None
    ) -> WhatsAppOutgoingMessage:
        """
        Send an audio message via WhatsApp.
        
        Args:
            to_number: Recipient phone number
            audio_url: URL of audio file to send
            audio_id: WhatsApp media ID (alternative to URL)
            context_message_id: Optional message ID to reply to
            
        Returns:
            WhatsAppOutgoingMessage with delivery tracking
        """
        message = WhatsAppOutgoingMessage(
            to_number=to_number,
            message_type=WhatsAppMessageType.AUDIO,
            media_url=audio_url,
            media_id=audio_id,
            context_message_id=context_message_id
        )
        
        audio_data = {}
        if audio_id:
            audio_data["id"] = audio_id
        elif audio_url:
            audio_data["link"] = audio_url
        else:
            raise ValueError("Either audio_url or audio_id must be provided")
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "audio",
            "audio": audio_data
        }
        
        if context_message_id:
            payload["context"] = {"message_id": context_message_id}
        
        try:
            response = await self.http_client.post(
                f"{self.base_url}/messages",
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            message.whatsapp_message_id = result.get("messages", [{}])[0].get("id")
            message.status = WhatsAppMessageStatus.SENT
            message.sent_at = datetime.utcnow()
            
            logger.info(f"Audio message sent to {to_number}: {message.whatsapp_message_id}")
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to send audio message to {to_number}: {e}")
            message.status = WhatsAppMessageStatus.FAILED
            message.failed_at = datetime.utcnow()
            message.error_message = str(e)
            
        return message
    
    async def send_document_message(
        self,
        to_number: str,
        document_url: Optional[str] = None,
        document_id: Optional[str] = None,
        filename: Optional[str] = None,
        caption: Optional[str] = None,
        context_message_id: Optional[str] = None
    ) -> WhatsAppOutgoingMessage:
        """
        Send a document message via WhatsApp.
        
        Args:
            to_number: Recipient phone number
            document_url: URL of document to send
            document_id: WhatsApp media ID (alternative to URL)
            filename: Document filename
            caption: Optional document caption
            context_message_id: Optional message ID to reply to
            
        Returns:
            WhatsAppOutgoingMessage with delivery tracking
        """
        message = WhatsAppOutgoingMessage(
            to_number=to_number,
            message_type=WhatsAppMessageType.DOCUMENT,
            media_url=document_url,
            media_id=document_id,
            filename=filename,
            caption=caption,
            context_message_id=context_message_id
        )
        
        document_data = {}
        if document_id:
            document_data["id"] = document_id
        elif document_url:
            document_data["link"] = document_url
        else:
            raise ValueError("Either document_url or document_id must be provided")
        
        if filename:
            document_data["filename"] = filename
        if caption:
            document_data["caption"] = caption
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "document",
            "document": document_data
        }
        
        if context_message_id:
            payload["context"] = {"message_id": context_message_id}
        
        try:
            response = await self.http_client.post(
                f"{self.base_url}/messages",
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            message.whatsapp_message_id = result.get("messages", [{}])[0].get("id")
            message.status = WhatsAppMessageStatus.SENT
            message.sent_at = datetime.utcnow()
            
            logger.info(f"Document message sent to {to_number}: {message.whatsapp_message_id}")
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to send document message to {to_number}: {e}")
            message.status = WhatsAppMessageStatus.FAILED
            message.failed_at = datetime.utcnow()
            message.error_message = str(e)
            
        return message
    
    async def send_location_message(
        self,
        to_number: str,
        latitude: float,
        longitude: float,
        name: Optional[str] = None,
        address: Optional[str] = None,
        context_message_id: Optional[str] = None
    ) -> WhatsAppOutgoingMessage:
        """
        Send a location message via WhatsApp.
        
        Args:
            to_number: Recipient phone number
            latitude: Location latitude
            longitude: Location longitude
            name: Location name
            address: Location address
            context_message_id: Optional message ID to reply to
            
        Returns:
            WhatsAppOutgoingMessage with delivery tracking
        """
        from .models import WhatsAppLocation
        
        location = WhatsAppLocation(
            latitude=latitude,
            longitude=longitude,
            name=name,
            address=address
        )
        
        message = WhatsAppOutgoingMessage(
            to_number=to_number,
            message_type=WhatsAppMessageType.LOCATION,
            location=location,
            context_message_id=context_message_id
        )
        
        location_data = {
            "latitude": latitude,
            "longitude": longitude
        }
        if name:
            location_data["name"] = name
        if address:
            location_data["address"] = address
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "location",
            "location": location_data
        }
        
        if context_message_id:
            payload["context"] = {"message_id": context_message_id}
        
        try:
            response = await self.http_client.post(
                f"{self.base_url}/messages",
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            message.whatsapp_message_id = result.get("messages", [{}])[0].get("id")
            message.status = WhatsAppMessageStatus.SENT
            message.sent_at = datetime.utcnow()
            
            logger.info(f"Location message sent to {to_number}: {message.whatsapp_message_id}")
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to send location message to {to_number}: {e}")
            message.status = WhatsAppMessageStatus.FAILED
            message.failed_at = datetime.utcnow()
            message.error_message = str(e)
            
        return message
    
    async def mark_message_as_read(self, message_id: str) -> bool:
        """
        Mark a message as read.
        
        Args:
            message_id: WhatsApp message ID to mark as read
            
        Returns:
            True if successful, False otherwise
        """
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        
        try:
            response = await self.http_client.post(
                f"{self.base_url}/messages",
                json=payload
            )
            response.raise_for_status()
            logger.info(f"Message {message_id} marked as read")
            return True
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to mark message {message_id} as read: {e}")
            return False
    
    async def download_media(self, media_id: str) -> Optional[bytes]:
        """
        Download media file from WhatsApp.
        
        Args:
            media_id: WhatsApp media ID
            
        Returns:
            Media file bytes or None if failed
        """
        try:
            # First, get media URL
            response = await self.http_client.get(
                f"https://graph.facebook.com/v18.0/{media_id}"
            )
            response.raise_for_status()
            
            media_info = response.json()
            media_url = media_info.get("url")
            
            if not media_url:
                logger.error(f"No URL found for media {media_id}")
                return None
            
            # Download media
            media_response = await self.http_client.get(media_url)
            media_response.raise_for_status()
            
            logger.info(f"Downloaded media {media_id}")
            return media_response.content
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to download media {media_id}: {e}")
            return None
    
    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()
