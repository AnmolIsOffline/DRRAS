# Expanded demo seed validation report

Generated from the packaged SQLite database by `seed_demo.py`. All counts are read from persisted records.

## Active accounts by role

| Role | Count |
|---|---:|
| Administrator | 3 |
| Citizen | 33 |
| Driver | 55 |
| Government Official | 6 |
| NGO Coordinator | 4 |
| Volunteer | 56 |

## Availability (derived from persisted active assignments/tasks)

| Category | Approved total | Available | Busy |
|---|---:|---:|---:|
| Government Drivers | 24 | 20 | 4 |
| Government Responders / Volunteers | 25 | 25 | 0 |
| NGO Drivers | 30 | 28 | 2 |
| NGO Volunteers | 31 | 26 | 5 |

## NGO personnel distribution

| NGO | Approved Drivers | Available Drivers | Approved Volunteers | Available Volunteers |
|---|---:|---:|---:|---:|
| Punjab Relief Coalition | 10 | 8 | 11 | 6 |
| Khalsa Aid Foundation | 10 | 10 | 10 | 10 |
| Red Cross District Chapter | 10 | 10 | 10 | 10 |

## Vehicle fleet and stock

| Owner | Vehicles | Genuinely available | Busy / unavailable | Cargo trucks (250+ units) | Ambulances | Rescue units | Relief vans | Usable stock units |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Government | 29 | 26 | 3 | 21 | 3 | 2 | 2 | 12372 |
| Punjab Relief Coalition | 29 | 27 | 2 | 20 | 3 | 3 | 1 | 1065 |
| Khalsa Aid Foundation | 28 | 28 | 0 | 20 | 3 | 3 | 1 | 585 |
| Red Cross District Chapter | 28 | 28 | 0 | 20 | 3 | 3 | 1 | 600 |

## Vehicle data integrity

- Vehicles missing registration numbers: **0**.
- Duplicate registration numbers: **0**.
- Vehicle availability is calculated from persisted status, driver reservation, active dispatches and active response assignments.

## Automated workflow validation

Run `python -m pytest -q` to record the current test result. The seed process does not claim that application workflow tests have passed.
