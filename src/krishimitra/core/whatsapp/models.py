"""
WhatsApp message models for KrishiMitra.

This module defines Pydantic models for WhatsApp messages,
status updates, and webhook payloads.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, validator


class WhatsAppMessageType(str, Enum):
    """WhatsApp message types."""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACTS = "contacts"
    STICKER = "sticker"
    TEMPLATE = "template"
    INTERACTIVE = "interactive"
    REACTION = "reaction"


class WhatsAppMessageStatus(str, Enum):
    """WhatsApp message delivery status."""
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    DELETED = "deleted"


class WhatsAppMediaInfo(BaseModel):
    """WhatsApp media information."""
    id: Optional[str] = Field(default=None, description="Media ID from WhatsApp")
    mime_type: Optional[str] = Field(default=None, description="MIME type")
    sha256: Optional[str] = Field(default=None, description="SHA256 hash")
    file_size: Optional[int] = Field(default=None, description="File size in bytes")
    url: Optional[str] = Field(default=None, description="Media URL")
    caption: Optional[str] = Field(default=None, description="Media caption")


class WhatsAppLocation(BaseModel):
    """WhatsApp location information."""
    latitude: float = Field(description="Latitude")
    longitude: float = Field(description="Longitude")
    name: Optional[str] = Field(default=None, description="Location name")
    address: Optional[str] = Field(default=None, description="Location address")


class WhatsAppContact(BaseModel):
    """WhatsApp contact information."""
    name: Dict[str, str] = Field(description="Contact name")
    phones: Optional[List[Dict[str, str]]] = Field(default=None, description="Phone numbers")
    emails: Optional[List[Dict[str, str]]] = Field(default=None, description="Email addresses")
    org: Optional[Dict[str, str]] = Field(default=None, description="Organization")


class WhatsAppIncomingMessage(BaseModel):
    """Incoming WhatsApp message model."""
    
    # Message identification
    message_id: str = Field(description="WhatsApp message ID")
    from_number: str = Field(description="Sender phone number")
    timestamp: datetime = Field(description="Message timestamp")
    
    # Message type and content
    message_type: WhatsAppMessageType = Field(description="Message type")
    
    # Text content
    text: Optional[str] = Field(default=None, description="Text message body")
    
    # Media content
    media: Optional[WhatsAppMediaInfo] = Field(default=None, description="Media information")
    
    # Location content
    location: Optional[WhatsAppLocation] = Field(default=None, description="Location information")
    
    # Contacts content
    contacts: Optional[List[WhatsAppContact]] = Field(default=None, description="Contact information")
    
    # Context (for replies)
    context_message_id: Optional[str] = Field(default=None, description="ID of message being replied to")
    
    # Metadata
    profile_name: Optional[str] = Field(default=None, description="Sender profile name")
    is_forwarded: bool = Field(default=False, description="Whether message is forwarded")
    is_frequently_forwarded: bool = Field(default=False, description="Whether message is frequently forwarded")
    
    # Processing metadata
    received_at: datetime = Field(default_factory=datetime.utcnow, description="When message was received by system")
    processed: bool = Field(default=False, description="Whether message has been processed")
    processing_started_at: Optional[datetime] = Field(default=None, description="When processing started")
    processing_completed_at: Optional[datetime] = Field(default=None, description="When processing completed")
    
    # Conversation context
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID")
    farmer_id: Optional[str] = Field(default=None, description="Associated farmer ID")
    
    @validator('timestamp', pre=True)
    def parse_timestamp(cls, v):
        """Parse timestamp from Unix timestamp if needed."""
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v)
        return v


class WhatsAppOutgoingMessage(BaseModel):
    """Outgoing WhatsApp message model."""
    
    # Message identification
    message_id: str = Field(default_factory=lambda: str(uuid4()), description="Internal message ID")
    to_number: str = Field(description="Recipient phone number")
    
    # Message type and content
    message_type: WhatsAppMessageType = Field(description="Message type")
    
    # Text content
    text: Optional[str] = Field(default=None, description="Text message body")
    
    # Media content
    media_id: Optional[str] = Field(default=None, description="Media ID for sending")
    media_url: Optional[str] = Field(default=None, description="Media URL for sending")
    caption: Optional[str] = Field(default=None, description="Media caption")
    filename: Optional[str] = Field(default=None, description="Document filename")
    
    # Location content
    location: Optional[WhatsAppLocation] = Field(default=None, description="Location to send")
    
    # Template message
    template_name: Optional[str] = Field(default=None, description="Template name")
    template_language: Optional[str] = Field(default="en", description="Template language")
    template_parameters: Optional[List[Dict[str, Any]]] = Field(default=None, description="Template parameters")
    
    # Context (for replies)
    context_message_id: Optional[str] = Field(default=None, description="ID of message being replied to")
    
    # Delivery tracking
    status: WhatsAppMessageStatus = Field(default=WhatsAppMessageStatus.QUEUED, description="Message status")
    whatsapp_message_id: Optional[str] = Field(default=None, description="WhatsApp assigned message ID")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When message was created")
    queued_at: Optional[datetime] = Field(default=None, description="When message was queued")
    sent_at: Optional[datetime] = Field(default=None, description="When message was sent")
    delivered_at: Optional[datetime] = Field(default=None, description="When message was delivered")
    read_at: Optional[datetime] = Field(default=None, description="When message was read")
    failed_at: Optional[datetime] = Field(default=None, description="When message failed")
    
    # Error tracking
    error_code: Optional[str] = Field(default=None, description="Error code if failed")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    retry_count: int = Field(default=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    
    # Conversation context
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID")
    farmer_id: Optional[str] = Field(default=None, description="Associated farmer ID")
    
    # Priority
    priority: int = Field(default=5, ge=1, le=10, description="Message priority (1=highest, 10=lowest)")
    
    @validator('text')
    def validate_text_length(cls, v, values):
        """Validate text message length (WhatsApp limit is 4096 characters)."""
        if v and len(v) > 4096:
            raise ValueError("Text message cannot exceed 4096 characters")
        return v


class WhatsAppStatusUpdate(BaseModel):
    """WhatsApp message status update."""
    
    message_id: str = Field(description="WhatsApp message ID")
    status: WhatsAppMessageStatus = Field(description="New status")
    timestamp: datetime = Field(description="Status update timestamp")
    
    # Error information
    error_code: Optional[str] = Field(default=None, description="Error code if failed")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    
    # Pricing information
    pricing_model: Optional[str] = Field(default=None, description="Pricing model")
    pricing_category: Optional[str] = Field(default=None, description="Pricing category")
    
    @validator('timestamp', pre=True)
    def parse_timestamp(cls, v):
        """Parse timestamp from Unix timestamp if needed."""
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v)
        return v


class WhatsAppWebhookPayload(BaseModel):
    """WhatsApp webhook payload model."""
    
    object: str = Field(description="Webhook object type")
    entry: List[Dict[str, Any]] = Field(description="Webhook entries")


class WhatsAppMessageDeliveryReport(BaseModel):
    """WhatsApp message delivery report."""
    
    message_id: str = Field(description="Internal message ID")
    whatsapp_message_id: Optional[str] = Field(default=None, description="WhatsApp message ID")
    to_number: str = Field(description="Recipient phone number")
    
    # Status history
    status: WhatsAppMessageStatus = Field(description="Current status")
    status_history: List[Dict[str, Any]] = Field(default_factory=list, description="Status change history")
    
    # Timing metrics
    time_to_send: Optional[float] = Field(default=None, description="Time to send in seconds")
    time_to_deliver: Optional[float] = Field(default=None, description="Time to deliver in seconds")
    time_to_read: Optional[float] = Field(default=None, description="Time to read in seconds")
    
    # Success/failure
    is_successful: bool = Field(description="Whether message was successfully delivered")
    failure_reason: Optional[str] = Field(default=None, description="Failure reason if applicable")
    
    # Retry information
    retry_count: int = Field(default=0, description="Number of retries")
    final_attempt: bool = Field(default=False, description="Whether this was the final attempt")
