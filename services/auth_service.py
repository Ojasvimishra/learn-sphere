"""
LearnSphere - Core Authentication Service (Tier 2)
Provides registration (public signup locked to student role, educator approval queue),
Argon2id hashing, short-lived access JWT (15m), rotating refresh tokens (7d),
token revocation list, and account lockout protection.
"""

import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
import jwt
from database.repositories.user_repo import UserRepository
from core.rbac import ROLE_STUDENT, ROLE_EDUCATOR, normalize_role
from core.validation import validate_email, validate_username, validate_string, ValidationError
from core.redis_client import get_cache_client
from services.audit_service import AuditService

JWT_SECRET = os.getenv("JWT_SECRET", "learnsphere-jwt-secret-secure-token-938472918347")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_MINUTES = int(os.getenv("JWT_ACCESS_MINUTES", "15"))
JWT_REFRESH_DAYS = int(os.getenv("JWT_REFRESH_DAYS", "7"))


class AuthService:
    def __init__(self):
        self.user_repo = UserRepository()
        self.cache = get_cache_client()
        self.audit = AuditService()

    def register(
        self,
        username: str,
        email: str,
        password: str,
        role: str = ROLE_STUDENT,
        full_name: str = "",
        bio: str = "",
        ip_address: str = "127.0.0.1"
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Public registration.
        CRITICAL SECURITY REQUIREMENT:
        All public registrations are ALWAYS assigned 'student' role.
        Educator signup requests are set to 'educator' with is_approved=False
        requiring admin approval before accessing educator capabilities.
        """
        try:
            clean_username = validate_username(username)
            clean_email = validate_email(email)
            validate_string(password, "password", min_length=8, max_length=128)
        except ValidationError as e:
            return False, e.message, None

        # Check uniqueness
        if self.user_repo.find_by_email(clean_email):
            return False, "An account with this email already exists.", None

        if self.user_repo.find_by_username(clean_username):
            return False, "This username is already taken.", None

        # Enforce role rules:
        requested_role = (role or "").strip().lower()
        if requested_role == ROLE_EDUCATOR:
            assigned_role = ROLE_EDUCATOR
            is_approved = False  # Educator queued for admin review
            msg = "Registration submitted! Your educator application is pending administrator approval."
        else:
            assigned_role = ROLE_STUDENT
            is_approved = True
            msg = "Registration successful."

        user = self.user_repo.create_user(
            username=clean_username,
            email=clean_email,
            raw_password=password,
            role=assigned_role,
            full_name=full_name,
            bio=bio,
            is_approved=is_approved
        )

        self.audit.log_event(
            action="auth.register",
            actor=user,
            resource_type="user",
            resource_id=user["id"],
            status="success",
            ip_address=ip_address,
            details={"role": assigned_role, "is_approved": is_approved}
        )

        return True, msg, user

    def authenticate(
        self,
        username_or_email: str,
        password: str,
        ip_address: str = "127.0.0.1",
        user_agent: str = ""
    ) -> Tuple[bool, str, Optional[Dict[str, Any]], Optional[Dict[str, str]]]:
        """
        Verifies credentials, handles account lockouts, generates access & refresh token pair.
        Returns: (success, message, user_dict, tokens_dict)
        """
        clean_input = (username_or_email or "").strip()
        if not clean_input or not password:
            return False, "Username/email and password are required.", None, None

        status, user, lockout_seconds = self.user_repo.verify_credentials(clean_input, password)

        if status == "locked":
            mins = max(1, (lockout_seconds + 59) // 60)
            self.audit.log_account_lockout(clean_input, ip_address, mins)
            return False, f"Account is temporarily locked due to repeated failed login attempts. Please try again in {mins} minute(s).", None, None

        if status == "inactive":
            return False, "This account has been deactivated. Please contact support.", None, None

        if status != "success" or not user:
            self.audit.log_auth_failure(clean_input, ip_address, "Invalid credentials", user_agent)
            return False, "Invalid username/email or password.", None, None

        # Generate rotating tokens
        tokens = self.generate_tokens(user)
        self.audit.log_auth_success(user, ip_address, user_agent)
        return True, "Authentication successful.", user, tokens

    def generate_tokens(self, user: Dict[str, Any]) -> Dict[str, str]:
        """
        Generates short-lived access token (15m) and rotating refresh token (7d).
        Refresh token ID (jti) is tracked for rotation and revocation.
        """
        now = datetime.now(timezone.utc)
        user_id = str(user.get("id") or user.get("_id"))
        role = normalize_role(user.get("role"))

        # Access Token (15 min) with unique jti
        access_jti = str(uuid.uuid4())
        access_payload = {
            "sub": user_id,
            "jti": access_jti,
            "username": user.get("username", ""),
            "email": user.get("email", ""),
            "role": role,
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=JWT_ACCESS_MINUTES)
        }
        access_token = jwt.encode(access_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        # Refresh Token (7 days) with unique jti
        refresh_jti = str(uuid.uuid4())
        refresh_payload = {
            "sub": user_id,
            "jti": refresh_jti,
            "type": "refresh",
            "iat": now,
            "exp": now + timedelta(days=JWT_REFRESH_DAYS)
        }
        refresh_token = jwt.encode(refresh_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        # Store active refresh token in cache for revocation tracking
        refresh_ttl = JWT_REFRESH_DAYS * 86400
        self.cache.set(f"refresh_token:{refresh_jti}", user_id, ex=refresh_ttl)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": JWT_ACCESS_MINUTES * 60,
            "token_type": "Bearer"
        }

    def refresh_access_token(self, refresh_token_str: str) -> Tuple[bool, str, Optional[Dict[str, str]]]:
        """
        Rotates refresh token: verifies old refresh token, revokes it,
        and generates a brand new access + refresh token pair.
        """
        try:
            payload = jwt.decode(refresh_token_str, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            return False, "Refresh token has expired. Please sign in again.", None
        except jwt.InvalidTokenError:
            return False, "Invalid refresh token.", None

        if payload.get("type") != "refresh":
            return False, "Token is not a refresh token.", None

        jti = payload.get("jti")
        user_id = payload.get("sub")

        # Verify against revocation cache
        cached_user = self.cache.get(f"refresh_token:{jti}")
        if not cached_user:
            return False, "Refresh token has been revoked or expired.", None

        # Revoke old refresh token (Rotation)
        self.cache.delete(f"refresh_token:{jti}")

        # Fetch active user
        user = self.user_repo.find_by_id(user_id)
        if not user or not user.get("is_active", True):
            return False, "User account is no longer active.", None

        new_tokens = self.generate_tokens(user)
        return True, "Token refreshed successfully.", new_tokens

    def revoke_refresh_token(self, refresh_token_str: str) -> bool:
        """Revokes a refresh token on logout."""
        try:
            payload = jwt.decode(refresh_token_str, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            jti = payload.get("jti")
            if jti:
                self.cache.delete(f"refresh_token:{jti}")
                return True
        except Exception:
            pass
        return False

    def verify_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        """Decodes and validates access token."""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            if payload.get("type") not in ["access", None]:  # Allow legacy tokens
                return None
            user_id = payload.get("sub")
            if not user_id:
                return None
            user = self.user_repo.find_by_id(user_id)
            if user and user.get("is_active", True):
                return user
            return None
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self.user_repo.find_by_id(user_id)

    def toggle_bookmark(self, user_id: str, resource_id: str) -> bool:
        return self.user_repo.bookmark_resource(user_id, resource_id)

    def enroll_course(self, user_id: str, course_id: str) -> bool:
        return self.user_repo.enroll_in_course(user_id, course_id)
