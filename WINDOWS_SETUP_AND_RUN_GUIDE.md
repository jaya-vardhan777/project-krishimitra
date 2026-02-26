# KrishiMitra - Windows Setup and Run Guide

## Prerequisites

### 1. Python Environment
```powershell
# Check Python version (should be 3.9 or higher)
python --version

# If not installed, download from https://www.python.org/downloads/
```

### 2. Install Dependencies
```powershell
# Navigate to project directory
cd path\to\project-krishimitra

# Install all required packages
pip install -r requirements.txt

# Install development dependencies (for testing)
pip install -r requirements-dev.txt
```

### 3. AWS Configuration (Optional for Local Development)

For local development, the code uses mocked AWS services. For production:

```powershell
# Install AWS CLI
# Download from: https://aws.amazon.com/cli/

# Configure AWS credentials
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Enter default region: ap-south-1
# Enter default output format: json
```

## Environment Configuration

### 1. Create Environment File

Create a `.env` file in the project root:

```powershell
# Copy the example environment file
copy .env.example .env
```

### 2. Edit `.env` File

Open `.env` in your text editor and configure:

```env
# Application Settings
ENV=development
DEBUG=True

# AWS Configuration
AWS_REGION=ap-south-1

# Database Tables (DynamoDB)
FARMER_PROFILES_TABLE=dev-farmer-profiles
CONVERSATIONS_TABLE=dev-conversations
RECOMMENDATIONS_TABLE=dev-recommendations
SENSOR_READINGS_TABLE=dev-sensor-readings

# S3 Buckets
AGRICULTURAL_IMAGERY_BUCKET=dev-agricultural-imagery
WEATHER_DATA_BUCKET=dev-weather-data
MARKET_DATA_BUCKET=dev-market-data
MODEL_ARTIFACTS_BUCKET=dev-model-artifacts

# Bedrock Configuration
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20240620-v1:0
BEDROCK_REGION=us-east-1

# Audio Processing
AUDIO_BUCKET_NAME=dev-audio-files
MAX_AUDIO_DURATION_SECONDS=300
MIN_AUDIO_DURATION_SECONDS=0.5
MAX_AUDIO_SIZE_MB=50.0

# Security
JWT_SECRET_KEY=your-secret-key-change-in-production
KRISHIMITRA_ENCRYPTION_PASSWORD=your-encryption-password
KRISHIMITRA_ENCRYPTION_SALT=your-encryption-salt

# Logging
LOG_LEVEL=INFO

# Optional: External API Keys (for production)
# WHATSAPP_VERIFY_TOKEN=your-whatsapp-verify-token
# WHATSAPP_ACCESS_TOKEN=your-whatsapp-access-token
# WHATSAPP_PHONE_NUMBER_ID=your-phone-number-id
# WEATHER_API_KEY=your-weather-api-key
# MARKET_API_KEY=your-market-api-key
```

## Running the Application

### Option 1: Run Locally with Uvicorn (Recommended for Development)

```powershell
# Method 1: Using Python module
python -m uvicorn src.krishimitra.main:app --reload --host 0.0.0.0 --port 8000

# Method 2: Using the main.py directly
python src/krishimitra/main.py
```

**Access the application:**
- API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Alternative Docs: http://localhost:8000/redoc

### Option 2: Run with Gunicorn (Production-like)

```powershell
# Install gunicorn (if not already installed)
pip install gunicorn

# Run with gunicorn
gunicorn src.krishimitra.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Option 3: Run in Docker (Recommended for Production Testing)

```powershell
# Build Docker image
docker build -t krishimitra:latest .

# Run container
docker run -p 8000:8000 --env-file .env krishimitra:latest
```

## Testing the Application

### 1. Run All Tests

```powershell
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run with coverage report
python -m pytest --cov=src/krishimitra --cov-report=html
```

### 2. Run Specific Test Suites

```powershell
# Run integration tests only
python -m pytest tests/integration/ -v

# Run end-to-end workflow tests
python -m pytest tests/integration/test_end_to_end_workflows.py -v

# Run specific test class
python -m pytest tests/integration/test_end_to_end_workflows.py::TestCompleteUserJourneys -v

# Run specific test
python -m pytest tests/integration/test_end_to_end_workflows.py::TestCompleteUserJourneys::test_farmer_registration_to_first_recommendation -v
```

### 3. Run Property-Based Tests

```powershell
# Run property tests
python -m pytest tests/property/ -v

# Run with more examples (slower but more thorough)
python -m pytest tests/property/ -v --hypothesis-profile=ci
```

### 4. Check Code Quality

```powershell
# Run linting
flake8 src/krishimitra

# Run type checking
mypy src/krishimitra

# Format code
black src/krishimitra tests
```

## Accessing the API

### 1. Health Check

```powershell
# Using curl (if installed)
curl http://localhost:8000/api/v1/health

# Using PowerShell
Invoke-WebRequest -Uri http://localhost:8000/api/v1/health -Method GET
```

### 2. Interactive API Documentation

Open your browser and navigate to:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

You can test all API endpoints directly from the Swagger UI.

### 3. Example API Calls

```powershell
# Get API information
Invoke-WebRequest -Uri http://localhost:8000/ -Method GET

# Register a farmer (example)
$body = @{
    name = "राम कुमार"
    phone_number = "+919876543210"
    preferred_language = "hi-IN"
    location = @{
        state = "उत्तर प्रदेश"
        district = "मेरठ"
        village = "सरधना"
    }
} | ConvertTo-Json

Invoke-WebRequest -Uri http://localhost:8000/api/v1/farmers/register -Method POST -Body $body -ContentType "application/json"
```

## Troubleshooting

### Issue 1: Port Already in Use

```powershell
# Find process using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID with actual process ID)
taskkill /PID <PID> /F

# Or use a different port
python -m uvicorn src.krishimitra.main:app --reload --port 8001
```

### Issue 2: Module Not Found Errors

```powershell
# Ensure you're in the project root directory
cd path\to\project-krishimitra

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Add project to PYTHONPATH
$env:PYTHONPATH = "$PWD;$env:PYTHONPATH"
```

### Issue 3: AWS Service Errors (Local Development)

The application uses mocked AWS services for local development. If you see AWS errors:

```powershell
# Set environment to development
$env:ENV = "development"

# Or ensure .env file has ENV=development
```

### Issue 4: Database Connection Errors

For local development without AWS:

```powershell
# Install and run LocalStack (local AWS emulator)
pip install localstack
localstack start

# Or use mocked services (default in tests)
```

### Issue 5: Pydantic Warnings

The application has some Pydantic V1 to V2 migration warnings. These don't affect functionality but can be fixed:

```powershell
# These are deprecation warnings, not errors
# The application will still run correctly
# To suppress warnings during development:
$env:PYTHONWARNINGS = "ignore::DeprecationWarning"
```

## Development Workflow

### 1. Start Development Server

```powershell
# Terminal 1: Start the API server
python -m uvicorn src.krishimitra.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Run Tests in Watch Mode

```powershell
# Terminal 2: Run tests automatically on file changes
python -m pytest-watch
```

### 3. Monitor Logs

```powershell
# Logs are written to console by default
# For file logging, check the logs directory (if configured)
```

## Production Deployment

### 1. AWS Lambda Deployment

```powershell
# Install AWS CDK
npm install -g aws-cdk

# Navigate to infrastructure directory
cd infrastructure

# Install Python dependencies
pip install -r requirements.txt

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy to AWS
cdk deploy --all

# Or use the deployment script
python ..\scripts\deploy.py
```

### 2. Environment-Specific Deployment

```powershell
# Deploy to development
$env:ENV = "development"
cdk deploy --all

# Deploy to staging
$env:ENV = "staging"
cdk deploy --all

# Deploy to production
$env:ENV = "production"
cdk deploy --all
```

## Monitoring and Debugging

### 1. View Application Logs

```powershell
# Logs are printed to console
# For production, check CloudWatch Logs in AWS Console
```

### 2. Debug Mode

```powershell
# Enable debug mode in .env
# DEBUG=True

# Or set environment variable
$env:DEBUG = "True"

# Run with debug logging
python -m uvicorn src.krishimitra.main:app --reload --log-level debug
```

### 3. Performance Profiling

```powershell
# Install profiling tools
pip install py-spy

# Profile the running application
py-spy top --pid <process_id>

# Generate flame graph
py-spy record -o profile.svg -- python src/krishimitra/main.py
```

## Quick Start Commands

```powershell
# Complete setup and run (copy-paste friendly)

# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env file (edit with your values)
copy .env.example .env

# 3. Run the application
python -m uvicorn src.krishimitra.main:app --reload

# 4. Open browser to http://localhost:8000/docs

# 5. Run tests (in another terminal)
python -m pytest -v
```

## Useful Commands Reference

```powershell
# Start server
python -m uvicorn src.krishimitra.main:app --reload

# Run all tests
python -m pytest -v

# Run integration tests
python -m pytest tests/integration/ -v

# Check code coverage
python -m pytest --cov=src/krishimitra --cov-report=html

# Format code
black src/krishimitra tests

# Lint code
flake8 src/krishimitra

# Type check
mypy src/krishimitra

# View API docs
start http://localhost:8000/docs

# Deploy to AWS
cd infrastructure && cdk deploy --all
```

## Using the Web UI

A modern web interface is available to interact with the API:

### Starting the Web UI

```powershell
# Terminal 1: Start the API server
python -m uvicorn src.krishimitra.main:app --reload

# Terminal 2: Start the web UI
cd ui
python -m http.server 8080

# Open your browser to:
# http://localhost:8080
```

### Web UI Features

- 🌾 Farmer Registration
- 💡 Get AI Recommendations
- 🎤 Voice Queries (7 Indian languages)
- 💬 WhatsApp Integration
- 📡 IoT Sensor Data
- 💰 Market Prices
- 🏛️ Government Schemes

See `ui/README.md` for detailed usage instructions.

## Next Steps

1. **Start the server**: `python -m uvicorn src.krishimitra.main:app --reload`
2. **Open Web UI**: http://localhost:8080 (after starting the UI server)
3. **Or use API docs**: http://localhost:8000/docs
4. **Run tests**: `python -m pytest -v`
5. **Review integration status**: Check `INTEGRATION_STATUS.md`
6. **Complete missing endpoints**: See test failures for what needs implementation

## Support and Resources

- **API Documentation**: http://localhost:8000/docs (when running)
- **Integration Status**: See `INTEGRATION_STATUS.md`
- **Architecture**: See `.kiro/specs/krishimitra/design.md`
- **Tasks**: See `.kiro/specs/krishimitra/tasks.md`

---

**Last Updated**: 2026-02-08
**Platform**: Windows
**Python Version**: 3.9+
