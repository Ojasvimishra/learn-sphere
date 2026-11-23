"""
LearnSphere - Curated Resources & Scraping Vault Views
Curated tools and articles inspired by modern web scraping automation research.
"""

from django.shortcuts import render, redirect
from django.http import Http404
from django.views.decorators.http import require_http_methods
from services.resource_service import ResourceService
from services.auth_service import AuthService
from core.permissions import login_required_mongo
from core.utils import api_success, api_error

resource_service = ResourceService()
auth_service = AuthService()


@require_http_methods(["GET"])
def resources_list_view(request):
    q = request.GET.get("q", "").strip()
    tag = request.GET.get("tag", "all").strip()
    relevance = request.GET.get("relevance", "all").strip()
    page = int(request.GET.get("page", 1))

    pagination = resource_service.get_resources(
        query=q,
        relevance=relevance,
        tag=tag,
        page=page,
        per_page=9
    )
    all_tags = resource_service.get_available_tags()
    user = getattr(request, "mongo_user", None)
    user_bookmarks = user.get("bookmarked_resources", []) if user else []

    return render(request, "pages/resources.html", {
        "pagination": pagination,
        "resources": pagination["items"],
        "all_tags": all_tags,
        "selected_q": q,
        "selected_tag": tag,
        "selected_relevance": relevance,
        "user_bookmarks": user_bookmarks
    })


@require_http_methods(["GET"])
def resource_detail_view(request, resource_id):
    resource = resource_service.get_resource_by_id(resource_id)
    if not resource:
        raise Http404("Resource not found")

    user = getattr(request, "mongo_user", None)
    is_bookmarked = (resource["id"] in user.get("bookmarked_resources", [])) if user else False

    return render(request, "pages/resource_detail.html", {
        "resource": resource,
        "is_bookmarked": is_bookmarked
    })


# --- JSON API Endpoints ---

@require_http_methods(["GET"])
def api_resources_search(request):
    q = request.GET.get("q", "").strip()
    tag = request.GET.get("tag", "all").strip()
    relevance = request.GET.get("relevance", "all").strip()
    page = int(request.GET.get("page", 1))

    data = resource_service.get_resources(
        query=q,
        relevance=relevance,
        tag=tag,
        page=page,
        per_page=9
    )
    return api_success(data)


@require_http_methods(["POST"])
@login_required_mongo()
def api_resource_bookmark(request, resource_id):
    user = request.mongo_user
    success = auth_service.toggle_bookmark(user["id"], resource_id)
    return api_success({"bookmarked": success}, message="Bookmark updated")
