from django.urls import path
from apps.exams import views

urlpatterns = [
    # Student Views
    path("", views.exams_list_view, name="exams_list"),
    path("<str:exam_id>/take/", views.exam_take_view, name="exam_take"),
    path("attempt/<str:attempt_id>/result/", views.exam_result_view, name="exam_result"),

    # REST APIs for Proctored Execution
    path("api/<str:exam_id>/start/", views.api_exam_start, name="api_exam_start"),
    path("api/attempt/<str:attempt_id>/proctor-event/", views.api_proctor_event, name="api_proctor_event"),
    path("api/attempt/<str:attempt_id>/submit/", views.api_exam_submit, name="api_exam_submit"),

    # Educator Studio Exam Management
    path("educator/create/", views.educator_exam_create_view, name="educator_exam_create"),
    path("educator/<str:exam_id>/submissions/", views.educator_submissions_view, name="educator_exam_submissions"),
    path("api/attempt/<str:attempt_id>/override-grade/", views.api_override_grade, name="api_override_grade"),
]
