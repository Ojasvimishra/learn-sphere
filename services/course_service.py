"""
LearnSphere - Smart Education Courses Service (Tier 2)
Orchestrates educational tracks, lesson progress, and student enrollments.
"""

from typing import Any, Dict, List, Optional
from database.repositories.course_repo import CourseRepository


class CourseService:
    def __init__(self):
        self.repo = CourseRepository()

    def get_courses(self, level: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.repo.list_courses(level)

    def get_course_by_id(self, course_id: str) -> Optional[Dict[str, Any]]:
        return self.repo.find_by_id(course_id)

    def enroll_student(self, course_id: str, student_id: str) -> bool:
        course = self.repo.find_by_id(course_id)
        if not course:
            return False
        self.repo.increment_enrollment(course_id)
        return True
