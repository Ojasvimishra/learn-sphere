"""
Migration 0002: Seed EdTech Initial Data
Safely seeds digital library textbooks & smart study guides,
smart education course tracks, and student innovation showcase projects.
SECURITY COMPLIANCE:
Demo user accounts are ONLY seeded when DEBUG=True or SEED_DEMO_DATA=1.
Passwords are read strictly from environment variables (DEMO_ADMIN_PASSWORD, etc.)
and are never hardcoded. In production, user seeding is completely bypassed.
"""

import os
import secrets
import string
from datetime import datetime, timezone
from django.contrib.auth.hashers import make_password


def generate_secure_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def up(db):
    print(" -> Seeding initial EdTech digital books and learning tracks...")
    now = datetime.now(timezone.utc)

    # 1. Seed Initial Users ONLY if DEBUG or SEED_DEMO_DATA is enabled
    is_debug = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    seed_demo = os.getenv("SEED_DEMO_DATA", "0") == "1"

    users_col = db["users"]
    admin_user = None
    mentor_user = None
    student_user = None

    if is_debug or seed_demo:
        admin_pass = os.getenv("DEMO_ADMIN_PASSWORD") or generate_secure_password()
        educator_pass = os.getenv("DEMO_EDUCATOR_PASSWORD") or generate_secure_password()
        student_pass = os.getenv("DEMO_STUDENT_PASSWORD") or generate_secure_password()

        print(" [SECURITY] Seeding demo accounts (DEBUG / SEED_DEMO_DATA enabled):")
        if not os.getenv("DEMO_ADMIN_PASSWORD"):
            print(f"   -> Generated Admin Password: {admin_pass}")

        seed_users = [
            {
                "username": "admin",
                "email": "admin@learnsphere.io",
                "password_hash": make_password(admin_pass),
                "role": "super_admin",
                "full_name": "LearnSphere System Administrator",
                "bio": "Lead Infrastructure Architect for LearnSphere Smart Education Portal.",
                "is_active": True,
                "is_approved": True,
                "failed_login_attempts": 0,
                "locked_until": None,
                "enrolled_courses": [],
                "bookmarked_resources": [],
                "created_at": now,
                "updated_at": now,
                "last_login": None
            },
            {
                "username": "sarah_mentor",
                "email": "mentor@learnsphere.io",
                "password_hash": make_password(educator_pass),
                "role": "educator",
                "full_name": "Prof. Sarah Jenkins",
                "bio": "Dean of Digital Learning & Senior Mentor in Smart Educational Technologies.",
                "is_active": True,
                "is_approved": True,
                "failed_login_attempts": 0,
                "locked_until": None,
                "enrolled_courses": [],
                "bookmarked_resources": [],
                "created_at": now,
                "updated_at": now,
                "last_login": None
            },
            {
                "username": "alex_student",
                "email": "student@learnsphere.io",
                "password_hash": make_password(student_pass),
                "role": "student",
                "full_name": "Alex Chen",
                "bio": "Undergraduate Student Researcher in Smart Education & Adaptive Learning.",
                "is_active": True,
                "is_approved": True,
                "failed_login_attempts": 0,
                "locked_until": None,
                "enrolled_courses": [],
                "bookmarked_resources": [],
                "created_at": now,
                "updated_at": now,
                "last_login": None
            }
        ]
        for u in seed_users:
            users_col.update_one({"email": u["email"]}, {"$setOnInsert": u}, upsert=True)

        admin_user = users_col.find_one({"email": "admin@learnsphere.io"})
        student_user = users_col.find_one({"email": "student@learnsphere.io"})
        mentor_user = users_col.find_one({"email": "mentor@learnsphere.io"})
    else:
        print(" [SECURITY] Production migration: skipping demo user account seeding.")

    # 2. Seed Digital Books & Smart Study Resources (Google Books Inspired EdTech Library)
    res_col = db["resources"]

    seed_books = [
        {
            "url": "https://books.google.com/smart-education-digital-age",
            "title": "Smart Education: Concepts and Paradigms for the Digital Age",
            "description": "An essential guide exploring how digital technologies enable learners to learn more effectively, efficiently, flexibly, and comfortably. Covers intelligent tutoring systems, cognitive load management, and adaptive assessment design.",
            "relevance": "high",
            "tags": ["smart-education", "cognitive-learning", "pedagogy", "edtech"],
            "category": "Smart Education & Pedagogy",
            "source": "Oxford Academic Press",
            "markdown": """# Key Principles of Smart Education

1. **Effective Learning**: Aligning digital curriculum with cognitive mastery rather than rote retention.
2. **Efficient Learning**: Minimizing extraneous cognitive friction through high-yield interactive modules.
3. **Flexible Learning**: Self-paced, non-linear progression accessible anytime, anywhere across devices.
4. **Comfortable Learning**: Accessible typography, multi-modal audio/visual aids, and ergonomic study pacing.""",
            "highlights": "Comprehensive analysis of modern digital learning environments, adaptive feedback loops, and empirical student engagement metrics.",
            "views": 620,
            "bookmarks_count": 142,
            "created_at": now,
            "updated_at": now
        },
        {
            "url": "https://books.google.com/foundations-of-adaptive-learning",
            "title": "Adaptive Learning Systems: Algorithms and Student Modeling",
            "description": "Explores how modern educational platforms model student knowledge states using Bayesian Knowledge Tracing and Deep Knowledge Tracing to provide bespoke, individualized study paths.",
            "relevance": "high",
            "tags": ["adaptive-learning", "ai-in-education", "student-modeling"],
            "category": "AI in Education",
            "source": "MIT Press",
            "markdown": """```python
# Knowledge Tracing probability update
def update_mastery(prior_mastery, student_correct, slip=0.1, guess=0.2):
    if student_correct:
        num = prior_mastery * (1 - slip)
        den = num + (1 - prior_mastery) * guess
    else:
        num = prior_mastery * slip
        den = num + (1 - prior_mastery) * (1 - guess)
    return num / den
```""",
            "highlights": "Mathematical foundations for adaptive test sequencing and automated student proficiency estimation.",
            "views": 540,
            "bookmarks_count": 98,
            "created_at": now,
            "updated_at": now
        },
        {
            "url": "https://books.google.com/modern-python-full-stack",
            "title": "High-Performance Full Stack Engineering with Python & MongoDB",
            "description": "A comprehensive textbook on architecting enterprise-grade 3-Tier web platforms with low latency using Django, REST APIs, and connection-pooled MongoDB.",
            "relevance": "high",
            "tags": ["django", "mongodb", "3-tier-architecture"],
            "category": "Computer Science & Engineering",
            "source": "O'Reilly Media",
            "markdown": """# 3-Tier Architecture Pattern
- **Tier 1 (Presentation)**: Material Design 3 UI, templates, and asynchronous AJAX interactions.
- **Tier 2 (Logic)**: Decoupled Python services, RBAC authorization, and sliding window rate limiting.
- **Tier 3 (Data)**: Connection-pooled MongoDB with compound indexes and query sanitization.""",
            "highlights": "Real-world connection pool tuning, B-tree index strategies, and memory optimization.",
            "views": 780,
            "bookmarks_count": 215,
            "created_at": now,
            "updated_at": now
        },
        {
            "url": "https://books.google.com/data-structures-visualized",
            "title": "Data Structures and Algorithm Design: An Interactive Approach",
            "description": "Clear conceptual explanations of fundamental computer science algorithms: graph theory, dynamic programming, tree traversals, and asymptotic analysis with visual diagrams.",
            "relevance": "high",
            "tags": ["algorithms", "data-structures", "computer-science"],
            "category": "Computer Science & Engineering",
            "source": "Cambridge University Press",
            "markdown": """```python
def binary_search(arr, target):
    low, high = 0, len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1
```""",
            "highlights": "Visual algorithm complexity guides and interactive step-by-step memory traces.",
            "views": 690,
            "bookmarks_count": 178,
            "created_at": now,
            "updated_at": now
        },
        {
            "url": "https://books.google.com/inclusive-classroom-ux",
            "title": "Designing Comfortable Learning: Ergonomics and Inclusive EdTech UX",
            "description": "How to design digital education platforms that reduce cognitive fatigue. Covers dyslexia-friendly typography, accessible color contrast ratios, screen reader optimization, and wellness breaks.",
            "relevance": "high",
            "tags": ["accessible-design", "ux-design", "comfortable-learning"],
            "category": "Smart Education & Pedagogy",
            "source": "Harvard Graduate School of Education",
            "markdown": """# Accessibility Checkpoints for Smart Classrooms
- WCAG 2.1 AAA contrast compliance for reading surfaces.
- Dynamic font scaling and kerning controls for neurodiverse readers.
- Keyboard-only navigation across all interactive quiz components.
- Automatic session pacing to avoid digital eyestrain.""",
            "highlights": "Actionable design patterns for creating stress-free digital study environments.",
            "views": 410,
            "bookmarks_count": 89,
            "created_at": now,
            "updated_at": now
        },
        {
            "url": "https://books.google.com/collaborative-learning-networks",
            "title": "Peer Collaboration in the Digital Age: Building Learning Communities",
            "description": "Studies the impact of student-led innovation hubs, peer code reviews, and project showcases on academic outcomes and critical problem-solving skills.",
            "relevance": "high",
            "tags": ["peer-learning", "student-innovation", "collaboration"],
            "category": "Student Innovation & Research",
            "source": "Stanford Educational Review",
            "markdown": """# The Power of Peer Review
- Students who receive structured peer feedback demonstrate 40% higher conceptual retention.
- Publicly showcasing prototypes increases learner motivation and accountability.
- Upvoting and constructive discussions foster a vibrant classroom knowledge commons.""",
            "highlights": "Empirical studies demonstrating that student-led showcases boost STEM retention by 35%.",
            "views": 480,
            "bookmarks_count": 104,
            "created_at": now,
            "updated_at": now
        }
    ]

    for b in seed_books:
        res_col.update_one({"url": b["url"]}, {"$setOnInsert": b}, upsert=True)

    # 3. Seed Smart Education Courses (4 Core Tracks) with Rich Modules & Lessons
    courses_col = db["courses"]
    courses_col.delete_many({})

    seed_courses = [
        {
            "title": "Smart Education & AI-Driven Digital Learning",
            "tagline": "A concept that describes learning in digital age — learn more effectively, efficiently, flexibly and comfortably.",
            "description": "Explores the fundamental paradigm shift from static classrooms to personalized, data-driven smart education ecosystems. Covers intelligent tutoring systems, adaptive learning algorithms, and digital knowledge graphs.",
            "level": "Beginner",
            "duration_hours": 14,
            "instructor_name": "Prof. Sarah Jenkins",
            "instructor_id": str(mentor_user["_id"]) if mentor_user else "educator_01",
            "category": "Smart Education & Pedagogy",
            "badge": "Core Track",
            "rating": 4.98,
            "status": "published",
            "thumbnail_gradient": "linear-gradient(135deg, #1a73e8 0%, #4285f4 100%)",
            "modules": [
                {
                    "id": "mod_1",
                    "title": "Module 1: Foundations of Smart Education",
                    "order": 1,
                    "lessons": [
                        {
                            "id": "les_smart_1",
                            "title": "1.1 Introduction to Smart Learning Paradigms",
                            "type": "video",
                            "duration": "25m",
                            "duration_minutes": 25,
                            "video_url": "",
                            "content_markdown": "# What is Smart Education?\n\nSmart Education represents the fusion of digital technologies with cognitive science to create adaptive, highly personalized learning pathways. It enables learners to study:\n\n1. **Effectively**: Aligning tasks with long-term retention goals.\n2. **Efficiently**: Removing friction and cognitive overload.\n3. **Flexibly**: Learn anytime, anywhere, on any device.\n4. **Comfortably**: Ergonomic pacing and stress-free mastery.",
                            "is_free_preview": True,
                            "status": "unlocked",
                            "order": 1
                        },
                        {
                            "id": "les_smart_2",
                            "title": "1.2 Cognitive Load Management in Digital Spaces",
                            "type": "reading",
                            "duration": "20m",
                            "duration_minutes": 20,
                            "content_markdown": "# Cognitive Load Management\n\nSweller's Cognitive Load Theory identifies three forms of load:\n\n- **Intrinsic Load**: Inherent difficulty of the material.\n- **Extraneous Load**: Friction introduced by poor interface or confusing explanations.\n- **Germane Load**: Mental processing devoted to processing information and constructing schemas.\n\nSmart Education platforms intentionally minimize extraneous load to maximize germane schema building.",
                            "is_free_preview": True,
                            "status": "unlocked",
                            "order": 2
                        }
                    ]
                },
                {
                    "id": "mod_2",
                    "title": "Module 2: Adaptive Algorithms & Real-Time Feedback",
                    "order": 2,
                    "lessons": [
                        {
                            "id": "les_smart_3",
                            "title": "2.1 Bayesian Knowledge Tracing & Student Models",
                            "type": "video",
                            "duration": "35m",
                            "duration_minutes": 35,
                            "is_free_preview": False,
                            "status": "locked",
                            "order": 1
                        },
                        {
                            "id": "les_smart_4",
                            "title": "2.2 Designing Comfortable Learning Interfaces",
                            "type": "reading",
                            "duration": "25m",
                            "duration_minutes": 25,
                            "is_free_preview": False,
                            "status": "locked",
                            "order": 2
                        }
                    ]
                }
            ],
            "modules_count": 2,
            "lessons_count": 4,
            "enrolled_count": 412,
            "created_at": now,
            "updated_at": now
        },
        {
            "title": "Computer Science Foundations & Interactive Problem Solving",
            "tagline": "Master core algorithms, data structures, and computational thinking with visual diagrams.",
            "description": "A student-centric course breaking down core computer science topics into digestible, high-yield lessons with interactive coding exercises and real-world problem sets.",
            "level": "Intermediate",
            "duration_hours": 18,
            "instructor_name": "Prof. Sarah Jenkins",
            "instructor_id": str(mentor_user["_id"]) if mentor_user else "educator_01",
            "category": "Computer Science & Engineering",
            "badge": "Essential STEM",
            "rating": 4.96,
            "status": "published",
            "thumbnail_gradient": "linear-gradient(135deg, #1e8e3e 0%, #34a853 100%)",
            "modules": [
                {
                    "id": "mod_cs_1",
                    "title": "Module 1: Computational Complexity & Big-O",
                    "order": 1,
                    "lessons": [
                        {
                            "id": "les_cs_1",
                            "title": "1.1 Understanding Asymptotic Growth Rates",
                            "type": "video",
                            "duration": "30m",
                            "duration_minutes": 30,
                            "is_free_preview": True,
                            "status": "unlocked",
                            "order": 1
                        },
                        {
                            "id": "les_cs_2",
                            "title": "1.2 Binary Search & Logarithmic Time Complexity",
                            "type": "reading",
                            "duration": "25m",
                            "duration_minutes": 25,
                            "is_free_preview": False,
                            "status": "locked",
                            "order": 2
                        }
                    ]
                }
            ],
            "modules_count": 1,
            "lessons_count": 2,
            "enrolled_count": 523,
            "created_at": now,
            "updated_at": now
        },
        {
            "title": "High-Performance 3-Tier Enterprise Systems in Django & MongoDB",
            "tagline": "Build mission-critical platforms capable of serving high-concurrency student workloads with low latency.",
            "description": "Learn how to architect high-throughput educational web applications with strict separation of Presentation, Business Logic, and MongoDB data tiers. Includes connection pooling, indexing, caching, and rate limiting.",
            "level": "Advanced",
            "duration_hours": 24,
            "instructor_name": "LearnSphere System Administrator",
            "instructor_id": str(admin_user["_id"]) if admin_user else "admin_01",
            "category": "Computer Science & Engineering",
            "badge": "Production Grade",
            "rating": 4.99,
            "status": "published",
            "thumbnail_gradient": "linear-gradient(135deg, #9334e6 0%, #a855f7 100%)",
            "modules": [
                {
                    "id": "mod_arch_1",
                    "title": "Module 1: 3-Tier Layering & Separation of Concerns",
                    "order": 1,
                    "lessons": [
                        {
                            "id": "les_arch_1",
                            "title": "1.1 Presentation, Service, and Repository Boundaries",
                            "type": "video",
                            "duration": "45m",
                            "duration_minutes": 45,
                            "is_free_preview": True,
                            "status": "unlocked",
                            "order": 1
                        }
                    ]
                }
            ],
            "modules_count": 1,
            "lessons_count": 1,
            "enrolled_count": 645,
            "created_at": now,
            "updated_at": now
        }
    ]

    for c in seed_courses:
        courses_col.update_one({"title": c["title"]}, {"$setOnInsert": c}, upsert=True)

    # 4. Seed Student Innovation Showcase Projects
    proj_col = db["projects"]
    seed_projects = [
        {
            "title": "NeuroPulse: Adaptive Learning Assistant for Neurodiverse Students",
            "abstract": "An open-source browser companion and study assistant that dynamically adjusts font kerning, contrast, and sentence complexity using lightweight AI to reduce cognitive fatigue in real-time.",
            "author_id": str(student_user["_id"]) if student_user else "student_01",
            "author_name": "Alex Chen",
            "tech_stack": ["Python", "Django", "MongoDB", "WebExtensions", "TensorFlow Lite"],
            "category": "Smart Education",
            "repo_url": "https://github.com/learnsphere-innovations/neuropulse",
            "demo_url": "https://neuropulse.learnsphere.io",
            "upvotes": 58,
            "upvoted_by": [],
            "status": "published",
            "comments": [
                {
                    "user_id": str(mentor_user["_id"]) if mentor_user else "mentor_01",
                    "user_name": "Prof. Sarah Jenkins",
                    "text": "Brilliant concept! The dyslexia-friendly layout algorithm showed impressive empirical improvements in reading speed.",
                    "created_at": now.isoformat()
                }
            ],
            "created_at": now,
            "updated_at": now
        },
        {
            "title": "ClassSphere: Real-Time Collaborative Study Canvas & Whiteboard",
            "abstract": "A distributed vector whiteboard allowing remote student study groups to brainstorm, sketch math proofs, and share interactive Python code snippets simultaneously with low latency synchronization.",
            "author_id": str(student_user["_id"]) if student_user else "student_01",
            "author_name": "Alex Chen & Team",
            "tech_stack": ["WebSockets", "Django Channels", "MongoDB", "Canvas API"],
            "category": "Student Innovation & Collaboration",
            "repo_url": "https://github.com/learnsphere-innovations/classsphere",
            "demo_url": "https://classsphere.learnsphere.io",
            "upvotes": 74,
            "upvoted_by": [],
            "status": "published",
            "comments": [
                {
                    "user_id": str(admin_user["_id"]) if admin_user else "admin_01",
                    "user_name": "LearnSphere System Administrator",
                    "text": "Excellent WebSocket optimization. Connection memory footprint stayed minimal.",
                    "created_at": now.isoformat()
                }
            ],
            "created_at": now,
            "updated_at": now
        }
    ]

    for p in seed_projects:
        proj_col.update_one({"title": p["title"]}, {"$setOnInsert": p}, upsert=True)

    print(" -> Seeding complete: Digital Books Library, Courses, and Innovation Projects are active.")


def down(db):
    print(" -> Clearing seeded data...")
    db["resources"].delete_many({})
    db["courses"].delete_many({})
    db["projects"].delete_many({})
