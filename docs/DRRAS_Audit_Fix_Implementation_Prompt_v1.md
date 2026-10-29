# DRRAS — DETAILED AUDIT-REPAIR AND VERIFICATION PROMPT

**Purpose:** Repair the concrete security, workflow, database consistency, API/UI integration, and testing problems found in the latest DRRAS-Flask audit. This is an implementation prompt, not a request for advice.

## HOW TO USE THIS PROMPT

Give the coding AI these inputs together:
1. The **latest DRRAS-Flask ZIP/repository** (the newest version, not an older copy).
2. The existing `DRRAS_Master_Implementation_Prompt_v2.md` or its TXT equivalent.
3. The audit report `DRRAS_Audit_Report_2026-10-26.md`.
4. This file, `DRRAS_Audit_Fix_Implementation_Prompt_v1.md`.

This repair prompt adds concrete mandatory corrections to the master prompt. It does not replace the broader functional requirements in the master prompt. If the current repository differs from the audited ZIP because work continued after the audit, **inspect the current code and adapt the findings to its current state**. Do not blindly reapply old patches.

---

# 1. YOUR ROLE AND REQUIRED OUTPUT

Act as a senior Flask/Python engineer, SQLite database architect, application-security engineer, frontend integration engineer, and QA engineer.

You must edit the actual working project, not merely explain what should be done. Your responsibilities are to:

- inspect the current repository and all existing modifications;
- identify which audit findings still exist, which have already been fixed, and which have changed;
- fix the outstanding findings in the priority order below;
- implement and connect real database-backed operations;
- add regression tests before or alongside fixes;
- run syntax checks, migrations, service tests, HTTP/API tests and the full test suite where dependencies permit;
- fix regressions caused by your changes;
- update documentation to match the actual code;
- deliver the corrected project directory or ZIP and a truthful test report.

**Do not stop after an audit, plan, TODO list, or sample code.** Do not ask me to implement the fixes manually. Do not create only visual changes. Continue through implementation and verification until all feasible work is done.

Do not claim any test passed unless you executed it and observed a passing result. If a dependency or environment prevents a test from running, label it `BLOCKED`, show the command and actual error, and continue with the tests that are possible.

# 2. CURRENT PROJECT CONTEXT AND AUDIT FACTS

The project is **DRRAS — Disaster Relief Resource Allocation System**. Preserve the existing stack unless a specific technical requirement demands a minimal, justified change:

- Python + Flask
- SQLite
- Jinja2 templates
- HTML/CSS/vanilla JavaScript
- existing run scripts and established user interface
- pytest-based testing

Existing files/routes may include `app.py`, `api_routes.py`, `services.py`, `database.py`, `migrations.py`, `seed_demo.py`, `drras.db`, `templates/index.html`, `static/js/app.js`, CSS files, seed data, documentation and tests. Inspect actual files before making assumptions.

There are six roles: `Administrator`, `Government Official`, `NGO Coordinator`, `Volunteer`, `Citizen`, and `Driver`.

The prior audit of `DRRAS-Flask(5).zip` observed the following. Re-check each item against the current repository rather than assuming it still exists:

1. The Python and JavaScript syntax checks passed.
2. Four schema migrations and a 41-table migrated/seeded temporary database were checked; foreign-key validation returned no violations in that test database.
3. Seed idempotency passed on a disposable database.
4. The full pytest suite could not be run in that audit environment because `werkzeug` was missing; dependency installation was blocked by network/DNS failure. A README/cache claim of `68 passed` was not independently verified by that audit.
5. A real service-layer reproduction showed that rejecting delivery proof still set the emergency request to `Delivered`, left a reservation active, failed to reconcile stock, and made the vehicle available. This is a verified prior defect unless subsequently fixed.
6. The legacy UI still called `/api/dispatches/<id>/advance`, which could move a dispatch directly to `Delivered` without proof review and reconciliation.
7. Some sensitive reads/exports/events were public or insufficiently scoped; Citizen delivery confirmation/request-issue actions lacked record ownership checks; role decorators gave Administrator a universal permission bypass; suspended account handling was incomplete.
8. There were API/UI payload mismatches for volunteer tasks, donations, delivery proof and route blockages; an inventory ledger UI referenced a missing endpoint.
9. Inventory balances could diverge between a legacy inventory table and warehouse stock/ledger tables.
10. Fund totals were hardcoded in a legacy `/api/funds` handler; finance action permissions were incomplete; some financial/advisory/inter-agency workflows skipped their intended approval state.
11. Allocation could bypass request verification and could fall back to unavailable/nonexistent vehicles; NGO/fund workflows could use fallback organization records instead of the logged-in user's verified organization membership.
12. Shelter partial transfer logic could move the full admission record while decrementing only part of occupancy, and direct shelter updates could overwrite occupancy without an admission-ledger transaction.

The audit report contains more detailed file references and reproductions. Read it fully before modifying code.

# 3. FIRST ACTIONS — SAFELY RECONSTRUCT THE CURRENT STATE

Before editing:

1. List/examine the project files and identify the actual repository root.
2. Inspect `git status` and `git diff` if Git metadata exists. Preserve uncommitted user/AI changes. If no Git repository exists, make a working backup/snapshot outside the active source directory.
3. Read the master prompt, this repair prompt, audit report, README, setup guide, route modules, services, migrations, database code, templates, JavaScript and tests.
4. Identify the exact current entry points for authentication, `roles_required`, database connections, migrations, seeding, stock mutation, allocation, dispatch advancement, proof review, finance, shelter transfers, event streaming/polling and CSV exports.
5. Run baseline checks before edits where practical. Record actual commands/results.
6. Make a compact tracking file such as `IMPLEMENTATION_PROGRESS.md` with: audit finding, current status (`OPEN`, `FIXED`, `TESTED`, or `BLOCKED`), files, tests and remaining work. Update it throughout the repair.
7. Do not operate on the user's real `drras.db` while experimenting. Use disposable temporary databases for migrations, seeding, reproductions and destructive/rollback tests.
8. Do not reset the database, remove features or remove existing tests as a shortcut.

If the newest source has already fixed a finding correctly, verify the fix and add/retain regression coverage rather than rewriting it unnecessarily.

# 4. PRIORITY P0 — CLOSE AUTHORIZATION AND PRIVACY HOLES FIRST

Treat this section as release-blocking. Fix it before adding new visual features.

## 4.1 Protect sensitive list/detail APIs

Inspect and repair, at minimum, these areas if they are still exposed or insufficiently scoped:

- `app.py`: `GET /api/requests`
- `app.py`: `GET /api/dispatches`
- `app.py`: event stream/SSE and event polling routes
- `app.py`: `GET /api/export/<dataset>.csv`
- `api_routes.py`: donation list/detail endpoints
- field-report list/detail endpoints
- shelter-admission list/detail endpoints
- finance and fleet/vehicle list/detail endpoints
- request detail, item, timeline, issue-report and delivery-confirmation endpoints
- dispatch detail and all operational mutation endpoints
- any newer endpoint that exposes addresses, coordinates, requester names, needs, donation/finance data, vehicle/driver details, proof references or audit records.

Default rule: sensitive operational data requires authentication and authorization to the exact resource/incident/zone/organization scope. Do not leave sensitive endpoints public simply because the frontend needs to call them.

If a public dashboard is genuinely needed, create a separate deliberately minimal public projection that does not contain private names, exact addresses, coordinates, contact details, medical descriptions, driver details, proofs or unrestricted event payloads. Do not make the complete private API public to support a demo.

### Required security tests

For each sensitive read endpoint, test at least:
- unauthenticated request;
- logged-in Citizen querying unrelated/global records;
- Volunteer attempting another person's task/report;
- Driver attempting another Driver's dispatch;
- NGO Coordinator attempting an unrelated organization's record;
- Government Official attempting a record outside allowed incident/zone scope, where scope applies;
- properly authorized user accessing an allowed record.

Use expected `401`, `403`, or `404` responses consistently. It is acceptable to return `404` for a record outside the caller's visibility to avoid information leakage, if the behavior is consistent and documented.

## 4.2 CSV exports must not leak private data

Audit every supported export dataset. Do not only block a Citizen from a few export names while allowing aliases or other datasets.

- Citizen: deny global exports, or export only the authenticated Citizen's own privacy-safe records.
- Volunteer: only permitted tasks/reports and fields required for the role.
- Driver: only assigned dispatch data and necessary fields.
- NGO Coordinator: only approved organization/zone scope.
- Government Official: records within authorized incident/district scope.
- Administrator: audit/configuration access according to explicit permission; do not interpret this as a reason for every other endpoint to bypass roles.

Protect against spreadsheet formula injection in CSV fields beginning with `=`, `+`, `-`, or `@` where applicable. Do not export password hashes, session data, unnecessary personal information, secret keys or unrestricted proof paths.

Add tests for each role and each export dataset/alias.

## 4.3 Scope SSE, event polling and notifications

`/api/events/stream` and `/api/events/poll` must not allow anyone to fetch the global history using an old event ID.

- Require an authenticated active account unless a separate public event feed is deliberately designed.
- Filter records by the user's authorized role and entity scope.
- Do not place unnecessary sensitive requester data in event payloads.
- Check authorization before returning event contents, not just before rendering the dashboard.
- Verify event IDs/cursors and ensure a client cannot obtain another user's private event by guessing an ID.
- Ensure reconnection/catch-up returns only events that user is allowed to see.
- Test unauthorized access, old-cursor history access and cross-user event access.

Distinguish `audit_logs`, `system_events`, `activities` and user-facing `notifications`; they serve different purposes.

## 4.4 Remove the universal Administrator bypass

Inspect both `app.py` and `api_routes.py` role decorators/helpers. If `Administrator` automatically passes every `roles_required(...)` guard, remove that implicit bypass.

Implement explicit authorization per operation:

- system administration and user management are Administrator responsibilities;
- incident command actions belong to Government Official unless a documented, audited emergency override is explicitly granted;
- NGO operations require verified organization membership and scope;
- Volunteer operations require assignment/ownership;
- Driver operations require canonical dispatch ownership;
- Citizen actions require request ownership.

If emergency override exists, implement a dedicated permission/helper for named operations. Require an explanation, record the actor and old/new states, and write an audit entry. Do not use a global “Admin can do anything” condition.

Add tests proving that Administrator is denied an ordinary Government Official/Driver/Volunteer/finance action unless that precise action has an explicit documented override. This is intentionally stricter than a universal bypass.

## 4.5 Suspended/inactive account handling

- Reject suspended, disabled, pending or rejected accounts at login according to the documented status model.
- Check the current database account status on authenticated requests or use a securely invalidated session/version mechanism. A user who was suspended must not retain working permissions through an old session.
- On logout/suspension, invalidate relevant session state.
- Add tests for login as suspended user and for using an existing session after suspension.
- Keep the existing session-cookie approach unless there is a strong technical reason to change it. Do not introduce JWT just to avoid implementing secure sessions.

## 4.6 Add CSRF protection to cookie-authenticated mutations

Inspect the current browser authentication model. If state-changing routes use the session cookie, implement CSRF protection suitable for the current Flask setup.

- Add a secure token generation/exposure path for the trusted frontend.
- Validate tokens on POST/PATCH/PUT/DELETE browser mutations.
- Apply the policy consistently to forms and JavaScript fetch calls.
- Do not exempt important mutation routes without justification.
- Keep API/automated tests usable by explicitly supplying tokens or using a test-only configuration, not by silently turning off CSRF in normal operation.
- Verify cookie flags/settings (`HttpOnly`, appropriate `SameSite`, `Secure` in HTTPS deployments) and origin assumptions.
- Test missing/invalid tokens and a successful valid-token request.

## 4.7 Secret key and error handling

The previous audit found a fixed fallback secret key. Do not ship a predictable fallback in non-development mode.

- Use environment/configuration for `SECRET_KEY`.
- Permit a clearly labelled development-only key only in explicitly configured local-demo mode.
- Fail safely on startup in production-like configuration if no strong secret is supplied.
- Never expose stack traces, SQL errors, paths, secrets or session data in API errors.
- Log diagnostic details server-side with sensitive values redacted.

# 5. PRIORITY P0 — REPAIR REQUEST OWNERSHIP AND REQUEST LIFECYCLE

## 5.1 Citizen request ownership

The authenticated session must determine the requester identity. Never accept `requester_user_id`/owner from a Citizen's client payload.

For each Citizen action, verify `requester_user_id == authenticated_user.id` or apply a separately documented delegated-access mechanism.

Fix and test:
- request detail;
- request items;
- request timeline;
- `citizen_confirm_delivery`;
- `report_request_issue`;
- additional-information responses;
- request cancellation where allowed;
- all client-callable request mutations.

A Citizen must not confirm or change a request belonging to another Citizen by substituting its ID.

## 5.2 Request state machine

Create/centralize a documented state-transition map and use it in service functions, not only in frontend controls.

The exact status set should remain compatible with existing client expectations where possible. At minimum model the distinct meanings of:

- submitted/unverified;
- under review;
- more information required;
- verified;
- awaiting allocation/resource;
- allocated;
- dispatched;
- partial fulfilment;
- delivery pending confirmation/review;
- delivered;
- closed;
- rejected;
- duplicate;
- cancelled.

Do not allow invalid shortcuts, for example:
- unverified request → delivered;
- rejected request → allocated without a documented reopen path;
- delivered request → en route;
- duplicate secondary request → independent allocation without appropriate review;
- cancelled request → delivery completed with no reopen/reconciliation action.

A request can only become Delivered after the associated dispatch/proof/quantity policy has passed. `Delivered` and `Closed` should have clearly distinct meanings. Keep a persisted `request_events` timeline including actor, timestamp, from/to state and reason.

## 5.3 Allocation verification bypass

The prior audit found that the legacy allocation handler could call `allocate_request_service(... emergency_override=True)` and bypass verification.

- Remove automatic bypass from normal allocation.
- Require the request to be verified before ordinary allocation.
- If emergency overrides are truly required, make them a separate documented Government Official operation with a mandatory reason, explicit permission, alert/audit, and tests.
- Ensure the UI makes it obvious when an override is used.
- Do not let a generic Administrator bypass verification just because it is Admin.
- If stock/vehicle capacity cannot be met, return a conflict with a useful message and leave all records in a consistent pending state.

# 6. PRIORITY P0 — ONE SAFE DELIVERY AND DISPATCH WORKFLOW

This is one of the most important verified defects. Fix the complete lifecycle from frontend to database.

## 6.1 Remove the legacy proof bypass

The prior audit found that `static/js/app.js` around the dispatch UI still calls `/api/dispatches/<id>/advance` and presents a “Confirm Delivery” action. The legacy `app.py` `advance_dispatch` route can jump from En Route to Delivered without a proof/review workflow and uses a display-name string for Driver ownership.

- Re-open the current frontend and route code to confirm the issue.
- Make all frontend dispatch actions use one canonical lifecycle.
- The old endpoint may remain only as a safe compatibility adapter; it must reject or redirect attempts to mark a dispatch Delivered without proof, verified review and reconciliation.
- Never retain a hidden legacy route that bypasses new safeguards.
- Driver ownership must use canonical `driver_user_id` and the session user ID, not display-name string equality.
- Keep old response shapes only when safe and compatible. If an old action conflicts with the new safety rules, migrate the frontend and tests with a documented deprecation rather than preserving an unsafe behavior.

## 6.2 Canonical dispatch state machine

Implement a centralized, tested transition map. Suggested normal path:

`Planned → Stock Reserved → Picking → Loading → Ready → En Route → Arrived → Proof Submitted / Pending Review → Delivered`

Suggested exception states, adapted to the existing schema:

- `Allocation Blocked`
- `Route Blocked`
- `Delivery Exception`
- `Recipient Unavailable`
- `Partially Delivered`
- `Proof Rejected`
- `Return Pending`
- `Returned to Warehouse`
- `Cancelled`

Use the project's existing exact spellings where necessary to preserve compatibility, but do not create multiple aliases with ambiguous behavior. Document every transition and the actors permitted to execute it.

Require appropriate prerequisites:
- `Ready → En Route`: required stock has been issued/loaded and an eligible Driver/available vehicle are assigned.
- `En Route → Arrived`: only the assigned Driver or authorized exception handler.
- `Arrived → Proof Submitted`: valid quantities and a permitted proof/reference are submitted.
- `Proof Submitted → Delivered`: only an authorized verifier accepts proof and quantity/stock reconciliation succeeds.
- `Proof Rejected`: does not mean the delivery is complete; route to review/exception/return reconciliation.
- Vehicle returns to Available only after legitimate dispatch closure/return checks.

Reject illegal transitions with HTTP `409` (or the consistent API conflict response). Never set multiple linked status fields blindly to a success value just because a handler ran.

## 6.3 Correct the rejected-proof bug

The prior audit executed `review_delivery_service` and observed:

- reservation `RSV-019` remained Active;
- stock moved from `(on_hand, reserved) = (4820, 0)` to `(4820, 2)` as the reservation was made;
- after rejecting proof, request status incorrectly became `Delivered`;
- reservation stayed Active;
- proof status was `Rejected`;
- vehicle was set to `Available`.

Reproduce this with a disposable database, add a failing regression test first where practical, then fix it.

Required outcomes:

1. Rejected or Needs Review proof must never mark the emergency request Delivered or set `delivery_confirmed_at`.
2. A rejected proof should leave a visible unresolved delivery exception and record the reviewer/reason. The request remains in the correct unresolved or partial status.
3. Do not mark a vehicle Available merely because proof was rejected. It must follow dispatch/return/inspection rules. If it has not physically returned, it remains unavailable/in-trip; if it returned, record that separate confirmed return state.
4. Do not blindly release reserved/issued stock on proof rejection: physical goods may have left the warehouse. Reconcile based on the dispatch manifest and confirmed delivered/returned/damaged quantities. Unissued reservations may be released; issued quantities must remain accounted for until return, delivery or an authorized adjustment is recorded.
5. Successful verified full delivery must atomically update proof status, dispatch status, request status, dispatch item quantities, reservations, ledger and vehicle/trip status as dictated by the documented lifecycle.
6. Partial delivery remains explicitly partial; do not label the entire request Delivered when required quantities remain outstanding.
7. A retry of the same proof review must not duplicate transactions or change a rejected proof to accepted without a new authorized review record.
8. Record request/dispatch/audit events in the same transaction as the successful status change when practical.

Never falsify physical stock changes simply to force the UI to show a clean status. If physical stock disposition is unknown, keep it in a clear reconciliation-pending state.

## 6.4 Delivery proof payload and UI must match

The prior audit found the form sent fields like `recipient_name`, `phone`, `received_quantity` and a fixed fake image data URI, while the API expected different keys such as `proof_type`, `proof_reference`, `notes` and `items`. The UI then displayed a success toast even if the server had not verified the proof.

Fix both sides together.

Define and document one payload shape, for example:

```json
{
  "proof_type": "RecipientConfirmation",
  "proof_reference": null,
  "recipient_confirmation": "received",
  "notes": "Delivered at the approved relief point",
  "items": [
    {
      "dispatch_item_id": 12,
      "quantity_delivered": 8,
      "quantity_returned": 2,
      "quantity_damaged": 0
    }
  ]
}
```

Treat this as an example and adapt field names to the existing schema consistently. Validate all fields on the backend. If no actual upload subsystem exists, provide a safe proof reference/notes flow or implement validated uploads; never send or trust a made-up image data URI. Do not collect recipient phone numbers unless the workflow needs them and storage/access/privacy has been designed.

Frontend success behavior:
- after submission, say `Proof submitted for review` if that is the actual server status;
- say `Delivery verified` only if the API returns verified completion;
- display validation/conflict/permission errors honestly;
- refresh the dispatch, request, stock and timeline from server state after successful mutation.

## 6.5 Route blockage, reroute and trip return

The route-blockage UI previously used keys such as `blockage_location` and `suggested_detour`, but backend code read `reason`, `notes`, `lat`, `lng`.

- Pick a canonical API schema, for example `reason`, `notes`, optional `lat/lng`, optional `blockage_location`, and `suggested_detour`.
- Persist the reported location and detour rather than silently discarding inputs.
- Validate coordinates and text lengths.
- Restrict report/reroute actions to the assigned Driver or authorized incident coordinator.
- Allow blockage only in legal states; do not mark a delivered/cancelled trip as blocked.
- Require authorized review/decision before changing the assigned route/destination/vehicle.
- Record who chose the reroute and why. A map route preview must not be represented as proof that a road is passable.
- Reconcile vehicle return and remaining cargo when the trip ends.

# 7. PRIORITY P0/P1 — ESTABLISH ONE INVENTORY SOURCE OF TRUTH

The legacy inventory route/table and newer `warehouse_stock`/reservation/ledger structure must never drift apart.

## 7.1 Canonical stock model

Inspect migrations and service code and define exactly one canonical source for stock.

Recommended model if supported by current migrations:
- `resources` identifies the resource type/SKU/unit;
- `warehouses` identifies physical storage locations;
- `warehouse_stock` holds on-hand and reserved quantities per warehouse/resource;
- `inventory_reservations` and `inventory_reservation_items` hold allocations before issue;
- `inventory_transactions` records all physical/memo stock movements with actor, time, reference and idempotency key.

The legacy `/api/inventory` endpoints may remain as compatibility adapters that serialize/update the canonical source through safe service functions. They must not maintain an independent balance that can diverge.

Do not introduce two writable stock totals. If a migration must preserve old inventory rows, migrate them transactionally and preserve every row/quantity. Make the transformation repeatable and documented.

## 7.2 Quantity semantics

Document and enforce these distinct values:
- physical on-hand stock;
- actively reserved quantity;
- available-to-allocate = on-hand minus active reservations, or an equivalent rigorously defined rule;
- issued/handed-over quantity;
- delivered quantity;
- returned quantity;
- damaged/unusable quantity.

Do not subtract the same quantity twice. Decide when stock moves from on-hand to issued and represent the change with ledger transactions. A reservation itself must not pretend goods have physically left the warehouse.

## 7.3 Allocation/reservation

- Normal allocation requires verified request and real mapped resource items.
- Validate requested quantities, stock, warehouse status, zone/incident scope and capacity.
- Reserve quantities transactionally.
- Prevent simultaneous allocations from oversubscribing stock. Use appropriate SQLite transaction/conditional-update strategy and uniqueness/idempotency guards.
- A duplicate allocation request must either return the existing allocation idempotently or return a clear `409`; it must never create another dispatch or deduct stock twice.
- If there is insufficient stock, return a structured error with item, requested quantity and available quantity; leave request/stock/dispatch/vehicle unchanged except for an explicit shortage event.
- Do not invent a resource mapping from ambiguous free text. If `need` cannot map to a known resource, ask an authorized operator to map it.
- Do not select a vehicle in maintenance/unavailable status or fabricate `V-12 · Relief Van` text when no actual vehicle record exists. If no eligible vehicle/Driver exists, leave allocation pending or blocked with a reason.
- Require an explicit, audited Government Official override for any exceptional unverified allocation; normal allocation cannot silently use `emergency_override=True`.

## 7.4 Stock issue, return and rejected/partial delivery

- At warehouse handover/loading, issue only the actual loaded quantity and link it to the dispatch/reservation.
- At delivery review, reconcile loaded = delivered + returned + damaged + still-unresolved quantity (adapt for legitimate transfer/wastage rules and document them).
- Only physically inspected returns become allocatable stock again.
- Do not automatically make issued goods available just because a delivery proof is rejected.
- For cancelled dispatch before issue, release unused reservation transactionally.
- For cancelled dispatch after partial/complete issue, require a return/adjustment record; do not simply decrement `reserved` and hope the on-hand figure is right.
- Provide an audited compensating transaction instead of editing/deleting a prior stock movement.

## 7.5 Fix the stock ledger UI/API

The audited frontend contains a stock ledger tab that calls a missing endpoint. Implement `GET /api/inventory/ledger` (or update the UI to a documented equivalent and keep backward compatibility as appropriate).

Support safe filters such as `warehouse_id`, `resource_id`, `transaction_type`, `reference_id`, `from`, `to`, `page`, and `per_page`. The endpoint must be authenticated, scoped and must not leak private/different-organization data.

Return a documented structure including the transaction ID, resource, warehouse, transaction type, quantity/direction, reference, reason, actor display where permitted and timestamp. Test the endpoint and the UI connection.

# 8. FIX ALLOCATION, VEHICLE AND DRIVER SELECTION

The prior audit found the allocation path may bypass verification and can choose an unavailable vehicle or invent a display string when no actual vehicle row is suitable.

- Inspect the latest `allocate_request_service` and any helper that chooses a vehicle/Driver.
- Select a real active/available vehicle record matching required capabilities/capacity.
- Select a real eligible active Driver account; store `driver_user_id` and `vehicle_id` as canonical foreign keys.
- Keep legacy text `driver` and `vehicle` fields only as derived display/compatibility fields if needed. Do not authorize based on these strings.
- Do not auto-assign a Driver who is inactive, suspended, unapproved or already engaged in an incompatible active trip.
- Do not reserve a vehicle unless the assignment transaction succeeds.
- If no candidate is available, return a documented `409`/pending-allocation state and let an authorized coordinator resolve it.
- Check capacity and compatibility before creating the dispatch, not after.
- Ensure all related actions (reservation, dispatch, resource/vehicle assignment, request status, audit/event) either commit together or roll back together.
- Add tests for no vehicle, no Driver, unavailable vehicle, busy Driver, wrong capability, insufficient capacity, duplicate allocation, wrong role and unverified request.

# 9. FINANCE — REMOVE HARDCODED TOTALS AND FIX ACTION AUTHORIZATION

## 9.1 Remove fixed financial totals

The previous `GET /api/funds` handler returned example totals such as `₹42.6L`, `₹28.1L`, and `₹14.5L` as hardcoded values.

- Locate every hardcoded financial total, percentage, approved amount, utilization figure and balance in backend and frontend.
- Use `fund_budgets`, `fund_requests`, `fund_transactions` and cash-donation records as the documented source of truth.
- Distinguish requested, approved, committed, paid, refunded, reconciled and remaining amounts.
- Use integer paise or another exact representation. Do not use float arithmetic for money.
- If there are no transactions, display zero/empty values correctly; avoid division by zero. Preserve the legacy response shape if the existing UI depends on it, but populate it from data.
- A seeded sample transaction may be shown only as clearly labelled fictional demo data.

## 9.2 Secure every finance action at both route and service layers

The audit found the `fund_request_action` route and service did not enforce equivalent role permissions for `approve`, `commit`, `pay` and `reconcile`.

Create a central action permission matrix and validate it in the route **and** service. Never rely solely on the front-end controls or a route decorator if services can be called through another route/test path.

At minimum:
- authorized NGO/agency users can submit requests for their own organization;
- an authorized Official/finance role can review/approve within configured scope and thresholds;
- commitment/payment/reconciliation are separate actions and each has its own permission/state precondition;
- do not allow the requester to approve their own request where dual control is required by the configured demo policy;
- Citizen, Volunteer and Driver cannot approve/pay/reconcile organization funds;
- Administrator has no automatic financial approval privilege; any explicit override must be narrowly defined and audited;
- reject duplicate payments using a unique transaction/reference/idempotency guard;
- only allow payment from an approved/committed request within its permitted amount/budget;
- partial payment must persist the actual paid amount and outstanding balance correctly;
- refund/reversal must create a compensating transaction, not erase a historical payment.

## 9.3 Do not skip workflow states

Fix cases where:
- a new budget is created already `Approved` instead of awaiting review;
- a new public advisory is created already `Published` and the creator is assigned as approver;
- a new inter-agency request is created already `Mobilized`.

New records start at `Draft` or `Submitted` according to the intended process. Separate approval, publication, mobilization and completion actions are required, with authorized actor, time and reason.

# 10. VOLUNTEER TASKS — FIX AUTHORIZATION AND FORM CONTRACT

## 10.1 Server-side authorization

The prior audit found task progress could be updated by a random authenticated user and task approval was not sufficiently restricted.

- A Volunteer can accept/decline, check in, report progress and submit only a task assigned to their own Volunteer profile/user relationship.
- An NGO Coordinator can assign/manage tasks only within their verified organization and approved zone/incident scope.
- A Government Official can oversee tasks only within authorized incident scope.
- Supervisor approval requires the task to be `Submitted for Review`; reject approve-before-submit, double-approve and terminal-task mutation.
- Do not trust a submitted `volunteer_id`, `organization_id`, `assigned_by_user_id` or role. Derive actor fields from the session and validate assignment targets.
- Status of the Volunteer roster and status of a specific task are different concepts. Do not mark the Volunteer Available while another active assignment prevents that.

## 10.2 Fix the volunteer task modal payload

The prior form sent fields like `title`, `zone_id`, `skill`, `target_quantity`, `unit`, and `description`, but the server required `volunteer_id` and `task_type`. This can cause task creation failure.

- Inspect actual frontend modal, API handler, validation schema and service.
- Build a real select field for an eligible Volunteer; if the task is skill-targeted, match skills and show eligible options. Do not send a skill string as a substitute for `volunteer_id`.
- Use one canonical payload, e.g. `title`, `task_type`, `description`, `volunteer_id`, optional `incident_id`, `zone_id`, `request_id`, `dispatch_id`, `quantity_expected`, `shift_start`, `shift_end`, safety instructions.
- Validate the Volunteer belongs to the correct organization/allowed scope and is eligible/available for the requested shift.
- Handle no eligible Volunteer as a visible, non-destructive validation error.
- Display the actual backend task ID/status and refresh the appropriate list.
- Add an HTTP-level test using the exact payload the frontend sends, not only a direct service unit test.

## 10.3 Quantity reconciliation

For distribution tasks, record received/distributed/damaged/remaining or returned quantities. Enforce a clearly documented equation, such as `received = completed/distributed + damaged + remaining/returned`, with deliberate handling of transfers/wastage. If the quantity does not reconcile, require an explanation and review rather than marking the task complete.

# 11. DONATIONS — FIX ITEM MAPPING AND ACCEPTANCE

The prior audit found the in-kind donation form sends `resource_name` and `quantity_declared` without canonical `resource_id`; the service may skip invalid items while still creating the donation header.

## Required behavior

- Donation creation validates the header and every line item before inserting any records.
- For in-kind donations, each item must resolve to an existing active resource (prefer `resource_id`; support name lookup only if unambiguous and safely resolved server-side).
- Do not silently skip malformed items or create an empty donation header and show success.
- If any required item is invalid, return validation errors and roll back the whole create transaction unless the UI explicitly supports a documented draft with incomplete items.
- Store declared quantity, actual received quantity, accepted quantity, rejected quantity, variance and reason separately.
- On receipt, record physical receiving, who received it and when.
- On verification, ensure `quantity_accepted + quantity_rejected <= quantity_received` and ensure received quantities were not exceeded by the accepted values.
- Only an authorized verifier may accept/reject a receipt; the donor/NGO must not self-approve a disputed receipt under the demo policy.
- Accepted in-kind quantities become warehouse stock exactly once through a transaction and ledger entry. Cash donations must never create physical stock.
- Repeat verify/accept requests must be idempotent and must not duplicate stock or cash ledger entries.
- Provide visible discrepancy review when declared quantity differs from actual received.

## Frontend/API contract

Update both form and API. The canonical in-kind item payload should use `resource_id` and `quantity_declared`, or a documented equivalent. Populate the resource selector from `GET /api/resources`. Do not submit arbitrary names that the backend ignores.

Add tests for: a valid multi-item donation; invalid/missing resource; zero/negative quantity; partial receipt; discrepancy; accepted quantity; rejection; repeat acceptance; cash donation; unauthenticated access; wrong organization; and only accepted physical units entering stock.

# 12. SHELTER ADMISSIONS AND TRANSFERS — STOP OCCUPANCY CORRUPTION

The prior audit found a partial-transfer defect: transfer of fewer people than the group's size could move the full admission row to another shelter but decrement source occupancy only by the transferred count. It also used `max(0, old_occupants - count)`, masking inconsistent data. Legacy shelter updates could directly overwrite `occupants` without ledger history.

Implement one of these models and document it clearly:

**Preferred simple model:** A single admission group must transfer as a whole. Reject a transfer unless `people_count` equals the current admission group's active count. If a family/group must split, create distinct admission/household subrecords with separate quantities and an explicit split operation.

Rules:
- Verify the requested transfer count is positive and not greater than the active admission count.
- Verify the source shelter has sufficient derived occupancy; do not clamp inconsistencies to zero.
- Validate destination readiness and capacity before mutation.
- In one transaction, update admission/transfer records and both source/destination occupancy representations (or derive the occupancies from admissions if that becomes the canonical model).
- Never count the same individuals as active at both shelters simultaneously.
- A transfer must have an explicit lifecycle: Requested -> Approved -> InTransit -> Completed or Cancelled; define what counts as current occupancy at each state.
- `Cancelled` transfers must reverse/rescind provisional reservations correctly without corrupting the admission.
- Direct `PUT/PATCH /api/shelters/<id>` must not allow arbitrary `occupants` writes. Occupancy changes come from admissions/transfers or a narrowly permissioned, reason-required audit reconciliation action.
- Migrate/backfill existing shelter occupancy safely; preserve existing demo counts.

Tests must include full-group transfer success, invalid partial transfer, insufficient source occupancy, full destination, destination unavailable, cancelled transfer, retry/idempotency and concurrent/boundary admissions.

# 13. FIX FRONTEND/API CONTRACT MISMATCHES EVERYWHERE

For each action in the UI, trace the complete chain:

`HTML/Jinja form → JS payload → route → schema validation → service → DB transaction → response → UI state refresh`.

Do not patch only one side. Define canonical JSON schemas and document them. Use one consistent response/error contract while preserving compatibility where practical.

## Known forms to fix

1. **Volunteer task creation:** ensure `volunteer_id` and `task_type` are present and valid; don't send a `skill` label in place of a chosen Volunteer ID.
2. **In-kind donation:** send valid resource IDs and line-item quantities; no header-only “success” when item validation failed.
3. **Delivery proof:** send the fields the backend actually validates, persist submitted quantities and show `Pending Review` versus `Verified` accurately. Remove fixed fake image data URIs.
4. **Route blockage:** persist location/reason/notes/coordinates/suggested detour through a consistent request schema.
5. **Inventory ledger:** implement the UI's endpoint or change UI to the existing documented endpoint. Do not leave a tab that always 404s.
6. Review every other form, modal, dashboard action and button to identify endpoint names, HTTP methods, payload keys and expected status behavior.

For each form, add at least one test of the actual Flask test client request or equivalent HTTP contract. A service-only test does not prove that the frontend/API is wired correctly.

# 14. COMPLETE MISSING API LIFECYCLES OR DOCUMENT EQUIVALENT ROUTES

Inspect the current endpoints. Implement the following capabilities, using equivalent route names only if they already exist and are secure, documented and connected to the UI.

## Requests
- request detail with ownership/scope;
- request timeline;
- request more information;
- explicit reject with reason;
- mark duplicate with primary reference and cycle prevention;
- escalate;
- closure with reason and state preconditions;
- request line-item CRUD under permission/state rules;
- Citizen confirmation and issue reporting with ownership checks.

## Resources / warehouses / stock
- resource list/create/update;
- warehouse list/create/update;
- per-warehouse stock listing;
- receipt/adjustment workflow;
- stock reservation create/release/issue;
- ledger listing and transaction reversal/compensating movement;
- filters and pagination where suitable.

## Donations
- list/detail;
- mark in transit where relevant;
- physical receipt;
- multi-item verification/acceptance;
- timeline.

## Volunteers
- profile update with scope check;
- task list/create/detail;
- accept/decline;
- check-in/progress/submit;
- supervisor approve/needs-correction;
- field report submit/review.

## Fleet / dispatch
- vehicle list/detail/create/update/readiness/maintenance;
- eligible vehicle/Driver selection;
- dispatch detail/list with ownership/scope;
- readiness/departure/arrival/blockage/reroute;
- proof submit/review/reject;
- return and cargo reconciliation.

## Shelters
- shelter list/detail/update without arbitrary occupancy edits;
- referral/admission/exit;
- transfer request/review/complete/cancel;
- occupancy report and capacity warnings.

## Finance
- budgets and requests;
- explicit approve/reject/commit/pay/refund/reconcile actions;
- transaction list/detail;
- ledger-derived summary.

## Inter-agency/public advisories
- request creation;
- acknowledge/accept/reject/mobilize/complete actions;
- advisory draft/review/approve/publish/expire/withdraw actions;
- actor, timestamp, reason and incident scope on transitions.

Do not create a second duplicate endpoint merely because the name here differs. Provide a mapping table in API documentation showing the final canonical route and how it relates to any legacy route.

# 15. API DESIGN AND VALIDATION EXPECTATIONS

Keep existing public contracts compatible where safe and update the frontend and tests together when a shape must change.

For new routes, use a consistent JSON error structure where possible, e.g.:

```json
{
  "error": {
    "code": "INSUFFICIENT_STOCK",
    "message": "Not enough stock in the selected warehouse.",
    "details": {"resource_id": 1, "requested": 10, "available": 6},
    "request_id": "correlation-id"
  }
}
```

Expected status code behavior:
- `200`: successful read/update;
- `201`: new record created;
- `204`: successful no-content operation where appropriate;
- `400`/`422`: malformed/semantically invalid fields, following existing API convention;
- `401`: not authenticated;
- `403`: authenticated but forbidden;
- `404`: record does not exist or is not visible to caller according to policy;
- `409`: illegal state transition, stock conflict, duplicate action or concurrent update conflict;
- `500`: unexpected server error with generic client message and detailed server-side logging.

Never trust client-provided actor fields (`user_id`, `role`, `approved_by`, `created_by`, `driver_id`, `volunteer_id` when the caller isn't authorized to choose the target). Derive current actor from session. Accept a target user only when the caller is authorized to assign that exact eligible user.

For list routes, add suitable filters (`status`, incident, zone, organization, date range, search) and bounded pagination where it is useful. Validate page size. Avoid unbounded global reads.

Use parameterized SQL only. Validate IDs, status enums, text lengths, quantities, amounts, dates and coordinates. Reject NaN/infinity and boolean values masquerading as numeric quantities. Do not leak SQL tracebacks to clients.

# 16. DATABASE MIGRATION AND DATA CONSISTENCY

Do not rebuild/reset the database casually.

- Maintain ordered, idempotent schema migrations.
- Keep `PRAGMA foreign_keys=ON` for every SQLite connection.
- Preserve existing `users`, requests, inventory, volunteers, dispatches, shelters, funds, activities and events rows.
- Use a backup/snapshot before migration in the dev workflow.
- Test migrations against both a clean database and a copy of the legacy schema.
- If an existing SQLite table must be rebuilt, copy data within a safe migration, validate counts and relationships, then switch only after validation.
- Use constraints and foreign keys; add indexes on frequent foreign keys and scope filters.
- Use transactions for multi-row workflows and verify rollback under an injected failure.
- Use idempotency keys/unique constraints for allocations, stock movements, proof reviews where needed, donation acceptance and payment posting.
- Do not physically delete historical financial, stock, delivery or audit records as a correction; use explicit compensating records.
- Ensure seed data is fictional, repeatable, and never resets a user's database or user-created records on every startup.
- After migrations/seeding, run `PRAGMA foreign_key_check` and investigate all results.

# 17. REQUIRED REGRESSION TEST MATRIX

Create tests for the actual bug patterns below. Use a temporary test database with deterministic fixtures. Include both service-level tests and Flask test-client/HTTP tests.

## Authentication and privacy
1. Anonymous `GET /api/requests` denied or receives explicitly minimal public projection.
2. Anonymous `GET /api/dispatches` denied or receives minimal safe projection.
3. Anonymous donation/finance/fleet/admission/field-report reads denied.
4. Anonymous event poll/SSE denied.
5. Citizen cannot read another Citizen's request, timeline, items or proof.
6. Citizen cannot confirm delivery or report issue on another Citizen's request.
7. Driver A cannot read/change Driver B's dispatch.
8. Volunteer A cannot modify Volunteer B's task or checkpoint.
9. NGO A cannot access NGO B's donation, stock or task records.
10. User without incident scope cannot perform incident-specific mutation.
11. Citizen cannot export other users' requests/private data via any dataset alias.
12. Administrator is rejected from actions not explicitly allowed by the operation matrix.
13. Suspended user cannot login and an existing session is no longer accepted.
14. Missing/incorrect CSRF token fails for protected browser mutation; correct token succeeds.

## Requests / allocation
15. Citizen creation binds requester to session identity, ignoring forged owner ID.
16. Unverified request allocation is rejected by default.
17. Properly authorized, reasoned exceptional override works only if implemented and creates audit record.
18. Duplicate submission/allocation does not create a second dispatch/reservation or deduct stock twice.
19. Invalid request transitions return conflict and leave data unchanged.
20. Duplicate linking prevents self-reference/cycles and preserves history.

## Dispatch/proof lifecycle
21. Legacy advance endpoint cannot mark Delivered without verified proof/reconciliation.
22. Assigned Driver can perform allowed trip actions; another Driver cannot.
23. Illegal dispatch state changes are rejected.
24. Rejected proof does not mark request Delivered.
25. Needs-review proof does not mark request Delivered.
26. Rejected proof does not make vehicle available prematurely.
27. Rejected proof does not silently release issued stock; unresolved quantities remain visible.
28. Full accepted proof plus reconciliation transitions request/dispatch correctly.
29. Partial delivery remains partial and leaves outstanding quantities.
30. Retry of proof verification/rejection does not duplicate stock movements.
31. Route blockage input fields are persisted; invalid coordinates fail validation.
32. Reroute requires authorized actor and valid dispatch state.
33. Vehicle return and returned-goods receipt are recorded before vehicle/stock is released.

## Inventory/donations
34. Stock cannot go negative.
35. Active reservation reduces available-to-allocate exactly once.
36. Concurrent/conflicting reservations cannot oversubscribe stock.
37. Reservation release affects only unissued quantity.
38. Warehouse issue decreases on-hand according to the documented rule and creates a ledger record.
39. Returned items become available only after explicit receipt/inspection.
40. Damaged quantity is recorded and cannot be allocated as usable stock.
41. Legacy inventory endpoint and canonical warehouse stock never diverge.
42. Ledger endpoint exists and frontend request succeeds.
43. Invalid in-kind donation item rolls back rather than creating an empty successful header.
44. Only accepted donation item quantity adds stock, exactly once.
45. Declared-vs-received discrepancy is preserved and reviewable.
46. Cash donation never adds physical inventory.

## Volunteer tasks
47. Task creation API works with exact frontend payload.
48. Task cannot be assigned to unverified/inactive/unavailable Volunteer or wrong organization.
49. Volunteer cannot accept/update an unassigned task.
50. Task approval is only possible from Submitted for Review.
51. Task quantity mismatch requires explanation and cannot silently complete.
52. Completion state and Volunteer availability stay consistent with other active tasks.

## Finance
53. No hardcoded fund totals are returned when database ledger changes.
54. Unauthorized user cannot approve, commit, pay, refund or reconcile.
55. Requester cannot approve own request where dual control is required.
56. Repeated payment post is idempotent/rejected and does not double count.
57. Partial payments/budget remaining are calculated correctly.
58. Advisory and inter-agency request do not skip review/approval states.

## Shelters
59. Admission capacity cannot exceed the policy limit without a documented authorized exception.
60. Partial group transfer is rejected unless the data model explicitly splits admissions.
61. Source occupancy mismatch fails rather than being clamped to zero.
62. Transfer updates source and destination consistently in one transaction.
63. Cancelled transfer leaves admission/occupancy consistent.
64. Direct shelter update cannot arbitrarily set occupant count.

## Migrations and overall integration
65. Fresh database migration succeeds.
66. Legacy database migration preserves existing row counts/data that should be preserved.
67. Migration rerun is safe and idempotent.
68. Seed rerun does not duplicate or reset records.
69. `PRAGMA foreign_key_check` is clean after migrations, seed and workflow tests.
70. Injected failure in a multi-record allocation/receipt/payment flow rolls back partial changes.
71. Each frontend-called API route exists and returns a response shape the UI expects.
72. Full end-to-end scenario works for successful delivery, partial delivery, rejected proof, insufficient stock and blocked route.

You may add more tests. Do not remove these categories to reduce the number of failures.

# 18. EXECUTION COMMANDS AND ENVIRONMENT LIMITATIONS

Use the project's own `requirements.txt`, run scripts and README to determine the appropriate commands. Common checks may include:

```bash
python -m py_compile app.py api_routes.py database.py migrations.py services.py seed_demo.py
node --check static/js/app.js
node --check static/js/icons.js
python -m pytest -q
```

Run the full application and HTTP tests when dependencies are available. If dependencies are missing:

1. attempt installation using the repository's declared requirements in the current environment;
2. if package access fails, capture the exact error;
3. do not substitute a fake `werkzeug`/Flask shim and call it a full application pass;
4. still run all safe syntax/database/service checks that truly work;
5. explain which authentication/HTTP/integration guarantees remain unverified;
6. leave clear local instructions for rerunning the blocked tests.

Do not claim the previous `68 passed` line in pytest cache/README as proof. Only report test results generated by the current run. Do not mark an unexecuted test as passing.

# 19. REQUIRED MANUAL SMOKE TEST AND DEMO

After repairs, demonstrate one coherent fictional flood scenario in the actual running app:

1. Government Official creates and activates a fictional incident and zone.
2. NGO Coordinator belonging to a verified organization requests coverage; Official approves it.
3. Citizen submits a request; requester ownership and priority are recorded.
4. Authorized responder verifies the request.
5. Coordinator tries allocation with insufficient stock; app reports shortage without half-created dispatch or stock corruption.
6. Add/verify a donation in the warehouse; only accepted quantity increases canonical stock.
7. Allocate the request; stock is reserved exactly once, and a real eligible Vehicle/Driver is assigned.
8. Warehouse records picking/loading and issues the actual loaded quantity.
9. Driver starts journey and reports a test route blockage; Coordinator handles it and history is recorded.
10. Driver arrives and submits delivery proof with actual item quantities.
11. Test proof rejection: request must not be Delivered, vehicle must not prematurely become Available and stock must remain accounted for.
12. Submit a new/corrected proof through a documented process and approve full or partial delivery.
13. Reconcile delivered, returned and damaged quantities; close the trip only when conditions allow.
14. Volunteer accepts/executes a linked task where required and submits quantities for supervisor review.
15. Confirm that Citizen sees only their own safe timeline.
16. Verify shelter admission/transfer if the scenario uses shelter support.
17. Verify fund totals change only through authorized ledger transactions.
18. Verify the Government Official dashboard and incident report reflect the same real database records.
19. Verify Admin audit trail shows who did what and when.
20. Test wrong-role, anonymous and cross-record requests throughout the scenario.

Use clearly fictional seeded accounts/records. Confirm test credentials from the code and label them development-only. Do not claim the app is integrated with real government agencies or live disaster services.

# 20. DOCUMENTATION CHANGES

Update `README.md`, `SETUP-GUIDE.md`, and preferably `docs/API.md` with:

- actual setup/run steps;
- migration and backup instructions;
- canonical data model and legacy compatibility decisions;
- role-by-role permissions;
- valid state-transition tables;
- API paths, methods, roles, request payloads, responses and error codes;
- how stock reservation/issue/return works;
- delivery proof and rejection/partial-delivery process;
- financial approval/payment/reconciliation model;
- test commands and actual latest results;
- demo-only features and external integrations not implemented;
- remaining issues and limitations.

Never document a route as available unless it exists and is verified. Remove stale claims that contradict behavior.

# 21. WORKING METHOD AND HANDOFF

Follow this sequence while remaining in the existing project:

**Phase A — Re-audit:** Check the current code and update `IMPLEMENTATION_PROGRESS.md`. Mark each finding already fixed, still open, or unverified.

**Phase B — P0 security:** Fix endpoint authentication, record-level permissions, Administrator bypass, suspended-session behavior, event privacy, exports and CSRF.

**Phase C — P0 delivery:** Make one safe dispatch state machine; remove legacy bypass; fix proof review; ownership and quantity reconciliation; vehicle state and reservation handling.

**Phase D — Canonical stock:** Fix reservation/issue/return ledger semantics, one source of truth, legacy API adapters and stock ledger endpoint.

**Phase E — Other high-priority workflows:** Fix allocation candidate selection, NGO membership, volunteer tasks, donation item handling, finance authorization/totals and shelter transfers.

**Phase F — API/UI integration:** Fix payload mismatches, error handling, state refresh and false success toasts; review every visible workflow action.

**Phase G — Regression verification:** Run relevant tests as fixes are made, then the whole suite; inspect schema/seed integrity and run the scenario.

**Phase H — Handoff:** Update docs, progress report and final deliverables.

Do not stop at P0 security and then announce that the entire master prompt is complete. Continue through every phase within practical limits. If a task cannot be completed, mark it `BLOCKED` or `DEFERRED`, state why, and name the precise files/steps left.

Before editing, preserve the latest source. Do not overwrite the real database. Do not delete tests or weaken authorization to make a test pass. Fix the code, not the assertion, unless documented intended behavior has deliberately changed.

At the end, deliver:
1. the corrected source directory or a new ZIP;
2. exact list of modified/new files;
3. a finding-by-finding before/after matrix;
4. actual commands run and pass/fail/blocked output summary;
5. API routes added/fixed and any route mapping;
6. the end-to-end scenario results;
7. known remaining limitations;
8. exact steps to run locally on Windows.

## FINAL COMMAND

Start now by inspecting the latest uploaded DRRAS-Flask repository and the existing master prompt/audit report. **Fix the currently outstanding verified defects first, implement the missing contracts, run the tests that are actually executable, and deliver the modified project. Do not return only a plan and do not claim success without evidence.**
