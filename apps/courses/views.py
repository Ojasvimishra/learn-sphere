"""
LearnSphere - Smart Education Courses & Tracks Views
Interactive curriculum, modules, and enrollment workflows.
"""

from django.shortcuts import render, redirect
from django.http import Http404
from django.views.decorators.http import require_http_methods
from services.course_service import CourseService
from services.auth_service import AuthService
from core.permissions import login_required_mongo
from core.utils import api_success, api_error

course_service = CourseService()
auth_service = AuthService()


@require_http_methods(["GET"])
def courses_list_view(request):
    level = request.GET.get("level", "all")
    courses = course_service.get_courses(level=level)
    user = getattr(request, "mongo_user", None)
    enrolled_ids = user.get("enrolled_courses", []) if user else []

    return render(request, "pages/courses.html", {
        "courses": courses,
        "selected_level": level,
        "enrolled_ids": enrolled_ids
    })


@require_http_methods(["GET"])
def course_detail_view(request, course_id):
    course = course_service.get_course_by_id(course_id)
    if not course:
        raise Http404("Course not found")

    user = getattr(request, "mongo_user", None)
    is_enrolled = (course["id"] in user.get("enrolled_courses", [])) if user else False

    return render(request, "pages/course_detail.html", {
        "course": course,
        "is_enrolled": is_enrolled
    })


@require_http_methods(["POST"])
@login_required_mongo()
def api_enroll_course(request, course_id):
    user = request.mongo_user
    success = auth_service.enroll_course(user["id"], course_id)
    if success:
        course_service.enroll_student(course_id, user["id"])
        return api_success({"enrolled": True}, message="Successfully enrolled in course!")
    return api_error("Failed to enroll", 400)
