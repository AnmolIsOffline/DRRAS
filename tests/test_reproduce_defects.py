import pytest

def test_reproduce_admin_unknown_email_approval(client):
    # Log in as Admin
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    
    # Approving non-existent email should return 404, not 200
    res = client.post('/api/admin/approve-user', json={'email': 'nonexistent_user_999@drras.in'})
    assert res.status_code == 404, f"Expected 404 for unknown user, got {res.status_code}: {res.get_json()}"

def test_reproduce_fractional_people_count(client):
    # Submitting fractional people count should return 400
    res = client.post('/api/requests', json={
        'name': 'Test Requester',
        'area': 'Ward 1',
        'address': 'Street 1',
        'need': 'Food ration',
        'people': 5.5
    })
    assert res.status_code == 400, f"Expected 400 for fractional people, got {res.status_code}"

def test_reproduce_vulnerable_case_insensitivity(client):
    # Submitting 'Yes' (title case) should calculate 93, not 68 (58 + 25 + 10)
    res = client.post('/api/requests', json={
        'name': 'Test Requester',
        'area': 'Ward 1',
        'address': 'Street 1',
        'need': 'Food ration',
        'people': 10,
        'vulnerable': 'Yes'
    })
    assert res.status_code == 201
    assert res.get_json()['priority_score'] == 93, f"Expected 93, got {res.get_json()['priority_score']}"

def test_reproduce_assign_unavailable_volunteer(client):
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    vols = client.get('/api/volunteers').get_json()
    ontask_vol = next((v for v in vols if v['status'] == 'On task'), None)
    if ontask_vol:
        res = client.post(f"/api/volunteers/{ontask_vol['id']}/assign")
        assert res.status_code == 400, f"Expected 400 assigning already 'On task' volunteer, got {res.status_code}"

def test_reproduce_citizen_advance_dispatch_forbidden(client):
    # Citizen logs in
    login=client.post('/api/auth/login', json={'email': 'citizen@drras.in', 'password': 'citizen123'})
    dispatches = client.get('/api/dispatches').get_json()
    conn=__import__('database').get_db()
    own_ids={r['id'] for r in conn.execute('SELECT id FROM emergency_requests WHERE requester_user_id=?',(login.get_json()['id'],))}
    conn.close()
    assert all(d['request_id'] in own_ids for d in dispatches)  # Only the citizen's persisted requests are exposed.
    res = client.post('/api/dispatches/DSP-01/advance')
    assert res.status_code == 403, f"Expected 403 for Citizen advancing dispatch, got {res.status_code}"

def test_reproduce_citizen_export_volunteers_forbidden(client):
    # Citizen logs in
    client.post('/api/auth/login', json={'email': 'citizen@drras.in', 'password': 'citizen123'})
    res = client.get('/api/export/volunteers.csv')
    assert res.status_code == 403, f"Expected 403 for Citizen exporting volunteers, got {res.status_code}"
