"""
Privacy policy management for KrishiMitra platform.

This module provides privacy policy versioning, farmer acceptance tracking,
and policy update notifications.
"""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class PolicyType(str, Enum):
    """Types of policies."""
    
    PRIVACY_POLICY = "privacy_policy"
    TERMS_OF_SERVICE = "terms_of_service"
    DATA_USAGE_POLICY = "data_usage_policy"
    COOKIE_POLICY = "cookie_policy"


class PolicyVersion(BaseModel):
    """Model for policy version."""
    
    policy_id: str = Field(..., description="Unique policy ID")
    policy_type: PolicyType = Field(..., description="Type of policy")
    version: str = Field(..., description="Version number (e.g., 1.0, 1.1)")
    effective_date: datetime = Field(..., description="When policy becomes effective")
    content: Dict[str, str] = Field(..., description="Policy content by language")
    summary: Dict[str, str] = Field(default_factory=dict, description="Summary by language")
    changes_from_previous: Dict[str, List[str]] = Field(default_factory=dict, description="Key changes by language")
    is_active: bool = Field(default=True, description="Whether this version is active")
    requires_acceptance: bool = Field(default=True, description="Whether farmers must accept")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class PolicyAcceptance(BaseModel):
    """Model for policy acceptance record."""
    
    acceptance_id: str = Field(..., description="Unique acceptance ID")
    farmer_id: str = Field(..., description="Farmer ID")
    policy_id: str = Field(..., description="Policy ID")
    policy_type: PolicyType = Field(..., description="Type of policy")
    version: str = Field(..., description="Version accepted")
    accepted_at: datetime = Field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = Field(None, description="IP address when accepted")
    user_agent: Optional[str] = Field(None, description="User agent when accepted")
    language: str = Field(default="en", description="Language of policy shown")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class PrivacyPolicyManager:
    """
    Manager for privacy policy versioning and acceptance tracking.
    
    Provides methods to manage policy versions, track farmer acceptance,
    and notify farmers of policy updates.
    """
    
    def __init__(
        self,
        policy_table_name: str = "PrivacyPolicies",
        acceptance_table_name: str = "PolicyAcceptances"
    ):
        """
        Initialize privacy policy manager.
        
        Args:
            policy_table_name: DynamoDB table for policy versions
            acceptance_table_name: DynamoDB table for acceptance records
        """
        self.policy_table_name = policy_table_name
        self.acceptance_table_name = acceptance_table_name
        
        self.dynamodb = boto3.resource('dynamodb')
        
        self.policy_table = None
        self.acceptance_table = None
        
        try:
            self.policy_table = self.dynamodb.Table(self.policy_table_name)
        except Exception as e:
            logger.warning(f"Could not connect to policy table: {e}")
        
        try:
            self.acceptance_table = self.dynamodb.Table(self.acceptance_table_name)
        except Exception as e:
            logger.warning(f"Could not connect to acceptance table: {e}")
    
    def _generate_policy_id(self, policy_type: PolicyType, version: str) -> str:
        """Generate unique policy ID."""
        return f"{policy_type.value}_{version}"
    
    def _generate_acceptance_id(self, farmer_id: str, policy_id: str) -> str:
        """Generate unique acceptance ID."""
        import uuid
        return f"{farmer_id}_{policy_id}_{uuid.uuid4().hex[:8]}"
    
    def create_policy_version(
        self,
        policy_type: PolicyType,
        version: str,
        content: Dict[str, str],
        effective_date: datetime,
        summary: Optional[Dict[str, str]] = None,
        changes_from_previous: Optional[Dict[str, List[str]]] = None,
        requires_acceptance: bool = True
    ) -> PolicyVersion:
        """
        Create a new policy version.
        
        Args:
            policy_type: Type of policy
            version: Version number
            content: Policy content by language code
            effective_date: When policy becomes effective
            summary: Summary by language code
            changes_from_previous: Key changes by language code
            requires_acceptance: Whether farmers must accept
            
        Returns:
            Policy version record
        """
        policy_id = self._generate_policy_id(policy_type, version)
        
        policy_version = PolicyVersion(
            policy_id=policy_id,
            policy_type=policy_type,
            version=version,
            effective_date=effective_date,
            content=content,
            summary=summary or {},
            changes_from_previous=changes_from_previous or {},
            requires_acceptance=requires_acceptance
        )
        
        # Store in DynamoDB
        if self.policy_table:
            try:
                self.policy_table.put_item(Item=json.loads(policy_version.json()))
                logger.info(f"Created policy version {policy_id}")
            except ClientError as e:
                logger.error(f"Failed to store policy version: {e}")
        
        return policy_version
    
    def get_active_policy(
        self,
        policy_type: PolicyType
    ) -> Optional[PolicyVersion]:
        """
        Get the active version of a policy.
        
        Args:
            policy_type: Type of policy
            
        Returns:
            Active policy version or None
        """
        if not self.policy_table:
            logger.error("Policy table not available")
            return None
        
        try:
            # Query for active policies of this type
            response = self.policy_table.query(
                IndexName="policy_type-index",
                KeyConditionExpression="policy_type = :type",
                FilterExpression="is_active = :active AND effective_date <= :now",
                ExpressionAttributeValues={
                    ":type": policy_type.value,
                    ":active": True,
                    ":now": datetime.utcnow().isoformat()
                },
                ScanIndexForward=False,  # Get most recent first
                Limit=1
            )
            
            items = response.get("Items", [])
            if items:
                return PolicyVersion(**items[0])
            
            return None
        
        except ClientError as e:
            logger.error(f"Failed to get active policy: {e}")
            return None
    
    def get_policy_version(
        self,
        policy_id: str
    ) -> Optional[PolicyVersion]:
        """
        Get a specific policy version.
        
        Args:
            policy_id: Policy ID
            
        Returns:
            Policy version or None
        """
        if not self.policy_table:
            logger.error("Policy table not available")
            return None
        
        try:
            response = self.policy_table.get_item(Key={"policy_id": policy_id})
            
            if "Item" in response:
                return PolicyVersion(**response["Item"])
            
            return None
        
        except ClientError as e:
            logger.error(f"Failed to get policy version: {e}")
            return None
    
    def record_acceptance(
        self,
        farmer_id: str,
        policy_id: str,
        policy_type: PolicyType,
        version: str,
        language: str = "en",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> PolicyAcceptance:
        """
        Record farmer's acceptance of a policy.
        
        Args:
            farmer_id: Farmer ID
            policy_id: Policy ID
            policy_type: Type of policy
            version: Version accepted
            language: Language of policy shown
            ip_address: IP address when accepted
            user_agent: User agent when accepted
            
        Returns:
            Policy acceptance record
        """
        acceptance_id = self._generate_acceptance_id(farmer_id, policy_id)
        
        acceptance = PolicyAcceptance(
            acceptance_id=acceptance_id,
            farmer_id=farmer_id,
            policy_id=policy_id,
            policy_type=policy_type,
            version=version,
            language=language,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Store in DynamoDB
        if self.acceptance_table:
            try:
                self.acceptance_table.put_item(Item=json.loads(acceptance.json()))
                logger.info(f"Recorded policy acceptance for farmer {farmer_id}")
            except ClientError as e:
                logger.error(f"Failed to store policy acceptance: {e}")
        
        return acceptance
    
    def get_farmer_acceptances(
        self,
        farmer_id: str,
        policy_type: Optional[PolicyType] = None
    ) -> List[PolicyAcceptance]:
        """
        Get all policy acceptances for a farmer.
        
        Args:
            farmer_id: Farmer ID
            policy_type: Filter by policy type
            
        Returns:
            List of policy acceptances
        """
        if not self.acceptance_table:
            logger.error("Acceptance table not available")
            return []
        
        try:
            query_params = {
                "IndexName": "farmer_id-index",
                "KeyConditionExpression": "farmer_id = :farmer_id",
                "ExpressionAttributeValues": {":farmer_id": farmer_id}
            }
            
            if policy_type:
                query_params["FilterExpression"] = "policy_type = :type"
                query_params["ExpressionAttributeValues"][":type"] = policy_type.value
            
            response = self.acceptance_table.query(**query_params)
            
            acceptances = []
            for item in response.get("Items", []):
                try:
                    acceptances.append(PolicyAcceptance(**item))
                except Exception as e:
                    logger.warning(f"Failed to parse acceptance record: {e}")
            
            return acceptances
        
        except ClientError as e:
            logger.error(f"Failed to query acceptances: {e}")
            return []
    
    def has_accepted_current_policy(
        self,
        farmer_id: str,
        policy_type: PolicyType
    ) -> bool:
        """
        Check if farmer has accepted the current active policy.
        
        Args:
            farmer_id: Farmer ID
            policy_type: Type of policy
            
        Returns:
            True if farmer has accepted current policy
        """
        # Get active policy
        active_policy = self.get_active_policy(policy_type)
        if not active_policy:
            # No active policy, so no acceptance required
            return True
        
        # Get farmer's acceptances
        acceptances = self.get_farmer_acceptances(farmer_id, policy_type)
        
        # Check if any acceptance matches current version
        for acceptance in acceptances:
            if acceptance.version == active_policy.version:
                return True
        
        return False
    
    def get_policies_requiring_acceptance(
        self,
        farmer_id: str
    ) -> List[PolicyVersion]:
        """
        Get all policies that require farmer's acceptance.
        
        Args:
            farmer_id: Farmer ID
            
        Returns:
            List of policies requiring acceptance
        """
        policies_requiring_acceptance = []
        
        for policy_type in PolicyType:
            if not self.has_accepted_current_policy(farmer_id, policy_type):
                active_policy = self.get_active_policy(policy_type)
                if active_policy and active_policy.requires_acceptance:
                    policies_requiring_acceptance.append(active_policy)
        
        return policies_requiring_acceptance
    
    def get_policy_content(
        self,
        policy_type: PolicyType,
        language: str = "en",
        version: Optional[str] = None
    ) -> Optional[str]:
        """
        Get policy content in specified language.
        
        Args:
            policy_type: Type of policy
            language: Language code
            version: Specific version (if None, gets active version)
            
        Returns:
            Policy content or None
        """
        if version:
            policy_id = self._generate_policy_id(policy_type, version)
            policy = self.get_policy_version(policy_id)
        else:
            policy = self.get_active_policy(policy_type)
        
        if not policy:
            return None
        
        # Get content in requested language, fallback to English
        return policy.content.get(language) or policy.content.get("en")
    
    def get_policy_summary(
        self,
        policy_type: PolicyType,
        language: str = "en"
    ) -> Optional[str]:
        """
        Get policy summary in specified language.
        
        Args:
            policy_type: Type of policy
            language: Language code
            
        Returns:
            Policy summary or None
        """
        policy = self.get_active_policy(policy_type)
        
        if not policy:
            return None
        
        # Get summary in requested language, fallback to English
        return policy.summary.get(language) or policy.summary.get("en")


# Global privacy policy manager instance
_policy_manager = None


def get_policy_manager() -> PrivacyPolicyManager:
    """Get global privacy policy manager instance."""
    global _policy_manager
    if _policy_manager is None:
        _policy_manager = PrivacyPolicyManager()
    return _policy_manager
