"""
LangChain tools for WhatsApp message processing in KrishiMitra.

This module provides LangChain tools that can be used by AI agents
to interact with WhatsApp Business API.
"""

import logging
from typing import Optional, Dict, Any, Type
from datetime import datetime

from langchain.tools import BaseTool
from langchain.pydantic_v1 import BaseModel as LangChainBaseModel, Field

from .client import WhatsAppClient
from .queue import WhatsAppMessageQueue
from .models import (
    WhatsAppOutgoingMessage,
    WhatsAppMessageType,
    WhatsAppMessageStatus
)

logger = logging.getLogger(__name__)


# Input schemas for LangChain tools
class SendTextMessageInput(LangChainBaseModel):
    """Input for sending text message."""
    to_number: str = Field(description="Recipient phone number with country code (e.g., +919876543210)")
    text: str = Field(description="Message text to send (max 4096 characters)")
    reply_to_message_id: Optional[str] = Field(default=None, description="Optional message ID to reply to")
    priority: int = Field(default=5, description="Message priority (1=highest, 10=lowest)")


class SendImageMessageInput(LangChainBaseModel):
    """Input for sending image message."""
    to_number: str = Field(description="Recipient phone number with country code")
    image_url: str = Field(description="URL of image to send")
    caption: Optional[str] = Field(default=None, description="Optional image caption")
    reply_to_message_id: Optional[str] = Field(default=None, description="Optional message ID to reply to")
    priority: int = Field(default=5, description="Message priority")


class SendAudioMessageInput(LangChainBaseModel):
    """Input for sending audio message."""
    to_number: str = Field(description="Recipient phone number with country code")
    audio_url: str = Field(description="URL of audio file to send")
    reply_to_message_id: Optional[str] = Field(default=None, description="Optional message ID to reply to")
    priority: int = Field(default=5, description="Message priority")


class SendLocationMessageInput(LangChainBaseModel):
    """Input for sending location message."""
    to_number: str = Field(description="Recipient phone number with country code")
    latitude: float = Field(description="Location latitude")
    longitude: float = Field(description="Location longitude")
    name: Optional[str] = Field(default=None, description="Location name")
    address: Optional[str] = Field(default=None, description="Location address")
    reply_to_message_id: Optional[str] = Field(default=None, description="Optional message ID to reply to")
    priority: int = Field(default=5, description="Message priority")


class GetMessageStatusInput(LangChainBaseModel):
    """Input for getting message status."""
    message_id: str = Field(description="Internal message ID to check status")


class MarkMessageReadInput(LangChainBaseModel):
    """Input for marking message as read."""
    whatsapp_message_id: str = Field(description="WhatsApp message ID to mark as read")


# LangChain tools
class SendWhatsAppTextMessageTool(BaseTool):
    """Tool for sending WhatsApp text messages."""
    
    name: str = "send_whatsapp_text_message"
    description: str = (
        "Send a text message to a farmer via WhatsApp. "
        "Use this to respond to farmer queries, provide recommendations, "
        "or send agricultural advice. The message will be queued and sent asynchronously."
    )
    args_schema: Type[LangChainBaseModel] = SendTextMessageInput
    
    def _run(
        self,
        to_number: str,
        text: str,
        reply_to_message_id: Optional[str] = None,
        priority: int = 5
    ) -> Dict[str, Any]:
        """Send WhatsApp text message."""
        try:
            # Create message
            message = WhatsAppOutgoingMessage(
                to_number=to_number,
                message_type=WhatsAppMessageType.TEXT,
                text=text,
                context_message_id=reply_to_message_id,
                priority=priority
            )
            
            # Enqueue message
            queue = WhatsAppMessageQueue()
            task_id = queue.enqueue_outgoing_message(message)
            
            logger.info(f"Queued WhatsApp text message to {to_number}: {task_id}")
            
            return {
                "success": True,
                "message_id": message.message_id,
                "task_id": task_id,
                "status": "queued",
                "to_number": to_number
            }
            
        except Exception as e:
            logger.error(f"Failed to send WhatsApp text message: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _arun(
        self,
        to_number: str,
        text: str,
        reply_to_message_id: Optional[str] = None,
        priority: int = 5
    ) -> Dict[str, Any]:
        """Async version of send WhatsApp text message."""
        return self._run(to_number, text, reply_to_message_id, priority)


class SendWhatsAppImageMessageTool(BaseTool):
    """Tool for sending WhatsApp image messages."""
    
    name: str = "send_whatsapp_image_message"
    description: str = (
        "Send an image to a farmer via WhatsApp. "
        "Use this to share crop health analysis results, pest identification images, "
        "or visual agricultural guidance. Provide the image URL and optional caption."
    )
    args_schema: Type[LangChainBaseModel] = SendImageMessageInput
    
    def _run(
        self,
        to_number: str,
        image_url: str,
        caption: Optional[str] = None,
        reply_to_message_id: Optional[str] = None,
        priority: int = 5
    ) -> Dict[str, Any]:
        """Send WhatsApp image message."""
        try:
            # Create message
            message = WhatsAppOutgoingMessage(
                to_number=to_number,
                message_type=WhatsAppMessageType.IMAGE,
                media_url=image_url,
                caption=caption,
                context_message_id=reply_to_message_id,
                priority=priority
            )
            
            # Enqueue message
            queue = WhatsAppMessageQueue()
            task_id = queue.enqueue_outgoing_message(message)
            
            logger.info(f"Queued WhatsApp image message to {to_number}: {task_id}")
            
            return {
                "success": True,
                "message_id": message.message_id,
                "task_id": task_id,
                "status": "queued",
                "to_number": to_number,
                "image_url": image_url
            }
            
        except Exception as e:
            logger.error(f"Failed to send WhatsApp image message: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _arun(
        self,
        to_number: str,
        image_url: str,
        caption: Optional[str] = None,
        reply_to_message_id: Optional[str] = None,
        priority: int = 5
    ) -> Dict[str, Any]:
        """Async version of send WhatsApp image message."""
        return self._run(to_number, image_url, caption, reply_to_message_id, priority)


class SendWhatsAppAudioMessageTool(BaseTool):
    """Tool for sending WhatsApp audio messages."""
    
    name: str = "send_whatsapp_audio_message"
    description: str = (
        "Send an audio message to a farmer via WhatsApp. "
        "Use this to provide voice responses in the farmer's preferred language, "
        "especially useful for farmers with low literacy. Provide the audio file URL."
    )
    args_schema: Type[LangChainBaseModel] = SendAudioMessageInput
    
    def _run(
        self,
        to_number: str,
        audio_url: str,
        reply_to_message_id: Optional[str] = None,
        priority: int = 5
    ) -> Dict[str, Any]:
        """Send WhatsApp audio message."""
        try:
            # Create message
            message = WhatsAppOutgoingMessage(
                to_number=to_number,
                message_type=WhatsAppMessageType.AUDIO,
                media_url=audio_url,
                context_message_id=reply_to_message_id,
                priority=priority
            )
            
            # Enqueue message
            queue = WhatsAppMessageQueue()
            task_id = queue.enqueue_outgoing_message(message)
            
            logger.info(f"Queued WhatsApp audio message to {to_number}: {task_id}")
            
            return {
                "success": True,
                "message_id": message.message_id,
                "task_id": task_id,
                "status": "queued",
                "to_number": to_number,
                "audio_url": audio_url
            }
            
        except Exception as e:
            logger.error(f"Failed to send WhatsApp audio message: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _arun(
        self,
        to_number: str,
        audio_url: str,
        reply_to_message_id: Optional[str] = None,
        priority: int = 5
    ) -> Dict[str, Any]:
        """Async version of send WhatsApp audio message."""
        return self._run(to_number, audio_url, reply_to_message_id, priority)


class SendWhatsAppLocationMessageTool(BaseTool):
    """Tool for sending WhatsApp location messages."""
    
    name: str = "send_whatsapp_location_message"
    description: str = (
        "Send a location to a farmer via WhatsApp. "
        "Use this to share locations of nearby markets, agricultural offices, "
        "or recommended service providers. Provide latitude, longitude, and optional name/address."
    )
    args_schema: Type[LangChainBaseModel] = SendLocationMessageInput
    
    def _run(
        self,
        to_number: str,
        latitude: float,
        longitude: float,
        name: Optional[str] = None,
        address: Optional[str] = None,
        reply_to_message_id: Optional[str] = None,
        priority: int = 5
    ) -> Dict[str, Any]:
        """Send WhatsApp location message."""
        try:
            from .models import WhatsAppLocation
            
            # Create location
            location = WhatsAppLocation(
                latitude=latitude,
                longitude=longitude,
                name=name,
                address=address
            )
            
            # Create message
            message = WhatsAppOutgoingMessage(
                to_number=to_number,
                message_type=WhatsAppMessageType.LOCATION,
                location=location,
                context_message_id=reply_to_message_id,
                priority=priority
            )
            
            # Enqueue message
            queue = WhatsAppMessageQueue()
            task_id = queue.enqueue_outgoing_message(message)
            
            logger.info(f"Queued WhatsApp location message to {to_number}: {task_id}")
            
            return {
                "success": True,
                "message_id": message.message_id,
                "task_id": task_id,
                "status": "queued",
                "to_number": to_number,
                "location": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "name": name,
                    "address": address
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to send WhatsApp location message: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _arun(
        self,
        to_number: str,
        latitude: float,
        longitude: float,
        name: Optional[str] = None,
        address: Optional[str] = None,
        reply_to_message_id: Optional[str] = None,
        priority: int = 5
    ) -> Dict[str, Any]:
        """Async version of send WhatsApp location message."""
        return self._run(to_number, latitude, longitude, name, address, reply_to_message_id, priority)


class GetWhatsAppMessageStatusTool(BaseTool):
    """Tool for checking WhatsApp message status."""
    
    name: str = "get_whatsapp_message_status"
    description: str = (
        "Check the delivery status of a WhatsApp message. "
        "Use this to verify if a message was sent, delivered, or read by the farmer. "
        "Provide the internal message ID."
    )
    args_schema: Type[LangChainBaseModel] = GetMessageStatusInput
    
    def _run(self, message_id: str) -> Dict[str, Any]:
        """Get WhatsApp message status."""
        try:
            queue = WhatsAppMessageQueue()
            status = queue.get_message_status(message_id)
            
            if not status:
                return {
                    "success": False,
                    "error": "Message not found"
                }
            
            return {
                "success": True,
                "message_id": message_id,
                "status": status
            }
            
        except Exception as e:
            logger.error(f"Failed to get message status: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _arun(self, message_id: str) -> Dict[str, Any]:
        """Async version of get WhatsApp message status."""
        return self._run(message_id)


class MarkWhatsAppMessageReadTool(BaseTool):
    """Tool for marking WhatsApp messages as read."""
    
    name: str = "mark_whatsapp_message_read"
    description: str = (
        "Mark a WhatsApp message as read. "
        "Use this to acknowledge receipt of a farmer's message. "
        "Provide the WhatsApp message ID (not the internal message ID)."
    )
    args_schema: Type[LangChainBaseModel] = MarkMessageReadInput
    
    def _run(self, whatsapp_message_id: str) -> Dict[str, Any]:
        """Mark WhatsApp message as read."""
        import asyncio
        
        try:
            client = WhatsAppClient()
            
            # Run async operation
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            success = loop.run_until_complete(
                client.mark_message_as_read(whatsapp_message_id)
            )
            
            loop.run_until_complete(client.close())
            
            return {
                "success": success,
                "whatsapp_message_id": whatsapp_message_id,
                "status": "read" if success else "failed"
            }
            
        except Exception as e:
            logger.error(f"Failed to mark message as read: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _arun(self, whatsapp_message_id: str) -> Dict[str, Any]:
        """Async version of mark WhatsApp message as read."""
        return self._run(whatsapp_message_id)


class WhatsAppLangChainTools:
    """Collection of WhatsApp LangChain tools."""
    
    @staticmethod
    def get_all_tools():
        """Get all WhatsApp LangChain tools."""
        return [
            SendWhatsAppTextMessageTool(),
            SendWhatsAppImageMessageTool(),
            SendWhatsAppAudioMessageTool(),
            SendWhatsAppLocationMessageTool(),
            GetWhatsAppMessageStatusTool(),
            MarkWhatsAppMessageReadTool()
        ]
    
    @staticmethod
    def get_send_tools():
        """Get only message sending tools."""
        return [
            SendWhatsAppTextMessageTool(),
            SendWhatsAppImageMessageTool(),
            SendWhatsAppAudioMessageTool(),
            SendWhatsAppLocationMessageTool()
        ]
    
    @staticmethod
    def get_status_tools():
        """Get only status checking tools."""
        return [
            GetWhatsAppMessageStatusTool(),
            MarkWhatsAppMessageReadTool()
        ]
