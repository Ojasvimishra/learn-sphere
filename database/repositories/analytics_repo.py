"""
LearnSphere - Analytics & Concurrency Audit Repository (Tier 3)
Tracks system benchmark records, throughput metrics, and audit logs.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List
from database.repositories.base import BaseRepository


class AnalyticsRepository(BaseRepository):
    def __init__(self):
        super().__init__("audit_logs")

    def log_activity(self, user_id: str, action: str, ip_address: str, metadata: Dict[str, Any] = None):
        """Asynchronously or synchronously records activity audit logs."""
        try:
            doc = {
                "user_id": user_id,
                "action": action,
                "ip_address": ip_address,
                "metadata": metadata or {},
                "timestamp": datetime.now(timezone.utc)
            }
            self.insert_one(doc)
        except Exception:
            pass  # Do not block main thread

    def record_benchmark(self, concurrent_users: int, total_requests: int, avg_latency_ms: float, p99_latency_ms: float, rps: float, success_rate: float):
        try:
            self.collection.database["benchmarks"].insert_one({
                "concurrent_users": concurrent_users,
                "total_requests": total_requests,
                "avg_latency_ms": round(avg_latency_ms, 2),
                "p99_latency_ms": round(p99_latency_ms, 2),
                "requests_per_second": round(rps, 2),
                "success_rate_percent": round(success_rate, 2),
                "timestamp": datetime.now(timezone.utc)
            })
        except Exception:
            pass

    def get_latest_benchmarks(self, limit: int = 10) -> List[Dict[str, Any]]:
        cursor = self.collection.database["benchmarks"].find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
        return list(cursor)
