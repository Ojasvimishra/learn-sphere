from django.urls import path
from apps.courses import views

urlpatterns = [
    # Student Catalog & Lesson Player
    path("", views.courses_list_view, name="courses_list"),
    path("<str:course_id>/", views.course_detail_view, name="course_detail"),
    path("<str:course_id>/lessons/<str:lesson_id>/", views.lesson_player_view, name="lesson_player"),
    path("api/<str:course_id>/enroll/", views.api_enroll_course, name="api_enroll_course"),
    path("api/<str:course_id>/lessons/<str:lesson_id>/complete/", views.api_complete_lesson, name="api_complete_lesson"),

    # Educator Studio Views
    path("educator/studio/", views.educator_courses_list_view, name="educator_courses"),
    path("educator/create/", views.educator_course_create_view, name="educator_course_create"),
]
