# KrishiMitra UI Quick Start Guide

## 🚀 Fastest Way to Get Started

### Option 1: One-Click Start (Recommended)

**Using Batch File:**
```powershell
# Double-click this file or run:
start-krishimitra.bat
```

**Using PowerShell Script:**
```powershell
# Right-click and "Run with PowerShell" or run:
.\start-krishimitra.ps1
```

This will:
1. ✅ Start the API server on http://localhost:8000
2. ✅ Start the Web UI on http://localhost:8080
3. ✅ Open your browser automatically

### Option 2: Manual Start

**Terminal 1 - API Server:**
```powershell
python -m uvicorn src.krishimitra.main:app --reload
```

**Terminal 2 - Web UI:**
```powershell
cd ui
python -m http.server 8080
```

**Browser:**
Open http://localhost:8080

## 📱 Using the Web Interface

### 1. Dashboard
- View API status
- See system statistics
- Quick overview of features

### 2. Farmer Registration
**Steps:**
1. Click "👨‍🌾 Farmer Registration" in the sidebar
2. Fill in the form:
   - Name: राम कुमार
   - Phone: +919876543210
   - Language: Hindi (हिंदी)
   - Location: State, District, Village
3. Click "Register Farmer"
4. **Save the Farmer ID** from the response!

**Example Response:**
```json
{
  "farmer_id": "farmer-abc123",
  "name": "राम कुमार",
  "status": "registered"
}
```

### 3. Get Recommendations
**Steps:**
1. Click "💡 Get Recommendations"
2. Enter the Farmer ID (from registration)
3. Type your query in any language:
   - Hindi: "मेरी गेहूं की फसल में पीले पत्ते दिख रहे हैं। क्या करूं?"
   - English: "My wheat crop has yellow leaves. What should I do?"
4. Select language
5. Click "Get Recommendation"

**What You'll Get:**
- Personalized agricultural advice
- Crop-specific recommendations
- Sustainable farming practices
- Resource optimization tips

### 4. Voice Query
**Steps:**
1. Click "🎤 Voice Query"
2. Select your language
3. **Option A - Record:**
   - Click "Start Recording"
   - Speak your question
   - Click "Stop Recording"
4. **Option B - Upload:**
   - Click "Choose File"
   - Select audio file
   - Click "Upload & Process"

**Supported Languages:**
- Hindi (हिंदी)
- Tamil (தமிழ்)
- Telugu (తెలుగు)
- Bengali (বাংলা)
- Marathi (मराठी)
- Gujarati (ગુજરાતી)
- Punjabi (ਪੰਜਾਬੀ)

### 5. WhatsApp Integration
**Steps:**
1. Click "💬 WhatsApp Integration"
2. Enter phone number with country code: +919876543210
3. Type your message
4. Click "Send WhatsApp Message"

**Use Cases:**
- Send farming tips to farmers
- Broadcast weather alerts
- Share market price updates
- Provide scheme notifications

### 6. IoT Sensor Data
**Steps:**
1. Click "📡 IoT Sensor Data"
2. Fill in sensor readings:
   - Device ID: sensor-001
   - Farmer ID: farmer-abc123
   - Temperature: 28.5°C
   - Humidity: 65%
   - Soil Moisture: 45%
   - Soil pH: 6.5
3. Click "Submit Sensor Data"

**What Happens:**
- Data is stored in the system
- Triggers automated recommendations
- Alerts for abnormal conditions
- Historical trend analysis

### 7. Market Prices
**Steps:**
1. Click "💰 Market Prices"
2. Enter crop name: "Wheat" or "गेहूं"
3. Enter location: "Meerut, Uttar Pradesh"
4. Click "Get Market Prices"

**Information Provided:**
- Current market prices
- Price trends
- Nearby markets
- Best selling locations
- Transportation costs

### 8. Government Schemes
**Steps:**
1. Click "🏛️ Government Schemes"
2. Enter Farmer ID
3. Click "Check Eligible Schemes"

**What You'll See:**
- Eligible government schemes
- Application requirements
- Deadline information
- Application guidance
- Document checklist

## 🎨 UI Features

### Real-time API Status
- Green dot (●) = API Online
- Red dot (●) = API Offline
- Auto-checks every 30 seconds

### Responsive Design
- Works on desktop, tablet, and mobile
- Adapts to screen size
- Touch-friendly interface

### Form Validation
- Required fields marked with *
- Input format validation
- Clear error messages

### Result Display
- Success messages in green
- Error messages in red
- JSON response viewer
- Copy-paste friendly

## 🔧 Troubleshooting

### Problem: "API Offline" Status

**Solution:**
```powershell
# Check if API server is running
# Start it with:
python -m uvicorn src.krishimitra.main:app --reload
```

### Problem: UI Not Loading

**Solution:**
```powershell
# Make sure you're running through a server:
cd ui
python -m http.server 8080

# Then open: http://localhost:8080
```

### Problem: Voice Recording Not Working

**Solutions:**
1. Grant microphone permissions in browser
2. Use HTTPS or localhost
3. Try uploading an audio file instead
4. Check browser console for errors

### Problem: Form Submission Fails

**Check:**
1. All required fields are filled
2. API server is running
3. Correct data format (phone numbers, etc.)
4. Browser console for error messages

### Problem: CORS Errors

**Solution:**
The API includes CORS middleware. If you still see errors:
1. Ensure API is running on localhost:8000
2. Check browser console for specific error
3. Verify API configuration in `src/krishimitra/main.py`

## 📊 Sample Data for Testing

### Farmer Registration
```
Name: राम कुमार
Phone: +919876543210
Language: Hindi (हिंदी)
State: उत्तर प्रदेश
District: मेरठ
Village: सरधना
```

### Recommendation Query
```
Farmer ID: farmer-abc123
Query: मेरी गेहूं की फसल में पीले पत्ते दिख रहे हैं। क्या करूं?
Language: Hindi
```

### IoT Sensor Data
```
Device ID: sensor-001
Farmer ID: farmer-abc123
Temperature: 28.5
Humidity: 65.0
Soil Moisture: 45.0
Soil pH: 6.5
```

### Market Prices
```
Crop: Wheat
Location: Meerut, Uttar Pradesh
```

## 🌐 Browser Support

✅ **Recommended Browsers:**
- Chrome 90+
- Firefox 88+
- Edge 90+
- Safari 14+

## 📱 Mobile Usage

The UI is fully responsive and works on mobile devices:
1. Open http://localhost:8080 on your phone
2. Ensure phone is on same network as server
3. Use your computer's IP instead of localhost
4. Example: http://192.168.1.100:8080

## 🔐 Security Notes

- Never share API keys in the UI
- Use HTTPS in production
- Validate all inputs on server side
- Keep dependencies updated

## 📚 Additional Resources

- **API Documentation**: http://localhost:8000/docs
- **UI README**: `ui/README.md`
- **Setup Guide**: `WINDOWS_SETUP_AND_RUN_GUIDE.md`
- **Integration Status**: `INTEGRATION_STATUS.md`

## 💡 Tips & Tricks

1. **Keep Both Terminals Open**: Don't close the API server or UI server terminals
2. **Save Farmer IDs**: Copy and save farmer IDs for future queries
3. **Use Browser DevTools**: Press F12 to see network requests and responses
4. **Test with Sample Data**: Use the sample data provided above
5. **Check API Docs**: Visit http://localhost:8000/docs for detailed API information

## 🎯 Next Steps

1. ✅ Start the servers
2. ✅ Register a test farmer
3. ✅ Try getting a recommendation
4. ✅ Test voice query
5. ✅ Explore other features
6. 📖 Read the full documentation
7. 🚀 Deploy to production

## 🆘 Getting Help

If you encounter issues:
1. Check this guide
2. Review browser console (F12)
3. Check API server logs
4. Verify all services are running
5. Review `INTEGRATION_STATUS.md` for known issues

---

**Happy Farming! 🌾**

*KrishiMitra - Empowering Rural Farmers with AI*
