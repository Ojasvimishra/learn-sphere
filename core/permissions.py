"""
LearnSphere - Authorization & RBAC Permission Decorators
Granular role guards for views and REST endpoints.
Roles: 'student', 'educator', 'admin'
"""

from functools import wraps
from django.http import JsonResponse
from django.shortcuts import redirect
from rest_framework import permissions


def login_required_mongo(redirect_to="/auth/login/"):
    """View decorator ensuring request has an authenticated mongo_user."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not getattr(request, "mongo_user", None):
                if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.path.startswith("/api/"):
                    return JsonResponse({"error": "Unauthorized", "message": "Authentication required."}, status=401)
                return redirect(f"{redirect_to}?next={request.path}")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def role_required_mongo(*allowed_roles):
    """View decorator verifying user has at least one of the specified RBAC roles."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = getattr(request, "mongo_user", None)
            if not user:
                if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.path.startswith("/api/"):
                    return JsonResponse({"error": "Unauthorized", "message": "Authentication required."}, status=401)
                return redirect(f"/auth/login/?next={request.path}")

            user_role = user.get("role", "student")
            if user_role not in allowed_roles and "admin" not in allowed_roles and user_role != "admin":
                if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.path.startswith("/api/"):
                    return JsonResponse({"error": "Forbidden", "message": f"Requires one of roles: {allowed_roles}"}, status=403)
                return redirect("/dashboard/?error=insufficient_permissions")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


class IsMongoAuthenticated(permissions.BasePermission):
    """DRF permission class for checking request.mongo_user."""
    def has_permission(self, request, view):
        return bool(getattr(request, "mongo_user", None))


class IsEducatorOrAdmin(permissions.BasePermission):
    """DRF permission allowing only educators or administrators."""
    def has_permission(self, request, view):
        user = getattr(request, "mongo_user", None)
        if not user:
            return False
        return user.get("role") in ["educator", "admin"]
