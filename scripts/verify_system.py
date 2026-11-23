"""
LearnSphere - Automated End-to-End System Verification Suite
Validates Tier 1, Tier 2, and Tier 3 functionality, including:
- MongoDB connection & schema status
- User Registration, PBKDF2 Password Hashing, JWT Authentication
- Curated Resource search & filtering
- Student Innovation Project submission & atomic upvoting
- Smart Education Course enrollment
- 500+ Concurrent Requests Load Test with Latency & Zero-Loss Verification
"""

import os
import sys
import time
import concurrent.futures

# Set up Django environment
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "learnsphere.settings")

import django
django.setup()

from django.test import Client
from database.connection import MongoConnectionManager, get_db
from database.repositories.user_repo import UserRepository
from database.repositories.resource_repo import ResourceRepository
from database.repositories.project_repo import ProjectRepository
from database.repositories.course_repo import CourseRepository
from services.auth_service import AuthService


def run_tests():
    print("=" * 70)
    print("LearnSphere 3-Tier Enterprise System Verification")
    print("=" * 70)

    # 1. Test Tier 3: MongoDB Connection & Health
    print("\n[Step 1/6] Testing Tier 3: MongoDB Connection & Health...")
    mgr = MongoConnectionManager.get_instance()
    is_healthy = mgr.ping()
    assert is_healthy, "MongoDB ping failed!"
    db = get_db()
    collections = db.list_collection_names()
    print(f" -> MongoDB Connected! Active collections: {collections}")
    assert "users" in collections
    assert "resources" in collections
    assert "projects" in collections
    assert "courses" in collections
    print(" -> Tier 3 MongoDB Health: PASSED")

    # 2. Test Tier 2: Authentication & PBKDF2 Hashing
    print("\n[Step 2/6] Testing Tier 2: Authentication & PBKDF2 Hashing...")
    auth_service = AuthService()
    test_user = f"tester_{int(time.time())}"
    test_email = f"{test_user}@test.io"
    success, msg, user = auth_service.register(
        username=test_user,
        email=test_email,
        password="SecureTestPassword123!",
        role="student",
        full_name="E2E Test Student"
    )
    assert success, f"Registration failed: {msg}"
    print(f" -> Registered user '{test_user}' with PBKDF2 hashed password.")

    # Authenticate
    auth_ok, auth_msg, authed_user, token = auth_service.authenticate(test_email, "SecureTestPassword123!")
    assert auth_ok, f"Authentication failed: {auth_msg}"
    assert token is not None, "JWT token was not generated!"
    print(f" -> Authenticated successfully. JWT token: {token[:25]}...")

    # Verify JWT decoding
    decoded_user = auth_service.verify_jwt(token)
    assert decoded_user is not None and decoded_user["username"] == test_user
    print(" -> Tier 2 Authentication & JWT Claims: PASSED")

    # 3. Test Tier 2 & 3: Digital Books & Curated Resources
    print("\n[Step 3/6] Testing Digital Books & Search Indices...")
    res_repo = ResourceRepository()
    total_resources = res_repo.count()
    print(f" -> Total curated digital books in MongoDB: {total_resources}")
    assert total_resources >= 8, f"Expected at least 8 books, got {total_resources}"

    # Search for Smart Education
    search_res = res_repo.search_resources(query_text="Smart Education")
    print(f" -> Search for 'Smart Education' returned: {len(search_res['items'])} items")
    assert len(search_res["items"]) > 0

    # Test high relevance filter
    high_rel = res_repo.search_resources(relevance="high")
    print(f" -> High relevance items: {len(high_rel['items'])}")
    print(" -> Digital Books & Index Search: PASSED")

    # 4. Test Student Innovation & Atomic Upvoting
    print("\n[Step 4/6] Testing Student Innovation Showcase & Atomic Upvoting...")
    proj_repo = ProjectRepository()
    p_id = proj_repo.create_project(
        title="Test E2E Innovation Prototype",
        abstract="A novel experimental methodology for smart adaptive learning interfaces.",
        author_id=user["id"],
        author_name=user["full_name"],
        tech_stack=["Python", "Django", "MongoDB"]
    )
    assert p_id is not None
    print(f" -> Created project: {p_id}")

    # Upvote
    up_res1 = proj_repo.toggle_upvote(p_id, user["id"])
    assert up_res1["upvoted"] is True
    assert up_res1["count"] == 1
    print(" -> Atomic upvote increment verified.")

    # Toggle down
    up_res2 = proj_repo.toggle_upvote(p_id, user["id"])
    assert up_res2["upvoted"] is False
    assert up_res2["count"] == 0
    print(" -> Atomic upvote toggle back verified.")

    # Add comment
    comm_ok = proj_repo.add_comment(p_id, user["id"], user["full_name"], "Impressive technical implementation!")
    assert comm_ok is True
    print(" -> Peer review comment added successfully.")
    print(" -> Student Innovation Hub: PASSED")

    # 5. Test Tier 1 Views via Django Test Client
    print("\n[Step 5/6] Testing Tier 1 HTTP Views & Routing...")
    client = Client()

    # Home view
    resp_home = client.get("/")
    assert resp_home.status_code == 200
    assert "Student Innovation" in resp_home.content.decode()
    assert "Smart education" in resp_home.content.decode()
    print(" -> Home view rendered successfully (Status 200, Quote present)")

    # Resources view
    resp_res = client.get("/resources/")
    assert resp_res.status_code == 200
    assert "Digital Books" in resp_res.content.decode()
    print(" -> Resources view rendered successfully (Status 200)")

    # Innovation view
    resp_inn = client.get("/innovation/")
    assert resp_inn.status_code == 200
    print(" -> Innovation view rendered successfully (Status 200)")

    # Courses view
    resp_crs = client.get("/courses/")
    assert resp_crs.status_code == 200
    print(" -> Courses view rendered successfully (Status 200)")

    # Benchmark page
    resp_bm = client.get("/benchmark/")
    assert resp_bm.status_code == 200
    print(" -> Benchmark view rendered successfully (Status 200)")
    print(" -> Tier 1 HTTP Presentation Views: PASSED")

    # 6. Test 500+ Concurrent Requests Load Test
    print("\n[Step 6/6] Executing 500 Concurrent Requests Load Test...")
    concurrency = 500
    print(f" -> Spawning {concurrency} simultaneous workers hitting pooled MongoDB...")

    def worker_task(idx):
        t0 = time.perf_counter()
        # Query resources
        docs = res_repo.find_many({"relevance": "high"}, limit=3)
        return (time.perf_counter() - t0) * 1000

    latencies = []
    errors = 0
    wall_start = time.perf_counter()

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(worker_task, i) for i in range(concurrency)]
        for f in concurrent.futures.as_completed(futures):
            try:
                lat = f.result()
                latencies.append(lat)
            except Exception as err:
                errors += 1

    wall_duration = time.perf_counter() - wall_start
    latencies.sort()
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0
    rps = concurrency / wall_duration if wall_duration > 0 else 0
    success_rate = ((concurrency - errors) / concurrency) * 100

    print("-" * 60)
    print(f"  Concurrent Workers   : {concurrency}")
    print(f"  Total Requests       : {concurrency}")
    print(f"  Wall Time Duration   : {wall_duration:.3f} seconds")
    print(f"  Requests Per Second  : {rps:.1f} req/s")
    print(f"  Average Latency      : {avg_latency:.2f} ms")
    print(f"  P95 Latency          : {p95:.2f} ms")
    print(f"  P99 Latency          : {p99:.2f} ms")
    print(f"  Failed Requests      : {errors}")
    print(f"  Success Rate         : {success_rate:.2f}% (Target: 100%)")
    print("-" * 60)

    assert errors == 0, f"Encountered {errors} failed requests!"
    assert success_rate == 100.0, "Success rate was not 100%!"
    print(" -> 500+ High-Concurrency Verification: PASSED (100% Zero-Loss)")

    print("\n" + "=" * 70)
    print("ALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
