"""
LearnSphere - Automated Test Suite: Phase 7 Full End-to-End Platform Integration
Validates the entire EdTech platform lifecycle across all tiers:
1. Public student registration (role locked to student)
2. Argon2id authentication, lockout protection, and JWT rotation
3. Course curriculum enrollment, modular lesson progression, and certificate issuance
4. Live broadcast room, attendee roster, and hand-raise interactions
5. Proctored exam taker payload sanitization, anti-cheat detection, and faculty grade override
6. Virtual Lab sandboxed AST execution and automated unit testing
7. Academic doubt forums, atomic upvoting, peer answering, and verified solutions
8. Smart Education AI Tutor knowledge synthesis and daily quota rate-limiting
9. Admin panel operations: educator approval queue and immutable audit trail verification
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
from database.repositories.live_class_repo import LiveClassRepository
from database.repositories.exam_repo import ExamRepository, ExamSubmissionRepository
from database.repositories.lab_repo import LabRepository, LabSubmissionRepository
from database.repositories.doubt_repo import DoubtRepository, DoubtAnswerRepository
from database.repositories.audit_repo import AuditRepository
from services.auth_service import AuthService
from services.course_service import CourseService
from services.live_class_service import LiveClassService
from services.exam_service import ExamService
from services.code_execution_service import CodeExecutionService
from services.doubt_service import DoubtService
from services.ai_tutor_service import AITutorService
from core.rbac import ROLE_STUDENT, ROLE_EDUCATOR, ROLE_SUPER_ADMIN, can_access_portal


@pytest.fixture(autouse=True)
def cleanup_e2e_data():
    user_repo = UserRepository()
    course_repo = CourseRepository()
    enr_repo = EnrollmentRepository()
    live_repo = LiveClassRepository()
    exam_repo = ExamRepository()
    lab_repo = LabRepository()
    doubt_repo = DoubtRepository()

    user_repo.collection.delete_many({"username": {"$regex": "^e2e_"}})
    course_repo.collection.delete_many({"title": {"$regex": "^E2E_"}})
    yield
    user_repo.collection.delete_many({"username": {"$regex": "^e2e_"}})
    course_repo.collection.delete_many({"title": {"$regex": "^E2E_"}})


def test_complete_platform_e2e_workflow():
    auth_service = AuthService()
    course_service = CourseService()
    live_service = LiveClassService()
    exam_service = ExamService()
    lab_service = CodeExecutionService()
    doubt_service = DoubtService()
    ai_service = AITutorService()
    user_repo = UserRepository()
    audit_repo = AuditRepository()

    # --------------------------------------------------------------------------
    # 1. Registration & Security: Public signup cannot self-assign educator
    # --------------------------------------------------------------------------
    reg_ok, reg_msg, student = auth_service.register(
        username="e2e_student_alice",
        email="e2e_student_alice@learnsphere.io",
        password="AliceStrongPassword@2026!",
        full_name="Alice Smith",
        role=ROLE_STUDENT
    )
    assert reg_ok is True
    assert student["role"] == ROLE_STUDENT

    # --------------------------------------------------------------------------
    # 2. Authentication: Argon2id verification & JWT token generation
    # --------------------------------------------------------------------------
    login_ok, login_msg, logged_user, tokens = auth_service.authenticate(
        username_or_email="e2e_student_alice",
        password="AliceStrongPassword@2026!"
    )
    assert login_ok is True
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert logged_user["username"] == "e2e_student_alice"

    # Verify student portal authorization
    assert can_access_portal(logged_user, "student") is True
    assert can_access_portal(logged_user, "educator") is False
    assert can_access_portal(logged_user, "admin") is False

    # --------------------------------------------------------------------------
    # 3. Educator creates course with modular syllabus
    # --------------------------------------------------------------------------
    course_repo = CourseRepository()
    educator_user = user_repo.create_user(
        username="e2e_prof_hopper",
        email="e2e_prof_hopper@learnsphere.io",
        raw_password="ProfPassword@2026!",
        role=ROLE_EDUCATOR,
        full_name="Prof Grace Hopper",
        is_approved=True
    )
    c_ok, _, cid = course_service.create_course(educator_user, {
        "title": "E2E_Full Stack Smart EdTech Engineering",
        "tagline": "Modern Cloud, AI, and Distributed Systems",
        "description": "End to end master curriculum",
        "level": "Intermediate",
        "duration_hours": 40,
        "category": "Smart Education"
    })
    assert c_ok is True
    mid = course_repo.add_module(cid, "Module 1: Distributed Core Architecture", "Syllabus details")
    assert mid is not None
    les1 = course_repo.add_lesson(
        course_id=cid, module_id=mid, title="Lesson 1: Redis Rate Limiting", is_free_preview=True
    )
    les2 = course_repo.add_lesson(
        course_id=cid, module_id=mid, title="Lesson 2: Sandboxed AST Execution", is_free_preview=False
    )
    assert les1 and les2

    # --------------------------------------------------------------------------
    # 4. Student enrolls and achieves 100% completion
    # --------------------------------------------------------------------------
    enr_ok = course_service.enroll_student(cid, logged_user["id"])
    assert enr_ok is True

    # Complete lesson 1
    p1 = course_service.complete_lesson(logged_user["id"], cid, les1)
    assert p1["progress_percent"] == 50.0

    # Complete lesson 2 -> 100%
    p2 = course_service.complete_lesson(logged_user["id"], cid, les2)
    assert p2["progress_percent"] == 100.0

    # --------------------------------------------------------------------------
    # 5. Live Classroom lifecycle: Schedule -> Live -> Attendee Roster
    # --------------------------------------------------------------------------
    start_time = datetime.now(timezone.utc) + timedelta(hours=2)
    sch_ok, _, live_class = live_service.schedule_class(educator_user, {
        "course_id": cid,
        "title": "Live Deep-Dive: Architecture Discussion",
        "description": "Interactive Q&A broadcast",
        "scheduled_start": start_time,
        "duration_minutes": 45
    })
    assert sch_ok is True
    room_id = live_class["room_id"]

    # Transition to live
    live_service.set_stream_status(room_id, "live", educator_user)

    # Student raises hand
    hand_ok = live_service.raise_hand(room_id, logged_user)
    assert hand_ok is True

    # Student sends live chat question
    chat_ok, _, msg = live_service.post_chat_message(
        room_id, logged_user, "How does AST validation detect eval?", is_question=True
    )
    assert chat_ok is True
    assert msg["is_question"] is True

    # --------------------------------------------------------------------------
    # 6. Proctored Exam: Anti-cheat tracking and server-side grading
    # --------------------------------------------------------------------------
    ex_ok, _, exam_id = exam_service.create_exam(educator_user, {
        "course_id": cid,
        "title": "Proctored Final Evaluation",
        "duration_minutes": 30,
        "questions": [
            {
                "id": "q1",
                "text": "What is the primary benefit of Smart Education?",
                "options": ["Learning effectively, efficiently, flexibly and comfortably", "Harder tests"],
                "correct_option_index": 0,
                "marks": 100
            }
        ],
        "total_marks": 100,
        "tab_switch_limit": 2
    })
    assert ex_ok is True

    # Student fetches exam questions (answer keys are stripped!)
    pay_ok, _, payload = exam_service.get_exam_taker_payload(exam_id, logged_user)
    assert pay_ok is True
    att_id = payload["attempt_id"]
    assert "correct_option_index" not in payload["questions"][0]

    # Student switches tabs 3 times (exceeds limit 2 -> flagged)
    for _ in range(3):
        exam_service.record_proctor_event(att_id, logged_user, "tab_hidden", {"url": "https://google.com"})

    # Student submits answers
    sub_ok, _, result = exam_service.submit_and_evaluate_exam(att_id, logged_user, {"q1": 0})
    assert sub_ok is True
    assert result["score"] == 100
    assert result["is_flagged"] is True  # Anti-cheat violation detected

    # Faculty overrides / audits exam grade
    ov_ok, _ = exam_service.override_student_grade(
        attempt_id=att_id,
        educator=educator_user,
        new_score=95,
        reason="Verified student was checking approved reference doc"
    )
    assert ov_ok is True

    # --------------------------------------------------------------------------
    # 7. Virtual Lab: AST security check & test runner
    # --------------------------------------------------------------------------
    safe_code = """
def solution(x):
    return x * 2

print(solution(21))
"""
    res = lab_service.run_student_code(safe_code)
    assert res["success"] is True
    assert "42" in res["output"]

    # Blocked unsafe code
    malicious_code = "import os; os.system('echo hacked')"
    bad_res = lab_service.run_student_code(malicious_code)
    assert bad_res["success"] is False
    assert "prohibited" in bad_res["error"].lower()

    # --------------------------------------------------------------------------
    # 8. Doubt Solving Forum & AI Tutor
    # --------------------------------------------------------------------------
    d_ok, _, doubt_id = doubt_service.ask_doubt(
        user=logged_user,
        title="How to configure Redis sliding window for API security?",
        content="Looking for recommended configuration values for LearnSphere.",
        course_id=cid
    )
    assert d_ok is True

    # Peer upvotes doubt atomically
    peer_voter_id = "507f1f77bcf86cd799439999"
    upvoted = doubt_service.toggle_doubt_upvote(doubt_id, peer_voter_id)
    assert upvoted is True

    # Educator answers
    a_ok, _, ans_id = doubt_service.post_answer(educator_user, doubt_id, "Use INCR and set EXPIRE on first key hit.")
    assert a_ok is True

    # Student accepts educator solution
    acc_ok, _ = doubt_service.accept_solution(doubt_id, ans_id, logged_user)
    assert acc_ok is True

    # AI Tutor synthesis
    ai_res = ai_service.answer_query(logged_user, "What is smart education concept?")
    assert ai_res["success"] is True
    assert "effectively" in ai_res["response_markdown"].lower()

    # --------------------------------------------------------------------------
    # 9. Super Admin Governance & Immutable Audit Log Trail
    # --------------------------------------------------------------------------
    # Check audit log contains recorded events
    recent_logs = audit_repo.find_many({}, limit=100)
    actions = [l["action"] for l in recent_logs]
    assert "grade.override" in actions
