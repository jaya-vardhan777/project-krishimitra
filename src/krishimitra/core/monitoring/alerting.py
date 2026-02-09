"""
Alerting system for KrishiMitra platform.

This module implements comprehensive alerting for service failures,
performance issues, and system anomalies.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertCategory(Enum):
    """Alert categories."""
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    SECURITY = "security"
    DATA_QUALITY = "data_quality"
    CAPACITY = "capacity"
    COST = "cost"


@dataclass
class Alert:
    """Alert data structure."""
    alert_id: str
    severity: AlertSeverity
    category: AlertCategory
    title: str
    description: str
    component: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metrics: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None


class AlertManager:
    """
    Manages alerts for KrishiMitra platform.
    
    Implements alert creation, notification, tracking, and resolution
    for system issues and anomalies.
    """
    
    def __init__(
        self,
        region: str = "ap-south-1",
        sns_topic_arn: Optional[str] = None
    ):
        """
        Initialize alert manager.
        
        Args:
            region: AWS region
            sns_topic_arn: SNS topic ARN for alert notifications
        """
        self.region = region
        self.sns_topic_arn = sns_topic_arn
        
        # AWS clients
        self.sns_client = boto3.client('sns', region_name=region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        
        # Alert storage
        self.alerts_table_name = 'KrishiMitra-Alerts'
        self._ensure_alerts_table()
    
    def _ensure_alerts_table(self):
        """Ensure alerts table exists."""
        try:
            self.alerts_table = self.dynamodb.Table(self.alerts_table_name)
            # Test table exists
            self.alerts_table.table_status
        except Exception:
            logger.warning(f"Alerts table {self.alerts_table_name} not found")
            self.alerts_table = None
    
    def create_alert(
        self,
        severity: AlertSeverity,
        category: AlertCategory,
        title: str,
        description: str,
        component: str,
        metrics: Optional[Dict[str, Any]] = None,
        notify: bool = True
    ) -> Alert:
        """
        Create a new alert.
        
        Args:
            severity: Alert severity
            category: Alert category
            title: Alert title
            description: Alert description
            component: Component name
            metrics: Additional metrics
            notify: Whether to send notification
            
        Returns:
            Created alert
        """
        alert_id = f"{component}_{datetime.utcnow().timestamp()}"
        
        alert = Alert(
            alert_id=alert_id,
            severity=severity,
            category=category,
            title=title,
            description=description,
            component=component,
            metrics=metrics or {}
        )
        
        # Store alert
        self._store_alert(alert)
        
        # Send notification if requested
        if notify:
            self._send_notification(alert)
        
        # Create CloudWatch alarm if critical
        if severity == AlertSeverity.CRITICAL:
            self._create_cloudwatch_alarm(alert)
        
        logger.info(f"Created alert: {alert_id} - {title}")
        return alert
    
    def resolve_alert(
        self,
        alert_id: str,
        resolution_notes: Optional[str] = None
    ) -> bool:
        """
        Resolve an alert.
        
        Args:
            alert_id: Alert ID
            resolution_notes: Resolution notes
            
        Returns:
            True if resolved successfully
        """
        try:
            if not self.alerts_table:
                return False
            
            self.alerts_table.update_item(
                Key={'alert_id': alert_id},
                UpdateExpression='SET resolved = :r, resolved_at = :ra, resolution_notes = :rn',
                ExpressionAttributeValues={
                    ':r': True,
                    ':ra': datetime.utcnow().isoformat(),
                    ':rn': resolution_notes or ''
                }
            )
            
            logger.info(f"Resolved alert: {alert_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to resolve alert: {e}")
            return False
    
    def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        category: Optional[AlertCategory] = None,
        component: Optional[str] = None
    ) -> List[Alert]:
        """
        Get active (unresolved) alerts.
        
        Args:
            severity: Filter by severity
            category: Filter by category
            component: Filter by component
            
        Returns:
            List of active alerts
        """
        try:
            if not self.alerts_table:
                return []
            
            # Scan for unresolved alerts
            filter_expression = 'resolved = :r'
            expression_values = {':r': False}
            
            if severity:
                filter_expression += ' AND severity = :s'
                expression_values[':s'] = severity.value
            
            if category:
                filter_expression += ' AND category = :c'
                expression_values[':c'] = category.value
            
            if component:
                filter_expression += ' AND component = :comp'
                expression_values[':comp'] = component
            
            response = self.alerts_table.scan(
                FilterExpression=filter_expression,
                ExpressionAttributeValues=expression_values
            )
            
            alerts = []
            for item in response.get('Items', []):
                alert = Alert(
                    alert_id=item['alert_id'],
                    severity=AlertSeverity(item['severity']),
                    category=AlertCategory(item['category']),
                    title=item['title'],
                    description=item['description'],
                    component=item['component'],
                    timestamp=datetime.fromisoformat(item['timestamp']),
                    metrics=item.get('metrics', {}),
                    resolved=item.get('resolved', False)
                )
                alerts.append(alert)
            
            return alerts
        except Exception as e:
            logger.error(f"Failed to get active alerts: {e}")
            return []
    
    def get_alert_summary(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get summary of alerts for the specified time period.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Alert summary statistics
        """
        try:
            if not self.alerts_table:
                return {
                    'total_alerts': 0,
                    'by_severity': {},
                    'by_category': {},
                    'active_alerts': 0
                }
            
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            response = self.alerts_table.scan()
            items = response.get('Items', [])
            
            # Filter by time
            recent_alerts = [
                item for item in items
                if datetime.fromisoformat(item['timestamp']) >= cutoff_time
            ]
            
            # Calculate statistics
            by_severity = {}
            by_category = {}
            active_count = 0
            
            for alert in recent_alerts:
                # Count by severity
                severity = alert['severity']
                by_severity[severity] = by_severity.get(severity, 0) + 1
                
                # Count by category
                category = alert['category']
                by_category[category] = by_category.get(category, 0) + 1
                
                # Count active
                if not alert.get('resolved', False):
                    active_count += 1
            
            return {
                'total_alerts': len(recent_alerts),
                'by_severity': by_severity,
                'by_category': by_category,
                'active_alerts': active_count,
                'time_period_hours': hours
            }
        except Exception as e:
            logger.error(f"Failed to get alert summary: {e}")
            return {
                'total_alerts': 0,
                'by_severity': {},
                'by_category': {},
                'active_alerts': 0,
                'error': str(e)
            }
    
    def _store_alert(self, alert: Alert):
        """Store alert in DynamoDB."""
        try:
            if not self.alerts_table:
                return
            
            self.alerts_table.put_item(
                Item={
                    'alert_id': alert.alert_id,
                    'severity': alert.severity.value,
                    'category': alert.category.value,
                    'title': alert.title,
                    'description': alert.description,
                    'component': alert.component,
                    'timestamp': alert.timestamp.isoformat(),
                    'metrics': alert.metrics,
                    'resolved': alert.resolved
                }
            )
        except Exception as e:
            logger.error(f"Failed to store alert: {e}")
    
    def _send_notification(self, alert: Alert):
        """Send alert notification via SNS."""
        try:
            if not self.sns_topic_arn:
                logger.warning("SNS topic ARN not configured, skipping notification")
                return
            
            subject = f"[{alert.severity.value.upper()}] {alert.title}"
            message = f"""
Alert Details:
--------------
Severity: {alert.severity.value}
Category: {alert.category.value}
Component: {alert.component}
Time: {alert.timestamp.isoformat()}

Description:
{alert.description}

Metrics:
{self._format_metrics(alert.metrics)}
"""
            
            self.sns_client.publish(
                TopicArn=self.sns_topic_arn,
                Subject=subject,
                Message=message
            )
            
            logger.info(f"Sent notification for alert: {alert.alert_id}")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
    
    def _create_cloudwatch_alarm(self, alert: Alert):
        """Create CloudWatch alarm for critical alerts."""
        try:
            alarm_name = f"KrishiMitra-{alert.component}-{alert.category.value}"
            
            self.cloudwatch_client.put_metric_alarm(
                AlarmName=alarm_name,
                AlarmDescription=alert.description,
                ActionsEnabled=True,
                AlarmActions=[self.sns_topic_arn] if self.sns_topic_arn else [],
                MetricName='CriticalAlert',
                Namespace='KrishiMitra/Alerts',
                Statistic='Sum',
                Period=300,
                EvaluationPeriods=1,
                Threshold=1.0,
                ComparisonOperator='GreaterThanThreshold'
            )
            
            logger.info(f"Created CloudWatch alarm: {alarm_name}")
        except Exception as e:
            logger.error(f"Failed to create CloudWatch alarm: {e}")
    
    def _format_metrics(self, metrics: Dict[str, Any]) -> str:
        """Format metrics for notification message."""
        if not metrics:
            return "No additional metrics"
        
        lines = []
        for key, value in metrics.items():
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)


from datetime import timedelta
