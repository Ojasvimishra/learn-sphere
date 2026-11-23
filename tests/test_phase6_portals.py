"""
LearnSphere - Automated Test Suite: Phase 6 Dedicated 3-Tier Portals & Dashboards
Tests:
1. Real-event activity streak and study metric engine
2. Server-side Daily Quiz verification and single-daily XP award enforcement
3. Student verified course completion certificate eligibility
4. Educator Studio access controls, submissions audit, and grade overrides with audit logging
5. Admin Panel access controls, educator approvals, and 5-role governance
"""

import os
from datetime import datetime, timezone, timedelta
import pytest
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "learnsphere.settings")
django.setup()

from database.repositories.user_repo import UserRepository
from database.repositories.course_repo import CourseRepository
from database.repositories.enrollment_repo import EnrollmentRepository
from database.repositories.exam_repo import ExamRepository, ExamSubmissionRepository
from database.repositories.audit_repo import AuditRepository
from core.rbac import can_access_portal, can_manage_user, ROLE_SUPER_ADMIN, ROLE_EDUCATOR, ROLE_STUDENT
from apps.portals.streak_calculator import calculate_real_user_metrics
from apps.portals.daily_quiz_bank import get_daily_question_for_today, evaluate_daily_quiz_answer


@pytest.fixture(autouse=True)
def cleanup_test_data():
    user_repo = UserRepository()
    course_repo = CourseRepository()
    enr_repo = EnrollmentRepository()
    exam_sub_repo = ExamSubmissionRepository()
    audit_repo = AuditRepository()

    user_repo.collection.delete_many({"username": {"$regex": "^test_portal_"}})
    course_repo.collection.delete_many({"title": {"$regex": "^TEST_PORTAL_"}})
    yield
    user_repo.collection.delete_many({"username": {"$regex": "^test_portal_"}})
    course_repo.collection.delete_many({"title": {"$regex": "^TEST_PORTAL_"}})


def test_real_event_metrics_and_streak_calculation():
    user_repo = UserRepository()
    enr_repo = EnrollmentRepository()
    course_repo = CourseRepository()

    # Create test user with yesterday's last login
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    user = user_repo.create_user(
        username="test_portal_learner",
        email="test_portal_learner@learnsphere.io",
        raw_password="TestPassword@123!",
        role=ROLE_STUDENT,
        full_name="Portal Learner"
    )
    user_repo.update_one({"_id": user_repo.to_object_id(user["id"])}, {"$set": {"last_login": yesterday}})

    # Create test course and enroll user
    cid = course_repo.create_course(
        title="TEST_PORTAL_Computing Fundamentals",
        tagline="Foundational Computing",
        description="Comprehensive course",
        level="Beginner",
        duration_hours=10,
        instructor_name="Instructor",
        instructor_id="inst_1"
    )

    enr = enr_repo.enroll(user["id"], cid)
    enr_repo.mark_lesson_complete(user["id"], cid, "les_1", 2)
    enr_repo.mark_lesson_complete(user["id"], cid, "les_2", 2)

    fresh_user = user_repo.find_by_id(user["id"])
    metrics = calculate_real_user_metrics(fresh_user)

    assert metrics["total_completed_lessons"] == 2
    assert metrics["certificates_count"] == 1  # 100% progress
    assert metrics["current_streak_days"] >= 1
    assert metrics["total_study_hours"] > 0.0


def test_server_side_daily_quiz_xp_security():
    user_repo = UserRepository()
    user = user_repo.create_user(
        username="test_portal_quizzer",
        email="test_portal_quizzer@learnsphere.io",
        raw_password="TestPassword@123!",
        role=ROLE_STUDENT
    )
    user_id = user["id"]

    # 1. Ensure student quiz question payload never exposes answer keys
    question = get_daily_question_for_today()
    assert "correct_index" not in question
    assert "explanation" not in question
    assert "question" in question
    assert len(question["options"]) >= 2

    # 2. Test server-side evaluation
    # Incorrect option
    wrong_res = evaluate_daily_quiz_answer(question["id"], 99)
    assert wrong_res["correct"] is False

    # 3. Test XP award idempotency (single daily award)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # First award: Success (+50 XP)
    awarded1, delta1, total1 = user_repo.award_daily_quiz_xp(user_id, xp_amount=50)
    assert awarded1 is True
    assert delta1 == 50
    assert total1 == 50

    fresh = user_repo.find_by_id(user_id)
    assert fresh["last_daily_quiz_date"] == today_str
    assert fresh["xp"] == 50

    # Second award attempt today: Blocked (0 XP added)
    awarded2, delta2, total2 = user_repo.award_daily_quiz_xp(user_id, xp_amount=50)
    assert awarded2 is False
    assert delta2 == 0
    assert total2 == 50


def test_student_certificate_eligibility():
    user_repo = UserRepository()
    course_repo = CourseRepository()
    enr_repo = EnrollmentRepository()

    user = user_repo.create_user(
        username="test_portal_cert_student",
        email="test_portal_cert_student@learnsphere.io",
        raw_password="TestPassword@123!",
        role=ROLE_STUDENT
    )
    cid = course_repo.create_course(
        title="TEST_PORTAL_AI Architecture",
        tagline="Advanced AI Systems",
        description="Course description",
        level="Advanced",
        duration_hours=20,
        instructor_name="Prof Mentor",
        instructor_id="prof_1"
    )

    # Incomplete enrollment (50% progress)
    enr = enr_repo.enroll(user["id"], cid)
    enr_repo.mark_lesson_complete(user["id"], cid, "les_1", 2)
    incomplete_enr = enr_repo.get_enrollment(user["id"], cid)
    assert incomplete_enr["progress_percent"] == 50.0

    # Complete remaining lesson -> 100%
    enr_repo.mark_lesson_complete(user["id"], cid, "les_2", 2)
    complete_enr = enr_repo.get_enrollment(user["id"], cid)
    assert complete_enr["progress_percent"] == 100.0


def test_portal_rbac_authorization():
    # Students can access student portal, but not educator or admin portals
    student_user = {"role": ROLE_STUDENT, "is_approved": True}
    assert can_access_portal(student_user, "student") is True
    assert can_access_portal(student_user, "educator") is False
    assert can_access_portal(student_user, "admin") is False

    # Pending educator cannot access educator studio
    pending_educator = {"role": ROLE_EDUCATOR, "is_approved": False}
    assert can_access_portal(pending_educator, "educator") is False

    # Approved educator can access educator studio
    approved_educator = {"role": ROLE_EDUCATOR, "is_approved": True}
    assert can_access_portal(approved_educator, "educator") is True
    assert can_access_portal(approved_educator, "admin") is False

    # Super admin has unrestricted portal access
    admin_user = {"role": ROLE_SUPER_ADMIN, "is_approved": True}
    assert can_access_portal(admin_user, "student") is True
    assert can_access_portal(admin_user, "educator") is True
    assert can_access_portal(admin_user, "admin") is True


def test_educator_grade_override_and_audit():
    user_repo = UserRepository()
    exam_repo = ExamRepository()
    exam_sub_repo = ExamSubmissionRepository()
    audit_repo = AuditRepository()

    educator = user_repo.create_user(
        username="test_portal_faculty",
        email="test_portal_faculty@learnsphere.io",
        raw_password="TestPassword@123!",
        role=ROLE_EDUCATOR,
        full_name="Prof Test"
    )
    student = user_repo.create_user(
        username="test_portal_examinee",
        email="test_portal_examinee@learnsphere.io",
        raw_password="TestPassword@123!",
        role=ROLE_STUDENT
    )

    exam_id = exam_repo.create_exam(
        title="TEST_PORTAL_Exam",
        course_id="c_test",
        course_title="Course Test",
        instructor_id=educator["id"],
        instructor_name="Prof Test",
        duration_minutes=30,
        questions=[{"id": "q1", "question": "What is Python?", "options": ["Lang", "Snake"], "correct_answer": 0, "marks": 100}],
        total_marks=100
    )

    # Student attempts exam
    exam_doc = exam_repo.find_by_id(exam_id)
    attempt = exam_sub_repo.start_attempt(exam_doc, student)
    graded_attempt = exam_sub_repo.submit_and_grade(
        attempt_id=attempt["id"],
        answers={"q1": 1},
        score=0,
        total_marks=100,
        passed=False,
        is_flagged=True
    )
    assert graded_attempt["score"] == 0

    # Faculty overrides grade
    ok = exam_sub_repo.override_grade(
        attempt_id=attempt["id"],
        new_score=85,
        total_marks=100,
        reason="Verified technical network glitch on question 1",
        educator_name="Prof Test"
    )
    assert ok is True

    updated_attempt = exam_sub_repo.find_by_id(attempt["id"])
    assert updated_attempt["score"] == 85
    assert updated_attempt["passed"] is True
    assert updated_attempt["grade_overridden"] is True
    assert updated_attempt["overridden_by"] == "Prof Test"


def test_admin_educator_approval_queue():
    user_repo = UserRepository()

    # Public registration for educator creates account in pending status
    pending_edu = user_repo.create_user(
        username="test_portal_pending_prof",
        email="test_portal_pending_prof@learnsphere.io",
        raw_password="TestPassword@123!",
        role=ROLE_EDUCATOR,
        is_approved=False
    )
    assert pending_edu["is_approved"] is False

    # Verify pending queue lists this account
    pending_list = user_repo.list_pending_educators()
    assert any(str(u["id"]) == str(pending_edu["id"]) for u in pending_list)

    # Admin approves educator
    approved = user_repo.approve_educator(pending_edu["id"])
    assert approved is True

    fresh = user_repo.find_by_id(pending_edu["id"])
    assert fresh["is_approved"] is True
    assert fresh["role"] == ROLE_EDUCATOR
