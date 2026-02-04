"""
Conversation models for KrishiMitra platform.

This module contains models for chat conversations, messages,
and communication history.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from uuid import uuid4

from pydantic import Field, validator

from .base import BaseModel, TimestampedModel, LanguageCode


class MessageType(str, Enum):
    """Types of messages in conversations."""
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACT = "contact"
    SYSTEM = "system"
    RECOMMENDATION = "recommendation"
    FEEDBACK_REQUEST = "feedback_request"
    ALERT = "alert"


class MessageDirection(str, Enum):
    """Direction of messages."""
    INCOMING = "incoming"  # From farmer to system
    OUTGOING = "outgoing"  # From system to farmer


class MessageStatus(str, Enum):
    """Status of messages."""
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    PENDING = "pending"


class ConversationChannel(str, Enum):
    """Communication channels."""
    WHATSAPP = "whatsapp"
    SMS = "sms"
    VOICE_CALL = "voice_call"
    WEB_CHAT = "web_chat"
    MOBILE_APP = "mobile_app"


class MessageContent(BaseModel):
    """Base message content."""
    
    type: MessageType = Field(description="Message content type")
    language: Optional[LanguageCode] = Field(default=None, description="Message language")


class TextMessage(MessageContent):
    """Text message content."""
    
    type: MessageType = Field(default=MessageType.TEXT, description="Message type")
    text: str = Field(description="Message text")
    formatted_text: Optional[str] = Field(default=None, description="Formatted text (HTML/Markdown)")
    mentions: List[str] = Field(default_factory=list, description="Mentioned entities")
    hashtags: List[str] = Field(default_factory=list, description="Hashtags")
    
    # Translation support
    original_language: Optional[LanguageCode] = Field(default=None, description="Original language")
    translated_text: Optional[Dict[str, str]] = Field(default=None, description="Translated text by language")
    
    # Intent and entities
    detected_intent: Optional[str] = Field(default=None, description="Detected user intent")
    extracted_entities: Dict[str, Any] = Field(default_factory=dict, description="Extracted entities")
    confidence_score: Optional[float] = Field(default=None, ge=0, le=1, description="Intent confidence score")


class VoiceMessage(MessageContent):
    """Voice message content."""
    
    type: MessageType = Field(default=MessageType.VOICE, description="Message type")
    audio_url: str = Field(description="Audio file URL")
    duration: float = Field(gt=0, description="Audio duration in seconds")
    file_size: Optional[int] = Field(default=None, description="File size in bytes")
    format: str = Field(default="mp3", description="Audio format")
    
    # Transcription
    transcribed_text: Optional[str] = Field(default=None, description="Transcribed text")
    transcription_confidence: Optional[float] = Field(default=None, ge=0, le=1, description="Transcription confidence")
    transcription_language: Optional[LanguageCode] = Field(default=None, description="Detected language")
    
    # Audio quality
    sample_rate: Optional[int] = Field(default=None, description="Audio sample rate")
    bitrate: Optional[int] = Field(default=None, description="Audio bitrate")
    noise_level: Optional[float] = Field(default=None, ge=0, le=1, description="Background noise level")
    
    # Processing
    is_processed: bool = Field(default=False, description="Whether audio has been processed")
    processing_status: Optional[str] = Field(default=None, description="Processing status")


class ImageMessage(MessageContent):
    """Image message content."""
    
    type: MessageType = Field(default=MessageType.IMAGE, description="Message type")
    image_url: str = Field(description="Image file URL")
    thumbnail_url: Optional[str] = Field(default=None, description="Thumbnail URL")
    caption: Optional[str] = Field(default=None, description="Image caption")
    
    # Image metadata
    width: Optional[int] = Field(default=None, description="Image width in pixels")
    height: Optional[int] = Field(default=None, description="Image height in pixels")
    file_size: Optional[int] = Field(default=None, description="File size in bytes")
    format: str = Field(default="jpeg", description="Image format")
    
    # Analysis results
    detected_objects: List[str] = Field(default_factory=list, description="Detected objects in image")
    crop_analysis: Optional[Dict[str, Any]] = Field(default=None, description="Crop analysis results")
    disease_detection: Optional[Dict[str, Any]] = Field(default=None, description="Disease detection results")
    pest_detection: Optional[Dict[str, Any]] = Field(default=None, description="Pest detection results")
    
    # Processing
    is_analyzed: bool = Field(default=False, description="Whether image has been analyzed")
    analysis_confidence: Optional[float] = Field(default=None, ge=0, le=1, description="Analysis confidence")


class DocumentMessage(MessageContent):
    """Document message content."""
    
    type: MessageType = Field(default=MessageType.DOCUMENT, description="Message type")
    document_url: str = Field(description="Document file URL")
    filename: str = Field(description="Original filename")
    file_size: Optional[int] = Field(default=None, description="File size in bytes")
    mime_type: str = Field(description="MIME type")
    
    # Document processing
    extracted_text: Optional[str] = Field(default=None, description="Extracted text content")
    document_type: Optional[str] = Field(default=None, description="Document type classification")
    is_processed: bool = Field(default=False, description="Whether document has been processed")


class LocationMessage(MessageContent):
    """Location message content."""
    
    type: MessageType = Field(default=MessageType.LOCATION, description="Message type")
    latitude: float = Field(ge=-90, le=90, description="Latitude")
    longitude: float = Field(ge=-180, le=180, description="Longitude")
    address: Optional[str] = Field(default=None, description="Human-readable address")
    accuracy: Optional[float] = Field(default=None, description="Location accuracy in meters")
    
    # Additional location data
    altitude: Optional[float] = Field(default=None, description="Altitude in meters")
    bearing: Optional[float] = Field(default=None, ge=0, le=360, description="Bearing in degrees")
    speed: Optional[float] = Field(default=None, description="Speed in m/s")


class SystemMessage(MessageContent):
    """System-generated message content."""
    
    type: MessageType = Field(default=MessageType.SYSTEM, description="Message type")
    message_key: str = Field(description="Message template key")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Template parameters")
    rendered_text: str = Field(description="Rendered message text")
    
    # System message metadata
    system_event: Optional[str] = Field(default=None, description="System event that triggered this message")
    priority: str = Field(default="normal", description="Message priority")
    requires_action: bool = Field(default=False, description="Whether message requires user action")


class ConversationMessage(TimestampedModel):
    """Individual message in a conversation."""
    
    conversation_id: str = Field(description="Conversation ID")
    message_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique message ID")
    
    # Message metadata
    direction: MessageDirection = Field(description="Message direction")
    channel: ConversationChannel = Field(description="Communication channel")
    status: MessageStatus = Field(default=MessageStatus.SENT, description="Message status")
    
    # Content
    content: Union[TextMessage, VoiceMessage, ImageMessage, DocumentMessage, LocationMessage, SystemMessage] = Field(
        description="Message content", discriminator="type"
    )
    
    # Sender information
    sender_id: Optional[str] = Field(default=None, description="Sender ID (farmer ID for incoming messages)")
    sender_name: Optional[str] = Field(default=None, description="Sender name")
    sender_phone: Optional[str] = Field(default=None, description="Sender phone number")
    
    # Delivery information
    sent_at: datetime = Field(default_factory=datetime.utcnow, description="Sent timestamp")
    delivered_at: Optional[datetime] = Field(default=None, description="Delivered timestamp")
    read_at: Optional[datetime] = Field(default=None, description="Read timestamp")
    
    # Context
    context: Dict[str, Any] = Field(default_factory=dict, description="Message context")
    thread_id: Optional[str] = Field(default=None, description="Thread ID for grouped messages")
    reply_to_message_id: Optional[str] = Field(default=None, description="ID of message being replied to")
    
    # Processing
    is_processed: bool = Field(default=False, description="Whether message has been processed by AI")
    processing_time_ms: Optional[int] = Field(default=None, description="Processing time in milliseconds")
    agent_response_id: Optional[str] = Field(default=None, description="ID of agent response to this message")
    
    # Analytics
    engagement_score: Optional[float] = Field(default=None, ge=0, le=1, description="Engagement score")
    sentiment_score: Optional[float] = Field(default=None, ge=-1, le=1, description="Sentiment score")
    
    @validator('delivered_at')
    def validate_delivered_after_sent(cls, v, values):
        if v and 'sent_at' in values and v < values['sent_at']:
            raise ValueError('Delivered time cannot be before sent time')
        return v
    
    @validator('read_at')
    def validate_read_after_delivered(cls, v, values):
        if v and 'delivered_at' in values and values['delivered_at'] and v < values['delivered_at']:
            raise ValueError('Read time cannot be before delivered time')
        return v


class ConversationSummary(BaseModel):
    """Summary of a conversation."""
    
    total_messages: int = Field(description="Total number of messages")
    messages_by_type: Dict[str, int] = Field(description="Message count by type")
    messages_by_direction: Dict[str, int] = Field(description="Message count by direction")
    
    # Engagement metrics
    response_time_avg: Optional[float] = Field(default=None, description="Average response time in seconds")
    farmer_engagement_score: Optional[float] = Field(default=None, ge=0, le=1, description="Farmer engagement score")
    conversation_satisfaction: Optional[float] = Field(default=None, ge=1, le=5, description="Conversation satisfaction")
    
    # Content analysis
    main_topics: List[str] = Field(default_factory=list, description="Main conversation topics")
    detected_intents: List[str] = Field(default_factory=list, description="Detected user intents")
    sentiment_trend: Optional[str] = Field(default=None, description="Overall sentiment trend")
    
    # Outcomes
    recommendations_provided: int = Field(default=0, description="Number of recommendations provided")
    issues_resolved: int = Field(default=0, description="Number of issues resolved")
    follow_up_needed: bool = Field(default=False, description="Whether follow-up is needed")


class ConversationHistory(TimestampedModel):
    """Complete conversation history for a farmer."""
    
    farmer_id: str = Field(description="Farmer ID")
    conversation_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique conversation ID")
    
    # Conversation metadata
    channel: ConversationChannel = Field(description="Primary communication channel")
    status: str = Field(default="active", description="Conversation status")
    title: Optional[str] = Field(default=None, description="Conversation title/topic")
    
    # Messages
    messages: List[ConversationMessage] = Field(default_factory=list, description="Conversation messages")
    
    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow, description="Conversation start time")
    last_message_at: Optional[datetime] = Field(default=None, description="Last message timestamp")
    ended_at: Optional[datetime] = Field(default=None, description="Conversation end time")
    
    # Participants
    participants: List[str] = Field(default_factory=list, description="Conversation participants")
    agent_ids: List[str] = Field(default_factory=list, description="AI agents involved")
    
    # Context and state
    conversation_context: Dict[str, Any] = Field(default_factory=dict, description="Conversation context")
    current_topic: Optional[str] = Field(default=None, description="Current conversation topic")
    language: LanguageCode = Field(default_factory=LanguageCode.hindi, description="Conversation language")
    
    # Summary and analytics
    summary: Optional[ConversationSummary] = Field(default=None, description="Conversation summary")
    
    # Tags and categorization
    tags: List[str] = Field(default_factory=list, description="Conversation tags")
    category: Optional[str] = Field(default=None, description="Conversation category")
    priority: str = Field(default="normal", description="Conversation priority")
    
    # Follow-up
    follow_up_scheduled: Optional[datetime] = Field(default=None, description="Scheduled follow-up time")
    follow_up_reason: Optional[str] = Field(default=None, description="Reason for follow-up")
    
    def add_message(self, message: ConversationMessage) -> None:
        """Add a message to the conversation."""
        message.conversation_id = self.conversation_id
        self.messages.append(message)
        self.last_message_at = message.sent_at
        self.update_timestamp()
    
    def get_messages_by_type(self, message_type: MessageType) -> List[ConversationMessage]:
        """Get messages of a specific type."""
        return [msg for msg in self.messages if msg.content.type == message_type]
    
    def get_recent_messages(self, limit: int = 10) -> List[ConversationMessage]:
        """Get recent messages."""
        return sorted(self.messages, key=lambda x: x.sent_at, reverse=True)[:limit]
    
    def calculate_response_time(self) -> Optional[float]:
        """Calculate average response time."""
        response_times = []
        for i in range(1, len(self.messages)):
            prev_msg = self.messages[i-1]
            curr_msg = self.messages[i]
            if (prev_msg.direction == MessageDirection.INCOMING and 
                curr_msg.direction == MessageDirection.OUTGOING):
                response_time = (curr_msg.sent_at - prev_msg.sent_at).total_seconds()
                response_times.append(response_time)
        
        return sum(response_times) / len(response_times) if response_times else None