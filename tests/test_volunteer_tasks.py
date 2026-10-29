import pytest
from database import get_db

def test_volunteer_task_lifecycle_and_quantity_reconciliation(client):
    # 1. Login as NGO Coordinator
    client.post('/api/auth/login', json={'email': 'ngo@drras.in', 'password': 'ngo123'})

    # Get volunteer list
    v_list = client.get('/api/volunteers').get_json()
    assert len(v_list) > 0
    active_ids={t['volunteer_id'] for t in client.get('/api/volunteer-tasks').get_json() if t['status'] in ('Assigned','Accepted','In Progress','Submitted for Review','Needs Correction')}
    vol=next(v for v in v_list if v['status']=='Available' and v['id'] not in active_ids)
    vol_id=vol['id']
    conn=get_db(); volunteer_email=conn.execute('SELECT u.email FROM users u JOIN volunteers v ON v.user_id=u.id WHERE v.id=?',(vol_id,)).fetchone()['email']; conn.close()

    # 2. Coordinator creates a distribution task for volunteer
    task_res = client.post('/api/volunteer-tasks', json={
        'title': 'Distribute 50 Food Kits in Ward 8',
        'task_type': 'Distribution',
        'description': 'Door to door relief delivery for flooded homes',
        'volunteer_id': vol_id,
        'quantity_expected': 50
    })
    assert task_res.status_code == 201
    task = task_res.get_json()
    task_id = task['id']
    assert task['status'] == 'Assigned'

    # 3. Login as the Volunteer account linked to this organization's assigned roster record.
    conn=get_db(); pw='volunteer123' if volunteer_email=='volunteer@drras.in' else 'volunteer123'; conn.close()
    client.post('/api/auth/login', json={'email': volunteer_email, 'password': pw})

    # Accept task
    acc_res = client.post(f'/api/volunteer-tasks/{task_id}/accept')
    assert acc_res.status_code == 200
    assert acc_res.get_json()['status'] == 'Accepted'

    # Field check-in
    chk_res = client.post(f'/api/volunteer-tasks/{task_id}/check-in', json={
        'lat': 30.9010,
        'lng': 75.8573,
        'notes': 'Arrived at distribution point Ward 8 Community Center'
    })
    assert chk_res.status_code == 200
    assert chk_res.get_json()['status'] == 'In Progress'

    # 4. Attempt to submit with broken reconciliation equation:
    # Received: 50, Completed: 40, Damaged: 2, Remaining: 5 => Sum is 47 != 50! Must be rejected!
    bad_sub = client.post(f'/api/volunteer-tasks/{task_id}/submit', json={
        'quantity_received': 50,
        'quantity_completed': 40,
        'quantity_damaged': 2,
        'quantity_remaining': 5,
        'notes': 'Some unaccounted shortage'
    })
    assert bad_sub.status_code == 400
    assert 'reconcil' in bad_sub.get_json()['error'].lower()

    # 5. Submit with accurate reconciliation equation:
    # Received: 50, Completed: 45, Damaged: 2, Remaining: 3 => 45 + 2 + 3 = 50!
    good_sub = client.post(f'/api/volunteer-tasks/{task_id}/submit', json={
        'quantity_received': 50,
        'quantity_completed': 45,
        'quantity_damaged': 2,
        'quantity_remaining': 3,
        'notes': '45 distributed successfully, 2 packages soaked in floodwater, 3 returned'
    })
    assert good_sub.status_code == 200
    assert good_sub.get_json()['status'] == 'Submitted for Review'

    # 6. Volunteer cannot approve their own task
    self_app = client.post(f'/api/volunteer-tasks/{task_id}/approve', json={'reason': 'Self approved'})
    assert self_app.status_code == 403

    # 7. Supervisor (NGO or Official) logs in and approves task
    client.post('/api/auth/login', json={'email': 'ngo@drras.in', 'password': 'ngo123'})
    app_res = client.post(f'/api/volunteer-tasks/{task_id}/approve', json={'reason': 'Distribution ledger verified'})
    assert app_res.status_code == 200
    assert app_res.get_json()['status'] == 'Completed'


def test_volunteer_task_rbac_isolation(client):
    # Setup task for volunteer 1
    client.post('/api/auth/login', json={'email': 'ngo@drras.in', 'password': 'ngo123'})
    v_list = client.get('/api/volunteers').get_json()
    active_ids={t['volunteer_id'] for t in client.get('/api/volunteer-tasks').get_json() if t['status'] in ('Assigned','Accepted','In Progress','Submitted for Review','Needs Correction')}
    volunteer=next(v for v in v_list if v['status']=='Available' and v['id'] not in active_ids)
    task_res = client.post('/api/volunteer-tasks', json={
        'title': 'Medical Triage Support',
        'task_type': 'Medical',
        'description': 'Assist medical team',
        'volunteer_id': volunteer['id'],
        'quantity_expected': 0
    })
    task_id = task_res.get_json()['id']

    # Citizen cannot access or mutate volunteer task
    client.post('/api/auth/login', json={'email': 'citizen@drras.in', 'password': 'citizen123'})
    res = client.post(f'/api/volunteer-tasks/{task_id}/accept')
    assert res.status_code == 403
