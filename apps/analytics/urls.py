from django.urls import path
from apps.analytics import views

urlpatterns = [
    path("", views.home_view, name="home"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("benchmark/", views.benchmark_view, name="benchmark"),
    path("api/benchmark/run/", views.api_benchmark_run, name="api_benchmark_run"),
    path("api/health/", views.api_health_check, name="api_health"),
]
