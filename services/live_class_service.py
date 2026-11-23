"""
LearnSphere - Live Class & Timetable Scheduling Service (Tier 2)
Orchestrates live broadcast sessions, calendar timetables, live chat questions,
and attendee presence.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from database.repositories.live_class_repo import LiveClassRepository, LiveMessageRepository
from database.repositories.course_repo import CourseRepository
from core.validation import validate_string, ValidationError


class LiveClassService:
    def __init__(self):
        self.live_repo = LiveClassRepository()
        self.msg_repo = LiveMessageRepository()
        self.course_repo = CourseRepository()

    def schedule_class(
        self,
        instructor: Dict[str, Any],
        data: Dict[str, Any]
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        try:
            title = validate_string(data.get("title"), "title", min_length=5, max_length=150)
            desc = validate_string(data.get("description", ""), "description", min_length=10, max_length=1000)
            course_id = validate_string(data.get("course_id"), "course_id")
        except ValidationError as e:
            return False, e.message, None

        course = self.course_repo.find_by_id(course_id)
        course_title = course.get("title") if course else "General Academic Workshop"

        start_time = data.get("scheduled_start")
        if isinstance(start_time, str):
            try:
                start_time = datetime.fromisoformat(start_time)
            except Exception:
                start_time = datetime.now(timezone.utc) + timedelta(hours=1)
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)

        duration = int(data.get("duration_minutes", 60))

        class_id = self.live_repo.create_live_class(
            title=title,
            description=desc,
            course_id=course_id,
            course_title=course_title,
            instructor_id=str(instructor.get("id")),
            instructor_name=instructor.get("full_name") or instructor.get("username", "Faculty"),
            scheduled_start=start_time,
            duration_minutes=duration,
            stream_url=data.get("stream_url", "")
        )

        created_class = self.live_repo.find_by_id(class_id)
        return True, "Live class successfully scheduled.", created_class

    def get_room_details(self, room_id: str) -> Optional[Dict[str, Any]]:
        return self.live_repo.find_by_room_id(room_id)

    def get_upcoming_schedule(self) -> List[Dict[str, Any]]:
        return self.live_repo.list_upcoming(limit=30)

    def get_instructor_schedule(self, instructor_id: str) -> List[Dict[str, Any]]:
        return self.live_repo.list_by_instructor(instructor_id)

    def set_stream_status(self, room_id: str, new_status: str, acting_user: Dict[str, Any]) -> Tuple[bool, str]:
        room = self.live_repo.find_by_room_id(room_id)
        if not room:
            return False, "Room not found"

        role = acting_user.get("role")
        user_id = str(acting_user.get("id"))
        is_owner = str(room.get("instructor_id")) == user_id
        is_admin = role in ["super_admin", "dept_admin"]

        if not is_owner and not is_admin:
            return False, "Permission denied: Only the scheduled instructor or administrator can alter stream state."

        if new_status not in ["scheduled", "live", "completed", "cancelled"]:
            return False, "Invalid status value"

        self.live_repo.update_status(room_id, new_status)
        return True, f"Stream status changed to {new_status}"

    def post_chat_message(
        self,
        room_id: str,
        user: Dict[str, Any],
        message: str,
        is_question: bool = False
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        clean_text = (message or "").strip()
        if not clean_text:
            return False, "Message cannot be empty", None

        msg_id = self.msg_repo.insert_message(
            room_id=room_id,
            sender_id=str(user.get("id")),
            sender_name=user.get("full_name") or user.get("username", "Student"),
            sender_role=user.get("role", "student"),
            message=clean_text[:500],
            is_question=is_question
        )
        saved = self.msg_repo.find_by_id(msg_id)
        return True, "Message sent", saved

    def get_chat_history(self, room_id: str) -> List[Dict[str, Any]]:
        return self.msg_repo.list_room_messages(room_id, limit=100)

    def raise_hand(self, room_id: str, user: Dict[str, Any]) -> bool:
        user_id = str(user.get("id"))
        name = user.get("full_name") or user.get("username", "Student")
        return self.live_repo.toggle_hand_raise(room_id, user_id, name)
