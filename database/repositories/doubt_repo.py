"""
LearnSphere - Doubts & Discussion Forum Repository (Tier 3)
Manages academic doubts, peer & faculty answers, accepted solutions,
and verified mentor badges.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from database.repositories.base import BaseRepository


class DoubtRepository(BaseRepository):
    def __init__(self):
        super().__init__("doubts")

    def create_doubt(
        self,
        title: str,
        content_markdown: str,
        author_id: str,
        author_name: str,
        course_id: Optional[str] = None,
        course_title: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        now = datetime.now(timezone.utc)
        doc = {
            "title": title.strip(),
            "content_markdown": content_markdown.strip(),
            "author_id": str(author_id),
            "author_name": author_name.strip(),
            "course_id": str(course_id) if course_id else None,
            "course_title": (course_title or "").strip() or "General Academic Inquiry",
            "tags": tags or ["smart-education"],
            "status": "open",  # open, resolved
            "accepted_answer_id": None,
            "answers_count": 0,
            "upvotes": 0,
            "upvoted_by": [],
            "created_at": now,
            "updated_at": now
        }
        return self.insert_one(doc)

    def list_doubts(
        self,
        course_id: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = {}
        if course_id and course_id != "all":
            query["course_id"] = str(course_id)
        if status and status != "all":
            query["status"] = status
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"content_markdown": {"$regex": search, "$options": "i"}}
            ]
        return self.find_many(query, sort=[("created_at", -1)], limit=50)

    def toggle_upvote(self, doubt_id: str, user_id: str) -> bool:
        """Atomic upvoting: strictly enforces one vote per user."""
        oid = self.to_object_id(doubt_id)
        if not oid:
            return False
        clean_user = str(user_id)
        doc = self.find_by_id(doubt_id)
        if not doc:
            return False

        if clean_user in doc.get("upvoted_by", []):
            self.collection.update_one(
                {"_id": oid},
                {"$pull": {"upvoted_by": clean_user}, "$inc": {"upvotes": -1}}
            )
            return False
        else:
            self.collection.update_one(
                {"_id": oid},
                {"$addToSet": {"upvoted_by": clean_user}, "$inc": {"upvotes": 1}}
            )
            return True

    def mark_resolved(self, doubt_id: str, answer_id: str) -> bool:
        oid = self.to_object_id(doubt_id)
        if not oid:
            return False
        return self.update_one(
            {"_id": oid},
            {
                "status": "resolved",
                "accepted_answer_id": str(answer_id),
                "updated_at": datetime.now(timezone.utc)
            }
        )


class DoubtAnswerRepository(BaseRepository):
    def __init__(self):
        super().__init__("doubt_answers")

    def create_answer(
        self,
        doubt_id: str,
        author_id: str,
        author_name: str,
        author_role: str,
        content_markdown: str,
        is_faculty_verified: bool = False
    ) -> str:
        now = datetime.now(timezone.utc)
        doc = {
            "doubt_id": str(doubt_id),
            "author_id": str(author_id),
            "author_name": author_name.strip(),
            "author_role": author_role,
            "content_markdown": content_markdown.strip(),
            "is_accepted": False,
            "is_faculty_verified": is_faculty_verified,
            "upvotes": 0,
            "upvoted_by": [],
            "created_at": now
        }
        ans_id = self.insert_one(doc)
        # Increment doubt answer count
        doubt_repo = DoubtRepository()
        oid = doubt_repo.to_object_id(doubt_id)
        if oid:
            doubt_repo.collection.update_one({"_id": oid}, {"$inc": {"answers_count": 1}})
        return ans_id

    def list_by_doubt(self, doubt_id: str) -> List[Dict[str, Any]]:
        return self.find_many(
            {"doubt_id": str(doubt_id)},
            sort=[("is_accepted", -1), ("is_faculty_verified", -1), ("upvotes", -1), ("created_at", 1)]
        )

    def mark_accepted(self, answer_id: str) -> bool:
        oid = self.to_object_id(answer_id)
        if not oid:
            return False
        return self.update_one({"_id": oid}, {"is_accepted": True})
