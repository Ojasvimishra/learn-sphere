"""
LearnSphere - Hands-on Virtual Labs & Code Submissions Repository (Tier 3)
Manages interactive programming exercises, test suites, and student code execution history.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from database.repositories.base import BaseRepository


class LabRepository(BaseRepository):
    def __init__(self):
        super().__init__("labs")

    def create_lab(
        self,
        title: str,
        description: str,
        course_id: str,
        language: str = "python",
        difficulty: str = "Medium",
        starter_code: str = "# Write your solution below\n",
        solution_code: str = "",
        test_cases: Optional[List[Dict[str, Any]]] = None,
        hints: Optional[List[str]] = None,
        xp_reward: int = 50
    ) -> str:
        now = datetime.now(timezone.utc)
        doc = {
            "title": title.strip(),
            "description": description.strip(),
            "course_id": str(course_id),
            "language": language.lower(),
            "difficulty": difficulty.capitalize(),
            "starter_code": starter_code,
            "solution_code": solution_code,
            "test_cases": test_cases or [],
            "hints": hints or [],
            "xp_reward": xp_reward,
            "completions_count": 0,
            "created_at": now,
            "updated_at": now
        }
        return self.insert_one(doc)

    def list_labs(self, language: Optional[str] = None, difficulty: Optional[str] = None) -> List[Dict[str, Any]]:
        query = {}
        if language and language != "all":
            query["language"] = language.lower()
        if difficulty and difficulty != "all":
            query["difficulty"] = difficulty.capitalize()
        return self.find_many(query, sort=[("created_at", -1)], limit=50)


class LabSubmissionRepository(BaseRepository):
    def __init__(self):
        super().__init__("lab_submissions")

    def record_submission(
        self,
        lab_id: str,
        student_id: str,
        code: str,
        status: str,
        tests_passed: int,
        total_tests: int,
        runtime_ms: float,
        output: str
    ) -> str:
        now = datetime.now(timezone.utc)
        doc = {
            "lab_id": str(lab_id),
            "student_id": str(student_id),
            "code": code,
            "status": status,  # passed, failed, error
            "tests_passed": tests_passed,
            "total_tests": total_tests,
            "runtime_ms": runtime_ms,
            "output": output[:2000],
            "submitted_at": now
        }
        return self.insert_one(doc)

    def list_by_student(self, student_id: str) -> List[Dict[str, Any]]:
        return self.find_many({"student_id": str(student_id)}, sort=[("submitted_at", -1)])
