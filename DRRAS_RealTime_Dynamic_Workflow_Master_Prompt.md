# DRRAS — REAL-TIME, DATABASE-DRIVEN, ROLE-BY-ROLE WORKFLOW IMPLEMENTATION PROMPT
## For the existing Antigravity workspace — preserve the project and make the whole demo genuinely functional

---

# 0. THE MOST IMPORTANT REQUIREMENT — READ THIS FIRST

You are working on my **existing DRRAS-Flask project**, which is already open in the current Antigravity workspace.

My goal is to submit and demonstrate this college project. My teacher will mainly evaluate the **workflows, connected functionality, realistic behavior, and whether actions actually work**. Do not spend time on an unrelated security overhaul, a complete redesign, or rebuilding the application from scratch.

**The application must be genuinely database-driven and update in real time. ALL operational values, dashboard counts, request statuses, inventory quantities, donation quantities, volunteer statuses, dispatch statuses, shelter occupancy, finance totals, timelines, and reports must come from the current database/API state. Do not leave fake/static values pretending to be live data.**

**Preserve all existing features, pages, roles, UI style, and useful code. Do not delete features just because they are incomplete. Repair and connect them. You may add missing APIs, database tables/columns, workflow states, UI actions, and small supporting features when needed to make an existing workflow complete.**

Do not only provide a plan. Inspect, implement, run, test, fix, and document the real project files.

---

# 1. EXISTING PROJECT AND SCOPE

Project: **DRRAS — Disaster Relief Resource Allocation System**

Existing architecture should remain:
- Python + Flask backend
- SQLite database
- Jinja2 templates
- HTML/CSS
- Vanilla JavaScript
- Existing routes, services, database/migration logic, tests, and launch scripts

The project has six roles:
1. Administrator
2. Government Official
3. NGO Coordinator
4. Citizen
5. Volunteer
6. Driver

The project already has functionality related to:
- Authentication and role-specific dashboards
- Emergency request creation and priority scoring
- Incident and zone management
- Request verification
- NGO zone adoption and donations
- Inventory/warehouse management
- Resource allocation
- Volunteer tasks and field reports
- Vehicles, dispatch and delivery proof
- Shelters and occupancy
- Funds and donations
- Notifications/events/activity
- Audit history and CSV reports

These are the expected areas to inspect, not permission to assume every feature is complete. Verify the current code before changing it.

## Source of truth
The currently open project is the source of truth. Inspect its actual files and database schema. Do not overwrite it with an older ZIP or recreate it from scratch. Preserve existing user data and working functionality.

If the prior audit or prompt files are accessible in the workspace, read them. If they are not accessible, continue from this specification and the actual code; do not claim to have read inaccessible files.

---

# 2. ABSOLUTE RULES: NO FAKE LIVE DATA, NO STATIC BUSINESS VALUES

This section is mandatory and takes precedence over cosmetic implementation.

## 2.1 What must NOT be hardcoded as live operational data

Do not hardcode any of the following in frontend JavaScript, HTML templates, Flask response dictionaries, or dashboard fallback objects:
- Number of active incidents
- Number of open/verified/unverified/critical requests
- Request priority values
- Request status
- Number of pending NGO approvals
- Donation totals or quantities
- Warehouse stock and available stock
- Reserved/issued/returned/damaged stock
- Volunteer counts, availability, task status, or task completion
- Vehicle availability, assigned driver, dispatch status, ETA or delivery result
- Shelter capacity, occupants, occupancy percentage, available beds
- Fund allocation, approved amount, commitments, payments, utilization, remaining balance
- Notifications, audit events, task history, request timeline
- Delivery quantities or proof state
- Any number that is meant to reflect current project activity

Do not use values such as `42.6L`, `28.1L`, sample counts, fixed arrays, or fallback numbers as if they represent the current database. A demo seed record may contain example data, but dashboards must calculate from those persisted records.

## 2.2 What may remain static

Static content is allowed for:
- Labels, icons, headings, descriptions and help text
- Resource category names and role names, if they are configuration/master data
- Status labels and explanatory copy
- Fixed business rules/configuration, provided the rules are explicitly configured and not presented as live operational measurements
- Clearly labelled demo seed data stored in the database

If demo seed data is used, it must be inserted into the database by an explicit, repeatable seed process. The UI must fetch and calculate from those records. Never fabricate a live number just because the database is empty.

## 2.3 Empty state, not fake fallback

If the database has no data:
- Show `0` for genuine count queries.
- Show an appropriate empty state such as “No donations recorded yet”.
- Show `Not configured` or `Data unavailable` if a metric cannot be computed.
- Show a clear error if an API call fails.
- Never silently substitute a plausible-looking number.

If an API fails, do not replace the result with mock data. Keep the last known result only if the UI explicitly marks it stale and tells the user it could not refresh.

## 2.4 Find and remove fake operational values

Search the entire project for:
- Hardcoded dashboard numbers and money totals
- Frontend arrays used as operational lists instead of API responses
- `||` / `??` fallback values for operational statistics
- Static sample request/task/dispatch objects used by live pages
- Mock delivery proof, fake GPS, fake ETAs, fake notification records
- Buttons that display success without a real backend action
- API responses that return fabricated success or fabricated quantities

For each occurrence:
1. Decide whether it is harmless UI configuration, legitimate database seed data, or fake operational data.
2. Preserve harmless static UI.
3. Keep demo examples in the seed process/database.
4. Replace fake operational data with actual API/database results.
5. If a metric cannot yet be computed, implement the required query or show a truthful empty/unavailable state.

Do not delete demo records that are already in the database unless they are duplicate/corrupt and a safe, justified migration is required.

---

# 3. REAL-TIME UPDATE REQUIREMENT

“Real-time” means that after one user performs a successful action, every relevant dashboard or workflow view reflects the committed database state promptly without requiring the operator to manually reload the entire application.

Choose the simplest reliable approach compatible with the current app:
- Prefer the project's existing SSE/event/polling mechanism if it works.
- Otherwise implement a small shared polling/refresh mechanism for relevant APIs.
- Use SSE only if it is already supported or can be added reliably.
- Do not introduce a new frontend framework or complex infrastructure just for real-time updates.
- Do not pretend a UI update is real-time if it only changes local JavaScript state without saving to the backend.

## 3.1 Required behavior after each successful operation

When an action changes data:
1. Validate the action on the backend.
2. Commit the database transaction.
3. Persist a business event/audit event when appropriate.
4. Return the actual updated record/state from the API.
5. Refresh the current view using the API response or refetch.
6. Notify/refetch other affected dashboards using SSE, polling, or the existing event system.
7. Recalculate affected metrics from the database.
8. Show success only after the backend confirms success.

If the operation fails, do not emit a success event or update UI to a completed state.

## 3.2 Cross-role update examples that MUST work

- Citizen submits a request → Government Official's triage queue updates.
- Official verifies a request → request status/timeline and allocation eligibility update.
- Official approves an NGO zone adoption → NGO dashboard shows the approved zone.
- Warehouse verifies a donation → donation status and actual available stock update.
- Coordinator allocates a request → request, reservation, dispatch queue and relevant dashboard counts update.
- Volunteer accepts a task → NGO/Official task views and volunteer availability update.
- Driver starts a dispatch → dispatch status, vehicle state, request tracking and relevant Citizen view update.
- Driver submits delivery proof → review queue updates; request must not be falsely completed before required review.
- Reviewer accepts or rejects proof → dispatch/request state and dashboards update consistently.
- Shelter admission or transfer → occupancy and remaining capacity update in all shelter views.
- Finance transaction is approved/paid/reconciled → finance dashboard totals are recalculated from ledger records.
- New operational event → only authorized users see relevant notifications/activity.

## 3.3 Real-time technical requirements

- Use database-backed APIs as the source of truth.
- Do not trust local browser state as authoritative.
- Avoid duplicate event handling and repeated refresh loops.
- Clean up polling/SSE listeners when views are destroyed or the user logs out.
- Handle network errors without fabricating data.
- Do not expose private Citizen information through global event messages.
- Use timestamps from actual server/database actions.
- Avoid refresh intervals that overload SQLite or create excessive requests.
- If a client misses events, it must be able to refetch current state.
- Explain in documentation whether updates use polling or SSE and which views are refreshed.

---

# 4. WORK METHOD — INSPECT BEFORE CHANGING

Before implementation:
1. Inspect the current project tree.
2. Inspect Flask routes, service functions, database schema/migrations, JavaScript handlers, templates, seed logic and tests.
3. Run the existing tests if the environment allows.
4. Identify broken workflow transitions, payload mismatches, fake/static values and disconnected UI buttons.
5. Create/update `DRRAS_PROGRESS_HANDOFF.md` with current status.
6. Work directly on the current files.
7. Do not wait after returning a plan; proceed to implementation unless a real blocker exists.

Do not perform an unrelated redesign. Do not replace Flask/SQLite/vanilla JS. Do not delete an existing module to avoid fixing it. Do not reset the database. Do not overwrite newer workspace changes with old code.

---

# 5. USER 1 — ADMINISTRATOR WORKFLOW

Administrator is responsible for system-level administration, not normal field dispatch decisions.

## 5.1 Account approvals
- Fetch pending accounts from the database.
- Display actual pending account records, not a hardcoded list.
- Approve/reject the selected account through a backend endpoint.
- Record reviewer, timestamp, decision and reason.
- Update the account state only after backend success.
- Refresh the pending count and list immediately.
- Do not allow an already decided account to be approved/rejected repeatedly without an explicit valid transition.

## 5.2 User and master-data management
Where these features already exist, make them functional:
- User status and role administration
- Organizations/NGOs
- Resource categories
- Warehouses
- Vehicles
- Shelters
- Zones/incident master data
- Workflow configuration

All tables and dropdown options must be fetched from the database/API if they represent editable operational data.

## 5.3 Audit/activity
- Fetch real audit events from the backend.
- Show actor, action, target record, timestamp and reason where available.
- Filters and pagination must query actual records.
- Do not fabricate audit rows.

## 5.4 Administrator acceptance test
Create or use a pending account, approve it, and verify:
- The database account status changed.
- Pending count decreased.
- Approved user can access the allowed workspace.
- The audit trail contains the real action.
- A repeated request behaves correctly.

---

# 6. USER 2 — GOVERNMENT OFFICIAL WORKFLOW

## 6.1 Incident management
- Create/view/update incidents using actual database records.
- Incident status changes must be validated by the backend.
- Create zones linked to the correct incident.
- Update incident and zone views after successful changes.
- Incident dashboard counts must be calculated from current records.

## 6.2 Citizen request triage and verification
- Display requests from the real API/database.
- Show current request status, verification status, priority score, category, affected people, zone and submission time.
- Make verification actions match the backend's actual accepted decision values.
- If UI offers a duplicate decision, implement it end to end or remove/disable that option until supported; do not leave a broken action.
- Preserve the request and its history when marked duplicate; link it to a primary request where supported.
- Ensure an unverified/rejected/duplicate request cannot be allocated as if verified unless an explicit authorized override exists and is documented.
- Priority score must be calculated from the existing business rules on the server or fetched from the persisted result. Do not hardcode priority labels/scores in the frontend.
- Show verification errors from the backend and keep the record in its correct prior state on failure.

## 6.3 NGO zone adoption
- Show actual pending adoption requests.
- Approve/reject only valid pending requests.
- Record decision, reviewer, time and reason.
- Approved zone coverage must be visible to the NGO through the database/API.
- Rejected or revoked zones must no longer appear as active approved coverage.
- Update both the Official and NGO views after the transaction commits.

## 6.4 Government dashboard
Calculate every KPI from database queries:
- Active incidents
- Requests by verification/status/priority
- Requests awaiting allocation
- Resource shortages
- Active dispatches and blocked routes
- Pending zone adoption requests
- Shelter capacity/occupancy
- Volunteer task progress
- Donation discrepancies
- Financial totals, if this role is authorized to view them

Do not use fixed counts, fixed rupee totals or frontend fallback numbers.

## 6.5 Government acceptance test
Submit a Citizen request, verify it, and check that:
- The request leaves the pending verification queue.
- The status/timeline changes in the database.
- The request becomes eligible for allocation only when the rules permit it.
- Dashboard counters update.
- Other relevant views receive an update.

---

# 7. USER 3 — NGO COORDINATOR WORKFLOW

## 7.1 NGO organization and zone scope
- Fetch the logged-in NGO's actual organization membership and approved zones.
- Display adoption status from database records.
- Do not use a fixed array of zones.
- A submitted adoption request must persist.
- Approval/rejection by the Official must be reflected without fake UI status.
- Do not allow an NGO to operate in an unapproved zone unless the current documented business rule explicitly allows it.

## 7.2 Donation registration and verification
Donation records must distinguish:
- Cash donation
- In-kind donation
- Declared quantity/value
- Actual received quantity/value
- Accepted quantity/value
- Damaged/rejected quantity
- Verification status
- Linked warehouse, incident and zone where relevant
- Donor/reference, timestamps and verifier

A declared donation must not automatically increase available inventory.

For in-kind donations:
1. NGO registers the declaration.
2. Warehouse records physical receipt.
3. Actual quantities are entered.
4. Differences are recorded.
5. Authorized verification/acceptance occurs.
6. Only accepted quantity creates the corresponding inventory receipt transaction.
7. Donation, stock and dashboards refresh from committed database data.

Do not use fake fallback quantities if a resource mapping is missing. Show an actionable validation error.

Donation acceptance must be idempotent: repeating an API call must not add the same stock twice.

For cash donations, record the financial transaction separately from physical stock.

## 7.3 Volunteer task management
- Create tasks through a real API and database record.
- Assign an actual eligible Volunteer.
- Store task objective, incident/zone, linked request if applicable, expected quantity, supervisor, shift and current status.
- Show the same status vocabulary as the backend.
- If the backend status is `In Progress`, frontend conditions must not check only `InProgress`.
- If the backend uses `Submitted for Review`, the UI must use that exact canonical state or a centralized mapping.
- Accept/decline, start, submit and review actions must save to the backend.
- Update NGO and Volunteer dashboards after successful transitions.

## 7.4 NGO daily operations dashboard
Derive counts from actual records:
- Approved zones
- Pending adoption requests
- Volunteers assigned/active
- Tasks pending/in progress/review/completed
- Donations awaiting receipt/verification
- Accepted supplies and discrepancies
- Distribution/fulfilment progress
- Outstanding resource shortages
- Fund requests and actual financial status where permitted

No fabricated values.

## 7.5 NGO acceptance test
Register a donation, verify receipt, assign a task and confirm that:
- Donation state changes persist.
- Only accepted quantities enter stock.
- The task appears in the selected Volunteer’s task list.
- Task state changes appear in NGO and Volunteer views.
- The dashboard reflects actual database records.

---

# 8. USER 4 — CITIZEN WORKFLOW

## 8.1 Submit an emergency request
- Form fields must match the actual backend payload contract.
- Validate required fields on both client and server.
- Generate a unique request ID on the backend.
- Save requester, category, description, location, affected people, vulnerability flags, incident/zone if known, timestamp and initial status.
- Calculate priority according to the existing server-side rules.
- Do not fabricate an ID, priority score or success state in JavaScript.
- On API failure, show the real error and preserve the user's entered form data where feasible.

## 8.2 Track request
- Fetch the Citizen's own actual requests.
- Display real status, priority, timeline, assigned dispatch/fulfilment information and relevant advisory/shelter data where available.
- Timeline events must be from persisted events/status history, not a hardcoded sequence.
- A request must not show Delivered if the linked dispatch has not passed the configured delivery-review workflow.
- Do not display fabricated ETAs or GPS locations.

## 8.3 Confirm or report an issue
- Submit confirmation/issue through a real endpoint.
- Validate that the request belongs to the logged-in Citizen.
- Record the actual response and timestamp.
- A Citizen confirmation should be treated according to the existing business rules; it must not silently replace missing delivery proof or required reviewer approval.
- Issue reports must reach the responsible queue and create a persisted record/event.
- Update request timeline and relevant reviewer dashboard.

## 8.4 Citizen acceptance test
Submit a new request and verify:
- It appears in the Citizen’s request list.
- It appears in the Official’s triage queue.
- Its ID/status/priority are database-derived.
- The Official’s verification decision changes its real state.
- The Citizen sees that change without a full manual page reload, using the implemented real-time refresh mechanism.

---

# 9. USER 5 — VOLUNTEER WORKFLOW

## 9.1 Task inbox
- Fetch tasks actually assigned to the logged-in Volunteer.
- Do not display a hardcoded task array.
- Show objective, zone, linked request, supervisor, shift, expected quantity, instructions and actual status.

## 9.2 Task lifecycle
Support the transitions defined by the current business rules, such as:
`Assigned → Accepted/Declined → In Progress → Submitted for Review → Completed`

Use one canonical status representation across backend, database, API and frontend. If legacy status values exist, map/migrate them deliberately; do not use scattered inconsistent string comparisons.

Only allow actions valid for the current status.

## 9.3 Check-in and progress
- Record check-in/check-out timestamps on the backend.
- Location capture is optional; do not fake GPS.
- Progress updates must persist.
- Field reports must be linked to the relevant incident/zone and remain unverified until authorized review if required.

## 9.4 Quantity reconciliation
The form payload field names must match the backend's expected contract.

For distribution tasks, record:
- Quantity received
- Quantity distributed
- Quantity damaged
- Quantity remaining/returned
- Explanation for discrepancy

Validate the quantity invariant:
`Received = Distributed + Damaged + Remaining/Returned`
where this model applies.

Do not accept impossible negative quantities or silently rewrite a mismatch.

## 9.5 Supervisor review
- Submission moves the task to the canonical review state.
- Supervisor can approve or return for correction.
- Completion updates the real task record, audit history, and relevant dashboard metrics.
- Volunteer availability must reflect actual active assignments, not a static flag.

## 9.6 Volunteer acceptance test
Assign a task to a Volunteer, accept it, start it, submit progress and reconcile quantities. Verify every state transition in the database and both dashboards.

---

# 10. USER 6 — DRIVER WORKFLOW

## 10.1 Dispatch list
- Fetch actual dispatches assigned to the logged-in Driver.
- Show real request, pickup warehouse, destination, vehicle, manifest items, quantities and current status.
- Do not use hardcoded dispatch cards or fake ETA values.

## 10.2 Vehicle and dispatch readiness
Before journey start, validate the dispatch’s current state, required stock issue, assigned Driver, assigned vehicle and required manifest data.
Do not allow a vehicle with an unresolved active trip to be marked Available.

## 10.3 Journey
- Start journey through a backend endpoint.
- Record a real server timestamp.
- Update dispatch and vehicle state atomically where appropriate.
- Update linked request tracking and relevant dashboard data.
- Route blockage must create a real persisted report and review task.
- Do not claim live map tracking unless real location data is received.

## 10.4 Delivery proof
- Delivery proof must use actual dispatch manifest items and quantities.
- Never use one generic quantity for every item in a multi-item dispatch.
- Validate that submitted item IDs belong to the dispatch.
- Record submitted quantity, proof reference/type, actor and timestamp.
- Repeated proof submission must not double-count delivered quantities.
- Rejected proof must not complete the request.
- Partial delivery must preserve outstanding, returned and damaged quantities.
- Final request completion must follow the defined proof/review/confirmation policy.
- Legacy endpoints must not bypass these rules.

## 10.5 Vehicle return
- Record returned stock through inventory transactions.
- Mark vehicle Available only after the trip is properly closed and no active assignment remains.
- Record damage/maintenance state where relevant.

## 10.6 Driver acceptance test
Run a complete dispatch from Loading/Ready to En route, arrival, proof submission, review and final resolution. Test both accepted and rejected proof. Verify request, dispatch, vehicle and inventory records remain consistent.

---

# 11. INVENTORY AND RESOURCE ALLOCATION — CONNECTED BUSINESS LOGIC

## 11.1 Single source of truth
Inspect legacy inventory tables and warehouse/resource stock tables. There must be one canonical source of truth for physical stock and reservations.

If old APIs require compatibility, derive their values from the canonical stock model or update records atomically. Do not maintain independent balances that can diverge.

## 11.2 Required quantities
Keep these distinct:
- On-hand
- Reserved
- Available to allocate
- Issued
- Delivered
- Returned
- Damaged/unusable

`Available to Allocate = On-hand - Active Reservations`

Do not allow negative available stock.

## 11.3 Allocation eligibility
- An unverified, rejected or duplicate request must not be allocated through the normal flow.
- Validate stock, incident/zone, request state, quantity and eligible resource.
- Allocation should create a persistent allocation/reservation record and related dispatch only according to the business rules.
- Prevent duplicate allocation and duplicate stock deductions.
- If allocation fails, rollback all related changes.

## 11.4 Reconciliation
When a dispatch is cancelled, partially delivered or returned, determine which items are still at the warehouse, issued to the vehicle, delivered, damaged or returned. Release a reservation only when the physical/business state allows it.

Do not release issued goods as if they never left the warehouse.

## 11.5 Inventory acceptance test
Create a stock balance, reserve a quantity, issue it, partially deliver it and return the remainder. Verify ledger entries and calculated balances after every step. Repeat the same request to confirm no duplicate transaction is created.

---

# 12. SHELTER WORKFLOW

Shelter values must be database-derived.

- Fetch actual shelter records, capacities and current occupants.
- Record each admission/exit/transfer persistently.
- Calculate remaining capacity as `Capacity - Current Occupants` using the actual occupancy model.
- Validate capacity before confirming an admission.
- Do not count historical admissions as current occupants.
- Transfers must update source and destination consistently and atomically.
- If only part of a household moves, model the split explicitly; do not transfer the entire record accidentally.
- Cancelled/failed transfers must not leave occupancy changed.
- Refresh shelter cards and capacity alerts after successful admission/transfer/exit.
- Never use static occupancy numbers or percentages.

Test admission, full shelter, exit, full transfer, partial transfer if supported, and rollback on failure.

---

# 13. FUNDS AND FINANCE WORKFLOW

Finance values must come from persisted ledger records, not hardcoded dashboard numbers.

Keep separate:
- Requested amount
- Approved amount
- Committed amount
- Paid amount
- Refunds/reversals
- Reconciled expenditure
- Remaining budget according to the defined accounting formula

Use integer paise or another exact monetary representation.

- Do not treat approval as payment.
- Do not treat payment as reconciliation.
- Do not derive a total from a fabricated fallback.
- Keep cash donations separate from in-kind stock.
- Every financial transaction must have a real record, actor, timestamp, reference and status.
- Duplicate submission must not double-count a payment or donation.
- Failed transactions must not update the dashboard as if successful.

If the database contains no transactions, show zero or an explicit empty state rather than an invented total.

Test request, approval, commitment, payment, rejection, reconciliation and duplicate submission according to the existing supported workflow.

---

# 14. API AND FRONTEND CONTRACT CHECK

For every visible button and form, trace this complete path:

`UI action → JavaScript handler → API request → Flask route → validation/service → SQLite transaction → API response → UI refresh → other affected views refresh`

Create an endpoint map in `docs/WORKFLOW_API_MAP.md` or another suitable existing documentation location.

For each important endpoint document:
- Method and path
- Payload fields
- Response fields
- Required role
- Business preconditions
- Database side effects
- Status transitions
- Error responses
- Which dashboards/views refresh after success

Fix mismatches in field names and status strings. Do not solve a mismatch by hardcoding a fake response in JavaScript.

Every visible action must either:
- Work end to end, or
- Be clearly disabled/labeled as unavailable if it is outside the intended scope.

Do not display success until the backend confirms success.

---

# 15. REAL-TIME DASHBOARD METRICS

Create or repair database-backed API endpoints for dashboard summaries. Reuse existing endpoints where suitable; do not create duplicate APIs without need.

Each dashboard KPI must be computed from current records and authorized to the correct role.

Examples:
- Pending request count = query current eligible request records.
- Active dispatch count = query dispatches in active states.
- Available stock = calculate from canonical stock and active reservations.
- Volunteer available count = derive from actual active assignments/status rules.
- Shelter occupancy = calculate from admissions/exits/transfers or the canonical occupancy model.
- Donation accepted quantity = sum verified accepted transaction quantities, not declared quantities.
- Finance totals = calculate from ledger entries according to documented formulas.
- Task completion = query actual task states.
- Notifications = query persisted notification/event records available to the current user.

After an operation commits, update affected KPI cards and lists through the real-time mechanism. Do not increment/decrement a frontend number optimistically as the only source of truth. The backend must be authoritative.

If a refresh fails, show an error/stale indicator and provide retry. Never substitute mock data.

---

# 16. DATABASE, MIGRATIONS AND DEMO DATA

- Inspect the existing schema and migration versions first.
- Preserve current user data.
- Add only the schema changes required for correct workflows.
- Use safe, repeatable migrations.
- Do not reset the database as a shortcut.
- Do not create duplicate tables for concepts already represented.
- Ensure foreign-key relationships and indexes support actual queries.
- Ensure repeated seeding does not duplicate demo records.
- Seed only clearly fictional demo data, through the existing seed process.
- Do not seed fake dashboard totals; seed actual related records and let queries calculate totals.
- Test on a disposable copy before applying migrations to the main database.
- Verify foreign-key integrity and important quantity/occupancy/accounting invariants.

---

# 17. TESTING REQUIREMENTS

Inspect and preserve the existing tests. Update obsolete expectations when the intended workflow is corrected, but never delete or weaken tests merely to get a pass.

Run tests using the actual project environment. If dependencies are missing, inspect the existing venv and requirements first. Do not claim a test passed unless it actually ran.

At minimum test:

1. Request submission → Official queue.
2. Verification → allocation eligibility.
3. Invalid/unverified request allocation is rejected.
4. Duplicate decision behavior.
5. Donation declared vs received vs accepted quantity.
6. Accepted donation updates stock exactly once.
7. Allocation creates correct reservation/dispatch records.
8. Duplicate allocation does not double-deduct stock.
9. Volunteer task assignment appears in the correct account.
10. Volunteer status transitions match frontend/backend.
11. Quantity reconciliation payload matches the backend.
12. Driver dispatch status updates the Citizen tracking view.
13. Rejected delivery proof does not complete a request.
14. Multi-item dispatch quantities remain separate.
15. Repeated proof submission does not double-count.
16. Return/cancellation reconciles inventory correctly.
17. Shelter admission/transfer updates occupancy correctly.
18. Finance totals change only after actual ledger transactions.
19. Dashboard counts are computed from database records.
20. A failed API does not show success or fake values.
21. Real-time/polling/SSE updates refresh relevant views.
22. A full positive and negative end-to-end scenario.

Also manually verify each role’s actual UI in the running application if browser access is available.

---

# 18. REQUIRED END-TO-END DEMO SCENARIO

Use the existing fictional flood incident and existing database records where appropriate. Do not create contradictory hardcoded scenario values in the UI.

Run this flow through the actual app/API:

1. Administrator approves a pending staff/NGO account if the approval workflow requires it.
2. Government Official opens/activates the incident and reviews zones.
3. Citizen submits a new medical/water emergency request.
4. The request appears in the Government Official’s queue without a manual full-page reload.
5. Official verifies the request.
6. NGO adoption is approved where needed and the NGO sees the approved zone.
7. NGO registers a donation.
8. Warehouse verifies actual received quantities; accepted stock updates the inventory ledger.
9. Authorized coordinator allocates resources to the verified request.
10. The stock reservation and dispatch manifest are created consistently.
11. A Volunteer receives and accepts a linked field task if the workflow requires one.
12. Driver sees the actual assigned dispatch, starts the trip and updates status.
13. Citizen tracking and relevant dashboards refresh from backend state.
14. Driver submits item-specific delivery proof.
15. Authorized review accepts or rejects proof.
16. The request is completed only when the configured business rules are satisfied.
17. Inventory and vehicle status are reconciled.
18. Volunteer task and distribution quantities are reviewed where applicable.
19. Shelter and finance dashboards reflect actual related records if those operations were performed.
20. Audit/timeline/report views show the real sequence of actions.

Also run negative scenarios:
- Request is not verified.
- Insufficient stock.
- Donation discrepancy.
- Volunteer declines task.
- Route blocked.
- Delivery proof rejected.
- Partial delivery.
- Shelter is full.
- API/network error.

Each failure must leave the system in a consistent state and show a truthful message.

---

# 19. SUBMISSION-READY DEMONSTRATION

Prepare `DEMO_WALKTHROUGH.md` with:
- Confirmed local demo accounts from the actual project.
- Startup command.
- Each role’s login and main task.
- The exact order for demonstrating the connected workflow.
- Which records are seeded and which records the presenter should create during the demo.
- Expected database-backed state changes.
- How to show real-time updates.
- Known limitations and simulation-only features.

Never invent credentials or claim an integration is real if it is simulated.

Keep the project easy to run locally. Do not introduce deployment infrastructure or new services unless required by the existing architecture.

---

# 20. DEFINITION OF DONE

The work is done only when:

- The current project has been preserved.
- All six role workflows have been inspected.
- Existing features work end to end or their genuine limitations are documented.
- No operational dashboard value is falsely presented as live static data.
- Database/API responses are the source of truth for operational values.
- A successful operation updates its database records and affected views.
- Relevant dashboards refresh promptly through the implemented polling/SSE/event mechanism.
- Failed operations do not show fake success.
- Status strings and request payload fields are consistent across frontend and backend.
- Inventory, dispatch, request, donation, shelter and finance records remain consistent.
- Positive and negative workflow tests have been run where the environment allows.
- The app starts using the documented local command.
- `DEMO_WALKTHROUGH.md` reflects the actual implementation.
- Any test or environment limitation is reported honestly.

Do not claim all criteria are complete unless you have verified them.

---

# 21. FINAL INSTRUCTION TO THE CODING AGENT

Start by inspecting the current DRRAS-Flask workspace and database. Then implement the repairs directly in the existing code.

**NON-NEGOTIABLE: EVERY OPERATIONAL VALUE MUST BE DYNAMIC AND DATABASE/API-DRIVEN. ALL EXISTING USER WORKFLOWS MUST BE CONNECTED AND FUNCTIONAL. CROSS-ROLE UPDATES MUST REFLECT COMMITTED DATABASE CHANGES PROMPTLY. NO FAKE STATIC DASHBOARD VALUES, NO FAKE SUCCESS MESSAGES, AND NO LOCAL-STATE-ONLY IMPLEMENTATIONS OF BUSINESS OPERATIONS.**

Preserve the current project. Do not restart or delete features. Add the missing supporting APIs and functionality when required. Run the tests, verify the actual workflows, fix the issues you find, and provide the updated project and a truthful implementation/test report.

Do not stop after writing a plan. Implement, run, verify, and document.
