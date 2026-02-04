"""
KrishiMitra AWS CDK Stack

This module defines the complete AWS infrastructure for the KrishiMitra platform,
including API Gateway, Lambda functions, DynamoDB tables, S3 buckets, Bedrock access,
IoT Core, Cognito authentication, and CloudWatch monitoring.
"""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_apigateway as apigateway,
    aws_lambda as lambda_,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_iot as iot,
    aws_cognito as cognito,
    aws_logs as logs,
    aws_cloudwatch as cloudwatch,
    aws_iam as iam,
    aws_applicationautoscaling as autoscaling,
    CfnOutput,
)
from constructs import Construct


class KrishiMitraStack(Stack):
    """
    Main CDK stack for KrishiMitra platform infrastructure.
    
    Creates all necessary AWS resources for development, staging, and production environments
    with proper scaling, monitoring, and security configurations.
    """

    def __init__(self, scope: Construct, construct_id: str, env_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.env_name = env_name
        
        # Create core infrastructure components
        self._create_storage_layer()
        self._create_authentication()
        self._create_compute_layer()
        self._create_api_gateway()
        self._create_iot_infrastructure()
        self._create_monitoring()
        self._setup_permissions()
        self._create_outputs()

    def _create_storage_layer(self):
        """Create DynamoDB tables and S3 buckets for data storage."""
        
        # DynamoDB Tables
        self.farmer_profiles_table = dynamodb.Table(
            self, "FarmerProfiles",
            table_name=f"krishimitra-farmer-profiles-{self.env_name}",
            partition_key=dynamodb.Attribute(
                name="farmerId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN,
            point_in_time_recovery=True,
            encryption=dynamodb.TableEncryption.AWS_MANAGED
        )
        
        self.conversations_table = dynamodb.Table(
            self, "Conversations",
            table_name=f"krishimitra-conversations-{self.env_name}",
            partition_key=dynamodb.Attribute(
                name="conversationId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.NUMBER
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN,
            time_to_live_attribute="ttl",
            encryption=dynamodb.TableEncryption.AWS_MANAGED
        )
        
        self.recommendations_table = dynamodb.Table(
            self, "Recommendations",
            table_name=f"krishimitra-recommendations-{self.env_name}",
            partition_key=dynamodb.Attribute(
                name="recommendationId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN,
            encryption=dynamodb.TableEncryption.AWS_MANAGED
        )
        
        # Add GSI for farmer-based queries
        self.recommendations_table.add_global_secondary_index(
            index_name="FarmerIndex",
            partition_key=dynamodb.Attribute(
                name="farmerId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.NUMBER
            )
        )
        
        self.sensor_readings_table = dynamodb.Table(
            self, "SensorReadings",
            table_name=f"krishimitra-sensor-readings-{self.env_name}",
            partition_key=dynamodb.Attribute(
                name="deviceId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.NUMBER
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN,
            time_to_live_attribute="ttl",
            encryption=dynamodb.TableEncryption.AWS_MANAGED
        )
        
        # S3 Buckets
        self.agricultural_imagery_bucket = s3.Bucket(
            self, "AgriculturalImagery",
            bucket_name=f"krishimitra-agricultural-imagery-{self.env_name}",
            removal_policy=RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ArchiveOldImages",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(30)
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90)
                        )
                    ]
                )
            ]
        )
        
        self.weather_data_bucket = s3.Bucket(
            self, "WeatherData",
            bucket_name=f"krishimitra-weather-data-{self.env_name}",
            removal_policy=RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN,
            encryption=s3.BucketEncryption.S3_MANAGED
        )
        
        self.market_data_bucket = s3.Bucket(
            self, "MarketData",
            bucket_name=f"krishimitra-market-data-{self.env_name}",
            removal_policy=RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN,
            encryption=s3.BucketEncryption.S3_MANAGED
        )
        
        self.model_artifacts_bucket = s3.Bucket(
            self, "ModelArtifacts",
            bucket_name=f"krishimitra-model-artifacts-{self.env_name}",
            removal_policy=RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True
        )

    def _create_authentication(self):
        """Create Cognito User Pool for authentication and authorization."""
        
        self.user_pool = cognito.UserPool(
            self, "KrishiMitraUserPool",
            user_pool_name=f"krishimitra-users-{self.env_name}",
            sign_in_aliases=cognito.SignInAliases(
                phone=True,
                email=True
            ),
            auto_verify=cognito.AutoVerifiedAttrs(
                phone=True,
                email=True
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False
            ),
            mfa=cognito.Mfa.OPTIONAL,
            mfa_second_factor=cognito.MfaSecondFactor(
                sms=True,
                otp=True
            ),
            account_recovery=cognito.AccountRecovery.PHONE_WITHOUT_MFA_AND_EMAIL,
            removal_policy=RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN
        )
        
        # Add custom attributes for farmer profiles
        self.user_pool.add_domain(
            "KrishiMitraDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"krishimitra-{self.env_name}"
            )
        )
        
        self.user_pool_client = self.user_pool.add_client(
            "KrishiMitraAppClient",
            user_pool_client_name=f"krishimitra-app-{self.env_name}",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
                custom=True
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True,
                    implicit_code_grant=True
                ),
                scopes=[
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.PROFILE,
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.PHONE
                ]
            )
        )
        
        # Identity Pool for AWS resource access
        self.identity_pool = cognito.CfnIdentityPool(
            self, "KrishiMitraIdentityPool",
            identity_pool_name=f"krishimitra_identity_pool_{self.env_name}",
            allow_unauthenticated_identities=False,
            cognito_identity_providers=[
                cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
                    client_id=self.user_pool_client.user_pool_client_id,
                    provider_name=self.user_pool.user_pool_provider_name
                )
            ]
        )

    def _create_compute_layer(self):
        """Create Lambda functions for the FastAPI application."""
        
        # Main FastAPI Lambda function
        self.main_api_function = lambda_.Function(
            self, "MainAPIFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="main.handler",
            code=lambda_.Code.from_asset("src/krishimitra"),
            function_name=f"krishimitra-main-api-{self.env_name}",
            timeout=Duration.seconds(30),
            memory_size=512,
            environment={
                "ENV": self.env_name,
                "FARMER_PROFILES_TABLE": self.farmer_profiles_table.table_name,
                "CONVERSATIONS_TABLE": self.conversations_table.table_name,
                "RECOMMENDATIONS_TABLE": self.recommendations_table.table_name,
                "SENSOR_READINGS_TABLE": self.sensor_readings_table.table_name,
                "AGRICULTURAL_IMAGERY_BUCKET": self.agricultural_imagery_bucket.bucket_name,
                "WEATHER_DATA_BUCKET": self.weather_data_bucket.bucket_name,
                "MARKET_DATA_BUCKET": self.market_data_bucket.bucket_name,
                "MODEL_ARTIFACTS_BUCKET": self.model_artifacts_bucket.bucket_name,
                "USER_POOL_ID": self.user_pool.user_pool_id,
                "USER_POOL_CLIENT_ID": self.user_pool_client.user_pool_client_id,
                "REGION": self.region
            },
            log_retention=logs.RetentionDays.ONE_WEEK if self.env_name == "dev" else logs.RetentionDays.ONE_MONTH
        )
        
        # Auto-scaling configuration for production
        if self.env_name == "prod":
            alias = self.main_api_function.add_alias("live")
            
            scaling_target = autoscaling.ScalableTarget(
                self, "APIScalingTarget",
                service_namespace=autoscaling.ServiceNamespace.LAMBDA,
                resource_id=f"function:{self.main_api_function.function_name}:live",
                scalable_dimension="lambda:function:ProvisionedConcurrencyConfig:ProvisionedConcurrencyUtilization",
                min_capacity=5,
                max_capacity=100
            )
            
            scaling_target.scale_to_track_metric(
                "APITargetTracking",
                target_value=70.0,
                predefined_metric=autoscaling.PredefinedMetric.LAMBDA_PROVISIONED_CONCURRENCY_UTILIZATION
            )

    def _create_api_gateway(self):
        """Create API Gateway for REST API endpoints."""
        
        # Create API Gateway
        self.api = apigateway.RestApi(
            self, "KrishiMitraAPI",
            rest_api_name=f"krishimitra-api-{self.env_name}",
            description=f"KrishiMitra AI Agricultural Platform API - {self.env_name.upper()}",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key"]
            ),
            deploy_options=apigateway.StageOptions(
                stage_name=self.env_name,
                throttling_rate_limit=1000,
                throttling_burst_limit=2000,
                logging_level=apigateway.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                metrics_enabled=True
            )
        )
        
        # Create Cognito authorizer
        self.authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self, "KrishiMitraAuthorizer",
            cognito_user_pools=[self.user_pool],
            authorizer_name="KrishiMitraAuth"
        )
        
        # Lambda integration
        lambda_integration = apigateway.LambdaIntegration(
            self.main_api_function,
            proxy=True,
            integration_responses=[
                apigateway.IntegrationResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": "'*'"
                    }
                )
            ]
        )
        
        # API resources
        api_v1 = self.api.root.add_resource("api").add_resource("v1")
        
        # Health endpoint (no auth required)
        health = api_v1.add_resource("health")
        health.add_method("GET", lambda_integration)
        
        # Authenticated endpoints
        farmers = api_v1.add_resource("farmers")
        farmers.add_method("GET", lambda_integration, authorizer=self.authorizer)
        farmers.add_method("POST", lambda_integration, authorizer=self.authorizer)
        
        recommendations = api_v1.add_resource("recommendations")
        recommendations.add_method("GET", lambda_integration, authorizer=self.authorizer)
        recommendations.add_method("POST", lambda_integration, authorizer=self.authorizer)
        
        chat = api_v1.add_resource("chat")
        chat.add_method("POST", lambda_integration, authorizer=self.authorizer)
        
        voice = api_v1.add_resource("voice")
        voice.add_method("POST", lambda_integration, authorizer=self.authorizer)
        
        whatsapp = api_v1.add_resource("whatsapp")
        whatsapp.add_method("POST", lambda_integration)  # Webhook doesn't use Cognito auth

    def _create_iot_infrastructure(self):
        """Create AWS IoT Core infrastructure for sensor data collection."""
        
        # IoT Thing Type for agricultural sensors
        self.sensor_thing_type = iot.CfnThingType(
            self, "AgriculturalSensorType",
            thing_type_name=f"KrishiMitra-Sensor-{self.env_name}",
            thing_type_description="Agricultural sensors for KrishiMitra platform",
            thing_type_properties=iot.CfnThingType.ThingTypePropertiesProperty(
                thing_type_description="IoT sensors for soil, weather, and crop monitoring"
            )
        )
        
        # IoT Policy for sensor devices
        self.sensor_policy = iot.CfnPolicy(
            self, "SensorPolicy",
            policy_name=f"KrishiMitra-Sensor-Policy-{self.env_name}",
            policy_document={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "iot:Connect",
                            "iot:Publish",
                            "iot:Subscribe",
                            "iot:Receive"
                        ],
                        "Resource": [
                            f"arn:aws:iot:{self.region}:{self.account}:client/krishimitra-sensor-*",
                            f"arn:aws:iot:{self.region}:{self.account}:topic/krishimitra/sensors/*",
                            f"arn:aws:iot:{self.region}:{self.account}:topicfilter/krishimitra/sensors/*"
                        ]
                    }
                ]
            }
        )
        
        # IoT Rule for processing sensor data
        self.sensor_data_rule = iot.CfnTopicRule(
            self, "SensorDataRule",
            rule_name=f"KrishiMitra_Sensor_Data_Rule_{self.env_name}",
            topic_rule_payload=iot.CfnTopicRule.TopicRulePayloadProperty(
                sql=f"SELECT *, timestamp() as aws_timestamp FROM 'krishimitra/sensors/+/data'",
                description="Process incoming sensor data and store in DynamoDB",
                actions=[
                    iot.CfnTopicRule.ActionProperty(
                        dynamo_d_bv2=iot.CfnTopicRule.DynamoDBv2ActionProperty(
                            put_item=iot.CfnTopicRule.PutItemInputProperty(
                                table_name=self.sensor_readings_table.table_name
                            ),
                            role_arn=self._create_iot_rule_role().role_arn
                        )
                    )
                ]
            )
        )

    def _create_iot_rule_role(self):
        """Create IAM role for IoT rules to access DynamoDB."""
        
        iot_rule_role = iam.Role(
            self, "IoTRuleRole",
            role_name=f"KrishiMitra-IoT-Rule-Role-{self.env_name}",
            assumed_by=iam.ServicePrincipal("iot.amazonaws.com"),
            inline_policies={
                "DynamoDBAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "dynamodb:PutItem",
                                "dynamodb:UpdateItem"
                            ],
                            resources=[self.sensor_readings_table.table_arn]
                        )
                    ]
                )
            }
        )
        
        return iot_rule_role

    def _create_monitoring(self):
        """Create CloudWatch monitoring and alerting infrastructure."""
        
        # CloudWatch Log Groups
        self.api_log_group = logs.LogGroup(
            self, "APILogGroup",
            log_group_name=f"/aws/lambda/krishimitra-main-api-{self.env_name}",
            retention=logs.RetentionDays.ONE_WEEK if self.env_name == "dev" else logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # CloudWatch Dashboard
        self.dashboard = cloudwatch.Dashboard(
            self, "KrishiMitraDashboard",
            dashboard_name=f"KrishiMitra-{self.env_name}"
        )
        
        # API Gateway metrics
        api_requests_metric = cloudwatch.Metric(
            namespace="AWS/ApiGateway",
            metric_name="Count",
            dimensions_map={
                "ApiName": self.api.rest_api_name,
                "Stage": self.env_name
            },
            statistic="Sum"
        )
        
        api_latency_metric = cloudwatch.Metric(
            namespace="AWS/ApiGateway",
            metric_name="Latency",
            dimensions_map={
                "ApiName": self.api.rest_api_name,
                "Stage": self.env_name
            },
            statistic="Average"
        )
        
        api_errors_metric = cloudwatch.Metric(
            namespace="AWS/ApiGateway",
            metric_name="4XXError",
            dimensions_map={
                "ApiName": self.api.rest_api_name,
                "Stage": self.env_name
            },
            statistic="Sum"
        )
        
        # Lambda metrics
        lambda_duration_metric = cloudwatch.Metric(
            namespace="AWS/Lambda",
            metric_name="Duration",
            dimensions_map={
                "FunctionName": self.main_api_function.function_name
            },
            statistic="Average"
        )
        
        lambda_errors_metric = cloudwatch.Metric(
            namespace="AWS/Lambda",
            metric_name="Errors",
            dimensions_map={
                "FunctionName": self.main_api_function.function_name
            },
            statistic="Sum"
        )
        
        # Add widgets to dashboard
        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="API Requests",
                left=[api_requests_metric],
                width=12,
                height=6
            ),
            cloudwatch.GraphWidget(
                title="API Latency",
                left=[api_latency_metric],
                width=12,
                height=6
            ),
            cloudwatch.GraphWidget(
                title="API Errors",
                left=[api_errors_metric],
                width=12,
                height=6
            ),
            cloudwatch.GraphWidget(
                title="Lambda Performance",
                left=[lambda_duration_metric],
                right=[lambda_errors_metric],
                width=12,
                height=6
            )
        )
        
        # CloudWatch Alarms for production
        if self.env_name == "prod":
            cloudwatch.Alarm(
                self, "HighAPILatency",
                alarm_name=f"KrishiMitra-High-API-Latency-{self.env_name}",
                metric=api_latency_metric,
                threshold=3000,  # 3 seconds
                evaluation_periods=2,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
            )
            
            cloudwatch.Alarm(
                self, "HighErrorRate",
                alarm_name=f"KrishiMitra-High-Error-Rate-{self.env_name}",
                metric=api_errors_metric,
                threshold=10,
                evaluation_periods=2,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
            )

    def _setup_permissions(self):
        """Set up IAM permissions for Lambda functions and services."""
        
        # Grant Lambda function permissions to access DynamoDB tables
        self.farmer_profiles_table.grant_read_write_data(self.main_api_function)
        self.conversations_table.grant_read_write_data(self.main_api_function)
        self.recommendations_table.grant_read_write_data(self.main_api_function)
        self.sensor_readings_table.grant_read_data(self.main_api_function)
        
        # Grant Lambda function permissions to access S3 buckets
        self.agricultural_imagery_bucket.grant_read_write(self.main_api_function)
        self.weather_data_bucket.grant_read(self.main_api_function)
        self.market_data_bucket.grant_read(self.main_api_function)
        self.model_artifacts_bucket.grant_read(self.main_api_function)
        
        # Grant Lambda function permissions to access Bedrock
        self.main_api_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0",
                    f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
                ]
            )
        )
        
        # Grant Lambda function permissions to access other AWS services
        self.main_api_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "transcribe:StartTranscriptionJob",
                    "transcribe:GetTranscriptionJob",
                    "polly:SynthesizeSpeech",
                    "translate:TranslateText",
                    "comprehend:DetectDominantLanguage",
                    "rekognition:DetectLabels",
                    "rekognition:DetectText"
                ],
                resources=["*"]
            )
        )
        
        # Grant Lambda function permissions to publish CloudWatch metrics
        self.main_api_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudwatch:PutMetricData"
                ],
                resources=["*"]
            )
        )

    def _create_outputs(self):
        """Create CloudFormation outputs for important resources."""
        
        CfnOutput(
            self, "UserPoolId",
            value=self.user_pool.user_pool_id,
            description="Cognito User Pool ID",
            export_name=f"KrishiMitra-{self.env_name}-UserPoolId"
        )
        
        CfnOutput(
            self, "UserPoolClientId",
            value=self.user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID",
            export_name=f"KrishiMitra-{self.env_name}-UserPoolClientId"
        )
        
        CfnOutput(
            self, "ApiGatewayUrl",
            value=self.api.url,
            description="API Gateway URL",
            export_name=f"KrishiMitra-{self.env_name}-ApiUrl"
        )
        
        CfnOutput(
            self, "FarmerProfilesTableName",
            value=self.farmer_profiles_table.table_name,
            description="DynamoDB Farmer Profiles Table Name",
            export_name=f"KrishiMitra-{self.env_name}-FarmerProfilesTable"
        )
        
        CfnOutput(
            self, "ConversationsTableName",
            value=self.conversations_table.table_name,
            description="DynamoDB Conversations Table Name",
            export_name=f"KrishiMitra-{self.env_name}-ConversationsTable"
        )
        
        CfnOutput(
            self, "RecommendationsTableName",
            value=self.recommendations_table.table_name,
            description="DynamoDB Recommendations Table Name",
            export_name=f"KrishiMitra-{self.env_name}-RecommendationsTable"
        )
        
        CfnOutput(
            self, "SensorReadingsTableName",
            value=self.sensor_readings_table.table_name,
            description="DynamoDB Sensor Readings Table Name",
            export_name=f"KrishiMitra-{self.env_name}-SensorReadingsTable"
        )