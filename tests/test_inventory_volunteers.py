import pytest
from database import get_db

# ---------------- INVENTORY TESTS ----------------

def test_inventory_list(client):
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    res = client.get('/api/inventory')
    assert res.status_code == 200
    items = res.get_json()
    assert len(items) >= 5
    # Verify core attributes
    first = items[0]
    assert 'resource_name' in first
    assert 'available_units' in first
    assert 'target_stock' in first
    assert 'status' in first

def test_add_inventory_valid_and_status_calculation(client):
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    
    # Critical status (< 35% of target)
    res_crit = client.post('/api/inventory', json={
        'name': 'Emergency Solar Lamps',
        'available': 20,
        'target': 100
    })
    assert res_crit.status_code == 201

    # Low status (< 100% of target)
    res_low = client.post('/api/inventory', json={
        'name': 'Baby Diapers & Wipes',
        'available': 50,
        'target': 100
    })
    assert res_low.status_code == 201

    # Safe status (>= 100% of target)
    res_safe = client.post('/api/inventory', json={
        'name': 'Tarpaulin Sheets',
        'available': 150,
        'target': 100
    })
    assert res_safe.status_code == 201

    # Verify statuses in inventory list
    inv = client.get('/api/inventory').get_json()
    crit_item = next(i for i in inv if i['resource_name'] == 'Emergency Solar Lamps')
    assert crit_item['status'] == 'Critical'
    low_item = next(i for i in inv if i['resource_name'] == 'Baby Diapers & Wipes')
    assert low_item['status'] == 'Low'
    safe_item = next(i for i in inv if i['resource_name'] == 'Tarpaulin Sheets')
    assert safe_item['status'] == 'Safe'

def test_add_inventory_validation_and_duplicate(client):
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})

    # Missing name
    res1 = client.post('/api/inventory', json={'name': '', 'available': 10, 'target': 20})
    assert res1.status_code == 400

    # Negative available
    res2 = client.post('/api/inventory', json={'name': 'Bad Item', 'available': -5, 'target': 20})
    assert res2.status_code == 400

    # Zero or negative target
    res3 = client.post('/api/inventory', json={'name': 'Bad Item 2', 'available': 10, 'target': 0})
    assert res3.status_code == 400

    # Duplicate resource name
    res4 = client.post('/api/inventory', json={'name': 'Drinking Water', 'available': 100, 'target': 200})
    assert res4.status_code == 409
    assert 'already exists' in res4.get_json()['error'].lower()

# ---------------- VOLUNTEER TESTS ----------------

def test_volunteers_list(client):
    client.post('/api/auth/login',json={'email':'admin@drras.in','password':'admin123'})
    res = client.get('/api/volunteers')
    assert res.status_code == 200
    vols = res.get_json()
    assert len(vols) >= 4

def test_register_volunteer_validation(client):
    client.post('/api/auth/login', json={'email': 'ngo@drras.in', 'password': 'ngo123'})
    res=client.post('/api/ngo/volunteers',json={'name':'Harpreet Gill','email':'harpreet@drras.in','password':'harpreet123','skill':'Water Rescue & Boat Operations','zone':'Riverbank Village'})
    assert res.status_code==201
    assert res.get_json()['status']=='PENDING'
    assert res.get_json()['organization_id']==1
    volunteer_id=res.get_json()['id']
    assert client.post(f"/api/ngo/personnel/{volunteer_id}/approve",json={'skill':'Water Rescue & Boat Operations','zone':'Riverbank Village'}).status_code==200
    # A different NGO cannot approve this organization's pending personnel.
    pending_driver=client.post('/api/ngo/drivers',json={'name':'Org One Driver','email':'org1.driver.test@drras.in','password':'org1driver123'})
    assert pending_driver.status_code==201 and pending_driver.get_json()['status']=='PENDING'
    driver_id=pending_driver.get_json()['id']
    client.post('/api/auth/login',json={'email':'contact@khalsaaid.org','password':'ngo123'})
    assert client.post(f'/api/ngo/personnel/{volunteer_id}/approve',json={}).status_code==404
    assert client.post(f'/api/ngo/personnel/{driver_id}/approve',json={}).status_code==404
    client.post('/api/auth/login',json={'email':'ngo@drras.in','password':'ngo123'})
    approved_driver=client.post(f'/api/ngo/personnel/{driver_id}/approve',json={})
    assert approved_driver.status_code==200 and approved_driver.get_json()['status']=='ACTIVE'
    driver_login=client.post('/api/auth/login',json={'email':'org1.driver.test@drras.in','password':'org1driver123'})
    assert driver_login.status_code==200 and driver_login.get_json()['organization_id']==1
    assert client.post('/api/ngo/volunteers',json={'name':'','email':'bad@drras.in','password':'longpassword','skill':'Medical','zone':'Ward 8'}).status_code==403
    client.post('/api/auth/login',json={'email':'ngo@drras.in','password':'ngo123'})
    assert client.post('/api/ngo/volunteers',json={'name':'Kuldeep','email':'bad2@drras.in','password':'longpassword','skill':'','zone':'Ward 8'}).status_code==400

def test_assign_volunteer_workflow(client):
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})

    # Find available volunteer
    vols = client.get('/api/volunteers').get_json()
    active_ids={t['volunteer_id'] for t in client.get('/api/volunteer-tasks').get_json() if t['status'] in ('Assigned','Accepted','In Progress','Submitted for Review','Needs Correction')}
    avail = next(v for v in vols if v['status'] == 'Available' and v['id'] not in active_ids)

    # Assign volunteer
    res = client.post(f"/api/volunteers/{avail['id']}/assign")
    assert res.status_code == 200

    # Verify status changed
    updated_vols = client.get('/api/volunteers').get_json()
    updated = next(v for v in updated_vols if v['id'] == avail['id'])
    assert updated['status'] == 'On task'

    # Assigning nonexistent volunteer should return 404
    res_404 = client.post('/api/volunteers/999999/assign')
    assert res_404.status_code == 404

def test_update_inventory_and_authorization(client):
    # Log in as admin
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    inv = client.get('/api/inventory').get_json()
    first_item = inv[0]
    item_id = first_item['id']

    # Update item available units to trigger 'Critical' status
    warehouses=client.get('/api/warehouses').get_json()
    conn=get_db(); stock=conn.execute("SELECT ws.id,ws.resource_id,w.id AS warehouse_id FROM warehouse_stock ws JOIN warehouses w ON w.id=ws.warehouse_id WHERE ws.id=?",(item_id,)).fetchone(); conn.close()
    if first_item['owner_type']!='government':
        first_item=next(i for i in inv if i['owner_type']=='government'); item_id=first_item['id']; conn=get_db(); stock=conn.execute("SELECT ws.id,ws.resource_id,w.id AS warehouse_id FROM warehouse_stock ws JOIN warehouses w ON w.id=ws.warehouse_id WHERE ws.id=?",(item_id,)).fetchone(); conn.close()
    destination_res=client.post('/api/warehouses',json={'code':'WH-MOVE-TEST','name':'East Hub','district':'Demo District','address':'East Hub, Demo District'})
    assert destination_res.status_code==201
    destination=destination_res.get_json()
    res = client.put(f'/api/inventory/{item_id}', json={
        'available': 10,
        'target': 200,
        'warehouse_id': destination['id']
    })
    assert res.status_code == 200
    updated = res.get_json()
    assert updated['available_units'] == 10
    assert updated['target_stock'] == 200
    assert updated['status'] == 'Critical'
    assert updated['warehouse_name'] == destination['name']

    # Invalid updates
    res_bad1 = client.put(f'/api/inventory/{item_id}', json={'available': -1, 'target': 100})
    assert res_bad1.status_code == 400

    res_bad2 = client.put(f'/api/inventory/{item_id}', json={'available': 10, 'target': 0})
    assert res_bad2.status_code == 400

    # Nonexistent ID
    res_404 = client.put('/api/inventory/999999', json={'available': 50, 'target': 100})
    assert res_404.status_code == 404

    # Unauthorized access as Citizen
    client.post('/api/auth/login', json={'email': 'citizen@drras.in', 'password': 'citizen123'})
    res_unauth = client.put(f'/api/inventory/{item_id}', json={'available': 50, 'target': 100})
    assert res_unauth.status_code == 403

def test_unassign_volunteer_and_authorization(client):
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    vols=client.get('/api/volunteers').get_json()
    active_ids={t['volunteer_id'] for t in client.get('/api/volunteer-tasks').get_json() if t['status'] in ('Assigned','Accepted','In Progress','Submitted for Review','Needs Correction')}
    volunteer=next(v for v in vols if v['owner_type']=='government' and v['status']=='Available' and v['id'] not in active_ids)
    vol_id=volunteer['id']

    # First assign
    client.post(f'/api/volunteers/{vol_id}/assign')

    # Now unassign
    res = client.post(f'/api/volunteers/{vol_id}/unassign')
    assert res.status_code == 200
    assert 'available' in res.get_json()['message'].lower()

    # Verify status is Available
    updated_vols = client.get('/api/volunteers').get_json()
    vol = next(v for v in updated_vols if v['id'] == vol_id)
    assert vol['status'] == 'Available'

    # Nonexistent volunteer
    res_404 = client.post('/api/volunteers/999999/unassign')
    assert res_404.status_code == 404

    # Citizen cannot unassign
    client.post('/api/auth/login', json={'email': 'citizen@drras.in', 'password': 'citizen123'})
    res_unauth = client.post(f'/api/volunteers/{vol_id}/unassign')
    assert res_unauth.status_code == 403

