"""
LearnSphere - Administrative Command Center Views (Tier 1)
Delivers comprehensive operations tooling for Super Admins, Department Admins, and Moderators:
- Platform-wide telemetry (users, courses, enrollments, exams, doubts)
- 5-Role user management with strict hierarchical permission controls
- Educator approval queue with instant review/decision actions
- Course publication approval workflow
- Immutable audit log explorer (read-only query interface)
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from core.permissions import login_required_mongo, portal_access_required, permission_required_mongo
from core.rbac import can_manage_user, ALL_ROLES, normalize_role
from database.repositories.user_repo import UserRepository
from database.repositories.course_repo import CourseRepository
from database.repositories.enrollment_repo import EnrollmentRepository
from database.repositories.exam_repo import ExamSubmissionRepository
from database.repositories.doubt_repo import DoubtRepository
from database.repositories.audit_repo import AuditRepository
from services.audit_service import AuditService


@login_required_mongo()
@portal_access_required("admin")
def admin_panel_view(request):
    """Master operations dashboard for administrators and compliance officers."""
    user = request.mongo_user

    user_repo = UserRepository()
    course_repo = CourseRepository()
    enr_repo = EnrollmentRepository()
    exam_sub_repo = ExamSubmissionRepository()
    doubt_repo = DoubtRepository()
    audit_repo = AuditRepository()

    # 1. Platform-wide telemetry metrics
    metrics = {
        "total_users": user_repo.collection.count_documents({}),
        "total_courses": course_repo.collection.count_documents({}),
        "total_enrollments": enr_repo.collection.count_documents({}),
        "total_exam_submissions": exam_sub_repo.collection.count_documents({}),
        "total_doubts": doubt_repo.collection.count_documents({})
    }

    # 2. Users list with role filtering
    role_filter = request.GET.get("role", "all")
    search_query = request.GET.get("q", "").strip()
    users_list = user_repo.list_all_users(role=role_filter, search=search_query, limit=50)

    # 3. Pending Educator Approval Queue
    pending_educators = user_repo.list_pending_educators()

    # 4. Pending / Draft Course Queue
    pending_courses = course_repo.find_many({"status": {"$in": ["draft", "pending_approval"]}}, limit=30)

    # 5. Immutable Audit Logs (Recent 30 entries)
    audit_page = audit_repo.query_logs(page=1, per_page=30)
    audit_logs = audit_page.get("items", [])

    context = {
        "user": user,
        "metrics": metrics,
        "users_list": users_list,
        "pending_educators": pending_educators,
        "pending_courses": pending_courses,
        "audit_logs": audit_logs,
        "available_roles": ALL_ROLES,
        "current_role_filter": role_filter,
        "search_query": search_query
    }
    return render(request, "portals/admin_panel.html", context)


@login_required_mongo()
@permission_required_mongo("user.manage")
@require_http_methods(["POST"])
def admin_approve_educator_api(request, user_id):
    """Approves a pending educator account and writes an immutable audit record."""
    user_repo = UserRepository()
    target = user_repo.find_by_id(user_id)
    if not target:
        return JsonResponse({"success": False, "error": "User not found."}, status=404)

    ok = user_repo.approve_educator(user_id)
    if ok:
        AuditService().log_event(
            action="user.educator_approved",
            actor=request.mongo_user,
            resource_type="user",
            resource_id=user_id,
            details={"approved_username": target.get("username"), "email": target.get("email")},
            request=request
        )
        return JsonResponse({"success": True, "message": f"Educator @{target.get('username')} approved successfully."})

    return JsonResponse({"success": False, "error": "Failed to approve educator."}, status=500)


@login_required_mongo()
@permission_required_mongo("user.manage")
@require_http_methods(["POST"])
def admin_reject_educator_api(request, user_id):
    """Rejects pending educator request, reverting role to student with audit log."""
    user_repo = UserRepository()
    target = user_repo.find_by_id(user_id)
    if not target:
        return JsonResponse({"success": False, "error": "User not found."}, status=404)

    ok = user_repo.reject_educator(user_id)
    if ok:
        AuditService().log_event(
            action="user.educator_rejected",
            actor=request.mongo_user,
            resource_type="user",
            resource_id=user_id,
            details={"rejected_username": target.get("username"), "reverted_to": "student"},
            request=request
        )
        return JsonResponse({"success": True, "message": f"Application rejected. @{target.get('username')} reverted to student."})

    return JsonResponse({"success": False, "error": "Failed to reject educator."}, status=500)


@login_required_mongo()
@permission_required_mongo("user.manage")
@require_http_methods(["POST"])
def admin_change_role_api(request, user_id):
    """Hierarchically changes a user's RBAC role with audit recording."""
    acting_user = request.mongo_user
    user_repo = UserRepository()
    target = user_repo.find_by_id(user_id)
    if not target:
        return JsonResponse({"success": False, "error": "Target user not found."}, status=404)

    new_role = request.POST.get("new_role", "").strip()
    if new_role not in ALL_ROLES:
        return JsonResponse({"success": False, "error": f"Invalid role. Must be one of: {ALL_ROLES}"}, status=400)

    # Check hierarchy
    if not can_manage_user(acting_user, target):
        return JsonResponse({
            "success": False,
            "error": "Forbidden: You cannot modify a user with an equal or higher administrative rank."
        }, status=403)

    old_role = target.get("role")
    ok = user_repo.update_role(user_id, new_role)
    if ok:
        AuditService().log_event(
            action="user.role_changed",
            actor=acting_user,
            resource_type="user",
            resource_id=user_id,
            details={"target_username": target.get("username"), "old_role": old_role, "new_role": new_role},
            request=request
        )
        return JsonResponse({
            "success": True,
            "message": f"Role for @{target.get('username')} updated to '{new_role}'.",
            "new_role": new_role
        })

    return JsonResponse({"success": False, "error": "Failed to update user role."}, status=500)


@login_required_mongo()
@permission_required_mongo("course.approve")
@require_http_methods(["POST"])
def admin_approve_course_api(request, course_id):
    """Reviews and publishes a submitted course curriculum."""
    course_repo = CourseRepository()
    course = course_repo.find_by_id(course_id)
    if not course:
        return JsonResponse({"success": False, "error": "Course not found."}, status=404)

    ok = course_repo.approve_course(course_id)
    if ok:
        AuditService().log_event(
            action="course.approved",
            actor=request.mongo_user,
            resource_type="course",
            resource_id=course_id,
            details={"course_title": course.get("title")},
            request=request
        )
        return JsonResponse({"success": True, "message": f"Course '{course.get('title')}' approved and published."})

    return JsonResponse({"success": False, "error": "Failed to approve course."}, status=500)
