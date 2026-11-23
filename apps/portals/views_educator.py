"""
LearnSphere - Educator Studio Views (Tier 1)
Delivers comprehensive operations tooling for faculty & educators:
- Course syllabus authoring and publication oversight
- Live class broadcast console and schedule management
- Anti-cheat proctoring audit with manual grade override controls
- Student academic doubt inbox and solution verification
"""

from datetime import datetime, timezone
from django.shortcuts import render, redirect
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from core.permissions import login_required_mongo, portal_access_required, permission_required_mongo
from database.repositories.course_repo import CourseRepository
from database.repositories.live_class_repo import LiveClassRepository
from database.repositories.exam_repo import ExamRepository, ExamSubmissionRepository
from database.repositories.doubt_repo import DoubtRepository
from services.audit_service import AuditService


@login_required_mongo()
@portal_access_required("educator")
def educator_studio_view(request):
    """Unified command studio for teachers, professors, and subject matter experts."""
    user = request.mongo_user
    educator_id = str(user.get("id"))

    course_repo = CourseRepository()
    live_repo = LiveClassRepository()
    exam_repo = ExamRepository()
    exam_sub_repo = ExamSubmissionRepository()
    doubt_repo = DoubtRepository()

    # 1. Authored courses and enrollment metrics
    my_courses = course_repo.list_by_instructor(educator_id)
    total_students_enrolled = sum(c.get("enrolled_count", 0) for c in my_courses)
    published_courses_count = sum(1 for c in my_courses if c.get("status") == "published")
    draft_courses_count = len(my_courses) - published_courses_count

    # 2. Upcoming live classes
    my_live_classes = live_repo.find_many({"instructor_id": educator_id}, sort=[("scheduled_start", -1)], limit=10)

    # 3. Proctored exam submissions requiring review
    all_submissions = exam_sub_repo.list_all_submissions(limit=25)
    flagged_submissions = [s for s in all_submissions if s.get("is_flagged")]

    # 4. Open academic doubts
    open_doubts = doubt_repo.list_doubts(status="open", limit=10)

    context = {
        "user": user,
        "my_courses": my_courses,
        "total_students_enrolled": total_students_enrolled,
        "published_courses_count": published_courses_count,
        "draft_courses_count": draft_courses_count,
        "my_live_classes": my_live_classes,
        "all_submissions": all_submissions,
        "flagged_submissions": flagged_submissions,
        "open_doubts": open_doubts
    }
    return render(request, "portals/educator_studio.html", context)


@login_required_mongo()
@portal_access_required("educator")
def educator_submissions_view(request):
    """Detailed audit list of student exam attempts with anti-cheat telemetry."""
    exam_sub_repo = ExamSubmissionRepository()
    submissions = exam_sub_repo.list_all_submissions(limit=100)

    filter_flagged = request.GET.get("flagged") == "true"
    if filter_flagged:
        submissions = [s for s in submissions if s.get("is_flagged")]

    context = {
        "user": request.mongo_user,
        "submissions": submissions,
        "filter_flagged": filter_flagged
    }
    return render(request, "pages/educator_exam_submissions.html", context)


@login_required_mongo()
@permission_required_mongo("grade.override")
@require_http_methods(["POST"])
def educator_grade_override_api(request, attempt_id):
    """Faculty override for flagged or disputed student grades with mandatory audit logging."""
    user = request.mongo_user
    educator_name = user.get("full_name") or user.get("username", "Educator")

    try:
        new_score = int(request.POST.get("new_score", 0))
        total_marks = int(request.POST.get("total_marks", 100))
        reason = request.POST.get("reason", "").strip()
    except (ValueError, TypeError):
        return JsonResponse({"success": False, "error": "Invalid score or total marks."}, status=400)

    if not reason:
        return JsonResponse({"success": False, "error": "A clear justification reason is mandatory for grade overrides."}, status=400)

    exam_sub_repo = ExamSubmissionRepository()
    attempt = exam_sub_repo.find_by_id(attempt_id)
    if not attempt:
        return JsonResponse({"success": False, "error": "Exam attempt record not found."}, status=404)

    prev_score = attempt.get("score", 0)

    ok = exam_sub_repo.override_grade(
        attempt_id=attempt_id,
        new_score=new_score,
        total_marks=total_marks,
        reason=reason,
        educator_name=educator_name
    )

    if ok:
        # Record immutable audit trail
        audit_service = AuditService()
        audit_service.log_event(
            action="grade.override",
            actor=user,
            resource_type="exam_attempt",
            resource_id=attempt_id,
            details={
                "previous_score": prev_score,
                "new_score": new_score,
                "total_marks": total_marks,
                "reason": reason,
                "student_id": attempt.get("student_id")
            },
            request=request
        )
        return JsonResponse({
            "success": True,
            "message": f"Grade overridden successfully to {new_score}/{total_marks}.",
            "new_score": new_score,
            "percentage": round((new_score / max(1, total_marks)) * 100.0, 1)
        })

    return JsonResponse({"success": False, "error": "Failed to update grade."}, status=500)
