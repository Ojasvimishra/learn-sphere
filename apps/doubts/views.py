"""
LearnSphere - Doubts & AI Tutor Views
Handles student doubt asking, peer answers, solution verification,
and the AI study companion.
"""

import json
from django.shortcuts import render, redirect
from django.http import Http404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from services.doubt_service import DoubtService
from services.ai_tutor_service import AITutorService
from core.permissions import login_required_mongo
from core.utils import api_success, api_error

doubt_service = DoubtService()
ai_service = AITutorService()


@require_http_methods(["GET"])
def doubts_list_view(request):
    status = request.GET.get("status", "all")
    search = request.GET.get("q", "").strip()
    doubts = doubt_service.doubt_repo.list_doubts(status=status, search=search)

    return render(request, "pages/doubts_list.html", {
        "doubts": doubts,
        "selected_status": status,
        "search_query": search,
        "user": getattr(request, "mongo_user", None)
    })


@require_http_methods(["GET", "POST"])
@login_required_mongo()
def doubt_create_view(request):
    user = request.mongo_user
    error_msg = None

    if request.method == "POST":
        title = request.POST.get("title", "")
        content = request.POST.get("content", "")
        course_title = request.POST.get("course_title", "General")
        tags_raw = request.POST.get("tags", "")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

        ok, msg, doubt_id = doubt_service.ask_doubt(
            user=user,
            title=title,
            content=content,
            course_title=course_title,
            tags=tags
        )
        if ok:
            return redirect(f"/doubts/{doubt_id}/")
        else:
            error_msg = msg

    return render(request, "pages/doubt_create.html", {"error_msg": error_msg})


@require_http_methods(["GET"])
def doubt_detail_view(request, doubt_id):
    doubt = doubt_service.doubt_repo.find_by_id(doubt_id)
    if not doubt:
        raise Http404("Doubt not found")

    answers = doubt_service.answer_repo.list_by_doubt(doubt_id)
    user = getattr(request, "mongo_user", None)

    return render(request, "pages/doubt_detail.html", {
        "doubt": doubt,
        "answers": answers,
        "user": user
    })


@csrf_exempt
@require_http_methods(["POST"])
@login_required_mongo()
def api_post_answer(request, doubt_id):
    user = request.mongo_user
    try:
        data = json.loads(request.body)
    except Exception:
        return api_error("Invalid JSON", 400)

    content = data.get("content", "")
    ok, msg, ans_id = doubt_service.post_answer(user, doubt_id, content)
    if not ok:
        return api_error(msg, 400)

    return api_success({"answer_id": ans_id}, message="Answer submitted successfully.", status_code=201)


@csrf_exempt
@require_http_methods(["POST"])
@login_required_mongo()
def api_toggle_doubt_upvote(request, doubt_id):
    user = request.mongo_user
    upvoted = doubt_service.toggle_doubt_upvote(doubt_id, user["id"])
    return api_success({"upvoted": upvoted})


@csrf_exempt
@require_http_methods(["POST"])
@login_required_mongo()
def api_accept_solution(request, doubt_id, answer_id):
    user = request.mongo_user
    ok, msg = doubt_service.accept_solution(doubt_id, answer_id, user)
    if not ok:
        return api_error(msg, 403)
    return api_success({"accepted": True}, message=msg)


# --- AI Tutor View & Endpoint ---

@require_http_methods(["GET"])
def ai_tutor_view(request):
    user = getattr(request, "mongo_user", None)
    remaining_quota = ai_service.get_remaining_daily_quota(user["id"]) if user else 50

    return render(request, "pages/ai_tutor.html", {
        "user": user,
        "remaining_quota": remaining_quota
    })


@csrf_exempt
@require_http_methods(["POST"])
@login_required_mongo()
def api_ai_query(request):
    user = request.mongo_user
    try:
        data = json.loads(request.body)
    except Exception:
        return api_error("Invalid JSON", 400)

    query = data.get("query", "").strip()
    if not query:
        return api_error("Question prompt is required.", 400)

    result = ai_service.answer_query(user, query)
    if not result.get("success"):
        return api_error(result.get("error", "Rate limit exceeded"), 429)

    return api_success(result)
