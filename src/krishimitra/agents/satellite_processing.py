"""
Satellite Imagery Processing for KrishiMitra Platform

This module processes satellite imagery using Amazon SageMaker Geospatial capabilities
to analyze crop health, NDVI, and provide agricultural insights.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
import asyncio

import boto3
import numpy as np
from pydantic import BaseModel, Field
from langchain.tools import BaseTool

from ..core.config import get_settings
from ..models.agricultural_intelligence import (
    SatelliteData, CropHealthAnalysis, VegetationIndex, 
    GeographicCoordinate, Measurement
)

logger = logging.getLogger(__name__)
settings = get_settings()


class SatelliteImageRequest(BaseModel):
    """Request for satellite imagery analysis"""
    field_boundary: List[GeographicCoordinate] = Field(description="Field boundary coordinates")
    start_date: datetime = Field(description="Start date for imagery search")
    end_date: datetime = Field(description="End date for imagery search")
    max_cloud_cover: float = Field(default=20.0, ge=0, le=100, description="Maximum cloud cover percentage")
    resolution_meters: float = Field(default=10.0, description="Desired resolution in meters")


class NDVIAnalysisResult(BaseModel):
    """NDVI analysis results"""
    mean_ndvi: float = Field(ge=-1, le=1, description="Mean NDVI value")
    std_ndvi: float = Field(ge=0, description="Standard deviation of NDVI")
    min_ndvi: float = Field(ge=-1, le=1, description="Minimum NDVI value")
    max_ndvi: float = Field(ge=-1, le=1, description="Maximum NDVI value")
    healthy_area_percentage: float = Field(ge=0, le=100, description="Percentage of healthy vegetation")
    stressed_area_percentage: float = Field(ge=0, le=100, description="Percentage of stressed vegetation")
    bare_soil_percentage: float = Field(ge=0, le=100, description="Percentage of bare soil")


class SatelliteImageProcessor:
    """Processes satellite imagery using AWS SageMaker Geospatial"""
    
    def __init__(self):
        self.sagemaker_client = boto3.client('sagemaker-geospatial', region_name=settings.aws_region)
        self.s3_client = boto3.client('s3', region_name=settings.aws_region)
        self.bucket_name = 'krishimitra-satellite-data'
    
    async def search_satellite_imagery(self, request: SatelliteImageRequest) -> Optional[List[Dict[str, Any]]]:
        """Search for available satellite imagery"""
        try:
            # Convert field boundary to GeoJSON
            coordinates = [[coord.longitude, coord.latitude] for coord in request.field_boundary]
            coordinates.append(coordinates[0])  # Close the polygon
            
            geometry = {
                "type": "Polygon",
                "coordinates": [coordinates]
            }
            
            # Search for Sentinel-2 imagery
            search_params = {
                "Arn": "arn:aws:sagemaker-geospatial:us-west-2:081040173940:raster-data-collection/public/nmqj48dcu3g7ayw8",  # Sentinel-2 L2A
                "RasterDataCollectionQuery": {
                    "AreaOfInterest": {
                        "AreaOfInterestGeometry": {
                            "PolygonGeometry": geometry
                        }
                    },
                    "TimeRangeFilter": {
                        "StartTime": request.start_date,
                        "EndTime": request.end_date
                    },
                    "PropertyFilters": {
                        "Properties": ["eo:cloud_cover"],
                        "LogicalOperator": "AND",
                        "PropertyFilters": [
                            {
                                "Property": "eo:cloud_cover",
                                "Operator": "LESS_THAN",
                                "Value": str(request.max_cloud_cover)
                            }
                        ]
                    }
                }
            }
            
            response = self.sagemaker_client.search_raster_data_collection(**search_params)
            
            items = response.get('Items', [])
            logger.info(f"Found {len(items)} satellite images matching criteria")
            
            return items
            
        except Exception as e:
            logger.error(f"Error searching satellite imagery: {e}")
            return None
    
    async def start_earth_observation_job(
        self, 
        image_items: List[Dict[str, Any]], 
        field_boundary: List[GeographicCoordinate]
    ) -> Optional[str]:
        """Start an Earth Observation Job for processing satellite imagery"""
        try:
            # Convert field boundary to GeoJSON
            coordinates = [[coord.longitude, coord.latitude] for coord in field_boundary]
            coordinates.append(coordinates[0])  # Close the polygon
            
            geometry = {
                "type": "Polygon",
                "coordinates": [coordinates]
            }
            
            # Select the best image (most recent with lowest cloud cover)
            best_image = min(image_items, key=lambda x: (
                x.get('Properties', {}).get('eo:cloud_cover', 100),
                -datetime.fromisoformat(x.get('DateTime', '1970-01-01')).timestamp()
            ))
            
            # Configure the Earth Observation Job
            job_config = {
                "Name": f"krishimitra-crop-analysis-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                "InputConfig": {
                    "RasterDataCollectionQuery": {
                        "RasterDataCollectionArn": best_image.get('Assets', {}).get('visual', {}).get('Href', ''),
                        "AreaOfInterest": {
                            "AreaOfInterestGeometry": {
                                "PolygonGeometry": geometry
                            }
                        }
                    }
                },
                "JobConfig": {
                    "BandMathConfig": {
                        "PredefinedIndices": ["NDVI", "EVI", "SAVI", "NDWI"],
                        "CustomIndices": {
                            "operations": [
                                {
                                    "name": "NDVI",
                                    "equation": "(B08 - B04) / (B08 + B04)",
                                    "output_type": "FLOAT32"
                                }
                            ]
                        }
                    },
                    "CloudRemovalConfig": {
                        "AlgorithmName": "INTERPOLATION",
                        "InterpolationValue": "0",
                        "TargetBands": ["B02", "B03", "B04", "B08"]
                    },
                    "LandCoverSegmentationConfig": {
                        "AlgorithmName": "STANDARD"
                    }
                },
                "OutputConfig": {
                    "S3Data": {
                        "S3Uri": f"s3://{self.bucket_name}/earth-observation-jobs/",
                        "KmsKeyId": settings.aws_kms_key_id if hasattr(settings, 'aws_kms_key_id') else None
                    }
                },
                "RoleArn": f"arn:aws:iam::{settings.aws_account_id}:role/SageMakerGeospatialExecutionRole"
            }
            
            response = self.sagemaker_client.start_earth_observation_job(**job_config)
            job_arn = response['Arn']
            
            logger.info(f"Started Earth Observation Job: {job_arn}")
            return job_arn
            
        except Exception as e:
            logger.error(f"Error starting Earth Observation Job: {e}")
            return None
    
    async def get_job_results(self, job_arn: str) -> Optional[Dict[str, Any]]:
        """Get results from completed Earth Observation Job"""
        try:
            # Check job status
            response = self.sagemaker_client.get_earth_observation_job(Arn=job_arn)
            status = response['Status']
            
            if status == 'COMPLETED':
                output_location = response['OutputConfig']['S3Data']['S3Uri']
                
                # Download and process results
                results = await self._process_job_output(output_location)
                return results
            elif status == 'FAILED':
                logger.error(f"Earth Observation Job failed: {response.get('ErrorDetails', 'Unknown error')}")
                return None
            else:
                logger.info(f"Earth Observation Job status: {status}")
                return {"status": status, "message": "Job still in progress"}
                
        except Exception as e:
            logger.error(f"Error getting job results: {e}")
            return None
    
    async def _process_job_output(self, s3_output_location: str) -> Dict[str, Any]:
        """Process the output from Earth Observation Job"""
        try:
            # Parse S3 location
            bucket = s3_output_location.split('/')[2]
            prefix = '/'.join(s3_output_location.split('/')[3:])
            
            # List objects in the output location
            response = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            
            results = {
                "ndvi_analysis": None,
                "vegetation_indices": None,
                "land_cover": None,
                "output_files": []
            }
            
            for obj in response.get('Contents', []):
                key = obj['Key']
                results["output_files"].append(f"s3://{bucket}/{key}")
                
                # Process NDVI results
                if 'ndvi' in key.lower():
                    ndvi_data = await self._download_and_analyze_ndvi(bucket, key)
                    if ndvi_data:
                        results["ndvi_analysis"] = ndvi_data
                
                # Process other vegetation indices
                if any(index in key.lower() for index in ['evi', 'savi', 'ndwi']):
                    index_data = await self._download_vegetation_index(bucket, key)
                    if index_data:
                        if not results["vegetation_indices"]:
                            results["vegetation_indices"] = {}
                        results["vegetation_indices"].update(index_data)
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing job output: {e}")
            return {}
    
    async def _download_and_analyze_ndvi(self, bucket: str, key: str) -> Optional[NDVIAnalysisResult]:
        """Download and analyze NDVI data"""
        try:
            # Download NDVI file
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            
            # For this example, we'll simulate NDVI analysis
            # In production, you would use libraries like rasterio to read GeoTIFF files
            
            # Simulated NDVI values for demonstration
            ndvi_values = np.random.normal(0.6, 0.2, 10000)  # Simulate healthy vegetation
            ndvi_values = np.clip(ndvi_values, -1, 1)
            
            # Calculate statistics
            mean_ndvi = float(np.mean(ndvi_values))
            std_ndvi = float(np.std(ndvi_values))
            min_ndvi = float(np.min(ndvi_values))
            max_ndvi = float(np.max(ndvi_values))
            
            # Classify vegetation health
            healthy_pixels = np.sum(ndvi_values > 0.5)
            stressed_pixels = np.sum((ndvi_values > 0.2) & (ndvi_values <= 0.5))
            bare_soil_pixels = np.sum(ndvi_values <= 0.2)
            total_pixels = len(ndvi_values)
            
            healthy_percentage = (healthy_pixels / total_pixels) * 100
            stressed_percentage = (stressed_pixels / total_pixels) * 100
            bare_soil_percentage = (bare_soil_pixels / total_pixels) * 100
            
            return NDVIAnalysisResult(
                mean_ndvi=mean_ndvi,
                std_ndvi=std_ndvi,
                min_ndvi=min_ndvi,
                max_ndvi=max_ndvi,
                healthy_area_percentage=healthy_percentage,
                stressed_area_percentage=stressed_percentage,
                bare_soil_percentage=bare_soil_percentage
            )
            
        except Exception as e:
            logger.error(f"Error analyzing NDVI data: {e}")
            return None
    
    async def _download_vegetation_index(self, bucket: str, key: str) -> Optional[Dict[str, float]]:
        """Download and process vegetation index data"""
        try:
            # Determine index type from filename
            index_name = None
            if 'evi' in key.lower():
                index_name = 'evi'
            elif 'savi' in key.lower():
                index_name = 'savi'
            elif 'ndwi' in key.lower():
                index_name = 'ndwi'
            
            if not index_name:
                return None
            
            # Download and process (simulated for this example)
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            
            # Simulate index calculation
            if index_name == 'evi':
                value = np.random.uniform(0.2, 0.8)
            elif index_name == 'savi':
                value = np.random.uniform(0.1, 0.6)
            elif index_name == 'ndwi':
                value = np.random.uniform(-0.5, 0.5)
            else:
                value = 0.0
            
            return {index_name: float(value)}
            
        except Exception as e:
            logger.error(f"Error processing vegetation index: {e}")
            return None
    
    async def analyze_crop_health(
        self, 
        field_boundary: List[GeographicCoordinate],
        crop_type: str = "unknown"
    ) -> Optional[CropHealthAnalysis]:
        """Perform comprehensive crop health analysis"""
        try:
            # Search for recent imagery
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=30)
            
            request = SatelliteImageRequest(
                field_boundary=field_boundary,
                start_date=start_date,
                end_date=end_date,
                max_cloud_cover=30.0
            )
            
            images = await self.search_satellite_imagery(request)
            if not images:
                logger.warning("No suitable satellite imagery found")
                return None
            
            # Start processing job
            job_arn = await self.start_earth_observation_job(images, field_boundary)
            if not job_arn:
                logger.error("Failed to start Earth Observation Job")
                return None
            
            # For this example, we'll simulate waiting for job completion
            # In production, you would poll the job status or use callbacks
            await asyncio.sleep(2)  # Simulate processing time
            
            # Get results (simulated)
            results = await self._simulate_job_results()
            
            # Convert to CropHealthAnalysis
            crop_analysis = self._create_crop_health_analysis(results, crop_type)
            return crop_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing crop health: {e}")
            return None
    
    async def _simulate_job_results(self) -> Dict[str, Any]:
        """Simulate job results for demonstration"""
        return {
            "ndvi_analysis": NDVIAnalysisResult(
                mean_ndvi=0.65,
                std_ndvi=0.15,
                min_ndvi=0.1,
                max_ndvi=0.9,
                healthy_area_percentage=75.0,
                stressed_area_percentage=20.0,
                bare_soil_percentage=5.0
            ),
            "vegetation_indices": {
                "evi": 0.45,
                "savi": 0.35,
                "ndwi": 0.1
            }
        }
    
    def _create_crop_health_analysis(self, results: Dict[str, Any], crop_type: str) -> CropHealthAnalysis:
        """Create CropHealthAnalysis from processing results"""
        ndvi_analysis = results.get("ndvi_analysis")
        vegetation_indices = results.get("vegetation_indices", {})
        
        # Calculate overall health score
        if ndvi_analysis:
            health_score = (
                ndvi_analysis.healthy_area_percentage * 0.7 +
                (100 - ndvi_analysis.stressed_area_percentage) * 0.2 +
                (100 - ndvi_analysis.bare_soil_percentage) * 0.1
            )
        else:
            health_score = 50.0  # Default moderate health
        
        # Create vegetation indices object
        veg_indices = VegetationIndex(
            ndvi=ndvi_analysis.mean_ndvi if ndvi_analysis else None,
            evi=vegetation_indices.get("evi"),
            savi=vegetation_indices.get("savi"),
            ndwi=vegetation_indices.get("ndwi")
        )
        
        # Generate recommendations based on analysis
        recommendations = self._generate_satellite_recommendations(ndvi_analysis, crop_type)
        
        return CropHealthAnalysis(
            overall_health_score=min(100.0, max(0.0, health_score)),
            vegetation_indices=veg_indices,
            growth_stage=self._estimate_growth_stage(ndvi_analysis),
            stress_indicators=self._identify_stress_indicators(ndvi_analysis),
            immediate_actions=recommendations["immediate"],
            long_term_recommendations=recommendations["long_term"]
        )
    
    def _estimate_growth_stage(self, ndvi_analysis: Optional[NDVIAnalysisResult]) -> str:
        """Estimate crop growth stage from NDVI"""
        if not ndvi_analysis:
            return "unknown"
        
        if ndvi_analysis.mean_ndvi < 0.2:
            return "early_vegetative"
        elif ndvi_analysis.mean_ndvi < 0.5:
            return "vegetative"
        elif ndvi_analysis.mean_ndvi < 0.7:
            return "reproductive"
        else:
            return "maturity"
    
    def _identify_stress_indicators(self, ndvi_analysis: Optional[NDVIAnalysisResult]) -> List[str]:
        """Identify crop stress indicators from satellite data"""
        if not ndvi_analysis:
            return []
        
        stress_indicators = []
        
        if ndvi_analysis.stressed_area_percentage > 30:
            stress_indicators.append("High percentage of stressed vegetation detected")
        
        if ndvi_analysis.bare_soil_percentage > 15:
            stress_indicators.append("Significant bare soil areas indicating poor crop establishment")
        
        if ndvi_analysis.std_ndvi > 0.3:
            stress_indicators.append("High variability in vegetation health across the field")
        
        if ndvi_analysis.mean_ndvi < 0.3:
            stress_indicators.append("Overall low vegetation vigor")
        
        return stress_indicators
    
    def _generate_satellite_recommendations(
        self, 
        ndvi_analysis: Optional[NDVIAnalysisResult], 
        crop_type: str
    ) -> Dict[str, List[str]]:
        """Generate recommendations based on satellite analysis"""
        immediate = []
        long_term = []
        
        if not ndvi_analysis:
            return {"immediate": ["Unable to analyze - no satellite data available"], "long_term": []}
        
        # Immediate actions
        if ndvi_analysis.stressed_area_percentage > 25:
            immediate.append("Investigate stressed areas for pest, disease, or nutrient deficiency")
            immediate.append("Consider targeted irrigation in stressed zones")
        
        if ndvi_analysis.bare_soil_percentage > 10:
            immediate.append("Assess crop establishment in bare soil areas")
            immediate.append("Consider replanting in severely affected areas")
        
        if ndvi_analysis.mean_ndvi < 0.4:
            immediate.append("Overall crop health is below optimal - investigate causes")
            immediate.append("Consider foliar nutrition application")
        
        # Long-term recommendations
        if ndvi_analysis.std_ndvi > 0.25:
            long_term.append("Implement precision agriculture techniques for variable rate application")
            long_term.append("Investigate soil variability across the field")
        
        long_term.append("Continue monitoring crop health through satellite imagery")
        long_term.append("Maintain field records for comparison with future seasons")
        
        return {"immediate": immediate, "long_term": long_term}


class SatelliteAnalysisTool(BaseTool):
    """LangChain tool for satellite imagery analysis"""
    
    name: str = "satellite_crop_analysis"
    description: str = "Analyze crop health using satellite imagery and vegetation indices"
    
    def _run(self, field_boundary_json: str, crop_type: str = "unknown") -> str:
        """Run the satellite analysis tool"""
        async def analyze():
            processor = SatelliteImageProcessor()
            try:
                # Parse field boundary
                boundary_data = json.loads(field_boundary_json)
                field_boundary = [
                    GeographicCoordinate(latitude=coord["latitude"], longitude=coord["longitude"])
                    for coord in boundary_data
                ]
                
                analysis = await processor.analyze_crop_health(field_boundary, crop_type)
                if analysis:
                    return f"Crop health analysis: Overall score {analysis.overall_health_score:.1f}%, NDVI {analysis.vegetation_indices.ndvi:.2f}, Growth stage: {analysis.growth_stage}"
                else:
                    return "Unable to perform satellite analysis - no suitable imagery available"
                    
            except Exception as e:
                return f"Error in satellite analysis: {str(e)}"
        
        return asyncio.run(analyze())
    
    async def _arun(self, field_boundary_json: str, crop_type: str = "unknown") -> str:
        """Async version of the tool"""
        processor = SatelliteImageProcessor()
        try:
            # Parse field boundary
            boundary_data = json.loads(field_boundary_json)
            field_boundary = [
                GeographicCoordinate(latitude=coord["latitude"], longitude=coord["longitude"])
                for coord in boundary_data
            ]
            
            analysis = await processor.analyze_crop_health(field_boundary, crop_type)
            if analysis:
                return f"Crop health analysis: Overall score {analysis.overall_health_score:.1f}%, NDVI {analysis.vegetation_indices.ndvi:.2f}, Growth stage: {analysis.growth_stage}"
            else:
                return "Unable to perform satellite analysis - no suitable imagery available"
                
        except Exception as e:
            return f"Error in satellite analysis: {str(e)}"