"""
LearnSphere - Core Audit Service (Tier 2)
Provides structured audit logging for security events, authentication,
administrative role changes, proctored exam actions, and grade overrides.
"""

from typing import Any, Dict, Optional
from database.repositories.audit_repo import AuditRepository

audit_repo = AuditRepository()


class AuditService:
    def __init__(self):
        self.repo = audit_repo

    def log_event(
        self,
        action: str,
        actor: Optional[Dict[str, Any]] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        status: str = "success",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Any] = None
    ) -> str:
        if request:
            from core.middleware import get_client_ip
            if not ip_address:
                ip_address = get_client_ip(request)
            if not user_agent:
                user_agent = request.META.get("HTTP_USER_AGENT", "")

        actor_id = actor.get("id") or actor.get("_id") if actor else None
        actor_email = actor.get("email") if actor else None
        actor_role = actor.get("role") if actor else None

        return self.repo.insert_log(
            action=action,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_role=actor_role,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details
        )

    def log_auth_success(self, user: Dict[str, Any], ip_address: str, user_agent: str = ""):
        self.log_event(
            action="auth.login.success",
            actor=user,
            resource_type="user",
            resource_id=user.get("id"),
            status="success",
            ip_address=ip_address,
            user_agent=user_agent
        )

    def log_auth_failure(self, identifier: str, ip_address: str, reason: str, user_agent: str = ""):
        self.log_event(
            action="auth.login.failure",
            actor=None,
            resource_type="auth",
            resource_id=identifier,
            status="failure",
            ip_address=ip_address,
            user_agent=user_agent,
            details={"identifier": identifier, "reason": reason}
        )

    def log_account_lockout(self, identifier: str, ip_address: str, lockout_duration_min: int = 15):
        self.log_event(
            action="auth.account_locked",
            actor=None,
            resource_type="auth",
            resource_id=identifier,
            status="warning",
            ip_address=ip_address,
            details={"identifier": identifier, "lockout_minutes": lockout_duration_min}
        )

    def log_role_change(self, acting_admin: Dict[str, Any], target_user_id: str, old_role: str, new_role: str, ip_address: str):
        self.log_event(
            action="user.role_change",
            actor=acting_admin,
            resource_type="user",
            resource_id=target_user_id,
            status="success",
            ip_address=ip_address,
            details={"old_role": old_role, "new_role": new_role}
        )

    def log_grade_override(self, acting_educator: Dict[str, Any], student_id: str, exam_id: str, old_grade: Any, new_grade: Any, reason: str):
        self.log_event(
            action="grade.override",
            actor=acting_educator,
            resource_type="exam_attempt",
            resource_id=f"{student_id}:{exam_id}",
            status="success",
            details={
                "student_id": student_id,
                "exam_id": exam_id,
                "old_grade": old_grade,
                "new_grade": new_grade,
                "reason": reason
            }
        )

    def query_audit_logs(self, action=None, actor_id=None, status=None, page=1, per_page=25):
        return self.repo.query_logs(action=action, actor_id=actor_id, status=status, page=page, per_page=per_page)
