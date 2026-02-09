"""
WhatsApp Business API endpoints for KrishiMitra.

This module handles WhatsApp webhook events and message processing
with comprehensive integration including message queuing, delivery tracking,
and LangChain tools for AI agent interaction.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Request, Query, Header
from pydantic import BaseModel

from ...core.config import get_settings
from ...core.whatsapp import (
    WhatsAppWebhookHandler,
    WhatsAppMessageQueue,
    WhatsAppClient,
    WhatsAppIncomingMessage,
    WhatsAppOutgoingMessage,
    WhatsAppMessageType
)

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

# Initialize WhatsApp components
webhook_handler = WhatsAppWebhookHandler()
message_queue = WhatsAppMessageQueue()


class WhatsAppMessage(BaseModel):
    """WhatsApp message model."""
    from_number: str
    message_type: str
    text: Optional[str] = None
    image_url: Optional[str] = None
    voice_url: Optional[str] = None


class WhatsAppResponse(BaseModel):
    """WhatsApp response model."""
    to_number: str
    message_type: str
    text: Optional[str] = None
    image_url: Optional[str] = None
    voice_url: Optional[str] = None


@router.get("/whatsapp/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_challenge: str = Query(alias="hub.challenge"),
    hub_verify_token: str = Query(alias="hub.verify_token")
) -> str:
    """
    Verify WhatsApp webhook.
    
    This endpoint is called by WhatsApp to verify the webhook URL.
    It validates the verify token and returns the challenge string.
    """
    
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        logger.info("WhatsApp webhook verified successfully")
        return hub_challenge
    
    logger.warning(f"Invalid webhook verification attempt with token: {hub_verify_token}")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid verification token"
    )


@router.post("/whatsapp/webhook")
async def handle_whatsapp_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256")
) -> Dict[str, str]:
    """
    Handle incoming WhatsApp webhook events.
    
    This endpoint receives webhook notifications from WhatsApp including:
    - Incoming messages (text, image, audio, video, document, location)
    - Message status updates (sent, delivered, read, failed)
    - Other webhook events
    
    Messages are queued for asynchronous processing by AI agents.
    """
    
    try:
        # Get raw payload for signature validation
        payload_bytes = await request.body()
        payload = await request.json()
        
        # Validate webhook signature if app secret is configured
        # Note: In production, you should always validate signatures
        # if x_hub_signature_256 and settings.whatsapp_app_secret:
        #     is_valid = webhook_handler.validate_webhook_signature(
        #         payload_bytes,
        #         x_hub_signature_256,
        #         settings.whatsapp_app_secret
        #     )
        #     if not is_valid:
        #         raise HTTPException(
        #             status_code=status.HTTP_403_FORBIDDEN,
        #             detail="Invalid webhook signature"
        #         )
        
        logger.info(f"Received WhatsApp webhook: {payload.get('object', 'unknown')}")
        
        # Parse webhook events
        events = webhook_handler.parse_webhook_payload(payload)
        
        # Process each event
        for event in events:
            event_type = event["type"]
            event_data = event["data"]
            
            if event_type == "message":
                # Incoming message - queue for processing
                message: WhatsAppIncomingMessage = event_data
                
                logger.info(
                    f"Received {message.message_type.value} message from {message.from_number}: "
                    f"{message.message_id}"
                )
                
                # Mark message as read
                try:
                    client = WhatsAppClient()
                    await client.mark_message_as_read(message.message_id)
                    await client.close()
                except Exception as e:
                    logger.warning(f"Failed to mark message as read: {e}")
                
                # Queue message for processing by AI agents
                task_id = message_queue.enqueue_incoming_message_processing(message)
                
                logger.info(f"Queued message {message.message_id} for processing: {task_id}")
                
            elif event_type == "status":
                # Message status update
                status_update = event_data
                
                logger.info(
                    f"Status update for message {status_update.message_id}: "
                    f"{status_update.status.value}"
                )
                
                # Update message status in tracking
                message_queue.update_message_status(
                    status_update.message_id,
                    status_update.status,
                    error_code=status_update.error_code,
                    error_message=status_update.error_message
                )
        
        return {"status": "success", "events_processed": len(events)}
        
    except Exception as e:
        logger.error(f"Error processing WhatsApp webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook"
        )


@router.post("/whatsapp/send")
async def send_whatsapp_message(message: WhatsAppResponse) -> Dict[str, Any]:
    """
    Send a WhatsApp message.
    
    This endpoint allows sending WhatsApp messages programmatically.
    Messages are queued for delivery with automatic retry on failure.
    """
    
    try:
        # Create outgoing message
        outgoing_message = WhatsAppOutgoingMessage(
            to_number=message.to_number,
            message_type=WhatsAppMessageType(message.message_type),
            text=message.text,
            media_url=message.image_url or message.voice_url
        )
        
        # Check rate limit
        if not message_queue.check_rate_limit(message.to_number):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded for this phone number"
            )
        
        # Queue message for sending
        task_id = message_queue.enqueue_outgoing_message(outgoing_message)
        
        logger.info(
            f"Queued {message.message_type} message to {message.to_number}: "
            f"{outgoing_message.message_id}"
        )
        
        return {
            "success": True,
            "message_id": outgoing_message.message_id,
            "task_id": task_id,
            "status": "queued"
        }
        
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )


@router.get("/whatsapp/status/{message_id}")
async def get_message_status(message_id: str) -> Dict[str, Any]:
    """
    Get WhatsApp message delivery status.
    
    This endpoint returns the current delivery status of a message
    including timestamps for sent, delivered, and read events.
    """
    
    try:
        status_info = message_queue.get_message_status(message_id)
        
        if not status_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )
        
        return {
            "success": True,
            "message_id": message_id,
            "status": status_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get message status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get message status"
        )


@router.get("/whatsapp/queue/stats")
async def get_queue_stats() -> Dict[str, Any]:
    """
    Get WhatsApp message queue statistics.
    
    This endpoint returns information about message queue lengths
    and processing status for monitoring purposes.
    """
    
    try:
        queue_lengths = message_queue.get_queue_length()
        
        return {
            "success": True,
            "queues": queue_lengths,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get queue statistics"
        )


@router.get("/whatsapp/group/{group_id}/stats")
async def get_group_stats(group_id: str) -> Dict[str, Any]:
    """
    Get WhatsApp group chat statistics.
    
    This endpoint returns information about a group chat session
    including participant count, message count, and activity.
    """
    
    try:
        from ...core.whatsapp.group_chat import GroupChatManager
        
        group_manager = GroupChatManager()
        stats = group_manager.get_session_stats(group_id)
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get group stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get group statistics"
        )


# Legacy placeholder functions for backward compatibility
async def process_whatsapp_message(message: Dict[str, Any], value: Dict[str, Any]) -> None:
    """
    Legacy function - now handled by webhook handler.
    Kept for backward compatibility.
    """
    logger.warning("Legacy process_whatsapp_message called - use webhook handler instead")


async def send_whatsapp_message(to_number: str, message: str) -> None:
    """
    Legacy function - now handled by message queue.
    Kept for backward compatibility.
    """
    logger.warning("Legacy send_whatsapp_message called - use message queue instead")
