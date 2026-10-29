MASTER PROMPT — DRRAS FULL-STACK DISASTER RESPONSE PLATFORM

ROLE AND EXPECTATION
You are a senior full-stack engineer, database designer, QA engineer, and security reviewer. You have access to my existing project ZIP/repository named DRRAS-Flask. Your job is to inspect the actual existing code and then IMPLEMENT the improvements directly in the project files. Do not only provide an architecture, suggestions, sample snippets, mockups, or a plan. Make the code changes, run the tests, fix regressions, and leave the project runnable.

PROJECT CONTEXT
DRRAS means Disaster Relief Resource Allocation System. The current app is built with Python Flask, SQLite, Jinja2, HTML, CSS, and vanilla JavaScript. Keep this architecture unless a concrete technical reason makes a small change necessary. Do not migrate to React, Node.js, Django, PostgreSQL, or a heavy build toolchain just for preference. Preserve the existing visual design, map UI, login flow, six dashboards/roles, and working functionality where possible.

The repository currently includes files such as app.py, database.py, drras.db, templates/index.html, static/css/styles.css, static/css/auth.css, static/js/app.js, static/js/icons.js, requirements.txt, run.bat, run.ps1, README.md, SETUP-GUIDE.md, and a pytest tests directory. Inspect the actual files; this list is not a substitute for repository inspection.

The existing six roles are:
1. Administrator
2. Government Official
3. NGO Coordinator
4. Volunteer
5. Citizen
6. Driver

The existing code already has core APIs for authentication, pending-user approvals, dashboard metrics, emergency requests and priority scoring, allocations, inventory, volunteer assignments, dispatches, shelter capacity/occupancy, funds display, workspace activity, live events/polling, and CSV export. Some areas may be incomplete, simulated, hardcoded, or UI-only. Verify each claim from the code. Do not mark a feature complete just because a button or dashboard card exists.

PRIMARY GOAL
Turn the current prototype into a coherent, database-backed, interconnected disaster-response operations platform. Every role must have a realistic workflow appropriate to its responsibility. Workflows must connect through actual relational records and backend business logic, not just through cards, hardcoded data, toasts, or frontend-only status changes.

NON-NEGOTIABLE WORKING RULES
1. First inspect the whole repository: application routes, database schema/migrations/seeding, frontend views/actions, current tests, README and setup scripts. Identify real existing behavior and missing behavior.
2. Give a short audit summary and an implementation plan, then continue implementing without waiting for approval unless a truly blocking issue cannot be resolved safely.
3. Modify the actual files. Do not stop after presenting recommendations or generating isolated code snippets.
4. Preserve existing features and the project's simple run experience. Do not delete existing tests to get a green test run. Add or update tests when behavior intentionally changes.
5. Do not overwrite the user's existing database or destroy user data. Add versioned/idempotent SQLite schema migrations. Make seed data creation safe to run repeatedly. Back up or clearly document any unavoidable data transformation.
6. Use parameterized SQL, transactions, foreign keys, validation, secure session handling, password hashing, and server-side authorization. Never rely on hiding a button in JavaScript as security.
7. For every sensitive API, validate both the user's role and their access to the particular record/incident/zone/task/dispatch. Prevent IDOR (insecure direct object reference) issues.
8. Use clear state-transition rules. Reject invalid transitions with a useful 4xx response. Avoid duplicate dispatches, duplicate reservations, duplicate task assignments, duplicate finance postings, and repeated stock deductions on retries.
9. Related changes must be atomic. For example, allocating a request, reserving stock, creating a dispatch, linking a volunteer task (when required), and writing the audit event must not leave partial inconsistent data if one operation fails.
10. Keep all external integrations honest. OpenStreetMap or a route preview is not proof a road is open. Do not pretend SMS, email delivery, government APIs, GPS tracking, payment processing, or real identity verification exists unless it is actually integrated. Use an explicitly labelled local simulation/demo adapter when a real external integration is unavailable.
11. Never hardcode live financial totals, stock availability, dashboard KPIs, workflow results, or success messages. Derive them from the database. Seeded demo records are acceptable only when explicitly treated as demo data.
12. Avoid huge rewrites. Use small, maintainable helpers/services where suitable, keep current Flask + SQLite + vanilla JS stack, and document meaningful design choices.
13. Do not expose private citizen medical/contact/location details to roles that do not need them. Restrict CSV exports and audit details by permission.
14. Do not claim “production-ready” without tests and clearly documented remaining limitations. This is a disaster-response simulation and must be presented honestly as a prototype unless validated for real operations.

REALISTIC END-TO-END SCENARIO
Use a fictional flood incident in a district as the main demo scenario. An authorized Government Official creates and activates an incident, creates zones, and coordinates agency coverage. Citizens submit emergency requests. The system assigns transparent triage scores and an authorized responder verifies requests. An NGO applies to cover a zone, receives approval, registers a donation, and warehouse staff verify the physical quantity received. Verified stock enters inventory via a stock ledger. An authorized coordinator allocates resources to a verified request; stock is reserved; a dispatch is created; the compatible available vehicle and an eligible driver are assigned. Where field distribution is required, a persistent volunteer task is assigned. The driver progresses through loading, departure, route exceptions if any, arrival, and delivery proof. The volunteer checks in, records actual work and quantities, and submits completion for review. The citizen or authorized verifier confirms fulfilment. Remaining/returned/damaged stock is reconciled. Shelter admissions/transfers are tracked where relevant. Funding approvals and actual expenses are recorded separately. The dashboard, event feed, notifications, audit trail, and incident reports reflect the same database facts.

ROLE-SPECIFIC WORKFLOWS
A. Administrator
- Approve/reject pending official, NGO and volunteer registrations; record actor, timestamp, and reason.
- Manage user status and safe role assignment. Restrict high-risk role changes and record them in audit history.
- Manage appropriate master data (incident categories, resource categories, warehouses, vehicles, shelters, zones, organizations and configurable thresholds) only where safe and appropriate.
- Inspect audit trails and export only authorized data.
- Do not give Admin arbitrary silent powers to rewrite historical transactions; corrections should be explicit and audited.

B. Government Official / Incident Command
- Create incident with ID, type, severity, affected area, description, command owner, created/activated timestamps and lifecycle.
- Incident lifecycle: Draft -> Under Verification -> Active -> Stabilizing -> Closed; allow documented Rejected/Cancelled paths.
- Create/link operational zones to an incident; define coordinator/coverage and operational status.
- Review critical requests and resource shortages; approve exceptional/bulk allocations and inter-agency support requests according to configurable demo policy.
- Review NGO zone adoption requests and approve/reject with reason.
- Manage public advisories as records with draft/review/approved/published/expired/withdrawn status. Do not claim messages were SMS-sent without an actual adapter.
- Review district command dashboard and incident reports with live DB-derived metrics.

C. NGO Coordinator
- Link NGO/organization membership to the logged-in account.
- Apply for incident/zone coverage with capacity, skills/resources, staffing, dates, constraints, and contact person.
- Adoption lifecycle: Requested -> Under Review -> Approved/Rejected -> Active -> Expired/Revoked.
- Register cash and in-kind donations separately. Track donor/reference, declared amount/quantity, expected arrival, actual received quantity/value, verifier, variance, supporting evidence/reference, and status.
- Donation lifecycle should include Submitted, In Transit (where relevant), Received, Verification Pending, Verified/Accepted, Partially Accepted, Rejected, and Cancelled where applicable.
- Only verified/accepted physical quantities enter inventory. A mismatch between declared and received quantity creates a discrepancy, not a silent correction.
- Coordinate volunteer assignments, approved-zone operations, daily distribution ledger, stock reconciliation, open tasks, and unresolved needs.

D. Citizen
- Register/login securely, create an emergency request with assistance type, location/address/map pin, affected persons, vulnerability factors, description, and optional evidence reference.
- Citizen can only see their own requests and public-safe progress updates; protect other citizens' records and precise location/contact details.
- Show actual status timeline, reference ID, priority band/score where appropriate, review outcome, delivery progress, and next actionable step.
- Citizen may confirm aid received, report incomplete/incorrect delivery, or provide requested additional information. A missing citizen response must not falsely prove delivery.

E. Volunteer
- Maintain skills, verification/training indicators as applicable, preferred/eligible zones, shift availability and current assignment status.
- A persistent volunteer task record is required. Do not represent assignment only by toggling a volunteer Available/On Task field.
- Task lifecycle: Created -> Assigned -> Accepted/Declined -> In Progress -> Submitted for Review -> Completed; also allow Cancelled, Reassignment Required, and Needs Correction where appropriate.
- Support field check-in/check-out and timestamps; GPS is optional and failure must not make the app unusable.
- Record task objective, incident/zone, supervisor, planned vs actual quantities, checkpoint notes, and optional evidence reference.
- Require quantity reconciliation for distribution tasks (e.g. received = distributed + damaged + remaining/returned), with exceptions explained.
- Ground reports must start as unverified; authorized responders review them before they affect official incident/request statuses.
- Volunteer can act only on assigned/permitted tasks.

F. Driver
- Create/maintain a vehicle master record with type, cargo/seat capacity as relevant, readiness/status, maintenance/unavailable state, and assigned driver where appropriate.
- Driver can see and update only their own authorized dispatches.
- Dispatch lifecycle should be richer than a single three-button mock workflow: Planned -> Stock Reserved -> Picking -> Loading -> Ready -> En Route -> Arrived -> Delivered Pending Proof -> Delivered. Add exception paths such as Allocation Blocked, Route Blocked, Failed Delivery, Returned to Warehouse, and Cancelled.
- Validate vehicle compatibility, availability, capacity, driver availability/eligibility, pickup stock and destination before dispatch.
- Record manifest/dispatch items, planned and actual quantities, departure/arrival times, optional route/ETA, route-blockage reports, reroute decision, delivery confirmation, proof type/reference and delivery exceptions.
- Delivered must not be set until required quantities/proof/exception review are satisfied. Partial delivery must remain partial and be represented explicitly.
- On trip closure, reconcile returned items and vehicle state before making the vehicle available again.

CROSS-MODULE WORKFLOWS TO IMPLEMENT
1. Incident -> zones -> NGO adoption approval -> requests/tasks/dispatches linked to incident/zone.
2. Citizen request -> triage/priority -> verification -> resource planning -> allocation/reservation -> dispatch -> delivery proof -> citizen confirmation/review -> closure.
3. Donation -> physical receiving -> quantity verification/discrepancy handling -> accepted donation -> inventory transaction -> request allocation.
4. Volunteer availability/skills -> task assignment -> accept/decline -> check-in -> work/quantity report -> supervisor review -> inventory reconciliation -> completion/availability.
5. Inventory reservation -> warehouse picking/issue -> dispatch manifest -> delivery/return/damage -> stock ledger reconciliation.
6. Shelter referral -> capacity validation -> confirmation -> arrival/admission -> transfer/exit -> occupancy recalculation. Never count the same person at two shelters at the same time in a transfer.
7. Fund request -> authorization -> commitment/procurement -> payment/expense -> reconciliation. Approved, committed, paid, and remaining amounts must be distinct measures.
8. Blocked route/failed delivery/no driver/no stock/declined volunteer/full shelter -> explicit exception record -> responsible coordinator notified -> resolution or escalation -> audit event.
9. Every important state change -> persisted audit/event record -> authorized dashboard updates/notifications.

SUGGESTED DATA MODEL
Inspect existing schema first. Reuse and migrate existing tables rather than duplicating concepts. Introduce suitable normalized tables where missing, such as:
- incidents
- zones
- organizations / organization_memberships where necessary
- zone_adoptions
- emergency request review/status history
- inventory_transactions
- inventory_reservations
- donation records and donation items/receipts
- volunteer_tasks and task_checkpoints
- vehicles
- dispatch_items / dispatch status history
- delivery_proofs
- shelter_admissions and shelter_transfers
- fund_requests / fund_transactions / expense records
- inter_agency_requests
- public_advisories
- notifications
- audit_logs or a robust extension of existing activities/events

Potential relationships include incident_id and zone_id on emergency requests; request_id on reservations/dispatches/tasks where relevant; organization_id on NGO operations/donations; inventory/warehouse references on stock movements; and actor_id on approvals/audit events. Add indexes, constraints, foreign keys and delete behavior intentionally. Use stable IDs and UTC/ISO timestamps consistently. Store money as integer minor units (e.g. paise) or a clearly documented decimal-safe representation; do not use imprecise float arithmetic for financial ledger postings.

IMPORTANT STOCK AND TRANSACTION RULES
- Available quantity = on-hand quantity minus active reservations; clearly distinguish physical on-hand, reserved, issued, damaged and returned quantities.
- Never reserve/issue more than available stock. Handle simultaneous requests with a SQLite transaction and conditional update/locking strategy appropriate to SQLite.
- Stock changes must be represented by ledger transactions rather than unexplained direct overwrites. Adjustments require a reason and actor.
- Reserving stock does not mean it has left the warehouse. Issuing stock does not prove recipient delivery. Returns must be physically recorded/inspected before becoming available.
- Allocation endpoints must be idempotent or safely reject duplicate submissions; do not double-deduct stock on retries.
- Where partial fulfilment is permitted, store requested, reserved, issued, delivered, returned, damaged and remaining quantities distinctly.

STATE MACHINES AND CONSISTENCY
Define allowed states and legal transitions in backend code/service helpers, not only frontend buttons. Use clear, consistent status strings and documented transition maps. Return helpful 400/403/404/409 responses for invalid input, forbidden scope, missing records or conflicting state. Keep related request/dispatch/task/inventory updates consistent. If the app has no mature event queue, use a persisted event/outbox table or a robust transaction-safe pattern; do not publish a success notification before the DB transaction commits. SSE/polling should expose only events the current user is allowed to see and should support clients catching up after temporary disconnection.

UI / UX REQUIREMENTS
- Preserve the current visual identity and responsive layout; enhance rather than redesign everything without need.
- All six roles must see role-appropriate dashboards and actionable queues, not generic duplicated pages.
- Implement real forms, loading states, validation messages, empty states, filters, search, pagination where helpful, confirmation for irreversible/high-impact actions, and informative error handling.
- Dashboard stats, status badges, task counts, inventory figures, fund totals, shelter occupancy and event activity must be generated from the database.
- Every visible action must call a real backend endpoint and display the API result. Remove or clearly label placeholders/demo-only actions; no dead buttons, fake success toasts or hardcoded operational records presented as live.
- Use accessible labels, keyboard operation, clear contrast and mobile-friendly responsive layout.
- Keep the no-heavy-build-toolchain behavior and preserve run.bat/run.ps1 if feasible.

SECURITY REQUIREMENTS
- Verify secure password hashing and safe session/cookie settings. Never store plaintext passwords. Use environment/configuration for secrets and document safe local defaults.
- Use CSRF protections appropriate to the chosen cookie/session auth model for state-changing browser requests.
- Validate and normalize all input server-side; restrict accepted status values and numeric ranges; avoid SQL injection, XSS and unsafe file uploads.
- Do not trust user-supplied role, owner ID, driver ID, approval status, inventory quantity, fund totals, or audit actor.
- Add record-level authorization for citizen-owned requests, driver-owned dispatches, volunteer-assigned tasks, NGO-owned operations and government incident scope.
- Restrict file type/size if uploads are implemented; otherwise keep references/metadata rather than adding unsafe upload handling.
- Ensure exports are authorized and avoid leaking sensitive personal data or passwords.
- Do not log passwords, session tokens, sensitive health information, or unnecessary precise locations.

TESTING REQUIREMENTS
Inspect and run the existing pytest suite before changes to establish a baseline. Preserve existing tests. Add thorough tests for:
- Authentication, role access and resource-level authorization / IDOR cases.
- Incident lifecycle and zone adoption approval/rejection.
- Citizen request creation, ownership, priority calculation, verification, duplicates and status timeline.
- Stock reservation, low/zero stock, insufficient stock, rollback, duplicate allocation and concurrent/conflicting allocation behavior where feasible.
- Donation declared-vs-received quantity mismatch and only verified quantities entering stock.
- Volunteer assignment acceptance/decline, task status transitions, check-ins, quantity reconciliation and unauthorized task access.
- Driver-only dispatch access, invalid transitions, blocked route, partial delivery, proof requirements, returned stock and vehicle availability.
- Shelter capacity boundary, concurrent admissions and transfer without double counting.
- Fund approval vs payment vs reconciliation, decimal/money accuracy and duplicate postings.
- Audit/event creation, SSE/poll access control, CSV export permissions and no hardcoded KPI output.
- Schema migrations working against both a fresh database and a copy of the previous schema/database.
- End-to-end scenario crossing at least request -> verify -> reserve -> dispatch -> delivery -> stock/request reconciliation.

Run the full test suite after the implementation. Fix failures caused by your changes. If a test cannot run because of an environmental limitation, state exactly which command failed and why; do not invent a successful test result. Add a concise manual smoke-test checklist for all six roles.

DEMO SEED DATA
Maintain a repeatable local demo setup with clearly fictional data, including one active flood incident, several zones, example citizens/requests, at least one approved NGO, verified and pending donations, stock quantities, several volunteers with skills, available/unavailable vehicles, dispatches in different states, shelter capacities, and a fund request/transaction lifecycle. Use unmistakably fictional names/data. Never seed the production app with real personal information. Seed functions must not duplicate data on each start or reset user-made records automatically.

DOCUMENTATION AND HANDOFF
Update README.md and SETUP-GUIDE.md with:
- Setup/run steps for Windows and command line.
- Demo accounts and their development-only nature (confirm credentials from code before documenting).
- Role-wise workflows.
- Main entities and relationships.
- Status transition diagrams/tables.
- API endpoint list and example request bodies/responses.
- Database migration and demo seed instructions.
- Test command and test results.
- Which features are fully implemented, simulation-only, or intentionally deferred because an external service/credential is unavailable.
- Security/production limitations and recommended deployment settings.

IMPLEMENTATION PROCESS
Phase 1: Inspect repository and baseline tests. Briefly report current working features, gaps, and risks.
Phase 2: Implement schema migrations, core business services, event/audit patterns and state transitions.
Phase 3: Implement connected incident/request, inventory/donation, dispatch/fleet, volunteer, shelter and finance workflows with server-side authorization.
Phase 4: Wire all role dashboards/forms/actions to real endpoints and database-derived states.
Phase 5: Add/update tests and demo seed data; run full tests and fix regressions.
Phase 6: Update documentation and provide final handoff.
You may adjust this sequence if the codebase needs a safer order, but do not skip any requirement without recording it as deferred and explaining why.

DEFINITION OF DONE
The project is only complete when:
1. The app starts using the documented existing run method.
2. All six roles have meaningful, permission-checked workflows.
3. Key modules are connected by actual database records and foreign-key relationships.
4. Request -> verification -> stock reservation -> dispatch -> delivery proof -> reconciliation works end-to-end.
5. Donation verification changes inventory correctly; volunteer tasks and shelter records have real histories; finance totals come from transactions.
6. Invalid transitions, unauthorized access, duplicate submissions, stock shortage, partial fulfilment and operational exceptions are handled explicitly.
7. Dashboards, status timelines, notifications, reports and exports reflect database state, not hardcoded demo claims.
8. Existing and new tests pass, or any remaining environmental failures are transparently documented.
9. README and SETUP-GUIDE match the actual implemented application.
10. Final response summarizes files changed, workflows implemented, tests run/results, how to launch, demo accounts confirmed from the repository, and any remaining limitations. Do not claim work that was not performed.

Start by inspecting the provided DRRAS-Flask project now. Then implement the system directly in the working repository. Do not return only a plan.

# 24. EXPLICIT IMPLEMENTATION SPECIFICATION — DO NOT LEAVE IMPORTANT DETAILS TO GUESSWORK

This section is mandatory. Treat it as a build contract. Earlier sections describe the goal and business workflows; this section specifies the minimum database structures, API routes, request fields, permissions, state transitions, validation rules and acceptance criteria. Implement all of it unless the existing code already provides equivalent, tested functionality. If you choose a different internal design, preserve the same capabilities and document the mapping.

Do not reply with only a list of APIs or SQL schema. Create the corresponding database migrations, Flask route handlers, service/business-logic functions, frontend views/actions and tests.

## 24.1 Inspect and preserve the existing application's contracts first

The supplied ZIP currently contains these existing route families. Re-open `app.py`, `database.py`, `static/js/app.js`, and the tests to confirm current behavior before changing anything.

Existing endpoints to preserve or replace with fully backward-compatible adapters:

- `GET /`
- `POST /api/auth/login` — JSON: `email`, `password`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `POST /api/auth/register` — JSON: `name`, `email`, `password`, optional `role`
- `GET /api/admin/pending-users`
- `POST /api/admin/approve-user`
- `POST /api/admin/reject-user`
- `GET /api/dashboard`
- `GET /api/requests`
- `POST /api/requests`
- `PATCH|POST /api/requests/<request_id>/allocate`
- `GET /api/inventory`
- `POST /api/inventory`
- `PUT|PATCH /api/inventory/<inventory_id>`
- `GET /api/volunteers`
- `POST /api/volunteers`
- `PATCH|POST /api/volunteers/<volunteer_id>/assign`
- `PATCH|POST /api/volunteers/<volunteer_id>/unassign`
- `GET /api/dispatches`
- `PATCH|POST /api/dispatches/<dispatch_id>/advance`
- `GET /api/shelters`
- `PUT|PATCH /api/shelters/<shelter_id>`
- `GET /api/funds`
- `GET|POST /api/workspace-activity`
- `GET /api/events/stream`
- `GET /api/events/poll`
- `GET /api/export/<dataset>.csv`

The current schema contains `users`, `emergency_requests`, `inventory`, `volunteers`, `dispatches`, `shelters`, `funds`, `activities` and `system_events`. The existing `emergency_requests` table uses a text request ID; the current inventory structure has a single resource-name uniqueness constraint; the current dispatch stores vehicle and driver display names as text. These are legacy constraints that must be addressed by safe migrations while preserving clients and tests.

Existing test files include `test_auth_rbac.py`, `test_dispatches_workflow.py`, `test_emergency_requests.py`, `test_inventory_volunteers.py`, `test_misc_modules_and_security.py`, `test_realtime_and_interconnected_workflows.py` and `test_reproduce_defects.py`. Read them and keep their intent. If the correct workflow changes a test expectation (for example reserve stock first rather than physically issue it), update the test to assert the new invariant; do not delete the test or weaken its security coverage.

Keep the existing role names exactly unless implementing a documented migration: `Administrator`, `Government Official`, `NGO Coordinator`, `Volunteer`, `Citizen`, `Driver`.

## 24.2 Mandatory API implementation conventions

1. Keep the current session-cookie authentication approach unless the existing implementation provides a sound reason to change it. Do not introduce JWT solely for fashion. Protect state-changing cookie-authenticated requests against CSRF.
2. All API request and response bodies use JSON unless the endpoint explicitly returns a CSV file or event stream.
3. Existing routes must continue to return the response shapes expected by the current frontend and tests. New routes should use a consistent format. Update frontend and tests together if an existing response shape must change.
4. For new API errors, use this standard shape wherever backward compatibility permits:
   `{"error":{"code":"VALIDATION_ERROR","message":"A useful explanation","details":{},"request_id":"..."}}`
   For existing endpoints that currently return `{"error":"message"}`, either preserve that shape or migrate all consumers and tests together. Never return HTML stack traces to API callers.
5. Use appropriate HTTP status codes: `200` read/update success; `201` created; `204` successful no-content action where appropriate; `400` malformed request; `401` unauthenticated; `403` authenticated but forbidden; `404` record absent/not visible; `409` invalid state transition, stock conflict, duplicate/conflicting action; `422` semantically invalid fields if consistent with the project; `500` unexpected server failure with a generic message and server-side logging.
6. Validate all IDs, numbers, enum values, lengths, dates, foreign keys and role permissions server-side. Reject boolean values where an integer is required; reject NaN/infinity for coordinates and amounts.
7. Use parameterized SQL only. No string interpolation for user-supplied SQL values.
8. Use transactions for multi-record workflows. Add an idempotency key or uniqueness guard for repeated allocation, donation acceptance, payment recording and inventory movements.
9. List endpoints must support useful query filters such as `status`, `incident_id`, `zone_id`, `from`, `to`, and text search where appropriate. New high-volume endpoints should support `page` and `per_page` (with a safe maximum, e.g. 100). Keep existing legacy list response shapes backward compatible.
10. For every new endpoint, document method, URL, role access, payload, response, expected error statuses, and side effects in `README.md` or `docs/API.md`.
11. The server must derive the acting user and role from the authenticated session. Never trust `user_id`, `role`, `approved_by`, `driver_id`, `created_by`, or similar actor fields submitted by the client. Accept user IDs only when the caller is explicitly assigning a different eligible person and has permission to do so.
12. For mutations, return the updated resource representation and ID(s) created, not a fake `success: true` that hides what happened.
13. Do not send event/notification success before the database transaction commits. Where practical, store the event within the same transaction as the business mutation.
14. Add an API route inventory test or documentation check so all frontend-called routes resolve and no button calls a nonexistent endpoint.

## 24.3 Required authentication, authorization and audit rules

Use the existing six roles and implement the following baseline permissions. Apply narrower record ownership/scope rules in addition to this role matrix.

| Operation | Administrator | Government Official | NGO Coordinator | Citizen | Volunteer | Driver |
|---|---|---|---|---|---|---|
| Manage user accounts / approve registrations | Yes | No, unless explicitly delegated | No | No | No | No |
| Create/activate/close incidents | System admin/config only; not automatically command authority | Yes | No | No | Report field observation only | Report route/field issue only |
| Create and manage incident zones | Config support | Yes | Read approved scopes / request adoption | Own request zone only | Assigned zones only | Assigned dispatch zones only |
| Submit emergency request | Test/admin support only if needed | On behalf of caller only with audit reason | On behalf of caller only with audit reason | Yes | Report field incident; do not silently impersonate Citizen | Report delivery/route incident; do not silently impersonate Citizen |
| Verify/reject/triage requests | Audit/support privileges; do not silently impersonate Official | Yes | Only within explicitly approved scope and capability | Own request details only | No, except submit a field report | No, except dispatch evidence/status |
| Allocate resources | Emergency override only if configured and audited | Yes | Only within approved zone/stock scope | No | No | No |
| Manage warehouse stock / verify receipt | Yes, with audit | Yes | Only authorized NGO/warehouse scope | No | Record assigned counts only | Confirm manifests/returns only |
| Manage NGO adoption/donations | Admin organization verification | Approve zone adoption; financial controls as assigned | Manage own organization, propose donation; cannot self-approve a disputed receipt | No | No | No |
| Manage Volunteer profiles/tasks | Support/configuration | Incident-level oversight | Own approved organization/zone | No | Accept/update own tasks only | No |
| Update dispatch | Oversight/admin exception only with reason | Oversight and exception resolution | Assign/coordinate only within scope | View own request status | No unless explicitly assigned as task role | Assigned dispatch only |
| Manage shelter admissions | Oversight | Incident-level | Only assigned shelter/zone scope | Own referral/status only | Record task observations; admission only if assigned permission | No except transport arrival info |
| Create/approve financial transactions | No automatic self-approval; configurable dual-control rules | Authorize within grant/role limits | Submit requests for own organization; cannot approve own request | No | No | No |
| View global audit logs | Yes | Incident-scoped operational history | Own organization/assigned scope | Own request timeline only | Own tasks and submitted reports | Own dispatches and proof |

Add explicit backend decorators/helpers for `login_required`, `roles_required`, `can_access_incident`, `can_access_zone`, `can_access_request`, `can_access_dispatch`, and organization membership where appropriate. Do not copy/paste inconsistent permission logic in every route.

For every high-impact action, persist the actor, entity type/ID, action, previous state, new state, reason, timestamp, and correlation/request ID. Never allow ordinary roles to edit or delete historical audit rows through the API.

# 25. DATABASE SCHEMA CONTRACT

Inspect the actual legacy schema and implement safe, ordered migrations. The entities below specify minimum required fields and relationships, not an instruction to duplicate a concept that already exists. Keep the canonical source of truth clear. Use SQLite foreign keys (`PRAGMA foreign_keys=ON` on every connection), transactions, indexes, check constraints and uniqueness constraints. Store timestamps consistently in UTC ISO 8601 or SQLite UTC timestamps and convert for display.

## 25.1 Existing tables — preserve and extend

### `users`
Keep existing columns `id`, `email`, `password`, `name`, `initials`, `role`, `status`, `created_at`. Add where needed:
- `phone TEXT NULL`
- `organization_id INTEGER NULL REFERENCES organizations(id)` or use a normalized `organization_memberships` table if multiple memberships are supported
- `updated_at TEXT`
- `last_login_at TEXT NULL`
- `suspended_at TEXT NULL`
- `suspension_reason TEXT NULL`

Constraints: case-insensitive unique email; password hashes only; role restricted to the six supported roles; status constrained to documented values such as `PENDING`, `ACTIVE`, `REJECTED`, `SUSPENDED`. Prefer `organization_memberships` for many-to-many membership and do not store conflicting ownership in two places.

### `emergency_requests`
Preserve the existing text `id`, requester/area/address/need/population/vulnerability/priority/status/location/time columns and add:
- `requester_user_id INTEGER NULL REFERENCES users(id)`
- `incident_id TEXT NULL REFERENCES incidents(id)`
- `zone_id TEXT NULL REFERENCES zones(id)`
- `description TEXT NULL`
- `verification_status TEXT NOT NULL DEFAULT 'Unverified'`
- `verified_by_user_id INTEGER NULL REFERENCES users(id)`
- `verified_at TEXT NULL`
- `review_reason TEXT NULL`
- `duplicate_of_request_id TEXT NULL REFERENCES emergency_requests(id)`
- `assigned_organization_id INTEGER NULL REFERENCES organizations(id)`
- `closed_by_user_id INTEGER NULL REFERENCES users(id)`
- `closed_at TEXT NULL`
- `delivery_confirmed_at TEXT NULL`
- `updated_at TEXT`

The server must set `requester_user_id` from the authenticated session for a Citizen-created request. Existing legacy requests may have NULL owner; migrate/backfill only when ownership is unambiguous. Keep the existing `need` value for backward compatibility while using `request_items` for multiple line items.

### `inventory` legacy route compatibility
Do not leave the current single-row-per-resource design as the long-term source of truth if the new design needs the same item in multiple warehouses. Migrate safely to a canonical resource/warehouse model. Keep `GET/POST /api/inventory` and `PUT/PATCH /api/inventory/<id>` working as compatibility adapters with their expected legacy field names (`resource_name` or `name`, `available_units` or `available`, `target_stock` or `target`, `warehouse_name`, `status`). Existing tests and frontend should keep working unless intentionally and comprehensively updated.

If the legacy `inventory` table is rebuilt, back up/migrate all existing rows transactionally before switching. Do not run a destructive reset. Do not maintain two independent stock balances that can diverge; if a compatibility projection is needed, make one canonical and derive the other from it or update it within the same transaction with tests.

### `volunteers`
Preserve existing `id`, `initials`, `name`, `skill`, `zone`, `status`. Add:
- `user_id INTEGER NULL REFERENCES users(id)` with unique constraint when present
- `organization_id INTEGER NULL REFERENCES organizations(id)`
- `verified INTEGER NOT NULL DEFAULT 0`
- `availability_start TEXT NULL`, `availability_end TEXT NULL`
- `phone TEXT NULL`
- `updated_at TEXT`

Keep volunteer roster data separate from `volunteer_tasks`. A Volunteer marked `On task` is not sufficient proof of an assigned/completed task.

### `dispatches`
Preserve legacy `id`, `vehicle`, `driver`, `destination`, `load_items`, `status`, `eta`, `request_id`. Add:
- `incident_id TEXT NULL REFERENCES incidents(id)`
- `zone_id TEXT NULL REFERENCES zones(id)`
- `vehicle_id INTEGER NULL REFERENCES vehicles(id)`
- `driver_user_id INTEGER NULL REFERENCES users(id)`
- `created_by_user_id INTEGER NULL REFERENCES users(id)`
- `warehouse_id INTEGER NULL REFERENCES warehouses(id)`
- `planned_at TEXT NULL`, `departed_at TEXT NULL`, `arrived_at TEXT NULL`, `delivered_at TEXT NULL`, `returned_at TEXT NULL`
- `route_status TEXT NULL`, `route_blockage_reason TEXT NULL`
- `delivery_result TEXT NULL`, `delivery_notes TEXT NULL`
- `updated_at TEXT`

Keep legacy `vehicle` and `driver` strings as compatibility/display fields while new foreign keys become canonical. Do not assign a fake driver name when no active Driver exists; return a resource-allocation conflict and leave the request in a pending state.

### `shelters`
Preserve current columns `id`, `name`, `occupants`, `capacity`, `status`. Add `incident_id`, address/zone/location fields, `updated_at`, and optional `created_by_user_id`. New admissions/transfers become the source of truth for occupancy. Add a migration/backfill strategy for existing occupancy counts so current demo occupancy is not lost.

### `funds`
The existing category/percentage/color structure may be retained as a compatibility/reporting output, but it must no longer be the authoritative financial ledger. The `GET /api/funds` compatibility response must calculate category totals/percentages from real `fund_transactions` where available; maintain the existing response shape with categories summing to 100% where the legacy UI/tests require that shape, and handle zero activity without division-by-zero. Do not use hardcoded rupee totals.

### `activities` and `system_events`
Preserve current functionality. Extend only if needed with actor/entity/correlation information. Keep `activities` for human-readable workspace history; use a structured append-only `audit_logs` table for audit and structured `system_events` for event updates. Do not treat one table as a substitute for all three concepts.

## 25.2 Required new canonical tables and minimum columns

Use the names below unless a clear existing equivalent already exists. Add created/updated timestamps, constraints and indexes where applicable.

### `incidents`
- `id TEXT PRIMARY KEY` (example `INC-2026-001`)
- `title TEXT NOT NULL`
- `incident_type TEXT NOT NULL`
- `severity TEXT NOT NULL CHECK` against documented severity values
- `description TEXT NOT NULL`
- `district TEXT NOT NULL`
- `status TEXT NOT NULL`
- `command_officer_user_id INTEGER NOT NULL REFERENCES users(id)`
- `reported_at TEXT`, `activated_at TEXT NULL`, `stabilized_at TEXT NULL`, `closed_at TEXT NULL`
- `created_by_user_id INTEGER NOT NULL REFERENCES users(id)`
- `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL`

### `zones`
- `id TEXT PRIMARY KEY` (example `Z-01`)
- `incident_id TEXT NOT NULL REFERENCES incidents(id)`
- `name TEXT NOT NULL`
- `description TEXT NULL`
- `district TEXT NOT NULL`
- `address_or_boundary TEXT NULL`
- `center_lat REAL NULL`, `center_lng REAL NULL`
- `severity TEXT NOT NULL`, `status TEXT NOT NULL`
- `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL`

Unique at minimum: `(incident_id, name)`. Validate coordinate ranges. Do not claim polygon-level GIS unless implemented.

### `organizations`
- `id INTEGER PRIMARY KEY`
- `name TEXT NOT NULL`
- `organization_type TEXT NOT NULL` (NGO, public agency, supplier, donor, other)
- `registration_reference TEXT NULL`
- `contact_name TEXT NOT NULL`
- `contact_email TEXT NULL`, `contact_phone TEXT NULL`
- `status TEXT NOT NULL` (`Pending`, `Approved`, `Rejected`, `Suspended`)
- `verified_by_user_id INTEGER NULL REFERENCES users(id)`
- `verified_at TEXT NULL`, `verification_reason TEXT NULL`
- `created_by_user_id INTEGER NULL REFERENCES users(id)`
- `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL`

Add `organization_memberships(id, organization_id FK, user_id FK, membership_role, status, created_at)` with unique `(organization_id,user_id)`. Do not let the NGO self-approve itself.

### `zone_adoptions`
- `id INTEGER PRIMARY KEY`
- `incident_id TEXT NOT NULL REFERENCES incidents(id)`
- `zone_id TEXT NOT NULL REFERENCES zones(id)`
- `organization_id INTEGER NOT NULL REFERENCES organizations(id)`
- `requested_by_user_id INTEGER NOT NULL REFERENCES users(id)`
- `requested_capacity TEXT NULL` or normalized numeric/capability fields
- `available_volunteers INTEGER NOT NULL DEFAULT 0 CHECK >= 0`
- `available_resource_summary TEXT NULL`
- `start_at TEXT NULL`, `end_at TEXT NULL`
- `status TEXT NOT NULL`
- `reviewed_by_user_id INTEGER NULL REFERENCES users(id)`
- `reviewed_at TEXT NULL`, `decision_reason TEXT NULL`
- `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL`

Support more than one approved organization per zone only when policy permits it. Prevent duplicate active adoption records for the same organization/zone/incident using an appropriate uniqueness rule or transaction guard.

### `resources`
- `id INTEGER PRIMARY KEY`
- `sku TEXT NULL UNIQUE`
- `name TEXT NOT NULL`
- `category TEXT NOT NULL`
- `unit TEXT NOT NULL` (kits, cartons, pieces, litres, etc.)
- `description TEXT NULL`
- `track_expiry INTEGER NOT NULL DEFAULT 0`
- `is_active INTEGER NOT NULL DEFAULT 1`
- `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL`

### `warehouses`
- `id INTEGER PRIMARY KEY`
- `code TEXT NOT NULL UNIQUE`
- `name TEXT NOT NULL`
- `district TEXT NOT NULL`
- `address TEXT NOT NULL`
- `lat REAL NULL`, `lng REAL NULL`
- `status TEXT NOT NULL` (Active, Inactive, Temporarily Closed)
- `manager_user_id INTEGER NULL REFERENCES users(id)`
- `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL`

### Canonical stock table `warehouse_stock`
- `id INTEGER PRIMARY KEY`
- `warehouse_id INTEGER NOT NULL REFERENCES warehouses(id)`
- `resource_id INTEGER NOT NULL REFERENCES resources(id)`
- `on_hand_units INTEGER NOT NULL CHECK >= 0`
- `reserved_units INTEGER NOT NULL DEFAULT 0 CHECK >= 0 AND reserved_units <= on_hand_units`
- `target_stock INTEGER NOT NULL CHECK > 0`
- `status TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- unique `(warehouse_id, resource_id)`

Calculate `available_to_allocate = on_hand_units - reserved_units`. Never store a contradictory independently editable available balance. Legacy `/api/inventory` must serialize `available_units` as the available-to-allocate quantity so current dashboards work.

### `inventory_reservations` and `inventory_reservation_items`
`inventory_reservations` minimum fields: `id TEXT PRIMARY KEY`, `request_id TEXT FK`, `dispatch_id TEXT NULL FK`, `status TEXT`, `reserved_by_user_id FK users`, `expires_at TEXT NULL`, `released_at TEXT NULL`, `created_at TEXT`, `updated_at TEXT`, `idempotency_key TEXT UNIQUE NULL`.

`inventory_reservation_items`: `id INTEGER PRIMARY KEY`, `reservation_id TEXT FK`, `warehouse_stock_id INTEGER FK warehouse_stock`, `quantity_units INTEGER NOT NULL CHECK > 0`, `issued_units INTEGER NOT NULL DEFAULT 0 CHECK >= 0`, `returned_units INTEGER NOT NULL DEFAULT 0 CHECK >= 0`, `created_at TEXT`; unique `(reservation_id, warehouse_stock_id)`.

### `inventory_transactions`
- `id INTEGER PRIMARY KEY`
- `warehouse_stock_id INTEGER NOT NULL REFERENCES warehouse_stock(id)`
- `transaction_type TEXT NOT NULL` (OpeningBalance, DonationReceived, Reserved, ReservationReleased, Issued, Returned, Damaged, Adjustment)
- `quantity_units INTEGER NOT NULL CHECK > 0`
- `direction TEXT NOT NULL CHECK IN ('IN','OUT','MEMO')` or an equally clear signed-quantity design
- `reference_type TEXT NULL`, `reference_id TEXT NULL`
- `idempotency_key TEXT NULL UNIQUE`
- `reason TEXT NULL`
- `performed_by_user_id INTEGER NOT NULL REFERENCES users(id)`
- `created_at TEXT NOT NULL`

Document how each transaction changes on-hand and reserved quantities. Never record the same stock movement twice. Reservations should be represented distinctly from physical issue so cancelled dispatches can release unissued quantities safely.

### `request_items`
- `id INTEGER PRIMARY KEY`
- `request_id TEXT NOT NULL REFERENCES emergency_requests(id)`
- `resource_id INTEGER NOT NULL REFERENCES resources(id)`
- `quantity_requested INTEGER NOT NULL CHECK > 0`
- `quantity_reserved INTEGER NOT NULL DEFAULT 0 CHECK >= 0`
- `quantity_issued INTEGER NOT NULL DEFAULT 0 CHECK >= 0`
- `quantity_delivered INTEGER NOT NULL DEFAULT 0 CHECK >= 0`
- `quantity_returned INTEGER NOT NULL DEFAULT 0 CHECK >= 0`
- `notes TEXT NULL`, `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL`

Do not allow quantity delivered/issued to exceed valid preceding quantities. When the legacy request only specifies a text `need`, map it to one appropriate resource item using a transparent, configurable rule; do not silently invent a stock item if no mapping exists. Require staff confirmation when the mapping is ambiguous.

### `request_events`
- `id INTEGER PRIMARY KEY`
- `request_id TEXT NOT NULL REFERENCES emergency_requests(id)`
- `event_type TEXT NOT NULL`
- `from_status TEXT NULL`, `to_status TEXT NULL`
- `reason TEXT NULL`, `notes TEXT NULL`
- `actor_user_id INTEGER NULL REFERENCES users(id)`
- `metadata_json TEXT NULL`
- `created_at TEXT NOT NULL`

### `volunteer_tasks`
- `id TEXT PRIMARY KEY` (example `TASK-041`)
- `incident_id TEXT NULL REFERENCES incidents(id)`
- `zone_id TEXT NULL REFERENCES zones(id)`
- `organization_id INTEGER NULL REFERENCES organizations(id)`
- `volunteer_id INTEGER NOT NULL REFERENCES volunteers(id)`
- `request_id TEXT NULL REFERENCES emergency_requests(id)`
- `dispatch_id TEXT NULL REFERENCES dispatches(id)`
- `title TEXT NOT NULL`, `task_type TEXT NOT NULL`, `description TEXT NOT NULL`
- `quantity_expected INTEGER NULL CHECK >= 0`
- `quantity_received INTEGER NULL CHECK >= 0`, `quantity_completed INTEGER NULL CHECK >= 0`, `quantity_damaged INTEGER NULL CHECK >= 0`, `quantity_remaining INTEGER NULL CHECK >= 0`
- `status TEXT NOT NULL`
- `shift_start TEXT NULL`, `shift_end TEXT NULL`
- `assigned_by_user_id INTEGER NOT NULL REFERENCES users(id)`
- `accepted_at TEXT NULL`, `started_at TEXT NULL`, `submitted_at TEXT NULL`, `reviewed_at TEXT NULL`, `completed_at TEXT NULL`
- `reviewed_by_user_id INTEGER NULL REFERENCES users(id)`
- `review_notes TEXT NULL`, `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL`

### `task_checkpoints`
- `id INTEGER PRIMARY KEY`
- `task_id TEXT NOT NULL REFERENCES volunteer_tasks(id)`
- `checkpoint_type TEXT NOT NULL` (CheckIn, Progress, CheckOut, FieldReport)
- `lat REAL NULL`, `lng REAL NULL`
- `notes TEXT NULL`, `quantity_delta INTEGER NULL`
- `created_by_user_id INTEGER NOT NULL REFERENCES users(id)`
- `created_at TEXT NOT NULL`

### `vehicles`
- `id INTEGER PRIMARY KEY`
- `vehicle_code TEXT NOT NULL UNIQUE`
- `vehicle_type TEXT NOT NULL`
- `capacity_units INTEGER NULL CHECK >= 0`
- `capacity_description TEXT NULL`
- `capabilities_json TEXT NULL`
- `status TEXT NOT NULL` (Available, Reserved, Loading, EnRoute, Maintenance, OutOfService)
- `current_driver_user_id INTEGER NULL REFERENCES users(id)`
- `warehouse_id INTEGER NULL REFERENCES warehouses(id)`
- `last_inspection_at TEXT NULL`, `maintenance_notes TEXT NULL`
- `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL`

### `dispatch_items`
- `id INTEGER PRIMARY KEY`
- `dispatch_id TEXT NOT NULL REFERENCES dispatches(id)`
- `resource_id INTEGER NOT NULL REFERENCES resources(id)`
- `quantity_planned INTEGER NOT NULL CHECK > 0`
- `quantity_loaded INTEGER NOT NULL DEFAULT 0 CHECK >= 0`
- `quantity_delivered INTEGER NOT NULL DEFAULT 0 CHECK >= 0`
- `quantity_returned INTEGER NOT NULL DEFAULT 0 CHECK >= 0`
- `quantity_damaged INTEGER NOT NULL DEFAULT 0 CHECK >= 0`
- `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL`

### `delivery_proofs`
- `id TEXT PRIMARY KEY`
- `dispatch_id TEXT NOT NULL REFERENCES dispatches(id)`
- `request_id TEXT NOT NULL REFERENCES emergency_requests(id)`
- `submitted_by_user_id INTEGER NOT NULL REFERENCES users(id)`
- `proof_type TEXT NOT NULL` (RecipientConfirmation, OTP, ImageReference, SupervisorVerification, Other)
- `proof_reference TEXT NULL` (store a safe file reference, not arbitrary local paths)
- `recipient_confirmation TEXT NULL`
- `delivered_at TEXT NULL`
- `notes TEXT NULL`
- `status TEXT NOT NULL` (Submitted, Verified, Rejected, NeedsReview)
- `reviewed_by_user_id INTEGER NULL REFERENCES users(id)`
- `reviewed_at TEXT NULL`, `review_reason TEXT NULL`
- `created_at TEXT NOT NULL`

Do not store raw OTPs. If OTP is implemented, store only a secure hash and expiry metadata, enforce attempt limits and delete/expire it appropriately. If no secure OTP implementation is built, use a supervisor confirmation rather than pretending the OTP integration exists.

### `donations`
- `id TEXT PRIMARY KEY`
- `organization_id INTEGER NULL REFERENCES organizations(id)`
- `donor_name TEXT NOT NULL`
- `donation_type TEXT NOT NULL CHECK IN ('Cash','InKind')`
- `incident_id TEXT NULL REFERENCES incidents(id)`
- `zone_id TEXT NULL REFERENCES zones(id)`
- `destination_warehouse_id INTEGER NULL REFERENCES warehouses(id)`
- `declared_amount_paise INTEGER NULL CHECK >= 0`
- `currency TEXT NOT NULL DEFAULT 'INR'`
- `declared_notes TEXT NULL`
- `status TEXT NOT NULL`
- `reference_code TEXT NULL UNIQUE`
- `submitted_by_user_id INTEGER NOT NULL REFERENCES users(id)`
- `received_at TEXT NULL`, `verified_at TEXT NULL`
- `verified_by_user_id INTEGER NULL REFERENCES users(id)`
- `verification_notes TEXT NULL`
- `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL`

### `donation_items`
- `id INTEGER PRIMARY KEY`
- `donation_id TEXT NOT NULL REFERENCES donations(id)`
- `resource_id INTEGER NOT NULL REFERENCES resources(id)`
- `quantity_declared INTEGER NOT NULL CHECK > 0`
- `quantity_received INTEGER NOT NULL DEFAULT 0 CHECK >= 0`
- `quantity_accepted INTEGER NOT NULL DEFAULT 0 CHECK >= 0`
- `quantity_rejected INTEGER NOT NULL DEFAULT 0 CHECK >= 0`
- `reason TEXT NULL`
- `created_at TEXT NOT NULL`

Accepting/validating a donation and adding accepted in-kind quantities to stock must occur once, transactionally. Cash donations must not create physical stock entries.

### `shelter_admissions`
- `id TEXT PRIMARY KEY`
- `shelter_id INTEGER NOT NULL REFERENCES shelters(id)`
- `incident_id TEXT NULL REFERENCES incidents(id)`
- `request_id TEXT NULL REFERENCES emergency_requests(id)`
- `household_reference TEXT NULL` (avoid unnecessary personal data)
- `people_count INTEGER NOT NULL CHECK > 0`
- `status TEXT NOT NULL` (Referred, Confirmed, Arrived, Admitted, NoShow, Transferred, Exited, Cancelled)
- `referred_by_user_id INTEGER NULL REFERENCES users(id)`
- `checked_in_by_user_id INTEGER NULL REFERENCES users(id)`
- `admitted_at TEXT NULL`, `exited_at TEXT NULL`
- `notes TEXT NULL`, `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL`

### `shelter_transfers`
- `id TEXT PRIMARY KEY`
- `admission_id TEXT NOT NULL REFERENCES shelter_admissions(id)`
- `from_shelter_id INTEGER NOT NULL REFERENCES shelters(id)`
- `to_shelter_id INTEGER NOT NULL REFERENCES shelters(id)`
- `people_count INTEGER NOT NULL CHECK > 0`
- `status TEXT NOT NULL` (Requested, Approved, InTransit, Completed, Cancelled)
- `requested_by_user_id INTEGER NOT NULL REFERENCES users(id)`
- `approved_by_user_id INTEGER NULL REFERENCES users(id)`
- `completed_at TEXT NULL`, `reason TEXT NULL`, `created_at TEXT NOT NULL`

### Financial tables

`fund_budgets`: `id`, `incident_id FK`, `organization_id FK NULL`, `category`, `budget_amount_paise CHECK >= 0`, `currency DEFAULT 'INR'`, `status`, `approved_by_user_id FK`, `approved_at`, `created_at`, `updated_at`.

`fund_requests`: `id TEXT PRIMARY KEY`, `incident_id FK`, `organization_id FK`, `category`, `purpose`, `requested_amount_paise CHECK > 0`, `approved_amount_paise CHECK >= 0 DEFAULT 0`, `status`, `requested_by_user_id FK`, `reviewed_by_user_id FK NULL`, `decision_reason`, `created_at`, `updated_at`.

`fund_transactions`: `id TEXT PRIMARY KEY`, `fund_request_id FK NULL`, `budget_id FK NULL`, `incident_id FK`, `organization_id FK NULL`, `transaction_type` (DonationReceived, Commitment, Payment, Refund, Adjustment), `amount_paise CHECK > 0`, `currency DEFAULT 'INR'`, `reference_code TEXT NULL UNIQUE`, `status`, `performed_by_user_id FK`, `approved_by_user_id FK NULL`, `receipt_reference TEXT NULL`, `reason TEXT NULL`, `occurred_at TEXT`, `created_at TEXT`.

Do not model cash donations as in-kind inventory. Use integer paise or another exact monetary representation. Separate approval, commitment, payment and reconciliation events.

### `notifications`
- `id INTEGER PRIMARY KEY`
- `recipient_user_id INTEGER NOT NULL REFERENCES users(id)`
- `event_type TEXT NOT NULL`
- `title TEXT NOT NULL`, `message TEXT NOT NULL`
- `entity_type TEXT NULL`, `entity_id TEXT NULL`
- `read_at TEXT NULL`
- `created_at TEXT NOT NULL`

### `audit_logs`
- `id INTEGER PRIMARY KEY`
- `actor_user_id INTEGER NULL REFERENCES users(id)`
- `action TEXT NOT NULL`
- `entity_type TEXT NOT NULL`, `entity_id TEXT NULL`
- `old_state_json TEXT NULL`, `new_state_json TEXT NULL`
- `reason TEXT NULL`
- `request_id TEXT NULL` (correlation ID, not necessarily an emergency request ID)
- `ip_summary TEXT NULL` only where appropriate and privacy compliant
- `created_at TEXT NOT NULL`

Audit logs are append-only to application roles. Avoid recording password/session/token data or excessive PII.

### Additional tables required if implementing these UI modules

- `field_reports`: ID, incident/zone, reporter user, category, severity, description, location, status, reviewer, review reason, created/updated timestamps.
- `inter_agency_requests`: ID, incident, requesting organization/agency, receiving organization/agency, capability, quantity, urgency, destination, needed-by, status, submitted/acknowledged/accepted/mobilized/completed timestamps, actor and decision reason.
- `public_advisories`: ID, incident, zone optional, title/body/category, status Draft/Review/Approved/Published/Expired/Withdrawn, created by, approved by, published at, valid until, created/updated timestamps.
- `entity_status_history` only if existing `request_events`, dispatch fields and audit history do not already provide equivalent reliable history. Do not duplicate identical history storage without a reason.

## 25.3 Data relationships and constraints

Implement actual relational links, not just IDs embedded in display strings:

- One incident has many zones and requests.
- A zone belongs to an incident.
- Organizations have multiple user memberships and adoption requests.
- A request may have multiple `request_items`.
- A request may have zero or one active allocation/dispatch unless explicit split dispatches are intentionally supported. Document which model is implemented and enforce it.
- A dispatch belongs to a request and can have multiple dispatch items and delivery proof records.
- A reservation belongs to a request and contains reservation items for warehouse stock.
- A donation can contain multiple donation items; accepted in-kind items produce inventory transactions.
- Volunteer tasks link to volunteers and optionally requests, dispatches, incidents and zones.
- Shelter admissions belong to one shelter at a time; transfers change shelter membership atomically.
- Fund requests and transactions link to an incident and relevant organization/budget.
- Notifications have explicit recipients; audit events identify their action actor where known.

Use indexes on high-frequency foreign keys, entity status columns, incident/zone filters, event IDs/timestamps and request/dispatch IDs. Apply uniqueness to email, warehouse code, resource SKU, warehouse-resource pair, idempotency keys and donation/transaction references where provided. Use `ON DELETE RESTRICT` for important financial/stock/history relationships unless there is a justified retention-safe alternative. Prefer soft deactivation to deleting referenced operational records.

# 26. REQUIRED API CATALOG — BUILD THESE ROUTES AND CONNECT THEM TO THE FRONTEND

The route names below are the target API surface. If an equivalent existing endpoint already works, preserve it and document the mapping rather than duplicating it. Implement all relevant methods and payload validation. Use the current session for identity/role. Exact field names may follow existing naming conventions, but request/response schemas must be documented consistently.

## 26.1 Authentication and user administration

Preserve:
- `POST /api/auth/login` body `{ "email": "...", "password": "..." }`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `POST /api/auth/register` body `{ "name": "...", "email": "...", "password": "...", "role": "Citizen" }`
- `GET /api/admin/pending-users`

Add or complete:
- `POST /api/admin/users/<int:user_id>/approve` body `{ "reason": "..." }`
- `POST /api/admin/users/<int:user_id>/reject` body `{ "reason": "..." }`
- `POST /api/admin/users/<int:user_id>/suspend` body `{ "reason": "..." }`
- `POST /api/admin/users/<int:user_id>/reactivate` body `{ "reason": "..." }`
- `GET /api/admin/users?role=&status=&q=&page=&per_page=`
- `GET /api/admin/audit-logs?actor_user_id=&entity_type=&entity_id=&from=&to=&page=&per_page=`

Keep the old `/api/admin/approve-user` and `/api/admin/reject-user` routes working as compatibility adapters if the frontend/tests use them.

## 26.2 Incident and zone APIs

- `GET /api/incidents?status=&severity=&district=&from=&to=&page=&per_page=` — Official/Admin scoped access; other roles see only incidents relevant to their scope.
- `POST /api/incidents` — Government Official only. Example body: `{ "title":"Flood Response - Demo District", "incident_type":"Flood", "severity":"Severe", "description":"Fictional training incident", "district":"Demo District" }`.
- `GET /api/incidents/<incident_id>`
- `PATCH /api/incidents/<incident_id>` — restricted editable fields and status transition validation.
- `POST /api/incidents/<incident_id>/activate` body `{ "reason":"..." }`
- `POST /api/incidents/<incident_id>/stabilize` body `{ "reason":"..." }`
- `POST /api/incidents/<incident_id>/close` body `{ "reason":"..." }`; refuse closure if open requests, dispatches or unresolved tasks remain unless an authorized documented override policy permits closure.
- `GET /api/incidents/<incident_id>/zones`
- `POST /api/incidents/<incident_id>/zones` body `{ "name":"Ward 8", "district":"Demo District", "description":"...", "severity":"High", "center_lat":30.9, "center_lng":75.85 }`
- `GET /api/zones/<zone_id>`
- `PATCH /api/zones/<zone_id>` — Official only for critical fields; status/history recorded.
- `GET /api/zones/<zone_id>/adoptions`
- `POST /api/zones/<zone_id>/adoptions` — NGO Coordinator in an approved organization; body includes expected volunteers, capabilities/resource summary, start/end dates and limitations.
- `POST /api/adoptions/<int:adoption_id>/approve` — Government Official only; body `{ "reason":"..." }`.
- `POST /api/adoptions/<int:adoption_id>/reject` — Government Official only; reason required.
- `POST /api/adoptions/<int:adoption_id>/revoke` — Government Official only; reason required.

## 26.3 Emergency request APIs

Preserve `GET /api/requests`, `POST /api/requests`, and `PATCH|POST /api/requests/<id>/allocate`.

Add/complete:
- `GET /api/requests/<request_id>` — Citizen sees own record only; staff see permitted incident/zone scope.
- `POST /api/requests/<request_id>/verify` — body `{ "decision":"Verified", "reason":"..." }` and enforce valid status.
- `POST /api/requests/<request_id>/request-info` — body `{ "message":"...", "required_fields":["address"] }`.
- `POST /api/requests/<request_id>/reject` — body `{ "reason":"..." }`.
- `POST /api/requests/<request_id>/mark-duplicate` — body `{ "primary_request_id":"REQ-...", "reason":"..." }`; prevent self-reference and circular duplicate chains.
- `POST /api/requests/<request_id>/escalate` — body `{ "reason":"...", "target_role":"Government Official" }`.
- `GET /api/requests/<request_id>/timeline` — return chronological persisted events; redact private fields based on viewer role.
- `GET /api/requests/<request_id>/items`
- `POST /api/requests/<request_id>/items` — staff only after request verification; body `{ "resource_id":1, "quantity_requested":5, "notes":"..." }`.
- `POST /api/requests/<request_id>/confirm-delivery` — owner Citizen or authorized verifier; body `{ "result":"Received", "notes":"..." }`.
- `POST /api/requests/<request_id>/report-issue` — Citizen or authorized field staff; body `{ "issue_type":"PartialDelivery", "description":"..." }`.
- `POST /api/requests/<request_id>/close` — allowed role only; require fulfilled or explicit authorized resolution reason.

Legacy `POST /api/requests` should continue accepting existing aliases such as `name/requesterName`, `need/assistanceType`, `people/peopleAffected`, and `vulnerable/vulnerablePeople` if existing clients depend on them. New canonical fields should include `incident_id`, `zone_id`, `address`, `lat`, `lng`, `description`, `need`, `people_affected` and vulnerability information. Bind the owner from the session.

## 26.4 Resources, warehouses, stock, reservations and ledger APIs

Preserve and adapt `GET/POST /api/inventory` and `PUT/PATCH /api/inventory/<id>`.

Add:
- `GET /api/resources?category=&active=&q=`
- `POST /api/resources` — authorized Admin/Official; body `{ "name":"Medical Kit", "category":"Medical", "unit":"kit", "sku":"MED-KIT-001", "track_expiry":false }`.
- `PATCH /api/resources/<int:resource_id>`
- `GET /api/warehouses?status=&district=&q=`
- `POST /api/warehouses` — Admin/Official only; body includes `code`, `name`, `district`, `address`, optional lat/lng and manager.
- `PATCH /api/warehouses/<int:warehouse_id>`
- `GET /api/warehouses/<int:warehouse_id>/stock`
- `GET /api/stock?warehouse_id=&resource_id=&status=&q=`
- `POST /api/stock/receipts` — authorized receipt/adjustment workflow; body must identify warehouse, resource, quantity and source reference.
- `POST /api/inventory/reservations` — body `{ "request_id":"REQ-...", "items":[{"resource_id":1,"warehouse_id":1,"quantity_units":5}], "expires_at":null, "idempotency_key":"..." }`.
- `POST /api/inventory/reservations/<reservation_id>/release` — reason required; only release units not already physically issued.
- `POST /api/inventory/reservations/<reservation_id>/issue` — body with issued items/quantities; create stock ledger movements and link to dispatch.
- `GET /api/inventory/transactions?warehouse_id=&resource_id=&type=&from=&to=&page=&per_page=`.
- `POST /api/inventory/transactions/<int:transaction_id>/reverse` — Admin/authorized Official only; reason required; create a compensating transaction, never edit/delete the original.

An inventory quantity must never become negative. Insufficient stock must return HTTP `409` with code such as `INSUFFICIENT_STOCK`, item ID/name, requested quantity and available quantity. If the request supports partial fulfillment, store exactly what has been reserved and what remains outstanding.

## 26.5 Donation and receipt APIs

- `GET /api/donations?status=&type=&incident_id=&organization_id=&from=&to=`
- `POST /api/donations` — NGO Coordinator/authorized official; body has `donor_name`, `donation_type`, optional `organization_id`, `incident_id`, `zone_id`, `destination_warehouse_id`, `reference_code`, and for cash `declared_amount_paise`; in-kind item list has `resource_id` and `quantity_declared`.
- `GET /api/donations/<donation_id>`
- `POST /api/donations/<donation_id>/mark-in-transit`
- `POST /api/donations/<donation_id>/receive` — body includes actual received quantities per item and receiver notes.
- `POST /api/donations/<donation_id>/verify` — authorized receiver/Official; body `{ "decision":"Accept|PartiallyAccept|Reject", "reason":"...", "items":[{"donation_item_id":1,"quantity_accepted":480,"quantity_rejected":0}] }`.
- `GET /api/donations/<donation_id>/timeline`

Only an authorized receipt verification action adds accepted in-kind amounts to stock. Reject or flag an invalid/inconsistent quantity. Make acceptance idempotent so retrying the same request cannot add stock a second time.

## 26.6 Volunteer profile, tasks and field reports APIs

Preserve `GET/POST /api/volunteers`, `POST/PATCH /api/volunteers/<id>/assign`, and `/unassign` where required for compatibility.

Add:
- `GET /api/volunteers?status=&skill=&zone_id=&organization_id=&available_at=`
- `GET /api/volunteers/<int:volunteer_id>` — scope-limited.
- `PATCH /api/volunteers/<int:volunteer_id>` — authorized profile updates.
- `GET /api/volunteer-tasks?status=&incident_id=&zone_id=&volunteer_id=&organization_id=`
- `POST /api/volunteer-tasks` — coordinator/Official within scope; required body fields include `title`, `task_type`, `description`, `volunteer_id`; optional `incident_id`, `zone_id`, `request_id`, `dispatch_id`, `quantity_expected`, `shift_start`, `shift_end`, safety instructions.
- `GET /api/volunteer-tasks/<task_id>`
- `POST /api/volunteer-tasks/<task_id>/accept`
- `POST /api/volunteer-tasks/<task_id>/decline` body `{ "reason":"..." }`
- `POST /api/volunteer-tasks/<task_id>/check-in` body `{ "lat":null, "lng":null, "notes":"..." }`
- `POST /api/volunteer-tasks/<task_id>/progress` body includes quantities and notes.
- `POST /api/volunteer-tasks/<task_id>/submit` — volunteer reports completion and final counts.
- `POST /api/volunteer-tasks/<task_id>/approve` — authorized supervisor; body `{ "reason":"..." }`.
- `POST /api/volunteer-tasks/<task_id>/request-correction` — reviewer; reason required.
- `POST /api/volunteer-tasks/<task_id>/cancel` — authorized person; reason required.
- `POST /api/field-reports` — volunteer, driver or authorized coordinator; body includes `incident_id`, `zone_id`, `category`, `severity`, `description`, optional lat/lng, resource requirement and evidence reference.
- `GET /api/field-reports?status=&incident_id=&zone_id=&severity=`
- `POST /api/field-reports/<report_id>/review` — authorized Official; decision and reason required.

Never change a volunteer to Available if they still have another active assignment or the task was not safely closed. Reconcile task quantities before approval.

## 26.7 Fleet and dispatch APIs

Preserve `GET /api/dispatches` and `POST|PATCH /api/dispatches/<id>/advance` for current frontend/test compatibility.

Add:
- `GET /api/vehicles?status=&type=&warehouse_id=`
- `POST /api/vehicles` — Admin/Official; fields `vehicle_code`, `vehicle_type`, optional capacities/capabilities, warehouse and current status.
- `PATCH /api/vehicles/<int:vehicle_id>` — restricted field updates and validation.
- `GET /api/dispatches/<dispatch_id>`
- `POST /api/dispatches` — normally created by request allocation service; direct creation restricted to authorized roles and must still reserve stock/validate driver and vehicle.
- `POST /api/dispatches/<dispatch_id>/accept` — assigned driver only.
- `POST /api/dispatches/<dispatch_id>/ready` — warehouse/operator role within scope; confirms picked/loaded quantities.
- `POST /api/dispatches/<dispatch_id>/start` — assigned driver; validates Ready state and required stock issue.
- `POST /api/dispatches/<dispatch_id>/arrive` — assigned driver.
- `POST /api/dispatches/<dispatch_id>/route-blockage` — assigned driver; body `{ "reason":"...", "lat":null, "lng":null, "notes":"..." }`.
- `POST /api/dispatches/<dispatch_id>/reroute` — authorized coordinator/Official; body includes new destination/route notes and reason.
- `POST /api/dispatches/<dispatch_id>/delivery-proof` — assigned driver; body includes delivered item quantities, recipient result, notes and proof reference.
- `POST /api/dispatches/<dispatch_id>/review-delivery` — authorized supervisor/Official; approve or reject with reason.
- `POST /api/dispatches/<dispatch_id>/return` — assigned driver/authorized warehouse receiver; records returned quantities and return condition.
- `POST /api/dispatches/<dispatch_id>/cancel` — authorized role; requires reason and correctly releases unissued reservations and vehicle/driver assignments.
- `GET /api/dispatches/<dispatch_id>/timeline`.

Driver assignment must use an active, eligible Driver user and an available compatible vehicle. If none exists, the API must return a conflict and retain the request in the appropriate pending state. Do not use hardcoded fallback names or non-existent vehicles. Validate that the logged-in Driver owns the dispatch before any driver action.

## 26.8 Shelter APIs

Preserve `GET /api/shelters` and `PUT|PATCH /api/shelters/<id>` but route occupancy changes through proper admission logic whenever possible.

Add:
- `GET /api/shelters?incident_id=&zone_id=&status=&capacity_available=`
- `POST /api/shelters` — Admin/Official; fields `name`, `capacity`, address/location and incident/zone where applicable.
- `POST /api/shelters/<int:shelter_id>/admissions` — authorized shelter operation; body `{ "request_id":"REQ-...", "people_count":4, "notes":"..." }`.
- `GET /api/shelter-admissions?status=&shelter_id=&incident_id=`
- `POST /api/shelter-admissions/<admission_id>/arrive`
- `POST /api/shelter-admissions/<admission_id>/admit`
- `POST /api/shelter-admissions/<admission_id>/exit`
- `POST /api/shelter-admissions/<admission_id>/transfer` — destination shelter, person count and reason; atomically validate destination capacity and change occupancy.
- `GET /api/shelters/<int:shelter_id>/timeline`.

The server, not the browser, calculates occupancy from active admission records or maintains a transactionally consistent count. Do not accept an arbitrary new `occupants` value from an untrusted user. Legacy Official/Admin updates, if retained, need an audited adjustment reason.

## 26.9 Funds and finance APIs

Preserve `GET /api/funds` for the existing UI, but calculate it from persisted finance data rather than hardcoded totals.

Add:
- `GET /api/fund-budgets?incident_id=&organization_id=&category=`
- `POST /api/fund-budgets` — authorized Government Official/Admin; budget amount in integer paise and documented approval policy.
- `GET /api/fund-requests?status=&incident_id=&organization_id=`
- `POST /api/fund-requests` — NGO Coordinator/requesting organization; body includes `incident_id`, `category`, `purpose`, `requested_amount_paise`.
- `POST /api/fund-requests/<request_id>/approve` — authorized approver different from requester where dual control applies; body `{ "approved_amount_paise":8000000, "reason":"..." }`.
- `POST /api/fund-requests/<request_id>/reject` — reason required.
- `POST /api/fund-requests/<request_id>/commit` — authorized finance role; reference required.
- `POST /api/fund-requests/<request_id>/pay` — authorized finance role; body includes actual amount, transaction reference, payment date and receipt reference. Do not integrate real payments unless explicitly configured.
- `POST /api/fund-requests/<request_id>/reconcile` — separate authorized action and documented proof/reference.
- `GET /api/fund-transactions?incident_id=&organization_id=&type=&from=&to=`
- `GET /api/incidents/<incident_id>/financial-report`.

Use integer paise, never binary floats for stored money. Validate requested/approved/committed/paid/reconciled amounts and budget ceiling. Where partial payment or refunds are supported, represent them as separate ledger transactions. Never update an original transaction amount silently.

## 26.10 Inter-agency, advisories, notifications and reporting APIs

Inter-agency:
- `GET /api/inter-agency-requests?incident_id=&status=`
- `POST /api/inter-agency-requests` — Official; capability, quantity, requesting/receiving organization, urgency, destination and needed-by time required.
- `POST /api/inter-agency-requests/<id>/acknowledge`
- `POST /api/inter-agency-requests/<id>/decision` — accept/reject with reason.
- `POST /api/inter-agency-requests/<id>/mobilize`
- `POST /api/inter-agency-requests/<id>/complete`

Public advisories:
- `GET /api/advisories?incident_id=&zone_id=&status=`
- `POST /api/advisories` — Government Official; draft only.
- `POST /api/advisories/<id>/approve`
- `POST /api/advisories/<id>/publish`
- `POST /api/advisories/<id>/withdraw` — reason required.

Notifications:
- `GET /api/notifications?unread_only=&page=&per_page=` — return only rows for the current user unless Admin has a documented privileged view.
- `POST /api/notifications/<int:id>/read`
- `POST /api/notifications/read-all` — current user only.
- Preserve `GET /api/events/poll` and `GET /api/events/stream`; authorize event access and avoid leaking private fields in event payloads.

Reporting:
- `GET /api/incidents/<incident_id>/report` — summary of requests, allocations, dispatch outcomes, stock movements, volunteer tasks, shelters, donations and finance; values derive from actual records.
- `GET /api/incidents/<incident_id>/report.csv` or use the existing `/api/export/<dataset>.csv` with authorization filters.
- Preserve CSV export for supported legacy datasets; reject unknown dataset names; protect against CSV formula injection by escaping cells beginning with `=`, `+`, `-`, or `@` when appropriate.

# 27. REQUIRED STATUS MACHINES AND TRANSITION GUARDS

Implement state transition maps in shared service/business-logic functions and test every transition. Do not scatteredly set arbitrary status strings in routes.

## 27.1 Emergency request

Normal path: `Submitted → Under Review → Verified → Awaiting Allocation → Allocated → Dispatched → Delivered Pending Confirmation → Delivered → Closed`.

Alternate states: `More Information Required`, `Duplicate`, `Rejected`, `Partially Fulfilled`, `Cancelled`, `Awaiting Resource`.

Guards:
- Only an authorized user can verify/reject/allocate.
- A request cannot be allocated before verification, except an explicitly configured emergency override recorded with actor and reason.
- A Delivered/Closed request cannot be silently reallocated.
- Partially fulfilled must carry requested, allocated, delivered and outstanding quantities.
- Duplicate requests must reference a different valid primary request and must not form a cycle.
- Closing requires fulfillment or a documented authorized resolution reason.

## 27.2 Incident

`Draft → Under Verification → Active → Stabilizing → Closed`; alternative `Rejected` or `Cancelled` from permitted pre-active states.

Do not close an incident while there are unresolved critical requests, active dispatches, unresolved field reports or open volunteer tasks unless the Official explicitly uses a documented override with reason and the system reports the unresolved items.

## 27.3 NGO zone adoption

`Requested → Under Review → Approved → Active → Expired/Revoked`; rejection goes to `Rejected` and terminal states require explicit re-submission to restart.

## 27.4 Donations

`Draft → Submitted → In Transit → Received → Verification Pending → Accepted`.

Alternatives: `Partially Accepted`, `Rejected`, `Cancelled`, `Exception Review`.

Do not re-run the inventory acceptance effect if status is already Accepted/Partially Accepted. If quantities differ from declared values, preserve the discrepancy and decision reason.

## 27.5 Reservation and stock

Reservation states: `Active`, `Partially Issued`, `Issued`, `Released`, `Expired`, `Cancelled`.

Rules:
- Reserve only available stock.
- Reservation quantity is not physical issue.
- Release only unissued reserved quantities.
- Issue no more than reserved quantities unless a separately authorized stock issue is recorded.
- Returns and damage create independent ledger transactions.
- Correcting a movement requires an opposite/compensating transaction, not deletion.

## 27.6 Volunteer task

`Created → Assigned → Accepted → In Progress → Submitted for Review → Completed`.

Alternatives: `Declined`, `Reassignment Required`, `Needs Correction`, `Cancelled`.

Only assigned volunteer can accept/decline/check in/submit; authorized supervisor can approve or request correction. Duplicate active assignments must be blocked unless concurrent tasks are explicitly allowed and the volunteer availability rules permit them.

## 27.7 Dispatch

`Planned → Stock Reserved → Picking → Loading → Ready → En Route → Arrived → Delivered Pending Proof → Delivered`.

Alternatives: `Allocation Blocked`, `Route Blocked`, `Failed Delivery`, `Returned to Warehouse`, `Cancelled`, `Partially Delivered`.

A driver can only perform driver actions on their own assigned dispatch. En Route requires valid Ready state and a recorded departure. Delivered requires item reconciliation and the configured delivery proof/review policy. A failed/blocked dispatch must not be marked delivered. Cancellation must release unissued stock and vehicle reservations correctly.

## 27.8 Shelter admission/transfer

Admission: `Referred → Confirmed → Arrived → Admitted → Exited`, with `NoShow`/`Cancelled` alternatives. Transfer: `Requested → Approved → InTransit → Completed`, or `Cancelled`.

Do not increase occupancy until admission occurs. Exit reduces occupancy exactly once. Transfer must decrement source and increment destination atomically only on the defined completion event; use a transfer reservation if necessary to avoid double counting. Deny admissions beyond capacity except documented emergency overrides.

## 27.9 Funds

Request: `Draft → Submitted → Approved → Committed → Partially Paid/Paid → Reconciled`; alternatives `Rejected`, `Cancelled`, `Disputed`.

Approval does not mean payment. Commitment does not mean payment. Payment does not mean reconciliation. All amount changes must be separately recorded and authorized.

# 28. TRANSACTIONAL BUSINESS LOGIC — EXACTLY WHAT MUST HAPPEN

## 28.1 Request allocation service

Implement one service function, for example `allocate_request(request_id, actor_id, idempotency_key=None)`, used by the route and tests. In one database transaction:

1. Fetch request and confirm it exists, is in an allocatable state, and is inside the actor's authorized scope.
2. Require verification unless a documented emergency override is used.
3. Read all `request_items`; if there are none, map the legacy text `need` to a resource only if the mapping is unambiguous, otherwise return a clear conflict asking the coordinator to add resource items.
4. Validate warehouse stock and reserve quantities using an atomic conditional update or transaction-safe lock strategy.
5. If sufficient stock does not exist, do not create a normal successful allocation. Return an explicit shortage result with the items/quantities available, leaving the request in a pending/partial state according to policy.
6. Validate that an active eligible Driver and compatible available vehicle exist. Do not assign a fake fallback driver or vehicle. If no assignment is possible, roll back the incomplete allocation or leave a clearly recorded `Awaiting Dispatch Resources` state without double-reserving stock. Pick one behavior, document it, and test it.
7. Create a reservation and reservation items; create one linked dispatch (or a documented split dispatch if this is intentionally supported); create dispatch item rows; associate incident/zone; update request status.
8. Record inventory transaction ledger entries for reservations, request status events, an activity entry, an audit entry and system events inside the same transaction where feasible.
9. Commit only if all required invariants pass.
10. Return the request, reservation, dispatch, assigned driver/vehicle and stock summary so the frontend can refresh all affected modules.

Idempotency requirement: repeating the same allocation request must not create another dispatch, reserve/deduct stock a second time, or duplicate activity/events. If an allocation already exists, return its details or a conflict with a stable error code.

## 28.2 Dispatch departure

When the assigned Driver starts the journey:

1. Authenticate and confirm exact driver/dispatch ownership.
2. Confirm dispatch is Ready and all required items were picked/issued.
3. Mark the dispatch En Route, set `departed_at`, set vehicle En Route, update the linked emergency request to Dispatched, and record event/audit history atomically.
4. Return the refreshed request/dispatch/vehicle state.

## 28.3 Delivery and return reconciliation

When the Driver submits delivery:

1. Validate each delivered quantity is non-negative and not more than loaded quantity.
2. Validate returned/damaged quantities and item balance. For each line, quantities must reconcile according to the chosen explicit equation, e.g. `loaded = delivered + returned + damaged + unresolved`, with unresolved quantity requiring an exception reason and review.
3. Create a delivery proof record; do not directly set final Delivered status if proof review is required.
4. Notify the Citizen/request owner and authorized supervisor, without exposing sensitive information to unrelated users.
5. When reviewed, update each `request_item` delivered quantity and recalculate request fulfilment status. Only mark Delivered when fulfilment policy is satisfied; otherwise Partially Fulfilled/Needs Review.
6. Record returned stock only when warehouse receipt and condition are verified.
7. Update vehicle status only after return/readiness checks.

## 28.4 Donation acceptance

In one transaction, verify each received and accepted quantity, ensure `accepted <= received <= declared` unless a documented exception is authorized, create stock ledger movements for accepted in-kind quantities, update canonical warehouse stock, mark the donation decision, write audit/activity/system events, and commit. Retried calls must not add the same stock twice.

## 28.5 Volunteer distribution

At task completion, reconcile received, completed/distributed, damaged, returned/remaining and unresolved quantities. The task cannot be approved if quantities do not reconcile or an explanation is missing. Stock movement must be linked to warehouse dispatch/task records so the same items cannot be simultaneously counted in warehouse stock and field stock.

## 28.6 Shelter occupancy

Protect occupancy against concurrent admissions. Validate available capacity using a transaction and unique/serialized updates. An exit or transfer must apply once only. Store admission records as the historical source; occupancy summary must match active admissions or a documented opening-balance reconciliation.

## 28.7 Financial operation

Use integer paise. Before approval/commit/payment, verify the actor's authority, amount and remaining budget. Store approved/committed/paid/refunded amounts as ledger movements and calculate totals from transactions. Use a unique transaction/reference/idempotency key to protect against duplicate payment recording. A manual payment record is a demo ledger event, not a real payment gateway.

# 29. REQUIRED UI PAGES AND FUNCTIONAL CONTROLS

Build the pages/views within the existing single-page Jinja/vanilla-JS application unless the existing router suggests a compatible structure. Every button listed must have a real backend handler and permission checks.

## Administrator UI
- User approvals: Pending, Approved, Rejected, Suspended filters; approve/reject/reactivate with reason.
- Master data: incidents overview (not command override), organizations, resources, warehouses, vehicles, shelters and system settings.
- Audit log: filters by actor/action/entity/date.
- System health: migration version, database connectivity, recent errors, pending events.

## Government Official UI
- Incident list and Create Incident form.
- Incident detail page: overview, zones, requests, resource shortage, dispatches, adoptions, field reports, shelters, funds, advisories and timeline.
- Request verification queue with score explanation, details, verify/request-info/reject/duplicate/escalate controls.
- Zone management and NGO adoption approval queue.
- Inter-agency requests and public advisories.
- Resource shortage and exceptional allocation approvals.

## NGO Coordinator UI
- Organization profile and approval status.
- Available zones / request adoption / active zone commitments.
- Donations: create, expected arrival, mark transit, receive status view, verification discrepancy and final stock receipt.
- Volunteer roster and task assignment board.
- Distribution report and daily operations ledger.
- Own organization request and resource views only.

## Citizen UI
- Create emergency request with field validation and location picker.
- Own requests only; request detail and chronological timeline.
- Display current status, assigned assistance/ETA only when recorded, and partial/blocked state honestly.
- Provide additional information, confirm assistance, report incomplete delivery.
- Avoid displaying other citizens' records or the full private address of other requesters.

## Volunteer UI
- Own profile, verified skills and availability.
- Assigned tasks, accept/decline, check-in, progress, field report, submit task for review.
- Show quantity reconciliation and status with reason when action is blocked.
- Show only permitted tasks and sensitive information.

## Driver UI
- Only own assigned dispatches.
- Vehicle and load manifest; accept, ready confirmation if authorized, start journey, arrive, route blockage, reroute request, delivery quantities/proof and return report.
- Show invalid status transitions with a clear explanation and allowed next action.

## Shared UI requirements
- Create loading/empty/error/success states for every asynchronous call.
- Add filters/search only when the backend supports them.
- Confirm destructive/high-impact operations.
- Disable duplicate submit while an action is pending and still enforce idempotency on the server.
- After a mutation, refresh all affected modules from the API rather than editing a random count locally.
- Use proper accessible labels and responsive layouts.
- Use clear states like `Awaiting Verification`, `Awaiting Resource`, `Partially Fulfilled`, `Route Blocked`, `Needs Review`, not vague generic labels.
- Never display fake progress percentages, fake live GPS, fake SMS-delivery status, arbitrary sample fund totals or pretend verified donation data.

# 30. REQUIRED RESPONSE EXAMPLES AND ERROR CASES

Document at least one request/response example for every endpoint family and include tests for the following error cases:

- Unauthenticated request returns 401.
- Authenticated role without permission returns 403.
- Private record belonging to another Citizen returns 403 or 404 according to the documented privacy policy.
- Missing record returns 404.
- Malformed JSON or missing required field returns 400 with field-level details.
- Invalid enum or state transition returns 409 or 422 consistently.
- Repeated allocation/idempotent retry does not duplicate dispatch or stock movement.
- Insufficient stock returns 409 and leaves ledger/stock consistent.
- No eligible driver/vehicle returns a clear conflict, not a fake assignment.
- Delivery quantity greater than loaded quantity is rejected.
- Donation acceptance repeated twice creates only one inventory credit.
- Shelter capacity would be exceeded: reject without changing admission or occupancy.
- Payment amount above approved/committed amount is rejected.
- Event stream cannot reveal another organization's or Citizen's confidential content.
- CSV formula injection is neutralized and access is permission-filtered.

# 31. REQUIRED DEMO SEED DATA AND DEMONSTRATION SCRIPT

Create an explicit `seed_demo.py` or equivalent idempotent seed command. Do not seed or reset data automatically on every app startup. Preserve user data and prevent duplicates using stable codes/IDs and uniqueness constraints.

The seeded local demo must include:
- One fictional active flood incident, at least three zones, and an incident timeline.
- At least three Citizens with multiple requests and different needs/priorities.
- One approved NGO organization and one pending adoption/approval scenario.
- Two warehouses and multiple resources including medical kits, food kits, water and blankets.
- A donation where declared quantity differs from received quantity, plus a verified in-kind donation that changes stock exactly once.
- At least three Volunteers with distinct skills and at least one task in Assigned/In Progress/Review status.
- At least three vehicles with different statuses, at least one active Driver and at least one dispatch that can complete the full lifecycle.
- At least two shelters with different occupancies and one admission/transfer workflow.
- At least one fund request in approval/commit/payment/reconciliation progress with plausible fictional amounts.
- One route-blockage or partial-delivery exception ready to demonstrate.

Use obviously fictional names/records and mark the environment as a local demo. Do not claim connection to a real government organization or real relief operation.

Deliver an exact 10–15 minute demonstration script where each step states: role to log in as, page to open, action to click/submit, record ID to note, expected database change, expected event/notification, and screen that verifies the change.

# 32. MIGRATION, CONFIGURATION AND LAUNCH REQUIREMENTS

- Add an explicit migration version table, e.g. `schema_migrations(version, applied_at)`.
- Each migration must be idempotent, ordered, safely retryable, and transactional where SQLite permits. Test fresh database initialization and migration from the supplied old schema.
- Back up the existing SQLite database before destructive structural migration; never drop or replace the supplied DB silently.
- Keep development DB and test DB separate. Tests must never mutate the user's production/demo database.
- Ensure `PRAGMA foreign_keys=ON` for every SQLite connection; consider a suitable busy timeout and WAL mode if tested/appropriate.
- Store configuration secrets in environment variables. Provide `.env.example` without real credentials. Keep development-only demo credentials clearly labelled.
- Update `requirements.txt` only for packages actually used.
- Keep `run.bat` and `run.ps1` functional, or update them and document changes.
- Ensure the application starts from the documented working directory and reports migration errors clearly.
- Add graceful handling for a missing or inaccessible database, but never silently create fake data to hide a failure.

# 33. ACCEPTANCE TEST MATRIX — IMPLEMENT, RUN, AND REPORT RESULTS

Create tests that exercise the live Flask test client against a temporary isolated SQLite DB. Add an end-to-end test covering the connected workflow, not merely separate route-unit tests.

Minimum end-to-end path:
1. Government Official activates an incident and creates a zone.
2. NGO Coordinator requests adoption; Government Official approves it.
3. Citizen submits a request tied to the incident/zone; the request is private to that Citizen.
4. Authorized responder verifies the request and adds required resources.
5. A verified donation is received and accepted; accepted quantities change stock and appear in the ledger once.
6. Coordinator allocates the request; stock reservation, reservation item, dispatch, dispatch items and linked events are created atomically.
7. Driver starts the assigned dispatch; request transitions to Dispatched and vehicle becomes En Route.
8. Driver reports an optional route blockage and authorized coordinator records a resolution/re-route without losing history.
9. Driver submits partial or full delivery proof and quantity reconciliation.
10. Citizen confirms delivery or reports an issue; authorized reviewer finalizes request status.
11. Volunteer accepts and completes a connected field task; stock/task quantities reconcile.
12. Shelter admission/transfer updates occupancy correctly if this request includes evacuation.
13. Finance totals and incident report reflect persisted transactions only.
14. Administrator/Government Official can view permitted audit/timeline records and CSV exports; an unauthorized role cannot access global records.

Minimum assertions:
- No negative stock, capacity, quantity or fund amount.
- No duplicate dispatch/reservation/stock movement when a request is retried.
- Failure halfway through a transaction rolls back related state changes.
- Request and dispatch statuses cannot diverge after a successful transition.
- Stock ledger and current stock reconcile.
- Donation acceptance does not double-credit stock.
- Shelter occupancy equals active admission count/opening balance according to documented model.
- Fund dashboard totals match ledger transaction sums.
- Every important mutation produces an authorized event/audit record.
- Event payloads and CSV exports do not leak unrelated private data.
- Legacy endpoints and current test expectations remain compatible or are intentionally migrated with updated tests proving equivalent behavior.

Run at least:
- the project's documented test command (usually `pytest -q`)
- syntax/compile checks for Python
- any JavaScript lint/build check configured by the project (do not invent a build tool if none exists)
- fresh-database initialization test
- migration-from-existing-database test
- manual role-based smoke test

In the final report, include each command and its actual pass/fail result. Do not write “all tests passed” unless the full suite actually passed.

# 34. REQUIRED DELIVERY OUTPUT

Modify the project files directly and deliver the working repository or ZIP. At completion provide:

1. A clear list of features actually implemented.
2. A list of files created/changed.
3. Database tables/migrations and key relationships added.
4. An API table showing method, path, roles allowed and purpose.
5. The exact end-to-end workflows proven by tests.
6. Exact environment setup and launch commands for Windows and, if supported, other platforms.
7. The seed command and confirmed demo credentials from actual files.
8. Test commands and real results, including known failures.
9. Known limitations, simulation-only integrations and unfinished items.
10. A short evaluator/viva explanation of how the connected workflow works.

Do not claim production readiness. Describe the result as a tested academic/demo platform unless operational deployment, security review, backups, monitoring, disaster recovery, privacy compliance and real-world validation have actually been completed.

FINAL EXECUTION COMMAND: Start inspecting the code now, use this specification as the implementation contract, make the changes in the repository, run the tests, correct the issues you find, and deliver the modified runnable project. Do not stop after writing a plan.
