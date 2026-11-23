"""
LearnSphere - Automated Test Suite: Phase 2 Live Classes & Timetables
Tests:
1. Live class scheduling by faculty
2. Room creation and room ID lookup
3. Stream lifecycle status changes (scheduled -> live -> completed)
4. In-stream live chat and question filtering
5. Real-time hand-raise interactions
6. Timetable schedule queries
"""

import os
import pytest
import django
from datetime import datetime, timezone, timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "learnsphere.settings")
django.setup()

from database.repositories.live_class_repo import LiveClassRepository, LiveMessageRepository
from services.live_class_service import LiveClassService


@pytest.fixture(autouse=True)
def cleanup_live_classes():
    live_repo = LiveClassRepository()
    msg_repo = LiveMessageRepository()
    live_repo.collection.delete_many({"title": {"$regex": "^TEST_LIVE_"}})
    msg_repo.collection.delete_many({"message": {"$regex": "^TEST_MSG_"}})
    yield
    live_repo.collection.delete_many({"title": {"$regex": "^TEST_LIVE_"}})
    msg_repo.collection.delete_many({"message": {"$regex": "^TEST_MSG_"}})


def test_schedule_live_class():
    """Verifies instructor can schedule live broadcast session with room ID."""
    live_service = LiveClassService()
    instructor = {"id": "inst_sarah", "full_name": "Prof. Sarah Jenkins", "username": "sarah", "role": "educator"}

    start_time = datetime.now(timezone.utc) + timedelta(days=2)
    ok, msg, live_class = live_service.schedule_class(instructor, {
        "title": "TEST_LIVE_ Transformers Deep Dive",
        "description": "Live architectural analysis of Multi-Head Self-Attention in PyTorch.",
        "course_id": "course_ai_101",
        "scheduled_start": start_time,
        "duration_minutes": 90,
        "stream_url": "https://meet.jit.si/learnsphere-test"
    })

    assert ok is True
    assert live_class is not None
    assert live_class["title"] == "TEST_LIVE_ Transformers Deep Dive"
    assert live_class["status"] == "scheduled"
    assert live_class["room_id"].startswith("room_")

    # Fetch by room ID
    room = live_service.get_room_details(live_class["room_id"])
    assert room is not None
    assert room["duration_minutes"] == 90


def test_stream_lifecycle_status_transitions():
    """Verifies instructor can transition class from scheduled to live and completed."""
    live_service = LiveClassService()
    instructor = {"id": "inst_sarah", "username": "sarah", "role": "educator"}
    unauthorized_student = {"id": "student_999", "username": "alex", "role": "student"}

    _, _, live_class = live_service.schedule_class(instructor, {
        "title": "TEST_LIVE_ Graph Neural Networks",
        "description": "Hands-on PyTorch Geometric session.",
        "course_id": "course_gnn",
        "scheduled_start": datetime.now(timezone.utc) + timedelta(hours=1),
        "duration_minutes": 60
    })
    room_id = live_class["room_id"]

    # Student cannot change stream status
    denied, _ = live_service.set_stream_status(room_id, "live", unauthorized_student)
    assert denied is False

    # Instructor starts broadcast -> 'live'
    ok_live, _ = live_service.set_stream_status(room_id, "live", instructor)
    assert ok_live is True
    assert live_service.get_room_details(room_id)["status"] == "live"

    # Instructor finishes broadcast -> 'completed'
    ok_done, _ = live_service.set_stream_status(room_id, "completed", instructor)
    assert ok_done is True
    assert live_service.get_room_details(room_id)["status"] == "completed"


def test_live_chat_and_doubt_questions():
    """Verifies in-room messaging and distinct handling of questions."""
    live_service = LiveClassService()
    instructor = {"id": "inst_sarah", "username": "sarah", "role": "educator"}
    student = {"id": "stud_1", "full_name": "Alex Chen", "username": "alex", "role": "student"}

    _, _, live_class = live_service.schedule_class(instructor, {
        "title": "TEST_LIVE_ Distributed Systems",
        "description": "Consensus protocols.",
        "course_id": "course_dist",
        "scheduled_start": datetime.now(timezone.utc) + timedelta(hours=3),
        "duration_minutes": 45
    })
    room_id = live_class["room_id"]

    # Post normal chat message
    ok1, _, msg1 = live_service.post_chat_message(room_id, student, "TEST_MSG_ Hello everyone!", is_question=False)
    assert ok1 is True
    assert msg1["is_question"] is False

    # Post question / doubt
    ok2, _, msg2 = live_service.post_chat_message(room_id, student, "TEST_MSG_ How does Raft handle network partitions?", is_question=True)
    assert ok2 is True
    assert msg2["is_question"] is True

    # Retrieve history
    history = live_service.get_chat_history(room_id)
    assert len(history) == 2
    assert history[0]["message"] == "TEST_MSG_ Hello everyone!"
    assert history[1]["is_question"] is True


def test_hand_raise_interaction():
    """Verifies attendees can raise hands during active live session."""
    live_service = LiveClassService()
    instructor = {"id": "inst_sarah", "username": "sarah", "role": "educator"}
    student = {"id": "stud_2", "full_name": "Maya Patel", "username": "maya", "role": "student"}

    _, _, live_class = live_service.schedule_class(instructor, {
        "title": "TEST_LIVE_ Bio-Informatics",
        "description": "Sequence alignment algorithms.",
        "course_id": "course_bio",
        "scheduled_start": datetime.now(timezone.utc) + timedelta(hours=5),
        "duration_minutes": 60
    })
    room_id = live_class["room_id"]

    raised = live_service.raise_hand(room_id, student)
    assert raised is True

    room = live_service.get_room_details(room_id)
    assert len(room["hand_raises"]) == 1
    assert room["hand_raises"][0]["user_id"] == "stud_2"
    assert room["hand_raises"][0]["username"] == "Maya Patel"
