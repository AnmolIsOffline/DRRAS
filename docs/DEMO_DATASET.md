# Fictional DRRAS Demonstration Dataset

This local showcase describes a fictional Sutlej Basin flood response in Demo District. Names, locations, quantities, requests, deliveries, donations and fund entries are demonstration content; none represent real emergencies or payments. Existing accounts, credentials, statuses and organization associations are preserved.

## Database completeness check

The packaged SQLite database has 44 application tables; 1 are empty. Required user fields (email, password hash, name, role and status) are blank for 0 accounts.
Empty tables: shelter_transfers.

## Current record counts

| Table | Records |
|---|---:|
| `users` | 142 |
| `organizations` | 3 |
| `incidents` | 1 |
| `zones` | 3 |
| `emergency_requests` | 73 |
| `request_items` | 10 |
| `response_assignments` | 1 |
| `dispatches` | 17 |
| `dispatch_items` | 3 |
| `delivery_proofs` | 2 |
| `volunteer_tasks` | 52 |
| `field_reports` | 16 |
| `shelters` | 6 |
| `shelter_admissions` | 2 |
| `shelter_transfers` | 0 |
| `warehouses` | 4 |
| `resources` | 5 |
| `warehouse_stock` | 20 |
| `inventory_reservations` | 1 |
| `inventory_reservation_items` | 2 |
| `inventory_transactions` | 5 |
| `donations` | 3 |
| `donation_items` | 2 |
| `fund_budgets` | 4 |
| `fund_requests` | 1 |
| `fund_transactions` | 3 |
| `public_advisories` | 3 |
| `notifications` | 152 |
| `audit_logs` | 14 |
| `request_events` | 71 |

## Ownership and state notes

- Government and each NGO retain separate warehouses, stock, vehicles, shelters, volunteer rosters, assignments and dispatch ownership.
- Punjab Relief Foundation and Khalsa Aid Foundation retain separate resources, assignments and dispatches. The Org2 Z-03 adoption is approved by the existing Government Official account; one verified citizen request is linked to its own volunteer, approved driver, compatible vehicle, stock allocation, dispatch, delivery proof and field activity.
- Red Cross District Chapter is `Approved` and has its own warehouse stock, shelter, vehicles, approved staff and historical activity.
- The dataset includes a submitted proof awaiting review, a verified proof for a completed dispatch, four field observations, and a completed household shelter transfer.
- Government driver dispatches already present in the database retain their existing statuses. The showcase backfills matching response-assignment history without changing their resource owners.
- Running `python seed_demo.py` repeatedly preserves stable showcase IDs and avoids adding duplicate account, roster, shelter, request, dispatch, assignment, task, proof, report, notification or advisory rows.
