"""
LearnSphere - Core Utility Functions
Provides JSON formatting, safe sanitization, and helper response constructors.
"""

from typing import Any, Dict
from django.http import JsonResponse


def api_success(data: Any = None, message: str = "Success", status_code: int = 200) -> JsonResponse:
    """Standardized API success envelope."""
    payload = {
        "status": "success",
        "message": message,
        "data": data
    }
    return JsonResponse(payload, status=status_code)


def api_error(message: str = "An error occurred", status_code: int = 400, errors: Any = None) -> JsonResponse:
    """Standardized API error envelope."""
    payload = {
        "status": "error",
        "message": message,
        "errors": errors
    }
    return JsonResponse(payload, status=status_code)
