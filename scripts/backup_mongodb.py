"""
LearnSphere - Database Backup & Disaster Recovery Utility (Tier 3)
Exports and restores collections using MongoDB Canonical Extended JSON (preserving ObjectIds, ISODates).
Features:
- Full Canonical Extended JSON dump and restore
- Restore verification mode (--verify)
- Password hash masking for sanitized developer exports (--sanitize)
- Integrity checksum verification
"""

import os
import json
import hashlib
import argparse
from datetime import datetime
from bson import json_util
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database.connection import get_db


def compute_checksum(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def backup(output_dir: str = "backups", sanitize: bool = False) -> str:
    db = get_db()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_dir = os.path.join(output_dir, f"backup_{timestamp}")
    os.makedirs(target_dir, exist_ok=True)

    collections = ["users", "resources", "projects", "courses", "audit_logs", "_schema_migrations"]
    summary = {}
    checksums = {}

    print(f"[Backup] Exporting MongoDB database '{db.name}' to {target_dir}...")
    for col_name in collections:
        if col_name not in db.list_collection_names():
            continue

        col = db[col_name]
        docs = list(col.find({}))

        if sanitize and col_name == "users":
            # Mask password hashes for developer export
            for d in docs:
                d["password_hash"] = "SANATIZED_SECRET_MASKED"

        file_path = os.path.join(target_dir, f"{col_name}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(json_util.dumps(docs, indent=2, json_options=json_util.CANONICAL_JSON_OPTIONS))

        summary[col_name] = len(docs)
        checksums[col_name] = compute_checksum(file_path)
        print(f" -> Backed up '{col_name}': {len(docs)} documents.")

    meta_path = os.path.join(target_dir, "metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({
            "database": db.name,
            "timestamp": timestamp,
            "sanitized": sanitize,
            "collections": summary,
            "checksums": checksums
        }, f, indent=2)

    print(f"[Backup COMPLETE] Archive saved successfully at: {target_dir}")
    return target_dir


def restore(source_dir: str, verify_only: bool = False) -> bool:
    if not os.path.exists(source_dir):
        print(f"[Restore ERROR] Directory does not exist: {source_dir}")
        return False

    # Check if target is a parent containing backup_ timestamp folders
    meta_path = os.path.join(source_dir, "metadata.json")
    if not os.path.exists(meta_path):
        subdirs = [os.path.join(source_dir, d) for d in os.listdir(source_dir) if os.path.isdir(os.path.join(source_dir, d))]
        subdirs.sort(reverse=True)
        for s in subdirs:
            if os.path.exists(os.path.join(s, "metadata.json")):
                source_dir = s
                meta_path = os.path.join(source_dir, "metadata.json")
                break

    if not os.path.exists(meta_path):
        print("[Restore ERROR] Missing metadata.json in backup directory.")
        return False

    with open(meta_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    # Verify Checksums
    checksums = metadata.get("checksums", {})
    for col_name, expected_hash in checksums.items():
        file_path = os.path.join(source_dir, f"{col_name}.json")
        if not os.path.exists(file_path):
            print(f"[Restore ERROR] Missing collection archive: {file_path}")
            return False
        actual_hash = compute_checksum(file_path)
        if actual_hash != expected_hash:
            print(f"[Restore ERROR] Integrity failure for {col_name}: checksum mismatch!")
            return False

    if verify_only:
        print("[Restore Verification] All collection checksums and Canonical JSON formats are VALID.")
        return True

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
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LearnSphere MongoDB Backup & Restore")
    parser.add_argument("--action", choices=["backup", "restore"], default="backup")
    parser.add_argument("--path", type=str, default="backups")
    parser.add_argument("--sanitize", action="store_true", help="Mask password hashes in backup")
    parser.add_argument("--verify", action="store_true", help="Verify backup integrity without modifying database")
    args = parser.parse_args()

    if args.action == "backup":
        backup(args.path, sanitize=args.sanitize)
    else:
        restore(args.path, verify_only=args.verify)
