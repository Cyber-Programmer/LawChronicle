# LawChronicle Improvement Tasks Checklist

Use this enumerated checklist to track improvements. Each item is actionable and starts with a checkbox. Complete items in order unless noted otherwise.

1. [ ] Fix README formatting issues (headers, stray characters, typos) and correct broken links (e.g., Phase 4 API doc path and typo "endpointspplication").
2. [ ] Consolidate duplicated/conflicting progress sections in README (August 12 vs August 21) into a single accurate status.
3. [ ] Add a CONTRIBUTING.md with coding standards, commit conventions, branching model, and PR checklist.
4. [ ] Add a CODE_OF_CONDUCT.md aligned with project/community expectations.
5. [ ] Create high-level architecture diagram and data flow (frontend ↔ backend ↔ MongoDB/GridFS ↔ Azure OpenAI) under docs/architecture/.
6. [ ] Add ADRs (Architecture Decision Records) for key choices (FastAPI, MongoDB, SSE, Azure OpenAI, RBAC) under docs/adrs/.
7. [ ] Document environment configuration strategy and secrets management (map env.example to all required variables with descriptions).
8. [ ] Add security and privacy note for AI usage (prompt/response handling, PII redaction policies).

9. [ ] Establish consistent code style and linting for backend (Black, Ruff/Flake8, isort) and define configs.
10. [ ] Establish consistent code style and linting for frontend (ESLint + TypeScript rules + Prettier) and define configs.
11. [ ] Add pre-commit hooks to run formatters, linters, and basic tests on staged changes.
12. [ ] Add EditorConfig (.editorconfig) to enforce whitespace, line endings, and charset to avoid encoding issues (e.g., "�").
13. [ ] Configure type checking gates (mypy for Python; tsc --noEmit for frontend) in CI.

14. [ ] Backend: Standardize error handling with a global exception handler returning a consistent problem+json schema.
15. [ ] Backend: Introduce structured logging (JSON logs) with correlation/request IDs and user context.
16. [ ] Backend: Add OpenTelemetry tracing and basic metrics (requests, latency, background jobs) with FastAPI/ASGI middleware.
17. [ ] Backend: Implement configuration via Pydantic Settings with strict types and validation on startup.
18. [ ] Backend: Review authentication flow (JWT): add refresh tokens/rotation, short-lived access tokens, and clock skew handling.
19. [ ] Backend: Harden CORS configuration and define allowed origins per environment.
20. [ ] Backend: Add rate limiting middleware/policy per route category (auth, AI, data export) and document defaults.
21. [ ] Backend: Validate all request models with Pydantic (strict types), including file uploads and pagination parameters.
22. [ ] Backend: Define explicit response models and error codes for all endpoints (including SSE endpoints).
23. [ ] Backend: Introduce idempotency keys for background/batch operations to prevent duplicate processing.
24. [ ] Backend: Implement graceful shutdown hooks and cancellation for background tasks (SSE aware).
25. [ ] Backend: Add health endpoints: /health/ready and /health/live, including DB and external dependency checks.

26. [ ] Database: Audit and create necessary MongoDB indexes for frequent queries; document them under backend/app/core/database_indexes.md.
27. [ ] Database: Add connection pooling settings and timeouts; verify async driver usage across all services.
28. [ ] Database: Implement pagination and server-side filtering/sorting for all list endpoints.
29. [ ] Database: Define data retention/archival policy for GridFS and large exports; implement cleanup jobs.
30. [ ] Database: Add schema/version migrations approach or compatibility layer for evolving collections.

31. [ ] AI Integration: Add retry with exponential backoff and circuit breaker for Azure OpenAI calls.
32. [ ] AI Integration: Centralize prompt templates and version them; log prompt/response metadata with redaction.
33. [ ] AI Integration: Expand deterministic fallback (regex/rules) coverage and unit tests; expose confidence thresholds via config.
34. [ ] AI Integration: Implement rate limit handling and backpressure for batch AI jobs; surface progress ETA in SSE.

35. [ ] Frontend: Introduce a unified API layer with typed clients and error normalization (including SSE handling utilities).
36. [ ] Frontend: Add global error boundary and toast/alert system for surfaced errors and long-running operations.
37. [ ] Frontend: Ensure strict TypeScript types across components/services; enable "strict" in tsconfig.
38. [ ] Frontend: Add route guards based on RBAC and protect Phase pages by roles; centralize auth token refresh.
39. [ ] Frontend: Optimize tables/lists with virtualization where needed; ensure pagination on large datasets.
40. [ ] Frontend: Extract reusable UI primitives (Progress, Buttons, Layout) with consistent accessibility (ARIA labels, focus states).
41. [ ] Frontend: Add comprehensive unit tests for contexts, services, and critical components; target >80% coverage for src/.
42. [ ] Frontend: Add E2E tests (Playwright or Cypress) for login, Phase 1–4 happy paths, and error scenarios.

43. [ ] API Design: Maintain versioned APIs (/api/v1); add deprecation policy and changelog for breaking changes.
44. [ ] API Design: Add standard pagination schema and filters; document across endpoints in OpenAPI with examples.
45. [ ] API Design: Provide consistent error response schema and error codes; document in API reference.
46. [ ] API Design: Add idempotent endpoints for applying AI results and bulk updates; include dry-run options.

47. [ ] Observability: Integrate Sentry (or similar) for frontend and backend error tracking with release tagging.
48. [ ] Observability: Expose Prometheus metrics for backend (uvicorn, FastAPI, MongoDB, task queue) and dashboard them.
49. [ ] Observability: Add audit logging for administrative actions (RBAC-sensitive) with secure storage.

50. [ ] Security: Validate file uploads (MIME/size) and add antivirus scanning before GridFS storage.
51. [ ] Security: Implement content security policy (CSP) headers and secure cookies where applicable.
52. [ ] Security: Secret management: avoid plaintext secrets in configs; support Azure Key Vault or env only.
53. [ ] Security: Add dependency vulnerability scanning (pip/audit, npm audit) in CI and define upgrade policy.

54. [ ] Performance: Review batch sizes and concurrency for background jobs; make them configurable per env.
55. [ ] Performance: Add caching layer (per-request and cross-request) for expensive reads; define invalidation strategy.
56. [ ] Performance: Optimize SSE streaming to avoid memory retention; ensure heartbeats/timeouts are configurable.

57. [ ] Testing: Backend unit tests for services (normalization, section extraction, phase4 search/worker); mock external deps.
58. [ ] Testing: Backend integration tests for API endpoints including auth, SSE progress, and GridFS flows.
59. [ ] Testing: Data fixtures and factories for MongoDB; provide lightweight seed/reset scripts.
60. [ ] Testing: Add smoke test scripts to validate environment setup (DB, API, frontend reachable) post-deploy.

61. [ ] DevOps: Add Dockerfiles for frontend and backend with multi-stage builds and production configs.
62. [ ] DevOps: Add docker-compose.yml (frontend, backend, mongodb, optional mongo-express) for local development.
63. [ ] DevOps: Configure GitHub Actions CI: lint, type-check, test (frontend/backend), build artifacts, and test reports.
64. [ ] DevOps: Configure CD pipeline for staging (build + deploy artifacts/images); document rollback procedures.
65. [ ] DevOps: Add versioning and release flow (semantic versioning, changelog generation).

66. [ ] Developer Experience: Add Makefile or cross-platform task runner (e.g., justfile or npm scripts) to orchestrate common tasks.
67. [ ] Developer Experience: Improve Windows PowerShell scripts parity with cross-platform alternatives; add environment bootstrap.
68. [ ] Developer Experience: Provide sample data and demo credentials provisioning scripts for quick start.
69. [ ] Developer Experience: Add feature flags system for toggling experimental features (e.g., Phase 5 previews).

70. [ ] Data Governance: Define PII handling policy and data deletion/anonymization workflows where applicable.
71. [ ] Compliance: Add license file and verify third-party license compliance for dependencies.
72. [ ] Accessibility: Run basic a11y audits (axe) and fix issues in UI components/pages.
73. [ ] Internationalization: Prepare for i18n support where labels/strings are hard-coded.

74. [ ] Documentation: Add API reference derived from OpenAPI (redocly or similar) and publish under docs/.
75. [ ] Documentation: Expand docs/phases with Phase 4 guide (and link corrections), and scaffold Phase 5 & 6 plans.
76. [ ] Documentation: Add troubleshooting guide (common errors, port conflicts, MongoDB connection issues).
77. [ ] Documentation: Create onboarding guide for new contributors with an end-to-end walkthrough (dev to deploy).

78. [ ] Roadmap: Define milestones for Phase 5 (Statute Versioning) and Phase 6 (Section Versioning) with acceptance criteria.
79. [ ] Roadmap: Add measurable success metrics (test coverage %, p95 latency, accessibility score, error budgets) and track them.
