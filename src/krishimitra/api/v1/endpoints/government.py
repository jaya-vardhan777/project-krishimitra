"""
Government Integration API Endpoints

This module provides FastAPI endpoints for government scheme identification,
eligibility assessment, and application tracking.
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from ....agents.government_integration import (
    GovernmentSchemeAgent,
    GovernmentScheme,
    FarmerEligibility,
    SchemeApplication,
    SchemeCategory,
    SchemeEligibilityStatus
)
from ....models.farmer import FarmerProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/government", tags=["government"])


# Request/Response Models
class SchemeIdentificationRequest(BaseModel):
    """Request model for scheme identification"""
    farmer_id: str = Field(..., description="Farmer's unique ID")
    min_eligibility_score: float = Field(default=50.0, ge=0, le=100, description="Minimum eligibility score")


class SchemeIdentificationResponse(BaseModel):
    """Response model for scheme identification"""
    farmer_id: str
    schemes_found: int
    schemes: List[Dict[str, Any]]


class EligibilityAssessmentRequest(BaseModel):
    """Request model for eligibility assessment"""
    farmer_id: str = Field(..., description="Farmer's unique ID")
    scheme_id: str = Field(..., description="Scheme ID to assess")


class ApplicationCreateRequest(BaseModel):
    """Request model for creating an application"""
    farmer_id: str = Field(..., description="Farmer's unique ID")
    scheme_id: str = Field(..., description="Scheme ID")
    documents: List[str] = Field(default_factory=list, description="List of submitted documents")


class ApplicationStatusResponse(BaseModel):
    """Response model for application status"""
    application_id: str
    farmer_id: str
    scheme_id: str
    application_status: str
    verification_status: str
    approval_status: str
    submitted_at: Optional[str]
    last_updated: str


class ApplicationGuidanceResponse(BaseModel):
    """Response model for application guidance"""
    scheme_name: str
    application_process: str
    required_documents: List[str]
    application_url: Optional[str]
    contact_info: Dict[str, str]
    steps: List[str]
    tips: List[str]


# Endpoints
@router.post("/schemes/identify", response_model=SchemeIdentificationResponse)
async def identify_applicable_schemes(
    request: SchemeIdentificationRequest,
    background_tasks: BackgroundTasks
):
    """
    Identify applicable government schemes for a farmer
    
    This endpoint analyzes the farmer's profile and identifies all government schemes
    they may be eligible for, along with eligibility assessments.
    """
    try:
        agent = GovernmentSchemeAgent()
        
        # Create farmer profile (in production, fetch from database)
        farmer_profile = {
            "farmer_id": request.farmer_id,
            "personal_info": {
                "location": {
                    "state": "Maharashtra"  # Should be fetched from farmer profile
                }
            },
            "farm_details": {
                "total_land_area": 2.0
            },
            "documents": ["Aadhaar card", "Bank account details"]
        }
        
        # Identify schemes
        schemes = await agent.identify_applicable_schemes(farmer_profile)
        
        # Filter by minimum score
        filtered_schemes = [
            s for s in schemes 
            if s.get("eligibility_score", 0) >= request.min_eligibility_score
        ]
        
        logger.info(f"Identified {len(filtered_schemes)} schemes for farmer {request.farmer_id}")
        
        return SchemeIdentificationResponse(
            farmer_id=request.farmer_id,
            schemes_found=len(filtered_schemes),
            schemes=filtered_schemes
        )
        
    except Exception as e:
        logger.error(f"Error identifying schemes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schemes/{scheme_id}")
async def get_scheme_details(scheme_id: str):
    """
    Get detailed information about a specific government scheme
    
    Returns comprehensive information including benefits, eligibility criteria,
    required documents, and application process.
    """
    try:
        agent = GovernmentSchemeAgent()
        scheme = agent.get_scheme_details(scheme_id)
        
        if not scheme:
            raise HTTPException(status_code=404, detail=f"Scheme {scheme_id} not found")
        
        return scheme.dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting scheme details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schemes")
async def list_schemes(
    category: Optional[str] = None,
    state: Optional[str] = None
):
    """
    List available government schemes with optional filters
    
    Supports filtering by category (subsidy, insurance, credit, etc.) and state.
    """
    try:
        agent = GovernmentSchemeAgent()
        
        if category:
            try:
                category_enum = SchemeCategory(category.lower())
                schemes = agent.scheme_db.get_schemes_by_category(category_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
        elif state:
            schemes = agent.scheme_db.get_schemes_by_state(state)
        else:
            schemes = agent.scheme_db.get_all_schemes()
        
        return {
            "total_schemes": len(schemes),
            "schemes": [s.dict() for s in schemes]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing schemes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/eligibility/assess")
async def assess_eligibility(request: EligibilityAssessmentRequest):
    """
    Assess farmer eligibility for a specific scheme
    
    Provides detailed eligibility assessment including matched/unmatched criteria,
    missing documents, and recommendations.
    """
    try:
        agent = GovernmentSchemeAgent()
        
        # Create farmer profile (in production, fetch from database)
        farmer_profile = {
            "farmer_id": request.farmer_id,
            "personal_info": {
                "location": {
                    "state": "Maharashtra"
                }
            },
            "farm_details": {
                "total_land_area": 2.0
            },
            "documents": ["Aadhaar card", "Bank account details"]
        }
        
        eligibility = agent.assess_scheme_eligibility(farmer_profile, request.scheme_id)
        
        if not eligibility:
            raise HTTPException(status_code=404, detail=f"Scheme {request.scheme_id} not found")
        
        return eligibility.dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assessing eligibility: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/applications", response_model=ApplicationStatusResponse)
async def create_application(request: ApplicationCreateRequest):
    """
    Create a new scheme application
    
    Initiates a new application for a government scheme with the provided documents.
    """
    try:
        agent = GovernmentSchemeAgent()
        
        application = agent.create_scheme_application(
            request.farmer_id,
            request.scheme_id,
            request.documents
        )
        
        if not application:
            raise HTTPException(status_code=500, detail="Failed to create application")
        
        return ApplicationStatusResponse(
            application_id=application.application_id,
            farmer_id=application.farmer_id,
            scheme_id=application.scheme_id,
            application_status=application.application_status,
            verification_status=application.verification_status,
            approval_status=application.approval_status,
            submitted_at=application.submitted_at,
            last_updated=application.last_updated
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating application: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/applications/{application_id}/submit")
async def submit_application(application_id: str):
    """
    Submit a scheme application
    
    Submits a draft application for processing and verification.
    """
    try:
        agent = GovernmentSchemeAgent()
        
        success = agent.submit_scheme_application(application_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
        
        return {"message": "Application submitted successfully", "application_id": application_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting application: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/applications/{application_id}", response_model=ApplicationStatusResponse)
async def get_application_status(application_id: str):
    """
    Get application status
    
    Retrieves the current status of a scheme application including verification
    and approval status.
    """
    try:
        agent = GovernmentSchemeAgent()
        
        application = agent.get_application_status(application_id)
        
        if not application:
            raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
        
        return ApplicationStatusResponse(
            application_id=application.application_id,
            farmer_id=application.farmer_id,
            scheme_id=application.scheme_id,
            application_status=application.application_status,
            verification_status=application.verification_status,
            approval_status=application.approval_status,
            submitted_at=application.submitted_at,
            last_updated=application.last_updated
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting application status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/applications/farmer/{farmer_id}")
async def get_farmer_applications(farmer_id: str):
    """
    Get all applications for a farmer
    
    Returns all scheme applications submitted by a specific farmer.
    """
    try:
        agent = GovernmentSchemeAgent()
        
        applications = agent.get_farmer_applications(farmer_id)
        
        return {
            "farmer_id": farmer_id,
            "total_applications": len(applications),
            "applications": [app.dict() for app in applications]
        }
        
    except Exception as e:
        logger.error(f"Error getting farmer applications: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schemes/{scheme_id}/guidance", response_model=ApplicationGuidanceResponse)
async def get_application_guidance(scheme_id: str):
    """
    Get step-by-step application guidance
    
    Provides detailed guidance on how to apply for a specific scheme including
    required documents, steps, and tips.
    """
    try:
        agent = GovernmentSchemeAgent()
        
        guidance = agent.provide_application_guidance(scheme_id)
        
        if "error" in guidance:
            raise HTTPException(status_code=404, detail=guidance["error"])
        
        return ApplicationGuidanceResponse(**guidance)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting application guidance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data/pmkisan/{farmer_id}")
async def get_pmkisan_status(farmer_id: str, aadhaar: Optional[str] = None):
    """
    Get PM-KISAN enrollment and payment status
    
    Retrieves the farmer's PM-KISAN enrollment status, installments received,
    and payment history.
    """
    try:
        from ....agents.government_integration import GovernmentAPIClient
        
        client = GovernmentAPIClient()
        status = await client.get_pmkisan_status(farmer_id, aadhaar or "")
        
        if not status:
            raise HTTPException(status_code=404, detail=f"PM-KISAN data not found for farmer {farmer_id}")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting PM-KISAN status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data/soil-health/{farmer_id}")
async def get_soil_health_card(farmer_id: str):
    """
    Get soil health card information
    
    Retrieves the farmer's soil health card data including pH, nutrients,
    and recommendations.
    """
    try:
        from ....agents.government_integration import GovernmentAPIClient
        
        client = GovernmentAPIClient()
        soil_data = await client.get_soil_health_card(farmer_id, {})
        
        if not soil_data:
            raise HTTPException(status_code=404, detail=f"Soil health card not found for farmer {farmer_id}")
        
        return soil_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting soil health card: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data/insurance/{farmer_id}")
async def get_crop_insurance_status(farmer_id: str, season: str = "Kharif2024"):
    """
    Get crop insurance enrollment and claim status
    
    Retrieves the farmer's crop insurance policy details, coverage, and claim status.
    """
    try:
        from ....agents.government_integration import GovernmentAPIClient
        
        client = GovernmentAPIClient()
        insurance_data = await client.get_crop_insurance_status(farmer_id, season)
        
        if not insurance_data:
            raise HTTPException(status_code=404, detail=f"Insurance data not found for farmer {farmer_id}")
        
        return insurance_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting crop insurance status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
