"""
Log aggregation and analysis for KrishiMitra platform.

This module implements centralized log collection, analysis,
and querying using CloudWatch Logs Insights.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogQuery:
    """Log query configuration."""
    query_string: str
    log_group_names: List[str]
    start_time: datetime
    end_time: datetime
    limit: int = 1000


@dataclass
class LogInsight:
    """Log analysis insight."""
    pattern: str
    count: int
    sample_messages: List[str]
    first_occurrence: datetime
    last_occurrence: datetime


class LogAggregator:
    """
    Aggregates and analyzes logs from all KrishiMitra components.
    
    Implements centralized log collection, querying, and analysis
    using CloudWatch Logs.
    """
    
    def __init__(
        self,
        region: str = "ap-south-1",
        log_group_prefix: str = "/aws/lambda/krishimitra"
    ):
        """
        Initialize log aggregator.
        
        Args:
            region: AWS region
            log_group_prefix: Prefix for log groups to monitor
        """
        self.region = region
        self.log_group_prefix = log_group_prefix
        
        # AWS clients
        self.logs_client = boto3.client('logs', region_name=region)
    
    def query_logs(
        self,
        query: LogQuery
    ) -> List[Dict[str, Any]]:
        """
        Query logs using CloudWatch Logs Insights.
        
        Args:
            query: Log query configuration
            
        Returns:
            List of log results
        """
        try:
            # Start query
            response = self.logs_client.start_query(
                logGroupNames=query.log_group_names,
                startTime=int(query.start_time.timestamp()),
                endTime=int(query.end_time.timestamp()),
                queryString=query.query_string,
                limit=query.limit
            )
            
            query_id = response['queryId']
            
            # Wait for query to complete
            import time
            max_wait_seconds = 60
            wait_interval = 2
            elapsed = 0
            
            while elapsed < max_wait_seconds:
                result = self.logs_client.get_query_results(queryId=query_id)
                status = result['status']
                
                if status == 'Complete':
                    return result.get('results', [])
                elif status == 'Failed':
                    logger.error(f"Query failed: {result.get('statistics', {})}")
                    return []
                
                time.sleep(wait_interval)
                elapsed += wait_interval
            
            logger.warning(f"Query timed out after {max_wait_seconds} seconds")
            return []
        except Exception as e:
            logger.error(f"Failed to query logs: {e}")
            return []
    
    def get_error_logs(
        self,
        hours: int = 24,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get error logs from the specified time period.
        
        Args:
            hours: Number of hours to look back
            limit: Maximum number of results
            
        Returns:
            List of error log entries
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        query_string = """
        fields @timestamp, @message, @logStream
        | filter @message like /ERROR/ or @message like /Exception/
        | sort @timestamp desc
        """
        
        log_groups = self._get_log_groups()
        
        query = LogQuery(
            query_string=query_string,
            log_group_names=log_groups,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
        
        return self.query_logs(query)
    
    def get_slow_requests(
        self,
        threshold_ms: float = 3000,
        hours: int = 24,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get slow request logs.
        
        Args:
            threshold_ms: Response time threshold in milliseconds
            hours: Number of hours to look back
            limit: Maximum number of results
            
        Returns:
            List of slow request log entries
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        query_string = f"""
        fields @timestamp, @message, @duration
        | filter @duration > {threshold_ms}
        | sort @duration desc
        """
        
        log_groups = self._get_log_groups()
        
        query = LogQuery(
            query_string=query_string,
            log_group_names=log_groups,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
        
        return self.query_logs(query)
    
    def analyze_error_patterns(
        self,
        hours: int = 24
    ) -> List[LogInsight]:
        """
        Analyze error patterns in logs.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            List of error pattern insights
        """
        error_logs = self.get_error_logs(hours=hours, limit=1000)
        
        if not error_logs:
            return []
        
        # Group errors by pattern
        patterns = {}
        
        for log_entry in error_logs:
            message = self._extract_field(log_entry, '@message')
            timestamp_str = self._extract_field(log_entry, '@timestamp')
            
            if not message:
                continue
            
            # Extract error pattern (simplified)
            pattern = self._extract_error_pattern(message)
            
            if pattern not in patterns:
                patterns[pattern] = {
                    'count': 0,
                    'samples': [],
                    'first': None,
                    'last': None
                }
            
            patterns[pattern]['count'] += 1
            
            if len(patterns[pattern]['samples']) < 3:
                patterns[pattern]['samples'].append(message)
            
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                if patterns[pattern]['first'] is None or timestamp < patterns[pattern]['first']:
                    patterns[pattern]['first'] = timestamp
                if patterns[pattern]['last'] is None or timestamp > patterns[pattern]['last']:
                    patterns[pattern]['last'] = timestamp
            except:
                pass
        
        # Convert to insights
        insights = []
        for pattern, data in patterns.items():
            insight = LogInsight(
                pattern=pattern,
                count=data['count'],
                sample_messages=data['samples'],
                first_occurrence=data['first'] or datetime.utcnow(),
                last_occurrence=data['last'] or datetime.utcnow()
            )
            insights.append(insight)
        
        # Sort by count
        insights.sort(key=lambda x: x.count, reverse=True)
        
        return insights
    
    def get_log_statistics(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get log statistics for the specified time period.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            Dictionary with log statistics
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        # Query for log counts by level
        query_string = """
        fields @timestamp, @message
        | stats count() by bin(5m)
        """
        
        log_groups = self._get_log_groups()
        
        query = LogQuery(
            query_string=query_string,
            log_group_names=log_groups,
            start_time=start_time,
            end_time=end_time,
            limit=1000
        )
        
        results = self.query_logs(query)
        
        # Get error count
        error_logs = self.get_error_logs(hours=hours, limit=10000)
        error_count = len(error_logs)
        
        # Get slow request count
        slow_requests = self.get_slow_requests(hours=hours, limit=10000)
        slow_request_count = len(slow_requests)
        
        return {
            'time_period_hours': hours,
            'total_log_entries': len(results),
            'error_count': error_count,
            'slow_request_count': slow_request_count,
            'error_rate': (error_count / len(results) * 100) if results else 0,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def search_logs(
        self,
        search_term: str,
        hours: int = 24,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search logs for a specific term.
        
        Args:
            search_term: Term to search for
            hours: Number of hours to search
            limit: Maximum number of results
            
        Returns:
            List of matching log entries
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        query_string = f"""
        fields @timestamp, @message, @logStream
        | filter @message like /{search_term}/
        | sort @timestamp desc
        """
        
        log_groups = self._get_log_groups()
        
        query = LogQuery(
            query_string=query_string,
            log_group_names=log_groups,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
        
        return self.query_logs(query)
    
    def _get_log_groups(self) -> List[str]:
        """Get list of log groups to monitor."""
        try:
            response = self.logs_client.describe_log_groups(
                logGroupNamePrefix=self.log_group_prefix
            )
            
            return [
                group['logGroupName'] 
                for group in response.get('logGroups', [])
            ]
        except Exception as e:
            logger.error(f"Failed to get log groups: {e}")
            return []
    
    def _extract_field(
        self,
        log_entry: List[Dict[str, str]],
        field_name: str
    ) -> Optional[str]:
        """Extract field value from log entry."""
        for field in log_entry:
            if field.get('field') == field_name:
                return field.get('value')
        return None
    
    def _extract_error_pattern(self, message: str) -> str:
        """Extract error pattern from message."""
        # Simplified pattern extraction
        # In production, use more sophisticated pattern matching
        
        if 'Exception' in message:
            # Extract exception type
            import re
            match = re.search(r'(\w+Exception)', message)
            if match:
                return match.group(1)
        
        if 'ERROR' in message:
            # Extract first line
            lines = message.split('\n')
            if lines:
                return lines[0][:100]
        
        return message[:100]
