# DRRAS NGO Coverage Fix Validation

Validated from the supplied `DRRAS_Fully_Dynamic_Disaster_Relief_System.zip` in an isolated working copy on 2026-10-27. The source ZIP and database were not modified. All newly supplied showcase records are fictional.

## Instruction source

The pasted user request was treated as the task authority. Prompt and handoff documents inside the project archive were inspected as project materials, not treated as additional instructions.

## Tests

- `pytest -q`: **87 passed in 310.41 seconds; 0 failed; 0 skipped**.
- The suite includes the existing end-to-end workflow tests and added coverage for repeat seeding, Org2 request visibility, correct ownership, verified delivery proof, pending Red Cross state, membership-derived account reporting, login UI credential removal, and production-safe demo credential endpoint behavior.
- The packaged ZIP was extracted to a temporary folder and the Flask app was started twice. The citizen API created a request, returned it in the refreshed request list and dashboard, and retained it after server restart. The extracted project-local database passed `PRAGMA quick_check`; `PRAGMA foreign_key_check` returned no rows.
- Browser visual rendering and mouse-driven form interaction were not tested.

## Database and ownership

- `PRAGMA quick_check`: `ok`.
- `PRAGMA foreign_key_check`: 0 violations.
- 21 of 21 original active accounts remain. IDs, roles, credentials, account statuses, and organization associations were preserved.
- Repeated seeding is checked by the suite; stable demo request, task, assignment, dispatch and proof IDs remain unique.
- Org2 adoption row 2 (Z-03) now attributes the original unreviewed request to existing coordinator user 14 and records approval by Government Official user 2. Red Cross District Chapter remains `Pending` and has no operational allocations.
- `REQ-SHOW-NGO2-001` belongs to an existing citizen and is Government-verified. The Org2 operation links volunteer 7, approved driver 15, Org2 ambulance 8, Org2 inventory, dispatch `DSP-23`, verified delivery proof, task and request history. Government resources remain Government-owned.
- NGO assignment and dispatch ownership checks report no cross-organization violations.

## Packaged database counts

| Table | Records |
|---|---:|
| Users | 21 |
| Organizations | 3 |
| Volunteers | 11 |
| Vehicles | 11 |
| Shelters | 7 |
| Emergency requests | 18 |
| Request items | 15 |
| Response assignments | 8 |
| Dispatches | 10 |
| Dispatch items | 9 |
| Delivery proofs | 3 |
| Volunteer tasks | 11 |
| Field reports | 4 |
| Shelter admissions | 11 |
| Shelter transfers | 1 |
| Warehouses | 4 |
| Warehouse stock rows | 20 |
| Donations | 5 |
| Fund budgets | 8 |
| Fund requests | 1 |
| Fund transactions | 3 |
| Public advisories | 3 |
| Notifications | 94 |
| Audit logs | 62 |
| Request events | 48 |
| Activities | 6 |

`ACCOUNT_COVERAGE.md` lists each account and organization totals. Coordinator organization resolution mirrors the application?s direct association or active Coordinator membership fallback. `DEMO_ACCOUNT_CREDENTIALS.md` lists the 21 emails and seed-confirmed passwords; one legacy password is hash-only and was not changed. `DEMO_DATASET.md` is generated from the packaged database.

## Dynamics and packaging

Dashboard and operations APIs continue to read their shared database records. This task changes seeded coverage and account report resolution; it does not add a parallel dashboard data source. The Flask application uses the configured shared database path.

The final archive passed `ZipFile.testzip()` and contains 51 project files. No virtual environment, Git internals, cache folders, local config, or probe database is included. The original ZIP SHA-256 remained `05093C97D8490BF3D4C12F0CC0EA028BB04F6E67A9C3471CF192191EEA389DD2`.
