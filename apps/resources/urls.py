from django.urls import path
from apps.resources import views

urlpatterns = [
    path("", views.resources_list_view, name="resources_list"),
    path("<str:resource_id>/", views.resource_detail_view, name="resource_detail"),
    path("api/search/", views.api_resources_search, name="api_resources_search"),
    path("api/<str:resource_id>/bookmark/", views.api_resource_bookmark, name="api_resource_bookmark"),
]
