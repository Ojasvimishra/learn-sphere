"""
LearnSphere - Smart Education Courses Service (Tier 2)
Orchestrates course catalog, syllabus management, video lessons,
and student enrollment progress tracking.
"""

from typing import Any, Dict, List, Optional, Tuple
from database.repositories.course_repo import CourseRepository
from database.repositories.enrollment_repo import EnrollmentRepository
from core.validation import validate_string, ValidationError


class CourseService:
    def __init__(self):
        self.course_repo = CourseRepository()
        self.enrollment_repo = EnrollmentRepository()

    def get_courses(
        self,
        level: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        status: str = "published"
    ) -> List[Dict[str, Any]]:
        return self.course_repo.list_courses(level=level, category=category, status=status, search=search)

    def get_course_by_id(self, course_id: str) -> Optional[Dict[str, Any]]:
        return self.course_repo.find_by_id(course_id)

    def get_instructor_courses(self, instructor_id: str) -> List[Dict[str, Any]]:
        return self.course_repo.list_by_instructor(instructor_id)

    def create_course(self, instructor: Dict[str, Any], data: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        try:
            title = validate_string(data.get("title"), "title", min_length=5, max_length=150)
            tagline = validate_string(data.get("tagline", ""), "tagline", min_length=5, max_length=200)
            desc = validate_string(data.get("description", ""), "description", min_length=20, max_length=3000)
        except ValidationError as e:
            return False, e.message, None

        course_id = self.course_repo.create_course(
            title=title,
            tagline=tagline,
            description=desc,
            level=data.get("level", "Beginner"),
            duration_hours=int(data.get("duration_hours", 10)),
            instructor_name=instructor.get("full_name") or instructor.get("username", "Educator"),
            instructor_id=str(instructor.get("id")),
            category=data.get("category", "Smart Education"),
            modules=data.get("modules", []),
            thumbnail_gradient=data.get("thumbnail_gradient", "linear-gradient(135deg, #1a73e8 0%, #4285f4 100%)"),
            status=data.get("status", "published"),
            price=float(data.get("price", 0.0))
        )
        return True, "Course created successfully.", course_id

    def update_course(self, course_id: str, instructor: Dict[str, Any], data: Dict[str, Any]) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        course = self.course_repo.find_by_id(course_id)
        if not course:
            return False, "Course not found.", None

        is_owner = str(course.get("instructor_id")) == str(instructor.get("id"))
        is_staff = instructor.get("role") in ["educator", "super_admin", "dept_admin"]
        if not (is_owner or is_staff):
            return False, "Permission denied: You do not have educator access to edit courses.", None

        try:
            title = validate_string(data.get("title", course.get("title")), "title", min_length=5, max_length=150)
            tagline = validate_string(data.get("tagline", course.get("tagline", "")), "tagline", min_length=5, max_length=200)
            desc = validate_string(data.get("description", course.get("description", "")), "description", min_length=20, max_length=3000)
        except ValidationError as e:
            return False, e.message, None

        update_fields = {
            "title": title,
            "tagline": tagline,
            "description": desc,
            "level": data.get("level", course.get("level", "Beginner")),
            "duration_hours": int(data.get("duration_hours", course.get("duration_hours", 10))),
            "category": data.get("category", course.get("category", "Smart Education")),
            "price": float(data.get("price", course.get("price", 0.0))),
            "status": data.get("status", course.get("status", "published"))
        }

        if "thumbnail_gradient" in data:
            update_fields["thumbnail_gradient"] = data["thumbnail_gradient"]

        ok = self.course_repo.update_course_details(course_id, update_fields)
        if not ok:
            return False, "Failed to update course details.", None

        if "modules" in data and isinstance(data["modules"], list):
            self.course_repo.update_syllabus(course_id, data["modules"])

        updated_course = self.course_repo.find_by_id(course_id)
        return True, "Course updated successfully.", updated_course

    def enroll_student(self, course_id: str, student_id: str) -> bool:
        course = self.course_repo.find_by_id(course_id)
        if not course:
            return False
        self.enrollment_repo.enroll(student_id, course_id)
        self.course_repo.increment_enrollment(course_id)
        return True

    def get_student_enrollment(self, student_id: str, course_id: str) -> Optional[Dict[str, Any]]:
        return self.enrollment_repo.get_enrollment(student_id, course_id)

    def complete_lesson(self, student_id: str, course_id: str, lesson_id: str) -> Dict[str, Any]:
        course = self.course_repo.find_by_id(course_id)
        total_lessons = course.get("lessons_count", 0) if course else 1
        return self.enrollment_repo.mark_lesson_complete(student_id, course_id, lesson_id, total_lessons)

    def get_lesson_context(
        self,
        course_id: str,
        lesson_id: str,
        user: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Fetches lesson along with course syllabus, completed state,
        prev/next navigation pointers, and verifies access permission.
        """
        course = self.course_repo.find_by_id(course_id)
        if not course:
            return False, "Course not found", None

        # Flatten lessons for navigation
        all_lessons = []
        for mod in course.get("modules", []):
            for les in mod.get("lessons", []):
                les_copy = dict(les)
                les_copy["module_title"] = mod.get("title", "")
                all_lessons.append(les_copy)

        current_lesson = None
        prev_lesson = None
        next_lesson = None

        for idx, les in enumerate(all_lessons):
            if les.get("id") == lesson_id:
                current_lesson = les
                if idx > 0:
                    prev_lesson = all_lessons[idx - 1]
                if idx < len(all_lessons) - 1:
                    next_lesson = all_lessons[idx + 1]
                break

        if not current_lesson:
            return False, "Lesson not found in syllabus", None

        # Verify Access: must be enrolled, instructor, admin, or free preview
        is_enrolled = False
        completed_lessons = set()
        progress_percent = 0.0

        if user:
            user_id = str(user.get("id"))
            role = user.get("role", "student")
            enrollment = self.enrollment_repo.get_enrollment(user_id, course_id)
            if enrollment:
                is_enrolled = True
                completed_lessons = set(enrollment.get("completed_lessons", []))
                progress_percent = enrollment.get("progress_percent", 0.0)

            is_staff = role in ["educator", "super_admin", "dept_admin"] or str(course.get("instructor_id")) == user_id
            if is_staff:
                is_enrolled = True

        if not is_enrolled and not current_lesson.get("is_free_preview", False):
            return False, "This lesson requires enrollment in the course track.", None

        return True, "Success", {
            "course": course,
            "lesson": current_lesson,
            "all_lessons": all_lessons,
            "prev_lesson": prev_lesson,
            "next_lesson": next_lesson,
            "is_enrolled": is_enrolled,
            "completed_lessons": list(completed_lessons),
            "progress_percent": progress_percent
        }
