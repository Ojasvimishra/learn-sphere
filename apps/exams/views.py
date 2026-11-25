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
    own_courses = course_service.get_instructor_courses(user["id"])
    all_courses = course_service.get_courses(status="published")
    seen_ids = {str(c.get("id")) for c in own_courses}
    courses = list(own_courses) + [c for c in all_courses if str(c.get("id")) not in seen_ids]
    error_msg = None

    if request.method == "POST":
        title = request.POST.get("title", "")
        course_id = request.POST.get("course_id", "")
        duration = int(request.POST.get("duration_minutes", 60) or 60)
        desc = request.POST.get("description", "")
        raw_json_q = request.POST.get("questions_json", "[]")
        scheduled_start = request.POST.get("scheduled_start") or None
        scheduled_end = request.POST.get("scheduled_end") or None
        is_proctored = request.POST.get("is_proctored") != "false"
        tab_switch_limit = int(request.POST.get("tab_switch_limit", 3) or 3)
        passing_marks = int(request.POST.get("passing_marks", 60) or 60)

        course_obj = course_service.get_course_by_id(course_id)
        course_title = course_obj.get("title", "Curriculum Exam") if course_obj else "Curriculum Exam"

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

        if not questions:
            questions = [
                {
                    "text": "Explain key core concepts covered in this curriculum module.",
                    "type": "single_choice",
                    "options": ["Principle A: High scalability", "Principle B: Zero fault tolerance", "Principle C: Single point failure", "Principle D: None"],
                    "correct_option_index": 0,
                    "marks": 10,
                    "explanation": "Scalable modular architecture is a core tenant."
                }
            ]

        ok, msg, exam_id = exam_service.create_exam(user, {
            "title": title,
            "course_id": course_id,
            "course_title": course_title,
            "duration_minutes": duration,
            "description": desc,
            "questions": questions,
            "is_proctored": is_proctored,
            "tab_switch_limit": tab_switch_limit,
            "passing_marks": passing_marks,
            "scheduled_start": scheduled_start,
            "scheduled_end": scheduled_end
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


@require_http_methods(["GET"])
@role_required_mongo("educator", "dept_admin", "super_admin")
def educator_proctor_console_view(request, exam_id=None):
    """Live Exams & Invigilation Console for Educators (sorted flagged-first)."""
    user = request.mongo_user
    all_exams = exam_service.exam_repo.find_many({}, sort=[("created_at", -1)], limit=50)

    target_exam_id = exam_id or request.GET.get("exam_id")
    selected_exam = None
    if target_exam_id:
        selected_exam = exam_service.exam_repo.find_by_id(target_exam_id)
    if not selected_exam and all_exams:
        selected_exam = all_exams[0]

    attempts = []
    if selected_exam:
        raw_attempts = exam_service.attempt_repo.list_by_exam(selected_exam["id"])
        # Sort flagged first, then by tab switches descending
        attempts = sorted(
            raw_attempts,
            key=lambda a: (0 if a.get("is_flagged") else 1, -(a.get("tab_switches_count", 0)))
        )

    flagged_count = sum(1 for a in attempts if a.get("is_flagged"))
    terminated_count = sum(1 for a in attempts if a.get("status") == "disqualified" or a.get("proctor_status") == "terminated")
    paused_count = sum(1 for a in attempts if a.get("proctor_status") == "paused")
    active_count = max(0, len(attempts) - terminated_count)

    return render(request, "pages/educator_exam_proctor.html", {
        "user": user,
        "all_exams": all_exams,
        "exam": selected_exam,
        "attempts": attempts,
        "active_count": active_count,
        "paused_count": paused_count,
        "flagged_count": flagged_count,
        "terminated_count": terminated_count
    })


@csrf_exempt
@require_http_methods(["POST"])
@role_required_mongo("educator", "dept_admin", "super_admin")
def api_proctor_action(request, attempt_id):
    """Executes proctor actions (send_warning, pause_student, extend_time, clear_flag, terminate) with audit logging."""
    from datetime import datetime, timezone
    from services.audit_service import AuditService

    user = request.mongo_user
    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST.dict()

    action = (data.get("action") or "").strip()
    reason = (data.get("reason") or "").strip()

    valid_actions = {"send_warning", "pause_student", "extend_time", "clear_flag", "terminate", "flag"}
    if action not in valid_actions:
        return api_error("Invalid proctor action.", 400)
    if not reason:
        return api_error("Every proctoring action requires a reason for the audit log.", 400)

    attempt = exam_service.attempt_repo.find_by_id(attempt_id)
    if not attempt:
        return api_error("Exam attempt not found.", 404)

    now = datetime.now(timezone.utc)
    update_fields = {"updated_at": now, "last_proctor_action": action, "last_proctor_reason": reason}

    if action == "clear_flag":
        update_fields["is_flagged"] = False
        update_fields["proctor_status"] = "cleared"
    elif action == "flag":
        update_fields["is_flagged"] = True
        update_fields["proctor_status"] = "flagged"
    elif action == "pause_student":
        update_fields["proctor_status"] = "paused"
    elif action == "extend_time":
        update_fields["extra_minutes"] = int(attempt.get("extra_minutes", 0)) + 15
        update_fields["proctor_status"] = "extended"
    elif action == "send_warning":
        update_fields["proctor_warning"] = reason
        update_fields["proctor_status"] = "warned"
    elif action == "terminate":
        update_fields["is_flagged"] = True
        update_fields["proctor_status"] = "terminated"
        update_fields["status"] = "disqualified"
        update_fields["score"] = 0
        update_fields["percentage"] = 0.0
        update_fields["passed"] = False

    oid = exam_service.attempt_repo.to_object_id(attempt_id)
    exam_service.attempt_repo.collection.update_one(
        {"_id": oid},
        {
            "$set": update_fields,
            "$push": {
                "proctor_events": {
                    "action": action,
                    "reason": reason,
                    "actor": user.get("full_name") or user.get("username"),
                    "timestamp": now.isoformat()
                }
            }
        }
    )

    AuditService().log_event(
        action=f"exam.proctor.{action}",
        actor=user,
        resource_type="exam_attempt",
        resource_id=attempt_id,
        details={
            "student_id": attempt.get("student_id"),
            "exam_id": attempt.get("exam_id"),
            "reason": reason
        },
        request=request
    )

    return api_success({"action": action, "attempt_id": attempt_id}, message=f"Proctor action '{action}' recorded.")
