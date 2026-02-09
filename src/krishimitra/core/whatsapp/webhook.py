"""
WhatsApp webhook handler for KrishiMitra.

This module handles incoming WhatsApp webhook events including
messages, status updates, and other notifications.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .models import (
    WhatsAppIncomingMessage,
    WhatsAppStatusUpdate,
    WhatsAppMessageType,
    WhatsAppMessageStatus,
    WhatsAppMediaInfo,
    WhatsAppLocation,
    WhatsAppContact
)

logger = logging.getLogger(__name__)


class WhatsAppWebhookHandler:
    """Handler for WhatsApp webhook events."""
    
    def __init__(self):
        """Initialize webhook handler."""
        pass
    
    def parse_webhook_payload(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse WhatsApp webhook payload and extract events.
        
        Args:
            payload: Raw webhook payload from WhatsApp
            
        Returns:
            List of parsed events
        """
        events = []
        
        if "entry" not in payload:
            logger.warning("No 'entry' field in webhook payload")
            return events
        
        for entry in payload["entry"]:
            if "changes" not in entry:
                continue
            
            for change in entry["changes"]:
                if change.get("field") != "messages":
                    continue
                
                value = change.get("value", {})
                
                # Parse messages
                if "messages" in value:
                    for message_data in value["messages"]:
                        try:
                            message = self.parse_incoming_message(message_data, value)
                            events.append({
                                "type": "message",
                                "data": message
                            })
                        except Exception as e:
                            logger.error(f"Failed to parse message: {e}", exc_info=True)
                
                # Parse status updates
                if "statuses" in value:
                    for status_data in value["statuses"]:
                        try:
                            status = self.parse_status_update(status_data)
                            events.append({
                                "type": "status",
                                "data": status
                            })
                        except Exception as e:
                            logger.error(f"Failed to parse status update: {e}", exc_info=True)
        
        return events
    
    def parse_incoming_message(
        self,
        message_data: Dict[str, Any],
        value: Dict[str, Any]
    ) -> WhatsAppIncomingMessage:
        """
        Parse incoming WhatsApp message.
        
        Args:
            message_data: Message data from webhook
            value: Value object containing metadata
            
        Returns:
            Parsed WhatsAppIncomingMessage
        """
        message_id = message_data.get("id")
        from_number = message_data.get("from")
        timestamp = message_data.get("timestamp")
        message_type = message_data.get("type")
        
        # Parse timestamp
        if isinstance(timestamp, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp)
        elif isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        else:
            timestamp = datetime.utcnow()
        
        # Get profile name from contacts
        profile_name = None
        contacts = value.get("contacts", [])
        for contact in contacts:
            if contact.get("wa_id") == from_number:
                profile_name = contact.get("profile", {}).get("name")
                break
        
        # Parse message content based on type
        text = None
        media = None
        location = None
        contacts_list = None
        context_message_id = None
        
        # Get context (reply information)
        if "context" in message_data:
            context_message_id = message_data["context"].get("id")
        
        # Parse based on message type
        if message_type == "text":
            text = message_data.get("text", {}).get("body")
        
        elif message_type == "image":
            image_data = message_data.get("image", {})
            media = WhatsAppMediaInfo(
                id=image_data.get("id"),
                mime_type=image_data.get("mime_type"),
                sha256=image_data.get("sha256"),
                caption=image_data.get("caption")
            )
        
        elif message_type == "audio":
            audio_data = message_data.get("audio", {})
            media = WhatsAppMediaInfo(
                id=audio_data.get("id"),
                mime_type=audio_data.get("mime_type"),
                sha256=audio_data.get("sha256")
            )
        
        elif message_type == "video":
            video_data = message_data.get("video", {})
            media = WhatsAppMediaInfo(
                id=video_data.get("id"),
                mime_type=video_data.get("mime_type"),
                sha256=video_data.get("sha256"),
                caption=video_data.get("caption")
            )
        
        elif message_type == "document":
            document_data = message_data.get("document", {})
            media = WhatsAppMediaInfo(
                id=document_data.get("id"),
                mime_type=document_data.get("mime_type"),
                sha256=document_data.get("sha256"),
                caption=document_data.get("caption")
            )
        
        elif message_type == "location":
            location_data = message_data.get("location", {})
            location = WhatsAppLocation(
                latitude=location_data.get("latitude"),
                longitude=location_data.get("longitude"),
                name=location_data.get("name"),
                address=location_data.get("address")
            )
        
        elif message_type == "contacts":
            contacts_data = message_data.get("contacts", [])
            contacts_list = []
            for contact_data in contacts_data:
                contact = WhatsAppContact(
                    name=contact_data.get("name", {}),
                    phones=contact_data.get("phones"),
                    emails=contact_data.get("emails"),
                    org=contact_data.get("org")
                )
                contacts_list.append(contact)
        
        # Create message object
        message = WhatsAppIncomingMessage(
            message_id=message_id,
            from_number=from_number,
            timestamp=timestamp,
            message_type=WhatsAppMessageType(message_type),
            text=text,
            media=media,
            location=location,
            contacts=contacts_list,
            context_message_id=context_message_id,
            profile_name=profile_name
        )
        
        logger.info(f"Parsed incoming message: {message_id} from {from_number} type {message_type}")
        
        return message
    
    def parse_status_update(self, status_data: Dict[str, Any]) -> WhatsAppStatusUpdate:
        """
        Parse WhatsApp message status update.
        
        Args:
            status_data: Status data from webhook
            
        Returns:
            Parsed WhatsAppStatusUpdate
        """
        message_id = status_data.get("id")
        status = status_data.get("status")
        timestamp = status_data.get("timestamp")
        
        # Parse timestamp
        if isinstance(timestamp, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp)
        elif isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        else:
            timestamp = datetime.utcnow()
        
        # Map WhatsApp status to our status enum
        status_mapping = {
            "sent": WhatsAppMessageStatus.SENT,
            "delivered": WhatsAppMessageStatus.DELIVERED,
            "read": WhatsAppMessageStatus.READ,
            "failed": WhatsAppMessageStatus.FAILED,
            "deleted": WhatsAppMessageStatus.DELETED
        }
        
        mapped_status = status_mapping.get(status, WhatsAppMessageStatus.SENT)
        
        # Get error information if failed
        error_code = None
        error_message = None
        if status == "failed" and "errors" in status_data:
            errors = status_data["errors"]
            if errors:
                error_code = str(errors[0].get("code"))
                error_message = errors[0].get("title")
        
        # Get pricing information
        pricing_model = status_data.get("pricing", {}).get("pricing_model")
        pricing_category = status_data.get("pricing", {}).get("category")
        
        status_update = WhatsAppStatusUpdate(
            message_id=message_id,
            status=mapped_status,
            timestamp=timestamp,
            error_code=error_code,
            error_message=error_message,
            pricing_model=pricing_model,
            pricing_category=pricing_category
        )
        
        logger.info(f"Parsed status update: {message_id} status {status}")
        
        return status_update
    
    def validate_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        app_secret: str
    ) -> bool:
        """
        Validate WhatsApp webhook signature.
        
        Args:
            payload: Raw webhook payload bytes
            signature: X-Hub-Signature-256 header value
            app_secret: WhatsApp app secret
            
        Returns:
            True if signature is valid, False otherwise
        """
        import hmac
        import hashlib
        
        # Remove 'sha256=' prefix if present
        if signature.startswith("sha256="):
            signature = signature[7:]
        
        # Calculate expected signature
        expected_signature = hmac.new(
            app_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        is_valid = hmac.compare_digest(expected_signature, signature)
        
        if not is_valid:
            logger.warning("Invalid webhook signature")
        
        return is_valid
