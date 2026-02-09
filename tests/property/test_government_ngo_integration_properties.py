"""
Property-Based Tests for Government and NGO Integration

This module implements property-based tests for government scheme identification,
NGO service connection, and integration systems using Hypothesis.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import Mock, patch, MagicMock

from src.krishimitra.agents.government_integration import (
    GovernmentSchemeAgent,
    GovernmentSchemeDatabase,
    EligibilityAssessor,
    ApplicationTracker,
    SchemeCategory,
    SchemeEligibilityStatus,
    GovernmentAPIClient
)
from src.krishimitra.agents.ngo_integration import (
    NGOIntegrationAgent,
    NGODatabase,
    NGOConnectionManager,
    ImpactTracker,
    NGOServiceCategory,
    NGOVerificationStatus
)


# Mock Redis for testing
@pytest.fixture(autouse=True)
def mock_redis():
    """Mock Redis client for all tests"""
    with patch('redis.Redis') as mock:
        mock_client = MagicMock()
        mock_client.get.return_value = None
        mock_client.setex.return_value = True
        mock_client.sadd.return_value = 1
        mock_client.smembers.return_value = set()
        mock.return_value = mock_client
        yield mock_client


# Custom strategies for agricultural domain
@st.composite
def farmer_profile_strategy(draw):
    """Generate realistic farmer profiles"""
    states = ["Maharashtra", "Karnataka", "Punjab", "Uttar Pradesh", "Tamil Nadu", 
              "Gujarat", "Rajasthan", "Madhya Pradesh", "Bihar", "West Bengal"]
    
    return {
        "farmer_id": f"FARMER{draw(st.integers(min_value=1000, max_value=9999))}",
        "personal_info": {
            "name": draw(st.text(min_size=5, max_size=30, alphabet=st.characters(whitelist_categories=('Lu', 'Ll')))),
            "location": {
                "state": draw(st.sampled_from(states)),
                "district": draw(st.text(min_size=5, max_size=20)),
                "village": draw(st.text(min_size=5, max_size=20))
            }
        },
        "farm_details": {
            "total_land_area": draw(st.floats(min_value=0.5, max_value=50.0)),
            "soil_type": draw(st.sampled_from(["Loamy", "Clay", "Sandy", "Black", "Red"])),
            "irrigation_type": draw(st.sampled_from(["Drip", "Sprinkler", "Flood", "Rainfed"]))
        },
        "documents": draw(st.lists(
            st.sampled_from(["Aadhaar card", "Bank account details", "Land ownership documents", "PAN card"]),
            min_size=1,
            max_size=4,
            unique=True
        ))
    }


@st.composite
def service_needs_strategy(draw):
    """Generate realistic service needs"""
    needs = [
        "training", "financial assistance", "market linkage", "technology support",
        "organic farming", "water management", "soil conservation", "livestock support"
    ]
    return draw(st.lists(st.sampled_from(needs), min_size=1, max_size=4, unique=True))


# Property 56: Government system integration
@given(farmer_profile=farmer_profile_strategy())
@settings(max_examples=10, deadline=5000)
@pytest.mark.asyncio
async def test_property_56_government_system_integration(farmer_profile):
    """
    Feature: krishimitra, Property 56: Government system integration
    For any available government database, the KrishiMitra_Platform should integrate 
    with PM-KISAN, soil health card systems, and crop insurance databases
    
    **Validates: Requirements 12.1**
    """
    # Test PM-KISAN integration
    client = GovernmentAPIClient()
    farmer_id = farmer_profile["farmer_id"]
    
    pmkisan_data = await client.get_pmkisan_status(farmer_id, "")
    assert pmkisan_data is not None, "PM-KISAN integration should return data"
    assert "enrollment_status" in pmkisan_data, "PM-KISAN data should include enrollment status"
    assert "installments_received" in pmkisan_data, "PM-KISAN data should include installments"
    
    # Test Soil Health Card integration
    soil_data = await client.get_soil_health_card(farmer_id, {})
    assert soil_data is not None, "Soil health card integration should return data"
    assert "ph_level" in soil_data, "Soil data should include pH level"
    assert "nitrogen" in soil_data, "Soil data should include nitrogen level"
    
    # Test Crop Insurance integration
    insurance_data = await client.get_crop_insurance_status(farmer_id, "Kharif2024")
    assert insurance_data is not None, "Crop insurance integration should return data"
    assert "enrollment_status" in insurance_data, "Insurance data should include enrollment status"
    assert "sum_insured" in insurance_data, "Insurance data should include sum insured"
    
    # Verify data consistency
    assert pmkisan_data["farmer_id"] == farmer_id, "PM-KISAN data should match farmer ID"
    assert soil_data["farmer_id"] == farmer_id, "Soil data should match farmer ID"
    assert insurance_data["farmer_id"] == farmer_id, "Insurance data should match farmer ID"


# Property 57: Automatic scheme identification
@given(farmer_profile=farmer_profile_strategy())
@settings(max_examples=10, deadline=5000)
@pytest.mark.asyncio
async def test_property_57_automatic_scheme_identification(farmer_profile):
    """
    Feature: krishimitra, Property 57: Automatic scheme identification
    For any farmer eligible for government schemes, the KrishiMitra_Platform should 
    automatically identify and notify farmers of applicable programs
    
    **Validates: Requirements 12.2**
    """
    agent = GovernmentSchemeAgent()
    farmer_id = farmer_profile["farmer_id"]
    
    # Identify applicable schemes
    schemes = await agent.identify_applicable_schemes(farmer_profile)
    
    # Verify schemes are identified
    assert isinstance(schemes, list), "Scheme identification should return a list"
    
    # If schemes are found, verify their structure
    if len(schemes) > 0:
        for scheme in schemes:
            assert "scheme_id" in scheme, "Each scheme should have an ID"
            assert "scheme_name" in scheme, "Each scheme should have a name"
            assert "eligibility_status" in scheme, "Each scheme should have eligibility status"
            assert "eligibility_score" in scheme, "Each scheme should have eligibility score"
            assert "benefits" in scheme, "Each scheme should list benefits"
            assert "recommendations" in scheme, "Each scheme should provide recommendations"
            
            # Verify eligibility score is valid
            assert 0 <= scheme["eligibility_score"] <= 100, "Eligibility score should be between 0 and 100"
            
            # Verify notification includes contact info
            assert "contact_info" in scheme, "Scheme notification should include contact information"
            
            # Verify timestamp
            assert "notified_at" in scheme, "Scheme notification should include timestamp"
            notified_time = datetime.fromisoformat(scheme["notified_at"])
            assert notified_time <= datetime.now(), "Notification time should not be in the future"


# Property 58: NGO service connection
@given(
    farmer_profile=farmer_profile_strategy(),
    service_needs=service_needs_strategy()
)
@settings(max_examples=10, deadline=5000)
def test_property_58_ngo_service_connection(farmer_profile, service_needs):
    """
    Feature: krishimitra, Property 58: NGO service connection
    For any relevant NGO service, the KrishiMitra_Platform should connect farmers 
    with local development organizations and their programs
    
    **Validates: Requirements 12.3**
    """
    agent = NGOIntegrationAgent()
    farmer_id = farmer_profile["farmer_id"]
    farmer_state = farmer_profile["personal_info"]["location"]["state"]
    
    # Find relevant NGOs
    matches = agent.find_relevant_ngos(farmer_profile, service_needs)
    
    # Verify NGO matching works
    assert isinstance(matches, list), "NGO matching should return a list"
    
    # If NGOs are found, verify connection capability
    if len(matches) > 0:
        for match in matches:
            assert "ngo" in match, "Each match should include NGO details"
            ngo = match["ngo"]
            
            # Verify NGO operates in farmer's region
            assert farmer_state in ngo.operating_regions or not ngo.operating_regions, \
                "NGO should operate in farmer's state or be national"
            
            # Verify NGO is verified
            assert ngo.verification_status == NGOVerificationStatus.VERIFIED, \
                "Only verified NGOs should be recommended"
            
            # Test connection creation
            connection = agent.connect_farmer_to_ngo(farmer_id, ngo.ngo_id)
            
            assert connection is not None, "Connection should be created successfully"
            assert connection.farmer_id == farmer_id, "Connection should link to correct farmer"
            assert connection.ngo_id == ngo.ngo_id, "Connection should link to correct NGO"
            assert connection.status == "initiated", "New connection should have 'initiated' status"
            
            # Verify connection can be retrieved
            retrieved_connection = agent.connection_manager.get_connection(connection.connection_id)
            assert retrieved_connection is not None, "Connection should be retrievable"
            assert retrieved_connection.connection_id == connection.connection_id, \
                "Retrieved connection should match created connection"
            
            # Only test first match to avoid creating too many connections
            break


# Property 59: Digital application guidance
@given(farmer_profile=farmer_profile_strategy())
@settings(max_examples=10, deadline=5000)
@pytest.mark.asyncio
async def test_property_59_digital_application_guidance(farmer_profile):
    """
    Feature: krishimitra, Property 59: Digital application guidance
    For any required government benefit application process, the KrishiMitra_Platform 
    should guide farmers through digital application procedures
    
    **Validates: Requirements 12.4**
    """
    agent = GovernmentSchemeAgent()
    
    # Get all available schemes
    schemes = agent.scheme_db.get_all_schemes()
    assume(len(schemes) > 0)  # Skip if no schemes available
    
    # Test guidance for each scheme
    for scheme in schemes[:3]:  # Test first 3 schemes
        guidance = agent.provide_application_guidance(scheme.scheme_id)
        
        # Verify guidance structure
        assert "scheme_name" in guidance, "Guidance should include scheme name"
        assert "application_process" in guidance, "Guidance should include application process"
        assert "required_documents" in guidance, "Guidance should list required documents"
        assert "steps" in guidance, "Guidance should provide step-by-step instructions"
        assert "tips" in guidance, "Guidance should provide helpful tips"
        
        # Verify required documents are listed
        assert isinstance(guidance["required_documents"], list), "Documents should be a list"
        assert len(guidance["required_documents"]) > 0, "At least one document should be required"
        
        # Verify steps are provided
        assert isinstance(guidance["steps"], list), "Steps should be a list"
        assert len(guidance["steps"]) > 0, "At least one step should be provided"
        
        # Verify contact information is included
        assert "contact_info" in guidance, "Guidance should include contact information"
        
        # Verify application URL if available
        if guidance.get("application_url"):
            assert guidance["application_url"].startswith("http"), \
                "Application URL should be a valid HTTP(S) URL"


# Property 60: Document verification and tracking
@given(farmer_profile=farmer_profile_strategy())
@settings(max_examples=10, deadline=5000)
@pytest.mark.asyncio
async def test_property_60_document_verification_tracking(farmer_profile):
    """
    Feature: krishimitra, Property 60: Document verification and tracking
    For any scheme application requiring verification, the KrishiMitra_Platform should 
    facilitate document verification and status tracking
    
    **Validates: Requirements 12.5**
    """
    agent = GovernmentSchemeAgent()
    farmer_id = farmer_profile["farmer_id"]
    
    # Get a scheme to apply for
    schemes = agent.scheme_db.get_all_schemes()
    assume(len(schemes) > 0)
    
    scheme = schemes[0]
    documents = farmer_profile["documents"]
    
    # Create an application
    application = agent.create_scheme_application(
        farmer_id,
        scheme.scheme_id,
        documents
    )
    
    assert application is not None, "Application should be created successfully"
    assert application.farmer_id == farmer_id, "Application should link to correct farmer"
    assert application.scheme_id == scheme.scheme_id, "Application should link to correct scheme"
    
    # Verify document tracking
    assert application.documents_submitted == documents, \
        "Application should track submitted documents"
    
    # Verify verification status tracking
    assert application.verification_status == "pending", \
        "New application should have pending verification status"
    assert application.approval_status == "pending", \
        "New application should have pending approval status"
    
    # Submit the application
    success = agent.submit_scheme_application(application.application_id)
    assert success, "Application submission should succeed"
    
    # Retrieve and verify status
    updated_application = agent.get_application_status(application.application_id)
    assert updated_application is not None, "Application should be retrievable"
    assert updated_application.application_status == "submitted", \
        "Submitted application should have 'submitted' status"
    assert updated_application.submitted_at is not None, \
        "Submitted application should have submission timestamp"
    
    # Verify application appears in farmer's applications
    farmer_applications = agent.get_farmer_applications(farmer_id)
    assert len(farmer_applications) > 0, "Farmer should have at least one application"
    
    application_ids = [app.application_id for app in farmer_applications]
    assert application.application_id in application_ids, \
        "Created application should appear in farmer's applications"
    
    # Verify status tracking over time
    assert updated_application.last_updated >= application.last_updated, \
        "Last updated timestamp should be current or later"


# Stateful testing for government scheme workflow
class GovernmentSchemeWorkflow(RuleBasedStateMachine):
    """Stateful testing for complete government scheme workflow"""
    
    def __init__(self):
        super().__init__()
        self.agent = GovernmentSchemeAgent()
        self.farmer_id = f"FARMER{datetime.now().timestamp()}"
        self.applications = []
    
    @rule()
    def identify_schemes(self):
        """Identify applicable schemes"""
        import asyncio
        
        farmer_profile = {
            "farmer_id": self.farmer_id,
            "personal_info": {"location": {"state": "Maharashtra"}},
            "farm_details": {"total_land_area": 2.0},
            "documents": ["Aadhaar card", "Bank account details"]
        }
        
        schemes = asyncio.run(self.agent.identify_applicable_schemes(farmer_profile))
        assert isinstance(schemes, list)
    
    @rule()
    def create_application(self):
        """Create a new application"""
        schemes = self.agent.scheme_db.get_all_schemes()
        if schemes:
            scheme = schemes[0]
            app = self.agent.create_scheme_application(
                self.farmer_id,
                scheme.scheme_id,
                ["Aadhaar card"]
            )
            if app:
                self.applications.append(app.application_id)
    
    @rule()
    def check_application_status(self):
        """Check status of existing applications"""
        if self.applications:
            app_id = self.applications[0]
            status = self.agent.get_application_status(app_id)
            assert status is not None
    
    @invariant()
    def applications_are_tracked(self):
        """All created applications should be retrievable"""
        for app_id in self.applications:
            app = self.agent.get_application_status(app_id)
            assert app is not None, f"Application {app_id} should be retrievable"


# Stateful testing for NGO connection workflow
class NGOConnectionWorkflow(RuleBasedStateMachine):
    """Stateful testing for complete NGO connection workflow"""
    
    def __init__(self):
        super().__init__()
        self.agent = NGOIntegrationAgent()
        self.farmer_id = f"FARMER{datetime.now().timestamp()}"
        self.connections = []
    
    @rule()
    def search_ngos(self):
        """Search for relevant NGOs"""
        farmer_profile = {
            "farmer_id": self.farmer_id,
            "personal_info": {"location": {"state": "Maharashtra"}}
        }
        
        matches = self.agent.find_relevant_ngos(farmer_profile, ["training"])
        assert isinstance(matches, list)
    
    @rule()
    def create_connection(self):
        """Create a farmer-NGO connection"""
        ngos = self.agent.ngo_db.get_ngos_by_region("Maharashtra")
        if ngos:
            ngo = ngos[0]
            conn = self.agent.connect_farmer_to_ngo(self.farmer_id, ngo.ngo_id)
            if conn:
                self.connections.append(conn.connection_id)
    
    @rule()
    def check_connections(self):
        """Check farmer's connections"""
        connections = self.agent.get_farmer_ngo_connections(self.farmer_id)
        assert isinstance(connections, list)
    
    @invariant()
    def connections_are_tracked(self):
        """All created connections should be retrievable"""
        for conn_id in self.connections:
            conn = self.agent.connection_manager.get_connection(conn_id)
            assert conn is not None, f"Connection {conn_id} should be retrievable"


# Run stateful tests
TestGovernmentSchemeWorkflow = GovernmentSchemeWorkflow.TestCase
TestNGOConnectionWorkflow = NGOConnectionWorkflow.TestCase
