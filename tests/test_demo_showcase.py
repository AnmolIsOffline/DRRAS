import sqlite3

from database import get_db
from seed_demo import seed_demo_data


def _count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_showcase_seed_is_repeat_safe_and_keeps_all_existing_accounts():
    conn = get_db()
    tables = ('users','volunteers','shelters','emergency_requests','response_assignments',
              'dispatches','delivery_proofs','volunteer_tasks','field_reports',
              'shelter_transfers','notifications','public_advisories')
    before = {table: _count(conn, table) for table in tables}
    accounts_before = [tuple(r) for r in conn.execute(
        "SELECT id,email,role,status,organization_id FROM users ORDER BY id")]
    conn.close()

    seed_demo_data()
    conn = get_db()
    after = {table: _count(conn, table) for table in tables}
    accounts_after = [tuple(r) for r in conn.execute(
        "SELECT id,email,role,status,organization_id FROM users ORDER BY id")]
    assert after == before
    assert accounts_after == accounts_before
    assert _count(conn, 'users') == len(accounts_before)
    assert _count(conn, 'response_assignments') == before['response_assignments']
    assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
    conn.close()


def test_active_roster_history_references_existing_accounts():
    conn = get_db()
    assert conn.execute("SELECT COUNT(*) FROM emergency_requests r LEFT JOIN users u ON u.id=r.requester_user_id WHERE r.requester_user_id IS NOT NULL AND u.id IS NULL").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM volunteers v LEFT JOIN users u ON u.id=v.user_id WHERE v.user_id IS NOT NULL AND u.id IS NULL").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM dispatches d LEFT JOIN users u ON u.id=d.driver_user_id WHERE d.driver_user_id IS NOT NULL AND u.id IS NULL").fetchone()[0] == 0
    conn.close()


def test_dashboard_uses_scoped_live_request_trend(client):
    login = client.post('/api/auth/login', json={'email':'citizen@drras.in','password':'citizen123'})
    assert login.status_code == 200
    response = client.get('/api/dashboard')
    assert response.status_code == 200
    data = response.get_json()
    conn = get_db()
    user_id = login.get_json()['id']
    own_open = conn.execute("SELECT COUNT(*) FROM emergency_requests WHERE requester_user_id=? AND status NOT IN ('Delivered','Closed','Rejected','Duplicate')",(user_id,)).fetchone()[0]
    assert data['openRequests'] == own_open
    assert len(data['trend']) == 7
    assert all(isinstance(point['v'], int) and point['v'] >= 0 for point in data['trend'])
    conn.close()


def test_ngo_views_include_its_assigned_requests_and_only_owned_stock(client):
    login = client.post('/api/auth/login', json={'email':'ngo@drras.in','password':'ngo123'})
    assert login.status_code == 200
    request_ids = {r['id'] for r in client.get('/api/requests').get_json()}
    assert request_ids.intersection({'REQ-SHOW-NGO1-002','REQ-SHOW-NGO1-003'})
    ledger = client.get('/api/inventory/ledger')
    assert ledger.status_code == 200
    assert all(row['warehouse_name'] != 'Khalsa Aid Foundation Relief Warehouse' for row in ledger.get_json())


def test_public_advisory_api_returns_published_current_records_only(client):
    response = client.get('/api/advisories')
    assert response.status_code == 200
    rows = response.get_json()
    assert rows
    assert all(row['status'] == 'Published' for row in rows)
    assert all(row['valid_until'] is None or row['valid_until'] > '2026-10-27 00:00:00' for row in rows)


def test_ngo2_coverage_uses_approved_adoption_and_owner_matched_response(client):
    conn=get_db()
    adoption=conn.execute("SELECT * FROM zone_adoptions WHERE organization_id=2 AND zone_id='Z-03'").fetchone()
    assert adoption['status']=='Approved'
    coordinator=conn.execute("SELECT u.id,u.name FROM users u JOIN organization_memberships m ON m.user_id=u.id WHERE u.role='NGO Coordinator' AND m.organization_id=2 AND m.membership_role='Coordinator' AND m.status='Active' ORDER BY u.id LIMIT 1").fetchone()
    assert adoption['requested_by_user_id']==coordinator['id']
    assert adoption['reviewed_by_user_id']==2
    assert conn.execute("SELECT status FROM organizations WHERE id=3").fetchone()['status']=='Approved'
    req=conn.execute("SELECT * FROM emergency_requests WHERE id='REQ-SHOW-NGO2-001'").fetchone()
    assert req and req['requester_user_id'] is not None and req['zone_id']=='Z-03'
    assignment=conn.execute("SELECT * FROM response_assignments WHERE request_id=? AND owner_type='ngo' AND organization_id=2",(req['id'],)).fetchone()
    dispatch=conn.execute("SELECT * FROM dispatches WHERE request_id=? AND owner_type='ngo' AND owner_organization_id=2",(req['id'],)).fetchone()
    assert assignment and dispatch and dispatch['status']=='Delivered'
    assert assignment['dispatch_id']==dispatch['id']
    assert conn.execute("SELECT 1 FROM volunteers WHERE id=? AND owner_type='ngo' AND organization_id=2 AND verified=1",(assignment['volunteer_id'],)).fetchone()
    assert conn.execute("SELECT 1 FROM ngo_personnel_approvals WHERE user_id=? AND organization_id=2 AND personnel_type='Driver' AND decision='Approved'",(assignment['driver_user_id'],)).fetchone()
    assert conn.execute("SELECT 1 FROM vehicles WHERE id=? AND owner_type='ngo' AND owner_organization_id=2",(assignment['vehicle_id'],)).fetchone()
    assert conn.execute("SELECT 1 FROM delivery_proofs WHERE dispatch_id=? AND request_id=? AND status='Verified'",(dispatch['id'],req['id'])).fetchone()
    assert conn.execute("SELECT 1 FROM request_events WHERE request_id=?",(req['id'],)).fetchone()
    conn.close()
    with client.session_transaction() as sess:
        sess.update(user_id=coordinator['id'],role='NGO Coordinator',name=coordinator['name'])
    requests={r['id']:r for r in client.get('/api/requests').get_json()}
    assert 'REQ-SHOW-NGO2-001' in requests
    assert 'REQ-SHOW-NGO1-002' in requests
    assert requests['REQ-SHOW-NGO1-002']['response_owner_type'] is None
    assert requests['REQ-SHOW-NGO1-002']['ngo_assignment_eligible']==1


def test_account_coverage_report_resolves_coordinator_membership():
    import showcase_seed
    from pathlib import Path
    conn=get_db()
    user_id,email,coordinator=conn.execute("SELECT u.id,u.email,COALESCE(u.organization_id,(SELECT organization_id FROM organization_memberships WHERE user_id=u.id AND membership_role='Coordinator' AND status='Active' ORDER BY id LIMIT 1)) FROM users u JOIN organization_memberships m ON m.user_id=u.id WHERE u.role='NGO Coordinator' AND m.organization_id=1 AND m.membership_role='Coordinator' AND m.status='Active' ORDER BY u.id LIMIT 1").fetchone()
    org_name=conn.execute("SELECT name FROM organizations WHERE id=?",(coordinator,)).fetchone()[0]
    showcase_seed.write_reports(conn)
    conn.close()
    report=(Path(__file__).resolve().parents[1]/'docs'/'ACCOUNT_COVERAGE.md').read_text(encoding='utf-8')
    assert f'| {user_id} | {email} | NGO Coordinator | ACTIVE | {org_name} |' in report
    assert 'All three named showcase NGOs are approved by the local demo seed' in report
    assert 'All three named showcase NGOs are approved by the local demo seed' in report
