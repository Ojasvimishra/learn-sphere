"""
LearnSphere - Doubts & Discussion Service (Tier 2)
Orchestrates student questions, peer & educator answers, resolution marking,
and solution verification.
"""

from typing import Any, Dict, List, Optional, Tuple
from database.repositories.doubt_repo import DoubtRepository, DoubtAnswerRepository
from core.validation import validate_string, ValidationError


class DoubtService:
    def __init__(self):
        self.doubt_repo = DoubtRepository()
        self.answer_repo = DoubtAnswerRepository()

    def ask_doubt(
        self,
        user: Dict[str, Any],
        title: str,
        content: str,
        course_id: Optional[str] = None,
        course_title: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Tuple[bool, str, Optional[str]]:
        try:
            clean_title = validate_string(title, "title", min_length=5, max_length=150)
            clean_content = validate_string(content, "content", min_length=10, max_length=5000)
        except ValidationError as e:
            return False, e.message, None

        doubt_id = self.doubt_repo.create_doubt(
            title=clean_title,
            content_markdown=clean_content,
            author_id=str(user.get("id")),
            author_name=user.get("full_name") or user.get("username", "Student"),
            course_id=course_id,
            course_title=course_title,
            tags=tags
        )
        return True, "Doubt posted successfully.", doubt_id

    def post_answer(
        self,
        user: Dict[str, Any],
        doubt_id: str,
        content: str
    ) -> Tuple[bool, str, Optional[str]]:
        try:
            clean_content = validate_string(content, "content", min_length=5, max_length=5000)
        except ValidationError as e:
            return False, e.message, None

        doubt = self.doubt_repo.find_by_id(doubt_id)
        if not doubt:
            return False, "Doubt not found", None

        role = user.get("role", "student")
        is_faculty = role in ["educator", "super_admin", "dept_admin"]

        ans_id = self.answer_repo.create_answer(
            doubt_id=doubt_id,
            author_id=str(user.get("id")),
            author_name=user.get("full_name") or user.get("username", "Learner"),
            author_role=role,
            content_markdown=clean_content,
            is_faculty_verified=is_faculty
        )
        return True, "Answer posted.", ans_id

    def accept_solution(self, doubt_id: str, answer_id: str, user: Dict[str, Any]) -> Tuple[bool, str]:
        doubt = self.doubt_repo.find_by_id(doubt_id)
        if not doubt:
            return False, "Doubt not found"

        user_id = str(user.get("id"))
        role = user.get("role")
        is_author = str(doubt.get("author_id")) == user_id
        is_faculty = role in ["educator", "super_admin", "dept_admin"]

        if not is_author and not is_faculty:
            return False, "Only the author or faculty can accept a solution."

        self.answer_repo.mark_accepted(answer_id)
        self.doubt_repo.mark_resolved(doubt_id, answer_id)
        return True, "Solution accepted and doubt marked as resolved."

    def toggle_doubt_upvote(self, doubt_id: str, user_id: str) -> bool:
        return self.doubt_repo.toggle_upvote(doubt_id, user_id)
