"""
Visualization and reporting for KrishiMitra analytics.

This module provides visualization capabilities using matplotlib and plotly
for generating charts and reports.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from io import BytesIO
import base64

logger = logging.getLogger(__name__)


class AnalyticsVisualizer:
    """
    Creates visualizations for KrishiMitra analytics.
    
    Generates charts and reports using matplotlib and plotly
    for farmer engagement and platform impact metrics.
    """
    
    def __init__(self):
        """Initialize analytics visualizer."""
        self.matplotlib_available = False
        self.plotly_available = False
        
        # Try to import visualization libraries
        try:
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
            import matplotlib.pyplot as plt
            self.plt = plt
            self.matplotlib_available = True
        except ImportError:
            logger.warning("matplotlib not available, some visualizations will be disabled")
        
        try:
            import plotly.graph_objects as go
            import plotly.express as px
            self.go = go
            self.px = px
            self.plotly_available = True
        except ImportError:
            logger.warning("plotly not available, some visualizations will be disabled")
    
    def create_engagement_chart(
        self,
        usage_patterns: Dict[str, Any],
        output_format: str = 'png'
    ) -> Optional[str]:
        """
        Create engagement visualization chart.
        
        Args:
            usage_patterns: Usage pattern data
            output_format: Output format ('png', 'html')
            
        Returns:
            Base64 encoded image or HTML string
        """
        if not self.matplotlib_available and output_format == 'png':
            logger.error("matplotlib not available for PNG output")
            return None
        
        if not self.plotly_available and output_format == 'html':
            logger.error("plotly not available for HTML output")
            return None
        
        try:
            if output_format == 'png':
                return self._create_engagement_chart_matplotlib(usage_patterns)
            else:
                return self._create_engagement_chart_plotly(usage_patterns)
        except Exception as e:
            logger.error(f"Failed to create engagement chart: {e}")
            return None
    
    def create_effectiveness_chart(
        self,
        effectiveness_data: List[Dict[str, Any]],
        output_format: str = 'png'
    ) -> Optional[str]:
        """
        Create recommendation effectiveness chart.
        
        Args:
            effectiveness_data: Effectiveness metrics
            output_format: Output format ('png', 'html')
            
        Returns:
            Base64 encoded image or HTML string
        """
        if not self.matplotlib_available and output_format == 'png':
            logger.error("matplotlib not available for PNG output")
            return None
        
        if not self.plotly_available and output_format == 'html':
            logger.error("plotly not available for HTML output")
            return None
        
        try:
            if output_format == 'png':
                return self._create_effectiveness_chart_matplotlib(effectiveness_data)
            else:
                return self._create_effectiveness_chart_plotly(effectiveness_data)
        except Exception as e:
            logger.error(f"Failed to create effectiveness chart: {e}")
            return None
    
    def create_impact_dashboard(
        self,
        impact_metrics: Dict[str, Any]
    ) -> str:
        """
        Create comprehensive impact dashboard HTML.
        
        Args:
            impact_metrics: Platform impact metrics
            
        Returns:
            HTML dashboard string
        """
        try:
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>KrishiMitra Impact Dashboard</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        margin: 20px;
                        background-color: #f5f5f5;
                    }}
                    .dashboard {{
                        max-width: 1200px;
                        margin: 0 auto;
                        background-color: white;
                        padding: 20px;
                        border-radius: 8px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }}
                    h1 {{
                        color: #2c5f2d;
                        border-bottom: 3px solid #97bc62;
                        padding-bottom: 10px;
                    }}
                    .metrics-grid {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                        gap: 20px;
                        margin: 20px 0;
                    }}
                    .metric-card {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 20px;
                        border-radius: 8px;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    }}
                    .metric-card.green {{
                        background: linear-gradient(135deg, #2c5f2d 0%, #97bc62 100%);
                    }}
                    .metric-card.blue {{
                        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                    }}
                    .metric-card.orange {{
                        background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
                    }}
                    .metric-value {{
                        font-size: 36px;
                        font-weight: bold;
                        margin: 10px 0;
                    }}
                    .metric-label {{
                        font-size: 14px;
                        opacity: 0.9;
                    }}
                    .timestamp {{
                        text-align: right;
                        color: #666;
                        font-size: 12px;
                        margin-top: 20px;
                    }}
                </style>
            </head>
            <body>
                <div class="dashboard">
                    <h1>🌾 KrishiMitra Platform Impact Dashboard</h1>
                    
                    <div class="metrics-grid">
                        <div class="metric-card green">
                            <div class="metric-label">Total Farmers</div>
                            <div class="metric-value">{impact_metrics.get('total_farmers', 0):,}</div>
                        </div>
                        
                        <div class="metric-card blue">
                            <div class="metric-label">Active Farmers</div>
                            <div class="metric-value">{impact_metrics.get('active_farmers', 0):,}</div>
                        </div>
                        
                        <div class="metric-card orange">
                            <div class="metric-label">Recommendations Delivered</div>
                            <div class="metric-value">{impact_metrics.get('total_recommendations', 0):,}</div>
                        </div>
                        
                        <div class="metric-card green">
                            <div class="metric-label">Implementation Rate</div>
                            <div class="metric-value">
                                {(impact_metrics.get('implemented_recommendations', 0) / max(impact_metrics.get('total_recommendations', 1), 1) * 100):.1f}%
                            </div>
                        </div>
                        
                        <div class="metric-card blue">
                            <div class="metric-label">Avg Yield Improvement</div>
                            <div class="metric-value">{impact_metrics.get('avg_yield_improvement', 0):.1f}%</div>
                        </div>
                        
                        <div class="metric-card orange">
                            <div class="metric-label">Avg Cost Reduction</div>
                            <div class="metric-value">{impact_metrics.get('avg_cost_reduction', 0):.1f}%</div>
                        </div>
                        
                        <div class="metric-card green">
                            <div class="metric-label">Water Savings</div>
                            <div class="metric-value">{impact_metrics.get('avg_water_savings', 0):.1f}%</div>
                        </div>
                        
                        <div class="metric-card blue">
                            <div class="metric-label">Chemical Reduction</div>
                            <div class="metric-value">{impact_metrics.get('avg_chemical_reduction', 0):.1f}%</div>
                        </div>
                        
                        <div class="metric-card orange">
                            <div class="metric-label">Farmer Satisfaction</div>
                            <div class="metric-value">{impact_metrics.get('farmer_satisfaction', 0):.1f}/5.0</div>
                        </div>
                    </div>
                    
                    <div class="timestamp">
                        Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
                        <br>
                        Time Period: {impact_metrics.get('time_period', 'N/A')}
                    </div>
                </div>
            </body>
            </html>
            """
            return html
        except Exception as e:
            logger.error(f"Failed to create impact dashboard: {e}")
            return "<html><body>Error creating dashboard</body></html>"
    
    def _create_engagement_chart_matplotlib(
        self,
        usage_patterns: Dict[str, Any]
    ) -> str:
        """Create engagement chart using matplotlib."""
        try:
            import matplotlib.pyplot as plt
            
            fig, axes = plt.subplots(2, 2, figsize=(12, 10))
            fig.suptitle('Farmer Engagement Patterns', fontsize=16, fontweight='bold')
            
            # By hour
            by_hour = usage_patterns.get('by_hour', {})
            if by_hour:
                hours = sorted(by_hour.keys())
                counts = [by_hour[h] for h in hours]
                axes[0, 0].bar(hours, counts, color='#2c5f2d')
                axes[0, 0].set_title('Activity by Hour of Day')
                axes[0, 0].set_xlabel('Hour')
                axes[0, 0].set_ylabel('Interactions')
            
            # By day of week
            by_day = usage_patterns.get('by_day_of_week', {})
            if by_day:
                days = list(by_day.keys())
                counts = list(by_day.values())
                axes[0, 1].bar(days, counts, color='#97bc62')
                axes[0, 1].set_title('Activity by Day of Week')
                axes[0, 1].set_xlabel('Day')
                axes[0, 1].set_ylabel('Interactions')
                axes[0, 1].tick_params(axis='x', rotation=45)
            
            # By language
            by_language = usage_patterns.get('by_language', {})
            if by_language:
                languages = list(by_language.keys())
                counts = list(by_language.values())
                axes[1, 0].pie(counts, labels=languages, autopct='%1.1f%%', startangle=90)
                axes[1, 0].set_title('Language Distribution')
            
            # By channel
            by_channel = usage_patterns.get('by_channel', {})
            if by_channel:
                channels = list(by_channel.keys())
                counts = list(by_channel.values())
                axes[1, 1].pie(counts, labels=channels, autopct='%1.1f%%', startangle=90)
                axes[1, 1].set_title('Channel Distribution')
            
            plt.tight_layout()
            
            # Convert to base64
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.read()).decode()
            plt.close()
            
            return image_base64
        except Exception as e:
            logger.error(f"Failed to create matplotlib chart: {e}")
            return ""
    
    def _create_engagement_chart_plotly(
        self,
        usage_patterns: Dict[str, Any]
    ) -> str:
        """Create engagement chart using plotly."""
        try:
            from plotly.subplots import make_subplots
            import plotly.graph_objects as go
            
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=('Activity by Hour', 'Activity by Day', 
                               'Language Distribution', 'Channel Distribution'),
                specs=[[{'type': 'bar'}, {'type': 'bar'}],
                       [{'type': 'pie'}, {'type': 'pie'}]]
            )
            
            # By hour
            by_hour = usage_patterns.get('by_hour', {})
            if by_hour:
                hours = sorted(by_hour.keys())
                counts = [by_hour[h] for h in hours]
                fig.add_trace(
                    go.Bar(x=hours, y=counts, name='Hour', marker_color='#2c5f2d'),
                    row=1, col=1
                )
            
            # By day
            by_day = usage_patterns.get('by_day_of_week', {})
            if by_day:
                fig.add_trace(
                    go.Bar(x=list(by_day.keys()), y=list(by_day.values()), 
                          name='Day', marker_color='#97bc62'),
                    row=1, col=2
                )
            
            # By language
            by_language = usage_patterns.get('by_language', {})
            if by_language:
                fig.add_trace(
                    go.Pie(labels=list(by_language.keys()), values=list(by_language.values())),
                    row=2, col=1
                )
            
            # By channel
            by_channel = usage_patterns.get('by_channel', {})
            if by_channel:
                fig.add_trace(
                    go.Pie(labels=list(by_channel.keys()), values=list(by_channel.values())),
                    row=2, col=2
                )
            
            fig.update_layout(
                title_text="Farmer Engagement Patterns",
                showlegend=False,
                height=800
            )
            
            return fig.to_html()
        except Exception as e:
            logger.error(f"Failed to create plotly chart: {e}")
            return ""
    
    def _create_effectiveness_chart_matplotlib(
        self,
        effectiveness_data: List[Dict[str, Any]]
    ) -> str:
        """Create effectiveness chart using matplotlib."""
        try:
            import matplotlib.pyplot as plt
            
            if not effectiveness_data:
                return ""
            
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))
            fig.suptitle('Recommendation Effectiveness Analysis', fontsize=16, fontweight='bold')
            
            types = [d['recommendation_type'] for d in effectiveness_data[:10]]
            
            # Implementation rate
            impl_rates = [d['implementation_rate'] for d in effectiveness_data[:10]]
            axes[0, 0].barh(types, impl_rates, color='#2c5f2d')
            axes[0, 0].set_title('Implementation Rate (%)')
            axes[0, 0].set_xlabel('Rate (%)')
            
            # Success rate
            success_rates = [d['success_rate'] for d in effectiveness_data[:10]]
            axes[0, 1].barh(types, success_rates, color='#97bc62')
            axes[0, 1].set_title('Success Rate (%)')
            axes[0, 1].set_xlabel('Rate (%)')
            
            # Satisfaction
            satisfaction = [d['avg_satisfaction'] for d in effectiveness_data[:10]]
            axes[1, 0].barh(types, satisfaction, color='#4facfe')
            axes[1, 0].set_title('Average Satisfaction (out of 5)')
            axes[1, 0].set_xlabel('Score')
            
            # Total delivered
            delivered = [d['total_delivered'] for d in effectiveness_data[:10]]
            axes[1, 1].barh(types, delivered, color='#fa709a')
            axes[1, 1].set_title('Total Recommendations Delivered')
            axes[1, 1].set_xlabel('Count')
            
            plt.tight_layout()
            
            # Convert to base64
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.read()).decode()
            plt.close()
            
            return image_base64
        except Exception as e:
            logger.error(f"Failed to create matplotlib effectiveness chart: {e}")
            return ""
    
    def _create_effectiveness_chart_plotly(
        self,
        effectiveness_data: List[Dict[str, Any]]
    ) -> str:
        """Create effectiveness chart using plotly."""
        try:
            from plotly.subplots import make_subplots
            import plotly.graph_objects as go
            
            if not effectiveness_data:
                return ""
            
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=('Implementation Rate', 'Success Rate', 
                               'Satisfaction Score', 'Total Delivered')
            )
            
            types = [d['recommendation_type'] for d in effectiveness_data[:10]]
            
            # Implementation rate
            fig.add_trace(
                go.Bar(y=types, x=[d['implementation_rate'] for d in effectiveness_data[:10]],
                      orientation='h', marker_color='#2c5f2d', name='Implementation'),
                row=1, col=1
            )
            
            # Success rate
            fig.add_trace(
                go.Bar(y=types, x=[d['success_rate'] for d in effectiveness_data[:10]],
                      orientation='h', marker_color='#97bc62', name='Success'),
                row=1, col=2
            )
            
            # Satisfaction
            fig.add_trace(
                go.Bar(y=types, x=[d['avg_satisfaction'] for d in effectiveness_data[:10]],
                      orientation='h', marker_color='#4facfe', name='Satisfaction'),
                row=2, col=1
            )
            
            # Total delivered
            fig.add_trace(
                go.Bar(y=types, x=[d['total_delivered'] for d in effectiveness_data[:10]],
                      orientation='h', marker_color='#fa709a', name='Delivered'),
                row=2, col=2
            )
            
            fig.update_layout(
                title_text="Recommendation Effectiveness Analysis",
                showlegend=False,
                height=800
            )
            
            return fig.to_html()
        except Exception as e:
            logger.error(f"Failed to create plotly effectiveness chart: {e}")
            return ""
