"""
LearnSphere - Live Classes & Timetable Views
Interactive WebRTC/HLS broadcast room, live interactive chat, doubt raising,
and weekly timetable scheduling.
"""

import json
from datetime import datetime, timezone, timedelta
from django.shortcuts import render, redirect
from django.http import Http404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from services.live_class_service import LiveClassService
from services.course_service import CourseService
from core.permissions import login_required_mongo, role_required_mongo
from core.utils import api_success, api_error

live_service = LiveClassService()
course_service = CourseService()


@require_http_methods(["GET"])
def timetable_view(request):
    """Displays weekly timetable of scheduled and ongoing live classes."""
    classes = live_service.get_upcoming_schedule()
    user = getattr(request, "mongo_user", None)

    return render(request, "pages/timetable.html", {
        "classes": classes,
        "user": user,
        "now": datetime.now(timezone.utc)
    })


@require_http_methods(["GET"])
@login_required_mongo()
def live_room_view(request, room_id):
    """Interactive broadcast room with video player, live chat, and Q&A."""
    user = request.mongo_user
    room = live_service.get_room_details(room_id)
    if not room:
        raise Http404("Live classroom not found")

    live_service.live_repo.add_attendee(room_id, user["id"])
    messages = live_service.get_chat_history(room_id)

    is_host = (str(room.get("instructor_id")) == str(user.get("id"))) or (user.get("role") in ["super_admin", "dept_admin"])

    return render(request, "pages/live_room.html", {
        "room": room,
        "messages": messages,
        "is_host": is_host,
        "user": user
    })


@require_http_methods(["GET", "POST"])
@role_required_mongo("educator", "dept_admin", "super_admin")
def educator_create_live_view(request):
    """Allows instructors to schedule a live broadcast session."""
    user = request.mongo_user
    error_msg = None
    courses = course_service.get_instructor_courses(user["id"])

    if request.method == "POST":
        title = request.POST.get("title", "")
        description = request.POST.get("description", "")
        course_id = request.POST.get("course_id", "")
        start_date_str = request.POST.get("start_date", "")
        start_time_str = request.POST.get("start_time", "")
        duration = int(request.POST.get("duration_minutes", 60) or 60)
        stream_url = request.POST.get("stream_url", "")

        try:
            combined_iso = f"{start_date_str}T{start_time_str}:00Z"
            dt = datetime.fromisoformat(combined_iso)
        except Exception:
            dt = datetime.now(timezone.utc) + timedelta(days=1)

        success, msg, live_class = live_service.schedule_class(user, {
            "title": title,
            "description": description,
            "course_id": course_id,
            "scheduled_start": dt,
            "duration_minutes": duration,
            "stream_url": stream_url
        })

        if success:
            return redirect(f"/live/room/{live_class['room_id']}/")
        else:
            error_msg = msg

    return render(request, "pages/educator_live_create.html", {
        "courses": courses,
        "error_msg": error_msg
    })


# --- REST APIs for Live Classroom Interactions ---

@csrf_exempt
@require_http_methods(["GET", "POST"])
@login_required_mongo()
def api_room_chat(request, room_id):
    user = request.mongo_user

    if request.method == "GET":
        messages = live_service.get_chat_history(room_id)
        return api_success(messages)

    try:
        data = json.loads(request.body)
    except Exception:
        data = {}

    msg_text = data.get("message", "")
    is_q = bool(data.get("is_question", False))

    success, msg, saved = live_service.post_chat_message(room_id, user, msg_text, is_question=is_q)
    if not success:
        return api_error(msg, 400)

    return api_success(saved, message="Message sent", status_code=201)


@csrf_exempt
@require_http_methods(["POST"])
@login_required_mongo()
def api_toggle_stream_status(request, room_id):
    user = request.mongo_user
    try:
        data = json.loads(request.body)
    except Exception:
        data = {}

    new_status = data.get("status", "live")
    success, msg = live_service.set_stream_status(room_id, new_status, user)
    if not success:
        return api_error(msg, 403)

    return api_success({"status": new_status}, message=msg)


@csrf_exempt
@require_http_methods(["POST"])
@login_required_mongo()
def api_raise_hand(request, room_id):
    user = request.mongo_user
    live_service.raise_hand(room_id, user)
    return api_success({"raised": True}, message="Hand raised to ask a live doubt.")
