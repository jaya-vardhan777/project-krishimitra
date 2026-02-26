# Getting Started with KrishiMitra

Welcome to KrishiMitra - an AI-powered agricultural advisory platform for rural farmers in India! 🌾

## 🚀 Quick Start (3 Steps)

### Step 1: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 2: Start the Platform
```powershell
# Option A: One-click start (easiest)
start-krishimitra.bat

# Option B: Manual start
# Terminal 1:
python -m uvicorn src.krishimitra.main:app --reload

# Terminal 2:
cd ui
python -m http.server 8080
```

### Step 3: Open Your Browser
```
http://localhost:8080
```

That's it! You're ready to use KrishiMitra! 🎉

## 📖 What You Can Do

### For Farmers
- 👨‍🌾 **Register** your profile with multilingual support
- 💡 **Get AI recommendations** for your crops
- 🎤 **Ask questions** using voice in 7 Indian languages
- 💬 **Receive updates** via WhatsApp
- 💰 **Check market prices** for your crops
- 🏛️ **Find government schemes** you're eligible for

### For Developers
- 🔌 **REST API** with comprehensive documentation
- 🧪 **Test suite** with integration tests
- 📊 **Monitoring** and analytics
- 🌐 **Web UI** for easy interaction
- 📱 **WhatsApp integration** for farmer outreach
- 📡 **IoT support** for sensor data

## 🌍 Supported Languages

- Hindi (हिंदी)
- Tamil (தமிழ்)
- Telugu (తెలుగు)
- Bengali (বাংলা)
- Marathi (मराठी)
- Gujarati (ગુજરાતી)
- Punjabi (ਪੰਜਾਬੀ)

## 📚 Documentation

### For Users
- **[UI Quick Start Guide](UI_QUICK_START.md)** - How to use the web interface
- **[Windows Setup Guide](WINDOWS_SETUP_AND_RUN_GUIDE.md)** - Complete setup instructions

### For Developers
- **[API Documentation](http://localhost:8000/docs)** - Interactive API docs (when server is running)
- **[Integration Status](INTEGRATION_STATUS.md)** - Current implementation status
- **[Design Document](.kiro/specs/krishimitra/design.md)** - System architecture
- **[Task List](.kiro/specs/krishimitra/tasks.md)** - Implementation tasks

## 🎯 Common Use Cases

### 1. Register a Farmer
```
1. Open http://localhost:8080
2. Click "Farmer Registration"
3. Fill in details
4. Save the Farmer ID
```

### 2. Get Crop Advice
```
1. Click "Get Recommendations"
2. Enter Farmer ID
3. Type your question (any language)
4. Get AI-powered advice
```

### 3. Voice Query
```
1. Click "Voice Query"
2. Select language
3. Record or upload audio
4. Get spoken response
```

### 4. Check Market Prices
```
1. Click "Market Prices"
2. Enter crop name
3. Enter location
4. View current prices
```

## 🔧 System Requirements

- **Python**: 3.9 or higher
- **OS**: Windows 10/11
- **Browser**: Chrome, Firefox, Edge, or Safari
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 2GB free space

## 📦 Project Structure

```
project-krishimitra/
├── src/                    # Source code
│   └── krishimitra/       # Main application
├── ui/                    # Web interface
│   ├── index.html        # UI home page
│   ├── styles.css        # Styling
│   └── app.js            # JavaScript
├── tests/                # Test suite
├── infrastructure/       # AWS deployment
├── start-krishimitra.bat # Quick start script
└── README.md            # Main documentation
```

## 🎨 Web UI Features

### Dashboard
- Real-time API status
- System statistics
- Feature overview

### Farmer Management
- Registration
- Profile updates
- Consent management

### AI Services
- Recommendations
- Voice queries
- Chat interface

### Data Services
- IoT sensor data
- Market prices
- Weather information

### Integration
- WhatsApp messaging
- Government schemes
- NGO services

## 🧪 Testing

### Run All Tests
```powershell
python -m pytest -v
```

### Run Integration Tests
```powershell
python -m pytest tests/integration/ -v
```

### Check Code Coverage
```powershell
python -m pytest --cov=src/krishimitra --cov-report=html
```

## 🌐 Access Points

When running locally:

| Service | URL | Description |
|---------|-----|-------------|
| Web UI | http://localhost:8080 | User interface |
| API Docs | http://localhost:8000/docs | Interactive API documentation |
| API Health | http://localhost:8000/api/v1/health | Health check endpoint |
| ReDoc | http://localhost:8000/redoc | Alternative API docs |

## 🔍 Troubleshooting

### API Won't Start
```powershell
# Check if port 8000 is in use
netstat -ano | findstr :8000

# Kill the process if needed
taskkill /PID <PID> /F

# Or use a different port
python -m uvicorn src.krishimitra.main:app --reload --port 8001
```

### UI Won't Load
```powershell
# Make sure you're in the ui directory
cd ui

# Start the server
python -m http.server 8080

# Open browser to http://localhost:8080
```

### Module Not Found
```powershell
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Add to PYTHONPATH
$env:PYTHONPATH = "$PWD;$env:PYTHONPATH"
```

### API Connection Failed
1. Ensure API server is running
2. Check firewall settings
3. Verify URL in `ui/app.js`
4. Check browser console for errors

## 📊 Sample Workflow

### Complete Farmer Journey

1. **Register Farmer**
   - Name: राम कुमार
   - Phone: +919876543210
   - Language: Hindi
   - Location: Meerut, UP

2. **Submit IoT Data**
   - Temperature: 28.5°C
   - Humidity: 65%
   - Soil Moisture: 45%

3. **Get Recommendation**
   - Query: "मेरी गेहूं की फसल में पीले पत्ते हैं"
   - Receive AI-powered advice

4. **Check Market Prices**
   - Crop: Wheat
   - Location: Meerut
   - View current rates

5. **Find Government Schemes**
   - Check eligibility
   - Get application guidance

## 🚀 Production Deployment

### Deploy to AWS
```powershell
cd infrastructure
pip install -r requirements.txt
cdk bootstrap
cdk deploy --all
```

### Environment Configuration
```powershell
# Development
$env:ENV = "development"

# Staging
$env:ENV = "staging"

# Production
$env:ENV = "production"
```

## 🤝 Contributing

1. Review the design document
2. Check the task list
3. Run tests before committing
4. Follow coding standards
5. Update documentation

## 📞 Support

### Documentation
- [UI Quick Start](UI_QUICK_START.md)
- [Windows Setup](WINDOWS_SETUP_AND_RUN_GUIDE.md)
- [Integration Status](INTEGRATION_STATUS.md)

### API Reference
- Interactive Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Testing
- Run tests: `python -m pytest -v`
- Check coverage: `python -m pytest --cov`

## 🎓 Learning Resources

### For Farmers
- Use the web UI for easy interaction
- Try voice queries in your language
- Check WhatsApp for updates
- Explore government schemes

### For Developers
- Review API documentation
- Study the design document
- Run integration tests
- Explore the codebase

## 🌟 Key Features

✅ **Multi-Agent AI System**
- Data Ingestion Agent
- Knowledge & Reasoning Agent
- Advisory Agent
- Sustainability Agent
- Feedback Agent

✅ **Multilingual Support**
- 7 Indian languages
- Voice input/output
- Text translation

✅ **Multiple Interfaces**
- Web UI
- REST API
- WhatsApp
- Voice

✅ **Real-time Data**
- IoT sensors
- Weather updates
- Market prices
- Satellite imagery

✅ **Smart Recommendations**
- Personalized advice
- Crop-specific tips
- Resource optimization
- Sustainable practices

## 📈 Next Steps

1. ✅ **Get Started** - Follow the quick start guide
2. 📱 **Try the UI** - Explore all features
3. 🧪 **Run Tests** - Verify everything works
4. 📖 **Read Docs** - Learn more about the system
5. 🚀 **Deploy** - Take it to production

## 🎉 You're Ready!

Start the platform and begin helping farmers with AI-powered agricultural advice!

```powershell
# Start everything
start-krishimitra.bat

# Open browser
start http://localhost:8080
```

---

**KrishiMitra** - Empowering Rural Farmers with AI 🌾

*Supporting 7 Indian Languages | Serving Farmers Across India*

**Last Updated**: 2026-02-09
**Version**: 1.0.0
