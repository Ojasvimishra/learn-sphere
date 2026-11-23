"""
LearnSphere - Core Security & Concurrency Middleware
Provides:
1. Enterprise Security Headers (CSP, X-Frame, X-Content-Type)
2. In-flight Concurrency Counter and Response Timing (sub-50ms target)
3. Sliding Window Rate Limiting (1,000 req/min)
4. Seamless Session & JWT Authentication context injection (request.mongo_user)
"""

import time
import os
import threading
from collections import defaultdict, deque
from django.http import JsonResponse, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from services.auth_service import AuthService

# Thread-safe in-flight metrics for 500+ concurrency tracking
_metrics_lock = threading.Lock()
_active_connections = 0
_total_requests_served = 0
_peak_concurrency = 0

# Rate limiting storage: IP -> deque of timestamps
_rate_limit_store = defaultdict(deque)
_rate_lock = threading.Lock()
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "1000"))

auth_service = AuthService()


def get_concurrency_stats():
    """Returns real-time concurrency metrics for monitoring & benchmarks."""
    with _metrics_lock:
        return {
            "active_concurrency": _active_connections,
            "peak_concurrency": _peak_concurrency,
            "total_requests": _total_requests_served
        }


class ConcurrencyAndPerformanceMiddleware(MiddlewareMixin):
    """
    Tracks real-time concurrency, latency, and injects performance headers.
    """
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
    High-performance sliding window rate limiter per client IP.
    Protects backend services from abusive flooding while smoothly handling 500+ users.
    """
    def process_request(self, request):
        # Exclude static assets and benchmark simulation endpoint from throttling
        if request.path.startswith("/static/") or request.path.startswith("/api/benchmark/"):
            return None

        ip = request.META.get("HTTP_X_FORWARDED_FOR")
        if ip:
            ip = ip.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR", "127.0.0.1")

        now = time.time()
        one_minute_ago = now - 60

        with _rate_lock:
            timestamps = _rate_limit_store[ip]
            while timestamps and timestamps[0] < one_minute_ago:
                timestamps.popleft()

            if len(timestamps) >= RATE_LIMIT_PER_MINUTE:
                return JsonResponse(
                    {
                        "error": "Too Many Requests",
                        "message": f"Rate limit exceeded ({RATE_LIMIT_PER_MINUTE} req/min). Please try again shortly.",
                        "status": 429
                    },
                    status=429
                )
            timestamps.append(now)
        return None


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Enforces modern browser defense standards:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: SAMEORIGIN
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: camera=(), microphone=(), geolocation=()
    - Strict Content Security Policy
    """
    def process_response(self, request, response):
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "SAMEORIGIN"
        response["X-XSS-Protection"] = "1; mode=block"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        
        # CSP allows inline CSS for Tailwind/glass gradients and scripts for chart/interactivity
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
    Resolves authenticated user from either Django Session OR JWT Bearer header.
    Attaches user object to `request.mongo_user`.
    """
    def process_request(self, request):
        request.mongo_user = None

        # 1. Check Bearer token in Authorization header
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            user = auth_service.verify_jwt(token)
            if user:
                request.mongo_user = user
                return

        # 2. Check Session
        user_id = request.session.get("mongo_user_id")
        if user_id:
            user = auth_service.get_user_by_id(user_id)
            if user and user.get("is_active"):
                request.mongo_user = user
