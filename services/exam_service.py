"""
LearnSphere - Proctored Exam & Server-Side Grading Service (Tier 2)
Guarantees strict server-side evaluation (correct answers are never sent to the client
prior to submission), anti-cheat proctor telemetry, and educator grade overrides.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from database.repositories.exam_repo import ExamRepository, ExamAttemptRepository
from services.audit_service import AuditService
from core.validation import validate_string, ValidationError


class ExamService:
    def __init__(self):
        self.exam_repo = ExamRepository()
        self.attempt_repo = ExamAttemptRepository()
        self.audit = AuditService()

    def create_exam(
        self,
        instructor: Dict[str, Any],
        data: Dict[str, Any]
    ) -> Tuple[bool, str, Optional[str]]:
        try:
            title = validate_string(data.get("title"), "title", min_length=5, max_length=150)
            course_id = validate_string(data.get("course_id"), "course_id")
        except ValidationError as e:
            return False, e.message, None

        questions = data.get("questions", [])
        if not questions:
            return False, "Exam must contain at least one question.", None

        # Calculate total marks
        total_marks = sum(q.get("marks", 5) for q in questions)
        passing_marks = int(data.get("passing_marks", round(total_marks * 0.6)))

        exam_id = self.exam_repo.create_exam(
            title=title,
            course_id=course_id,
            course_title=data.get("course_title", "Course Exam"),
            instructor_id=str(instructor.get("id")),
            instructor_name=instructor.get("full_name") or instructor.get("username", "Faculty"),
            duration_minutes=int(data.get("duration_minutes", 60)),
            questions=questions,
            total_marks=total_marks,
            passing_marks=passing_marks,
            is_proctored=bool(data.get("is_proctored", True)),
            tab_switch_limit=int(data.get("tab_switch_limit", 3)),
            description=data.get("description", "")
        )
        return True, "Exam created successfully.", exam_id

    def get_exam_taker_payload(self, exam_id: str, student: Dict[str, Any]) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        SECURITY REQUIREMENT:
        Prepares questions for the student taker viewport.
        CRITICAL: Strips correct_option_index, secret answer keys, and explanations!
        Answers must NEVER be inspectable via browser devtools.
        """
        exam = self.exam_repo.find_by_id(exam_id)
        if not exam:
            return False, "Exam not found", None

        attempt = self.attempt_repo.start_attempt(exam, student)

        # Sanitize questions for client
        sanitized_questions = []
        for q in exam.get("questions", []):
            sanitized_questions.append({
                "id": q.get("id"),
                "text": q.get("text"),
                "type": q.get("type", "single_choice"),
                "options": q.get("options", []),
                "marks": q.get("marks", 5)
            })

        return True, "Success", {
            "exam_id": exam["id"],
            "title": exam["title"],
            "course_title": exam.get("course_title"),
            "duration_minutes": exam["duration_minutes"],
            "total_marks": exam["total_marks"],
            "tab_switch_limit": exam.get("tab_switch_limit", 3),
            "is_proctored": exam.get("is_proctored", True),
            "attempt_id": attempt["id"],
            "started_at": attempt["started_at"],
            "questions": sanitized_questions,
            "existing_answers": attempt.get("answers", {})
        }

    def record_proctor_event(
        self,
        attempt_id: str,
        student: Dict[str, Any],
        event_type: str,
        details: Dict[str, Any]
    ) -> bool:
        """Records anti-cheat security flags (tab switch, window blur, fullscreen exit)."""
        logged = self.attempt_repo.log_proctor_event(attempt_id, event_type, details)

        # If student switched tabs, also log security audit trail
        if event_type in ["tab_hidden", "fullscreen_exit"]:
            self.audit.log_event(
                action=f"exam.proctor.{event_type}",
                actor=student,
                resource_type="exam_attempt",
                resource_id=attempt_id,
                status="warning",
                details=details
            )
        return logged

    def submit_and_evaluate_exam(
        self,
        attempt_id: str,
        student: Dict[str, Any],
        student_answers: Dict[str, Any]
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Evaluates exam server-side against secret answer key in database.
        Detects excessive tab switching (> limit) and flags attempt for review.
        """
        attempt = self.attempt_repo.find_by_id(attempt_id)
        if not attempt:
            return False, "Attempt not found", None

        if attempt.get("status") in ["submitted", "graded"]:
            return False, "Exam has already been submitted.", None

        exam = self.exam_repo.find_by_id(attempt["exam_id"])
        if not exam:
            return False, "Associated exam not found", None

        total_score = 0
        total_marks = exam.get("total_marks", 100)
        passing_marks = exam.get("passing_marks", 60)
        results_breakdown = []

        # Server-side verification of each question
        for q in exam.get("questions", []):
            q_id = str(q.get("id"))
            marks = int(q.get("marks", 5))
            correct_index = q.get("correct_option_index")
            student_choice = student_answers.get(q_id)

            is_correct = False
            if student_choice is not None and str(student_choice) == str(correct_index):
                is_correct = True
                total_score += marks

            results_breakdown.append({
                "question_id": q_id,
                "question_text": q.get("text"),
                "student_choice": student_choice,
                "correct_option_index": correct_index,
                "is_correct": is_correct,
                "marks_awarded": marks if is_correct else 0,
                "explanation": q.get("explanation", "")
            })

        passed = total_score >= passing_marks

        # Check anti-cheat tab switch limit
        tab_limit = exam.get("tab_switch_limit", 3)
        tab_count = attempt.get("tab_switches_count", 0)
        is_flagged = tab_count > tab_limit

        graded_attempt = self.attempt_repo.submit_and_grade(
            attempt_id=attempt_id,
            answers=student_answers,
            score=total_score,
            total_marks=total_marks,
            passed=passed,
            is_flagged=is_flagged
        )

        return True, "Exam evaluated successfully.", {
            "attempt_id": attempt_id,
            "score": total_score,
            "total_marks": total_marks,
            "percentage": graded_attempt["percentage"],
            "passed": passed,
            "is_flagged": is_flagged,
            "tab_switches": tab_count,
            "results_breakdown": results_breakdown
        }

    def override_student_grade(
        self,
        attempt_id: str,
        educator: Dict[str, Any],
        new_score: int,
        reason: str
    ) -> Tuple[bool, str]:
        attempt = self.attempt_repo.find_by_id(attempt_id)
        if not attempt:
            return False, "Attempt not found"

        old_score = attempt.get("score", 0)
        total_marks = attempt.get("total_marks", 100)
        educator_name = educator.get("full_name") or educator.get("username", "Faculty")

        ok = self.attempt_repo.override_grade(attempt_id, new_score, total_marks, reason, educator_name)
        if ok:
            # Mandatory immutable audit log
            self.audit.log_grade_override(
                acting_educator=educator,
                student_id=attempt["student_id"],
                exam_id=attempt["exam_id"],
                old_grade=old_score,
                new_grade=new_score,
                reason=reason
            )
            return True, "Grade successfully overridden and recorded in audit log."
        return False, "Failed to update grade."
