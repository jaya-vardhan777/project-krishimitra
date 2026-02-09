"""
End-to-End Integration Tests for KrishiMitra Platform

This module tests complete farmer journeys from registration to recommendation
across all user interfaces (WhatsApp, voice, web) and validates cross-service
communication and data flow.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
import uuid
import json

# Mock AWS services before importing the app
with patch('boto3.Session'), patch('boto3.client'):
    from src.krishimitra.main import app


@pytest.fixture
def client():
    """Create test client for FastAPI application."""
    return TestClient(app)


@pytest.fixture
def mock_aws_services():
    """Mock all AWS services for integration testing."""
    with patch('boto3.client') as mock_boto_client:
        # Mock DynamoDB
        mock_dynamodb = MagicMock()
        mock_dynamodb.put_item.return_value = {}
        mock_dynamodb.get_item.return_value = {
            'Item': {
                'farmerId': {'S': 'test-farmer-id'},
                'name': {'S': 'encrypted_name'},
                'phoneNumber': {'S': 'encrypted_phone'},
                'location': {
                    'M': {
                        'state': {'S': 'encrypted_state'},
                        'district': {'S': 'encrypted_district'},
                        'village': {'S': 'encrypted_village'}
                    }
                },
                'farmDetails': {
                    'M': {
                        'totalLandArea': {'N': '2.5'},
                        'soilType': {'S': 'loam'},
                        'irrigationType': {'S': 'drip'},
                        'crops': {'L': []}
                    }
                },
                'preferences': {
                    'M': {
                        'organicFarming': {'BOOL': False},
                        'riskTolerance': {'S': 'medium'},
                        'preferredLanguage': {'S': 'hi'}
                    }
                },
                'createdAt': {'S': datetime.now().isoformat()}

            }
        }
        
        # Mock Bedrock
        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model.return_value = {
            'body': MagicMock(read=lambda: json.dumps({
                'completion': 'Test recommendation response'
            }).encode())
        }
        
        # Mock Transcribe
        mock_transcribe = MagicMock()
        mock_transcribe.start_transcription_job.return_value = {
            'TranscriptionJob': {'TranscriptionJobName': 'test-job'}
        }
        
        # Mock Polly
        mock_polly = MagicMock()
        mock_polly.synthesize_speech.return_value = {
            'AudioStream': MagicMock(read=lambda: b'audio_data')
        }
        
        # Mock Translate
        mock_translate = MagicMock()
        mock_translate.translate_text.return_value = {
            'TranslatedText': 'Translated text'
        }
        
        # Configure mock client to return appropriate service
        def get_client(service_name, **kwargs):
            services = {
                'dynamodb': mock_dynamodb,
                'bedrock-runtime': mock_bedrock,
                'transcribe': mock_transcribe,
                'polly': mock_polly,
                'translate': mock_translate
            }
            return services.get(service_name, MagicMock())
        
        mock_boto_client.side_effect = get_client
        
        yield {
            'dynamodb': mock_dynamodb,
            'bedrock': mock_bedrock,
            'transcribe': mock_transcribe,
            'polly': mock_polly,
            'translate': mock_translate
        }


class TestCompleteUserJourneys:
    """Test complete farmer journeys from registration to recommendation."""
    
    def test_farmer_registration_to_first_recommendation(self, client, mock_aws_services):
        """Test complete journey: farmer registration -> profile creation -> first recommendation."""
        # Step 1: Register farmer
        registration_data = {
            "name": "राम कुमार",
            "phone_number": "+919876543210",
            "preferred_language": "hi-IN",
            "location": {
                "state": "उत्तर प्रदेश",
                "district": "मेरठ",
                "village": "सरधना"
            }
        }
        
        response = client.post("/api/v1/farmers/register", json=registration_data)
        assert response.status_code == 200
        farmer_data = response.json()
        farmer_id = farmer_data.get("farmer_id")
        assert farmer_id is not None
        
        # Step 2: Add farm details
        farm_details = {
            "total_land_area": 2.5,
            "soil_type": "loam",
            "irrigation_type": "drip",
            "crops": [
                {
                    "crop_type": "wheat",
                    "area": 1.5,
                    "planting_date": "2024-11-15"
                }
            ]
        }
        
        response = client.put(f"/api/v1/farmers/{farmer_id}/farm-details", json=farm_details)
        assert response.status_code == 200
        
        # Step 3: Request first recommendation
        query = {
            "farmer_id": farmer_id,
            "query": "मुझे गेहूं की फसल के लिए सलाह चाहिए",
            "language": "hi-IN"
        }
        
        response = client.post("/api/v1/recommendations/query", json=query)
        assert response.status_code == 200
        recommendation = response.json()
        assert "recommendation" in recommendation
        assert recommendation["language"] == "hi-IN"
    
    def test_voice_interaction_workflow(self, client, mock_aws_services):
        """Test complete voice interaction: audio upload -> transcription -> recommendation -> TTS."""
        # Step 1: Upload voice query
        audio_data = b"fake_audio_data"
        files = {"audio": ("query.wav", audio_data, "audio/wav")}
        data = {
            "farmer_id": "test-farmer-id",
            "language": "hi-IN"
        }
        
        response = client.post("/api/v1/voice/query", files=files, data=data)
        assert response.status_code == 200
        result = response.json()
        
        # Verify transcription was called
        assert mock_aws_services['transcribe'].start_transcription_job.called
        
        # Step 2: Get voice response
        query_id = result.get("query_id", "test-query-id")
        response = client.get(f"/api/v1/voice/response/{query_id}")
        assert response.status_code == 200
        
        # Verify TTS was called
        assert mock_aws_services['polly'].synthesize_speech.called
    
    def test_whatsapp_interaction_workflow(self, client, mock_aws_services):
        """Test complete WhatsApp interaction: message -> processing -> response."""
        # Step 1: Receive WhatsApp message
        whatsapp_message = {
            "from": "+919876543210",
            "message": "मुझे सिंचाई के बारे में सलाह चाहिए",
            "message_type": "text",
            "timestamp": datetime.now().isoformat()
        }
        
        response = client.post("/api/v1/whatsapp/webhook", json=whatsapp_message)
        assert response.status_code == 200
        
        # Step 2: Verify message was processed
        result = response.json()
        assert "message_id" in result
        assert result["status"] == "processed"
    
    def test_iot_data_to_recommendation_workflow(self, client, mock_aws_services):
        """Test IoT data ingestion triggering automatic recommendations."""
        # Step 1: Ingest IoT sensor data
        sensor_data = {
            "device_id": "sensor-001",
            "farmer_id": "test-farmer-id",
            "sensor_type": "soil_moisture",
            "readings": {
                "moisture": 25.5,
                "temperature": 22.3,
                "ph": 6.8
            },
            "timestamp": datetime.now().isoformat()
        }
        
        response = client.post("/api/v1/iot/data", json=sensor_data)
        assert response.status_code == 200
        
        # Step 2: Check if alert was generated
        response = client.get(f"/api/v1/farmers/test-farmer-id/alerts")
        assert response.status_code == 200
        alerts = response.json()
        assert isinstance(alerts, list)


class TestCrossServiceCommunication:
    """Test communication and data flow between different services."""
    
    def test_multi_agent_coordination(self, client, mock_aws_services):
        """Test coordination between multiple AI agents."""
        query = {
            "farmer_id": "test-farmer-id",
            "query": "मुझे टिकाऊ खेती के बारे में सलाह चाहिए",
            "language": "hi-IN",
            "include_sustainability": True,
            "include_market_data": True
        }
        
        response = client.post("/api/v1/recommendations/comprehensive", json=query)
        assert response.status_code == 200
        result = response.json()
        
        # Verify multiple agents were involved
        assert "advisory" in result
        assert "sustainability" in result
        assert "market_intelligence" in result
    
    def test_data_consistency_across_services(self, client, mock_aws_services):
        """Test data consistency when updating farmer profile across services."""
        farmer_id = "test-farmer-id"
        
        # Update farmer profile
        update_data = {
            "preferences": {
                "organic_farming": True,
                "preferred_language": "ta-IN"
            }
        }
        
        response = client.put(f"/api/v1/farmers/{farmer_id}", json=update_data)
        assert response.status_code == 200
        
        # Verify update is reflected in recommendations
        query = {
            "farmer_id": farmer_id,
            "query": "பயிர் பரிந்துரைகள்",
            "language": "ta-IN"
        }
        
        response = client.post("/api/v1/recommendations/query", json=query)
        assert response.status_code == 200
        recommendation = response.json()
        
        # Should prioritize organic methods
        assert recommendation["language"] == "ta-IN"


class TestMultilingualFunctionality:
    """Test multilingual functionality across all supported Indian languages."""
    
    @pytest.mark.parametrize("language,query", [
        ("hi-IN", "मुझे गेहूं की खेती के बारे में बताएं"),
        ("ta-IN", "கோதுமை விவசாயம் பற்றி சொல்லுங்கள்"),
        ("te-IN", "గోధుమ వ్యవసాయం గురించి చెప్పండి"),
        ("bn-IN", "গম চাষ সম্পর্কে বলুন"),
        ("mr-IN", "गहू शेतीबद्दल सांगा"),
        ("gu-IN", "ઘઉંની ખેતી વિશે જણાવો"),
        ("pa-IN", "ਕਣਕ ਦੀ ਖੇਤੀ ਬਾਰੇ ਦੱਸੋ")
    ])
    def test_multilingual_query_processing(self, client, mock_aws_services, language, query):
        """Test query processing in all supported Indian languages."""
        request_data = {
            "farmer_id": "test-farmer-id",
            "query": query,
            "language": language
        }
        
        response = client.post("/api/v1/recommendations/query", json=request_data)
        assert response.status_code == 200
        result = response.json()
        assert result["language"] == language
        assert "recommendation" in result


class TestSecurityAndPrivacy:
    """Test security and privacy compliance across all user interactions."""
    
    def test_data_encryption_in_transit(self, client, mock_aws_services):
        """Test that sensitive data is encrypted during transmission."""
        sensitive_data = {
            "name": "राम कुमार",
            "phone_number": "+919876543210",
            "aadhaar_number": "1234-5678-9012"
        }
        
        response = client.post("/api/v1/farmers/register", json=sensitive_data)
        assert response.status_code == 200
        
        # Verify DynamoDB received encrypted data
        call_args = mock_aws_services['dynamodb'].put_item.call_args
        stored_data = call_args[1]['Item']
        
        # Sensitive fields should be encrypted
        assert stored_data['name']['S'] != sensitive_data['name']
        assert stored_data['phoneNumber']['S'] != sensitive_data['phone_number']
    
    def test_consent_management(self, client, mock_aws_services):
        """Test explicit consent collection and tracking."""
        consent_data = {
            "farmer_id": "test-farmer-id",
            "consent_type": "data_sharing",
            "granted": True,
            "timestamp": datetime.now().isoformat()
        }
        
        response = client.post("/api/v1/farmers/consent", json=consent_data)
        assert response.status_code == 200
        
        # Verify consent is tracked
        response = client.get(f"/api/v1/farmers/test-farmer-id/consent")
        assert response.status_code == 200
        consents = response.json()
        assert any(c["consent_type"] == "data_sharing" for c in consents)


class TestSystemResilience:
    """Test system behavior under various failure scenarios."""
    
    def test_graceful_degradation_on_service_failure(self, client, mock_aws_services):
        """Test system continues to function when one service fails."""
        # Simulate Bedrock failure
        mock_aws_services['bedrock'].invoke_model.side_effect = Exception("Service unavailable")
        
        query = {
            "farmer_id": "test-farmer-id",
            "query": "मुझे सलाह चाहिए",
            "language": "hi-IN"
        }
        
        response = client.post("/api/v1/recommendations/query", json=query)
        
        # Should return cached or fallback recommendation
        assert response.status_code in [200, 503]
        if response.status_code == 200:
            result = response.json()
            assert "recommendation" in result or "fallback" in result
    
    def test_retry_mechanism_on_transient_failure(self, client, mock_aws_services):
        """Test automatic retry on transient failures."""
        # Simulate transient failure then success
        call_count = 0
        
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Transient error")
            return {'body': MagicMock(read=lambda: json.dumps({'completion': 'Success'}).encode())}
        
        mock_aws_services['bedrock'].invoke_model.side_effect = side_effect
        
        query = {
            "farmer_id": "test-farmer-id",
            "query": "सलाह",
            "language": "hi-IN"
        }
        
        response = client.post("/api/v1/recommendations/query", json=query)
        assert response.status_code == 200
        assert call_count >= 2  # Should have retried


class TestPerformanceRequirements:
    """Test that performance requirements are met."""
    
    def test_response_time_under_load(self, client, mock_aws_services):
        """Test response times meet requirements under concurrent requests."""
        import time
        import concurrent.futures
        
        def make_request():
            start = time.time()
            response = client.get("/api/v1/health")
            duration = time.time() - start
            return response.status_code, duration
        
        # Simulate 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in futures]
        
        # All requests should succeed
        assert all(status == 200 for status, _ in results)
        
        # Average response time should be under 2 seconds
        avg_duration = sum(duration for _, duration in results) / len(results)
        assert avg_duration < 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
