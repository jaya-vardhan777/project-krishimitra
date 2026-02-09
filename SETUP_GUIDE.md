# KrishiMitra Platform - Setup and Deployment Guide

This guide provides comprehensive instructions for setting up, testing, and deploying the KrishiMitra AI-powered agricultural platform.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Setup](#initial-setup)
3. [Development Environment](#development-environment)
4. [Testing](#testing)
5. [Infrastructure Deployment](#infrastructure-deployment)
6. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software

- **Python 3.11 or later**: [Download Python](https://www.python.org/downloads/)
- **Node.js 18+ and npm**: [Download Node.js](https://nodejs.org/)
- **AWS CLI**: [Install AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- **AWS CDK CLI**: Install via npm
  ```bash
  npm install -g aws-cdk
  ```
- **Git**: [Download Git](https://git-scm.com/downloads)

### AWS Account Requirements

- Active AWS account with appropriate permissions
- AWS credentials configured locally
- Access to the following AWS services:
  - Lambda, API Gateway, DynamoDB, S3
  - Cognito, Bedrock, IoT Core
  - Transcribe, Polly, Translate
  - CloudWatch, X-Ray

## Initial Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd krishimitra-platform
```

### 2. Create Python Virtual Environment

**On Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

**Install production dependencies:**
```bash
pip install -r requirements.txt
```

**Install development dependencies (includes testing tools):**
```bash
pip install -r requirements-dev.txt
```

**Install infrastructure dependencies:**
```bash
pip install -r infrastructure/requirements.txt
```

### 4. Configure Environment Variables

Copy the example environment file and update with your values:

```bash
cp .env.example .env
```

Edit `.env` and configure:
- AWS credentials and region
- Bedrock model configuration
- WhatsApp API credentials (if using WhatsApp integration)
- External API keys (weather, market data)

**Minimum required configuration:**
```env
ENV=development
AWS_REGION=ap-south-1
BEDROCK_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
```

### 5. Configure AWS Credentials

**Option 1: AWS CLI Configuration**
```bash
aws configure
```

**Option 2: Environment Variables**
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=ap-south-1
```

**Option 3: AWS Profiles**
```bash
aws configure --profile krishimitra-dev
export AWS_PROFILE=krishimitra-dev
```

## Development Environment

### Running the Application Locally

**Start the FastAPI development server:**
```bash
uvicorn src.krishimitra.main:app --reload --host 0.0.0.0 --port 8000
```

**Access the application:**
- API: http://localhost:8000
- Interactive API Documentation: http://localhost:8000/docs
- ReDoc Documentation: http://localhost:8000/redoc

### Project Structure

```
krishimitra-platform/
├── src/krishimitra/          # Main application code
│   ├── main.py              # FastAPI application entry point
│   ├── core/                # Core utilities and configuration
│   ├── api/v1/              # API endpoints
│   ├── agents/              # AI agents (LangChain/LangGraph)
│   ├── models/              # Pydantic data models
│   └── iot/                 # IoT device management
├── infrastructure/          # AWS CDK infrastructure code
│   ├── app.py              # CDK app entry point
│   └── stacks/             # CDK stack definitions
├── tests/                  # Test suite
│   ├── conftest.py         # Pytest configuration
│   ├── utils/              # Test utilities
│   └── property/           # Property-based tests
├── scripts/                # Deployment and utility scripts
├── requirements.txt        # Production dependencies
├── requirements-dev.txt    # Development dependencies
└── pyproject.toml         # Poetry configuration
```

## Testing

### Running Tests

**Run all tests:**
```bash
pytest
```

**Run with coverage:**
```bash
pytest --cov=src/krishimitra --cov-report=html
```

**Run specific test categories:**
```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Property-based tests only
pytest -m property

# Specific test file
pytest tests/test_main.py -v
```

### Testing with AWS Service Mocking

The project uses `moto` for mocking AWS services in tests. Ensure `moto` is installed:

```bash
pip install moto[dynamodb,s3,iot]
```

**Example test with mocked AWS services:**
```python
from tests.utils.aws_mocks import MockAWSEnvironment

def test_with_aws_mocks():
    with MockAWSEnvironment() as env:
        # Your test code here
        # DynamoDB and S3 are mocked and available
        pass
```

### Property-Based Testing

The project uses Hypothesis for property-based testing:

```bash
# Run property tests with default settings
pytest -m property

# Run with more examples for thorough testing
pytest -m property --hypothesis-profile=ci

# Run with verbose output for debugging
pytest -m property --hypothesis-profile=debug
```

## Infrastructure Deployment

### Prerequisites for Deployment

1. **AWS Account ID**: Get your AWS account ID
   ```bash
   aws sts get-caller-identity --query Account --output text
   ```

2. **Verify AWS Permissions**: Ensure you have permissions to create:
   - Lambda functions, API Gateway, DynamoDB tables
   - S3 buckets, Cognito user pools, IoT resources
   - IAM roles and policies

### Deployment Steps

#### 1. Bootstrap AWS CDK (First Time Only)

Bootstrap CDK in your AWS account and region:

```bash
cd infrastructure
cdk bootstrap aws://ACCOUNT-ID/REGION --context env=dev
```

Example:
```bash
cdk bootstrap aws://123456789012/ap-south-1 --context env=dev
```

#### 2. Synthesize CloudFormation Template

Preview the CloudFormation template that will be generated:

```bash
cdk synth --context env=dev
```

#### 3. Deploy Infrastructure

**Deploy to development environment:**
```bash
cdk deploy --context env=dev --require-approval never
```

**Deploy to staging environment:**
```bash
cdk deploy --context env=staging --require-approval never
```

**Deploy to production environment:**
```bash
cdk deploy --context env=prod
```

#### 4. Using the Deployment Script

Alternatively, use the provided deployment script:

```bash
python scripts/deploy.py dev --account YOUR_ACCOUNT_ID --region ap-south-1
```

**Script options:**
- `--skip-deps`: Skip dependency installation
- `--skip-bootstrap`: Skip CDK bootstrap step
- `--region`: AWS region (default: ap-south-1)

### Post-Deployment

After successful deployment, CDK will output important resource identifiers:

```
Outputs:
KrishiMitra-dev.UserPoolId = ap-south-1_XXXXXXXXX
KrishiMitra-dev.UserPoolClientId = XXXXXXXXXXXXXXXXXXXXXXXXXX
KrishiMitra-dev.ApiGatewayUrl = https://XXXXXXXXXX.execute-api.ap-south-1.amazonaws.com/dev/
```

**Update your `.env` file with these values:**
```env
USER_POOL_ID=ap-south-1_XXXXXXXXX
USER_POOL_CLIENT_ID=XXXXXXXXXXXXXXXXXXXXXXXXXX
API_GATEWAY_URL=https://XXXXXXXXXX.execute-api.ap-south-1.amazonaws.com/dev/
```

### Verifying Deployment

**Test the deployed API:**
```bash
curl https://YOUR_API_GATEWAY_URL/api/v1/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "environment": "dev",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Infrastructure Components

### AWS Services Configured

1. **API Gateway**: RESTful API endpoints with CORS and throttling
2. **Lambda Functions**: Python 3.11 runtime with FastAPI via Mangum
3. **DynamoDB Tables**:
   - FarmerProfiles: Farmer information and preferences
   - Conversations: Chat history and context
   - Recommendations: Advisory records and feedback
   - SensorReadings: Real-time IoT sensor data
4. **S3 Buckets**:
   - Agricultural imagery storage
   - Weather data storage
   - Market data storage
   - ML model artifacts
5. **Cognito**: User authentication and authorization
6. **IoT Core**: Device connectivity and message routing
7. **CloudWatch**: Logging and monitoring
8. **X-Ray**: Distributed tracing for performance analysis

### Auto-Scaling Configuration

**Development Environment:**
- Pay-per-request DynamoDB billing
- Basic Lambda concurrency

**Production Environment:**
- Provisioned concurrency for Lambda (5-100 instances)
- Auto-scaling based on 70% utilization
- Enhanced monitoring and alerting

## Monitoring and Observability

### CloudWatch Dashboard

Access the CloudWatch dashboard:
1. Go to AWS Console → CloudWatch → Dashboards
2. Select `KrishiMitra-{environment}` dashboard

**Metrics available:**
- API request count and latency
- Lambda function duration and errors
- DynamoDB read/write capacity
- Error rates and 4XX/5XX responses

### CloudWatch Logs

View application logs:
```bash
aws logs tail /aws/lambda/krishimitra-main-api-dev --follow
```

### X-Ray Tracing

View distributed traces:
1. Go to AWS Console → X-Ray → Traces
2. Filter by service name: `krishimitra-main-api-{environment}`

## Troubleshooting

### Common Issues

#### 1. CDK Bootstrap Fails

**Error:** "Unable to resolve AWS account to use"

**Solution:**
```bash
# Verify AWS credentials
aws sts get-caller-identity

# Configure AWS CLI if needed
aws configure
```

#### 2. Lambda Deployment Package Too Large

**Error:** "Unzipped size must be smaller than 262144000 bytes"

**Solution:**
- Use Lambda layers for large dependencies
- Exclude unnecessary files from deployment package
- Consider using Docker-based Lambda functions

#### 3. Bedrock Access Denied

**Error:** "User is not authorized to perform: bedrock:InvokeModel"

**Solution:**
1. Request Bedrock model access in AWS Console
2. Ensure IAM role has Bedrock permissions
3. Verify model ID is correct in configuration

#### 4. DynamoDB Table Already Exists

**Error:** "Table already exists"

**Solution:**
```bash
# Delete existing stack
cdk destroy --context env=dev

# Redeploy
cdk deploy --context env=dev
```

#### 5. Import Errors in Tests

**Error:** "ModuleNotFoundError: No module named 'moto'"

**Solution:**
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Or install moto specifically
pip install moto[dynamodb,s3,iot]
```

### Getting Help

- Check CloudWatch Logs for detailed error messages
- Review AWS X-Ray traces for performance issues
- Consult the API documentation at `/docs` endpoint
- Check AWS service quotas and limits

## Security Best Practices

1. **Never commit `.env` files** to version control
2. **Use AWS Secrets Manager** for sensitive credentials in production
3. **Enable MFA** for AWS console access
4. **Rotate credentials** regularly
5. **Use least-privilege IAM policies**
6. **Enable CloudTrail** for audit logging
7. **Encrypt data at rest and in transit**

## Next Steps

After successful setup and deployment:

1. **Configure WhatsApp Integration**: Set up WhatsApp Business API
2. **Set up IoT Devices**: Register and configure agricultural sensors
3. **Load Agricultural Knowledge Base**: Import crop and farming data
4. **Configure External APIs**: Set up weather and market data integrations
5. **Test End-to-End Workflows**: Verify complete farmer interaction flows

## Additional Resources

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LangChain Documentation](https://python.langchain.com/)
- [Hypothesis Testing Documentation](https://hypothesis.readthedocs.io/)
- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)

## Support

For technical support:
- Review the README.md for project overview
- Check the design.md in `.kiro/specs/krishimitra/` for architecture details
- Consult AWS documentation for service-specific issues
