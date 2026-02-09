"""
Farmer engagement and outcome analytics for KrishiMitra platform.

This module implements comprehensive analytics for farmer usage patterns,
recommendation effectiveness, and impact measurement using pandas and visualization libraries.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class FarmerEngagementMetrics:
    """Farmer engagement metrics."""
    farmer_id: str
    total_interactions: int
    active_days: int
    recommendations_received: int
    recommendations_implemented: int
    implementation_rate: float
    avg_satisfaction_score: float
    preferred_language: str
    last_interaction: datetime
    engagement_score: float


@dataclass
class RecommendationEffectiveness:
    """Recommendation effectiveness metrics."""
    recommendation_type: str
    total_delivered: int
    implementation_rate: float
    success_rate: float
    avg_satisfaction: float
    avg_yield_improvement: Optional[float] = None
    avg_cost_reduction: Optional[float] = None


@dataclass
class ImpactMetrics:
    """Impact measurement metrics."""
    time_period: str
    total_farmers: int
    active_farmers: int
    total_recommendations: int
    implemented_recommendations: int
    avg_yield_improvement: float
    avg_cost_reduction: float
    avg_water_savings: float
    avg_chemical_reduction: float
    farmer_satisfaction: float


class FarmerAnalytics:
    """
    Analyzes farmer engagement and outcomes for KrishiMitra platform.
    
    Implements comprehensive analytics using pandas for data processing
    and visualization libraries for reporting.
    """
    
    def __init__(
        self,
        region: str = "ap-south-1"
    ):
        """
        Initialize farmer analytics.
        
        Args:
            region: AWS region
        """
        self.region = region
        
        # AWS clients
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
        
        # Tables
        self.farmers_table = self.dynamodb.Table('KrishiMitra-FarmerProfiles')
        self.recommendations_table = self.dynamodb.Table('KrishiMitra-Recommendations')
        self.conversations_table = self.dynamodb.Table('KrishiMitra-Conversations')
    
    def get_farmer_engagement_metrics(
        self,
        farmer_id: str,
        days: int = 30
    ) -> FarmerEngagementMetrics:
        """
        Get engagement metrics for a specific farmer.
        
        Args:
            farmer_id: Farmer ID
            days: Number of days to analyze
            
        Returns:
            Farmer engagement metrics
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get farmer profile
            farmer_response = self.farmers_table.get_item(
                Key={'farmerId': farmer_id}
            )
            farmer = farmer_response.get('Item', {})
            
            # Get conversations
            conversations = self._get_farmer_conversations(
                farmer_id,
                cutoff_date
            )
            
            # Get recommendations
            recommendations = self._get_farmer_recommendations(
                farmer_id,
                cutoff_date
            )
            
            # Calculate metrics
            total_interactions = len(conversations)
            active_days = self._count_active_days(conversations)
            
            recommendations_received = len(recommendations)
            recommendations_implemented = sum(
                1 for r in recommendations 
                if r.get('feedback', {}).get('implemented', False)
            )
            implementation_rate = (
                recommendations_implemented / recommendations_received * 100
                if recommendations_received > 0 else 0
            )
            
            # Calculate satisfaction score
            satisfaction_scores = [
                r.get('feedback', {}).get('effectiveness', 0)
                for r in recommendations
                if r.get('feedback', {}).get('effectiveness')
            ]
            avg_satisfaction = (
                sum(satisfaction_scores) / len(satisfaction_scores)
                if satisfaction_scores else 0
            )
            
            # Calculate engagement score (0-100)
            engagement_score = self._calculate_engagement_score(
                total_interactions,
                active_days,
                implementation_rate,
                avg_satisfaction
            )
            
            # Get last interaction
            last_interaction = max(
                (datetime.fromisoformat(c['timestamp']) for c in conversations),
                default=datetime.utcnow()
            )
            
            return FarmerEngagementMetrics(
                farmer_id=farmer_id,
                total_interactions=total_interactions,
                active_days=active_days,
                recommendations_received=recommendations_received,
                recommendations_implemented=recommendations_implemented,
                implementation_rate=implementation_rate,
                avg_satisfaction_score=avg_satisfaction,
                preferred_language=farmer.get('personalInfo', {}).get('preferredLanguage', 'hindi'),
                last_interaction=last_interaction,
                engagement_score=engagement_score
            )
        except Exception as e:
            logger.error(f"Failed to get farmer engagement metrics: {e}")
            return FarmerEngagementMetrics(
                farmer_id=farmer_id,
                total_interactions=0,
                active_days=0,
                recommendations_received=0,
                recommendations_implemented=0,
                implementation_rate=0,
                avg_satisfaction_score=0,
                preferred_language='hindi',
                last_interaction=datetime.utcnow(),
                engagement_score=0
            )
    
    def analyze_recommendation_effectiveness(
        self,
        days: int = 30
    ) -> List[RecommendationEffectiveness]:
        """
        Analyze effectiveness of different recommendation types.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            List of recommendation effectiveness metrics
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get all recommendations
            recommendations = self._get_all_recommendations(cutoff_date)
            
            # Group by type
            by_type = {}
            for rec in recommendations:
                rec_type = rec.get('queryType', 'unknown')
                if rec_type not in by_type:
                    by_type[rec_type] = []
                by_type[rec_type].append(rec)
            
            # Calculate effectiveness for each type
            effectiveness_list = []
            for rec_type, recs in by_type.items():
                total_delivered = len(recs)
                
                implemented = sum(
                    1 for r in recs 
                    if r.get('feedback', {}).get('implemented', False)
                )
                implementation_rate = (
                    implemented / total_delivered * 100
                    if total_delivered > 0 else 0
                )
                
                # Success rate (effectiveness >= 4 out of 5)
                successful = sum(
                    1 for r in recs 
                    if r.get('feedback', {}).get('effectiveness', 0) >= 4
                )
                success_rate = (
                    successful / total_delivered * 100
                    if total_delivered > 0 else 0
                )
                
                # Average satisfaction
                satisfaction_scores = [
                    r.get('feedback', {}).get('effectiveness', 0)
                    for r in recs
                    if r.get('feedback', {}).get('effectiveness')
                ]
                avg_satisfaction = (
                    sum(satisfaction_scores) / len(satisfaction_scores)
                    if satisfaction_scores else 0
                )
                
                # Yield improvement
                yield_improvements = [
                    r.get('feedback', {}).get('outcome', {}).get('yield_improvement', 0)
                    for r in recs
                    if r.get('feedback', {}).get('outcome', {}).get('yield_improvement')
                ]
                avg_yield_improvement = (
                    sum(yield_improvements) / len(yield_improvements)
                    if yield_improvements else None
                )
                
                # Cost reduction
                cost_reductions = [
                    r.get('feedback', {}).get('outcome', {}).get('cost_reduction', 0)
                    for r in recs
                    if r.get('feedback', {}).get('outcome', {}).get('cost_reduction')
                ]
                avg_cost_reduction = (
                    sum(cost_reductions) / len(cost_reductions)
                    if cost_reductions else None
                )
                
                effectiveness = RecommendationEffectiveness(
                    recommendation_type=rec_type,
                    total_delivered=total_delivered,
                    implementation_rate=implementation_rate,
                    success_rate=success_rate,
                    avg_satisfaction=avg_satisfaction,
                    avg_yield_improvement=avg_yield_improvement,
                    avg_cost_reduction=avg_cost_reduction
                )
                effectiveness_list.append(effectiveness)
            
            # Sort by total delivered
            effectiveness_list.sort(key=lambda x: x.total_delivered, reverse=True)
            
            return effectiveness_list
        except Exception as e:
            logger.error(f"Failed to analyze recommendation effectiveness: {e}")
            return []
    
    def measure_platform_impact(
        self,
        days: int = 30
    ) -> ImpactMetrics:
        """
        Measure overall platform impact.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Platform impact metrics
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get all farmers
            farmers = self._get_all_farmers()
            total_farmers = len(farmers)
            
            # Get active farmers (interacted in period)
            active_farmers = self._count_active_farmers(cutoff_date)
            
            # Get all recommendations
            recommendations = self._get_all_recommendations(cutoff_date)
            total_recommendations = len(recommendations)
            
            implemented_recommendations = sum(
                1 for r in recommendations 
                if r.get('feedback', {}).get('implemented', False)
            )
            
            # Calculate average improvements
            yield_improvements = [
                r.get('feedback', {}).get('outcome', {}).get('yield_improvement', 0)
                for r in recommendations
                if r.get('feedback', {}).get('outcome', {}).get('yield_improvement')
            ]
            avg_yield_improvement = (
                sum(yield_improvements) / len(yield_improvements)
                if yield_improvements else 0
            )
            
            cost_reductions = [
                r.get('feedback', {}).get('outcome', {}).get('cost_reduction', 0)
                for r in recommendations
                if r.get('feedback', {}).get('outcome', {}).get('cost_reduction')
            ]
            avg_cost_reduction = (
                sum(cost_reductions) / len(cost_reductions)
                if cost_reductions else 0
            )
            
            water_savings = [
                r.get('feedback', {}).get('outcome', {}).get('water_savings', 0)
                for r in recommendations
                if r.get('feedback', {}).get('outcome', {}).get('water_savings')
            ]
            avg_water_savings = (
                sum(water_savings) / len(water_savings)
                if water_savings else 0
            )
            
            chemical_reductions = [
                r.get('feedback', {}).get('outcome', {}).get('chemical_reduction', 0)
                for r in recommendations
                if r.get('feedback', {}).get('outcome', {}).get('chemical_reduction')
            ]
            avg_chemical_reduction = (
                sum(chemical_reductions) / len(chemical_reductions)
                if chemical_reductions else 0
            )
            
            # Calculate farmer satisfaction
            satisfaction_scores = [
                r.get('feedback', {}).get('effectiveness', 0)
                for r in recommendations
                if r.get('feedback', {}).get('effectiveness')
            ]
            farmer_satisfaction = (
                sum(satisfaction_scores) / len(satisfaction_scores)
                if satisfaction_scores else 0
            )
            
            return ImpactMetrics(
                time_period=f"{days} days",
                total_farmers=total_farmers,
                active_farmers=active_farmers,
                total_recommendations=total_recommendations,
                implemented_recommendations=implemented_recommendations,
                avg_yield_improvement=avg_yield_improvement,
                avg_cost_reduction=avg_cost_reduction,
                avg_water_savings=avg_water_savings,
                avg_chemical_reduction=avg_chemical_reduction,
                farmer_satisfaction=farmer_satisfaction
            )
        except Exception as e:
            logger.error(f"Failed to measure platform impact: {e}")
            return ImpactMetrics(
                time_period=f"{days} days",
                total_farmers=0,
                active_farmers=0,
                total_recommendations=0,
                implemented_recommendations=0,
                avg_yield_improvement=0,
                avg_cost_reduction=0,
                avg_water_savings=0,
                avg_chemical_reduction=0,
                farmer_satisfaction=0
            )
    
    def get_usage_patterns(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze farmer usage patterns.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with usage pattern analytics
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get all conversations
            conversations = self._get_all_conversations(cutoff_date)
            
            # Analyze by hour of day
            by_hour = {}
            for conv in conversations:
                timestamp = datetime.fromisoformat(conv['timestamp'])
                hour = timestamp.hour
                by_hour[hour] = by_hour.get(hour, 0) + 1
            
            # Analyze by day of week
            by_day = {}
            for conv in conversations:
                timestamp = datetime.fromisoformat(conv['timestamp'])
                day = timestamp.strftime('%A')
                by_day[day] = by_day.get(day, 0) + 1
            
            # Analyze by language
            by_language = {}
            for conv in conversations:
                language = conv.get('language', 'unknown')
                by_language[language] = by_language.get(language, 0) + 1
            
            # Analyze by channel (WhatsApp, voice, web)
            by_channel = {}
            for conv in conversations:
                channel = conv.get('channel', 'unknown')
                by_channel[channel] = by_channel.get(channel, 0) + 1
            
            return {
                'total_interactions': len(conversations),
                'by_hour': by_hour,
                'by_day_of_week': by_day,
                'by_language': by_language,
                'by_channel': by_channel,
                'peak_hour': max(by_hour.items(), key=lambda x: x[1])[0] if by_hour else None,
                'most_active_day': max(by_day.items(), key=lambda x: x[1])[0] if by_day else None,
                'primary_language': max(by_language.items(), key=lambda x: x[1])[0] if by_language else None
            }
        except Exception as e:
            logger.error(f"Failed to get usage patterns: {e}")
            return {
                'total_interactions': 0,
                'by_hour': {},
                'by_day_of_week': {},
                'by_language': {},
                'by_channel': {},
                'error': str(e)
            }
    
    def publish_metrics_to_cloudwatch(
        self,
        metrics: ImpactMetrics
    ):
        """
        Publish impact metrics to CloudWatch.
        
        Args:
            metrics: Impact metrics to publish
        """
        try:
            metric_data = [
                {
                    'MetricName': 'TotalFarmers',
                    'Value': metrics.total_farmers,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'ActiveFarmers',
                    'Value': metrics.active_farmers,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'TotalRecommendations',
                    'Value': metrics.total_recommendations,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'ImplementedRecommendations',
                    'Value': metrics.implemented_recommendations,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'AvgYieldImprovement',
                    'Value': metrics.avg_yield_improvement,
                    'Unit': 'Percent'
                },
                {
                    'MetricName': 'AvgCostReduction',
                    'Value': metrics.avg_cost_reduction,
                    'Unit': 'Percent'
                },
                {
                    'MetricName': 'FarmerSatisfaction',
                    'Value': metrics.farmer_satisfaction,
                    'Unit': 'None'
                }
            ]
            
            self.cloudwatch_client.put_metric_data(
                Namespace='KrishiMitra/Impact',
                MetricData=metric_data
            )
            
            logger.info("Published impact metrics to CloudWatch")
        except Exception as e:
            logger.error(f"Failed to publish metrics: {e}")
    
    def _get_farmer_conversations(
        self,
        farmer_id: str,
        cutoff_date: datetime
    ) -> List[Dict]:
        """Get conversations for a farmer."""
        try:
            response = self.conversations_table.query(
                IndexName='FarmerIdIndex',
                KeyConditionExpression='farmerId = :fid',
                ExpressionAttributeValues={
                    ':fid': farmer_id
                }
            )
            
            conversations = response.get('Items', [])
            
            # Filter by date
            return [
                c for c in conversations
                if datetime.fromisoformat(c['timestamp']) >= cutoff_date
            ]
        except Exception:
            return []
    
    def _get_farmer_recommendations(
        self,
        farmer_id: str,
        cutoff_date: datetime
    ) -> List[Dict]:
        """Get recommendations for a farmer."""
        try:
            response = self.recommendations_table.query(
                IndexName='FarmerIdIndex',
                KeyConditionExpression='farmerId = :fid',
                ExpressionAttributeValues={
                    ':fid': farmer_id
                }
            )
            
            recommendations = response.get('Items', [])
            
            # Filter by date
            return [
                r for r in recommendations
                if datetime.fromisoformat(r['timestamp']) >= cutoff_date
            ]
        except Exception:
            return []
    
    def _get_all_recommendations(
        self,
        cutoff_date: datetime
    ) -> List[Dict]:
        """Get all recommendations."""
        try:
            response = self.recommendations_table.scan()
            recommendations = response.get('Items', [])
            
            # Filter by date
            return [
                r for r in recommendations
                if datetime.fromisoformat(r['timestamp']) >= cutoff_date
            ]
        except Exception:
            return []
    
    def _get_all_farmers(self) -> List[Dict]:
        """Get all farmers."""
        try:
            response = self.farmers_table.scan()
            return response.get('Items', [])
        except Exception:
            return []
    
    def _get_all_conversations(
        self,
        cutoff_date: datetime
    ) -> List[Dict]:
        """Get all conversations."""
        try:
            response = self.conversations_table.scan()
            conversations = response.get('Items', [])
            
            # Filter by date
            return [
                c for c in conversations
                if datetime.fromisoformat(c['timestamp']) >= cutoff_date
            ]
        except Exception:
            return []
    
    def _count_active_farmers(
        self,
        cutoff_date: datetime
    ) -> int:
        """Count active farmers in period."""
        try:
            conversations = self._get_all_conversations(cutoff_date)
            unique_farmers = set(c.get('farmerId') for c in conversations if c.get('farmerId'))
            return len(unique_farmers)
        except Exception:
            return 0
    
    def _count_active_days(
        self,
        conversations: List[Dict]
    ) -> int:
        """Count number of active days."""
        try:
            dates = set()
            for conv in conversations:
                timestamp = datetime.fromisoformat(conv['timestamp'])
                dates.add(timestamp.date())
            return len(dates)
        except Exception:
            return 0
    
    def _calculate_engagement_score(
        self,
        total_interactions: int,
        active_days: int,
        implementation_rate: float,
        avg_satisfaction: float
    ) -> float:
        """Calculate engagement score (0-100)."""
        # Weighted scoring
        interaction_score = min(total_interactions / 30 * 25, 25)  # Max 25 points
        activity_score = min(active_days / 30 * 25, 25)  # Max 25 points
        implementation_score = implementation_rate / 100 * 25  # Max 25 points
        satisfaction_score = avg_satisfaction / 5 * 25  # Max 25 points
        
        return interaction_score + activity_score + implementation_score + satisfaction_score
