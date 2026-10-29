import sqlite3
import os
import json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import migrations
import demo_identities

def log_system_event(conn, event_type, payload=None):
    """
    Authoritatively persists an event to system_events table in SQLite
    for Server-Sent Events (SSE) and polling synchronization across clients.
    """
    payload_str = json.dumps(payload or {}) if not isinstance(payload, str) else payload
    conn.execute(
        "INSERT INTO system_events (event_type, payload) VALUES (?, ?)",
        (event_type, payload_str)
    )

def log_audit_event(conn, actor_user_id, action, entity_type, entity_id=None, old_state=None, new_state=None, reason=None, request_id=None, ip_summary=None):
    """
    Append-only persistent audit trail matching enterprise compliance requirements.
    """
    old_json = json.dumps(old_state) if old_state is not None and not isinstance(old_state, str) else old_state
    new_json = json.dumps(new_state) if new_state is not None and not isinstance(new_state, str) else new_state
    conn.execute('''
        INSERT INTO audit_logs (actor_user_id, action, entity_type, entity_id, old_state_json, new_state_json, reason, request_id, ip_summary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (actor_user_id, action, entity_type, str(entity_id) if entity_id is not None else None, old_json, new_json, reason, request_id, ip_summary))

def create_notification(conn, recipient_user_id, event_type, title, message, entity_type=None, entity_id=None):
    """
    Creates an in-app notification for a designated user.
    """
    conn.execute('''
        INSERT INTO notifications (recipient_user_id, event_type, title, message, entity_type, entity_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (recipient_user_id, event_type, title, message, entity_type, str(entity_id) if entity_id is not None else None))

def get_db_path():
    return os.environ.get('DRRAS_DB_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'drras.db'))

def get_db():
    conn = sqlite3.connect(get_db_path(), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
    except Exception:
        pass
    return conn

def verify_password(stored_password, provided_password):
    """
    Verifies a password against a hash or plaintext (for legacy migration).
    Returns (is_valid, needs_rehash).
    """
    if not stored_password or not provided_password:
        return False, False
    
    if stored_password.startswith(('scrypt:', 'pbkdf2:sha256:')):
        return check_password_hash(stored_password, provided_password), False
    else:
        # Legacy plain-text check with migration flag
        if stored_password == provided_password:
            return True, True
        return False, False

def calc_priority(people_affected, vulnerable_people, need):
    """
    Automated Urgency Priority Algorithm matching DRRAS specification:
    Base (58)
    + Vulnerable Group Bonus (25 if True)
    + Population Weight (10 if people > 8)
    + Medical / Rescue weight (10 if need contains medical or rescue)
    Capped at 99. Minimum is 58.
    """
    score = 58
    if isinstance(vulnerable_people, str):
        vulnerable_clean = vulnerable_people.strip().lower()
    else:
        vulnerable_clean = vulnerable_people

    if vulnerable_clean in (True, 'yes', 'true', '1', 1):
        score += 25

    try:
        if people_affected is not None and not isinstance(people_affected, bool):
            if int(people_affected) > 8:
                score += 10
    except (ValueError, TypeError):
        pass

    need_str = (need or "").lower()
    if "medical" in need_str or "rescue" in need_str:
        score += 10

    return max(58, min(99, score))

def calc_inventory_status(available, target):
    """
    Calculates inventory stock health status:
    - Critical: < 35% of target stock
    - Low: < 100% of target stock
    - Safe: >= 100% of target stock
    """
    try:
        avail = int(available)
        tgt = int(target)
        if tgt <= 0 or avail < tgt * 0.35:
            return 'Critical'
        elif avail < tgt:
            return 'Low'
        return 'Safe'
    except (ValueError, TypeError):
        return 'Critical'

def init_db():
    conn = get_db()
    # Apply versioned database migrations
    migrations.apply_migrations(conn)
    cur = conn.cursor()

    # 1. Users Table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL COLLATE NOCASE,
        password TEXT NOT NULL,
        name TEXT NOT NULL,
        initials TEXT NOT NULL,
        role TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 2. Emergency Requests Table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS emergency_requests (
        id TEXT PRIMARY KEY,
        requester_name TEXT NOT NULL,
        area TEXT NOT NULL,
        address TEXT NOT NULL,
        need TEXT NOT NULL,
        people_affected INTEGER NOT NULL CHECK(people_affected > 0 AND people_affected <= 100000),
        vulnerable_people BOOLEAN NOT NULL DEFAULT 0,
        priority_score INTEGER NOT NULL CHECK(priority_score >= 1 AND priority_score <= 100),
        status TEXT NOT NULL DEFAULT 'Awaiting allocation',
        time_str TEXT,
        lat REAL DEFAULT 30.9009 CHECK(lat >= -90.0 AND lat <= 90.0),
        lng REAL DEFAULT 75.8573 CHECK(lng >= -180.0 AND lng <= 180.0),
        map_left REAL DEFAULT 50,
        map_top REAL DEFAULT 50,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 3. Inventory Stock Table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        resource_name TEXT UNIQUE NOT NULL COLLATE NOCASE,
        available_units INTEGER NOT NULL CHECK(available_units >= 0),
        target_stock INTEGER NOT NULL CHECK(target_stock > 0),
        warehouse_name TEXT NOT NULL DEFAULT 'Central Relief',
        status TEXT NOT NULL
    )
    ''')

    # 4. Volunteers Table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS volunteers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        initials TEXT NOT NULL,
        name TEXT NOT NULL,
        skill TEXT NOT NULL,
        zone TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Available'
    )
    ''')

    # 5. Dispatches Table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS dispatches (
        id TEXT PRIMARY KEY,
        vehicle TEXT NOT NULL,
        driver TEXT NOT NULL,
        destination TEXT NOT NULL,
        load_items TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Loading',
        eta TEXT NOT NULL,
        request_id TEXT,
        FOREIGN KEY (request_id) REFERENCES emergency_requests(id) ON DELETE SET NULL
    )
    ''')

    # 6. Shelters Table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS shelters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        occupants INTEGER NOT NULL CHECK(occupants >= 0),
        capacity INTEGER NOT NULL CHECK(capacity > 0),
        status TEXT NOT NULL
    )
    ''')

    # 7. Funds Table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS funds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        percentage INTEGER NOT NULL CHECK(percentage >= 0 AND percentage <= 100),
        color TEXT NOT NULL
    )
    ''')

    # 8. Activity / Workspace Logs
    cur.execute('''
    CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workspace_key TEXT NOT NULL,
        title TEXT NOT NULL,
        details TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 9. Real-Time System Events Table (Persistent SSE / Polling log)
    cur.execute('''
    CREATE TABLE IF NOT EXISTS system_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        payload TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Indexes for high performance and integrity
    cur.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_requests_priority ON emergency_requests(priority_score DESC);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_requests_status ON emergency_requests(status);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_dispatches_driver ON dispatches(driver);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_activities_key ON activities(workspace_key);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_system_events_id ON system_events(id);')

    # Seed Users if not present
    demo_users = [
        ('admin@drras.in', generate_password_hash('admin123'), 'Admin Mahajan', 'AM', 'Administrator', 'ACTIVE'),
        ('official@drras.in', generate_password_hash('official123'), 'Ananya Singh', 'AS', 'Government Official', 'ACTIVE'),
        ('ngo@drras.in', generate_password_hash('ngo123'), 'Neha Kapoor', 'NK', 'NGO Coordinator', 'ACTIVE'),
        ('volunteer@drras.in', generate_password_hash('volunteer123'), 'Vikram Kaur', 'VK', 'Volunteer', 'ACTIVE'),
        ('citizen@drras.in', generate_password_hash('citizen123'), 'Ramesh Kumar', 'RK', 'Citizen', 'ACTIVE'),
        ('driver@drras.in', generate_password_hash('driver123'), 'Arjun Mehta', 'AR', 'Driver', 'ACTIVE')
    ]
    for email, pwd_hash, name, inits, role, st in demo_users:
        cur.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email.lower(),))
        existing_email=cur.fetchone()
        existing_role=cur.execute("SELECT id FROM users WHERE role=? AND status='ACTIVE' LIMIT 1",(role,)).fetchone()
        if not existing_email and not existing_role:
            cur.execute('''
            INSERT INTO users (email, password, name, initials, role, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (email, pwd_hash, name, inits, role, st))

        # Check and upgrade legacy plaintext passwords for demo users if any exist
        existing_users = cur.execute('SELECT id, password FROM users').fetchall()
        for u in existing_users:
            pwd = u['password']
            if not pwd.startswith(('scrypt:', 'pbkdf2:sha256:')):
                hashed = generate_password_hash(pwd)
                cur.execute('UPDATE users SET password = ? WHERE id = ?', (hashed, u['id']))

    # Seed Emergency Requests if empty
    cur.execute('SELECT COUNT(*) FROM emergency_requests')
    if cur.fetchone()[0] == 0:
        requests = [
            ('REQ-2048', 'Ramesh Kumar', 'Dhaliwal Colony', 'Dhaliwal Colony, Ward 4', 'Medical kit & drinking water', 6, 1, 96, 'Awaiting allocation', '8 min ago', 30.9125, 75.8340, 72, 49),
            ('REQ-2047', 'Sonia Devi', 'Focal Point, Ward 8', 'Focal Point Industrial Area, Ward 8', 'Shelter & food ration', 14, 1, 88, 'Allocated', '21 min ago', 30.8950, 75.8750, 54, 37),
            ('REQ-2046', 'Gurpreet Singh', 'Riverbank Village', 'Old Riverside Road near Sutlej', 'Rescue support', 3, 0, 82, 'Dispatched', '43 min ago', 30.9350, 75.8150, 40, 62),
            ('REQ-2045', 'Asha Sharma', 'Model Town', 'House 412, Block C, Model Town', 'Baby food & blankets', 4, 0, 74, 'Delivered', '1 hr ago', 30.8810, 75.8450, 70, 74)
        ]
        cur.executemany('''
        INSERT INTO emergency_requests (id, requester_name, area, address, need, people_affected, vulnerable_people, priority_score, status, time_str, lat, lng, map_left, map_top)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', requests)

    # Seed Inventory if empty
    cur.execute('SELECT COUNT(*) FROM inventory')
    if cur.fetchone()[0] == 0:
        raw_stock = [
            ('Drinking Water', 4820, 8000, 'Central Relief'),
            ('Food Ration Kits', 1186, 2000, 'Central Relief'),
            ('Medical Kits', 312, 500, 'Central Relief'),
            ('Blankets', 2940, 2500, 'Central Relief'),
            ('Shelter Tents', 76, 150, 'Central Relief')
        ]
        stock = [
            (name, avail, target, wh, calc_inventory_status(avail, target))
            for name, avail, target, wh in raw_stock
        ]
        cur.executemany('''
        INSERT INTO inventory (resource_name, available_units, target_stock, warehouse_name, status)
        VALUES (?, ?, ?, ?, ?)
        ''', stock)

        # Ensure default warehouse exists
        cur.execute("SELECT id FROM warehouses WHERE code = 'WH-CENTRAL'")
        wh_row = cur.fetchone()
        if not wh_row:
            cur.execute("INSERT INTO warehouses (code, name, district, address, status) VALUES ('WH-CENTRAL', 'Central Relief Depot', 'Demo District', 'Station Road, Sector 3', 'Active')")
            wh_id = cur.lastrowid
        else:
            wh_id = wh_row[0]

        # Seed canonical resources and warehouse_stock
        for idx, (name, avail, target, wh, st) in enumerate(stock, start=1):
            cur.execute("SELECT id FROM resources WHERE LOWER(name) = ?", (name.lower(),))
            res_row = cur.fetchone()
            if not res_row:
                cat = 'General'
                unit = 'units'
                n_low = name.lower()
                if 'water' in n_low: cat = 'Water & Sanitation'; unit = 'litres'
                elif 'food' in n_low or 'ration' in n_low: cat = 'Food Supplies'; unit = 'kits'
                elif 'medical' in n_low: cat = 'Medical'; unit = 'kits'
                elif 'blanket' in n_low: cat = 'Shelter & Warmth'; unit = 'pieces'
                elif 'tent' in n_low: cat = 'Shelter & Warmth'; unit = 'tents'
                cur.execute("INSERT INTO resources (id, sku, name, category, unit, is_active) VALUES (?, ?, ?, ?, ?, 1)", (idx, f"RES-{idx:03d}", name, cat, unit))
                res_id = idx
            else:
                res_id = res_row[0]

            cur.execute("SELECT id FROM warehouse_stock WHERE warehouse_id = ? AND resource_id = ?", (wh_id, res_id))
            if not cur.fetchone():
                cur.execute("INSERT INTO warehouse_stock (warehouse_id, resource_id, on_hand_units, reserved_units, target_stock, status) VALUES (?, ?, ?, 0, ?, ?)",
                            (wh_id, res_id, avail, target, st))

    # Seed Volunteers if empty
    cur.execute('SELECT COUNT(*) FROM volunteers')
    if cur.fetchone()[0] == 0:
        vols = [
            ('VK', 'Vikram Kaur', 'Medical First Aid', 'Focal Point', 'On task'),
            ('AS', 'Aman Sharma', 'Logistics', 'Central Warehouse', 'Available'),
            ('RD', 'Riya Das', 'Search & Rescue', 'Riverbank', 'On task'),
            ('MS', 'Manpreet Singh', 'Food Distribution', 'Model Town', 'Available')
        ]
        cur.executemany('''
        INSERT INTO volunteers (initials, name, skill, zone, status)
        VALUES (?, ?, ?, ?, ?)
        ''', vols)

    # Seed Dispatches if empty
    cur.execute('SELECT COUNT(*) FROM dispatches')
    if cur.fetchone()[0] == 0:
        disps = [
            ('DSP-12', 'V-12 · Relief Van', 'Arjun Mehta', 'Riverbank Village', 'Medical kits, water', 'En route', '18 min', 'REQ-2048'),
            ('DSP-04', 'V-04 · Cargo Truck', 'Simran Kaur', 'Ward 8', 'Food ration kits', 'Loading', '35 min', 'REQ-2047'),
            ('DSP-18', 'V-18 · Ambulance', 'Karan Gill', 'Focal Point', 'Medical team', 'Delivered', 'Completed', 'REQ-2046')
        ]
        cur.executemany('''
        INSERT INTO dispatches (id, vehicle, driver, destination, load_items, status, eta, request_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', disps)

    # Seed Shelters if empty
    cur.execute('SELECT COUNT(*) FROM shelters')
    if cur.fetchone()[0] == 0:
        shelters_data = [
            ('Govt. School, Ward 8', 184, 250, 'Operational'),
            ('Community Hall, Model Town', 92, 120, 'Near capacity'),
            ('Sports Complex Shelter', 308, 500, 'Operational')
        ]
        cur.executemany('''
        INSERT INTO shelters (name, occupants, capacity, status)
        VALUES (?, ?, ?, ?)
        ''', shelters_data)

    # Seed Funds if empty
    cur.execute('SELECT COUNT(*) FROM funds')
    if cur.fetchone()[0] == 0:
        funds_data = [
            ('Food', 34, '#ef6542'),
            ('Medical', 26, '#2457d6'),
            ('Transport', 22, '#f4a23b'),
            ('Shelter', 18, '#28a780')
        ]
        cur.executemany('''
        INSERT INTO funds (category, percentage, color)
        VALUES (?, ?, ?)
        ''', funds_data)

    # The seeded Government Official is also a real roster entry for response verification.
    # The identity remains the existing account; options are read from this database row.
    if conn.execute("SELECT 1 FROM pragma_table_info('government_personnel') WHERE name='user_id'").fetchone():
        official=conn.execute("SELECT id,name FROM users WHERE LOWER(email)='official@drras.in' AND role='Government Official' AND status='ACTIVE'").fetchone()
        if official and not conn.execute("SELECT 1 FROM government_personnel WHERE user_id=? AND status='Active'",(official['id'],)).fetchone():
            conn.execute("INSERT INTO government_personnel(name,category,service_unit,skills,status,user_id,created_by_user_id,approved_by_user_id,approved_at) VALUES(?,?,?,?, 'Active',?,?,?,CURRENT_TIMESTAMP)",(official['name'],'Government Operations Officer','District Disaster Management Authority','Incident coordination, field response',official['id'],official['id'],official['id']))
    # Seed enough scoped Government response staff for concurrent demo scenarios.
    if conn.execute("SELECT 1 FROM pragma_table_info('government_personnel') WHERE name='user_id'").fetchone():
        admin=conn.execute("SELECT id FROM users WHERE role='Administrator' ORDER BY id LIMIT 1").fetchone()
        if admin:
            government_responders=(('Demo Government Medical Responder','Doctor / Paramedic','District Medical Unit','Medical, first aid'),('Demo Government Rescue Officer','Search and Rescue','District Rescue Unit','Water rescue, evacuation'),('Demo Government Fire Officer','Firefighter','District Fire Service','Fire response, rescue'))
            for name,category,unit,skills in government_responders:
                if not conn.execute("SELECT 1 FROM government_personnel WHERE name=?",(name,)).fetchone():
                    conn.execute("INSERT INTO government_personnel(name,category,service_unit,skills,status,created_by_user_id,approved_by_user_id,approved_at) VALUES(?,?,?,?,'Active',?,?,CURRENT_TIMESTAMP)",(name,category,unit,skills,admin['id'],admin['id']))
    # Reconcile demo-account organization links after legacy seed users exist.
    # Migrations run before the legacy seed block, so membership repair belongs here too.
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='organization_memberships'").fetchone():
        conn.execute("""INSERT OR IGNORE INTO organization_memberships (organization_id,user_id,membership_role,status)
            SELECT o.id,u.id,'Coordinator','Active' FROM users u JOIN organizations o
              ON o.id=1 AND o.organization_type='NGO' AND o.status='Approved'
            WHERE u.role='NGO Coordinator' AND u.status='ACTIVE'
              AND NOT EXISTS(SELECT 1 FROM organization_memberships m WHERE m.user_id=u.id AND m.membership_role='Coordinator' AND m.status='Active')
            ORDER BY u.id LIMIT 1""")
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='owner_type' LIMIT 1").fetchone() is not None:
        pass
    if conn.execute("SELECT 1 FROM pragma_table_info('shelters') WHERE name='owner_type'").fetchone():
        conn.execute("UPDATE shelters SET owner_type='government' WHERE owner_type='unassigned' AND LOWER(name) LIKE 'govt.%'")
        conn.execute("UPDATE shelters SET owner_type='government',owner_organization_id=NULL WHERE name IN ('Govt. School, Ward 8','Community Hall, Model Town','Sports Complex Shelter') AND owner_type='unassigned'")
    # Owner-scoped personnel links are managed by the idempotent demo seed;
    # never recreate legacy-email accounts here after their canonical rename.
    # One approved Government Volunteer/Responder demo account, independent of any NGO.
    responder=conn.execute("SELECT u.id,u.role,u.organization_id,u.status FROM users u JOIN government_personnel p ON p.user_id=u.id WHERE u.role='Volunteer' AND u.organization_id IS NULL AND u.status='ACTIVE' AND p.status='Active' ORDER BY u.id LIMIT 1").fetchone()
    admin=conn.execute("SELECT id FROM users WHERE role='Administrator' ORDER BY id LIMIT 1").fetchone()
    if responder and responder['role']=='Volunteer' and responder['organization_id'] is None and responder['status']=='ACTIVE' and admin:
        if not conn.execute("SELECT 1 FROM government_personnel WHERE user_id=?",(responder['id'],)).fetchone():
            conn.execute("INSERT INTO government_personnel(name,category,service_unit,skills,status,user_id,created_by_user_id,approved_by_user_id,approved_at) VALUES(?,'Volunteer / First Responder','Government Demo Unit','First aid, welfare checks, emergency distribution','Active',?,?,?,CURRENT_TIMESTAMP)",("Government Demo Responder",responder['id'],admin['id'],admin['id']))
        if not conn.execute("SELECT 1 FROM volunteers WHERE user_id=?",(responder['id'],)).fetchone():
            conn.execute("INSERT INTO volunteers(initials,name,skill,zone,status,user_id,organization_id,verified,owner_type) VALUES('GR','Government Demo Responder','First aid, emergency distribution','Government Demo Coverage','Available',?,NULL,1,'government')",(responder['id'],))

    # Ensure approved demo NGOs each have isolated, usable fleet, personnel and stock.
    # Existing real rows are preserved; deterministic demo identities are inserted idempotently.
    if conn.execute("SELECT 1 FROM pragma_table_info('vehicles') WHERE name='owner_type'").fetchone():
        for org in conn.execute("SELECT id,name,contact_name,contact_email FROM organizations WHERE organization_type='NGO' AND status='Approved' ORDER BY id").fetchall():
            oid=org['id']
            coord=conn.execute("SELECT u.id FROM users u JOIN organization_memberships m ON m.user_id=u.id WHERE m.organization_id=? AND m.membership_role='Coordinator' AND m.status='Active' AND u.role='NGO Coordinator' AND u.status='ACTIVE' LIMIT 1",(oid,)).fetchone()
            if not coord:
                email=(org['contact_email'] or f'demo.coordinator.{oid}@drras.in').lower()
                user=conn.execute("SELECT id,role,status,organization_id FROM users WHERE LOWER(email)=?",(email,)).fetchone()
                if user and user['role']=='NGO Coordinator' and user['status']=='ACTIVE' and user['organization_id']==oid:
                    cuid=user['id']
                else:
                    if user:
                        email=f'demo.coordinator.{oid}@drras.in'
                        suffix=1
                        while conn.execute("SELECT 1 FROM users WHERE LOWER(email)=?",(email,)).fetchone():
                            suffix+=1; email=f'demo.coordinator.{oid}.{suffix}@drras.in'
                    name=org['contact_name'] or org['name']+' Coordinator'; initials=''.join(x[0].upper() for x in name.split() if x)[:2] or 'NC'
                    cur=conn.execute("INSERT INTO users(email,password,name,initials,role,status,organization_id) VALUES(?,?,?,?,'NGO Coordinator','ACTIVE',?)",(email,generate_password_hash('ngo123'),name,initials,oid)); cuid=cur.lastrowid
                conn.execute("INSERT OR IGNORE INTO organization_memberships(organization_id,user_id,membership_role,status) VALUES(?,?,'Coordinator','Active')",(oid,cuid))
            else: cuid=coord['id']
            wh_code=f'WH-NGO-{oid:03d}'; wh=conn.execute("SELECT id,owner_type,owner_organization_id FROM warehouses WHERE code=?",(wh_code,)).fetchone()
            if wh and (wh['owner_type']!='ngo' or wh['owner_organization_id']!=oid):
                wh_code=f'{wh_code}-DEMO'; wh=conn.execute("SELECT id,owner_type,owner_organization_id FROM warehouses WHERE code=?",(wh_code,)).fetchone()
            if not wh:
                cur=conn.execute("INSERT INTO warehouses(code,name,district,address,status,manager_user_id,owner_type,owner_organization_id) VALUES(?,?,? ,?,'Active',?,'ngo',?)",(wh_code,org['name']+' Relief Warehouse','Demo District',org['name']+' Logistics Yard',cuid,oid)); whid=cur.lastrowid
            else: whid=wh['id']  # Existing ownership and manager fields are preserved.
            for res in conn.execute("SELECT id FROM resources WHERE is_active=1").fetchall():
                conn.execute("INSERT OR IGNORE INTO warehouse_stock(warehouse_id,resource_id,on_hand_units,reserved_units,target_stock,status) VALUES(?,?,120,0,150,'Safe')",(whid,res['id']))
            for code,vtype,capacity in ((f'NGO{oid:03d}-AMB-01','Ambulance',24),(f'NGO{oid:03d}-CARGO-01','Cargo Truck',160),(f'NGO{oid:03d}-RESCUE-01','Rescue Unit',36)):
                existing_vehicle=conn.execute("SELECT owner_type,owner_organization_id FROM vehicles WHERE vehicle_code=?",(code,)).fetchone()
                if existing_vehicle and (existing_vehicle['owner_type']!='ngo' or existing_vehicle['owner_organization_id']!=oid): code=f'{code}-DEMO'
                conn.execute("INSERT OR IGNORE INTO vehicles(vehicle_code,vehicle_type,capacity_units,capacity_description,warehouse_id,status,owner_type,owner_organization_id) VALUES(?,?,?, ?,?,'Available','ngo',?)",(code,vtype,capacity,f'{org["name"]} registered {vtype.lower()}',whid,oid))
            for n in (1,2):
                d=conn.execute("SELECT u.id FROM users u JOIN ngo_personnel_approvals a ON a.user_id=u.id WHERE u.role='Driver' AND a.organization_id=? AND a.personnel_type='Driver' AND a.decision='Approved' ORDER BY u.id LIMIT 1 OFFSET ?",(oid,n-1)).fetchone()
                if not d:
                    driver_name=demo_identities.human_name(5000+oid*10+n); driver_email=demo_identities.canonical_email(driver_name,f"ngo_{demo_identities.ORG[oid]}_driver"); initials=''.join(x[0].upper() for x in driver_name.split() if x)[:2]
                    d_id=conn.execute("INSERT INTO users(email,password,name,initials,role,status,organization_id) VALUES(?,?,?,?,'Driver','ACTIVE',?)",(driver_email,generate_password_hash('driver123'),driver_name,initials,oid)).lastrowid
                else: d_id=d['id']
                conn.execute("INSERT OR IGNORE INTO organization_memberships(organization_id,user_id,membership_role,status) VALUES(?,?,'Driver','Active')",(oid,d_id))
                conn.execute("INSERT OR IGNORE INTO ngo_personnel_approvals(user_id,organization_id,personnel_type,decision,decided_by_user_id,reason) VALUES(?,?,'Driver','Approved',?,'Seeded approved demo driver')",(d_id,oid,cuid))
                v=conn.execute("SELECT u.id FROM users u JOIN ngo_personnel_approvals a ON a.user_id=u.id WHERE u.role='Volunteer' AND a.organization_id=? AND a.personnel_type='Volunteer' AND a.decision='Approved' ORDER BY u.id LIMIT 1 OFFSET ?",(oid,n-1)).fetchone()
                if not v:
                    vol_name=demo_identities.human_name(6000+oid*10+n); vol_email=demo_identities.canonical_email(vol_name,f"ngo_{demo_identities.ORG[oid]}_volunteer"); initials=''.join(x[0].upper() for x in vol_name.split() if x)[:2]
                    v_id=conn.execute("INSERT INTO users(email,password,name,initials,role,status,organization_id) VALUES(?,?,?,?,'Volunteer','ACTIVE',?)",(vol_email,generate_password_hash('volunteer123'),vol_name,initials,oid)).lastrowid
                else: v_id=v['id']
                conn.execute("INSERT OR IGNORE INTO organization_memberships(organization_id,user_id,membership_role,status) VALUES(?,?,'Volunteer','Active')",(oid,v_id))
                conn.execute("INSERT OR IGNORE INTO ngo_personnel_approvals(user_id,organization_id,personnel_type,decision,decided_by_user_id,reason) VALUES(?,?,'Volunteer','Approved',?,'Seeded approved demo volunteer')",(v_id,oid,cuid))
                if not conn.execute("SELECT 1 FROM volunteers WHERE user_id=?",(v_id,)).fetchone():
                    conn.execute("INSERT INTO volunteers(initials,name,skill,zone,status,user_id,organization_id,verified,owner_type) VALUES(?,?,?,'Demo Coverage Zone','Available',?,?,1,'ngo')",(initials,vol_name,'General Response',v_id,oid))
            shelter_name=org['name']+' Relief Shelter'
            if not conn.execute("SELECT 1 FROM shelters WHERE name=? AND owner_type='ngo' AND owner_organization_id=?",(shelter_name,oid)).fetchone():
                conn.execute("INSERT INTO shelters(name,occupants,capacity,status,owner_type,owner_organization_id,created_by_user_id) VALUES(?,0,120,'Operational','ngo',?,?)",(shelter_name,oid,cuid))

    conn.execute("""UPDATE vehicles SET registration_number=
        CASE WHEN owner_type='government' THEN 'PB10GV'
             WHEN owner_organization_id=1 THEN 'PB11PR'
             WHEN owner_organization_id=2 THEN 'PB12KA'
             WHEN owner_organization_id=3 THEN 'PB13RC'
             ELSE 'PB99UN' END || printf('%04d',id)
        WHERE registration_number IS NULL OR trim(registration_number)=''""")
    conn.commit()
    demo_identities.normalize_demo_identities(conn)
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("DRRAS SQLite Database initialized successfully.")
