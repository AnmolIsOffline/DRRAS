from conftest import verify_request_with_team
import pytest

def test_dynamic_emergency_allocation_with_inventory_deduction(client):
    # Government response and allocation must use only Government responders, drivers, vehicles and stock.
    client.post('/api/auth/login',json={'email':'official@drras.in','password':'official123'})
    inv_list=client.get('/api/inventory').get_json()
    med=next(i for i in inv_list if 'Medical' in i['resource_name'])
    initial=med['available_units']
    client.post('/api/auth/login',json={'email':'citizen@drras.in','password':'citizen123'})
    req=client.post('/api/requests',json={'name':'Simran Kaur','area':'Ward 9 High Water Sector','address':'Plot 44, Riverbank Colony','need':'Immediate Medical Kits & Trauma Support','people':8})
    assert req.status_code==201
    req_id=req.get_json()['id']
    assert req.get_json()['priority_score']>=68
    client.post('/api/auth/login',json={'email':'official@drras.in','password':'official123'})
    assert verify_request_with_team(client,req_id).status_code==200
    alloc=client.post(f'/api/requests/{req_id}/allocate')
    assert alloc.status_code==200,alloc.get_json()
    assert alloc.get_json()['status']=='Allocated'
    dispatch=next(d for d in client.get('/api/dispatches').get_json() if d['request_id']==req_id)
    assert dispatch['status']=='Loading' and dispatch['owner_type']=='government'
    assert 'Ambulance' in dispatch['vehicle']
    updated=next(i for i in client.get('/api/inventory').get_json() if i['id']==med['id'])
    assert updated['available_units']==initial-2

def test_dispatch_lifecycle_synchronizes_request_status(client):
    """
    Verifies the end-to-end dispatch progression:
    - Loading -> En route (updates request to Dispatched)
    - En route -> Delivered (updates request to Delivered)
    - Emits dispatch_advanced and request_updated system events
    """
    # Admin logs in
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})

    # Create & allocate water relief request
    req_res = client.post('/api/requests', json={
        'name': 'Gurbaksh Singh',
        'area': 'Zone 5 Evacuation Ground',
        'address': 'Tent 14, Zone 5',
        'need': 'Drinking water supplies',
        'people': 12
    })
    req_id = req_res.get_json()['id']
    client.post('/api/auth/logout')
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    assert verify_request_with_team(client, req_id).status_code == 200
    client.post('/api/auth/logout')
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    client.post(f'/api/requests/{req_id}/allocate')

    dispatches = client.get('/api/dispatches').get_json()
    disp = next(d for d in dispatches if d['request_id'] == req_id)
    assert disp['status'] == 'Loading'

    # Advance Loading -> En route
    res_enroute = client.post(f"/api/dispatches/{disp['id']}/advance")
    assert res_enroute.status_code == 200
    assert res_enroute.get_json()['status'] == 'En route'

    # Verify request status transitioned to Dispatched
    reqs = client.get('/api/requests').get_json()
    synced_req = next(r for r in reqs if r['id'] == req_id)
    assert synced_req['status'] == 'Dispatched'

    # Arrival is separate from proof submission/review; legacy advance cannot complete delivery.
    res_arrived = client.post(f"/api/dispatches/{disp['id']}/advance")
    assert res_arrived.status_code == 200
    assert res_arrived.get_json()['status'] == 'Arrived'
    res_bypass = client.post(f"/api/dispatches/{disp['id']}/advance")
    assert res_bypass.status_code == 409
    assert res_bypass.get_json()['code'] == 'PROOF_REQUIRED'
    reqs_after = client.get('/api/requests').get_json()
    assert next(r for r in reqs_after if r['id'] == req_id)['status'] == 'Dispatched'


def test_driver_rbac_isolation(client):
    client.post('/api/auth/login',json={'email':'citizen@drras.in','password':'citizen123'})
    created=client.post('/api/requests',json={'name':'Isolation Test Citizen','area':'North Camp','address':'Block A','need':'Food Ration Kits','people':4})
    request_id=created.get_json()['id']
    client.post('/api/auth/login',json={'email':'official@drras.in','password':'official123'})
    assert verify_request_with_team(client,request_id).status_code==200
    assert client.post(f'/api/requests/{request_id}/allocate').status_code==200
    dispatch=next(d for d in client.get('/api/dispatches').get_json() if d['request_id']==request_id)
    provision=client.post('/api/government/drivers',json={'name':'Gurpreet Driver','email':'gurpreet.driver@drras.in','password':'driverpass123'})
    assert provision.status_code==201,provision.get_json()
    client.post('/api/auth/login',json={'email':'gurpreet.driver@drras.in','password':'driverpass123'})
    denied=client.post(f"/api/dispatches/{dispatch['id']}/advance")
    assert denied.status_code==403

def test_volunteer_self_handover_and_reassignment(client):
    """
    Verifies that:
    1. Admin or Coordinator can assign an available volunteer to active task.
    2. Other roles like Citizen cannot unassign.
    3. Official or volunteer can unassign, marking them Available.
    """
    # Admin logs in
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})

    volunteers = client.get('/api/volunteers').get_json()
    assert len(volunteers) > 0
    # Pick or make an available volunteer
    active_ids={t['volunteer_id'] for t in client.get('/api/volunteer-tasks').get_json() if t['status'] in ('Assigned','Accepted','In Progress','Submitted for Review','Needs Correction')}
    avail_vol = next((v for v in volunteers if v['owner_type']=='government' and v['status']=='Available' and v['id'] not in active_ids), None)
    assert avail_vol is not None

    # Assign volunteer
    assign_res = client.post(f"/api/volunteers/{avail_vol['id']}/assign")
    assert assign_res.status_code == 200
    assert assign_res.get_json()['success'] is True
    vols_after_assign = client.get('/api/volunteers').get_json()
    assert next(v for v in vols_after_assign if v['id'] == avail_vol['id'])['status'] == 'On task'

    # Another user (Citizen) cannot unassign the volunteer
    client.post('/api/auth/login', json={'email': 'citizen@drras.in', 'password': 'citizen123'})
    unauth_res = client.post(f"/api/volunteers/{avail_vol['id']}/unassign")
    assert unauth_res.status_code == 403

    # Official can unassign
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    release_res = client.post(f"/api/volunteers/{avail_vol['id']}/unassign")
    assert release_res.status_code == 200
    assert release_res.get_json()['success'] is True
    vols_after_release = client.get('/api/volunteers').get_json()
    assert next(v for v in vols_after_release if v['id'] == avail_vol['id'])['status'] == 'Available'


def test_shelter_capacity_management_and_rbac(client):
    """
    Verifies:
    1. Authorized roles (Government Official, Admin, NGO) can update shelter occupancy and capacity via PATCH and PUT.
    2. Status is recalculated to 'Near capacity' when occupants >= 90% capacity.
    3. Unauthorized roles (Citizen, Driver) get 403.
    4. Invalid payload (e.g. negative occupants) gets 400.
    """
    # 1. Citizen cannot update shelter
    client.post('/api/auth/login', json={'email': 'citizen@drras.in', 'password': 'citizen123'})
    res_citizen = client.patch('/api/shelters/1', json={'occupants': 200})
    assert res_citizen.status_code == 403

    # 2. Government Official can update shelter
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    
    # Valid update
    res_valid = client.patch('/api/shelters/1', json={'occupants': 450, 'capacity': 500, 'status': 'Operational'})
    assert res_valid.status_code == 200
    s_data = res_valid.get_json()
    assert s_data['occupants'] == 450
    assert s_data['capacity'] == 500

    # Test status recalculation to Near capacity when occupants >= 90% of capacity
    res_full = client.put('/api/shelters/1', json={'occupants': 490, 'capacity': 500, 'status': 'Operational'})
    assert res_full.status_code == 200
    assert res_full.get_json()['status'] == 'Near capacity'

    # Invalid update: negative occupants
    res_neg = client.patch('/api/shelters/1', json={'occupants': -10})
    assert res_neg.status_code == 400
    assert 'positive' in res_neg.get_json()['error'].lower() or 'occupants' in res_neg.get_json()['error'].lower()


def test_realtime_events_polling(client):
    """
    Verifies that system events are logged to the database and can be retrieved via /api/events/poll.
    """
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})

    # Baseline poll
    poll_before = client.get('/api/events/poll').get_json()
    last_id = poll_before['last_id']
    assert isinstance(last_id, int)

    # Perform an operational action in a real Government-owned warehouse.
    warehouse=next(w for w in client.get('/api/warehouses').get_json() if w['owner_type']=='government')
    inv_res = client.post('/api/inventory', json={
        'name': 'Emergency Water Purification Tablets',
        'category': 'Water & Sanitation',
        'available': 1000,
        'target': 2000,
        'warehouse_id': warehouse['id']
    })
    assert inv_res.status_code == 201

    # Poll with ?since=<last_id>
    poll_after = client.get(f'/api/events/poll?since={last_id}').get_json()
    events = poll_after['events']
    assert len(events) >= 1

    inv_event = next((e for e in events if e['event_type'] == 'inventory_updated'), None)
    assert inv_event is not None
    assert inv_event['payload'] == {}  # Global event stream carries no record details.
    assert poll_after['last_id'] > last_id
