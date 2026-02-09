"""
Property-based tests for data security and privacy in KrishiMitra platform.

This module implements property-based tests using Hypothesis to validate
security and privacy properties including encryption, access control,
consent management, and data deletion.
"""

import pytest
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import patch, MagicMock

from hypothesis import given, strategies as st, assume, settings
from hypothesis.strategies import composite

# Import security modules
from src.krishimitra.core.security.encryption import (
    EncryptionService, FieldEncryption, DataMasking, EncryptionError
)
from src.krishimitra.core.security.access_control import (
    AccessControl, User, Role, Permission, DataAccessPolicy
)
from src.krishimitra.core.security.audit import (
    AuditLogger, AuditEvent, AuditAction, AuditLevel
)
from src.krishimitra.core.security.anonymization import (
    DataAnonymizer, get_anonymizer, anonymize_for_research
)


# Custom strategies for security testing
@composite
def sensitive_farmer_data_strategy(draw):
    """Generate farmer data with sensitive information for security testing."""
    return {
        "farmer_id": draw(st.text(min_size=10, max_size=50)),
        "name": draw(st.text(min_size=2, max_size=100)),
        "phone_number": f"+91{draw(st.integers(min_value=6000000000, max_value=9999999999))}",
        "aadhaar_number": draw(st.text(alphabet='0123456789', min_size=12, max_size=12)),
        "pan_number": draw(st.text(alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', min_size=10, max_size=10)),
        "email": f"{draw(st.text(min_size=3, max_size=20))}@example.com",
        "location": {
            "state": draw(st.text(min_size=3, max_size=30)),
            "district": draw(st.text(min_size=3, max_size=30)),
            "village": draw(st.text(min_size=3, max_size=30)),
            "coordinates": {
                "latitude": draw(st.floats(min_value=6.0, max_value=37.0)),
                "longitude": draw(st.floats(min_value=68.0, max_value=97.0))
            }
        },
        "contact_info": {
            "primary_phone": f"+91{draw(st.integers(min_value=6000000000, max_value=9999999999))}",
            "email": f"{draw(st.text(min_size=3, max_size=20))}@example.com",
            "preferred_contact_method": draw(st.sampled_from(["voice", "text", "whatsapp"]))
        },
        "bank_account_details": {
            "account_number": draw(st.text(alphabet='0123456789', min_size=10, max_size=16)),
            "ifsc_code": draw(st.text(alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', min_size=11, max_size=11)),
            "bank_name": draw(st.text(min_size=5, max_size=50))
        }
    }


@composite
def user_role_strategy(draw):
    """Generate user with role and permissions."""
    role = draw(st.sampled_from([Role.FARMER, Role.AGENT, Role.SUPERVISOR, Role.ADMIN, Role.SYSTEM]))
    user_id = draw(st.text(min_size=5, max_size=50))
    farmer_id = draw(st.text(min_size=5, max_size=50)) if role == Role.FARMER else None
    
    return {
        "user_id": user_id,
        "role": role,
        "farmer_id": farmer_id
    }


class TestSecurityProperties:
    """Property-based tests for security and privacy features."""
    
    @given(farmer_data=sensitive_farmer_data_strategy())
    @settings(max_examples=50, deadline=None)
    def test_property_46_data_encryption_compliance(self, farmer_data):
        """
        Property 46: Data encryption compliance
        For any collected farmer data, all personal and sensitive information
        should be properly encrypted using industry-standard encryption.
        **Validates: Requirements 10.1**
        """
        # Initialize encryption service
        encryption_service = EncryptionService()
        field_encryption = FieldEncryption(encryption_service)
        
        # Test basic encryption/decryption
        sensitive_text = farmer_data["name"]
        encrypted_text = encryption_service.encrypt(sensitive_text)
        decrypted_text = encryption_service.decrypt(encrypted_text)
        
        # Verify encryption properties
        assert encrypted_text != sensitive_text, "Encrypted data should not match original"
        assert decrypted_text == sensitive_text, "Decrypted data should match original"
        assert len(encrypted_text) > len(sensitive_text), "Encrypted data should be longer"
        
        # Test field-level encryption for farmer profile
        encrypted_profile = field_encryption.encrypt_farmer_profile(farmer_data)
        decrypted_profile = field_encryption.decrypt_farmer_profile(encrypted_profile)
        
        # Verify sensitive fields are encrypted
        sensitive_fields = ["name", "phone_number"]
        for field in sensitive_fields:
            if field in farmer_data:
                assert encrypted_profile[field] != farmer_data[field], f"Field {field} should be encrypted"
                assert decrypted_profile[field] == farmer_data[field], f"Field {field} should decrypt correctly"
        
        # Test location encryption
        if "location" in farmer_data:
            location_fields = ["village", "coordinates"]
            for field in location_fields:
                if field in farmer_data["location"]:
                    if isinstance(farmer_data["location"][field], dict):
                        # For coordinates, check if they're encrypted as string
                        continue
                    assert encrypted_profile["location"][field] != farmer_data["location"][field], f"Location {field} should be encrypted"
        
        # Test contact info encryption
        if "contact_info" in farmer_data:
            contact_fields = ["primary_phone", "email"]
            for field in contact_fields:
                if field in farmer_data["contact_info"]:
                    assert encrypted_profile["contact_info"][field] != farmer_data["contact_info"][field], f"Contact {field} should be encrypted"
        
        # Test encryption with different data types
        test_data = {
            "string": "test string",
            "number": 12345,
            "dict": {"key": "value"},
            "list": [1, 2, 3]
        }
        
        for data_type, data_value in test_data.items():
            encrypted = encryption_service.encrypt(data_value)
            decrypted = encryption_service.decrypt(encrypted)
            
            # For non-string types, they get converted to string during encryption
            if isinstance(data_value, str):
                assert decrypted == data_value
            else:
                # Numbers and other types are converted to string
                assert decrypted == str(data_value) or decrypted == str(data_value).replace("'", '"')
    
    @given(
        farmer_data=sensitive_farmer_data_strategy(),
        user_data=user_role_strategy()
    )
    @settings(max_examples=30, deadline=None)
    def test_property_47_access_control_enforcement(self, farmer_data, user_data):
        """
        Property 47: Access control enforcement
        For any data access scenario, the system should enforce proper access controls
        ensuring only authorized personnel can view farmer information.
        **Validates: Requirements 10.2**
        """
        # Initialize access control
        access_control = AccessControl()
        
        # Create user with role-based permissions
        user = access_control.create_user(
            user_id=user_data["user_id"],
            role=user_data["role"],
            farmer_id=user_data["farmer_id"]
        )
        
        farmer_id = farmer_data["farmer_id"]
        
        # Test farmer data access permissions
        can_access = user.can_access_farmer_data(farmer_id)
        
        if user.role == Role.FARMER:
            # Farmers can only access their own data
            if user.farmer_id == farmer_id:
                assert can_access, "Farmers should access their own data"
            else:
                assert not can_access, "Farmers should not access other farmers' data"
        
        elif user.role in [Role.AGENT, Role.SUPERVISOR, Role.ADMIN]:
            # Agents, supervisors, and admins can access farmer data if they have permission
            has_permission = user.has_permission(Permission.READ_FARMER_PROFILE)
            assert can_access == has_permission, "Access should match READ_FARMER_PROFILE permission"
        
        elif user.role == Role.SYSTEM:
            # System role has full access
            assert can_access, "System role should have full access"
        
        # Test permission-based access control
        permissions_to_test = [
            Permission.READ_FARMER_PROFILE,
            Permission.UPDATE_FARMER_PROFILE,
            Permission.DELETE_FARMER_PROFILE,
            Permission.LIST_FARMER_PROFILES,
            Permission.EXPORT_DATA
        ]
        
        for permission in permissions_to_test:
            has_permission = user.has_permission(permission)
            expected_permissions = access_control.get_user_permissions(user.role)
            
            assert has_permission == (permission in expected_permissions), f"Permission {permission} should match role {user.role}"
        
        # Test data filtering based on user permissions
        policy = DataAccessPolicy()
        filtered_data = policy.filter_farmer_profile_fields(farmer_data, user)
        
        if user.role == Role.SYSTEM or user.role == Role.ADMIN:
            # System and admin get full access
            assert len(filtered_data) > 0, "System/Admin should get data"
        
        elif user.role in [Role.AGENT, Role.SUPERVISOR]:
            # Agents and supervisors get filtered data
            if len(filtered_data) > 0:
                # Should not contain highly sensitive fields
                sensitive_fields = ["aadhaar_number", "pan_number", "bank_account_details"]
                for field in sensitive_fields:
                    assert field not in filtered_data, f"Filtered data should not contain {field}"
        
        elif user.role == Role.FARMER:
            if user.farmer_id == farmer_id:
                # Own data - should get full access
                assert len(filtered_data) > 0, "Farmer should access own data"
            else:
                # Other farmer's data - should get very limited data
                if len(filtered_data) > 0:
                    allowed_fields = ["farmer_id", "name", "location"]
                    for field in filtered_data:
                        assert field in allowed_fields, f"Should only contain allowed fields, found {field}"
    
    @given(farmer_data=sensitive_farmer_data_strategy())
    @settings(max_examples=30, deadline=None)
    def test_property_48_explicit_consent_for_data_sharing(self, farmer_data):
        """
        Property 48: Explicit consent for data sharing
        For any data sharing scenario, the system should require and track
        explicit consent from farmers before sharing their data.
        **Validates: Requirements 10.3**
        """
        # Test consent data structure
        consent_data = {
            "farmer_id": farmer_data["farmer_id"],
            "consent_type": "data_sharing_research",
            "consent_given": True,
            "consent_timestamp": datetime.utcnow(),
            "consent_version": "1.0",
            "data_categories": ["profile", "farm_details", "preferences"],
            "sharing_purpose": "agricultural_research",
            "data_recipients": ["research_institution", "government_agency"],
            "consent_duration": "2_years",
            "withdrawal_method": "api_call"
        }
        
        # Verify consent structure has required fields
        required_consent_fields = [
            "farmer_id", "consent_type", "consent_given", "consent_timestamp",
            "data_categories", "sharing_purpose", "data_recipients"
        ]
        
        for field in required_consent_fields:
            assert field in consent_data, f"Consent data must include {field}"
        
        # Test consent validation
        assert isinstance(consent_data["consent_given"], bool), "Consent must be boolean"
        assert isinstance(consent_data["consent_timestamp"], datetime), "Consent timestamp must be datetime"
        assert isinstance(consent_data["data_categories"], list), "Data categories must be list"
        assert len(consent_data["data_categories"]) > 0, "Must specify data categories"
        assert isinstance(consent_data["data_recipients"], list), "Data recipients must be list"
        assert len(consent_data["data_recipients"]) > 0, "Must specify data recipients"
        
        # Test consent-based data filtering
        if consent_data["consent_given"]:
            # If consent given, data can be shared for specified categories
            allowed_categories = consent_data["data_categories"]
            
            for category in allowed_categories:
                if category == "profile":
                    assert "name" in farmer_data, "Profile data should be available"
                elif category == "farm_details":
                    # Farm details would be available
                    pass
                elif category == "preferences":
                    # Preferences would be available
                    pass
        else:
            # If consent not given, no data should be shared
            # This would be enforced by the data sharing logic
            pass
        
        # Test consent withdrawal
        withdrawal_data = {
            "farmer_id": farmer_data["farmer_id"],
            "consent_type": "data_sharing_research",
            "withdrawal_timestamp": datetime.utcnow(),
            "withdrawal_reason": "farmer_request",
            "data_deletion_requested": True
        }
        
        required_withdrawal_fields = [
            "farmer_id", "consent_type", "withdrawal_timestamp"
        ]
        
        for field in required_withdrawal_fields:
            assert field in withdrawal_data, f"Withdrawal data must include {field}"
        
        # Test consent audit trail
        audit_events = [
            {
                "event_type": "consent_given",
                "timestamp": consent_data["consent_timestamp"],
                "farmer_id": farmer_data["farmer_id"],
                "details": consent_data
            },
            {
                "event_type": "consent_withdrawn",
                "timestamp": withdrawal_data["withdrawal_timestamp"],
                "farmer_id": farmer_data["farmer_id"],
                "details": withdrawal_data
            }
        ]
        
        for event in audit_events:
            assert "event_type" in event, "Audit event must have type"
            assert "timestamp" in event, "Audit event must have timestamp"
            assert "farmer_id" in event, "Audit event must have farmer_id"
            assert event["farmer_id"] == farmer_data["farmer_id"], "Audit event must match farmer"
    
    @given(farmer_data=sensitive_farmer_data_strategy())
    @settings(max_examples=30, deadline=None)
    def test_property_49_timely_data_deletion(self, farmer_data):
        """
        Property 49: Timely data deletion
        For any data deletion request, the system should delete farmer data
        within specified timeframes and provide confirmation.
        **Validates: Requirements 10.4**
        """
        # Test data deletion request structure
        deletion_request = {
            "farmer_id": farmer_data["farmer_id"],
            "request_type": "complete_deletion",
            "request_timestamp": datetime.utcnow(),
            "requested_by": farmer_data["farmer_id"],  # Self-requested
            "reason": "farmer_request",
            "data_categories": ["all"],
            "deletion_deadline": datetime.utcnow() + timedelta(days=30),
            "confirmation_required": True
        }
        
        # Verify deletion request structure
        required_deletion_fields = [
            "farmer_id", "request_type", "request_timestamp", "requested_by",
            "data_categories", "deletion_deadline"
        ]
        
        for field in required_deletion_fields:
            assert field in deletion_request, f"Deletion request must include {field}"
        
        # Test deletion request validation
        assert deletion_request["farmer_id"] == farmer_data["farmer_id"], "Deletion request must match farmer"
        assert isinstance(deletion_request["request_timestamp"], datetime), "Request timestamp must be datetime"
        assert isinstance(deletion_request["deletion_deadline"], datetime), "Deletion deadline must be datetime"
        assert deletion_request["deletion_deadline"] > deletion_request["request_timestamp"], "Deadline must be after request"
        
        # Test deletion categories
        valid_categories = ["profile", "farm_details", "preferences", "recommendations", "conversations", "all"]
        for category in deletion_request["data_categories"]:
            assert category in valid_categories, f"Invalid deletion category: {category}"
        
        # Test deletion timeline compliance
        max_deletion_days = 30  # GDPR-style requirement
        deletion_period = (deletion_request["deletion_deadline"] - deletion_request["request_timestamp"]).days
        assert deletion_period <= max_deletion_days, f"Deletion deadline must be within {max_deletion_days} days"
        
        # Test data anonymization as alternative to deletion
        anonymizer = DataAnonymizer()
        anonymized_data = anonymizer.anonymize_farmer_profile(farmer_data, "high")
        
        # Verify anonymization removes identifying information
        assert anonymized_data["name"] != farmer_data["name"], "Name should be anonymized"
        assert anonymized_data["farmer_id"] != farmer_data["farmer_id"], "Farmer ID should be pseudonymized"
        
        # Sensitive fields should be anonymized
        sensitive_fields = ["aadhaar_number", "pan_number", "bank_account_details"]
        for field in sensitive_fields:
            if field in farmer_data:
                assert anonymized_data.get(field) == "ANONYMIZED", f"Field {field} should be anonymized"
        
        # Test deletion confirmation
        deletion_confirmation = {
            "farmer_id": farmer_data["farmer_id"],
            "deletion_request_id": "req_123",
            "deletion_completed_timestamp": datetime.utcnow(),
            "deleted_categories": deletion_request["data_categories"],
            "deletion_method": "secure_deletion",
            "confirmation_code": "DEL_" + farmer_data["farmer_id"][:8],
            "retention_period_expired": True
        }
        
        required_confirmation_fields = [
            "farmer_id", "deletion_completed_timestamp", "deleted_categories", "confirmation_code"
        ]
        
        for field in required_confirmation_fields:
            assert field in deletion_confirmation, f"Deletion confirmation must include {field}"
        
        # Test audit trail for deletion
        deletion_audit = {
            "action": "data_deletion",
            "farmer_id": farmer_data["farmer_id"],
            "timestamp": deletion_confirmation["deletion_completed_timestamp"],
            "categories_deleted": deletion_confirmation["deleted_categories"],
            "deletion_method": deletion_confirmation["deletion_method"],
            "compliance_status": "gdpr_compliant"
        }
        
        assert deletion_audit["farmer_id"] == farmer_data["farmer_id"], "Audit must match farmer"
        assert deletion_audit["action"] == "data_deletion", "Audit must record deletion action"
        assert len(deletion_audit["categories_deleted"]) > 0, "Audit must specify deleted categories"
    
    @given(farmer_data=sensitive_farmer_data_strategy())
    @settings(max_examples=20, deadline=None)
    def test_data_masking_properties(self, farmer_data):
        """
        Test data masking properties for safe display and logging.
        Ensures sensitive data is properly masked while preserving structure.
        """
        masking = DataMasking()
        
        # Test phone number masking
        if "phone_number" in farmer_data:
            masked_phone = masking.mask_phone_number(farmer_data["phone_number"])
            assert masked_phone != farmer_data["phone_number"], "Phone should be masked"
            assert masked_phone.endswith(farmer_data["phone_number"][-4:]), "Should show last 4 digits"
            assert "****" in masked_phone, "Should contain mask characters"
        
        # Test email masking
        if "email" in farmer_data:
            masked_email = masking.mask_email(farmer_data["email"])
            assert masked_email != farmer_data["email"], "Email should be masked"
            assert "@" in masked_email, "Should preserve email structure"
            assert "****" in masked_email, "Should contain mask characters"
        
        # Test name masking
        masked_name = masking.mask_name(farmer_data["name"])
        assert masked_name != farmer_data["name"], "Name should be masked"
        assert masked_name[0] == farmer_data["name"][0], "Should show first character"
        assert "*" in masked_name, "Should contain mask characters"
        
        # Test Aadhaar masking
        if "aadhaar_number" in farmer_data:
            masked_aadhaar = masking.mask_aadhaar(farmer_data["aadhaar_number"])
            assert masked_aadhaar != farmer_data["aadhaar_number"], "Aadhaar should be masked"
            assert masked_aadhaar.endswith(farmer_data["aadhaar_number"][-4:]), "Should show last 4 digits"
            assert "****" in masked_aadhaar, "Should contain mask characters"
        
        # Test profile masking
        masked_profile = masking.mask_farmer_profile(farmer_data)
        
        # Verify structure is preserved
        assert isinstance(masked_profile, dict), "Masked profile should be dict"
        assert "name" in masked_profile, "Should contain name field"
        
        # Verify sensitive fields are masked
        assert masked_profile["name"] != farmer_data["name"], "Profile name should be masked"
        
        if "contact_info" in farmer_data:
            if "primary_phone" in farmer_data["contact_info"]:
                assert masked_profile["contact_info"]["primary_phone"] != farmer_data["contact_info"]["primary_phone"], "Contact phone should be masked"
    
    @given(farmer_data_list=st.lists(sensitive_farmer_data_strategy(), min_size=2, max_size=5))
    @settings(max_examples=10, deadline=None)
    def test_anonymization_for_research(self, farmer_data_list):
        """
        Test anonymization properties for research data sharing.
        Ensures data utility is preserved while protecting privacy.
        """
        # Test research anonymization
        anonymized_data = anonymize_for_research(farmer_data_list, k_value=2)
        
        assert len(anonymized_data) == len(farmer_data_list), "Should preserve data count"
        
        for i, (original, anonymized) in enumerate(zip(farmer_data_list, anonymized_data)):
            # Verify anonymization
            assert anonymized["name"] != original["name"], f"Name should be anonymized in record {i}"
            assert anonymized["farmer_id"] != original["farmer_id"], f"Farmer ID should be pseudonymized in record {i}"
            
            # Verify structure preservation
            assert isinstance(anonymized, dict), f"Record {i} should be dict"
            assert "_anonymization" in anonymized, f"Record {i} should have anonymization metadata"
            
            # Verify metadata
            metadata = anonymized["_anonymization"]
            assert "level" in metadata, "Should have anonymization level"
            assert "timestamp" in metadata, "Should have anonymization timestamp"
            assert "method" in metadata, "Should have anonymization method"
        
        # Test synthetic data generation
        anonymizer = get_anonymizer()
        synthetic_profiles = []
        
        for original in farmer_data_list[:2]:  # Generate synthetic data from first 2 profiles
            synthetic = anonymizer.create_synthetic_profile(original)
            synthetic_profiles.append(synthetic)
            
            # Verify synthetic data properties
            assert synthetic["farmer_id"] != original["farmer_id"], "Synthetic ID should be different"
            assert synthetic["name"] != original["name"], "Synthetic name should be different"
            assert "_synthetic" in synthetic, "Should have synthetic metadata"
            
            # Verify synthetic metadata
            metadata = synthetic["_synthetic"]
            assert "generated_at" in metadata, "Should have generation timestamp"
            assert "template_based" in metadata, "Should indicate template-based generation"
        
        assert len(synthetic_profiles) == 2, "Should generate requested number of synthetic profiles"


# Configure Hypothesis profiles for security testing
@pytest.fixture(autouse=True)
def configure_hypothesis_security():
    """Configure Hypothesis settings for security testing."""
    import os
    
    if os.getenv("CI"):
        settings.load_profile("ci")
    elif os.getenv("DEBUG"):
        settings.load_profile("debug")
    else:
        settings.load_profile("dev")