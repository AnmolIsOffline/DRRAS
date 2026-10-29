# DRRAS â€” Disaster Relief Resource Allocation System (Full-Stack Operations Platform)

An enterprise-grade, relational-backed, role-aware **Disaster Relief Resource Allocation System (DRRAS)** engineered in **Python Flask**, **SQLite**, **HTML5**, **Vanilla CSS**, and **ES6 Vanilla JavaScript**.

> **Architecture Contract**: Zero React Â· Zero Vite Â· Zero Node.js Â· Zero Spring Boot Â· Zero Heavy Toolchains  
> Self-contained, launches in seconds, and runs out-of-the-box with standard Python 3.10+.

---

## ðŸŒŸ 1. System Overview & Core Capabilities

DRRAS transforms disaster emergency coordination from isolated spreadsheets and prototype mockups into an interconnected, transactional operations platform. All six stakeholder roles interact with a single source of relational truth backed by SQLite transactions, foreign-key constraints, audit logs, and automated business logic.

### ðŸ›¡ï¸ Non-Negotiable Operational Principles
1. **Relational Truth & Atomic Operations**: Every workflow (e.g. allocating aid, reserving stock, assigning driver/vehicle, dispatching cargo, logging audit events) executes inside atomic SQLite transactions (`PRAGMA foreign_keys = ON`).
2. **Integer Minor Currency Units**: All financial records, budgets, donations, and expense ledgers are tracked in **paise** ($1\text{ INR} = 100\text{ paise}$) to eliminate IEEE 754 binary floating-point rounding errors.
3. **Mathematical Stock Invariants**:
   - $\text{Available to Allocate} = \text{On-Hand Stock} - \text{Active Reservations}$.
   - Unverified donations never enter inventory; only physically received and accepted items generate stock ledger movements.
4. **Physical Field Reconciliation**:
   - Distribution Tasks: $\text{Received Units} = \text{Completed} + \text{Damaged} + \text{Remaining}$.
   - Fleet Delivery: $\text{Loaded Units} = \text{Delivered} + \text{Returned} + \text{Damaged} + \text{Unresolved}$.
5. **No Double-Counting in Shelter Transfers**: Shelter transfers transfer occupants atomically between facilities without double-counting bed occupancy.
6. **Transparent Security & Auditing**: Server-side RBAC, CSRF mitigation, IDOR prevention, and an append-only `audit_logs` ledger recording every state change with actor, timestamp, entity diff, and authorization context.
7. **Simulation Disclosure**: External integrations (GPS, route preview, SMS broadcast, payment processing) are honestly labelled local demonstration adapters.

---

## ðŸ—ºï¸ 2. Fictional Master Scenario: Sutlej River Flood Response

The built-in demo scenario models an acute monsoon flood in the **Ludhiana / Sutlej River Basin** (`INC-2026-FLOOD`):
- **Incident**: *Sutlej River Flash Flood Response â€” Ludhiana Sector* (Status: `Active`, Severity: `Severe`).
- **Operational Relief Zones**:
  - `Z-01`: *Old City & Riverfront Ward 8* (High Severity â€” Inundated).
  - `Z-02`: *Industrial Area Bypass* (Medium Severity â€” Logistics Corridor).
  - `Z-03`: *Civil Lines Relief Camp* (Low Severity â€” Staging & Shelters).
- **Facilities & Warehouses**:
  - `WH-01`: *Central Relief Depot (Ludhiana Cantonment)*.
  - `WH-02`: *Model Town Secondary Staging Hub*.
- **Fleet Assets**: Emergency Cargo Van (`PB-10-EM-101`), Heavy 4x4 Supply Truck (`PB-10-EM-204`), Rapid Relief Ambulance (`PB-10-EM-309`).
- **Shelters**: *Khalsa Senior Secondary Relief Shelter* (Capacity: 250), *Guru Nanak Community Center* (Capacity: 180).

---

## ðŸ”‘ 3. Verified Demo Login Credentials

All seeded demo accounts are listed in the generated [local credentials reference](docs/DEMO_CREDENTIALS.md). It includes only passwords that match stored hashes; unknown existing passwords are not guessed.

| Role | Operational Responsibilities |
|---|---|
| **Administrator** | System oversight, user approvals/suspensions, urgency weights, master data, full audit logs |
| **Government Official** | Incident command, zone activation, adoption approvals, advisory broadcasts, dual-control funds |
| **NGO Coordinator** | Zone adoption applications, donation intake, stock ledger, volunteer mission assignment |
| **Volunteer / Responder** | Field mission acceptance, GPS check-in, relief distribution, strict quantity reconciliation |
| **Citizen** | Emergency requests, Leaflet GPS pin picker, status timeline, delivery confirmation/issue report |
| **Driver** | Assigned dispatches, trip journey (Ready â†’ En Route â†’ Arrived), route blockage, delivery proof |

*Note: New public registrations for official, NGO, or volunteer roles are created with `PENDING` status and require Administrator authorization before granting system access.*

The login page no longer displays Quick Login buttons or prefilled demo credentials. The canonical, hash-verified local account list is generated in [docs/DEMO_CREDENTIALS.md](docs/DEMO_CREDENTIALS.md). Dataset totals and personnel availability are generated in [docs/DEMO_VALIDATION_REPORT.md](docs/DEMO_VALIDATION_REPORT.md). These credential references are project documentation, not files served by Flask static routes. Set `DRRAS_ENV=production` on a hosted deployment; the demo-credential API is disabled in production.

---

## ðŸ”„ 4. Core State Machine Transition Specifications

### 4.1 Emergency Request Lifecycle
```text
Submitted â”€â”€> Under Review â”€â”€> Verified â”€â”€> Awaiting Allocation â”€â”€> Allocated â”€â”€> Dispatched â”€â”€> Delivered Pending Confirmation â”€â”€> Delivered â”€â”€> Closed
     â”‚              â”‚               â”‚
     â””â”€â”€ Duplicate  â””â”€â”€ Rejected   â””â”€â”€ More Info Required / Partially Fulfilled
```
- **Guards**: Only Government Officials/Admins can verify requests; only verified requests can be allocated; repeated allocations are idempotent; citizen can confirm receipt or report delivery discrepancies.

### 4.2 Incident & Zone Adoption Lifecycle
```text
Incident: Draft â”€â”€> Under Verification â”€â”€> Active â”€â”€> Stabilizing â”€â”€> Closed (Blocks if open tasks/dispatches remain)
Adoption: Requested â”€â”€> Under Review â”€â”€> Approved â”€â”€> Active â”€â”€> Expired / Revoked
```

### 4.3 Donation & Stock Intake Lifecycle
```text
Draft â”€â”€> Submitted â”€â”€> In Transit â”€â”€> Received â”€â”€> Verification Pending â”€â”€> Accepted / Partially Accepted (Credits Stock Once)
```
- **Discrepancy Rule**: If declared > received, discrepancy is logged. Stock increases by $\min(\text{received}, \text{accepted})$.

### 4.4 Driver Dispatch Lifecycle
```text
Planned â”€â”€> Stock Reserved â”€â”€> Picking â”€â”€> Loading â”€â”€> Ready â”€â”€> En Route â”€â”€> Arrived â”€â”€> Delivered Pending Proof â”€â”€> Delivered
     â”‚                                                     â”‚
     â””â”€â”€ Cancelled (Releases stock reservation)           â””â”€â”€ Route Blocked â”€â”€> Rerouted
```

### 4.5 Volunteer Task Lifecycle
```text
Created â”€â”€> Assigned â”€â”€> Accepted â”€â”€> In Progress â”€â”€> Submitted for Review â”€â”€> Completed / Verified
                            â”‚
                            â””â”€â”€ Declined (Reassignment Required)
```
- **Reconciliation Constraint**: Reconciles before supervisor review: $\text{Received} = \text{Completed} + \text{Damaged} + \text{Remaining}$.

### 4.6 Dual-Control Fund Request Lifecycle
```text
Submitted â”€â”€> Approved â”€â”€> Committed â”€â”€> Paid (Recorded in Paise) â”€â”€> Reconciled
```

---

## ðŸ“¡ 5. REST API Catalog

The platform implements 45+ endpoints across 10 functional families. All mutation endpoints enforce session identity, RBAC decorators, parameterized SQL, and structured audit logs.

### 5.1 Authentication & User Administration
| Method | Endpoint | Allowed Roles | Description |
|---|---|---|---|
| `POST` | `/api/auth/login` | Public | Authenticates credentials and starts session |
| `GET` | `/api/auth/me` | Logged In | Returns authenticated user profile |
| `POST` | `/api/auth/logout` | Logged In | Clears session cookie |
| `POST` | `/api/auth/register` | Public | Citizen (auto-active) or Staff/NGO (pending approval) |
| `GET` | `/api/admin/pending-users` | Administrator | Lists pending account registration requests |
| `POST` | `/api/admin/approve-user` | Administrator | Approves applicant account |
| `POST` | `/api/admin/reject-user` | Administrator | Rejects applicant account |
| `POST` | `/api/admin/users/<id>/suspend`| Administrator | Suspends account with documented reason |
| `POST` | `/api/admin/users/<id>/reactivate`| Administrator | Reactivates suspended account |
| `GET` | `/api/admin/audit-logs` | Administrator | Returns immutable system security audit ledger |
| `GET` | `/api/admin/urgency-weights` | Administrator | Configures triage formula baseline and weights |

### 5.2 Incidents & Operational Zones
| Method | Endpoint | Allowed Roles | Description |
|---|---|---|---|
| `GET` | `/api/incidents` | All Authenticated | Incident summaries (filtered by role scope) |
| `POST` | `/api/incidents` | Government Official | Creates new disaster response incident |
| `GET` | `/api/incidents/<id>` | All Authenticated | Detailed incident record and operational status |
| `POST` | `/api/incidents/<id>/activate`| Government Official | Activates verified incident for response |
| `POST` | `/api/incidents/<id>/close` | Government Official | Closes incident (verifies open tasks/dispatches) |
| `GET` | `/api/zones` | All Authenticated | Operational response zones |
| `POST` | `/api/incidents/<id>/zones`| Government Official | Creates relief sector zone under incident |
| `GET` | `/api/zones/<id>/adoptions`| Govt, NGO, Admin | Lists adoption requests for a zone |
| `POST` | `/api/zones/<id>/adoptions`| NGO Coordinator | Submits NGO zone coverage adoption application |
| `POST` | `/api/adoptions/<id>/approve`| Government Official | Approves NGO zone adoption |
| `POST` | `/api/adoptions/<id>/reject` | Government Official | Rejects adoption application with reason |

### 5.3 Emergency Requests & Triage
| Method | Endpoint | Allowed Roles | Description |
|---|---|---|---|
| `GET` | `/api/requests` | All Authenticated | Priority-ranked requests (Citizen sees own only) |
| `POST` | `/api/requests` | All Authenticated | Submits emergency request; computes triage score |
| `GET` | `/api/requests/<id>` | All Authenticated | Request details (IDOR checked for Citizen) |
| `POST` | `/api/requests/<id>/verify` | Govt Official, Admin | Verifies emergency request with decision reason |
| `POST` | `/api/requests/<id>/mark-duplicate` | Govt Official, Admin | Flags request as duplicate of primary request |
| `POST` | `/api/requests/<id>/allocate` | Govt, NGO, Admin | **Atomic request allocation & reservation** |
| `GET` | `/api/requests/<id>/timeline`| All Authenticated | Audit event timeline for request |
| `POST` | `/api/requests/<id>/confirm-delivery` | Citizen, Official | Citizen confirms aid receipt with feedback |
| `POST` | `/api/requests/<id>/report-issue` | Citizen, Official | Citizen reports partial/incorrect delivery |

### 5.4 Warehouses, Stock & Ledger
| Method | Endpoint | Allowed Roles | Description |
|---|---|---|---|
| `GET` | `/api/inventory` | All Authenticated | Warehouse inventory (available = on-hand - reserved) |
| `POST` | `/api/inventory` | Govt, NGO, Admin | Adds or updates warehouse stock record |
| `GET` | `/api/resources` | All Authenticated | Standardized relief resource master catalog |
| `GET` | `/api/warehouses` | All Authenticated | Registered warehouses and staging depots |
| `GET` | `/api/inventory/transactions` | All Authenticated | Immutable double-entry stock ledger movements |

### 5.5 Donations & In-Kind Verification
| Method | Endpoint | Allowed Roles | Description |
|---|---|---|---|
| `GET` | `/api/donations` | Govt, NGO, Admin | All registered donations |
| `POST` | `/api/donations` | NGO, Official | Registers Cash (paise) or In-Kind items donation |
| `GET` | `/api/donations/<id>` | Govt, NGO, Admin | Detailed donation record and item lines |
| `POST` | `/api/donations/<id>/verify` | Govt Official, Admin | Physically verifies received cargo; credits stock |

### 5.6 Fleet, Dispatches & Delivery Proof
| Method | Endpoint | Allowed Roles | Description |
|---|---|---|---|
| `GET` | `/api/dispatches` | All Authenticated | Active dispatches (Driver sees own only) |
| `GET` | `/api/vehicles` | Govt, NGO, Driver, Admin | Vehicle fleet status and driver assignments |
| `POST` | `/api/dispatches/<id>/advance` | Driver, Govt, Admin | Legacy compatibility trip advance |
| `POST` | `/api/dispatches/<id>/start` | Assigned Driver | Starts journey; transitions to `En Route` |
| `POST` | `/api/dispatches/<id>/arrive` | Assigned Driver | Records arrival at delivery destination |
| `POST` | `/api/dispatches/<id>/route-blockage` | Assigned Driver | Reports flood road blockage with GPS |
| `POST` | `/api/dispatches/<id>/reroute` | Govt Official, Admin | Authorizes bypass route for blocked dispatch |
| `POST` | `/api/dispatches/<id>/delivery-proof` | Assigned Driver | Submits recipient proof & item delivery counts |
| `POST` | `/api/dispatches/<id>/review-delivery`| Govt Official, Admin | Finalizes proof; marks request Delivered |

### 5.7 Volunteer Roster & Field Tasks
| Method | Endpoint | Allowed Roles | Description |
|---|---|---|---|
| `GET` | `/api/volunteers` | All Authenticated | Roster of registered field volunteers |
| `POST` | `/api/volunteers` | All Authenticated | Registers volunteer skills and preferred zone |
| `GET` | `/api/volunteer-tasks` | All Authenticated | Field tasks (Volunteer sees own only) |
| `POST` | `/api/volunteer-tasks` | Govt, NGO, Admin | Creates and assigns operational field mission |
| `POST` | `/api/volunteer-tasks/<id>/accept` | Assigned Volunteer | Accepts field task mission |
| `POST` | `/api/volunteer-tasks/<id>/decline` | Assigned Volunteer | Declines task with documented reason |
| `POST` | `/api/volunteer-tasks/<id>/check-in` | Assigned Volunteer | Records GPS check-in at relief sector |
| `POST` | `/api/volunteer-tasks/<id>/submit` | Assigned Volunteer | Submits distribution counts for reconciliation |
| `POST` | `/api/field-reports` | All Authenticated | Submits ground obstacle or incident observation |

### 5.8 Shelters, Finance & Communications
| Method | Endpoint | Allowed Roles | Description |
|---|---|---|---|
| `GET` | `/api/shelters` | All Authenticated | Shelter facilities and real-time occupancy counts |
| `POST` | `/api/shelter-admissions` | Govt, NGO, Admin | Admits evacuees (enforces capacity limits) |
| `POST` | `/api/shelter-transfers` | Govt, NGO, Admin | Transfers evacuees atomically without double-counting |
| `GET` | `/api/funds` | All Authenticated | SDRF/NDRF fund utilization summary |
| `GET` | `/api/fund-budgets` | Govt, NGO, Admin | Incident relief budgets in integer paise |
| `POST` | `/api/fund-requests` | NGO Coordinator | Submits NGO grant request in integer paise |
| `POST` | `/api/fund-requests/<id>/<act>`| Govt Official, Admin | Dual-control: `approve`, `commit`, `pay`, `reconcile` |
| `GET` | `/api/advisories` | All Authenticated | Public safety advisories |
| `POST` | `/api/advisories` | Government Official | Drafts and broadcasts emergency advisory |
| `GET` | `/api/export/<dataset>.csv` | Permitted Roles | Sanitized CSV export with formula injection escaping |

---

## ðŸš€ 6. Launch & Execution Instructions

### 6.1 Prerequisites
- **Python 3.10, 3.11, or 3.12**
- Standard Python libraries (`sqlite3`, `json`, `csv`, `hashlib`, `datetime`).
- Required packages: `flask` and `pytest` (listed in `requirements.txt`).

### 6.2 1-Click Launch (Windows)
Double-click **`run.bat`** in the repository root. It validates Python, installs dependencies if missing, applies migrations, starts the server, and opens your browser at **`http://127.0.0.1:5055`**.

### 6.3 PowerShell / Terminal Launch
```powershell
# 1. Navigate to directory
cd c:\Users\ACER\Desktop\Codex\DRRAS-Flask

# 2. Install dependencies
pip install -r requirements.txt

# 3. Apply schema migrations & seed demo scenario (Idempotent)
python seed_demo.py

# 4. Start the application
python app.py
```
Visit **`http://127.0.0.1:5055`** in Chrome, Edge, or Firefox.

---

## 7. Automated Test Suite and Showcase Validation

The project includes regression tests for authorization, simultaneous request claims, dispatches, inventory, finance, shelters, volunteer tasks, and the fictional showcase workflows.

Run in PowerShell:

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
```

The current run results are recorded in `IMPLEMENTATION_PROGRESS.md` and the account/table details are in `docs/ACCOUNT_COVERAGE.md` and `docs/DEMO_DATASET.md`. The included `drras.db` is the packaged demonstration database. The original database was retained in the workspace outside this output copy.
## âš ï¸ 8. Honest Operational Disclosures & Limitations

1. **Academic & Simulation Nature**: DRRAS is a fully functional engineering prototype designed for disaster management research, academic demonstration, and operational scenario simulation. It is not certified for live emergency government dispatch without field hardware integration.
2. **Local Simulation Adapters**:
   - **GPS Coordinates**: Picked via Leaflet.js / OpenStreetMap coordinates; no proprietary hardware transponders are simulated.
   - **SMS / Push Broadcast**: Emergency advisories are stored in SQLite and displayed reactively in user dashboards; telecommunication SMS gateways (e.g. Twilio/CDAC) are simulated locally.
   - **Financial Disbursements**: Fund transactions and payments are tracked in double-entry integer paise ledgers; no live bank APIs or payment gateways are accessed.
3. **Database Concurrency**: The system utilizes SQLite with WAL mode (`PRAGMA journal_mode = WAL`) and a 10-second busy timeout. For high-concurrency multi-thousand node deployments, PostgreSQL is recommended.



