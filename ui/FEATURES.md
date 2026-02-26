# KrishiMitra Web UI - Feature Guide

## 🎨 Visual Tour

### Main Interface

```
┌─────────────────────────────────────────────────────────────┐
│  🌾 KrishiMitra                              ● API Online   │
│  AI-Powered Agricultural Advisory Platform                  │
└─────────────────────────────────────────────────────────────┘
┌──────────────┬──────────────────────────────────────────────┐
│              │                                              │
│  📊 Dashboard│  Welcome to KrishiMitra                      │
│  👨‍🌾 Farmer  │                                              │
│  💡 Recommend│  [Statistics Cards]                          │
│  🎤 Voice    │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐       │
│  💬 WhatsApp │  │ API  │ │Farmer│ │Recom │ │ Lang │       │
│  📡 IoT Data │  │Status│ │Count │ │Given │ │  7   │       │
│  💰 Market   │  └──────┘ └──────┘ └──────┘ └──────┘       │
│  🏛️ Schemes  │                                              │
│              │  [Feature Overview]                          │
└──────────────┴──────────────────────────────────────────────┘
```

## 📋 Feature Details

### 1. Dashboard 📊

**What You See:**
- Real-time API status (green = online, red = offline)
- System statistics in colorful cards
- Feature overview with descriptions
- Quick navigation hints

**Use Cases:**
- Check system health
- View platform statistics
- Get oriented with features
- Monitor API connectivity

---

### 2. Farmer Registration 👨‍🌾

**Form Fields:**
```
┌─────────────────────────────────────┐
│ Name: [राम कुमार              ]    │
│ Phone: [+919876543210          ]    │
│ Language: [Hindi (हिंदी) ▼    ]    │
│ State: [उत्तर प्रदेश           ]    │
│ District: [मेरठ                ]    │
│ Village: [सरधना                ]    │
│                                     │
│        [Register Farmer]            │
└─────────────────────────────────────┘
```

**Response:**
```json
{
  "farmer_id": "farmer-abc123",
  "name": "राम कुमार",
  "phone_number": "+919876543210",
  "status": "registered"
}
```

**Features:**
- ✅ Multilingual name support
- ✅ Phone validation
- ✅ 7 language options
- ✅ Location hierarchy
- ✅ Instant farmer ID

---

### 3. Get Recommendations 💡

**Interface:**
```
┌─────────────────────────────────────┐
│ Farmer ID: [farmer-abc123      ]    │
│                                     │
│ Query:                              │
│ ┌─────────────────────────────────┐ │
│ │ मेरी गेहूं की फसल में पीले     │ │
│ │ पत्ते दिख रहे हैं। क्या करूं?  │ │
│ └─────────────────────────────────┘ │
│                                     │
│ Language: [Hindi (हिंदी) ▼    ]    │
│                                     │
│     [Get Recommendation]            │
└─────────────────────────────────────┘
```

**AI Response:**
```
✓ Recommendation Generated

{
  "recommendation": "आपकी गेहूं की फसल में...",
  "confidence": 0.95,
  "actions": [
    "नाइट्रोजन उर्वरक डालें",
    "सिंचाई बढ़ाएं"
  ]
}
```

**Features:**
- ✅ Natural language queries
- ✅ Any supported language
- ✅ AI-powered responses
- ✅ Actionable advice
- ✅ Confidence scores

---

### 4. Voice Query 🎤

**Recording Interface:**
```
┌─────────────────────────────────────┐
│                                     │
│        ┌─────────────────┐          │
│        │  🎤 Start       │          │
│        │   Recording     │          │
│        └─────────────────┘          │
│                                     │
│    Status: Ready to record          │
│                                     │
│ Language: [Hindi (हिंदी) ▼    ]    │
│                                     │
│ Or upload audio file:               │
│ [Choose File] [Upload & Process]    │
└─────────────────────────────────────┘
```

**Recording States:**
1. **Ready**: Blue button, "Start Recording"
2. **Recording**: Red pulsing button, "Stop Recording"
3. **Processing**: Loading spinner, "Processing..."
4. **Complete**: Green result box with transcription

**Features:**
- ✅ Browser-based recording
- ✅ File upload option
- ✅ 7 language support
- ✅ Real-time status
- ✅ Audio transcription

---

### 5. WhatsApp Integration 💬

**Message Interface:**
```
┌─────────────────────────────────────┐
│ Webhook Configuration:              │
│ http://localhost:8000/api/v1/       │
│ whatsapp/webhook                    │
│                                     │
│ Phone: [+919876543210          ]    │
│                                     │
│ Message:                            │
│ ┌─────────────────────────────────┐ │
│ │ मुझे टमाटर की खेती के बारे में │ │
│ │ जानकारी चाहिए                  │ │
│ └─────────────────────────────────┘ │
│                                     │
│    [Send WhatsApp Message]          │
└─────────────────────────────────────┘
```

**Features:**
- ✅ Direct messaging
- ✅ Webhook setup info
- ✅ Message tracking
- ✅ Delivery status
- ✅ Multilingual support

---

### 6. IoT Sensor Data 📡

**Data Entry:**
```
┌─────────────────────────────────────┐
│ Device ID: [sensor-001         ]    │
│ Farmer ID: [farmer-abc123      ]    │
│                                     │
│ ┌──────────────┬──────────────────┐ │
│ │Temperature   │ Humidity         │ │
│ │[28.5    ]°C  │ [65.0      ]%    │ │
│ └──────────────┴──────────────────┘ │
│                                     │
│ ┌──────────────┬──────────────────┐ │
│ │Soil Moisture │ Soil pH          │ │
│ │[45.0    ]%   │ [6.5       ]     │ │
│ └──────────────┴──────────────────┘ │
│                                     │
│     [Submit Sensor Data]            │
└─────────────────────────────────────┘
```

**Data Visualization:**
```
Temperature: 28.5°C  ████████░░ 
Humidity:    65.0%   ██████░░░░
Soil Moist:  45.0%   ████░░░░░░
Soil pH:     6.5     ██████░░░░ (Optimal)
```

**Features:**
- ✅ Multi-sensor support
- ✅ Real-time submission
- ✅ Automatic timestamps
- ✅ Data validation
- ✅ Historical tracking

---

### 7. Market Prices 💰

**Price Query:**
```
┌─────────────────────────────────────┐
│ Crop Name: [Wheat / गेहूं      ]    │
│                                     │
│ Location: [Meerut, UP          ]    │
│                                     │
│      [Get Market Prices]            │
└─────────────────────────────────────┘
```

**Price Display:**
```
✓ Market Prices Retrieved

Wheat (गेहूं) - Meerut, Uttar Pradesh

Current Price: ₹2,150/quintal
Trend: ↑ +5% (Last 7 days)

Nearby Markets:
┌────────────────┬──────────┬──────────┐
│ Market         │ Price    │ Distance │
├────────────────┼──────────┼──────────┤
│ Meerut Mandi   │ ₹2,150   │ 0 km     │
│ Ghaziabad      │ ₹2,180   │ 45 km    │
│ Delhi          │ ₹2,200   │ 70 km    │
└────────────────┴──────────┴──────────┘
```

**Features:**
- ✅ Real-time prices
- ✅ Price trends
- ✅ Nearby markets
- ✅ Distance calculation
- ✅ Best rates

---

### 8. Government Schemes 🏛️

**Eligibility Check:**
```
┌─────────────────────────────────────┐
│ Farmer ID: [farmer-abc123      ]    │
│                                     │
│   [Check Eligible Schemes]          │
└─────────────────────────────────────┘
```

**Schemes Display:**
```
✓ Eligible Schemes Found

You are eligible for 3 schemes:

1. PM-KISAN (प्रधानमंत्री किसान सम्मान निधि)
   ├─ Benefit: ₹6,000/year
   ├─ Status: Active
   └─ Next Payment: March 2026

2. Crop Insurance (फसल बीमा योजना)
   ├─ Coverage: Up to ₹50,000
   ├─ Premium: ₹500/season
   └─ Deadline: 15 days

3. Soil Health Card (मृदा स्वास्थ्य कार्ड)
   ├─ Benefit: Free soil testing
   ├─ Status: Eligible
   └─ Apply: Online/Offline
```

**Features:**
- ✅ Automatic eligibility
- ✅ Scheme details
- ✅ Application guidance
- ✅ Deadline tracking
- ✅ Document checklist

---

## 🎨 Design Elements

### Color Scheme
```
Primary:   #2ecc71 (Green) - Success, Agriculture
Secondary: #3498db (Blue)  - Information
Accent:    #667eea (Purple)- Premium features
Warning:   #f39c12 (Orange)- Alerts
Error:     #e74c3c (Red)   - Errors
```

### Typography
```
Headings:  -apple-system, BlinkMacSystemFont, 'Segoe UI'
Body:      Roboto, Oxygen, Ubuntu, Cantarell
Code:      'Courier New', monospace
```

### Animations
- ✨ Fade in on section change
- 🔄 Pulse on API status
- 📊 Slide in on results
- 🎤 Pulse on recording
- ⏳ Spin on loading

---

## 📱 Responsive Design

### Desktop (1200px+)
```
┌────────────────────────────────────────┐
│  Header                                │
├──────────┬─────────────────────────────┤
│ Sidebar  │  Content Area               │
│ (250px)  │  (Flexible)                 │
│          │                             │
│ Nav      │  Forms & Results            │
│ Items    │                             │
└──────────┴─────────────────────────────┘
```

### Tablet (768px - 1199px)
```
┌────────────────────────────────────────┐
│  Header                                │
├──────────┬─────────────────────────────┤
│ Sidebar  │  Content Area               │
│ (200px)  │  (Flexible)                 │
└──────────┴─────────────────────────────┘
```

### Mobile (< 768px)
```
┌────────────────────────────────────────┐
│  Header                                │
├────────────────────────────────────────┤
│  Horizontal Scrolling Nav              │
├────────────────────────────────────────┤
│  Content Area (Full Width)             │
│                                        │
└────────────────────────────────────────┘
```

---

## 🔔 Status Indicators

### API Status
```
● Online  - Green, pulsing
● Offline - Red, pulsing
● Loading - Gray, spinning
```

### Form States
```
✓ Success - Green border, checkmark
✗ Error   - Red border, error icon
⏳ Loading - Blue border, spinner
```

### Results
```
┌─────────────────────────────────────┐
│ ✓ Success Title                     │
│ ─────────────────────────────────── │
│ Response data...                    │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ ✗ Error Title                       │
│ ─────────────────────────────────── │
│ Error message...                    │
└─────────────────────────────────────┘
```

---

## 🎯 User Flows

### New Farmer Journey
```
1. Open UI → Dashboard
2. Click "Farmer Registration"
3. Fill form → Submit
4. Save Farmer ID
5. Click "Get Recommendations"
6. Enter query → Get advice
```

### Voice Query Flow
```
1. Click "Voice Query"
2. Select language
3. Click "Start Recording"
4. Speak question
5. Click "Stop Recording"
6. View transcription & response
```

### IoT Data Flow
```
1. Click "IoT Sensor Data"
2. Enter device & farmer ID
3. Fill sensor readings
4. Submit data
5. View confirmation
6. Get automated recommendations
```

---

## 💡 Tips for Best Experience

1. **Keep API Running**: Don't close the API server terminal
2. **Save Farmer IDs**: Copy and store for future use
3. **Use DevTools**: Press F12 to see network activity
4. **Test Features**: Try all sections with sample data
5. **Check Status**: Monitor the API status indicator
6. **Read Responses**: Review JSON for detailed info
7. **Grant Permissions**: Allow microphone for voice
8. **Use Localhost**: Run through server, not file://

---

**KrishiMitra Web UI** - Making AI Agriculture Accessible 🌾
