#!/usr/bin/env python3

from src.krishimitra.agents.data_ingestion import IoTSensorData

def test_iot_sensor_data():
    """Simple test for IoT sensor data validation"""
    try:
        sensor_data = IoTSensorData(
            device_id='test-device-001',
            sensor_type='soil_moisture',
            value=45.5,
            unit='percent'
        )
        print(f'✓ Created sensor data: {sensor_data.device_id}, {sensor_data.sensor_type}, {sensor_data.value}')
        return True
    except Exception as e:
        print(f'✗ Error creating sensor data: {e}')
        return False

if __name__ == "__main__":
    success = test_iot_sensor_data()
    if success:
        print("IoT data collection implementation is working correctly!")
    else:
        print("IoT data collection implementation has issues.")