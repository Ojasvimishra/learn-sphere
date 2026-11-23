"""
LearnSphere - Authentication Views (Tier 2 / Tier 1 Bridge)
Supports both HTML session-based rendering and JSON REST API token flows.
"""

from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.views.decorators.http import require_http_methods
from services.auth_service import AuthService
from core.utils import api_success, api_error
import json

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

        success, msg, user, token = auth_service.authenticate(identifier, password)
        if success:
            request.session["mongo_user_id"] = user["id"]
            request.session["mongo_user_role"] = user.get("role", "student")
            request.session["jwt_token"] = token
            if not remember_me:
                request.session.set_expiry(0)  # Browser close expiry
            else:
                request.session.set_expiry(60 * 60 * 24 * 7)  # 7 days

            next_url = request.GET.get("next") or request.POST.get("next") or "/dashboard/"
            return redirect(next_url)
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
    if request.method == "POST":
        username = request.POST.get("username", "")
        email = request.POST.get("email", "")
        password = request.POST.get("password", "")
        role = request.POST.get("role", "student")
        full_name = request.POST.get("full_name", "")

        success, msg, user = auth_service.register(
            username=username,
            email=email,
            password=password,
            role=role,
            full_name=full_name
        )
        if success:
            # Auto login
            _, _, _, token = auth_service.authenticate(username, password)
            request.session["mongo_user_id"] = user["id"]
            request.session["mongo_user_role"] = user.get("role", "student")
            request.session["jwt_token"] = token
            return redirect("/dashboard/?welcome=1")
        else:
            error_msg = msg

    return render(request, "pages/register.html", {"error_msg": error_msg})


@require_http_methods(["GET", "POST"])
def logout_view(request):
    request.session.flush()
    return redirect("/")


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

    success, msg, user, token = auth_service.authenticate(identifier, password)
    if not success:
        return api_error(msg, 401)

    return api_success({
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": user.get("role", "student"),
            "full_name": user.get("full_name", "")
        }
    }, message="Login successful")


@csrf_exempt
@require_http_methods(["POST"])
def api_register(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return api_error("Invalid JSON body", 400)

    success, msg, user = auth_service.register(
        username=data.get("username", ""),
        email=data.get("email", ""),
        password=data.get("password", ""),
        role=data.get("role", "student"),
        full_name=data.get("full_name", "")
    )
    if not success:
        return api_error(msg, 400)

    return api_success({"id": user["id"], "username": user["username"]}, message="Registration successful", status_code=201)


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
        "enrolled_courses": user.get("enrolled_courses", []),
        "bookmarked_resources": user.get("bookmarked_resources", [])
    })
