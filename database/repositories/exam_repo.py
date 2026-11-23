"""
LearnSphere - Proctored Exams & Quizzes Repository (Tier 3)
Manages question banks, timed exams, student attempts, proctor anti-cheat logs,
and server-side grade records.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from database.repositories.base import BaseRepository


class ExamRepository(BaseRepository):
    def __init__(self):
        super().__init__("exams")

    def create_exam(
        self,
        title: str,
        course_id: str,
        course_title: str,
        instructor_id: str,
        instructor_name: str,
        duration_minutes: int,
        questions: List[Dict[str, Any]],
        total_marks: int = 100,
        passing_marks: int = 60,
        is_proctored: bool = True,
        tab_switch_limit: int = 3,
        description: str = ""
    ) -> str:
        now = datetime.now(timezone.utc)
        # Ensure questions have unique IDs
        normalized_q = []
        for idx, q in enumerate(questions):
            q_copy = dict(q)
            if "id" not in q_copy:
                q_copy["id"] = f"q_{idx + 1}_{uuid.uuid4().hex[:6]}"
            normalized_q.append(q_copy)

        doc = {
            "title": title.strip(),
            "course_id": str(course_id),
            "course_title": course_title.strip(),
            "instructor_id": str(instructor_id),
            "instructor_name": instructor_name.strip(),
            "description": description.strip(),
            "duration_minutes": duration_minutes,
            "total_marks": total_marks,
            "passing_marks": passing_marks,
            "is_proctored": is_proctored,
            "tab_switch_limit": tab_switch_limit,
            "questions": normalized_q,
            "questions_count": len(normalized_q),
            "status": "published",  # draft, published, closed
            "created_at": now,
            "updated_at": now
        }
        return self.insert_one(doc)

    def list_by_course(self, course_id: str) -> List[Dict[str, Any]]:
        return self.find_many({"course_id": str(course_id)}, sort=[("created_at", -1)])

    def list_available_exams(self) -> List[Dict[str, Any]]:
        return self.find_many({"status": "published"}, sort=[("created_at", -1)], limit=30)


class ExamAttemptRepository(BaseRepository):
    def __init__(self):
        super().__init__("exam_attempts")

    def start_attempt(self, exam: Dict[str, Any], student: Dict[str, Any]) -> Dict[str, Any]:
        """Creates or returns in-progress attempt for student."""
        student_id = str(student.get("id"))
        exam_id = str(exam.get("id"))

        existing = self.find_one({
            "exam_id": exam_id,
            "student_id": student_id,
            "status": "in_progress"
        })
        if existing:
            return existing

        now = datetime.now(timezone.utc)
        duration = int(exam.get("duration_minutes", 60))
        doc = {
            "exam_id": exam_id,
            "exam_title": exam.get("title", ""),
            "course_id": exam.get("course_id", ""),
            "student_id": student_id,
            "student_name": student.get("full_name") or student.get("username", "Student"),
            "student_email": student.get("email", ""),
            "started_at": now,
            "expires_at": now + timedelta(minutes=duration),
            "submitted_at": None,
            "status": "in_progress",  # in_progress, submitted, flagged_for_review, graded
            "answers": {},
            "score": 0,
            "total_marks": exam.get("total_marks", 100),
            "percentage": 0.0,
            "passed": False,
            "proctor_events": [],
            "tab_switches_count": 0,
            "is_flagged": False,
            "grade_overridden": False,
            "created_at": now
        }
        att_id = self.insert_one(doc)
        return self.find_by_id(att_id)

    def log_proctor_event(self, attempt_id: str, event_type: str, details: Dict[str, Any]) -> bool:
        oid = self.to_object_id(attempt_id)
        if not oid:
            return False

        now = datetime.now(timezone.utc)
        event = {
            "event": event_type,
            "timestamp": now.isoformat(),
            "details": details
        }

        update_ops = {
            "$push": {"proctor_events": event}
        }
        if event_type in ["tab_hidden", "window_blur"]:
            update_ops["$inc"] = {"tab_switches_count": 1}

        self.collection.update_one({"_id": oid}, update_ops)
        return True

    def submit_and_grade(
        self,
        attempt_id: str,
        answers: Dict[str, Any],
        score: int,
        total_marks: int,
        passed: bool,
        is_flagged: bool
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        oid = self.to_object_id(attempt_id)
        pct = round((score / max(1, total_marks)) * 100.0, 1)

        status = "flagged_for_review" if is_flagged else "graded"

        update_data = {
            "answers": answers,
            "score": score,
            "percentage": pct,
            "passed": passed,
            "is_flagged": is_flagged,
            "status": status,
            "submitted_at": now
        }
        self.update_one({"_id": oid}, update_data)
        return self.find_by_id(attempt_id)

    def override_grade(self, attempt_id: str, new_score: int, total_marks: int, reason: str, educator_name: str) -> bool:
        oid = self.to_object_id(attempt_id)
        if not oid:
            return False

        now = datetime.now(timezone.utc)
        pct = round((new_score / max(1, total_marks)) * 100.0, 1)
        passed = pct >= 60.0

        return self.update_one(
            {"_id": oid},
            {
                "score": new_score,
                "percentage": pct,
                "passed": passed,
                "grade_overridden": True,
                "override_reason": reason.strip(),
                "overridden_by": educator_name,
                "overridden_at": now,
                "status": "graded"
            }
        )

    def list_by_exam(self, exam_id: str) -> List[Dict[str, Any]]:
        return self.find_many({"exam_id": str(exam_id)}, sort=[("submitted_at", -1)])

    def list_by_student(self, student_id: str) -> List[Dict[str, Any]]:
        return self.find_many({"student_id": str(student_id)}, sort=[("created_at", -1)])

    def list_all_submissions(self, is_flagged: Optional[bool] = None, limit: int = 50) -> List[Dict[str, Any]]:
        query = {}
        if is_flagged is not None:
            query["is_flagged"] = is_flagged
        return self.find_many(query, sort=[("submitted_at", -1), ("created_at", -1)], limit=limit)


# Canonical alias for submissions repository
ExamSubmissionRepository = ExamAttemptRepository

