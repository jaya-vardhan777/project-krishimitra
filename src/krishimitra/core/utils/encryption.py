"""
Encryption and security utilities for KrishiMitra platform.

This module provides utilities for encrypting sensitive data,
hashing, and data masking for privacy protection.
"""

import hashlib
import secrets
import base64
import logging
from typing import Optional, Union, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import os

logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Exception raised when encryption/decryption fails."""
    pass


class EncryptionManager:
    """Manager class for encryption operations."""
    
    def __init__(self, master_key: Optional[str] = None):
        """
        Initialize encryption manager.
        
        Args:
            master_key: Master encryption key (if None, uses environment variable)
        """
        self.master_key = master_key or os.getenv('KRISHIMITRA_MASTER_KEY')
        if not self.master_key:
            logger.warning("No master key provided, generating temporary key")
            self.master_key = base64.urlsafe_b64encode(os.urandom(32)).decode()
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """
        Derive encryption key from password and salt.
        
        Args:
            password: Password string
            salt: Salt bytes
        
        Returns:
            Derived key bytes
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(password.encode())
    
    def encrypt_data(self, data: str, context: Optional[str] = None) -> str:
        """
        Encrypt sensitive data.
        
        Args:
            data: Data to encrypt
            context: Optional context for key derivation
        
        Returns:
            Base64 encoded encrypted data with salt
        """
        try:
            # Generate random salt
            salt = os.urandom(16)
            
            # Derive key
            key_material = self.master_key + (context or "")
            key = self._derive_key(key_material, salt)
            
            # Create Fernet cipher
            fernet = Fernet(base64.urlsafe_b64encode(key))
            
            # Encrypt data
            encrypted_data = fernet.encrypt(data.encode())
            
            # Combine salt and encrypted data
            combined = salt + encrypted_data
            
            # Return base64 encoded result
            return base64.urlsafe_b64encode(combined).decode()
            
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise EncryptionError(f"Failed to encrypt data: {e}")
    
    def decrypt_data(self, encrypted_data: str, context: Optional[str] = None) -> str:
        """
        Decrypt sensitive data.
        
        Args:
            encrypted_data: Base64 encoded encrypted data
            context: Optional context for key derivation
        
        Returns:
            Decrypted data string
        """
        try:
            # Decode base64
            combined = base64.urlsafe_b64decode(encrypted_data.encode())
            
            # Extract salt and encrypted data
            salt = combined[:16]
            encrypted_bytes = combined[16:]
            
            # Derive key
            key_material = self.master_key + (context or "")
            key = self._derive_key(key_material, salt)
            
            # Create Fernet cipher
            fernet = Fernet(base64.urlsafe_b64encode(key))
            
            # Decrypt data
            decrypted_data = fernet.decrypt(encrypted_bytes)
            
            return decrypted_data.decode()
            
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise EncryptionError(f"Failed to decrypt data: {e}")


# Global encryption manager instance
_encryption_manager = EncryptionManager()


def encrypt_sensitive_data(data: str, context: Optional[str] = None) -> str:
    """
    Encrypt sensitive data using the global encryption manager.
    
    Args:
        data: Data to encrypt
        context: Optional context for key derivation
    
    Returns:
        Encrypted data string
    """
    return _encryption_manager.encrypt_data(data, context)


def decrypt_sensitive_data(encrypted_data: str, context: Optional[str] = None) -> str:
    """
    Decrypt sensitive data using the global encryption manager.
    
    Args:
        encrypted_data: Encrypted data string
        context: Optional context for key derivation
    
    Returns:
        Decrypted data string
    """
    return _encryption_manager.decrypt_data(encrypted_data, context)


def hash_data(data: str, salt: Optional[str] = None) -> str:
    """
    Hash data using SHA-256 with optional salt.
    
    Args:
        data: Data to hash
        salt: Optional salt string
    
    Returns:
        Hexadecimal hash string
    """
    if salt:
        data_to_hash = data + salt
    else:
        data_to_hash = data
    
    return hashlib.sha256(data_to_hash.encode()).hexdigest()


def generate_salt(length: int = 32) -> str:
    """
    Generate a random salt string.
    
    Args:
        length: Length of salt in bytes
    
    Returns:
        Base64 encoded salt string
    """
    salt_bytes = secrets.token_bytes(length)
    return base64.urlsafe_b64encode(salt_bytes).decode()


def hash_password(password: str, salt: Optional[str] = None) -> Dict[str, str]:
    """
    Hash password with salt using PBKDF2.
    
    Args:
        password: Password to hash
        salt: Optional salt (if None, generates new salt)
    
    Returns:
        Dictionary with 'hash' and 'salt' keys
    """
    if salt is None:
        salt_bytes = os.urandom(32)
        salt = base64.urlsafe_b64encode(salt_bytes).decode()
    else:
        salt_bytes = base64.urlsafe_b64decode(salt.encode())
    
    # Use PBKDF2 for password hashing
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt_bytes,
        iterations=100000,
        backend=default_backend()
    )
    
    password_hash = kdf.derive(password.encode())
    hash_b64 = base64.urlsafe_b64encode(password_hash).decode()
    
    return {
        'hash': hash_b64,
        'salt': salt
    }


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """
    Verify password against stored hash.
    
    Args:
        password: Password to verify
        stored_hash: Stored password hash
        salt: Salt used for hashing
    
    Returns:
        True if password matches
    """
    try:
        result = hash_password(password, salt)
        return secrets.compare_digest(result['hash'], stored_hash)
    except Exception as e:
        logger.error(f"Password verification failed: {e}")
        return False


def mask_sensitive_data(data: str, data_type: str = "general") -> str:
    """
    Mask sensitive data for logging and display.
    
    Args:
        data: Data to mask
        data_type: Type of data (phone, email, aadhaar, pan, account, general)
    
    Returns:
        Masked data string
    """
    if not data:
        return ""
    
    if data_type == "phone":
        # Mask phone number: +91XXXXXX1234 -> +91XXXXXX****
        if len(data) >= 10:
            return data[:-4] + "****"
        return "****"
    
    elif data_type == "email":
        # Mask email: user@example.com -> u***@example.com
        if "@" in data:
            local, domain = data.split("@", 1)
            if len(local) > 1:
                masked_local = local[0] + "*" * (len(local) - 1)
            else:
                masked_local = "*"
            return f"{masked_local}@{domain}"
        return "****"
    
    elif data_type == "aadhaar":
        # Mask Aadhaar: 123456789012 -> XXXX-XXXX-9012
        if len(data) >= 12:
            return f"XXXX-XXXX-{data[-4:]}"
        return "XXXX-XXXX-XXXX"
    
    elif data_type == "pan":
        # Mask PAN: ABCDE1234F -> ABC**1234*
        if len(data) >= 10:
            return f"{data[:3]}**{data[5:9]}*"
        return "**********"
    
    elif data_type == "account":
        # Mask account number: 1234567890123456 -> XXXX-XXXX-XXXX-3456
        if len(data) >= 4:
            masked_part = "X" * (len(data) - 4)
            return f"{masked_part}{data[-4:]}"
        return "XXXX"
    
    else:  # general
        # Mask general data: show first and last character
        if len(data) <= 2:
            return "*" * len(data)
        elif len(data) <= 4:
            return data[0] + "*" * (len(data) - 2) + data[-1]
        else:
            return data[0] + "*" * (len(data) - 2) + data[-1]


def generate_api_key(prefix: str = "km", length: int = 32) -> str:
    """
    Generate API key with prefix.
    
    Args:
        prefix: Key prefix
        length: Length of random part
    
    Returns:
        API key string
    """
    random_part = secrets.token_urlsafe(length)
    return f"{prefix}_{random_part}"


def generate_secure_token(length: int = 32) -> str:
    """
    Generate cryptographically secure token.
    
    Args:
        length: Token length in bytes
    
    Returns:
        URL-safe base64 encoded token
    """
    return secrets.token_urlsafe(length)


def encrypt_field_data(data: Dict[str, Any], sensitive_fields: list) -> Dict[str, Any]:
    """
    Encrypt specific fields in a dictionary.
    
    Args:
        data: Dictionary containing data
        sensitive_fields: List of field names to encrypt
    
    Returns:
        Dictionary with encrypted sensitive fields
    """
    encrypted_data = data.copy()
    
    for field in sensitive_fields:
        if field in encrypted_data and encrypted_data[field]:
            try:
                encrypted_data[field] = encrypt_sensitive_data(
                    str(encrypted_data[field]), 
                    context=field
                )
                logger.debug(f"Encrypted field: {field}")
            except Exception as e:
                logger.error(f"Failed to encrypt field {field}: {e}")
                # Keep original value if encryption fails
    
    return encrypted_data


def decrypt_field_data(data: Dict[str, Any], sensitive_fields: list) -> Dict[str, Any]:
    """
    Decrypt specific fields in a dictionary.
    
    Args:
        data: Dictionary containing encrypted data
        sensitive_fields: List of field names to decrypt
    
    Returns:
        Dictionary with decrypted sensitive fields
    """
    decrypted_data = data.copy()
    
    for field in sensitive_fields:
        if field in decrypted_data and decrypted_data[field]:
            try:
                decrypted_data[field] = decrypt_sensitive_data(
                    decrypted_data[field], 
                    context=field
                )
                logger.debug(f"Decrypted field: {field}")
            except Exception as e:
                logger.error(f"Failed to decrypt field {field}: {e}")
                # Keep encrypted value if decryption fails
    
    return decrypted_data


def create_data_hash(data: Dict[str, Any], fields: Optional[list] = None) -> str:
    """
    Create hash of dictionary data for integrity checking.
    
    Args:
        data: Dictionary to hash
        fields: Optional list of specific fields to include in hash
    
    Returns:
        SHA-256 hash of the data
    """
    if fields:
        hash_data_dict = {k: v for k, v in data.items() if k in fields}
    else:
        hash_data_dict = data
    
    # Sort keys for consistent hashing
    sorted_data = dict(sorted(hash_data_dict.items()))
    
    # Convert to string representation
    data_string = str(sorted_data)
    
    return hashlib.sha256(data_string.encode()).hexdigest()


def verify_data_integrity(data: Dict[str, Any], expected_hash: str, fields: Optional[list] = None) -> bool:
    """
    Verify data integrity using hash comparison.
    
    Args:
        data: Dictionary to verify
        expected_hash: Expected hash value
        fields: Optional list of specific fields to include in hash
    
    Returns:
        True if data integrity is verified
    """
    current_hash = create_data_hash(data, fields)
    return secrets.compare_digest(current_hash, expected_hash)