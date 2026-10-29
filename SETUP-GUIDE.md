# DRRAS â€” Setup, Presentation & Evaluator Walkthrough Guide

## 1. System Prerequisites
- **Python 3.10 or higher** (Tested on Python 3.12.10).
- **No external heavy toolchains required**: Zero Node.js, npm, Java, or Docker needed.
- Standard libraries plus `flask` and `pytest` (specified in `requirements.txt`).

---

## 2. Launching the Application

### Option A: 1-Click Launch (Recommended for Windows)
1. Open Windows File Explorer and navigate to:
   ```text
   <project folder>
   ```
2. Double-click **`run.bat`**.
3. A command window verifies Python, installs dependencies if necessary, executes idempotent migrations and demo data seeding, and opens your browser at **`http://127.0.0.1:5055`**.

### Option B: PowerShell / Command Prompt
```powershell
cd <project folder>

# Install requirements
pip install -r requirements.txt

# Run idempotent database migration & demo scenario seeding
python seed_demo.py

# Launch Flask development server
$env:PORT = '5055'
python app.py
```
Open **`http://127.0.0.1:5055`** in your browser.

---

## 3. Verified Demo Accounts Summary

Click any quick-fill account badge on the login screen to populate credentials:

| Role | Primary Workflow |
|---|---|
| **Administrator** | Cross-owner administration and audit |
| **Government Official** | Government response, allocation, dispatch |
| **NGO Coordinator** | NGO-owned personnel, stock, shelters and assistance |
| **Citizen** | Emergency request and status tracking |
| **Government Driver** | Government-assigned dispatch and delivery proof |
| **NGO Driver** | NGO-owned dispatch and delivery proof |
| **Government Volunteer / Responder** | Government response tasks |
| **NGO Volunteer** | NGO-owned response tasks |

These are fictional local demonstration accounts only. Use [docs/DEMO_CREDENTIALS.md](docs/DEMO_CREDENTIALS.md) for current emails and verified passwords. See `DEMO_WALKTHROUGH.md` for the role and simultaneous-claim demo steps.
---

## 4. Complete 10â€“15 Minute Evaluator / Viva Demonstration Script

Follow this step-by-step walkthrough to demonstrate the full disaster relief lifecycle:

```text
[Citizen Emergency Call] â”€â”€> [Official Triage & Verify] â”€â”€> [Atomic Allocation & Stock Reservation]
                                                                     â”‚
[Driver Fleet Journey] <â”€â”€ [Vehicle & Driver Auto-Assignment] <â”€â”€â”€â”€â”€â”€â”˜
        â”‚
        â”œâ”€â”€> [Route Blockage & Reroute]
        â”‚
        â””â”€â”€> [Delivery Proof Submission] â”€â”€> [Citizen Aid Confirmation]
                                                      â”‚
[Volunteer Field Task & Strict Reconciliation] <â”€â”€â”€â”€â”€â”€â”˜
```

---

### Step 1: Citizen Submits Geo-Tagged Emergency Aid Request
1. **Login**: Click **Citizen** (`citizen@drras.in` / `citizen123`) $\rightarrow$ Sign In.
2. **Page**: Observe the Citizen Dashboard (*"My Relief Hub"*). Note that other citizens' private records are hidden.
3. **Action**: Click the red **"Emergency request"** button in the header.
4. **Form Input**:
   - Click the interactive Leaflet map to drop a pin in Sector 1 (e.g., Lat: `30.9100`, Lng: `75.8500`).
   - Requester Name: `Sukhwinder Kaur`
   - Area: `Old City & Riverfront Ward 8`
   - Assistance Type: `Medical Kit` (or `Food Rations`)
   - People Affected: `9`
   - Vulnerable Persons: `Yes` (elderly family members trapped by rising waters).
5. **Submit**: Click **Submit Emergency Request**.
6. **Expected Database & Screen Change**:
   - The urgency formula automatically computes:
     $$\text{Score} = 58 (\text{base}) + 25 (\text{vulnerable}) + 10 (>8\text{ people}) + 10 (\text{medical}) = 99 \text{ (Critical Tier)}$$
   - Request created with status `Awaiting allocation` (or `Submitted`), visible in your personal tracker with a unique ID (e.g. `REQ-2026-004`).
   - Click **"View audit timeline"** to view the initial submitted timestamp.
7. **Action**: Sign out.

---

### Step 2: Government Official Triages & Verifies Emergency Request
1. **Login**: Click **Government Official** (`official@drras.in` / `official123`) $\rightarrow$ Sign In.
2. **Page**: Observe the *District Emergency Operations Command* dashboard.
3. **Action**: Scroll to **"Priority Request Triage & Verification Queue"**.
4. **Action**: Locate the newly submitted request (`REQ-2026-004`).
5. **Action**: Click **"Verify Request"**.
6. **Modal**: In the verification dialog:
   - Select Decision: `Verified`.
   - Reason: `Field drone reconnaissance confirms severe waterlogging at coordinates.`
   - Click **Confirm Verification Decision**.
7. **Expected Database & Screen Change**:
   - Request verification status updates to `Verified`.
   - A real-time audit log event (`VERIFY_REQUEST`) is recorded in `audit_logs`.
   - Status badge transitions to `Verified Â· Ready for Allocation`.

---

### Step 3: Atomic Resource Allocation, Stock Reservation & Driver Assignment
1. **Page**: While still logged in as **Government Official** (or **NGO Coordinator**), navigate to **Emergency Requests** in the main navigation.
2. **Action**: On the verified request (`REQ-2026-004`), click **"Allocate"**.
3. **Expected Database & Relational Changes (Atomic Transaction)**:
   - Backend service `allocate_request_service` executes in a single SQLite transaction:
     1. Validates available stock in Central Relief Depot (`on_hand - reserved >= requested`).
     2. Deducts available units and creates a linked row in `inventory_reservations` and `inventory_reservation_items`.
     3. Validates the coordinator-selected available driver and compatible available vehicle from the database-backed allocation options.
     4. Creates a linked row in `dispatches` with status `Loading`.
     5. Transitions request status to `Allocated`.
     6. Appends immutable records to `inventory_transactions` (`Reserved`) and `audit_logs` (`ALLOCATE_REQUEST`).
4. **Verification**:
   - Notice the request status changes to `Allocated`.
   - Navigate to **"Warehouse Inventory"**: Available units decreased by the reserved amount.
   - Navigate to **"Vehicles & Dispatch"**: A new dispatch is scheduled for the selected available Driver with manifest details; that driver sees it in their API-scoped dispatch list.
5. **Action**: Sign out.

---

### Step 4: Driver Fleet Journey, Route Blockage & Delivery Proof
1. **Login**: Click **Driver** (`driver@drras.in` / `driver123`) $\rightarrow$ Sign In.
2. **Page**: Observe the *Driver Logistics Console*. The selected Driver sees only dispatches assigned to their user ID.
3. **Action 1 (Start Journey)**:
   - Click **"Start journey"** on the assigned trip.
   - Status transitions to `En Route`. Vehicle status updates to `EnRoute`. Request status updates to `Dispatched`.
4. **Action 2 (Report Route Blockage)**:
   - Click **"Report blockage"** button.
   - Specify reason: `National Highway submerged under 3 feet of flood water near Bridge 4`.
   - Click **Submit Route Blockage Alert**.
   - An emergency banner appears on the driver board: `ROUTE EXCEPTION ACTIVE: Reroute Authorized`.
5. **Action 3 (Arrive at Destination)**:
   - Click **"Mark Arrived"** $\rightarrow$ Status changes to `Arrived at Sector`.
6. **Action 4 (Submit Delivery Proof & Cargo Reconciliation)**:
   - Click **"Submit Delivery Proof"**.
   - In the proof modal:
     - Delivered quantity: `5` units (full delivery).
     - Returned quantity: `0`.
     - Damaged quantity: `0`.
     - Proof Type: `RecipientConfirmation`.
     - Recipient Signature / Note: `Received by community elder Sukhwinder Kaur`.
   - Click **Submit Proof of Delivery**.
7. **Expected Database Change**:
   - Status transitions to `Delivered Pending Proof` (or `Delivered`).
   - A `delivery_proofs` record is created.
   - Linked emergency request is updated.
8. **Action**: Sign out.

---

### Step 5: Citizen Confirms Delivery Receipt
1. **Login**: Click **Citizen** (`citizen@drras.in` / `citizen123`) $\rightarrow$ Sign In.
2. **Action**: Locate the request on your dashboard.
3. **Action**: Click **"Confirm aid received"**.
4. **Dialog**: Rate response quality (e.g., 5 stars) and note: `Supplies received in good order. Thank you.`
5. **Verification**:
   - Status transitions to `Delivered Â· Confirmed by Citizen`.
   - Request audit timeline displays all stages: `Submitted` $\rightarrow$ `Verified` $\rightarrow$ `Allocated` $\rightarrow$ `Dispatched` $\rightarrow$ `Delivered`.
6. **Action**: Sign out.

---

### Step 6: Volunteer Accepts Field Task & Submits Strict Reconciliation
1. **Login**: Click **Volunteer** (`volunteer@drras.in` / `volunteer123`) $\rightarrow$ Sign In.
2. **Page**: View the *Responder Workspace*.
3. **Action 1 (Accept Mission)**:
   - Scroll to **"Assigned Operational Missions (`volunteer_tasks`)"**.
   - Locate task `TASK-041` (*Emergency Food Ration Distribution â€” Ward 8*).
   - Click **"Accept"** $\rightarrow$ Status updates to `Accepted`.
4. **Action 2 (Field Check-in)**:
   - Click **"Check-In"** $\rightarrow$ Records field waypoint arrival with simulated GPS coordinates.
5. **Action 3 (Distribution Reconciliation)**:
   - Click **"Reconcile & Submit"**.
   - In the interactive modal:
     - Notice the live inventory formula box:
       $$\text{Received (50)} = \text{Completed (45)} + \text{Damaged (2)} + \text{Remaining (3)}$$
     - Observe the live green badge: `âœ“ Inventory Balanced (Diff: 0)`.
     - Intentionally change Damaged to `5` to show evaluator that when $50 \neq 45 + 5 + 3$, the box turns red (`Unbalanced -3 units`) and blocks submission!
     - Change it back to balance to `0` diff.
     - Notes: `Distribution completed at relief staging area.`
     - Click **Submit Distribution Report**.
6. **Expected Database Change**:
   - Task transitions to `Submitted for Review`.
   - Volunteer task quantities are stored accurately in `volunteer_tasks`.
7. **Action**: Sign out.

---

### Step 7: NGO Coordinator Donation Intake & In-Kind Discrepancy Handling
1. **Login**: Click **NGO Coordinator** (`ngo@drras.in` / `ngo123`) $\rightarrow$ Sign In.
2. **Action 1 (Register Donation)**:
   - In the NGO Feature Hub, click **"Register Donation"**.
   - Select In-Kind Donation:
     - Donor Name: `Punjab Rotary Humanitarian Trust`.
     - Resource: `Blankets`.
     - Declared Quantity: `500` units.
   - Click **Register In-Kind Donation**.
3. **Action 2 (Physical Verification & Discrepancy)**:
   - Log in as **Government Official** (`official@drras.in`).
   - Open **Donation Verification**:
     - Physical count conducted at warehouse bay: `480` blankets received intact, `20` missing/damaged during water transport.
     - Accepted: `480`. Rejected: `20`.
     - Decision: `PartiallyAccept`.
     - Reason: `20 cartons water-damaged during canal crossing.`
   - Click **Verify & Accept Donation**.
4. **Expected Database Change**:
   - Only `480` units enter warehouse stock (never the declared 500!).
   - An immutable transaction of type `DonationReceived` is posted to `inventory_transactions`.
   - Discrepancy record preserved for state audit inspection.

---

### Step 8: Administrator Security Audit Trail & System Management
1. **Login**: Use an Administrator email and verified password from `docs/DEMO_CREDENTIALS.md` $\rightarrow$ Sign In.
2. **Page**: Navigate to **Administration** in the main navigation.
3. **Action**:
   - Inspect **Pending Account Approvals**: Approve or reject pending staff registrations.
   - Inspect **Role-Based Access Control (RBAC) Matrix**: Review role privilege boundaries.
   - Inspect **Security & Compliance Audit Trail (`audit_logs`)**:
     - Review the complete chronological ledger showing every actor ID, action (`ALLOCATE_REQUEST`, `VERIFY_REQUEST`, `DELIVERY_PROOF_SUBMITTED`, etc.), target entity, and timestamp.
     - Click **"Refresh Audit Trail"** to fetch live updates.
4. **Action**: Click **"Urgency Weights & Triage Engine"** to demonstrate configuration of the mathematical triage score.
5. **Action**: Navigate to **Requests** or **Inventory** and click **"Export CSV"** to demonstrate formula injection-safe reporting.

---

## 5. Automated Test Suite Execution

Run the automated pytest regression suite. See `IMPLEMENTATION_PROGRESS.md` for the latest observed pass/fail totals:

```powershell
pytest -v
```

The suite includes regression tests for authentication and authorization, requests, dispatches, finance, inventory, shelters, volunteer tasks, escalation, and end-to-end workflows. Use the live pytest output for per-file counts; the prior hand-maintained module count has been removed.

---|---|---|
| `test_auth_rbac.py` | 13 | Login, session cookies, RBAC enforcement, pending registration approval |
| `test_emergency_requests.py` | 11 | Urgency formula, strict input validation, allocation idempotency |
| `test_dispatches_workflow.py` | 3 | Dispatch lifecycle, driver ownership isolation, request synchronization |
| `test_fleet_and_proof.py` | 1 | Trip start, flood route blockage, rerouting, delivery proof reconciliation |
| `test_donations_ledger.py` | 1 | Donation intake, discrepancy handling, stock ledger crediting |
| `test_volunteer_tasks.py` | 2 | Task assignment, check-in, strict distribution reconciliation |
| `test_shelter_transfers.py` | 2 | Capacity boundary enforcement, atomic transfer without double-counting |
| `test_funds_paise.py` | 1 | Dual-control grant approval, commitment, payment in integer paise |
| `test_incidents_zones.py` | 2 | Incident activation, zone creation, NGO adoption approval lifecycle |
| `test_e2e_flood_scenario.py` | 1 | Full end-to-end connected Sutlej flood scenario |
| `test_realtime_and_interconnected_workflows.py` | 6 | Cross-module synchronization, inventory deduction, event polling |
| `test_inventory_volunteers.py` | 8 | Warehouses, resource mapping, volunteer roster assignment |
| `test_misc_modules_and_security.py` | 11 | Centralized JSON errors, payload limit, CSV injection escaping |
| `test_reproduce_defects.py` | 6 | Regression verifications for previously identified edge cases |

---

## 6. Viva Architecture Defense Points

- **Why SQLite instead of heavy databases?**  
  SQLite is serverless, zero-configuration, and stores the entire system in a single transactional file (`drras.db`). With `PRAGMA foreign_keys = ON` and `WAL` journal mode, it offers enterprise relational integrity and acid transactions with zero runtime overhead.
- **Why Vanilla JS instead of React or Vue?**  
  Zero build steps, zero Webpack/Vite compilation, zero dependency vulnerabilities in `node_modules`, and sub-second browser boot times. The application uses modular, reactive ES6 JavaScript with semantic state management.
- **Why Paise instead of standard Rupee floats?**  
  IEEE 754 floating point arithmetic introduces binary precision errors (e.g. `0.1 + 0.2 = 0.30000000000000004`). In disaster finance, all currency is represented as 64-bit integer paise ($1\text{ INR} = 100\text{ paise}$), guaranteeing absolute mathematical precision.
- **How is data safety ensured during concurrent requests?**  
  Allocations, stock reservations, shelter transfers, and donation intake execute within exclusive database transactions with SQLite's busy timeout and status check guards to guarantee that double allocation or negative stock can never occur.

