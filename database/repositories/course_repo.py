"""
LearnSphere - Smart Education Courses & Tracks Repository (Tier 3)
Manages educational modules, syllabus, interactive lessons, and enrollments.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from database.repositories.base import BaseRepository


class CourseRepository(BaseRepository):
    def __init__(self):
        super().__init__("courses")

    def create_course(
        self,
        title: str,
        tagline: str,
        description: str,
        level: str,
        duration_hours: int,
        instructor_name: str,
        instructor_id: str,
        modules: List[Dict[str, Any]],
        thumbnail_gradient: str = "from-indigo-600 to-purple-600",
        badge: str = "Popular"
    ) -> str:
        now = datetime.now(timezone.utc)
        doc = {
            "title": title.strip(),
            "tagline": tagline.strip(),
            "description": description.strip(),
            "level": level.capitalize() if level in ["Beginner", "Intermediate", "Advanced"] else "Beginner",
            "duration_hours": duration_hours,
            "instructor_name": instructor_name.strip(),
            "instructor_id": instructor_id,
            "modules": modules,
            "modules_count": len(modules),
            "enrolled_count": 0,
            "rating": 4.9,
            "thumbnail_gradient": thumbnail_gradient,
            "badge": badge,
            "created_at": now,
            "updated_at": now
        }
        return self.insert_one(doc)

    def list_courses(self, level: Optional[str] = None) -> List[Dict[str, Any]]:
        query = {}
        if level and level != "all":
            query["level"] = level.capitalize()
        return self.find_many(query, sort=[("rating", -1), ("enrolled_count", -1)], limit=20)

    def increment_enrollment(self, course_id: str):
        oid = self.to_object_id(course_id)
        if oid:
            self.collection.update_one({"_id": oid}, {"$inc": {"enrolled_count": 1}})
