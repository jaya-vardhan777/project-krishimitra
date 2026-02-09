"""
Continuous Learning Module for KrishiMitra Platform.

This module implements machine learning models for:
- Pattern recognition for seasonal trends
- Knowledge sharing algorithms
- Accuracy monitoring and model updating
- Continuous learning pipelines with LangChain callbacks
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import json

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, mean_squared_error, r2_score

from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.pydantic_v1 import BaseModel as LangChainBaseModel, Field as LangChainField


class SeasonalPattern(LangChainBaseModel):
    """Model for seasonal pattern data."""
    season: str = LangChainField(description="Season name")
    crop_type: str = LangChainField(description="Crop type")
    pattern_data: dict = LangChainField(description="Pattern data")
    confidence: float = LangChainField(description="Pattern confidence score")


class ContinuousLearningCallback(BaseCallbackHandler):
    """
    LangChain callback for continuous learning.
    
    This callback captures recommendation generation events and outcomes
    for continuous model improvement.
    """
    
    def __init__(self, learning_system):
        """Initialize callback with learning system reference."""
        self.learning_system = learning_system
        self.current_recommendation = None
    
    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs) -> None:
        """Called when a chain starts."""
        self.current_recommendation = {
            "start_time": datetime.utcnow().isoformat(),
            "inputs": inputs,
            "chain_type": serialized.get("name", "unknown")
        }
    
    def on_chain_end(self, outputs: Dict[str, Any], **kwargs) -> None:
        """Called when a chain ends."""
        if self.current_recommendation:
            self.current_recommendation["end_time"] = datetime.utcnow().isoformat()
            self.current_recommendation["outputs"] = outputs
            
            # Log for learning
            self.learning_system.log_recommendation_event(self.current_recommendation)
    
    def on_chain_error(self, error: Exception, **kwargs) -> None:
        """Called when a chain errors."""
        if self.current_recommendation:
            self.current_recommendation["error"] = str(error)
            self.learning_system.log_error_event(self.current_recommendation)


class ContinuousLearningSystem:
    """
    Continuous Learning System for recommendation improvement.
    
    This system implements ML models for pattern recognition,
    knowledge sharing, and accuracy monitoring.
    """
    
    def __init__(self):
        """Initialize the continuous learning system."""
        self.seasonal_patterns = {}
        self.recommendation_history = []
        self.accuracy_metrics = defaultdict(list)
        self.knowledge_base = {}
        self.successful_techniques = defaultdict(list)
        
        # ML models
        self.recommendation_classifier = None
        self.outcome_predictor = None
        self.scaler = StandardScaler()
        
        # Model performance tracking
        self.model_versions = {}
        self.current_version = "1.0.0"
    
    def recognize_seasonal_patterns(
        self,
        feedback_data: List[Dict[str, Any]],
        time_window_days: int = 365
    ) -> Dict[str, Any]:
        """
        Recognize seasonal patterns from feedback data.
        
        Args:
            feedback_data: Historical feedback data
            time_window_days: Time window for pattern analysis
            
        Returns:
            Identified seasonal patterns with confidence scores
        """
        if not feedback_data:
            return {"patterns": [], "message": "Insufficient data for pattern recognition"}
        
        df = pd.DataFrame(feedback_data)
        
        # Extract temporal features
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["month"] = df["timestamp"].dt.month
        df["season"] = df["month"].apply(self._get_season)
        
        # Group by season and analyze patterns
        seasonal_analysis = {}
        
        for season in df["season"].unique():
            season_data = df[df["season"] == season]
            
            pattern = {
                "season": season,
                "total_recommendations": len(season_data),
                "average_rating": season_data["overall_rating"].mean() if "overall_rating" in season_data else None,
                "implementation_rate": (season_data["implementation_status"] == "completed").sum() / len(season_data) * 100 if "implementation_status" in season_data else None,
                "common_crops": self._get_common_values(season_data, "crop_type") if "crop_type" in season_data else [],
                "success_rate": season_data["outcome_achieved"].sum() / len(season_data) * 100 if "outcome_achieved" in season_data else None,
                "average_yield_impact": season_data["yield_impact"].mean() if "yield_impact" in season_data else None,
                "confidence": min(len(season_data) / 100, 1.0)  # Confidence based on sample size
            }
            
            seasonal_analysis[season] = pattern
            
            # Store pattern for future use
            self.seasonal_patterns[season] = pattern
        
        return {
            "patterns": seasonal_analysis,
            "analysis_period_days": time_window_days,
            "total_data_points": len(df),
            "seasons_analyzed": list(seasonal_analysis.keys())
        }
    
    def share_successful_techniques(
        self,
        feedback_data: List[Dict[str, Any]],
        success_threshold: float = 4.0,
        min_implementations: int = 3
    ) -> Dict[str, Any]:
        """
        Identify and share successful farming techniques.
        
        Args:
            feedback_data: Historical feedback data
            success_threshold: Minimum rating for success (default 4.0)
            min_implementations: Minimum implementations to consider (default 3)
            
        Returns:
            Successful techniques with sharing recommendations
        """
        if not feedback_data:
            return {"techniques": [], "message": "No feedback data available"}
        
        df = pd.DataFrame(feedback_data)
        
        # Filter successful recommendations
        successful = df[
            (df["overall_rating"] >= success_threshold) &
            (df["outcome_achieved"] == True)
        ]
        
        if len(successful) == 0:
            return {"techniques": [], "message": "No successful techniques found"}
        
        # Group by recommendation type and analyze
        technique_analysis = {}
        
        for rec_type in successful["recommendation_type"].unique() if "recommendation_type" in successful else []:
            type_data = successful[successful["recommendation_type"] == rec_type]
            
            if len(type_data) >= min_implementations:
                technique = {
                    "recommendation_type": rec_type,
                    "success_count": len(type_data),
                    "average_rating": type_data["overall_rating"].mean(),
                    "average_yield_impact": type_data["yield_impact"].mean() if "yield_impact" in type_data else None,
                    "average_cost_impact": type_data["cost_impact"].mean() if "cost_impact" in type_data else None,
                    "implementation_rate": 100.0,  # All are successful
                    "farmer_locations": self._get_common_values(type_data, "location") if "location" in type_data else [],
                    "crop_types": self._get_common_values(type_data, "crop_type") if "crop_type" in type_data else [],
                    "key_factors": self._extract_key_factors(type_data),
                    "sharing_priority": self._calculate_sharing_priority(type_data)
                }
                
                technique_analysis[rec_type] = technique
                
                # Store for knowledge sharing
                self.successful_techniques[rec_type].append(technique)
        
        return {
            "techniques": technique_analysis,
            "total_successful": len(successful),
            "success_threshold": success_threshold,
            "sharing_recommendations": self._generate_sharing_recommendations(technique_analysis)
        }
    
    def monitor_accuracy(
        self,
        recommendation_id: str,
        expected_outcome: Dict[str, Any],
        actual_outcome: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Monitor recommendation accuracy by comparing expected vs actual outcomes.
        
        Args:
            recommendation_id: Recommendation ID
            expected_outcome: Expected outcome data
            actual_outcome: Actual outcome data
            
        Returns:
            Accuracy metrics and analysis
        """
        accuracy_record = {
            "recommendation_id": recommendation_id,
            "timestamp": datetime.utcnow().isoformat(),
            "expected": expected_outcome,
            "actual": actual_outcome,
            "accuracy_scores": {}
        }
        
        # Calculate accuracy for different metrics
        if "yield" in expected_outcome and "yield" in actual_outcome:
            yield_accuracy = self._calculate_metric_accuracy(
                expected_outcome["yield"],
                actual_outcome["yield"]
            )
            accuracy_record["accuracy_scores"]["yield"] = yield_accuracy
        
        if "cost" in expected_outcome and "cost" in actual_outcome:
            cost_accuracy = self._calculate_metric_accuracy(
                expected_outcome["cost"],
                actual_outcome["cost"]
            )
            accuracy_record["accuracy_scores"]["cost"] = cost_accuracy
        
        if "time" in expected_outcome and "time" in actual_outcome:
            time_accuracy = self._calculate_metric_accuracy(
                expected_outcome["time"],
                actual_outcome["time"]
            )
            accuracy_record["accuracy_scores"]["time"] = time_accuracy
        
        # Calculate overall accuracy
        if accuracy_record["accuracy_scores"]:
            accuracy_record["overall_accuracy"] = np.mean(list(accuracy_record["accuracy_scores"].values()))
        else:
            accuracy_record["overall_accuracy"] = None
        
        # Store accuracy metric
        self.accuracy_metrics[recommendation_id].append(accuracy_record)
        
        # Check if model update is needed
        if self._should_update_model():
            accuracy_record["model_update_triggered"] = True
            self._trigger_model_update()
        else:
            accuracy_record["model_update_triggered"] = False
        
        return accuracy_record
    
    def train_recommendation_model(
        self,
        training_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Train ML model for recommendation generation.
        
        Args:
            training_data: Historical recommendation and outcome data
            
        Returns:
            Training results and model metrics
        """
        if len(training_data) < 50:
            return {
                "status": "insufficient_data",
                "message": "Need at least 50 training samples",
                "current_samples": len(training_data)
            }
        
        df = pd.DataFrame(training_data)
        
        # Prepare features
        X, y, feature_names = self._prepare_training_features(df)
        
        if X is None or y is None:
            return {
                "status": "feature_preparation_failed",
                "message": "Failed to prepare training features"
            }
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train model
        self.recommendation_classifier = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        self.recommendation_classifier.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = self.recommendation_classifier.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        
        # Feature importance
        feature_importance = dict(zip(
            feature_names,
            self.recommendation_classifier.feature_importances_
        ))
        
        # Update model version
        self.current_version = self._increment_version(self.current_version)
        
        training_results = {
            "status": "success",
            "model_version": self.current_version,
            "training_samples": len(X_train),
            "test_samples": len(X_test),
            "accuracy": accuracy,
            "feature_importance": feature_importance,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Store model version
        self.model_versions[self.current_version] = training_results
        
        return training_results
    
    def train_outcome_predictor(
        self,
        training_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Train ML model for outcome prediction.
        
        Args:
            training_data: Historical outcome data
            
        Returns:
            Training results and model metrics
        """
        if len(training_data) < 50:
            return {
                "status": "insufficient_data",
                "message": "Need at least 50 training samples",
                "current_samples": len(training_data)
            }
        
        df = pd.DataFrame(training_data)
        
        # Prepare features for regression
        X, y, feature_names = self._prepare_outcome_features(df)
        
        if X is None or y is None:
            return {
                "status": "feature_preparation_failed",
                "message": "Failed to prepare outcome features"
            }
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train model
        self.outcome_predictor = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=5,
            random_state=42
        )
        self.outcome_predictor.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = self.outcome_predictor.predict(X_test_scaled)
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        
        training_results = {
            "status": "success",
            "model_version": self.current_version,
            "training_samples": len(X_train),
            "test_samples": len(X_test),
            "mse": mse,
            "r2_score": r2,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return training_results
    
    def log_recommendation_event(self, event: Dict[str, Any]) -> None:
        """Log recommendation event for learning."""
        self.recommendation_history.append(event)
    
    def log_error_event(self, event: Dict[str, Any]) -> None:
        """Log error event for analysis."""
        # Store error for pattern analysis
        if "errors" not in self.knowledge_base:
            self.knowledge_base["errors"] = []
        self.knowledge_base["errors"].append(event)
    
    def get_learning_callback(self) -> ContinuousLearningCallback:
        """Get LangChain callback for continuous learning."""
        return ContinuousLearningCallback(self)
    
    def _get_season(self, month: int) -> str:
        """Map month to Indian agricultural season."""
        if month in [6, 7, 8, 9, 10]:
            return "kharif"  # Monsoon season
        elif month in [11, 12, 1, 2, 3, 4]:
            return "rabi"  # Winter season
        else:
            return "zaid"  # Summer season
    
    def _get_common_values(self, df: pd.DataFrame, column: str, top_n: int = 5) -> List[str]:
        """Get most common values from a column."""
        if column not in df:
            return []
        return df[column].value_counts().head(top_n).index.tolist()
    
    def _extract_key_factors(self, df: pd.DataFrame) -> List[str]:
        """Extract key success factors from data."""
        factors = []
        
        # Analyze implementation notes for common themes
        if "implementation_notes" in df:
            notes = df["implementation_notes"].dropna()
            # Simple keyword extraction (in production, use NLP)
            common_words = []
            for note in notes:
                if isinstance(note, str):
                    words = note.lower().split()
                    common_words.extend(words)
            
            if common_words:
                word_counts = pd.Series(common_words).value_counts()
                factors = word_counts.head(5).index.tolist()
        
        return factors
    
    def _calculate_sharing_priority(self, df: pd.DataFrame) -> str:
        """Calculate priority for sharing technique."""
        avg_rating = df["overall_rating"].mean() if "overall_rating" in df else 0
        success_count = len(df)
        
        if avg_rating >= 4.5 and success_count >= 10:
            return "high"
        elif avg_rating >= 4.0 and success_count >= 5:
            return "medium"
        else:
            return "low"
    
    def _generate_sharing_recommendations(self, techniques: Dict[str, Any]) -> List[str]:
        """Generate recommendations for sharing techniques."""
        recommendations = []
        
        for tech_type, tech_data in techniques.items():
            if tech_data["sharing_priority"] == "high":
                recommendations.append(
                    f"Widely share {tech_type} technique - high success rate with {tech_data['success_count']} implementations"
                )
            elif tech_data["sharing_priority"] == "medium":
                recommendations.append(
                    f"Share {tech_type} technique with similar farmers in {', '.join(tech_data['farmer_locations'][:2])}"
                )
        
        return recommendations
    
    def _calculate_metric_accuracy(self, expected: float, actual: float) -> float:
        """Calculate accuracy for a single metric."""
        if expected == 0:
            return 0.0
        
        error_percentage = abs((actual - expected) / expected) * 100
        accuracy = max(0, 100 - error_percentage)
        return accuracy
    
    def _should_update_model(self) -> bool:
        """Determine if model should be updated."""
        # Simple heuristic: update every 100 accuracy measurements
        total_measurements = sum(len(metrics) for metrics in self.accuracy_metrics.values())
        return total_measurements > 0 and total_measurements % 100 == 0
    
    def _trigger_model_update(self) -> None:
        """Trigger model update process."""
        # In production, this would trigger a retraining pipeline
        pass
    
    def _prepare_training_features(self, df: pd.DataFrame) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], List[str]]:
        """Prepare features for training recommendation model."""
        # This is a simplified version - in production, use more sophisticated feature engineering
        try:
            feature_columns = []
            
            # Numeric features
            if "overall_rating" in df:
                feature_columns.append("overall_rating")
            if "yield_impact" in df:
                feature_columns.append("yield_impact")
            if "cost_impact" in df:
                feature_columns.append("cost_impact")
            
            if not feature_columns:
                return None, None, []
            
            X = df[feature_columns].fillna(0).values
            y = (df["outcome_achieved"] == True).astype(int).values if "outcome_achieved" in df else None
            
            return X, y, feature_columns
        except Exception:
            return None, None, []
    
    def _prepare_outcome_features(self, df: pd.DataFrame) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], List[str]]:
        """Prepare features for training outcome predictor."""
        try:
            feature_columns = []
            
            if "expected_yield" in df:
                feature_columns.append("expected_yield")
            if "expected_cost" in df:
                feature_columns.append("expected_cost")
            
            if not feature_columns:
                return None, None, []
            
            X = df[feature_columns].fillna(0).values
            y = df["actual_yield"].fillna(0).values if "actual_yield" in df else None
            
            return X, y, feature_columns
        except Exception:
            return None, None, []
    
    def _increment_version(self, version: str) -> str:
        """Increment model version."""
        parts = version.split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)
