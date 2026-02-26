# How to Apply the Registration Fix

## What Was Fixed

The farmer registration endpoint `/api/v1/farmers/register` has been added to match what the UI expects. This is a simplified registration endpoint that doesn't require authentication or complex farm details.

## Steps to Apply the Fix

### Option 1: Restart Using the Start Script

1. **Stop the current servers** (close the terminal windows or press Ctrl+C)

2. **Run the start script again:**
   ```powershell
   start-krishimitra.bat
   ```

### Option 2: Manual Restart

1. **Stop the API server** (press Ctrl+C in the API terminal)

2. **Start it again:**
   ```powershell
   python -m uvicorn src.krishimitra.main:app --reload --host 0.0.0.0 --port 8000
   ```

   The `--reload` flag should automatically detect the changes, but if not, restart manually.

3. **The UI server can keep running** (no changes needed there)

## Test the Fix

### Option 1: Use the Web UI

1. Open http://localhost:8080
2. Click "Farmer Registration"
3. Fill in the form:
   - Name: राम कुमार
   - Phone: +919876543210
   - Language: Hindi (हिंदी)
   - State: उत्तर प्रदेश
   - District: मेरठ
   - Village: सरधना
4. Click "Register Farmer"
5. You should see a success message with a Farmer ID!

### Option 2: Use the Test Script

```powershell
python test_registration.py
```

This will test the endpoint directly and show you the response.

### Option 3: Use the API Docs

1. Open http://localhost:8000/docs
2. Find the `POST /api/v1/farmers/register` endpoint
3. Click "Try it out"
4. Use the sample data:
   ```json
   {
     "name": "राम कुमार",
     "phone_number": "+919876543210",
     "preferred_language": "hi-IN",
     "location": {
       "state": "उत्तर प्रदेश",
       "district": "मेरठ",
       "village": "सरधना"
     }
   }
   ```
5. Click "Execute"
6. Check the response!

## What Changed

### New Endpoint Added

**POST `/api/v1/farmers/register`**

- Simplified registration (no authentication required)
- Minimal required fields
- Returns farmer ID immediately
- Works in development mode even if DynamoDB is unavailable

### Request Format

```json
{
  "name": "string",
  "phone_number": "+919876543210",
  "preferred_language": "hi-IN",
  "location": {
    "state": "string",
    "district": "string",
    "village": "string"
  }
}
```

### Response Format

```json
{
  "farmer_id": "farmer-abc12345",
  "name": "राम कुमार",
  "phone_number": "+919876543210",
  "preferred_language": "hi-IN",
  "location": {
    "state": "उत्तर प्रदेश",
    "district": "मेरठ",
    "village": "सरधना"
  },
  "status": "registered",
  "created_at": "2026-02-09T10:30:00"
}
```

## Troubleshooting

### Issue: Still getting "Method Not Allowed"

**Solution:** The server needs to be restarted to load the new code.

1. Stop the API server completely (Ctrl+C)
2. Start it again
3. Wait for "Application startup complete" message
4. Try the registration again

### Issue: "Failed to register farmer"

**Solution:** This is expected if DynamoDB is not configured. In development mode, the endpoint will return a mock response anyway, so you'll still get a farmer ID.

### Issue: Server won't start

**Solution:** Check for syntax errors:

```powershell
# Test the code
python -c "from src.krishimitra.api.v1 import farmers; print('OK')"
```

If there are errors, check the file `src/krishimitra/api/v1/farmers.py`

## Verify It's Working

You should see output like this:

```
✅ Registration successful!

{
  "farmer_id": "farmer-abc12345",
  "name": "राम कुमार",
  "phone_number": "+919876543210",
  "preferred_language": "hi-IN",
  "location": {
    "state": "उत्तर प्रदेश",
    "district": "मेरठ",
    "village": "सरधना"
  },
  "status": "registered",
  "created_at": "2026-02-09T10:30:00.123456"
}
```

## Next Steps

Once registration works, you can:

1. ✅ Save the farmer ID
2. ✅ Try getting recommendations with that farmer ID
3. ✅ Test other features in the UI
4. ✅ Explore the API documentation

---

**Note:** The `--reload` flag in uvicorn should automatically detect file changes, but sometimes a manual restart is needed for new endpoints.
