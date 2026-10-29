"""Idempotent expansion of the fictional local DRRAS demonstration dataset.

This module only provisions the three named showcase NGOs and stable demo
identities. It uses the application's real SQLite tables and auth hashing.
"""
from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash

import database

PASSWORDS = {
    'Administrator': 'adminDemo26!', 'Government Official': 'govDemo26!',
    'Government Driver': 'driveDemo26!', 'Government Responder': 'respondDemo26!',
    'NGO Coordinator': 'ngoDemo26!', 'NGO Driver': 'driveDemo26!',
    'NGO Volunteer': 'serveDemo26!', 'Citizen': 'citizenDemo26!',
}
PASSWORD_HASHES = {role: generate_password_hash(password) for role,password in PASSWORDS.items()}
ORG_NAMES = {1: 'Punjab Relief Coalition', 2: 'Khalsa Aid Foundation', 3: 'Red Cross District Chapter'}
ACTIVE_DISPATCH = "('Loading','Ready','En route','Arrived','Delivered Pending Proof','Delivered Pending Confirmation','Needs Review','Proof Rejected')"
ACTIVE_TASK = "('Assigned','Accepted','In Progress','Submitted for Review','Needs Correction')"


def _valid(conn, uid):
    return conn.execute('SELECT id FROM users WHERE id=? AND status=\'ACTIVE\'', (uid,)).fetchone()


def _add_user(conn, email, name, role, org_id=None):
    row = conn.execute('SELECT * FROM users WHERE email=? COLLATE NOCASE', (email,)).fetchone()
    if row:
        return row['id'], False
    password_role = ('NGO Driver' if org_id else 'Government Driver') if role == 'Driver' else (('NGO Volunteer' if org_id else 'Government Responder') if role == 'Volunteer' else role)
    pwd_hash = PASSWORD_HASHES[password_role]
    cur = conn.execute("INSERT INTO users(email,password,name,initials,role,status,organization_id,phone) VALUES(?,?,?,?,?,'ACTIVE',?,?)",
                       (email, pwd_hash, name, ''.join(p[0] for p in name.split())[:2].upper(), role, org_id, '+91-90000-'+email.split('@')[0][-4:].zfill(4)))
    return cur.lastrowid, True


def _identity(conn, category, email, name, org_id=None, creator=None, approver=None):
    uid, created = _add_user(conn, email, name, 'Driver' if 'Driver' in category else 'Volunteer', org_id)
    if category in ('Government Driver','Government Responder'):
        if category == 'Government Driver':
            conn.execute("INSERT OR IGNORE INTO government_driver_approvals(user_id,approved_by_user_id,reason) VALUES(?,?,?)", (uid, approver, 'Approved local fictional demo driver'))
    else:
        ptype = 'Driver' if category.endswith('Driver') else 'Volunteer'
        conn.execute("INSERT INTO ngo_personnel_approvals(user_id,organization_id,personnel_type,decision,decided_by_user_id,reason) VALUES(?,?,?,'Approved',?,?) ON CONFLICT(user_id,organization_id,personnel_type) DO UPDATE SET decision='Approved',decided_by_user_id=excluded.decided_by_user_id,reason=excluded.reason", (uid,org_id,ptype,approver,'Approved local fictional demo personnel'))
        conn.execute("INSERT OR IGNORE INTO organization_memberships(organization_id,user_id,membership_role,status) VALUES(?,?,?,'Active')", (org_id,uid,ptype))
    if 'Responder' in category or category.endswith('Volunteer'):
        existing = conn.execute('SELECT id FROM volunteers WHERE user_id=? AND owner_type=? AND organization_id IS ?', (uid,'government' if org_id is None else 'ngo',org_id)).fetchone()
        if not existing:
            conn.execute("INSERT INTO volunteers(initials,name,skill,zone,status,user_id,organization_id,verified,phone,owner_type) VALUES(?,?,?,?,'Available',?,?,1,?,?)",
                         (''.join(p[0] for p in name.split())[:2].upper(),name,'Medical aid, distribution and evacuation','Z-01' if uid%2 else 'Z-02',uid,org_id,'+91-90000-'+str(uid).zfill(4),'government' if org_id is None else 'ngo'))
            vid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            if org_id is None:
                conn.execute("INSERT INTO government_personnel(name,category,service_unit,skills,status,incident_id,zone_id,user_id,created_by_user_id,approved_by_user_id,approved_at) VALUES(?,'Government Responder','District Disaster Response Unit','Medical aid, distribution and evacuation','Active','INC-2026-FLOOD','Z-01',?,?,?,CURRENT_TIMESTAMP)", (name,uid,creator,approver))
    return uid, created


def _ensure_org(conn, oid, official, admin):
    row = conn.execute('SELECT id FROM organizations WHERE id=?', (oid,)).fetchone()
    if not row:
        name = ORG_NAMES[oid]
        conn.execute("INSERT INTO organizations(id,name,organization_type,registration_reference,contact_name,contact_email,contact_phone,status,verified_by_user_id,verified_at,verification_reason,created_by_user_id) VALUES(?,?,'NGO',?,?,?,?,'Approved',?,CURRENT_TIMESTAMP,'Fictional local showcase organization approved for demonstration',?)",
                     (oid,name,'DEMO-NGO-'+str(oid),name+' Coordinator',f'coordinator{oid}@drras-demo.local','+91-90000-'+str(oid).zfill(4),official,admin))
    else:
        # This fixed packaged-demo organization is intentionally approved in the seed.
        conn.execute("UPDATE organizations SET status='Approved',verified_by_user_id=COALESCE(verified_by_user_id,?),verified_at=COALESCE(verified_at,CURRENT_TIMESTAMP),verification_reason=COALESCE(verification_reason,'Fictional local showcase organization approval') WHERE id=?", (official,oid))


def expand_demo_data(conn, write_credentials=False):
    admin = conn.execute("SELECT id FROM users WHERE role='Administrator' ORDER BY id LIMIT 1").fetchone()[0]
    official = conn.execute("SELECT id FROM users WHERE role='Government Official' ORDER BY id LIMIT 1").fetchone()[0]
    created_rows = []
    with conn:
        for oid in (1,2,3): _ensure_org(conn,oid,official,admin)
        # Two additional admins and four officials; original identities/passwords are untouched.
        for role, target, prefix in [('Administrator',2,'admin'),('Government Official',5,'official'),('NGO Coordinator',3,'coordinator'),('Citizen',32,'citizen')]:
            existing = conn.execute('SELECT COUNT(*) FROM users WHERE role=? AND status=\'ACTIVE\'',(role,)).fetchone()[0]
            for i in range(existing+1,target+1):
                org = (i-1)%3+1 if role=='NGO Coordinator' else None
                email=f'{prefix}.{i:03d}@drras-demo.local'
                uid, made = _add_user(conn,email,f'{role} Demo {i:03d}',role,org)
                if role=='NGO Coordinator':
                    conn.execute("INSERT OR IGNORE INTO organization_memberships(organization_id,user_id,membership_role,status) VALUES(?,?,'Coordinator','Active')",(org,uid))
                if made: created_rows.append((uid,email,PASSWORDS[role],role,org))
        for oid in (1,2,3):
            coord=conn.execute("SELECT u.id FROM users u JOIN organization_memberships m ON m.user_id=u.id WHERE u.role='NGO Coordinator' AND m.organization_id=? AND m.status='Active' ORDER BY u.id LIMIT 1",(oid,)).fetchone()
            if not coord:
                email=f'coordinator.org{oid}@drras-demo.local'; uid,made=_add_user(conn,email,f'{ORG_NAMES[oid]} Coordinator','NGO Coordinator',oid)
                conn.execute("INSERT OR IGNORE INTO organization_memberships(organization_id,user_id,membership_role,status) VALUES(?,?,'Coordinator','Active')",(oid,uid))
                if made: created_rows.append((uid,email,PASSWORDS['NGO Coordinator'],'NGO Coordinator',oid))
        # Role categories target 24 each; distribute NGO personnel 8 per organization.
        for category, total, orgs in [('Government Driver',24,[None]),('Government Responder',24,[None]),('NGO Driver',24,[1,2,3]),('NGO Volunteer',24,[1,2,3])]:
            for oid in orgs:
                goal = total if oid is None else total//3
                if category=='Government Driver':
                    rows=conn.execute("SELECT u.id FROM users u JOIN government_driver_approvals a ON a.user_id=u.id WHERE u.role='Driver' AND u.status='ACTIVE' AND u.organization_id IS NULL").fetchall()
                elif category=='Government Responder':
                    rows=conn.execute("SELECT DISTINCT u.id FROM users u JOIN government_personnel p ON p.user_id=u.id AND p.status='Active' WHERE u.role='Volunteer' AND u.status='ACTIVE' AND u.organization_id IS NULL").fetchall()
                else:
                    ptype='Driver' if category=='NGO Driver' else 'Volunteer'
                    rows=conn.execute("SELECT u.id FROM users u JOIN ngo_personnel_approvals a ON a.user_id=u.id WHERE u.role=? AND u.status='ACTIVE' AND a.organization_id=? AND a.personnel_type=? AND a.decision='Approved'",('Driver' if ptype=='Driver' else 'Volunteer',oid,ptype)).fetchall()
                n=len(rows)
                for i in range(n+1,goal+1):
                    serial=(oid*100 if oid else 0)+i
                    email=f"{'gov' if oid is None else 'ngo'+str(oid)}.{('driver' if 'Driver' in category else 'responder' if category=='Government Responder' else 'volunteer')}.{serial:03d}@drras-demo.local"
                    name=f"{ORG_NAMES[oid] if oid else 'Punjab Government'} {category} {i:02d}"
                    uid,made=_identity(conn,category,email,name,oid,admin,official if oid is None else conn.execute("SELECT u.id FROM users u JOIN organization_memberships m ON m.user_id=u.id WHERE u.role='NGO Coordinator' AND m.organization_id=? AND m.status='Active' ORDER BY u.id LIMIT 1",(oid,)).fetchone()[0])
                    if made: created_rows.append((uid,email,PASSWORDS[category],category,oid))
        # Repair any already-approved demo personnel account whose linked profile
        # was missing in a legacy seed run. Preserve all existing profile rows.
        for u in conn.execute("""SELECT DISTINCT u.id,u.name,a.organization_id FROM users u
            JOIN ngo_personnel_approvals a ON a.user_id=u.id AND a.personnel_type='Volunteer' AND a.decision='Approved'
            WHERE u.role='Volunteer' AND u.status='ACTIVE' ORDER BY u.id""").fetchall():
            if not conn.execute("SELECT 1 FROM volunteers WHERE user_id=? AND owner_type='ngo' AND organization_id=?",(u['id'],u['organization_id'])).fetchone():
                initials=''.join(part[0].upper() for part in u['name'].split())[:2]
                conn.execute("INSERT INTO volunteers(initials,name,skill,zone,status,user_id,organization_id,verified,owner_type) VALUES(?,?,?,'Demo Coverage Zone','Available',?,?,1,'ngo')",(initials,u['name'],'Medical aid, distribution and evacuation',u['id'],u['organization_id']))
        for u in conn.execute("""SELECT DISTINCT u.id,u.name FROM users u JOIN government_personnel p ON p.user_id=u.id
            WHERE u.role='Volunteer' AND u.status='ACTIVE' AND u.organization_id IS NULL AND p.status='Active' ORDER BY u.id""").fetchall():
            if not conn.execute("SELECT 1 FROM volunteers WHERE user_id=? AND owner_type='government' AND organization_id IS NULL",(u['id'],)).fetchone():
                initials=''.join(part[0].upper() for part in u['name'].split())[:2]
                conn.execute("INSERT INTO volunteers(initials,name,skill,zone,status,user_id,organization_id,verified,owner_type) VALUES(?,?,?,'Government Demo Coverage','Available',?,NULL,1,'government')",(initials,u['name'],'Medical aid, distribution and evacuation',u['id']))
        # Additional stable owned warehouses and compatible vehicles; stock rows reuse resource catalog.
        resource_ids=[r['id'] for r in conn.execute('SELECT id FROM resources WHERE is_active=1 ORDER BY id').fetchall()]
        for owner,oid in [('government',None),('ngo',1),('ngo',2),('ngo',3)]:
            wh=conn.execute('SELECT id FROM warehouses WHERE owner_type=? AND owner_organization_id IS ? ORDER BY id LIMIT 1',(owner,oid)).fetchone()
            if not wh:
                code='DEMO-GOV-WH' if oid is None else f'DEMO-NGO{oid}-WH'
                conn.execute("INSERT INTO warehouses(code,name,district,address,lat,lng,status,manager_user_id,owner_type,owner_organization_id) VALUES(?,?,'Ludhiana','Demo District Logistics Park',30.90,75.85,'Active',?,?,?)",(code,'Government Relief Warehouse' if oid is None else ORG_NAMES[oid]+' Warehouse',official if oid is None else conn.execute("SELECT id FROM users WHERE role='NGO Coordinator' AND organization_id=? ORDER BY id LIMIT 1",(oid,)).fetchone()[0],owner,oid))
                wh=conn.execute('SELECT id FROM warehouses WHERE code=?',(code,)).fetchone()
            wid=wh['id']
            for rid in resource_ids:
                conn.execute("INSERT OR IGNORE INTO warehouse_stock(warehouse_id,resource_id,on_hand_units,reserved_units,target_stock,status) VALUES(?,?,2500,0,2000,'Safe')",(wid,rid))
            prefix='GOV' if oid is None else f'N{oid}'
            registration_prefix='PB10GV' if oid is None else {1:'PB11PR',2:'PB12KA',3:'PB13RC'}[oid]
            fleet_specs={
                'Cargo Truck':(250,'250 relief units; food, water and bulk ration transport',['food','water','shelter']),
                'Ambulance':(80,'80 relief units; medical supplies and casualty transport',['medical','water']),
                'Rescue Unit':(120,'120 relief units; flood rescue equipment and boats',['rescue','boat','medical']),
                'Relief Van':(120,'120 relief units; general relief kits and shelter materials',['relief','food','water','medical','shelter']),
            }
            for i in range(1, 26):
                code=f'DEMO-{prefix}-V{i:02d}'
                vehicle_type='Cargo Truck' if i<=20 else 'Ambulance' if i<=22 else 'Rescue Unit' if i<=24 else 'Relief Van'
                capacity,description,capabilities=fleet_specs[vehicle_type]
                conn.execute("""INSERT OR IGNORE INTO vehicles(vehicle_code,vehicle_type,capacity_units,capacity_description,
                    capabilities_json,status,warehouse_id,owner_type,owner_organization_id,registration_number,last_inspection_at)
                    VALUES(?,?,?,?,?,'Available',?,?,?,?,CURRENT_TIMESTAMP)""",
                    (code,vehicle_type,capacity,description,json.dumps(capabilities),wid,owner,oid,
                     f'{registration_prefix}{1000+i:04d}'))
                # Reclassify only untouched, available seed fleet rows. Once a
                # vehicle has been used, its historical type and identity remain.
                if not conn.execute("""SELECT 1 FROM vehicles v WHERE v.vehicle_code=? AND v.status='Available'
                    AND v.current_driver_user_id IS NULL
                    AND NOT EXISTS(SELECT 1 FROM dispatches d WHERE d.vehicle_id=v.id)
                    AND NOT EXISTS(SELECT 1 FROM response_assignments a WHERE a.vehicle_id=v.id AND a.status IN ('Assigned','Active'))""",(code,)).fetchone():
                    continue
                conn.execute("""UPDATE vehicles SET vehicle_type=?,capacity_units=?,capacity_description=?,capabilities_json=?,
                    registration_number=COALESCE(registration_number,?),last_inspection_at=COALESCE(last_inspection_at,CURRENT_TIMESTAMP),
                    updated_at=CURRENT_TIMESTAMP WHERE vehicle_code=? AND owner_type=? AND owner_organization_id IS ?
                    AND status='Available' AND current_driver_user_id IS NULL
                    AND NOT EXISTS(SELECT 1 FROM dispatches d WHERE d.vehicle_id=vehicles.id)
                    AND NOT EXISTS(SELECT 1 FROM response_assignments a WHERE a.vehicle_id=vehicles.id AND a.status IN ('Assigned','Active'))""",
                    (vehicle_type,capacity,description,json.dumps(capabilities),f'{registration_prefix}{1000+i:04d}',code,owner,oid))
        conn.execute("""UPDATE vehicles SET registration_number=
            CASE WHEN owner_type='government' THEN 'PB10GV'
                 WHEN owner_organization_id=1 THEN 'PB11PR'
                 WHEN owner_organization_id=2 THEN 'PB12KA'
                 WHEN owner_organization_id=3 THEN 'PB13RC'
                 ELSE 'PB99UN' END || printf('%04d',id)
            WHERE registration_number IS NULL OR trim(registration_number)=''""")
        # Public information and account-scoped persisted activity.
        for row in conn.execute("SELECT id FROM users WHERE role='Citizen' AND status='ACTIVE'").fetchall():
            uid=row['id']; rid=f'DEMO-REQ-CIT-{uid:05d}'
            if not conn.execute('SELECT 1 FROM emergency_requests WHERE id=?',(rid,)).fetchone():
                user=conn.execute('SELECT name FROM users WHERE id=?',(uid,)).fetchone()
                conn.execute("INSERT INTO emergency_requests(id,requester_name,area,address,need,people_affected,vulnerable_people,priority_score,status,time_str,requester_user_id,incident_id,zone_id,description,verification_status) VALUES(?,?,?,'Demo District','Drinking water and food ration kits',6,0,68,'Awaiting allocation',CURRENT_TIMESTAMP,?,'INC-2026-FLOOD','Z-01','Seeded citizen request available for live response demonstration','Unverified')",(rid,user['name'],'Ward '+str(uid%12+1),uid))
                conn.execute("INSERT INTO request_events(request_id,event_type,to_status,reason,actor_user_id) VALUES(?,'RequestCreated','Awaiting allocation','Fictional local demo request',?)",(rid,uid))
                conn.execute("INSERT OR IGNORE INTO activities(workspace_key,title,details) VALUES(?,?,?)",(f'user:{uid}','Demo account ready','Citizen profile and persisted request are available.'))
        # Ensure shelter/public advisory baseline and staff activity trails.
        if not conn.execute("SELECT 1 FROM public_advisories WHERE status='Published' LIMIT 1").fetchone():
            conn.execute("INSERT INTO public_advisories(id,incident_id,title,body,category,status,created_by_user_id,approved_by_user_id,published_at) VALUES('ADV-DEMO-SAFETY','INC-2026-FLOOD','Flood safety and relief information','Use designated relief shelters and follow verified evacuation instructions.','Safety','Published',?,?,CURRENT_TIMESTAMP)",(official,official))
        # Historical, completed records make individual personnel views useful while
        # leaving the majority of the roster free under the live availability rules.
        for oid in (None,1,2,3):
            owner='government' if oid is None else 'ngo'
            drivers=conn.execute("SELECT id,name FROM users WHERE role='Driver' AND status='ACTIVE' AND organization_id IS ? ORDER BY id",(oid,)).fetchall()
            for index,u in enumerate(drivers):
                if index % 4: continue
                vehicle=conn.execute("SELECT * FROM vehicles WHERE owner_type=? AND owner_organization_id IS ? ORDER BY id LIMIT 1",(owner,oid)).fetchone()
                wh=conn.execute("SELECT id FROM warehouses WHERE owner_type=? AND owner_organization_id IS ? ORDER BY id LIMIT 1",(owner,oid)).fetchone()
                did=f'DEMO-HIST-DRIVER-{u["id"]}'
                if vehicle and wh and not conn.execute('SELECT 1 FROM dispatches WHERE id=?',(did,)).fetchone():
                    conn.execute("INSERT INTO dispatches(id,vehicle,driver,destination,load_items,status,eta,incident_id,zone_id,vehicle_id,driver_user_id,created_by_user_id,warehouse_id,planned_at,departed_at,arrived_at,delivered_at,route_status,delivery_result,delivery_notes,owner_type,owner_organization_id) VALUES(?,?,?,?,?,'Delivered','Completed','INC-2026-FLOOD','Z-01',?,?,?, ?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'Completed','Delivered','Completed historical demo trip',?,?)",(did,vehicle['vehicle_code']+' · '+vehicle['vehicle_type'],u['name'],'Civil Lines Relief Camp','Water and food relief kits',vehicle['id'],u['id'],official,wh['id'],owner,oid))
            if oid is None:
                roster=conn.execute("SELECT u.id,u.name,v.id volunteer_id FROM users u JOIN volunteers v ON v.user_id=u.id JOIN government_personnel gp ON gp.user_id=u.id AND gp.status='Active' WHERE u.role='Volunteer' AND u.status='ACTIVE' AND v.verified=1 AND u.organization_id IS NULL ORDER BY u.id").fetchall()
            else:
                roster=conn.execute("SELECT u.id,u.name,v.id volunteer_id FROM users u JOIN volunteers v ON v.user_id=u.id JOIN ngo_personnel_approvals a ON a.user_id=u.id AND a.organization_id=? AND a.personnel_type='Volunteer' AND a.decision='Approved' WHERE u.role='Volunteer' AND u.status='ACTIVE' AND v.verified=1 AND v.owner_type='ngo' AND v.organization_id=? ORDER BY u.id",(oid,oid)).fetchall()
            for index,u in enumerate(roster):
                if index % 4: continue
                tid=f'DEMO-HIST-TASK-{u["id"]}'
                if not conn.execute('SELECT 1 FROM volunteer_tasks WHERE id=?',(tid,)).fetchone():
                    conn.execute("INSERT INTO volunteer_tasks(id,incident_id,zone_id,organization_id,volunteer_id,title,task_type,description,quantity_expected,quantity_received,quantity_completed,quantity_damaged,quantity_remaining,status,assigned_by_user_id,accepted_at,started_at,submitted_at,reviewed_at,completed_at,reviewed_by_user_id,review_notes) VALUES(?,'INC-2026-FLOOD','Z-01',?,?,?,'Distribution','Historic completed neighborhood water handout.',8,8,7,1,0,'Completed',?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,?,'Quantities reconciled and reviewed.')",(tid,oid,u['volunteer_id'],f'Completed relief task — {u["name"]}',official,official))
                    conn.execute("INSERT INTO task_checkpoints(task_id,checkpoint_type,lat,lng,notes,quantity_delta,created_by_user_id) VALUES(?,'CheckIn',30.9125,75.8340,'Historical volunteer check-in at the Ward 4 distribution point.',0,?)",(tid,u['id']))
                    conn.execute("INSERT OR IGNORE INTO field_reports(id,incident_id,zone_id,reporter_user_id,category,severity,description,lat,lng,status,reviewer_user_id,review_reason) VALUES(?,'INC-2026-FLOOD','Z-01',?,'Distribution','Low','Historical report: household relief distribution completed and reconciled.',30.9125,75.8340,'Verified',?,'Reviewed by incident command.')",(f'DEMO-FIELD-{u["id"]}',u['id'],official))
        for uid, in conn.execute("SELECT id FROM users WHERE role IN ('Administrator','Government Official','NGO Coordinator','Driver','Volunteer') AND status='ACTIVE'").fetchall():
            conn.execute("INSERT OR IGNORE INTO activities(workspace_key,title,details) VALUES(?,?,?)",(f'user:{uid}','Demo workspace available','Owner-scoped operational records are linked to this account.'))
    if write_credentials:
        _write_credentials(conn, created_rows)
    return created_rows


def _write_credentials(conn, created_rows=None):
    # Regenerate from persisted stable demo identities and verify their hashes.
    rows=[]
    legacy_passwords={1:'admin123',2:'official123',3:'ngo123',4:'volunteer123',5:'citizen123',6:'driver123',8:'driver123',9:'driver123',10:'driver123',11:'volunteer123',12:'driver123',13:'volunteer123',14:'ngo123',15:'driver123',16:'volunteer123',17:'driver123',18:'volunteer123',19:'govvol123',20:'volunteer123',21:'volunteer123',23:'ngo123',24:'driver123',25:'volunteer123',26:'driver123',27:'volunteer123'}
    for u in conn.execute("SELECT u.id,u.email,u.name,u.role,u.organization_id,u.status,u.password FROM users u ORDER BY u.role,u.organization_id,u.email"):
        email=u['email'].lower(); role=u['role']
        password=legacy_passwords.get(u['id'])
        if password is None and u['id'] >= 28:
            category=role if role!='Volunteer' else ('NGO Volunteer' if u['organization_id'] else 'Government Responder')
            if role=='Driver': category='NGO Driver' if u['organization_id'] else 'Government Driver'
            compatibility={
                'Administrator':['admin123'], 'Government Official':['official123'],
                'NGO Coordinator':['ngo123'], 'Citizen':['citizen123'],
                'Government Driver':['driver123'], 'NGO Driver':['driver123'],
                'Government Responder':['govvol123'], 'NGO Volunteer':['volunteer123'],
            }
            passwords=[PASSWORDS.get(category),*compatibility.get(category,[])]
            password=next((candidate for candidate in passwords if candidate and check_password_hash(u['password'],candidate)),None)
        elif password and not check_password_hash(u['password'],password):
            password=None
        if password:
            org=ORG_NAMES.get(u['organization_id']) or ('Government' if role in ('Government Official','Driver','Volunteer') else '—')
            rows.append((u['name'],u['email'],password,role,org,u['status']))
    path=Path(__file__).resolve().parent/'docs'/'DEMO_CREDENTIALS.md'
    lines=['# Local demo credentials','','These accounts are fictional and intended only for local demonstrations. Credentials are listed only when a candidate password was verified against the stored hash; existing unknown passwords are omitted. Do not use these passwords in production.','','| Name | Email | Password | Role | Organization | Status |','|---|---|---|---|---|---|']
    lines += [f'| {n} | {e} | {p} | {r} | {o} | {s} |' for n,e,p,r,o,s in rows]
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')


def validation_report(conn, workflow_results='Not run'):
    role_counts={r['role']:r['n'] for r in conn.execute("SELECT role,COUNT(*) n FROM users WHERE status='ACTIVE' GROUP BY role")}
    gov_drivers=conn.execute(f"SELECT COUNT(*) total,SUM(CASE WHEN NOT EXISTS(SELECT 1 FROM dispatches d WHERE d.driver_user_id=u.id AND d.status IN {ACTIVE_DISPATCH}) AND NOT EXISTS(SELECT 1 FROM response_assignments a WHERE a.driver_user_id=u.id AND a.status IN ('Assigned','Active')) THEN 1 ELSE 0 END) available FROM users u JOIN government_driver_approvals g ON g.user_id=u.id WHERE u.role='Driver' AND u.status='ACTIVE' AND u.organization_id IS NULL").fetchone()
    gov_vol=conn.execute(f"SELECT COUNT(DISTINCT u.id) total,SUM(CASE WHEN NOT EXISTS(SELECT 1 FROM volunteers v JOIN volunteer_tasks t ON t.volunteer_id=v.id WHERE v.user_id=u.id AND t.status IN {ACTIVE_TASK}) AND NOT EXISTS(SELECT 1 FROM response_assignments a JOIN volunteers v ON v.id=a.volunteer_id WHERE v.user_id=u.id AND a.status IN ('Assigned','Active')) THEN 1 ELSE 0 END) available FROM users u JOIN government_personnel p ON p.user_id=u.id AND p.status='Active' WHERE u.role='Volunteer' AND u.status='ACTIVE' AND u.organization_id IS NULL").fetchone()
    ngo=[]
    for oid in (1,2,3):
        counts={}
        for kind,role in [('Drivers','Driver'),('Volunteers','Volunteer')]:
            row=conn.execute(f"SELECT COUNT(*) total FROM users u JOIN ngo_personnel_approvals a ON a.user_id=u.id WHERE u.role=? AND u.status='ACTIVE' AND a.organization_id=? AND a.personnel_type=? AND a.decision='Approved'",(role,oid,role)).fetchone()
            counts[kind]=row['total']
            if role=='Driver':
                free=conn.execute(f"SELECT COUNT(*) FROM users u JOIN ngo_personnel_approvals a ON a.user_id=u.id AND a.organization_id=? AND a.personnel_type='Driver' AND a.decision='Approved' WHERE u.role='Driver' AND u.status='ACTIVE' AND NOT EXISTS(SELECT 1 FROM dispatches d WHERE d.driver_user_id=u.id AND d.status IN {ACTIVE_DISPATCH}) AND NOT EXISTS(SELECT 1 FROM response_assignments x WHERE x.driver_user_id=u.id AND x.status IN ('Assigned','Active'))",(oid,)).fetchone()[0]
            else:
                free=conn.execute(f"SELECT COUNT(DISTINCT u.id) FROM users u JOIN ngo_personnel_approvals a ON a.user_id=u.id AND a.organization_id=? AND a.personnel_type='Volunteer' AND a.decision='Approved' JOIN volunteers v ON v.user_id=u.id AND v.organization_id=a.organization_id AND v.owner_type='ngo' AND v.verified=1 WHERE u.role='Volunteer' AND u.status='ACTIVE' AND NOT EXISTS(SELECT 1 FROM volunteer_tasks t WHERE t.volunteer_id=v.id AND t.status IN {ACTIVE_TASK}) AND NOT EXISTS(SELECT 1 FROM response_assignments x WHERE x.volunteer_id=v.id AND x.status IN ('Assigned','Active'))",(oid,)).fetchone()[0]
            counts[kind+'Available']=free
        ngo.append((oid,counts))
    totals={}
    for role,apptype,join in [('Driver','Driver','dispatches'),('Volunteer','Volunteer','volunteer_tasks')]:
        totals[role]=conn.execute('SELECT count(*) FROM users WHERE role=? AND status=\'ACTIVE\'',(role,)).fetchone()[0]
    return role_counts,dict(gov_drivers),dict(gov_vol),ngo

