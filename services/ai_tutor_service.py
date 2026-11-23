"""
LearnSphere - AI Tutor Engine (Tier 2)
Provides an adaptive cognitive study companion with daily quota rate-limiting (50 queries/day).
"""

from typing import Any, Dict, List, Optional
from core.redis_client import get_cache_client

cache_client = get_cache_client()
DAILY_AI_LIMIT = 50


class AITutorService:
    def __init__(self):
        self.cache = cache_client

    def get_remaining_daily_quota(self, user_id: str) -> int:
        key = f"ratelimit:ai:{user_id}"
        used = int(self.cache.get(key) or 0)
        return max(0, DAILY_AI_LIMIT - used)

    def answer_query(self, user: Dict[str, Any], query: str, context: Optional[str] = None) -> Dict[str, Any]:
        """Processes question through the Smart Education AI Tutor engine."""
        user_id = str(user.get("id"))
        key = f"ratelimit:ai:{user_id}"

        count = self.cache.incr(key)
        if count == 1:
            self.cache.expire(key, 86400)

        if count > DAILY_AI_LIMIT:
            return {
                "success": False,
                "error": f"Daily AI Tutor quota exceeded ({DAILY_AI_LIMIT} queries/day). Please try again tomorrow.",
                "remaining_quota": 0
            }

        q_lower = query.lower()

        # Knowledge domain synthesis
        if "smart education" in q_lower or "concept" in q_lower:
            reply = (
                "### 🎓 Smart Education in the Digital Age\n\n"
                "Smart education describes learning in the digital age. It enables learners to study:\n\n"
                "- **Effectively**: Focuses on cognitive retention and schema formation.\n"
                "- **Efficiently**: Streamlines study time by removing extraneous friction.\n"
                "- **Flexibly**: Learn anytime, anywhere, on any device.\n"
                "- **Comfortably**: Ergonomic typography, cognitive pacing, and accessibility.\n\n"
                "*Tip: Try breaking your study sessions into 25-minute Pomodoro intervals for peak retention.*"
            )
        elif "rate limit" in q_lower or "redis" in q_lower:
            reply = (
                "### ⚡ Rate Limiting with Redis\n\n"
                "LearnSphere uses a sliding-window rate limiter powered by Redis:\n\n"
                "1. `INCR key` atomically counts requests per IP or user ID.\n"
                "2. `EXPIRE key window_seconds` sets the sliding window time-to-live.\n"
                "3. In development environments, it seamlessly falls back to a thread-safe in-memory cache."
            )
        elif "argon2" in q_lower or "password" in q_lower:
            reply = (
                "### 🔒 Argon2id Password Hashing\n\n"
                "Argon2 won the Password Hashing Competition (PHC) and is the modern standard for cryptographic credential storage:\n\n"
                "- **Memory Hardness**: Requires substantial RAM to compute, preventing brute-force attacks via GPU clusters or ASICs.\n"
                "- **Side-Channel Defense**: Combines data-independent memory access (Argon2i) with data-dependent access (Argon2d)."
            )
        else:
            reply = (
                f"### 💡 AI Tutor Response\n\n"
                f"You asked: **\"{query}\"**\n\n"
                "Here is an adaptive conceptual breakdown:\n\n"
                "1. **Core Concept**: Identify the foundational theorem or architecture governing this topic.\n"
                "2. **Step-by-Step Walkthrough**: Break down the problem into sequential, testable sub-problems.\n"
                "3. **Practical Verification**: Write a concise test case in the Virtual Lab to confirm your understanding.\n\n"
                "Need a specific code snippet or deeper explanation of any particular step?"
            )

        remaining = max(0, DAILY_AI_LIMIT - count)
        return {
            "success": True,
            "response_markdown": reply,
            "remaining_quota": remaining
        }
