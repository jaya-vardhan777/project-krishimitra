"""
NGO Service Integration Agent for KrishiMitra Platform

This module implements NGO service connection, coordination, and impact measurement
for connecting farmers with local development organizations and their programs.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Set
from enum import Enum

import redis
from pydantic import BaseModel, Field, validator
from langchain.tools import BaseTool
from pydantic import BaseModel as LangChainBaseModel

from ..core.config import get_settings
from ..models.agricultural_intelligence import GeographicCoordinate

logger = logging.getLogger(__name__)
settings = get_settings()


class NGOServiceCategory(str, Enum):
    """Categories of NGO services"""
    TRAINING = "training"
    FINANCIAL_ASSISTANCE = "financial_assistance"
    MARKET_LINKAGE = "market_linkage"
    TECHNOLOGY_SUPPORT = "technology_support"
    ORGANIC_FARMING = "organic_farming"
    WOMEN_EMPOWERMENT = "women_empowerment"
    YOUTH_DEVELOPMENT = "youth_development"
    WATER_MANAGEMENT = "water_management"
    SOIL_CONSERVATION = "soil_conservation"
    LIVESTOCK_SUPPORT = "livestock_support"
    COMMUNITY_DEVELOPMENT = "community_development"


class NGOVerificationStatus(str, Enum):
    """Verification status for NGOs"""
    VERIFIED = "verified"
    PENDING = "pending"
    UNVERIFIED = "unverified"
    SUSPENDED = "suspended"


class NGOProfile(BaseModel):
    """Model for NGO profile information"""
    ngo_id: str = Field(..., description="Unique NGO identifier")
    ngo_name: str = Field(..., description="Official NGO name")
    registration_number: str = Field(..., description="Government registration number")
    verification_status: NGOVerificationStatus = Field(..., description="Verification status")
    description: str = Field(..., description="NGO description and mission")
    service_categories: List[NGOServiceCategory] = Field(default_factory=list, description="Service categories")
    services_offered: List[str] = Field(default_factory=list, description="Specific services")
    operating_regions: List[str] = Field(default_factory=list, description="States/districts of operation")
    headquarters_location: Optional[GeographicCoordinate] = Field(None, description="HQ coordinates")
    contact_info: Dict[str, str] = Field(default_factory=dict, description="Contact information")
    website: Optional[str] = Field(None, description="Website URL")
    established_year: Optional[int] = Field(None, description="Year established")
    beneficiaries_served: int = Field(default=0, description="Total beneficiaries served")
    active_programs: int = Field(default=0, description="Number of active programs")
    rating: float = Field(default=0.0, ge=0, le=5, description="Rating out of 5")
    certifications: List[str] = Field(default_factory=list, description="Certifications and accreditations")
    
    @validator('ngo_name')
    def validate_ngo_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('NGO name cannot be empty')
        return v.strip()


class NGOService(BaseModel):
    """Model for specific NGO service"""
    service_id: str = Field(..., description="Unique service identifier")
    ngo_id: str = Field(..., description="NGO providing the service")
    service_name: str = Field(..., description="Service name")
    category: NGOServiceCategory = Field(..., description="Service category")
    description: str = Field(..., description="Service description")
    eligibility_criteria: Dict[str, Any] = Field(default_factory=dict, description="Eligibility requirements")
    benefits: List[str] = Field(default_factory=list, description="Service benefits")
    duration: Optional[str] = Field(None, description="Service duration")
    cost: Optional[str] = Field(None, description="Cost (if any)")
    capacity: Optional[int] = Field(None, description="Maximum beneficiaries")
    current_enrollment: int = Field(default=0, description="Current enrollment")
    available_slots: Optional[int] = Field(None, description="Available slots")
    location: Optional[str] = Field(None, description="Service location")
    start_date: Optional[str] = Field(None, description="Service start date")
    end_date: Optional[str] = Field(None, description="Service end date")
    is_active: bool = Field(default=True, description="Whether service is currently active")


class FarmerNGOConnection(BaseModel):
    """Model for farmer-NGO connection"""
    connection_id: str = Field(..., description="Unique connection identifier")
    farmer_id: str = Field(..., description="Farmer's unique ID")
    ngo_id: str = Field(..., description="NGO's unique ID")
    service_id: Optional[str] = Field(None, description="Specific service ID")
    connection_type: str = Field(..., description="Type of connection")
    status: str = Field(..., description="Connection status")
    initiated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_interaction: str = Field(default_factory=lambda: datetime.now().isoformat())
    notes: List[str] = Field(default_factory=list, description="Connection notes")
    outcomes: List[str] = Field(default_factory=list, description="Outcomes achieved")


class ImpactMeasurement(BaseModel):
    """Model for measuring NGO program impact"""
    measurement_id: str = Field(..., description="Unique measurement identifier")
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
    measured_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class NGODatabase:
    """Database of registered NGOs and their services"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=True
        )
        self.cache_ttl = 24 * 3600  # 24 hours cache
        
        # Initialize with sample NGOs
        self._initialize_ngos()
    
    def _initialize_ngos(self):
        """Initialize database with sample NGOs"""
        ngos = [
            NGOProfile(
                ngo_id="NGO001",
                ngo_name="Digital Green Foundation",
                registration_number="DL/2008/0123456",
                verification_status=NGOVerificationStatus.VERIFIED,
                description="Empowering smallholder farmers through digital technology and community video",
                service_categories=[
                    NGOServiceCategory.TRAINING,
                    NGOServiceCategory.TECHNOLOGY_SUPPORT,
                    NGOServiceCategory.COMMUNITY_DEVELOPMENT
                ],
                services_offered=[
                    "Digital literacy training",
                    "Agricultural best practices videos",
                    "Peer-to-peer learning programs",
                    "Mobile-based extension services"
                ],
                operating_regions=["Karnataka", "Bihar", "Odisha", "Jharkhand", "Maharashtra"],
                contact_info={
                    "phone": "+91-80-41148943",
                    "email": "info@digitalgreen.org",
                    "address": "Bangalore, Karnataka"
                },
                website="https://www.digitalgreen.org",
                established_year=2008,
                beneficiaries_served=2500000,
                active_programs=15,
                rating=4.5,
                certifications=["ISO 9001:2015", "FCRA Registered"]
            ),
            NGOProfile(
                ngo_id="NGO002",
                ngo_name="PRADAN (Professional Assistance for Development Action)",
                registration_number="WB/1983/0234567",
                verification_status=NGOVerificationStatus.VERIFIED,
                description="Promoting sustainable livelihoods for rural poor through community institutions",
                service_categories=[
                    NGOServiceCategory.TRAINING,
                    NGOServiceCategory.FINANCIAL_ASSISTANCE,
                    NGOServiceCategory.WOMEN_EMPOWERMENT,
                    NGOServiceCategory.WATER_MANAGEMENT
                ],
                services_offered=[
                    "Self-help group formation",
                    "Livelihood promotion",
                    "Watershed development",
                    "Organic farming training",
                    "Women's empowerment programs"
                ],
                operating_regions=["Jharkhand", "Chhattisgarh", "Madhya Pradesh", "Odisha", "West Bengal"],
                contact_info={
                    "phone": "+91-11-41435600",
                    "email": "pradan@pradan.net",
                    "address": "New Delhi"
                },
                website="https://www.pradan.net",
                established_year=1983,
                beneficiaries_served=1000000,
                active_programs=25,
                rating=4.7,
                certifications=["FCRA Registered", "Credibility Alliance Accredited"]
            ),
            NGOProfile(
                ngo_id="NGO003",
                ngo_name="BAIF Development Research Foundation",
                registration_number="MH/1967/0345678",
                verification_status=NGOVerificationStatus.VERIFIED,
                description="Promoting sustainable tribal and rural development",
                service_categories=[
                    NGOServiceCategory.LIVESTOCK_SUPPORT,
                    NGOServiceCategory.ORGANIC_FARMING,
                    NGOServiceCategory.TRAINING,
                    NGOServiceCategory.SOIL_CONSERVATION
                ],
                services_offered=[
                    "Livestock development",
                    "Organic farming certification",
                    "Watershed management",
                    "Horticulture development",
                    "Veterinary services"
                ],
                operating_regions=["Maharashtra", "Karnataka", "Madhya Pradesh", "Rajasthan", "Gujarat"],
                contact_info={
                    "phone": "+91-20-25231661",
                    "email": "info@baif.org.in",
                    "address": "Pune, Maharashtra"
                },
                website="https://www.baif.org.in",
                established_year=1967,
                beneficiaries_served=5000000,
                active_programs=30,
                rating=4.6,
                certifications=["ISO 9001:2015", "FCRA Registered", "Niti Aayog Certified"]
            ),
            NGOProfile(
                ngo_id="NGO004",
                ngo_name="Swaminathan Research Foundation",
                registration_number="TN/1988/0456789",
                verification_status=NGOVerificationStatus.VERIFIED,
                description="Sustainable agriculture and rural development through research and extension",
                service_categories=[
                    NGOServiceCategory.TRAINING,
                    NGOServiceCategory.TECHNOLOGY_SUPPORT,
                    NGOServiceCategory.MARKET_LINKAGE,
                    NGOServiceCategory.ORGANIC_FARMING
                ],
                services_offered=[
                    "Sustainable agriculture training",
                    "Biodiversity conservation",
                    "Climate resilient farming",
                    "Market information systems",
                    "Seed banks and gene banks"
                ],
                operating_regions=["Tamil Nadu", "Puducherry", "Odisha", "Maharashtra"],
                contact_info={
                    "phone": "+91-44-22541229",
                    "email": "executivedirector@mssrf.res.in",
                    "address": "Chennai, Tamil Nadu"
                },
                website="https://www.mssrf.org",
                established_year=1988,
                beneficiaries_served=800000,
                active_programs=20,
                rating=4.8,
                certifications=["FCRA Registered", "UNESCO Recognition"]
            )
        ]
        
        # Store NGOs in Redis
        for ngo in ngos:
            self._store_ngo(ngo)
        
        logger.info(f"Initialized {len(ngos)} NGOs in database")
    
    def _store_ngo(self, ngo: NGOProfile):
        """Store NGO in Redis"""
        try:
            ngo_key = f"ngo:{ngo.ngo_id}"
            self.redis_client.setex(
                ngo_key,
                90 * 24 * 3600,  # 90 days
                json.dumps(ngo.dict())
            )
            
            # Add to category indexes
            for category in ngo.service_categories:
                category_key = f"ngos:category:{category.value}"
                self.redis_client.sadd(category_key, ngo.ngo_id)
            
            # Add to region indexes
            for region in ngo.operating_regions:
                region_key = f"ngos:region:{region}"
                self.redis_client.sadd(region_key, ngo.ngo_id)
            
            # Add to verified NGOs if verified
            if ngo.verification_status == NGOVerificationStatus.VERIFIED:
                self.redis_client.sadd("ngos:verified", ngo.ngo_id)
            
        except Exception as e:
            logger.error(f"Error storing NGO {ngo.ngo_id}: {e}")
    
    def get_ngo(self, ngo_id: str) -> Optional[NGOProfile]:
        """Retrieve an NGO by ID"""
        try:
            ngo_key = f"ngo:{ngo_id}"
            ngo_data = self.redis_client.get(ngo_key)
            
            if ngo_data:
                return NGOProfile(**json.loads(ngo_data))
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving NGO {ngo_id}: {e}")
            return None
    
    def get_ngos_by_region(self, region: str) -> List[NGOProfile]:
        """Get NGOs operating in a specific region"""
        try:
            region_key = f"ngos:region:{region}"
            ngo_ids = self.redis_client.smembers(region_key)
            
            ngos = []
            for ngo_id in ngo_ids:
                ngo = self.get_ngo(ngo_id)
                if ngo and ngo.verification_status == NGOVerificationStatus.VERIFIED:
                    ngos.append(ngo)
            
            # Sort by rating
            ngos.sort(key=lambda x: x.rating, reverse=True)
            
            return ngos
            
        except Exception as e:
            logger.error(f"Error retrieving NGOs for region {region}: {e}")
            return []
    
    def get_ngos_by_category(self, category: NGOServiceCategory) -> List[NGOProfile]:
        """Get NGOs by service category"""
        try:
            category_key = f"ngos:category:{category.value}"
            ngo_ids = self.redis_client.smembers(category_key)
            
            ngos = []
            for ngo_id in ngo_ids:
                ngo = self.get_ngo(ngo_id)
                if ngo and ngo.verification_status == NGOVerificationStatus.VERIFIED:
                    ngos.append(ngo)
            
            # Sort by rating
            ngos.sort(key=lambda x: x.rating, reverse=True)
            
            return ngos
            
        except Exception as e:
            logger.error(f"Error retrieving NGOs for category {category}: {e}")
            return []
    
    def search_ngos(
        self,
        region: Optional[str] = None,
        category: Optional[NGOServiceCategory] = None,
        min_rating: float = 0.0
    ) -> List[NGOProfile]:
        """Search NGOs with filters"""
        try:
            ngos = []
            
            if region:
                ngos = self.get_ngos_by_region(region)
            elif category:
                ngos = self.get_ngos_by_category(category)
            else:
                # Get all verified NGOs
                ngo_ids = self.redis_client.smembers("ngos:verified")
                for ngo_id in ngo_ids:
                    ngo = self.get_ngo(ngo_id)
                    if ngo:
                        ngos.append(ngo)
            
            # Apply rating filter
            if min_rating > 0:
                ngos = [ngo for ngo in ngos if ngo.rating >= min_rating]
            
            # Apply category filter if both region and category specified
            if region and category:
                ngos = [ngo for ngo in ngos if category in ngo.service_categories]
            
            return ngos
            
        except Exception as e:
            logger.error(f"Error searching NGOs: {e}")
            return []


class NGOConnectionManager:
    """Manages farmer-NGO connections and communications"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=True
        )
        self.ngo_db = NGODatabase()
    
    def create_connection(
        self,
        farmer_id: str,
        ngo_id: str,
        service_id: Optional[str] = None,
        connection_type: str = "service_inquiry"
    ) -> FarmerNGOConnection:
        """Create a new farmer-NGO connection"""
        try:
            connection_id = f"conn:{farmer_id}:{ngo_id}:{datetime.now().timestamp()}"
            
            connection = FarmerNGOConnection(
                connection_id=connection_id,
                farmer_id=farmer_id,
                ngo_id=ngo_id,
                service_id=service_id,
                connection_type=connection_type,
                status="initiated"
            )
            
            # Store connection
            self._store_connection(connection)
            
            logger.info(f"Created connection {connection_id}")
            return connection
            
        except Exception as e:
            logger.error(f"Error creating connection: {e}")
            raise
    
    def _store_connection(self, connection: FarmerNGOConnection):
        """Store connection in Redis"""
        try:
            conn_key = f"connection:{connection.connection_id}"
            self.redis_client.setex(
                conn_key,
                180 * 24 * 3600,  # 180 days
                json.dumps(connection.dict())
            )
            
            # Add to farmer's connections
            farmer_conn_key = f"farmer_connections:{connection.farmer_id}"
            self.redis_client.sadd(farmer_conn_key, connection.connection_id)
            
            # Add to NGO's connections
            ngo_conn_key = f"ngo_connections:{connection.ngo_id}"
            self.redis_client.sadd(ngo_conn_key, connection.connection_id)
            
        except Exception as e:
            logger.error(f"Error storing connection: {e}")
    
    def get_connection(self, connection_id: str) -> Optional[FarmerNGOConnection]:
        """Retrieve a connection by ID"""
        try:
            conn_key = f"connection:{connection_id}"
            conn_data = self.redis_client.get(conn_key)
            
            if conn_data:
                return FarmerNGOConnection(**json.loads(conn_data))
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving connection {connection_id}: {e}")
            return None
    
    def update_connection_status(
        self,
        connection_id: str,
        status: str,
        note: Optional[str] = None
    ) -> bool:
        """Update connection status"""
        try:
            connection = self.get_connection(connection_id)
            
            if not connection:
                return False
            
            connection.status = status
            connection.last_interaction = datetime.now().isoformat()
            
            if note:
                connection.notes.append(f"{datetime.now().isoformat()}: {note}")
            
            self._store_connection(connection)
            
            logger.info(f"Updated connection {connection_id} status to {status}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating connection status: {e}")
            return False
    
    def get_farmer_connections(self, farmer_id: str) -> List[FarmerNGOConnection]:
        """Get all connections for a farmer"""
        try:
            farmer_conn_key = f"farmer_connections:{farmer_id}"
            conn_ids = self.redis_client.smembers(farmer_conn_key)
            
            connections = []
            for conn_id in conn_ids:
                conn = self.get_connection(conn_id)
                if conn:
                    connections.append(conn)
            
            # Sort by last interaction
            connections.sort(
                key=lambda x: x.last_interaction,
                reverse=True
            )
            
            return connections
            
        except Exception as e:
            logger.error(f"Error retrieving farmer connections: {e}")
            return []
    
    def match_farmer_with_ngos(
        self,
        farmer_profile: Dict[str, Any],
        service_needs: List[str]
    ) -> List[Dict[str, Any]]:
        """Match farmer with relevant NGOs based on needs"""
        try:
            farmer_state = farmer_profile.get("personal_info", {}).get("location", {}).get("state")
            
            if not farmer_state:
                logger.warning("Farmer state not provided for NGO matching")
                return []
            
            # Get NGOs in farmer's region
            regional_ngos = self.ngo_db.get_ngos_by_region(farmer_state)
            
            matches = []
            
            for ngo in regional_ngos:
                # Calculate match score
                match_score = 0
                matched_services = []
                
                # Check service overlap
                for need in service_needs:
                    for service in ngo.services_offered:
                        if need.lower() in service.lower():
                            match_score += 20
                            matched_services.append(service)
                
                # Bonus for high rating
                match_score += ngo.rating * 10
                
                # Bonus for experience
                if ngo.beneficiaries_served > 100000:
                    match_score += 10
                
                if match_score > 0:
                    matches.append({
                        "ngo": ngo,
                        "match_score": min(match_score, 100),
                        "matched_services": matched_services
                    })
            
            # Sort by match score
            matches.sort(key=lambda x: x["match_score"], reverse=True)
            
            logger.info(f"Found {len(matches)} NGO matches for farmer")
            return matches
            
        except Exception as e:
            logger.error(f"Error matching farmer with NGOs: {e}")
            return []


class ImpactTracker:
    """Tracks and measures impact of NGO programs"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=True
        )
    
    def record_impact(self, impact: ImpactMeasurement):
        """Record impact measurement"""
        try:
            impact_key = f"impact:{impact.measurement_id}"
            self.redis_client.setex(
                impact_key,
                365 * 24 * 3600,  # 1 year
                json.dumps(impact.dict())
            )
            
            # Add to NGO's impact records
            ngo_impact_key = f"ngo_impact:{impact.ngo_id}"
            self.redis_client.sadd(ngo_impact_key, impact.measurement_id)
            
            logger.info(f"Recorded impact measurement {impact.measurement_id}")
            
        except Exception as e:
            logger.error(f"Error recording impact: {e}")
    
    def get_ngo_impact(self, ngo_id: str) -> List[ImpactMeasurement]:
        """Get all impact measurements for an NGO"""
        try:
            ngo_impact_key = f"ngo_impact:{ngo_id}"
            impact_ids = self.redis_client.smembers(ngo_impact_key)
            
            impacts = []
            for impact_id in impact_ids:
                impact_key = f"impact:{impact_id}"
                impact_data = self.redis_client.get(impact_key)
                
                if impact_data:
                    impacts.append(ImpactMeasurement(**json.loads(impact_data)))
            
            # Sort by measurement date
            impacts.sort(key=lambda x: x.measured_at, reverse=True)
            
            return impacts
            
        except Exception as e:
            logger.error(f"Error retrieving NGO impact: {e}")
            return []
    
    def calculate_aggregate_impact(self, ngo_id: str) -> Dict[str, Any]:
        """Calculate aggregate impact metrics for an NGO"""
        try:
            impacts = self.get_ngo_impact(ngo_id)
            
            if not impacts:
                return {
                    "total_farmers_reached": 0,
                    "total_farmers_benefited": 0,
                    "average_satisfaction": 0.0,
                    "average_income_improvement": 0.0,
                    "average_yield_improvement": 0.0
                }
            
            total_reached = sum(i.farmers_reached for i in impacts)
            total_benefited = sum(i.farmers_benefited for i in impacts)
            avg_satisfaction = sum(i.satisfaction_score for i in impacts) / len(impacts)
            
            income_improvements = [i.income_improvement for i in impacts if i.income_improvement is not None]
            avg_income = sum(income_improvements) / len(income_improvements) if income_improvements else 0.0
            
            yield_improvements = [i.yield_improvement for i in impacts if i.yield_improvement is not None]
            avg_yield = sum(yield_improvements) / len(yield_improvements) if yield_improvements else 0.0
            
            return {
                "total_farmers_reached": total_reached,
                "total_farmers_benefited": total_benefited,
                "average_satisfaction": round(avg_satisfaction, 2),
                "average_income_improvement": round(avg_income, 2),
                "average_yield_improvement": round(avg_yield, 2),
                "measurement_count": len(impacts)
            }
            
        except Exception as e:
            logger.error(f"Error calculating aggregate impact: {e}")
            return {}


class NGOIntegrationAgent:
    """Main agent for NGO service integration"""
    
    def __init__(self):
        self.ngo_db = NGODatabase()
        self.connection_manager = NGOConnectionManager()
        self.impact_tracker = ImpactTracker()
    
    def find_relevant_ngos(
        self,
        farmer_profile: Dict[str, Any],
        service_needs: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Find NGOs relevant to farmer's needs"""
        try:
            if service_needs:
                # Match based on specific needs
                return self.connection_manager.match_farmer_with_ngos(
                    farmer_profile,
                    service_needs
                )
            else:
                # Get all NGOs in farmer's region
                farmer_state = farmer_profile.get("personal_info", {}).get("location", {}).get("state")
                
                if not farmer_state:
                    return []
                
                ngos = self.ngo_db.get_ngos_by_region(farmer_state)
                
                return [{"ngo": ngo, "match_score": 50} for ngo in ngos]
                
        except Exception as e:
            logger.error(f"Error finding relevant NGOs: {e}")
            return []
    
    def connect_farmer_to_ngo(
        self,
        farmer_id: str,
        ngo_id: str,
        service_id: Optional[str] = None
    ) -> Optional[FarmerNGOConnection]:
        """Connect a farmer to an NGO"""
        try:
            return self.connection_manager.create_connection(
                farmer_id,
                ngo_id,
                service_id
            )
        except Exception as e:
            logger.error(f"Error connecting farmer to NGO: {e}")
            return None
    
    def get_ngo_details(self, ngo_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about an NGO including impact"""
        try:
            ngo = self.ngo_db.get_ngo(ngo_id)
            
            if not ngo:
                return None
            
            # Get impact metrics
            impact = self.impact_tracker.calculate_aggregate_impact(ngo_id)
            
            return {
                "ngo_profile": ngo.dict(),
                "impact_metrics": impact
            }
            
        except Exception as e:
            logger.error(f"Error getting NGO details: {e}")
            return None
    
    def get_farmer_ngo_connections(self, farmer_id: str) -> List[Dict[str, Any]]:
        """Get all NGO connections for a farmer"""
        try:
            connections = self.connection_manager.get_farmer_connections(farmer_id)
            
            result = []
            for conn in connections:
                ngo = self.ngo_db.get_ngo(conn.ngo_id)
                if ngo:
                    result.append({
                        "connection": conn.dict(),
                        "ngo": ngo.dict()
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting farmer NGO connections: {e}")
            return []


class NGOServiceTool(BaseTool, LangChainBaseModel):
    """LangChain tool for NGO service connection"""
    
    name: str = "ngo_service_connection"
    description: str = "Connect farmers with relevant NGO services and programs"
    
    def _run(self, farmer_id: str, state: str, service_needs: str = "") -> str:
        """Run the NGO service connection tool"""
        agent = NGOIntegrationAgent()
        
        # Create farmer profile
        farmer_profile = {
            "farmer_id": farmer_id,
            "personal_info": {
                "location": {
                    "state": state
                }
            }
        }
        
        # Parse service needs
        needs = [need.strip() for need in service_needs.split(",") if need.strip()] if service_needs else None
        
        # Find relevant NGOs
        matches = agent.find_relevant_ngos(farmer_profile, needs)
        
        if not matches:
            return f"No NGOs found in {state} matching the specified needs"
        
        response = f"Found {len(matches)} relevant NGOs in {state}:\n\n"
        for match in matches[:3]:  # Show top 3
            ngo = match["ngo"]
            score = match.get("match_score", 0)
            response += f"- {ngo.ngo_name} (Match: {score}%)\n"
            response += f"  Services: {', '.join(ngo.services_offered[:3])}\n"
            response += f"  Rating: {ngo.rating}/5.0\n"
            response += f"  Contact: {ngo.contact_info.get('phone', 'N/A')}\n\n"
        
        return response
    
    async def _arun(self, farmer_id: str, state: str, service_needs: str = "") -> str:
        """Async version of the tool"""
        return self._run(farmer_id, state, service_needs)
