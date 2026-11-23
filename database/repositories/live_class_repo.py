"""
LearnSphere - Live Classes & Real-Time Broadcast Repository (Tier 3)
Manages scheduled live lectures, WebRTC/HLS room IDs, attendance rosters,
and in-class live discussions.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from database.repositories.base import BaseRepository


class LiveClassRepository(BaseRepository):
    def __init__(self):
        super().__init__("live_classes")

    def create_live_class(
        self,
        title: str,
        description: str,
        course_id: str,
        course_title: str,
        instructor_id: str,
        instructor_name: str,
        scheduled_start: datetime,
        duration_minutes: int = 60,
        stream_url: str = "",
        room_id: Optional[str] = None
    ) -> str:
        now = datetime.now(timezone.utc)
        clean_room = room_id or f"room_{uuid.uuid4().hex[:10]}"

        doc = {
            "title": title.strip(),
            "description": description.strip(),
            "course_id": str(course_id),
            "course_title": course_title.strip(),
            "instructor_id": str(instructor_id),
            "instructor_name": instructor_name.strip(),
            "scheduled_start": scheduled_start,
            "scheduled_end": scheduled_start + timedelta(minutes=duration_minutes),
            "duration_minutes": duration_minutes,
            "room_id": clean_room,
            "stream_url": stream_url.strip(),
            "status": "scheduled",  # scheduled, live, completed, cancelled
            "attendees_count": 0,
            "active_viewers": [],
            "chat_enabled": True,
            "hand_raises": [],
            "created_at": now,
            "updated_at": now
        }
        return self.insert_one(doc)

    def find_by_room_id(self, room_id: str) -> Optional[Dict[str, Any]]:
        return self.find_one({"room_id": str(room_id).strip()})

    def list_upcoming(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Returns scheduled and active live classes ordered by start time."""
        now = datetime.now(timezone.utc)
        return self.find_many(
            {"status": {"$in": ["scheduled", "live"]}},
            sort=[("scheduled_start", 1)],
            limit=limit
        )

    def list_by_instructor(self, instructor_id: str) -> List[Dict[str, Any]]:
        return self.find_many(
            {"instructor_id": str(instructor_id)},
            sort=[("scheduled_start", -1)],
            limit=50
        )

    def list_by_course(self, course_id: str) -> List[Dict[str, Any]]:
        return self.find_many(
            {"course_id": str(course_id)},
            sort=[("scheduled_start", 1)]
        )

    def update_status(self, room_id: str, status: str) -> bool:
        oid_doc = self.find_by_room_id(room_id)
        if not oid_doc:
            return False
        return self.update_one(
            {"_id": self.to_object_id(oid_doc["id"])},
            {"status": status, "updated_at": datetime.now(timezone.utc)}
        )

    def add_attendee(self, room_id: str, user_id: str) -> bool:
        doc = self.find_by_room_id(room_id)
        if not doc:
            return False
        oid = self.to_object_id(doc["id"])
        self.collection.update_one(
            {"_id": oid},
            {"$addToSet": {"active_viewers": str(user_id)}, "$inc": {"attendees_count": 1}}
        )
        return True

    def toggle_hand_raise(self, room_id: str, user_id: str, username: str) -> bool:
        doc = self.find_by_room_id(room_id)
        if not doc:
            return False
        oid = self.to_object_id(doc["id"])
        hand = {"user_id": str(user_id), "username": username, "raised_at": datetime.now(timezone.utc).isoformat()}
        self.collection.update_one(
            {"_id": oid},
            {"$addToSet": {"hand_raises": hand}}
        )
        return True


class LiveMessageRepository(BaseRepository):
    def __init__(self):
        super().__init__("live_messages")

    def insert_message(
        self,
        room_id: str,
        sender_id: str,
        sender_name: str,
        sender_role: str,
        message: str,
        is_question: bool = False
    ) -> str:
        now = datetime.now(timezone.utc)
        doc = {
            "room_id": str(room_id),
            "sender_id": str(sender_id),
            "sender_name": sender_name.strip(),
            "sender_role": sender_role,
            "message": message.strip(),
            "is_question": is_question,
            "timestamp": now
        }
        return self.insert_one(doc)

    def list_room_messages(self, room_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        return self.find_many({"room_id": str(room_id)}, sort=[("timestamp", 1)], limit=limit)
