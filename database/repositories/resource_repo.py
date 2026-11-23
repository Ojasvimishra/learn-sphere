"""
LearnSphere - Resource Repository (Tier 3)
Stores curated developer articles, web scraping tools, and educational guides.
Incorporates metadata matching the user's reference dataset.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import re
from database.repositories.base import BaseRepository


class ResourceRepository(BaseRepository):
    def __init__(self):
        super().__init__("resources")

    def create_resource(
        self,
        title: str,
        url: str,
        description: str,
        relevance: str = "high",
        tags: List[str] = None,
        markdown: Optional[str] = None,
        highlights: Optional[str] = None,
        category: str = "Web Scraping & Headless Automation",
        source: str = "Tech Research Vault"
    ) -> str:
        now = datetime.now(timezone.utc)
        doc = {
            "title": title.strip(),
            "url": url.strip(),
            "description": description.strip(),
            "relevance": relevance.lower() if relevance in ["high", "medium", "standard"] else "high",
            "tags": [t.strip().lower() for t in (tags or [])],
            "markdown": markdown,
            "highlights": highlights,
            "category": category.strip(),
            "source": source.strip(),
            "views": 0,
            "bookmarks_count": 0,
            "created_at": now,
            "updated_at": now
        }
        return self.insert_one(doc)

    def search_resources(
        self,
        query_text: str = "",
        relevance: Optional[str] = None,
        tag: Optional[str] = None,
        page: int = 1,
        per_page: int = 9
    ) -> Dict[str, Any]:
        """High-efficiency filtered search with MongoDB regex and text indices."""
        filter_doc: Dict[str, Any] = {}

        if relevance and relevance != "all":
            filter_doc["relevance"] = relevance.lower()

        if tag and tag != "all":
            filter_doc["tags"] = tag.lower()

        if query_text:
            safe_text = re.escape(query_text.strip())
            filter_doc["$or"] = [
                {"title": {"$regex": safe_text, "$options": "i"}},
                {"description": {"$regex": safe_text, "$options": "i"}},
                {"tags": {"$regex": safe_text, "$options": "i"}}
            ]

        return self.paginate(
            filter_doc,
            page=page,
            per_page=per_page,
            sort=[("created_at", -1)]
        )

    def increment_view(self, resource_id: str):
        oid = self.to_object_id(resource_id)
        if oid:
            self.collection.update_one({"_id": oid}, {"$inc": {"views": 1}})

    def get_all_tags(self) -> List[str]:
        """Returns unique list of tags across all resources."""
        return self.collection.distinct("tags")
