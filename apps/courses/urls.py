from django.urls import path
from apps.courses import views

urlpatterns = [
    path("", views.courses_list_view, name="courses_list"),
    path("<str:course_id>/", views.course_detail_view, name="course_detail"),
    path("api/<str:course_id>/enroll/", views.api_enroll_course, name="api_enroll_course"),
]
