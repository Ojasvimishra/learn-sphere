"""
LearnSphere - Real-Event Activity Streak & Metric Engine
Calculates student learning streaks and total learning hours strictly from real MongoDB events:
- Course lesson completions (EnrollmentRepository)
- Virtual Lab executions and submissions (LabSubmissionRepository)
- Exam attempts (ExamSubmissionRepository)
- User authentication events (last_login)
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Set
from database.repositories.enrollment_repo import EnrollmentRepository
from database.repositories.lab_repo import LabSubmissionRepository
from database.repositories.exam_repo import ExamSubmissionRepository
from database.repositories.user_repo import UserRepository


def calculate_real_user_metrics(user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes genuine activity metrics:
    - current_streak_days: consecutive days with real learning activity
    - total_study_hours: estimated from completed lessons (avg 20m) and lab attempts
    - total_completed_lessons: actual count of finished lesson IDs
    - certificates_count: completed courses (100% progress)
    """
    user_id = str(user.get("id"))
    now = datetime.now(timezone.utc)
    today = now.date()
    yesterday = today - timedelta(days=1)

    active_dates: Set[Any] = set()

    # 1. Last login date
    last_login = user.get("last_login")
    if last_login:
        if isinstance(last_login, str):
            try:
                last_login = datetime.fromisoformat(last_login)
            except Exception:
                last_login = None
        if last_login:
            active_dates.add(last_login.date())

    # 2. Enrollment completions & last accessed dates
    enr_repo = EnrollmentRepository()
    enrollments = enr_repo.list_student_enrollments(user_id)
    total_completed_lessons = 0
    certificates_count = 0

    for enr in enrollments:
        completed = enr.get("completed_lessons", [])
        total_completed_lessons += len(completed)
        if enr.get("progress_percent", 0.0) >= 100.0:
            certificates_count += 1

        last_acc = enr.get("last_accessed_at")
        if last_acc:
            if isinstance(last_acc, str):
                try:
                    last_acc = datetime.fromisoformat(last_acc)
                except Exception:
                    last_acc = None
            if last_acc:
                active_dates.add(last_acc.date())

    # 3. Lab submissions
    try:
        lab_sub_repo = LabSubmissionRepository()
        lab_subs = lab_sub_repo.find_many({"student_id": user_id}, limit=50)
        for sub in lab_subs:
            created = sub.get("created_at")
            if created:
                if isinstance(created, str):
                    try:
                        created = datetime.fromisoformat(created)
                    except Exception:
                        created = None
                if created:
                    active_dates.add(created.date())
    except Exception:
        pass

    # 4. Exam attempts
    try:
        exam_sub_repo = ExamSubmissionRepository()
        exam_subs = exam_sub_repo.list_by_student(user_id)
        for att in exam_subs:
            started = att.get("started_at")
            if started:
                if isinstance(started, str):
                    try:
                        started = datetime.fromisoformat(started)
                    except Exception:
                        started = None
                if started:
                    active_dates.add(started.date())
    except Exception:
        pass

    # Calculate consecutive active day streak walking backwards
    streak = 0
    if today in active_dates or yesterday in active_dates:
        curr = today if today in active_dates else yesterday
        while curr in active_dates:
            streak += 1
            curr -= timedelta(days=1)

    # Compute realistic total study hours:
    # ~25 minutes per completed lesson + ~15 minutes per active day
    total_study_hours = round((total_completed_lessons * 25.0 + len(active_dates) * 15.0) / 60.0, 1)

    return {
        "current_streak_days": max(1 if today in active_dates else 0, streak),
        "total_study_hours": total_study_hours,
        "total_completed_lessons": total_completed_lessons,
        "certificates_count": certificates_count,
        "active_days_count": len(active_dates)
    }
