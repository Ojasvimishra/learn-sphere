from django.urls import path
from apps.live import views

urlpatterns = [
    # Schedule & Timetable
    path("", views.timetable_view, name="timetable"),
    path("schedule/", views.timetable_view, name="live_schedule"),

    # Live Classroom View
    path("room/<str:room_id>/", views.live_room_view, name="live_room"),

    # Educator Studio Live Scheduling
    path("create/", views.educator_create_live_view, name="educator_create_live"),

    # Real-Time Interactions REST APIs
    path("api/room/<str:room_id>/chat/", views.api_room_chat, name="api_room_chat"),
    path("api/room/<str:room_id>/status/", views.api_toggle_stream_status, name="api_stream_status"),
    path("api/room/<str:room_id>/raise-hand/", views.api_raise_hand, name="api_raise_hand"),
]
