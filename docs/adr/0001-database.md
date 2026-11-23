# Architecture Decision Record (ADR) 0001: Data Persistence Architecture

## Status
Accepted

## Context
LearnSphere is transitioning from a student innovation hub and digital library into a full-scale EdTech platform (comparable to PhysicsWallah, Coursera, and Udemy). Core capabilities require support for:
1. High-throughput recorded and live class streaming metadata.
2. Heterogeneous course syllabi, interactive lesson checkpoints, and markdown articles.
3. Rapid question-bank composition, multiple-choice quizzes, code submission logs, and proctored exam attempts.
4. Real-time doubt-solving discussions and student innovation showcases.
5. High-concurrency operations under heavy traffic spikes.

Two primary architectural paths were evaluated:
- **Option A: Pure PostgreSQL + Django ORM**. Standard relational model, foreign keys, migrations via Django.
- **Option B: MongoDB + PyMongo Repository Pattern (Tier 3) with Redis for transient caches & rate limits**. Native JSON/BSON document persistence, schema flexibility for syllabi and code execution telemetry, high read performance with compound indexes, decoupled repository pattern.

## Decision
We adopt **Option B: MongoDB (PyMongo Repository Architecture) + Redis + Canonical Extended JSON backups**:
1. **Repository Pattern (Tier 3)**:
   - All MongoDB access is strictly abstracted behind clean repositories (`UserRepository`, `CourseRepository`, `ResourceRepository`, `AuditRepository`, etc.).
   - Django views never execute direct database queries, preserving architectural layering and testability.
2. **Schema & Boundary Validation**:
   - Boundary validation is enforced using `core/validation.py` before queries reach the database layer, rejecting raw operator injection (`$where`, `$regex`, `$gt`) and ensuring strict typing.
3. **Connection Pooling**:
   - Sized conservatively (`maxPoolSize=20`, `minPoolSize=2` for dev; environment-driven for multi-process production) to prevent worker connection pool multiplication.
4. **Audit Logging**:
   - Security-critical events (authentication failures, role upgrades, grade overrides, proctoring violations) are written to an append-only `audit_logs` collection where update and delete operations are prohibited.
5. **Backups**:
   - Backups use Canonical Extended JSON with SHA-256 checksums, preserving exact BSON types (`ObjectId`, `ISODate`) and supporting verification modes.

## Consequences
- **Positive**: Exceptional flexibility for dynamic course curriculums, embedded quiz blocks, and code telemetry; simple horizontal scaling.
- **Mitigations**: Boundary validation replaces ORM constraints; transaction sessions (`client.start_session()`) are used for multi-document operations when replica sets are enabled.
