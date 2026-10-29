"""
DRRAS Demo Seed Script
Populates a realistic, interconnected disaster-response operations platform
for a fictional flood incident scenario in Demo District / Sutlej River Basin.
Safe and idempotent to run repeatedly.
"""

import os
import json
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash
import database
import showcase_seed
import demo_expansion
import demo_identities

def seed_demo_data(db_path=None):
    if db_path:
        os.environ['DRRAS_DB_PATH'] = db_path

    database.init_db()
    conn = database.get_db()

    with conn:
        cur = conn.cursor()

        # 1. Demo Users
        seed_people = [
            (1, 'admin123', 'Administrator', None), (2, 'official123', 'Government Official', None),
            (3, 'ngo123', 'NGO Coordinator', None), (4, 'volunteer123', 'Volunteer', 1),
            (5, 'citizen123', 'Citizen', None), (6, 'driver123', 'Driver', None),
        ]
        users = []
        for uid, password, role, oid in seed_people:
            name = demo_identities.human_name(uid)
            category = demo_identities.account_category(role, oid, uid)
            users.append((demo_identities.canonical_email(name, category), generate_password_hash(password), name, ''.join(p[0] for p in name.split()).upper(), role, 'ACTIVE', f'+91-98765-{uid:05d}'))
        for email, pwd, name, inits, role, status, phone in users:
            # Retain existing active identities across canonical-email changes;
            # expansion below fills any role-specific roster shortage.
            if role == 'NGO Coordinator':
                existing = cur.execute("SELECT 1 FROM users u JOIN organization_memberships m ON m.user_id=u.id WHERE u.role=? AND u.status='ACTIVE' AND m.organization_id=1 AND m.membership_role='Coordinator' AND m.status='Active' LIMIT 1", (role,)).fetchone()
            else:
                existing = cur.execute("SELECT 1 FROM users WHERE role=? AND status='ACTIVE' LIMIT 1", (role,)).fetchone()
            if existing:
                continue
            cur.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email.lower(),))
            if not cur.fetchone():
                cur.execute('''
                INSERT INTO users (email, password, name, initials, role, status, phone)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (email, pwd, name, inits, role, status, phone))

        admin_id = cur.execute("SELECT id FROM users WHERE role='Administrator' AND status='ACTIVE' ORDER BY id LIMIT 1").fetchone()[0]
        official_id = cur.execute("SELECT id FROM users WHERE role='Government Official' AND status='ACTIVE' ORDER BY id LIMIT 1").fetchone()[0]
        ngo_id = cur.execute("SELECT id FROM users WHERE role='NGO Coordinator' AND status='ACTIVE' ORDER BY id LIMIT 1").fetchone()[0]
        volunteer_id = cur.execute("SELECT id FROM users WHERE role='Volunteer' AND status='ACTIVE' ORDER BY id LIMIT 1").fetchone()[0]
        citizen_id = cur.execute("SELECT id FROM users WHERE role='Citizen' AND status='ACTIVE' ORDER BY id LIMIT 1").fetchone()[0]
        driver_id = cur.execute("SELECT id FROM users WHERE role='Driver' AND status='ACTIVE' ORDER BY id LIMIT 1").fetchone()[0]

        # 2. Organizations
        orgs = [
            (1, 'Punjab Relief Coalition', 'NGO', 'NGO-PB-2024-88', 'Neha Kapoor', 'ngo@drras.in', '+91-98765-00003', 'Approved'),
            (2, 'Khalsa Aid Foundation', 'NGO', 'NGO-KA-2023-12', 'Gurinder Singh', 'contact@khalsaaid.org', '+91-98765-11111', 'Approved'),
            (3, 'Red Cross District Chapter', 'NGO', 'RC-PB-2022-09', 'Dr. Harjit Sodhi', 'redcross@drras.in', '+91-98765-22222', 'Pending')
        ]
        for oid, name, otype, reg, cname, cemail, cphone, st in orgs:
            cur.execute("SELECT id FROM organizations WHERE id = ?", (oid,))
            if not cur.fetchone():
                cur.execute('''
                INSERT INTO organizations (id, name, organization_type, registration_reference, contact_name, contact_email, contact_phone, status, verified_by_user_id, verified_at, created_by_user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                ''', (oid, name, otype, reg, cname, cemail, cphone, st, official_id if st == 'Approved' else None, admin_id))

        # These three fixed fictional showcase organizations are approved by the
        # local demo seed so all subsequent owned-resource seeding is repeat-safe.
        for oid in (1, 2, 3):
            demo_expansion._ensure_org(cur, oid, official_id, admin_id)

        # Organization membership for NGO Coordinator
        cur.execute("SELECT id FROM organization_memberships WHERE organization_id = 1 AND user_id = ?", (ngo_id,))
        if not cur.fetchone():
            cur.execute('''
            INSERT INTO organization_memberships (organization_id, user_id, membership_role, status)
            VALUES (1, ?, 'Coordinator', 'Active')
            ''', (ngo_id,))

        # 3. Incident
        cur.execute("SELECT id FROM incidents WHERE id = 'INC-2026-FLOOD'")
        if not cur.fetchone():
            cur.execute('''
            INSERT INTO incidents (id, title, incident_type, severity, description, district, status, command_officer_user_id, reported_at, activated_at, created_by_user_id)
            VALUES ('INC-2026-FLOOD', 'Flood Response — Sutlej River Basin', 'Flood', 'Severe', 
                    'Monsoon river swelling causing localized inundation across low-lying municipal wards and riverside villages.',
                    'Demo District', 'Active', ?, '2026-10-24 06:00:00', '2026-10-24 07:30:00', ?)
            ''', (official_id, official_id))

        # 4. Operational Zones
        zones = [
            ('Z-01', 'INC-2026-FLOOD', 'Dhaliwal Colony — Ward 4', 'Low-lying residential area with 1-2ft water accumulation', 'Demo District', 'Ward 4 Municipal Sector', 30.9125, 75.8340, 'High', 'Active'),
            ('Z-02', 'INC-2026-FLOOD', 'Focal Point Industrial Area — Ward 8', 'Industrial and labor housing quarters near drain overflow', 'Demo District', 'Focal Point Phase 5', 30.8950, 75.8750, 'Critical', 'Active'),
            ('Z-03', 'INC-2026-FLOOD', 'Riverbank Village / Old Riverside', 'Direct river embankment perimeter vulnerable to rapid breach', 'Demo District', 'Old Sutlej Bund Road', 30.9350, 75.8150, 'Severe', 'Active')
        ]
        for zid, inc_id, zname, zdesc, zdist, zbound, lat, lng, sev, st in zones:
            cur.execute("SELECT id FROM zones WHERE id = ?", (zid,))
            if not cur.fetchone():
                cur.execute('''
                INSERT INTO zones (id, incident_id, name, description, district, address_or_boundary, center_lat, center_lng, severity, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (zid, inc_id, zname, zdesc, zdist, zbound, lat, lng, sev, st))

        # Zone Adoptions
        cur.execute("SELECT id FROM zone_adoptions WHERE zone_id = 'Z-02' AND organization_id = 1")
        if not cur.fetchone():
            cur.execute('''
            INSERT INTO zone_adoptions (incident_id, zone_id, organization_id, requested_by_user_id, requested_capacity, available_volunteers, available_resource_summary, status, reviewed_by_user_id, reviewed_at, decision_reason)
            VALUES ('INC-2026-FLOOD', 'Z-02', 1, ?, 'Shelter and dry ration distribution', 25, '2 Relief Vans, 500 Food Kits', 'Approved', ?, CURRENT_TIMESTAMP, 'Authorized by District Disaster Management Authority')
            ''', (ngo_id, official_id))

        cur.execute("SELECT id FROM zone_adoptions WHERE zone_id = 'Z-03' AND organization_id = 2")
        if not cur.fetchone():
            cur.execute('''
            INSERT INTO zone_adoptions (incident_id, zone_id, organization_id, requested_by_user_id, requested_capacity, available_volunteers, available_resource_summary, status)
            VALUES ('INC-2026-FLOOD', 'Z-03', 2, ?, 'Emergency boat rescue and medical camps', 15, '3 Rescue Rafts, Medical Team', 'Requested')
            ''', (ngo_id,))

        # 5. Warehouses
        warehouses = [
            (1, 'WH-CENTRAL', 'Central Relief Depot', 'Demo District', 'Station Road, Sector 3, Ludhiana', 30.9010, 75.8570, 'Active', admin_id),
            (2, 'WH-NORTH', 'North Logistics Hub', 'Demo District', 'Old River Bypass, North Ward, Ludhiana', 30.9400, 75.8200, 'Active', official_id)
        ]
        for wid, code, wname, dist, addr, lat, lng, st, mid in warehouses:
            cur.execute("SELECT id FROM warehouses WHERE id = ?", (wid,))
            if not cur.fetchone():
                cur.execute('''
                INSERT INTO warehouses (id, code, name, district, address, lat, lng, status, manager_user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (wid, code, wname, dist, addr, lat, lng, st, mid))

        # 6. Resources & Warehouse Stock
        resources = [
            (1, 'RES-001', 'Drinking Water', 'Water & Sanitation', 'litres', 'Clean sealed potable drinking water bottles (2L)', 0),
            (2, 'RES-002', 'Food Ration Kits', 'Food Supplies', 'kits', 'Standard family dry ration kit containing rice, pulses, oil, salt', 0),
            (3, 'RES-003', 'Medical Kits', 'Medical', 'kits', 'Emergency first-aid, ORS, trauma dressings, water-purification tablets', 1),
            (4, 'RES-004', 'Blankets', 'Shelter & Warmth', 'pieces', 'Thermal relief fleece blankets', 0),
            (5, 'RES-005', 'Shelter Tents', 'Shelter & Warmth', 'tents', 'Weatherproof 6-person emergency dome shelter tents', 0)
        ]
        for rid, sku, rname, cat, unit, desc, exp in resources:
            cur.execute("SELECT id FROM resources WHERE id = ?", (rid,))
            if not cur.fetchone():
                cur.execute('''
                INSERT INTO resources (id, sku, name, category, unit, description, track_expiry, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                ''', (rid, sku, rname, cat, unit, desc, exp))

        stocks = [
            (1, 1, 4820, 0, 8000, 'Low'),
            (1, 2, 1186, 0, 2000, 'Low'),
            (1, 3, 312, 0, 500, 'Low'),
            (1, 4, 2940, 0, 2500, 'Safe'),
            (1, 5, 76, 0, 150, 'Low'),
            (2, 1, 1500, 0, 3000, 'Low'),
            (2, 2, 600, 0, 1000, 'Low'),
            (2, 3, 120, 0, 250, 'Low'),
            (2, 4, 800, 0, 1000, 'Low'),
            (2, 5, 30, 0, 100, 'Critical')
        ]
        for wid, rid, onhand, res, tgt, st in stocks:
            cur.execute("SELECT id FROM warehouse_stock WHERE warehouse_id = ? AND resource_id = ?", (wid, rid))
            if not cur.fetchone():
                cur.execute('''
                INSERT INTO warehouse_stock (warehouse_id, resource_id, on_hand_units, reserved_units, target_stock, status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (wid, rid, onhand, res, tgt, st))

        # 7. Update Legacy Emergency Requests with incident_id, zone_id, requester_user_id
        cur.execute("UPDATE emergency_requests SET incident_id = 'INC-2026-FLOOD', zone_id = 'Z-01', requester_user_id = ?, verification_status = 'Verified' WHERE id = 'REQ-2048'", (citizen_id,))
        cur.execute("UPDATE emergency_requests SET incident_id = 'INC-2026-FLOOD', zone_id = 'Z-02', verification_status = 'Verified' WHERE id = 'REQ-2047'")
        cur.execute("UPDATE emergency_requests SET incident_id = 'INC-2026-FLOOD', zone_id = 'Z-03', verification_status = 'Verified' WHERE id = 'REQ-2046'")
        cur.execute("UPDATE emergency_requests SET incident_id = 'INC-2026-FLOOD', zone_id = 'Z-01', verification_status = 'Verified' WHERE id = 'REQ-2045'")

        # Ensure Request Items exist
        cur.execute("SELECT COUNT(*) FROM request_items WHERE request_id = 'REQ-2048'")
        if cur.fetchone()[0] == 0:
            cur.execute('''
            INSERT INTO request_items (request_id, resource_id, quantity_requested, quantity_reserved, quantity_issued, quantity_delivered)
            VALUES ('REQ-2048', 3, 2, 0, 0, 0), ('REQ-2048', 1, 12, 0, 0, 0)
            ''')

        # 8. Volunteer Tasks
        tasks = [
            ('TASK-041', 'INC-2026-FLOOD', 'Z-02', 1, 1, 'REQ-2047', None, 'Medical First Aid Triage at Focal Point', 'Medical', 'Conduct mobile health checks and dispense ORS/first aid kits to evacuated workers.', 20, 20, 14, 0, 6, 'In Progress', '2026-10-26 08:00', '2026-10-26 16:00', official_id),
            ('TASK-042', 'INC-2026-FLOOD', 'Z-01', 1, 2, 'REQ-2048', None, 'Clean Water Distribution — Ward 4', 'Distribution', 'Distribute 2L sealed water bottles door-to-door in inundated street 3.', 50, 0, 0, 0, 50, 'Assigned', '2026-10-26 10:00', '2026-10-26 14:00', ngo_id),
            ('TASK-043', 'INC-2026-FLOOD', 'Z-03', 2, 3, 'REQ-2046', None, 'Search & Rescue Evacuation Support', 'Rescue', 'Assist NDRF team with inflatable boats along Sutlej embankment perimeter.', 10, 10, 8, 0, 2, 'In Progress', '2026-10-26 06:00', '2026-10-26 18:00', official_id)
        ]
        for tid, inc, zid, org, vid, req, dsp, title, ttype, desc, qexp, qrec, qcomp, qdam, qrem, st, sstart, send, abby in tasks:
            cur.execute("SELECT id FROM volunteer_tasks WHERE id = ?", (tid,))
            if not cur.fetchone():
                cur.execute('''
                INSERT INTO volunteer_tasks (id, incident_id, zone_id, organization_id, volunteer_id, request_id, dispatch_id, title, task_type, description, quantity_expected, quantity_received, quantity_completed, quantity_damaged, quantity_remaining, status, shift_start, shift_end, assigned_by_user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (tid, inc, zid, org, vid, req, dsp, title, ttype, desc, qexp, qrec, qcomp, qdam, qrem, st, sstart, send, abby))

        # Checkpoints for TASK-041
        cur.execute("SELECT COUNT(*) FROM task_checkpoints WHERE task_id = 'TASK-041'")
        if cur.fetchone()[0] == 0:
            cur.execute('''
            INSERT INTO task_checkpoints (task_id, checkpoint_type, lat, lng, notes, quantity_delta, created_by_user_id)
            VALUES ('TASK-041', 'CheckIn', 30.8955, 75.8752, 'Responder checked in at Focal Point relief tent.', 0, ?),
                   ('TASK-041', 'Progress', 30.8960, 75.8760, '14 medical kits handed over to families with elderly residents.', 14, ?)
            ''', (volunteer_id, volunteer_id))

        # 9. Donations (Including declared vs received discrepancy demo!)
        donations = [
            ('DON-2026-001', 1, 'Ludhiana Chamber of Commerce & Industry', 'Cash', 'INC-2026-FLOOD', 'Z-01', 1, 50000000, 'INR', 'Emergency flood relief fund contribution for immediate purchase of rations and fuels.', 'Accepted', 'REF-CC-8821', admin_id, '2026-10-24 11:00:00', '2026-10-24 12:00:00', official_id, 'Verified via RTGS bank confirmation UTR#774182.'),
            ('DON-2026-002', 1, 'Apex Agro Foods Ltd.', 'InKind', 'INC-2026-FLOOD', 'Z-02', 1, None, 'INR', '500 Standard Family Dry Ration Kits for Ward 8 flood victims.', 'Accepted', 'REF-APEX-44', ngo_id, '2026-10-25 09:30:00', '2026-10-25 11:15:00', official_id, 'Shipment verified at Central Depot: 480 kits received in good condition, 20 water-damaged in transit and rejected.'),
            ('DON-2026-003', 2, 'MedLife Pharma Alliance', 'InKind', 'INC-2026-FLOOD', 'Z-03', 2, None, 'INR', '200 Essential Trauma & First Aid kits in transit from Delhi facility.', 'In Transit', 'REF-MED-109', ngo_id, None, None, None, 'Expected arrival via NH-44 transport convoy.')
        ]
        for did, oid, dname, dtype, inc, zid, whid, amt, curr_code, notes, st, ref, sub_uid, rec_at, ver_at, ver_uid, vnotes in donations:
            cur.execute("SELECT id FROM donations WHERE id = ?", (did,))
            if not cur.fetchone():
                cur.execute('''
                INSERT INTO donations (id, organization_id, donor_name, donation_type, incident_id, zone_id, destination_warehouse_id, declared_amount_paise, currency, declared_notes, status, reference_code, submitted_by_user_id, received_at, verified_at, verified_by_user_id, verification_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (did, oid, dname, dtype, inc, zid, whid, amt, curr_code, notes, st, ref, sub_uid, rec_at, ver_at, ver_uid, vnotes))

        # Donation Items
        cur.execute("SELECT COUNT(*) FROM donation_items WHERE donation_id = 'DON-2026-002'")
        if cur.fetchone()[0] == 0:
            cur.execute('''
            INSERT INTO donation_items (donation_id, resource_id, quantity_declared, quantity_received, quantity_accepted, quantity_rejected, reason)
            VALUES ('DON-2026-002', 2, 500, 480, 480, 20, '20 carton packaging ruptured due to rain exposure during transit')
            ''')
        cur.execute("SELECT COUNT(*) FROM donation_items WHERE donation_id = 'DON-2026-003'")
        if cur.fetchone()[0] == 0:
            cur.execute('''
            INSERT INTO donation_items (donation_id, resource_id, quantity_declared, quantity_received, quantity_accepted, quantity_rejected, reason)
            VALUES ('DON-2026-003', 3, 200, 0, 0, 0, NULL)
            ''')

        # 10. Shelter Admissions & Transfers
        shelters = cur.execute("SELECT id, name, occupants, capacity FROM shelters").fetchall()
        if shelters:
            s1_id = shelters[0]['id']
            cur.execute("SELECT COUNT(*) FROM shelter_admissions WHERE shelter_id = ?", (s1_id,))
            if cur.fetchone()[0] == 0:
                cur.execute('''
                INSERT INTO shelter_admissions (id, shelter_id, incident_id, request_id, household_reference, people_count, status, referred_by_user_id, checked_in_by_user_id, admitted_at)
                VALUES ('ADM-001', ?, 'INC-2026-FLOOD', 'REQ-2047', 'HH-FOCAL-22', 4, 'Admitted', ?, ?, '2026-10-25 14:00:00'),
                       ('ADM-002', ?, 'INC-2026-FLOOD', NULL, 'HH-FOCAL-89', 6, 'Admitted', ?, ?, '2026-10-25 15:30:00')
                ''', (s1_id, official_id, official_id, s1_id, official_id, official_id))

        # 11. Financial Budgets, Requests & Ledger Transactions
        cur.execute("SELECT id FROM fund_budgets WHERE incident_id = 'INC-2026-FLOOD'")
        if not cur.fetchone():
            budgets = [
                ('Food Supplies', 170000000),      # ₹17.0L
                ('Medical Relief', 130000000),     # ₹13.0L
                ('Transport & Fleet', 110000000),  # ₹11.0L
                ('Emergency Shelters', 90000000)   # ₹9.0L
            ]
            for cat, amt in budgets:
                cur.execute('''
                INSERT INTO fund_budgets (incident_id, organization_id, category, budget_amount_paise, approved_by_user_id, approved_at)
                VALUES ('INC-2026-FLOOD', NULL, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (cat, amt, official_id))

        cur.execute("SELECT id FROM fund_requests WHERE id = 'FR-2026-01'")
        if not cur.fetchone():
            cur.execute('''
            INSERT INTO fund_requests (id, incident_id, organization_id, category, purpose, requested_amount_paise, approved_amount_paise, status, requested_by_user_id, reviewed_by_user_id, decision_reason)
            VALUES ('FR-2026-01', 'INC-2026-FLOOD', 1, 'Food Supplies', 'Procurement of emergency high-energy biscuits and dry ration staples for 1000 evacuated persons.',
                    80000000, 80000000, 'Reconciled', ?, ?, 'Approved by District Emergency Disaster Committee')
            ''', (ngo_id, official_id))

        cur.execute("SELECT id FROM fund_transactions WHERE id = 'TX-2026-001'")
        if not cur.fetchone():
            cur.execute('''
            INSERT INTO fund_transactions (id, fund_request_id, incident_id, organization_id, transaction_type, amount_paise, reference_code, status, performed_by_user_id, approved_by_user_id, receipt_reference, reason, occurred_at)
            VALUES ('TX-2026-001', 'FR-2026-01', 'INC-2026-FLOOD', 1, 'Commitment', 80000000, 'COMM-PB-901', 'Completed', ?, ?, 'COMM-DOC-01', 'Committed for bulk staple grain purchase order #412', '2026-10-24 14:00:00'),
                   ('TX-2026-002', 'FR-2026-01', 'INC-2026-FLOOD', 1, 'Payment', 80000000, 'PAY-PB-901', 'Completed', ?, ?, 'INVOICE-GRAIN-88', 'Supplier payment disbursed via RTGS bank portal', '2026-10-25 10:30:00')
            ''', (official_id, official_id, official_id, official_id))

        # 12. Public Advisories
        cur.execute("SELECT id FROM public_advisories WHERE id = 'ADV-2026-01'")
        if not cur.fetchone():
            cur.execute('''
            INSERT INTO public_advisories (id, incident_id, zone_id, title, body, category, status, created_by_user_id, approved_by_user_id, published_at, valid_until)
            VALUES ('ADV-2026-01', 'INC-2026-FLOOD', 'Z-02', 
                    'Urgent Flood Evacuation Notice — Focal Point Sector 8',
                    'Residents and workers in low-lying industrial plots near Drain No. 3 are advised to move to the designated Govt. School Relief Camp on Link Road. Emergency transport is deployed.',
                    'Evacuation', 'Published', ?, ?, '2026-10-24 08:00:00', '2026-10-27 18:00:00')
            ''', (official_id, official_id))

        # 13. Inter-Agency Requests
        cur.execute("SELECT id FROM inter_agency_requests WHERE id = 'IAR-2026-01'")
        if not cur.fetchone():
            cur.execute('''
            INSERT INTO inter_agency_requests (id, incident_id, requesting_agency, receiving_agency, capability, quantity, urgency, destination, needed_by, status, submitted_by_user_id, submitted_at, acknowledged_at, accepted_at, mobilized_at)
            VALUES ('IAR-2026-01', 'INC-2026-FLOOD', 'District Administration', 'National Disaster Response Force (NDRF)',
                    'Motorized Inflatable Rescue Rafts', 4, 'Immediate', 'Riverbank Village Bund Point', '2026-10-24 09:00:00',
                    'Mobilized', ?, '2026-10-24 07:45:00', '2026-10-24 08:00:00', '2026-10-24 08:15:00', '2026-10-24 08:45:00')
            ''', (official_id,))

        # 14. Notifications for each role
        demo_notifs = [
            (admin_id, 'system_ready', 'System Operations Nominal', 'Relief command platform initialized with active Sutlej Flood incident and versioned schema.', 'incident', 'INC-2026-FLOOD'),
            (official_id, 'action_required', 'Adoption Request Pending Review', 'Khalsa Aid Foundation submitted zone adoption request for Riverbank Village (Z-03).', 'adoption', 'Z-03'),
            (ngo_id, 'adoption_approved', 'Zone Adoption Approved', 'Your adoption of Focal Point Industrial Area (Z-02) was approved by District Command.', 'zone', 'Z-02'),
            (volunteer_id, 'task_assigned', 'Field Mission Assigned', 'You have been assigned to Medical First Aid Triage at Focal Point (TASK-041).', 'task', 'TASK-041'),
            (citizen_id, 'request_update', 'Relief Dispatch En Route', 'Vehicle V-12 is en route to Dhaliwal Colony for your emergency medical request (REQ-2048).', 'request', 'REQ-2048'),
            (driver_id, 'dispatch_assigned', 'Active Trip Assigned', 'Dispatch DSP-12 assigned for medical supply delivery to Riverbank Village.', 'dispatch', 'DSP-12')
        ]
        for uid, ev_type, title, msg, ent_type, ent_id in demo_notifs:
            cur.execute("SELECT id FROM notifications WHERE recipient_user_id = ? AND title = ?", (uid, title))
            if not cur.fetchone():
                cur.execute('''
                INSERT INTO notifications (recipient_user_id, event_type, title, message, entity_type, entity_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (uid, ev_type, title, msg, ent_type, ent_id))

        # 15. Seed isolated, fully usable demo resources for every approved NGO.
        # These are persisted starter records; all subsequent changes run through API/DB workflows.
        for org in cur.execute("SELECT id,name,contact_name,contact_email FROM organizations WHERE organization_type='NGO' AND status='Approved' ORDER BY id").fetchall():
            oid=org['id']
            coordinator=cur.execute("SELECT u.id FROM users u JOIN organization_memberships m ON m.user_id=u.id WHERE m.organization_id=? AND m.membership_role='Coordinator' AND m.status='Active' AND u.role='NGO Coordinator' AND u.status='ACTIVE' ORDER BY u.id LIMIT 1",(oid,)).fetchone()
            if not coordinator:
                coord_email=org['contact_email'].lower()
                user=cur.execute("SELECT u.id FROM users u JOIN organization_memberships m ON m.user_id=u.id WHERE u.role='NGO Coordinator' AND m.organization_id=? AND m.membership_role='Coordinator' AND m.status='Active' ORDER BY u.id LIMIT 1",(oid,)).fetchone()
                if not user:
                    name=org['contact_name'] or org['name']+' Coordinator'; initials=''.join(p[0].upper() for p in name.split() if p)[:2] or 'NC'
                    cur.execute("INSERT INTO users(email,password,name,initials,role,status,organization_id) VALUES(?,?,?,?,'NGO Coordinator','ACTIVE',?)",(coord_email,generate_password_hash('ngo123'),name,initials,oid)); cuid=cur.lastrowid
                else: cuid=user['id']  # Preserve an existing user's status and organization assignment.
                cur.execute("INSERT OR IGNORE INTO organization_memberships(organization_id,user_id,membership_role,status) VALUES(?,?,'Coordinator','Active')",(oid,cuid)); coordinator={'id':cuid}
            cuid=coordinator['id']
            wh_code=f'WH-NGO-{oid:03d}'
            wh=cur.execute("SELECT id,owner_type,owner_organization_id FROM warehouses WHERE code=?",(wh_code,)).fetchone()
            if wh and (wh['owner_type']!='ngo' or wh['owner_organization_id']!=oid):
                wh_code=f'{wh_code}-DEMO'
                wh=cur.execute("SELECT id,owner_type,owner_organization_id FROM warehouses WHERE code=?",(wh_code,)).fetchone()
            if not wh:
                cur.execute("INSERT INTO warehouses(code,name,district,address,status,manager_user_id,owner_type,owner_organization_id) VALUES(?,?,? ,?,'Active',?,'ngo',?)",(wh_code,org['name']+' Relief Warehouse','Demo District',org['name']+' Logistics Yard',cuid,oid)); whid=cur.lastrowid
            else:
                whid=wh['id']  # Existing ownership and manager fields are preserved.
            for resource in cur.execute("SELECT id,name FROM resources WHERE is_active=1 ORDER BY id").fetchall():
                cur.execute("INSERT OR IGNORE INTO warehouse_stock(warehouse_id,resource_id,on_hand_units,reserved_units,target_stock,status) VALUES(?,?,120,0,150,'Safe')",(whid,resource['id']))
            for code,vehicle_type,capacity in ((f'NGO{oid:03d}-AMB-01','Ambulance',24),(f'NGO{oid:03d}-CARGO-01','Cargo Truck',160),(f'NGO{oid:03d}-RESCUE-01','Rescue Unit',36)):
                existing_vehicle=cur.execute("SELECT owner_type,owner_organization_id FROM vehicles WHERE vehicle_code=?",(code,)).fetchone()
                if existing_vehicle and (existing_vehicle['owner_type']!='ngo' or existing_vehicle['owner_organization_id']!=oid):
                    code=f'{code}-DEMO'
                cur.execute("INSERT OR IGNORE INTO vehicles(vehicle_code,vehicle_type,capacity_units,capacity_description,warehouse_id,status,owner_type,owner_organization_id) VALUES(?,?,?,? ,?,'Available','ngo',?)",(code,vehicle_type,capacity,f'{org["name"]} registered {vehicle_type.lower()}',whid,oid))
            for n in (1,2):
                driver=cur.execute("SELECT u.id FROM users u JOIN ngo_personnel_approvals a ON a.user_id=u.id WHERE u.role='Driver' AND a.organization_id=? AND a.personnel_type='Driver' AND a.decision='Approved' ORDER BY u.id LIMIT 1 OFFSET ?",(oid,n-1)).fetchone()
                if not driver:
                    driver_name=demo_identities.human_name(1000 + oid * 10 + n)
                    driver_email=demo_identities.canonical_email(driver_name, f"ngo_{demo_identities.ORG[oid]}_driver")
                    initials=''.join(x[0].upper() for x in driver_name.split() if x)[:2]
                    cur.execute("INSERT INTO users(email,password,name,initials,role,status,organization_id) VALUES(?,?,?,?,'Driver','ACTIVE',?)",(driver_email,generate_password_hash('driver123'),driver_name,initials,oid)); duid=cur.lastrowid
                else: duid=driver['id']  # Never reactivate or reassign a pre-existing account during seeding.
                cur.execute("INSERT OR IGNORE INTO organization_memberships(organization_id,user_id,membership_role,status) VALUES(?,?,'Driver','Active')",(oid,duid))
                cur.execute("INSERT OR IGNORE INTO ngo_personnel_approvals(user_id,organization_id,personnel_type,decision,decided_by_user_id,reason) VALUES(?,?,'Driver','Approved',?,'Seeded approved demo driver')",(duid,oid,cuid))
                vu=cur.execute("SELECT u.id FROM users u JOIN ngo_personnel_approvals a ON a.user_id=u.id WHERE u.role='Volunteer' AND a.organization_id=? AND a.personnel_type='Volunteer' AND a.decision='Approved' ORDER BY u.id LIMIT 1 OFFSET ?",(oid,n-1)).fetchone()
                if not vu:
                    volunteer_name=demo_identities.human_name(1100 + oid * 10 + n)
                    volunteer_email=demo_identities.canonical_email(volunteer_name, f"ngo_{demo_identities.ORG[oid]}_volunteer")
                    initials=''.join(x[0].upper() for x in volunteer_name.split() if x)[:2]
                    cur.execute("INSERT INTO users(email,password,name,initials,role,status,organization_id) VALUES(?,?,?,?,'Volunteer','ACTIVE',?)",(volunteer_email,generate_password_hash('volunteer123'),volunteer_name,initials,oid)); vuid=cur.lastrowid
                else: vuid=vu['id']  # Never reactivate or reassign a pre-existing account during seeding.
                cur.execute("INSERT OR IGNORE INTO organization_memberships(organization_id,user_id,membership_role,status) VALUES(?,?,'Volunteer','Active')",(oid,vuid))
                cur.execute("INSERT OR IGNORE INTO ngo_personnel_approvals(user_id,organization_id,personnel_type,decision,decided_by_user_id,reason) VALUES(?,?,'Volunteer','Approved',?,'Seeded approved demo volunteer')",(vuid,oid,cuid))
                if not cur.execute("SELECT 1 FROM volunteers WHERE user_id=?",(vuid,)).fetchone():
                    cur.execute("INSERT INTO volunteers(initials,name,skill,zone,status,user_id,organization_id,verified,owner_type) VALUES(?,?,?,'Demo Coverage Zone','Available',?,?,1,'ngo')",(initials,volunteer_name,'General Response',vuid,oid))
            shelter_name=org['name']+' Relief Shelter'
            if not cur.execute("SELECT 1 FROM shelters WHERE name=? AND owner_type='ngo' AND owner_organization_id=?",(shelter_name,oid)).fetchone():
                cur.execute("INSERT INTO shelters(name,occupants,capacity,status,owner_type,owner_organization_id,created_by_user_id) VALUES(?,0,120,'Operational','ngo',?,?)",(shelter_name,oid,cuid))

        # Reconcile the named demo donations into their correct ownership and ledgers.
        # This is scoped to these fixed demo IDs and is safe to repeat.
        for donation_id, org_id in (('DON-2026-001', None), ('DON-2026-002', 1), ('DON-2026-003', 2)):
            if org_id is None:
                warehouse=cur.execute("SELECT id FROM warehouses WHERE owner_type='government' AND owner_organization_id IS NULL ORDER BY id LIMIT 1").fetchone()
            else:
                warehouse=cur.execute("SELECT id FROM warehouses WHERE owner_type='ngo' AND owner_organization_id=? ORDER BY id LIMIT 1",(org_id,)).fetchone()
            if warehouse:
                cur.execute("UPDATE donations SET organization_id=?, destination_warehouse_id=? WHERE id=?", (org_id, warehouse['id'], donation_id))
        cash = cur.execute("SELECT * FROM donations WHERE id='DON-2026-001' AND status IN ('Accepted','Partially Accepted')").fetchone()
        if cash and cash['declared_amount_paise'] and not cur.execute("SELECT 1 FROM fund_transactions WHERE id='TX-DON-DON-2026-001'").fetchone():
            cur.execute("""INSERT INTO fund_transactions(id,incident_id,organization_id,transaction_type,amount_paise,currency,reference_code,status,performed_by_user_id,approved_by_user_id,receipt_reference,reason,occurred_at)
                VALUES('TX-DON-DON-2026-001',?,NULL,'DonationReceived',?,'INR','REF-CC-8821','Completed',?,?,?,'Verified demo cash donation',CURRENT_TIMESTAMP)""",
                (cash['incident_id'], cash['declared_amount_paise'], official_id, official_id, cash['reference_code']))
        accepted_items = cur.execute("SELECT di.resource_id,di.quantity_accepted FROM donation_items di WHERE di.donation_id='DON-2026-002' AND di.quantity_accepted>0").fetchall()
        for item in accepted_items:
            stock = cur.execute("SELECT id FROM warehouse_stock WHERE warehouse_id=3 AND resource_id=?", (item['resource_id'],)).fetchone()
            if stock and not cur.execute("SELECT 1 FROM inventory_transactions WHERE reference_type='donations' AND reference_id='DON-2026-002' AND warehouse_stock_id=? AND transaction_type='DonationReceived'", (stock['id'],)).fetchone():
                cur.execute("UPDATE warehouse_stock SET on_hand_units=on_hand_units+?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (item['quantity_accepted'], stock['id']))
                cur.execute("INSERT INTO inventory_transactions(warehouse_stock_id,transaction_type,quantity_units,direction,reference_type,reference_id,reason,performed_by_user_id) VALUES(?,'DonationReceived',?,'IN','donations','DON-2026-002','Accepted demo donation receipt',?)", (stock['id'],item['quantity_accepted'],official_id))
        for stock in cur.execute("SELECT id,on_hand_units,reserved_units,target_stock FROM warehouse_stock").fetchall():
            available=max(0,stock['on_hand_units']-stock['reserved_units'])
            cur.execute("UPDATE warehouse_stock SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (database.calc_inventory_status(available,stock['target_stock']),stock['id']))

        demo_request_id='REQ-DEMO-GOV-001'
        if not cur.execute("SELECT 1 FROM emergency_requests WHERE id=?",(demo_request_id,)).fetchone():
            cur.execute("""INSERT INTO emergency_requests(id,requester_name,area,address,need,people_affected,vulnerable_people,priority_score,status,time_str,lat,lng,requester_user_id,incident_id,zone_id,description,verification_status)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (demo_request_id,'Ramesh Kumar','Dhaliwal Colony — Ward 4','Ward 4 Municipal Sector, Demo District','Drinking water and food ration kits',18,1,92,'Awaiting allocation',datetime.now().strftime('%Y-%m-%d %H:%M'),30.9125,75.8340,citizen_id,'INC-2026-FLOOD','Z-01','Flood-affected households need potable water and family ration kits.','Unverified'))
            cur.execute("INSERT INTO request_items(request_id,resource_id,quantity_requested,notes) VALUES(?,1,36,'Government allocation queue demo need'),(?,2,18,'Government allocation queue demo need')",(demo_request_id,demo_request_id))

        # 15. Initial Audit Log entries
        cur.execute("SELECT COUNT(*) FROM audit_logs")
        if cur.fetchone()[0] == 0:
            cur.execute('''
            INSERT INTO audit_logs (actor_user_id, action, entity_type, entity_id, new_state_json, reason, request_id)
            VALUES (?, 'ACTIVATE_INCIDENT', 'incidents', 'INC-2026-FLOOD', '{"status":"Active"}', 'Declared emergency response protocol', 'SYS-INIT-01'),
                   (?, 'APPROVE_ADOPTION', 'zone_adoptions', 'Z-02', '{"organization_id":1,"status":"Approved"}', 'NGO coverage authorization', 'SYS-INIT-02')
            ''', (official_id, official_id))

    demo_expansion.expand_demo_data(conn)
    demo_identities.normalize_demo_identities(conn)
    # A second pass reconciles any role or organization defaults supplied by
    # the application's baseline initializer before finalizing the demo roster.
    demo_expansion.expand_demo_data(conn)
    demo_identities.normalize_demo_identities(conn)
    showcase_seed.seed_showcase_data(conn)
    # Showcase workflow records are created after the expansion pass; finish
    # registration backfill once every seed dependency has run.
    conn.execute("""UPDATE vehicles SET registration_number=
        CASE WHEN owner_type='government' THEN 'PB10GV'
             WHEN owner_organization_id=1 THEN 'PB11PR'
             WHEN owner_organization_id=2 THEN 'PB12KA'
             WHEN owner_organization_id=3 THEN 'PB13RC'
             ELSE 'PB99UN' END || printf('%04d',id)
        WHERE registration_number IS NULL OR trim(registration_number)=''""")
    conn.commit()
    packaged_db=os.path.abspath(os.path.join(os.path.dirname(__file__),'drras.db'))
    if os.path.abspath(database.get_db_path()) == packaged_db:
        showcase_seed.write_reports(conn)
        demo_expansion._write_credentials(conn)
        write_demo_validation_report(conn)
    conn.close()
    print("DRRAS Demo Scenario data seeded successfully.")

def write_demo_validation_report(conn):
    roles, gov_drivers, gov_volunteers, ngo = demo_expansion.validation_report(conn)
    lines=['# Expanded demo seed validation report','','Generated from the packaged SQLite database by `seed_demo.py`. All counts are read from persisted records.','', '## Active accounts by role','', '| Role | Count |','|---|---:|']
    lines += [f'| {role} | {count} |' for role,count in sorted(roles.items())]
    ngod=sum(c['Drivers'] for _,c in ngo); ngov=sum(c['Volunteers'] for _,c in ngo)
    ngodfree=sum(c['DriversAvailable'] for _,c in ngo); ngovfree=sum(c['VolunteersAvailable'] for _,c in ngo)
    lines += ['', '## Availability (derived from persisted active assignments/tasks)','', '| Category | Approved total | Available | Busy |','|---|---:|---:|---:|',f"| Government Drivers | {gov_drivers['total'] or 0} | {gov_drivers['available'] or 0} | {(gov_drivers['total'] or 0)-(gov_drivers['available'] or 0)} |",f"| Government Responders / Volunteers | {gov_volunteers['total'] or 0} | {gov_volunteers['available'] or 0} | {(gov_volunteers['total'] or 0)-(gov_volunteers['available'] or 0)} |",f'| NGO Drivers | {ngod} | {ngodfree} | {ngod-ngodfree} |',f'| NGO Volunteers | {ngov} | {ngovfree} | {ngov-ngovfree} |']
    lines += ['', '## NGO personnel distribution','', '| NGO | Approved Drivers | Available Drivers | Approved Volunteers | Available Volunteers |','|---|---:|---:|---:|---:|']
    lines += [f'| {demo_expansion.ORG_NAMES[oid]} | {counts["Drivers"]} | {counts["DriversAvailable"]} | {counts["Volunteers"]} | {counts["VolunteersAvailable"]} |' for oid,counts in ngo]
    lines += ['', '## Vehicle fleet and stock','', '| Owner | Vehicles | Genuinely available | Busy / unavailable | Cargo trucks (250+ units) | Ambulances | Rescue units | Relief vans | Usable stock units |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for owner,oid,label in [('government',None,'Government'),('ngo',1,demo_expansion.ORG_NAMES[1]),('ngo',2,demo_expansion.ORG_NAMES[2]),('ngo',3,demo_expansion.ORG_NAMES[3])]:
        fleet=conn.execute("""SELECT COUNT(*) total,
            SUM(CASE WHEN v.status='Available' AND v.current_driver_user_id IS NULL
              AND NOT EXISTS(SELECT 1 FROM dispatches d WHERE d.vehicle_id=v.id AND d.status IN ('Loading','Ready','En route','Arrived','Delivered Pending Proof','Delivered Pending Confirmation','Needs Review','Proof Rejected'))
              AND NOT EXISTS(SELECT 1 FROM response_assignments a WHERE a.vehicle_id=v.id AND a.status IN ('Assigned','Active')) THEN 1 ELSE 0 END) available,
            SUM(CASE WHEN v.vehicle_type='Cargo Truck' AND v.capacity_units>=250 THEN 1 ELSE 0 END) cargo,
            SUM(CASE WHEN v.vehicle_type='Ambulance' THEN 1 ELSE 0 END) ambulances,
            SUM(CASE WHEN v.vehicle_type='Rescue Unit' THEN 1 ELSE 0 END) rescue,
            SUM(CASE WHEN v.vehicle_type='Relief Van' THEN 1 ELSE 0 END) vans
            FROM vehicles v WHERE v.owner_type=? AND v.owner_organization_id IS ?""",(owner,oid)).fetchone()
        stock=conn.execute("SELECT COALESCE(SUM(on_hand_units-reserved_units),0) FROM warehouse_stock s JOIN warehouses w ON w.id=s.warehouse_id WHERE w.owner_type=? AND w.owner_organization_id IS ? AND w.status='Active'",(owner,oid)).fetchone()[0]
        lines.append(f'| {label} | {fleet["total"] or 0} | {fleet["available"] or 0} | {(fleet["total"] or 0)-(fleet["available"] or 0)} | {fleet["cargo"] or 0} | {fleet["ambulances"] or 0} | {fleet["rescue"] or 0} | {fleet["vans"] or 0} | {stock} |')
    missing=conn.execute("SELECT COUNT(*) FROM vehicles WHERE registration_number IS NULL OR trim(registration_number)=''").fetchone()[0]
    duplicates=conn.execute("SELECT COUNT(*) FROM (SELECT registration_number FROM vehicles WHERE registration_number IS NOT NULL GROUP BY registration_number HAVING COUNT(*)>1)").fetchone()[0]
    lines += ['', '## Vehicle data integrity', '', f'- Vehicles missing registration numbers: **{missing}**.', f'- Duplicate registration numbers: **{duplicates}**.', '- Vehicle availability is calculated from persisted status, driver reservation, active dispatches and active response assignments.', '', '## Automated workflow validation', '', 'Run `python -m pytest -q` to record the current test result. The seed process does not claim that application workflow tests have passed.','']
    with open(os.path.join(os.path.dirname(__file__),'docs','DEMO_VALIDATION_REPORT.md'),'w',encoding='utf-8') as f: f.write('\n'.join(lines))

if __name__ == '__main__':
    seed_demo_data()
