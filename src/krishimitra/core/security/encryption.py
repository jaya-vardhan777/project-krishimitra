"""
Encryption utilities for KrishiMitra platform.

This module provides encryption and decryption services for sensitive farmer data
using industry-standard cryptographic libraries and best practices.
"""

import base64
import os
from typing import Optional, Dict, Any, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import json
import logging

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    Service for encrypting and decrypting sensitive data.
    
    Uses Fernet (symmetric encryption) for data encryption with key derivation
    from environment variables or configuration.
    """
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize encryption service.
        
        Args:
            encryption_key: Base64-encoded encryption key. If None, generates from environment.
        """
        if encryption_key:
            self.key = encryption_key.encode()
        else:
            # Get key from environment or generate one
            env_key = os.getenv("KRISHIMITRA_ENCRYPTION_KEY")
            if env_key:
                self.key = env_key.encode()
            else:
                # Generate a key from a password and salt
                password = os.getenv("KRISHIMITRA_ENCRYPTION_PASSWORD", "default-dev-password").encode()
                salt = os.getenv("KRISHIMITRA_ENCRYPTION_SALT", "default-dev-salt").encode()
                
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                    backend=default_backend()
                )
                self.key = base64.urlsafe_b64encode(kdf.derive(password))
        
        self.fernet = Fernet(self.key)
    
    def encrypt(self, data: Union[str, Dict[str, Any]]) -> str:
        """
        Encrypt data using Fernet symmetric encryption.
        
        Args:
            data: Data to encrypt (string or dictionary)
            
        Returns:
            Base64-encoded encrypted data
        """
        try:
            if isinstance(data, dict):
                data = json.dumps(data, default=str)
            elif not isinstance(data, str):
                data = str(data)
            
            encrypted_data = self.fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
        
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise EncryptionError(f"Failed to encrypt data: {e}")
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt data using Fernet symmetric encryption.
        
        Args:
            encrypted_data: Base64-encoded encrypted data
            
        Returns:
            Decrypted data as string
        """
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self.fernet.decrypt(encrypted_bytes)
            return decrypted_data.decode()
        
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise EncryptionError(f"Failed to decrypt data: {e}")
    
    def encrypt_dict(self, data: Dict[str, Any]) -> Dict[str, str]:
        """
        Encrypt dictionary values while preserving keys.
        
        Args:
            data: Dictionary with values to encrypt
            
        Returns:
            Dictionary with encrypted values
        """
        encrypted_dict = {}
        for key, value in data.items():
            if value is not None:
                encrypted_dict[key] = self.encrypt(value)
            else:
                encrypted_dict[key] = None
        return encrypted_dict
    
    def decrypt_dict(self, encrypted_data: Dict[str, str]) -> Dict[str, Any]:
        """
        Decrypt dictionary values.
        
        Args:
            encrypted_data: Dictionary with encrypted values
            
        Returns:
            Dictionary with decrypted values
        """
        decrypted_dict = {}
        for key, value in encrypted_data.items():
            if value is not None:
                try:
                    decrypted_value = self.decrypt(value)
                    # Try to parse as JSON first
                    try:
                        decrypted_dict[key] = json.loads(decrypted_value)
                    except json.JSONDecodeError:
                        decrypted_dict[key] = decrypted_value
                except EncryptionError:
                    # If decryption fails, keep original value (might not be encrypted)
                    decrypted_dict[key] = value
            else:
                decrypted_dict[key] = None
        return decrypted_dict


class FieldEncryption:
    """
    Utility for encrypting specific fields in data structures.
    
    Provides field-level encryption for sensitive data while leaving
    non-sensitive fields in plaintext for querying and indexing.
    """
    
    def __init__(self, encryption_service: EncryptionService):
        """
        Initialize field encryption utility.
        
        Args:
            encryption_service: Encryption service instance
        """
        self.encryption_service = encryption_service
        
        # Define which fields should be encrypted
        self.sensitive_fields = {
            "farmer_profile": [
                "name", "father_name", "aadhaar_number", "pan_number",
                "phone_number", "email", "bank_account_details"
            ],
            "location": [
                "street", "village", "coordinates"
            ],
            "contact_info": [
                "primary_phone", "secondary_phone", "whatsapp_number", "email"
            ]
        }
    
    def encrypt_farmer_profile(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt sensitive fields in farmer profile data.
        
        Args:
            profile_data: Farmer profile data
            
        Returns:
            Profile data with sensitive fields encrypted
        """
        encrypted_data = profile_data.copy()
        
        # Encrypt top-level sensitive fields
        for field in self.sensitive_fields.get("farmer_profile", []):
            if field in encrypted_data and encrypted_data[field] is not None:
                encrypted_data[field] = self.encryption_service.encrypt(encrypted_data[field])
        
        # Encrypt location fields
        if "location" in encrypted_data and encrypted_data["location"]:
            location = encrypted_data["location"].copy()
            for field in self.sensitive_fields.get("location", []):
                if field in location and location[field] is not None:
                    location[field] = self.encryption_service.encrypt(location[field])
            encrypted_data["location"] = location
        
        # Encrypt contact info fields
        if "contact_info" in encrypted_data and encrypted_data["contact_info"]:
            contact_info = encrypted_data["contact_info"].copy()
            for field in self.sensitive_fields.get("contact_info", []):
                if field in contact_info and contact_info[field] is not None:
                    contact_info[field] = self.encryption_service.encrypt(contact_info[field])
            encrypted_data["contact_info"] = contact_info
        
        return encrypted_data
    
    def decrypt_farmer_profile(self, encrypted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt sensitive fields in farmer profile data.
        
        Args:
            encrypted_data: Farmer profile data with encrypted fields
            
        Returns:
            Profile data with sensitive fields decrypted
        """
        decrypted_data = encrypted_data.copy()
        
        # Decrypt top-level sensitive fields
        for field in self.sensitive_fields.get("farmer_profile", []):
            if field in decrypted_data and decrypted_data[field] is not None:
                try:
                    decrypted_data[field] = self.encryption_service.decrypt(decrypted_data[field])
                except EncryptionError:
                    # Field might not be encrypted, keep original value
                    pass
        
        # Decrypt location fields
        if "location" in decrypted_data and decrypted_data["location"]:
            location = decrypted_data["location"].copy()
            for field in self.sensitive_fields.get("location", []):
                if field in location and location[field] is not None:
                    try:
                        location[field] = self.encryption_service.decrypt(location[field])
                    except EncryptionError:
                        # Field might not be encrypted, keep original value
                        pass
            decrypted_data["location"] = location
        
        # Decrypt contact info fields
        if "contact_info" in decrypted_data and decrypted_data["contact_info"]:
            contact_info = decrypted_data["contact_info"].copy()
            for field in self.sensitive_fields.get("contact_info", []):
                if field in contact_info and contact_info[field] is not None:
                    try:
                        contact_info[field] = self.encryption_service.decrypt(contact_info[field])
                    except EncryptionError:
                        # Field might not be encrypted, keep original value
                        pass
            decrypted_data["contact_info"] = contact_info
        
        return decrypted_data


class DataMasking:
    """
    Utility for masking sensitive data for display or logging purposes.
    
    Provides methods to mask sensitive information while preserving
    data structure and some readability for debugging.
    """
    
    @staticmethod
    def mask_phone_number(phone: str) -> str:
        """Mask phone number, showing only last 4 digits."""
        if not phone or len(phone) < 4:
            return "****"
        return f"****{phone[-4:]}"
    
    @staticmethod
    def mask_email(email: str) -> str:
        """Mask email address, showing only domain."""
        if not email or "@" not in email:
            return "****@****.***"
        local, domain = email.split("@", 1)
        return f"****@{domain}"
    
    @staticmethod
    def mask_aadhaar(aadhaar: str) -> str:
        """Mask Aadhaar number, showing only last 4 digits."""
        if not aadhaar or len(aadhaar) < 4:
            return "****"
        return f"****-****-{aadhaar[-4:]}"
    
    @staticmethod
    def mask_name(name: str) -> str:
        """Mask name, showing only first letter and length."""
        if not name:
            return "****"
        return f"{name[0]}{'*' * (len(name) - 1)}"
    
    def mask_farmer_profile(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mask sensitive fields in farmer profile for safe display.
        
        Args:
            profile_data: Farmer profile data
            
        Returns:
            Profile data with sensitive fields masked
        """
        masked_data = profile_data.copy()
        
        # Mask sensitive fields
        if "name" in masked_data:
            masked_data["name"] = self.mask_name(masked_data["name"])
        
        if "aadhaar_number" in masked_data:
            masked_data["aadhaar_number"] = self.mask_aadhaar(masked_data["aadhaar_number"])
        
        if "contact_info" in masked_data and masked_data["contact_info"]:
            contact_info = masked_data["contact_info"].copy()
            if "primary_phone" in contact_info:
                contact_info["primary_phone"] = self.mask_phone_number(contact_info["primary_phone"])
            if "email" in contact_info:
                contact_info["email"] = self.mask_email(contact_info["email"])
            masked_data["contact_info"] = contact_info
        
        return masked_data


class EncryptionError(Exception):
    """Exception raised for encryption/decryption errors."""
    pass


# Global encryption service instance
_encryption_service = None


def get_encryption_service() -> EncryptionService:
    """Get global encryption service instance."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


def encrypt_sensitive_data(data: Union[str, Dict[str, Any]]) -> str:
    """
    Convenience function to encrypt sensitive data.
    
    Args:
        data: Data to encrypt
        
    Returns:
        Encrypted data as base64 string
    """
    return get_encryption_service().encrypt(data)


def decrypt_sensitive_data(encrypted_data: str) -> str:
    """
    Convenience function to decrypt sensitive data.
    
    Args:
        encrypted_data: Encrypted data as base64 string
        
    Returns:
        Decrypted data as string
    """
    return get_encryption_service().decrypt(encrypted_data)