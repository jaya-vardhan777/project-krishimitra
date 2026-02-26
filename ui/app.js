// Configuration
const API_BASE_URL = 'http://localhost:8000';

// State
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initializeNavigation();
    checkAPIStatus();
    initializeForms();
    initializeVoiceRecording();
});

// Navigation
function initializeNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const sections = document.querySelectorAll('.section');

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const targetSection = item.dataset.section;

            // Update active nav item
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            // Update active section
            sections.forEach(section => section.classList.remove('active'));
            document.getElementById(targetSection).classList.add('active');
        });
    });
}

// API Status Check
async function checkAPIStatus() {
    const statusIndicator = document.getElementById('api-status');
    const statusText = document.getElementById('api-status-text');
    const dashboardStatus = document.getElementById('dashboard-api-status');

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/health`);
        const data = await response.json();

        if (response.ok && data.status === 'healthy') {
            statusIndicator.classList.add('online');
            statusText.textContent = 'API Online';
            dashboardStatus.textContent = '✅ Online';
            dashboardStatus.style.color = '#2ecc71';
        } else {
            throw new Error('API not healthy');
        }
    } catch (error) {
        statusIndicator.classList.add('offline');
        statusText.textContent = 'API Offline';
        dashboardStatus.textContent = '❌ Offline';
        dashboardStatus.style.color = '#e74c3c';
        console.error('API Status Check Failed:', error);
    }
}

// Initialize Forms
function initializeForms() {
    // Farmer Registration Form
    document.getElementById('farmer-registration-form').addEventListener('submit', handleFarmerRegistration);

    // Recommendations Form
    document.getElementById('recommendations-form').addEventListener('submit', handleRecommendations);

    // WhatsApp Form
    document.getElementById('whatsapp-form').addEventListener('submit', handleWhatsApp);

    // IoT Form
    document.getElementById('iot-form').addEventListener('submit', handleIoTData);

    // Market Prices Form
    document.getElementById('market-form').addEventListener('submit', handleMarketPrices);

    // Government Schemes Form
    document.getElementById('schemes-form').addEventListener('submit', handleGovernmentSchemes);

    // Audio Upload
    document.getElementById('upload-audio-btn').addEventListener('click', handleAudioUpload);
}

// Farmer Registration Handler
async function handleFarmerRegistration(e) {
    e.preventDefault();
    const resultBox = document.getElementById('farmer-registration-result');

    const formData = {
        name: document.getElementById('farmer-name').value,
        phone_number: document.getElementById('farmer-phone').value,
        preferred_language: document.getElementById('farmer-language').value,
        location: {
            state: document.getElementById('farmer-state').value,
            district: document.getElementById('farmer-district').value,
            village: document.getElementById('farmer-village').value
        }
    };

    try {
        showLoading(resultBox);
        const response = await fetch(`${API_BASE_URL}/api/v1/farmers/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });

        const data = await response.json();

        if (response.ok) {
            showResult(resultBox, 'success', 'Farmer Registered Successfully!', data);
        } else {
            showResult(resultBox, 'error', 'Registration Failed', data);
        }
    } catch (error) {
        showResult(resultBox, 'error', 'Error', {
            message: 'Failed to connect to API. Make sure the server is running.',
            error: error.message
        });
    }
}

// Recommendations Handler
async function handleRecommendations(e) {
    e.preventDefault();
    const resultBox = document.getElementById('recommendations-result');

    const formData = {
        farmer_id: document.getElementById('rec-farmer-id').value,
        query: document.getElementById('rec-query').value,
        language: document.getElementById('rec-language').value
    };

    try {
        showLoading(resultBox);
        const response = await fetch(`${API_BASE_URL}/api/v1/recommendations/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });

        const data = await response.json();

        if (response.ok) {
            showResult(resultBox, 'success', 'Recommendation Generated', data);
        } else {
            showResult(resultBox, 'error', 'Failed to Get Recommendation', data);
        }
    } catch (error) {
        showResult(resultBox, 'error', 'Error', {
            message: 'Failed to connect to API. Make sure the server is running.',
            error: error.message
        });
    }
}

// Voice Recording
function initializeVoiceRecording() {
    const recordBtn = document.getElementById('record-btn');
    const voiceStatus = document.getElementById('voice-status');

    recordBtn.addEventListener('click', async () => {
        if (!isRecording) {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];

                mediaRecorder.ondataavailable = (event) => {
                    audioChunks.push(event.data);
                };

                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    await processVoiceQuery(audioBlob);
                };

                mediaRecorder.start();
                isRecording = true;
                recordBtn.textContent = '⏹️ Stop Recording';
                recordBtn.classList.add('recording');
                voiceStatus.textContent = 'Recording... Speak now';
            } catch (error) {
                voiceStatus.textContent = 'Error: Could not access microphone';
                console.error('Microphone access error:', error);
            }
        } else {
            mediaRecorder.stop();
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
            isRecording = false;
            recordBtn.textContent = '🎤 Start Recording';
            recordBtn.classList.remove('recording');
            voiceStatus.textContent = 'Processing...';
        }
    });
}

// Audio Upload Handler
async function handleAudioUpload() {
    const fileInput = document.getElementById('audio-file');
    const file = fileInput.files[0];

    if (!file) {
        alert('Please select an audio file first');
        return;
    }

    await processVoiceQuery(file);
}

// Process Voice Query
async function processVoiceQuery(audioBlob) {
    const resultBox = document.getElementById('voice-result');
    const language = document.getElementById('voice-language').value;

    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.wav');
    formData.append('language', language);

    try {
        showLoading(resultBox);
        const response = await fetch(`${API_BASE_URL}/api/v1/voice/query`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            showResult(resultBox, 'success', 'Voice Query Processed', data);
            document.getElementById('voice-status').textContent = 'Ready to record';
        } else {
            showResult(resultBox, 'error', 'Voice Processing Failed', data);
            document.getElementById('voice-status').textContent = 'Ready to record';
        }
    } catch (error) {
        showResult(resultBox, 'error', 'Error', {
            message: 'Failed to connect to API. Make sure the server is running.',
            error: error.message
        });
        document.getElementById('voice-status').textContent = 'Ready to record';
    }
}

// WhatsApp Handler
async function handleWhatsApp(e) {
    e.preventDefault();
    const resultBox = document.getElementById('whatsapp-result');

    const formData = {
        phone_number: document.getElementById('whatsapp-phone').value,
        message: document.getElementById('whatsapp-message').value
    };

    try {
        showLoading(resultBox);
        const response = await fetch(`${API_BASE_URL}/api/v1/whatsapp/send`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });

        const data = await response.json();

        if (response.ok) {
            showResult(resultBox, 'success', 'WhatsApp Message Sent', data);
        } else {
            showResult(resultBox, 'error', 'Failed to Send Message', data);
        }
    } catch (error) {
        showResult(resultBox, 'error', 'Error', {
            message: 'Failed to connect to API. Make sure the server is running.',
            error: error.message
        });
    }
}

// IoT Data Handler
async function handleIoTData(e) {
    e.preventDefault();
    const resultBox = document.getElementById('iot-result');

    const formData = {
        device_id: document.getElementById('iot-device-id').value,
        farmer_id: document.getElementById('iot-farmer-id').value,
        sensor_data: {
            temperature: parseFloat(document.getElementById('iot-temperature').value) || null,
            humidity: parseFloat(document.getElementById('iot-humidity').value) || null,
            soil_moisture: parseFloat(document.getElementById('iot-soil-moisture').value) || null,
            soil_ph: parseFloat(document.getElementById('iot-soil-ph').value) || null
        },
        timestamp: new Date().toISOString()
    };

    try {
        showLoading(resultBox);
        const response = await fetch(`${API_BASE_URL}/api/v1/iot/data`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });

        const data = await response.json();

        if (response.ok) {
            showResult(resultBox, 'success', 'IoT Data Submitted', data);
        } else {
            showResult(resultBox, 'error', 'Failed to Submit Data', data);
        }
    } catch (error) {
        showResult(resultBox, 'error', 'Error', {
            message: 'Failed to connect to API. Make sure the server is running.',
            error: error.message
        });
    }
}

// Market Prices Handler
async function handleMarketPrices(e) {
    e.preventDefault();
    const resultBox = document.getElementById('market-result');

    const crop = document.getElementById('market-crop').value;
    const location = document.getElementById('market-location').value;

    try {
        showLoading(resultBox);
        const response = await fetch(
            `${API_BASE_URL}/api/v1/market/prices?crop=${encodeURIComponent(crop)}&location=${encodeURIComponent(location)}`
        );

        const data = await response.json();

        if (response.ok) {
            showResult(resultBox, 'success', 'Market Prices Retrieved', data);
        } else {
            showResult(resultBox, 'error', 'Failed to Get Prices', data);
        }
    } catch (error) {
        showResult(resultBox, 'error', 'Error', {
            message: 'Failed to connect to API. Make sure the server is running.',
            error: error.message
        });
    }
}

// Government Schemes Handler
async function handleGovernmentSchemes(e) {
    e.preventDefault();
    const resultBox = document.getElementById('schemes-result');

    const farmerId = document.getElementById('schemes-farmer-id').value;

    try {
        showLoading(resultBox);
        const response = await fetch(`${API_BASE_URL}/api/v1/government/schemes/${farmerId}`);

        const data = await response.json();

        if (response.ok) {
            showResult(resultBox, 'success', 'Eligible Schemes Found', data);
        } else {
            showResult(resultBox, 'error', 'Failed to Get Schemes', data);
        }
    } catch (error) {
        showResult(resultBox, 'error', 'Error', {
            message: 'Failed to connect to API. Make sure the server is running.',
            error: error.message
        });
    }
}

// Utility Functions
function showLoading(resultBox) {
    resultBox.innerHTML = '<div class="text-center"><div class="loading"></div> Processing...</div>';
    resultBox.classList.add('show');
    resultBox.classList.remove('success', 'error');
}

function showResult(resultBox, type, title, data) {
    resultBox.classList.add('show', type);
    resultBox.innerHTML = `
        <h3>${title}</h3>
        <pre>${JSON.stringify(data, null, 2)}</pre>
    `;
}

// Refresh API status every 30 seconds
setInterval(checkAPIStatus, 30000);
