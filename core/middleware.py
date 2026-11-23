"""
LearnSphere - Core Security & Rate Limiting Middleware
Provides:
1. Enterprise Security Headers (HSTS, CSP, Permissions-Policy, X-Frame-Options, X-Content-Type-Options)
2. In-flight Concurrency Counter and Response Timing
3. Redis-backed Rate Limiter with per-endpoint granular limits and trusted proxy handling
4. Seamless Session & Short-Lived JWT Authentication context injection (request.mongo_user)
"""

import time
import os
import threading
from django.conf import settings
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from services.auth_service import AuthService
from core.redis_client import get_cache_client

# Thread-safe in-flight metrics
_metrics_lock = threading.Lock()
_active_connections = 0
_total_requests_served = 0
_peak_concurrency = 0

auth_service = AuthService()
cache_client = get_cache_client()

# Trusted proxies list from configuration
TRUSTED_PROXIES = set(os.getenv("TRUSTED_PROXIES", "127.0.0.1,::1").split(","))

# Granular Rate Limits
RATE_LIMIT_LOGIN = int(os.getenv("RATE_LIMIT_LOGIN", "5"))         # 5 per minute per IP+Account
RATE_LIMIT_AI = int(os.getenv("RATE_LIMIT_AI", "50"))              # 50 per day per user
RATE_LIMIT_API = int(os.getenv("RATE_LIMIT_API", "120"))           # 120 per minute per IP
RATE_LIMIT_DEFAULT = int(os.getenv("RATE_LIMIT_DEFAULT", "300"))   # 300 per minute per IP


def get_client_ip(request) -> str:
    """Extracts client IP, respecting X-Forwarded-For ONLY when coming from a trusted proxy."""
    remote_addr = request.META.get("REMOTE_ADDR", "127.0.0.1")
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded and remote_addr in TRUSTED_PROXIES:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[0]
    return remote_addr


def get_concurrency_stats():
    """Returns real-time concurrency metrics for monitoring & benchmarks."""
    with _metrics_lock:
        return {
            "active_concurrency": _active_connections,
            "peak_concurrency": _peak_concurrency,
            "total_requests": _total_requests_served
        }


class ConcurrencyAndPerformanceMiddleware(MiddlewareMixin):
    """Tracks real-time concurrency, latency, and injects performance headers."""
    def process_request(self, request):
        global _active_connections, _peak_concurrency, _total_requests_served
        request.start_time = time.time()
        with _metrics_lock:
            _active_connections += 1
            if _active_connections > _peak_concurrency:
                _peak_concurrency = _active_connections
            _total_requests_served += 1

    def process_response(self, request, response):
        global _active_connections
        with _metrics_lock:
            _active_connections = max(0, _active_connections - 1)

        if hasattr(request, "start_time"):
            duration_ms = round((time.time() - request.start_time) * 1000, 2)
            response["X-Response-Time"] = f"{duration_ms}ms"
            response["X-Active-Concurrency"] = str(_active_connections)
        return response


class RateLimiterMiddleware(MiddlewareMixin):
    """
    Granular Redis-backed sliding window rate limiter.
    Per-endpoint rules:
    - /auth/login/, /auth/api/login/ -> 5 req/min per IP
    - /ai/tutor/ -> 50 req/day per user
    - /api/ -> 120 req/min per IP
    - Web routes -> 300 req/min per IP
    """
    def process_request(self, request):
        if request.path.startswith("/static/") or request.path.startswith("/api/benchmark/"):
            return None

        ip = get_client_ip(request)
        path = request.path

        if path.startswith("/auth/login") or path.startswith("/auth/api/login"):
            limit = RATE_LIMIT_LOGIN
            window = 60
            key = f"ratelimit:login:{ip}"
        elif "/ai/tutor" in path:
            user_id = getattr(request, "mongo_user", {}).get("id") or ip
            limit = RATE_LIMIT_AI
            window = 86400  # 1 day
            key = f"ratelimit:ai:{user_id}"
        elif path.startswith("/api/"):
            limit = RATE_LIMIT_API
            window = 60
            key = f"ratelimit:api:{ip}"
        else:
            limit = RATE_LIMIT_DEFAULT
            window = 60
            key = f"ratelimit:web:{ip}"

        count = cache_client.incr(key)
        if count == 1:
            cache_client.expire(key, window)

        if count > limit:
            return JsonResponse(
                {
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded ({limit} requests per window). Please wait before retrying.",
                    "status": 429
                },
                status=429
            )
        return None


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Enforces enterprise browser defense standards:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: SAMEORIGIN
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: camera=(), microphone=(), geolocation=()
    - Strict-Transport-Security (HSTS in production)
    - Strict Content Security Policy
    """
    def process_response(self, request, response):
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "SAMEORIGIN"
        response["X-XSS-Protection"] = "1; mode=block"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        if not getattr(settings, "DEBUG", True):
            response["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # Content Security Policy
        csp = (
            "default-src 'self' https: data: 'unsafe-inline' 'unsafe-eval'; "
            "img-src 'self' https: data: blob:; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com;"
        )
        response["Content-Security-Policy"] = csp
        return response


class MongoAuthMiddleware(MiddlewareMixin):
    """
    Resolves authenticated user from either Django Session OR JWT Bearer header / cookie.
    Attaches user object to `request.mongo_user`.
    """
    def process_request(self, request):
        request.mongo_user = None

        # 1. Bearer token in Authorization header
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            user = auth_service.verify_jwt(token)
            if user:
                request.mongo_user = user
                return

        # 2. Access token in HttpOnly cookie
        cookie_token = request.COOKIES.get("learnsphere_access_token")
        if cookie_token:
            user = auth_service.verify_jwt(cookie_token)
            if user:
                request.mongo_user = user
                return

        # 3. Session
        user_id = request.session.get("mongo_user_id")
        if user_id:
            user = auth_service.get_user_by_id(user_id)
            if user and user.get("is_active", True):
                request.mongo_user = user
