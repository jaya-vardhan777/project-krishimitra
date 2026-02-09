"""
Consent management system for KrishiMitra platform.

This module provides explicit consent collection and tracking for data sharing,
ensuring compliance with privacy regulations and farmer data protection requirements.
"""

import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, asdict
from pydantic import BaseModel, Field
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class ConsentType(str, Enum):
    """Types of consent that can be requested."""
    
    # Data collection consent
    PROFILE_DATA_COLLECTION = "profile_data_collection"
    LOCATION_DATA_COLLECTION = "location_data_collection"
    FARM_DATA_COLLECTION = "farm_data_collection"
    SENSOR_DATA_COLLECTION = "sensor_data_collection"
    
    # Data usage consent
    RECOMMENDATION_GENERATION = "recommendation_generation"
    ANALYTICS_PROCESSING = "analytics_processing"
    RESEARCH_PURPOSES = "research_purposes"
    
    # Data sharing consent
    GOVERNMENT_SHARING = "government_sharing"
    NGO_SHARING = "ngo_sharing"
    MARKET_INTELLIGENCE_SHARING = "market_intelligence_sharing"
    THIRD_PARTY_SHARING = "third_party_sharing"
    
    # Communication consent
    SMS_NOTIFICATIONS = "sms_notifications"
    WHATSAPP_MESSAGES = "whatsapp_messages"
    VOICE_CALLS = "voice_calls"
    EMAIL_COMMUNICATIONS = "email_communications"


class ConsentStatus(str, Enum):
    """Status of consent."""
    
    GRANTED = "granted"
    DENIED = "denied"
    REVOKED = "revoked"
    EXPIRED = "expired"
    PENDING = "pending"


class ConsentRecord(BaseModel):
    """Model for consent record."""
    
    consent_id: str = Field(..., description="Unique consent record ID")
    farmer_id: str = Field(..., description="Farmer ID")
    consent_type: ConsentType = Field(..., description="Type of consent")
    status: ConsentStatus = Field(..., description="Current consent status")
    granted_at: Optional[datetime] = Field(None, description="When consent was granted")
    revoked_at: Optional[datetime] = Field(None, description="When consent was revoked")
    expires_at: Optional[datetime] = Field(None, description="When consent expires")
    purpose: str = Field(..., description="Purpose of data usage")
    data_categories: List[str] = Field(default_factory=list, description="Categories of data covered")
    third_party_recipients: List[str] = Field(default_factory=list, description="Third parties who may receive data")
    consent_text: str = Field(..., description="Text of consent shown to farmer")
    language: str = Field(default="en", description="Language of consent")
    ip_address: Optional[str] = Field(None, description="IP address when consent was given")
    user_agent: Optional[str] = Field(None, description="User agent when consent was given")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ConsentRequest(BaseModel):
    """Model for consent request."""
    
    farmer_id: str
    consent_type: ConsentType
    purpose: str
    data_categories: List[str]
    third_party_recipients: List[str] = Field(default_factory=list)
    language: str = "en"
    expires_in_days: Optional[int] = None


class ConsentManager:
    """
    Manager for consent collection and tracking.
    
    Provides methods to request, grant, revoke, and track consent for data usage
    and sharing, ensuring compliance with privacy regulations.
    """
    
    def __init__(self, dynamodb_table_name: str = "FarmerConsents"):
        """
        Initialize consent manager.
        
        Args:
            dynamodb_table_name: Name of DynamoDB table for storing consents
        """
        self.table_name = dynamodb_table_name
        self.dynamodb = boto3.resource('dynamodb')
        self.table = None
        
        try:
            self.table = self.dynamodb.Table(self.table_name)
        except Exception as e:
            logger.warning(f"Could not connect to DynamoDB table {self.table_name}: {e}")
    
    def _generate_consent_id(self, farmer_id: str, consent_type: ConsentType) -> str:
        """Generate unique consent ID."""
        import uuid
        return f"{farmer_id}_{consent_type.value}_{uuid.uuid4().hex[:8]}"
    
    def _get_consent_text(self, consent_type: ConsentType, language: str = "en") -> str:
        """
        Get consent text for specific type and language.
        
        Args:
            consent_type: Type of consent
            language: Language code
            
        Returns:
            Consent text in specified language
        """
        # Consent text templates (in production, these would be in a database)
        consent_texts = {
            ConsentType.PROFILE_DATA_COLLECTION: {
                "en": "I consent to KrishiMitra collecting and storing my personal profile information including name, contact details, and farm information for providing agricultural advisory services.",
                "hi": "मैं कृषिमित्र को कृषि सलाहकार सेवाएं प्रदान करने के लिए अपनी व्यक्तिगत प्रोफ़ाइल जानकारी एकत्र करने और संग्रहीत करने की सहमति देता हूं।"
            },
            ConsentType.GOVERNMENT_SHARING: {
                "en": "I consent to KrishiMitra sharing my data with government agencies for accessing agricultural schemes, subsidies, and benefits.",
                "hi": "मैं कृषिमित्र को कृषि योजनाओं, सब्सिडी और लाभों तक पहुंचने के लिए सरकारी एजेंसियों के साथ मेरा डेटा साझा करने की सहमति देता हूं।"
            },
            ConsentType.WHATSAPP_MESSAGES: {
                "en": "I consent to receiving agricultural advice and notifications via WhatsApp messages from KrishiMitra.",
                "hi": "मैं कृषिमित्र से व्हाट्सएप संदेशों के माध्यम से कृषि सलाह और सूचनाएं प्राप्त करने की सहमति देता हूं।"
            }
        }
        
        return consent_texts.get(consent_type, {}).get(language, 
            f"I consent to {consent_type.value} by KrishiMitra platform.")
    
    def request_consent(
        self,
        request: ConsentRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> ConsentRecord:
        """
        Create a consent request for farmer.
        
        Args:
            request: Consent request details
            ip_address: IP address of request
            user_agent: User agent of request
            
        Returns:
            Consent record with pending status
        """
        consent_id = self._generate_consent_id(request.farmer_id, request.consent_type)
        consent_text = self._get_consent_text(request.consent_type, request.language)
        
        expires_at = None
        if request.expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)
        
        consent_record = ConsentRecord(
            consent_id=consent_id,
            farmer_id=request.farmer_id,
            consent_type=request.consent_type,
            status=ConsentStatus.PENDING,
            purpose=request.purpose,
            data_categories=request.data_categories,
            third_party_recipients=request.third_party_recipients,
            consent_text=consent_text,
            language=request.language,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Store in DynamoDB
        if self.table:
            try:
                self.table.put_item(Item=json.loads(consent_record.json()))
                logger.info(f"Created consent request {consent_id} for farmer {request.farmer_id}")
            except ClientError as e:
                logger.error(f"Failed to store consent request: {e}")
        
        return consent_record
    
    def grant_consent(
        self,
        consent_id: str,
        farmer_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[ConsentRecord]:
        """
        Grant consent for a pending request.
        
        Args:
            consent_id: ID of consent to grant
            farmer_id: Farmer ID (for verification)
            ip_address: IP address when consent was granted
            user_agent: User agent when consent was granted
            
        Returns:
            Updated consent record or None if not found
        """
        if not self.table:
            logger.error("DynamoDB table not available")
            return None
        
        try:
            # Get existing consent record
            response = self.table.get_item(Key={"consent_id": consent_id})
            
            if "Item" not in response:
                logger.warning(f"Consent record {consent_id} not found")
                return None
            
            item = response["Item"]
            
            # Verify farmer_id matches
            if item.get("farmer_id") != farmer_id:
                logger.warning(f"Farmer ID mismatch for consent {consent_id}")
                return None
            
            # Update consent status
            now = datetime.utcnow()
            self.table.update_item(
                Key={"consent_id": consent_id},
                UpdateExpression="SET #status = :status, granted_at = :granted_at, ip_address = :ip, user_agent = :ua",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": ConsentStatus.GRANTED.value,
                    ":granted_at": now.isoformat(),
                    ":ip": ip_address,
                    ":ua": user_agent
                }
            )
            
            logger.info(f"Granted consent {consent_id} for farmer {farmer_id}")
            
            # Return updated record
            item["status"] = ConsentStatus.GRANTED.value
            item["granted_at"] = now.isoformat()
            return ConsentRecord(**item)
        
        except ClientError as e:
            logger.error(f"Failed to grant consent: {e}")
            return None
    
    def revoke_consent(
        self,
        consent_id: str,
        farmer_id: str,
        reason: Optional[str] = None
    ) -> Optional[ConsentRecord]:
        """
        Revoke previously granted consent.
        
        Args:
            consent_id: ID of consent to revoke
            farmer_id: Farmer ID (for verification)
            reason: Reason for revocation
            
        Returns:
            Updated consent record or None if not found
        """
        if not self.table:
            logger.error("DynamoDB table not available")
            return None
        
        try:
            # Get existing consent record
            response = self.table.get_item(Key={"consent_id": consent_id})
            
            if "Item" not in response:
                logger.warning(f"Consent record {consent_id} not found")
                return None
            
            item = response["Item"]
            
            # Verify farmer_id matches
            if item.get("farmer_id") != farmer_id:
                logger.warning(f"Farmer ID mismatch for consent {consent_id}")
                return None
            
            # Update consent status
            now = datetime.utcnow()
            update_expr = "SET #status = :status, revoked_at = :revoked_at"
            expr_values = {
                ":status": ConsentStatus.REVOKED.value,
                ":revoked_at": now.isoformat()
            }
            
            if reason:
                update_expr += ", revocation_reason = :reason"
                expr_values[":reason"] = reason
            
            self.table.update_item(
                Key={"consent_id": consent_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues=expr_values
            )
            
            logger.info(f"Revoked consent {consent_id} for farmer {farmer_id}")
            
            # Return updated record
            item["status"] = ConsentStatus.REVOKED.value
            item["revoked_at"] = now.isoformat()
            return ConsentRecord(**item)
        
        except ClientError as e:
            logger.error(f"Failed to revoke consent: {e}")
            return None
    
    def get_farmer_consents(
        self,
        farmer_id: str,
        consent_type: Optional[ConsentType] = None,
        status: Optional[ConsentStatus] = None
    ) -> List[ConsentRecord]:
        """
        Get all consents for a farmer.
        
        Args:
            farmer_id: Farmer ID
            consent_type: Filter by consent type
            status: Filter by status
            
        Returns:
            List of consent records
        """
        if not self.table:
            logger.error("DynamoDB table not available")
            return []
        
        try:
            # Query by farmer_id (assuming GSI exists)
            filter_expr = None
            expr_values = {}
            
            if consent_type:
                filter_expr = "consent_type = :type"
                expr_values[":type"] = consent_type.value
            
            if status:
                if filter_expr:
                    filter_expr += " AND #status = :status"
                else:
                    filter_expr = "#status = :status"
                expr_values[":status"] = status.value
            
            query_params = {
                "IndexName": "farmer_id-index",
                "KeyConditionExpression": "farmer_id = :farmer_id",
                "ExpressionAttributeValues": {":farmer_id": farmer_id, **expr_values}
            }
            
            if filter_expr:
                query_params["FilterExpression"] = filter_expr
                query_params["ExpressionAttributeNames"] = {"#status": "status"}
            
            response = self.table.query(**query_params)
            
            consents = []
            for item in response.get("Items", []):
                try:
                    consents.append(ConsentRecord(**item))
                except Exception as e:
                    logger.warning(f"Failed to parse consent record: {e}")
            
            return consents
        
        except ClientError as e:
            logger.error(f"Failed to query consents: {e}")
            return []
    
    def check_consent(
        self,
        farmer_id: str,
        consent_type: ConsentType
    ) -> bool:
        """
        Check if farmer has granted consent for specific type.
        
        Args:
            farmer_id: Farmer ID
            consent_type: Type of consent to check
            
        Returns:
            True if consent is granted and not expired
        """
        consents = self.get_farmer_consents(
            farmer_id=farmer_id,
            consent_type=consent_type,
            status=ConsentStatus.GRANTED
        )
        
        now = datetime.utcnow()
        for consent in consents:
            # Check if consent is not expired
            if consent.expires_at is None or consent.expires_at > now:
                return True
        
        return False
    
    def get_required_consents(self, operation: str) -> List[ConsentType]:
        """
        Get required consents for a specific operation.
        
        Args:
            operation: Operation name
            
        Returns:
            List of required consent types
        """
        # Define required consents for different operations
        operation_consents = {
            "create_profile": [ConsentType.PROFILE_DATA_COLLECTION],
            "collect_location": [ConsentType.LOCATION_DATA_COLLECTION],
            "collect_farm_data": [ConsentType.FARM_DATA_COLLECTION],
            "generate_recommendations": [
                ConsentType.PROFILE_DATA_COLLECTION,
                ConsentType.RECOMMENDATION_GENERATION
            ],
            "share_with_government": [
                ConsentType.PROFILE_DATA_COLLECTION,
                ConsentType.GOVERNMENT_SHARING
            ],
            "send_whatsapp": [ConsentType.WHATSAPP_MESSAGES],
            "analytics": [
                ConsentType.PROFILE_DATA_COLLECTION,
                ConsentType.ANALYTICS_PROCESSING
            ]
        }
        
        return operation_consents.get(operation, [])
    
    def verify_operation_consent(
        self,
        farmer_id: str,
        operation: str
    ) -> tuple[bool, List[ConsentType]]:
        """
        Verify if farmer has all required consents for an operation.
        
        Args:
            farmer_id: Farmer ID
            operation: Operation name
            
        Returns:
            Tuple of (has_all_consents, missing_consents)
        """
        required_consents = self.get_required_consents(operation)
        missing_consents = []
        
        for consent_type in required_consents:
            if not self.check_consent(farmer_id, consent_type):
                missing_consents.append(consent_type)
        
        return len(missing_consents) == 0, missing_consents


# Global consent manager instance
_consent_manager = None


def get_consent_manager() -> ConsentManager:
    """Get global consent manager instance."""
    global _consent_manager
    if _consent_manager is None:
        _consent_manager = ConsentManager()
    return _consent_manager
