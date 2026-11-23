"""
LearnSphere - Automated Test Suite: Phase 3 Quizzes, Proctored Exams & Anti-Cheat
Tests:
1. Exam creation with question bank and marks
2. Client-side answer leakage prevention (sanitized questions without answer keys)
3. Anti-cheat proctor telemetry logging (tab_hidden, window_blur)
4. Server-side grading verification
5. Anomaly threshold flagging when tab switches > limit
6. Faculty grade override with mandatory audit log trail
"""

import os
import pytest
import django
from datetime import datetime, timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "learnsphere.settings")
django.setup()

from database.repositories.exam_repo import ExamRepository, ExamAttemptRepository
from database.repositories.audit_repo import AuditRepository
from database.repositories.user_repo import UserRepository
from services.exam_service import ExamService


@pytest.fixture(autouse=True)
def cleanup_test_exams():
    exam_repo = ExamRepository()
    att_repo = ExamAttemptRepository()
    user_repo = UserRepository()
    exam_repo.collection.delete_many({"title": {"$regex": "^TEST_EXAM_"}})
    att_repo.collection.delete_many({"exam_title": {"$regex": "^TEST_EXAM_"}})
    user_repo.collection.delete_many({"username": {"$regex": "^test_exam_"}})
    yield
    exam_repo.collection.delete_many({"title": {"$regex": "^TEST_EXAM_"}})
    att_repo.collection.delete_many({"exam_title": {"$regex": "^TEST_EXAM_"}})
    user_repo.collection.delete_many({"username": {"$regex": "^test_exam_"}})


def test_exam_creation_and_taker_payload_sanitization():
    """
    SECURITY CRITICAL TEST:
    Ensures that when a student fetches questions for an exam attempt,
    correct_option_index and answers are STRIPPED from the returned payload.
    """
    exam_service = ExamService()
    instructor = {"id": "inst_1", "username": "prof_sarah", "role": "educator"}
    student = {"id": "stud_1", "username": "alex", "email": "alex@learnsphere.io", "role": "student"}

    questions = [
        {
            "id": "q1",
            "text": "What is the primary advantage of Argon2id?",
            "type": "single_choice",
            "options": ["Memory hardness", "Shorter string", "Faster computation"],
            "correct_option_index": 0,
            "marks": 10,
            "explanation": "Argon2id resists GPU/ASIC parallel cracking."
        },
        {
            "id": "q2",
            "text": "Which component manages rate limiting in LearnSphere?",
            "type": "single_choice",
            "options": ["Postgres", "Redis", "Nginx"],
            "correct_option_index": 1,
            "marks": 10,
            "explanation": "Redis provides high-throughput in-memory sliding window counters."
        }
    ]

    ok, _, exam_id = exam_service.create_exam(instructor, {
        "title": "TEST_EXAM_ Enterprise Security",
        "course_id": "course_sec_101",
        "duration_minutes": 30,
        "questions": questions,
        "tab_switch_limit": 2
    })
    assert ok is True

    # Student starts exam and fetches questions
    ok_fetch, _, payload = exam_service.get_exam_taker_payload(exam_id, student)
    assert ok_fetch is True
    assert "questions" in payload
    assert len(payload["questions"]) == 2

    for q in payload["questions"]:
        # Verify secret keys are NEVER sent to student client
        assert "correct_option_index" not in q
        assert "explanation" not in q
        assert "options" in q
        assert "text" in q


def test_server_side_grading_and_evaluation():
    """Tests that student submissions are evaluated strictly server-side."""
    exam_service = ExamService()
    instructor = {"id": "inst_1", "username": "prof", "role": "educator"}
    student = {"id": "stud_2", "username": "maya", "role": "student"}

    questions = [
        {"id": "q_a", "text": "Q1", "options": ["A", "B"], "correct_option_index": 0, "marks": 20},
        {"id": "q_b", "text": "Q2", "options": ["C", "D"], "correct_option_index": 1, "marks": 30}
    ]

    _, _, exam_id = exam_service.create_exam(instructor, {
        "title": "TEST_EXAM_ Discrete Logic",
        "course_id": "course_cs",
        "duration_minutes": 20,
        "questions": questions
    })

    _, _, payload = exam_service.get_exam_taker_payload(exam_id, student)
    attempt_id = payload["attempt_id"]

    # Student answers Q1 correctly (0) and Q2 incorrectly (0 instead of 1)
    student_answers = {"q_a": 0, "q_b": 0}

    ok_submit, _, result = exam_service.submit_and_evaluate_exam(attempt_id, student, student_answers)
    assert ok_submit is True
    assert result["score"] == 20  # 20 marks for q_a, 0 for q_b
    assert result["total_marks"] == 50
    assert result["percentage"] == 40.0
    assert result["passed"] is False  # Requires 60%


def test_anti_cheat_proctor_flagging():
    """Verifies that exceeding the tab switch limit marks the attempt as flagged for review."""
    exam_service = ExamService()
    instructor = {"id": "inst_1", "username": "prof", "role": "educator"}
    student = {"id": "stud_cheater", "username": "cheater", "role": "student"}

    questions = [
        {"id": "q1", "text": "Q1", "options": ["A", "B"], "correct_option_index": 0, "marks": 50}
    ]

    _, _, exam_id = exam_service.create_exam(instructor, {
        "title": "TEST_EXAM_ Strict Proctor",
        "course_id": "course_law",
        "duration_minutes": 15,
        "questions": questions,
        "tab_switch_limit": 2
    })

    _, _, payload = exam_service.get_exam_taker_payload(exam_id, student)
    attempt_id = payload["attempt_id"]

    # Student switches tabs 3 times (limit is 2)
    for _ in range(3):
        exam_service.record_proctor_event(attempt_id, student, "tab_hidden", {"url": "https://google.com"})

    # Submit
    _, _, result = exam_service.submit_and_evaluate_exam(attempt_id, student, {"q1": 0})
    assert result["tab_switches"] == 3
    assert result["is_flagged"] is True  # FLAGGED FOR FACULTY AUDIT


def test_faculty_grade_override_and_audit_trail():
    """Verifies faculty can override grade and action is permanently recorded in immutable audit log."""
    exam_service = ExamService()
    audit_repo = AuditRepository()
    instructor = {"id": "inst_overrider", "full_name": "Prof. Charles", "username": "charles", "role": "educator"}
    student = {"id": "stud_review", "username": "bob", "role": "student"}

    questions = [
        {"id": "q1", "text": "Q1", "options": ["A", "B"], "correct_option_index": 0, "marks": 100}
    ]

    _, _, exam_id = exam_service.create_exam(instructor, {
        "title": "TEST_EXAM_ Grade Override Test",
        "course_id": "course_math",
        "duration_minutes": 30,
        "questions": questions
    })

    _, _, payload = exam_service.get_exam_taker_payload(exam_id, student)
    attempt_id = payload["attempt_id"]

    # Student got 0
    exam_service.submit_and_evaluate_exam(attempt_id, student, {"q1": 1})

    # Faculty overrides grade to 85 due to valid justification
    ok_ov, _ = exam_service.override_student_grade(attempt_id, instructor, 85, "Alternative valid proof provided.")
    assert ok_ov is True

    # Check updated attempt
    updated_attempt = exam_service.attempt_repo.find_by_id(attempt_id)
    assert updated_attempt["score"] == 85
    assert updated_attempt["grade_overridden"] is True
    assert updated_attempt["override_reason"] == "Alternative valid proof provided."

    # Check immutable audit logs
    audit_events = audit_repo.find_many({"action": "grade.override", "resource_id": f"stud_review:{exam_id}"})
    assert len(audit_events) > 0
    assert audit_events[0]["details"]["new_grade"] == 85


def test_exam_take_view_renders_cleanly_for_student():
    """Verifies that the /exams/<id>/take/ view renders 200 without JSON/datetime serialization errors."""
    from django.test import Client
    from database.repositories.user_repo import UserRepository
    from django.conf import settings

    exam_service = ExamService()
    user_repo = UserRepository()

    instructor = {"id": "inst_render", "username": "prof_render", "role": "educator"}
    ok, _, exam_id = exam_service.create_exam(instructor, {
        "title": "TEST_EXAM_ Rendering Validation",
        "course_id": "course_render",
        "duration_minutes": 25,
        "questions": [{"id": "q1", "text": "Is this working?", "options": ["Yes", "No"], "correct_option_index": 0, "marks": 10}]
    })
    assert ok is True

    # Authenticate student via session
    student = user_repo.create_user(
        username="test_exam_student_taker",
        email="test_exam_student_taker@learnsphere.io",
        raw_password="TestPassword@123!",
        role="student"
    )

    client = Client()
    s = client.session
    s["mongo_user_id"] = str(student["id"])
    s.save()
    client.cookies[settings.SESSION_COOKIE_NAME] = s.session_key

    resp = client.get(f"/exams/{exam_id}/take/")
    assert resp.status_code == 200
    assert "TEST_EXAM_ Rendering Validation" in resp.content.decode("utf-8")
    assert "Time Remaining" in resp.content.decode("utf-8")

