# Architecture & Design Decisions (LearnSphere 2.0)

## 1. 5-Role Role-Based Access Control (RBAC)
The platform establishes a strict 5-tier role hierarchy:
1. `super_admin`: Global platform governor, security auditor, role administrator.
2. `dept_admin`: Department-level curriculum approval, educator management, batch student onboarding.
3. `moderator`: Community discussion oversight, project showcase review, dispute resolution.
4. `educator`: Course authoring, live class hosting, quiz/exam creation, grade management.
5. `student`: Enrolling, video streaming, taking exams, participating in labs, submitting innovations.

All public registrations default to `student`. Educator applications enter an approval queue (`is_approved=False`) requiring administrative clearance.

## 2. Authentication & Token Lifecycle
- **Password Hasher**: Argon2id primary hasher with PBKDF2 compatibility.
- **Account Lockout**: 5 failed consecutive attempts within 15 minutes trigger a temporary 15-minute lock.
- **Token Security**:
  - Access Token: 15-minute lifetime, signed with HMAC-SHA256.
  - Refresh Token: 7-day lifetime, rotates on every refresh. Previous refresh token is immediately revoked in Redis/Cache.
  - Cookies: Transmitted with `HttpOnly`, `SameSite=Lax`, and `Secure` (in HTTPS/production).

## 3. Rate Limiting & Proxy Boundary
- Redis sliding window rate limiter with in-memory fallback.
- Granular per-endpoint quotas:
  - Login/Register: 5 req/min per IP + account identifier.
  - AI Tutor: 50 req/day per user.
  - API endpoints: 120 req/min per IP.
  - Public pages: 300 req/min per IP.
- Client IP resolution strictly inspects `X-Forwarded-For` only when requests originate from configured `TRUSTED_PROXIES`.

## 4. Immutable Audit Trail
- Stored in append-only collection `audit_logs`.
- Logs record: timestamp (UTC), actor, action code, resource, IP address, user agent, and contextual payload.
- Repository explicitly overrides and disallows `update_one` and `delete_one`.
