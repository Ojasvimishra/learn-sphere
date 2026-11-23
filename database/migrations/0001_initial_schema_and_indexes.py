"""
Migration 0001: Initial Schema and High-Performance Indexes
Creates collections and necessary indexing for high-concurrency (500+ req/s) operations.
"""

from pymongo import ASCENDING, DESCENDING, TEXT, IndexModel

def up(db):
    print(" -> Creating collections and setting up high-performance indexes...")

    # 1. Users Collection
    users_col = db["users"]
    users_indexes = [
        IndexModel([("email", ASCENDING)], unique=True, name="idx_users_email_unique"),
        IndexModel([("username", ASCENDING)], unique=True, name="idx_users_username_unique"),
        IndexModel([("role", ASCENDING)], name="idx_users_role"),
        IndexModel([("created_at", DESCENDING)], name="idx_users_created_at")
    ]
    users_col.create_indexes(users_indexes)

    # 2. Resources Collection (Web Scraping & Tech Articles)
    res_col = db["resources"]
    res_indexes = [
        IndexModel([("url", ASCENDING)], unique=True, name="idx_resources_url_unique"),
        IndexModel([("relevance", ASCENDING), ("created_at", DESCENDING)], name="idx_resources_relevance_date"),
        IndexModel([("tags", ASCENDING)], name="idx_resources_tags"),
        IndexModel([("views", DESCENDING)], name="idx_resources_views"),
        IndexModel(
            [("title", TEXT), ("description", TEXT), ("tags", TEXT)],
            name="idx_resources_text_search"
        )
    ]
    res_col.create_indexes(res_indexes)

    # 3. Innovation Projects Collection
    proj_col = db["projects"]
    proj_indexes = [
        IndexModel([("author_id", ASCENDING)], name="idx_projects_author"),
        IndexModel([("status", ASCENDING), ("upvotes", DESCENDING)], name="idx_projects_status_upvotes"),
        IndexModel([("category", ASCENDING)], name="idx_projects_category"),
        IndexModel([("created_at", DESCENDING)], name="idx_projects_created_at"),
        IndexModel(
            [("title", TEXT), ("abstract", TEXT), ("tech_stack", TEXT)],
            name="idx_projects_text_search"
        )
    ]
    proj_col.create_indexes(proj_indexes)

    # 4. Courses Collection (Smart Education Modules)
    course_col = db["courses"]
    course_indexes = [
        IndexModel([("level", ASCENDING)], name="idx_courses_level"),
        IndexModel([("enrolled_count", DESCENDING)], name="idx_courses_enrolled"),
        IndexModel([("rating", DESCENDING)], name="idx_courses_rating")
    ]
    course_col.create_indexes(course_indexes)

    # 5. Audit & Activity Logs Collection
    audit_col = db["audit_logs"]
    audit_indexes = [
        IndexModel([("user_id", ASCENDING), ("timestamp", DESCENDING)], name="idx_audit_user_time"),
        IndexModel([("action", ASCENDING)], name="idx_audit_action"),
        IndexModel([("timestamp", DESCENDING)], name="idx_audit_timestamp")
    ]
    audit_col.create_indexes(audit_indexes)

    # 6. Benchmark Performance Records
    bench_col = db["benchmarks"]
    bench_indexes = [
        IndexModel([("timestamp", DESCENDING)], name="idx_benchmarks_timestamp")
    ]
    bench_col.create_indexes(bench_indexes)

    print(" -> Indexes created successfully across all collections.")

def down(db):
    print(" -> Rolling back indexes...")
    for col_name in ["users", "resources", "projects", "courses", "audit_logs", "benchmarks"]:
        db[col_name].drop_indexes()
