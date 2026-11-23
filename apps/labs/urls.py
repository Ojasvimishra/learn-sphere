from django.urls import path
from apps.labs import views

urlpatterns = [
    # Catalog of Virtual Coding Labs
    path("", views.labs_list_view, name="labs_list"),
    path("<str:lab_id>/", views.lab_workspace_view, name="lab_workspace"),

    # REST APIs for Code Execution
    path("api/<str:lab_id>/run/", views.api_run_code, name="api_run_code"),
    path("api/<str:lab_id>/submit/", views.api_submit_lab, name="api_submit_lab"),
]
