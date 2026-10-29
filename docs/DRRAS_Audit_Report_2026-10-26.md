# DRRAS-Flask Audit Report

**Audit date:** 26 October 2026  
**Reviewed artifact:** `DRRAS-Flask(5).zip`  
**Audit method:** Extracted to an isolated working copy; source inspection, syntax checks, temporary-database migration/seed checks, and a direct service-layer failure reproduction. The uploaded ZIP and its original database were not modified.

## Executive verdict

**Status: Substantial progress, but not correct/complete enough to accept as finished.** The implementation has added a meaningful service layer, versioned SQLite migrations, operational tables, multiple new APIs, role workflows, a demo seed script, documentation, and a broad pytest suite. However, there are severe authorization/privacy gaps and several workflows contradict the master specification. Most importantly, the delivery-proof review path can mark a request `Delivered` even when the proof is rejected, and stock reservation/vehicle state is not reconciled properly. The old frontend also still uses a legacy dispatch endpoint that can bypass delivery proof.

Do not present this build as production-ready or as fully satisfying the master prompt yet. Some basic code/data checks passed; the full Flask/pytest suite could not be run in this sandbox because Flask/Werkzeug dependencies were not installed and package installation failed due to unavailable network access.

## What is genuinely implemented

- The project retains the requested Flask + SQLite + Jinja2 + vanilla JavaScript stack.
- Added/expanded files include `api_routes.py`, `services.py`, `migrations.py`, and `seed_demo.py`.
- Four versioned migrations are recorded in the tested temporary database.
- The migrated schema creates 41 tables, including incidents, zones, organizations, adoptions, resources/warehouses/stock, reservations, inventory transactions, request items/events, volunteer tasks/checkpoints, vehicles/dispatch items/delivery proofs, donations/items, shelter admissions/transfers, fund budgets/requests/transactions, notifications and audit logs.
- A number of service-layer operations exist for incident creation/activation, NGO zone adoption, request verification/allocation, driver trip events, proof submission/review, donations, volunteer tasks, shelter workflows and fund requests.
- README documentation now describes API/workflows and discloses that some external integrations are simulated.
- Python and JavaScript syntax checks passed (details below).

These are meaningful improvements, but their existence is not sufficient proof that each workflow is properly authorized or works end to end.

## Verification performed

| Check | Result | Notes |
|---|---|---|
| Python syntax | PASS | `python -m py_compile app.py api_routes.py database.py migrations.py services.py seed_demo.py` |
| JavaScript syntax | PASS | `node --check static/js/app.js` and `node --check static/js/icons.js` |
| Fresh temporary SQLite database | PASS with import shim | Migrations initialized; versions 1–4 recorded; 41 tables created. A temporary test-only `werkzeug.security` shim was required because Werkzeug was not installed. This is not an authentication or HTTP integration test. |
| Demo seed idempotency | PASS with import shim | Seeded twice into a temporary database; counts remained stable (e.g. 8 users, 1 incident, 3 zones, 3 organizations, 2 adoptions, 5 resources, 2 warehouses, 10 warehouse-stock rows, 4 requests, 3 dispatches, 3 volunteer tasks, 3 donations, 3 shelters, 2 admissions, 1 fund request and 2 fund transactions). |
| SQLite foreign-key check | PASS | `PRAGMA foreign_key_check` returned no rows for the temporary migrated/seeded DB. |
| Legacy-schema migration | PASS with import shim | A synthetic legacy DB retained its user record through migration; no foreign-key violations were found. This does not prove every historical user DB shape migrates correctly. |
| Full pytest suite | BLOCKED | `python -m pytest -q` stopped during import with `ModuleNotFoundError: No module named 'werkzeug'`. |
| Install dependencies | BLOCKED | `python -m pip install -r requirements.txt` failed because package index/DNS network access was unavailable; no Flask/Werkzeug install could be completed. |
| Delivery-review service reproduction | FAIL | A rejected proof still changed the emergency request to `Delivered`; reservation stayed `Active`, reserved quantity remained locked, on-hand quantity did not get reconciled, and vehicle became `Available`. Reproduced on a disposable temporary DB using actual project services. |

**Important:** The repository contains a pytest cache/README claim of “68 passed”, but this audit could not independently reproduce that result in the current environment. It should be treated as an existing project claim, not an audit-confirmed test pass.

## Critical issues to fix first

### P0 — Sensitive endpoints expose operational/private data

- `app.py` `GET /api/requests` (around lines 328–332) has no `login_required` and returns all requests including names, addresses, locations and emergency needs.
- `app.py` `GET /api/dispatches` (around lines 620–624) is public and returns driver/destination/cargo details.
- Event stream/poll endpoints in `app.py` are not authenticated/scoped; polling from an old event ID can expose global event history. Events may contain request data.
- `app.py` CSV export only blocks Citizens from a few datasets; a Citizen can export `requests.csv`, including every requester’s identifying/address data.
- `api_routes.py` donation list/detail, field reports, shelter admissions and several finance/fleet reads are public or insufficiently scoped.
- `api_routes.py` request item/timeline/detail endpoints do not consistently enforce citizen ownership and incident/zone scope.

**Required fix:** Default sensitive reads to authenticated + scope-authorized; allow unauthenticated/public data only through a deliberate, minimal public projection. Restrict Citizen exports to their own records or deny them entirely. Scope event feeds and SSE/poll access to authorized recipients.

### P0 — Citizen delivery confirmation lacks ownership and lifecycle checks

- `api_routes.py` `citizen_confirm_delivery` (around lines 597–615) does not verify that the caller owns the request, and does not sufficiently require a valid dispatch/proof state. Any authenticated user may be able to mark another user’s request `Delivered` prematurely.
- `report_request_issue` (around lines 619–638) similarly lacks a clear requester/record ownership check.

**Required fix:** Verify role, `requester_user_id == session user` for Citizen actions, valid request state, linked dispatch/proof conditions, and incident/zone scope. Return `403` or `409` as appropriate and add IDOR tests.

### P0 — Universal Administrator permission bypass

Both `app.py` and `api_routes.py` `roles_required` helpers let `Administrator` pass every role guard even when not listed. This gives implicit operational powers such as incident commands, financial actions or field workflow approvals, contrary to the role matrix in the master prompt.

Login checks `PENDING` and `REJECTED` but not `SUSPENDED` in `app.py` around lines 141–150; existing sessions are not clearly invalidated on suspension either.

**Required fix:** Remove implicit Admin bypass; create explicit, audited override permissions for specific operations only. Reject suspended/inactive accounts during login and validate active status on authenticated requests.

### P0 — Legacy dispatch endpoint bypasses delivery proof

- The main dispatch UI in `static/js/app.js` around lines 3227–3255 still calls `/api/dispatches/<id>/advance` and presents “Confirm Delivery”.
- `app.py` `advance_dispatch` (around lines 628–679) can transition `En route` directly to `Delivered` without proof, item reconciliation or review.
- This also identifies the Driver by display-name string (`session.name == dispatch.driver`) rather than canonical `driver_user_id`.

**Required fix:** Wire the UI exclusively to the newer lifecycle (arrive → submit proof → authorized review → reconcile). Remove or safely deprecate the bypass endpoint, or make it reject direct delivery completion. Use canonical foreign keys for ownership.

### P0 — Rejected delivery proof still marks request Delivered

`services.py` `review_delivery_service` (around lines 554–596) chooses dispatch status `Partially Delivered` when the proof is rejected/needs review, but **always** sets the related request to `Delivered` and sets `delivery_confirmed_at`. It also sets the vehicle `Available` regardless of rejected proof and does not release/convert the active reservation correctly.

This was reproduced in a disposable SQLite database:

```text
Reservation created: RSV-019
Stock before (on_hand,reserved): (4820, 0)
Stock after rejected proof (on_hand,reserved): (4820, 2)
Request after rejected proof: status='Delivered'
Reservation after delivery review: status='Active'
Proof after rejection: status='Rejected'
Vehicle status after rejection: Available
```

**Required fix:** Rejected/needs-review proof must not close or mark the request delivered. Require valid current dispatch state and an existing submitted proof. Only verified complete delivery may mark `Delivered`; partial/rejected delivery must remain unresolved with an explicit exception path. Do not release vehicle or inventory until the trip/return workflow is reconciled.

## High priority correctness/security issues

### P1 — Allocation can bypass request verification and choose unavailable vehicles

- `app.py` allocation handler around lines 422–438 calls `allocate_request_service(... emergency_override=True)` for permitted users, bypassing the service’s normal verification guard.
- `services.py` allocation selection (around lines 213–230) can fall back to a vehicle that is not available and can fabricate a display string such as `V-12 · Relief Van` when no actual vehicle row is available.
- Vehicle capacity/readiness and required resource mapping are not consistently enforced. A rescue request may map to a generic food resource or create an allocation without the right item mapping.

**Fix:** Remove unconditional emergency override. Make override explicit, narrow, authorized, reason-required and audited. Never fabricate a vehicle assignment; if no compatible available vehicle/resource exists, return a conflict and leave the request awaiting allocation. Require an explicit resource mapping when a legacy `need` label is ambiguous.

### P1 — Stock has two competing sources of truth and reservations are not reconciled

- `allocate_request_service` reserves canonical `warehouse_stock` and creates a reservation/memo transaction, but also decrements the legacy `inventory.available_units` at reservation time.
- The legacy `/api/inventory` create/update routes update only the old `inventory` table, not canonical resources/warehouse stock/ledger.
- After delivery/rejected proof, reservations remain active and the reserved quantity is never properly converted to issued/delivered/returned quantities.
- Frontend calls `/api/inventory/ledger` (`static/js/app.js` around line 4669), but no matching route exists; the API available is `/api/inventory/transactions`.

**Fix:** Make `resources + warehouses + warehouse_stock + reservations + inventory_transactions` the canonical model. Treat `/api/inventory` as a compatibility serializer/adapter. Do not store a second independent balance. Implement reservation release, warehouse issue, delivery, returns and damaged stock as well-defined transactional ledger movements. Add the missing ledger endpoint or update the frontend to the real API.

### P1 — Finance actions are not sufficiently role-protected

- `api_routes.py` `fund_request_action` around lines 1224–1236 has login protection but no route-level role protection for every action.
- `services.py` `fund_request_action_service` enforces role restrictions for `approve`, but not equivalently for `commit`, `pay` and `reconcile`; a generic authenticated user can attempt those operations.
- `GET /api/funds` in `app.py` around lines 732–742 still uses hardcoded totals: `₹42.6L`, `₹28.1L`, `₹14.5L`, and percentage values.
- Budget creation sets a budget directly to Approved; public advisory creation directly marks the advisory Published and sets current user as approver; inter-agency request creation directly sets status Mobilized. These skip required approval lifecycle stages.

**Fix:** Add explicit per-action roles and organization/incident scope checks at route and service layers. Enforce dual control for approval/payment where appropriate. Calculate totals from ledger rows; start workflows in Submitted/Draft states and transition only through authorized actions. Correct partial payment tracking and prevent duplicate postings.

### P1 — Workflow actions lack state/scope validation

- `api_routes.py` `dispatch_ready` (around lines 970–981) only requires login; it does not adequately restrict role, ownership or legal state transition.
- Dispatch detail endpoint is login-only and not fully record-scoped. Reroute/blockage service actions lack sufficient state-transition checks, so completed/loading dispatches may be altered incorrectly.
- Volunteer task progress action is insufficiently authorized in `services.update_volunteer_task_status_service`; a random logged-in user may be able to add progress to an unrelated task. Task approval should require Submitted for Review.
- NGO zone adoption can fall back to the first approved organization or create/use a seeded organization when the logged-in Coordinator lacks a real membership. Fund request creation similarly falls back to an organization ID. This causes misattribution rather than a safe authorization error.

**Fix:** Validate acting user against canonical `driver_user_id`, assigned `volunteer_id`, organization membership and permitted zone/incident scope. Do not select fallback organizations or unrelated vehicles. Validate a single documented transition map for every state-changing route.

### P1 — Frontend/API contract mismatches cause broken workflows

- Volunteer task modal in `static/js/app.js` around lines 4561–4650 sends `title`, `zone_id`, `skill`, `target_quantity`, `unit`, `description`, but the API requires `volunteer_id` and `task_type`. Task creation will fail validation.
- In-kind donation form around lines 4510–4545 sends `resource_name` and `quantity_declared` without canonical `resource_id`; the service skips items without `resource_id`, so a donation header can be created without donation items and accepted goods will not enter stock.
- Delivery proof form around lines 5168–5256 sends `recipient_name`, `phone`, `received_quantity` and a fixed fake image data URI. The API reads different fields (`proof_type`, `proof_reference`, `notes`, `items`) and ignores the submitted recipient/quantity/image details. UI falsely toasts that proof was verified and request is Delivered even though backend enters proof review.
- Route blockage form sends `blockage_location` and `suggested_detour`, but endpoint reads `reason`, `notes`, `lat`, `lng`; key form data is lost.
- The stock ledger tab calls a missing endpoint.

**Fix:** Define request/response schemas once, make the frontend match them, validate payloads on the backend, and show the real returned state. Do not use hardcoded/fake data URLs as proof. Test every visible form through its real API.

### P1 — Shelter transfer can corrupt occupancy/admission history

`services.py` `transfer_shelter_service` (around lines 937–1000) allows a transfer of fewer people than the admission’s group size, updates the complete admission to point at the destination, but moves only part of the occupancy. It also uses `max(0, old_occupants - count)`, masking an occupancy mismatch rather than rejecting it. The legacy shelter update route can directly override `occupants` without an admission-ledger transaction.

**Fix:** Either enforce full-group transfer or model split admissions/household members explicitly. Validate source occupancy; never silently clamp an inconsistent count. Derive occupancy from admissions and transfer events, and restrict direct manual adjustments to an audited reconciliation action.

## Required API contract gaps

The master prompt specifies a wider API surface than is currently implemented. The following are absent or not implemented as full lifecycle endpoints (equivalent routes may be used if documented and tested):

- Request `request-info`, explicit `reject`, `escalate`, `close` and timeline completeness.
- `PATCH /api/resources/<id>` and warehouse create/update endpoints.
- Stock list/receipt endpoints, reservation create/release/issue routes, and stock transaction reverse/compensating endpoint.
- Donation mark-in-transit, receive, timeline endpoints and robust multi-item receipt validation.
- Volunteer profile `PATCH`, complete task status/review lifecycle and assigned-user checks.
- Vehicle create/update/readiness endpoints and vehicle maintenance lifecycle.
- Inter-agency acknowledgment/accept/reject/mobilize/complete action endpoints.
- Public-advisory draft/review/approve/publish/expire/withdraw lifecycle.
- Missing `/api/inventory/ledger` endpoint or corresponding UI correction.
- Consistent pagination for list endpoints where specified.

Some underlying service operations exist, but they do not substitute for a fully connected and authorized API/frontend workflow.

## Additional security/configuration observations

- `app.py` uses a fallback secret key (`drras-secure-local-session-key-2026`) when `SECRET_KEY` is absent. Acceptable for local-only development only if clearly guarded/documented; fail safely for non-development deployments.
- No CSRF protection was found for state-changing cookie-session APIs. Add CSRF token validation for browser mutations.
- Validate status of authenticated users on requests so suspending an account invalidates effective access, not just the login gate.
- Ensure uploaded evidence, if supported, uses safe filenames, file type/size limits, no arbitrary local paths and authorization checks.
- Seed users/demo data should be explicitly development-only and repeated seed runs must not reset real data.

## Prioritized repair plan

### Phase 1 — Close security/privacy holes
1. Protect `GET /api/requests`, `/api/dispatches`, donations, field reports, shelter admission, funds, fleet and event endpoints with authentication + role/scope checks.
2. Restrict request exports and all other CSVs by role, record scope and PII needs.
3. Remove universal Administrator bypass from both `roles_required` helpers; add explicit audited overrides only where needed.
4. Reject suspended users and validate account status on authenticated access.
5. Fix Citizen confirmation/report ownership and dispatch/task record authorization.
6. Add CSRF protection.

### Phase 2 — Make delivery a single safe workflow
1. Remove/deprecate the legacy direct-to-Delivered endpoint from the UI, or make it impossible to bypass proof/review.
2. Make proof payload and UI forms agree; remove fake proof image/status messages.
3. Do not mark a request delivered for rejected/needs-review/partial proof.
4. Only release the vehicle after a legitimate completion/return transition.

### Phase 3 — Establish one inventory truth
1. Canonicalize warehouse stock and transactions.
2. Make allocation reserve stock only; issue stock at warehouse handover.
3. Correctly reconcile reservations after issue, cancellation, delivery and return.
4. Make legacy inventory routes safe adapters, not independent stock writers.
5. Fix the missing ledger route/front-end mismatch.

### Phase 4 — Fix UI/API contract and remaining workflows
1. Fix volunteer task form payload and select/assign a real eligible volunteer.
2. Resolve in-kind donation resource IDs and reject malformed items instead of silently skipping.
3. Persist delivery quantity, recipient confirmation and route blockage/reroute fields correctly.
4. Add vehicle/warehouse/stock APIs and missing inter-agency/advisory lifecycles.
5. Fix organization membership fallbacks and shelter partial transfers.

### Phase 5 — Re-run full verification
1. Run pytest in an environment with the declared dependencies installed.
2. Fix all failing tests; add tests specifically for each finding above.
3. Run the complete citizen → verified request → reservation → picking/issue → dispatch → proof review → stock/request closure scenario for success, partial delivery and rejected proof.
4. Test unauthenticated and wrong-role access to every sensitive list/detail/export/SSE endpoint.
5. Re-run migration and seed idempotency checks, and inspect the final database for FK violations.
6. Update README/API docs so their claims match verified behavior.

## Final assessment

The other AI produced more than a superficial UI: there is real database and service-layer work. But several requirements in the master prompt are currently only partially implemented, incorrectly wired or contradicted by old routes. **Do not accept the current ZIP as “done” yet.** Prioritize data privacy/authorization and delivery/inventory consistency before adding more screens. Full pytest/HTTP behavior remains unverified in this environment due missing dependencies/network, and that limitation must not be confused with a pass.
