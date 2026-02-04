# KrishiMitra Platform

KrishiMitra (कृषि मित्र - Agriculture Friend) is an AI-powered agricultural advisory platform designed to improve rural livelihoods, sustainability, and access to information for farmers in rural India.

## Architecture Overview

The platform follows a microservices architecture deployed on AWS using Python, featuring:

- **Multi-Agent AI System**: Five specialized AI agents built with LangChain and LangGraph for data ingestion, knowledge processing, advisory, sustainability, and feedback
- **FastAPI Backend**: High-performance REST APIs with automatic documentation
- **Multilingual Voice Interface**: Speech-to-text and text-to-speech in 7 Indian languages
- **Real-time Agricultural Intelligence**: IoT sensors, satellite imagery, weather data, and market prices
- **WhatsApp Integration**: Familiar interface for rural farmers
- **Low-bandwidth Optimization**: Designed for 2G/3G networks

## Technology Stack

### Backend Services
- **FastAPI**: Modern, fast web framework for building APIs
- **LangChain**: Framework for developing applications with LLMs
- **LangGraph**: Library for building stateful, multi-agent applications
- **Pydantic**: Data validation using Python type annotations
- **Celery**: Distributed task queue for background processing

### AI/ML Services
- **Amazon Bedrock**: Foundation models (Claude 3.5 Sonnet, Claude 3 Haiku)
- **Amazon SageMaker**: Custom ML model training and inference
- **Amazon Rekognition**: Crop image analysis
- **LangChain RAG**: Retrieval-augmented generation for agricultural knowledge

### Infrastructure
- **Amazon Cognito**: User authentication and authorization
- **Amazon DynamoDB**: NoSQL database for farmer profiles, conversations, recommendations
- **Amazon S3**: Object storage for images, weather data, market data, ML models
- **Amazon API Gateway**: RESTful API endpoints with throttling and monitoring
- **AWS Lambda**: Serverless compute for business logic
- **AWS IoT Core**: Device connectivity and message routing

### Communication Services
- **Amazon Polly**: Text-to-speech in Indian languages
- **Amazon Transcribe**: Speech-to-text conversion
- **Amazon Translate**: Multi-language support
- **WhatsApp Business API**: Chat interface integration

## Project Structure

```
├── src/krishimitra/           # Main application package
│   ├── main.py               # FastAPI application entry point
│   ├── core/                 # Core utilities and configuration
│   ├── api/v1/               # API version 1 endpoints
│   ├── agents/               # LangGraph AI agents (to be implemented)
│   ├── models/               # Pydantic data models
│   └── services/             # Business logic services
├── infrastructure/           # AWS CDK infrastructure code
│   ├── app.py               # CDK application entry point
│   ├── stacks/              # CDK stack definitions
│   └── constructs/          # Reusable CDK constructs
├── tests/                   # Test suite
│   ├── api/                 # API endpoint tests
│   ├── agents/              # AI agent tests
│   └── property/            # Property-based tests
├── scripts/                 # Deployment and utility scripts
└── docs/                    # Documentation
```

## Prerequisites

- Python 3.11 or later
- Poetry (recommended) or pip for dependency management
- AWS CLI configured with appropriate credentials
- AWS CDK CLI: `npm install -g aws-cdk`
- Node.js 18+ (for CDK)

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd krishimitra-platform

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt
```

### 2. Environment Configuration

Create a `.env` file in the project root:

```env
KRISHIMITRA_ENVIRONMENT=development
KRISHIMITRA_LOG_LEVEL=DEBUG
KRISHIMITRA_SECRET_KEY=your-secret-key-here
KRISHIMITRA_AWS_REGION=ap-south-1
KRISHIMITRA_REDIS_URL=redis://localhost:6379/0
```

### 3. Run the Application

```bash
# Start the FastAPI development server
uvicorn src.krishimitra.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 4. Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/krishimitra

# Run property-based tests
pytest -m property

# Run specific test file
pytest tests/test_main.py -v
```

## Deployment

### Using the Deployment Script

```bash
# Deploy to development
python scripts/deploy.py development --profile dev

# Deploy to staging
python scripts/deploy.py staging --profile staging

# Deploy to production (requires confirmation)
python scripts/deploy.py production --profile prod
```

### Manual Deployment

```bash
# Install dependencies
pip install -r requirements.txt
pip install -r infrastructure/requirements.txt

# Deploy infrastructure
cd infrastructure
cdk bootstrap --context environment=development
cdk deploy --context environment=development

# The application deployment will be automated in later tasks
```

## Environment Configurations

### Development
- Pay-per-request DynamoDB billing
- Basic encryption and security
- Minimal resource allocation
- Detailed logging enabled
- API documentation available

### Staging
- Point-in-time recovery enabled
- S3 versioning enabled
- Increased Lambda memory allocation
- Higher API throttling limits
- Production-like configuration

### Production
- Required MFA for Cognito
- Maximum resource allocation
- Strict security policies
- Error-level logging only
- Resource retention policies
- API documentation disabled

## API Endpoints

### Health and Monitoring
- `GET /health` - Basic health check
- `GET /api/v1/health/` - API health check
- `GET /api/v1/health/ready` - Readiness probe
- `GET /api/v1/health/live` - Liveness probe

### Authentication
- `POST /api/v1/auth/register` - Register new farmer
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/refresh` - Refresh token
- `GET /api/v1/auth/profile` - Get user profile

### Farmer Management
- `POST /api/v1/farmers/` - Create farmer profile
- `GET /api/v1/farmers/{farmer_id}` - Get farmer profile
- `PUT /api/v1/farmers/{farmer_id}` - Update farmer profile
- `GET /api/v1/farmers/{farmer_id}/crops` - Get farmer crops

### Chat and Voice
- `POST /api/v1/chat/` - Send text message
- `POST /api/v1/voice/transcribe` - Transcribe audio
- `POST /api/v1/voice/synthesize` - Text-to-speech
- `POST /api/v1/voice/conversation` - Complete voice interaction

### Recommendations
- `POST /api/v1/recommendations/` - Get recommendation
- `GET /api/v1/recommendations/{id}` - Get specific recommendation
- `POST /api/v1/recommendations/{id}/feedback` - Submit feedback

### WhatsApp Integration
- `GET /api/v1/whatsapp/webhook` - Webhook verification
- `POST /api/v1/whatsapp/webhook` - Process webhook events

## Multi-Agent AI System

The platform uses LangGraph to orchestrate five specialized AI agents:

### 1. Data Ingestion Agent
- Collects data from IoT sensors, weather APIs, satellite imagery
- Normalizes and validates incoming data streams
- Implements data quality checks and anomaly detection

### 2. Knowledge & Reasoning Agent
- Powered by LangChain integration with Amazon Bedrock
- Processes agricultural knowledge bases using RAG
- Generates evidence-based recommendations

### 3. Advisory Agent
- Delivers personalized recommendations using LangChain decision trees
- Integrates outputs from other agents
- Handles multilingual communication

### 4. Sustainability Agent
- Monitors environmental impact using specialized LangChain tools
- Provides climate-resilient farming recommendations
- Tracks carbon footprint and biodiversity metrics

### 5. Feedback Agent
- Captures farmer feedback using LangChain structured output parsers
- Implements continuous learning algorithms
- Updates recommendation models based on real-world results

## Testing Strategy

### Unit Tests
- FastAPI endpoint validation using pytest
- Pydantic model validation and serialization
- LangChain chain and tool functionality testing
- Integration points with external services

### Property-Based Tests
- Uses Hypothesis for generating test data
- Validates universal correctness properties
- Tests agricultural domain-specific logic
- Ensures robustness across input ranges

### Integration Tests
- End-to-end conversation flows
- Multi-agent coordination testing
- Cross-service communication validation
- Performance testing under load

## Development Guidelines

### Code Quality
- Use Black for code formatting
- Use isort for import sorting
- Use mypy for type checking
- Use flake8 for linting
- Pre-commit hooks for automated checks

### Testing
- Write tests for all new functionality
- Maintain high test coverage (>90%)
- Use property-based testing for complex logic
- Mock external services in tests

### Documentation
- Document all public APIs
- Use type hints throughout
- Write clear docstrings
- Update README for significant changes

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run the test suite
5. Submit a pull request

## Security

- All data is encrypted at rest and in transit
- Role-based access control (RBAC)
- API key management for external integrations
- Regular security audits and updates

## Monitoring and Observability

- Structured logging with JSON output
- CloudWatch integration for metrics and logs
- Custom metrics for farmer engagement
- Error tracking and alerting
- Performance monitoring

## Support

For technical support and questions:
- Check the API documentation at `/docs`
- Review CloudWatch logs for error details
- Consult AWS documentation for service-specific issues

## License

This project is licensed under the MIT License - see the LICENSE file for details.