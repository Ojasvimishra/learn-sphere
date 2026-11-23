"""
LearnSphere - Authentication Views (Tier 2 / Tier 1 Bridge)
Supports HTML session rendering with HttpOnly SameSite cookies and JSON REST API token flows
with short-lived access JWT (15m) and rotating refresh tokens (7d).
"""

import json
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.views.decorators.http import require_http_methods
from services.auth_service import AuthService
from core.utils import api_success, api_error
from core.validation import validate_email, validate_username, validate_string, ValidationError
from core.middleware import get_client_ip

auth_service = AuthService()


@require_http_methods(["GET", "POST"])
@csrf_protect
def login_view(request):
    if getattr(request, "mongo_user", None):
        return redirect("/dashboard/")

    error_msg = None
    if request.method == "POST":
        identifier = request.POST.get("identifier", "").strip()
        password = request.POST.get("password", "")
        remember_me = request.POST.get("remember_me")
        ip = get_client_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "")

        success, msg, user, tokens = auth_service.authenticate(identifier, password, ip_address=ip, user_agent=ua)
        if success:
            request.session["mongo_user_id"] = user["id"]
            request.session["mongo_user_role"] = user.get("role", "student")
            request.session["jwt_token"] = tokens["access_token"]

            if not remember_me:
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(60 * 60 * 24 * 7)

            next_url = request.GET.get("next") or request.POST.get("next") or "/dashboard/"
            response = redirect(next_url)

            # Set HttpOnly SameSite Lax cookies
            is_secure = not request.build_absolute_uri().startswith("http://localhost") and request.is_secure()
            response.set_cookie(
                "learnsphere_access_token",
                tokens["access_token"],
                max_age=15 * 60,
                httponly=True,
                samesite="Lax",
                secure=is_secure
            )
            response.set_cookie(
                "learnsphere_refresh_token",
                tokens["refresh_token"],
                max_age=7 * 86400,
                httponly=True,
                samesite="Lax",
                secure=is_secure
            )
            return response
        else:
            error_msg = msg

    return render(request, "pages/login.html", {
        "error_msg": error_msg,
        "next": request.GET.get("next", "")
    })


@require_http_methods(["GET", "POST"])
@csrf_protect
def register_view(request):
    if getattr(request, "mongo_user", None):
        return redirect("/dashboard/")

    error_msg = None
    success_msg = None
    if request.method == "POST":
        username = request.POST.get("username", "")
        email = request.POST.get("email", "")
        password = request.POST.get("password", "")
        role = request.POST.get("role", "student")
        full_name = request.POST.get("full_name", "")
        ip = get_client_ip(request)

        success, msg, user = auth_service.register(
            username=username,
            email=email,
            password=password,
            role=role,
            full_name=full_name,
            ip_address=ip
        )
        if success:
            if user.get("role") == "educator" and not user.get("is_approved", True):
                # Queued for admin approval
                return render(request, "pages/login.html", {
                    "success_msg": "Your educator application has been submitted and is awaiting administrator verification. You will be notified once reviewed."
                })

            # Auto login for student
            _, _, _, tokens = auth_service.authenticate(username, password, ip_address=ip)
            request.session["mongo_user_id"] = user["id"]
            request.session["mongo_user_role"] = user.get("role", "student")
            request.session["jwt_token"] = tokens["access_token"]

            response = redirect("/dashboard/?welcome=1")
            is_secure = not request.build_absolute_uri().startswith("http://localhost") and request.is_secure()
            response.set_cookie(
                "learnsphere_access_token",
                tokens["access_token"],
                max_age=15 * 60,
                httponly=True,
                samesite="Lax",
                secure=is_secure
            )
            response.set_cookie(
                "learnsphere_refresh_token",
                tokens["refresh_token"],
                max_age=7 * 86400,
                httponly=True,
                samesite="Lax",
                secure=is_secure
            )
            return response
        else:
            error_msg = msg

    return render(request, "pages/register.html", {"error_msg": error_msg})


@require_http_methods(["GET", "POST"])
def logout_view(request):
    # Revoke refresh token if present
    refresh_token = request.COOKIES.get("learnsphere_refresh_token")
    if refresh_token:
        auth_service.revoke_refresh_token(refresh_token)

    request.session.flush()
    response = redirect("/")
    response.delete_cookie("learnsphere_access_token")
    response.delete_cookie("learnsphere_refresh_token")
    return response


# --- REST API Endpoints ---

@csrf_exempt
@require_http_methods(["POST"])
def api_login(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return api_error("Invalid JSON body", 400)

    identifier = data.get("identifier", "").strip()
    password = data.get("password", "")
    ip = get_client_ip(request)
    ua = request.META.get("HTTP_USER_AGENT", "")

    success, msg, user, tokens = auth_service.authenticate(identifier, password, ip_address=ip, user_agent=ua)
    if not success:
        return api_error(msg, 401)

    return api_success({
        "tokens": tokens,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": user.get("role", "student"),
            "full_name": user.get("full_name", ""),
            "is_approved": user.get("is_approved", True)
        }
    }, message="Login successful")


@csrf_exempt
@require_http_methods(["POST"])
def api_register(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return api_error("Invalid JSON body", 400)

    ip = get_client_ip(request)
    success, msg, user = auth_service.register(
        username=data.get("username", ""),
        email=data.get("email", ""),
        password=data.get("password", ""),
        role=data.get("role", "student"),
        full_name=data.get("full_name", ""),
        ip_address=ip
    )
    if not success:
        return api_error(msg, 400)

    return api_success(
        {
            "id": user["id"],
            "username": user["username"],
            "role": user.get("role"),
            "is_approved": user.get("is_approved", True)
        },
        message=msg,
        status_code=201
    )


@csrf_exempt
@require_http_methods(["POST"])
def api_refresh_token(request):
    """Rotates refresh token and returns new token pair."""
    try:
        data = json.loads(request.body)
    except Exception:
        data = {}

    token_str = data.get("refresh_token") or request.COOKIES.get("learnsphere_refresh_token")
    if not token_str:
        return api_error("Refresh token is required.", 400)

    success, msg, new_tokens = auth_service.refresh_access_token(token_str)
    if not success:
        return api_error(msg, 401)

    response = api_success(new_tokens, message="Token refreshed")
    is_secure = not request.build_absolute_uri().startswith("http://localhost") and request.is_secure()
    response.set_cookie(
        "learnsphere_access_token",
        new_tokens["access_token"],
        max_age=15 * 60,
        httponly=True,
        samesite="Lax",
        secure=is_secure
    )
    response.set_cookie(
        "learnsphere_refresh_token",
        new_tokens["refresh_token"],
        max_age=7 * 86400,
        httponly=True,
        samesite="Lax",
        secure=is_secure
    )
    return response


@csrf_exempt
@require_http_methods(["POST"])
def api_logout(request):
    try:
        data = json.loads(request.body)
    except Exception:
        data = {}

    token_str = data.get("refresh_token") or request.COOKIES.get("learnsphere_refresh_token")
    if token_str:
        auth_service.revoke_refresh_token(token_str)

    request.session.flush()
    response = api_success({}, message="Logged out successfully")
    response.delete_cookie("learnsphere_access_token")
    response.delete_cookie("learnsphere_refresh_token")
    return response


@require_http_methods(["GET"])
def api_me(request):
    user = getattr(request, "mongo_user", None)
    if not user:
        return api_error("Not authenticated", 401)
    return api_success({
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user.get("role", "student"),
        "full_name": user.get("full_name", ""),
        "is_approved": user.get("is_approved", True),
        "enrolled_courses": user.get("enrolled_courses", []),
        "bookmarked_resources": user.get("bookmarked_resources", [])
    })
