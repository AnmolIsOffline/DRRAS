import pytest

def test_shelter_capacity_boundary_and_atomic_transfer(client):
    # 1. Official logs in
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})

    shelters = client.get('/api/shelters').get_json()
    assert len(shelters) >= 2
    s1 = shelters[0]
    s2 = shelters[1]
    s1_id = s1['id']
    s2_id = s2['id']

    s1_initial_occ = s1['occupants']
    s1_cap = s1['capacity']
    s2_initial_occ = s2['occupants']
    s2_cap = s2['capacity']

    # 2. Attempt admission that exceeds shelter capacity
    excess_people = (s1_cap - s1_initial_occ) + 50
    bad_adm = client.post(f'/api/shelters/{s1_id}/admissions', json={
        'people_count': excess_people,
        'household_reference': 'HH-EXCESS-01',
        'notes': 'Overcrowding attempt'
    })
    assert bad_adm.status_code == 409
    assert 'capacity' in bad_adm.get_json()['error'].lower()

    # Verify shelter 1 occupancy remained unchanged
    s1_chk = next(s for s in client.get('/api/shelters').get_json() if s['id'] == s1_id)
    assert s1_chk['occupants'] == s1_initial_occ

    # 3. Valid admission (10 people into shelter 1)
    adm_res = client.post(f'/api/shelters/{s1_id}/admissions', json={
        'people_count': 10,
        'household_reference': 'HH-EVAC-10',
        'notes': 'Family evacuated from flooded riverside'
    })
    assert adm_res.status_code == 201
    adm_data = adm_res.get_json()
    adm_id = adm_data['id']
    assert adm_data['status'] == 'Admitted'

    # Verify shelter 1 occupancy increased by 10
    s1_after_adm = next(s for s in client.get('/api/shelters').get_json() if s['id'] == s1_id)
    assert s1_after_adm['occupants'] == s1_initial_occ + 10

    # 4. Atomic transfer of 6 people from shelter 1 to shelter 2
    trans_res = client.post(f'/api/shelter-admissions/{adm_id}/transfer', json={
        'to_shelter_id': s2_id,
        'people_count': 6,
        'reason': 'Transferred to higher-ground medical support shelter'
    })
    assert trans_res.status_code == 200
    trans_data = trans_res.get_json()
    assert trans_data['status'] == 'Completed'

    # 5. Zero Double-Counting Verification:
    # Shelter 1 occupants must be: (s1_initial_occ + 10) - 6
    # Shelter 2 occupants must be: s2_initial_occ + 6
    # Total sum of occupants across both shelters must equal: s1_initial_occ + s2_initial_occ + 10
    shelters_final = client.get('/api/shelters').get_json()
    s1_final = next(s for s in shelters_final if s['id'] == s1_id)
    s2_final = next(s for s in shelters_final if s['id'] == s2_id)

    assert s1_final['occupants'] == (s1_initial_occ + 10) - 6
    assert s2_final['occupants'] == s2_initial_occ + 6
    assert (s1_final['occupants'] + s2_final['occupants']) == (s1_initial_occ + s2_initial_occ + 10)


def test_shelter_admissions_unauthorized_access(client):
    # Citizen attempts to admit occupants
    client.post('/api/auth/login', json={'email': 'citizen@drras.in', 'password': 'citizen123'})
    res = client.post('/api/shelters/1/admissions', json={'people_count': 4})
    assert res.status_code == 403
