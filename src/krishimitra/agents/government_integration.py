"""
Government Scheme Integration Agent for KrishiMitra Platform

This module implements government scheme identification, eligibility assessment,
and notification systems for farmers to access government benefits and programs.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Set
from enum import Enum

import httpx
import redis
from pydantic import BaseModel, Field, validator
from langchain.tools import BaseTool
from pydantic import BaseModel as LangChainBaseModel
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_aws import ChatBedrock

from ..core.config import get_settings
from ..models.agricultural_intelligence import GeographicCoordinate

logger = logging.getLogger(__name__)
settings = get_settings()


class SchemeCategory(str, Enum):
    """Categories of government schemes"""
    SUBSIDY = "subsidy"
    INSURANCE = "insurance"
    CREDIT = "credit"
    TRAINING = "training"
    INFRASTRUCTURE = "infrastructure"
    MARKET_ACCESS = "market_access"
    TECHNOLOGY = "technology"
    WELFARE = "welfare"


class SchemeEligibilityStatus(str, Enum):
    """Eligibility status for schemes"""
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    PARTIALLY_ELIGIBLE = "partially_eligible"
    PENDING_VERIFICATION = "pending_verification"


class GovernmentScheme(BaseModel):
    """Model for government scheme information"""
    scheme_id: str = Field(..., description="Unique scheme identifier")
    scheme_name: str = Field(..., description="Official scheme name")
    category: SchemeCategory = Field(..., description="Scheme category")
    description: str = Field(..., description="Scheme description")
    benefits: List[str] = Field(default_factory=list, description="List of benefits")
    eligibility_criteria: Dict[str, Any] = Field(default_factory=dict, description="Eligibility requirements")
    required_documents: List[str] = Field(default_factory=list, description="Required documents")
    application_process: str = Field(..., description="How to apply")
    application_url: Optional[str] = Field(None, description="Online application URL")
    contact_info: Dict[str, str] = Field(default_factory=dict, description="Contact information")
    valid_from: Optional[str] = Field(None, description="Scheme start date")
    valid_until: Optional[str] = Field(None, description="Scheme end date")
    implementing_agency: str = Field(..., description="Government agency")
    state_specific: bool = Field(False, description="Whether scheme is state-specific")
    applicable_states: List[str] = Field(default_factory=list, description="Applicable states")
    
    @validator('scheme_name')
    def validate_scheme_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Scheme name cannot be empty')
        return v.strip()


class FarmerEligibility(BaseModel):
    """Model for farmer eligibility assessment"""
    farmer_id: str = Field(..., description="Farmer's unique ID")
    scheme_id: str = Field(..., description="Scheme ID")
    eligibility_status: SchemeEligibilityStatus = Field(..., description="Eligibility status")
    eligibility_score: float = Field(..., ge=0, le=100, description="Eligibility score (0-100)")
    matched_criteria: List[str] = Field(default_factory=list, description="Criteria met")
    unmatched_criteria: List[str] = Field(default_factory=list, description="Criteria not met")
    missing_documents: List[str] = Field(default_factory=list, description="Missing documents")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")
    assessed_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class SchemeApplication(BaseModel):
    """Model for scheme application tracking"""
    application_id: str = Field(..., description="Unique application ID")
    farmer_id: str = Field(..., description="Farmer's unique ID")
    scheme_id: str = Field(..., description="Scheme ID")
    application_status: str = Field(..., description="Application status")
    submitted_at: Optional[str] = Field(None, description="Submission timestamp")
    documents_submitted: List[str] = Field(default_factory=list, description="Submitted documents")
    verification_status: str = Field(default="pending", description="Verification status")
    approval_status: str = Field(default="pending", description="Approval status")
    rejection_reason: Optional[str] = Field(None, description="Rejection reason if applicable")
    disbursement_status: Optional[str] = Field(None, description="Benefit disbursement status")
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())
    notes: List[str] = Field(default_factory=list, description="Application notes")


class GovernmentSchemeDatabase:
    """Database of government schemes with eligibility matching"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=True
        )
        self.cache_ttl = 24 * 3600  # 24 hours cache
        
        # Initialize with common Indian government schemes
        self._initialize_schemes()
    
    def _initialize_schemes(self):
        """Initialize database with common government schemes"""
        schemes = [
            GovernmentScheme(
                scheme_id="PM-KISAN",
                scheme_name="Pradhan Mantri Kisan Samman Nidhi",
                category=SchemeCategory.SUBSIDY,
                description="Direct income support of ₹6000 per year to all farmer families",
                benefits=[
                    "₹6000 per year in three equal installments",
                    "Direct bank transfer",
                    "No application fee"
                ],
                eligibility_criteria={
                    "land_ownership": "Must own cultivable land",
                    "family_definition": "Husband, wife and minor children",
                    "exclusions": ["Institutional landholders", "Income tax payers"]
                },
                required_documents=[
                    "Aadhaar card",
                    "Bank account details",
                    "Land ownership documents"
                ],
                application_process="Apply online at pmkisan.gov.in or through Common Service Centers",
                application_url="https://pmkisan.gov.in/",
                implementing_agency="Ministry of Agriculture and Farmers Welfare",
                contact_info={"helpline": "155261", "email": "pmkisan-ict@gov.in"},
                state_specific=False,
                applicable_states=[]
            ),
            GovernmentScheme(
                scheme_id="PMFBY",
                scheme_name="Pradhan Mantri Fasal Bima Yojana",
                category=SchemeCategory.INSURANCE,
                description="Crop insurance scheme providing financial support to farmers in case of crop failure",
                benefits=[
                    "Comprehensive risk insurance",
                    "Coverage for all stages of crop cycle",
                    "Low premium rates (2% for Kharif, 1.5% for Rabi)",
                    "Quick claim settlement"
                ],
                eligibility_criteria={
                    "farmer_type": "All farmers including sharecroppers and tenant farmers",
                    "crop_coverage": "Notified crops in notified areas",
                    "enrollment": "Must enroll before sowing season"
                },
                required_documents=[
                    "Aadhaar card",
                    "Bank account details",
                    "Land records or tenancy agreement",
                    "Sowing certificate"
                ],
                application_process="Apply through banks, CSCs, or online portal",
                application_url="https://pmfby.gov.in/",
                implementing_agency="Ministry of Agriculture and Farmers Welfare",
                contact_info={"helpline": "18001801551", "email": "pmfby@gov.in"},
                state_specific=False,
                applicable_states=[]
            ),
            GovernmentScheme(
                scheme_id="KCC",
                scheme_name="Kisan Credit Card",
                category=SchemeCategory.CREDIT,
                description="Credit facility for farmers to meet agricultural expenses",
                benefits=[
                    "Flexible credit limit based on land holding",
                    "Low interest rates (7% per annum)",
                    "Interest subvention of 3%",
                    "Accident insurance coverage of ₹50,000"
                ],
                eligibility_criteria={
                    "farmer_type": "All farmers including tenant farmers",
                    "land_requirement": "Must have cultivable land",
                    "credit_history": "Good repayment track record preferred"
                },
                required_documents=[
                    "Aadhaar card",
                    "Land ownership documents",
                    "Bank account details",
                    "Passport size photographs"
                ],
                application_process="Apply at nearest bank branch or through CSCs",
                application_url="https://www.nabard.org/content1.aspx?id=523&catid=8&mid=489",
                implementing_agency="NABARD and Banks",
                contact_info={"helpline": "1800-180-1111"},
                state_specific=False,
                applicable_states=[]
            ),
            GovernmentScheme(
                scheme_id="SHC",
                scheme_name="Soil Health Card Scheme",
                category=SchemeCategory.TECHNOLOGY,
                description="Provides soil health cards to farmers with nutrient status and recommendations",
                benefits=[
                    "Free soil testing",
                    "Customized fertilizer recommendations",
                    "Improved soil health management",
                    "Reduced input costs"
                ],
                eligibility_criteria={
                    "farmer_type": "All farmers",
                    "land_requirement": "Must have agricultural land"
                },
                required_documents=[
                    "Aadhaar card",
                    "Land ownership documents",
                    "Soil samples"
                ],
                application_process="Contact local agriculture department or soil testing labs",
                application_url="https://soilhealth.dac.gov.in/",
                implementing_agency="Department of Agriculture and Cooperation",
                contact_info={"helpline": "011-23382012"},
                state_specific=False,
                applicable_states=[]
            ),
            GovernmentScheme(
                scheme_id="PKVY",
                scheme_name="Paramparagat Krishi Vikas Yojana",
                category=SchemeCategory.SUBSIDY,
                description="Promotes organic farming through cluster approach",
                benefits=[
                    "₹50,000 per hectare for 3 years",
                    "Support for organic inputs",
                    "Certification assistance",
                    "Market linkage support"
                ],
                eligibility_criteria={
                    "farmer_type": "Farmers willing to adopt organic farming",
                    "cluster_requirement": "Minimum 50 farmers forming a cluster",
                    "land_requirement": "Minimum 50 acres cluster area"
                },
                required_documents=[
                    "Aadhaar card",
                    "Land ownership documents",
                    "Cluster formation certificate",
                    "Bank account details"
                ],
                application_process="Apply through State Agriculture Department",
                implementing_agency="Ministry of Agriculture and Farmers Welfare",
                contact_info={"email": "pkvy-dac@gov.in"},
                state_specific=False,
                applicable_states=[]
            )
        ]
        
        # Store schemes in Redis
        for scheme in schemes:
            self._store_scheme(scheme)
        
        logger.info(f"Initialized {len(schemes)} government schemes in database")
    
    def _store_scheme(self, scheme: GovernmentScheme):
        """Store scheme in Redis"""
        try:
            scheme_key = f"scheme:{scheme.scheme_id}"
            self.redis_client.setex(
                scheme_key,
                30 * 24 * 3600,  # 30 days
                json.dumps(scheme.dict())
            )
            
            # Add to category index
            category_key = f"schemes:category:{scheme.category.value}"
            self.redis_client.sadd(category_key, scheme.scheme_id)
            
            # Add to state index if state-specific
            if scheme.state_specific:
                for state in scheme.applicable_states:
                    state_key = f"schemes:state:{state}"
                    self.redis_client.sadd(state_key, scheme.scheme_id)
            else:
                # Add to national schemes
                self.redis_client.sadd("schemes:national", scheme.scheme_id)
            
        except Exception as e:
            logger.error(f"Error storing scheme {scheme.scheme_id}: {e}")
    
    def get_scheme(self, scheme_id: str) -> Optional[GovernmentScheme]:
        """Retrieve a scheme by ID"""
        try:
            scheme_key = f"scheme:{scheme_id}"
            scheme_data = self.redis_client.get(scheme_key)
            
            if scheme_data:
                return GovernmentScheme(**json.loads(scheme_data))
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving scheme {scheme_id}: {e}")
            return None
    
    def get_all_schemes(self) -> List[GovernmentScheme]:
        """Get all available schemes"""
        try:
            schemes = []
            
            # Get all scheme IDs
            national_schemes = self.redis_client.smembers("schemes:national")
            
            for scheme_id in national_schemes:
                scheme = self.get_scheme(scheme_id)
                if scheme:
                    schemes.append(scheme)
            
            return schemes
            
        except Exception as e:
            logger.error(f"Error retrieving all schemes: {e}")
            return []
    
    def get_schemes_by_category(self, category: SchemeCategory) -> List[GovernmentScheme]:
        """Get schemes by category"""
        try:
            category_key = f"schemes:category:{category.value}"
            scheme_ids = self.redis_client.smembers(category_key)
            
            schemes = []
            for scheme_id in scheme_ids:
                scheme = self.get_scheme(scheme_id)
                if scheme:
                    schemes.append(scheme)
            
            return schemes
            
        except Exception as e:
            logger.error(f"Error retrieving schemes by category {category}: {e}")
            return []
    
    def get_schemes_by_state(self, state: str) -> List[GovernmentScheme]:
        """Get schemes applicable to a state"""
        try:
            schemes = []
            
            # Get national schemes
            national_schemes = self.get_all_schemes()
            schemes.extend(national_schemes)
            
            # Get state-specific schemes
            state_key = f"schemes:state:{state}"
            scheme_ids = self.redis_client.smembers(state_key)
            
            for scheme_id in scheme_ids:
                scheme = self.get_scheme(scheme_id)
                if scheme:
                    schemes.append(scheme)
            
            return schemes
            
        except Exception as e:
            logger.error(f"Error retrieving schemes for state {state}: {e}")
            return []


class EligibilityAssessor:
    """Assesses farmer eligibility for government schemes"""
    
    def __init__(self):
        self.scheme_db = GovernmentSchemeDatabase()
        
        # Initialize LangChain LLM for intelligent eligibility assessment
        try:
            self.llm = ChatBedrock(
                model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
                region_name=settings.aws_region or "us-east-1",
                model_kwargs={"temperature": 0.3, "max_tokens": 2000}
            )
            
            # Create eligibility assessment prompt
            self.eligibility_prompt = PromptTemplate(
                input_variables=["farmer_profile", "scheme_criteria", "scheme_name"],
                template="""You are an expert in Indian government agricultural schemes and farmer eligibility assessment.

Farmer Profile:
{farmer_profile}

Scheme: {scheme_name}
Eligibility Criteria:
{scheme_criteria}

Assess the farmer's eligibility for this scheme. Provide:
1. Eligibility status (eligible/not_eligible/partially_eligible)
2. Matched criteria (list what criteria the farmer meets)
3. Unmatched criteria (list what criteria the farmer doesn't meet)
4. Missing information (what additional information is needed)
5. Recommendations (actionable steps for the farmer)

Provide your assessment in JSON format with keys: status, matched_criteria, unmatched_criteria, missing_info, recommendations"""
            )
            
            self.eligibility_chain = LLMChain(
                llm=self.llm,
                prompt=self.eligibility_prompt
            )
            
        except Exception as e:
            logger.warning(f"Could not initialize LLM for eligibility assessment: {e}")
            self.llm = None
            self.eligibility_chain = None
    
    def assess_eligibility(
        self,
        farmer_profile: Dict[str, Any],
        scheme: GovernmentScheme
    ) -> FarmerEligibility:
        """Assess farmer eligibility for a specific scheme"""
        try:
            farmer_id = farmer_profile.get("farmer_id", "unknown")
            
            # Use LLM-based assessment if available
            if self.eligibility_chain:
                return self._llm_based_assessment(farmer_profile, scheme)
            else:
                return self._rule_based_assessment(farmer_profile, scheme)
                
        except Exception as e:
            logger.error(f"Error assessing eligibility: {e}")
            return FarmerEligibility(
                farmer_id=farmer_id,
                scheme_id=scheme.scheme_id,
                eligibility_status=SchemeEligibilityStatus.PENDING_VERIFICATION,
                eligibility_score=0,
                recommendations=["Unable to assess eligibility. Please contact support."]
            )
    
    def _llm_based_assessment(
        self,
        farmer_profile: Dict[str, Any],
        scheme: GovernmentScheme
    ) -> FarmerEligibility:
        """Use LLM for intelligent eligibility assessment"""
        try:
            # Prepare inputs
            farmer_profile_str = json.dumps(farmer_profile, indent=2)
            scheme_criteria_str = json.dumps(scheme.eligibility_criteria, indent=2)
            
            # Run LLM chain
            result = self.eligibility_chain.run(
                farmer_profile=farmer_profile_str,
                scheme_criteria=scheme_criteria_str,
                scheme_name=scheme.scheme_name
            )
            
            # Parse LLM response
            try:
                assessment = json.loads(result)
            except json.JSONDecodeError:
                # Fallback to rule-based if LLM response is not valid JSON
                logger.warning("LLM response not valid JSON, falling back to rule-based assessment")
                return self._rule_based_assessment(farmer_profile, scheme)
            
            # Map status
            status_map = {
                "eligible": SchemeEligibilityStatus.ELIGIBLE,
                "not_eligible": SchemeEligibilityStatus.NOT_ELIGIBLE,
                "partially_eligible": SchemeEligibilityStatus.PARTIALLY_ELIGIBLE
            }
            status = status_map.get(
                assessment.get("status", "").lower(),
                SchemeEligibilityStatus.PENDING_VERIFICATION
            )
            
            # Calculate eligibility score
            matched = len(assessment.get("matched_criteria", []))
            unmatched = len(assessment.get("unmatched_criteria", []))
            total = matched + unmatched
            score = (matched / total * 100) if total > 0 else 0
            
            return FarmerEligibility(
                farmer_id=farmer_profile.get("farmer_id", "unknown"),
                scheme_id=scheme.scheme_id,
                eligibility_status=status,
                eligibility_score=score,
                matched_criteria=assessment.get("matched_criteria", []),
                unmatched_criteria=assessment.get("unmatched_criteria", []),
                missing_documents=assessment.get("missing_info", []),
                recommendations=assessment.get("recommendations", [])
            )
            
        except Exception as e:
            logger.error(f"Error in LLM-based assessment: {e}")
            return self._rule_based_assessment(farmer_profile, scheme)
    
    def _rule_based_assessment(
        self,
        farmer_profile: Dict[str, Any],
        scheme: GovernmentScheme
    ) -> FarmerEligibility:
        """Rule-based eligibility assessment as fallback"""
        try:
            farmer_id = farmer_profile.get("farmer_id", "unknown")
            matched_criteria = []
            unmatched_criteria = []
            missing_documents = []
            recommendations = []
            
            # Check land ownership
            if "land_ownership" in scheme.eligibility_criteria:
                if farmer_profile.get("farm_details", {}).get("total_land_area", 0) > 0:
                    matched_criteria.append("Has cultivable land")
                else:
                    unmatched_criteria.append("No land ownership documented")
            
            # Check documents
            farmer_documents = set(farmer_profile.get("documents", []))
            required_docs = set(scheme.required_documents)
            
            for doc in required_docs:
                if doc.lower() in [d.lower() for d in farmer_documents]:
                    matched_criteria.append(f"Has {doc}")
                else:
                    missing_documents.append(doc)
                    unmatched_criteria.append(f"Missing {doc}")
            
            # Check state eligibility
            if scheme.state_specific:
                farmer_state = farmer_profile.get("personal_info", {}).get("location", {}).get("state")
                if farmer_state in scheme.applicable_states:
                    matched_criteria.append(f"Located in applicable state: {farmer_state}")
                else:
                    unmatched_criteria.append(f"Scheme not applicable in {farmer_state}")
            
            # Calculate eligibility score
            total_criteria = len(matched_criteria) + len(unmatched_criteria)
            score = (len(matched_criteria) / total_criteria * 100) if total_criteria > 0 else 0
            
            # Determine status
            if score >= 80:
                status = SchemeEligibilityStatus.ELIGIBLE
                recommendations.append(f"You are eligible for {scheme.scheme_name}. Proceed with application.")
            elif score >= 50:
                status = SchemeEligibilityStatus.PARTIALLY_ELIGIBLE
                recommendations.append(f"You may be eligible for {scheme.scheme_name}. Complete missing requirements.")
            else:
                status = SchemeEligibilityStatus.NOT_ELIGIBLE
                recommendations.append(f"You may not be eligible for {scheme.scheme_name} at this time.")
            
            # Add document recommendations
            if missing_documents:
                recommendations.append(f"Obtain the following documents: {', '.join(missing_documents)}")
            
            return FarmerEligibility(
                farmer_id=farmer_id,
                scheme_id=scheme.scheme_id,
                eligibility_status=status,
                eligibility_score=score,
                matched_criteria=matched_criteria,
                unmatched_criteria=unmatched_criteria,
                missing_documents=missing_documents,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error in rule-based assessment: {e}")
            return FarmerEligibility(
                farmer_id=farmer_profile.get("farmer_id", "unknown"),
                scheme_id=scheme.scheme_id,
                eligibility_status=SchemeEligibilityStatus.PENDING_VERIFICATION,
                eligibility_score=0,
                recommendations=["Unable to complete assessment. Please contact support."]
            )
    
    def find_eligible_schemes(
        self,
        farmer_profile: Dict[str, Any],
        min_score: float = 50.0
    ) -> List[Dict[str, Any]]:
        """Find all schemes the farmer is eligible for"""
        try:
            farmer_state = farmer_profile.get("personal_info", {}).get("location", {}).get("state")
            
            # Get applicable schemes
            if farmer_state:
                schemes = self.scheme_db.get_schemes_by_state(farmer_state)
            else:
                schemes = self.scheme_db.get_all_schemes()
            
            eligible_schemes = []
            
            for scheme in schemes:
                # Assess eligibility
                eligibility = self.assess_eligibility(farmer_profile, scheme)
                
                # Include if meets minimum score
                if eligibility.eligibility_score >= min_score:
                    eligible_schemes.append({
                        "scheme": scheme,
                        "eligibility": eligibility
                    })
            
            # Sort by eligibility score
            eligible_schemes.sort(
                key=lambda x: x["eligibility"].eligibility_score,
                reverse=True
            )
            
            logger.info(f"Found {len(eligible_schemes)} eligible schemes for farmer")
            return eligible_schemes
            
        except Exception as e:
            logger.error(f"Error finding eligible schemes: {e}")
            return []


class ApplicationTracker:
    """Tracks scheme applications and their status"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=True
        )
    
    def create_application(
        self,
        farmer_id: str,
        scheme_id: str,
        documents: List[str]
    ) -> SchemeApplication:
        """Create a new scheme application"""
        try:
            application_id = f"app:{farmer_id}:{scheme_id}:{datetime.now().timestamp()}"
            
            application = SchemeApplication(
                application_id=application_id,
                farmer_id=farmer_id,
                scheme_id=scheme_id,
                application_status="draft",
                documents_submitted=documents,
                submitted_at=None
            )
            
            # Store application
            self._store_application(application)
            
            logger.info(f"Created application {application_id}")
            return application
            
        except Exception as e:
            logger.error(f"Error creating application: {e}")
            raise
    
    def _store_application(self, application: SchemeApplication):
        """Store application in Redis"""
        try:
            app_key = f"application:{application.application_id}"
            self.redis_client.setex(
                app_key,
                90 * 24 * 3600,  # 90 days
                json.dumps(application.dict())
            )
            
            # Add to farmer's applications
            farmer_apps_key = f"farmer_applications:{application.farmer_id}"
            self.redis_client.sadd(farmer_apps_key, application.application_id)
            
        except Exception as e:
            logger.error(f"Error storing application: {e}")
    
    def get_application(self, application_id: str) -> Optional[SchemeApplication]:
        """Retrieve an application by ID"""
        try:
            app_key = f"application:{application_id}"
            app_data = self.redis_client.get(app_key)
            
            if app_data:
                return SchemeApplication(**json.loads(app_data))
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving application {application_id}: {e}")
            return None
    
    def update_application_status(
        self,
        application_id: str,
        status: str,
        notes: Optional[str] = None
    ) -> bool:
        """Update application status"""
        try:
            application = self.get_application(application_id)
            
            if not application:
                logger.warning(f"Application {application_id} not found")
                return False
            
            application.application_status = status
            application.last_updated = datetime.now().isoformat()
            
            if notes:
                application.notes.append(f"{datetime.now().isoformat()}: {notes}")
            
            self._store_application(application)
            
            logger.info(f"Updated application {application_id} status to {status}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating application status: {e}")
            return False
    
    def submit_application(self, application_id: str) -> bool:
        """Submit an application"""
        try:
            application = self.get_application(application_id)
            
            if not application:
                return False
            
            application.application_status = "submitted"
            application.submitted_at = datetime.now().isoformat()
            application.verification_status = "pending"
            application.last_updated = datetime.now().isoformat()
            
            self._store_application(application)
            
            logger.info(f"Submitted application {application_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error submitting application: {e}")
            return False
    
    def get_farmer_applications(self, farmer_id: str) -> List[SchemeApplication]:
        """Get all applications for a farmer"""
        try:
            farmer_apps_key = f"farmer_applications:{farmer_id}"
            app_ids = self.redis_client.smembers(farmer_apps_key)
            
            applications = []
            for app_id in app_ids:
                app = self.get_application(app_id)
                if app:
                    applications.append(app)
            
            # Sort by last updated
            applications.sort(
                key=lambda x: x.last_updated,
                reverse=True
            )
            
            return applications
            
        except Exception as e:
            logger.error(f"Error retrieving farmer applications: {e}")
            return []


class GovernmentSchemeAgent:
    """Main agent for government scheme integration"""
    
    def __init__(self):
        self.scheme_db = GovernmentSchemeDatabase()
        self.eligibility_assessor = EligibilityAssessor()
        self.application_tracker = ApplicationTracker()
        self.redis_client = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=True
        )
    
    async def identify_applicable_schemes(
        self,
        farmer_profile: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Identify and notify farmer of applicable schemes"""
        try:
            farmer_id = farmer_profile.get("farmer_id", "unknown")
            
            # Find eligible schemes
            eligible_schemes = self.eligibility_assessor.find_eligible_schemes(
                farmer_profile,
                min_score=50.0
            )
            
            # Create notifications
            notifications = []
            for scheme_info in eligible_schemes:
                scheme = scheme_info["scheme"]
                eligibility = scheme_info["eligibility"]
                
                notification = {
                    "farmer_id": farmer_id,
                    "scheme_id": scheme.scheme_id,
                    "scheme_name": scheme.scheme_name,
                    "category": scheme.category.value,
                    "eligibility_status": eligibility.eligibility_status.value,
                    "eligibility_score": eligibility.eligibility_score,
                    "benefits": scheme.benefits,
                    "recommendations": eligibility.recommendations,
                    "application_url": scheme.application_url,
                    "contact_info": scheme.contact_info,
                    "notified_at": datetime.now().isoformat()
                }
                
                notifications.append(notification)
                
                # Store notification
                self._store_notification(farmer_id, notification)
            
            logger.info(f"Identified {len(notifications)} applicable schemes for farmer {farmer_id}")
            return notifications
            
        except Exception as e:
            logger.error(f"Error identifying applicable schemes: {e}")
            return []
    
    def _store_notification(self, farmer_id: str, notification: Dict[str, Any]):
        """Store scheme notification"""
        try:
            notification_id = f"notification:{farmer_id}:{notification['scheme_id']}:{datetime.now().timestamp()}"
            
            self.redis_client.setex(
                notification_id,
                30 * 24 * 3600,  # 30 days
                json.dumps(notification)
            )
            
            # Add to farmer's notifications
            farmer_notif_key = f"farmer_notifications:{farmer_id}"
            self.redis_client.sadd(farmer_notif_key, notification_id)
            
        except Exception as e:
            logger.error(f"Error storing notification: {e}")
    
    def get_scheme_details(self, scheme_id: str) -> Optional[GovernmentScheme]:
        """Get detailed information about a scheme"""
        return self.scheme_db.get_scheme(scheme_id)
    
    def assess_scheme_eligibility(
        self,
        farmer_profile: Dict[str, Any],
        scheme_id: str
    ) -> Optional[FarmerEligibility]:
        """Assess farmer eligibility for a specific scheme"""
        try:
            scheme = self.scheme_db.get_scheme(scheme_id)
            
            if not scheme:
                logger.warning(f"Scheme {scheme_id} not found")
                return None
            
            return self.eligibility_assessor.assess_eligibility(farmer_profile, scheme)
            
        except Exception as e:
            logger.error(f"Error assessing scheme eligibility: {e}")
            return None
    
    def create_scheme_application(
        self,
        farmer_id: str,
        scheme_id: str,
        documents: List[str]
    ) -> Optional[SchemeApplication]:
        """Create a new scheme application"""
        try:
            return self.application_tracker.create_application(
                farmer_id,
                scheme_id,
                documents
            )
        except Exception as e:
            logger.error(f"Error creating scheme application: {e}")
            return None
    
    def submit_scheme_application(self, application_id: str) -> bool:
        """Submit a scheme application"""
        return self.application_tracker.submit_application(application_id)
    
    def get_application_status(self, application_id: str) -> Optional[SchemeApplication]:
        """Get application status"""
        return self.application_tracker.get_application(application_id)
    
    def get_farmer_applications(self, farmer_id: str) -> List[SchemeApplication]:
        """Get all applications for a farmer"""
        return self.application_tracker.get_farmer_applications(farmer_id)
    
    def provide_application_guidance(
        self,
        scheme_id: str
    ) -> Dict[str, Any]:
        """Provide step-by-step application guidance"""
        try:
            scheme = self.scheme_db.get_scheme(scheme_id)
            
            if not scheme:
                return {"error": "Scheme not found"}
            
            guidance = {
                "scheme_name": scheme.scheme_name,
                "application_process": scheme.application_process,
                "required_documents": scheme.required_documents,
                "application_url": scheme.application_url,
                "contact_info": scheme.contact_info,
                "steps": [
                    "1. Gather all required documents",
                    "2. Visit the application portal or nearest CSC",
                    "3. Fill out the application form with accurate information",
                    "4. Upload/submit required documents",
                    "5. Submit the application and note the application ID",
                    "6. Track application status regularly"
                ],
                "tips": [
                    "Keep copies of all submitted documents",
                    "Note down application ID for future reference",
                    "Follow up if no response within expected timeframe",
                    "Contact helpline for any queries"
                ]
            }
            
            return guidance
            
        except Exception as e:
            logger.error(f"Error providing application guidance: {e}")
            return {"error": str(e)}


class GovernmentSchemeTool(BaseTool, LangChainBaseModel):
    """LangChain tool for government scheme identification"""
    
    name: str = "government_scheme_identification"
    description: str = "Identify applicable government schemes and assess farmer eligibility"
    
    def _run(self, farmer_id: str, state: str = None) -> str:
        """Run the scheme identification tool"""
        import asyncio
        
        async def identify_schemes():
            agent = GovernmentSchemeAgent()
            
            # Create minimal farmer profile
            farmer_profile = {
                "farmer_id": farmer_id,
                "personal_info": {
                    "location": {
                        "state": state or "Unknown"
                    }
                },
                "farm_details": {
                    "total_land_area": 2.0  # Assume some land
                },
                "documents": ["Aadhaar card", "Bank account details"]
            }
            
            schemes = await agent.identify_applicable_schemes(farmer_profile)
            
            if not schemes:
                return f"No applicable schemes found for farmer {farmer_id}"
            
            response = f"Found {len(schemes)} applicable schemes:\n\n"
            for scheme in schemes[:3]:  # Show top 3
                response += f"- {scheme['scheme_name']} ({scheme['category']})\n"
                response += f"  Eligibility: {scheme['eligibility_status']} ({scheme['eligibility_score']:.0f}%)\n"
                if scheme.get('benefits'):
                    response += f"  Benefits: {scheme['benefits'][0]}\n"
                response += "\n"
            
            return response
        
        return asyncio.run(identify_schemes())
    
    async def _arun(self, farmer_id: str, state: str = None) -> str:
        """Async version of the tool"""
        agent = GovernmentSchemeAgent()
        
        # Create minimal farmer profile
        farmer_profile = {
            "farmer_id": farmer_id,
            "personal_info": {
                "location": {
                    "state": state or "Unknown"
                }
            },
            "farm_details": {
                "total_land_area": 2.0
            },
            "documents": ["Aadhaar card", "Bank account details"]
        }
        
        schemes = await agent.identify_applicable_schemes(farmer_profile)
        
        if not schemes:
            return f"No applicable schemes found for farmer {farmer_id}"
        
        response = f"Found {len(schemes)} applicable schemes:\n\n"
        for scheme in schemes[:3]:
            response += f"- {scheme['scheme_name']} ({scheme['category']})\n"
            response += f"  Eligibility: {scheme['eligibility_status']} ({scheme['eligibility_score']:.0f}%)\n"
            if scheme.get('benefits'):
                response += f"  Benefits: {scheme['benefits'][0]}\n"
            response += "\n"
        
        return response



class GovernmentAPIClient:
    """Client for connecting to government databases and APIs"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=True
        )
        self.cache_ttl = 24 * 3600  # 24 hours cache
        
        # API endpoints (placeholder - in production use actual government APIs)
        self.pmkisan_api_url = "https://pmkisan.gov.in/api"
        self.soil_health_api_url = "https://soilhealth.dac.gov.in/api"
        self.crop_insurance_api_url = "https://pmfby.gov.in/api"
    
    async def get_pmkisan_status(self, farmer_id: str, aadhaar: str) -> Dict[str, Any]:
        """Get PM-KISAN enrollment and payment status"""
        try:
            # In production, make actual API call
            # For now, return mock data
            cache_key = f"pmkisan:{farmer_id}"
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            
            # Mock response
            status = {
                "farmer_id": farmer_id,
                "enrollment_status": "enrolled",
                "beneficiary_id": f"BEN{farmer_id}",
                "installments_received": 3,
                "total_amount_received": 6000,
                "last_payment_date": "2024-01-15",
                "next_payment_due": "2024-04-15",
                "bank_account_verified": True
            }
            
            self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(status))
            return status
            
        except Exception as e:
            logger.error(f"Error getting PM-KISAN status: {e}")
            return {}
    
    async def get_soil_health_card(self, farmer_id: str, location: Dict[str, Any]) -> Dict[str, Any]:
        """Get soil health card information"""
        try:
            cache_key = f"soil_health:{farmer_id}"
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            
            # Mock response
            soil_data = {
                "farmer_id": farmer_id,
                "card_number": f"SHC{farmer_id}",
                "issue_date": "2023-06-15",
                "valid_until": "2026-06-15",
                "soil_type": "Loamy",
                "ph_level": 6.5,
                "organic_carbon": 0.65,
                "nitrogen": "Medium",
                "phosphorus": "Low",
                "potassium": "High",
                "recommendations": [
                    "Apply 20 kg/acre of phosphorus fertilizer",
                    "Maintain organic matter through crop residue",
                    "Consider green manuring"
                ]
            }
            
            self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(soil_data))
            return soil_data
            
        except Exception as e:
            logger.error(f"Error getting soil health card: {e}")
            return {}
    
    async def get_crop_insurance_status(self, farmer_id: str, season: str) -> Dict[str, Any]:
        """Get crop insurance enrollment and claim status"""
        try:
            cache_key = f"crop_insurance:{farmer_id}:{season}"
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            
            # Mock response
            insurance_data = {
                "farmer_id": farmer_id,
                "season": season,
                "enrollment_status": "enrolled",
                "policy_number": f"PMFBY{farmer_id}{season}",
                "insured_crops": ["Rice", "Wheat"],
                "sum_insured": 50000,
                "premium_paid": 1000,
                "claims_filed": 0,
                "claims_settled": 0,
                "coverage_start": "2024-06-01",
                "coverage_end": "2024-11-30"
            }
            
            self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(insurance_data))
            return insurance_data
            
        except Exception as e:
            logger.error(f"Error getting crop insurance status: {e}")
            return {}


class GovernmentDataTool(BaseTool, LangChainBaseModel):
    """LangChain tool for government data access"""
    
    name: str = "government_data_access"
    description: str = "Access government databases for PM-KISAN, soil health cards, and crop insurance"
    
    def _run(self, farmer_id: str, data_type: str = "pmkisan") -> str:
        """Run the government data access tool"""
        import asyncio
        
        async def get_government_data():
            client = GovernmentAPIClient()
            
            if data_type == "pmkisan":
                data = await client.get_pmkisan_status(farmer_id, "")
                if data:
                    return f"PM-KISAN Status: {data.get('enrollment_status', 'unknown')}, Installments: {data.get('installments_received', 0)}, Amount: ₹{data.get('total_amount_received', 0)}"
            elif data_type == "soil_health":
                data = await client.get_soil_health_card(farmer_id, {})
                if data:
                    return f"Soil Health Card: pH {data.get('ph_level', 'N/A')}, N: {data.get('nitrogen', 'N/A')}, P: {data.get('phosphorus', 'N/A')}, K: {data.get('potassium', 'N/A')}"
            elif data_type == "insurance":
                data = await client.get_crop_insurance_status(farmer_id, "Kharif2024")
                if data:
                    return f"Crop Insurance: {data.get('enrollment_status', 'unknown')}, Policy: {data.get('policy_number', 'N/A')}, Sum Insured: ₹{data.get('sum_insured', 0)}"
            
            return f"No {data_type} data found for farmer {farmer_id}"
        
        return asyncio.run(get_government_data())
    
    async def _arun(self, farmer_id: str, data_type: str = "pmkisan") -> str:
        """Async version of the tool"""
        client = GovernmentAPIClient()
        
        if data_type == "pmkisan":
            data = await client.get_pmkisan_status(farmer_id, "")
            if data:
                return f"PM-KISAN Status: {data.get('enrollment_status', 'unknown')}, Installments: {data.get('installments_received', 0)}, Amount: ₹{data.get('total_amount_received', 0)}"
        elif data_type == "soil_health":
            data = await client.get_soil_health_card(farmer_id, {})
            if data:
                return f"Soil Health Card: pH {data.get('ph_level', 'N/A')}, N: {data.get('nitrogen', 'N/A')}, P: {data.get('phosphorus', 'N/A')}, K: {data.get('potassium', 'N/A')}"
        elif data_type == "insurance":
            data = await client.get_crop_insurance_status(farmer_id, "Kharif2024")
            if data:
                return f"Crop Insurance: {data.get('enrollment_status', 'unknown')}, Policy: {data.get('policy_number', 'N/A')}, Sum Insured: ₹{data.get('sum_insured', 0)}"
        
        return f"No {data_type} data found for farmer {farmer_id}"


# Alias for backward compatibility
GovernmentIntegrationAgent = GovernmentSchemeAgent
