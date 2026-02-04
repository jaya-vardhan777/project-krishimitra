"""
Validation utilities for KrishiMitra platform.

This module contains validation functions for various data types
including Indian-specific formats like phone numbers, Aadhaar, PAN, etc.
"""

import re
from typing import Optional, Tuple, Dict, Any
from decimal import Decimal, InvalidOperation
import logging

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Exception raised when validation fails."""
    pass


def validate_phone_number(phone: str, country_code: str = "+91") -> Tuple[bool, Optional[str]]:
    """
    Validate Indian phone number format.
    
    Args:
        phone: Phone number to validate
        country_code: Country code (default: +91 for India)
    
    Returns:
        Tuple of (is_valid, normalized_phone_number)
    """
    if not phone:
        return False, None
    
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    # Handle different formats
    if cleaned.startswith('+91'):
        mobile_part = cleaned[3:]
    elif cleaned.startswith('91') and len(cleaned) == 12:
        mobile_part = cleaned[2:]
    elif cleaned.startswith('0') and len(cleaned) == 11:
        mobile_part = cleaned[1:]
    elif len(cleaned) == 10:
        mobile_part = cleaned
    else:
        return False, None
    
    # Validate mobile number format (Indian mobile numbers start with 6-9)
    if not re.match(r'^[6-9]\d{9}$', mobile_part):
        return False, None
    
    normalized = f"{country_code}{mobile_part}"
    return True, normalized


def validate_aadhaar_number(aadhaar: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Aadhaar number format and checksum.
    
    Args:
        aadhaar: Aadhaar number to validate
    
    Returns:
        Tuple of (is_valid, normalized_aadhaar)
    """
    if not aadhaar:
        return False, None
    
    # Remove all non-digit characters
    cleaned = re.sub(r'\D', '', aadhaar)
    
    # Check length
    if len(cleaned) != 12:
        return False, None
    
    # Check if all digits are same (invalid Aadhaar)
    if len(set(cleaned)) == 1:
        return False, None
    
    # Validate using Verhoeff algorithm
    if not _verify_aadhaar_checksum(cleaned):
        return False, None
    
    return True, cleaned


def _verify_aadhaar_checksum(aadhaar: str) -> bool:
    """
    Verify Aadhaar checksum using Verhoeff algorithm.
    
    Args:
        aadhaar: 12-digit Aadhaar number
    
    Returns:
        True if checksum is valid
    """
    # Verhoeff algorithm multiplication table
    multiplication_table = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
        [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
        [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
        [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
        [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
        [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
        [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
        [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
        [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    ]
    
    # Permutation table
    permutation_table = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
        [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
        [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
        [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
        [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
        [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
        [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]
    ]
    
    # Inverse table
    inverse_table = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]
    
    checksum = 0
    for i, digit in enumerate(reversed(aadhaar)):
        checksum = multiplication_table[checksum][permutation_table[i % 8][int(digit)]]
    
    return checksum == 0


def validate_pan_number(pan: str) -> Tuple[bool, Optional[str]]:
    """
    Validate PAN (Permanent Account Number) format.
    
    Args:
        pan: PAN number to validate
    
    Returns:
        Tuple of (is_valid, normalized_pan)
    """
    if not pan:
        return False, None
    
    # Remove spaces and convert to uppercase
    cleaned = pan.replace(' ', '').upper()
    
    # Validate PAN format: 5 letters + 4 digits + 1 letter
    if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', cleaned):
        return False, None
    
    # Additional validation: 4th character should be 'P' for individual PAN
    # This is a common but not universal rule
    return True, cleaned


def validate_pincode(pincode: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Indian PIN code format.
    
    Args:
        pincode: PIN code to validate
    
    Returns:
        Tuple of (is_valid, normalized_pincode)
    """
    if not pincode:
        return False, None
    
    # Remove all non-digit characters
    cleaned = re.sub(r'\D', '', pincode)
    
    # Check length and format
    if not re.match(r'^[1-9][0-9]{5}$', cleaned):
        return False, None
    
    return True, cleaned


def validate_coordinates(latitude: float, longitude: float) -> bool:
    """
    Validate geographic coordinates.
    
    Args:
        latitude: Latitude value
        longitude: Longitude value
    
    Returns:
        True if coordinates are valid
    """
    if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
        return False
    
    # Check latitude range
    if latitude < -90 or latitude > 90:
        return False
    
    # Check longitude range
    if longitude < -180 or longitude > 180:
        return False
    
    # Check if coordinates are in India (approximate bounds)
    # India bounds: Lat 6.4-37.6, Lon 68.7-97.25
    if not (6.4 <= latitude <= 37.6 and 68.7 <= longitude <= 97.25):
        logger.warning(f"Coordinates ({latitude}, {longitude}) are outside India bounds")
    
    return True


def sanitize_text(text: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize text input by removing harmful characters and normalizing.
    
    Args:
        text: Text to sanitize
        max_length: Maximum allowed length
    
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Remove control characters except newlines and tabs
    sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    # Normalize whitespace
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
    # Truncate if necessary
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length].strip()
    
    return sanitized


def normalize_crop_name(crop_name: str) -> str:
    """
    Normalize crop name for consistent storage and matching.
    
    Args:
        crop_name: Crop name to normalize
    
    Returns:
        Normalized crop name
    """
    if not crop_name:
        return ""
    
    # Convert to lowercase and remove extra spaces
    normalized = crop_name.lower().strip()
    
    # Remove special characters except hyphens and spaces
    normalized = re.sub(r'[^\w\s\-]', '', normalized)
    
    # Normalize spaces
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Common crop name mappings
    crop_mappings = {
        'paddy': 'rice',
        'maize': 'corn',
        'groundnut': 'peanut',
        'gram': 'chickpea',
        'arhar': 'pigeon pea',
        'moong': 'mung bean',
        'urad': 'black gram',
        'masoor': 'lentil',
        'sarson': 'mustard',
        'til': 'sesame',
        'bajra': 'pearl millet',
        'jowar': 'sorghum',
        'ragi': 'finger millet'
    }
    
    return crop_mappings.get(normalized, normalized)


def validate_measurement(value: float, unit: str, measurement_type: str) -> bool:
    """
    Validate measurement values based on type and unit.
    
    Args:
        value: Measurement value
        unit: Unit of measurement
        measurement_type: Type of measurement (area, weight, volume, etc.)
    
    Returns:
        True if measurement is valid
    """
    if not isinstance(value, (int, float)) or value < 0:
        return False
    
    # Define valid units for different measurement types
    valid_units = {
        'area': ['acre', 'hectare', 'sq_meter', 'sq_feet', 'bigha', 'katha', 'guntha'],
        'weight': ['kg', 'gram', 'quintal', 'ton', 'pound'],
        'volume': ['liter', 'ml', 'gallon', 'cubic_meter'],
        'length': ['meter', 'cm', 'mm', 'feet', 'inch', 'km'],
        'temperature': ['celsius', 'fahrenheit', 'kelvin'],
        'pressure': ['hpa', 'bar', 'psi', 'atm'],
        'speed': ['kmph', 'mph', 'mps']
    }
    
    if measurement_type not in valid_units:
        return False
    
    if unit not in valid_units[measurement_type]:
        return False
    
    # Check reasonable ranges for different measurement types
    ranges = {
        'area': (0, 10000),  # 0 to 10,000 acres
        'weight': (0, 100000),  # 0 to 100,000 kg
        'volume': (0, 1000000),  # 0 to 1,000,000 liters
        'length': (0, 100000),  # 0 to 100,000 meters
        'temperature': (-50, 70),  # -50 to 70 Celsius
        'pressure': (800, 1200),  # 800 to 1200 hPa
        'speed': (0, 200)  # 0 to 200 kmph
    }
    
    if measurement_type in ranges:
        min_val, max_val = ranges[measurement_type]
        if not (min_val <= value <= max_val):
            logger.warning(f"Measurement value {value} {unit} is outside expected range for {measurement_type}")
    
    return True


def validate_monetary_amount(amount: float, currency: str = "INR") -> bool:
    """
    Validate monetary amount.
    
    Args:
        amount: Amount value
        currency: Currency code
    
    Returns:
        True if amount is valid
    """
    if not isinstance(amount, (int, float, Decimal)):
        return False
    
    if amount < 0:
        return False
    
    # Check for reasonable maximum (100 crores INR)
    if currency == "INR" and amount > 1000000000:
        logger.warning(f"Amount {amount} INR is very large")
    
    # Validate currency code
    valid_currencies = ['INR', 'USD', 'EUR', 'GBP']
    if currency not in valid_currencies:
        return False
    
    return True


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
    
    Returns:
        Tuple of (is_valid, normalized_email)
    """
    if not email:
        return False, None
    
    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    # Normalize email (lowercase)
    normalized = email.lower().strip()
    
    if not re.match(pattern, normalized):
        return False, None
    
    # Check length limits
    if len(normalized) > 254:  # RFC 5321 limit
        return False, None
    
    local_part, domain = normalized.split('@')
    if len(local_part) > 64:  # RFC 5321 limit
        return False, None
    
    return True, normalized


def validate_indian_bank_account(account_number: str, ifsc_code: str) -> Tuple[bool, Dict[str, str]]:
    """
    Validate Indian bank account number and IFSC code.
    
    Args:
        account_number: Bank account number
        ifsc_code: IFSC code
    
    Returns:
        Tuple of (is_valid, normalized_data)
    """
    result = {}
    
    # Validate account number
    if not account_number:
        return False, result
    
    # Remove spaces and special characters
    clean_account = re.sub(r'[^\d]', '', account_number)
    
    # Account number should be 9-18 digits
    if not re.match(r'^\d{9,18}$', clean_account):
        return False, result
    
    result['account_number'] = clean_account
    
    # Validate IFSC code
    if not ifsc_code:
        return False, result
    
    # IFSC format: 4 letters + 0 + 6 alphanumeric
    clean_ifsc = ifsc_code.upper().replace(' ', '')
    if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', clean_ifsc):
        return False, result
    
    result['ifsc_code'] = clean_ifsc
    
    return True, result


def validate_date_range(start_date: str, end_date: str) -> bool:
    """
    Validate that end date is after start date.
    
    Args:
        start_date: Start date in ISO format
        end_date: End date in ISO format
    
    Returns:
        True if date range is valid
    """
    try:
        from datetime import datetime
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        return end > start
    except (ValueError, AttributeError):
        return False


def validate_percentage(value: float) -> bool:
    """
    Validate percentage value (0-100).
    
    Args:
        value: Percentage value
    
    Returns:
        True if percentage is valid
    """
    return isinstance(value, (int, float)) and 0 <= value <= 100


def validate_ph_value(ph: float) -> bool:
    """
    Validate pH value (0-14).
    
    Args:
        ph: pH value
    
    Returns:
        True if pH is valid
    """
    return isinstance(ph, (int, float)) and 0 <= ph <= 14