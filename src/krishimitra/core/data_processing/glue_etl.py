"""
AWS Glue ETL Manager for KrishiMitra Platform

This module manages AWS Glue ETL jobs for data transformation,
cataloging, and preparation for analytics.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

from src.krishimitra.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ETLJobConfig:
    """Configuration for AWS Glue ETL job"""
    job_name: str
    script_location: str
    role_arn: str
    max_capacity: float = 2.0
    timeout: int = 2880  # 48 hours in minutes
    max_retries: int = 1
    worker_type: str = "G.1X"  # Standard worker
    number_of_workers: int = 2
    glue_version: str = "4.0"
    default_arguments: Optional[Dict[str, str]] = None
    
    def __post_init__(self):
        if self.default_arguments is None:
            self.default_arguments = {
                '--enable-metrics': 'true',
                '--enable-continuous-cloudwatch-log': 'true',
                '--enable-spark-ui': 'true',
                '--spark-event-logs-path': f's3://{settings.s3_bucket}/spark-logs/'
            }


class GlueETLManager:
    """
    Manages AWS Glue ETL jobs for data processing
    
    Handles job creation, execution, monitoring, and optimization
    for agricultural data transformation pipelines.
    """
    
    def __init__(self):
        self.glue_client = boto3.client('glue', region_name=settings.aws_region)
        self.s3_client = boto3.client('s3', region_name=settings.aws_region)
    
    async def create_etl_job(self, config: ETLJobConfig) -> bool:
        """
        Create or update Glue ETL job
        
        Args:
            config: ETL job configuration
            
        Returns:
            True if job created/updated successfully
        """
        try:
            # Check if job exists
            try:
                self.glue_client.get_job(JobName=config.job_name)
                # Job exists, update it
                return await self._update_job(config)
            except ClientError as e:
                if e.response['Error']['Code'] != 'EntityNotFoundException':
                    raise
            
            # Create new job
            job_params = {
                'Name': config.job_name,
                'Role': config.role_arn,
                'Command': {
                    'Name': 'glueetl',
                    'ScriptLocation': config.script_location,
                    'PythonVersion': '3'
                },
                'DefaultArguments': config.default_arguments,
                'MaxRetries': config.max_retries,
                'Timeout': config.timeout,
                'GlueVersion': config.glue_version,
                'WorkerType': config.worker_type,
                'NumberOfWorkers': config.number_of_workers
            }
            
            self.glue_client.create_job(**job_params)
            logger.info(f"Created Glue ETL job: {config.job_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating Glue ETL job: {e}")
            return False
    
    async def _update_job(self, config: ETLJobConfig) -> bool:
        """Update existing Glue job"""
        try:
            job_update = {
                'Role': config.role_arn,
                'Command': {
                    'Name': 'glueetl',
                    'ScriptLocation': config.script_location,
                    'PythonVersion': '3'
                },
                'DefaultArguments': config.default_arguments,
                'MaxRetries': config.max_retries,
                'Timeout': config.timeout,
                'GlueVersion': config.glue_version,
                'WorkerType': config.worker_type,
                'NumberOfWorkers': config.number_of_workers
            }
            
            self.glue_client.update_job(
                JobName=config.job_name,
                JobUpdate=job_update
            )
            
            logger.info(f"Updated Glue ETL job: {config.job_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating Glue ETL job: {e}")
            return False
    
    async def start_job_run(self, job_name: str, 
                           arguments: Optional[Dict[str, str]] = None) -> Optional[str]:
        """
        Start ETL job run
        
        Args:
            job_name: Name of the Glue job
            arguments: Optional job arguments
            
        Returns:
            Job run ID if successful, None otherwise
        """
        try:
            params = {'JobName': job_name}
            if arguments:
                params['Arguments'] = arguments
            
            response = self.glue_client.start_job_run(**params)
            job_run_id = response['JobRunId']
            
            logger.info(f"Started Glue job run: {job_name} (ID: {job_run_id})")
            return job_run_id
            
        except Exception as e:
            logger.error(f"Error starting Glue job run: {e}")
            return None
    
    async def get_job_run_status(self, job_name: str, run_id: str) -> Dict[str, Any]:
        """
        Get status of job run
        
        Args:
            job_name: Name of the Glue job
            run_id: Job run ID
            
        Returns:
            Dictionary with job run status information
        """
        try:
            response = self.glue_client.get_job_run(
                JobName=job_name,
                RunId=run_id
            )
            
            job_run = response['JobRun']
            
            return {
                'job_name': job_name,
                'run_id': run_id,
                'state': job_run['JobRunState'],
                'started_on': job_run.get('StartedOn'),
                'completed_on': job_run.get('CompletedOn'),
                'execution_time': job_run.get('ExecutionTime'),
                'error_message': job_run.get('ErrorMessage'),
                'dpu_seconds': job_run.get('DPUSeconds')
            }
            
        except Exception as e:
            logger.error(f"Error getting job run status: {e}")
            return {'state': 'UNKNOWN', 'error': str(e)}
    
    async def create_database(self, database_name: str, 
                             description: str = "Agricultural data catalog") -> bool:
        """
        Create Glue catalog database
        
        Args:
            database_name: Name of the database
            description: Database description
            
        Returns:
            True if database created successfully
        """
        try:
            self.glue_client.create_database(
                DatabaseInput={
                    'Name': database_name,
                    'Description': description
                }
            )
            
            logger.info(f"Created Glue database: {database_name}")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'AlreadyExistsException':
                logger.info(f"Database {database_name} already exists")
                return True
            logger.error(f"Error creating Glue database: {e}")
            return False
    
    async def create_table(self, database_name: str, table_name: str,
                          s3_location: str, columns: List[Dict[str, str]],
                          partition_keys: Optional[List[Dict[str, str]]] = None) -> bool:
        """
        Create Glue catalog table
        
        Args:
            database_name: Database name
            table_name: Table name
            s3_location: S3 location of data
            columns: List of column definitions
            partition_keys: Optional partition key definitions
            
        Returns:
            True if table created successfully
        """
        try:
            table_input = {
                'Name': table_name,
                'StorageDescriptor': {
                    'Columns': columns,
                    'Location': s3_location,
                    'InputFormat': 'org.apache.hadoop.mapred.TextInputFormat',
                    'OutputFormat': 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat',
                    'SerdeInfo': {
                        'SerializationLibrary': 'org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe',
                        'Parameters': {
                            'field.delim': ',',
                            'skip.header.line.count': '1'
                        }
                    }
                },
                'TableType': 'EXTERNAL_TABLE'
            }
            
            if partition_keys:
                table_input['PartitionKeys'] = partition_keys
            
            self.glue_client.create_table(
                DatabaseName=database_name,
                TableInput=table_input
            )
            
            logger.info(f"Created Glue table: {database_name}.{table_name}")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'AlreadyExistsException':
                logger.info(f"Table {database_name}.{table_name} already exists")
                return True
            logger.error(f"Error creating Glue table: {e}")
            return False
    
    async def create_crawler(self, crawler_name: str, database_name: str,
                            s3_targets: List[str], role_arn: str,
                            schedule: Optional[str] = None) -> bool:
        """
        Create Glue crawler for automatic schema discovery
        
        Args:
            crawler_name: Name of the crawler
            database_name: Target database name
            s3_targets: List of S3 paths to crawl
            role_arn: IAM role ARN for crawler
            schedule: Optional cron schedule
            
        Returns:
            True if crawler created successfully
        """
        try:
            crawler_params = {
                'Name': crawler_name,
                'Role': role_arn,
                'DatabaseName': database_name,
                'Targets': {
                    'S3Targets': [{'Path': path} for path in s3_targets]
                },
                'SchemaChangePolicy': {
                    'UpdateBehavior': 'UPDATE_IN_DATABASE',
                    'DeleteBehavior': 'LOG'
                }
            }
            
            if schedule:
                crawler_params['Schedule'] = schedule
            
            self.glue_client.create_crawler(**crawler_params)
            logger.info(f"Created Glue crawler: {crawler_name}")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'AlreadyExistsException':
                logger.info(f"Crawler {crawler_name} already exists")
                return True
            logger.error(f"Error creating Glue crawler: {e}")
            return False
    
    async def start_crawler(self, crawler_name: str) -> bool:
        """Start Glue crawler"""
        try:
            self.glue_client.start_crawler(Name=crawler_name)
            logger.info(f"Started Glue crawler: {crawler_name}")
            return True
        except Exception as e:
            logger.error(f"Error starting crawler: {e}")
            return False
    
    async def get_job_metrics(self, job_name: str, days: int = 7) -> Dict[str, Any]:
        """
        Get job execution metrics
        
        Args:
            job_name: Name of the Glue job
            days: Number of days to look back
            
        Returns:
            Dictionary with job metrics
        """
        try:
            response = self.glue_client.get_job_runs(
                JobName=job_name,
                MaxResults=100
            )
            
            job_runs = response.get('JobRuns', [])
            
            # Calculate metrics
            total_runs = len(job_runs)
            successful_runs = sum(1 for run in job_runs if run['JobRunState'] == 'SUCCEEDED')
            failed_runs = sum(1 for run in job_runs if run['JobRunState'] == 'FAILED')
            
            execution_times = [
                run.get('ExecutionTime', 0) for run in job_runs 
                if run.get('ExecutionTime')
            ]
            
            avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0
            
            dpu_seconds = [
                run.get('DPUSeconds', 0) for run in job_runs 
                if run.get('DPUSeconds')
            ]
            
            total_dpu_seconds = sum(dpu_seconds)
            
            return {
                'job_name': job_name,
                'total_runs': total_runs,
                'successful_runs': successful_runs,
                'failed_runs': failed_runs,
                'success_rate': successful_runs / total_runs if total_runs > 0 else 0,
                'avg_execution_time_seconds': avg_execution_time,
                'total_dpu_seconds': total_dpu_seconds
            }
            
        except Exception as e:
            logger.error(f"Error getting job metrics: {e}")
            return {}
