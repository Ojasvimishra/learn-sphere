"""
LearnSphere - Immutable Audit Log Repository (Tier 3)
Guarantees append-only audit persistence for security compliance.
Updates and deletions are strictly disallowed.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from database.repositories.base import BaseRepository


class AuditRepository(BaseRepository):
    def __init__(self):
        super().__init__("audit_logs")

    def insert_log(
        self,
        action: str,
        actor_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        status: str = "success",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """Appends an immutable audit entry."""
        entry = {
            "timestamp": datetime.now(timezone.utc),
            "action": action,
            "actor_id": str(actor_id) if actor_id else "anonymous",
            "actor_email": actor_email or "anonymous",
            "actor_role": actor_role or "guest",
            "resource_type": resource_type or "system",
            "resource_id": str(resource_id) if resource_id else None,
            "status": status,
            "ip_address": ip_address or "127.0.0.1",
            "user_agent": (user_agent or "")[:255],
            "details": details or {}
        }
        return self.insert_one(entry)

    def update_one(self, *args, **kwargs) -> bool:
        """Audit logs are strictly append-only; update is blocked."""
        raise NotImplementedError("Audit logs are strictly immutable and cannot be updated.")

    def delete_one(self, *args, **kwargs) -> bool:
        """Audit logs are strictly append-only; deletion is blocked."""
        raise NotImplementedError("Audit logs are strictly immutable and cannot be deleted.")

    def query_logs(
        self,
        action: Optional[str] = None,
        actor_id: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 25
    ) -> Dict[str, Any]:
        """Queries audit log entries ordered newest first."""
        query = {}
        if action:
            query["action"] = action
        if actor_id:
            query["actor_id"] = str(actor_id)
        if status:
            query["status"] = status

        return self.paginate(
            query=query,
            page=page,
            per_page=per_page,
            sort=[("timestamp", -1)]
        )
