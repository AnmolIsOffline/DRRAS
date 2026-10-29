from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import os

import database
from conftest import verify_request_with_team


def _new_request(client, zone='Z-01'):
    client.post('/api/auth/login', json={'email': 'citizen@drras.in', 'password': 'citizen123'})
    response = client.post('/api/requests', json={
        'name': 'Demo Citizen',
        'area': 'Focal Point, Ward 8',
        'address': 'Community Lane 12',
        'need': 'Food ration kits and drinking water',
        'people': 4,
        'incident_id': 'INC-2026-FLOOD',
        'zone_id': zone,
    })
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def _team_from_options(options):
    return {
        'volunteer_id': next(v['id'] for v in options['volunteers'] if v['available']),
        'driver_user_id': next(d['id'] for d in options['drivers'] if d['available']),
        'vehicle_id': next(v['id'] for v in options['vehicles'] if v['available']),
        'notes': 'Food and water response team',
    }


def _login(client, email):
    response = client.post('/api/auth/login', json={'email': email, 'password': 'ngo123'})
    assert response.status_code == 200, response.get_json()


def test_new_request_is_utc_and_immediately_visible_to_government_and_all_ngos(client):
    created = _new_request(client, zone='Z-01')
    timestamp = datetime.fromisoformat(created['created_at'])
    assert timestamp.utcoffset() == timedelta(0)
    assert created['response_owner_type'] is None

    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    government_request = next(r for r in client.get('/api/requests').get_json() if r['id'] == created['id'])
    assert government_request['verification_status'] == 'Unverified'
    assert government_request['response_owner_type'] is None

    _login(client, 'ngo@drras.in')
    ngo_one_request = next(r for r in client.get('/api/requests').get_json() if r['id'] == created['id'])
    assert ngo_one_request['ngo_assignment_eligible'] == 1
    assert ngo_one_request['zone_id'] == 'Z-01'
    options = client.get(f"/api/ngo/response-options/{created['id']}").get_json()
    assert options['eligible'] is True

    _login(client, 'contact@khalsaaid.org')
    ngo_two_request = next(r for r in client.get('/api/requests').get_json() if r['id'] == created['id'])
    assert ngo_two_request['ngo_assignment_eligible'] == 1

    conn = database.get_db()
    try:
        notification_count = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE entity_type='emergency_requests' AND entity_id=?",
            (created['id'],),
        ).fetchone()[0]
        assert notification_count >= 3
    finally:
        conn.close()


def test_government_claim_wins_and_removes_request_from_ngo_actions(client):
    created = _new_request(client)
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    accepted = verify_request_with_team(client, created['id'])
    assert accepted.status_code == 200, accepted.get_json()
    assert accepted.get_json()['response_owner_type'] == 'government'

    _login(client, 'ngo@drras.in')
    ngo_request = next(r for r in client.get('/api/requests').get_json() if r['id'] == created['id'])
    assert ngo_request['response_owner_type'] == 'government'
    assert ngo_request['ngo_assignment_eligible'] == 0
    options = client.get(f"/api/ngo/response-options/{created['id']}").get_json()
    assert options['eligible'] is False
    loser = client.post(f"/api/requests/{created['id']}/ngo-assign", json=_team_from_options(options))
    assert loser.status_code == 409
    assert loser.get_json()['code'] == 'REQUEST_CLAIMED'
    assert client.post(f"/api/requests/{created['id']}/allocate", json={}).status_code == 409

    conn = database.get_db()
    try:
        assert conn.execute("SELECT COUNT(*) FROM response_assignments WHERE request_id=?", (created['id'],)).fetchone()[0] == 1
    finally:
        conn.close()


def test_ngo_can_claim_unverified_request_and_other_dashboards_show_winner(client):
    created = _new_request(client, zone='Z-01')
    _login(client, 'ngo@drras.in')
    options = client.get(f"/api/ngo/response-options/{created['id']}").get_json()
    assert options['eligible'] is True
    accepted = client.post(f"/api/requests/{created['id']}/ngo-assign", json=_team_from_options(options))
    assert accepted.status_code == 201, accepted.get_json()

    government = client.application.test_client()
    government.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    government_request = next(r for r in government.get('/api/requests').get_json() if r['id'] == created['id'])
    assert government_request['response_owner_type'] == 'ngo'
    assert government_request['response_organization_name'] == 'Punjab Relief Foundation'
    assert government_request['response_assignment_status'] == 'Assigned'
    assert government.get(f"/api/government/response-options/{created['id']}").get_json()['eligible'] is False
    competing_gov_claim = verify_request_with_team(government, created['id'])
    assert competing_gov_claim.status_code == 409
    assert competing_gov_claim.get_json()['code'] == 'REQUEST_CLAIMED'
    assert government.post(f"/api/requests/{created['id']}/allocate", json={}).status_code == 409

    _login(client, 'contact@khalsaaid.org')
    second_ngo_request = next(r for r in client.get('/api/requests').get_json() if r['id'] == created['id'])
    assert second_ngo_request['response_owner_type'] == 'ngo'
    assert second_ngo_request['response_organization_name'] == 'Punjab Relief Foundation'
    assert second_ngo_request['ngo_assignment_eligible'] == 0
    second_options = client.get(f"/api/ngo/response-options/{created['id']}").get_json()
    assert second_options['eligible'] is False
    competing_ngo_claim = client.post(
        f"/api/requests/{created['id']}/ngo-assign", json=_team_from_options(second_options)
    )
    assert competing_ngo_claim.status_code == 409

    client.post('/api/auth/login', json={'email': 'ngo@drras.in', 'password': 'ngo123'})
    allocated = client.post(f"/api/requests/{created['id']}/allocate", json={})
    assert allocated.status_code == 200, allocated.get_json()
    dispatch = next(d for d in client.get('/api/dispatches').get_json() if d['request_id'] == created['id'])
    assert dispatch['owner_type'] == 'ngo'
    assert dispatch['owner_organization_id'] == 1


def test_failed_ngo_assignment_does_not_claim_or_reserve_request(client):
    created = _new_request(client)
    _login(client, 'ngo@drras.in')
    failed = client.post(f"/api/requests/{created['id']}/ngo-assign", json={})
    assert failed.status_code == 400
    assert failed.get_json()['code'] == 'ASSIGNMENT_REQUIRED'

    conn = database.get_db()
    try:
        row = conn.execute("SELECT response_owner_type FROM emergency_requests WHERE id=?", (created['id'],)).fetchone()
        assert row['response_owner_type'] is None
        assert conn.execute("SELECT COUNT(*) FROM response_assignments WHERE request_id=?", (created['id'],)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM volunteer_tasks WHERE request_id=?", (created['id'],)).fetchone()[0] == 0
    finally:
        conn.close()

    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    success = verify_request_with_team(client, created['id'])
    assert success.status_code == 200, success.get_json()


def test_concurrent_ngo_claims_commit_exactly_one_assignment(client):
    created = _new_request(client)
    clients = [client.application.test_client(), client.application.test_client()]
    emails = ['ngo@drras.in', 'contact@khalsaaid.org']
    payloads = []
    for candidate, email in zip(clients, emails):
        _login(candidate, email)
        options = candidate.get(f"/api/ngo/response-options/{created['id']}").get_json()
        assert options['eligible'] is True
        payloads.append(_team_from_options(options))

    def claim(args):
        candidate, payload = args
        return candidate.post(f"/api/requests/{created['id']}/ngo-assign", json=payload).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(claim, zip(clients, payloads)))

    assert sorted(statuses) == [201, 409]
    conn = database.get_db()
    try:
        assert conn.execute("SELECT COUNT(*) FROM response_assignments WHERE request_id=?", (created['id'],)).fetchone()[0] == 1
        claim = conn.execute("SELECT response_owner_type,response_organization_id FROM emergency_requests WHERE id=?", (created['id'],)).fetchone()
        assert claim['response_owner_type'] == 'ngo'
        assert claim['response_organization_id'] in (1, 2)
    finally:
        conn.close()


def test_eight_demo_accounts_authenticate_with_separate_ownership(client):
    old_demo_mode = os.environ.get('DRRAS_DEMO_MODE')
    os.environ['DRRAS_DEMO_MODE'] = 'true'
    accounts = client.get('/api/demo-accounts').get_json()
    assert len(accounts) == 8
    expected = {
        'Administrator': ('Administrator', None),
        'Government Official': ('Government Official', None),
        'NGO Coordinator': ('NGO Coordinator', 1),
        'Citizen': ('Citizen', None),
        'Government Driver': ('Driver', None),
        'NGO Driver': ('Driver', 1),
        'Government Volunteer/Responder': ('Volunteer', None),
        'NGO Volunteer': ('Volunteer', 1),
    }
    assert {a['label'] for a in accounts} == set(expected)
    for account in accounts:
        login = client.post('/api/auth/login', json={'email': account['email'], 'password': account['password']})
        assert login.status_code == 200, (account, login.get_json())
        body = login.get_json()
        assert (body['role'], body['organization_id']) == expected[account['label']]
        assert client.get('/api/auth/me').status_code == 200
        assert client.get('/api/dashboard').status_code == 200
        assert client.get('/api/dispatches').status_code == 200
        if body['role'] == 'Volunteer':
            assert client.get('/api/volunteer-tasks').status_code == 200
        client.post('/api/auth/logout')
    old_environment = os.environ.get('DRRAS_ENV')
    os.environ['DRRAS_ENV'] = 'production'
    try:
        assert client.get('/api/demo-accounts').get_json() == []
    finally:
        if old_environment is None:
            os.environ.pop('DRRAS_ENV', None)
        else:
            os.environ['DRRAS_ENV'] = old_environment
        if old_demo_mode is None:
            os.environ.pop('DRRAS_DEMO_MODE', None)
        else:
            os.environ['DRRAS_DEMO_MODE'] = old_demo_mode


def test_login_frontend_has_no_demo_accounts_or_prefilled_credentials():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')
    assert '/api/demo-accounts' not in source
    assert 'demo-chip-btn' not in source
    assert 'value="admin@drras.in"' not in source
    assert 'value="admin123"' not in source


def test_demo_credentials_endpoint_is_opt_in_and_never_enabled_in_production(client):
    old_mode = os.environ.pop('DRRAS_DEMO_MODE', None)
    old_environment = os.environ.pop('DRRAS_ENV', None)
    try:
        assert client.get('/api/demo-accounts').get_json() == []
        os.environ['DRRAS_DEMO_MODE'] = 'true'
        assert len(client.get('/api/demo-accounts').get_json()) == 8
        os.environ['DRRAS_ENV'] = 'production'
        assert client.get('/api/demo-accounts').get_json() == []
    finally:
        os.environ.pop('DRRAS_DEMO_MODE', None)
        os.environ.pop('DRRAS_ENV', None)
        if old_mode is not None:
            os.environ['DRRAS_DEMO_MODE'] = old_mode
        if old_environment is not None:
            os.environ['DRRAS_ENV'] = old_environment


def test_demo_seed_preserves_existing_account_state_and_operational_rows(client):
    from seed_demo import seed_demo_data

    conn = database.get_db()
    try:
        account = conn.execute("SELECT u.id FROM users u JOIN ngo_personnel_approvals a ON a.user_id=u.id WHERE u.role='Volunteer' AND a.organization_id=1 AND a.personnel_type='Volunteer' AND a.decision='Approved' ORDER BY u.id LIMIT 1").fetchone()
        assert account
        conn.execute("UPDATE users SET status='SUSPENDED' WHERE id=?", (account['id'],))
        existing = conn.execute("SELECT COUNT(*) FROM vehicles WHERE owner_type='ngo' AND owner_organization_id=1").fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    seed_demo_data()
    conn = database.get_db()
    try:
        assert conn.execute("SELECT status FROM users WHERE id=?", (account['id'],)).fetchone()['status'] == 'SUSPENDED'
        assert conn.execute("SELECT COUNT(*) FROM vehicles WHERE owner_type='ngo' AND owner_organization_id=1").fetchone()[0] == existing
        assert conn.execute("SELECT COUNT(*) FROM users u JOIN ngo_personnel_approvals a ON a.user_id=u.id WHERE u.role='Volunteer' AND a.organization_id=1 AND a.personnel_type='Volunteer' AND a.decision='Approved'").fetchone()[0] >= 8
    finally:
        conn.close()
