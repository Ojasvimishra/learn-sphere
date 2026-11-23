"""
LearnSphere - Smart Education Courses & Tracks Repository (Tier 3)
Manages educational modules, syllabus, interactive lessons, video streams,
and course publication workflows (draft, pending_approval, published).
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from database.repositories.base import BaseRepository
from core.validation import validate_string, validate_payload_types


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
        category: str = "Smart Education",
        modules: Optional[List[Dict[str, Any]]] = None,
        thumbnail_gradient: str = "linear-gradient(135deg, #1a73e8 0%, #4285f4 100%)",
        badge: str = "Core Track",
        status: str = "published",
        price: float = 0.0
    ) -> str:
        now = datetime.now(timezone.utc)
        normalized_modules = modules or []

        # Count total lessons across all modules
        total_lessons = sum(len(m.get("lessons", [])) for m in normalized_modules)
        if total_lessons == 0 and normalized_modules:
            # Handle legacy module format where each module was a lesson
            total_lessons = len(normalized_modules)

        doc = {
            "title": title.strip(),
            "tagline": tagline.strip(),
            "description": description.strip(),
            "category": category.strip(),
            "level": level.capitalize() if level in ["Beginner", "Intermediate", "Advanced"] else "Beginner",
            "duration_hours": duration_hours,
            "instructor_name": instructor_name.strip(),
            "instructor_id": str(instructor_id),
            "status": status,  # draft, pending_approval, published, archived
            "modules": normalized_modules,
            "modules_count": len(normalized_modules),
            "lessons_count": total_lessons,
            "enrolled_count": 0,
            "rating": 4.95,
            "price": price,
            "thumbnail_gradient": thumbnail_gradient,
            "badge": badge,
            "created_at": now,
            "updated_at": now
        }
        return self.insert_one(doc)

    def list_courses(
        self,
        level: Optional[str] = None,
        category: Optional[str] = None,
        status: str = "published",
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = {}
        if status and status != "all":
            query["status"] = status
        if level and level != "all":
            query["level"] = level.capitalize()
        if category and category != "all":
            query["category"] = category
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"tagline": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}}
            ]
        return self.find_many(query, sort=[("rating", -1), ("enrolled_count", -1)], limit=50)

    def list_by_instructor(self, instructor_id: str) -> List[Dict[str, Any]]:
        return self.find_many({"instructor_id": str(instructor_id)}, sort=[("updated_at", -1)])

    def approve_course(self, course_id: str) -> bool:
        """Approves a course and transitions status to published."""
        oid = self.to_object_id(course_id)
        if not oid:
            return False
        return self.update_one(
            {"_id": oid},
            {"status": "published", "updated_at": datetime.now(timezone.utc)}
        )

    def update_course_details(self, course_id: str, update_data: Dict[str, Any]) -> bool:
        oid = self.to_object_id(course_id)
        if not oid:
            return False
        update_data["updated_at"] = datetime.now(timezone.utc)
        return self.update_one({"_id": oid}, update_data)

    def update_syllabus(self, course_id: str, modules: List[Dict[str, Any]]) -> bool:
        oid = self.to_object_id(course_id)
        if not oid:
            return False
        total_lessons = sum(len(m.get("lessons", [])) for m in modules)
        return self.update_one(
            {"_id": oid},
            {
                "modules": modules,
                "modules_count": len(modules),
                "lessons_count": total_lessons,
                "updated_at": datetime.now(timezone.utc)
            }
        )

    def add_module(self, course_id: str, title: str, description: str = "") -> Optional[str]:
        course = self.find_by_id(course_id)
        if not course:
            return None
        modules = course.get("modules", [])
        module_id = f"mod_{len(modules) + 1}_{uuid.uuid4().hex[:6]}"
        new_module = {
            "id": module_id,
            "title": title.strip(),
            "description": description.strip(),
            "order": len(modules) + 1,
            "lessons": []
        }
        modules.append(new_module)
        self.update_syllabus(course_id, modules)
        return module_id

    def add_lesson(
        self,
        course_id: str,
        module_id: str,
        title: str,
        lesson_type: str = "video",
        duration_minutes: int = 20,
        video_url: str = "",
        content_markdown: str = "",
        is_free_preview: bool = False
    ) -> Optional[str]:
        course = self.find_by_id(course_id)
        if not course:
            return None

        modules = course.get("modules", [])
        target_mod = None
        for m in modules:
            if m.get("id") == module_id or str(m.get("order")) == str(module_id):
                target_mod = m
                break

        if not target_mod:
            # If no module matched, append to first or create default module
            if not modules:
                modules.append({"id": "mod_1", "title": "Module 1: Foundations", "order": 1, "lessons": []})
            target_mod = modules[0]

        lessons = target_mod.get("lessons", [])
        lesson_id = f"les_{len(lessons) + 1}_{uuid.uuid4().hex[:6]}"
        new_lesson = {
            "id": lesson_id,
            "title": title.strip(),
            "type": lesson_type if lesson_type in ["video", "reading", "quiz", "lab"] else "video",
            "duration_minutes": duration_minutes,
            "duration": f"{duration_minutes}m",
            "video_url": video_url.strip(),
            "content_markdown": content_markdown.strip(),
            "is_free_preview": is_free_preview,
            "status": "unlocked" if is_free_preview else "locked",
            "order": len(lessons) + 1
        }
        lessons.append(new_lesson)
        target_mod["lessons"] = lessons
        self.update_syllabus(course_id, modules)
        return lesson_id

    def find_lesson(self, course: Dict[str, Any], lesson_id: str) -> Optional[Dict[str, Any]]:
        """Locates specific lesson and returns lesson details with parent module title."""
        for mod in course.get("modules", []):
            for les in mod.get("lessons", []):
                if les.get("id") == lesson_id:
                    res = dict(les)
                    res["module_title"] = mod.get("title", "")
                    res["module_id"] = mod.get("id", "")
                    return res
        return None

    def increment_enrollment(self, course_id: str):
        oid = self.to_object_id(course_id)
        if oid:
            self.collection.update_one({"_id": oid}, {"$inc": {"enrolled_count": 1}})
