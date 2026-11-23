"""
LearnSphere - User Repository (Tier 3)
Handles user accounts, authentication data, and RBAC roles in MongoDB.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from django.contrib.auth.hashers import make_password, check_password
from database.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self):
        super().__init__("users")

    def create_user(
        self,
        username: str,
        email: str,
        raw_password: str,
        role: str = "student",
        full_name: str = "",
        bio: str = ""
    ) -> Dict[str, Any]:
        """Creates user with securely hashed password and assigned RBAC role."""
        now = datetime.now(timezone.utc)
        normalized_email = email.strip().lower()
        normalized_username = username.strip().lower()

        user_doc = {
            "username": normalized_username,
            "email": normalized_email,
            "password_hash": make_password(raw_password),
            "role": role if role in ["student", "educator", "admin"] else "student",
            "full_name": full_name.strip() or normalized_username.capitalize(),
            "bio": bio.strip(),
            "is_active": True,
            "enrolled_courses": [],
            "bookmarked_resources": [],
            "created_at": now,
            "updated_at": now,
            "last_login": None
        }

        user_id = self.insert_one(user_doc)
        return self.find_by_id(user_id)

    def find_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        return self.find_one({"email": email.strip().lower()})

    def find_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        return self.find_one({"username": username.strip().lower()})

    def verify_credentials(self, username_or_email: str, raw_password: str) -> Optional[Dict[str, Any]]:
        """Validates credentials against PBKDF2 hash."""
        clean_input = username_or_email.strip().lower()
        user = self.find_one({
            "$or": [
                {"email": clean_input},
                {"username": clean_input}
            ]
        })
        if not user or not user.get("is_active"):
            return None

        if check_password(raw_password, user.get("password_hash", "")):
            # Update last_login
            self.update_one(
                {"_id": self.to_object_id(user["id"])},
                {"$set": {"last_login": datetime.now(timezone.utc)}}
            )
            return user
        return None

    def update_profile(self, user_id: str, full_name: str, bio: str) -> bool:
        oid = self.to_object_id(user_id)
        if not oid:
            return False
        return self.update_one(
            {"_id": oid},
            {
                "full_name": full_name.strip(),
                "bio": bio.strip(),
                "updated_at": datetime.now(timezone.utc)
            }
        )

    def enroll_in_course(self, user_id: str, course_id: str) -> bool:
        oid = self.to_object_id(user_id)
        if not oid:
            return False
        return self.update_one(
            {"_id": oid},
            {"$addToSet": {"enrolled_courses": course_id}}
        )

    def bookmark_resource(self, user_id: str, resource_id: str) -> bool:
        oid = self.to_object_id(user_id)
        if not oid:
            return False
        # Toggle bookmark
        user = self.find_by_id(user_id)
        if not user:
            return False
        bookmarks = user.get("bookmarked_resources", [])
        if resource_id in bookmarks:
            return self.update_one({"_id": oid}, {"$pull": {"bookmarked_resources": resource_id}})
        else:
            return self.update_one({"_id": oid}, {"$addToSet": {"bookmarked_resources": resource_id}})
