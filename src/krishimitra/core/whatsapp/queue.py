"""
WhatsApp message queue for KrishiMitra.

This module provides message queuing functionality using Celery and Redis
for high-volume WhatsApp message processing.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import json

from celery import Celery, Task
from celery.result import AsyncResult
from redis import Redis

from ...core.config import get_settings
from .models import (
    WhatsAppOutgoingMessage,
    WhatsAppMessageStatus,
    WhatsAppIncomingMessage
)

logger = logging.getLogger(__name__)
settings = get_settings()


# Initialize Celery app
celery_app = Celery(
    "krishimitra_whatsapp",
    broker=f"redis://localhost:6379/0",
    backend=f"redis://localhost:6379/0"
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
)


class WhatsAppMessageQueue:
    """Queue manager for WhatsApp messages."""
    
    def __init__(self):
        """Initialize message queue."""
        self.celery = celery_app
        self.redis_client = Redis(
            host="localhost",
            port=6379,
            db=0,
            decode_responses=True
        )
        
        # Queue names
        self.high_priority_queue = "whatsapp_high_priority"
        self.normal_priority_queue = "whatsapp_normal"
        self.low_priority_queue = "whatsapp_low_priority"
        
        # Rate limiting keys
        self.rate_limit_key_prefix = "whatsapp_rate_limit"
    
    def enqueue_outgoing_message(
        self,
        message: WhatsAppOutgoingMessage,
        delay_seconds: int = 0
    ) -> str:
        """
        Enqueue an outgoing WhatsApp message for sending.
        
        Args:
            message: WhatsApp message to send
            delay_seconds: Optional delay before sending
            
        Returns:
            Task ID for tracking
        """
        # Determine queue based on priority
        queue_name = self._get_queue_for_priority(message.priority)
        
        # Update message status
        message.status = WhatsAppMessageStatus.QUEUED
        message.queued_at = datetime.utcnow()
        
        # Enqueue task
        if delay_seconds > 0:
            task = send_whatsapp_message_task.apply_async(
                args=[message.dict()],
                countdown=delay_seconds,
                queue=queue_name
            )
        else:
            task = send_whatsapp_message_task.apply_async(
                args=[message.dict()],
                queue=queue_name
            )
        
        # Store message in Redis for tracking
        self._store_message_tracking(message.message_id, task.id, message)
        
        logger.info(
            f"Enqueued message {message.message_id} to {message.to_number} "
            f"in queue {queue_name} with task ID {task.id}"
        )
        
        return task.id
    
    def enqueue_incoming_message_processing(
        self,
        message: WhatsAppIncomingMessage
    ) -> str:
        """
        Enqueue an incoming WhatsApp message for processing.
        
        Args:
            message: Incoming WhatsApp message
            
        Returns:
            Task ID for tracking
        """
        # Always use high priority for incoming messages
        task = process_incoming_message_task.apply_async(
            args=[message.dict()],
            queue=self.high_priority_queue
        )
        
        logger.info(
            f"Enqueued incoming message {message.message_id} from {message.from_number} "
            f"with task ID {task.id}"
        )
        
        return task.id
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get status of a queued task.
        
        Args:
            task_id: Celery task ID
            
        Returns:
            Task status information
        """
        result = AsyncResult(task_id, app=self.celery)
        
        return {
            "task_id": task_id,
            "state": result.state,
            "info": result.info,
            "ready": result.ready(),
            "successful": result.successful() if result.ready() else None,
            "failed": result.failed() if result.ready() else None
        }
    
    def get_message_status(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a message by message ID.
        
        Args:
            message_id: Internal message ID
            
        Returns:
            Message status information or None
        """
        tracking_key = f"whatsapp_message:{message_id}"
        tracking_data = self.redis_client.get(tracking_key)
        
        if not tracking_data:
            return None
        
        return json.loads(tracking_data)
    
    def update_message_status(
        self,
        message_id: str,
        status: WhatsAppMessageStatus,
        **kwargs
    ) -> bool:
        """
        Update message status in tracking.
        
        Args:
            message_id: Internal message ID
            status: New message status
            **kwargs: Additional fields to update
            
        Returns:
            True if updated, False if message not found
        """
        tracking_key = f"whatsapp_message:{message_id}"
        tracking_data = self.redis_client.get(tracking_key)
        
        if not tracking_data:
            return False
        
        data = json.loads(tracking_data)
        data["status"] = status.value
        data["updated_at"] = datetime.utcnow().isoformat()
        
        # Update additional fields
        for key, value in kwargs.items():
            data[key] = value
        
        # Store updated data
        self.redis_client.setex(
            tracking_key,
            timedelta(days=7),  # Keep for 7 days
            json.dumps(data)
        )
        
        return True
    
    def check_rate_limit(self, phone_number: str, limit: int = 10, window_seconds: int = 60) -> bool:
        """
        Check if sending to a phone number would exceed rate limit.
        
        Args:
            phone_number: Phone number to check
            limit: Maximum messages allowed in window
            window_seconds: Time window in seconds
            
        Returns:
            True if within rate limit, False if exceeded
        """
        rate_limit_key = f"{self.rate_limit_key_prefix}:{phone_number}"
        
        # Get current count
        current_count = self.redis_client.get(rate_limit_key)
        
        if current_count is None:
            # First message in window
            self.redis_client.setex(rate_limit_key, window_seconds, 1)
            return True
        
        current_count = int(current_count)
        
        if current_count >= limit:
            logger.warning(f"Rate limit exceeded for {phone_number}: {current_count}/{limit}")
            return False
        
        # Increment count
        self.redis_client.incr(rate_limit_key)
        return True
    
    def get_queue_length(self, queue_name: Optional[str] = None) -> Dict[str, int]:
        """
        Get length of message queues.
        
        Args:
            queue_name: Optional specific queue name
            
        Returns:
            Dictionary of queue names to lengths
        """
        if queue_name:
            queues = [queue_name]
        else:
            queues = [
                self.high_priority_queue,
                self.normal_priority_queue,
                self.low_priority_queue
            ]
        
        lengths = {}
        for queue in queues:
            length = self.redis_client.llen(queue)
            lengths[queue] = length
        
        return lengths
    
    def _get_queue_for_priority(self, priority: int) -> str:
        """Get queue name based on message priority."""
        if priority <= 3:
            return self.high_priority_queue
        elif priority <= 7:
            return self.normal_priority_queue
        else:
            return self.low_priority_queue
    
    def _store_message_tracking(
        self,
        message_id: str,
        task_id: str,
        message: WhatsAppOutgoingMessage
    ) -> None:
        """Store message tracking information in Redis."""
        tracking_key = f"whatsapp_message:{message_id}"
        
        tracking_data = {
            "message_id": message_id,
            "task_id": task_id,
            "to_number": message.to_number,
            "message_type": message.message_type.value,
            "status": message.status.value,
            "priority": message.priority,
            "created_at": message.created_at.isoformat(),
            "queued_at": message.queued_at.isoformat() if message.queued_at else None,
            "conversation_id": message.conversation_id,
            "farmer_id": message.farmer_id
        }
        
        # Store with 7-day expiration
        self.redis_client.setex(
            tracking_key,
            timedelta(days=7),
            json.dumps(tracking_data)
        )


# Celery tasks
@celery_app.task(bind=True, max_retries=3)
def send_whatsapp_message_task(self: Task, message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Celery task to send WhatsApp message.
    
    Args:
        message_data: WhatsApp message data
        
    Returns:
        Result dictionary with status
    """
    from .client import WhatsAppClient
    import asyncio
    
    try:
        # Reconstruct message object
        message = WhatsAppOutgoingMessage(**message_data)
        
        # Create client and send message
        client = WhatsAppClient()
        
        # Run async send in event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is already running, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result_message = loop.run_until_complete(
            _send_message_by_type(client, message)
        )
        
        loop.run_until_complete(client.close())
        
        # Update tracking
        queue = WhatsAppMessageQueue()
        queue.update_message_status(
            message.message_id,
            result_message.status,
            whatsapp_message_id=result_message.whatsapp_message_id,
            sent_at=result_message.sent_at.isoformat() if result_message.sent_at else None,
            error_message=result_message.error_message
        )
        
        if result_message.status == WhatsAppMessageStatus.FAILED:
            # Retry if not at max retries
            if message.retry_count < message.max_retries:
                message.retry_count += 1
                raise self.retry(countdown=60 * (2 ** message.retry_count))  # Exponential backoff
        
        return {
            "success": result_message.status == WhatsAppMessageStatus.SENT,
            "message_id": message.message_id,
            "whatsapp_message_id": result_message.whatsapp_message_id,
            "status": result_message.status.value
        }
        
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {e}", exc_info=True)
        
        # Update tracking with failure
        queue = WhatsAppMessageQueue()
        queue.update_message_status(
            message_data["message_id"],
            WhatsAppMessageStatus.FAILED,
            error_message=str(e)
        )
        
        raise


@celery_app.task(bind=True)
def process_incoming_message_task(self: Task, message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Celery task to process incoming WhatsApp message.
    
    Args:
        message_data: Incoming message data
        
    Returns:
        Processing result
    """
    from .processor import WhatsAppMessageProcessor
    import asyncio
    
    try:
        # Reconstruct message object
        message = WhatsAppIncomingMessage(**message_data)
        
        logger.info(f"Processing incoming message {message.message_id} from {message.from_number}")
        
        # Create processor and process message
        processor = WhatsAppMessageProcessor()
        
        # Run async processing in event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        response_message = loop.run_until_complete(
            processor.process_message(message)
        )
        
        # If response generated, queue it for sending
        if response_message:
            queue = WhatsAppMessageQueue()
            task_id = queue.enqueue_outgoing_message(response_message)
            
            logger.info(f"Queued response message: {task_id}")
        
        loop.run_until_complete(processor.close())
        
        return {
            "success": True,
            "message_id": message.message_id,
            "from_number": message.from_number,
            "response_queued": response_message is not None
        }
        
    except Exception as e:
        logger.error(f"Failed to process incoming message: {e}", exc_info=True)
        raise


async def _send_message_by_type(
    client: 'WhatsAppClient',
    message: WhatsAppOutgoingMessage
) -> WhatsAppOutgoingMessage:
    """Helper to send message based on type."""
    from .models import WhatsAppMessageType
    
    if message.message_type == WhatsAppMessageType.TEXT:
        return await client.send_text_message(
            message.to_number,
            message.text,
            message.context_message_id
        )
    elif message.message_type == WhatsAppMessageType.IMAGE:
        return await client.send_image_message(
            message.to_number,
            message.media_url,
            message.media_id,
            message.caption,
            message.context_message_id
        )
    elif message.message_type == WhatsAppMessageType.AUDIO:
        return await client.send_audio_message(
            message.to_number,
            message.media_url,
            message.media_id,
            message.context_message_id
        )
    elif message.message_type == WhatsAppMessageType.DOCUMENT:
        return await client.send_document_message(
            message.to_number,
            message.media_url,
            message.media_id,
            message.filename,
            message.caption,
            message.context_message_id
        )
    elif message.message_type == WhatsAppMessageType.LOCATION:
        return await client.send_location_message(
            message.to_number,
            message.location.latitude,
            message.location.longitude,
            message.location.name,
            message.location.address,
            message.context_message_id
        )
    else:
        raise ValueError(f"Unsupported message type: {message.message_type}")
