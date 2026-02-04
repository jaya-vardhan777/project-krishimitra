"""
Base models for KrishiMitra platform.

This module contains base Pydantic models that provide common functionality
for all other models in the application.
"""

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel as PydanticBaseModel, Field, ConfigDict
from pydantic.alias_generators import to_camel


T = TypeVar('T')


class BaseModel(PydanticBaseModel):
    """Base model with common configuration for all KrishiMitra models."""
    
    model_config = ConfigDict(
        # Use camelCase for JSON serialization
        alias_generator=to_camel,
        # Allow population by field name and alias
        populate_by_name=True,
        # Validate assignment
        validate_assignment=True,
        # Use enum values
        use_enum_values=True,
        # Extra fields are forbidden
        extra='forbid',
        # Serialize by alias
        ser_by_alias=True
    )


class TimestampedModel(BaseModel):
    """Base model with timestamp fields."""
    
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response model."""
    
    items: List[T] = Field(description="List of items")
    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page number")
    size: int = Field(description="Page size")
    pages: int = Field(description="Total number of pages")
    has_next: bool = Field(description="Whether there is a next page")
    has_prev: bool = Field(description="Whether there is a previous page")
    
    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        page: int,
        size: int
    ) -> 'PaginatedResponse[T]':
        """Create a paginated response."""
        pages = (total + size - 1) // size  # Ceiling division
        
        return cls(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1
        )


class ErrorResponse(BaseModel):
    """Standard error response model."""
    
    error: str = Field(description="Error type")
    message: str = Field(description="Error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    request_id: Optional[str] = Field(default=None, description="Request ID for tracking")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class HealthStatus(BaseModel):
    """Health check status model."""
    
    status: str = Field(description="Overall health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    version: str = Field(description="Application version")
    environment: str = Field(description="Environment name")
    services: Optional[Dict[str, str]] = Field(default=None, description="Service health status")
    uptime: Optional[float] = Field(default=None, description="Uptime in seconds")


class GeographicCoordinate(BaseModel):
    """Geographic coordinate model."""
    
    latitude: float = Field(ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: float = Field(ge=-180, le=180, description="Longitude in decimal degrees")
    altitude: Optional[float] = Field(default=None, description="Altitude in meters")
    accuracy: Optional[float] = Field(default=None, description="Accuracy in meters")


class Address(BaseModel):
    """Address model for Indian locations."""
    
    village: str = Field(description="Village name")
    block: Optional[str] = Field(default=None, description="Block/Tehsil name")
    district: str = Field(description="District name")
    state: str = Field(description="State name")
    pincode: Optional[str] = Field(default=None, pattern=r"^\d{6}$", description="6-digit PIN code")
    country: str = Field(default="India", description="Country name")
    coordinates: Optional[GeographicCoordinate] = Field(default=None, description="Geographic coordinates")


class LanguageCode(BaseModel):
    """Language code model for multilingual support."""
    
    code: str = Field(pattern=r"^[a-z]{2}(-[A-Z]{2})?$", description="Language code (ISO 639-1 with optional country)")
    name: str = Field(description="Language name")
    native_name: str = Field(description="Native language name")
    
    @classmethod
    def hindi(cls) -> 'LanguageCode':
        return cls(code="hi-IN", name="Hindi", native_name="हिन्दी")
    
    @classmethod
    def tamil(cls) -> 'LanguageCode':
        return cls(code="ta-IN", name="Tamil", native_name="தமிழ்")
    
    @classmethod
    def telugu(cls) -> 'LanguageCode':
        return cls(code="te-IN", name="Telugu", native_name="తెలుగు")
    
    @classmethod
    def bengali(cls) -> 'LanguageCode':
        return cls(code="bn-IN", name="Bengali", native_name="বাংলা")
    
    @classmethod
    def marathi(cls) -> 'LanguageCode':
        return cls(code="mr-IN", name="Marathi", native_name="मराठी")
    
    @classmethod
    def gujarati(cls) -> 'LanguageCode':
        return cls(code="gu-IN", name="Gujarati", native_name="ગુજરાતી")
    
    @classmethod
    def punjabi(cls) -> 'LanguageCode':
        return cls(code="pa-IN", name="Punjabi", native_name="ਪੰਜਾਬੀ")


class Currency(BaseModel):
    """Currency model for financial data."""
    
    code: str = Field(default="INR", pattern=r"^[A-Z]{3}$", description="3-letter currency code")
    symbol: str = Field(default="₹", description="Currency symbol")
    name: str = Field(default="Indian Rupee", description="Currency name")


class MonetaryAmount(BaseModel):
    """Monetary amount with currency."""
    
    amount: float = Field(ge=0, description="Amount value")
    currency: Currency = Field(default_factory=Currency, description="Currency information")
    
    def __str__(self) -> str:
        return f"{self.currency.symbol}{self.amount:,.2f}"


class Measurement(BaseModel):
    """Generic measurement with unit."""
    
    value: float = Field(description="Measurement value")
    unit: str = Field(description="Unit of measurement")
    precision: Optional[int] = Field(default=None, description="Decimal precision")
    
    def __str__(self) -> str:
        if self.precision is not None:
            return f"{self.value:.{self.precision}f} {self.unit}"
        return f"{self.value} {self.unit}"