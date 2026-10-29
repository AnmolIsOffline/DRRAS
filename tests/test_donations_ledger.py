import pytest

def test_donation_intake_verification_and_stock_ledger(client):
    # 1. NGO Coordinator logs in and creates in-kind donation
    client.post('/api/auth/login', json={'email': 'ngo@drras.in', 'password': 'ngo123'})

    # Get resource ID for Food Ration Kits
    res_list = client.get('/api/resources').get_json()
    food_res = next(r for r in res_list if 'Food' in r['name'])

    # Record initial inventory stock for Food Ration Kits
    inv_list = client.get('/api/inventory').get_json()
    inv_food = next(i for i in inv_list if 'Food' in i['resource_name'])
    initial_stock = inv_food['available_units']

    # Submit in-kind donation
    ngo_warehouse=next(w for w in client.get('/api/warehouses').get_json() if w['owner_type']=='ngo')
    don_res = client.post('/api/donations', json={
        'donor_name': 'Rotary Club of Punjab',
        'donation_type': 'InKind',
        'destination_warehouse_id': ngo_warehouse['id'],
        'reference_code': 'ROT-DON-2026',
        'notes': '500 emergency dry food kits',
        'items': [
            {'resource_id': food_res['id'], 'quantity_declared': 500}
        ]
    })
    assert don_res.status_code == 201
    don_data = don_res.get_json()
    don_id = don_data['id']
    assert don_data['status'] == 'Submitted'

    # Unverified donation MUST NOT affect warehouse stock yet
    inv_unverified = client.get('/api/inventory').get_json()
    inv_food_unver = next(i for i in inv_unverified if i['id'] == inv_food['id'])
    assert inv_food_unver['available_units'] == initial_stock

    # Get donation items
    don_detail = client.get(f'/api/donations/{don_id}').get_json()
    assert len(don_detail['items']) == 1
    d_item_id = don_detail['items'][0]['id']

    # 2. Government Official verifies shipment with DISCREPANCY:
    # Declared: 500, Received: 480, Accepted: 480, Rejected: 20
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    ver_res = client.post(f'/api/donations/{don_id}/verify', json={
        'decision': 'Accept',
        'reason': 'Verified by warehouse manager: 480 accepted, 20 water-damaged',
        'items': [
            {
                'donation_item_id': d_item_id,
                'quantity_received': 480,
                'quantity_accepted': 480,
                'quantity_rejected': 20,
                'reason': '20 packages damaged by rain'
            }
        ]
    })
    assert ver_res.status_code == 200
    assert ver_res.get_json()['status'] == 'Accepted'

    # Check the destination NGO's scoped stock after Government verification.
    client.post('/api/auth/login', json={'email':'ngo@drras.in','password':'ngo123'})
    # 3. Verify ONLY verified/accepted quantity (480) entered inventory stock!
    inv_after = client.get('/api/inventory').get_json()
    inv_food_after = next(i for i in inv_after if i['id'] == inv_food['id'])
    assert inv_food_after['available_units'] == initial_stock + 480

    # 4. Verify stock ledger entry was generated
    tx_list = client.get('/api/inventory/transactions').get_json()
    don_tx = next(t for t in tx_list if t['reference_type'] == 'donations' and t['reference_id'] == don_id)
    assert don_tx['quantity_units'] == 480
    assert don_tx['direction'] == 'IN'

    # 5. Idempotency guard: Attempting to verify/accept again MUST be rejected (no duplicate stock credit)
    client.post('/api/auth/login',json={'email':'official@drras.in','password':'official123'})
    ver_retry = client.post(f'/api/donations/{don_id}/verify', json={
        'decision': 'Accept',
        'reason': 'Duplicate retry',
        'items': [{'donation_item_id': d_item_id, 'quantity_received': 480, 'quantity_accepted': 480}]
    })
    assert ver_retry.status_code == 400
    assert 'already' in ver_retry.get_json()['error'].lower()

    # Stock balance must remain unchanged (+480, not +960)
    client.post('/api/auth/login',json={'email':'ngo@drras.in','password':'ngo123'})
    inv_retry = client.get('/api/inventory').get_json()
    inv_food_retry = next(i for i in inv_retry if i['id'] == inv_food['id'])
    assert inv_food_retry['available_units'] == initial_stock + 480
