"""Quick test for farmer registration endpoint."""
import requests
import json

# Test data
farmer_data = {
    "name": "राम कुमार",
    "phone_number": "+919876543210",
    "preferred_language": "hi-IN",
    "location": {
        "state": "उत्तर प्रदेश",
        "district": "मेरठ",
        "village": "सरधना"
    }
}

# Test the endpoint
try:
    response = requests.post(
        "http://localhost:8000/api/v1/farmers/register",
        json=farmer_data,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    
    if response.status_code == 201:
        print("\n✅ Registration successful!")
    else:
        print("\n❌ Registration failed!")
        
except requests.exceptions.ConnectionError:
    print("❌ Could not connect to API server. Make sure it's running on http://localhost:8000")
except Exception as e:
    print(f"❌ Error: {e}")
