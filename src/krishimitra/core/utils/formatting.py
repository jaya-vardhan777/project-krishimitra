"""
Formatting utilities for KrishiMitra platform.

This module provides utilities for formatting various data types
for display in different contexts and languages.
"""

import re
from datetime import datetime, date
from typing import Optional, Dict, Any
from decimal import Decimal


def format_currency(
    amount: float, 
    currency: str = "INR", 
    locale: str = "hi-IN",
    include_symbol: bool = True
) -> str:
    """
    Format currency amount for display.
    
    Args:
        amount: Amount to format
        currency: Currency code
        locale: Locale for formatting
        include_symbol: Whether to include currency symbol
    
    Returns:
        Formatted currency string
    """
    # Currency symbols
    symbols = {
        "INR": "₹",
        "USD": "$",
        "EUR": "€",
        "GBP": "£"
    }
    
    symbol = symbols.get(currency, currency)
    
    # Format based on locale
    if locale.startswith("hi") or locale.startswith("en-IN"):
        # Indian number formatting (lakhs and crores)
        if amount >= 10000000:  # 1 crore
            crores = amount / 10000000
            formatted = f"{crores:.2f} करोड़" if locale.startswith("hi") else f"{crores:.2f} Cr"
        elif amount >= 100000:  # 1 lakh
            lakhs = amount / 100000
            formatted = f"{lakhs:.2f} लाख" if locale.startswith("hi") else f"{lakhs:.2f} L"
        elif amount >= 1000:  # 1 thousand
            thousands = amount / 1000
            formatted = f"{thousands:.2f} हज़ार" if locale.startswith("hi") else f"{thousands:.2f} K"
        else:
            formatted = f"{amount:.2f}"
    else:
        # Standard formatting
        if amount >= 1000000:
            millions = amount / 1000000
            formatted = f"{millions:.2f}M"
        elif amount >= 1000:
            thousands = amount / 1000
            formatted = f"{thousands:.2f}K"
        else:
            formatted = f"{amount:.2f}"
    
    if include_symbol:
        return f"{symbol}{formatted}"
    else:
        return formatted


def format_measurement(
    value: float, 
    unit: str, 
    locale: str = "hi-IN",
    precision: int = 2
) -> str:
    """
    Format measurement values for display.
    
    Args:
        value: Measurement value
        unit: Unit of measurement
        locale: Locale for formatting
        precision: Decimal precision
    
    Returns:
        Formatted measurement string
    """
    # Unit translations for Hindi
    unit_translations = {
        "acre": "एकड़",
        "hectare": "हेक्टेयर", 
        "kg": "किलो",
        "gram": "ग्राम",
        "quintal": "क्विंटल",
        "liter": "लीटर",
        "meter": "मीटर",
        "cm": "सेमी",
        "feet": "फीट",
        "celsius": "°C",
        "fahrenheit": "°F"
    }
    
    # Format value
    if value >= 1000 and unit in ["kg", "gram", "liter"]:
        if unit == "kg" and value >= 1000:
            tons = value / 1000
            formatted_value = f"{tons:.{precision}f}"
            unit = "टन" if locale.startswith("hi") else "ton"
        elif unit == "gram" and value >= 1000:
            kg = value / 1000
            formatted_value = f"{kg:.{precision}f}"
            unit = "किलो" if locale.startswith("hi") else "kg"
        else:
            formatted_value = f"{value:.{precision}f}"
    else:
        formatted_value = f"{value:.{precision}f}"
    
    # Translate unit if Hindi locale
    if locale.startswith("hi"):
        display_unit = unit_translations.get(unit, unit)
    else:
        display_unit = unit
    
    return f"{formatted_value} {display_unit}"


def format_date_indian(
    date_obj: datetime, 
    locale: str = "hi-IN",
    format_type: str = "medium"
) -> str:
    """
    Format date for Indian locales.
    
    Args:
        date_obj: Date object to format
        locale: Locale for formatting
        format_type: Format type (short, medium, long, full)
    
    Returns:
        Formatted date string
    """
    if locale.startswith("hi"):
        # Hindi month names
        hindi_months = [
            "जनवरी", "फरवरी", "मार्च", "अप्रैल", "मई", "जून",
            "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"
        ]
        
        # Hindi day names
        hindi_days = [
            "सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"
        ]
        
        if format_type == "short":
            return f"{date_obj.day:02d}/{date_obj.month:02d}/{date_obj.year}"
        elif format_type == "medium":
            return f"{date_obj.day} {hindi_months[date_obj.month-1]} {date_obj.year}"
        elif format_type == "long":
            day_name = hindi_days[date_obj.weekday()]
            return f"{day_name}, {date_obj.day} {hindi_months[date_obj.month-1]} {date_obj.year}"
        else:  # full
            day_name = hindi_days[date_obj.weekday()]
            return f"{day_name}, {date_obj.day} {hindi_months[date_obj.month-1]} {date_obj.year}"
    
    else:
        # English formatting
        if format_type == "short":
            return date_obj.strftime("%d/%m/%Y")
        elif format_type == "medium":
            return date_obj.strftime("%d %b %Y")
        elif format_type == "long":
            return date_obj.strftime("%A, %d %B %Y")
        else:  # full
            return date_obj.strftime("%A, %d %B %Y")


def format_phone_number(phone: str, format_type: str = "display") -> str:
    """
    Format phone number for display.
    
    Args:
        phone: Phone number to format
        format_type: Format type (display, international, national)
    
    Returns:
        Formatted phone number
    """
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    if cleaned.startswith('+91'):
        country_code = '+91'
        number = cleaned[3:]
    elif cleaned.startswith('91') and len(cleaned) == 12:
        country_code = '+91'
        number = cleaned[2:]
    else:
        country_code = '+91'
        number = cleaned[-10:] if len(cleaned) >= 10 else cleaned
    
    if len(number) == 10:
        if format_type == "display":
            return f"{country_code} {number[:5]} {number[5:]}"
        elif format_type == "international":
            return f"{country_code} {number}"
        elif format_type == "national":
            return f"0{number}"
        else:
            return f"{country_code}{number}"
    else:
        return phone


def format_address(address_dict: Dict[str, Any], locale: str = "hi-IN") -> str:
    """
    Format address for display.
    
    Args:
        address_dict: Dictionary containing address components
        locale: Locale for formatting
    
    Returns:
        Formatted address string
    """
    components = []
    
    # Order of components for Indian addresses
    if address_dict.get('village'):
        components.append(address_dict['village'])
    
    if address_dict.get('block'):
        components.append(address_dict['block'])
    
    if address_dict.get('district'):
        components.append(address_dict['district'])
    
    if address_dict.get('state'):
        components.append(address_dict['state'])
    
    if address_dict.get('pincode'):
        components.append(address_dict['pincode'])
    
    if address_dict.get('country'):
        components.append(address_dict['country'])
    
    return ", ".join(components)


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to specified length with suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncated
    
    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    
    # Try to truncate at word boundary
    if max_length > len(suffix):
        truncate_at = max_length - len(suffix)
        
        # Find last space before truncation point
        last_space = text.rfind(' ', 0, truncate_at)
        
        if last_space > max_length // 2:  # Only use word boundary if it's not too early
            return text[:last_space] + suffix
        else:
            return text[:truncate_at] + suffix
    else:
        return text[:max_length]


def format_percentage(value: float, precision: int = 1) -> str:
    """
    Format percentage value.
    
    Args:
        value: Percentage value (0-100)
        precision: Decimal precision
    
    Returns:
        Formatted percentage string
    """
    return f"{value:.{precision}f}%"


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human readable format.
    
    Args:
        size_bytes: Size in bytes
    
    Returns:
        Formatted file size string
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"


def format_duration(seconds: int) -> str:
    """
    Format duration in human readable format.
    
    Args:
        seconds: Duration in seconds
    
    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        if remaining_seconds == 0:
            return f"{minutes}m"
        else:
            return f"{minutes}m {remaining_seconds}s"
    else:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        if remaining_minutes == 0:
            return f"{hours}h"
        else:
            return f"{hours}h {remaining_minutes}m"


def format_crop_name(crop_name: str, locale: str = "hi-IN") -> str:
    """
    Format crop name for display in specified locale.
    
    Args:
        crop_name: Crop name to format
        locale: Locale for formatting
    
    Returns:
        Formatted crop name
    """
    # Crop name translations
    crop_translations = {
        "rice": "चावल",
        "wheat": "गेहूं", 
        "corn": "मक्का",
        "sugarcane": "गन्ना",
        "cotton": "कपास",
        "soybean": "सोयाबीन",
        "chickpea": "चना",
        "pigeon_pea": "अरहर",
        "lentil": "मसूर",
        "mustard": "सरसों",
        "groundnut": "मूंगफली",
        "sesame": "तिल",
        "sunflower": "सूरजमुखी",
        "potato": "आलू",
        "onion": "प्याज",
        "tomato": "टमाटर",
        "chili": "मिर्च",
        "turmeric": "हल्दी",
        "ginger": "अदरक",
        "garlic": "लहसुन"
    }
    
    if locale.startswith("hi"):
        return crop_translations.get(crop_name.lower(), crop_name.title())
    else:
        return crop_name.title()


def format_weather_condition(condition: str, locale: str = "hi-IN") -> str:
    """
    Format weather condition for display.
    
    Args:
        condition: Weather condition
        locale: Locale for formatting
    
    Returns:
        Formatted weather condition
    """
    condition_translations = {
        "clear": "साफ",
        "partly_cloudy": "आंशिक बादल",
        "cloudy": "बादल",
        "overcast": "घने बादल",
        "light_rain": "हल्की बारिश",
        "moderate_rain": "मध्यम बारिश", 
        "heavy_rain": "भारी बारिश",
        "thunderstorm": "तूफान",
        "fog": "कोहरा",
        "haze": "धुंध",
        "dust_storm": "धूल भरी आंधी"
    }
    
    if locale.startswith("hi"):
        return condition_translations.get(condition.lower(), condition.title())
    else:
        return condition.replace("_", " ").title()


def format_number_indian(number: float, precision: int = 2) -> str:
    """
    Format number in Indian numbering system.
    
    Args:
        number: Number to format
        precision: Decimal precision
    
    Returns:
        Formatted number string
    """
    if number >= 10000000:  # 1 crore
        return f"{number/10000000:.{precision}f} करोड़"
    elif number >= 100000:  # 1 lakh
        return f"{number/100000:.{precision}f} लाख"
    elif number >= 1000:  # 1 thousand
        return f"{number/1000:.{precision}f} हज़ार"
    else:
        return f"{number:.{precision}f}"