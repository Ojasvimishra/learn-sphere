from django.urls import path
from apps.doubts import views

urlpatterns = [
    # Doubts Forum Views
    path("", views.doubts_list_view, name="doubts_list"),
    path("ask/", views.doubt_create_view, name="doubt_create"),
    path("<str:doubt_id>/", views.doubt_detail_view, name="doubt_detail"),

    # REST APIs
    path("api/<str:doubt_id>/answer/", views.api_post_answer, name="api_post_answer"),
    path("api/<str:doubt_id>/upvote/", views.api_toggle_doubt_upvote, name="api_doubt_upvote"),
    path("api/<str:doubt_id>/accept/<str:answer_id>/", views.api_accept_solution, name="api_accept_solution"),

    # AI Tutor
    path("ai/tutor/", views.ai_tutor_view, name="ai_tutor"),
    path("api/ai/query/", views.api_ai_query, name="api_ai_query"),
]
