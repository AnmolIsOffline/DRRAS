import pytest

def test_fund_request_dual_control_lifecycle_and_paise(client):
    # 1. Government Official sets up an incident and fund budget
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    
    # Create incident
    inc_res = client.post('/api/incidents', json={
        'title': 'Monsoon Relief Fund Incident',
        'incident_type': 'Flood',
        'severity': 'Severe',
        'description': 'District flood response finance pool',
        'district': 'Ludhiana District'
    })
    inc_id = inc_res.get_json()['id']

    # Create Budget of 10,00,000 INR = 1,00,00,000 paise (integer)
    bgt_res = client.post('/api/fund-budgets', json={
        'incident_id': inc_id,
        'category': 'Emergency Rations',
        'budget_amount_paise': 10000000
    })
    assert bgt_res.status_code == 201

    # 2. NGO Coordinator logs in and creates a Fund Request
    client.post('/api/auth/login', json={'email': 'ngo@drras.in', 'password': 'ngo123'})
    req_res = client.post('/api/fund-requests', json={
        'incident_id': inc_id,
        'category': 'Emergency Rations',
        'purpose': 'Bulk procurement of rice, lentils and drinking water',
        'requested_amount_paise': 4500000  # 45,000 INR
    })
    assert req_res.status_code == 201
    fr_data = req_res.get_json()
    fr_id = fr_data['id']
    assert fr_data['status'] == 'Submitted'
    assert fr_data['requested_amount_paise'] == 4500000

    # 3. Dual-Control Enforcement:
    # NGO Coordinator CANNOT approve their own request!
    self_app = client.post(f'/api/fund-requests/{fr_id}/approve', json={
        'approved_amount_paise': 4500000,
        'reason': 'Self approval'
    })
    assert self_app.status_code == 403

    # 4. Government Official logs in and approves the request
    client.post('/api/auth/login', json={'email': 'official@drras.in', 'password': 'official123'})
    app_res = client.post(f'/api/fund-requests/{fr_id}/approve', json={
        'approved_amount_paise': 4000000,  # 40,000 INR approved (partial)
        'reason': 'Approved according to district procurement schedule'
    })
    assert app_res.status_code == 200
    assert app_res.get_json()['status'] == 'Approved'
    assert app_res.get_json()['approved_amount_paise'] == 4000000

    # 5. Commit funds
    comm_res = client.post(f'/api/fund-requests/{fr_id}/commit', json={
        'reference': 'PO-GRAIN-2026-08',
        'reason': 'Purchase order issued to grain supplier'
    })
    assert comm_res.status_code == 200
    assert comm_res.get_json()['status'] == 'Committed'

    # Verify commitment transaction was recorded in integer paise
    txs = client.get(f'/api/fund-transactions?incident_id={inc_id}').get_json()
    comm_tx = next(t for t in txs if t['transaction_type'] == 'Commitment' and t['fund_request_id'] == fr_id)
    assert comm_tx['amount_paise'] == 4000000

    # 6. Attempt payment exceeding committed/approved amount (e.g. 50,000 INR = 5,000,000 paise > 4,000,000 paise)
    over_pay = client.post(f'/api/fund-requests/{fr_id}/pay', json={
        'amount_paise': 5000000,
        'reference_code': 'UTR-BANK-OVER',
        'receipt_reference': 'INV-OVER-01'
    })
    assert over_pay.status_code == 400
    assert 'exceed' in over_pay.get_json()['error'].lower()

    # 7. Valid Payment (40,000 INR = 4,000,000 paise)
    pay_res = client.post(f'/api/fund-requests/{fr_id}/pay', json={
        'amount_paise': 4000000,
        'reference_code': 'UTR-BANK-99812',
        'receipt_reference': 'INV-GRAIN-FINAL'
    })
    assert pay_res.status_code == 200
    assert pay_res.get_json()['status'] == 'Paid'

    # Verify payment transaction recorded
    txs_after = client.get(f'/api/fund-transactions?incident_id={inc_id}').get_json()
    pay_tx = next(t for t in txs_after if t['transaction_type'] == 'Payment' and t['fund_request_id'] == fr_id)
    assert pay_tx['amount_paise'] == 4000000

    # 8. Reconcile
    rec_res = client.post(f'/api/fund-requests/{fr_id}/reconcile', json={
        'reason': 'Invoice, bank UTR, and warehouse goods receipt verified'
    })
    assert rec_res.status_code == 200
    assert rec_res.get_json()['status'] == 'Reconciled'
