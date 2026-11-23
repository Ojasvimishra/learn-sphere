"""
LearnSphere - Curated Resources & Scraping Vault Service (Tier 2)
Business logic for searching, filtering, and curating developer tech resources.
"""

from typing import Any, Dict, List, Optional
from database.repositories.resource_repo import ResourceRepository


class ResourceService:
    def __init__(self):
        self.repo = ResourceRepository()

    def get_resources(
        self,
        query: str = "",
        relevance: str = "all",
        tag: str = "all",
        page: int = 1,
        per_page: int = 9
    ) -> Dict[str, Any]:
        """Provides filtered, paginated resource listings."""
        return self.repo.search_resources(
            query_text=query,
            relevance=relevance,
            tag=tag,
            page=page,
            per_page=per_page
        )

    def get_resource_by_id(self, resource_id: str) -> Optional[Dict[str, Any]]:
        self.repo.increment_view(resource_id)
        return self.repo.find_by_id(resource_id)

    def get_available_tags(self) -> List[str]:
        return self.repo.get_all_tags()

    def submit_resource(
        self,
        title: str,
        url: str,
        description: str,
        tags: List[str],
        category: str,
        relevance: str = "high",
        markdown: Optional[str] = None
    ) -> str:
        return self.repo.create_resource(
            title=title,
            url=url,
            description=description,
            relevance=relevance,
            tags=tags,
            category=category,
            markdown=markdown
        )
