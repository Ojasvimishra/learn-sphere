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
from database.repositories.enrollment_repo import EnrollmentRepository
from database.repositories.user_repo import UserRepository
from database.repositories.report_repo import EducatorReportRepository
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

    # 1. Authored & catalog courses (educators can access and update courses)
    own_courses = course_repo.list_by_instructor(educator_id)
    all_catalog_courses = course_repo.list_courses(status=None)
    seen_cids = {str(c.get("id")) for c in own_courses}
    my_courses = list(own_courses) + [c for c in all_catalog_courses if str(c.get("id")) not in seen_cids]

    total_students_enrolled = sum(c.get("enrolled_count", 0) for c in my_courses)
    published_courses_count = sum(1 for c in my_courses if c.get("status") == "published")
    draft_courses_count = len(my_courses) - published_courses_count

    # 2. Live classes (upcoming/active)
    my_live_classes = live_repo.list_upcoming(limit=20)

    # 3. Proctored exams & submissions requiring review
    proctored_exams = exam_repo.find_many({}, sort=[("created_at", -1)], limit=20)
    all_submissions = exam_sub_repo.list_all_submissions(limit=30)
    flagged_submissions = [s for s in all_submissions if s.get("is_flagged")]

    # 4. At-risk students derived from flagged/low-score submissions & low-progress enrollments
    at_risk_map = {}
    for s in all_submissions:
        sid = str(s.get("student_id", ""))
        if not sid:
            continue
        if s.get("is_flagged") or float(s.get("percentage", 100)) < 50.0:
            if sid not in at_risk_map:
                sname = s.get("student_name") or "Student"
                reason = "Flagged exam anomaly" if s.get("is_flagged") else f"Low exam score ({s.get('percentage', 0)}%)"
                at_risk_map[sid] = {
                    "id": sid,
                    "name": sname,
                    "initials": "".join(p[0].upper() for p in sname.split()[:2]) or "ST",
                    "reason": reason
                }
    at_risk_students = list(at_risk_map.values())[:6]

    # 5. Open academic doubts
    open_doubts = doubt_repo.list_doubts(status="open", limit=10)

    # 6. Reports & updates sent to admin
    report_repo = EducatorReportRepository()
    my_reports = report_repo.list_by_educator(educator_id, limit=10)

    context = {
        "user": user,
        "my_courses": my_courses,
        "total_students_enrolled": total_students_enrolled,
        "published_courses_count": published_courses_count,
        "draft_courses_count": draft_courses_count,
        "my_live_classes": my_live_classes,
        "proctored_exams": proctored_exams,
        "all_submissions": all_submissions,
        "flagged_submissions": flagged_submissions,
        "at_risk_students": at_risk_students,
        "open_doubts": open_doubts,
        "my_reports": my_reports,
        "today_date": datetime.now(timezone.utc)
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


@login_required_mongo()
@portal_access_required("educator")
def educator_students_progress_view(request):
    """Visual dashboard for faculty to track student course completion rates, active lessons, and certificates."""
    user = request.mongo_user
    educator_id = str(user.get("id"))

    course_repo = CourseRepository()
    enr_repo = EnrollmentRepository()
    user_repo = UserRepository()

    own_courses = course_repo.list_by_instructor(educator_id)
    all_catalog = course_repo.list_courses(status=None)
    seen_ids = {str(c["id"]) for c in own_courses}
    my_courses = list(own_courses) + [c for c in all_catalog if str(c["id"]) not in seen_ids]
    course_map = {str(c["id"]): c for c in my_courses}
    course_ids = list(course_map.keys())

    selected_course_id = request.GET.get("course_id", "all")
    search_query = request.GET.get("q", "").strip().lower()

    if selected_course_id != "all" and selected_course_id in course_map:
        enrollments = enr_repo.list_by_course(selected_course_id)
    else:
        enrollments = enr_repo.list_by_course_ids(course_ids)

    # Enrich enrollment records with student data
    students_data = []
    user_cache = {}

    for enr in enrollments:
        uid = enr.get("user_id")
        if uid not in user_cache:
            user_cache[uid] = user_repo.find_by_id(uid)
        u = user_cache[uid]

        student_name = (u.get("full_name") or u.get("username", "Student")) if u else "Student"
        student_email = u.get("email", "") if u else ""
        student_username = u.get("username", "") if u else ""

        # Search filter
        if search_query:
            match_name = search_query in student_name.lower()
            match_email = search_query in student_email.lower()
            match_user = search_query in student_username.lower()
            if not (match_name or match_email or match_user):
                continue

        c_info = course_map.get(str(enr.get("course_id")), {})
        total_lessons = c_info.get("lessons_count", 0)
        completed_lessons = len(enr.get("completed_lessons", []))
        pct = enr.get("progress_percent", 0.0)

        students_data.append({
            "id": enr.get("id"),
            "student_id": uid,
            "student_name": student_name,
            "student_username": student_username,
            "student_email": student_email,
            "course_id": enr.get("course_id"),
            "course_title": c_info.get("title", "Curriculum"),
            "total_lessons": total_lessons,
            "completed_lessons": completed_lessons,
            "progress_percent": pct,
            "enrolled_at": enr.get("enrolled_at"),
            "last_accessed_at": enr.get("last_accessed_at"),
            "completed_at": enr.get("completed_at"),
            "is_completed": pct >= 100.0 or bool(enr.get("completed_at"))
        })

    # Summary metrics
    total_enrolled = len(students_data)
    completed_count = sum(1 for s in students_data if s["is_completed"])
    in_progress_count = total_enrolled - completed_count
    avg_progress = round(sum(s["progress_percent"] for s in students_data) / max(1, total_enrolled), 1)

    context = {
        "user": user,
        "my_courses": my_courses,
        "selected_course_id": selected_course_id,
        "search_query": search_query,
        "students": students_data,
        "total_enrolled": total_enrolled,
        "completed_count": completed_count,
        "in_progress_count": in_progress_count,
        "avg_progress": avg_progress
    }
    return render(request, "portals/educator_students_progress.html", context)


@login_required_mongo()
@portal_access_required("educator")
@require_http_methods(["POST"])
def educator_submit_report_to_admin_api(request):
    """Allows educators to dispatch academic reports, exam cheating alerts, or course approvals to the Admin Center."""
    user = request.mongo_user
    educator_id = str(user.get("id"))
    educator_name = user.get("full_name") or user.get("username", "Educator")
    educator_email = user.get("email", "")

    title = request.POST.get("title", "").strip()
    message = request.POST.get("message", "").strip()
    report_type = request.POST.get("report_type", "general_update").strip()
    course_id = request.POST.get("course_id", "").strip() or None
    priority = request.POST.get("priority", "normal").strip()

    if not title or not message:
        return JsonResponse({"success": False, "error": "Title and detailed message are required."}, status=400)

    course_title = None
    if course_id:
        c = CourseRepository().find_by_id(course_id)
        if c:
            course_title = c.get("title")

    report_repo = EducatorReportRepository()
    report_id = report_repo.create_report(
        educator_id=educator_id,
        educator_name=educator_name,
        educator_email=educator_email,
        report_type=report_type,
        title=title,
        message=message,
        course_id=course_id,
        course_title=course_title,
        priority=priority
    )

    # Log immutable audit event
    AuditService().log_event(
        action="educator.report_submitted",
        actor=user,
        resource_type="educator_report",
        resource_id=report_id,
        details={
            "report_type": report_type,
            "title": title,
            "course_title": course_title,
            "priority": priority
        },
        request=request
    )

    return JsonResponse({
        "success": True,
        "message": "Report successfully dispatched to the Administrative Command Center.",
        "report_id": report_id
    })


@login_required_mongo()
@portal_access_required("educator")
def educator_student_detail_view(request, student_id):
    """Comprehensive single-student academic profile for educators: progress, quizzes, doubts, and notes."""
    user_repo = UserRepository()
    student = user_repo.find_by_id(student_id)
    if not student:
        raise Http404("Student not found")

    enr_repo = EnrollmentRepository()
    course_repo = CourseRepository()
    exam_sub_repo = ExamSubmissionRepository()
    doubt_repo = DoubtRepository()

    enrollments = enr_repo.find_many({"user_id": str(student_id)})
    course_progress = []
    for enr in enrollments:
        c = course_repo.find_by_id(str(enr.get("course_id")))
        course_progress.append({
            "course_id": str(enr.get("course_id")),
            "course_title": c.get("title", "Course Track") if c else "Course Track",
            "category": c.get("category", "General") if c else "General",
            "progress_percent": round(float(enr.get("progress_percent", 0.0)), 1),
            "completed_lessons": len(enr.get("completed_lessons", [])),
            "total_lessons": c.get("lessons_count", 0) if c else 0
        })

    submissions = exam_sub_repo.find_many({"student_id": str(student_id)}, sort=[("submitted_at", -1)], limit=15)
    avg_score = round(sum(float(s.get("percentage", 0)) for s in submissions) / max(1, len(submissions)), 1) if submissions else 0.0
    flagged_count = sum(1 for s in submissions if s.get("is_flagged"))

    doubts = doubt_repo.find_many({"author_id": str(student_id)}, sort=[("created_at", -1)], limit=10)
    resolved_doubts = sum(1 for d in doubts if d.get("status") == "resolved")

    sname = student.get("full_name") or student.get("username", "Student")
    initials = "".join(p[0].upper() for p in sname.split()[:2]) or "ST"
    notes = student.get("educator_notes", [])

    return render(request, "portals/educator_student_detail.html", {
        "user": request.mongo_user,
        "student": student,
        "student_name": sname,
        "student_initials": initials,
        "course_progress": course_progress,
        "submissions": submissions,
        "avg_score": avg_score,
        "flagged_count": flagged_count,
        "doubts_count": len(doubts),
        "resolved_doubts": resolved_doubts,
        "notes": notes,
        "is_at_risk": flagged_count > 0 or (submissions and avg_score < 50.0)
    })


@login_required_mongo()
@portal_access_required("educator")
@require_http_methods(["POST"])
def educator_add_student_note_api(request, student_id):
    """Persists an educator-only observation note or nudge on a student's profile."""
    user = request.mongo_user
    note_text = (request.POST.get("note") or "").strip()
    action_type = (request.POST.get("type") or "note").strip()
    if not note_text:
        return JsonResponse({"success": False, "error": "Note text cannot be empty."}, status=400)

    user_repo = UserRepository()
    student = user_repo.find_by_id(student_id)
    if not student:
        return JsonResponse({"success": False, "error": "Student not found."}, status=404)

    now = datetime.now(timezone.utc)
    entry = {
        "author": user.get("full_name") or user.get("username", "Educator"),
        "type": action_type,
        "text": note_text,
        "created_at": now.strftime("%b %d, %Y %H:%M UTC")
    }
    oid = user_repo.to_object_id(student_id)
    user_repo.collection.update_one({"_id": oid}, {"$push": {"educator_notes": entry}})

    AuditService().log_event(
        action=f"educator.student_{action_type}",
        actor=user,
        resource_type="student",
        resource_id=student_id,
        details={"note": note_text},
        request=request
    )
    return JsonResponse({"success": True, "entry": entry})
