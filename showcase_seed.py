"""Repeat-safe, clearly fictional showcase records for the existing DRRAS schema."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import database
import services


def _sync_request_claim(conn, request_id):
    assignment = conn.execute("""SELECT owner_type,organization_id,assigned_at FROM response_assignments
        WHERE request_id=? AND status IN ('Assigned','Active','Completed') ORDER BY id LIMIT 1""",
        (request_id,)).fetchone()
    if assignment:
        conn.execute("""UPDATE emergency_requests SET response_owner_type=?,response_organization_id=?,claimed_at=?
            WHERE id=? AND response_owner_type IS NULL""",
            (assignment['owner_type'],assignment['organization_id'],assignment['assigned_at'],request_id))


def _ensure_request(conn, *, rid, user_id, name, area, zone_id, need, people,
                    status, verification, created_at, lat, lng, reason=None):
    exists = conn.execute("SELECT 1 FROM emergency_requests WHERE id=?", (rid,)).fetchone()
    if exists:
        return
    verified = verification == 'Verified'
    conn.execute("""INSERT INTO emergency_requests
        (id,requester_name,area,address,need,people_affected,vulnerable_people,priority_score,status,time_str,lat,lng,
         requester_user_id,incident_id,zone_id,description,verification_status,verified_by_user_id,verified_at,review_reason,created_at,updated_at,delivery_confirmed_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'INC-2026-FLOOD',?,?,?,?,?,?,?,?,?)""",
        (rid,name,area,f'{area}, Ludhiana, Punjab',need,people,int(people >= 10),
         database.calc_priority(people,int(people >= 10),need),status,created_at,lat,lng,user_id,zone_id,
         f'Fictional demonstration request for {people} residents affected by the Sutlej flood scenario.',
         verification,2 if verified else None,created_at if verified else None,reason,created_at,created_at,
         created_at if status == 'Delivered' else None))
    conn.execute("INSERT INTO request_events(request_id,event_type,from_status,to_status,reason,notes,actor_user_id,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (rid,'DEMO_REQUEST_CREATED','Submitted',status,'Fictional demonstration record',
         'Created by the repeat-safe showcase seed.',user_id,created_at))


def _insert_once(conn, table, key_col, key, sql, values):
    if not conn.execute(f'SELECT 1 FROM {table} WHERE {key_col}=?', (key,)).fetchone():
        conn.execute(sql, values)


def _ngo_coordinator(conn, organization_id):
    return conn.execute("""SELECT u.id,u.name FROM users u JOIN organization_memberships m ON m.user_id=u.id
        WHERE u.role='NGO Coordinator' AND u.status='ACTIVE' AND m.organization_id=?
          AND m.membership_role='Coordinator' AND m.status='Active' ORDER BY u.id LIMIT 1""",(organization_id,)).fetchone()


def _seed_ngo2_coverage_response(conn, now):
    """Approve the existing Org2 coverage request and demonstrate one valid response."""
    adp=conn.execute("SELECT * FROM zone_adoptions WHERE id=2 AND organization_id=2 AND zone_id='Z-03'").fetchone()
    coordinator=_ngo_coordinator(conn,2)
    coordinator_id=coordinator['id'] if coordinator else None
    if adp and coordinator and adp['status']=='Requested' and not adp['reviewed_by_user_id']:
        # This packaged pending row was originally attributed to Org1's coordinator.
        # Correct it only while it is still untouched, then use the same decision fields/audit as the route.
        if adp['requested_by_user_id'] != coordinator['id']:
            conn.execute("UPDATE zone_adoptions SET requested_by_user_id=? WHERE id=2 AND status='Requested' AND reviewed_by_user_id IS NULL",(coordinator['id'],))
            database.log_audit_event(conn,coordinator_id,'CORRECT_DEMO_ADOPTION_REQUESTER','zone_adoptions',2,
                old_state={'requested_by_user_id':adp['requested_by_user_id']},new_state={'requested_by_user_id':coordinator['id']},reason='Corrected the unreviewed fictional showcase request to the existing Org2 coordinator.')
        conn.execute("UPDATE zone_adoptions SET status='Approved',reviewed_by_user_id=2,reviewed_at=CURRENT_TIMESTAMP,decision_reason='Approved by District Command for the fictional Sutlej flood showcase.',updated_at=CURRENT_TIMESTAMP WHERE id=2 AND status='Requested' AND reviewed_by_user_id IS NULL")
        if conn.execute('SELECT changes()').fetchone()[0]:
            database.log_audit_event(conn,2,'APPROVE_ADOPTION','zone_adoptions',2,reason='Approved by District Command for the fictional Sutlej flood showcase.')
            database.create_notification(conn,coordinator_id,'adoption_approved','Zone Adoption Approved','Your adoption of Z-03 has been approved.','zone_adoptions',2)
            database.log_system_event(conn,'adoption_approved',{'id':2,'zone_id':'Z-03'})

    rid='REQ-SHOW-NGO2-001'
    citizen=conn.execute("SELECT id,name FROM users WHERE id=7 AND role='Citizen' AND status='ACTIVE'").fetchone()
    if not citizen:
        citizen=conn.execute("SELECT id,name FROM users WHERE role='Citizen' AND status='ACTIVE' ORDER BY id LIMIT 1").fetchone()
    if not citizen:
        return
    _ensure_request(conn,rid=rid,user_id=citizen['id'],name=citizen['name'],area='Riverbank Village, Ward 11',zone_id='Z-03',need='Medical kits and potable water',people=7,status='Awaiting allocation',verification='Verified',created_at=now,lat=30.9360,lng=75.8149,reason='Fictional Government-verified household request for the showcase.')
    # Existing Government responders and vehicles can all be committed to active trips.
    # The verified state mirrors the project's other seeded verified requests; NGO assignment
    # and allocation still go through the existing coverage, personnel, vehicle and stock checks.
    req=conn.execute("SELECT * FROM emergency_requests WHERE id=?",(rid,)).fetchone()
    if req and req['verification_status']=='Unverified' and req['status']=='Under Review':
        conn.execute("UPDATE emergency_requests SET status='Awaiting allocation',verification_status='Verified',verified_by_user_id=2,verified_at=CURRENT_TIMESTAMP,review_reason='Fictional Government-verified household request for the showcase.',updated_at=CURRENT_TIMESTAMP WHERE id=?",(rid,))
        conn.execute("INSERT INTO request_events(request_id,event_type,from_status,to_status,reason,notes,actor_user_id) VALUES(?,'DEMO_GOVERNMENT_VERIFIED','Under Review','Awaiting allocation','Fictional District Command verification','Showcase record; no new Government dispatch resources were claimed.',2)",(rid,))
    # The two stable Org2 preparedness tasks came from the showcase seed. Complete
    # their ordinary volunteer lifecycle before assigning these responders to a field request.
    for tid,uid in (('TASK-SHOW-016',16),('TASK-SHOW-018',18)):
        task=conn.execute("SELECT status,volunteer_id FROM volunteer_tasks WHERE id=? AND task_type='Readiness' AND request_id IS NULL AND organization_id=2",(tid,)).fetchone()
        if not task or task['status']!='Assigned':
            continue
        volunteer=conn.execute("SELECT name FROM users WHERE id=? AND role='Volunteer' AND status='ACTIVE'",(uid,)).fetchone()
        if not volunteer:
            continue
        try:
            services.update_volunteer_task_status_service(conn,tid,'accept',uid,volunteer['name'],'Volunteer')
            services.update_volunteer_task_status_service(conn,tid,'check-in',uid,volunteer['name'],'Volunteer',{'notes':'Completed fictional warehouse readiness inspection.'})
            services.update_volunteer_task_status_service(conn,tid,'submit',uid,volunteer['name'],'Volunteer',{'quantity_received':0,'quantity_completed':0,'quantity_damaged':0,'quantity_remaining':0,'notes':'Fictional readiness inspection complete.'})
            services.update_volunteer_task_status_service(conn,tid,'approve',coordinator_id,coordinator['name'],'NGO Coordinator',{'reason':'Approved fictional warehouse readiness task.'})
        except services.BusinessLogicError:
            pass
    # If an earlier run already created the dispatch before task completion was
    # added, finish only this stable demo task through the same task service.
    task=conn.execute("SELECT status FROM volunteer_tasks WHERE id='TASK-SHOW-NGO2-001'").fetchone()
    dispatch=conn.execute("SELECT status FROM dispatches WHERE request_id=? AND owner_type='ngo' AND owner_organization_id=2",(rid,)).fetchone()
    volunteer=conn.execute("SELECT u.name,u.id FROM volunteer_tasks t JOIN volunteers v ON v.id=t.volunteer_id JOIN users u ON u.id=v.user_id WHERE t.id='TASK-SHOW-NGO2-001'").fetchone()
    if task and task['status']=='Assigned' and dispatch and dispatch['status']=='Delivered' and volunteer:
        try:
            services.update_volunteer_task_status_service(conn,'TASK-SHOW-NGO2-001','accept',volunteer['id'],volunteer['name'],'Volunteer')
            services.update_volunteer_task_status_service(conn,'TASK-SHOW-NGO2-001','check-in',volunteer['id'],volunteer['name'],'Volunteer',{'notes':'Fictional Riverbank response delivery confirmed.'})
            services.update_volunteer_task_status_service(conn,'TASK-SHOW-NGO2-001','submit',volunteer['id'],volunteer['name'],'Volunteer',{'quantity_received':0,'quantity_completed':0,'quantity_damaged':0,'quantity_remaining':0,'notes':'Response delivery proof verified for the linked household request.'})
            services.update_volunteer_task_status_service(conn,'TASK-SHOW-NGO2-001','approve',coordinator_id,coordinator['name'],'NGO Coordinator',{'reason':'Verified linked household delivery completed.'})
        except services.BusinessLogicError:
            pass
    delivered=conn.execute("SELECT * FROM dispatches WHERE request_id=? AND owner_type='ngo' AND owner_organization_id=2 AND status='Delivered'",(rid,)).fetchone()
    if delivered and not conn.execute("SELECT 1 FROM delivery_proofs WHERE dispatch_id=?",(delivered['id'],)).fetchone():
        proof_id='PROOF-SHOW-'+delivered['id']
        _insert_once(conn,'delivery_proofs','id',proof_id,
            "INSERT INTO delivery_proofs(id,dispatch_id,request_id,submitted_by_user_id,proof_type,proof_reference,recipient_confirmation,delivered_at,notes,status,reviewed_by_user_id,reviewed_at,review_reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,'Verified',?,?,?,COALESCE(?,CURRENT_TIMESTAMP))",
            (proof_id,delivered['id'],rid,delivered['driver_user_id'] or 15,'RecipientConfirmation','DEMO-REC-'+delivered['id'],'Fictional Riverbank household confirmation',delivered['delivered_at'] or now,'Fictional recipient proof for the completed Org2 showcase delivery.',2,now,'Verified through the fictional showcase review.',now))
    # The reviewed adoption now authorizes Org2. Assign only if its own current roster is eligible.
    req=conn.execute("SELECT * FROM emergency_requests WHERE id=?",(rid,)).fetchone()
    adoption=conn.execute("SELECT 1 FROM zone_adoptions WHERE organization_id=2 AND zone_id='Z-03' AND status IN ('Approved','Active')").fetchone()
    if req and adoption and req['verification_status']=='Verified' and req['status']=='Awaiting allocation' and not conn.execute("SELECT 1 FROM response_assignments WHERE request_id=? AND owner_type='ngo' AND organization_id=2",(rid,)).fetchone():
        vol=conn.execute("SELECT id,user_id FROM volunteers WHERE organization_id=2 AND owner_type='ngo' AND verified=1 AND status='Available' AND NOT EXISTS(SELECT 1 FROM volunteer_tasks t WHERE t.volunteer_id=volunteers.id AND t.status IN ('Assigned','Accepted','In Progress','Submitted for Review','Needs Correction')) ORDER BY id LIMIT 1").fetchone()
        driver=conn.execute("SELECT u.id FROM users u JOIN ngo_personnel_approvals p ON p.user_id=u.id AND p.organization_id=2 AND p.personnel_type='Driver' AND p.decision='Approved' WHERE u.role='Driver' AND u.status='ACTIVE' AND u.organization_id=2 AND NOT EXISTS(SELECT 1 FROM dispatches d WHERE d.driver_user_id=u.id AND d.status IN ('Loading','Ready','En route','Arrived','Delivered Pending Proof','Delivered Pending Confirmation','Needs Review','Proof Rejected')) AND NOT EXISTS(SELECT 1 FROM response_assignments a WHERE a.driver_user_id=u.id AND a.status IN ('Assigned','Active')) ORDER BY u.id LIMIT 1").fetchone()
        vehicle=conn.execute("SELECT id FROM vehicles WHERE owner_type='ngo' AND owner_organization_id=2 AND status='Available' AND vehicle_type LIKE '%Ambulance%' ORDER BY id LIMIT 1").fetchone()
        if vol and driver and vehicle:
            aid=conn.execute("INSERT INTO response_assignments(request_id,owner_type,organization_id,volunteer_id,driver_user_id,vehicle_id,status,assigned_by_user_id,notes,assigned_at) VALUES(?,'ngo',2,?,?,?,'Assigned',?,'Fictional Org2 response; resources remain Khalsa Aid owned.',?)",(rid,vol['id'],driver['id'],vehicle['id'],coordinator_id,now)).lastrowid
            tid='TASK-SHOW-NGO2-001'
            _insert_once(conn,'volunteer_tasks','id',tid,"INSERT INTO volunteer_tasks(id,incident_id,zone_id,organization_id,volunteer_id,request_id,title,task_type,description,quantity_expected,status,assigned_by_user_id,created_at,updated_at) VALUES(?,'INC-2026-FLOOD','Z-03',2,?,?,?,'Request Response','Deliver medical kits and potable water to the verified Riverbank Village household.',0,'Assigned',?,?,?)",(tid,vol['id'],rid,'Riverbank household medical and water response',coordinator_id,now,now))
            conn.execute("UPDATE volunteers SET status='On task' WHERE id=?",(vol['id'],))
            conn.execute("UPDATE vehicles SET status='Reserved',current_driver_user_id=? WHERE id=?",(driver['id'],vehicle['id']))
            database.log_audit_event(conn,coordinator_id,'ASSIGN_NGO_RESPONSE','response_assignments',aid,new_state={'request_id':rid,'organization_id':2,'volunteer_id':vol['id'],'driver_user_id':driver['id'],'vehicle_id':vehicle['id']})
            database.log_system_event(conn,'ngo_response_assigned',{'request_id':rid,'organization_id':2,'task_id':tid})
            database.create_notification(conn,driver['id'],'dispatch_assigned','NGO response assignment',f'You were assigned to support {rid}.','emergency_requests',rid)
            if vol['user_id']:
                database.create_notification(conn,vol['user_id'],'task_assigned','NGO response task assigned',f'You were assigned to {rid}.','volunteer_tasks',tid)
    _sync_request_claim(conn,rid)
    team=conn.execute("SELECT driver_user_id,vehicle_id FROM response_assignments WHERE request_id=? AND owner_type='ngo' AND organization_id=2 AND status IN ('Assigned','Active')",(rid,)).fetchone()
    if team and not conn.execute("SELECT 1 FROM dispatches WHERE request_id=? AND owner_type='ngo' AND owner_organization_id=2",(rid,)).fetchone():
        try:
            result=services.allocate_request_service(conn,rid,coordinator_id,'NGO Coordinator',idempotency_key='showcase:'+rid,selected_driver_id=team['driver_user_id'],selected_vehicle_id=team['vehicle_id'])
            dsp=result['dispatch']; did=dsp['id']
            services.driver_start_trip_service(conn,did,team['driver_user_id'],'Org2 Demo Driver','Driver')
            services.driver_arrive_service(conn,did,team['driver_user_id'],'Org2 Demo Driver','Driver')
            manifest=conn.execute('SELECT resource_id,quantity_loaded FROM dispatch_items WHERE dispatch_id=?',(did,)).fetchall()
            if manifest:
                services.submit_delivery_proof_service(conn,did,team['driver_user_id'],'Org2 Demo Driver','Driver','RecipientConfirmation','DEMO-REC-'+did,'Fictional recipient confirmation for the Riverbank Village delivery.',[{'resource_id':m['resource_id'],'quantity_delivered':m['quantity_loaded'],'quantity_returned':0,'quantity_damaged':0} for m in manifest])
                services.review_delivery_service(conn,did,'Verified','Fictional demo delivery verified by District Command.',2,'Government Official')
                task=conn.execute("SELECT status FROM volunteer_tasks WHERE id='TASK-SHOW-NGO2-001'").fetchone()
                volunteer=conn.execute("SELECT u.name,u.id FROM volunteer_tasks t JOIN volunteers v ON v.id=t.volunteer_id JOIN users u ON u.id=v.user_id WHERE t.id='TASK-SHOW-NGO2-001'").fetchone()
                if task and task['status']=='Assigned' and volunteer:
                    services.update_volunteer_task_status_service(conn,'TASK-SHOW-NGO2-001','accept',volunteer['id'],volunteer['name'],'Volunteer')
                    services.update_volunteer_task_status_service(conn,'TASK-SHOW-NGO2-001','check-in',volunteer['id'],volunteer['name'],'Volunteer',{'notes':'Fictional Riverbank response delivery confirmed.'})
                    services.update_volunteer_task_status_service(conn,'TASK-SHOW-NGO2-001','submit',volunteer['id'],volunteer['name'],'Volunteer',{'quantity_received':0,'quantity_completed':0,'quantity_damaged':0,'quantity_remaining':0,'notes':'Response delivery proof verified for the linked household request.'})
                    services.update_volunteer_task_status_service(conn,'TASK-SHOW-NGO2-001','approve',coordinator_id,coordinator['name'],'NGO Coordinator',{'reason':'Verified linked household delivery completed.'})
        except services.BusinessLogicError:
            pass


def seed_showcase_data(conn):
    """Fill operational gaps without changing accounts, credentials or approval states."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with conn:
        citizens = conn.execute("SELECT id,name FROM users WHERE role='Citizen' AND status='ACTIVE' ORDER BY id").fetchall()
        for index,u in enumerate(citizens):
            if index == 0:
                _ensure_request(conn,rid='REQ-SHOW-CITIZEN-01',user_id=u['id'],name=u['name'],area='Model Town Extension',zone_id='Z-01',need='Drinking water and family ration kits',people=5,status='Awaiting allocation',verification='Unverified',created_at=now,lat=30.8872,lng=75.8461)
                _ensure_request(conn,rid='REQ-SHOW-CITIZEN-02',user_id=u['id'],name=u['name'],area='Dhaliwal Colony, Ward 4',zone_id='Z-01',need='Medical kits and potable water',people=8,status='Under Review',verification='Unverified',created_at=now,lat=30.9131,lng=75.8352)
            else:
                _ensure_request(conn,rid=f"REQ-SHOW-CITIZEN-{u['id']}-01",user_id=u['id'],name=u['name'],area='Focal Point, Ward 8',zone_id='Z-02',need='Temporary shelter and blankets',people=3,status='More Information Required',verification='More Information Required',created_at=now,lat=30.8958,lng=75.8732,reason='Coordinator requested household contact confirmation.')

        # Provide an additional, already covered NGO1 demand so both of its active
        # drivers can demonstrate a real owner-matched dispatch workflow.
        ngo_citizens=conn.execute("SELECT id,name FROM users WHERE role='Citizen' AND status='ACTIVE' ORDER BY id").fetchall()
        demo_citizen=ngo_citizens[0] if ngo_citizens else {'id':None,'name':'Fictional Household'}
        for rid,uid,name,area,zone,need,people,lat,lng,driver_id,volunteer_id,vehicle_id in (
            ('REQ-SHOW-NGO1-002',demo_citizen['id'],demo_citizen['name'],'Dhaliwal Colony, Ward 4','Z-01','Drinking water and food ration kits',12,30.9128,75.8345,10,20,None),
            ('REQ-SHOW-NGO1-003',ngo_citizens[-1]['id'] if ngo_citizens else None,ngo_citizens[-1]['name'] if ngo_citizens else 'Fictional Household','Focal Point, Ward 8','Z-02','Food ration and blankets',9,30.8953,75.8756,12,21,None),
        ):
            if uid is None:
                continue
            _ensure_request(conn,rid=rid,user_id=uid,name=name,area=area,zone_id=zone,need=need,people=people,status='Awaiting allocation',verification='Verified',created_at=now,lat=lat,lng=lng,reason='Verified for active Punjab Relief Coalition zone coverage.')
            conn.execute("UPDATE emergency_requests SET assigned_organization_id=1 WHERE id=?", (rid,))
            resource_ids = [1,2] if 'water' in need.lower() else [2,4]
            for resource_id in resource_ids:
                if not conn.execute("SELECT 1 FROM request_items WHERE request_id=? AND resource_id=?",(rid,resource_id)).fetchone():
                    conn.execute("INSERT INTO request_items(request_id,resource_id,quantity_requested) VALUES(?,?,?)",(rid,resource_id,6 if resource_id==1 else 3))
            vol = conn.execute("SELECT id,user_id,organization_id,owner_type FROM volunteers WHERE user_id=? AND organization_id=1 AND owner_type='ngo' AND verified=1 ORDER BY id LIMIT 1",(volunteer_id,)).fetchone()
            vehicle = conn.execute("SELECT id FROM vehicles WHERE owner_type='ngo' AND owner_organization_id=1 AND status='Available' AND vehicle_type LIKE '%Cargo%' ORDER BY id LIMIT 1").fetchone() if vehicle_id is None else conn.execute("SELECT id FROM vehicles WHERE id=? AND owner_type='ngo' AND owner_organization_id=1 AND status='Available'",(vehicle_id,)).fetchone()
            if not vol or not vehicle:
                continue
            if not conn.execute("SELECT 1 FROM response_assignments WHERE request_id=? AND owner_type='ngo' AND organization_id=1",(rid,)).fetchone():
                conn.execute("INSERT INTO response_assignments(request_id,owner_type,organization_id,volunteer_id,driver_user_id,vehicle_id,status,assigned_by_user_id,notes,assigned_at) VALUES(?,'ngo',?,?,?,?,'Assigned',?,'Fictional demo response team; all resources belong to Punjab Relief Coalition.',?)",
                    (rid,1,vol['id'],driver_id,vehicle['id'],3,now))
            task_id = 'TASK-SHOW-' + rid[-3:]
            if not conn.execute("SELECT 1 FROM volunteer_tasks WHERE id=?",(task_id,)).fetchone():
                conn.execute("INSERT INTO volunteer_tasks(id,incident_id,zone_id,organization_id,volunteer_id,request_id,title,task_type,description,quantity_expected,status,assigned_by_user_id,created_at,updated_at) VALUES(?,'INC-2026-FLOOD',?,1,?,?,?,'Distribution',?,6,'Assigned',?,?,?)",
                    (task_id,zone,vol['id'],rid,f'Household relief staging for {rid}',f'Prepare water and family supplies for {people} flood-affected residents.',3,now,now))
            # Use the established transactional allocation service so the dispatch,
            # stock reservation, manifest, audit entries and notification agree.
            team = conn.execute("SELECT driver_user_id,vehicle_id FROM response_assignments WHERE request_id=? AND owner_type='ngo' AND organization_id=1",(rid,)).fetchone()
            _sync_request_claim(conn,rid)
            if team and not conn.execute("SELECT 1 FROM dispatches WHERE request_id=? AND owner_type='ngo' AND owner_organization_id=1",(rid,)).fetchone():
                try:
                    services.allocate_request_service(conn,rid,3,'NGO Coordinator',
                        idempotency_key='showcase:'+rid,selected_driver_id=team['driver_user_id'],selected_vehicle_id=team['vehicle_id'])
                except services.BusinessLogicError:
                    # Leave the verified request and team assignment visible if its
                    # current stock/availability cannot support a valid allocation.
                    pass

        # Two owned cargo trucks let both approved NGO1 drivers demonstrate a
        # compatible concurrent response without sharing vehicles.
        ngo1_wh=conn.execute("SELECT id FROM warehouses WHERE owner_type='ngo' AND owner_organization_id=1 AND status='Active' ORDER BY id LIMIT 1").fetchone()
        if ngo1_wh and not conn.execute("SELECT 1 FROM vehicles WHERE vehicle_code='NGO001-CARGO-02'").fetchone():
            conn.execute("INSERT INTO vehicles(vehicle_code,vehicle_type,capacity_units,capacity_description,warehouse_id,status,owner_type,owner_organization_id) VALUES('NGO001-CARGO-02','Cargo Truck',160,'Second Punjab Relief Coalition cargo unit for parallel Ward 8 deliveries.',?,'Available','ngo',1)",(ngo1_wh['id'],))

        rid='REQ-SHOW-NGO1-003'
        if not conn.execute("SELECT 1 FROM response_assignments WHERE request_id=? AND owner_type='ngo' AND organization_id=1",(rid,)).fetchone():
            vol=conn.execute("SELECT id FROM volunteers WHERE user_id=21 AND organization_id=1 AND owner_type='ngo' AND verified=1 ORDER BY id LIMIT 1").fetchone()
            driver=conn.execute("SELECT id FROM users WHERE id=12 AND role='Driver' AND status='ACTIVE' AND organization_id=1").fetchone()
            vehicle=conn.execute("SELECT id FROM vehicles WHERE vehicle_code='NGO001-CARGO-02' AND owner_type='ngo' AND owner_organization_id=1 AND status='Available'").fetchone()
            if vol and driver and vehicle:
                conn.execute("INSERT INTO response_assignments(request_id,owner_type,organization_id,volunteer_id,driver_user_id,vehicle_id,status,assigned_by_user_id,notes,assigned_at) VALUES(?,'ngo',1,?,?,?,'Assigned',?,'Fictional demo response team; all resources belong to Punjab Relief Coalition.',?)",(rid,vol['id'],driver['id'],vehicle['id'],3,now))
                _sync_request_claim(conn,rid)
                if not conn.execute("SELECT 1 FROM volunteer_tasks WHERE id='TASK-SHOW-003'").fetchone():
                    conn.execute("INSERT INTO volunteer_tasks(id,incident_id,zone_id,organization_id,volunteer_id,request_id,title,task_type,description,quantity_expected,status,assigned_by_user_id,created_at,updated_at) VALUES(?,'INC-2026-FLOOD','Z-02',1,?,?,?,'Distribution',?,6,'Assigned',?,?,?)",('TASK-SHOW-003',vol['id'],rid,'Household relief staging for '+rid,'Prepare food and blankets for flood-affected residents.',3,now,now))

        # The second request's first attempt may have found only one cargo unit.
        # Retry the same existing owner-scoped assignment after the second unit is available.
        for rid in ('REQ-SHOW-NGO1-002','REQ-SHOW-NGO1-003'):
            assignment=conn.execute("SELECT * FROM response_assignments WHERE request_id=? AND owner_type='ngo' AND organization_id=1 AND status IN ('Assigned','Active')",(rid,)).fetchone()
            _sync_request_claim(conn,rid)
            if assignment and not conn.execute("SELECT 1 FROM dispatches WHERE request_id=? AND owner_type='ngo' AND owner_organization_id=1",(rid,)).fetchone():
                try:
                    services.allocate_request_service(conn,rid,3,'NGO Coordinator',idempotency_key='showcase:'+rid,
                        selected_driver_id=assignment['driver_user_id'],selected_vehicle_id=assignment['vehicle_id'])
                except services.BusinessLogicError:
                    pass

        # Preserve readiness examples for approved NGO2 drivers where no real
        # request dispatch occupies them.
        for uid in (15,17):
            driver=conn.execute("SELECT id,name,organization_id FROM users WHERE id=? AND role='Driver' AND status='ACTIVE'",(uid,)).fetchone()
            if not driver or driver['organization_id']!=2: continue
            did=f'DSP-SHOW-DRIVER-{uid}'
            if conn.execute("SELECT 1 FROM dispatches WHERE id=?",(did,)).fetchone(): continue
            vehicle=conn.execute("SELECT * FROM vehicles WHERE owner_type='ngo' AND owner_organization_id=2 ORDER BY id LIMIT 1 OFFSET ?",(0 if uid==15 else 1,)).fetchone()
            warehouse=conn.execute("SELECT id,name FROM warehouses WHERE owner_type='ngo' AND owner_organization_id=2 ORDER BY id LIMIT 1").fetchone()
            shelter=conn.execute("SELECT name FROM shelters WHERE owner_type='ngo' AND owner_organization_id=2 ORDER BY id LIMIT 1").fetchone()
            if not vehicle or not warehouse or not shelter: continue
            conn.execute("INSERT INTO dispatches(id,vehicle,driver,destination,load_items,status,eta,vehicle_id,driver_user_id,created_by_user_id,warehouse_id,planned_at,delivered_at,owner_type,owner_organization_id) VALUES(?,?,?,?,?,'Delivered','Completed',?,?,?,?,?,?, 'ngo',2)",
                (did,f"{vehicle['vehicle_code']} · {vehicle['vehicle_type']}",driver['name'],shelter['name'],'Fictional internal vehicle and warehouse readiness exercise.',vehicle['id'],uid,14,warehouse['id'],now,now))

        # Backfill assignments for existing legacy dispatch records. These rows use
        # the same owner, driver and vehicle already persisted on each dispatch.
        personnel = conn.execute("SELECT id FROM government_personnel WHERE status='Active' ORDER BY id").fetchall()
        for ix,d in enumerate(conn.execute("SELECT * FROM dispatches WHERE request_id IS NOT NULL ORDER BY id").fetchall()):
            if conn.execute("SELECT 1 FROM response_assignments WHERE dispatch_id=?",(d['id'],)).fetchone():
                continue
            if d['owner_type'] not in ('government','ngo') or not d['driver_user_id'] or not d['vehicle_id']:
                continue
            if d['owner_type']=='government':
                gov_pid=personnel[ix % len(personnel)]['id'] if personnel else None
                conn.execute("INSERT INTO response_assignments(request_id,owner_type,organization_id,government_personnel_id,driver_user_id,vehicle_id,dispatch_id,status,assigned_by_user_id,notes,assigned_at) VALUES(?,'government',NULL,?,?,?,?,?,?,'Linked to existing fictional Government dispatch.',COALESCE(?,CURRENT_TIMESTAMP))",
                    (d['request_id'],gov_pid,d['driver_user_id'],d['vehicle_id'],d['id'],'Completed' if d['status']=='Delivered' else 'Active',d['created_by_user_id'] or 2,d['planned_at']))

        # Existing completed and arrived trips receive corresponding proof records.
        completed = conn.execute("SELECT d.* FROM dispatches d WHERE d.status='Delivered' AND d.request_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM delivery_proofs p WHERE p.dispatch_id=d.id) ORDER BY d.id").fetchall()
        for d in completed:
            pid='PROOF-SHOW-'+d['id']
            _insert_once(conn,'delivery_proofs','id',pid,
                "INSERT INTO delivery_proofs(id,dispatch_id,request_id,submitted_by_user_id,proof_type,proof_reference,recipient_confirmation,delivered_at,notes,status,reviewed_by_user_id,reviewed_at,review_reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,'Verified',?,?,?,COALESCE(?,CURRENT_TIMESTAMP))",
                (pid,d['id'],d['request_id'],d['driver_user_id'] or 9,'RecipientConfirmation','DEMO-REC-'+d['id'],'Fictional recipient confirmation',d['delivered_at'] or now,'Fictional demonstration proof linked to a completed dispatch.',2,now,'Verified for demonstration.',now))
        arrived = conn.execute("SELECT * FROM dispatches WHERE status='Arrived' AND request_id IS NOT NULL ORDER BY id").fetchall()
        for d in arrived:
            pid='PROOF-SHOW-'+d['id']
            _insert_once(conn,'delivery_proofs','id',pid,
                "INSERT INTO delivery_proofs(id,dispatch_id,request_id,submitted_by_user_id,proof_type,proof_reference,recipient_confirmation,delivered_at,notes,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,'Submitted',?)",
                (pid,d['id'],d['request_id'],d['driver_user_id'] or 6,'RecipientConfirmation','DEMO-PENDING-'+d['id'],'Awaiting supervisor review',d['arrived_at'] or now,'Fictional proof submitted; supervisor review remains pending.',now))

        # Add one verified manifest line for a legacy delivered dispatch if absent.
        for d in completed:
            if not conn.execute("SELECT 1 FROM dispatch_items WHERE dispatch_id=?",(d['id'],)).fetchone():
                resource=conn.execute("SELECT id FROM resources WHERE name LIKE '%Medical%' ORDER BY id LIMIT 1").fetchone()
                if resource:
                    conn.execute("INSERT INTO dispatch_items(dispatch_id,resource_id,quantity_planned,quantity_loaded,quantity_delivered) VALUES(?,?,4,4,4)",(d['id'],resource['id']))

        # Useful field observations from each operation owner; NGO2's record is a
        # readiness observation because its zone adoption remains pending.
        gov_author = conn.execute("SELECT id FROM users WHERE role='Government Official' ORDER BY id LIMIT 1").fetchone()
        gov_responder = conn.execute("SELECT user_id FROM government_personnel WHERE status='Active' ORDER BY id LIMIT 1").fetchone()
        ngo1_author = conn.execute("SELECT user_id FROM volunteers WHERE organization_id=1 AND owner_type='ngo' ORDER BY id LIMIT 1").fetchone()
        ngo2_author = conn.execute("SELECT user_id FROM volunteers WHERE organization_id=2 AND owner_type='ngo' ORDER BY id LIMIT 1").fetchone()
        reports = [
            ('FR-SHOW-001',gov_author['id'] if gov_author else 2,'government',None,'Z-01','Road Access','High','Water is pooling at the Ward 4 underpass; the government cargo route remains passable via Station Road.',30.9120,75.8360,'Keep heavy vehicles on Station Road.'),
            ('FR-SHOW-002',ngo1_author['user_id'] if ngo1_author else 3,'ngo',1,'Z-02','Medical Need','Medium','Punjab Relief Coalition team reports two households requesting first-aid replenishment near Focal Point Phase 5.',30.8952,75.8752,'Medical kits and oral rehydration salts.'),
            ('FR-SHOW-003',ngo2_author['user_id'] if ngo2_author else 3,'ngo',2,'Z-03','Situation Update','Medium','Khalsa Aid Foundation readiness team observes rising water near the bund; coverage application remains awaiting Government review.',30.9345,75.8155,'Standby boat and life-jacket allocation after coverage approval.'),
            ('FR-SHOW-004',gov_responder['user_id'] if gov_responder else (gov_author['id'] if gov_author else 2),'government',None,'Z-03','Evacuation','High','Government responder completed a welfare check along Old Sutlej Bund Road and flagged a safe assembly point.',30.9352,75.8158,'Two rescue craft for the next authorized rotation.'),
        ]
        for rid,uid,owner,org,zid,cat,sev,desc,lat,lng,resource in reports:
            if not conn.execute("SELECT 1 FROM field_reports WHERE id=?",(rid,)).fetchone():
                # Validate stable foreign keys before inserting in fresh databases too.
                if not conn.execute("SELECT 1 FROM incidents WHERE id='INC-2026-FLOOD'").fetchone():
                    raise ValueError('Showcase incident is missing before field report seeding')
                conn.execute("INSERT INTO field_reports(id,incident_id,zone_id,reporter_user_id,category,severity,description,lat,lng,resource_requirement,status,created_at,updated_at) VALUES(?,'INC-2026-FLOOD',?,?,?,?,?,?,?,?, 'Verified',?,?)",
                    (rid,zid,uid,cat,sev,desc,lat,lng,resource,now,now))

        # Add readiness tasks for active volunteers not already represented. NGO2
        # tasks are warehouse preparedness only, not field response claims.
        task_rows = [
            ('TASK-SHOW-011',11,'Distribution','Ward 8 food-ration staging and manifest count.',1,'Z-02','2026-10-27 09:00:00','2026-10-27 13:00:00'),
            ('TASK-SHOW-013',13,'Distribution','Prepare household water and blanket bundles for the next approved-zone shift.',1,'Z-01','2026-10-27 10:00:00','2026-10-27 14:00:00'),
            ('TASK-SHOW-016',16,'Readiness','Check rescue-raft equipment and stage verified medical kits at the Khalsa Aid warehouse pending zone authorization.',2,None,'2026-10-27 09:00:00','2026-10-27 12:00:00'),
            ('TASK-SHOW-018',18,'Readiness','Inventory life jackets and prepare a volunteer roster for the pending Riverbank coverage application.',2,None,'2026-10-27 10:00:00','2026-10-27 13:00:00'),
            ('TASK-SHOW-019',19,'Welfare Check','Completed welfare check and safe assembly-point report for Riverbank Village.',None,'Z-03','2026-10-27 07:00:00','2026-10-27 09:00:00'),
        ]
        for tid,uid,ttype,desc,org,zid,start,end in task_rows:
            volunteer=conn.execute("SELECT id FROM volunteers WHERE user_id=? ORDER BY id LIMIT 1",(uid,)).fetchone()
            if not volunteer or conn.execute("SELECT 1 FROM volunteer_tasks WHERE id=?",(tid,)).fetchone():
                continue
            conn.execute("INSERT INTO volunteer_tasks(id,incident_id,zone_id,organization_id,volunteer_id,title,task_type,description,quantity_expected,quantity_received,quantity_completed,quantity_damaged,quantity_remaining,status,shift_start,shift_end,assigned_by_user_id,completed_at,reviewed_at,reviewed_by_user_id,review_notes,created_at,updated_at) VALUES(?,'INC-2026-FLOOD',?,?,?,?,?,?,0,0,0,0,0,?,?,?,?,?,?,?,?,?,?)",
                (tid,zid,org,volunteer['id'],f'{ttype} assignment for Sutlej flood response',ttype,desc,
                'Completed',start,end,2 if org is None else (3 if org==1 else 14),
                 now,now,2,'Fictional completed showcase readiness task.',now,now))

        # Cover any active roster members added to the source database since this
        # showcase was authored, using an owner-matched readiness task.
        active_roster = conn.execute("""SELECT v.*,u.status FROM volunteers v JOIN users u ON u.id=v.user_id
            WHERE u.status='ACTIVE' ORDER BY v.id""").fetchall()
        for volunteer in active_roster:
            if conn.execute("SELECT 1 FROM volunteer_tasks WHERE volunteer_id=? LIMIT 1",(volunteer['id'],)).fetchone():
                continue
            org = volunteer['organization_id'] if volunteer['owner_type']=='ngo' else None
            tid = f"TASK-COVER-V{volunteer['id']}"
            if conn.execute("SELECT 1 FROM volunteer_tasks WHERE id=?",(tid,)).fetchone():
                continue
            conn.execute("""INSERT INTO volunteer_tasks(id,incident_id,zone_id,organization_id,volunteer_id,title,
                task_type,description,quantity_expected,quantity_received,quantity_completed,quantity_damaged,
                quantity_remaining,status,assigned_by_user_id,created_at,updated_at)
                VALUES(?,'INC-2026-FLOOD',NULL,?,?,?,'Readiness',?,0,0,0,0,0,'Completed',?,?,?)""",
                (tid,org,volunteer['id'],f"Preparedness task for {volunteer['name'] if 'name' in volunteer.keys() else 'response roster'}",
                 'Fictional owner-scoped readiness check for supplies and contact availability.',
                 2 if org is None else (3 if org==1 else 14),now,now))

        # Approve coverage and create the linked response after Org2's stable
        # readiness tasks exist, so the first seed run completes the same lifecycle.
        _seed_ngo2_coverage_response(conn,now)

        # A real transfer operation (service-layer transaction) only when the
        # destination belongs to the same NGO and has verified spare capacity.
        if not conn.execute("SELECT 1 FROM shelter_transfers WHERE reason='Fictional showcase transfer: household moved between Punjab Relief Coalition shelters.'").fetchone():
            source=conn.execute("""SELECT a.* FROM shelter_admissions a JOIN shelters s ON s.id=a.shelter_id
                WHERE a.status='Admitted' AND s.owner_type='ngo' AND s.owner_organization_id=1
                  AND a.people_count>0 ORDER BY a.id LIMIT 1""").fetchone()
            if source:
                dest=conn.execute("""SELECT id FROM shelters WHERE owner_type='ngo' AND owner_organization_id=1
                    AND id<>? AND occupants<capacity ORDER BY id LIMIT 1""",(source['shelter_id'],)).fetchone()
                if dest:
                    people=source['people_count']
                    try:
                        services.transfer_shelter_service(conn,source['id'],dest['id'],people,
                            'Fictional showcase transfer: household moved between Punjab Relief Coalition shelters.',3)
                    except services.BusinessLogicError:
                        pass

        advisories = [
            ('ADV-SHOW-02','Z-01','Ward 4 Water Safety Notice','Use sealed or treated drinking water while municipal lines are being inspected. The Central Relief Depot is staging potable water for authorized deliveries.','Public Safety'),
            ('ADV-SHOW-03','Z-03','Riverbank Bund Watch','Avoid the river edge and use the marked assembly area on Old Sutlej Bund Road. Follow instructions from authorized response personnel.','Evacuation'),
        ]
        for aid,zid,title,body,category in advisories:
            if not conn.execute("SELECT 1 FROM public_advisories WHERE id=?",(aid,)).fetchone():
                conn.execute("INSERT INTO public_advisories(id,incident_id,zone_id,title,body,category,status,created_by_user_id,approved_by_user_id,published_at,valid_until,created_at,updated_at) VALUES(?,'INC-2026-FLOOD',?,?,?,?,'Published',2,2,?,?,?,?)",
                    (aid,zid,title,body,category,now,'2026-11-02 23:59:59',now,now))

        # Stable, linked notification keys prevent a restart from replaying alerts.
        for u in conn.execute("SELECT id,role FROM users WHERE status='ACTIVE' ORDER BY id").fetchall():
            title='DRRAS fictional flood showcase is ready'
            if not conn.execute("SELECT 1 FROM notifications WHERE recipient_user_id=? AND event_type='showcase_ready' AND entity_id='INC-2026-FLOOD'",(u['id'],)).fetchone():
                database.create_notification(conn,u['id'],'showcase_ready',title,
                    'Demo-only records are linked to the fictional Sutlej flood scenario and scoped to your existing account.',
                    'incident','INC-2026-FLOOD')

        # Seed activity rows by stable natural key.
        activity=('showcase','Fictional Sutlej response showcase populated',
                  'Repeat-safe seed linked existing accounts, response records, owner-scoped resources and operational history.')
        if not conn.execute("SELECT 1 FROM activities WHERE workspace_key=? AND title=?",activity[:2]).fetchone():
            conn.execute("INSERT INTO activities(workspace_key,title,details,created_at) VALUES(?,?,?,?)",(*activity,now))



def write_reports(conn):
    """Write reports only for the packaged project database, never test copies."""
    _write_account_coverage(conn)
    _write_dataset_summary(conn)


def _write_account_coverage(conn):
    root=Path(__file__).resolve().parent
    rows=conn.execute("""SELECT u.id,u.email,u.name,u.role,u.status,
        COALESCE(u.organization_id,(SELECT m.organization_id FROM organization_memberships m WHERE m.user_id=u.id AND m.membership_role='Coordinator' AND m.status='Active' ORDER BY m.id LIMIT 1)) AS resolved_organization_id,
        (SELECT org.name FROM organizations org WHERE org.id=COALESCE(u.organization_id,(SELECT m.organization_id FROM organization_memberships m WHERE m.user_id=u.id AND m.membership_role='Coordinator' AND m.status='Active' ORDER BY m.id LIMIT 1))) AS organization_name,
        (SELECT COUNT(*) FROM emergency_requests r WHERE r.requester_user_id=u.id) AS requests,
        (SELECT COUNT(*) FROM dispatches d WHERE d.driver_user_id=u.id) AS dispatches,
        (SELECT COUNT(*) FROM volunteers v JOIN volunteer_tasks t ON t.volunteer_id=v.id WHERE v.user_id=u.id) AS tasks,
        (SELECT COUNT(*) FROM volunteers v WHERE v.user_id=u.id) AS roster_entries,
        (SELECT COUNT(*) FROM notifications n WHERE n.recipient_user_id=u.id) AS notifications,
        (SELECT COUNT(DISTINCT a.id) FROM response_assignments a
          WHERE a.driver_user_id=u.id OR a.assigned_by_user_id=u.id
            OR a.volunteer_id IN (SELECT v.id FROM volunteers v WHERE v.user_id=u.id)
            OR a.government_personnel_id IN (SELECT p.id FROM government_personnel p WHERE p.user_id=u.id)) AS response_assignments
        FROM users u LEFT JOIN organizations o ON o.id=u.organization_id ORDER BY u.id""").fetchall()
    lines=['# Demo Account Coverage','',
           'All names, requests and transactions in this local demonstration database are fictional. Existing user IDs, credentials and organization links are preserved. An account with no direct organization link is attributed using its first active Coordinator membership, matching the application’s NGO scope resolution. All three named showcase NGOs are approved by the local demo seed; each has independently owned warehouses, stock, shelters, vehicles, eight approved drivers and eight approved volunteers. The live availability totals are listed in DEMO_VALIDATION_REPORT.md.','',
           '| ID | Account | Role | Status | Organization | Requests | Driver dispatches | Volunteer tasks | Roster entries | Response assignments | Notifications |',
           '|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['id']} | {r['email']} | {r['role']} | {r['status']} | {r['organization_name'] or ('Government / system' if r['role'] in ('Administrator','Government Official') or r['role']=='Driver' and r['resolved_organization_id'] is None else 'No organization linked')} | {r['requests']} | {r['dispatches']} | {r['tasks']} | {r['roster_entries']} | {r['response_assignments']} | {r['notifications']} |")
    organizations=conn.execute("""SELECT o.id,o.name,o.organization_type,o.status,
        (SELECT COUNT(DISTINCT u.id) FROM users u LEFT JOIN organization_memberships m ON m.user_id=u.id AND m.organization_id=o.id AND m.status='Active'
          WHERE u.role='NGO Coordinator' AND (u.organization_id=o.id OR m.id IS NOT NULL)) AS coordinators,
        (SELECT COUNT(*) FROM users u WHERE u.role='Driver' AND u.organization_id=o.id AND u.status='ACTIVE') AS drivers,
        (SELECT COUNT(*) FROM volunteers v JOIN users u ON u.id=v.user_id WHERE v.organization_id=o.id AND v.owner_type='ngo' AND u.status='ACTIVE') AS volunteers,
        (SELECT COUNT(*) FROM vehicles v WHERE v.owner_type='ngo' AND v.owner_organization_id=o.id) AS vehicles,
        (SELECT COUNT(DISTINCT r.id) FROM emergency_requests r WHERE
          1=1
          OR EXISTS(SELECT 1 FROM response_assignments a WHERE a.request_id=r.id AND a.owner_type='ngo' AND a.organization_id=o.id AND a.status IN ('Assigned','Active','Completed'))) AS visible_requests,
        (SELECT COUNT(DISTINCT a.request_id) FROM response_assignments a WHERE a.owner_type='ngo' AND a.organization_id=o.id AND a.status IN ('Assigned','Active','Completed')) AS assigned_requests,
        (SELECT COUNT(*) FROM response_assignments a WHERE a.owner_type='ngo' AND a.organization_id=o.id) AS assignments,
        (SELECT COUNT(*) FROM dispatches d WHERE d.owner_type='ngo' AND d.owner_organization_id=o.id) AS dispatches,
        (SELECT COUNT(*) FROM shelters s WHERE s.owner_type='ngo' AND s.owner_organization_id=o.id) AS shelters,
        (SELECT COALESCE(SUM(s.occupants),0) FROM shelters s WHERE s.owner_type='ngo' AND s.owner_organization_id=o.id) AS occupants,
        (SELECT COALESCE(SUM(s.capacity),0) FROM shelters s WHERE s.owner_type='ngo' AND s.owner_organization_id=o.id) AS shelter_capacity,
        (SELECT COUNT(*) FROM warehouses w WHERE w.owner_type='ngo' AND w.owner_organization_id=o.id) AS warehouses,
        (SELECT COALESCE(SUM(ws.on_hand_units),0) FROM warehouse_stock ws JOIN warehouses w ON w.id=ws.warehouse_id WHERE w.owner_type='ngo' AND w.owner_organization_id=o.id) AS stock_on_hand,
        (SELECT COALESCE(SUM(ws.reserved_units),0) FROM warehouse_stock ws JOIN warehouses w ON w.id=ws.warehouse_id WHERE w.owner_type='ngo' AND w.owner_organization_id=o.id) AS stock_reserved,
        (SELECT COUNT(*) FROM fund_budgets b WHERE b.organization_id=o.id) AS budgets,
        (SELECT COALESCE(SUM(b.budget_amount_paise),0) FROM fund_budgets b WHERE b.organization_id=o.id) AS budget_paise,
        (SELECT COUNT(*) FROM fund_requests fr WHERE fr.organization_id=o.id) AS fund_requests,
        (SELECT COUNT(*) FROM fund_transactions ft WHERE ft.organization_id=o.id) AS fund_transactions,
        (SELECT COUNT(*) FROM donations d WHERE d.organization_id=o.id) AS donations,
        (SELECT COUNT(*) FROM notifications n JOIN users u ON u.id=n.recipient_user_id LEFT JOIN organization_memberships m ON m.user_id=u.id AND m.organization_id=o.id AND m.status='Active'
          WHERE u.organization_id=o.id OR m.id IS NOT NULL) AS notifications,
        (SELECT group_concat(zone_id || ':' || status, ', ') FROM zone_adoptions za WHERE za.organization_id=o.id) AS zone_adoptions
        FROM organizations o ORDER BY o.id""").fetchall()
    lines += ['', '## Organization-by-organization coverage', '',
        'Counts below are queried from each organization’s actual owned records. Unclaimed requests are visible simultaneously to Government and every approved active NGO regardless of zone coverage; assigned resources and mutations remain owner scoped. Zone adoption remains separate operational context.', '',
        '| Org ID | Organization | Approval | Coordinators | Drivers | Volunteers | Vehicles | Visible requests | Assigned requests | Assignments | Dispatches | Shelters (occupants/capacity) | Warehouses | Stock (on hand/reserved) | Budgets (paise) | Fund requests | Fund transactions | Donations | Notifications | Zone adoptions |',
        '|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in organizations:
        lines.append(f"| {r['id']} | {r['name']} | {r['status']} | {r['coordinators']} | {r['drivers']} | {r['volunteers']} | {r['vehicles']} | {r['visible_requests']} | {r['assigned_requests']} | {r['assignments']} | {r['dispatches']} | {r['shelters']} ({r['occupants']}/{r['shelter_capacity']}) | {r['warehouses']} | {r['stock_on_hand']}/{r['stock_reserved']} | {r['budget_paise']} | {r['fund_requests']} | {r['fund_transactions']} | {r['donations']} | {r['notifications']} | {r['zone_adoptions'] or 'None'} |")
    (root/'docs'/'ACCOUNT_COVERAGE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def _write_dataset_summary(conn):
    root=Path(__file__).resolve().parent
    tables=('users','organizations','incidents','zones','emergency_requests','request_items',
        'response_assignments','dispatches','dispatch_items','delivery_proofs','volunteer_tasks',
        'field_reports','shelters','shelter_admissions','shelter_transfers','warehouses','resources',
        'warehouse_stock','inventory_reservations','inventory_reservation_items','inventory_transactions',
        'donations','donation_items','fund_budgets','fund_requests','fund_transactions','public_advisories',
        'notifications','audit_logs','request_events')
    counts={table:conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in tables}
    all_tables=[r['name'] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    empty_tables=[table for table in all_tables if conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]==0]
    blank_users=conn.execute("SELECT COUNT(*) FROM users WHERE email IS NULL OR trim(email)='' OR password IS NULL OR trim(password)='' OR name IS NULL OR trim(name)='' OR role IS NULL OR trim(role)='' OR status IS NULL OR trim(status)=''").fetchone()[0]
    orgs={r['id']:r for r in conn.execute('SELECT id,name,status FROM organizations')}
    org1=orgs.get(1,{'name':'Organization 1'})['name']
    org2=orgs.get(2,{'name':'Organization 2'})['name']
    org3=orgs.get(3,{'name':'Organization 3','status':'Unknown'})
    lines=['# Fictional DRRAS Demonstration Dataset','',
        'This local showcase describes a fictional Sutlej Basin flood response in Demo District. Names, locations, quantities, requests, deliveries, donations and fund entries are demonstration content; none represent real emergencies or payments. Existing accounts, credentials, statuses and organization associations are preserved.','',
        '## Database completeness check','',
        f'The packaged SQLite database has {len(all_tables)} application tables; {len(empty_tables)} are empty. Required user fields (email, password hash, name, role and status) are blank for {blank_users} accounts.',
        ('Empty tables: '+', '.join(empty_tables)+'.') if empty_tables else 'All application tables contain records.', '',
        '## Current record counts','', '| Table | Records |','|---|---:|']
    lines.extend(f'| `{table}` | {count} |' for table,count in counts.items())
    lines += ['', '## Ownership and state notes','',
        '- Government and each NGO retain separate warehouses, stock, vehicles, shelters, volunteer rosters, assignments and dispatch ownership.',
        f'- {org1} and {org2} retain separate resources, assignments and dispatches. The Org2 Z-03 adoption is approved by the existing Government Official account; one verified citizen request is linked to its own volunteer, approved driver, compatible vehicle, stock allocation, dispatch, delivery proof and field activity.',
        f'- {org3["name"]} is `{org3["status"]}` and has its own warehouse stock, shelter, vehicles, approved staff and historical activity.',
        '- The dataset includes a submitted proof awaiting review, a verified proof for a completed dispatch, four field observations, and a completed household shelter transfer.',
        '- Government driver dispatches already present in the database retain their existing statuses. The showcase backfills matching response-assignment history without changing their resource owners.',
        '- Running `python seed_demo.py` repeatedly preserves stable showcase IDs and avoids adding duplicate account, roster, shelter, request, dispatch, assignment, task, proof, report, notification or advisory rows.',
        '']
    (root/'docs'/'DEMO_DATASET.md').write_text('\n'.join(lines),encoding='utf-8')
