"""
LearnSphere - Management Command: bootstrap_admin
Creates or updates a super_admin user without publishing plaintext passwords in code or migrations.
Reads from environment variables (BOOTSTRAP_ADMIN_EMAIL, BOOTSTRAP_ADMIN_PASSWORD)
or CLI flags (--email, --password).
"""

import os
import secrets
import string
from django.core.management.base import BaseCommand
from database.repositories.user_repo import UserRepository
from core.rbac import ROLE_SUPER_ADMIN
from django.contrib.auth.hashers import make_password
from datetime import datetime, timezone


class Command(BaseCommand):
    help = "Bootstrap a super_admin user safely from environment or command-line flags."

    def add_arguments(self, parser):
        parser.add_argument("--email", type=str, default=None, help="Administrator email address")
        parser.add_argument("--username", type=str, default="admin", help="Administrator username")
        parser.add_argument("--password", type=str, default=None, help="Administrator raw password")

    def handle(self, *args, **options):
        email = options["email"] or os.getenv("BOOTSTRAP_ADMIN_EMAIL") or "admin@learnsphere.io"
        username = options["username"] or "admin"
        password = options["password"] or os.getenv("BOOTSTRAP_ADMIN_PASSWORD")

        generated = False
        if not password:
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            password = "".join(secrets.choice(alphabet) for _ in range(18))
            generated = True

        user_repo = UserRepository()
        existing = user_repo.find_by_email(email)

        now = datetime.now(timezone.utc)
        if existing:
            user_repo.update_one(
                {"_id": user_repo.to_object_id(existing["id"])},
                {
                    "password_hash": make_password(password),
                    "role": ROLE_SUPER_ADMIN,
                    "is_active": True,
                    "is_approved": True,
                    "failed_login_attempts": 0,
                    "locked_until": None,
                    "updated_at": now
                }
            )
            self.stdout.write(self.style.SUCCESS(f"Updated existing user '{email}' to super_admin."))
        else:
            user_doc = {
                "username": username,
                "email": email.strip().lower(),
                "password_hash": make_password(password),
                "role": ROLE_SUPER_ADMIN,
                "full_name": "LearnSphere Super Administrator",
                "bio": "Platform Lead Administrator.",
                "is_active": True,
                "is_approved": True,
                "failed_login_attempts": 0,
                "locked_until": None,
                "enrolled_courses": [],
                "bookmarked_resources": [],
                "created_at": now,
                "updated_at": now,
                "last_login": None
            }
            user_repo.insert_one(user_doc)
            self.stdout.write(self.style.SUCCESS(f"Created new super_admin account: {email}"))

        if generated:
            self.stdout.write(self.style.WARNING("=================================================="))
            self.stdout.write(self.style.WARNING("NOTICE: Super Admin password was auto-generated."))
            self.stdout.write(self.style.WARNING(f"Email:    {email}"))
            self.stdout.write(self.style.WARNING(f"Password: {password}"))
            self.stdout.write(self.style.WARNING("Store this credential securely. It will not be shown again."))
            self.stdout.write(self.style.WARNING("=================================================="))
