"""
LearnSphere - Student Innovation Projects Repository (Tier 3)
Stores student projects, concepts, research artifacts, and community upvotes.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import re
from database.repositories.base import BaseRepository


class ProjectRepository(BaseRepository):
    def __init__(self):
        super().__init__("projects")

    def create_project(
        self,
        title: str,
        abstract: str,
        author_id: str,
        author_name: str,
        tech_stack: List[str],
        category: str = "Smart Education",
        repo_url: str = "",
        demo_url: str = ""
    ) -> str:
        now = datetime.now(timezone.utc)
        doc = {
            "title": title.strip(),
            "abstract": abstract.strip(),
            "author_id": author_id,
            "author_name": author_name.strip(),
            "tech_stack": [t.strip() for t in tech_stack if t.strip()],
            "category": category.strip(),
            "repo_url": repo_url.strip(),
            "demo_url": demo_url.strip(),
            "upvotes": 0,
            "upvoted_by": [],
            "status": "published",
            "comments": [],
            "created_at": now,
            "updated_at": now
        }
        return self.insert_one(doc)

    def toggle_upvote(self, project_id: str, user_id: str) -> Dict[str, Any]:
        """Atomically toggles upvote status for high concurrency."""
        oid = self.to_object_id(project_id)
        if not oid:
            return {"success": False, "upvoted": False, "count": 0}

        project = self.find_by_id(project_id)
        if not project:
            return {"success": False, "upvoted": False, "count": 0}

        upvoted_by = project.get("upvoted_by", [])
        if user_id in upvoted_by:
            self.collection.update_one(
                {"_id": oid},
                {"$pull": {"upvoted_by": user_id}, "$inc": {"upvotes": -1}}
            )
            upvoted = False
            new_count = max(0, project.get("upvotes", 1) - 1)
        else:
            self.collection.update_one(
                {"_id": oid},
                {"$addToSet": {"upvoted_by": user_id}, "$inc": {"upvotes": 1}}
            )
            upvoted = True
            new_count = project.get("upvotes", 0) + 1

        return {"success": True, "upvoted": upvoted, "count": new_count}

    def add_comment(self, project_id: str, user_id: str, user_name: str, text: str) -> bool:
        oid = self.to_object_id(project_id)
        if not oid:
            return False
        comment = {
            "user_id": user_id,
            "user_name": user_name,
            "text": text.strip(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        res = self.collection.update_one(
            {"_id": oid},
            {"$push": {"comments": comment}}
        )
        return res.modified_count > 0

    def search_projects(
        self,
        query_text: str = "",
        category: Optional[str] = None,
        page: int = 1,
        per_page: int = 6
    ) -> Dict[str, Any]:
        filter_doc: Dict[str, Any] = {"status": "published"}
        if category and category != "all":
            filter_doc["category"] = category

        if query_text:
            safe_text = re.escape(query_text.strip())
            filter_doc["$or"] = [
                {"title": {"$regex": safe_text, "$options": "i"}},
                {"abstract": {"$regex": safe_text, "$options": "i"}},
                {"tech_stack": {"$regex": safe_text, "$options": "i"}}
            ]

        return self.paginate(
            filter_doc,
            page=page,
            per_page=per_page,
            sort=[("upvotes", -1), ("created_at", -1)]
        )
