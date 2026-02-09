"""
Security breach detection and response for KrishiMitra platform.

This module provides breach detection, notification, and containment procedures
to ensure rapid response to security incidents.
"""

import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass
from pydantic import BaseModel, Field
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class BreachType(str, Enum):
    """Types of security breaches."""
    
    DATA_BREACH = "data_breach"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    SYSTEM_COMPROMISE = "system_compromise"
    MALWARE_INFECTION = "malware_infection"
    INSIDER_THREAT = "insider_threat"
    ACCOUNT_TAKEOVER = "account_takeover"


class BreachSeverity(str, Enum):
    """Severity levels for breaches."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BreachStatus(str, Enum):
    """Status of breach response."""
    
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    CONTAINED = "contained"
    MITIGATED = "mitigated"
    RESOLVED = "resolved"


class NotificationStatus(str, Enum):
    """Status of breach notifications."""
    
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class BreachIncident(BaseModel):
    """Model for security breach incident."""
    
    incident_id: str = Field(..., description="Unique incident ID")
    breach_type: BreachType = Field(..., description="Type of breach")
    severity: BreachSeverity = Field(..., description="Severity level")
    status: BreachStatus = Field(default=BreachStatus.DETECTED)
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    contained_at: Optional[datetime] = Field(None)
    resolved_at: Optional[datetime] = Field(None)
    affected_users: List[str] = Field(default_factory=list, description="List of affected farmer IDs")
    affected_data_types: List[str] = Field(default_factory=list)
    description: str = Field(..., description="Incident description")
    indicators: Dict[str, Any] = Field(default_factory=dict)
    containment_actions: List[str] = Field(default_factory=list)
    mitigation_actions: List[str] = Field(default_factory=list)
    notifications_sent: Dict[str, NotificationStatus] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class BreachResponseManager:
    """
    Manager for security breach detection, notification, and response.
    
    Provides automated breach detection, farmer notification within 24 hours,
    and containment procedures to minimize impact.
    """
    
    def __init__(
        self,
        incident_table_name: str = "SecurityIncidents",
        notification_sns_topic: Optional[str] = None,
        notification_deadline_hours: int = 24
    ):
        """
        Initialize breach response manager.
        
        Args:
            incident_table_name: DynamoDB table for incidents
            notification_sns_topic: SNS topic for notifications
            notification_deadline_hours: Hours within which to notify (default 24)
        """
        self.incident_table_name = incident_table_name
        self.notification_sns_topic = notification_sns_topic
        self.notification_deadline_hours = notification_deadline_hours
        
        # Initialize AWS clients
        self.dynamodb = boto3.resource('dynamodb')
        self.sns = boto3.client('sns') if notification_sns_topic else None
        self.ses = boto3.client('ses')
        self.lambda_client = boto3.client('lambda')
        
        self.incident_table = None
        try:
            self.incident_table = self.dynamodb.Table(self.incident_table_name)
        except Exception as e:
            logger.warning(f"Could not connect to incident table: {e}")
    
    def _generate_incident_id(self) -> str:
        """Generate unique incident ID."""
        import uuid
        return f"INC_{datetime.utcnow().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
    
    def create_incident(
        self,
        breach_type: BreachType,
        severity: BreachSeverity,
        description: str,
        affected_users: Optional[List[str]] = None,
        affected_data_types: Optional[List[str]] = None,
        indicators: Optional[Dict[str, Any]] = None
    ) -> BreachIncident:
        """
        Create a new security breach incident.
        
        Args:
            breach_type: Type of breach
            severity: Severity level
            description: Incident description
            affected_users: List of affected farmer IDs
            affected_data_types: Types of data affected
            indicators: Breach indicators
            
        Returns:
            Breach incident record
        """
        incident_id = self._generate_incident_id()
        
        incident = BreachIncident(
            incident_id=incident_id,
            breach_type=breach_type,
            severity=severity,
            description=description,
            affected_users=affected_users or [],
            affected_data_types=affected_data_types or [],
            indicators=indicators or {}
        )
        
        # Store in DynamoDB
        if self.incident_table:
            try:
                self.incident_table.put_item(Item=json.loads(incident.json()))
                logger.info(f"Created security incident {incident_id}")
            except ClientError as e:
                logger.error(f"Failed to store incident: {e}")
        
        # Trigger immediate containment for critical breaches
        if severity == BreachSeverity.CRITICAL:
            self._trigger_containment(incident)
        
        return incident
    
    def _trigger_containment(self, incident: BreachIncident) -> None:
        """
        Trigger automated containment procedures.
        
        Args:
            incident: Breach incident
        """
        logger.info(f"Triggering containment for incident {incident.incident_id}")
        
        containment_actions = []
        
        # Containment actions based on breach type
        if incident.breach_type == BreachType.UNAUTHORIZED_ACCESS:
            # Revoke access tokens
            containment_actions.append("revoke_access_tokens")
            self._revoke_affected_tokens(incident.affected_users)
        
        elif incident.breach_type == BreachType.ACCOUNT_TAKEOVER:
            # Lock affected accounts
            containment_actions.append("lock_accounts")
            self._lock_affected_accounts(incident.affected_users)
        
        elif incident.breach_type == BreachType.DATA_BREACH:
            # Enable additional monitoring
            containment_actions.append("enable_enhanced_monitoring")
            self._enable_enhanced_monitoring(incident.affected_users)
        
        elif incident.breach_type == BreachType.SYSTEM_COMPROMISE:
            # Isolate affected systems
            containment_actions.append("isolate_systems")
            self._isolate_systems(incident.indicators.get("affected_systems", []))
        
        # Update incident with containment actions
        if self.incident_table and containment_actions:
            try:
                self.incident_table.update_item(
                    Key={"incident_id": incident.incident_id},
                    UpdateExpression="SET containment_actions = :actions, #status = :status, contained_at = :time",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":actions": containment_actions,
                        ":status": BreachStatus.CONTAINED.value,
                        ":time": datetime.utcnow().isoformat()
                    }
                )
            except ClientError as e:
                logger.error(f"Failed to update incident: {e}")
    
    def _revoke_affected_tokens(self, user_ids: List[str]) -> None:
        """Revoke access tokens for affected users."""
        logger.info(f"Revoking tokens for {len(user_ids)} users")
        # Implementation would revoke JWT tokens or session tokens
        # This is a placeholder for the actual implementation
        pass
    
    def _lock_affected_accounts(self, user_ids: List[str]) -> None:
        """Lock affected user accounts."""
        logger.info(f"Locking {len(user_ids)} accounts")
        # Implementation would update user status to locked
        # This is a placeholder for the actual implementation
        pass
    
    def _enable_enhanced_monitoring(self, user_ids: List[str]) -> None:
        """Enable enhanced monitoring for affected users."""
        logger.info(f"Enabling enhanced monitoring for {len(user_ids)} users")
        # Implementation would increase monitoring sensitivity
        # This is a placeholder for the actual implementation
        pass
    
    def _isolate_systems(self, systems: List[str]) -> None:
        """Isolate affected systems."""
        logger.info(f"Isolating {len(systems)} systems")
        # Implementation would update security groups or network ACLs
        # This is a placeholder for the actual implementation
        pass
    
    def notify_affected_users(
        self,
        incident_id: str,
        notification_method: str = "email"
    ) -> Dict[str, NotificationStatus]:
        """
        Notify affected users about the breach.
        
        Args:
            incident_id: Incident ID
            notification_method: Method of notification (email, sms, whatsapp)
            
        Returns:
            Dictionary of user_id to notification status
        """
        if not self.incident_table:
            logger.error("Incident table not available")
            return {}
        
        try:
            # Get incident
            response = self.incident_table.get_item(Key={"incident_id": incident_id})
            
            if "Item" not in response:
                logger.warning(f"Incident {incident_id} not found")
                return {}
            
            incident = BreachIncident(**response["Item"])
            
            # Check if notification deadline has passed
            deadline = incident.detected_at + timedelta(hours=self.notification_deadline_hours)
            if datetime.utcnow() > deadline:
                logger.warning(f"Notification deadline passed for incident {incident_id}")
            
            notification_results = {}
            
            # Notify each affected user
            for user_id in incident.affected_users:
                try:
                    if notification_method == "email":
                        self._send_email_notification(user_id, incident)
                    elif notification_method == "sms":
                        self._send_sms_notification(user_id, incident)
                    elif notification_method == "whatsapp":
                        self._send_whatsapp_notification(user_id, incident)
                    
                    notification_results[user_id] = NotificationStatus.SENT
                    logger.info(f"Notified user {user_id} about incident {incident_id}")
                
                except Exception as e:
                    logger.error(f"Failed to notify user {user_id}: {e}")
                    notification_results[user_id] = NotificationStatus.FAILED
            
            # Update incident with notification status
            self.incident_table.update_item(
                Key={"incident_id": incident_id},
                UpdateExpression="SET notifications_sent = :notifications",
                ExpressionAttributeValues={
                    ":notifications": {k: v.value for k, v in notification_results.items()}
                }
            )
            
            return notification_results
        
        except ClientError as e:
            logger.error(f"Failed to notify users: {e}")
            return {}
    
    def _send_email_notification(
        self,
        user_id: str,
        incident: BreachIncident
    ) -> None:
        """
        Send email notification to user.
        
        Args:
            user_id: User ID
            incident: Breach incident
        """
        # Get user email from database
        # This is a placeholder - actual implementation would fetch from user profile
        user_email = f"{user_id}@example.com"
        
        subject = f"Security Notification: Data Breach Alert"
        
        body = f"""
Dear Farmer,

We are writing to inform you about a security incident that may have affected your data on the KrishiMitra platform.

Incident Details:
- Incident ID: {incident.incident_id}
- Type: {incident.breach_type.value}
- Detected: {incident.detected_at.strftime('%Y-%m-%d %H:%M:%S')}
- Severity: {incident.severity.value}

What Happened:
{incident.description}

What We're Doing:
We have taken immediate steps to contain this incident and protect your data:
{chr(10).join(f'- {action}' for action in incident.containment_actions)}

What You Should Do:
1. Change your password immediately
2. Review your account activity for any suspicious actions
3. Enable two-factor authentication if not already enabled
4. Contact our support team if you notice any unusual activity

We take the security of your data very seriously and apologize for any inconvenience this may cause.

If you have any questions or concerns, please contact our support team.

Best regards,
KrishiMitra Security Team
"""
        
        try:
            self.ses.send_email(
                Source='security@krishimitra.com',
                Destination={'ToAddresses': [user_email]},
                Message={
                    'Subject': {'Data': subject},
                    'Body': {'Text': {'Data': body}}
                }
            )
        except ClientError as e:
            logger.error(f"Failed to send email: {e}")
            raise
    
    def _send_sms_notification(
        self,
        user_id: str,
        incident: BreachIncident
    ) -> None:
        """Send SMS notification to user."""
        # Placeholder implementation
        logger.info(f"Sending SMS notification to user {user_id}")
        pass
    
    def _send_whatsapp_notification(
        self,
        user_id: str,
        incident: BreachIncident
    ) -> None:
        """Send WhatsApp notification to user."""
        # Placeholder implementation
        logger.info(f"Sending WhatsApp notification to user {user_id}")
        pass
    
    def update_incident_status(
        self,
        incident_id: str,
        status: BreachStatus,
        mitigation_actions: Optional[List[str]] = None
    ) -> Optional[BreachIncident]:
        """
        Update incident status.
        
        Args:
            incident_id: Incident ID
            status: New status
            mitigation_actions: Mitigation actions taken
            
        Returns:
            Updated incident or None
        """
        if not self.incident_table:
            logger.error("Incident table not available")
            return None
        
        try:
            update_expr = "SET #status = :status"
            expr_values = {":status": status.value}
            
            if status == BreachStatus.RESOLVED:
                update_expr += ", resolved_at = :time"
                expr_values[":time"] = datetime.utcnow().isoformat()
            
            if mitigation_actions:
                update_expr += ", mitigation_actions = :actions"
                expr_values[":actions"] = mitigation_actions
            
            self.incident_table.update_item(
                Key={"incident_id": incident_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues=expr_values
            )
            
            logger.info(f"Updated incident {incident_id} to status {status.value}")
            
            # Get updated incident
            response = self.incident_table.get_item(Key={"incident_id": incident_id})
            if "Item" in response:
                return BreachIncident(**response["Item"])
            
            return None
        
        except ClientError as e:
            logger.error(f"Failed to update incident: {e}")
            return None
    
    def get_incident(self, incident_id: str) -> Optional[BreachIncident]:
        """Get incident by ID."""
        if not self.incident_table:
            return None
        
        try:
            response = self.incident_table.get_item(Key={"incident_id": incident_id})
            if "Item" in response:
                return BreachIncident(**response["Item"])
            return None
        except ClientError as e:
            logger.error(f"Failed to get incident: {e}")
            return None
    
    def get_active_incidents(
        self,
        severity: Optional[BreachSeverity] = None
    ) -> List[BreachIncident]:
        """
        Get all active (unresolved) incidents.
        
        Args:
            severity: Filter by severity
            
        Returns:
            List of active incidents
        """
        if not self.incident_table:
            return []
        
        try:
            # Scan for unresolved incidents
            filter_expr = "#status <> :resolved"
            expr_values = {":resolved": BreachStatus.RESOLVED.value}
            
            if severity:
                filter_expr += " AND severity = :severity"
                expr_values[":severity"] = severity.value
            
            response = self.incident_table.scan(
                FilterExpression=filter_expr,
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues=expr_values
            )
            
            incidents = []
            for item in response.get("Items", []):
                try:
                    incidents.append(BreachIncident(**item))
                except Exception as e:
                    logger.warning(f"Failed to parse incident: {e}")
            
            return incidents
        
        except ClientError as e:
            logger.error(f"Failed to get active incidents: {e}")
            return []
    
    def check_notification_compliance(self) -> List[str]:
        """
        Check if all breaches have been notified within deadline.
        
        Returns:
            List of incident IDs that missed notification deadline
        """
        active_incidents = self.get_active_incidents()
        missed_deadline = []
        
        for incident in active_incidents:
            deadline = incident.detected_at + timedelta(hours=self.notification_deadline_hours)
            
            if datetime.utcnow() > deadline:
                # Check if all affected users have been notified
                notified_users = set(incident.notifications_sent.keys())
                affected_users = set(incident.affected_users)
                
                if not affected_users.issubset(notified_users):
                    missed_deadline.append(incident.incident_id)
                    logger.warning(f"Incident {incident.incident_id} missed notification deadline")
        
        return missed_deadline


# Global breach response manager instance
_breach_response_manager = None


def get_breach_response_manager() -> BreachResponseManager:
    """Get global breach response manager instance."""
    global _breach_response_manager
    if _breach_response_manager is None:
        _breach_response_manager = BreachResponseManager()
    return _breach_response_manager
