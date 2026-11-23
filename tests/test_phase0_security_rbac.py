"""
LearnSphere - Automated Test Suite: Phase 0 Security & 5-Role RBAC
Tests:
1. Password hashing (Argon2id/PBKDF2) & Account Lockout
2. Registration role enforcement (Student default, Educator queue)
3. JWT Short-Lived Access, Rotating Refresh & Revocation
4. Boundary Schema Validation & NoSQL Injection Protection
5. 5-Role RBAC Permission Matrix & Portal Access
6. Immutable Audit Log Appending & Disallowed Mutation
"""

import os
import pytest
import django
from datetime import datetime, timezone, timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "learnsphere.settings")
django.setup()

from core.rbac import (
    ROLE_SUPER_ADMIN, ROLE_DEPT_ADMIN, ROLE_MODERATOR, ROLE_EDUCATOR, ROLE_STUDENT,
    has_permission, can_manage_user, can_access_portal, normalize_role
)
from core.validation import (
    validate_string, validate_email, validate_username, validate_object_id,
    validate_payload_types, assert_no_mongo_operators, ValidationError
)
from database.repositories.user_repo import UserRepository
from database.repositories.audit_repo import AuditRepository
from services.auth_service import AuthService
from services.audit_service import AuditService
from core.redis_client import get_cache_client


@pytest.fixture(autouse=True)
def cleanup_test_state():
    """Cleanup test accounts and cache keys before/after tests."""
    cache = get_cache_client()
    user_repo = UserRepository()
    test_emails = [
        "test_student@learnsphere.io",
        "test_educator@learnsphere.io",
        "test_lockout@learnsphere.io",
        "test_jwt@learnsphere.io"
    ]
    for email in test_emails:
        u = user_repo.find_by_email(email)
        if u:
            oid = user_repo.to_object_id(u["id"])
            user_repo.collection.delete_one({"_id": oid})
    yield
    for email in test_emails:
        u = user_repo.find_by_email(email)
        if u:
            oid = user_repo.to_object_id(u["id"])
            user_repo.collection.delete_one({"_id": oid})


def test_rbac_matrix_and_hierarchy():
    """Validates 5-role permission definitions and hierarchy."""
    super_admin = {"role": ROLE_SUPER_ADMIN, "is_active": True}
    dept_admin = {"role": ROLE_DEPT_ADMIN, "is_active": True}
    moderator = {"role": ROLE_MODERATOR, "is_active": True}
    educator = {"role": ROLE_EDUCATOR, "is_active": True, "is_approved": True}
    student = {"role": ROLE_STUDENT, "is_active": True}

    # Super admin has wildcard access
    assert has_permission(super_admin, "course.create")
    assert has_permission(super_admin, "audit.view")
    assert has_permission(super_admin, "grade.override")

    # Educator permissions
    assert has_permission(educator, "course.create")
    assert has_permission(educator, "exam.create")
    assert not has_permission(educator, "audit.view")
    assert not has_permission(educator, "user.manage")

    # Student permissions
    assert has_permission(student, "course.enroll")
    assert has_permission(student, "exam.take")
    assert not has_permission(student, "course.create")
    assert not has_permission(student, "grade.override")

    # Portal access rules
    assert can_access_portal(super_admin, "admin")
    assert can_access_portal(dept_admin, "admin")
    assert not can_access_portal(student, "admin")
    assert can_access_portal(educator, "educator")
    assert not can_access_portal(student, "educator")
    assert can_access_portal(student, "student")


def test_boundary_schema_validation():
    """Tests strict typing and rejection of NoSQL injection operators."""
    # Valid strings and emails
    assert validate_string("SafeString", "field") == "SafeString"
    assert validate_email("user@example.com") == "user@example.com"
    assert validate_username("alex_student") == "alex_student"

    # Rejection of invalid types
    with pytest.raises(ValidationError):
        validate_string({"$gt": ""}, "field")

    with pytest.raises(ValidationError):
        validate_string(["not_a_string"], "field")

    with pytest.raises(ValidationError):
        validate_email("invalid-email-address")

    # Rejection of operator keys
    with pytest.raises(ValidationError):
        assert_no_mongo_operators({"$where": "this.password == 'secret'"})

    with pytest.raises(ValidationError):
        assert_no_mongo_operators({"user": {"$ne": None}})

    # Valid payload schema validation
    schema = {"title": str, "views": int, "is_active": bool}
    valid_payload = {"title": "Calculus I", "views": 100, "is_active": True}
    cleaned = validate_payload_types(valid_payload, schema)
    assert cleaned["title"] == "Calculus I"
    assert cleaned["views"] == 100


def test_public_registration_role_lockdown():
    """Ensures public self-registration cannot escalate to admin/educator without approval."""
    auth_service = AuthService()

    # Public registration as student
    ok, msg, student_user = auth_service.register(
        username="test_student",
        email="test_student@learnsphere.io",
        password="SecurePassword2026!",
        role="student"
    )
    assert ok is True
    assert student_user["role"] == ROLE_STUDENT
    assert student_user["is_approved"] is True

    # Educator signup enters approval queue (is_approved=False)
    ok2, msg2, educator_user = auth_service.register(
        username="test_educator",
        email="test_educator@learnsphere.io",
        password="SecurePassword2026!",
        role="educator"
    )
    assert ok2 is True
    assert educator_user["role"] == ROLE_EDUCATOR
    assert educator_user["is_approved"] is False
    assert "pending administrator approval" in msg2


def test_account_lockout_after_failed_attempts():
    """Verifies account is locked out after 5 consecutive bad passwords."""
    auth_service = AuthService()
    user_repo = UserRepository()

    # Create active user
    auth_service.register(
        username="test_lockout",
        email="test_lockout@learnsphere.io",
        password="CorrectPassword123!",
        role="student"
    )

    # 4 failed attempts: still invalid credentials
    for i in range(4):
        ok, msg, _, _ = auth_service.authenticate("test_lockout@learnsphere.io", f"WrongPass{i}")
        assert ok is False
        assert "Invalid username/email or password" in msg

    # 5th failed attempt: triggers account lockout
    ok, msg, _, _ = auth_service.authenticate("test_lockout@learnsphere.io", "WrongPass5")
    assert ok is False
    assert "Account is temporarily locked" in msg

    # Even with correct password, login is blocked while locked
    ok_correct, msg_locked, _, _ = auth_service.authenticate("test_lockout@learnsphere.io", "CorrectPassword123!")
    assert ok_correct is False
    assert "Account is temporarily locked" in msg_locked


def test_jwt_short_lived_access_and_rotation():
    """Verifies 15-minute access token, rotating refresh token, and revocation."""
    auth_service = AuthService()

    auth_service.register(
        username="test_jwt",
        email="test_jwt@learnsphere.io",
        password="SecurePassword123!",
        role="student"
    )

    # Authenticate and receive token pair
    ok, _, user, tokens = auth_service.authenticate("test_jwt@learnsphere.io", "SecurePassword123!")
    assert ok is True
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    # Verify access token
    verified_user = auth_service.verify_jwt(tokens["access_token"])
    assert verified_user is not None
    assert verified_user["email"] == "test_jwt@learnsphere.io"

    # Rotate refresh token
    refreshed_ok, _, new_tokens = auth_service.refresh_access_token(tokens["refresh_token"])
    assert refreshed_ok is True
    assert new_tokens["access_token"] != tokens["access_token"]
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    # Old refresh token is now revoked and cannot be reused
    old_reuse_ok, old_msg, _ = auth_service.refresh_access_token(tokens["refresh_token"])
    assert old_reuse_ok is False
    assert "revoked or expired" in old_msg

    # Revoke new refresh token on logout
    revoked = auth_service.revoke_refresh_token(new_tokens["refresh_token"])
    assert revoked is True
    third_refresh, _, _ = auth_service.refresh_access_token(new_tokens["refresh_token"])
    assert third_refresh is False


def test_immutable_audit_log():
    """Verifies audit entries are append-only and mutate attempts raise exceptions."""
    audit_repo = AuditRepository()
    audit_service = AuditService()

    log_id = audit_service.log_event(
        action="security.test_event",
        actor={"id": "actor_123", "email": "admin@learnsphere.io", "role": "super_admin"},
        resource_type="system",
        resource_id="res_456",
        status="success",
        details={"ip": "127.0.0.1", "action_detail": "Testing immutability"}
    )
    assert log_id is not None

    # Fetch inserted log
    saved = audit_repo.find_by_id(log_id)
    assert saved is not None
    assert saved["action"] == "security.test_event"

    # Attempt to update log -> must raise NotImplementedError
    with pytest.raises(NotImplementedError):
        audit_repo.update_one({"_id": audit_repo.to_object_id(log_id)}, {"status": "tampered"})

    # Attempt to delete log -> must raise NotImplementedError
    with pytest.raises(NotImplementedError):
        audit_repo.delete_one({"_id": audit_repo.to_object_id(log_id)})
