"""
LearnSphere - Dedicated Portals URL Configuration (Tier 1)
Routes student, educator, and administrator command centers.
"""

from django.urls import path
from apps.portals.views_student import (
    student_dashboard_view,
    daily_quiz_submit_api,
    student_certificate_view
)
from apps.portals.views_educator import (
    educator_studio_view,
    educator_submissions_view,
    educator_grade_override_api,
    educator_students_progress_view,
    educator_submit_report_to_admin_api,
    educator_student_detail_view,
    educator_add_student_note_api
)
from apps.exams.views import educator_proctor_console_view
from apps.portals.views_admin import (
    admin_panel_view,
    admin_approve_educator_api,
    admin_reject_educator_api,
    admin_change_role_api,
    admin_approve_course_api,
    admin_acknowledge_report_api
)

urlpatterns = [
    # Student Portal
    path("student/", student_dashboard_view, name="student_dashboard"),
    path("student/daily-quiz/submit/", daily_quiz_submit_api, name="daily_quiz_submit"),
    path("student/certificate/<str:course_id>/", student_certificate_view, name="student_certificate"),

    # Educator Studio
    path("educator/", educator_studio_view, name="educator_studio"),
    path("educator/students-progress/", educator_students_progress_view, name="educator_students_progress"),
    path("educator/students/<str:student_id>/", educator_student_detail_view, name="educator_student_detail"),
    path("educator/students/<str:student_id>/note/", educator_add_student_note_api, name="educator_student_note"),
    path("educator/proctoring/", educator_proctor_console_view, name="educator_proctor_console"),
    path("educator/reports/submit/", educator_submit_report_to_admin_api, name="educator_submit_report"),
    path("educator/exams/submissions/", educator_submissions_view, name="educator_submissions"),
    path("educator/exams/submissions/<str:attempt_id>/override/", educator_grade_override_api, name="educator_grade_override"),

    # Admin Panel
    path("admin-panel/", admin_panel_view, name="admin_panel"),
    path("admin-panel/educators/<str:user_id>/approve/", admin_approve_educator_api, name="admin_approve_educator"),
    path("admin-panel/educators/<str:user_id>/reject/", admin_reject_educator_api, name="admin_reject_educator"),
    path("admin-panel/users/<str:user_id>/role/", admin_change_role_api, name="admin_change_role"),
    path("admin-panel/courses/<str:course_id>/approve/", admin_approve_course_api, name="admin_approve_course"),
    path("admin-panel/reports/<str:report_id>/acknowledge/", admin_acknowledge_report_api, name="admin_acknowledge_report"),
]
