from conftest import verify_request_with_team
import pytest

def test_dispatches_lifecycle_and_request_synchronization(client):
    # Log in as Administrator
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})

    # 1. Create and allocate an emergency request
    req_res = client.post('/api/requests', json={
        'name': 'Pooja Rani',
        'area': 'Ward 12 Relief Point',
        'address': 'Street 3, Ward 12',
        'need': 'Drinking water & food kits',
        'people': 5
    })
    req_id = req_res.get_json()['id']
    client.post('/api/auth/logout')
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    assert verify_request_with_team(client, req_id).status_code == 200
    client.post('/api/auth/logout')
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    assert client.post(f'/api/requests/{req_id}/allocate').status_code == 200

    # Find the linked dispatch
    dispatches = client.get('/api/dispatches').get_json()
    disp = next(d for d in dispatches if d['request_id'] == req_id)
    assert disp['status'] == 'Loading'

    # Step 1: Advance Loading -> En route
    res_enroute = client.post(f"/api/dispatches/{disp['id']}/advance")
    assert res_enroute.status_code == 200
    assert res_enroute.get_json()['status'] == 'En route'

    # Arrival does not bypass itemized proof and authorized review.
    res_arrived = client.post(f"/api/dispatches/{disp['id']}/advance")
    assert res_arrived.status_code == 200
    assert res_arrived.get_json()['status'] == 'Arrived'
    res_invalid = client.post(f"/api/dispatches/{disp['id']}/advance")
    assert res_invalid.status_code == 409
    assert res_invalid.get_json()['code'] == 'PROOF_REQUIRED'
    all_reqs = client.get('/api/requests').get_json()
    synced_req = next(r for r in all_reqs if r['id'] == req_id)
    assert synced_req['status'] == 'Dispatched'

def test_advance_nonexistent_dispatch(client):
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    res = client.post('/api/dispatches/DSP-9999/advance')
    assert res.status_code == 404

def test_driver_specific_dispatch_authorization(client):
    # Driver Arjun Mehta logs in
    client.post('/api/auth/login', json={'email': 'driver@drras.in', 'password': 'driver123'})

    dispatches = client.get('/api/dispatches').get_json()
    arjun_trip = next((d for d in dispatches if d['driver'] == 'Arjun Mehta' and d['status'] != 'Delivered'), None)
    other_trip = next((d for d in dispatches if d['driver'] != 'Arjun Mehta' and d['status'] != 'Delivered'), None)

    # Arjun can advance his own trip
    if arjun_trip:
        res_own = client.post(f"/api/dispatches/{arjun_trip['id']}/advance")
        assert res_own.status_code in (200, 400) # 200 or 400 if already delivered

    # Arjun cannot advance another driver's trip (e.g. Simran Kaur)
    if other_trip:
        res_other = client.post(f"/api/dispatches/{other_trip['id']}/advance")
        assert res_other.status_code == 403
        assert 'not authorized' in res_other.get_json()['error'].lower()
