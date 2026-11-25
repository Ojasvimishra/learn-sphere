"""
LearnSphere - Educator Reports & Admin Updates Repository (Tier 3)
Tracks faculty updates, course submission requests, proctoring escalations,
and academic progress reports delivered to the Administrative Command Center.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from database.repositories.base import BaseRepository


class EducatorReportRepository(BaseRepository):
    def __init__(self):
        super().__init__("educator_reports")

    def create_report(
        self,
        educator_id: str,
        educator_name: str,
        educator_email: str,
        report_type: str,
        title: str,
        message: str,
        course_id: Optional[str] = None,
        course_title: Optional[str] = None,
        exam_id: Optional[str] = None,
        exam_title: Optional[str] = None,
        priority: str = "normal"
    ) -> str:
        now = datetime.now(timezone.utc)
        doc = {
            "educator_id": str(educator_id),
            "educator_name": educator_name.strip(),
            "educator_email": educator_email.strip(),
            "report_type": report_type.strip(),  # course_update, proctor_incident, progress_summary, general_update
            "title": title.strip(),
            "message": message.strip(),
            "course_id": str(course_id) if course_id else None,
            "course_title": str(course_title) if course_title else None,
            "exam_id": str(exam_id) if exam_id else None,
            "exam_title": str(exam_title) if exam_title else None,
            "priority": priority,  # normal, urgent, high
            "status": "pending",  # pending, reviewed, resolved
            "admin_response": None,
            "reviewed_by": None,
            "reviewed_at": None,
            "created_at": now,
            "updated_at": now
        }
        return self.insert_one(doc)

    def list_reports(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        query = {}
        if status and status != "all":
            query["status"] = status
        return self.find_many(query, sort=[("created_at", -1)], limit=limit)

    def list_by_educator(self, educator_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        return self.find_many({"educator_id": str(educator_id)}, sort=[("created_at", -1)], limit=limit)

    def acknowledge_report(self, report_id: str, admin_user: Dict[str, Any], notes: str = "") -> bool:
        oid = self.to_object_id(report_id)
        if not oid:
            return False
        now = datetime.now(timezone.utc)
        admin_name = admin_user.get("full_name") or admin_user.get("username", "Admin")
        return self.update_one(
            {"_id": oid},
            {
                "status": "reviewed",
                "admin_response": notes.strip() if notes else "Acknowledged and reviewed by administration.",
                "reviewed_by": admin_name,
                "reviewed_at": now,
                "updated_at": now
            }
        )
