# KrishiMitra Web UI

A modern, responsive web interface for interacting with the KrishiMitra API.

## Features

- 🌾 **Farmer Registration** - Register new farmers with multilingual support
- 💡 **Get Recommendations** - Query the AI system for agricultural advice
- 🎤 **Voice Queries** - Record or upload audio in 7 Indian languages
- 💬 **WhatsApp Integration** - Send and receive WhatsApp messages
- 📡 **IoT Sensor Data** - Submit and view sensor readings
- 💰 **Market Prices** - Check real-time crop prices
- 🏛️ **Government Schemes** - Find eligible government programs

## Supported Languages

- Hindi (हिंदी)
- Tamil (தமிழ்)
- Telugu (తెలుగు)
- Bengali (বাংলা)
- Marathi (मराठी)
- Gujarati (ગુજરાતી)
- Punjabi (ਪੰਜਾਬੀ)

## Quick Start

### Prerequisites

1. **KrishiMitra API Server Running**
   ```powershell
   # In the project root directory
   python -m uvicorn src.krishimitra.main:app --reload
   ```

2. **Web Browser** (Chrome, Firefox, Edge, or Safari)

### Running the UI

#### Option 1: Using Python HTTP Server (Recommended)

```powershell
# Navigate to the ui directory
cd ui

# Start a simple HTTP server
python -m http.server 8080

# Open your browser to:
# http://localhost:8080
```

#### Option 2: Using Node.js HTTP Server

```powershell
# Install http-server globally (one time)
npm install -g http-server

# Navigate to the ui directory
cd ui

# Start the server
http-server -p 8080

# Open your browser to:
# http://localhost:8080
```

#### Option 3: Direct File Access

Simply open `index.html` in your web browser:

```powershell
# Windows
start ui/index.html

# Or double-click the index.html file in File Explorer
```

**Note**: Some features (like voice recording) may require running through a server due to browser security restrictions.

## Configuration

The UI is configured to connect to the API at `http://localhost:8000` by default.

To change the API URL, edit `app.js`:

```javascript
// Configuration
const API_BASE_URL = 'http://localhost:8000';  // Change this if needed
```

## Usage Guide

### 1. Dashboard

The dashboard shows:
- API connection status
- System statistics
- Quick overview of features

### 2. Farmer Registration

Register a new farmer:
1. Fill in farmer details (name, phone, language)
2. Add location information (state, district, village)
3. Click "Register Farmer"
4. Save the returned Farmer ID for future queries

### 3. Get Recommendations

Query the AI system:
1. Enter the Farmer ID
2. Type your agricultural query (in any supported language)
3. Select the language
4. Click "Get Recommendation"

### 4. Voice Query

Use voice input:
1. Click "Start Recording" to record audio
2. Speak your query
3. Click "Stop Recording"
4. Or upload a pre-recorded audio file

### 5. WhatsApp Integration

Send WhatsApp messages:
1. Enter the phone number (with country code)
2. Type your message
3. Click "Send WhatsApp Message"

### 6. IoT Sensor Data

Submit sensor readings:
1. Enter Device ID and Farmer ID
2. Fill in sensor values (temperature, humidity, soil moisture, pH)
3. Click "Submit Sensor Data"

### 7. Market Prices

Check crop prices:
1. Enter crop name (e.g., "Wheat" or "गेहूं")
2. Enter location
3. Click "Get Market Prices"

### 8. Government Schemes

Find eligible schemes:
1. Enter Farmer ID
2. Click "Check Eligible Schemes"

## API Endpoints Used

The UI interacts with these API endpoints:

- `GET /api/v1/health` - Check API status
- `POST /api/v1/farmers/register` - Register farmer
- `POST /api/v1/recommendations/query` - Get recommendations
- `POST /api/v1/voice/query` - Process voice query
- `POST /api/v1/whatsapp/send` - Send WhatsApp message
- `POST /api/v1/iot/data` - Submit IoT data
- `GET /api/v1/market/prices` - Get market prices
- `GET /api/v1/government/schemes/{farmer_id}` - Get schemes

## Browser Compatibility

- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Edge 90+
- ✅ Safari 14+

## Features

### Real-time API Status

The UI automatically checks API connectivity and displays the status in the header.

### Responsive Design

The interface adapts to different screen sizes:
- Desktop: Full sidebar navigation
- Mobile: Horizontal scrolling navigation

### Form Validation

All forms include client-side validation to ensure data quality before submission.

### Error Handling

Clear error messages are displayed when:
- API is offline
- Invalid data is submitted
- Network errors occur

## Troubleshooting

### API Connection Issues

**Problem**: "API Offline" status or connection errors

**Solutions**:
1. Ensure the API server is running:
   ```powershell
   python -m uvicorn src.krishimitra.main:app --reload
   ```

2. Check the API URL in `app.js` matches your server

3. Verify no firewall is blocking port 8000

### CORS Errors

**Problem**: Browser console shows CORS errors

**Solution**: The API server includes CORS middleware. Ensure it's configured correctly in `src/krishimitra/main.py`.

### Voice Recording Not Working

**Problem**: Microphone access denied or not working

**Solutions**:
1. Run the UI through a server (not direct file access)
2. Grant microphone permissions in browser
3. Use HTTPS (required by some browsers)
4. Try uploading an audio file instead

### Form Submission Fails

**Problem**: Forms don't submit or show errors

**Solutions**:
1. Check browser console for error messages
2. Verify all required fields are filled
3. Ensure API endpoints are implemented
4. Check network tab for API response details

## Development

### File Structure

```
ui/
├── index.html      # Main HTML structure
├── styles.css      # Styling and layout
├── app.js          # JavaScript functionality
└── README.md       # This file
```

### Customization

**Change Colors**: Edit the CSS variables in `styles.css`

**Add New Features**: 
1. Add HTML section in `index.html`
2. Add navigation item
3. Add form handler in `app.js`

**Modify API Calls**: Update functions in `app.js`

## Security Notes

- Never commit API keys or credentials to the UI code
- Use environment variables for sensitive configuration
- Always validate user input on the server side
- Use HTTPS in production

## Production Deployment

For production deployment:

1. **Build Process**: Minify CSS and JavaScript
2. **CDN**: Host static files on a CDN
3. **HTTPS**: Always use HTTPS
4. **Environment Config**: Use environment-specific API URLs
5. **Error Tracking**: Add error monitoring (e.g., Sentry)

## Support

For issues or questions:
- Check the main project README
- Review API documentation at http://localhost:8000/docs
- Check browser console for error messages

## License

Part of the KrishiMitra project - AI-Powered Agricultural Advisory Platform

---

**Last Updated**: 2026-02-09
**Version**: 1.0.0
