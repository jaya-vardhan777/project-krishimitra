"""
Security monitoring and anomaly detection for KrishiMitra platform.

This module provides real-time security monitoring, anomaly detection,
and threat identification using Python ML libraries and AWS CloudWatch.
"""

import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from pydantic import BaseModel, Field
import boto3
from botocore.exceptions import ClientError
import numpy as np
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class ThreatLevel(str, Enum):
    """Threat severity levels."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(str, Enum):
    """Types of security threats."""
    
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    BRUTE_FORCE_ATTACK = "brute_force_attack"
    DATA_EXFILTRATION = "data_exfiltration"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    SQL_INJECTION = "sql_injection"
    XSS_ATTACK = "xss_attack"
    DOS_ATTACK = "dos_attack"


class SecurityEvent(BaseModel):
    """Model for security event."""
    
    event_id: str = Field(..., description="Unique event ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    threat_type: ThreatType = Field(..., description="Type of threat")
    threat_level: ThreatLevel = Field(..., description="Severity level")
    source_ip: Optional[str] = Field(None, description="Source IP address")
    user_id: Optional[str] = Field(None, description="User ID if authenticated")
    resource: Optional[str] = Field(None, description="Affected resource")
    description: str = Field(..., description="Event description")
    indicators: Dict[str, Any] = Field(default_factory=dict, description="Threat indicators")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class SecurityMonitor:
    """
    Security monitoring system for detecting threats and anomalies.
    
    Provides real-time monitoring of security events, anomaly detection,
    and threat identification using statistical analysis and pattern matching.
    """
    
    def __init__(
        self,
        cloudwatch_namespace: str = "KrishiMitra/Security",
        alert_sns_topic: Optional[str] = None
    ):
        """
        Initialize security monitor.
        
        Args:
            cloudwatch_namespace: CloudWatch namespace for metrics
            alert_sns_topic: SNS topic ARN for alerts
        """
        self.cloudwatch_namespace = cloudwatch_namespace
        self.alert_sns_topic = alert_sns_topic
        
        # Initialize AWS clients
        self.cloudwatch = boto3.client('cloudwatch')
        self.sns = boto3.client('sns') if alert_sns_topic else None
        self.dynamodb = boto3.resource('dynamodb')
        
        # In-memory tracking for anomaly detection
        self.login_attempts = defaultdict(lambda: deque(maxlen=100))
        self.api_requests = defaultdict(lambda: deque(maxlen=1000))
        self.failed_auth = defaultdict(lambda: deque(maxlen=50))
        
        # Thresholds for anomaly detection
        self.thresholds = {
            "max_login_attempts_per_minute": 5,
            "max_failed_auth_per_hour": 10,
            "max_api_requests_per_minute": 100,
            "max_data_access_per_minute": 50,
            "unusual_access_time_hours": [0, 1, 2, 3, 4, 5]  # 12 AM - 6 AM
        }
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        import uuid
        return f"SEC_{datetime.utcnow().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
    
    def _publish_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "Count",
        dimensions: Optional[List[Dict[str, str]]] = None
    ) -> None:
        """
        Publish metric to CloudWatch.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: Unit of measurement
            dimensions: Metric dimensions
        """
        try:
            metric_data = {
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit,
                'Timestamp': datetime.utcnow()
            }
            
            if dimensions:
                metric_data['Dimensions'] = dimensions
            
            self.cloudwatch.put_metric_data(
                Namespace=self.cloudwatch_namespace,
                MetricData=[metric_data]
            )
        
        except ClientError as e:
            logger.error(f"Failed to publish metric: {e}")
    
    def _send_alert(
        self,
        subject: str,
        message: str,
        threat_level: ThreatLevel
    ) -> None:
        """
        Send security alert via SNS.
        
        Args:
            subject: Alert subject
            message: Alert message
            threat_level: Threat severity level
        """
        if not self.sns or not self.alert_sns_topic:
            logger.warning("SNS not configured, alert not sent")
            return
        
        try:
            self.sns.publish(
                TopicArn=self.alert_sns_topic,
                Subject=f"[{threat_level.upper()}] {subject}",
                Message=message,
                MessageAttributes={
                    'threat_level': {
                        'DataType': 'String',
                        'StringValue': threat_level.value
                    }
                }
            )
            logger.info(f"Sent security alert: {subject}")
        
        except ClientError as e:
            logger.error(f"Failed to send alert: {e}")
    
    def detect_brute_force(
        self,
        user_id: str,
        source_ip: str,
        success: bool
    ) -> Optional[SecurityEvent]:
        """
        Detect brute force login attempts.
        
        Args:
            user_id: User ID attempting login
            source_ip: Source IP address
            success: Whether login was successful
            
        Returns:
            Security event if threat detected, None otherwise
        """
        now = datetime.utcnow()
        key = f"{user_id}_{source_ip}"
        
        # Track login attempt
        self.login_attempts[key].append((now, success))
        
        # Count failed attempts in last minute
        one_minute_ago = now - timedelta(minutes=1)
        recent_attempts = [
            (ts, s) for ts, s in self.login_attempts[key]
            if ts > one_minute_ago
        ]
        
        failed_count = sum(1 for _, s in recent_attempts if not s)
        
        # Check if threshold exceeded
        if failed_count >= self.thresholds["max_login_attempts_per_minute"]:
            event = SecurityEvent(
                event_id=self._generate_event_id(),
                threat_type=ThreatType.BRUTE_FORCE_ATTACK,
                threat_level=ThreatLevel.HIGH,
                source_ip=source_ip,
                user_id=user_id,
                description=f"Brute force attack detected: {failed_count} failed login attempts in 1 minute",
                indicators={
                    "failed_attempts": failed_count,
                    "time_window": "1 minute",
                    "threshold": self.thresholds["max_login_attempts_per_minute"]
                }
            )
            
            # Publish metric
            self._publish_metric(
                "BruteForceAttempts",
                failed_count,
                dimensions=[
                    {"Name": "SourceIP", "Value": source_ip},
                    {"Name": "UserID", "Value": user_id}
                ]
            )
            
            # Send alert
            self._send_alert(
                "Brute Force Attack Detected",
                f"Multiple failed login attempts detected for user {user_id} from IP {source_ip}",
                ThreatLevel.HIGH
            )
            
            return event
        
        return None
    
    def detect_unusual_access_pattern(
        self,
        user_id: str,
        resource: str,
        access_count: int,
        time_window_minutes: int = 1
    ) -> Optional[SecurityEvent]:
        """
        Detect unusual data access patterns.
        
        Args:
            user_id: User ID
            resource: Resource being accessed
            access_count: Number of accesses
            time_window_minutes: Time window for counting
            
        Returns:
            Security event if anomaly detected, None otherwise
        """
        threshold = self.thresholds["max_data_access_per_minute"]
        
        if access_count > threshold:
            event = SecurityEvent(
                event_id=self._generate_event_id(),
                threat_type=ThreatType.DATA_EXFILTRATION,
                threat_level=ThreatLevel.MEDIUM,
                user_id=user_id,
                resource=resource,
                description=f"Unusual data access pattern: {access_count} accesses in {time_window_minutes} minute(s)",
                indicators={
                    "access_count": access_count,
                    "time_window_minutes": time_window_minutes,
                    "threshold": threshold
                }
            )
            
            # Publish metric
            self._publish_metric(
                "UnusualDataAccess",
                access_count,
                dimensions=[
                    {"Name": "UserID", "Value": user_id},
                    {"Name": "Resource", "Value": resource}
                ]
            )
            
            # Send alert for high volume
            if access_count > threshold * 2:
                self._send_alert(
                    "Potential Data Exfiltration",
                    f"User {user_id} accessed {resource} {access_count} times in {time_window_minutes} minute(s)",
                    ThreatLevel.MEDIUM
                )
            
            return event
        
        return None
    
    def detect_privilege_escalation(
        self,
        user_id: str,
        old_role: str,
        new_role: str,
        authorized_by: Optional[str] = None
    ) -> Optional[SecurityEvent]:
        """
        Detect unauthorized privilege escalation attempts.
        
        Args:
            user_id: User ID
            old_role: Previous role
            new_role: New role
            authorized_by: User who authorized the change
            
        Returns:
            Security event if suspicious, None otherwise
        """
        # Define role hierarchy
        role_hierarchy = {
            "farmer": 0,
            "agent": 1,
            "supervisor": 2,
            "admin": 3,
            "system": 4
        }
        
        old_level = role_hierarchy.get(old_role.lower(), 0)
        new_level = role_hierarchy.get(new_role.lower(), 0)
        
        # Check if escalation is significant (more than 1 level)
        if new_level > old_level + 1:
            event = SecurityEvent(
                event_id=self._generate_event_id(),
                threat_type=ThreatType.PRIVILEGE_ESCALATION,
                threat_level=ThreatLevel.HIGH,
                user_id=user_id,
                description=f"Significant privilege escalation: {old_role} -> {new_role}",
                indicators={
                    "old_role": old_role,
                    "new_role": new_role,
                    "level_jump": new_level - old_level,
                    "authorized_by": authorized_by
                }
            )
            
            # Publish metric
            self._publish_metric(
                "PrivilegeEscalation",
                new_level - old_level,
                dimensions=[
                    {"Name": "UserID", "Value": user_id},
                    {"Name": "NewRole", "Value": new_role}
                ]
            )
            
            # Send alert
            self._send_alert(
                "Privilege Escalation Detected",
                f"User {user_id} escalated from {old_role} to {new_role}. Authorized by: {authorized_by or 'Unknown'}",
                ThreatLevel.HIGH
            )
            
            return event
        
        return None
    
    def detect_sql_injection(
        self,
        user_id: Optional[str],
        source_ip: str,
        query_string: str
    ) -> Optional[SecurityEvent]:
        """
        Detect potential SQL injection attempts.
        
        Args:
            user_id: User ID if authenticated
            source_ip: Source IP address
            query_string: Query string to analyze
            
        Returns:
            Security event if SQL injection detected, None otherwise
        """
        # Common SQL injection patterns
        sql_patterns = [
            "' OR '1'='1",
            "' OR 1=1",
            "'; DROP TABLE",
            "'; DELETE FROM",
            "UNION SELECT",
            "' UNION SELECT",
            "exec(",
            "execute(",
            "xp_cmdshell"
        ]
        
        query_lower = query_string.lower()
        detected_patterns = [p for p in sql_patterns if p.lower() in query_lower]
        
        if detected_patterns:
            event = SecurityEvent(
                event_id=self._generate_event_id(),
                threat_type=ThreatType.SQL_INJECTION,
                threat_level=ThreatLevel.CRITICAL,
                source_ip=source_ip,
                user_id=user_id,
                description="SQL injection attempt detected",
                indicators={
                    "detected_patterns": detected_patterns,
                    "query_sample": query_string[:200]  # First 200 chars
                }
            )
            
            # Publish metric
            self._publish_metric(
                "SQLInjectionAttempts",
                1,
                dimensions=[
                    {"Name": "SourceIP", "Value": source_ip}
                ]
            )
            
            # Send alert
            self._send_alert(
                "SQL Injection Attempt Detected",
                f"SQL injection attempt from IP {source_ip}. User: {user_id or 'Anonymous'}",
                ThreatLevel.CRITICAL
            )
            
            return event
        
        return None
    
    def detect_dos_attack(
        self,
        source_ip: str,
        request_count: int,
        time_window_seconds: int = 60
    ) -> Optional[SecurityEvent]:
        """
        Detect potential DoS/DDoS attacks.
        
        Args:
            source_ip: Source IP address
            request_count: Number of requests
            time_window_seconds: Time window for counting
            
        Returns:
            Security event if DoS detected, None otherwise
        """
        threshold = self.thresholds["max_api_requests_per_minute"]
        
        if request_count > threshold:
            event = SecurityEvent(
                event_id=self._generate_event_id(),
                threat_type=ThreatType.DOS_ATTACK,
                threat_level=ThreatLevel.HIGH,
                source_ip=source_ip,
                description=f"Potential DoS attack: {request_count} requests in {time_window_seconds} seconds",
                indicators={
                    "request_count": request_count,
                    "time_window_seconds": time_window_seconds,
                    "threshold": threshold
                }
            )
            
            # Publish metric
            self._publish_metric(
                "DoSAttempts",
                request_count,
                dimensions=[
                    {"Name": "SourceIP", "Value": source_ip}
                ]
            )
            
            # Send alert
            self._send_alert(
                "Potential DoS Attack",
                f"High request rate from IP {source_ip}: {request_count} requests in {time_window_seconds} seconds",
                ThreatLevel.HIGH
            )
            
            return event
        
        return None
    
    def analyze_access_time(
        self,
        user_id: str,
        access_time: datetime
    ) -> Optional[SecurityEvent]:
        """
        Analyze if access time is unusual.
        
        Args:
            user_id: User ID
            access_time: Time of access
            
        Returns:
            Security event if unusual time detected, None otherwise
        """
        hour = access_time.hour
        
        if hour in self.thresholds["unusual_access_time_hours"]:
            event = SecurityEvent(
                event_id=self._generate_event_id(),
                threat_type=ThreatType.SUSPICIOUS_ACTIVITY,
                threat_level=ThreatLevel.LOW,
                user_id=user_id,
                description=f"Access during unusual hours: {hour}:00",
                indicators={
                    "access_hour": hour,
                    "access_time": access_time.isoformat()
                }
            )
            
            # Publish metric
            self._publish_metric(
                "UnusualAccessTime",
                1,
                dimensions=[
                    {"Name": "UserID", "Value": user_id},
                    {"Name": "Hour", "Value": str(hour)}
                ]
            )
            
            return event
        
        return None
    
    def get_security_metrics(
        self,
        start_time: datetime,
        end_time: datetime,
        metric_names: Optional[List[str]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get security metrics from CloudWatch.
        
        Args:
            start_time: Start time for metrics
            end_time: End time for metrics
            metric_names: List of metric names to retrieve
            
        Returns:
            Dictionary of metrics and their data points
        """
        if not metric_names:
            metric_names = [
                "BruteForceAttempts",
                "UnusualDataAccess",
                "PrivilegeEscalation",
                "SQLInjectionAttempts",
                "DoSAttempts"
            ]
        
        metrics_data = {}
        
        for metric_name in metric_names:
            try:
                response = self.cloudwatch.get_metric_statistics(
                    Namespace=self.cloudwatch_namespace,
                    MetricName=metric_name,
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,  # 5 minutes
                    Statistics=['Sum', 'Average', 'Maximum']
                )
                
                metrics_data[metric_name] = response.get('Datapoints', [])
            
            except ClientError as e:
                logger.error(f"Failed to get metric {metric_name}: {e}")
                metrics_data[metric_name] = []
        
        return metrics_data


# Global security monitor instance
_security_monitor = None


def get_security_monitor() -> SecurityMonitor:
    """Get global security monitor instance."""
    global _security_monitor
    if _security_monitor is None:
        _security_monitor = SecurityMonitor()
    return _security_monitor
