"""
Data Processing Module for KrishiMitra Platform

This module provides scalable data ingestion and processing pipelines
using AWS Kinesis, Glue, and EMR with Apache Spark.
"""

from .kinesis_pipeline import KinesisDataPipeline, DataPartitioner
from .glue_etl import GlueETLManager, ETLJobConfig
from .spark_processor import SparkDataProcessor, EMRClusterManager
from .lifecycle_manager import S3LifecycleManager, DataArchiver
from .performance_monitor import PerformanceMonitor, ResourceOptimizer

__all__ = [
    'KinesisDataPipeline',
    'DataPartitioner',
    'GlueETLManager',
    'ETLJobConfig',
    'SparkDataProcessor',
    'EMRClusterManager',
    'S3LifecycleManager',
    'DataArchiver',
    'PerformanceMonitor',
    'ResourceOptimizer',
]
