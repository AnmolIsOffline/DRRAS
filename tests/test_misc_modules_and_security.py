import pytest

def test_shelters_and_funds(client):
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    # Create a separately owned Government shelter.
    gov_shelter=client.post('/api/shelters',json={'name':'Test Government Shelter','address':'North Camp','district':'Demo District','capacity':120,'occupants':3})
    assert gov_shelter.status_code==201 and gov_shelter.get_json()['owner_type']=='government'
    client.post('/api/auth/login',json={'email':'ngo@drras.in','password':'ngo123'})
    ngo_shelter=client.post('/api/shelters',json={'name':'Test NGO Shelter','address':'South Camp','district':'Demo District','capacity':80,'occupants':2})
    assert ngo_shelter.status_code==201 and ngo_shelter.get_json()['owner_type']=='ngo' and ngo_shelter.get_json()['owner_organization_id']==1
    assert all(s['owner_type']=='ngo' and s['owner_organization_id']==1 for s in client.get('/api/shelters').get_json())
    client.post('/api/auth/login',json={'email':'official@drras.in','password':'official123'})
    assert all(s['owner_type']=='government' and s['owner_organization_id'] is None for s in client.get('/api/shelters').get_json())
    client.post('/api/auth/login',json={'email':'admin@drras.in','password':'admin123'})
    res_s = client.get('/api/shelters')
    assert res_s.status_code == 200
    shelters = res_s.get_json()
    assert len(shelters) >= 3
    for s in shelters:
        assert s['occupants'] >= 0
        assert s['capacity'] > 0
        assert s['occupants'] <= s['capacity'] * 1.5  # reasonable sanity bound

    # Funds
    res_f = client.get('/api/funds')
    assert res_f.status_code == 200
    funds = res_f.get_json()
    assert 'categories' in funds
    assert sum(c['percentage'] for c in funds['categories']) == 100

def test_workspace_activity(client):
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})

    # Create workspace activity
    res_post = client.post('/api/workspace-activity', json={
        'key': 'test_workspace',
        'title': 'Test Operation Note',
        'details': 'Relief materials safely delivered to warehouse 3.'
    })
    assert res_post.status_code == 200

    # Retrieve workspace activities
    res_get = client.get('/api/workspace-activity?key=test_workspace')
    assert res_get.status_code == 200
    activities = res_get.get_json()
    assert len(activities) >= 1
    assert activities[0]['title'] == 'Test Operation Note'

def test_dashboard_statistics_data_consistency(client):
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    res_dash = client.get('/api/dashboard')
    assert res_dash.status_code == 200
    dash = res_dash.get_json()

    # Compare open requests count against actual requests in DB
    all_reqs = client.get('/api/requests').get_json()
    open_reqs_actual = len([r for r in all_reqs if r['status'] != 'Delivered'])
    assert dash['openRequests'] == open_reqs_actual

    # Compare volunteer count against actual volunteers in DB
    all_vols = client.get('/api/volunteers').get_json()
    assert dash['activeVolunteers'] == len(all_vols)

def test_csv_exports_and_injection_prevention(client):
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})

    # Insert a malicious request containing Excel formula injection payloads
    client.post('/api/requests', json={
        'name': '=CMD|"/C calc"!A0',
        'area': '+SUM(1,2)',
        'address': '-2+3+cmd',
        'need': '@SUM(A1:A10)',
        'people': 2
    })

    # Test requests CSV export
    res_csv = client.get('/api/export/requests.csv')
    assert res_csv.status_code == 200
    assert 'text/csv' in res_csv.content_type
    content = res_csv.data.decode('utf-8')

    # Ensure dangerous formula characters at the start of cells are escaped with a prepended single quote (')
    lines = content.splitlines()
    header = lines[0]
    assert 'Request ID' in header
    
    # Check that cells starting with '=', '+', '-', '@' have been safely escaped
    calc_line = next((l for l in lines if 'calc' in l), None)
    assert calc_line is not None
    assert "'=CMD" in calc_line or "\\=CMD" in calc_line

    # Test other datasets
    for ds in ['inventory', 'volunteers', 'dispatches']:
        r = client.get(f'/api/export/{ds}.csv')
        assert r.status_code == 200
        assert 'text/csv' in r.content_type

def test_csv_export_unauthenticated_access(client):
    # Log out
    client.post('/api/auth/logout')
    res = client.get('/api/export/requests.csv')
    # Sensitive CSV exports should require authentication
    assert res.status_code == 401

def test_csv_utf8_bom_excel_compatibility(client):
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    res = client.get('/api/export/requests.csv')
    assert res.status_code == 200
    # Must start with UTF-8 BOM (0xef 0xbb 0xbf) for Excel on Windows to display non-ASCII correctly
    assert res.data.startswith(b'\xef\xbb\xbf')

def test_centralized_json_error_handlers(client):
    # Non-existent API route should return JSON 404
    res_404 = client.get('/api/non-existent-endpoint-xyz')
    assert res_404.status_code == 404
    assert res_404.is_json
    assert 'not found' in res_404.get_json()['error'].lower()

    # Method not allowed on API route should return JSON 405
    res_405 = client.delete('/api/inventory')
    assert res_405.status_code == 405
    assert res_405.is_json
    assert 'method not allowed' in res_405.get_json()['error'].lower()

def test_payload_too_large_rejection(client):
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    # Payload exceeding 2MB should trigger 413
    huge_data = {'name': 'A' * (3 * 1024 * 1024)}
    res = client.post('/api/requests', json=huge_data)
    assert res.status_code == 413
    assert res.is_json
    assert 'exceeds' in res.get_json()['error'].lower()

def test_database_rollback_on_failure(client):
    import database
    import sqlite3

    conn = database.get_db()
    init_count = conn.execute("SELECT COUNT(*) FROM volunteers").fetchone()[0]

    try:
        with conn:
            conn.execute("INSERT INTO volunteers (initials, name, skill, zone, status) VALUES ('RT', 'Rollback Test', 'Rescue', 'Z1', 'Available')")
            # Force syntax error to trigger transaction rollback
            conn.execute("INSERT INTO nonexistent_table (col) VALUES (1)")
    except (sqlite3.OperationalError, sqlite3.IntegrityError):
        pass

    # Volunteer count should remain unchanged after rollback
    final_count = conn.execute("SELECT COUNT(*) FROM volunteers").fetchone()[0]
    assert final_count == init_count


