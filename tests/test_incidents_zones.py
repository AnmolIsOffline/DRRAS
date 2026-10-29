import pytest

def test_incident_lifecycle_and_zone_adoptions(client):
    # 1. Government Official logs in
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})

    # Create new incident
    create_res = client.post('/api/incidents', json={
        'title': 'Test Monsoon Cloudburst',
        'incident_type': 'Flood',
        'severity': 'Severe',
        'district': 'Demo District',
        'description': 'Rapid localized inundation across low sectors'
    })
    assert create_res.status_code == 201
    inc_data = create_res.get_json()
    inc_id = inc_data['id']
    assert inc_data['status'] == 'Active'

    # Create zone under incident
    zone_res = client.post(f'/api/incidents/{inc_id}/zones', json={
        'name': 'Sector 14 Bund Area',
        'severity': 'Critical',
        'district': 'Demo District',
        'center_lat': 30.92,
        'center_lng': 75.84
    })
    assert zone_res.status_code == 201
    zone_data = zone_res.get_json()
    zone_id = zone_data['id']

    # Stabilize incident
    stab_res = client.post(f'/api/incidents/{inc_id}/stabilize', json={'reason': 'Water level receded by 3 feet'})
    assert stab_res.status_code == 200
    assert stab_res.get_json()['status'] == 'Stabilizing'

    # 2. NGO Coordinator logs in and requests zone adoption
    client.post('/api/auth/login', json={'email': 'ngo@drras.in', 'password': 'ngo123'})
    adp_res = client.post(f'/api/zones/{zone_id}/adoptions', json={
        'requested_capacity': 'Medical triage and clean water',
        'available_volunteers': 15,
        'available_resource_summary': '1 Relief Van, 200 kits'
    })
    assert adp_res.status_code == 201
    adp_id = adp_res.get_json()['adoption_id']

    # 3. Government Official reviews and approves adoption
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    appr_res = client.post(f'/api/adoptions/{adp_id}/approve', json={'reason': 'Verified NGO credential & capacity'})
    assert appr_res.status_code == 200

    # Verify adoption status is Approved
    adps = client.get(f'/api/zones/{zone_id}/adoptions').get_json()
    approved_adp = next(a for a in adps if a['id'] == adp_id)
    assert approved_adp['status'] == 'Approved'

    # Close incident
    close_res = client.post(f'/api/incidents/{inc_id}/close', json={'reason': 'All operations completed'})
    assert close_res.status_code == 200
    assert close_res.get_json()['status'] == 'Closed'

def test_unauthorized_incident_creation_by_citizen(client):
    client.post('/api/auth/login', json={'email': 'citizen@drras.in', 'password': 'citizen123'})
    res = client.post('/api/incidents', json={'title': 'Unauthorized Incident', 'description': 'Test'})
    assert res.status_code == 403
