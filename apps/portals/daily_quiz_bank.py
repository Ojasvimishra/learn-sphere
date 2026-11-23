"""
LearnSphere - Daily Smart Education Quiz Bank
Answer keys are kept strictly server-side and never exposed to the client prior to evaluation.
"""

from typing import Any, Dict, List

DAILY_QUIZ_QUESTIONS: List[Dict[str, Any]] = [
    {
        "id": "dq_smart_edu",
        "question": "What is the primary objective of Smart Education in the digital age?",
        "options": [
            "Replacing human educators entirely with autonomous LLM scripts",
            "Enabling learners to learn more effectively, efficiently, flexibly and comfortably",
            "Enforcing continuous 24/7 locked-browser proctoring without breaks",
            "Restricting education access exclusively to proprietary native applications"
        ],
        "correct_index": 1,
        "explanation": "Smart education describes learning in the digital age. It enables learners to learn more effectively, efficiently, flexibly and comfortably."
    },
    {
        "id": "dq_argon2",
        "question": "Why does LearnSphere prioritize Argon2id over legacy single-round hashing for password security?",
        "options": [
            "Argon2id produces 16-bit compressed hash tokens",
            "Argon2id features tunable memory-hardness that defends against GPU/ASIC brute-force clusters",
            "Argon2id does not require cryptographic salt generation",
            "Argon2id executes in sub-millisecond time without CPU overhead"
        ],
        "correct_index": 1,
        "explanation": "Argon2id combines memory hardness with side-channel attack defenses, making GPU dictionary attacks computationally intractable."
    },
    {
        "id": "dq_redis_rate",
        "question": "How does LearnSphere achieve atomic sliding-window rate limiting across multi-worker deployments?",
        "options": [
            "Using a global Python in-memory dictionary shared across threads",
            "Using Redis atomic INCR and TTL expiration keys per user or IP",
            "Relying solely on client-side localStorage request counters",
            "Querying unindexed MongoDB audit logs on every request"
        ],
        "correct_index": 1,
        "explanation": "Redis provides atomic INCR and key-level TTL expiration, ensuring strict per-endpoint rate enforcement regardless of how many Django web workers run."
    },
    {
        "id": "dq_rbac",
        "question": "Which role in LearnSphere's 5-role RBAC hierarchy is authorized to override student proctored exam grades?",
        "options": [
            "Student",
            "Moderator",
            "Educator, Department Admin, and Super Admin",
            "Anonymous Guest"
        ],
        "correct_index": 2,
        "explanation": "Grade overrides require the 'grade.override' permission, granted to educators, department admins, and super admins with mandatory audit trail logging."
    },
    {
        "id": "dq_ast_sandbox",
        "question": "How does LearnSphere's Virtual Lab runner prevent dangerous arbitrary code execution in student programs?",
        "options": [
            "By renaming student files to .txt before execution",
            "By inspecting the Python Abstract Syntax Tree (AST) to block prohibited modules like os and subprocess and dangerous builtins like eval",
            "By running student code directly in the main Django server thread",
            "By asking the student not to import system libraries"
        ],
        "correct_index": 1,
        "explanation": "Before running code, LearnSphere parses student scripts using Python's ast module, rejecting forbidden imports and dangerous builtins prior to execution."
    }
]


def get_daily_question_for_today() -> Dict[str, Any]:
    """Returns today's question without the answer key or explanation."""
    from datetime import datetime, timezone
    day_of_year = datetime.now(timezone.utc).timetuple().tm_yday
    idx = day_of_year % len(DAILY_QUIZ_QUESTIONS)
    full = DAILY_QUIZ_QUESTIONS[idx]

    # Return student-safe payload (never leak correct_index or explanation)
    return {
        "id": full["id"],
        "question": full["question"],
        "options": full["options"],
        "total_options": len(full["options"])
    }


def evaluate_daily_quiz_answer(question_id: str, selected_option_index: int) -> Dict[str, Any]:
    """Server-side verification of student answer."""
    question = next((q for q in DAILY_QUIZ_QUESTIONS if q["id"] == question_id), None)
    if not question:
        return {
            "success": False,
            "error": "Invalid or expired quiz question."
        }

    is_correct = int(selected_option_index) == question["correct_index"]
    return {
        "success": True,
        "correct": is_correct,
        "correct_index": question["correct_index"],
        "explanation": question["explanation"]
    }
