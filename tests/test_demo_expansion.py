from werkzeug.security import check_password_hash
from database import get_db
from seed_demo import seed_demo_data


def test_expanded_demo_rosters_are_approved_owned_and_available():
    conn=get_db()
    assert conn.execute("SELECT COUNT(*) FROM users WHERE status='ACTIVE'").fetchone()[0] >= 120
    expected={'Administrator':2,'Government Official':5,'NGO Coordinator':3,'Citizen':32}
    for role,count in expected.items():
        assert conn.execute("SELECT COUNT(*) FROM users WHERE role=? AND status='ACTIVE'",(role,)).fetchone()[0] >= count
    for oid in (1,2,3):
        assert conn.execute("SELECT status FROM organizations WHERE id=?",(oid,)).fetchone()[0]=='Approved'
        assert conn.execute("SELECT COUNT(*) FROM users u JOIN organization_memberships m ON m.user_id=u.id WHERE u.role='NGO Coordinator' AND m.organization_id=? AND m.membership_role='Coordinator' AND m.status='Active'",(oid,)).fetchone()[0] >= 1
        for role in ('Driver','Volunteer'):
            assert conn.execute("SELECT COUNT(*) FROM users u JOIN ngo_personnel_approvals a ON a.user_id=u.id WHERE u.role=? AND u.status='ACTIVE' AND a.organization_id=? AND a.personnel_type=? AND a.decision='Approved'",(role,oid,role)).fetchone()[0] >= 8
    assert conn.execute("SELECT COUNT(*) FROM users u JOIN government_driver_approvals a ON a.user_id=u.id WHERE u.role='Driver' AND u.status='ACTIVE' AND u.organization_id IS NULL").fetchone()[0] in range(20,31)
    assert conn.execute("SELECT COUNT(DISTINCT u.id) FROM users u JOIN government_personnel p ON p.user_id=u.id AND p.status='Active' WHERE u.role='Volunteer' AND u.status='ACTIVE' AND u.organization_id IS NULL").fetchone()[0] in range(20,31)
    for oid in (None,'ngo'):
        if oid is None:
            scope='u.organization_id IS NULL AND EXISTS(SELECT 1 FROM government_driver_approvals g WHERE g.user_id=u.id)'
            volunteer_scope="JOIN government_personnel p ON p.user_id=u.id AND p.status='Active'"
        else:
            scope="EXISTS(SELECT 1 FROM ngo_personnel_approvals g WHERE g.user_id=u.id AND g.personnel_type='Driver' AND g.decision='Approved')"
            volunteer_scope="JOIN ngo_personnel_approvals p ON p.user_id=u.id AND p.personnel_type='Volunteer' AND p.decision='Approved' JOIN volunteers v ON v.user_id=u.id AND v.organization_id=p.organization_id AND v.owner_type='ngo'"
        driver_sql=f"SELECT COUNT(*) FROM users u WHERE u.role='Driver' AND u.status='ACTIVE' AND {scope} AND NOT EXISTS(SELECT 1 FROM dispatches d WHERE d.driver_user_id=u.id AND d.status IN ('Loading','Ready','En route','Arrived','Delivered Pending Proof','Delivered Pending Confirmation','Needs Review','Proof Rejected')) AND NOT EXISTS(SELECT 1 FROM response_assignments ra WHERE ra.driver_user_id=u.id AND ra.status IN ('Assigned','Active'))"
        volunteer_id="v.id" if oid else "(SELECT id FROM volunteers WHERE user_id=u.id AND owner_type='government' ORDER BY id LIMIT 1)"
        people_sql=f"SELECT COUNT(DISTINCT u.id) FROM users u {volunteer_scope} WHERE u.role='Volunteer' AND u.status='ACTIVE' AND {('u.organization_id IS NULL' if oid is None else '1=1')} AND NOT EXISTS(SELECT 1 FROM volunteer_tasks t WHERE t.volunteer_id={volunteer_id} AND t.status IN ('Assigned','Accepted','In Progress','Submitted for Review','Needs Correction')) AND NOT EXISTS(SELECT 1 FROM response_assignments ra WHERE ra.volunteer_id={volunteer_id} AND ra.status IN ('Assigned','Active'))"
        assert conn.execute(driver_sql).fetchone()[0] >= 15
        assert conn.execute(people_sql).fetchone()[0] >= 15
    for owner,oid,minimum in [('government',None,25),('ngo',1,15),('ngo',2,15),('ngo',3,15)]:
        total=conn.execute("SELECT COUNT(*) FROM vehicles WHERE owner_type=? AND owner_organization_id IS ?",(owner,oid)).fetchone()[0]
        genuinely_available=conn.execute("""SELECT COUNT(*) FROM vehicles v WHERE v.owner_type=? AND v.owner_organization_id IS ?
            AND v.status='Available' AND v.current_driver_user_id IS NULL
            AND NOT EXISTS(SELECT 1 FROM dispatches d WHERE d.vehicle_id=v.id AND d.status IN ('Loading','Ready','En route','Arrived','Delivered Pending Proof','Delivered Pending Confirmation','Needs Review','Proof Rejected'))
            AND NOT EXISTS(SELECT 1 FROM response_assignments a WHERE a.vehicle_id=v.id AND a.status IN ('Assigned','Active'))""",(owner,oid)).fetchone()[0]
        assert total >= minimum
        assert genuinely_available / total >= 0.8
    assert conn.execute("SELECT COUNT(*) FROM vehicles WHERE registration_number IS NULL OR trim(registration_number)=''").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM (SELECT registration_number FROM vehicles GROUP BY registration_number HAVING COUNT(*)>1)").fetchone()[0] == 0
    demo=conn.execute("SELECT password FROM users WHERE role='Driver' AND organization_id IS NULL AND email LIKE '%_govt_driver@drras-demo.local'").fetchall()
    assert any(check_password_hash(row['password'],'driveDemo26!') for row in demo)


def test_demo_human_identities_match_roles_organizations_and_profiles():
    conn=get_db()
    users=conn.execute("SELECT id,name,email,role,organization_id FROM users ORDER BY id").fetchall()
    assert len(users) >= 120
    assert len({row['name'] for row in users}) == len(users)
    for user in users:
        first,last=user['name'].lower().split(' ',1)
        base=f"{first}.{last}_"
        if user['role']=='Driver' and user['organization_id'] is None:
            assert user['email'].startswith(base) and user['email'].endswith('_govt_driver@drras-demo.local')
        elif user['role']=='Volunteer' and user['organization_id'] is None:
            assert user['email'].startswith(base) and user['email'].endswith('_govt_responder@drras-demo.local')
        elif user['role']=='Driver' and user['organization_id']:
            org={1:'punjabrelief',2:'khalsaaid',3:'redcross'}[user['organization_id']]
            assert user['email']==f"{base}ngo_{org}_driver@drras-demo.local"
        elif user['role']=='Volunteer' and user['organization_id']:
            org={1:'punjabrelief',2:'khalsaaid',3:'redcross'}[user['organization_id']]
            assert user['email']==f"{base}ngo_{org}_volunteer@drras-demo.local"
    assert conn.execute("SELECT COUNT(*) FROM volunteers v JOIN users u ON u.id=v.user_id WHERE v.name<>u.name").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM government_personnel p JOIN users u ON u.id=p.user_id WHERE p.name<>u.name").fetchone()[0] == 0


def test_assignment_dropdown_options_return_persisted_human_names(client):
    conn=get_db()
    request_id=conn.execute("SELECT id FROM emergency_requests WHERE response_owner_type IS NULL AND status='Awaiting allocation' ORDER BY id LIMIT 1").fetchone()['id']
    ngo_name=conn.execute("SELECT name FROM organizations WHERE id=1").fetchone()['name']
    conn.close()
    assert client.post('/api/auth/login',json={'email':'official@drras.in','password':'official123'}).status_code == 200
    government=client.get(f'/api/government/response-options/{request_id}').get_json()
    assert government['drivers'] and government['personnel']
    assert all(p['organization_name']=='Government' and isinstance(p['name'],str) for p in government['personnel'])
    assert government['vehicles'] and all(v['owner_type']=='government' if 'owner_type' in v else v['registration_number'].startswith('PB10GV') for v in government['vehicles'])
    assert all(v['registration_number'] and v['capacity_units'] > 0 and v['available'] for v in government['vehicles'])
    assert client.post('/api/auth/logout').status_code == 200
    assert client.post('/api/auth/login',json={'email':'ngo@drras.in','password':'ngo123'}).status_code == 200
    ngo=client.get(f'/api/ngo/response-options/{request_id}').get_json()
    assert ngo['drivers'] and ngo['volunteers']
    assert all(d['organization_name']==ngo_name for d in ngo['drivers'])
    assert all(v['organization_name']==ngo_name for v in ngo['volunteers'])
    assert ngo['vehicles'] and all(v['registration_number'].startswith('PB11PR') and v['capacity_units'] > 0 and v['available'] for v in ngo['vehicles'])
    conn.close()


def test_expansion_seed_is_idempotent():
    conn=get_db()
    before={t:conn.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('users','volunteers','government_personnel','vehicles','warehouses','warehouse_stock','dispatches','volunteer_tasks','request_events')}
    conn.close()
    seed_demo_data()
    conn=get_db()
    after={t:conn.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in before}
    conn.close()
    assert after==before
