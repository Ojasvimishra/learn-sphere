"""
LearnSphere - Smart Education Courses & Tracks Views
Interactive curriculum, modules, video lesson player, and educator syllabus authoring studio.
"""

import json
from django.shortcuts import render, redirect
from django.http import Http404, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from services.course_service import CourseService
from services.auth_service import AuthService
from core.permissions import login_required_mongo, role_required_mongo, permission_required_mongo
from core.utils import api_success, api_error

course_service = CourseService()
auth_service = AuthService()


@require_http_methods(["GET"])
def courses_list_view(request):
    level = request.GET.get("level", "all")
    category = request.GET.get("category", "all")
    search = request.GET.get("q", "").strip()

    courses = course_service.get_courses(level=level, category=category, search=search)
    user = getattr(request, "mongo_user", None)
    enrolled_ids = user.get("enrolled_courses", []) if user else []

    return render(request, "pages/courses.html", {
        "courses": courses,
        "selected_level": level,
        "selected_category": category,
        "search_query": search,
        "enrolled_ids": enrolled_ids
    })


@require_http_methods(["GET"])
def course_detail_view(request, course_id):
    course = course_service.get_course_by_id(course_id)
    if not course:
        raise Http404("Course not found")

    user = getattr(request, "mongo_user", None)
    is_enrolled = False
    progress = None

    if user:
        user_id = str(user.get("id"))
        is_enrolled = (course["id"] in user.get("enrolled_courses", []))
        if is_enrolled:
            progress = course_service.get_student_enrollment(user_id, course_id)

    # First lesson link for "Start Learning"
    first_lesson_id = None
    for mod in course.get("modules", []):
        for les in mod.get("lessons", []):
            first_lesson_id = les.get("id")
            break
        if first_lesson_id:
            break

    return render(request, "pages/course_detail.html", {
        "course": course,
        "is_enrolled": is_enrolled,
        "progress": progress,
        "first_lesson_id": first_lesson_id
    })


@require_http_methods(["GET"])
def lesson_player_view(request, course_id, lesson_id):
    user = getattr(request, "mongo_user", None)
    success, msg, context = course_service.get_lesson_context(course_id, lesson_id, user)
    if not success:
        if not user:
            return redirect(f"/auth/login/?next={request.path}")
        return render(request, "pages/course_detail.html", {
            "course": course_service.get_course_by_id(course_id),
            "error_msg": msg
        })

    return render(request, "pages/lesson_player.html", context)


@csrf_exempt
@require_http_methods(["POST"])
@login_required_mongo()
def api_enroll_course(request, course_id):
    user = request.mongo_user
    success = auth_service.enroll_course(user["id"], course_id)
    if success:
        course_service.enroll_student(course_id, user["id"])
        return api_success({"enrolled": True}, message="Successfully enrolled in course!")
    return api_error("Failed to enroll", 400)


@csrf_exempt
@require_http_methods(["POST"])
@login_required_mongo()
def api_complete_lesson(request, course_id, lesson_id):
    user = request.mongo_user
    updated_enrollment = course_service.complete_lesson(user["id"], course_id, lesson_id)
    return api_success(
        {
            "progress_percent": updated_enrollment.get("progress_percent"),
            "completed_lessons": updated_enrollment.get("completed_lessons"),
            "certificate_issued": updated_enrollment.get("certificate_issued", False)
        },
        message="Lesson marked as completed!"
    )


# --- Educator Course Authoring Studio ---

@require_http_methods(["GET"])
@role_required_mongo("educator", "dept_admin", "super_admin")
def educator_courses_list_view(request):
    user = request.mongo_user
    courses = course_service.get_instructor_courses(user["id"])
    return render(request, "pages/educator_courses.html", {
        "courses": courses,
        "user": user
    })


@require_http_methods(["GET", "POST"])
@role_required_mongo("educator", "dept_admin", "super_admin")
def educator_course_create_view(request):
    user = request.mongo_user
    error_msg = None

    if request.method == "POST":
        title = request.POST.get("title", "")
        tagline = request.POST.get("tagline", "")
        description = request.POST.get("description", "")
        level = request.POST.get("level", "Beginner")
        duration_hours = int(request.POST.get("duration_hours", 10) or 10)
        category = request.POST.get("category", "Smart Education")

        success, msg, course_id = course_service.create_course(user, {
            "title": title,
            "tagline": tagline,
            "description": description,
            "level": level,
            "duration_hours": duration_hours,
            "category": category,
            "modules": []
        })

        if success:
            return redirect(f"/courses/{course_id}/")
        else:
            error_msg = msg

    return render(request, "pages/educator_course_create.html", {"error_msg": error_msg})
