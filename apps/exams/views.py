"""
LearnSphere - Proctored Exams & Quizzes Views
Orchestrates timed exam taking, anti-cheat client event monitoring,
server-side evaluation, and faculty proctor inspection.
"""

import json
from django.shortcuts import render, redirect
from django.http import Http404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from services.exam_service import ExamService
from services.course_service import CourseService
from core.permissions import login_required_mongo, role_required_mongo, permission_required_mongo
from core.utils import api_success, api_error

exam_service = ExamService()
course_service = CourseService()


@require_http_methods(["GET"])
def exams_list_view(request):
    """Lists available published exams and past student attempts."""
    user = getattr(request, "mongo_user", None)
    exams = exam_service.exam_repo.list_available_exams()
    attempts = exam_service.attempt_repo.list_by_student(user["id"]) if user else []

    return render(request, "pages/exams_list.html", {
        "exams": exams,
        "attempts": attempts,
        "user": user
    })


@require_http_methods(["GET"])
@login_required_mongo()
def exam_take_view(request, exam_id):
    """Proctored student exam interface with anti-cheat client telemetry."""
    user = request.mongo_user
    ok, msg, payload = exam_service.get_exam_taker_payload(exam_id, user)
    if not ok:
        raise Http404(msg)

    return render(request, "pages/exam_take.html", {
        "exam_data": json.dumps(payload, default=str),
        "exam": payload,
        "user": user
    })


@require_http_methods(["GET"])
@login_required_mongo()
def exam_result_view(request, attempt_id):
    """Shows student grade summary and question review after submission."""
    user = request.mongo_user
    attempt = exam_service.attempt_repo.find_by_id(attempt_id)
    if not attempt or (str(attempt.get("student_id")) != str(user.get("id")) and user.get("role") not in ["educator", "super_admin", "dept_admin"]):
        raise Http404("Attempt not found")

    exam = exam_service.exam_repo.find_by_id(attempt["exam_id"])

    return render(request, "pages/exam_result.html", {
        "attempt": attempt,
        "exam": exam,
        "user": user
    })


# --- REST API Endpoints ---

@csrf_exempt
@require_http_methods(["POST"])
@login_required_mongo()
def api_exam_start(request, exam_id):
    user = request.mongo_user
    ok, msg, payload = exam_service.get_exam_taker_payload(exam_id, user)
    if not ok:
        return api_error(msg, 400)
    return api_success(payload)


@csrf_exempt
@require_http_methods(["POST"])
@login_required_mongo()
def api_proctor_event(request, attempt_id):
    """Receives anti-cheat signals from browser (tab_hidden, window_blur, fullscreen_exit)."""
    user = request.mongo_user
    try:
        data = json.loads(request.body)
    except Exception:
        data = {}

    event_type = data.get("event", "tab_hidden")
    details = data.get("details", {})

    exam_service.record_proctor_event(attempt_id, user, event_type, details)
    return api_success({"recorded": True}, message="Security telemetry logged.")


@csrf_exempt
@require_http_methods(["POST"])
@login_required_mongo()
def api_exam_submit(request, attempt_id):
    """Validates exam server-side and awards grade."""
    user = request.mongo_user
    try:
        data = json.loads(request.body)
    except Exception:
        return api_error("Invalid payload", 400)

    student_answers = data.get("answers", {})
    ok, msg, result = exam_service.submit_and_evaluate_exam(attempt_id, user, student_answers)
    if not ok:
        return api_error(msg, 400)

    return api_success(result, message=msg)


# --- Educator Proctoring & Grade Override Studio ---

@require_http_methods(["GET", "POST"])
@role_required_mongo("educator", "dept_admin", "super_admin")
def educator_exam_create_view(request):
    user = request.mongo_user
    courses = course_service.get_instructor_courses(user["id"])
    error_msg = None

    if request.method == "POST":
        title = request.POST.get("title", "")
        course_id = request.POST.get("course_id", "")
        duration = int(request.POST.get("duration_minutes", 60) or 60)
        desc = request.POST.get("description", "")
        raw_json_q = request.POST.get("questions_json", "[]")

        try:
            questions = json.loads(raw_json_q)
        except Exception:
            questions = [
                {
                    "text": "What is the primary advantage of Argon2id over basic SHA-256 for password hashing?",
                    "type": "single_choice",
                    "options": ["Memory hardness resisting GPU/ASIC attacks", "Lower memory consumption", "Smaller hash string", "Faster execution"],
                    "correct_option_index": 0,
                    "marks": 10,
                    "explanation": "Argon2id utilizes memory-hard algorithms specifically designed to neutralize parallel brute-force cracking on GPUs and custom ASICs."
                }
            ]

        ok, msg, exam_id = exam_service.create_exam(user, {
            "title": title,
            "course_id": course_id,
            "duration_minutes": duration,
            "description": desc,
            "questions": questions,
            "is_proctored": True
        })

        if ok:
            return redirect(f"/exams/educator/{exam_id}/submissions/")
        else:
            error_msg = msg

    return render(request, "pages/educator_exam_create.html", {
        "courses": courses,
        "error_msg": error_msg
    })


@require_http_methods(["GET"])
@role_required_mongo("educator", "dept_admin", "super_admin")
def educator_submissions_view(request, exam_id):
    exam = exam_service.exam_repo.find_by_id(exam_id)
    if not exam:
        raise Http404("Exam not found")

    submissions = exam_service.attempt_repo.list_by_exam(exam_id)

    return render(request, "pages/educator_exam_submissions.html", {
        "exam": exam,
        "submissions": submissions,
        "user": request.mongo_user
    })


@csrf_exempt
@require_http_methods(["POST"])
@role_required_mongo("educator", "dept_admin", "super_admin")
def api_override_grade(request, attempt_id):
    user = request.mongo_user
    try:
        data = json.loads(request.body)
    except Exception:
        return api_error("Invalid JSON", 400)

    new_score = int(data.get("new_score", 0))
    reason = data.get("reason", "").strip()
    if not reason:
        return api_error("A justification rationale is mandatory for grade overrides.", 400)

    ok, msg = exam_service.override_student_grade(attempt_id, user, new_score, reason)
    if not ok:
        return api_error(msg, 400)

    return api_success({"overridden": True}, message=msg)
