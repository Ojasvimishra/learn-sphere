"""
LearnSphere - 5-Role Role-Based Access Control (RBAC) System
Defines system roles, granular code permissions, and role hierarchy.
"""

from typing import Any, Dict, List, Set, Optional

# The 5 Core System Roles
ROLE_SUPER_ADMIN = "super_admin"
ROLE_DEPT_ADMIN = "dept_admin"
ROLE_MODERATOR = "moderator"
ROLE_EDUCATOR = "educator"
ROLE_STUDENT = "student"

ALL_ROLES = [
    ROLE_SUPER_ADMIN,
    ROLE_DEPT_ADMIN,
    ROLE_MODERATOR,
    ROLE_EDUCATOR,
    ROLE_STUDENT
]

# Granular Code Permissions
ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    ROLE_SUPER_ADMIN: {
        # Super admin has unrestricted access
        "*"
    },
    ROLE_DEPT_ADMIN: {
        "course.view", "course.create", "course.edit", "course.publish", "course.approve",
        "exam.view", "exam.create", "exam.proctor", "grade.view", "grade.override",
        "live.view", "live.host",
        "lab.view", "lab.create", "lab.execute",
        "doubt.view", "doubt.answer",
        "innovation.view", "innovation.review", "innovation.endorse",
        "user.view", "user.manage", "user.bulk_import",
        "report.export", "audit.view"
    },
    ROLE_MODERATOR: {
        "course.view",
        "innovation.view", "innovation.review", "innovation.comment_moderate",
        "doubt.view", "doubt.moderate",
        "user.view", "report.export"
    },
    ROLE_EDUCATOR: {
        "course.view", "course.create", "course.edit", "course.publish",
        "exam.view", "exam.create", "exam.proctor", "grade.view", "grade.override",
        "live.view", "live.host",
        "lab.view", "lab.create", "lab.execute",
        "doubt.view", "doubt.answer",
        "innovation.view", "innovation.endorse"
    },
    ROLE_STUDENT: {
        "course.view", "course.enroll", "course.stream",
        "exam.view", "exam.take", "grade.view_own",
        "live.view", "live.join",
        "lab.view", "lab.execute",
        "doubt.view", "doubt.ask",
        "innovation.view", "innovation.submit", "innovation.upvote"
    }
}


def normalize_role(role: Optional[str]) -> str:
    """Normalizes legacy 'admin' to 'super_admin' and validates role."""
    if not role:
        return ROLE_STUDENT
    role = role.strip().lower()
    if role == "admin":
        return ROLE_SUPER_ADMIN
    if role in ALL_ROLES:
        return role
    return ROLE_STUDENT


def get_user_permissions(role: str) -> Set[str]:
    """Returns permission code set for a given role."""
    norm = normalize_role(role)
    return ROLE_PERMISSIONS.get(norm, set())


def has_permission(user: Optional[Dict[str, Any]], permission_code: str) -> bool:
    """Checks whether the user possesses the required permission code."""
    if not user or not user.get("is_active", True):
        return False

    role = normalize_role(user.get("role"))
    perms = get_user_permissions(role)

    if "*" in perms:
        return True

    return permission_code in perms


def can_manage_user(acting_user: Dict[str, Any], target_user: Dict[str, Any]) -> bool:
    """Enforces hierarchical user management rules."""
    acting_role = normalize_role(acting_user.get("role"))
    target_role = normalize_role(target_user.get("role"))

    if acting_role == ROLE_SUPER_ADMIN:
        return True

    if acting_role == ROLE_DEPT_ADMIN:
        return target_role in [ROLE_EDUCATOR, ROLE_STUDENT, ROLE_MODERATOR]

    return False


def can_access_portal(user: Optional[Dict[str, Any]], portal: str) -> bool:
    """
    Validates portal access:
    - /admin-panel/ -> super_admin, dept_admin, moderator
    - /educator/ -> super_admin, dept_admin, educator (must be approved)
    - /student/ -> any active authenticated user
    """
    if not user:
        return False

    role = normalize_role(user.get("role"))

    if portal == "admin":
        return role in [ROLE_SUPER_ADMIN, ROLE_DEPT_ADMIN, ROLE_MODERATOR]

    if portal == "educator":
        if role in [ROLE_SUPER_ADMIN, ROLE_DEPT_ADMIN]:
            return True
        if role == ROLE_EDUCATOR:
            return bool(user.get("is_approved", True))
        return False

    if portal == "student":
        return True

    return False
