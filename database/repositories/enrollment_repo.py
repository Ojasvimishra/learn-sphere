"""
LearnSphere - Student Enrollment & Course Progress Repository (Tier 3)
Tracks student course enrollments, completed lessons, progress percentages,
and completion timestamps in MongoDB.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from database.repositories.base import BaseRepository


class EnrollmentRepository(BaseRepository):
    def __init__(self):
        super().__init__("enrollments")

    def enroll(self, user_id: str, course_id: str) -> Dict[str, Any]:
        """Creates or returns existing student enrollment."""
        now = datetime.now(timezone.utc)
        clean_user = str(user_id)
        clean_course = str(course_id)

        existing = self.find_one({"user_id": clean_user, "course_id": clean_course})
        if existing:
            return existing

        doc = {
            "user_id": clean_user,
            "course_id": clean_course,
            "progress_percent": 0.0,
            "completed_lessons": [],
            "last_accessed_lesson_id": None,
            "last_accessed_at": now,
            "enrolled_at": now,
            "completed_at": None,
            "certificate_issued": False
        }
        enr_id = self.insert_one(doc)
        return self.find_by_id(enr_id)

    def get_enrollment(self, user_id: str, course_id: str) -> Optional[Dict[str, Any]]:
        return self.find_one({"user_id": str(user_id), "course_id": str(course_id)})

    def list_student_enrollments(self, user_id: str) -> List[Dict[str, Any]]:
        return self.find_many({"user_id": str(user_id)}, sort=[("last_accessed_at", -1)])

    def mark_lesson_complete(
        self,
        user_id: str,
        course_id: str,
        lesson_id: str,
        total_lessons_count: int
    ) -> Dict[str, Any]:
        """
        Records completed lesson, recalculates progress percentage,
        and marks course complete when 100%.
        """
        now = datetime.now(timezone.utc)
        enrollment = self.enroll(user_id, course_id)

        completed = set(enrollment.get("completed_lessons", []))
        completed.add(str(lesson_id))
        completed_list = list(completed)

        total = max(1, total_lessons_count)
        progress = round(min(100.0, (len(completed_list) / total) * 100.0), 1)

        update_data = {
            "completed_lessons": completed_list,
            "progress_percent": progress,
            "last_accessed_lesson_id": str(lesson_id),
            "last_accessed_at": now
        }

        if progress >= 100.0 and not enrollment.get("completed_at"):
            update_data["completed_at"] = now
            update_data["certificate_issued"] = True

        self.update_one(
            {"_id": self.to_object_id(enrollment["id"])},
            update_data
        )
        return self.find_by_id(enrollment["id"])

    def update_last_accessed(self, user_id: str, course_id: str, lesson_id: str):
        now = datetime.now(timezone.utc)
        self.collection.update_one(
            {"user_id": str(user_id), "course_id": str(course_id)},
            {"$set": {"last_accessed_lesson_id": str(lesson_id), "last_accessed_at": now}}
        )

    def list_by_course(self, course_id: str) -> List[Dict[str, Any]]:
        """Returns all student enrollments for a given course."""
        return self.find_many({"course_id": str(course_id)}, sort=[("enrolled_at", -1)])

    def list_by_course_ids(self, course_ids: List[str]) -> List[Dict[str, Any]]:
        """Returns student enrollments across a list of courses."""
        clean_ids = [str(cid) for cid in course_ids]
        return self.find_many({"course_id": {"$in": clean_ids}}, sort=[("last_accessed_at", -1)])

    def get_course_completion_stats(self, course_id: str) -> Dict[str, Any]:
        """Calculates enrollment count, average progress, and completion numbers."""
        enrollments = self.list_by_course(course_id)
        total = len(enrollments)
        if total == 0:
            return {"total_enrolled": 0, "avg_progress": 0.0, "completed_count": 0}

        completed = sum(1 for e in enrollments if e.get("progress_percent", 0) >= 100.0 or e.get("completed_at"))
        avg_progress = round(sum(e.get("progress_percent", 0.0) for e in enrollments) / total, 1)
        return {
            "total_enrolled": total,
            "avg_progress": avg_progress,
            "completed_count": completed
        }
