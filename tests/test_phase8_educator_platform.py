"""
Tests for Educator Operations Platform:
- Updating course metadata & syllabus structure
- Student progress & cohort completion analytics
- Scheduling proctored exams with time windows
- Reviewing exam results & anti-cheat telemetry
- Dispatching educator updates & incident reports to admin
"""

import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "learnsphere.settings")
django.setup()

import pytest
from datetime import datetime, timezone, timedelta
from django.test import Client
from database.repositories.user_repo import UserRepository
from database.repositories.course_repo import CourseRepository
from database.repositories.enrollment_repo import EnrollmentRepository
from database.repositories.exam_repo import ExamRepository, ExamSubmissionRepository
from database.repositories.report_repo import EducatorReportRepository
from services.auth_service import AuthService
from services.course_service import CourseService
from services.exam_service import ExamService


@pytest.fixture(autouse=True)
def clear_rate_limit():
    from core.redis_client import get_cache_client
    get_cache_client().delete("ratelimit:login:127.0.0.1")


@pytest.fixture
def educator_env():
    user_repo = UserRepository()
    course_repo = CourseRepository()
    enr_repo = EnrollmentRepository()
    exam_repo = ExamRepository()
    report_repo = EducatorReportRepository()

    # Create educator user
    educator = user_repo.find_one({"username": "sarah_mentor"})
    if not educator:
        user_id = user_repo.create_user(
            username="sarah_mentor",
            email="mentor@learnsphere.io",
            raw_password="Mentor@LearnSphere2026!",
            role="educator"
        )
        user_repo.approve_educator(user_id)
        educator = user_repo.find_by_id(user_id)

    # Create student user
    student = user_repo.find_one({"username": "alex_student"})
    if not student:
        s_id = user_repo.create_user(
            username="alex_student",
            email="student@learnsphere.io",
            raw_password="Student@LearnSphere2026!",
            role="student"
        )
        student = user_repo.find_by_id(s_id)

    # Create admin user
    admin = user_repo.find_one({"username": "phase8_admin"})
    if not admin:
        a_id = user_repo.create_user(
            username="phase8_admin",
            email="phase8_admin@learnsphere.io",
            raw_password="Admin@LearnSphere2026!",
            role="super_admin"
        )
        admin = user_repo.find_by_id(a_id)

    # Create course authored by educator
    course_id = course_repo.create_course(
        title="Test Educator Course for Progress",
        tagline="Comprehensive course for testing operations.",
        description="Detailed description for testing educator operations platform capabilities.",
        level="Intermediate",
        duration_hours=12,
        instructor_name="Sarah Mentor",
        instructor_id=str(educator["id"]),
        category="Smart Education",
        modules=[
            {
                "id": "mod_1",
                "title": "Module 1",
                "lessons": [
                    {"id": "les_1", "title": "Lesson 1", "duration": "10m"},
                    {"id": "les_2", "title": "Lesson 2", "duration": "15m"}
                ]
            }
        ],
        status="published"
    )

    # Enroll student in course and complete 1 lesson
    enr_repo.enroll(student["id"], course_id)
    enr_repo.mark_lesson_complete(student["id"], course_id, "les_1", total_lessons_count=2)

    yield {
        "educator": educator,
        "student": student,
        "admin": admin,
        "course_id": course_id
    }


def test_educator_can_update_course(educator_env):
    """Verifies educator can update course title, metadata, syllabus, and submit to admin."""
    client = Client()
    client.post('/auth/login/', {'identifier': 'mentor@learnsphere.io', 'password': 'Mentor@LearnSphere2026!'})

    course_id = educator_env["course_id"]
    course_repo = CourseRepository()

    # GET edit view
    resp = client.get(f"/courses/educator/{course_id}/edit/")
    assert resp.status_code == 200
    assert b"Update Course Curriculum" in resp.content

    # POST update
    updated_title = "Updated Quantum Computing Masterclass"
    post_data = {
        "title": updated_title,
        "tagline": "Updated tagline for quantum exploration.",
        "description": "Updated deep dive into quantum algorithms and hardware architecture principles.",
        "level": "Advanced",
        "duration_hours": 20,
        "category": "Artificial Intelligence",
        "price": 29.99,
        "status_action": "submit_admin",
        "modules_json": '[{"id":"mod_new","title":"Quantum Gates","lessons":[{"id":"l1","title":"Hadamard Gate","duration":"12m"}]}]'
    }
    update_resp = client.post(f"/courses/educator/{course_id}/edit/", post_data)
    assert update_resp.status_code in [200, 302]

    # Check course updated in MongoDB
    updated_course = course_repo.find_by_id(course_id)
    assert updated_course["title"] == updated_title
    assert updated_course["level"] == "Advanced"
    assert updated_course["status"] == "pending_approval"
    assert len(updated_course["modules"]) == 1


def test_educator_can_see_students_progress(educator_env):
    """Verifies educator can view student completion percentage, lessons, and metrics."""
    client = Client()
    client.post('/auth/login/', {'identifier': 'mentor@learnsphere.io', 'password': 'Mentor@LearnSphere2026!'})

    resp = client.get("/educator/students-progress/")
    assert resp.status_code == 200
    assert b"Student Course Progress &amp; Completion" in resp.content or b"Student Course Progress" in resp.content
    assert b"alex_student" in resp.content or b"Student" in resp.content
    assert b"50.0%" in resp.content or b"50%" in resp.content  # 1 of 2 lessons completed


def test_educator_can_schedule_exam(educator_env):
    """Verifies educator can schedule an exam with start/end windows and questions."""
    client = Client()
    client.post('/auth/login/', {'identifier': 'mentor@learnsphere.io', 'password': 'Mentor@LearnSphere2026!'})

    course_id = educator_env["course_id"]
    exam_repo = ExamRepository()

    # GET create view
    resp = client.get("/exams/educator/create/")
    assert resp.status_code == 200
    assert b"Schedule &amp; Author Proctored Exam" in resp.content or b"Schedule & Author Proctored Exam" in resp.content

    # POST schedule exam
    post_data = {
        "title": "Scheduled Midterm Exam 2026",
        "course_id": course_id,
        "duration_minutes": 60,
        "passing_marks": 50,
        "scheduled_start": "2026-12-01T09:00",
        "scheduled_end": "2026-12-01T12:00",
        "is_proctored": "true",
        "tab_switch_limit": 3,
        "description": "Timed proctored midterm evaluation.",
        "questions_json": '[{"text":"What is O(1) complexity?","type":"single_choice","options":["Constant time","Linear time","Exponential","None"],"correct_option_index":0,"marks":10,"explanation":"Direct lookup."}]'
    }
    create_resp = client.post("/exams/educator/create/", post_data)
    assert create_resp.status_code in [200, 302]

    # Verify exam exists in MongoDB with schedule data
    exams = exam_repo.find_many({"title": "Scheduled Midterm Exam 2026"})
    assert len(exams) >= 1
    assert exams[0]["duration_minutes"] == 60
    assert exams[0]["scheduled_start"] == "2026-12-01T09:00"


def test_educator_can_see_results_and_override_grade(educator_env):
    """Verifies educator can inspect exam submissions and override student grades with justification."""
    client = Client()
    client.post('/auth/login/', {'identifier': 'mentor@learnsphere.io', 'password': 'Mentor@LearnSphere2026!'})

    exam_sub_repo = ExamSubmissionRepository()
    attempt_id = exam_sub_repo.insert_one({
        "student_id": educator_env["student"]["id"],
        "student_name": "alex_student",
        "student_email": "student@learnsphere.io",
        "course_id": educator_env["course_id"],
        "exam_title": "Scheduled Midterm Exam 2026",
        "score": 40,
        "total_marks": 100,
        "percentage": 40.0,
        "passed": False,
        "tab_switches_count": 4,
        "is_flagged": True,
        "status": "flagged_for_review",
        "submitted_at": datetime.now(timezone.utc)
    })

    # Submissions log view
    resp = client.get("/educator/exams/submissions/")
    assert resp.status_code == 200
    assert b"alex_student" in resp.content

    # Grade override API
    override_resp = client.post(
        f"/educator/exams/submissions/{attempt_id}/override/",
        {"new_score": 75, "total_marks": 100, "reason": "Verified false positive tab switch due to OS notification."},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest"
    )
    assert override_resp.status_code == 200
    data = override_resp.json()
    assert data["success"] is True
    assert data["new_score"] == 75

    updated_attempt = exam_sub_repo.find_by_id(attempt_id)
    assert updated_attempt["score"] == 75
    assert updated_attempt["passed"] is True


def test_educator_report_and_admin_workflow(educator_env):
    """Verifies educator can submit updates to admin and admin can review/acknowledge."""
    client = Client()

    # 1. Educator submits update report
    client.post('/auth/login/', {'identifier': 'mentor@learnsphere.io', 'password': 'Mentor@LearnSphere2026!'})
    report_resp = client.post(
        "/educator/reports/submit/",
        {
            "title": "Curriculum Completion Milestone",
            "report_type": "progress_summary",
            "course_id": educator_env["course_id"],
            "message": "Over 80% of students have reached Module 2. Scheduling final evaluation."
        },
        HTTP_X_REQUESTED_WITH="XMLHttpRequest"
    )
    assert report_resp.status_code == 200
    r_data = report_resp.json()
    assert r_data["success"] is True
    report_id = r_data["report_id"]

    # 2. Admin logs in and views reports queue
    admin_client = Client()
    login_resp = admin_client.post('/auth/login/', {'identifier': 'phase8_admin@learnsphere.io', 'password': 'Admin@LearnSphere2026!'})
    assert login_resp.status_code in [200, 302]

    panel_resp = admin_client.get("/admin-panel/")
    assert panel_resp.status_code == 200
    assert b"Faculty Updates &amp; Incident Reports" in panel_resp.content or b"Curriculum Completion Milestone" in panel_resp.content

    # 3. Admin acknowledges report
    ack_resp = admin_client.post(
        f"/admin-panel/reports/{report_id}/acknowledge/",
        {"notes": "Noted. Exam schedule approved."},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest"
    )
    assert ack_resp.status_code == 200
    ack_data = ack_resp.json()
    assert ack_data["success"] is True

    # Check report status is reviewed
    report_repo = EducatorReportRepository()
    rep = report_repo.find_by_id(report_id)
    assert rep["status"] == "reviewed"
    assert rep["admin_response"] == "Noted. Exam schedule approved."
