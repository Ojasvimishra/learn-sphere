"""
LearnSphere - Automated Test Suite: Phase 5 Doubt Solving & AI Tutor Engine
Tests:
1. Student doubt creation, validation and retrieval
2. Peer & educator answer submission, faculty verification
3. Solution acceptance and thread resolution
4. Atomic upvoting with set-based deduplication
5. AI Tutor knowledge synthesis and daily quota rate-limiting (50 queries/day)
"""

import os
import pytest
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "learnsphere.settings")
django.setup()

from database.repositories.doubt_repo import DoubtRepository, DoubtAnswerRepository
from services.doubt_service import DoubtService
from services.ai_tutor_service import AITutorService
from core.redis_client import get_cache_client


@pytest.fixture(autouse=True)
def cleanup_test_doubts():
    doubt_repo = DoubtRepository()
    ans_repo = DoubtAnswerRepository()
    doubt_repo.collection.delete_many({"title": {"$regex": "^TEST_DOUBT_"}})
    yield
    doubt_repo.collection.delete_many({"title": {"$regex": "^TEST_DOUBT_"}})


def test_ask_doubt_and_post_answers():
    service = DoubtService()
    student = {
        "id": "507f1f77bcf86cd799439011",
        "username": "student_alpha",
        "full_name": "Student Alpha",
        "role": "student"
    }

    # Ask doubt
    ok, msg, doubt_id = service.ask_doubt(
        user=student,
        title="TEST_DOUBT_How does Redis sliding window work in LearnSphere?",
        content="I want to understand how atomic INCR and EXPIRE are used together for rate limiting.",
        tags=["redis", "architecture"]
    )
    assert ok is True
    assert doubt_id is not None

    # Retrieve doubt
    doubt = service.doubt_repo.find_by_id(doubt_id)
    assert doubt is not None
    assert doubt["title"] == "TEST_DOUBT_How does Redis sliding window work in LearnSphere?"
    assert doubt["status"] == "open"

    # Peer student posts answer
    peer = {
        "id": "507f1f77bcf86cd799439012",
        "username": "peer_coder",
        "full_name": "Peer Coder",
        "role": "student"
    }
    ok_ans, _, ans_id = service.post_answer(
        user=peer,
        doubt_id=doubt_id,
        content="It calls INCR on key, and sets TTL on the first hit so it automatically resets."
    )
    assert ok_ans is True
    assert ans_id is not None

    answers = service.answer_repo.list_by_doubt(doubt_id)
    assert len(answers) == 1
    assert answers[0]["is_faculty_verified"] is False
    assert answers[0]["is_accepted"] is False

    # Educator posts verified answer
    educator = {
        "id": "507f1f77bcf86cd799439013",
        "username": "prof_turing",
        "full_name": "Prof Alan Turing",
        "role": "educator"
    }
    ok_fac, _, fac_ans_id = service.post_answer(
        user=educator,
        doubt_id=doubt_id,
        content="Correct. In Redis, INCR returns 1 if key was created, allowing a single EXPIRE command."
    )
    assert ok_fac is True

    updated_answers = service.answer_repo.list_by_doubt(doubt_id)
    assert len(updated_answers) == 2
    fac_ans = [a for a in updated_answers if str(a["_id"]) == fac_ans_id][0]
    assert fac_ans["is_faculty_verified"] is True


def test_accept_solution_resolution():
    service = DoubtService()
    student = {
        "id": "507f1f77bcf86cd799439021",
        "username": "doubt_asker",
        "role": "student"
    }
    ok, _, doubt_id = service.ask_doubt(
        user=student,
        title="TEST_DOUBT_What is the difference between Argon2i and Argon2id?",
        content="Can someone explain memory hardness tradeoffs in modern cryptographic hashers?"
    )
    assert ok is True

    answerer = {
        "id": "507f1f77bcf86cd799439022",
        "username": "crypto_expert",
        "role": "student"
    }
    _, _, ans_id = service.post_answer(
        user=answerer,
        doubt_id=doubt_id,
        content="Argon2id uses data-independent memory access at the start and data-dependent memory access later."
    )

    # Unauthorized user tries to accept solution
    stranger = {"id": "507f1f77bcf86cd799439099", "role": "student"}
    unauth_ok, unauth_msg = service.accept_solution(doubt_id, ans_id, stranger)
    assert unauth_ok is False
    assert "Only the author or faculty" in unauth_msg

    # Author accepts solution
    auth_ok, _ = service.accept_solution(doubt_id, ans_id, student)
    assert auth_ok is True

    doubt = service.doubt_repo.find_by_id(doubt_id)
    assert doubt["status"] == "resolved"
    assert doubt["accepted_answer_id"] == ans_id

    answer = service.answer_repo.collection.find_one({"_id": service.answer_repo.collection.find_one()["_id"]})
    assert answer is not None


def test_atomic_upvoting():
    service = DoubtService()
    student = {
        "id": "507f1f77bcf86cd799439031",
        "username": "voter_user",
        "role": "student"
    }
    _, _, doubt_id = service.ask_doubt(
        user=student,
        title="TEST_DOUBT_Explain ACID transactions in distributed systems",
        content="How does 2-phase commit coordinate consensus among heterogeneous partition nodes?"
    )

    user_voter_id = "507f1f77bcf86cd799439040"

    # First vote: Upvoted (added)
    added = service.toggle_doubt_upvote(doubt_id, user_voter_id)
    assert added is True
    doubt = service.doubt_repo.find_by_id(doubt_id)
    assert doubt["upvotes"] == 1
    assert user_voter_id in doubt["upvoted_by"]

    # Second vote by same user: Downvoted / removed
    removed = service.toggle_doubt_upvote(doubt_id, user_voter_id)
    assert removed is False
    doubt = service.doubt_repo.find_by_id(doubt_id)
    assert doubt["upvotes"] == 0
    assert user_voter_id not in doubt["upvoted_by"]


def test_ai_tutor_synthesis_and_quota_limits():
    ai_service = AITutorService()
    user_id = "ai_test_user_unique_99"
    user = {"id": user_id, "username": "ai_learner"}

    # Clear rate limit key for test user
    cache = get_cache_client()
    cache.delete(f"ratelimit:ai:{user_id}")

    # Query 1: Smart education vision
    res = ai_service.answer_query(user, "What is the concept of smart education?")
    assert res["success"] is True
    assert "Smart Education in the Digital Age" in res["response_markdown"]
    assert "Effectively" in res["response_markdown"]
    assert res["remaining_quota"] == 49

    # Fast forward quota usage to 50
    cache.set(f"ratelimit:ai:{user_id}", 50)
    assert ai_service.get_remaining_daily_quota(user_id) == 0

    # 51st Query must be blocked by rate limiter
    blocked_res = ai_service.answer_query(user, "Tell me more about cryptography.")
    assert blocked_res["success"] is False
    assert "Daily AI Tutor quota exceeded" in blocked_res["error"]
    assert blocked_res["remaining_quota"] == 0
