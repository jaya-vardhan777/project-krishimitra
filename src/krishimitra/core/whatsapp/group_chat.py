"""
WhatsApp group chat management for KrishiMitra.

This module handles multi-farmer conversations in WhatsApp groups,
maintaining individual context for each participant while managing
shared group conversation state.
"""

import logging
from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timedelta
import json

from redis import Redis
import boto3
from botocore.exceptions import ClientError

from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage

from ...core.config import get_settings
from .models import WhatsAppIncomingMessage, WhatsAppOutgoingMessage, WhatsAppMessageType
from .chains import WhatsAppGroupChatChain, WhatsAppConversationChain

logger = logging.getLogger(__name__)
settings = get_settings()


class GroupChatParticipant:
    """Represents a participant in a group chat."""
    
    def __init__(
        self,
        phone_number: str,
        name: Optional[str] = None,
        farmer_id: Optional[str] = None
    ):
        """Initialize participant."""
        self.phone_number = phone_number
        self.name = name or phone_number
        self.farmer_id = farmer_id
        self.joined_at = datetime.utcnow()
        self.last_active = datetime.utcnow()
        self.message_count = 0
        
        # Individual context for this participant
        self.context: Dict[str, Any] = {}
        self.conversation_memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            max_token_limit=500  # Smaller limit for group chats
        )
    
    def update_activity(self):
        """Update last active timestamp."""
        self.last_active = datetime.utcnow()
        self.message_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "phone_number": self.phone_number,
            "name": self.name,
            "farmer_id": self.farmer_id,
            "joined_at": self.joined_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "message_count": self.message_count,
            "context": self.context
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GroupChatParticipant':
        """Create from dictionary."""
        participant = cls(
            phone_number=data["phone_number"],
            name=data.get("name"),
            farmer_id=data.get("farmer_id")
        )
        participant.joined_at = datetime.fromisoformat(data["joined_at"])
        participant.last_active = datetime.fromisoformat(data["last_active"])
        participant.message_count = data.get("message_count", 0)
        participant.context = data.get("context", {})
        return participant


class GroupChatSession:
    """Manages a WhatsApp group chat session."""
    
    def __init__(self, group_id: str):
        """Initialize group chat session."""
        self.group_id = group_id
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        
        # Participants
        self.participants: Dict[str, GroupChatParticipant] = {}
        
        # Shared group context
        self.group_context: Dict[str, Any] = {
            "topics": [],
            "active_discussions": [],
            "shared_resources": []
        }
        
        # Message history (limited for performance)
        self.recent_messages: List[Dict[str, Any]] = []
        self.max_recent_messages = 50
        
        # Group conversation memory
        self.group_memory = ConversationBufferMemory(
            memory_key="group_history",
            return_messages=True,
            max_token_limit=1000
        )
    
    def add_participant(self, participant: GroupChatParticipant):
        """Add participant to group."""
        self.participants[participant.phone_number] = participant
        logger.info(f"Added participant {participant.name} to group {self.group_id}")
    
    def get_participant(self, phone_number: str) -> Optional[GroupChatParticipant]:
        """Get participant by phone number."""
        return self.participants.get(phone_number)
    
    def add_message(
        self,
        phone_number: str,
        message_text: str,
        message_type: str = "text",
        is_bot: bool = False
    ):
        """Add message to group history."""
        # Update participant activity
        participant = self.get_participant(phone_number)
        if participant:
            participant.update_activity()
        
        # Add to recent messages
        message_data = {
            "phone_number": phone_number,
            "name": participant.name if participant else phone_number,
            "text": message_text,
            "type": message_type,
            "is_bot": is_bot,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.recent_messages.append(message_data)
        
        # Keep only recent messages
        if len(self.recent_messages) > self.max_recent_messages:
            self.recent_messages = self.recent_messages[-self.max_recent_messages:]
        
        # Update group memory
        if is_bot:
            self.group_memory.chat_memory.add_message(
                AIMessage(content=message_text)
            )
        else:
            sender_name = participant.name if participant else phone_number
            self.group_memory.chat_memory.add_message(
                HumanMessage(content=f"{sender_name}: {message_text}")
            )
        
        self.last_activity = datetime.utcnow()
    
    def get_context_for_participant(self, phone_number: str) -> str:
        """Get conversation context for a specific participant."""
        participant = self.get_participant(phone_number)
        if not participant:
            return ""
        
        # Combine participant's individual context with group context
        context_parts = []
        
        # Recent group messages
        recent_group = self._format_recent_messages(limit=10)
        if recent_group:
            context_parts.append(f"Recent Group Discussion:\n{recent_group}")
        
        # Participant's individual context
        if participant.context:
            context_parts.append(f"Your Context: {json.dumps(participant.context)}")
        
        return "\n\n".join(context_parts)
    
    def _format_recent_messages(self, limit: int = 10) -> str:
        """Format recent messages for context."""
        recent = self.recent_messages[-limit:]
        
        formatted = []
        for msg in recent:
            sender = msg["name"]
            text = msg["text"]
            formatted.append(f"{sender}: {text}")
        
        return "\n".join(formatted)
    
    def get_active_participants(self, minutes: int = 30) -> List[GroupChatParticipant]:
        """Get participants active in last N minutes."""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        
        return [
            p for p in self.participants.values()
            if p.last_active >= cutoff
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "group_id": self.group_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "participants": {
                phone: p.to_dict()
                for phone, p in self.participants.items()
            },
            "group_context": self.group_context,
            "recent_messages": self.recent_messages
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GroupChatSession':
        """Create from dictionary."""
        session = cls(data["group_id"])
        session.created_at = datetime.fromisoformat(data["created_at"])
        session.last_activity = datetime.fromisoformat(data["last_activity"])
        session.group_context = data.get("group_context", {})
        session.recent_messages = data.get("recent_messages", [])
        
        # Restore participants
        for phone, p_data in data.get("participants", {}).items():
            participant = GroupChatParticipant.from_dict(p_data)
            session.participants[phone] = participant
        
        return session


class GroupChatManager:
    """Manages WhatsApp group chat sessions with persistence."""
    
    def __init__(self):
        """Initialize group chat manager."""
        self.settings = settings
        
        # Redis for fast session access
        self.redis_client = Redis(
            host="localhost",
            port=6379,
            db=1,  # Use different DB from message queue
            decode_responses=True
        )
        
        # DynamoDB for persistent storage
        self.dynamodb = boto3.resource('dynamodb', region_name=settings.aws_region)
        self.conversations_table = self.dynamodb.Table(settings.conversations_table)
        
        # LangChain chains for group chat
        self.group_chain = WhatsAppGroupChatChain()
        self.conversation_chain = WhatsAppConversationChain()
        
        # In-memory cache of active sessions
        self.active_sessions: Dict[str, GroupChatSession] = {}
    
    def get_or_create_session(self, group_id: str) -> GroupChatSession:
        """Get existing session or create new one."""
        # Check in-memory cache
        if group_id in self.active_sessions:
            return self.active_sessions[group_id]
        
        # Try to load from Redis
        session = self._load_session_from_redis(group_id)
        
        if not session:
            # Try to load from DynamoDB
            session = self._load_session_from_dynamodb(group_id)
        
        if not session:
            # Create new session
            session = GroupChatSession(group_id)
            logger.info(f"Created new group chat session: {group_id}")
        
        # Cache in memory
        self.active_sessions[group_id] = session
        
        return session
    
    def save_session(self, session: GroupChatSession):
        """Save session to Redis and DynamoDB."""
        # Save to Redis (fast access)
        self._save_session_to_redis(session)
        
        # Save to DynamoDB (persistent storage)
        self._save_session_to_dynamodb(session)
    
    async def process_group_message(
        self,
        message: WhatsAppIncomingMessage,
        group_id: str
    ) -> Optional[WhatsAppOutgoingMessage]:
        """
        Process message in group chat context.
        
        Args:
            message: Incoming message
            group_id: WhatsApp group ID
            
        Returns:
            Response message or None
        """
        try:
            # Get or create session
            session = self.get_or_create_session(group_id)
            
            # Get or create participant
            participant = session.get_participant(message.from_number)
            if not participant:
                participant = GroupChatParticipant(
                    phone_number=message.from_number,
                    name=message.profile_name,
                    farmer_id=message.farmer_id
                )
                session.add_participant(participant)
            
            # Add message to session
            session.add_message(
                message.from_number,
                message.text or f"[{message.message_type.value}]",
                message.message_type.value
            )
            
            # Get context for this participant
            context = session.get_context_for_participant(message.from_number)
            
            # Determine if bot should respond
            should_respond = self._should_respond_in_group(message, session)
            
            if not should_respond:
                # Save session and return
                self.save_session(session)
                return None
            
            # Generate response using group chat chain
            response_text = await self.group_chain.generate_group_response(
                current_message=message.text or "",
                sender_name=participant.name,
                group_context=context
            )
            
            # Add bot response to session
            session.add_message(
                "KrishiMitra",
                response_text,
                "text",
                is_bot=True
            )
            
            # Save session
            self.save_session(session)
            
            # Create response message
            response = WhatsAppOutgoingMessage(
                to_number=group_id,  # Send to group
                message_type=WhatsAppMessageType.TEXT,
                text=response_text,
                context_message_id=message.message_id,
                conversation_id=group_id,
                priority=5  # Normal priority for group messages
            )
            
            return response
        
        except Exception as e:
            logger.error(f"Error processing group message: {e}", exc_info=True)
            return None
    
    def _should_respond_in_group(
        self,
        message: WhatsAppIncomingMessage,
        session: GroupChatSession
    ) -> bool:
        """Determine if bot should respond to group message."""
        text = (message.text or "").lower()
        
        # Respond if bot is mentioned
        if any(keyword in text for keyword in ["krishimitra", "कृषि मित्र", "@krishimitra"]):
            return True
        
        # Respond if it's a question
        if any(text.endswith(q) for q in ["?", "।"]):
            return True
        
        # Respond if no recent bot activity (avoid spam)
        recent_messages = session.recent_messages[-5:]
        bot_messages = [m for m in recent_messages if m.get("is_bot")]
        
        if not bot_messages:
            return True
        
        # Don't respond if bot just responded
        if recent_messages and recent_messages[-1].get("is_bot"):
            return False
        
        return False
    
    def _load_session_from_redis(self, group_id: str) -> Optional[GroupChatSession]:
        """Load session from Redis."""
        try:
            key = f"group_chat:{group_id}"
            data = self.redis_client.get(key)
            
            if data:
                session_dict = json.loads(data)
                return GroupChatSession.from_dict(session_dict)
            
            return None
        except Exception as e:
            logger.error(f"Error loading session from Redis: {e}")
            return None
    
    def _save_session_to_redis(self, session: GroupChatSession):
        """Save session to Redis with expiration."""
        try:
            key = f"group_chat:{session.group_id}"
            data = json.dumps(session.to_dict())
            
            # Store with 24-hour expiration
            self.redis_client.setex(key, timedelta(hours=24), data)
        except Exception as e:
            logger.error(f"Error saving session to Redis: {e}")
    
    def _load_session_from_dynamodb(self, group_id: str) -> Optional[GroupChatSession]:
        """Load session from DynamoDB."""
        try:
            response = self.conversations_table.get_item(
                Key={"conversation_id": f"group_{group_id}"}
            )
            
            if "Item" in response:
                item = response["Item"]
                session_data = json.loads(item.get("session_data", "{}"))
                return GroupChatSession.from_dict(session_data)
            
            return None
        except ClientError as e:
            logger.error(f"Error loading session from DynamoDB: {e}")
            return None
    
    def _save_session_to_dynamodb(self, session: GroupChatSession):
        """Save session to DynamoDB."""
        try:
            self.conversations_table.put_item(
                Item={
                    "conversation_id": f"group_{session.group_id}",
                    "session_data": json.dumps(session.to_dict()),
                    "last_activity": session.last_activity.isoformat(),
                    "participant_count": len(session.participants),
                    "message_count": len(session.recent_messages)
                }
            )
        except ClientError as e:
            logger.error(f"Error saving session to DynamoDB: {e}")
    
    def get_session_stats(self, group_id: str) -> Dict[str, Any]:
        """Get statistics for a group chat session."""
        session = self.get_or_create_session(group_id)
        
        return {
            "group_id": group_id,
            "participant_count": len(session.participants),
            "message_count": len(session.recent_messages),
            "active_participants": len(session.get_active_participants()),
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat()
        }
    
    def cleanup_inactive_sessions(self, hours: int = 24):
        """Remove inactive sessions from memory."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        inactive_groups = [
            group_id
            for group_id, session in self.active_sessions.items()
            if session.last_activity < cutoff
        ]
        
        for group_id in inactive_groups:
            # Save before removing
            self.save_session(self.active_sessions[group_id])
            del self.active_sessions[group_id]
            logger.info(f"Cleaned up inactive session: {group_id}")
        
        return len(inactive_groups)
