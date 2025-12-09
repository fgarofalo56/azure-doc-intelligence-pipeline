"""Unit tests for profiles module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from services.profiles import (
    BUILT_IN_PROFILES,
    FieldValidation,
    ProcessingProfile,
    _custom_profiles,
    create_profile_from_request,
    get_profile,
    list_profiles,
    load_custom_profiles,
)


class TestFieldValidation:
    """Tests for FieldValidation class."""

    def test_validate_required_with_value(self):
        """Test required validation with value present."""
        validation = FieldValidation(
            field_name="name",
            validation_type="required",
        )
        is_valid, error = validation.validate("John")
        assert is_valid is True
        assert error is None

    def test_validate_required_with_none(self):
        """Test required validation with None value."""
        validation = FieldValidation(
            field_name="name",
            validation_type="required",
        )
        is_valid, error = validation.validate(None)
        assert is_valid is False
        assert "required" in error.lower()

    def test_validate_required_with_empty_string(self):
        """Test required validation with empty string."""
        validation = FieldValidation(
            field_name="name",
            validation_type="required",
        )
        is_valid, error = validation.validate("")
        assert is_valid is False
        assert "required" in error.lower()

    def test_validate_format_matching(self):
        """Test format validation with matching pattern."""
        validation = FieldValidation(
            field_name="email",
            validation_type="format",
            params={"pattern": r"^[a-z]+@[a-z]+\.[a-z]+$"},
        )
        is_valid, error = validation.validate("test@example.com")
        assert is_valid is True
        assert error is None

    def test_validate_format_not_matching(self):
        """Test format validation with non-matching pattern."""
        validation = FieldValidation(
            field_name="email",
            validation_type="format",
            params={"pattern": r"^[a-z]+@[a-z]+\.[a-z]+$"},
        )
        is_valid, error = validation.validate("invalid-email")
        assert is_valid is False
        assert "does not match format" in error

    def test_validate_format_with_none(self):
        """Test format validation with None value (passes)."""
        validation = FieldValidation(
            field_name="email",
            validation_type="format",
            params={"pattern": r"^[a-z]+$"},
        )
        is_valid, error = validation.validate(None)
        assert is_valid is True
        assert error is None

    def test_validate_format_default_pattern(self):
        """Test format validation with default pattern (matches anything)."""
        validation = FieldValidation(
            field_name="field",
            validation_type="format",
        )
        is_valid, error = validation.validate("anything")
        assert is_valid is True
        assert error is None

    def test_validate_range_within(self):
        """Test range validation with value within range."""
        validation = FieldValidation(
            field_name="amount",
            validation_type="range",
            params={"min": 0, "max": 100},
        )
        is_valid, error = validation.validate(50)
        assert is_valid is True
        assert error is None

    def test_validate_range_below_min(self):
        """Test range validation with value below minimum."""
        validation = FieldValidation(
            field_name="amount",
            validation_type="range",
            params={"min": 0, "max": 100},
        )
        is_valid, error = validation.validate(-10)
        assert is_valid is False
        assert "below minimum" in error

    def test_validate_range_above_max(self):
        """Test range validation with value above maximum."""
        validation = FieldValidation(
            field_name="amount",
            validation_type="range",
            params={"min": 0, "max": 100},
        )
        is_valid, error = validation.validate(150)
        assert is_valid is False
        assert "above maximum" in error

    def test_validate_range_with_string_number(self):
        """Test range validation with string that can be converted to number."""
        validation = FieldValidation(
            field_name="amount",
            validation_type="range",
            params={"min": 0, "max": 100},
        )
        is_valid, error = validation.validate("50.5")
        assert is_valid is True
        assert error is None

    def test_validate_range_with_invalid_number(self):
        """Test range validation with non-numeric string."""
        validation = FieldValidation(
            field_name="amount",
            validation_type="range",
            params={"min": 0, "max": 100},
        )
        is_valid, error = validation.validate("not-a-number")
        assert is_valid is False
        assert "not a valid number" in error

    def test_validate_range_with_none(self):
        """Test range validation with None value (passes)."""
        validation = FieldValidation(
            field_name="amount",
            validation_type="range",
            params={"min": 0, "max": 100},
        )
        is_valid, error = validation.validate(None)
        assert is_valid is True
        assert error is None

    def test_validate_range_min_only(self):
        """Test range validation with only minimum specified."""
        validation = FieldValidation(
            field_name="amount",
            validation_type="range",
            params={"min": 0},
        )
        is_valid, error = validation.validate(1000000)
        assert is_valid is True
        assert error is None

    def test_validate_range_max_only(self):
        """Test range validation with only maximum specified."""
        validation = FieldValidation(
            field_name="amount",
            validation_type="range",
            params={"max": 100},
        )
        is_valid, error = validation.validate(-1000)
        assert is_valid is True
        assert error is None

    def test_validate_lookup_in_list(self):
        """Test lookup validation with value in allowed list."""
        validation = FieldValidation(
            field_name="status",
            validation_type="lookup",
            params={"values": ["active", "inactive", "pending"]},
        )
        is_valid, error = validation.validate("active")
        assert is_valid is True
        assert error is None

    def test_validate_lookup_not_in_list(self):
        """Test lookup validation with value not in allowed list."""
        validation = FieldValidation(
            field_name="status",
            validation_type="lookup",
            params={"values": ["active", "inactive", "pending"]},
        )
        is_valid, error = validation.validate("unknown")
        assert is_valid is False
        assert "not in allowed values" in error

    def test_validate_lookup_with_none(self):
        """Test lookup validation with None value (passes)."""
        validation = FieldValidation(
            field_name="status",
            validation_type="lookup",
            params={"values": ["active", "inactive"]},
        )
        is_valid, error = validation.validate(None)
        assert is_valid is True
        assert error is None

    def test_validate_lookup_numeric_values(self):
        """Test lookup validation with numeric values."""
        validation = FieldValidation(
            field_name="priority",
            validation_type="lookup",
            params={"values": [1, 2, 3]},
        )
        is_valid, error = validation.validate(2)
        assert is_valid is True
        assert error is None

    def test_validate_unknown_type(self):
        """Test validation with unknown type (passes by default)."""
        validation = FieldValidation(
            field_name="field",
            validation_type="unknown_type",
        )
        is_valid, error = validation.validate("any_value")
        assert is_valid is True
        assert error is None


class TestProcessingProfile:
    """Tests for ProcessingProfile class."""

    def test_create_profile_with_defaults(self):
        """Test creating profile with default values."""
        profile = ProcessingProfile(
            name="test",
            model_id="test-model",
        )
        assert profile.name == "test"
        assert profile.model_id == "test-model"
        assert profile.pages_per_form == 2
        assert profile.confidence_threshold == 0.8
        assert profile.required_fields == []
        assert profile.validations == []
        assert profile.auto_detect_forms is False

    def test_create_profile_with_all_fields(self):
        """Test creating profile with all fields specified."""
        validations = [FieldValidation("field1", "required")]
        profile = ProcessingProfile(
            name="test",
            model_id="test-model",
            pages_per_form=3,
            confidence_threshold=0.9,
            required_fields=["field1", "field2"],
            validations=validations,
            description="Test profile",
            tags=["test", "demo"],
            auto_detect_forms=True,
        )
        assert profile.pages_per_form == 3
        assert profile.confidence_threshold == 0.9
        assert profile.required_fields == ["field1", "field2"]
        assert profile.validations == validations
        assert profile.description == "Test profile"
        assert profile.tags == ["test", "demo"]
        assert profile.auto_detect_forms is True

    def test_validate_result_all_valid(self):
        """Test validate_result with all fields valid."""
        profile = ProcessingProfile(
            name="test",
            model_id="test-model",
            confidence_threshold=0.8,
            required_fields=["name", "amount"],
        )
        result = profile.validate_result(
            fields={"name": "John", "amount": 100},
            confidence={"name": 0.95, "amount": 0.9},
        )
        assert result["is_valid"] is True
        assert result["errors"] == []
        assert result["warnings"] == []

    def test_validate_result_missing_required_field(self):
        """Test validate_result with missing required field."""
        profile = ProcessingProfile(
            name="test",
            model_id="test-model",
            required_fields=["name", "amount"],
        )
        result = profile.validate_result(
            fields={"name": "John"},
            confidence={"name": 0.9},
        )
        assert result["is_valid"] is False
        assert any("amount" in err.lower() for err in result["errors"])

    def test_validate_result_null_required_field(self):
        """Test validate_result with None value for required field."""
        profile = ProcessingProfile(
            name="test",
            model_id="test-model",
            required_fields=["name"],
        )
        result = profile.validate_result(
            fields={"name": None},
            confidence={},
        )
        assert result["is_valid"] is False
        assert any("name" in err.lower() for err in result["errors"])

    def test_validate_result_low_confidence(self):
        """Test validate_result with low confidence score."""
        profile = ProcessingProfile(
            name="test",
            model_id="test-model",
            confidence_threshold=0.9,
        )
        result = profile.validate_result(
            fields={"name": "John"},
            confidence={"name": 0.7},
        )
        assert result["is_valid"] is True  # Low confidence is warning, not error
        assert len(result["warnings"]) > 0
        assert any("confidence" in w.lower() for w in result["warnings"])

    def test_validate_result_with_validations(self):
        """Test validate_result with custom validations."""
        profile = ProcessingProfile(
            name="test",
            model_id="test-model",
            validations=[
                FieldValidation("amount", "range", {"min": 0, "max": 1000}),
            ],
        )
        result = profile.validate_result(
            fields={"amount": 2000},
            confidence={"amount": 0.9},
        )
        assert result["is_valid"] is False
        assert any("maximum" in err.lower() for err in result["errors"])

    def test_validate_result_fields_validated_count(self):
        """Test validate_result returns correct fields_validated count."""
        profile = ProcessingProfile(
            name="test",
            model_id="test-model",
        )
        result = profile.validate_result(
            fields={"field1": "a", "field2": "b", "field3": "c"},
            confidence={},
        )
        assert result["fields_validated"] == 3


class TestBuiltInProfiles:
    """Tests for built-in profiles."""

    def test_all_built_in_profiles_exist(self):
        """Test all expected built-in profiles are defined."""
        expected_profiles = [
            "default",
            "invoice",
            "receipt",
            "w2",
            "id-document",
            "business-card",
            "contract",
            "health-insurance",
        ]
        for profile_name in expected_profiles:
            assert profile_name in BUILT_IN_PROFILES

    def test_default_profile(self):
        """Test default profile configuration."""
        profile = BUILT_IN_PROFILES["default"]
        assert profile.model_id == "prebuilt-layout"
        assert profile.pages_per_form == 2

    def test_invoice_profile(self):
        """Test invoice profile configuration."""
        profile = BUILT_IN_PROFILES["invoice"]
        assert profile.model_id == "prebuilt-invoice"
        assert profile.pages_per_form == 1
        assert "VendorName" in profile.required_fields


class TestLoadCustomProfiles:
    """Tests for load_custom_profiles function."""

    def setup_method(self):
        """Clear custom profiles before each test."""
        _custom_profiles.clear()

    def teardown_method(self):
        """Clear custom profiles after each test."""
        _custom_profiles.clear()

    @patch.dict("os.environ", {"CUSTOM_PROFILES_JSON": ""})
    def test_load_custom_profiles_empty_env(self):
        """Test loading profiles with empty environment variable."""
        load_custom_profiles()
        assert len(_custom_profiles) == 0

    @patch.dict("os.environ", {}, clear=True)
    def test_load_custom_profiles_no_env(self):
        """Test loading profiles with no environment variable."""
        load_custom_profiles()
        assert len(_custom_profiles) == 0

    @patch.dict(
        "os.environ",
        {
            "CUSTOM_PROFILES_JSON": json.dumps(
                {
                    "my-form": {
                        "model_id": "custom-model-v1",
                        "pages_per_form": 3,
                        "confidence_threshold": 0.85,
                        "required_fields": ["field1", "field2"],
                        "description": "My custom form",
                        "tags": ["custom"],
                        "auto_detect_forms": True,
                    }
                }
            )
        },
    )
    def test_load_custom_profiles_success(self):
        """Test loading custom profiles from environment."""
        load_custom_profiles()
        assert "my-form" in _custom_profiles
        profile = _custom_profiles["my-form"]
        assert profile.model_id == "custom-model-v1"
        assert profile.pages_per_form == 3
        assert profile.confidence_threshold == 0.85
        assert profile.required_fields == ["field1", "field2"]
        assert profile.auto_detect_forms is True

    @patch.dict(
        "os.environ",
        {
            "CUSTOM_PROFILES_JSON": json.dumps(
                {
                    "validated-form": {
                        "model_id": "model-v1",
                        "validations": [
                            {
                                "field_name": "amount",
                                "validation_type": "range",
                                "params": {"min": 0, "max": 100},
                            }
                        ],
                    }
                }
            )
        },
    )
    def test_load_custom_profiles_with_validations(self):
        """Test loading custom profiles with validations."""
        load_custom_profiles()
        assert "validated-form" in _custom_profiles
        profile = _custom_profiles["validated-form"]
        assert len(profile.validations) == 1
        assert profile.validations[0].field_name == "amount"
        assert profile.validations[0].validation_type == "range"

    @patch.dict("os.environ", {"CUSTOM_PROFILES_JSON": "invalid json"})
    def test_load_custom_profiles_invalid_json(self):
        """Test loading profiles with invalid JSON (should not raise)."""
        load_custom_profiles()  # Should not raise
        assert len(_custom_profiles) == 0

    @patch.dict(
        "os.environ",
        {"CUSTOM_PROFILES_JSON": json.dumps({"form": {"missing_model_id": True}})},
    )
    def test_load_custom_profiles_missing_required_field(self):
        """Test loading profiles with missing required field."""
        load_custom_profiles()  # Should not raise, but profile won't be added
        assert len(_custom_profiles) == 0


class TestGetProfile:
    """Tests for get_profile function."""

    def setup_method(self):
        """Clear custom profiles before each test."""
        _custom_profiles.clear()

    def teardown_method(self):
        """Clear custom profiles after each test."""
        _custom_profiles.clear()

    def test_get_built_in_profile(self):
        """Test getting a built-in profile."""
        profile = get_profile("invoice")
        assert profile is not None
        assert profile.name == "invoice"

    def test_get_nonexistent_profile(self):
        """Test getting a profile that doesn't exist."""
        profile = get_profile("nonexistent")
        assert profile is None

    @patch.dict(
        "os.environ",
        {
            "CUSTOM_PROFILES_JSON": json.dumps(
                {"custom-form": {"model_id": "custom-model"}}
            )
        },
    )
    def test_get_custom_profile(self):
        """Test getting a custom profile."""
        profile = get_profile("custom-form")
        assert profile is not None
        assert profile.name == "custom-form"
        assert profile.model_id == "custom-model"


class TestListProfiles:
    """Tests for list_profiles function."""

    def setup_method(self):
        """Clear custom profiles before each test."""
        _custom_profiles.clear()

    def teardown_method(self):
        """Clear custom profiles after each test."""
        _custom_profiles.clear()

    def test_list_profiles_returns_built_in(self):
        """Test list_profiles returns built-in profiles."""
        profiles = list_profiles()
        profile_names = [p["name"] for p in profiles]
        assert "default" in profile_names
        assert "invoice" in profile_names

    def test_list_profiles_includes_type(self):
        """Test list_profiles includes type field."""
        profiles = list_profiles()
        for p in profiles:
            assert p["type"] in ["built-in", "custom"]

    @patch.dict(
        "os.environ",
        {
            "CUSTOM_PROFILES_JSON": json.dumps(
                {"my-custom": {"model_id": "custom-model", "description": "My custom"}}
            )
        },
    )
    def test_list_profiles_includes_custom(self):
        """Test list_profiles includes custom profiles."""
        profiles = list_profiles()
        custom_profiles = [p for p in profiles if p["type"] == "custom"]
        assert len(custom_profiles) > 0
        assert any(p["name"] == "my-custom" for p in custom_profiles)

    def test_list_profiles_structure(self):
        """Test list_profiles returns correct structure."""
        profiles = list_profiles()
        for p in profiles:
            assert "name" in p
            assert "model_id" in p
            assert "pages_per_form" in p
            assert "auto_detect_forms" in p
            assert "description" in p
            assert "tags" in p
            assert "type" in p


class TestCreateProfileFromRequest:
    """Tests for create_profile_from_request function."""

    @patch("config.get_config")
    def test_create_profile_with_defaults(self, mock_config):
        """Test creating profile with default values from config."""
        mock_config.return_value = MagicMock(pages_per_form=4)

        profile = create_profile_from_request(model_id="custom-model")

        assert profile.name == "ad-hoc"
        assert profile.model_id == "custom-model"
        assert profile.pages_per_form == 4  # From config
        assert profile.confidence_threshold == 0.8  # Default

    @patch("config.get_config")
    def test_create_profile_with_all_params(self, mock_config):
        """Test creating profile with all parameters specified."""
        mock_config.return_value = MagicMock(pages_per_form=2)

        profile = create_profile_from_request(
            model_id="custom-model",
            pages_per_form=5,
            confidence_threshold=0.95,
            required_fields=["field1", "field2"],
        )

        assert profile.model_id == "custom-model"
        assert profile.pages_per_form == 5  # Override
        assert profile.confidence_threshold == 0.95  # Override
        assert profile.required_fields == ["field1", "field2"]

    @patch("config.get_config")
    def test_create_profile_description(self, mock_config):
        """Test created profile has ad-hoc description."""
        mock_config.return_value = MagicMock(pages_per_form=2)

        profile = create_profile_from_request(model_id="model")

        assert "ad-hoc" in profile.description.lower()
