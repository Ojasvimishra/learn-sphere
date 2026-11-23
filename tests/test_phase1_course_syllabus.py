"""
LearnSphere - Automated Test Suite: Phase 1 Course & Syllabus Engine
Tests:
1. Course creation with structured modules, lessons, and metadata
2. Dynamic module and lesson addition (add_module, add_lesson)
3. Free preview vs locked lesson access permissions
4. Student enrollment and lesson completion progress calculation
5. Sequential navigation (prev_lesson, next_lesson)
6. Educator course authoring isolation
"""

import os
import pytest
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "learnsphere.settings")
django.setup()

from database.repositories.course_repo import CourseRepository
from database.repositories.enrollment_repo import EnrollmentRepository
from services.course_service import CourseService
from services.auth_service import AuthService


@pytest.fixture(autouse=True)
def cleanup_test_courses():
    course_repo = CourseRepository()
    enrollment_repo = EnrollmentRepository()
    # Delete test courses and enrollments
    course_repo.collection.delete_many({"title": {"$regex": "^TEST_"}})
    enrollment_repo.collection.delete_many({"user_id": {"$regex": "^test_user"}})
    yield
    course_repo.collection.delete_many({"title": {"$regex": "^TEST_"}})
    enrollment_repo.collection.delete_many({"user_id": {"$regex": "^test_user"}})


def test_course_creation_and_syllabus_authoring():
    """Tests creating course and dynamically building syllabus modules and lessons."""
    course_service = CourseService()
    course_repo = CourseRepository()

    instructor = {"id": "inst_123", "full_name": "Prof. Alan Turing", "username": "aturing"}
    ok, msg, course_id = course_service.create_course(instructor, {
        "title": "TEST_ Quantum Computing Foundations",
        "tagline": "Master qubits, superposition, quantum gates, and circuits.",
        "description": "Comprehensive course covering quantum algorithms, Shor's algorithm, and Qiskit.",
        "level": "Advanced",
        "duration_hours": 20,
        "category": "Computer Science & Engineering"
    })

    assert ok is True
    assert course_id is not None

    # Add Module 1
    mod1_id = course_repo.add_module(course_id, "Module 1: Qubit Linear Algebra", "Inner products, bases, unitary matrices.")
    assert mod1_id is not None

    # Add Lesson 1.1 (Free Preview)
    les1_id = course_repo.add_lesson(
        course_id=course_id,
        module_id=mod1_id,
        title="1.1 Dirac Bra-Ket Notation & State Vectors",
        lesson_type="video",
        duration_minutes=25,
        video_url="https://www.youtube.com/watch?v=mock_quantum_1",
        content_markdown="# Bra-Ket Notation\n\nState vectors are represented as ket |psi>.",
        is_free_preview=True
    )
    assert les1_id is not None

    # Add Lesson 1.2 (Locked / Enrolled Only)
    les2_id = course_repo.add_lesson(
        course_id=course_id,
        module_id=mod1_id,
        title="1.2 Pauli Matrix Transformations",
        lesson_type="reading",
        duration_minutes=30,
        content_markdown="# Pauli Matrices\n\nSigma_X, Sigma_Y, Sigma_Z.",
        is_free_preview=False
    )
    assert les2_id is not None

    # Fetch updated course
    course = course_repo.find_by_id(course_id)
    assert course["modules_count"] == 1
    assert course["lessons_count"] == 2
    assert len(course["modules"][0]["lessons"]) == 2


def test_lesson_access_preview_vs_enrolled():
    """Verifies that free preview lessons are accessible to public, but locked lessons require enrollment."""
    course_service = CourseService()
    course_repo = CourseRepository()

    instructor = {"id": "inst_123", "full_name": "Dr. Sarah", "username": "sarah"}
    _, _, course_id = course_service.create_course(instructor, {
        "title": "TEST_ Mobile App Development",
        "tagline": "Build native Android and iOS apps with Kotlin and Flutter.",
        "description": "Complete mobile development curriculum with projects.",
        "level": "Intermediate",
        "duration_hours": 15
    })

    mod_id = course_repo.add_module(course_id, "Intro to Jetpack Compose")
    free_lesson_id = course_repo.add_lesson(course_id, mod_id, "Lesson 1: Declarative UI", is_free_preview=True)
    locked_lesson_id = course_repo.add_lesson(course_id, mod_id, "Lesson 2: State Hoisting", is_free_preview=False)

    # 1. Anonymous / unenrolled student
    student_guest = None
    ok_free, _, ctx_free = course_service.get_lesson_context(course_id, free_lesson_id, user=student_guest)
    assert ok_free is True
    assert ctx_free["lesson"]["title"] == "Lesson 1: Declarative UI"

    # Accessing locked lesson without enrollment -> DENIED
    ok_locked, msg, _ = course_service.get_lesson_context(course_id, locked_lesson_id, user=student_guest)
    assert ok_locked is False
    assert "requires enrollment" in msg

    # 2. Student enrolls
    student_user = {"id": "test_user_456", "role": "student"}
    course_service.enroll_student(course_id, student_user["id"])

    # Now locked lesson is ACCESSIBLE
    ok_enrolled, _, ctx_enrolled = course_service.get_lesson_context(course_id, locked_lesson_id, user=student_user)
    assert ok_enrolled is True
    assert ctx_enrolled["is_enrolled"] is True


def test_student_progress_and_completion():
    """Tests lesson completion progress calculation and certificate issuance flag at 100%."""
    course_service = CourseService()
    course_repo = CourseRepository()
    enrollment_repo = EnrollmentRepository()

    _, _, course_id = course_service.create_course({"id": "inst_1", "username": "prof"}, {
        "title": "TEST_ Discrete Mathematics",
        "tagline": "Logic, sets, proofs, graph theory.",
        "description": "Essential mathematical toolkit for computer science.",
        "level": "Beginner",
        "duration_hours": 10
    })

    mod_id = course_repo.add_module(course_id, "Propositional Logic")
    l1 = course_repo.add_lesson(course_id, mod_id, "Truth Tables")
    l2 = course_repo.add_lesson(course_id, mod_id, "Predicate Calculus")

    user_id = "test_user_789"
    course_service.enroll_student(course_id, user_id)

    # Complete Lesson 1 -> 50%
    enr_1 = course_service.complete_lesson(user_id, course_id, l1)
    assert enr_1["progress_percent"] == 50.0
    assert l1 in enr_1["completed_lessons"]
    assert enr_1["certificate_issued"] is False

    # Complete Lesson 2 -> 100%
    enr_2 = course_service.complete_lesson(user_id, course_id, l2)
    assert enr_2["progress_percent"] == 100.0
    assert l2 in enr_2["completed_lessons"]
    assert enr_2["certificate_issued"] is True
    assert enr_2["completed_at"] is not None


def test_prev_next_lesson_navigation():
    """Verifies that lesson player correctly calculates previous and next lesson links."""
    course_service = CourseService()
    course_repo = CourseRepository()

    _, _, course_id = course_service.create_course({"id": "inst_1", "username": "prof"}, {
        "title": "TEST_ Data Structures",
        "tagline": "Arrays, Stacks, Queues, Heaps.",
        "description": "Core data structure implementations.",
        "level": "Intermediate",
        "duration_hours": 12
    })

    m1 = course_repo.add_module(course_id, "Linear Data Structures")
    l1 = course_repo.add_lesson(course_id, m1, "Arrays", is_free_preview=True)
    l2 = course_repo.add_lesson(course_id, m1, "Linked Lists", is_free_preview=True)
    l3 = course_repo.add_lesson(course_id, m1, "Stacks & Queues", is_free_preview=True)

    # Middle lesson (l2): should have l1 as prev and l3 as next
    ok, _, ctx = course_service.get_lesson_context(course_id, l2, user=None)
    assert ok is True
    assert ctx["prev_lesson"]["id"] == l1
    assert ctx["next_lesson"]["id"] == l3

    # First lesson (l1): prev is None, next is l2
    _, _, ctx_first = course_service.get_lesson_context(course_id, l1, user=None)
    assert ctx_first["prev_lesson"] is None
    assert ctx_first["next_lesson"]["id"] == l2

    # Last lesson (l3): prev is l2, next is None
    _, _, ctx_last = course_service.get_lesson_context(course_id, l3, user=None)
    assert ctx_last["prev_lesson"]["id"] == l2
    assert ctx_last["next_lesson"] is None
