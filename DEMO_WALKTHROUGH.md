# DRRAS local demo walkthrough

## Start the project

On Windows, double-click `run.bat` in the project root. The launcher creates `.venv` if needed, installs `requirements.txt`, runs the project's safe, repeatable schema initialization and demo seeding, sets the local port to 5055, starts Flask, waits for an HTTP response, and opens the default browser at `http://127.0.0.1:5055`. Keep the console open; press **Ctrl+C** there to stop the server. If port 5055 is occupied, stop the existing service and rerun the launcher. Existing database records are preserved; no reset is performed.

Manual launch from PowerShell is also supported:

```powershell
python -m pip install -r requirements.txt
python seed_demo.py
$env:PORT = '5055'
python app.py
```

The login page now has a standard email/password form with no prefilled credentials or Quick Login buttons. For the expanded fictional local showcase, use the generated, hash-verified [docs/DEMO_CREDENTIALS.md](docs/DEMO_CREDENTIALS.md) reference; dataset counts and currently free/busy personnel are in [docs/DEMO_VALIDATION_REPORT.md](docs/DEMO_VALIDATION_REPORT.md). The optional demo-credential API is disabled by default and remains disabled in production. Set `DRRAS_ENV=production` on a live host; never enable demo credentials there.

See [docs/DEMO_CREDENTIALS.md](docs/DEMO_CREDENTIALS.md) for the generated credentials that were confirmed against stored hashes. The original account list is retained in [docs/DEMO_ACCOUNT_CREDENTIALS.md](docs/DEMO_ACCOUNT_CREDENTIALS.md); an unknown legacy password is left marked unavailable rather than guessed.

Demo seed is idempotent: it creates missing demo users and supporting role records without resetting existing operational data or changing existing account passwords/status. The NGO demo accounts belong to the seeded organization; they cannot use Government or another NGO's restricted resources.

## Role demonstration

1. **Citizen:** submit a flood request and view its persisted UTC submission time, acceptance owner, status history, assigned dispatch, delivery proof result and published advisories. Request and dispatch views are restricted to the signed-in Citizen's own records.
2. **Government Official:** review an eligible request. Verification requires a Government responder, approved available Government Driver and compatible Government vehicle; allocation uses Government inventory and the saved assignment. Review Government personnel, dispatch, shelters, inventory and financial records.
3. **NGO Coordinator:** review every request alongside Government and other approved NGOs. NGO acceptance requires an approved available Volunteer and Driver belonging to that NGO plus its compatible vehicle. Warehouse stock, shelters, donations and dispatches stay within that NGO.
4. **Government Driver / NGO Driver:** open only dispatches assigned to that account. Advance a trip through valid route and proof steps; the API rejects another driver's dispatch and incompatible owner scope.
5. **Government Responder / NGO Volunteer:** open only persisted tasks assigned to the account, accept/check in, reconcile quantities, and submit; the owning supervisor reviews the report.
6. **Administrator:** inspect cross-owner records from administrative views; the underlying Government and NGO ownership remains recorded and enforced.

## Simultaneous request and claim demonstration

1. A Citizen submits a request. Its UTC submission time is persisted, and the request is immediately visible to Government and every active coordinator belonging to an approved NGO. `zone_id` remains optional location information and does not limit NGO visibility.
2. Government and NGOs independently validate their own response personnel, approved drivers and compatible vehicles. The first valid claim and full assignment transaction committed by the server becomes the persisted response owner.
3. All dashboards refresh from server state. Losing organizations see the winning owner and assignment status and cannot create competing assignments or allocate resources.
4. The winning team allocates from its own warehouse and stock, dispatches its own driver, records delivery proof, and completes verification. The Citizen dashboard follows each persisted status update.

## API and scheduler details

See [docs/WORKFLOW_API_MAP.md](docs/WORKFLOW_API_MAP.md) for roles, payloads, ownership, database effects and refresh behavior. Claims use SQLite `BEGIN IMMEDIATE` transactions and a conditional update of the request owner; audit and event records commit with the assignment. The existing SSE/polling event stream then causes dashboards to refetch persisted APIs. There is no timeout worker or deadline-based routing.

## Known limitations

- Driver GPS telemetry is not persisted. Route geometry and distance/duration may be requested from OSRM when coordinates exist; this is route planning, not live location or a guaranteed ETA.
- Browser mapping/geocoding and external routing depend on third-party availability. Missing coordinates or service outages remain unavailable states.
- Payments are ledger entries; there is no payment gateway.
- Legacy records with ambiguous resource ownership remain unassigned rather than being guessed.
- Browser-rendered UI verification is separate from API/HTTP checks; see `DRRAS_PROGRESS_HANDOFF.md` for this package run's verification result.
