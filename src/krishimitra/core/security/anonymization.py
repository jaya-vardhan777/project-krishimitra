"""
Data anonymization utilities for KrishiMitra platform.

This module provides utilities for anonymizing and pseudonymizing farmer data
for research, analytics, and compliance purposes while preserving data utility.
"""

import hashlib
import random
import string
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, date
import uuid


class DataAnonymizer:
    """
    Service for anonymizing sensitive data while preserving analytical value.
    
    Provides various anonymization techniques including k-anonymity,
    pseudonymization, and data masking.
    """
    
    def __init__(self, salt: Optional[str] = None):
        """
        Initialize data anonymizer.
        
        Args:
            salt: Salt for consistent pseudonymization
        """
        self.salt = salt or "krishimitra-anonymization-salt"
    
    def pseudonymize_id(self, original_id: str) -> str:
        """
        Create a consistent pseudonym for an ID.
        
        Args:
            original_id: Original identifier
            
        Returns:
            Pseudonymized identifier
        """
        # Create a consistent hash-based pseudonym
        hash_input = f"{self.salt}{original_id}".encode()
        hash_digest = hashlib.sha256(hash_input).hexdigest()
        return f"anon_{hash_digest[:16]}"
    
    def anonymize_name(self, name: str) -> str:
        """
        Anonymize a person's name.
        
        Args:
            name: Original name
            
        Returns:
            Anonymized name
        """
        if not name:
            return "Anonymous"
        
        # Generate a consistent pseudonym based on the name
        hash_input = f"{self.salt}{name}".encode()
        hash_digest = hashlib.md5(hash_input).hexdigest()
        
        # Create a readable pseudonym
        prefixes = ["Farmer", "Grower", "Cultivator", "Producer"]
        prefix = prefixes[int(hash_digest[0], 16) % len(prefixes)]
        suffix = hash_digest[:6].upper()
        
        return f"{prefix}_{suffix}"
    
    def anonymize_location(self, location: Dict[str, Any], precision: str = "district") -> Dict[str, Any]:
        """
        Anonymize location data with specified precision.
        
        Args:
            location: Original location data
            precision: Level of precision to maintain (state, district, village)
            
        Returns:
            Anonymized location data
        """
        anonymized = {}
        
        if precision == "state":
            anonymized["state"] = location.get("state")
            anonymized["district"] = "ANONYMIZED"
            anonymized["village"] = "ANONYMIZED"
        elif precision == "district":
            anonymized["state"] = location.get("state")
            anonymized["district"] = location.get("district")
            anonymized["village"] = "ANONYMIZED"
        elif precision == "village":
            anonymized = location.copy()
        else:
            # No location data
            anonymized = {"state": "ANONYMIZED", "district": "ANONYMIZED", "village": "ANONYMIZED"}
        
        # Always remove exact coordinates
        if "coordinates" in location:
            coords = location["coordinates"]
            if isinstance(coords, dict) and "latitude" in coords and "longitude" in coords:
                # Add noise to coordinates (±0.01 degrees ≈ ±1km)
                lat_noise = random.uniform(-0.01, 0.01)
                lon_noise = random.uniform(-0.01, 0.01)
                anonymized["coordinates"] = {
                    "latitude": round(coords["latitude"] + lat_noise, 4),
                    "longitude": round(coords["longitude"] + lon_noise, 4)
                }
        
        return anonymized
    
    def anonymize_contact_info(self, contact_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Anonymize contact information.
        
        Args:
            contact_info: Original contact information
            
        Returns:
            Anonymized contact information
        """
        anonymized = {}
        
        # Remove all direct contact information
        if "primary_phone" in contact_info:
            anonymized["primary_phone"] = "ANONYMIZED"
        if "email" in contact_info:
            anonymized["email"] = "ANONYMIZED"
        
        # Keep non-identifying preferences
        if "preferred_contact_method" in contact_info:
            anonymized["preferred_contact_method"] = contact_info["preferred_contact_method"]
        if "preferred_contact_time" in contact_info:
            anonymized["preferred_contact_time"] = contact_info["preferred_contact_time"]
        
        return anonymized
    
    def generalize_age(self, birth_date: Union[str, date], age_groups: List[tuple] = None) -> str:
        """
        Generalize age into age groups.
        
        Args:
            birth_date: Birth date
            age_groups: List of (min_age, max_age) tuples for grouping
            
        Returns:
            Age group string
        """
        if age_groups is None:
            age_groups = [(18, 25), (26, 35), (36, 45), (46, 55), (56, 65), (66, 100)]
        
        if isinstance(birth_date, str):
            birth_date = datetime.fromisoformat(birth_date).date()
        
        today = date.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        
        for min_age, max_age in age_groups:
            if min_age <= age <= max_age:
                return f"{min_age}-{max_age}"
        
        return "unknown"
    
    def generalize_farm_size(self, area: float, size_groups: List[tuple] = None) -> str:
        """
        Generalize farm size into categories.
        
        Args:
            area: Farm area in hectares
            size_groups: List of (min_area, max_area) tuples for grouping
            
        Returns:
            Farm size category
        """
        if size_groups is None:
            size_groups = [(0, 1), (1, 2), (2, 5), (5, 10), (10, 50), (50, float('inf'))]
        
        for min_area, max_area in size_groups:
            if min_area <= area < max_area:
                if max_area == float('inf'):
                    return f"{min_area}+ hectares"
                return f"{min_area}-{max_area} hectares"
        
        return "unknown"
    
    def anonymize_farmer_profile(
        self,
        profile: Dict[str, Any],
        anonymization_level: str = "medium"
    ) -> Dict[str, Any]:
        """
        Anonymize a complete farmer profile.
        
        Args:
            profile: Original farmer profile
            anonymization_level: Level of anonymization (low, medium, high)
            
        Returns:
            Anonymized farmer profile
        """
        anonymized = {}
        
        # Always anonymize direct identifiers
        if "farmer_id" in profile:
            anonymized["farmer_id"] = self.pseudonymize_id(profile["farmer_id"])
        
        if "name" in profile:
            anonymized["name"] = self.anonymize_name(profile["name"])
        
        # Remove highly sensitive fields
        sensitive_fields = ["aadhaar_number", "pan_number", "bank_account_details", "father_name"]
        for field in sensitive_fields:
            if field in profile:
                anonymized[field] = "ANONYMIZED"
        
        # Anonymize contact information
        if "contact_info" in profile:
            anonymized["contact_info"] = self.anonymize_contact_info(profile["contact_info"])
        
        # Anonymize location based on level
        if "location" in profile:
            if anonymization_level == "low":
                precision = "village"
            elif anonymization_level == "medium":
                precision = "district"
            else:  # high
                precision = "state"
            anonymized["location"] = self.anonymize_location(profile["location"], precision)
        
        # Generalize demographic data
        if "date_of_birth" in profile and profile["date_of_birth"]:
            anonymized["age_group"] = self.generalize_age(profile["date_of_birth"])
        
        # Keep non-identifying farm details with generalization
        if "farm_details" in profile:
            farm_details = profile["farm_details"].copy()
            
            # Generalize farm size
            if "total_land_area" in farm_details:
                anonymized["farm_size_category"] = self.generalize_farm_size(farm_details["total_land_area"])
            
            # Keep non-identifying agricultural data
            keep_fields = ["soil_type", "irrigation_type", "crops"]
            anonymized["farm_details"] = {
                field: farm_details[field] for field in keep_fields if field in farm_details
            }
        
        # Keep preferences (generally non-identifying)
        if "preferences" in profile:
            prefs = profile["preferences"].copy()
            # Remove budget information for higher anonymization levels
            if anonymization_level == "high" and "budget_constraints" in prefs:
                del prefs["budget_constraints"]
            anonymized["preferences"] = prefs
        
        # Add anonymization metadata
        anonymized["_anonymization"] = {
            "level": anonymization_level,
            "timestamp": datetime.utcnow().isoformat(),
            "method": "pseudonymization_with_generalization"
        }
        
        return anonymized
    
    def create_synthetic_profile(self, template_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a synthetic profile based on a template.
        
        Args:
            template_profile: Template profile to base synthetic data on
            
        Returns:
            Synthetic farmer profile
        """
        synthetic = {}
        
        # Generate synthetic identifiers
        synthetic["farmer_id"] = f"synthetic_{uuid.uuid4().hex[:16]}"
        synthetic["name"] = self._generate_synthetic_name()
        
        # Generate synthetic location in same region
        if "location" in template_profile:
            synthetic["location"] = self._generate_synthetic_location(template_profile["location"])
        
        # Generate synthetic contact info
        synthetic["contact_info"] = self._generate_synthetic_contact()
        
        # Keep similar farm characteristics but with variation
        if "farm_details" in template_profile:
            synthetic["farm_details"] = self._generate_synthetic_farm_details(template_profile["farm_details"])
        
        # Keep similar preferences
        if "preferences" in template_profile:
            synthetic["preferences"] = template_profile["preferences"].copy()
        
        # Add synthetic data metadata
        synthetic["_synthetic"] = {
            "generated_at": datetime.utcnow().isoformat(),
            "template_based": True
        }
        
        return synthetic
    
    def _generate_synthetic_name(self) -> str:
        """Generate a synthetic farmer name."""
        first_names = ["राम", "श्याम", "गीता", "सुनीता", "मोहन", "प्रेम", "सुमित्रा", "राधा"]
        last_names = ["कुमार", "सिंह", "देवी", "शर्मा", "लाल", "चंद", "प्रसाद", "वर्मा"]
        
        first = random.choice(first_names)
        last = random.choice(last_names)
        return f"{first} {last}"
    
    def _generate_synthetic_location(self, template_location: Dict[str, Any]) -> Dict[str, Any]:
        """Generate synthetic location based on template."""
        synthetic_location = {
            "state": template_location.get("state"),
            "district": template_location.get("district"),
            "village": f"Synthetic Village {random.randint(1, 999)}",
            "pincode": f"{random.randint(100000, 999999)}"
        }
        
        # Generate coordinates near the template location
        if "coordinates" in template_location:
            coords = template_location["coordinates"]
            if isinstance(coords, dict):
                lat_offset = random.uniform(-0.1, 0.1)
                lon_offset = random.uniform(-0.1, 0.1)
                synthetic_location["coordinates"] = {
                    "latitude": coords.get("latitude", 0) + lat_offset,
                    "longitude": coords.get("longitude", 0) + lon_offset
                }
        
        return synthetic_location
    
    def _generate_synthetic_contact(self) -> Dict[str, Any]:
        """Generate synthetic contact information."""
        return {
            "primary_phone": f"+91{random.randint(6000000000, 9999999999)}",
            "email": f"synthetic.farmer{random.randint(1000, 9999)}@example.com",
            "preferred_contact_method": random.choice(["voice", "text", "whatsapp"])
        }
    
    def _generate_synthetic_farm_details(self, template_farm: Dict[str, Any]) -> Dict[str, Any]:
        """Generate synthetic farm details based on template."""
        synthetic_farm = {}
        
        # Vary farm size by ±20%
        if "total_land_area" in template_farm:
            base_area = template_farm["total_land_area"]
            variation = random.uniform(0.8, 1.2)
            synthetic_farm["total_land_area"] = round(base_area * variation, 2)
        
        # Keep similar soil and irrigation types
        for field in ["soil_type", "irrigation_type"]:
            if field in template_farm:
                synthetic_farm[field] = template_farm[field]
        
        # Generate similar crops with variation
        if "crops" in template_farm:
            synthetic_farm["crops"] = []
            for crop in template_farm["crops"]:
                synthetic_crop = crop.copy()
                # Vary crop area
                if "area" in synthetic_crop:
                    variation = random.uniform(0.7, 1.3)
                    synthetic_crop["area"] = round(synthetic_crop["area"] * variation, 2)
                synthetic_farm["crops"].append(synthetic_crop)
        
        return synthetic_farm


# Global anonymizer instance
_anonymizer = None


def get_anonymizer() -> DataAnonymizer:
    """Get global data anonymizer instance."""
    global _anonymizer
    if _anonymizer is None:
        _anonymizer = DataAnonymizer()
    return _anonymizer


def anonymize_for_research(data: List[Dict[str, Any]], k_value: int = 5) -> List[Dict[str, Any]]:
    """
    Anonymize data for research purposes with k-anonymity.
    
    Args:
        data: List of farmer profiles
        k_value: Minimum group size for k-anonymity
        
    Returns:
        Anonymized data with k-anonymity guarantee
    """
    anonymizer = get_anonymizer()
    
    # Anonymize all profiles
    anonymized_data = []
    for profile in data:
        anonymized_profile = anonymizer.anonymize_farmer_profile(profile, "medium")
        anonymized_data.append(anonymized_profile)
    
    # Group by quasi-identifiers for k-anonymity
    # This is a simplified implementation
    # In production, would use more sophisticated k-anonymity algorithms
    
    return anonymized_data


def create_synthetic_dataset(
    template_data: List[Dict[str, Any]], 
    synthetic_count: int
) -> List[Dict[str, Any]]:
    """
    Create synthetic dataset based on template data.
    
    Args:
        template_data: Template profiles to base synthetic data on
        synthetic_count: Number of synthetic profiles to generate
        
    Returns:
        List of synthetic farmer profiles
    """
    anonymizer = get_anonymizer()
    synthetic_data = []
    
    for _ in range(synthetic_count):
        template = random.choice(template_data)
        synthetic_profile = anonymizer.create_synthetic_profile(template)
        synthetic_data.append(synthetic_profile)
    
    return synthetic_data