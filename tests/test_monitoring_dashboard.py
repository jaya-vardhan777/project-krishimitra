"""
Tests for monitoring and analytics dashboard.

This module tests system health monitoring, alerting, log aggregation,
and farmer engagement analytics.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.krishimitra.core.monitoring import (
    HealthMonitor,
    SystemHealthStatus,
    AlertManager,
    AlertSeverity,
    AlertCategory,
    LogAggregator,
    LogLevel,
    DashboardManager,
    FarmerAnalytics,
    AnalyticsVisualizer
)


class TestHealthMonitor:
    """Test health monitoring functionality."""
    
    @pytest.fixture
    def health_monitor(self):
        """Create health monitor instance."""
        with patch('boto3.client'):
            return HealthMonitor(region='ap-south-1')
    
    def test_health_monitor_initialization(self, health_monitor):
        """Test health monitor initializes correctly."""
        assert health_monitor.region == 'ap-south-1'
        assert health_monitor.check_interval_seconds == 60
        assert 'response_time_ms' in health_monitor.thresholds
    
    def test_check_system_health(self, health_monitor):
        """Test system health check."""
        with patch.object(health_monitor, 'check_lambda_health') as mock_lambda:
            mock_lambda.return_value = Mock(
                component_name='test-function',
                status=SystemHealthStatus.HEALTHY
            )
            
            components = {
                'lambda_functions': ['test-function']
            }
            
            health = health_monitor.check_system_health(components)
            
            assert health.overall_status == SystemHealthStatus.HEALTHY
            assert len(health.components) == 1
            assert health.healthy_count == 1


class TestAlertManager:
    """Test alerting functionality."""
    
    @pytest.fixture
    def alert_manager(self):
        """Create alert manager instance."""
        with patch('boto3.client'), patch('boto3.resource'):
            return AlertManager(region='ap-south-1')
    
    def test_alert_manager_initialization(self, alert_manager):
        """Test alert manager initializes correctly."""
        assert alert_manager.region == 'ap-south-1'
        assert alert_manager.alerts_table_name == 'KrishiMitra-Alerts'
    
    def test_create_alert(self, alert_manager):
        """Test alert creation."""
        with patch.object(alert_manager, '_store_alert'), \
             patch.object(alert_manager, '_send_notification'):
            
            alert = alert_manager.create_alert(
                severity=AlertSeverity.HIGH,
                category=AlertCategory.PERFORMANCE,
                title='High Response Time',
                description='API response time exceeded threshold',
                component='api-gateway',
                notify=False
            )
            
            assert alert.severity == AlertSeverity.HIGH
            assert alert.category == AlertCategory.PERFORMANCE
            assert alert.title == 'High Response Time'
            assert alert.component == 'api-gateway'
            assert not alert.resolved


class TestLogAggregator:
    """Test log aggregation functionality."""
    
    @pytest.fixture
    def log_aggregator(self):
        """Create log aggregator instance."""
        with patch('boto3.client'):
            return LogAggregator(region='ap-south-1')
    
    def test_log_aggregator_initialization(self, log_aggregator):
        """Test log aggregator initializes correctly."""
        assert log_aggregator.region == 'ap-south-1'
        assert log_aggregator.log_group_prefix == '/aws/lambda/krishimitra'
    
    def test_get_error_logs(self, log_aggregator):
        """Test error log retrieval."""
        with patch.object(log_aggregator, 'query_logs') as mock_query:
            mock_query.return_value = [
                [
                    {'field': '@timestamp', 'value': '2024-01-01T00:00:00Z'},
                    {'field': '@message', 'value': 'ERROR: Test error'}
                ]
            ]
            
            with patch.object(log_aggregator, '_get_log_groups') as mock_groups:
                mock_groups.return_value = ['/aws/lambda/test']
                
                errors = log_aggregator.get_error_logs(hours=24)
                
                assert len(errors) == 1


class TestDashboardManager:
    """Test dashboard management functionality."""
    
    @pytest.fixture
    def dashboard_manager(self):
        """Create dashboard manager instance."""
        with patch('boto3.client'):
            return DashboardManager(region='ap-south-1')
    
    def test_dashboard_manager_initialization(self, dashboard_manager):
        """Test dashboard manager initializes correctly."""
        assert dashboard_manager.region == 'ap-south-1'
    
    def test_create_system_health_dashboard(self, dashboard_manager):
        """Test system health dashboard creation."""
        with patch.object(dashboard_manager.cloudwatch_client, 'put_dashboard') as mock_put:
            components = {
                'lambda_functions': ['test-function'],
                'dynamodb_tables': ['test-table']
            }
            
            result = dashboard_manager.create_system_health_dashboard(
                'test-dashboard',
                components
            )
            
            assert result is True
            mock_put.assert_called_once()


class TestFarmerAnalytics:
    """Test farmer analytics functionality."""
    
    @pytest.fixture
    def farmer_analytics(self):
        """Create farmer analytics instance."""
        with patch('boto3.resource'), patch('boto3.client'):
            return FarmerAnalytics(region='ap-south-1')
    
    def test_farmer_analytics_initialization(self, farmer_analytics):
        """Test farmer analytics initializes correctly."""
        assert farmer_analytics.region == 'ap-south-1'
    
    def test_get_farmer_engagement_metrics(self, farmer_analytics):
        """Test farmer engagement metrics calculation."""
        with patch.object(farmer_analytics.farmers_table, 'get_item') as mock_get, \
             patch.object(farmer_analytics, '_get_farmer_conversations') as mock_convs, \
             patch.object(farmer_analytics, '_get_farmer_recommendations') as mock_recs:
            
            mock_get.return_value = {
                'Item': {
                    'farmerId': 'farmer_123',
                    'personalInfo': {'preferredLanguage': 'hindi'}
                }
            }
            
            mock_convs.return_value = [
                {'timestamp': datetime.utcnow().isoformat()}
            ]
            
            mock_recs.return_value = [
                {
                    'timestamp': datetime.utcnow().isoformat(),
                    'feedback': {
                        'implemented': True,
                        'effectiveness': 4
                    }
                }
            ]
            
            metrics = farmer_analytics.get_farmer_engagement_metrics('farmer_123')
            
            assert metrics.farmer_id == 'farmer_123'
            assert metrics.total_interactions == 1
            assert metrics.recommendations_received == 1
    
    def test_measure_platform_impact(self, farmer_analytics):
        """Test platform impact measurement."""
        with patch.object(farmer_analytics, '_get_all_farmers') as mock_farmers, \
             patch.object(farmer_analytics, '_count_active_farmers') as mock_active, \
             patch.object(farmer_analytics, '_get_all_recommendations') as mock_recs:
            
            mock_farmers.return_value = [{'farmerId': 'f1'}, {'farmerId': 'f2'}]
            mock_active.return_value = 2
            mock_recs.return_value = [
                {
                    'timestamp': datetime.utcnow().isoformat(),
                    'feedback': {
                        'implemented': True,
                        'effectiveness': 4,
                        'outcome': {
                            'yield_improvement': 15.0,
                            'cost_reduction': 10.0
                        }
                    }
                }
            ]
            
            impact = farmer_analytics.measure_platform_impact(days=30)
            
            assert impact.total_farmers == 2
            assert impact.active_farmers == 2
            assert impact.total_recommendations == 1


class TestAnalyticsVisualizer:
    """Test analytics visualization functionality."""
    
    @pytest.fixture
    def visualizer(self):
        """Create analytics visualizer instance."""
        return AnalyticsVisualizer()
    
    def test_visualizer_initialization(self, visualizer):
        """Test visualizer initializes correctly."""
        assert isinstance(visualizer, AnalyticsVisualizer)
    
    def test_create_impact_dashboard(self, visualizer):
        """Test impact dashboard HTML generation."""
        impact_metrics = {
            'total_farmers': 1000,
            'active_farmers': 750,
            'total_recommendations': 5000,
            'implemented_recommendations': 3500,
            'avg_yield_improvement': 15.5,
            'avg_cost_reduction': 12.3,
            'avg_water_savings': 20.0,
            'avg_chemical_reduction': 18.5,
            'farmer_satisfaction': 4.2,
            'time_period': '30 days'
        }
        
        html = visualizer.create_impact_dashboard(impact_metrics)
        
        assert 'KrishiMitra Platform Impact Dashboard' in html
        assert '1,000' in html
        assert '750' in html
        assert '5,000' in html


def test_monitoring_integration():
    """Test integration of monitoring components."""
    with patch('boto3.client'), patch('boto3.resource'):
        # Create all components
        health_monitor = HealthMonitor()
        alert_manager = AlertManager()
        log_aggregator = LogAggregator()
        dashboard_manager = DashboardManager()
        farmer_analytics = FarmerAnalytics()
        visualizer = AnalyticsVisualizer()
        
        # Verify all components are created
        assert health_monitor is not None
        assert alert_manager is not None
        assert log_aggregator is not None
        assert dashboard_manager is not None
        assert farmer_analytics is not None
        assert visualizer is not None
