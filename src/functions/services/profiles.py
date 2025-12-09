"""Processing profiles for different form types.

Profiles define processing configurations for various document types,
including model selection, page settings, and validation rules.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FieldValidation:
    """Validation rule for an extracted field."""

    field_name: str
    validation_type: str  # "required", "format", "range", "lookup"
    params: dict[str, Any] = field(default_factory=dict)

    def validate(self, value: Any) -> tuple[bool, str | None]:
        """Validate a field value.

        Args:
            value: The value to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        if self.validation_type == "required":
            if value is None or value == "":
                return False, f"Field '{self.field_name}' is required"
            return True, None

        elif self.validation_type == "format":
            import re

            pattern = self.params.get("pattern", ".*")
            if value is not None and not re.match(pattern, str(value)):
                return False, f"Field '{self.field_name}' does not match format: {pattern}"
            return True, None

        elif self.validation_type == "range":
            min_val = self.params.get("min")
            max_val = self.params.get("max")
            if value is not None:
                try:
                    num_val = float(value) if not isinstance(value, (int, float)) else value
                    if min_val is not None and num_val < min_val:
                        return False, f"Field '{self.field_name}' below minimum: {min_val}"
                    if max_val is not None and num_val > max_val:
                        return False, f"Field '{self.field_name}' above maximum: {max_val}"
                except (ValueError, TypeError):
                    return False, f"Field '{self.field_name}' is not a valid number"
            return True, None

        elif self.validation_type == "lookup":
            allowed_values = self.params.get("values", [])
            if value is not None and str(value) not in [str(v) for v in allowed_values]:
                return False, f"Field '{self.field_name}' not in allowed values: {allowed_values}"
            return True, None

        return True, None


@dataclass
class ProcessingProfile:
    """Configuration profile for document processing."""

    name: str
    model_id: str
    pages_per_form: int = 2
    confidence_threshold: float = 0.8
    required_fields: list[str] = field(default_factory=list)
    validations: list[FieldValidation] = field(default_factory=list)
    description: str = ""
    tags: list[str] = field(default_factory=list)
    auto_detect_forms: bool = False  # Use smart form boundary detection

    def validate_result(self, fields: dict[str, Any], confidence: dict[str, float]) -> dict[str, Any]:
        """Validate extraction results against profile rules.

        Args:
            fields: Extracted field values.
            confidence: Confidence scores per field.

        Returns:
            Validation result with is_valid, errors, and warnings.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check required fields
        for field_name in self.required_fields:
            if field_name not in fields or fields[field_name] is None:
                errors.append(f"Missing required field: {field_name}")

        # Check confidence threshold
        for field_name, conf in confidence.items():
            if conf < self.confidence_threshold:
                warnings.append(
                    f"Low confidence for '{field_name}': {conf:.2f} < {self.confidence_threshold}"
                )

        # Run custom validations
        for validation in self.validations:
            value = fields.get(validation.field_name)
            is_valid, error_msg = validation.validate(value)
            if not is_valid and error_msg:
                errors.append(error_msg)

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "fields_validated": len(fields),
        }


# Built-in profiles registry
BUILT_IN_PROFILES: dict[str, ProcessingProfile] = {
    # Generic document profile (default)
    "default": ProcessingProfile(
        name="default",
        model_id="prebuilt-layout",
        pages_per_form=2,
        confidence_threshold=0.7,
        description="Default profile using prebuilt layout model",
        tags=["generic", "layout"],
    ),
    # Invoice processing
    "invoice": ProcessingProfile(
        name="invoice",
        model_id="prebuilt-invoice",
        pages_per_form=1,
        confidence_threshold=0.85,
        required_fields=["VendorName", "InvoiceTotal", "InvoiceDate"],
        validations=[
            FieldValidation("InvoiceTotal", "range", {"min": 0}),
            FieldValidation("VendorName", "required", {}),
        ],
        description="Invoice extraction with prebuilt invoice model",
        tags=["financial", "invoice"],
    ),
    # Receipt processing
    "receipt": ProcessingProfile(
        name="receipt",
        model_id="prebuilt-receipt",
        pages_per_form=1,
        confidence_threshold=0.8,
        required_fields=["MerchantName", "Total"],
        description="Receipt extraction with prebuilt receipt model",
        tags=["financial", "receipt"],
    ),
    # Tax form W-2
    "w2": ProcessingProfile(
        name="w2",
        model_id="prebuilt-tax.us.w2",
        pages_per_form=1,
        confidence_threshold=0.9,
        required_fields=["Employee", "Employer", "WagesTipsOtherCompensation"],
        description="W-2 tax form extraction",
        tags=["tax", "w2", "us"],
    ),
    # ID document
    "id-document": ProcessingProfile(
        name="id-document",
        model_id="prebuilt-idDocument",
        pages_per_form=1,
        confidence_threshold=0.85,
        required_fields=["FirstName", "LastName"],
        description="ID document (license, passport) extraction",
        tags=["identity", "document"],
    ),
    # Business card
    "business-card": ProcessingProfile(
        name="business-card",
        model_id="prebuilt-businessCard",
        pages_per_form=1,
        confidence_threshold=0.75,
        description="Business card extraction",
        tags=["contact", "business"],
    ),
    # Contract (multi-page)
    "contract": ProcessingProfile(
        name="contract",
        model_id="prebuilt-contract",
        pages_per_form=3,
        confidence_threshold=0.75,
        description="Contract document extraction (multi-page)",
        tags=["legal", "contract"],
    ),
    # Health insurance card
    "health-insurance": ProcessingProfile(
        name="health-insurance",
        model_id="prebuilt-healthInsuranceCard.us",
        pages_per_form=1,
        confidence_threshold=0.85,
        required_fields=["MemberName", "MemberId"],
        description="US Health insurance card extraction",
        tags=["healthcare", "insurance", "us"],
    ),
}

# Custom profiles loaded from environment/file
_custom_profiles: dict[str, ProcessingProfile] = {}


def load_custom_profiles() -> None:
    """Load custom profiles from CUSTOM_PROFILES_JSON environment variable.

    Expected format:
    {
        "my-form": {
            "model_id": "custom-model-v1",
            "pages_per_form": 2,
            "confidence_threshold": 0.85,
            "required_fields": ["field1", "field2"],
            "description": "My custom form"
        }
    }
    """
    global _custom_profiles

    profiles_json = os.getenv("CUSTOM_PROFILES_JSON")
    if not profiles_json:
        return

    try:
        profiles_data = json.loads(profiles_json)
        for name, data in profiles_data.items():
            validations = []
            for val_data in data.get("validations", []):
                validations.append(
                    FieldValidation(
                        field_name=val_data["field_name"],
                        validation_type=val_data["validation_type"],
                        params=val_data.get("params", {}),
                    )
                )

            _custom_profiles[name] = ProcessingProfile(
                name=name,
                model_id=data["model_id"],
                pages_per_form=data.get("pages_per_form", 2),
                confidence_threshold=data.get("confidence_threshold", 0.8),
                required_fields=data.get("required_fields", []),
                validations=validations,
                description=data.get("description", ""),
                tags=data.get("tags", []),
                auto_detect_forms=data.get("auto_detect_forms", False),
            )
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        import logging

        logging.getLogger(__name__).warning(f"Failed to load custom profiles: {e}")


def get_profile(name: str) -> ProcessingProfile | None:
    """Get a processing profile by name.

    Args:
        name: Profile name (e.g., "invoice", "w2", "custom-form").

    Returns:
        ProcessingProfile or None if not found.
    """
    # Check built-in profiles first
    if name in BUILT_IN_PROFILES:
        return BUILT_IN_PROFILES[name]

    # Load and check custom profiles
    if not _custom_profiles:
        load_custom_profiles()

    return _custom_profiles.get(name)


def list_profiles() -> list[dict[str, Any]]:
    """List all available profiles.

    Returns:
        List of profile summaries with name, model_id, description.
    """
    # Ensure custom profiles are loaded
    if not _custom_profiles:
        load_custom_profiles()

    profiles = []

    for profile in BUILT_IN_PROFILES.values():
        profiles.append(
            {
                "name": profile.name,
                "model_id": profile.model_id,
                "pages_per_form": profile.pages_per_form,
                "auto_detect_forms": profile.auto_detect_forms,
                "description": profile.description,
                "tags": profile.tags,
                "type": "built-in",
            }
        )

    for profile in _custom_profiles.values():
        profiles.append(
            {
                "name": profile.name,
                "model_id": profile.model_id,
                "pages_per_form": profile.pages_per_form,
                "auto_detect_forms": profile.auto_detect_forms,
                "description": profile.description,
                "tags": profile.tags,
                "type": "custom",
            }
        )

    return profiles


def create_profile_from_request(
    model_id: str,
    pages_per_form: int | None = None,
    confidence_threshold: float | None = None,
    required_fields: list[str] | None = None,
) -> ProcessingProfile:
    """Create an ad-hoc profile from request parameters.

    Args:
        model_id: Document Intelligence model ID.
        pages_per_form: Pages per form (default from config).
        confidence_threshold: Minimum confidence (default 0.8).
        required_fields: List of required field names.

    Returns:
        ProcessingProfile for the request.
    """
    from config import get_config

    config = get_config()

    return ProcessingProfile(
        name="ad-hoc",
        model_id=model_id,
        pages_per_form=pages_per_form or config.pages_per_form,
        confidence_threshold=confidence_threshold or 0.8,
        required_fields=required_fields or [],
        description="Ad-hoc profile from request parameters",
    )
