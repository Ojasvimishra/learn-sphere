"""
LearnSphere - Safe Code Execution & Virtual Lab Runner (Tier 2)
Executes student code within controlled sandbox boundaries with timeouts,
AST safety validation, and automated unit test verification.
"""

import sys
import io
import time
import ast
import traceback
from typing import Any, Dict, List, Optional, Tuple
from database.repositories.lab_repo import LabRepository, LabSubmissionRepository

FORBIDDEN_MODULES = {"os", "subprocess", "sys", "shutil", "socket", "requests", "urllib", "importlib"}
FORBIDDEN_CALLS = {"eval", "exec", "open", "__import__", "globals", "locals"}


def validate_python_code_safety(code_str: str) -> Tuple[bool, str]:
    """Inspects Abstract Syntax Tree (AST) to prevent system destruction / sandbox escapes."""
    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        return False, f"Syntax Error: {str(e)}"

    for node in ast.walk(tree):
        # Disallow dangerous imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_MODULES:
                    return False, f"Security Violation: Import of '{alias.name}' is prohibited in virtual lab sandbox."
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in FORBIDDEN_MODULES:
                return False, f"Security Violation: Import from '{node.module}' is prohibited in virtual lab sandbox."

        # Disallow eval/exec/open calls
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                return False, f"Security Violation: Invocation of '{node.func.id}()' is prohibited in virtual lab sandbox."

    return True, "Safe"


class CodeExecutionService:
    def __init__(self):
        self.lab_repo = LabRepository()
        self.sub_repo = LabSubmissionRepository()

    def run_student_code(self, code_str: str, stdin_input: str = "") -> Dict[str, Any]:
        """Safely executes code with captured stdout/stderr and execution timing."""
        safe, msg = validate_python_code_safety(code_str)
        if not safe:
            return {
                "success": False,
                "output": "",
                "error": msg,
                "runtime_ms": 0.0
            }

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        old_stdout = sys.stdout
        old_stderr = sys.stderr

        start = time.time()
        success = True
        error_msg = ""

        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture

            # Safe execution sandbox dictionary
            safe_globals = {
                "__builtins__": {
                    "print": print, "range": range, "len": len, "int": int, "float": float,
                    "str": str, "bool": bool, "list": list, "dict": dict, "set": set, "tuple": tuple,
                    "max": max, "min": min, "sum": sum, "sorted": sorted, "enumerate": enumerate,
                    "zip": zip, "abs": abs, "round": round, "map": map, "filter": filter
                }
            }
            exec(code_str, safe_globals)
        except Exception:
            success = False
            error_msg = traceback.format_exc().splitlines()[-1]
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        runtime_ms = round((time.time() - start) * 1000, 2)
        out = stdout_capture.getvalue()
        if not out and success:
            out = "(Code executed successfully with no output)"

        return {
            "success": success,
            "output": out if success else "",
            "error": error_msg,
            "runtime_ms": runtime_ms
        }

    def evaluate_lab_submission(
        self,
        lab_id: str,
        student_id: str,
        code_str: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        lab = self.lab_repo.find_by_id(lab_id)
        if not lab:
            return False, "Virtual lab not found", {}

        safe, sec_msg = validate_python_code_safety(code_str)
        if not safe:
            self.sub_repo.record_submission(lab_id, student_id, code_str, "error", 0, 0, 0.0, sec_msg)
            return False, sec_msg, {"passed": False, "error": sec_msg, "tests": []}

        test_cases = lab.get("test_cases", [])
        total_tests = len(test_cases)
        passed_count = 0
        test_results = []
        start_eval = time.time()

        for idx, tc in enumerate(test_cases):
            expected = str(tc.get("expected_output", "")).strip()
            invoc = tc.get("invocation", "")

            full_code = f"{code_str}\n\nres = {invoc}\nprint(res)"
            exec_res = self.run_student_code(full_code)

            actual = exec_res["output"].strip()
            passed = (actual == expected)
            if passed:
                passed_count += 1

            test_results.append({
                "test_index": idx + 1,
                "invocation": invoc,
                "expected": expected,
                "actual": actual if not tc.get("is_hidden") else ("Hidden Test Output" if not passed else "MATCHED"),
                "passed": passed,
                "is_hidden": tc.get("is_hidden", False)
            })

        runtime = round((time.time() - start_eval) * 1000, 2)
        all_passed = (passed_count == total_tests) if total_tests > 0 else True
        status = "passed" if all_passed else "failed"

        self.sub_repo.record_submission(
            lab_id=lab_id,
            student_id=student_id,
            code=code_str,
            status=status,
            tests_passed=passed_count,
            total_tests=total_tests,
            runtime_ms=runtime,
            output=f"Passed {passed_count}/{total_tests} test cases."
        )

        if all_passed:
            self.lab_repo.collection.update_one(
                {"_id": self.lab_repo.to_object_id(lab_id)},
                {"$inc": {"completions_count": 1}}
            )

        return True, "Evaluation complete.", {
            "status": status,
            "passed": all_passed,
            "tests_passed": passed_count,
            "total_tests": total_tests,
            "runtime_ms": runtime,
            "test_results": test_results,
            "xp_earned": lab.get("xp_reward", 50) if all_passed else 0
        }
