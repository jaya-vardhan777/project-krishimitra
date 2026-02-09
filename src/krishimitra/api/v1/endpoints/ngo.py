"""
NGO Integration API Endpoints

This module provides FastAPI endpoints for NGO service connection, coordination,
and impact measurement.
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from ....agents.ngo_integration import (
    NGOIntegrationAgent,
    NGOProfile,
    NGOService,
    FarmerNGOConnection,
    ImpactMeasurement,
    NGOServiceCategory,
    NGOVerificationStatus
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ngo", tags=["ngo"])


# Request/Response Models
class NGOSearchRequest(BaseModel):
    """Request model for NGO search"""
    farmer_id: str = Field(..., description="Farmer's unique ID")
    state: Optional[str] = Field(None, description="State to search in")
    category: Optional[str] = Field(None, description="Service category")
    service_needs: Optional[List[str]] = Field(None, description="Specific service needs")
    min_rating: float = Field(default=0.0, ge=0, le=5, description="Minimum rating")


class NGOSearchResponse(BaseModel):
    """Response model for NGO search"""
    farmer_id: str
    ngos_found: int
    ngos: List[Dict[str, Any]]


class NGOConnectionRequest(BaseModel):
    """Request model for creating NGO connection"""
    farmer_id: str = Field(..., description="Farmer's unique ID")
    ngo_id: str = Field(..., description="NGO ID")
    service_id: Optional[str] = Field(None, description="Specific service ID")
    connection_type: str = Field(default="service_inquiry", description="Type of connection")


class NGOConnectionResponse(BaseModel):
    """Response model for NGO connection"""
    connection_id: str
    farmer_id: str
    ngo_id: str
    service_id: Optional[str]
    connection_type: str
    status: str
    initiated_at: str


class ImpactReportRequest(BaseModel):
    """Request model for impact measurement"""
    ngo_id: str = Field(..., description="NGO ID")
    service_id: Optional[str] = Field(None, description="Service ID")
    measurement_period: str = Field(..., description="Measurement period")
    farmers_reached: int = Field(default=0, description="Number of farmers reached")
    farmers_benefited: int = Field(default=0, description="Number of farmers benefited")
    satisfaction_score: float = Field(default=0.0, ge=0, le=5, description="Average satisfaction")
    income_improvement: Optional[float] = Field(None, description="Average income improvement %")
    yield_improvement: Optional[float] = Field(None, description="Average yield improvement %")
    adoption_rate: Optional[float] = Field(None, description="Technology/practice adoption rate %")
    sustainability_score: float = Field(default=0.0, ge=0, le=5, description="Sustainability score")
    key_achievements: List[str] = Field(default_factory=list, description="Key achievements")
    challenges: List[str] = Field(default_factory=list, description="Challenges faced")


# Endpoints
@router.post("/search", response_model=NGOSearchResponse)
async def search_ngos(request: NGOSearchRequest):
    """
    Search for NGOs based on farmer needs and location
    
    This endpoint finds relevant NGOs operating in the farmer's region that
    provide services matching their needs.
    """
    try:
        agent = NGOIntegrationAgent()
        
        # Create farmer profile
        farmer_profile = {
            "farmer_id": request.farmer_id,
            "personal_info": {
                "location": {
                    "state": request.state or "Maharashtra"
                }
            }
        }
        
        # Find relevant NGOs
        if request.service_needs:
            matches = agent.find_relevant_ngos(farmer_profile, request.service_needs)
        else:
            matches = agent.find_relevant_ngos(farmer_profile)
        
        # Filter by rating if specified
        if request.min_rating > 0:
            matches = [m for m in matches if m.get("ngo", {}).rating >= request.min_rating]
        
        # Filter by category if specified
        if request.category:
            try:
                category_enum = NGOServiceCategory(request.category.lower())
                matches = [
                    m for m in matches 
                    if category_enum in m.get("ngo", {}).service_categories
                ]
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid category: {request.category}")
        
        logger.info(f"Found {len(matches)} NGOs for farmer {request.farmer_id}")
        
        return NGOSearchResponse(
            farmer_id=request.farmer_id,
            ngos_found=len(matches),
            ngos=matches
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching NGOs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_ngos(
    region: Optional[str] = None,
    category: Optional[str] = None,
    min_rating: float = 0.0,
    verified_only: bool = True
):
    """
    List available NGOs with optional filters
    
    Supports filtering by region, service category, rating, and verification status.
    """
    try:
        agent = NGOIntegrationAgent()
        
        # Parse category if provided
        category_enum = None
        if category:
            try:
                category_enum = NGOServiceCategory(category.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
        
        # Search NGOs
        ngos = agent.ngo_db.search_ngos(
            region=region,
            category=category_enum,
            min_rating=min_rating
        )
        
        # Filter verified only if requested
        if verified_only:
            ngos = [ngo for ngo in ngos if ngo.verification_status == NGOVerificationStatus.VERIFIED]
        
        return {
            "total_ngos": len(ngos),
            "ngos": [ngo.dict() for ngo in ngos]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing NGOs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ngo_id}")
async def get_ngo_details(ngo_id: str):
    """
    Get detailed information about a specific NGO
    
    Returns comprehensive NGO profile including services, impact metrics,
    and contact information.
    """
    try:
        agent = NGOIntegrationAgent()
        
        ngo_details = agent.get_ngo_details(ngo_id)
        
        if not ngo_details:
            raise HTTPException(status_code=404, detail=f"NGO {ngo_id} not found")
        
        return ngo_details
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting NGO details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connect", response_model=NGOConnectionResponse)
async def connect_farmer_to_ngo(
    request: NGOConnectionRequest,
    background_tasks: BackgroundTasks
):
    """
    Create a connection between farmer and NGO
    
    Initiates a connection for service inquiry or enrollment.
    """
    try:
        agent = NGOIntegrationAgent()
        
        connection = agent.connect_farmer_to_ngo(
            request.farmer_id,
            request.ngo_id,
            request.service_id
        )
        
        if not connection:
            raise HTTPException(status_code=500, detail="Failed to create connection")
        
        # Send notification in background
        background_tasks.add_task(
            _send_connection_notification,
            connection.connection_id,
            request.farmer_id,
            request.ngo_id
        )
        
        return NGOConnectionResponse(
            connection_id=connection.connection_id,
            farmer_id=connection.farmer_id,
            ngo_id=connection.ngo_id,
            service_id=connection.service_id,
            connection_type=connection.connection_type,
            status=connection.status,
            initiated_at=connection.initiated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error connecting farmer to NGO: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connections/farmer/{farmer_id}")
async def get_farmer_connections(farmer_id: str):
    """
    Get all NGO connections for a farmer
    
    Returns all active and past connections between the farmer and NGOs.
    """
    try:
        agent = NGOIntegrationAgent()
        
        connections = agent.get_farmer_ngo_connections(farmer_id)
        
        return {
            "farmer_id": farmer_id,
            "total_connections": len(connections),
            "connections": connections
        }
        
    except Exception as e:
        logger.error(f"Error getting farmer connections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connections/{connection_id}")
async def get_connection_details(connection_id: str):
    """
    Get details of a specific connection
    
    Returns the current status and history of a farmer-NGO connection.
    """
    try:
        agent = NGOIntegrationAgent()
        
        connection = agent.connection_manager.get_connection(connection_id)
        
        if not connection:
            raise HTTPException(status_code=404, detail=f"Connection {connection_id} not found")
        
        # Get NGO details
        ngo = agent.ngo_db.get_ngo(connection.ngo_id)
        
        return {
            "connection": connection.dict(),
            "ngo": ngo.dict() if ngo else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting connection details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/connections/{connection_id}/status")
async def update_connection_status(
    connection_id: str,
    status: str,
    note: Optional[str] = None
):
    """
    Update the status of a connection
    
    Updates the connection status (e.g., active, completed, cancelled) with optional notes.
    """
    try:
        agent = NGOIntegrationAgent()
        
        success = agent.connection_manager.update_connection_status(
            connection_id,
            status,
            note
        )
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Connection {connection_id} not found")
        
        return {"message": "Connection status updated successfully", "connection_id": connection_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating connection status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/impact/record")
async def record_impact_measurement(request: ImpactReportRequest):
    """
    Record impact measurement for an NGO program
    
    Records the impact metrics of an NGO's program including farmers reached,
    satisfaction scores, and outcome improvements.
    """
    try:
        agent = NGOIntegrationAgent()
        
        # Create impact measurement
        from datetime import datetime
        measurement_id = f"impact:{request.ngo_id}:{datetime.now().timestamp()}"
        
        impact = ImpactMeasurement(
            measurement_id=measurement_id,
            ngo_id=request.ngo_id,
            service_id=request.service_id,
            measurement_period=request.measurement_period,
            farmers_reached=request.farmers_reached,
            farmers_benefited=request.farmers_benefited,
            satisfaction_score=request.satisfaction_score,
            income_improvement=request.income_improvement,
            yield_improvement=request.yield_improvement,
            adoption_rate=request.adoption_rate,
            sustainability_score=request.sustainability_score,
            key_achievements=request.key_achievements,
            challenges=request.challenges
        )
        
        agent.impact_tracker.record_impact(impact)
        
        return {
            "message": "Impact measurement recorded successfully",
            "measurement_id": measurement_id
        }
        
    except Exception as e:
        logger.error(f"Error recording impact measurement: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/impact/{ngo_id}")
async def get_ngo_impact(ngo_id: str):
    """
    Get impact measurements for an NGO
    
    Returns all recorded impact measurements and aggregate metrics for an NGO.
    """
    try:
        agent = NGOIntegrationAgent()
        
        # Get individual measurements
        impacts = agent.impact_tracker.get_ngo_impact(ngo_id)
        
        # Get aggregate metrics
        aggregate = agent.impact_tracker.calculate_aggregate_impact(ngo_id)
        
        return {
            "ngo_id": ngo_id,
            "total_measurements": len(impacts),
            "aggregate_impact": aggregate,
            "measurements": [impact.dict() for impact in impacts]
        }
        
    except Exception as e:
        logger.error(f"Error getting NGO impact: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def list_service_categories():
    """
    List all available NGO service categories
    
    Returns the complete list of service categories for filtering and search.
    """
    return {
        "categories": [
            {
                "value": category.value,
                "name": category.value.replace("_", " ").title()
            }
            for category in NGOServiceCategory
        ]
    }


# Helper functions
async def _send_connection_notification(connection_id: str, farmer_id: str, ngo_id: str):
    """Send notification about new connection (background task)"""
    try:
        logger.info(f"Sending connection notification for {connection_id}")
        # In production, send actual notifications via SMS/WhatsApp/Email
        # For now, just log
        logger.info(f"Notification sent for connection {connection_id}")
    except Exception as e:
        logger.error(f"Error sending connection notification: {e}")
