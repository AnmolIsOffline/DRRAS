from werkzeug.security import check_password_hash

import database


def _credentials_for_assignment(request_id):
    conn=database.get_db()
    row=conn.execute("SELECT a.id AS assignment_id,u.id AS user_id,u.email,u.password FROM response_assignments a JOIN users u ON u.id=a.driver_user_id WHERE a.request_id=? ORDER BY a.id DESC LIMIT 1",(request_id,)).fetchone()
    conn.close()
    password=next(candidate for candidate in ('driver123','driveDemo26!') if check_password_hash(row['password'],candidate))
    return row['assignment_id'],row['email'],password


def _create_request(client):
    client.post('/api/auth/login',json={'email':'citizen@drras.in','password':'citizen123'})
    response=client.post('/api/requests',json={'name':'Assignment Test Citizen','area':'Ward 8','address':'Relief Lane','need':'Food ration kits and water','people':5,'incident_id':'INC-2026-FLOOD','zone_id':'Z-01'})
    assert response.status_code==201,response.get_json()
    return response.get_json()['id']


def _assign_government_team(client, request_id, exclude_driver_id=None):
    options=client.get(f'/api/government/response-options/{request_id}').get_json()
    personnel=next(item for item in options['personnel'] if item['available'])
    driver=next(item for item in options['drivers'] if item['available'] and item['id'] != exclude_driver_id)
    vehicle=next(item for item in options['vehicles'] if item['available'])
    return client.post(f'/api/requests/{request_id}/verify',json={'decision':'Verified','reason':'Government team assignment','response_personnel_id':personnel['id'],'driver_user_id':driver['id'],'vehicle_id':vehicle['id']}),driver['id']


def test_government_driver_can_accept_decline_and_be_reassigned(client):
    request_id=_create_request(client)
    client.post('/api/auth/login',json={'email':'official@drras.in','password':'official123'})
    verified,first_driver_id=_assign_government_team(client,request_id)
    assert verified.status_code==200,verified.get_json()
    assignment_id,driver_email,driver_password=_credentials_for_assignment(request_id)

    client.post('/api/auth/login',json={'email':driver_email,'password':driver_password})
    pending=next(row for row in client.get('/api/driver/assignments').get_json() if row['request_id']==request_id)
    assert pending['driver_decision']=='Pending'
    declined=client.post(f"/api/driver/assignments/{assignment_id}/decline",json={'reason':'Driver unavailable for this shift'})
    assert declined.status_code==200,declined.get_json()
    assert declined.get_json()['driver_decision']=='Declined'

    conn=database.get_db()
    state=conn.execute("SELECT a.status,a.driver_decision,v.status AS vehicle_status,v.current_driver_user_id,r.response_owner_type,r.status AS request_status FROM response_assignments a JOIN vehicles v ON v.id=a.vehicle_id JOIN emergency_requests r ON r.id=a.request_id WHERE a.id=?",(assignment_id,)).fetchone()
    conn.close()
    assert state['status']=='Cancelled'
    assert state['vehicle_status']=='Available' and state['current_driver_user_id'] is None
    assert state['response_owner_type']=='government' and state['request_status']=='Awaiting allocation'

    client.post('/api/auth/login',json={'email':'official@drras.in','password':'official123'})
    reassigned,new_driver_id=_assign_government_team(client,request_id,exclude_driver_id=first_driver_id)
    assert reassigned.status_code==200,reassigned.get_json()
    conn=database.get_db()
    updated=conn.execute("SELECT id,driver_user_id,status,driver_decision FROM response_assignments WHERE request_id=?",(request_id,)).fetchone()
    conn.close()
    assert updated['id']==assignment_id and updated['driver_user_id']==new_driver_id
    assert updated['status']=='Assigned' and updated['driver_decision']=='Pending'
    blocked=client.post(f'/api/requests/{request_id}/allocate',json={})
    assert blocked.status_code==409 and blocked.get_json()['code']=='DRIVER_ACCEPTANCE_PENDING'

    _,new_email,new_password=_credentials_for_assignment(request_id)
    client.post('/api/auth/login',json={'email':new_email,'password':new_password})
    pending=next(row for row in client.get('/api/driver/assignments').get_json() if row['request_id']==request_id)
    accepted=client.post(f"/api/driver/assignments/{pending['assignment_id']}/accept",json={})
    assert accepted.status_code==200 and accepted.get_json()['driver_decision']=='Accepted'
    client.post('/api/auth/login',json={'email':'official@drras.in','password':'official123'})
    allocated=client.post(f'/api/requests/{request_id}/allocate',json={})
    assert allocated.status_code==200,allocated.get_json()


def test_ngo_assigned_driver_sees_and_accepts_the_response(client):
    request_id=_create_request(client)
    client.post('/api/auth/login',json={'email':'ngo@drras.in','password':'ngo123'})
    options=client.get(f'/api/ngo/response-options/{request_id}').get_json()
    payload={'volunteer_id':next(v['id'] for v in options['volunteers'] if v['available']),
             'driver_user_id':next(d['id'] for d in options['drivers'] if d['available']),
             'vehicle_id':next(v['id'] for v in options['vehicles'] if v['available']),
             'notes':'Paired NGO field response'}
    assigned=client.post(f'/api/requests/{request_id}/ngo-assign',json=payload)
    assert assigned.status_code==201,assigned.get_json()
    assignment_id,driver_email,driver_password=_credentials_for_assignment(request_id)
    assert assigned.get_json()['driver_decision']=='Pending'

    client.post('/api/auth/login',json={'email':driver_email,'password':driver_password})
    pending=next(row for row in client.get('/api/driver/assignments').get_json() if row['request_id']==request_id)
    assert pending['owner_type']=='ngo' and pending['assignment_id']==assignment_id
    accepted=client.post(f"/api/driver/assignments/{assignment_id}/accept",json={})
    assert accepted.status_code==200 and accepted.get_json()['driver_decision']=='Accepted'

    client.post('/api/auth/login',json={'email':'ngo@drras.in','password':'ngo123'})
    allocated=client.post(f'/api/requests/{request_id}/allocate',json={})
    assert allocated.status_code==200,allocated.get_json()


def test_driver_assignment_actions_are_restricted_to_the_assigned_driver(client):
    request_id=_create_request(client)
    client.post('/api/auth/login',json={'email':'official@drras.in','password':'official123'})
    verified,first_driver_id=_assign_government_team(client,request_id)
    assert verified.status_code==200
    assignment_id,_,_=_credentials_for_assignment(request_id)
    conn=database.get_db()
    other=conn.execute("SELECT u.email,u.password FROM users u JOIN government_driver_approvals a ON a.user_id=u.id WHERE u.role='Driver' AND u.id<>? ORDER BY u.id LIMIT 1",(first_driver_id,)).fetchone()
    conn.close()
    other_password=next(candidate for candidate in ('driver123','driveDemo26!') if check_password_hash(other['password'],candidate))
    client.post('/api/auth/login',json={'email':other['email'],'password':other_password})
    denied=client.post(f'/api/driver/assignments/{assignment_id}/accept',json={})
    assert denied.status_code==403
