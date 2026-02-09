"""
Security module for KrishiMitra platform.

This module provides encryption, access control, security utilities,
consent management, data deletion, privacy policy management,
security monitoring, breach response, and vulnerability scanning
for protecting farmer data and ensuring compliance with privacy requirements.
"""

from .encryption import EncryptionService, encrypt_sensitive_data, decrypt_sensitive_data, get_encryption_service
from .access_control import AccessControl, require_permission, require_farmer_access, get_current_user, get_access_control
from .audit import AuditLogger, log_data_access, log_data_modification, get_audit_logger
from .consent import ConsentManager, ConsentType, ConsentStatus, get_consent_manager
from .data_deletion import DataDeletionManager, DeletionStatus, DeletionScope, get_deletion_manager
from .privacy_policy import PrivacyPolicyManager, PolicyType, get_policy_manager
from .monitoring import SecurityMonitor, ThreatLevel, ThreatType, get_security_monitor
from .breach_response import BreachResponseManager, BreachType, BreachSeverity, get_breach_response_manager
from .vulnerability_scanner import VulnerabilityScanner, VulnerabilityType, VulnerabilitySeverity, get_vulnerability_scanner

__all__ = [
    "EncryptionService",
    "encrypt_sensitive_data", 
    "decrypt_sensitive_data",
    "get_encryption_service",
    "AccessControl",
    "require_permission",
    "require_farmer_access",
    "get_current_user",
    "get_access_control",
    "AuditLogger",
    "log_data_access",
    "log_data_modification",
    "get_audit_logger",
    "ConsentManager",
    "ConsentType",
    "ConsentStatus",
    "get_consent_manager",
    "DataDeletionManager",
    "DeletionStatus",
    "DeletionScope",
    "get_deletion_manager",
    "PrivacyPolicyManager",
    "PolicyType",
    "get_policy_manager",
    "SecurityMonitor",
    "ThreatLevel",
    "ThreatType",
    "get_security_monitor",
    "BreachResponseManager",
    "BreachType",
    "BreachSeverity",
    "get_breach_response_manager",
    "VulnerabilityScanner",
    "VulnerabilityType",
    "VulnerabilitySeverity",
    "get_vulnerability_scanner"
]