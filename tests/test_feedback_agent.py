"""
Tests for Feedback Agent and Continuous Learning System.

This module tests feedback collection, outcome tracking,
effectiveness analysis, and continuous learning capabilities.
"""

import pytest
from datetime import datetime, timedelta
from src.krishimitra.agents.feedback import FeedbackAgent
from src.krishimitra.agents.continuous_learning import ContinuousLearningSystem


class TestFeedbackAgent:
    """Test suite for Feedback Agent."""
    
    @pytest.fixture
    def feedback_agent(self):
        """Create a feedback agent instance for testing."""
        return FeedbackAgent()
    
    @pytest.fixture
    def sample_feedback_data(self):
        """Sample feedback data for testing."""
        return {
            "overall_rating": 5,
            "usefulness_rating": 5,
            "clarity_rating": 4,
            "feasibility_rating": 4,
            "implementation_status": "completed",
            "implementation_challenges": ["weather", "labor"],
            "implementation_notes": "Worked well with drip irrigation",
            "outcome_achieved": True,
            "outcome_description": "Yield increased by 25%",
            "yield_impact": 25.0,
            "cost_impact": -15.0,
            "time_impact": "2 weeks",
            "suggestions_for_improvement": "More detailed timeline",
            "would_recommend_to_others": True,
            "additional_comments": "Very helpful recommendation",
            "needs_follow_up": False
        }
    
    @pytest.fixture
    def sample_outcome_data(self):
        """Sample outcome data for testing."""
        return {
            "actual_yield": 1250.0,
            "expected_yield": 1000.0,
            "actual_cost": 8500.0,
            "expected_cost": 10000.0,
            "implementation_time": "14 days",
            "quality_metrics": {"grade_a": 80, "grade_b": 20},
            "environmental_impact": {"water_saved": 20, "pesticide_reduced": 30},
            "farmer_satisfaction": 5
        }
    
    def test_collect_feedback(self, feedback_agent, sample_feedback_data):
        """Test feedback collection."""
        recommendation_id = "rec_123"
        farmer_id = "farmer_456"
        
        feedback_record = feedback_agent.collect_feedback(
            recommendation_id=recommendation_id,
            farmer_id=farmer_id,
            feedback_data=sample_feedback_data
        )
        
        assert feedback_record["recommendation_id"] == recommendation_id
        assert feedback_record["farmer_id"] == farmer_id
        assert feedback_record["overall_rating"] == 5
        assert "feedback_id" in feedback_record
        assert "timestamp" in feedback_record
        
        # Verify storage
        assert recommendation_id in feedback_agent.feedback_storage
        assert len(feedback_agent.feedback_storage[recommendation_id]) == 1
    
    def test_track_outcome(self, feedback_agent, sample_outcome_data):
        """Test outcome tracking."""
        recommendation_id = "rec_123"
        farmer_id = "farmer_456"
        
        outcome_record = feedback_agent.track_outcome(
            recommendation_id=recommendation_id,
            farmer_id=farmer_id,
            outcome_data=sample_outcome_data
        )
        
        assert outcome_record["recommendation_id"] == recommendation_id
        assert outcome_record["farmer_id"] == farmer_id
        assert outcome_record["actual_yield"] == 1250.0
        assert outcome_record["yield_variance"] == 25.0  # (1250-1000)/1000 * 100
        assert "outcome_id" in outcome_record
        
        # Verify storage
        assert recommendation_id in feedback_agent.outcome_storage
        assert len(feedback_agent.outcome_storage[recommendation_id]) == 1
    
    def test_analyze_effectiveness_no_data(self, feedback_agent):
        """Test effectiveness analysis with no data."""
        analysis = feedback_agent.analyze_effectiveness()
        
        assert analysis["total_feedback"] == 0
        assert "message" in analysis
    
    def test_analyze_effectiveness_with_data(self, feedback_agent, sample_feedback_data):
        """Test effectiveness analysis with feedback data."""
        # Add multiple feedback records
        for i in range(5):
            feedback_agent.collect_feedback(
                recommendation_id=f"rec_{i}",
                farmer_id=f"farmer_{i}",
                feedback_data=sample_feedback_data
            )
        
        analysis = feedback_agent.analyze_effectiveness(time_period_days=30)
        
        assert analysis["total_feedback"] == 5
        assert analysis["average_overall_rating"] == 5.0
        assert analysis["implementation_rate"] == 100.0
        assert analysis["outcome_achieved_rate"] == 100.0
    
    def test_correlate_outcomes_no_data(self, feedback_agent):
        """Test outcome correlation with no data."""
        correlation = feedback_agent.correlate_outcomes("rec_123")
        
        assert "message" in correlation
        assert correlation["recommendation_id"] == "rec_123"
    
    def test_correlate_outcomes_with_data(self, feedback_agent, sample_outcome_data):
        """Test outcome correlation with data."""
        recommendation_id = "rec_123"
        
        # Add outcome data
        feedback_agent.track_outcome(
            recommendation_id=recommendation_id,
            farmer_id="farmer_456",
            outcome_data=sample_outcome_data
        )
        
        correlation = feedback_agent.correlate_outcomes(recommendation_id)
        
        assert correlation["recommendation_id"] == recommendation_id
        assert correlation["total_outcomes"] == 1
        assert "yield_accuracy" in correlation
        assert "cost_accuracy" in correlation
    
    def test_get_improvement_insights(self, feedback_agent, sample_feedback_data):
        """Test improvement insights generation."""
        # Add feedback data
        for i in range(3):
            feedback_agent.collect_feedback(
                recommendation_id=f"rec_{i}",
                farmer_id=f"farmer_{i}",
                feedback_data=sample_feedback_data
            )
        
        insights = feedback_agent.get_improvement_insights(time_period_days=30)
        
        assert "overall_performance" in insights
        assert "strengths" in insights
        assert "areas_for_improvement" in insights
        assert "recommendations" in insights
    
    def test_langchain_tools(self, feedback_agent):
        """Test LangChain tools generation."""
        tools = feedback_agent.get_langchain_tools()
        
        assert len(tools) == 5
        assert all(hasattr(tool, "name") for tool in tools)
        assert all(hasattr(tool, "description") for tool in tools)
        assert all(hasattr(tool, "func") for tool in tools)


class TestContinuousLearningSystem:
    """Test suite for Continuous Learning System."""
    
    @pytest.fixture
    def learning_system(self):
        """Create a learning system instance for testing."""
        return ContinuousLearningSystem()
    
    @pytest.fixture
    def sample_feedback_list(self):
        """Sample feedback list for testing."""
        feedback_list = []
        for i in range(10):
            feedback_list.append({
                "timestamp": (datetime.utcnow() - timedelta(days=i*30)).isoformat(),
                "overall_rating": 4 + (i % 2),
                "usefulness_rating": 4,
                "clarity_rating": 4,
                "feasibility_rating": 4,
                "implementation_status": "completed" if i % 2 == 0 else "in_progress",
                "outcome_achieved": i % 2 == 0,
                "yield_impact": 20.0 + i,
                "cost_impact": -10.0 - i,
                "crop_type": "wheat" if i < 5 else "rice",
                "location": "Punjab" if i < 5 else "Tamil Nadu",
                "recommendation_type": "irrigation"
            })
        return feedback_list
    
    def test_recognize_seasonal_patterns_no_data(self, learning_system):
        """Test seasonal pattern recognition with no data."""
        patterns = learning_system.recognize_seasonal_patterns([])
        
        assert "message" in patterns
        assert patterns["patterns"] == []
    
    def test_recognize_seasonal_patterns_with_data(self, learning_system, sample_feedback_list):
        """Test seasonal pattern recognition with data."""
        patterns = learning_system.recognize_seasonal_patterns(sample_feedback_list)
        
        assert "patterns" in patterns
        assert "total_data_points" in patterns
        assert patterns["total_data_points"] == 10
        assert len(patterns["patterns"]) > 0
    
    def test_share_successful_techniques_no_data(self, learning_system):
        """Test successful technique sharing with no data."""
        techniques = learning_system.share_successful_techniques([])
        
        assert "message" in techniques
        assert techniques["techniques"] == []
    
    def test_share_successful_techniques_with_data(self, learning_system, sample_feedback_list):
        """Test successful technique sharing with data."""
        techniques = learning_system.share_successful_techniques(
            sample_feedback_list,
            success_threshold=4.0,
            min_implementations=3
        )
        
        assert "techniques" in techniques
        assert "total_successful" in techniques
        assert "sharing_recommendations" in techniques
    
    def test_monitor_accuracy(self, learning_system):
        """Test accuracy monitoring."""
        recommendation_id = "rec_123"
        expected_outcome = {"yield": 1000.0, "cost": 10000.0, "time": 14}
        actual_outcome = {"yield": 1200.0, "cost": 9000.0, "time": 12}
        
        accuracy_record = learning_system.monitor_accuracy(
            recommendation_id,
            expected_outcome,
            actual_outcome
        )
        
        assert accuracy_record["recommendation_id"] == recommendation_id
        assert "accuracy_scores" in accuracy_record
        assert "yield" in accuracy_record["accuracy_scores"]
        assert "cost" in accuracy_record["accuracy_scores"]
        assert "overall_accuracy" in accuracy_record
    
    def test_train_recommendation_model_insufficient_data(self, learning_system):
        """Test model training with insufficient data."""
        training_data = [{"overall_rating": 4, "yield_impact": 20, "outcome_achieved": True}] * 10
        
        result = learning_system.train_recommendation_model(training_data)
        
        assert result["status"] == "insufficient_data"
        assert "message" in result
    
    def test_train_outcome_predictor_insufficient_data(self, learning_system):
        """Test outcome predictor training with insufficient data."""
        training_data = [{"expected_yield": 1000, "actual_yield": 1200}] * 10
        
        result = learning_system.train_outcome_predictor(training_data)
        
        assert result["status"] == "insufficient_data"
        assert "message" in result
    
    def test_learning_callback(self, learning_system):
        """Test LangChain learning callback."""
        callback = learning_system.get_learning_callback()
        
        assert callback is not None
        assert hasattr(callback, "on_chain_start")
        assert hasattr(callback, "on_chain_end")
        assert hasattr(callback, "on_chain_error")
    
    def test_callback_chain_lifecycle(self, learning_system):
        """Test callback chain lifecycle."""
        callback = learning_system.get_learning_callback()
        
        # Simulate chain start
        callback.on_chain_start(
            {"name": "test_chain"},
            {"query": "test query"}
        )
        
        assert callback.current_recommendation is not None
        assert "start_time" in callback.current_recommendation
        
        # Simulate chain end
        callback.on_chain_end({"result": "test result"})
        
        assert "end_time" in callback.current_recommendation
        assert len(learning_system.recommendation_history) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
