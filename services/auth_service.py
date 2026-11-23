"""
LearnSphere - Core Authentication Service (Tier 2)
Provides registration, login, JWT token issuance, session binding,
and role-based authorization verification.
"""

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
import jwt
from database.repositories.user_repo import UserRepository

JWT_SECRET = os.getenv("JWT_SECRET", "learnsphere-jwt-secret-secure-token-938472918347")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))


class AuthService:
    def __init__(self):
        self.user_repo = UserRepository()

    def register(
        self,
        username: str,
        email: str,
        password: str,
        role: str = "student",
        full_name: str = "",
        bio: str = ""
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Validates user input and creates new account."""
        # 1. Validation
        username = (username or "").strip().lower()
        email = (email or "").strip().lower()

        if len(username) < 3 or not re.match(r"^[a-zA-Z0-9_.-]+$", username):
            return False, "Username must be at least 3 characters and contain only letters, numbers, underscores, and dashes.", None

        if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
            return False, "Please provide a valid email address.", None

        if len(password) < 6:
            return False, "Password must be at least 6 characters long.", None

        if role not in ["student", "educator"]:
            role = "student"  # Admin accounts cannot be self-registered

        # 2. Uniqueness check
        if self.user_repo.find_by_email(email):
            return False, "An account with this email already exists.", None

        if self.user_repo.find_by_username(username):
            return False, "This username is already taken.", None

        # 3. Creation
        user = self.user_repo.create_user(
            username=username,
            email=email,
            raw_password=password,
            role=role,
            full_name=full_name,
            bio=bio
        )
        return True, "Registration successful.", user

    def authenticate(
        self,
        username_or_email: str,
        password: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]], Optional[str]]:
        """Verifies credentials and returns user profile + JWT token."""
        user = self.user_repo.verify_credentials(username_or_email, password)
        if not user:
            return False, "Invalid username/email or password.", None, None

        token = self.generate_jwt(user)
        return True, "Authentication successful.", user, token

    def generate_jwt(self, user: Dict[str, Any]) -> str:
        """Issues signed JWT token with user identity and claims."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user["id"]),
            "username": user["username"],
            "email": user["email"],
            "role": user.get("role", "student"),
            "iat": now,
            "exp": now + timedelta(hours=JWT_EXPIRY_HOURS)
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    def verify_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        """Decodes and validates JWT token."""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("sub")
            if not user_id:
                return None
            return self.user_repo.find_by_id(user_id)
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self.user_repo.find_by_id(user_id)

    def toggle_bookmark(self, user_id: str, resource_id: str) -> bool:
        return self.user_repo.bookmark_resource(user_id, resource_id)

    def enroll_course(self, user_id: str, course_id: str) -> bool:
        return self.user_repo.enroll_in_course(user_id, course_id)
