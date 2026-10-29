from conftest import verify_request_with_team
from database import get_db
import pytest

def test_full_e2e_flood_response_scenario(client):
    """
    Complete end-to-end multi-role disaster response scenario across all 6 roles:
    Official -> Zone -> NGO Adoption -> Citizen Request -> Verification ->
    Donation Receipt -> Atomic Allocation -> Driver Trip & Blockage & Proof ->
    Citizen Confirmation -> Volunteer Task Distribution -> Shelter Admission ->
    Finance & Incident Operational Report.
    """

    # -------------------------------------------------------------
    # Step 1: Official creates and activates Incident & Zones
    # -------------------------------------------------------------
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})

    inc_res = client.post('/api/incidents', json={
        'title': 'Sutlej River Flash Flood Response',
        'incident_type': 'Flood',
        'severity': 'Severe',
        'description': 'Rapid embankment breach causing flood inundation across 3 municipal wards.',
        'district': 'Ludhiana District'
    })
    assert inc_res.status_code == 201
    inc_data = inc_res.get_json()
    inc_id = inc_data['id']

    # Activate incident
    act_res = client.post(f'/api/incidents/{inc_id}/activate', json={'reason': 'DDMA emergency protocol invoked'})
    assert act_res.status_code == 200
    assert act_res.get_json()['status'] == 'Active'

    # Create Zone
    zone_res = client.post(f'/api/incidents/{inc_id}/zones', json={
        'id': 'Z-FLOOD-01',
        'name': 'Old Riverside Lowlands',
        'district': 'Ludhiana District',
        'description': 'Directly exposed floodplain sector',
        'severity': 'Critical',
        'center_lat': 30.9350,
        'center_lng': 75.8150
    })
    assert zone_res.status_code == 201
    zone_id = zone_res.get_json()['id']

    # -------------------------------------------------------------
    # Step 2: NGO Coordinator requests Zone Adoption & Official approves
    # -------------------------------------------------------------
    client.post('/api/auth/login', json={'email': 'ngo@drras.in', 'password': 'ngo123'})
    adopt_res = client.post(f'/api/zones/{zone_id}/adoptions', json={
        'available_volunteers': 30,
        'available_resource_summary': '2 relief vans, 200 food kits, first aid team',
        'requested_capacity': 'Food and water distribution for 500 households'
    })
    assert adopt_res.status_code == 201
    adopt_id = adopt_res.get_json()['id']

    # Official approves zone adoption
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    app_adopt = client.post(f'/api/adoptions/{adopt_id}/approve', json={'reason': 'NGO capabilities verified'})
    assert app_adopt.status_code == 200
    assert app_adopt.get_json()['status'] == 'Approved'

    # -------------------------------------------------------------
    # Step 3: Citizen submits Distress Request (Private to Citizen)
    # -------------------------------------------------------------
    citizen_login=client.post('/api/auth/login', json={'email': 'citizen@drras.in', 'password': 'citizen123'})
    req_res = client.post('/api/requests', json={
        'name': 'Ramesh Kumar',
        'area': 'Old Riverside Lowlands',
        'address': 'H.No 12, Bund Road, Sector 3',
        'need': 'Emergency drinking water & ration kit for family stranded on rooftop',
        'people': 5,
        'vulnerable': 1,
        'incident_id': inc_id,
        'zone_id': zone_id
    })
    assert req_res.status_code == 201
    req_data = req_res.get_json()
    req_id = req_data['id']

    # Close and reopen a separate SQLite connection to check persistence, then
    # fetch the citizen list again to check refresh-level visibility.
    database = __import__('database')
    conn = database.get_db()
    citizen_id = citizen_login.get_json()['id']
    stored_request = conn.execute("SELECT requester_user_id,status FROM emergency_requests WHERE id=?",(req_id,)).fetchone()
    assert stored_request and stored_request['requester_user_id'] == citizen_id
    conn.close()
    reopened = database.get_db()
    assert reopened.execute("SELECT 1 FROM emergency_requests WHERE id=?",(req_id,)).fetchone()
    reopened.close()

    # Citizen sees own request
    own_req = client.get(f'/api/requests/{req_id}')
    assert own_req.status_code == 200
    assert any(request['id'] == req_id for request in client.get('/api/requests').get_json())
    own_dashboard = client.get('/api/dashboard').get_json()
    refreshed_db = database.get_db()
    own_open_count = refreshed_db.execute("""SELECT COUNT(*) FROM emergency_requests
        WHERE requester_user_id=? AND status NOT IN ('Delivered','Closed','Rejected','Duplicate')""",(citizen_id,)).fetchone()[0]
    today_count = refreshed_db.execute("SELECT COUNT(*) FROM emergency_requests WHERE requester_user_id=? AND substr(created_at,1,10)=date('now','localtime')",(citizen_id,)).fetchone()[0]
    refreshed_db.close()
    assert own_dashboard['openRequests'] == own_open_count
    assert own_dashboard['trend'][-1]['v'] == today_count

    # Another citizen cannot view this request (privacy isolation)
    # Create temp citizen 2
    client.post('/api/auth/register', json={
        'name': 'Pooja Verma',
        'email': 'pooja.citizen@drras.in',
        'password': 'password123',
        'role': 'Citizen'
    })
    client.post('/api/auth/login', json={'email': 'pooja.citizen@drras.in', 'password': 'password123'})
    unauth_req = client.get(f'/api/requests/{req_id}')
    assert unauth_req.status_code == 403

    # -------------------------------------------------------------
    # Step 4: Official verifies the request and adds required items
    # -------------------------------------------------------------
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    ver_res = verify_request_with_team(client, req_id, reason='Field drone report confirmed stranded household on rooftop')
    assert ver_res.status_code == 200
    assert ver_res.get_json()['verification_status'] == 'Verified'

    # Get resource IDs for Water and Food
    res_list = client.get('/api/resources').get_json()
    water_res = next(r for r in res_list if 'Water' in r['name'])
    food_res = next(r for r in res_list if 'Food' in r['name'])

    # Add specific request items
    it1 = client.post(f'/api/requests/{req_id}/items', json={'resource_id': water_res['id'], 'quantity_requested': 10})
    assert it1.status_code == 201
    it2 = client.post(f'/api/requests/{req_id}/items', json={'resource_id': food_res['id'], 'quantity_requested': 3})
    assert it2.status_code == 201

    # -------------------------------------------------------------
    # Step 5: NGO registers donation & Warehouse accepts -> Stock enters ledger
    # -------------------------------------------------------------
    client.post('/api/auth/login', json={'email': 'ngo@drras.in', 'password': 'ngo123'})
    ngo_warehouse=next(w for w in client.get('/api/warehouses').get_json() if w['owner_type']=='ngo')
    don_res = client.post('/api/donations', json={
        'donor_name': 'Punjab Chamber of Relief Donors',
        'donation_type': 'InKind',
        'destination_warehouse_id': ngo_warehouse['id'],
        'incident_id': inc_id,
        'reference_code': f'PCRD-{inc_id}',
        'items': [{'resource_id': food_res['id'], 'quantity_declared': 100}]
    })
    assert don_res.status_code == 201
    don_id = don_res.get_json()['id']

    # Official verifies donation
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    don_detail = client.get(f'/api/donations/{don_id}').get_json()
    d_item_id = don_detail['items'][0]['id']

    don_acc = client.post(f'/api/donations/{don_id}/verify', json={
        'decision': 'Accept',
        'reason': 'All 100 kits received intact',
        'items': [{'donation_item_id': d_item_id, 'quantity_received': 100, 'quantity_accepted': 100, 'quantity_rejected': 0}]
    })
    assert don_acc.status_code == 200

    # -------------------------------------------------------------
    # Step 6: Atomic Allocation (Reserves stock, generates dispatch)
    # -------------------------------------------------------------
    alloc_res = client.post(f'/api/requests/{req_id}/allocate')
    assert alloc_res.status_code == 200
    alloc_data = alloc_res.get_json()
    dsp_id = alloc_data['dispatch_id']

    # -------------------------------------------------------------
    # Step 7: Driver accepts dispatch, starts journey, handles blockage
    # -------------------------------------------------------------
    dsp = client.get(f'/api/dispatches/{dsp_id}').get_json()
    driver_name = dsp['driver']

    conn=get_db()
    driver=conn.execute("SELECT email,password FROM users WHERE role='Driver' AND name=?",(driver_name,)).fetchone()
    from werkzeug.security import check_password_hash
    driver_password=next(p for p in ('driver123','driveDemo26!') if check_password_hash(driver['password'],p))
    conn.close()
    client.post('/api/auth/login', json={'email': driver['email'], 'password': driver_password})

    # Ready & Start trip
    client.post(f'/api/dispatches/{dsp_id}/ready')
    start_res = client.post(f'/api/dispatches/{dsp_id}/start')
    assert start_res.status_code == 200
    assert start_res.get_json()['status'] == 'En route'

    # Route blockage
    blk = client.post(f'/api/dispatches/{dsp_id}/route-blockage', json={'reason': 'Submerged bridge'})
    assert blk.status_code == 200

    # Coordinator reroutes
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    client.post(f'/api/dispatches/{dsp_id}/reroute', json={'destination': 'Old Riverside via High Embankment', 'reason': 'High ridge route clear'})

    # Driver arrives
    client.post('/api/auth/login', json={'email': driver['email'], 'password': driver_password})
    client.post(f'/api/dispatches/{dsp_id}/arrive')

    # Driver submits delivery proof
    prf_res = client.post(f'/api/dispatches/{dsp_id}/delivery-proof', json={
        'proof_type': 'RecipientConfirmation',
        'recipient_confirmation': 'Ramesh Kumar',
        'notes': 'Supplies transferred to boat rescue team for rooftop delivery',
        'items': [
            {'resource_id': water_res['id'], 'quantity_delivered': 10, 'quantity_returned': 0},
            {'resource_id': food_res['id'], 'quantity_delivered': 3, 'quantity_returned': 0}
        ]
    })
    assert prf_res.status_code == 200

    # Supervisor approves delivery proof
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    rev_dsp = client.post(f'/api/dispatches/{dsp_id}/review-delivery', json={'decision': 'Verified', 'reason': 'Rooftop handoff verified'})
    assert rev_dsp.status_code == 200
    assert rev_dsp.get_json()['status'] == 'Delivered'

    # -------------------------------------------------------------
    # Step 8: Citizen confirms delivery
    # -------------------------------------------------------------
    client.post('/api/auth/login', json={'email': 'citizen@drras.in', 'password': 'citizen123'})
    conf_res = client.post(f'/api/requests/{req_id}/confirm-delivery', json={
        'result': 'Received',
        'notes': 'Drinking water and rations received in excellent condition. Thank you!'
    })
    assert conf_res.status_code == 200
    post_delivery_dashboard = client.get('/api/dashboard').get_json()
    conn = database.get_db()
    own_open_count = conn.execute("""SELECT COUNT(*) FROM emergency_requests
        WHERE requester_user_id=? AND status NOT IN ('Delivered','Closed','Rejected','Duplicate')""",(citizen_id,)).fetchone()[0]
    conn.close()
    assert post_delivery_dashboard['openRequests'] == own_open_count

    # -------------------------------------------------------------
    # Step 9: Volunteer task distribution and live reconciliation
    # -------------------------------------------------------------
    client.post('/api/auth/login', json={'email': 'ngo@drras.in', 'password': 'ngo123'})
    vols=client.get('/api/volunteers').get_json()
    active_volunteers={t['volunteer_id'] for t in client.get('/api/volunteer-tasks').get_json() if t['status'] in ('Assigned','Accepted','In Progress','Submitted for Review','Needs Correction')}
    volunteer=next(v for v in vols if v['owner_type']=='ngo' and v['status']=='Available' and v['verified'] and v['id'] not in active_volunteers)
    conn=__import__('database').get_db(); volunteer_email=conn.execute('SELECT email FROM users WHERE id=?',(volunteer['user_id'],)).fetchone()['email']; conn.close()
    v_task_res = client.post('/api/volunteer-tasks', json={
        'title': 'Field distribution of 20 hygiene packets',
        'task_type': 'Distribution',
        'description': 'Deliver hygiene packs to evacuated riverside families',
        'volunteer_id': volunteer['id'],
        'quantity_expected': 20,
        'incident_id': inc_id,
        'zone_id': zone_id
    })
    assert v_task_res.status_code==201,v_task_res.get_json()
    v_task_id=v_task_res.get_json()['id']

    # The selected account owns the Volunteer roster record and is approved through this NGO.
    client.post('/api/auth/login',json={'email':volunteer_email,'password':'volunteer123'})
    client.post(f'/api/volunteer-tasks/{v_task_id}/accept')
    client.post(f'/api/volunteer-tasks/{v_task_id}/check-in', json={'lat': 30.935, 'lng': 75.815, 'notes': 'On field'})
    v_sub = client.post(f'/api/volunteer-tasks/{v_task_id}/submit', json={
        'quantity_received': 20,
        'quantity_completed': 18,
        'quantity_damaged': 1,
        'quantity_remaining': 1,
        'notes': '18 distributed, 1 pack crushed, 1 returned'
    })
    assert v_sub.status_code == 200

    # Supervisor approves task
    client.post('/api/auth/login', json={'email': 'ngo@drras.in', 'password': 'ngo123'})
    v_app = client.post(f'/api/volunteer-tasks/{v_task_id}/approve', json={'reason': 'Field counts verified'})
    assert v_app.status_code == 200
    assert v_app.get_json()['status'] == 'Completed'

    # -------------------------------------------------------------
    # Step 10: Shelter Admission & Zero-Double-Counting Transfer
    # -------------------------------------------------------------
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    shelters = client.get('/api/shelters').get_json()
    sh1_id = shelters[0]['id']
    sh2_id = shelters[1]['id']

    adm_res = client.post(f'/api/shelters/{sh1_id}/admissions', json={
        'people_count': 8,
        'incident_id': inc_id,
        'household_reference': 'HH-E2E-FLOOD',
        'notes': 'Rescued family admitted'
    })
    assert adm_res.status_code == 201
    adm_id = adm_res.get_json()['id']

    trf_res = client.post(f'/api/shelter-admissions/{adm_id}/transfer', json={
        'to_shelter_id': sh2_id,
        'people_count': 4,
        'reason': 'Specialized medical care transfer'
    })
    assert trf_res.status_code == 200
    assert trf_res.get_json()['status'] == 'Completed'

    # -------------------------------------------------------------
    # Step 11: Finance & Incident Operational Report
    # -------------------------------------------------------------
    # Budget & Fund request
    client.post('/api/fund-budgets', json={
        'incident_id': inc_id,
        'category': 'Emergency Logistics',
        'budget_amount_paise': 20000000
    })

    client.post('/api/auth/login', json={'email': 'ngo@drras.in', 'password': 'ngo123'})
    fr_res = client.post('/api/fund-requests', json={
        'incident_id': inc_id,
        'category': 'Emergency Logistics',
        'purpose': 'Fuel and boat rental expenses',
        'requested_amount_paise': 5000000
    })
    fr_id = fr_res.get_json()['id']

    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    client.post(f'/api/fund-requests/{fr_id}/approve', json={'approved_amount_paise': 5000000, 'reason': 'Approved'})
    client.post(f'/api/fund-requests/{fr_id}/commit', json={'reference': 'PO-FUEL-01'})
    client.post(f'/api/fund-requests/{fr_id}/pay', json={'amount_paise': 5000000, 'reference_code': 'UTR-FUEL-88'})
    client.post(f'/api/fund-requests/{fr_id}/reconcile', json={'reason': 'Fuel vouchers reconciled'})

    # Verify Incident Operational Report reflects database state
    rep_res = client.get(f'/api/incidents/{inc_id}/report')
    assert rep_res.status_code == 200
    rep = rep_res.get_json()

    assert rep['incident']['id'] == inc_id
    assert rep['requests']['total'] >= 1
    assert rep['finance']['total_paid_paise'] == 5000000
    assert rep['shelter_admissions'] >= 1

    # Verify Admin Audit Trail has logged these actions
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    audit_res = client.get('/api/admin/audit-logs')
    assert audit_res.status_code == 200
    logs = audit_res.get_json()
    assert len(logs) > 0
