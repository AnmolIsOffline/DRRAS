import os
import tempfile
import pytest
from werkzeug.security import check_password_hash

import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure isolated test database before importing app or database
test_db_fd, test_db_path = tempfile.mkstemp(suffix='.db', prefix='drras_test_')
os.close(test_db_fd)
os.environ['DRRAS_DB_PATH'] = test_db_path
os.environ['SECRET_KEY'] = 'test-secret-key-drras-secure'

from database import init_db, get_db
from seed_demo import seed_demo_data
from app import app as flask_app

@pytest.fixture(scope='session', autouse=True)
def setup_test_db():
    init_db()
    yield
    # Cleanup temporary test database file after session
    try:
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
    except Exception as e:
        print("Cleanup error:", e)

@pytest.fixture(autouse=True)
def fresh_database_per_test():
    """Keep workflow tests independent so vehicle/stock mutations cannot leak."""
    fd, path = tempfile.mkstemp(suffix='.db', prefix='drras_case_')
    os.close(fd)
    os.environ['DRRAS_DB_PATH'] = path
    seed_demo_data()
    conn = get_db()
    admin_id = conn.execute("SELECT id FROM users WHERE role='Administrator' ORDER BY id LIMIT 1").fetchone()[0]
    responders = [
        ('Dr. Test Responder', 'Doctor / Paramedic', 'District Medical Unit', 'Medical, first aid'),
        ('Test Rescue Officer', 'Search and Rescue', 'District Rescue Unit', 'Water rescue, evacuation'),
        ('Test Fire Officer', 'Firefighter', 'District Fire Service', 'Fire response, rescue')
    ]
    for name, category, unit, skills in responders:
        conn.execute("INSERT OR IGNORE INTO government_personnel (name,category,service_unit,skills,status,created_by_user_id,approved_by_user_id,approved_at) VALUES (?,?,?,?,'Active',?,?,CURRENT_TIMESTAMP)", (name,category,unit,skills,admin_id,admin_id))
    for driver in conn.execute("SELECT id FROM users WHERE role='Driver' AND organization_id IS NULL").fetchall():
        conn.execute("INSERT OR IGNORE INTO government_driver_approvals(user_id,approved_by_user_id,reason) VALUES(?,?,'Test-approved Government driver')",(driver['id'],admin_id))
    conn.execute("UPDATE warehouses SET owner_type='government',owner_organization_id=NULL WHERE code='WH-CENTRAL'")
    conn.execute("UPDATE vehicles SET owner_type='government',owner_organization_id=NULL WHERE warehouse_id IN (SELECT id FROM warehouses WHERE owner_type='government')")
    conn.commit()
    conn.close()
    yield
    for suffix in ('', '-wal', '-shm'):
        try:
            os.remove(path + suffix)
        except (FileNotFoundError, PermissionError):
            pass

@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    with flask_app.test_client() as client:
        yield client

@pytest.fixture
def auth_client(client):
    """Client with authenticated Administrator session."""
    def _login(email='admin@drras.in', password='admin123'):
        res = client.post('/api/auth/login', json={'email': email, 'password': password})
        return res
    return _login


def verify_request_with_team(client, request_id, reason='Verified by Government response team', decision='Verified'):
    options_response = client.get(f'/api/government/response-options/{request_id}')
    assert options_response.status_code == 200, options_response.get_json()
    options = options_response.get_json()
    personnel = next((p for p in options['personnel'] if p['available']), None)
    driver = next((d for d in options['drivers'] if d['available']), None)
    vehicle = next((v for v in options['vehicles'] if v['available']), None)
    assert personnel and driver and vehicle, options
    response = client.post(f'/api/requests/{request_id}/verify', json={
        'decision': decision, 'reason': reason,
        'response_personnel_id': personnel['id'],
        'driver_user_id': driver['id'], 'vehicle_id': vehicle['id']
    })
    if response.status_code == 200 and decision == 'Verified':
        conn=get_db()
        assigned=conn.execute("SELECT u.email,u.password FROM response_assignments a JOIN users u ON u.id=a.driver_user_id WHERE a.request_id=? AND a.owner_type='government' ORDER BY a.id DESC LIMIT 1",(request_id,)).fetchone()
        conn.close()
        driver_password=next((candidate for candidate in ('driver123','driveDemo26!') if check_password_hash(assigned['password'],candidate)),None)
        assert driver_password, 'The assigned demo Driver credential must match its stored hash.'
        client.post('/api/auth/login',json={'email':assigned['email'],'password':driver_password})
        decisions=client.get('/api/driver/assignments').get_json()
        pending=next(item for item in decisions if item['request_id']==request_id)
        accepted=client.post(f"/api/driver/assignments/{pending['assignment_id']}/accept",json={})
        assert accepted.status_code == 200, accepted.get_json()
        client.post('/api/auth/login',json={'email':'official@drras.in','password':'official123'})
    return response
