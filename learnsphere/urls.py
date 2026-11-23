"""
LearnSphere URL Configuration
Root routing connecting presentation tier views and REST endpoints.
"""

from django.urls import path, include
from apps.analytics.views import home_view

urlpatterns = [
    path("", home_view, name="home"),
    path("", include("apps.analytics.urls")),
    path("auth/", include("apps.authentication.urls")),
    path("resources/", include("apps.resources.urls")),
    path("innovation/", include("apps.innovation.urls")),
    path("courses/", include("apps.courses.urls")),
    path("live/", include("apps.live.urls")),
    path("exams/", include("apps.exams.urls")),
    path("labs/", include("apps.labs.urls")),
]
