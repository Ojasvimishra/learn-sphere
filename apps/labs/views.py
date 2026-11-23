"""
LearnSphere - Hands-on Virtual Labs Views
Interactive browser-based coding workspace with real-time sandboxed execution.
"""

import json
from django.shortcuts import render, redirect
from django.http import Http404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from services.code_execution_service import CodeExecutionService
from core.permissions import login_required_mongo
from core.utils import api_success, api_error

exec_service = CodeExecutionService()


@require_http_methods(["GET"])
def labs_list_view(request):
    lang = request.GET.get("lang", "all")
    difficulty = request.GET.get("difficulty", "all")
    labs = exec_service.lab_repo.list_labs(language=lang, difficulty=difficulty)

    return render(request, "pages/labs_list.html", {
        "labs": labs,
        "selected_lang": lang,
        "selected_difficulty": difficulty,
        "user": getattr(request, "mongo_user", None)
    })


@require_http_methods(["GET"])
def lab_workspace_view(request, lab_id):
    lab = exec_service.lab_repo.find_by_id(lab_id)
    if not lab:
        raise Http404("Virtual lab not found")

    return render(request, "pages/lab_workspace.html", {
        "lab": lab,
        "user": getattr(request, "mongo_user", None)
    })


# --- Code Execution APIs ---

@csrf_exempt
@require_http_methods(["POST"])
def api_run_code(request, lab_id):
    """Executes student code against custom stdout."""
    try:
        data = json.loads(request.body)
    except Exception:
        return api_error("Invalid JSON", 400)

    code_str = data.get("code", "")
    res = exec_service.run_student_code(code_str)
    return api_success(res)


@csrf_exempt
@require_http_methods(["POST"])
@login_required_mongo()
def api_submit_lab(request, lab_id):
    """Evaluates student code against automated unit test cases."""
    user = request.mongo_user
    try:
        data = json.loads(request.body)
    except Exception:
        return api_error("Invalid JSON", 400)

    code_str = data.get("code", "")
    ok, msg, results = exec_service.evaluate_lab_submission(lab_id, user["id"], code_str)
    if not ok:
        return api_error(msg, 400)

    return api_success(results, message=msg)
