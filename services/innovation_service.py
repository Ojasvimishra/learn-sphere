"""
LearnSphere - Student Innovation Service (Tier 2)
Business logic for managing student innovation projects, peer review, and voting.
"""

from typing import Any, Dict, List, Optional
from database.repositories.project_repo import ProjectRepository


class InnovationService:
    def __init__(self):
        self.repo = ProjectRepository()

    def get_projects(
        self,
        query: str = "",
        category: str = "all",
        page: int = 1,
        per_page: int = 6
    ) -> Dict[str, Any]:
        return self.repo.search_projects(
            query_text=query,
            category=category,
            page=page,
            per_page=per_page
        )

    def get_project_by_id(self, project_id: str) -> Optional[Dict[str, Any]]:
        return self.repo.find_by_id(project_id)

    def submit_project(
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
        return self.repo.create_project(
            title=title,
            abstract=abstract,
            author_id=author_id,
            author_name=author_name,
            tech_stack=tech_stack,
            category=category,
            repo_url=repo_url,
            demo_url=demo_url
        )

    def toggle_upvote(self, project_id: str, user_id: str) -> Dict[str, Any]:
        return self.repo.toggle_upvote(project_id, user_id)

    def add_comment(self, project_id: str, user_id: str, user_name: str, text: str) -> bool:
        return self.repo.add_comment(project_id, user_id, user_name, text)
