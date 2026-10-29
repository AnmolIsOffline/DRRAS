from conftest import verify_request_with_team
import pytest
from werkzeug.security import check_password_hash

def test_driver_dispatch_lifecycle_route_blockage_and_proof(client):
    # 1. Official creates and verifies a fresh request
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    req_res = client.post('/api/requests', json={
        'name': 'Rohan Varma',
        'area': 'Dhaliwal Colony Sector 4',
        'address': 'Plot 99, River Road',
        'need': 'Immediate Medical Kits & Trauma Support',
        'people': 6
    })
    assert req_res.status_code == 201
    req_id = req_res.get_json()['id']
    verify_request_with_team(client, req_id)

    alloc_res = client.post(f'/api/requests/{req_id}/allocate')
    assert alloc_res.status_code == 200
    dsp_id = alloc_res.get_json()['dispatch_id']

    # Get dispatch details
    dsp = client.get(f'/api/dispatches/{dsp_id}').get_json()
    assert dsp['status'] == 'Loading'
    assigned_driver = dsp['driver']

    # 2. Unauthorized driver cannot start this dispatch
    conn=__import__('database').get_db()
    assigned=conn.execute("SELECT id,email,password FROM users WHERE name=? AND role='Driver'",(assigned_driver,)).fetchone()
    other=conn.execute("SELECT email,password FROM users WHERE role='Driver' AND organization_id IS NULL AND id<>? ORDER BY id LIMIT 1",(assigned['id'],)).fetchone()
    driver_email=assigned['email']
    other_email=other['email']
    driver_password=next(p for p in ('driver123','driveDemo26!') if check_password_hash(assigned['password'],p))
    other_password=next(p for p in ('driver123','driveDemo26!') if check_password_hash(other['password'],p))
    conn.close()

    client.post('/api/auth/login', json={'email': other_email, 'password': other_password})
    unauth = client.post(f'/api/dispatches/{dsp_id}/start')
    assert unauth.status_code == 403

    # Login as the assigned driver
    client.post('/api/auth/login', json={'email': driver_email, 'password': driver_password})

    # 3. Driver accepts and marks ready/depart
    # Set to Ready
    rdy = client.post(f'/api/dispatches/{dsp_id}/ready')
    assert rdy.status_code == 200
    assert rdy.get_json()['status'] == 'Ready'

    # Start journey -> En route
    dep = client.post(f'/api/dispatches/{dsp_id}/start')
    assert dep.status_code == 200
    dep_data = dep.get_json()
    assert dep_data['status'] == 'En route'
    assert dep_data['departed_at'] is not None

    # Verify linked request is now also 'Dispatched'
    req_chk = client.get(f'/api/requests/{req_id}').get_json()
    assert req_chk['status'] == 'Dispatched'

    # 4. Driver encounters Route Blockage
    block_res = client.post(f'/api/dispatches/{dsp_id}/route-blockage', json={
        'reason': 'Waterlogging at Old Bridge (3.5ft water depth)',
        'lat': 30.9150,
        'lng': 75.8400,
        'notes': 'Bridge impassable for van, requesting clearance or detour via Bypass'
    })
    assert block_res.status_code == 200
    block_data = block_res.get_json()
    assert block_data['route_status'] == 'Blocked'

    # 5. Coordinator reroutes the vehicle
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    reroute_res = client.post(f'/api/dispatches/{dsp_id}/reroute', json={
        'destination': 'Dhaliwal Colony via South Bypass Road',
        'reason': 'Clear secondary route confirmed with local traffic police'
    })
    assert reroute_res.status_code == 200
    assert reroute_res.get_json()['route_status'] == 'Rerouted'

    # 6. Driver arrives at destination
    client.post('/api/auth/login', json={'email': driver_email, 'password': 'driver123'})
    arr_res = client.post(f'/api/dispatches/{dsp_id}/arrive')
    assert arr_res.status_code == 200
    assert arr_res.get_json()['status'] == 'Arrived'

    # 7. Driver submits Delivery Proof
    proof_res = client.post(f'/api/dispatches/{dsp_id}/delivery-proof', json={
        'proof_type': 'RecipientConfirmation',
        'recipient_confirmation': 'Ramesh Kumar (Ward 4 Resident)',
        'notes': 'Handed over 2 medical kits to family head',
        'items': [
            {'resource_id': item['resource_id'], 'quantity_delivered': item['quantity_loaded'], 'quantity_returned': 0, 'quantity_damaged': 0}
            for item in dsp['items']
        ]
    })
    assert proof_res.status_code == 200
    proof_data = proof_res.get_json()
    assert proof_data['status'] == 'Delivered Pending Proof'
    # A retry cannot overwrite proof or double-count quantities.
    retry = client.post(f'/api/dispatches/{dsp_id}/delivery-proof', json={
        'proof_type': 'RecipientConfirmation', 'proof_reference': 'retry',
        'items': [{'resource_id': item['resource_id'], 'quantity_delivered': item['quantity_loaded'], 'quantity_returned': 0, 'quantity_damaged': 0} for item in dsp['items']]
    })
    assert retry.status_code == 409
    assert retry.get_json()['code'] == 'PROOF_ALREADY_SUBMITTED'

    # 8. Supervisor reviews and approves delivery proof
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    rev_res = client.post(f'/api/dispatches/{dsp_id}/review-delivery', json={
        'decision': 'Accept',
        'reason': 'Verified recipient signature and photo'
    })
    assert rev_res.status_code == 200
    assert rev_res.get_json()['status'] == 'Delivered'

    # Verify linked request status updated to Delivered Pending Confirmation
    req_final = client.get(f'/api/requests/{req_id}').get_json()
    assert req_final['status'] in ('Delivered Pending Confirmation', 'Delivered')


def test_rejected_delivery_proof_does_not_complete_request(client):
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    created = client.post('/api/requests', json={
        'name': 'Nirmal Kaur', 'area': 'Riverside Ward 3', 'address': 'House 18',
        'need': 'Medical kits', 'people': 6
    }).get_json()
    req_id = created['id']
    assert verify_request_with_team(client, req_id).status_code == 200
    allocated = client.post(f'/api/requests/{req_id}/allocate').get_json()
    dsp_id = allocated['dispatch_id']
    assert client.post(f'/api/dispatches/{dsp_id}/start').status_code == 200
    assert client.post(f'/api/dispatches/{dsp_id}/arrive').status_code == 200
    manifest = client.get(f'/api/dispatches/{dsp_id}').get_json()['items']
    items = [{'resource_id': i['resource_id'], 'quantity_delivered': i['quantity_loaded'], 'quantity_returned': 0, 'quantity_damaged': 0} for i in manifest]
    assert client.post(f'/api/dispatches/{dsp_id}/delivery-proof', json={'proof_type': 'RecipientConfirmation', 'proof_reference': 'test-ref', 'items': items}).status_code == 200
    rejected = client.post(f'/api/dispatches/{dsp_id}/review-delivery', json={'decision': 'Rejected', 'reason': 'Recipient could not verify handover'})
    assert rejected.status_code == 200
    assert rejected.get_json()['status'] == 'Proof Rejected'
    assert client.get(f'/api/requests/{req_id}').get_json()['status'] == 'Dispatched'
    conn = __import__('database').get_db()
    try:
        assert conn.execute('SELECT status FROM inventory_reservations WHERE dispatch_id = ?', (dsp_id,)).fetchone()['status'] == 'Active'
        assert conn.execute('SELECT status FROM vehicles WHERE id = (SELECT vehicle_id FROM dispatches WHERE id = ?)', (dsp_id,)).fetchone()['status'] == 'EnRoute'
    finally:
        conn.close()


def test_official_selects_available_driver_and_assigned_driver_sees_dispatch(client):
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    created = client.post('/api/requests', json={
        'name': 'Amanpreet Kaur', 'area': 'North Ward', 'address': 'Shelter Lane 4',
        'need': 'Medical kits', 'people': 8, 'lat': 30.93, 'lng': 75.84
    }).get_json()
    req_id = created['id']
    assert verify_request_with_team(client, req_id).status_code == 200
    opts_res = client.get(f'/api/allocation-options/{req_id}')
    assert opts_res.status_code == 200
    opts = opts_res.get_json()
    assert len(opts['drivers']) >= 3
    driver = next(d for d in opts['drivers'] if d['available'])
    vehicle = next(v for v in opts['vehicles'] if v['available'])
    alloc = client.post(f'/api/requests/{req_id}/allocate', json={'driver_user_id': driver['id'], 'vehicle_id': vehicle['id']})
    assert alloc.status_code == 200, alloc.get_json()
    dsp_id = alloc.get_json()['dispatch_id']
    conn = __import__('database').get_db()
    try:
        assigned = conn.execute('SELECT driver_user_id, vehicle_id FROM dispatches WHERE id=?', (dsp_id,)).fetchone()
        driver_email = conn.execute('SELECT email FROM users WHERE id=?', (driver['id'],)).fetchone()['email']
        other = conn.execute("SELECT email FROM users WHERE role='Driver' AND id != ? ORDER BY id LIMIT 1", (driver['id'],)).fetchone()['email']
    finally:
        conn.close()
    assert assigned['driver_user_id'] == driver['id']
    assert assigned['vehicle_id'] == vehicle['id']
    client.post('/api/auth/login', json={'email': driver_email, 'password': 'driver123'})
    driver_dispatches = client.get('/api/dispatches').get_json()
    assert any(d['id'] == dsp_id for d in driver_dispatches)
    assert next(d for d in driver_dispatches if d['id'] == dsp_id)['destination_lat'] == 30.93
    client.post('/api/auth/login', json={'email': other, 'password': 'driver123'})
    assert all(d['id'] != dsp_id for d in client.get('/api/dispatches').get_json())
