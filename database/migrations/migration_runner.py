"""
LearnSphere - Database Migration Engine (Tier 3)
Tracks schema versions, index creation, and data seeding in MongoDB.
Ensures zero-downtime, idempotent database migrations with full audit trails.
"""

import importlib
import os
import sys
import time
from datetime import datetime, timezone
from typing import List, Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Ensure Django settings are configured for hashers and utilities
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "learnsphere.settings")
try:
    import django
    django.setup()
except Exception:
    pass

from database.connection import get_db

class MongoMigrationRunner:
    """
    Executes and tracks MongoDB schema migrations and index definitions.
    Maintains a versioned audit table '_schema_migrations'.
    """

    def __init__(self):
        self.db = get_db()
        self.migration_col = self.db["_schema_migrations"]

    def get_applied_migrations(self) -> List[str]:
        """Returns list of migration names already executed."""
        docs = self.migration_col.find({}, {"migration_name": 1}).sort("applied_at", 1)
        return [d["migration_name"] for d in docs]

    def discover_migrations(self) -> List[str]:
        """Discovers migration files in database/migrations/ sorted alphabetically."""
        migrations_dir = os.path.dirname(__file__)
        files = []
        for f in os.listdir(migrations_dir):
            if f.endswith(".py") and f[0].isdigit() and not f.startswith("__"):
                files.append(f[:-3])  # strip .py
        files.sort()
        return files

    def run_migrations(self) -> Dict[str, Any]:
        """Executes all pending migrations in order."""
        applied = set(self.get_applied_migrations())
        available = self.discover_migrations()
        pending = [m for m in available if m not in applied]

        results = {
            "applied_count": len(applied),
            "pending_count": len(pending),
            "executed": [],
            "status": "success"
        }

        if not pending:
            print("[Migrations] Database schema is already up to date.")
            return results

        print(f"[Migrations] Found {len(pending)} pending migration(s)...")

        for migration_name in pending:
            print(f"[Migrations] Applying: {migration_name}...")
            start_time = time.time()
            try:
                mod = importlib.import_module(f"database.migrations.{migration_name}")
                if hasattr(mod, "up"):
                    mod.up(self.db)
                duration_ms = round((time.time() - start_time) * 1000, 2)

                self.migration_col.insert_one({
                    "migration_name": migration_name,
                    "applied_at": datetime.now(timezone.utc),
                    "duration_ms": duration_ms,
                    "status": "applied"
                })

                results["executed"].append({
                    "name": migration_name,
                    "duration_ms": duration_ms
                })
                print(f"[Migrations] Successfully applied {migration_name} in {duration_ms}ms")
            except Exception as e:
                print(f"[Migrations ERROR] Failed applying {migration_name}: {str(e)}")
                results["status"] = "failed"
                results["error"] = str(e)
                raise e

        return results

    def status(self):
        """Displays status of all migrations."""
        applied = {d["migration_name"]: d for d in self.migration_col.find()}
        available = self.discover_migrations()

        print("\n================== LearnSphere MongoDB Migrations ==================")
        print(f"{'Migration Name':<45} | {'Status':<10} | {'Applied At':<25}")
        print("-" * 85)
        for m in available:
            if m in applied:
                at = applied[m].get("applied_at").strftime("%Y-%m-%d %H:%M:%S UTC") if applied[m].get("applied_at") else "N/A"
                print(f"{m:<45} | {'APPLIED':<10} | {at:<25}")
            else:
                print(f"{m:<45} | {'PENDING':<10} | {'-':<25}")
        print("====================================================================\n")


    def run(self):
        return self.run_migrations()


if __name__ == "__main__":
    runner = MongoMigrationRunner()
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        runner.status()
    else:
        runner.run()

