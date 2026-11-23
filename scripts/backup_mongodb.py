"""
LearnSphere - Database Backup & Disaster Recovery Utility (Tier 3)
Exports and restores collections to/from structured JSON/BSON archives.
"""

import os
import json
import argparse
from datetime import datetime
from bson import json_util
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database.connection import get_db


def backup(output_dir: str = "backups"):
    db = get_db()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_dir = os.path.join(output_dir, f"backup_{timestamp}")
    os.makedirs(target_dir, exist_ok=True)

    collections = ["users", "resources", "projects", "courses", "audit_logs", "_schema_migrations"]
    summary = {}

    print(f"[Backup] Exporting MongoDB database '{db.name}' to {target_dir}...")
    for col_name in collections:
        col = db[col_name]
        docs = list(col.find({}))
        file_path = os.path.join(target_dir, f"{col_name}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(json_util.dumps(docs, indent=2))
        summary[col_name] = len(docs)
        print(f" -> Backed up '{col_name}': {len(docs)} documents.")

    meta_path = os.path.join(target_dir, "metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({
            "database": db.name,
            "timestamp": timestamp,
            "collections": summary
        }, f, indent=2)

    print(f"[Backup COMPLETE] Archive saved successfully at: {target_dir}")
    return target_dir


def restore(source_dir: str):
    if not os.path.exists(source_dir):
        print(f"[Restore ERROR] Directory does not exist: {source_dir}")
        return

    db = get_db()
    print(f"[Restore] Restoring database from {source_dir}...")
    for file_name in os.listdir(source_dir):
        if file_name.endswith(".json") and file_name != "metadata.json":
            col_name = file_name[:-5]
            file_path = os.path.join(source_dir, file_name)
            with open(file_path, "r", encoding="utf-8") as f:
                docs = json_util.loads(f.read())
            if docs:
                col = db[col_name]
                col.delete_many({})
                col.insert_many(docs)
                print(f" -> Restored '{col_name}': {len(docs)} documents.")

    print("[Restore COMPLETE] Database successfully restored.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LearnSphere MongoDB Backup & Restore")
    parser.add_argument("--action", choices=["backup", "restore"], default="backup")
    parser.add_argument("--path", type=str, default="backups")
    args = parser.parse_args()

    if args.action == "backup":
        backup(args.path)
    else:
        restore(args.path)
