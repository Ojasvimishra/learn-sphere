"""
LearnSphere - Student Portal Views (Tier 1)
Delivers personalized student command center, real-time learning telemetry,
daily server-side quiz XP engine, and verified course completion certificates.
"""

from datetime import datetime, timezone
from django.shortcuts import render, redirect
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from core.permissions import login_required_mongo, portal_access_required
from database.repositories.enrollment_repo import EnrollmentRepository
from database.repositories.course_repo import CourseRepository
from database.repositories.live_class_repo import LiveClassRepository
from database.repositories.doubt_repo import DoubtRepository
from database.repositories.user_repo import UserRepository
from apps.portals.streak_calculator import calculate_real_user_metrics
from apps.portals.daily_quiz_bank import get_daily_question_for_today, evaluate_daily_quiz_answer


@login_required_mongo()
@portal_access_required("student")
def student_dashboard_view(request):
    """Personalized learning center for enrolled students."""
    user = request.mongo_user
    user_id = str(user.get("id"))
    user_repo = UserRepository()

    # Refresh fresh user document
    fresh_user = user_repo.find_by_id(user_id) or user

    # 1. Real activity metrics (calculated from actual database events)
    metrics = calculate_real_user_metrics(fresh_user)

    # 2. Enrolled courses with real-time calculated completion %
    enr_repo = EnrollmentRepository()
    course_repo = CourseRepository()
    enrollments = enr_repo.list_student_enrollments(user_id)

    enrolled_courses = []
    completed_courses = []
    for enr in enrollments:
        cid = enr.get("course_id")
        course = course_repo.find_by_id(cid)
        if course:
            item = {
                "enrollment": enr,
                "course": course,
                "progress_percent": enr.get("progress_percent", 0.0),
                "completed_lessons_count": len(enr.get("completed_lessons", [])),
                "is_completed": enr.get("progress_percent", 0.0) >= 100.0,
                "last_accessed_lesson_id": enr.get("last_accessed_lesson_id")
            }
            enrolled_courses.append(item)
            if item["is_completed"]:
                completed_courses.append(item)

    # 3. Upcoming live classes
    live_repo = LiveClassRepository()
    upcoming_classes = live_repo.list_upcoming(limit=6)

    # 4. Daily Quiz question (answers kept strictly server-side)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    already_completed_quiz = fresh_user.get("last_daily_quiz_date") == today_str
    daily_question = get_daily_question_for_today()

    # 5. Recent academic doubts & peer discussions
    doubt_repo = DoubtRepository()
    recent_doubts = doubt_repo.list_doubts(limit=6)

    context = {
        "user": fresh_user,
        "metrics": metrics,
        "enrolled_courses": enrolled_courses,
        "completed_courses": completed_courses,
        "upcoming_classes": upcoming_classes,
        "daily_question": daily_question,
        "already_completed_quiz": already_completed_quiz,
        "recent_doubts": recent_doubts,
        "today_str": today_str
    }
    return render(request, "portals/student_dashboard.html", context)


@login_required_mongo()
@require_http_methods(["POST"])
def daily_quiz_submit_api(request):
    """
    Evaluates student answer on server, awards 50 XP once per calendar day.
    Never exposes correct answer key beforehand.
    """
    user = request.mongo_user
    user_id = str(user.get("id"))
    question_id = request.POST.get("question_id", "").strip()
    selected_option = request.POST.get("selected_option")

    if selected_option is None or not question_id:
        return JsonResponse({"success": False, "error": "Missing question ID or selected option."}, status=400)

    try:
        opt_idx = int(selected_option)
    except ValueError:
        return JsonResponse({"success": False, "error": "Invalid option index."}, status=400)

    # Server-side validation
    eval_result = evaluate_daily_quiz_answer(question_id, opt_idx)
    if not eval_result["success"]:
        return JsonResponse(eval_result, status=400)

    is_correct = eval_result["correct"]
    xp_awarded = 0
    already_done = False
    total_xp = user.get("xp", 0)

    if is_correct:
        user_repo = UserRepository()
        awarded, xp_delta, new_total = user_repo.award_daily_quiz_xp(user_id, xp_amount=50)
        if awarded:
            xp_awarded = xp_delta
            total_xp = new_total
        else:
            already_done = True
            total_xp = new_total

    return JsonResponse({
        "success": True,
        "correct": is_correct,
        "xp_awarded": xp_awarded,
        "already_done_today": already_done,
        "total_xp": total_xp,
        "explanation": eval_result["explanation"]
    })


@login_required_mongo()
def student_certificate_view(request, course_id):
    """Generates official verified certificate of completion for 100% finished courses."""
    user = request.mongo_user
    user_id = str(user.get("id"))

    enr_repo = EnrollmentRepository()
    course_repo = CourseRepository()

    enrollment = enr_repo.get_enrollment(user_id, course_id)
    course = course_repo.find_by_id(course_id)

    if not course or not enrollment:
        raise Http404("Course enrollment record not found.")

    if enrollment.get("progress_percent", 0.0) < 100.0:
        return render(request, "portals/certificate_ineligible.html", {
            "course": course,
            "enrollment": enrollment
        }, status=403)

    # Issue certificate timestamp if not already recorded
    completed_at = enrollment.get("completed_at") or datetime.now(timezone.utc)
    if isinstance(completed_at, str):
        try:
            completed_at = datetime.fromisoformat(completed_at)
        except Exception:
            completed_at = datetime.now(timezone.utc)

    cert_hash = f"LS-CERT-{str(enrollment.get('_id', ''))[:8].upper()}-{str(course_id)[:6].upper()}"

    context = {
        "user": user,
        "course": course,
        "enrollment": enrollment,
        "completed_at": completed_at,
        "certificate_id": cert_hash
    }
    return render(request, "portals/student_certificate.html", context)
