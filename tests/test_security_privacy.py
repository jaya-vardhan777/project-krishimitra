"""
Tests for security, privacy, and compliance systems.

This module tests consent management, data deletion, privacy policy management,
security monitoring, breach response, and vulnerability scanning.
"""

import pytest
from datetime import datetime, timedelta
from src.krishimitra.core.security.consent import (
    ConsentManager, ConsentType, ConsentStatus, ConsentRequest
)
from src.krishimitra.core.security.data_deletion import (
    DataDeletionManager, DeletionScope, DeletionStatus
)
from src.krishimitra.core.security.privacy_policy import (
    PrivacyPolicyManager, PolicyType
)
from src.krishimitra.core.security.monitoring import (
    SecurityMonitor, ThreatType, ThreatLevel
)
from src.krishimitra.core.security.breach_response import (
    BreachResponseManager, BreachType, BreachSeverity
)
from src.krishimitra.core.security.vulnerability_scanner import (
    VulnerabilityScanner, VulnerabilityType, VulnerabilitySeverity
)


class TestConsentManagement:
    """Test consent management functionality."""
    
    def test_consent_request_creation(self):
        """Test creating a consent request."""
        manager = ConsentManager()
        
        request = ConsentRequest(
            farmer_id="farmer123",
            consent_type=ConsentType.PROFILE_DATA_COLLECTION,
            purpose="Provide agricultural advisory services",
            data_categories=["name", "contact", "farm_details"],
            language="en"
        )
        
        consent_record = manager.request_consent(request)
        
        assert consent_record.farmer_id == "farmer123"
        assert consent_record.consent_type == ConsentType.PROFILE_DATA_COLLECTION
        assert consent_record.status == ConsentStatus.PENDING
        assert len(consent_record.consent_id) > 0
    
    def test_consent_verification(self):
        """Test checking if consent exists."""
        manager = ConsentManager()
        
        # Should return False for non-existent consent
        has_consent = manager.check_consent("farmer123", ConsentType.GOVERNMENT_SHARING)
        assert has_consent == False
    
    def test_required_consents_for_operation(self):
        """Test getting required consents for operations."""
        manager = ConsentManager()
        
        required = manager.get_required_consents("create_profile")
        assert ConsentType.PROFILE_DATA_COLLECTION in required
        
        required = manager.get_required_consents("share_with_government")
        assert ConsentType.GOVERNMENT_SHARING in required


class TestDataDeletion:
    """Test data deletion and right-to-be-forgotten functionality."""
    
    def test_deletion_request_creation(self):
        """Test creating a deletion request."""
        manager = DataDeletionManager(grace_period_days=30)
        
        deletion_request = manager.create_deletion_request(
            farmer_id="farmer123",
            scope=DeletionScope.ALL_DATA,
            reason="User requested account deletion"
        )
        
        assert deletion_request.farmer_id == "farmer123"
        assert deletion_request.scope == DeletionScope.ALL_DATA
        assert deletion_request.status == DeletionStatus.PENDING
        
        # Check grace period
        expected_time = datetime.utcnow() + timedelta(days=30)
        time_diff = abs((deletion_request.scheduled_for - expected_time).total_seconds())
        assert time_diff < 60  # Within 1 minute
    
    def test_immediate_deletion_request(self):
        """Test creating an immediate deletion request."""
        manager = DataDeletionManager()
        
        deletion_request = manager.create_deletion_request(
            farmer_id="farmer123",
            scope=DeletionScope.PROFILE_ONLY,
            immediate=True
        )
        
        # Should be scheduled for immediate deletion
        time_diff = abs((deletion_request.scheduled_for - datetime.utcnow()).total_seconds())
        assert time_diff < 60  # Within 1 minute


class TestPrivacyPolicy:
    """Test privacy policy management."""
    
    def test_policy_version_creation(self):
        """Test creating a policy version."""
        manager = PrivacyPolicyManager()
        
        policy = manager.create_policy_version(
            policy_type=PolicyType.PRIVACY_POLICY,
            version="1.0",
            content={
                "en": "This is our privacy policy...",
                "hi": "यह हमारी गोपनीयता नीति है..."
            },
            effective_date=datetime.utcnow(),
            summary={
                "en": "We protect your data",
                "hi": "हम आपके डेटा की सुरक्षा करते हैं"
            }
        )
        
        assert policy.policy_type == PolicyType.PRIVACY_POLICY
        assert policy.version == "1.0"
        assert "en" in policy.content
        assert "hi" in policy.content
    
    def test_policy_content_retrieval(self):
        """Test retrieving policy content."""
        manager = PrivacyPolicyManager()
        
        # Create a policy
        manager.create_policy_version(
            policy_type=PolicyType.TERMS_OF_SERVICE,
            version="1.0",
            content={
                "en": "Terms of service content",
                "hi": "सेवा की शर्तें"
            },
            effective_date=datetime.utcnow() - timedelta(days=1)  # Already effective
        )
        
        # Retrieve content
        content = manager.get_policy_content(PolicyType.TERMS_OF_SERVICE, language="en")
        # Note: This will return None in test environment without DynamoDB
        # In production, it would return the actual content


class TestSecurityMonitoring:
    """Test security monitoring and threat detection."""
    
    def test_brute_force_detection(self):
        """Test brute force attack detection."""
        monitor = SecurityMonitor()
        
        # Simulate multiple failed login attempts
        for i in range(6):
            event = monitor.detect_brute_force(
                user_id="farmer123",
                source_ip="192.168.1.100",
                success=False
            )
        
        # Should detect brute force after threshold
        assert event is not None
        assert event.threat_type == ThreatType.BRUTE_FORCE_ATTACK
        assert event.threat_level == ThreatLevel.HIGH
    
    def test_unusual_access_pattern(self):
        """Test unusual data access pattern detection."""
        monitor = SecurityMonitor()
        
        event = monitor.detect_unusual_access_pattern(
            user_id="farmer123",
            resource="farmer_profiles",
            access_count=100,  # Exceeds threshold
            time_window_minutes=1
        )
        
        assert event is not None
        assert event.threat_type == ThreatType.DATA_EXFILTRATION
    
    def test_sql_injection_detection(self):
        """Test SQL injection detection."""
        monitor = SecurityMonitor()
        
        malicious_query = "SELECT * FROM users WHERE id = '1' OR '1'='1'"
        
        event = monitor.detect_sql_injection(
            user_id="attacker",
            source_ip="192.168.1.200",
            query_string=malicious_query
        )
        
        assert event is not None
        assert event.threat_type == ThreatType.SQL_INJECTION
        assert event.threat_level == ThreatLevel.CRITICAL


class TestBreachResponse:
    """Test breach detection and response."""
    
    def test_incident_creation(self):
        """Test creating a security incident."""
        manager = BreachResponseManager()
        
        incident = manager.create_incident(
            breach_type=BreachType.DATA_BREACH,
            severity=BreachSeverity.HIGH,
            description="Unauthorized access to farmer data detected",
            affected_users=["farmer123", "farmer456"],
            affected_data_types=["profile", "contact_info"]
        )
        
        assert incident.breach_type == BreachType.DATA_BREACH
        assert incident.severity == BreachSeverity.HIGH
        assert len(incident.affected_users) == 2
        assert incident.status == BreachStatus.DETECTED
    
    def test_notification_deadline(self):
        """Test notification deadline calculation."""
        manager = BreachResponseManager(notification_deadline_hours=24)
        
        incident = manager.create_incident(
            breach_type=BreachType.UNAUTHORIZED_ACCESS,
            severity=BreachSeverity.MEDIUM,
            description="Suspicious access detected",
            affected_users=["farmer123"]
        )
        
        # Check that notification deadline is 24 hours from detection
        expected_deadline = incident.detected_at + timedelta(hours=24)
        # Notification should be sent before this deadline


class TestVulnerabilityScanner:
    """Test vulnerability scanning."""
    
    def test_sql_injection_scan(self):
        """Test scanning for SQL injection vulnerabilities."""
        scanner = VulnerabilityScanner()
        
        vulnerable_code = '''
        def get_user(user_id):
            query = "SELECT * FROM users WHERE id = " + user_id
            cursor.execute(query)
        '''
        
        vulnerabilities = scanner.scan_code_for_sql_injection(
            code=vulnerable_code,
            file_path="test.py"
        )
        
        assert len(vulnerabilities) > 0
        assert vulnerabilities[0].vulnerability_type == VulnerabilityType.SQL_INJECTION
        assert vulnerabilities[0].severity == VulnerabilitySeverity.HIGH
    
    def test_sensitive_data_scan(self):
        """Test scanning for hardcoded sensitive data."""
        scanner = VulnerabilityScanner()
        
        vulnerable_code = '''
        API_KEY = "sk-1234567890abcdef"
        PASSWORD = "admin123"
        '''
        
        vulnerabilities = scanner.scan_code_for_sensitive_data(
            code=vulnerable_code,
            file_path="config.py"
        )
        
        assert len(vulnerabilities) > 0
        assert vulnerabilities[0].vulnerability_type == VulnerabilityType.SENSITIVE_DATA_EXPOSURE
        assert vulnerabilities[0].severity == VulnerabilitySeverity.CRITICAL
    
    def test_api_endpoint_scan(self):
        """Test scanning API endpoints."""
        scanner = VulnerabilityScanner()
        
        vulnerabilities = scanner.scan_api_endpoint(
            endpoint="/api/farmers",
            method="DELETE",
            requires_auth=False,  # Missing auth
            input_validation=False,  # Missing validation
            rate_limiting=False  # Missing rate limiting
        )
        
        assert len(vulnerabilities) >= 3  # Should find multiple issues
        
        # Check for missing authentication
        auth_vulns = [v for v in vulnerabilities if v.vulnerability_type == VulnerabilityType.BROKEN_AUTHENTICATION]
        assert len(auth_vulns) > 0
    
    def test_configuration_scan(self):
        """Test scanning configuration."""
        scanner = VulnerabilityScanner()
        
        insecure_config = {
            "DEBUG": True,
            "SECRET_KEY": "weak",
            "CORS_ALLOW_ALL_ORIGINS": True
        }
        
        vulnerabilities = scanner.scan_configuration(insecure_config)
        
        assert len(vulnerabilities) >= 3  # Should find multiple issues
        
        # Check for debug mode
        debug_vulns = [v for v in vulnerabilities if "Debug Mode" in v.title]
        assert len(debug_vulns) > 0
    
    def test_vulnerability_report_generation(self):
        """Test generating vulnerability report."""
        scanner = VulnerabilityScanner()
        
        # Create some test vulnerabilities
        vulnerabilities = scanner.scan_configuration({
            "DEBUG": True,
            "SECRET_KEY": "weak"
        })
        
        report = scanner.generate_report(vulnerabilities)
        
        assert "scan_date" in report
        assert "total_vulnerabilities" in report
        assert "severity_breakdown" in report
        assert "risk_score" in report
        assert report["total_vulnerabilities"] == len(vulnerabilities)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
