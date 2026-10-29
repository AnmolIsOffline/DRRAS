from conftest import verify_request_with_team
import pytest
from database import calc_priority

def test_priority_score_algorithm_combinations():
    # 1. Base condition: people <= 8, vulnerable = False, non-medical need
    assert calc_priority(5, False, 'Food ration') == 58
    assert calc_priority(8, False, 'Blankets') == 58

    # 2. Vulnerable only: 58 + 25 = 83
    assert calc_priority(4, True, 'Food ration') == 83
    assert calc_priority(4, 'yes', 'Food ration') == 83
    assert calc_priority(4, 'true', 'Food ration') == 83

    # 3. People > 8 only: 58 + 10 = 68
    assert calc_priority(9, False, 'Food ration') == 68
    assert calc_priority(20, False, 'Food ration') == 68

    # 4. Medical / Rescue only: 58 + 10 = 68
    assert calc_priority(4, False, 'Medical kit') == 68
    assert calc_priority(4, False, 'Search and rescue') == 68

    # 5. Vulnerable + People > 8: 58 + 25 + 10 = 93
    assert calc_priority(12, True, 'Food ration') == 93

    # 6. Vulnerable + Medical: 58 + 25 + 10 = 93
    assert calc_priority(4, True, 'Medical emergency') == 93

    # 7. People > 8 + Rescue: 58 + 10 + 10 = 78
    assert calc_priority(15, False, 'Rescue operation') == 78

    # 8. All conditions met: 58 + 25 + 10 + 10 = 103 -> capped at 99
    assert calc_priority(15, True, 'Immediate medical rescue') == 99

def test_get_all_requests_sorted(client):
    res = client.get('/api/requests')
    assert res.status_code == 200
    reqs = res.get_json()
    assert len(reqs) >= 4
    # Verify sorted by priority DESC
    priorities = [r['priority_score'] for r in reqs]
    assert priorities == sorted(priorities, reverse=True)

def test_create_valid_request(client):
    payload = {
        'name': 'Sardar Singh',
        'area': 'Ward 5 Relief Camp',
        'address': 'Main Gate, Govt Senior Secondary School',
        'need': 'Medical kit & drinking water',
        'people': 6,
        'vulnerable': True,
        'lat': 30.9100,
        'lng': 75.8500
    }
    res = client.post('/api/requests', json=payload)
    assert res.status_code == 201
    created = res.get_json()
    assert created['id'].startswith('REQ-')
    assert created['requester_name'] == 'Sardar Singh'
    assert created['priority_score'] == 93  # 58 + 25 + 10
    assert created['status'] == 'Awaiting allocation'

def test_create_request_validation_errors(client):
    base = {
        'name': 'Test User',
        'area': 'Test Area',
        'address': 'Test Address',
        'need': 'Food ration',
        'people': 4,
        'lat': 30.9,
        'lng': 75.8
    }

    # Missing name
    p1 = base.copy(); p1['name'] = ''
    assert client.post('/api/requests', json=p1).status_code == 400

    # Missing area
    p2 = base.copy(); p2['area'] = '   '
    assert client.post('/api/requests', json=p2).status_code == 400

    # Missing need
    p3 = base.copy(); p3['need'] = ''
    assert client.post('/api/requests', json=p3).status_code == 400

    # Missing address
    p4 = base.copy(); p4['address'] = ''
    assert client.post('/api/requests', json=p4).status_code == 400

    # Zero people
    p5 = base.copy(); p5['people'] = 0
    assert client.post('/api/requests', json=p5).status_code == 400

    # Negative people
    p6 = base.copy(); p6['people'] = -5
    assert client.post('/api/requests', json=p6).status_code == 400

    # Non-numeric people
    p7 = base.copy(); p7['people'] = "many"
    assert client.post('/api/requests', json=p7).status_code == 400

    # Excessively large people count (> 100,000)
    p8 = base.copy(); p8['people'] = 9999999
    assert client.post('/api/requests', json=p8).status_code == 400

    # Invalid latitude (> 90 or < -90)
    p9 = base.copy(); p9['lat'] = 95.0
    assert client.post('/api/requests', json=p9).status_code == 400

    # Invalid longitude (> 180 or < -180)
    p10 = base.copy(); p10['lng'] = -200.0
    assert client.post('/api/requests', json=p10).status_code == 400

def test_request_id_uniqueness(client):
    ids = set()
    for i in range(5):
        payload = {
            'name': f'Requester {i}',
            'area': f'Area {i}',
            'address': f'Street {i}',
            'need': 'Drinking water',
            'people': 2
        }
        res = client.post('/api/requests', json=payload)
        assert res.status_code == 201
        new_id = res.get_json()['id']
        assert new_id not in ids, f"Duplicate request ID generated: {new_id}"
        ids.add(new_id)

def test_allocation_workflow_and_dispatch_linking(client):
    # Log in as Administrator
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})

    # Create request awaiting allocation
    req_res = client.post('/api/requests', json={
        'name': 'Gurcharan Singh',
        'area': 'Model Town Sector 2',
        'address': 'Plot 44, Model Town',
        'need': 'Food ration kits',
        'people': 10
    })
    req_id = req_res.get_json()['id']

    # Official verification is required before normal allocation.
    client.post('/api/auth/logout')
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    ver = verify_request_with_team(client, req_id)
    assert ver.status_code == 200
    client.post('/api/auth/logout')
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    alloc_res = client.post(f'/api/requests/{req_id}/allocate')
    assert alloc_res.status_code == 200
    allocated = alloc_res.get_json()
    assert allocated['status'] == 'Allocated'

    # Verify dispatch was created and linked to this request
    disp_res = client.get('/api/dispatches')
    assert disp_res.status_code == 200
    dispatches = disp_res.get_json()
    linked_dispatch = next((d for d in dispatches if d['request_id'] == req_id), None)
    assert linked_dispatch is not None
    assert linked_dispatch['destination'] == 'Model Town Sector 2'

    # Test repeated allocation: should be idempotent and not create duplicate dispatches
    dsp_count_before = len(dispatches)
    alloc_repeat = client.post(f'/api/requests/{req_id}/allocate')
    assert alloc_repeat.status_code == 200
    disp_res2 = client.get('/api/dispatches')
    assert len(disp_res2.get_json()) == dsp_count_before

def test_allocate_nonexistent_request(client):
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    res = client.post('/api/requests/REQ-99999/allocate')
    assert res.status_code == 404
    assert 'error' in res.get_json()

def test_vulnerable_person_all_supported_formats(client):
    supported = [True, 'yes', 'Yes', 'YES', 'true', 'TRUE', 'True', '1', 1]
    for val in supported:
        payload = {
            'name': 'Format Test',
            'area': 'Ward 3',
            'address': 'Street 3',
            'need': 'Drinking water',
            'people': 4,
            'vulnerable': val
        }
        res = client.post('/api/requests', json=payload)
        assert res.status_code == 201
        # 58 (base) + 25 (vulnerable) = 83
        assert res.get_json()['priority_score'] == 83, f"Failed for format {val}"

def test_cannot_reallocate_delivered_request(client):
    # Admin logs in
    client.post('/api/auth/login', json={'email': 'admin@drras.in', 'password': 'admin123'})
    
    # REQ-2045 is seeded as 'Delivered'
    res = client.post('/api/requests/REQ-2045/allocate')
    assert res.status_code == 400
    assert 'already been delivered' in res.get_json()['error'].lower()

def test_unauthorized_allocation_by_citizen(client):
    # Citizen logs in
    client.post('/api/auth/login', json={'email': 'citizen@drras.in', 'password': 'citizen123'})
    res = client.post('/api/requests/REQ-2048/allocate')
    assert res.status_code == 403
    assert 'access denied' in res.get_json()['error'].lower()

def test_create_request_strict_type_validations(client):
    base = {'name': 'Test', 'area': 'Area', 'address': 'Addr', 'need': 'Food'}

    # 1. Boolean for people count
    res_bool = client.post('/api/requests', json={**base, 'people': True})
    assert res_bool.status_code == 400

    # 2. Float for people count
    res_float = client.post('/api/requests', json={**base, 'people': 4.5})
    assert res_float.status_code == 400

    # 3. Boolean for lat/lng
    res_coord_bool = client.post('/api/requests', json={**base, 'people': 2, 'lat': True})
    assert res_coord_bool.status_code == 400

