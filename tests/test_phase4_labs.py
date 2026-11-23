"""
LearnSphere - Automated Test Suite: Phase 4 Virtual Labs & Sandboxed Code Runner
Tests:
1. Virtual lab creation and test cases definition
2. Sandboxed execution with stdout capture and timing
3. AST security filters blocking malicious imports and eval/exec
4. Automated unit test evaluation and scoring
"""

import os
import pytest
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "learnsphere.settings")
django.setup()

from database.repositories.lab_repo import LabRepository, LabSubmissionRepository
from services.code_execution_service import CodeExecutionService, validate_python_code_safety


@pytest.fixture(autouse=True)
def cleanup_test_labs():
    lab_repo = LabRepository()
    sub_repo = LabSubmissionRepository()
    lab_repo.collection.delete_many({"title": {"$regex": "^TEST_LAB_"}})
    sub_repo.collection.delete_many({"output": {"$regex": "^Passed"}})
    yield
    lab_repo.collection.delete_many({"title": {"$regex": "^TEST_LAB_"}})


def test_code_runner_safe_execution():
    """Verifies safe code runs cleanly and captures output and timing."""
    exec_service = CodeExecutionService()

    code = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

print(factorial(5))
"""
    res = exec_service.run_student_code(code)
    assert res["success"] is True
    assert "120" in res["output"]
    assert res["runtime_ms"] >= 0.0


def test_code_sandbox_security_rejections():
    """Verifies that attempts to import os, subprocess or call eval are intercepted by AST."""
    exec_service = CodeExecutionService()

    # 1. Reject import os
    bad_code1 = "import os\nos.system('dir')"
    res1 = exec_service.run_student_code(bad_code1)
    assert res1["success"] is False
    assert "Security Violation: Import of 'os' is prohibited" in res1["error"]

    # 2. Reject subprocess
    bad_code2 = "from subprocess import Popen\nPopen(['calc.exe'])"
    res2 = exec_service.run_student_code(bad_code2)
    assert res2["success"] is False
    assert "Security Violation: Import from 'subprocess' is prohibited" in res2["error"]

    # 3. Reject open() call
    bad_code3 = "f = open('secret.txt', 'r')"
    res3 = exec_service.run_student_code(bad_code3)
    assert res3["success"] is False
    assert "Security Violation: Invocation of 'open()' is prohibited" in res3["error"]


def test_lab_test_case_evaluation():
    """Verifies automated evaluation of student solution against test cases."""
    exec_service = CodeExecutionService()
    lab_repo = LabRepository()

    # Create two-sum challenge lab
    test_cases = [
        {"invocation": "two_sum([2, 7, 11, 15], 9)", "expected_output": "[0, 1]", "is_hidden": False},
        {"invocation": "two_sum([3, 2, 4], 6)", "expected_output": "[1, 2]", "is_hidden": False},
        {"invocation": "two_sum([3, 3], 6)", "expected_output": "[0, 1]", "is_hidden": True}
    ]

    lab_id = lab_repo.create_lab(
        title="TEST_LAB_ Two Sum Challenge",
        description="Return indices of the two numbers such that they add up to target.",
        course_id="course_algo_101",
        language="python",
        difficulty="Easy",
        test_cases=test_cases,
        xp_reward=50
    )

    # 1. Correct Solution
    valid_solution = """
def two_sum(nums, target):
    seen = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []
"""
    ok, _, eval_res = exec_service.evaluate_lab_submission(lab_id, "student_1", valid_solution)
    assert ok is True
    assert eval_res["passed"] is True
    assert eval_res["tests_passed"] == 3
    assert eval_res["total_tests"] == 3
    assert eval_res["xp_earned"] == 50

    # 2. Incorrect Solution (returns hardcoded wrong index)
    buggy_solution = """
def two_sum(nums, target):
    return [0, 0]
"""
    ok_bad, _, eval_bad = exec_service.evaluate_lab_submission(lab_id, "student_1", buggy_solution)
    assert ok_bad is True
    assert eval_bad["passed"] is False
    assert eval_bad["tests_passed"] == 0
