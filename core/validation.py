"""
LearnSphere - Strict Schema Boundary Validation
Guarantees input types and protects against NoSQL injection, malformed IDs,
and parameter tampering. Replaces fragile blacklist-only approaches.
"""

import re
from typing import Any, Dict, List, Optional
from bson import ObjectId


class ValidationError(Exception):
    """Raised when request payload violates type or format constraints."""
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.field = field


EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")
OBJECTID_REGEX = re.compile(r"^[a-fA-F0-9]{24}$")


def validate_string(
    val: Any,
    field_name: str,
    min_length: int = 1,
    max_length: int = 255,
    allow_empty: bool = False
) -> str:
    """Ensures value is strictly a string within length bounds."""
    if val is None:
        if allow_empty:
            return ""
        raise ValidationError(f"Field '{field_name}' is required.", field=field_name)

    if not isinstance(val, str):
        raise ValidationError(
            f"Field '{field_name}' must be a string, got {type(val).__name__}.",
            field=field_name
        )

    val = val.strip()
    if not val and not allow_empty:
        raise ValidationError(f"Field '{field_name}' cannot be empty.", field=field_name)

    if len(val) < min_length:
        raise ValidationError(
            f"Field '{field_name}' must be at least {min_length} characters.",
            field=field_name
        )

    if len(val) > max_length:
        raise ValidationError(
            f"Field '{field_name}' cannot exceed {max_length} characters.",
            field=field_name
        )

    return val


def validate_email(val: Any, field_name: str = "email") -> str:
    """Strictly validates email format and length."""
    val = validate_string(val, field_name, min_length=5, max_length=120).lower()
    if not EMAIL_REGEX.match(val):
        raise ValidationError(f"Field '{field_name}' contains an invalid email address.", field=field_name)
    return val


def validate_username(val: Any, field_name: str = "username") -> str:
    """Validates alphanumeric username format."""
    val = validate_string(val, field_name, min_length=3, max_length=32).lower()
    if not USERNAME_REGEX.match(val):
        raise ValidationError(
            f"Field '{field_name}' must be 3-32 characters and contain only letters, numbers, underscores, dashes or dots.",
            field=field_name
        )
    return val


def validate_object_id(val: Any, field_name: str = "id") -> ObjectId:
    """Ensures value is a valid 24-character hexadecimal ObjectId."""
    if isinstance(val, ObjectId):
        return val

    if not isinstance(val, str) or not OBJECTID_REGEX.match(val):
        raise ValidationError(
            f"Field '{field_name}' must be a valid 24-character hexadecimal ObjectId.",
            field=field_name
        )
    return ObjectId(val)


def validate_int(
    val: Any,
    field_name: str,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None,
    default: Optional[int] = None
) -> int:
    """Ensures value is an integer within valid range."""
    if val is None:
        if default is not None:
            return default
        raise ValidationError(f"Field '{field_name}' is required.", field=field_name)

    try:
        num = int(val)
    except (ValueError, TypeError):
        raise ValidationError(f"Field '{field_name}' must be an integer.", field=field_name)

    if min_val is not None and num < min_val:
        raise ValidationError(f"Field '{field_name}' cannot be less than {min_val}.", field=field_name)
    if max_val is not None and num > max_val:
        raise ValidationError(f"Field '{field_name}' cannot be greater than {max_val}.", field=field_name)

    return num


def validate_payload_types(payload: Any, allowed_schema: Dict[str, type]) -> Dict[str, Any]:
    """
    Validates a dictionary against an allowed schema dictionary.
    Rejects nested dicts where strings are expected (preventing operator injection like {"$gt": ""}).
    """
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object.")

    validated = {}
    for field_name, expected_type in allowed_schema.items():
        if field_name not in payload:
            continue

        val = payload[field_name]
        if val is None:
            validated[field_name] = None
            continue

        if expected_type == str:
            if not isinstance(val, str):
                raise ValidationError(
                    f"Invalid type for '{field_name}': expected string, got {type(val).__name__}.",
                    field=field_name
                )
            validated[field_name] = val.strip()

        elif expected_type == int:
            if not isinstance(val, int) or isinstance(val, bool):
                raise ValidationError(
                    f"Invalid type for '{field_name}': expected integer, got {type(val).__name__}.",
                    field=field_name
                )
            validated[field_name] = val

        elif expected_type == bool:
            if not isinstance(val, bool):
                raise ValidationError(
                    f"Invalid type for '{field_name}': expected boolean, got {type(val).__name__}.",
                    field=field_name
                )
            validated[field_name] = val

        elif expected_type == list:
            if not isinstance(val, list):
                raise ValidationError(
                    f"Invalid type for '{field_name}': expected list, got {type(val).__name__}.",
                    field=field_name
                )
            # Ensure elements do not contain arbitrary dict operators
            for item in val:
                if isinstance(item, dict):
                    assert_no_mongo_operators(item)
            validated[field_name] = val

        elif expected_type == dict:
            if not isinstance(val, dict):
                raise ValidationError(
                    f"Invalid type for '{field_name}': expected dict, got {type(val).__name__}.",
                    field=field_name
                )
            assert_no_mongo_operators(val)
            validated[field_name] = val

    return validated


def assert_no_mongo_operators(data: Any):
    """Recursively checks that no dictionary key starts with '$'."""
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(k, str) and k.startswith("$"):
                raise ValidationError(f"Forbidden query operator key '{k}' detected in input.")
            assert_no_mongo_operators(v)
    elif isinstance(data, list):
        for item in data:
            assert_no_mongo_operators(item)
