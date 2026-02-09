"""
Language detection and dialect recognition for multilingual voice processing.

This module provides language identification and regional dialect detection
for Indian languages.
"""

import logging
from typing import Dict, List, Optional, Tuple
import re

logger = logging.getLogger(__name__)


class LanguageDetector:
    """
    Detects language and dialect from text or audio.
    
    Supports Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, and Punjabi
    with regional dialect recognition.
    """
    
    # Language codes and names
    LANGUAGES = {
        "hi": {"name": "Hindi", "native": "हिन्दी", "script": "Devanagari"},
        "ta": {"name": "Tamil", "native": "தமிழ்", "script": "Tamil"},
        "te": {"name": "Telugu", "native": "తెలుగు", "script": "Telugu"},
        "bn": {"name": "Bengali", "native": "বাংলা", "script": "Bengali"},
        "mr": {"name": "Marathi", "native": "मराठी", "script": "Devanagari"},
        "gu": {"name": "Gujarati", "native": "ગુજરાતી", "script": "Gujarati"},
        "pa": {"name": "Punjabi", "native": "ਪੰਜਾਬੀ", "script": "Gurmukhi"},
        "en": {"name": "English", "native": "English", "script": "Latin"},
    }
    
    # Unicode ranges for script detection
    SCRIPT_RANGES = {
        "Devanagari": (0x0900, 0x097F),
        "Bengali": (0x0980, 0x09FF),
        "Gurmukhi": (0x0A00, 0x0A7F),
        "Gujarati": (0x0A80, 0x0AFF),
        "Tamil": (0x0B80, 0x0BFF),
        "Telugu": (0x0C00, 0x0C7F),
        "Latin": (0x0041, 0x007A),
    }
    
    # Regional dialects and their linguistic markers
    DIALECT_MARKERS = {
        "hi": {
            "delhi": ["यार", "भाई", "अच्छा"],
            "mumbai": ["बोले", "मस्त", "झकास"],
            "lucknow": ["जनाब", "आदाब"],
            "jaipur": ["घणो", "थारो"],
        },
        "ta": {
            "chennai": ["டா", "மச்சி"],
            "madurai": ["டேய்", "போடா"],
            "coimbatore": ["டா", "மாப்ள"],
        },
        "te": {
            "hyderabad": ["రా", "బాబు"],
            "vijayawada": ["అన్న", "చెల్లి"],
        },
        "bn": {
            "kolkata": ["দাদা", "দিদি"],
        },
        "mr": {
            "mumbai": ["रे", "भावा"],
            "pune": ["ग", "काय"],
            "nagpur": ["बाबा", "ताई"],
        },
        "gu": {
            "ahmedabad": ["ભાઈ", "બેન"],
            "surat": ["સાહેબ"],
        },
        "pa": {
            "amritsar": ["ਵੀਰ", "ਭਾਈ"],
            "ludhiana": ["ਯਾਰ"],
        },
    }
    
    def __init__(self):
        """Initialize the language detector."""
        pass
    
    def detect_language_from_text(
        self,
        text: str,
        candidate_languages: Optional[List[str]] = None
    ) -> Tuple[str, float]:
        """
        Detect language from text using script analysis.
        
        Args:
            text: Text to analyze
            candidate_languages: List of candidate language codes
            
        Returns:
            Tuple of (language_code, confidence)
        """
        if not text or not text.strip():
            return "unknown", 0.0
        
        if candidate_languages is None:
            candidate_languages = list(self.LANGUAGES.keys())
        
        # Detect script
        script_scores = self._analyze_scripts(text)
        
        if not script_scores:
            return "unknown", 0.0
        
        # Map script to language
        dominant_script = max(script_scores, key=script_scores.get)
        confidence = script_scores[dominant_script]
        
        # Find language with matching script
        for lang_code in candidate_languages:
            lang_info = self.LANGUAGES.get(lang_code, {})
            if lang_info.get("script") == dominant_script:
                logger.info(
                    f"Detected language: {lang_code} ({dominant_script}) "
                    f"with confidence: {confidence:.2f}"
                )
                return lang_code, confidence
        
        # If no exact match, return based on script
        script_to_lang = {
            "Devanagari": "hi",  # Default to Hindi for Devanagari
            "Bengali": "bn",
            "Gurmukhi": "pa",
            "Gujarati": "gu",
            "Tamil": "ta",
            "Telugu": "te",
            "Latin": "en",
        }
        
        detected_lang = script_to_lang.get(dominant_script, "unknown")
        return detected_lang, confidence
    
    def detect_dialect(
        self,
        text: str,
        language_code: str
    ) -> Optional[str]:
        """
        Detect regional dialect from text.
        
        Args:
            text: Text to analyze
            language_code: Language code
            
        Returns:
            Detected dialect/region or None
        """
        if language_code not in self.DIALECT_MARKERS:
            return None
        
        dialect_markers = self.DIALECT_MARKERS[language_code]
        dialect_scores = {}
        
        # Count dialect markers
        text_lower = text.lower()
        for dialect, markers in dialect_markers.items():
            score = sum(1 for marker in markers if marker in text)
            if score > 0:
                dialect_scores[dialect] = score
        
        if not dialect_scores:
            return None
        
        # Return dialect with highest score
        detected_dialect = max(dialect_scores, key=dialect_scores.get)
        logger.info(f"Detected dialect: {detected_dialect} for language: {language_code}")
        
        return detected_dialect
    
    def _analyze_scripts(self, text: str) -> Dict[str, float]:
        """
        Analyze text to determine script composition.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary mapping script names to confidence scores
        """
        script_counts = {script: 0 for script in self.SCRIPT_RANGES.keys()}
        total_chars = 0
        
        for char in text:
            code_point = ord(char)
            
            # Skip whitespace and punctuation
            if char.isspace() or not char.isalnum():
                continue
            
            total_chars += 1
            
            # Check which script this character belongs to
            for script, (start, end) in self.SCRIPT_RANGES.items():
                if start <= code_point <= end:
                    script_counts[script] += 1
                    break
        
        if total_chars == 0:
            return {}
        
        # Calculate confidence scores
        script_scores = {
            script: count / total_chars
            for script, count in script_counts.items()
            if count > 0
        }
        
        return script_scores
    
    def get_language_info(self, language_code: str) -> Optional[Dict]:
        """
        Get information about a language.
        
        Args:
            language_code: Language code
            
        Returns:
            Dictionary with language information or None
        """
        return self.LANGUAGES.get(language_code)
    
    def is_supported_language(self, language_code: str) -> bool:
        """
        Check if a language is supported.
        
        Args:
            language_code: Language code to check
            
        Returns:
            True if supported, False otherwise
        """
        return language_code in self.LANGUAGES
    
    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported language codes.
        
        Returns:
            List of language codes
        """
        return list(self.LANGUAGES.keys())
    
    def normalize_language_code(self, language_code: str) -> str:
        """
        Normalize language code to standard format.
        
        Args:
            language_code: Language code (e.g., 'hi', 'hi-IN', 'hin')
            
        Returns:
            Normalized language code
        """
        # Extract base language code
        base_code = language_code.split("-")[0].lower()
        
        # Map common variations
        code_mappings = {
            "hin": "hi",
            "tam": "ta",
            "tel": "te",
            "ben": "bn",
            "mar": "mr",
            "guj": "gu",
            "pan": "pa",
            "eng": "en",
        }
        
        normalized = code_mappings.get(base_code, base_code)
        
        # Validate
        if normalized not in self.LANGUAGES:
            logger.warning(f"Unknown language code: {language_code}")
            return "hi"  # Default to Hindi
        
        return normalized
    
    def format_language_code_for_aws(self, language_code: str) -> str:
        """
        Format language code for AWS services (Transcribe, Polly, Translate).
        
        Args:
            language_code: Base language code
            
        Returns:
            AWS-formatted language code (e.g., 'hi-IN')
        """
        normalized = self.normalize_language_code(language_code)
        
        # AWS uses region-specific codes
        aws_codes = {
            "hi": "hi-IN",
            "ta": "ta-IN",
            "te": "te-IN",
            "bn": "bn-IN",
            "mr": "mr-IN",
            "gu": "gu-IN",
            "pa": "pa-IN",
            "en": "en-IN",
        }
        
        return aws_codes.get(normalized, "hi-IN")
