"""
LearnSphere - Authorization & RBAC Permission Decorators
Granular role and code-permission guards for views and REST endpoints.
Roles: 'super_admin', 'dept_admin', 'moderator', 'educator', 'student'
"""

from functools import wraps
from typing import Any, Dict, List, Optional
from django.http import JsonResponse
from django.shortcuts import redirect
from rest_framework import permissions
from core.rbac import (
    has_permission,
    normalize_role,
    can_access_portal,
    ROLE_SUPER_ADMIN,
    ROLE_DEPT_ADMIN,
    ROLE_MODERATOR,
    ROLE_EDUCATOR,
    ROLE_STUDENT
)


def login_required_mongo(redirect_to="/auth/login/"):
    """View decorator ensuring request has an authenticated active mongo_user."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = getattr(request, "mongo_user", None)
            if not user or not user.get("is_active", True):
                if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.path.startswith("/api/"):
                    return JsonResponse({"error": "Unauthorized", "message": "Authentication required."}, status=401)
                return redirect(f"{redirect_to}?next={request.path}")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def role_required_mongo(*allowed_roles):
    """View decorator verifying user has at least one of the specified RBAC roles."""
    normalized_allowed = [normalize_role(r) for r in allowed_roles]

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = getattr(request, "mongo_user", None)
            if not user or not user.get("is_active", True):
                if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.path.startswith("/api/"):
                    return JsonResponse({"error": "Unauthorized", "message": "Authentication required."}, status=401)
                return redirect(f"/auth/login/?next={request.path}")

            user_role = normalize_role(user.get("role"))
            if user_role == ROLE_SUPER_ADMIN:
                return view_func(request, *args, **kwargs)

            if user_role not in normalized_allowed:
                if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.path.startswith("/api/"):
                    return JsonResponse(
                        {"error": "Forbidden", "message": f"Requires one of roles: {list(allowed_roles)}"},
                        status=403
                    )
                return redirect("/dashboard/?error=insufficient_permissions")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def permission_required_mongo(permission_code: str):
    """View decorator verifying user holds the specific code permission."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = getattr(request, "mongo_user", None)
            if not user or not user.get("is_active", True):
                if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.path.startswith("/api/"):
                    return JsonResponse({"error": "Unauthorized", "message": "Authentication required."}, status=401)
                return redirect(f"/auth/login/?next={request.path}")

            if not has_permission(user, permission_code):
                if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.path.startswith("/api/"):
                    return JsonResponse(
                        {"error": "Forbidden", "message": f"Permission denied: requires '{permission_code}'"},
                        status=403
                    )
                return redirect("/dashboard/?error=permission_denied")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def can_edit_resource(user: Optional[Dict[str, Any]], resource_owner_id: Any) -> bool:
    """Helper to check if user is resource author or has elevated admin rights."""
    if not user:
        return False
    user_role = normalize_role(user.get("role"))
    if user_role in [ROLE_SUPER_ADMIN, ROLE_DEPT_ADMIN]:
        return True
    return str(user.get("id")) == str(resource_owner_id)


class IsMongoAuthenticated(permissions.BasePermission):
    """DRF permission checking request.mongo_user."""
    def has_permission(self, request, view):
        user = getattr(request, "mongo_user", None)
        return bool(user and user.get("is_active", True))


class HasPermissionCode(permissions.BasePermission):
    """DRF permission dynamically checking permission code attribute on view."""
    def has_permission(self, request, view):
        user = getattr(request, "mongo_user", None)
        if not user or not user.get("is_active", True):
            return False
        code = getattr(view, "required_permission", None)
        if not code:
            return True
        return has_permission(user, code)


class IsEducatorOrAdmin(permissions.BasePermission):
    """DRF permission allowing only educators or administrators."""
    def has_permission(self, request, view):
        user = getattr(request, "mongo_user", None)
        if not user or not user.get("is_active", True):
            return False
        role = normalize_role(user.get("role"))
        return role in [ROLE_SUPER_ADMIN, ROLE_DEPT_ADMIN, ROLE_EDUCATOR]
