import pytest
from database import get_db

def test_login_all_demo_accounts(client):
    demo_accounts = [
        ('admin@drras.in', 'admin123', 'Administrator'),
        ('official@drras.in', 'official123', 'Government Official'),
        ('ngo@drras.in', 'ngo123', 'NGO Coordinator'),
        ('volunteer@drras.in', 'volunteer123', 'Volunteer'),
        ('citizen@drras.in', 'citizen123', 'Citizen'),
        ('driver@drras.in', 'driver123', 'Driver')
    ]
    for email, password, role in demo_accounts:
        res = client.post('/api/auth/login', json={'email': email, 'password': password})
        assert res.status_code == 200, f"Failed login for {email}: {res.get_json()}"
        data = res.get_json()
        assert data['role'] == role
        assert data['email'].lower().endswith('@drras-demo.local')
        assert 'name' in data
        assert data['status'] == 'ACTIVE'

def test_login_incorrect_password(client):
    res = client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'wrongpassword'})
    assert res.status_code == 401
    assert 'error' in res.get_json()

def test_login_unknown_email(client):
    res = client.post('/api/auth/login', json={'email': 'unknown@drras.in', 'password': 'admin123'})
    assert res.status_code == 401
    assert 'error' in res.get_json()

def test_login_missing_fields(client):
    res1 = client.post('/api/auth/login', json={'email': '', 'password': 'password'})
    assert res1.status_code == 400
    res2 = client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': ''})
    assert res2.status_code == 400
    res3 = client.post('/api/auth/login', json={})
    assert res3.status_code == 400
    res4 = client.post('/api/auth/login', data="not json", content_type='text/plain')
    assert res4.status_code == 400

def test_login_email_case_and_whitespace(client):
    # Test uppercase and leading/trailing whitespace
    res = client.post('/api/auth/login', json={'email': '   ADMIN@DRRAS.IN   ', 'password': 'admin123'})
    assert res.status_code == 200
    assert res.get_json()['role'] == 'Administrator'

def test_registration_validation(client):
    # Empty fields
    res = client.post('/api/auth/register', json={'email': '', 'password': '', 'name': '', 'role': 'Citizen'})
    assert res.status_code == 400
    assert 'error' in res.get_json()

    # Short password (< 6 chars)
    res = client.post('/api/auth/register', json={'email': 'test_short@drras.in', 'password': '123', 'name': 'Short', 'role': 'Citizen'})
    assert res.status_code == 400
    assert 'Password' in res.get_json()['error']

    # Invalid email format
    res = client.post('/api/auth/register', json={'email': 'notanemail', 'password': 'password123', 'name': 'Invalid Email', 'role': 'Citizen'})
    assert res.status_code == 400
    assert 'email' in res.get_json()['error'].lower()

def test_registration_roles_and_approval_flow(client):
    # 1. Citizen registration should be immediately ACTIVE
    res_cit = client.post('/api/auth/register', json={
        'email': 'newcitizen@drras.in',
        'password': 'password123',
        'name': 'New Citizen',
        'role': 'Citizen'
    })
    assert res_cit.status_code == 201
    assert res_cit.get_json()['status'] == 'ACTIVE'

    # Can immediately login
    login_cit = client.post('/api/auth/login', json={'email': 'newcitizen@drras.in', 'password': 'password123'})
    assert login_cit.status_code == 200

    # 2. Volunteer registration should be PENDING
    res_vol = client.post('/api/auth/register', json={
        'email': 'newvol@drras.in',
        'password': 'password123',
        'name': 'New Volunteer',
        'role': 'Volunteer', 'organization_id': 1
    })
    assert res_vol.status_code == 201
    assert res_vol.get_json()['status'] == 'PENDING'

    # Cannot login while PENDING
    login_vol = client.post('/api/auth/login', json={'email': 'newvol@drras.in', 'password': 'password123'})
    assert login_vol.status_code == 403
    assert 'pending' in login_vol.get_json()['error'].lower()

    # Admin checks pending users
    # First login as Admin
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    pending_res = client.get('/api/admin/pending-users')
    assert pending_res.status_code == 200
    pending_list = pending_res.get_json()
    assert any(u['email'] == 'newvol@drras.in' for u in pending_list)

    # Admin approves user
    approve_res = client.post('/api/admin/approve-user', json={'email': 'newvol@drras.in'})
    assert approve_res.status_code == 409  # NGO personnel require approval by their owning Coordinator.
    client.post('/api/auth/login',json={'email':'ngo@drras.in','password':'ngo123'})
    pending = client.get('/api/ngo/personnel').get_json()
    personnel = next(u for u in pending['accounts'] if u['email'] == 'newvol@drras.in')
    approved = client.post(f"/api/ngo/personnel/{personnel['id']}/approve", json={'skill':'Medical','zone':'Ward 8'})
    assert approved.status_code == 200

    # Now Volunteer can login
    login_vol2 = client.post('/api/auth/login', json={'email': 'newvol@drras.in', 'password': 'password123'})
    assert login_vol2.status_code == 200
    assert login_vol2.get_json()['status'] == 'ACTIVE'

def test_admin_reject_user(client):
    # Register an NGO coordinator
    client.post('/api/auth/register', json={
        'email': 'bad_actor@drras.in',
        'password': 'password123',
        'name': 'Bad Actor',
        'role': 'NGO Coordinator', 'organization_id': 1
    })

    # Login as Admin and reject
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    reject_res = client.post('/api/admin/reject-user', json={'email': 'bad_actor@drras.in'})
    assert reject_res.status_code == 200

    # Login attempt must fail
    res = client.post('/api/auth/login', json={'email': 'bad_actor@drras.in', 'password': 'password123'})
    assert res.status_code in (401, 403)

def test_duplicate_registration_including_case(client):
    res1 = client.post('/api/auth/register', json={
        'email': 'uniqueuser@drras.in',
        'password': 'password123',
        'name': 'Unique User',
        'role': 'Citizen'
    })
    assert res1.status_code == 201

    # Try registering again with mixed case
    res2 = client.post('/api/auth/register', json={
        'email': 'UNIQUEUSER@DRRAS.IN',
        'password': 'password123',
        'name': 'Duplicate User',
        'role': 'Citizen'
    })
    assert res2.status_code == 400
    assert 'already exists' in res2.get_json()['error'].lower()

def test_rbac_endpoint_protection(client):
    # 1. Unauthenticated request to admin endpoint must return 401
    client.post('/api/auth/logout') # Ensure logged out
    res_unauth = client.get('/api/admin/pending-users')
    assert res_unauth.status_code == 401

    # 2. Citizen login attempting to call admin approval endpoint must return 403
    client.post('/api/auth/login', json={'email': 'citizen@drras.in', 'password': 'citizen123'})
    res_citizen = client.post('/api/admin/approve-user', json={'email': 'someuser@drras.in'})
    assert res_citizen.status_code == 403

    # 3. Citizen attempting to allocate requests must return 403
    res_alloc = client.post('/api/requests/REQ-2048/allocate')
    assert res_alloc.status_code == 403

def test_auth_me_and_logout(client):
    # Login
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    res_me = client.get('/api/auth/me')
    assert res_me.status_code == 200
    assert res_me.get_json()['email'].endswith('@drras-demo.local')

    # Logout
    res_logout = client.post('/api/auth/logout')
    assert res_logout.status_code == 200

    # /api/auth/me should now return 401
    res_me_after = client.get('/api/auth/me')
    assert res_me_after.status_code == 401

def test_registration_all_supported_roles_and_admin_protection(client):
    roles_status = [
        ('Citizen', 'ACTIVE'),
        ('Volunteer', 'PENDING'),
        ('NGO Coordinator', 'PENDING'),
        ('Government Official', 'PENDING'),
        ('Driver', 'PENDING'),
    ]
    for role, expected_status in roles_status:
        email = f"user_{role.lower().replace(' ', '_')}@drras.in"
        payload={'email':email,'password':'password123','name':f'Role {role}','role':role}
        if role in ('Volunteer','NGO Coordinator','Driver'): payload['organization_id']=1
        res = client.post('/api/auth/register', json=payload)
        assert res.status_code == 201
        data = res.get_json()
        assert data['role'] == role
        assert data['status'] == expected_status

    # Attempting to register as Administrator should default to Citizen
    res_admin = client.post('/api/auth/register', json={
        'email': 'sneaky_admin@drras.in',
        'password': 'password123',
        'name': 'Sneaky User',
        'role': 'Administrator'
    })
    assert res_admin.status_code == 201
    assert res_admin.get_json()['role'] == 'Citizen'

def test_admin_approval_edge_cases(client):
    # Login as Admin
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})

    # 1. Non-existent email -> 404
    res_404 = client.post('/api/admin/approve-user', json={'email': 'ghost@drras.in'})
    assert res_404.status_code == 404
    assert 'not found' in res_404.get_json()['error'].lower()

    res_rej_404 = client.post('/api/admin/reject-user', json={'email': 'ghost@drras.in'})
    assert res_rej_404.status_code == 404

    # 2. Missing email -> 400
    res_bad = client.post('/api/admin/approve-user', json={})
    assert res_bad.status_code == 400

    # 3. Repeated approval -> idempotent 200
    # Register pending volunteer
    client.post('/api/auth/register', json={
        'email': 'repeat_vol@drras.in',
        'password': 'password123',
        'name': 'Repeat Vol',
        'role': 'Volunteer', 'organization_id': 1
    })
    user_id=get_db().execute("SELECT id FROM users WHERE email='repeat_vol@drras.in'").fetchone()['id']
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    appr1 = client.post('/api/admin/approve-user', json={'email': 'repeat_vol@drras.in'})
    assert appr1.status_code == 409
    client.post('/api/auth/login', json={'email':'ngo@drras.in','password':'ngo123'})
    appr1=client.post(f'/api/ngo/personnel/{user_id}/approve',json={'skill':'Medical','zone':'Ward 8'})
    assert appr1.status_code == 200
    appr2=client.post(f'/api/ngo/personnel/{user_id}/approve',json={})
    assert appr2.status_code == 409  # Re-reviewing a non-pending account is a state conflict.

