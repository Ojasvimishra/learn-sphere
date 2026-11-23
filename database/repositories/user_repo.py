"""
LearnSphere - User Repository (Tier 3)
Handles user accounts, authentication data, 5 RBAC roles, and account lockout tracking.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from django.contrib.auth.hashers import make_password, check_password
from database.repositories.base import BaseRepository
from core.rbac import normalize_role, ROLE_STUDENT, ROLE_EDUCATOR, ROLE_SUPER_ADMIN
from core.validation import validate_email, validate_username, validate_string


class UserRepository(BaseRepository):
    def __init__(self):
        super().__init__("users")

    def create_user(
        self,
        username: str,
        email: str,
        raw_password: str,
        role: str = ROLE_STUDENT,
        full_name: str = "",
        bio: str = "",
        is_approved: bool = True
    ) -> Dict[str, Any]:
        """Creates user with modern password hasher (Argon2 / PBKDF2) and RBAC role."""
        now = datetime.now(timezone.utc)
        clean_email = validate_email(email)
        clean_username = validate_username(username)
        normalized_role = normalize_role(role)

        approved_status = is_approved if normalized_role != ROLE_EDUCATOR else is_approved

        user_doc = {
            "username": clean_username,
            "email": clean_email,
            "password_hash": make_password(raw_password),
            "role": normalized_role,
            "full_name": full_name.strip() or clean_username.capitalize(),
            "bio": bio.strip(),
            "is_active": True,
            "is_approved": approved_status,
            "failed_login_attempts": 0,
            "locked_until": None,
            "enrolled_courses": [],
            "bookmarked_resources": [],
            "created_at": now,
            "updated_at": now,
            "last_login": None
        }

        user_id = self.insert_one(user_doc)
        return self.find_by_id(user_id)

    def find_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        if not email or not isinstance(email, str):
            return None
        return self.find_one({"email": email.strip().lower()})

    def find_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        if not username or not isinstance(username, str):
            return None
        return self.find_one({"username": username.strip().lower()})

    def verify_credentials(self, username_or_email: str, raw_password: str) -> Tuple[str, Optional[Dict[str, Any]], int]:
        """
        Validates credentials, checks account lockout, and handles failed attempt counters.
        Returns: (status: str, user_dict_or_none, lockout_remaining_seconds: int)
        Status values: 'success', 'locked', 'invalid_credentials', 'inactive'
        """
        clean_input = (username_or_email or "").strip().lower()
        user = self.find_one({
            "$or": [
                {"email": clean_input},
                {"username": clean_input}
            ]
        })

        if not user:
            return "invalid_credentials", None, 0

        if not user.get("is_active", True):
            return "inactive", None, 0

        now = datetime.now(timezone.utc)
        user_oid = self.to_object_id(user["id"])

        # Check account lockout
        locked_until = user.get("locked_until")
        if locked_until:
            if isinstance(locked_until, str):
                try:
                    locked_until = datetime.fromisoformat(locked_until)
                except Exception:
                    locked_until = None

            if locked_until:
                if locked_until.tzinfo is None:
                    locked_until = locked_until.replace(tzinfo=timezone.utc)

                if locked_until > now:
                    remaining = int((locked_until - now).total_seconds())
                    return "locked", user, remaining
                else:
                    # Lockout period expired; reset lock
                    self.update_one(
                        {"_id": user_oid},
                        {"$set": {"locked_until": None, "failed_login_attempts": 0}}
                    )

        # Verify password
        if check_password(raw_password, user.get("password_hash", "")):
            # Reset failures and update last login
            self.update_one(
                {"_id": user_oid},
                {
                    "$set": {
                        "failed_login_attempts": 0,
                        "locked_until": None,
                        "last_login": now
                    }
                }
            )
            return "success", user, 0
        else:
            # Increment failed attempts
            failed_count = user.get("failed_login_attempts", 0) + 1
            update_fields = {"failed_login_attempts": failed_count}

            # 5 failed attempts locks for 15 minutes (900 seconds)
            if failed_count >= 5:
                lock_duration = timedelta(minutes=15)
                update_fields["locked_until"] = now + lock_duration
                self.update_one({"_id": user_oid}, {"$set": update_fields})
                return "locked", user, 900

            self.update_one({"_id": user_oid}, {"$set": update_fields})
            return "invalid_credentials", None, 0

    def update_role(self, user_id: str, new_role: str) -> bool:
        """Updates user's RBAC role."""
        oid = self.to_object_id(user_id)
        if not oid:
            return False
        normalized = normalize_role(new_role)
        return self.update_one(
            {"_id": oid},
            {"role": normalized, "updated_at": datetime.now(timezone.utc)}
        )

    def approve_educator(self, user_id: str) -> bool:
        """Approves a pending educator account."""
        oid = self.to_object_id(user_id)
        if not oid:
            return False
        return self.update_one(
            {"_id": oid},
            {"is_approved": True, "updated_at": datetime.now(timezone.utc)}
        )

    def list_pending_educators(self) -> List[Dict[str, Any]]:
        """Finds all educator accounts waiting for approval."""
        return self.find_many({"role": ROLE_EDUCATOR, "is_approved": False})

    def reject_educator(self, user_id: str) -> bool:
        """Rejects a pending educator account, reverting to student."""
        oid = self.to_object_id(user_id)
        if not oid:
            return False
        return self.update_one(
            {"_id": oid},
            {"role": ROLE_STUDENT, "is_approved": True, "updated_at": datetime.now(timezone.utc)}
        )

    def list_all_users(
        self,
        role: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Lists users with optional role and username/email search."""
        query = {}
        if role and role != "all":
            query["role"] = normalize_role(role)
        if search:
            query["$or"] = [
                {"username": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
                {"full_name": {"$regex": search, "$options": "i"}}
            ]
        return self.find_many(query, sort=[("created_at", -1)], limit=limit)

    def award_daily_quiz_xp(self, user_id: str, xp_amount: int = 50) -> Tuple[bool, int, int]:
        """
        Awards daily quiz XP once per calendar day.
        Returns (awarded: bool, xp_added: int, total_xp: int)
        """
        oid = self.to_object_id(user_id)
        if not oid:
            return False, 0, 0
        user = self.find_by_id(user_id)
        if not user:
            return False, 0, 0

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if user.get("last_daily_quiz_date") == today_str:
            return False, 0, user.get("xp", 0)

        new_xp = user.get("xp", 0) + xp_amount
        self.update_one(
            {"_id": oid},
            {
                "$set": {
                    "last_daily_quiz_date": today_str,
                    "updated_at": datetime.now(timezone.utc)
                },
                "$inc": {"xp": xp_amount}
            }
        )
        return True, xp_amount, new_xp

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
            {"$addToSet": {"enrolled_courses": str(course_id)}}
        )

    def bookmark_resource(self, user_id: str, resource_id: str) -> bool:
        oid = self.to_object_id(user_id)
        if not oid:
            return False
        user = self.find_by_id(user_id)
        if not user:
            return False
        bookmarks = user.get("bookmarked_resources", [])
        if resource_id in bookmarks:
            return self.update_one({"_id": oid}, {"$pull": {"bookmarked_resources": str(resource_id)}})
        else:
            return self.update_one({"_id": oid}, {"$addToSet": {"bookmarked_resources": str(resource_id)}})
