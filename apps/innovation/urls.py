from django.urls import path
from apps.innovation import views

urlpatterns = [
    path("", views.innovation_projects_view, name="innovation_projects"),
    path("<str:project_id>/", views.project_detail_view, name="project_detail"),
    path("api/submit/", views.api_submit_project, name="api_submit_project"),
    path("api/<str:project_id>/upvote/", views.api_upvote_project, name="api_upvote_project"),
    path("api/<str:project_id>/comment/", views.api_add_comment, name="api_add_comment"),
]
