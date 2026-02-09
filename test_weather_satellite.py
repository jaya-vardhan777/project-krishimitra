#!/usr/bin/env python3

import asyncio
from src.krishimitra.agents.weather_integration import WeatherAPIClient, WeatherDataTool
from src.krishimitra.agents.satellite_processing import SatelliteImageProcessor, SatelliteAnalysisTool

async def test_weather_integration():
    """Test weather API integration"""
    print("Testing Weather Integration...")
    
    try:
        # Test weather client
        weather_client = WeatherAPIClient()
        
        # Test coordinates (Delhi, India)
        latitude, longitude = 28.6139, 77.2090
        
        # Test weather data collection (will use mock data since no API keys)
        weather_data = await weather_client.get_agricultural_weather_data(latitude, longitude)
        
        if weather_data:
            print(f"✓ Weather data collected: {weather_data.temperature}°C, {weather_data.condition.value}")
        else:
            print("✓ Weather client initialized (no API keys configured)")
        
        await weather_client.close()
        
        # Test weather tool
        weather_tool = WeatherDataTool()
        result = await weather_tool._arun(latitude, longitude)
        print(f"✓ Weather tool result: {result}")
        
        return True
        
    except Exception as e:
        print(f"✗ Weather integration test failed: {e}")
        return False

async def test_satellite_processing():
    """Test satellite imagery processing"""
    print("\nTesting Satellite Processing...")
    
    try:
        # Test satellite processor
        processor = SatelliteImageProcessor()
        
        # Test field boundary (small area in Punjab, India)
        field_boundary = [
            {"latitude": 30.7333, "longitude": 76.7794},
            {"latitude": 30.7343, "longitude": 76.7804},
            {"latitude": 30.7353, "longitude": 76.7794},
            {"latitude": 30.7343, "longitude": 76.7784}
        ]
        
        from src.krishimitra.models.agricultural_intelligence import GeographicCoordinate
        
        boundary_coords = [
            GeographicCoordinate(latitude=coord["latitude"], longitude=coord["longitude"])
            for coord in field_boundary
        ]
        
        # Test crop health analysis (will use simulated data)
        analysis = await processor.analyze_crop_health(boundary_coords, "wheat")
        
        if analysis:
            print(f"✓ Satellite analysis completed: Health score {analysis.overall_health_score:.1f}%")
            print(f"  NDVI: {analysis.vegetation_indices.ndvi:.2f}")
            print(f"  Growth stage: {analysis.growth_stage}")
        else:
            print("✓ Satellite processor initialized (simulated analysis)")
        
        # Test satellite tool
        satellite_tool = SatelliteAnalysisTool()
        import json
        boundary_json = json.dumps(field_boundary)
        result = await satellite_tool._arun(boundary_json, "wheat")
        print(f"✓ Satellite tool result: {result}")
        
        return True
        
    except Exception as e:
        print(f"✗ Satellite processing test failed: {e}")
        return False

async def test_data_ingestion_agent():
    """Test the complete data ingestion agent"""
    print("\nTesting Data Ingestion Agent...")
    
    try:
        from src.krishimitra.agents.data_ingestion import DataIngestionAgent
        
        agent = DataIngestionAgent()
        
        # Test comprehensive data collection
        farmer_id = "test-farmer-001"
        location = {"latitude": 28.6139, "longitude": 77.2090}
        field_boundary = [
            {"latitude": 28.6139, "longitude": 77.2090},
            {"latitude": 28.6149, "longitude": 77.2100},
            {"latitude": 28.6159, "longitude": 77.2090},
            {"latitude": 28.6149, "longitude": 77.2080}
        ]
        
        results = await agent.collect_comprehensive_data(
            farmer_id=farmer_id,
            location=location,
            field_boundary=field_boundary,
            crop_type="rice"
        )
        
        print(f"✓ Comprehensive data collection completed for farmer {farmer_id}")
        print(f"  Sensor data: {len(results['sensor_data'])} readings")
        print(f"  Weather data: {'Available' if results['weather_data'] else 'Not available'}")
        print(f"  Satellite data: {'Available' if results['satellite_data'] else 'Not available'}")
        print(f"  Errors: {len(results['errors'])}")
        
        # Test tools
        print(f"✓ Agent initialized with {len(agent.tools)} tools:")
        for tool in agent.tools:
            print(f"  - {tool.name}: {tool.description}")
        
        return True
        
    except Exception as e:
        print(f"✗ Data ingestion agent test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("Testing Weather API and Satellite Imagery Integration\n")
    
    tests = [
        test_weather_integration(),
        test_satellite_processing(),
        test_data_ingestion_agent()
    ]
    
    results = await asyncio.gather(*tests, return_exceptions=True)
    
    success_count = sum(1 for result in results if result is True)
    total_tests = len(tests)
    
    print(f"\n{'='*50}")
    print(f"Test Results: {success_count}/{total_tests} tests passed")
    
    if success_count == total_tests:
        print("✓ All weather and satellite integration tests passed!")
        return True
    else:
        print("✗ Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)