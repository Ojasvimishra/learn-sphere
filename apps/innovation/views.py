"""
LearnSphere - Student Innovation Showcase Views
Empowering students to share ideas, research prototypes, and digital tools.
"""

from django.shortcuts import render, redirect
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_http_methods
from services.innovation_service import InnovationService
from core.permissions import login_required_mongo
from core.utils import api_success, api_error
import json

innovation_service = InnovationService()


@require_http_methods(["GET"])
def innovation_projects_view(request):
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "all").strip()
    page = int(request.GET.get("page", 1))

    pagination = innovation_service.get_projects(
        query=q,
        category=category,
        page=page,
        per_page=6
    )
    user = getattr(request, "mongo_user", None)
    user_id = user["id"] if user else None

    return render(request, "pages/innovation.html", {
        "pagination": pagination,
        "projects": pagination["items"],
        "selected_q": q,
        "selected_category": category,
        "current_user_id": user_id
    })


@require_http_methods(["GET"])
def project_detail_view(request, project_id):
    project = innovation_service.get_project_by_id(project_id)
    if not project:
        raise Http404("Project not found")

    user = getattr(request, "mongo_user", None)
    has_upvoted = (user["id"] in project.get("upvoted_by", [])) if user else False

    return render(request, "pages/project_detail.html", {
        "project": project,
        "has_upvoted": has_upvoted
    })


# --- JSON API Endpoints ---

@require_http_methods(["POST"])
@login_required_mongo()
def api_submit_project(request):
    user = request.mongo_user
    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    title = data.get("title", "").strip()
    abstract = data.get("abstract", "").strip()
    category = data.get("category", "Smart Education").strip()
    tech_stack_raw = data.get("tech_stack", "")
    repo_url = data.get("repo_url", "").strip()
    demo_url = data.get("demo_url", "").strip()

    if isinstance(tech_stack_raw, str):
        tech_stack = [t.strip() for t in tech_stack_raw.split(",") if t.strip()]
    elif isinstance(tech_stack_raw, list):
        tech_stack = tech_stack_raw
    else:
        tech_stack = []

    if not title or len(title) < 5:
        return api_error("Title must be at least 5 characters long.")
    if not abstract or len(abstract) < 20:
        return api_error("Abstract must be at least 20 characters long.")

    project_id = innovation_service.submit_project(
        title=title,
        abstract=abstract,
        author_id=user["id"],
        author_name=user.get("full_name") or user["username"],
        tech_stack=tech_stack,
        category=category,
        repo_url=repo_url,
        demo_url=demo_url
    )
    return api_success({"id": project_id}, message="Project published to Student Innovation Hub!")


@require_http_methods(["POST"])
@login_required_mongo()
def api_upvote_project(request, project_id):
    user = request.mongo_user
    res = innovation_service.toggle_upvote(project_id, user["id"])
    return api_success(res)


@require_http_methods(["POST"])
@login_required_mongo()
def api_add_comment(request, project_id):
    user = request.mongo_user
    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    text = data.get("text", "").strip()
    if not text:
        return api_error("Comment cannot be empty.")

    success = innovation_service.add_comment(
        project_id=project_id,
        user_id=user["id"],
        user_name=user.get("full_name") or user["username"],
        text=text
    )
    return api_success({"success": success}, message="Comment added.")
