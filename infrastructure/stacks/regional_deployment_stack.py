"""
KrishiMitra Regional Deployment Stack

This module implements multi-region deployment, failover systems, uptime monitoring,
disaster recovery, and automated recovery procedures for the KrishiMitra platform.

Requirements: 11.3, 11.5
"""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_backup as backup,
    aws_events as events,
    aws_events_targets as event_targets,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_logs as logs,
    CfnOutput,
)
from constructs import Construct
from typing import List, Dict


class RegionalDeploymentStack(Stack):
    """
    Regional deployment stack for KrishiMitra platform.
    
    Implements multi-region deployment with automatic failover, health monitoring,
    disaster recovery, and business continuity capabilities.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        primary_region: str,
        secondary_regions: List[str],
        domain_name: str = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.env_name = env_name
        self.primary_region = primary_region
        self.secondary_regions = secondary_regions
        self.domain_name = domain_name
        
        # Create SNS topic for alerts
        self._create_alerting_infrastructure()
        
        # Create health check monitoring
        self._create_health_checks()
        
        # Create disaster recovery infrastructure
        self._create_disaster_recovery()
        
        # Create automated failover system
        self._create_failover_automation()
        
        # Create outputs
        self._create_outputs()

    def _create_alerting_infrastructure(self):
        """Create SNS topics and subscriptions for operational alerts."""
        
        # SNS topic for critical alerts
        self.critical_alerts_topic = sns.Topic(
            self, "CriticalAlerts",
            topic_name=f"krishimitra-critical-alerts-{self.env_name}",
            display_name=f"KrishiMitra Critical Alerts - {self.env_name.upper()}"
        )
        
        # SNS topic for operational alerts
        self.operational_alerts_topic = sns.Topic(
            self, "OperationalAlerts",
            topic_name=f"krishimitra-operational-alerts-{self.env_name}",
            display_name=f"KrishiMitra Operational Alerts - {self.env_name.upper()}"
        )
        
        # Add email subscriptions (can be configured via context)
        alert_emails = self.node.try_get_context("alert_emails") or []
        for email in alert_emails:
            self.critical_alerts_topic.add_subscription(
                subscriptions.EmailSubscription(email)
            )
            self.operational_alerts_topic.add_subscription(
                subscriptions.EmailSubscription(email)
            )

    def _create_health_checks(self):
        """Create Route 53 health checks for service monitoring."""
        
        # Health check for primary region API endpoint
        self.primary_health_check = route53.CfnHealthCheck(
            self, "PrimaryRegionHealthCheck",
            health_check_config=route53.CfnHealthCheck.HealthCheckConfigProperty(
                type="HTTPS",
                resource_path="/api/v1/health",
                port=443,
                request_interval=30,
                failure_threshold=3,
                measure_latency=True,
                enable_sni=True
            ),
            health_check_tags=[
                route53.CfnHealthCheck.HealthCheckTagProperty(
                    key="Name",
                    value=f"KrishiMitra-Primary-{self.env_name}"
                ),
                route53.CfnHealthCheck.HealthCheckTagProperty(
                    key="Environment",
                    value=self.env_name
                ),
                route53.CfnHealthCheck.HealthCheckTagProperty(
                    key="Region",
                    value=self.primary_region
                )
            ]
        )
        
        # Create health checks for secondary regions
        self.secondary_health_checks = []
        for idx, region in enumerate(self.secondary_regions):
            health_check = route53.CfnHealthCheck(
                self, f"SecondaryRegionHealthCheck{idx}",
                health_check_config=route53.CfnHealthCheck.HealthCheckConfigProperty(
                    type="HTTPS",
                    resource_path="/api/v1/health",
                    port=443,
                    request_interval=30,
                    failure_threshold=3,
                    measure_latency=True,
                    enable_sni=True
                ),
                health_check_tags=[
                    route53.CfnHealthCheck.HealthCheckTagProperty(
                        key="Name",
                        value=f"KrishiMitra-Secondary-{region}-{self.env_name}"
                    ),
                    route53.CfnHealthCheck.HealthCheckTagProperty(
                        key="Environment",
                        value=self.env_name
                    ),
                    route53.CfnHealthCheck.HealthCheckTagProperty(
                        key="Region",
                        value=region
                    )
                ]
            )
            self.secondary_health_checks.append(health_check)
        
        # Create CloudWatch alarms for health check failures
        self._create_health_check_alarms()

    def _create_health_check_alarms(self):
        """Create CloudWatch alarms for Route 53 health check failures."""
        
        # Alarm for primary region health check
        primary_health_alarm = cloudwatch.Alarm(
            self, "PrimaryRegionHealthAlarm",
            alarm_name=f"KrishiMitra-Primary-Health-{self.env_name}",
            alarm_description=f"Primary region ({self.primary_region}) health check failure",
            metric=cloudwatch.Metric(
                namespace="AWS/Route53",
                metric_name="HealthCheckStatus",
                dimensions_map={
                    "HealthCheckId": self.primary_health_check.attr_health_check_id
                },
                statistic="Minimum",
                period=Duration.minutes(1)
            ),
            threshold=1,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.BREACHING
        )
        
        # Add SNS action to alarm
        primary_health_alarm.add_alarm_action(
            cw_actions.SnsAction(self.critical_alerts_topic)
        )
        
        # Create alarms for secondary regions
        for idx, health_check in enumerate(self.secondary_health_checks):
            region = self.secondary_regions[idx]
            alarm = cloudwatch.Alarm(
                self, f"SecondaryRegionHealthAlarm{idx}",
                alarm_name=f"KrishiMitra-Secondary-{region}-Health-{self.env_name}",
                alarm_description=f"Secondary region ({region}) health check failure",
                metric=cloudwatch.Metric(
                    namespace="AWS/Route53",
                    metric_name="HealthCheckStatus",
                    dimensions_map={
                        "HealthCheckId": health_check.attr_health_check_id
                    },
                    statistic="Minimum",
                    period=Duration.minutes(1)
                ),
                threshold=1,
                evaluation_periods=2,
                comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.BREACHING
            )
            
            alarm.add_alarm_action(
                cw_actions.SnsAction(self.operational_alerts_topic)
            )
        
        # Create composite alarm for overall system health
        self.system_health_alarm = cloudwatch.CompositeAlarm(
            self, "SystemHealthAlarm",
            alarm_name=f"KrishiMitra-System-Health-{self.env_name}",
            alarm_description="Overall system health across all regions",
            composite_alarm_name=f"KrishiMitra-System-Health-{self.env_name}",
            actions_enabled=True,
            alarm_rule=cloudwatch.AlarmRule.all_of(
                cloudwatch.AlarmRule.from_alarm(
                    primary_health_alarm,
                    cloudwatch.AlarmState.ALARM
                ),
                *[
                    cloudwatch.AlarmRule.from_alarm(
                        cloudwatch.Alarm.from_alarm_arn(
                            self,
                            f"ImportedSecondaryAlarm{idx}",
                            f"arn:aws:cloudwatch:{self.region}:{self.account}:alarm:KrishiMitra-Secondary-{region}-Health-{self.env_name}"
                        ),
                        cloudwatch.AlarmState.ALARM
                    )
                    for idx, region in enumerate(self.secondary_regions)
                ]
            )
        )
        
        self.system_health_alarm.add_alarm_action(
            cw_actions.SnsAction(self.critical_alerts_topic)
        )

    def _create_disaster_recovery(self):
        """Create AWS Backup plans for disaster recovery."""
        
        # Create backup vault
        self.backup_vault = backup.BackupVault(
            self, "KrishiMitraBackupVault",
            backup_vault_name=f"krishimitra-backup-vault-{self.env_name}",
            removal_policy=RemovalPolicy.RETAIN
        )
        
        # Create backup plan for DynamoDB tables
        self.dynamodb_backup_plan = backup.BackupPlan(
            self, "DynamoDBBackupPlan",
            backup_plan_name=f"krishimitra-dynamodb-backup-{self.env_name}",
            backup_vault=self.backup_vault
        )
        
        # Add backup rules based on environment
        if self.env_name == "prod":
            # Production: Daily backups with 30-day retention
            self.dynamodb_backup_plan.add_rule(
                backup.BackupPlanRule(
                    rule_name="DailyBackup",
                    schedule_expression=events.Schedule.cron(
                        hour="2",
                        minute="0"
                    ),
                    delete_after=Duration.days(30),
                    enable_continuous_backup=True,
                    start_window=Duration.hours(1),
                    completion_window=Duration.hours(2)
                )
            )
            
            # Weekly backups with 90-day retention
            self.dynamodb_backup_plan.add_rule(
                backup.BackupPlanRule(
                    rule_name="WeeklyBackup",
                    schedule_expression=events.Schedule.cron(
                        week_day="SUN",
                        hour="3",
                        minute="0"
                    ),
                    delete_after=Duration.days(90),
                    move_to_cold_storage_after=Duration.days(30)
                )
            )
            
            # Monthly backups with 1-year retention
            self.dynamodb_backup_plan.add_rule(
                backup.BackupPlanRule(
                    rule_name="MonthlyBackup",
                    schedule_expression=events.Schedule.cron(
                        day="1",
                        hour="4",
                        minute="0"
                    ),
                    delete_after=Duration.days(365),
                    move_to_cold_storage_after=Duration.days(60)
                )
            )
        else:
            # Non-production: Daily backups with 7-day retention
            self.dynamodb_backup_plan.add_rule(
                backup.BackupPlanRule(
                    rule_name="DailyBackup",
                    schedule_expression=events.Schedule.cron(
                        hour="2",
                        minute="0"
                    ),
                    delete_after=Duration.days(7)
                )
            )
        
        # Create backup plan for S3 buckets
        self.s3_backup_plan = backup.BackupPlan(
            self, "S3BackupPlan",
            backup_plan_name=f"krishimitra-s3-backup-{self.env_name}",
            backup_vault=self.backup_vault
        )
        
        # Add S3 backup rules
        if self.env_name == "prod":
            self.s3_backup_plan.add_rule(
                backup.BackupPlanRule(
                    rule_name="WeeklyS3Backup",
                    schedule_expression=events.Schedule.cron(
                        week_day="SAT",
                        hour="1",
                        minute="0"
                    ),
                    delete_after=Duration.days(90),
                    move_to_cold_storage_after=Duration.days(30)
                )
            )

    def _create_failover_automation(self):
        """Create Lambda functions for automated failover and recovery."""
        
        # Lambda function for automated failover
        self.failover_function = lambda_.Function(
            self, "FailoverFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="failover_handler.handler",
            code=lambda_.Code.from_asset("infrastructure/lambda/failover"),
            function_name=f"krishimitra-failover-{self.env_name}",
            timeout=Duration.minutes(5),
            memory_size=256,
            environment={
                "ENV": self.env_name,
                "PRIMARY_REGION": self.primary_region,
                "SECONDARY_REGIONS": ",".join(self.secondary_regions),
                "CRITICAL_ALERTS_TOPIC_ARN": self.critical_alerts_topic.topic_arn,
                "OPERATIONAL_ALERTS_TOPIC_ARN": self.operational_alerts_topic.topic_arn
            },
            log_retention=logs.RetentionDays.ONE_MONTH,
            tracing=lambda_.Tracing.ACTIVE
        )
        
        # Grant permissions to failover function
        self.failover_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "route53:ChangeResourceRecordSets",
                    "route53:GetHealthCheckStatus",
                    "route53:GetHealthCheck",
                    "route53:ListHealthChecks",
                    "cloudwatch:DescribeAlarms",
                    "cloudwatch:GetMetricStatistics",
                    "sns:Publish",
                    "dynamodb:DescribeTable",
                    "dynamodb:UpdateTable",
                    "lambda:UpdateFunctionConfiguration",
                    "apigateway:GET",
                    "apigateway:PATCH"
                ],
                resources=["*"]
            )
        )
        
        # Lambda function for health monitoring
        self.health_monitor_function = lambda_.Function(
            self, "HealthMonitorFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="health_monitor.handler",
            code=lambda_.Code.from_asset("infrastructure/lambda/health_monitor"),
            function_name=f"krishimitra-health-monitor-{self.env_name}",
            timeout=Duration.minutes(2),
            memory_size=256,
            environment={
                "ENV": self.env_name,
                "PRIMARY_REGION": self.primary_region,
                "SECONDARY_REGIONS": ",".join(self.secondary_regions),
                "PRIMARY_HEALTH_CHECK_ID": self.primary_health_check.attr_health_check_id,
                "OPERATIONAL_ALERTS_TOPIC_ARN": self.operational_alerts_topic.topic_arn
            },
            log_retention=logs.RetentionDays.ONE_MONTH
        )
        
        # Grant permissions to health monitor function
        self.health_monitor_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "route53:GetHealthCheckStatus",
                    "route53:GetHealthCheck",
                    "cloudwatch:PutMetricData",
                    "cloudwatch:GetMetricStatistics",
                    "sns:Publish"
                ],
                resources=["*"]
            )
        )
        
        # Lambda function for disaster recovery
        self.disaster_recovery_function = lambda_.Function(
            self, "DisasterRecoveryFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="disaster_recovery.handler",
            code=lambda_.Code.from_asset("infrastructure/lambda/disaster_recovery"),
            function_name=f"krishimitra-disaster-recovery-{self.env_name}",
            timeout=Duration.minutes(15),
            memory_size=512,
            environment={
                "ENV": self.env_name,
                "PRIMARY_REGION": self.primary_region,
                "SECONDARY_REGIONS": ",".join(self.secondary_regions),
                "BACKUP_VAULT_NAME": self.backup_vault.backup_vault_name,
                "CRITICAL_ALERTS_TOPIC_ARN": self.critical_alerts_topic.topic_arn
            },
            log_retention=logs.RetentionDays.ONE_MONTH,
            tracing=lambda_.Tracing.ACTIVE
        )
        
        # Grant permissions to disaster recovery function
        self.disaster_recovery_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "backup:StartRestoreJob",
                    "backup:DescribeRestoreJob",
                    "backup:ListRecoveryPointsByBackupVault",
                    "dynamodb:RestoreTableFromBackup",
                    "dynamodb:DescribeTable",
                    "s3:RestoreObject",
                    "s3:GetObject",
                    "s3:PutObject",
                    "sns:Publish",
                    "cloudformation:DescribeStacks",
                    "cloudformation:UpdateStack"
                ],
                resources=["*"]
            )
        )
        
        # Create EventBridge rules for automated execution
        self._create_automation_rules()

    def _create_automation_rules(self):
        """Create EventBridge rules for automated failover and monitoring."""
        
        # Rule to trigger health monitoring every 5 minutes
        health_monitor_rule = events.Rule(
            self, "HealthMonitorRule",
            rule_name=f"krishimitra-health-monitor-{self.env_name}",
            description="Periodic health monitoring for KrishiMitra platform",
            schedule=events.Schedule.rate(Duration.minutes(5)),
            enabled=True
        )
        
        health_monitor_rule.add_target(
            event_targets.LambdaFunction(self.health_monitor_function)
        )
        
        # Rule to trigger failover on CloudWatch alarm state change
        failover_rule = events.Rule(
            self, "FailoverRule",
            rule_name=f"krishimitra-failover-trigger-{self.env_name}",
            description="Trigger automated failover on health check failures",
            event_pattern=events.EventPattern(
                source=["aws.cloudwatch"],
                detail_type=["CloudWatch Alarm State Change"],
                detail={
                    "alarmName": [
                        f"KrishiMitra-Primary-Health-{self.env_name}",
                        f"KrishiMitra-System-Health-{self.env_name}"
                    ],
                    "state": {
                        "value": ["ALARM"]
                    }
                }
            ),
            enabled=True if self.env_name == "prod" else False
        )
        
        failover_rule.add_target(
            event_targets.LambdaFunction(self.failover_function)
        )
        
        # Rule to trigger disaster recovery on manual invocation
        disaster_recovery_rule = events.Rule(
            self, "DisasterRecoveryRule",
            rule_name=f"krishimitra-disaster-recovery-{self.env_name}",
            description="Manual trigger for disaster recovery procedures",
            event_pattern=events.EventPattern(
                source=["krishimitra.disaster-recovery"],
                detail_type=["Disaster Recovery Initiated"]
            ),
            enabled=True
        )
        
        disaster_recovery_rule.add_target(
            event_targets.LambdaFunction(self.disaster_recovery_function)
        )

    def _create_outputs(self):
        """Create CloudFormation outputs for regional deployment resources."""
        
        CfnOutput(
            self, "CriticalAlertsTopicArn",
            value=self.critical_alerts_topic.topic_arn,
            description="SNS Topic ARN for critical alerts",
            export_name=f"KrishiMitra-{self.env_name}-CriticalAlertsTopic"
        )
        
        CfnOutput(
            self, "OperationalAlertsTopicArn",
            value=self.operational_alerts_topic.topic_arn,
            description="SNS Topic ARN for operational alerts",
            export_name=f"KrishiMitra-{self.env_name}-OperationalAlertsTopic"
        )
        
        CfnOutput(
            self, "PrimaryHealthCheckId",
            value=self.primary_health_check.attr_health_check_id,
            description="Route 53 Health Check ID for primary region",
            export_name=f"KrishiMitra-{self.env_name}-PrimaryHealthCheckId"
        )
        
        CfnOutput(
            self, "BackupVaultName",
            value=self.backup_vault.backup_vault_name,
            description="AWS Backup Vault Name",
            export_name=f"KrishiMitra-{self.env_name}-BackupVaultName"
        )
        
        CfnOutput(
            self, "FailoverFunctionArn",
            value=self.failover_function.function_arn,
            description="Lambda Function ARN for automated failover",
            export_name=f"KrishiMitra-{self.env_name}-FailoverFunctionArn"
        )
        
        CfnOutput(
            self, "DisasterRecoveryFunctionArn",
            value=self.disaster_recovery_function.function_arn,
            description="Lambda Function ARN for disaster recovery",
            export_name=f"KrishiMitra-{self.env_name}-DisasterRecoveryFunctionArn"
        )
