import os
import csv
import io
import re
import json
import time
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, request, jsonify, render_template, Response, session, g, make_response
from werkzeug.security import generate_password_hash
import database
from database import calc_priority, calc_inventory_status, init_db, verify_password, log_system_event, log_audit_event, create_notification
import services
from services import BusinessLogicError
from api_routes import api_bp

app = Flask(__name__, static_folder='static', template_folder='templates')
deployment_environment = (os.environ.get('DRRAS_ENV') or os.environ.get('FLASK_ENV') or '').strip().lower()
is_production = deployment_environment == 'production'
configured_secret_key = os.environ.get('SECRET_KEY')
if is_production and not configured_secret_key:
    raise RuntimeError('SECRET_KEY must be configured when DRRAS_ENV=production.')
app.config['SECRET_KEY'] = configured_secret_key or 'drras-secure-local-session-key-2026'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB max request payload
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = is_production

# Register modular domain API routes
app.register_blueprint(api_bp)

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

# Ensure DB initialized on startup
init_db()

def get_db():
    if 'db' not in g:
        g.db = database.get_db()
    return g.db

@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass

# ----------------- ERROR HANDLERS -----------------

@app.errorhandler(400)
def handle_bad_request(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': getattr(e, 'description', 'Bad request')}), 400
    return render_template('index.html'), 400

@app.errorhandler(404)
def handle_not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Resource not found'}), 404
    return render_template('index.html'), 404

@app.errorhandler(405)
def handle_method_not_allowed(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Method not allowed'}), 405
    return render_template('index.html'), 405

@app.errorhandler(413)
def handle_payload_too_large(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Payload exceeds maximum allowed size (2MB).'}), 413
    return "Payload too large", 413

@app.errorhandler(500)
def handle_server_error(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('index.html'), 500

# ----------------- AUTHENTICATION HELPERS & DECORATORS -----------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required. Please sign in.'}), 401
        conn = get_db()
        user = conn.execute("SELECT id, role, status FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user or user['status'] != 'ACTIVE':
            session.clear()
            return jsonify({'error': 'Account inactive or session invalidated. Please sign in again.'}), 401
        return f(*args, **kwargs)
    return decorated

def roles_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user_id = session.get('user_id')
            if not user_id:
                return jsonify({'error': 'Authentication required. Please sign in.'}), 401
            conn = get_db()
            user = conn.execute("SELECT id, role, status FROM users WHERE id = ?", (user_id,)).fetchone()
            if not user or user['status'] != 'ACTIVE':
                session.clear()
                return jsonify({'error': 'Account inactive or session invalidated. Please sign in again.'}), 401
            user_role = user['role']
            if user_role not in allowed_roles:
                return jsonify({'error': f'Access denied. Required role(s): {", ".join(allowed_roles)}'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

@app.before_request
def csrf_protect():
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        if request.path.startswith('/static') or request.path in ('/api/auth/login', '/api/auth/register', '/api/auth/logout'):
            return None
        # Enforce if explicit testing flag set or in live runtime
        if app.config.get('TESTING') and not app.config.get('ENFORCE_CSRF'):
            return None
        if session.get('user_id'):
            token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
            if not token or token != session.get('csrf_token'):
                return jsonify({'error': 'Invalid or missing CSRF token.', 'code': 'CSRF_FAILED'}), 403

def sanitize_csv_cell(val):
    if val is None:
        return ''
    s = str(val)
    stripped = s.lstrip()
    if stripped and stripped[0] in ('=', '+', '-', '@', '\t', '\r', '%'):
        return f"'{s}"
    return s

# ----------------- HOME PAGE -----------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/healthz', methods=['GET'])
def health_check():
    """Lightweight Render health check backed by an actual database query."""
    conn = None
    try:
        conn = database.get_db()
        conn.execute('SELECT 1').fetchone()
        return jsonify({'status': 'ok'}), 200
    except Exception:
        app.logger.exception('Database health check failed')
        return jsonify({'status': 'unavailable'}), 503
    finally:
        if conn is not None:
            conn.close()

# ----------------- AUTHENTICATION ROUTES -----------------

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE LOWER(email) = ?', (email,)).fetchone()

    # Compatibility login aliases for the original local demonstration roster.
    # These are not stored as duplicate emails; every account's canonical
    # database email remains the organization/role-specific drras-demo.local address.
    legacy_aliases = {
        'admin@drras.in': ('Administrator','admin123',"1=1",()),
        'official@drras.in': ('Government Official','official123',"1=1",()),
        'ngo@drras.in': ('NGO Coordinator','ngo123',"EXISTS(SELECT 1 FROM organization_memberships m WHERE m.user_id=u.id AND m.organization_id=1 AND m.membership_role='Coordinator' AND m.status='Active')",()),
        'volunteer@drras.in': ('Volunteer','volunteer123',"EXISTS(SELECT 1 FROM ngo_personnel_approvals a WHERE a.user_id=u.id AND a.organization_id=1 AND a.personnel_type='Volunteer' AND a.decision='Approved')",()),
        'citizen@drras.in': ('Citizen','citizen123',"1=1",()),
        'driver@drras.in': ('Driver','driver123',"u.organization_id IS NULL AND EXISTS(SELECT 1 FROM government_driver_approvals a WHERE a.user_id=u.id)",(0,)),
        'simran.driver@drras.in': ('Driver','driver123',"u.organization_id IS NULL AND EXISTS(SELECT 1 FROM government_driver_approvals a WHERE a.user_id=u.id)",(1,)),
        'karan.driver@drras.in': ('Driver','driver123',"u.organization_id IS NULL AND EXISTS(SELECT 1 FROM government_driver_approvals a WHERE a.user_id=u.id)",(2,)),
        'responder.demo@drras.in': ('Volunteer','govvol123',"EXISTS(SELECT 1 FROM government_personnel p WHERE p.user_id=u.id AND p.status='Active')",()),
        'contact@khalsaaid.org': ('NGO Coordinator','ngo123',"EXISTS(SELECT 1 FROM organization_memberships m WHERE m.user_id=u.id AND m.organization_id=2 AND m.membership_role='Coordinator' AND m.status='Active')",()),
        'redcross@drras.in': ('NGO Coordinator','ngo123',"EXISTS(SELECT 1 FROM organization_memberships m WHERE m.user_id=u.id AND m.organization_id=3 AND m.membership_role='Coordinator' AND m.status='Active')",()),
    }
    legacy_match = re.fullmatch(r'(driver|volunteer)\.ngo([1-3])\.([12])@drras\.in', email)
    if legacy_match:
        kind, oid, n = legacy_match.groups()
        role='Driver' if kind=='driver' else 'Volunteer'
        personnel_type=role
        legacy_aliases[email]=(role,'driver123' if role=='Driver' else 'volunteer123',
            f"EXISTS(SELECT 1 FROM ngo_personnel_approvals a WHERE a.user_id=u.id AND a.organization_id={int(oid)} AND a.personnel_type='{personnel_type}' AND a.decision='Approved')",(int(n)-1,))
    if user is None and email in legacy_aliases:
        alias_role, alias_password, scope, offset = legacy_aliases[email]
        candidates=conn.execute(f"SELECT u.* FROM users u WHERE u.role=? AND u.status='ACTIVE' AND {scope} ORDER BY u.id",(alias_role,)).fetchall()
        candidates=candidates[offset[0]:offset[0]+1] if offset else candidates[:1]
        user=next((candidate for candidate in candidates if verify_password(candidate['password'],password)[0] and password==alias_password),None)

    if not user:
        return jsonify({'error': 'Invalid email or password.'}), 401

    is_valid, needs_rehash = verify_password(user['password'], password)
    if not is_valid:
        return jsonify({'error': 'Invalid email or password.'}), 401

    if needs_rehash:
        new_hash = generate_password_hash(password)
        conn.execute('UPDATE users SET password = ? WHERE id = ?', (new_hash, user['id']))
        conn.commit()

    if user['status'] != 'ACTIVE':
        status_msg = {
            'PENDING': 'Your registration is pending Admin approval. Please contact an administrator.',
            'REJECTED': 'Your registration request was rejected by an administrator.',
            'SUSPENDED': 'Your account has been suspended. Please contact an administrator.'
        }.get(user['status'], f"Account status '{user['status']}' is not active.")
        return jsonify({'error': status_msg}), 403

    if user['role'] == 'Driver':
        if user['organization_id']:
            approved_driver = conn.execute("SELECT 1 FROM ngo_personnel_approvals WHERE user_id=? AND organization_id=? AND personnel_type='Driver' AND decision='Approved'", (user['id'], user['organization_id'])).fetchone()
        else:
            approved_driver = conn.execute("SELECT 1 FROM government_driver_approvals WHERE user_id=?", (user['id'],)).fetchone()
        if not approved_driver:
            return jsonify({'error': 'Driver account is not approved for a Government fleet or its owning NGO.'}), 403
    if user['role'] == 'Volunteer':
        if user['organization_id']:
            approved_volunteer = conn.execute("SELECT 1 FROM ngo_personnel_approvals WHERE user_id=? AND organization_id=? AND personnel_type='Volunteer' AND decision='Approved'", (user['id'], user['organization_id'])).fetchone()
            if not approved_volunteer:return jsonify({'error': 'Volunteer access is pending approval by the owning NGO Coordinator.'}), 403
        else:
            approved_volunteer=conn.execute("SELECT 1 FROM government_personnel gp JOIN volunteers v ON v.user_id=gp.user_id WHERE gp.user_id=? AND gp.status='Active' AND v.owner_type='government' AND v.organization_id IS NULL AND v.verified=1",(user['id'],)).fetchone()
            if not approved_volunteer:return jsonify({'error':'Government responder account is not linked to an active Government roster entry.'}),403
    login_organization_id=user['organization_id']
    if user['role'] == 'NGO Coordinator':
        coordinator_org = conn.execute("SELECT o.id FROM organizations o JOIN organization_memberships m ON m.organization_id=o.id WHERE m.user_id=? AND m.membership_role='Coordinator' AND m.status='Active' AND o.status='Approved' ORDER BY o.id LIMIT 1", (user['id'],)).fetchone()
        if not coordinator_org:
            return jsonify({'error': 'This NGO Coordinator account is not linked to an approved organization.'}), 403
        login_organization_id=login_organization_id or coordinator_org['id']

    # Set server-side session
    session['user_id'] = user['id']
    session['email'] = user['email']
    session['role'] = user['role']
    session['name'] = user['name']
    session['organization_id'] = login_organization_id
    csrf_token = secrets.token_hex(32)
    session['csrf_token'] = csrf_token

    resp = make_response(jsonify({
        'id': user['id'],
        'email': user['email'],
        'name': user['name'],
        'initials': user['initials'],
        'role': user['role'],
        'status': user['status'],
        'organization_id': login_organization_id,
        'driver_classification': ('NGO Driver' if user['organization_id'] else 'Government Driver') if user['role'] == 'Driver' else None,
        'csrf_token': csrf_token
    }))
    resp.set_cookie('csrf_token', csrf_token, samesite='Lax', secure=False, httponly=False)
    return resp

@app.route('/api/auth/me', methods=['GET'])
def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not logged in'}), 401

    conn = get_db()
    user = conn.execute('SELECT id, email, name, initials, role, status FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        session.clear()
        return jsonify({'error': 'User not found'}), 401

    return jsonify(dict(user))

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully.'})

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()
    name = (data.get('name') or '').strip()
    role = (data.get('role') or 'Citizen').strip()

    if not email or not password or not name:
        return jsonify({'error': 'All fields are required.'}), 400

    if not EMAIL_REGEX.match(email):
        return jsonify({'error': 'Please enter a valid email address.'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters long.'}), 400

    valid_roles = ('Citizen', 'Volunteer', 'NGO Coordinator', 'Government Official', 'Driver')
    if role not in valid_roles:
        role = 'Citizen'
    conn = get_db()
    org_id = None
    if role in ('Volunteer','Driver','NGO Coordinator'):
        driver_type=(data.get('driver_type') or 'NGO Driver').strip()
        org_raw=data.get('organization_id')
        if role=='Driver' and driver_type!='NGO Driver':
            return jsonify({'error':'Public signup can request an NGO Driver account only. Government Drivers must be provisioned by an authorized Administrator or Official.'}),400
        try: org_id=int(org_raw)
        except (TypeError,ValueError): return jsonify({'error':'Select the organization that will review this personnel application.'}),400
        org=conn.execute("SELECT id FROM organizations WHERE id=? AND organization_type='NGO' AND status='Approved'",(org_id,)).fetchone()
        if not org: return jsonify({'error':'Selected NGO is not approved to receive personnel applications.'}),400

    initials = "".join([part[0].upper() for part in name.split() if part])[:2] or 'U'
    status = 'ACTIVE' if role == 'Citizen' else 'PENDING'

    existing = conn.execute('SELECT id FROM users WHERE LOWER(email) = ?', (email,)).fetchone()
    if existing:
        return jsonify({'error': 'An account already exists with this email address.'}), 400

    hashed_pw = generate_password_hash(password)
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO users (email, password, name, initials, role, status, organization_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (email, hashed_pw, name, initials, role, status, org_id))
    if role in ('Volunteer','Driver','NGO Coordinator'):
        membership_role='Coordinator' if role=='NGO Coordinator' else role
        conn.execute("INSERT INTO organization_memberships (organization_id,user_id,membership_role,status) VALUES (?,?,?,'Inactive')",(org_id,cur.lastrowid,membership_role))
    conn.commit()
    user_id = cur.lastrowid

    return jsonify({
        'id': user_id,
        'email': email,
        'name': name,
        'initials': initials,
        'role': role,
        'status': status,
        'message': 'Account created successfully.' if status == 'ACTIVE' else (f'Registration submitted for {role}. The owning NGO Coordinator must approve it before you can sign in.' if role in ('Volunteer','Driver') else f'Registration submitted for {role}. An Admin must approve it before you can sign in.')
    }), 201

# ----------------- ADMIN APPROVALS -----------------

@app.route('/api/admin/pending-users', methods=['GET'])
@roles_required('Administrator')
def get_pending_users():
    conn = get_db()
    rows = conn.execute("SELECT id, email, name, initials, role, status, created_at FROM users WHERE status = 'PENDING' ORDER BY id DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/admin/approve-user', methods=['POST'])
@roles_required('Administrator')
def approve_user():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    if not email:
        return jsonify({'error': 'Email is required'}), 400

    conn = get_db()
    user = conn.execute("SELECT id, status, name, role FROM users WHERE LOWER(email) = ?", (email,)).fetchone()
    if not user:
        return jsonify({'error': f'User with email {email} not found'}), 404

    if user['status'] == 'ACTIVE':
        return jsonify({'success': True, 'message': f'Account {email} is already active.'})
    if user['role'] in ('Volunteer','Driver'):
        return jsonify({'error':'NGO personnel must be approved by a Coordinator of their owning organization.','code':'OWNER_APPROVAL_REQUIRED'}),409

    with conn:
        conn.execute("UPDATE users SET status = 'ACTIVE' WHERE LOWER(email) = ?", (email,))
        if user['role']=='NGO Coordinator':
            ngo_user=conn.execute("SELECT id,organization_id FROM users WHERE LOWER(email)=?",(email,)).fetchone()
            if not ngo_user['organization_id']:
                return jsonify({'error':'NGO Coordinator application must select an approved organization.'}),409
            conn.execute("UPDATE organization_memberships SET status='Active' WHERE user_id=? AND organization_id=? AND membership_role='Coordinator'",(ngo_user['id'],ngo_user['organization_id']))
        if user['role'] == 'Driver':
            driver_row=conn.execute("SELECT id,organization_id FROM users WHERE LOWER(email)=?",(email,)).fetchone()
            if driver_row and driver_row['organization_id'] is None:
                conn.execute("INSERT OR IGNORE INTO government_driver_approvals(user_id,approved_by_user_id,reason) VALUES(?,?,?)",(driver_row['id'],session.get('user_id'),'Approved by Administrator'))
        conn.execute('''
            INSERT INTO activities (workspace_key, title, details)
            VALUES ('admin', ?, ?)
        ''', (f"Account Activated: {user['name']}", f"Role: {user['role']} ({email}). Granted system access."))
        log_system_event(conn, 'user_status_changed', {'email': email, 'status': 'ACTIVE', 'role': user['role']})

    return jsonify({'success': True, 'message': f'Account {email} approved successfully.'})

@app.route('/api/admin/reject-user', methods=['POST'])
@roles_required('Administrator')
def reject_user():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    if not email:
        return jsonify({'error': 'Email is required'}), 400

    conn = get_db()
    user = conn.execute("SELECT id, status, name, role FROM users WHERE LOWER(email) = ?", (email,)).fetchone()
    if not user:
        return jsonify({'error': f'User with email {email} not found'}), 404

    if user['status'] == 'REJECTED':
        return jsonify({'success': True, 'message': f'Account {email} is already rejected.'})

    with conn:
        conn.execute("UPDATE users SET status = 'REJECTED' WHERE LOWER(email) = ?", (email,))
        conn.execute('''
            INSERT INTO activities (workspace_key, title, details)
            VALUES ('admin', ?, ?)
        ''', (f"Registration Rejected: {user['name']}", f"Role requested: {user['role']} ({email}). Rejected by Administrator."))
        log_system_event(conn, 'user_status_changed', {'email': email, 'status': 'REJECTED', 'role': user['role']})

    return jsonify({'success': True, 'message': f'Account {email} registration rejected.'})

# ----------------- DASHBOARD SUMMARY -----------------

@app.route('/api/dashboard', methods=['GET'])
@login_required
def dashboard_summary():
    conn = get_db()
    role=session.get('role'); user_id=session.get('user_id'); params=[]; request_scope='1=1'
    if role == 'Citizen':
        request_scope='r.requester_user_id=?'; params=[user_id]
    elif role == 'Driver':
        request_scope='EXISTS(SELECT 1 FROM dispatches d WHERE d.request_id=r.id AND d.driver_user_id=?)'; params=[user_id]
    elif role == 'Volunteer':
        request_scope='EXISTS(SELECT 1 FROM volunteer_tasks t JOIN volunteers v ON v.id=t.volunteer_id WHERE t.request_id=r.id AND v.user_id=?)'; params=[user_id]
    elif role == 'NGO Coordinator':
        org=conn.execute("SELECT COALESCE(u.organization_id,(SELECT organization_id FROM organization_memberships WHERE user_id=u.id AND membership_role='Coordinator' AND status='Active' LIMIT 1)) FROM users u WHERE u.id=?",(user_id,)).fetchone()
        org_id=org[0] if org else None
        request_scope='(r.assigned_organization_id=? OR EXISTS(SELECT 1 FROM response_assignments a WHERE a.request_id=r.id AND a.owner_type=\'ngo\' AND a.organization_id=?) OR EXISTS(SELECT 1 FROM zone_adoptions za WHERE za.zone_id=r.zone_id AND za.organization_id=? AND za.status IN (\'Approved\',\'Active\')))' 
        params=[org_id,org_id,org_id]
    open_reqs=conn.execute(f"SELECT COUNT(*) FROM emergency_requests r WHERE {request_scope} AND r.status NOT IN ('Delivered','Closed','Rejected','Duplicate')",params).fetchone()[0]
    crit_reqs=conn.execute(f"SELECT COUNT(*) FROM emergency_requests r WHERE {request_scope} AND r.priority_score>=85 AND r.verification_status='Verified' AND r.status IN ('Verified','Awaiting allocation','Partially Fulfilled')",params).fetchone()[0]
    resource_scope=''; volunteer_scope=''; zone_scope=''; vehicle_scope=''; warehouse_scope=''; resource_params=[]; volunteer_params=[]; scope_params=[]; zone_params=[]; vehicle_params=[]
    if role=='Government Official':
        resource_scope="WHERE w.owner_type='government' AND w.owner_organization_id IS NULL"; warehouse_scope=resource_scope; vehicle_scope="WHERE owner_type='government' AND owner_organization_id IS NULL"; volunteer_scope="WHERE owner_type='government' OR (owner_type='unassigned' AND user_id IN (SELECT user_id FROM government_personnel WHERE user_id IS NOT NULL))"; zone_scope="WHERE status='Active'"
    elif role=='NGO Coordinator':
        resource_scope="WHERE w.owner_type='ngo' AND w.owner_organization_id=?"; warehouse_scope=resource_scope; vehicle_scope="WHERE owner_type='ngo' AND owner_organization_id=?"; volunteer_scope="WHERE owner_type='ngo' AND organization_id=?"; zone_scope="WHERE status='Active' AND id IN (SELECT zone_id FROM zone_adoptions WHERE organization_id=? AND status IN ('Approved','Active'))"; resource_params=[org_id]; volunteer_params=[org_id]; zone_params=[org_id]; vehicle_params=[org_id]
    elif role=='Driver':
        driver_org=conn.execute('SELECT organization_id FROM users WHERE id=?',(user_id,)).fetchone(); org_id=driver_org[0] if driver_org else None
        owner='ngo' if org_id else 'government'
        resource_scope="WHERE w.owner_type=? AND w.owner_organization_id IS ?"; warehouse_scope=resource_scope; vehicle_scope="WHERE owner_type=? AND owner_organization_id IS ?"; volunteer_scope="WHERE 0"; zone_scope="WHERE status='Active'"; resource_params=[owner,org_id]; vehicle_params=[owner,org_id]
    elif role=='Volunteer':
        resource_scope="WHERE w.owner_type='government' AND w.owner_organization_id IS NULL"; warehouse_scope=resource_scope; vehicle_scope="WHERE owner_type='government' AND owner_organization_id IS NULL"; volunteer_scope="WHERE user_id=?"; zone_scope="WHERE status='Active'"; volunteer_params=[user_id]
    elif role=='Citizen':
        resource_scope="WHERE w.owner_type='government' AND w.owner_organization_id IS NULL"; warehouse_scope=resource_scope; vehicle_scope="WHERE 0"; volunteer_scope="WHERE 0"; zone_scope="WHERE status='Active'"
    else:
        resource_scope=''; warehouse_scope=''; vehicle_scope=''; volunteer_scope=''; zone_scope="WHERE status='Active'"
    total_res=conn.execute(f"SELECT COALESCE(SUM(MAX(0,ws.on_hand_units-ws.reserved_units)),0) FROM warehouse_stock ws JOIN warehouses w ON w.id=ws.warehouse_id {resource_scope}",resource_params).fetchone()[0]
    vol_count=conn.execute(f"SELECT COUNT(*) FROM volunteers {volunteer_scope}",volunteer_params).fetchone()[0]
    active_inc_row = conn.execute("SELECT id, title FROM incidents WHERE status = 'Active' ORDER BY created_at DESC LIMIT 1").fetchone()
    active_inc_count = conn.execute("SELECT COUNT(*) FROM incidents WHERE status = 'Active'").fetchone()[0]
    active_zones_count = conn.execute(f"SELECT COUNT(*) FROM zones {zone_scope}",zone_params).fetchone()[0]
    wh_query=f"SELECT COUNT(*) FROM warehouses w {warehouse_scope} AND w.status='Active'" if warehouse_scope else "SELECT COUNT(*) FROM warehouses WHERE status='Active'"
    wh_count = conn.execute(wh_query,resource_params).fetchone()[0]
    available_vehicles = conn.execute(f"SELECT COUNT(*) FROM vehicles {vehicle_scope} AND status='Available'" if vehicle_scope else "SELECT COUNT(*) FROM vehicles WHERE status='Available'",vehicle_params).fetchone()[0]
    today=datetime.now().date(); first_day=(today-timedelta(days=6)).isoformat()
    trend_rows=conn.execute(f"SELECT substr(r.created_at,1,10) AS day,COUNT(*) AS total FROM emergency_requests r WHERE {request_scope} AND substr(r.created_at,1,10)>=? GROUP BY substr(r.created_at,1,10)",params+[first_day]).fetchall()
    counts={r['day']:r['total'] for r in trend_rows}
    trend=[{'d':(today-timedelta(days=6-i)).strftime('%d %b'),'v':counts.get((today-timedelta(days=6-i)).isoformat(),0)} for i in range(7)]
    return jsonify({
        'activeDisasters': active_inc_count,
        'activeIncidentTitle': active_inc_row['title'] if active_inc_row else 'No active incident',
        'activeIncidentId': active_inc_row['id'] if active_inc_row else None,
        'activeZonesCount': active_zones_count,
        'warehousesCount': wh_count,
        'availableVehiclesCount': available_vehicles,
        'openRequests': open_reqs,
        'criticalRequests': crit_reqs,
        'availableResources': total_res,
        'availableResourcesFormatted': f"{total_res:,}",
        'activeVolunteers': vol_count,
        'criticalAlerts': crit_reqs,
        'lastUpdated': datetime.now().astimezone().isoformat(),
        'trend': trend
    })

# ----------------- EMERGENCY REQUESTS -----------------

@app.route('/api/requests', methods=['GET'])
def get_requests():
    conn = get_db()
    user_id = session.get('user_id')
    user_role = session.get('role')
    user_name = session.get('name')

    if not user_id:
        # Public redacted projection: preserve counts, priorities, area, but redact sensitive personal PII
        rows = conn.execute("SELECT id,requester_name,area,need,people_affected,vulnerable_people,priority_score,status,time_str,lat,lng,incident_id,zone_id,created_at FROM emergency_requests ORDER BY priority_score DESC, created_at DESC").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d['requester_name'] = 'Confidential'
            d['address'] = d['area']
            if d.get('lat') is not None:
                d['lat'] = round(d['lat'], 2)
            if d.get('lng') is not None:
                d['lng'] = round(d['lng'], 2)
            result.append(d)
        return jsonify(result)

    if user_role == 'Citizen':
        rows = conn.execute("""SELECT r.*,o.name AS response_organization_name,
            (SELECT a.status FROM response_assignments a WHERE a.request_id=r.id
              AND a.owner_type=r.response_owner_type AND a.organization_id IS r.response_organization_id
              AND a.status IN ('Assigned','Active','Completed') ORDER BY a.id DESC LIMIT 1) AS response_assignment_status
            FROM emergency_requests r LEFT JOIN organizations o ON o.id=r.response_organization_id
            WHERE r.requester_user_id=? ORDER BY r.priority_score DESC,r.created_at DESC""",(user_id,)).fetchall()
        return jsonify([dict(r) for r in rows])

    if user_role == 'Driver':
        rows = conn.execute('''
            SELECT * FROM emergency_requests 
            WHERE id IN (
                SELECT request_id FROM dispatches WHERE driver_user_id = ?
            )
            ORDER BY priority_score DESC, created_at DESC
        ''', (user_id,)).fetchall()
        return jsonify([dict(r) for r in rows])

    if user_role == 'NGO Coordinator':
        org_row=conn.execute("SELECT COALESCE(u.organization_id,(SELECT organization_id FROM organization_memberships WHERE user_id=u.id AND membership_role='Coordinator' AND status='Active' LIMIT 1)) FROM users u WHERE u.id=?",(user_id,)).fetchone()
        org_id=org_row[0] if org_row else None
        if not org_id or not conn.execute("SELECT 1 FROM organizations WHERE id=? AND organization_type='NGO' AND status='Approved'",(org_id,)).fetchone(): return jsonify([])
        rows=conn.execute("""SELECT DISTINCT r.id,r.area,r.need,r.people_affected,r.vulnerable_people,r.priority_score,r.status,r.created_at,r.incident_id,r.zone_id,r.verification_status,
            r.response_owner_type,r.response_organization_id,owner.name AS response_organization_name,
            'Confidential' AS requester_name,r.area AS address,
            (SELECT a.status FROM response_assignments a WHERE a.request_id=r.id AND a.owner_type=r.response_owner_type
              AND a.organization_id IS r.response_organization_id AND a.status IN ('Assigned','Active','Completed')
              ORDER BY a.id DESC LIMIT 1) AS response_assignment_status,
            CASE WHEN r.response_owner_type='ngo' AND r.response_organization_id=?
              AND EXISTS(SELECT 1 FROM response_assignments a WHERE a.request_id=r.id AND a.owner_type='ngo'
                AND a.organization_id=? AND a.status IN ('Assigned','Active')) THEN 1 ELSE 0 END AS ngo_assignment_active,
            CASE WHEN (r.response_owner_type IS NULL OR (r.response_owner_type='ngo' AND r.response_organization_id=?
              AND NOT EXISTS(SELECT 1 FROM response_assignments x WHERE x.request_id=r.id AND x.owner_type='ngo' AND x.organization_id=? AND x.status IN ('Assigned','Active')))) AND r.verification_status!='Rejected'
              AND r.status NOT IN ('Rejected','Closed','Delivered','Duplicate','Cancelled') THEN 1 ELSE 0 END AS ngo_assignment_eligible
            FROM emergency_requests r
            LEFT JOIN organizations owner ON owner.id=r.response_organization_id
            ORDER BY r.priority_score DESC,r.created_at DESC""",(org_id,org_id,org_id,org_id)).fetchall()
        return jsonify([dict(r) for r in rows])

    if user_role == 'Volunteer':
        rows=conn.execute("""SELECT DISTINCT r.* FROM emergency_requests r JOIN volunteer_tasks t ON t.request_id=r.id
            JOIN volunteers v ON v.id=t.volunteer_id WHERE v.user_id=? ORDER BY r.priority_score DESC""",(user_id,)).fetchall()
        return jsonify([dict(r) for r in rows])

    # Administrator/Government operational view.
    rows = conn.execute("""SELECT r.*,o.name AS response_organization_name,
        (SELECT a.status FROM response_assignments a WHERE a.request_id=r.id
          AND a.owner_type=r.response_owner_type AND a.organization_id IS r.response_organization_id
          AND a.status IN ('Assigned','Active','Completed') ORDER BY a.id DESC LIMIT 1) AS response_assignment_status
        FROM emergency_requests r LEFT JOIN organizations o ON o.id=r.response_organization_id
        ORDER BY r.priority_score DESC,r.created_at DESC""").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/requests', methods=['POST'])
def create_request():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or data.get('requesterName') or '').strip()
    area = (data.get('area') or '').strip()
    address = (data.get('address') or '').strip()
    need = (data.get('need') or data.get('assistanceType') or '').strip()
    people_raw = data.get('people') if data.get('people') is not None else data.get('peopleAffected')

    if not name or not area or not need or not address:
        return jsonify({'error': 'Name, area, address, and assistance need are all required.'}), 400

    # Validate people: strictly whole positive integer, reject boolean and float
    if isinstance(people_raw, bool) or isinstance(people_raw, float):
        return jsonify({'error': 'People affected must be a positive whole integer.'}), 400
    if isinstance(people_raw, str):
        if not people_raw.strip().isdigit():
            return jsonify({'error': 'People affected must be a valid positive integer.'}), 400

    try:
        people = int(people_raw)
        if people <= 0 or people > 100000:
            return jsonify({'error': 'People affected must be a positive integer between 1 and 100,000.'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid number of people affected.'}), 400

    # Validate lat / lng
    lat_raw = data.get('lat')
    lng_raw = data.get('lng')
    if (lat_raw is None) != (lng_raw is None):
        return jsonify({'error': 'Latitude and longitude must be supplied together.'}), 400
    if isinstance(lat_raw, bool) or isinstance(lng_raw, bool):
        return jsonify({'error': 'Coordinates must be valid numbers.'}), 400

    try:
        lat = float(lat_raw) if lat_raw is not None else None
        lng = float(lng_raw) if lng_raw is not None else None
        if lat is not None and (not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0)):
            return jsonify({'error': 'Coordinates out of valid range (-90 to 90 lat, -180 to 180 lng).'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Coordinates must be valid numbers.'}), 400

    # Parse vulnerable case-insensitively
    vuln_input = data.get('vulnerable') if data.get('vulnerable') is not None else data.get('vulnerablePeople')
    if isinstance(vuln_input, str):
        vuln_clean = vuln_input.strip().lower()
    else:
        vuln_clean = vuln_input
    vulnerable = vuln_clean in (True, 'yes', 'true', '1', 1)

    priority = calc_priority(people, vulnerable, need)

    conn = get_db()
    with conn:
        # Atomic generation of next REQ- ID using max numeric suffix
        max_num_row = conn.execute("SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM emergency_requests").fetchone()
        next_num = (max_num_row[0] or 2049) + 1
        req_id = f"REQ-{next_num}"

        map_left = 30 + ((abs(lat) * 100) % 55) if lat is not None else None
        map_top = 25 + ((abs(lng) * 100) % 55) if lng is not None else None

        req_user_id = session.get('user_id')
        submitted_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
        inc_id = data.get('incident_id')
        if inc_id:
            chk_inc = conn.execute("SELECT id FROM incidents WHERE id = ?", (inc_id,)).fetchone()
            if not chk_inc:
                inc_id = None
        zone_id = data.get('zone_id')
        if zone_id:
            chk_z = conn.execute("SELECT id FROM zones WHERE id = ?", (zone_id,)).fetchone()
            if not chk_z:
                zone_id = None
        desc = (data.get('description') or need).strip()

        conn.execute('''
            INSERT INTO emergency_requests 
            (id, requester_name, area, address, need, people_affected, vulnerable_people, priority_score, status, time_str, lat, lng, map_left, map_top, requester_user_id, incident_id, zone_id, description, verification_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Awaiting allocation', 'just now', ?, ?, ?, ?, ?, ?, ?, ?, 'Unverified', ?)
        ''', (req_id, name, area, address, need, people, 1 if vulnerable else 0, priority, lat, lng, map_left, map_top, req_user_id, inc_id, zone_id, desc, submitted_at))

        officials = conn.execute("SELECT id FROM users WHERE role IN ('Government Official','Administrator') AND status='ACTIVE'").fetchall()
        for official in officials:
            create_notification(conn, official['id'], 'request_created', f'New citizen request {req_id}', f'{need} is needed in {area}. Review and assign an eligible Government response team.', 'emergency_requests', req_id)
        coordinators = conn.execute("""SELECT DISTINCT u.id FROM organizations o
                JOIN users u ON u.role='NGO Coordinator' AND u.status='ACTIVE'
                  AND (u.organization_id=o.id OR EXISTS(
                    SELECT 1 FROM organization_memberships m WHERE m.user_id=u.id AND m.organization_id=o.id
                      AND m.membership_role='Coordinator' AND m.status='Active'))
                WHERE o.organization_type='NGO' AND o.status='Approved'""").fetchall()
        for coordinator in coordinators:
            create_notification(conn, coordinator['id'], 'request_available', f'New request available: {req_id}', f'{need} is needed in {area}. Your approved NGO may accept and assign its own response team.', 'emergency_requests', req_id)
        conn.execute('''
            INSERT INTO activities (workspace_key, title, details)
            VALUES ('requests', ?, ?)
        ''', (f"Distress Signal: {req_id}", f"{name} in {area} reported urgent need for {need} ({people} affected, Score: {priority})."))
        log_system_event(conn, 'request_created', {'id': req_id, 'requester_name': name, 'area': area, 'need': need, 'priority_score': priority})

    created = conn.execute("SELECT * FROM emergency_requests WHERE id = ?", (req_id,)).fetchone()
    return jsonify(dict(created)), 201

@app.route('/api/requests/<id>/allocate', methods=['PATCH', 'POST'])
@roles_required('Administrator', 'Government Official', 'NGO Coordinator')
def allocate_request(id):
    conn = get_db()
    user_id = session.get('user_id') or 1
    user_role = session.get('role')
    data = request.get_json(silent=True) or {}

    override = bool(data.get('emergency_override'))
    if override:
        return jsonify({'error': 'Emergency override is not enabled. Verify the request before allocation.', 'code': 'VERIFICATION_REQUIRED'}), 409

    try:
        with conn:
            res = services.allocate_request_service(conn, id, user_id, user_role, emergency_override=override, selected_driver_id=data.get('driver_user_id'), selected_vehicle_id=data.get('vehicle_id'))
        resp = dict(res['request'])
        if 'dispatch_id' in res:
            resp['dispatch_id'] = res['dispatch_id']
        elif res.get('dispatch'):
            resp['dispatch_id'] = res['dispatch']['id']
        if 'reservation_id' in res:
            resp['reservation_id'] = res['reservation_id']
        return jsonify(resp)
    except BusinessLogicError as e:
        return jsonify({'error': e.message, 'code': e.code}), e.status_code

# ----------------- INVENTORY & WAREHOUSES -----------------

@app.route('/api/inventory', methods=['GET'])
@login_required
def get_inventory():
    conn=get_db(); role=session.get('role'); user_id=session.get('user_id')
    scope=None; org_id=None
    if role=='Government Official': scope='government'
    elif role=='NGO Coordinator':
        row=conn.execute("SELECT COALESCE(u.organization_id,(SELECT organization_id FROM organization_memberships WHERE user_id=u.id AND membership_role='Coordinator' AND status='Active' LIMIT 1)) FROM users u WHERE u.id=?",(user_id,)).fetchone()
        org_id=row[0] if row else None; scope='ngo'
    elif role=='Driver':
        row=conn.execute('SELECT organization_id FROM users WHERE id=?',(user_id,)).fetchone(); org_id=row[0] if row else None; scope='ngo' if org_id else 'government'
    where=''; params=[]
    if role in ('Citizen','Volunteer'): return jsonify([])
    if role=='Administrator': scope='all'
    if scope=='government': where="WHERE w.owner_type='government' AND w.owner_organization_id IS NULL"
    elif scope=='ngo': where="WHERE w.owner_type='ngo' AND w.owner_organization_id=?"; params=[org_id]
    rows=conn.execute(f"""SELECT ws.id,ws.resource_id,ws.warehouse_id,r.name AS resource_name,ws.target_stock,w.name AS warehouse_name,
        w.owner_type,w.owner_organization_id,o.name AS owner_name,
        ws.on_hand_units,ws.reserved_units,MAX(0,ws.on_hand_units-ws.reserved_units) AS available_units,ws.status
        FROM warehouse_stock ws JOIN warehouses w ON w.id=ws.warehouse_id JOIN resources r ON r.id=ws.resource_id
        LEFT JOIN organizations o ON o.id=w.owner_organization_id {where} ORDER BY w.id,r.name""",params).fetchall()
    result=[]
    for row in rows:
        item=dict(row)
        item['status']=calc_inventory_status(item['available_units'],item['target_stock'])
        result.append(item)
    return jsonify(result)

@app.route('/api/inventory', methods=['POST'])
@roles_required('Administrator', 'Government Official', 'NGO Coordinator')
def add_inventory():
    data=request.get_json(silent=True) or {};name=(data.get('name') or '').strip();warehouse=data.get('warehouse_id',data.get('warehouse'))
    available_raw=data.get('available');target_raw=data.get('target')
    if available_raw is None or target_raw is None:return jsonify({'error':'Available stock and target stock must be provided explicitly.'}),400
    if isinstance(available_raw,bool) or isinstance(target_raw,bool) or isinstance(available_raw,float) or isinstance(target_raw,float):return jsonify({'error':'Available and target stock must be whole integers.'}),400
    try:available=int(available_raw);target=int(target_raw)
    except (TypeError,ValueError):return jsonify({'error':'Enter whole stock quantities.'}),400
    whid=None
    if warehouse not in (None,''):
        try:whid=int(warehouse)
        except (TypeError,ValueError):return jsonify({'error':'Select an active warehouse.'}),400
    if available<0 or target<=0:return jsonify({'error':'Available units must be >= 0 and target stock must be > 0.'}),400
    conn=get_db();role=session['role']
    if whid is None:
        owner_type='government' if role in ('Administrator','Government Official') else 'ngo';org_id=None
        if role=='NGO Coordinator':
            org=conn.execute("SELECT COALESCE(u.organization_id,(SELECT organization_id FROM organization_memberships WHERE user_id=u.id AND membership_role='Coordinator' AND status='Active' LIMIT 1)) FROM users u WHERE u.id=?",(session['user_id'],)).fetchone();org_id=org[0] if org else None
        wh_default=conn.execute("SELECT id FROM warehouses WHERE owner_type=? AND owner_organization_id IS ? AND status='Active' ORDER BY id LIMIT 1",(owner_type,org_id)).fetchone()
        if not wh_default:return jsonify({'error':'No active warehouse is configured for this owner.'}),409
        whid=wh_default['id']
    wh=conn.execute("SELECT * FROM warehouses WHERE id=? AND status='Active'",(whid,)).fetchone()
    if not wh:return jsonify({'error':'Select an active warehouse from the warehouse list.'}),400
    role=session['role']
    if role=='Government Official' and not(wh['owner_type']=='government' and wh['owner_organization_id'] is None):return jsonify({'error':'Warehouse is outside Government ownership.'}),403
    if role=='NGO Coordinator':
        org=conn.execute("SELECT COALESCE(u.organization_id,(SELECT organization_id FROM organization_memberships WHERE user_id=u.id AND membership_role='Coordinator' AND status='Active' LIMIT 1)) FROM users u WHERE u.id=?",(session['user_id'],)).fetchone()
        if not org or wh['owner_type']!='ngo' or wh['owner_organization_id']!=org[0]:return jsonify({'error':'Warehouse is outside this NGO ownership.'}),403
    resource=None
    if data.get('resource_id'):
        try:resource=conn.execute('SELECT * FROM resources WHERE id=? AND is_active=1',(int(data['resource_id']),)).fetchone()
        except (TypeError,ValueError):return jsonify({'error':'Resource ID must be an integer.'}),400
    elif name:resource=conn.execute('SELECT * FROM resources WHERE LOWER(name)=LOWER(?) AND is_active=1',(name,)).fetchone()
    if not resource and not name:return jsonify({'error':'Choose an existing resource or provide a new resource name.'}),400
    if resource:name=resource['name']
    if conn.execute('SELECT 1 FROM warehouse_stock WHERE warehouse_id=? AND resource_id=?',(whid,resource['id'] if resource else -1)).fetchone():return jsonify({'error':'This resource already exists in a stock record at the selected warehouse.'}),409
    status=calc_inventory_status(available,target)
    with conn:
        if not resource:
            cur=conn.execute("INSERT INTO resources(name,category,unit) VALUES(?,?,?)",(name,(data.get('category') or 'General').strip(),(data.get('unit') or 'units').strip()));resource_id=cur.lastrowid
        else:resource_id=resource['id']
        cur=conn.execute("INSERT INTO warehouse_stock(warehouse_id,resource_id,on_hand_units,reserved_units,target_stock,status) VALUES(?,?,?,0,?,?)",(whid,resource_id,available,target,status));stock_id=cur.lastrowid
        conn.execute("INSERT INTO inventory(resource_name,available_units,target_stock,warehouse_name,status) VALUES(?,?,?,?,?)",(name,available,target,wh['name'],status))
        if available:conn.execute("INSERT INTO inventory_transactions(warehouse_stock_id,transaction_type,quantity_units,direction,reference_type,reference_id,performed_by_user_id,reason) VALUES(?,'OpeningBalance',?,'IN','warehouse_stock',?,?,?)",(stock_id,available,str(stock_id),session['user_id'],'Opening balance entered through inventory management'))
        log_audit_event(conn,session['user_id'],'OPEN_INVENTORY_STOCK','warehouse_stock',stock_id,new_state={'warehouse_id':whid,'resource_id':resource_id,'on_hand_units':available,'target_stock':target})
        log_system_event(conn,'inventory_updated',{'warehouse_id':whid,'stock_id':stock_id,'resource_id':resource_id,'available_units':available})
    return jsonify({'resource_id':resource_id,'warehouse_stock_id':stock_id,'resource_name':name,'available_units':available,'target_stock':target,'warehouse_name':wh['name'],'status':status}),201

@app.route('/api/inventory/<int:id>', methods=['PUT', 'PATCH'])
@roles_required('Administrator', 'Government Official', 'NGO Coordinator')
def update_inventory(id):
    conn=get_db();item=conn.execute("SELECT ws.*,r.name AS resource_name,w.name AS warehouse_name,w.owner_type,w.owner_organization_id FROM warehouse_stock ws JOIN resources r ON r.id=ws.resource_id JOIN warehouses w ON w.id=ws.warehouse_id WHERE ws.id=?",(id,)).fetchone()
    if not item:return jsonify({'error':f'Warehouse stock item {id} not found.'}),404
    role=session['role']
    if role=='Government Official' and not(item['owner_type']=='government' and item['owner_organization_id'] is None):return jsonify({'error':'Stock is outside Government ownership.'}),403
    if role=='NGO Coordinator':
        org=conn.execute("SELECT COALESCE(u.organization_id,(SELECT organization_id FROM organization_memberships WHERE user_id=u.id AND membership_role='Coordinator' AND status='Active' LIMIT 1)) FROM users u WHERE u.id=?",(session['user_id'],)).fetchone()
        if not org or item['owner_type']!='ngo' or item['owner_organization_id']!=org[0]:return jsonify({'error':'Stock is outside this NGO ownership.'}),403
    data=request.get_json(silent=True) or {};available_raw=data.get('available',item['on_hand_units']-item['reserved_units']);target_raw=data.get('target',item['target_stock'])
    if isinstance(available_raw,bool) or isinstance(target_raw,bool) or isinstance(available_raw,float) or isinstance(target_raw,float):return jsonify({'error':'Available and target stock must be whole integers.'}),400
    try:available=int(available_raw);target=int(target_raw)
    except (ValueError,TypeError):return jsonify({'error':'Available and target stock must be valid integers.'}),400
    if available<0 or target<=0:return jsonify({'error':'Available units must be >= 0 and target stock must be > 0.'}),400
    destination_id=item['warehouse_id']; destination=item
    if data.get('warehouse_id') is not None:
        try: destination_id=int(data['warehouse_id'])
        except (TypeError,ValueError): return jsonify({'error':'Warehouse ID must be a valid integer.'}),400
        destination=conn.execute("SELECT id,name,owner_type,owner_organization_id,status FROM warehouses WHERE id=?",(destination_id,)).fetchone()
        if not destination or destination['status']!='Active': return jsonify({'error':'Select an active destination warehouse.'}),400
        if destination['owner_type']!=item['owner_type'] or destination['owner_organization_id']!=item['owner_organization_id']: return jsonify({'error':'Stock cannot be moved across Government/NGO ownership boundaries.'}),403
        if destination_id!=item['warehouse_id'] and item['reserved_units']>0: return jsonify({'error':'Stock with active reservations cannot be moved.'}),409
        if destination_id!=item['warehouse_id'] and conn.execute("SELECT 1 FROM warehouse_stock WHERE warehouse_id=? AND resource_id=?",(destination_id,item['resource_id'])).fetchone(): return jsonify({'error':'Destination already has a stock record for this resource.'}),409
    new_on_hand=available+item['reserved_units'];status=calc_inventory_status(available,target);delta=new_on_hand-item['on_hand_units']
    with conn:
        conn.execute("UPDATE warehouse_stock SET warehouse_id=?,on_hand_units=?,target_stock=?,status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(destination_id,new_on_hand,target,status,id))
        if delta:conn.execute("INSERT INTO inventory_transactions(warehouse_stock_id,transaction_type,quantity_units,direction,reference_type,reference_id,performed_by_user_id,reason) VALUES(?,?,?,?,?,?,?,?)",(id,'Adjustment',abs(delta),'IN' if delta>0 else 'OUT','warehouse_stock',str(id),session['user_id'],'Authorized stock adjustment'))
        log_audit_event(conn,session['user_id'],'ADJUST_INVENTORY_STOCK','warehouse_stock',id,old_state={'warehouse_id':item['warehouse_id'],'on_hand_units':item['on_hand_units'],'target_stock':item['target_stock']},new_state={'warehouse_id':destination_id,'on_hand_units':new_on_hand,'target_stock':target})
        log_system_event(conn,'inventory_updated',{'stock_id':id,'resource_name':item['resource_name'],'available_units':available,'target_stock':target})
    updated=conn.execute("SELECT ws.id,r.name AS resource_name,ws.target_stock,w.name AS warehouse_name,w.owner_type,w.owner_organization_id,ws.on_hand_units,ws.reserved_units,MAX(0,ws.on_hand_units-ws.reserved_units) AS available_units,ws.status FROM warehouse_stock ws JOIN resources r ON r.id=ws.resource_id JOIN warehouses w ON w.id=ws.warehouse_id WHERE ws.id=?",(id,)).fetchone()
    return jsonify(dict(updated))

# ----------------- VOLUNTEERS -----------------

@app.route('/api/volunteers', methods=['GET'])
@login_required
def get_volunteers():
    conn=get_db(); role=session.get('role'); user_id=session.get('user_id')
    if role=='NGO Coordinator':
        org=conn.execute("SELECT COALESCE(u.organization_id,(SELECT organization_id FROM organization_memberships WHERE user_id=u.id AND membership_role='Coordinator' AND status='Active' LIMIT 1)) FROM users u WHERE u.id=?",(user_id,)).fetchone(); rows=conn.execute("SELECT * FROM volunteers WHERE owner_type='ngo' AND organization_id=? ORDER BY id ASC",(org[0] if org else None,)).fetchall()
    elif role=='Administrator': rows=conn.execute("SELECT * FROM volunteers ORDER BY id ASC").fetchall()
    elif role=='Government Official': rows=conn.execute("SELECT * FROM volunteers WHERE owner_type='government' ORDER BY id ASC").fetchall()
    elif role=='Volunteer': rows=conn.execute("SELECT * FROM volunteers WHERE user_id=? ORDER BY id ASC",(user_id,)).fetchall()
    else: return jsonify({'error':'Access denied.'}),403
    return jsonify([dict(r) for r in rows])

@app.route('/api/volunteers', methods=['POST'])
@roles_required('Administrator', 'Government Official')
def register_volunteer():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    skill = (data.get('skill') or '').strip()
    zone = (data.get('zone') or 'Ward 8').strip()

    if not name or not skill:
        return jsonify({'error': 'Name and skill are required'}), 400

    initials = "".join([part[0].upper() for part in name.split() if part])[:2] or 'V'
    conn = get_db()
    with conn:
        conn.execute('''
            INSERT INTO volunteers (initials, name, skill, zone, status)
            VALUES (?, ?, ?, ?, 'Available')
        ''', (initials, name, skill, zone))
        conn.execute('''
            INSERT INTO activities (workspace_key, title, details)
            VALUES ('volunteers', ?, ?)
        ''', (f"Responder Onboarded: {name}", f"Registered for {zone} disaster zone. Skill: {skill}."))
        log_system_event(conn, 'volunteer_updated', {'name': name, 'status': 'Available', 'zone': zone})

    return jsonify({'success': True, 'message': f'{name} registered as volunteer.'}), 201

@app.route('/api/volunteers/<int:id>/assign', methods=['PATCH', 'POST'])
@roles_required('Administrator', 'Government Official', 'NGO Coordinator')
def assign_volunteer(id):
    conn = get_db()
    vol = conn.execute("SELECT id, name, skill, zone, status FROM volunteers WHERE id = ?", (id,)).fetchone()
    if not vol:
        return jsonify({'error': f'Volunteer with ID {id} not found'}), 404
    role=session.get('role'); uid=session.get('user_id')
    if role=='NGO Coordinator':
        org=conn.execute("SELECT COALESCE(u.organization_id,(SELECT organization_id FROM organization_memberships WHERE user_id=u.id AND membership_role='Coordinator' AND status='Active' LIMIT 1)) FROM users u WHERE u.id=?",(uid,)).fetchone()
        full=conn.execute('SELECT owner_type,organization_id FROM volunteers WHERE id=?',(id,)).fetchone()
        if not org or full['owner_type']!='ngo' or full['organization_id']!=org[0]: return jsonify({'error':'Volunteer is outside this NGO ownership.'}),403
    elif role=='Government Official':
        full=conn.execute('SELECT owner_type,organization_id FROM volunteers WHERE id=?',(id,)).fetchone()
        if full['owner_type']!='government' or full['organization_id'] is not None: return jsonify({'error':'Volunteer is outside Government ownership.'}),403

    if vol['status'] == 'On task':
        return jsonify({'error': 'Volunteer is already assigned to an active task.'}), 400
    if vol['status'] != 'Available':
        return jsonify({'error': f"Volunteer is currently '{vol['status']}' and cannot be assigned."}), 400
    if conn.execute("SELECT 1 FROM volunteer_tasks WHERE volunteer_id=? AND status IN ('Assigned','Accepted','In Progress','Submitted for Review','Needs Correction')",(id,)).fetchone(): return jsonify({'error':'Volunteer already has an active task.'}),409

    with conn:
        conn.execute("UPDATE volunteers SET status = 'On task' WHERE id = ?", (id,))
        conn.execute('''
            INSERT INTO activities (workspace_key, title, details)
            VALUES ('volunteers', ?, ?)
        ''', (f"Field Task Assigned: {vol['name']}", f"Deployed to {vol['zone']} for active {vol['skill']} relief mission."))
        log_system_event(conn, 'volunteer_updated', {'id': id, 'name': vol['name'], 'status': 'On task'})

    return jsonify({'success': True, 'message': 'Volunteer assigned to active task.'})

@app.route('/api/volunteers/<int:id>/unassign', methods=['PATCH', 'POST'])
@login_required
def unassign_volunteer(id):
    user_role = session.get('role')
    user_name = session.get('name')
    conn = get_db()
    vol = conn.execute("SELECT id, name, skill, zone, status, user_id, owner_type, organization_id FROM volunteers WHERE id = ?", (id,)).fetchone()
    if not vol:
        return jsonify({'error': f'Volunteer with ID {id} not found'}), 404

    # Allow only an owner administrator, Government official, owning NGO coordinator, or the actual volunteer.
    if user_role == 'Government Official' and vol['owner_type']!='government':
        return jsonify({'error':'Volunteer is outside Government ownership.'}),403
    if user_role == 'NGO Coordinator':
        org=conn.execute("SELECT COALESCE(u.organization_id,(SELECT organization_id FROM organization_memberships WHERE user_id=u.id AND membership_role='Coordinator' AND status='Active' LIMIT 1)) FROM users u WHERE u.id=?",(session['user_id'],)).fetchone()
        if not org or vol['owner_type']!='ngo' or vol['organization_id']!=org[0]: return jsonify({'error':'Volunteer is outside this NGO ownership.'}),403
    if user_role not in ('Administrator','Government Official','NGO Coordinator') and not (user_role=='Volunteer' and vol['user_id']==session['user_id']):
        return jsonify({'error': 'Access denied. You do not have permission to unassign this volunteer.'}), 403
    if conn.execute("SELECT 1 FROM volunteer_tasks WHERE volunteer_id=? AND status IN ('Assigned','Accepted','In Progress','Submitted for Review','Needs Correction')",(id,)).fetchone():
        return jsonify({'error':'Complete or reassign the active task before marking this Volunteer available.'}),409

    with conn:
        conn.execute("UPDATE volunteers SET status = 'Available' WHERE id = ?", (id,))
        conn.execute('''
            INSERT INTO activities (workspace_key, title, details)
            VALUES ('volunteers', ?, ?)
        ''', (f"Field Handover: {vol['name']}", f"Task completed in {vol['zone']}. Responder is now Available."))
        log_system_event(conn, 'volunteer_updated', {'id': id, 'name': vol['name'], 'status': 'Available'})

    return jsonify({'success': True, 'message': 'Volunteer marked as available.'})

# ----------------- DISPATCHES & VEHICLES -----------------

@app.route('/api/dispatches', methods=['GET'])
@login_required
def get_dispatches():
    conn=get_db(); user_id=session.get('user_id'); role=session.get('role')
    base="SELECT d.*,w.name AS warehouse_name,w.lat AS pickup_lat,w.lng AS pickup_lng,r.lat AS destination_lat,r.lng AS destination_lng,r.area AS request_area,o.name AS owner_name FROM dispatches d LEFT JOIN warehouses w ON w.id=d.warehouse_id LEFT JOIN emergency_requests r ON r.id=d.request_id LEFT JOIN organizations o ON o.id=d.owner_organization_id"
    params=[]; where=''
    if role=='Driver':
        usr=conn.execute('SELECT organization_id FROM users WHERE id=?',(user_id,)).fetchone(); org_id=usr['organization_id'] if usr else None
        scope='ngo' if org_id else 'government'
        where=' WHERE d.driver_user_id=? AND d.owner_type=? AND d.owner_organization_id IS ?'; params=[user_id,scope,org_id]
    elif role=='Citizen':
        where=' WHERE d.request_id IN (SELECT id FROM emergency_requests WHERE requester_user_id=?)'; params=[user_id]
    elif role=='Government Official': where=" WHERE d.owner_type='government' AND d.owner_organization_id IS NULL"
    elif role=='NGO Coordinator':
        usr=conn.execute("SELECT COALESCE(u.organization_id,(SELECT organization_id FROM organization_memberships WHERE user_id=u.id AND membership_role='Coordinator' AND status='Active' LIMIT 1)) AS org FROM users u WHERE u.id=?",(user_id,)).fetchone(); org_id=usr['org'] if usr else None
        where=" WHERE d.owner_type='ngo' AND d.owner_organization_id=?"; params=[org_id]
    elif role=='Volunteer':
        where=" WHERE d.owner_type='ngo' AND EXISTS(SELECT 1 FROM volunteer_tasks t JOIN volunteers v ON v.id=t.volunteer_id WHERE t.dispatch_id=d.id AND v.user_id=? )"; params=[user_id]
    elif role not in ('Administrator',): return jsonify({'error':'Access denied.'}),403
    rows=conn.execute(base+where+' ORDER BY d.id ASC',params).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/dispatches/<id>/advance', methods=['PATCH', 'POST'])
@login_required
def advance_dispatch(id):
    user_role = session.get('role')
    user_name = session.get('name')
    user_id = session.get('user_id')

    # Role Authorization: Only Driver, Administrator, Government Official, NGO Coordinator allowed
    allowed_roles = ('Driver', 'Administrator', 'Government Official', 'NGO Coordinator')
    if user_role not in allowed_roles:
        return jsonify({'error': 'Access denied. You do not have permission to advance dispatches.'}), 403

    conn = get_db()
    curr = conn.execute("SELECT * FROM dispatches WHERE id = ?", (id,)).fetchone()
    if not curr:
        return jsonify({'error': 'Dispatch record not found'}), 404

    # If logged in as Driver, driver can only advance their own dispatch
    if user_role == 'Driver':
        if curr['driver_user_id'] and curr['driver_user_id'] != user_id:
            return jsonify({'error': 'You are not authorized to advance another driver\'s dispatch.'}), 403
        elif not curr['driver_user_id'] and user_name and user_name != curr['driver']:
            return jsonify({'error': 'You are not authorized to advance another driver\'s dispatch.'}), 403
        pending_decision=conn.execute("SELECT driver_decision FROM response_assignments WHERE dispatch_id=? AND driver_user_id=? ORDER BY id DESC LIMIT 1",(id,user_id)).fetchone()
        if pending_decision and pending_decision['driver_decision']!='Accepted':
            return jsonify({'error':'Accept this assigned dispatch before advancing the trip.','code':'DRIVER_ACCEPTANCE_PENDING'}),409

    elif user_role == 'Government Official' and not (curr['owner_type']=='government' and curr['owner_organization_id'] is None):
        return jsonify({'error':'Dispatch is outside Government ownership.'}),403
    elif user_role == 'NGO Coordinator':
        own=conn.execute("SELECT COALESCE(u.organization_id,(SELECT organization_id FROM organization_memberships WHERE user_id=u.id AND membership_role='Coordinator' AND status='Active' LIMIT 1)) FROM users u WHERE u.id=?",(user_id,)).fetchone()
        if not own or curr['owner_type']!='ngo' or curr['owner_organization_id']!=own[0]:
            return jsonify({'error':'Dispatch is outside this NGO ownership.'}),403
    current_status = curr['status']
    if current_status == 'Delivered':
        return jsonify({'error': 'Dispatch is already delivered and completed.'}), 400

    if current_status in ('Arrived', 'Delivered Pending Proof', 'Delivered Pending Confirmation', 'Needs Review', 'Proof Rejected'):
        return jsonify({
            'error': 'Dispatch is at destination. Submission and supervisor review of formal delivery proof are required to confirm delivery.',
            'code': 'PROOF_REQUIRED',
            'status': current_status
        }), 409

    if current_status == 'Loading':
        new_status = 'En route'
        new_eta = 'Not recorded'
        with conn:
            conn.execute("UPDATE dispatches SET status = ?, eta = ?, departed_at = COALESCE(departed_at, CURRENT_TIMESTAMP), updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, new_eta, id))
            # Synchronize linked emergency request to Dispatched
            if curr['request_id']:
                conn.execute("UPDATE emergency_requests SET status = 'Dispatched', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (curr['request_id'],))
            conn.execute('''
                INSERT INTO activities (workspace_key, title, details)
                VALUES ('dispatches', ?, ?)
            ''', (f"Transit Underway: {id}", f"Vehicle {curr['vehicle']} (Driver: {curr['driver']}) is now En route to {curr['destination']}."))
            log_system_event(conn, 'dispatch_advanced', {'id': id, 'status': new_status, 'request_id': curr['request_id']})
            log_system_event(conn, 'request_updated', {'id': curr['request_id'], 'status': 'Dispatched'})
    elif current_status == 'En route':
        new_status = 'Arrived'
        new_eta = 'Not recorded'
        with conn:
            conn.execute("UPDATE dispatches SET status = ?, eta = ?, arrived_at = COALESCE(arrived_at, CURRENT_TIMESTAMP), updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, new_eta, id))
            conn.execute("INSERT INTO activities (workspace_key, title, details) VALUES ('dispatches', ?, ?)", (f"Vehicle Arrived: {id}", f"Vehicle {curr['vehicle']} (Driver: {curr['driver']}) arrived at {curr['destination']}. Delivery proof and reviewer decision are required."))
            log_system_event(conn, 'dispatch_advanced', {'id': id, 'status': new_status, 'request_id': curr['request_id']})
    else:
        return jsonify({'error': f'Invalid current dispatch status transition from {current_status}'}), 400

    updated = conn.execute("SELECT * FROM dispatches WHERE id = ?", (id,)).fetchone()
    return jsonify(dict(updated))

# ----------------- SHELTERS -----------------

@app.route('/api/shelters', methods=['GET'])
@login_required
def get_shelters():
    conn=get_db(); role=session.get('role'); user_id=session.get('user_id'); where=''; params=[]
    if role=='Government Official': where=" WHERE owner_type='government' AND owner_organization_id IS NULL"
    elif role=='NGO Coordinator':
        org=conn.execute("SELECT COALESCE(u.organization_id,(SELECT organization_id FROM organization_memberships WHERE user_id=u.id AND membership_role='Coordinator' AND status='Active' LIMIT 1)) FROM users u WHERE u.id=?",(user_id,)).fetchone(); where=" WHERE owner_type='ngo' AND owner_organization_id=?"; params=[org[0] if org else None]
    elif role=='Driver':
        org=conn.execute('SELECT organization_id FROM users WHERE id=?',(user_id,)).fetchone(); scope='ngo' if org and org[0] else 'government'; where=' WHERE owner_type=? AND owner_organization_id IS ?'; params=[scope,org[0] if org else None]
    elif role not in ('Administrator','Citizen','Volunteer'): return jsonify({'error':'Access denied.'}),403
    rows=conn.execute('SELECT * FROM shelters'+where+' ORDER BY id ASC',params).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/shelters', methods=['POST'])
@roles_required('Administrator','Government Official','NGO Coordinator')
def create_shelter():
    conn=get_db();data=request.get_json(silent=True) or {};role=session['role']
    name=(data.get('name') or '').strip();address=(data.get('address') or '').strip();district=(data.get('district') or '').strip()
    if not name or not address or not district:return jsonify({'error':'Shelter name, district and address are required.'}),400
    def whole(value,default=None):
        if value is None and default is not None:return default
        if isinstance(value,bool) or isinstance(value,float):raise ValueError()
        return int(value)
    try:capacity=whole(data.get('capacity'));occupants=whole(data.get('occupants'),0)
    except (ValueError,TypeError):return jsonify({'error':'Capacity and occupancy must be whole numbers.'}),400
    if capacity<=0 or occupants<0 or occupants>capacity:return jsonify({'error':'Capacity must be positive and occupancy must be between zero and capacity.'}),400
    if role=='NGO Coordinator':
        org=conn.execute("SELECT COALESCE(u.organization_id,(SELECT organization_id FROM organization_memberships WHERE user_id=u.id AND membership_role='Coordinator' AND status='Active' LIMIT 1)) FROM users u WHERE u.id=?",(session['user_id'],)).fetchone();owner='ngo';org_id=org[0] if org else None
        if not org_id or not conn.execute("SELECT 1 FROM organizations WHERE id=? AND status='Approved'",(org_id,)).fetchone():return jsonify({'error':'Approved NGO ownership is required.'}),403
    elif role=='Government Official':owner='government';org_id=None
    else:
        owner=(data.get('owner_type') or 'government').lower();org_raw=data.get('owner_organization_id')
        if owner=='ngo':
            try:org_id=int(org_raw)
            except (ValueError,TypeError):return jsonify({'error':'Approved NGO organization is required.'}),400
            if not conn.execute("SELECT 1 FROM organizations WHERE id=? AND status='Approved'",(org_id,)).fetchone():return jsonify({'error':'NGO is not approved.'}),400
        elif owner=='government':org_id=None
        else:return jsonify({'error':'Owner must be Government or NGO.'}),400
    status='Near capacity' if occupants/capacity>=.9 else 'Operational'
    lat=data.get('lat');lng=data.get('lng')
    try:
        if (lat is None)!=(lng is None):raise ValueError()
        lat=float(lat) if lat is not None else None;lng=float(lng) if lng is not None else None
        if lat is not None and not(-90<=lat<=90 and -180<=lng<=180):raise ValueError()
    except (TypeError,ValueError):return jsonify({'error':'Coordinates must be a valid latitude/longitude pair.'}),400
    with conn:
        cur=conn.execute("INSERT INTO shelters(name,occupants,capacity,status,district,address,lat,lng,owner_type,owner_organization_id,created_by_user_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(name,occupants,capacity,status,district,address,lat,lng,owner,org_id,session['user_id']));sid=cur.lastrowid
        log_audit_event(conn,session['user_id'],'CREATE_SHELTER','shelters',sid,new_state={'owner_type':owner,'organization_id':org_id,'capacity':capacity})
        log_system_event(conn,'shelter_created',{'id':sid,'owner_type':owner,'organization_id':org_id})
    return jsonify(dict(conn.execute('SELECT * FROM shelters WHERE id=?',(sid,)).fetchone())),201

@app.route('/api/shelters/<int:id>', methods=['PATCH', 'PUT'])
@roles_required('Administrator', 'Government Official', 'NGO Coordinator')
def update_shelter(id):
    conn = get_db()
    shelter = conn.execute("SELECT * FROM shelters WHERE id = ?", (id,)).fetchone()
    if not shelter:
        return jsonify({'error': f'Shelter with ID {id} not found'}), 404
    role=session.get('role'); user_id=session.get('user_id')
    if role=='Government Official' and not (shelter['owner_type']=='government' and shelter['owner_organization_id'] is None): return jsonify({'error':'Shelter is outside Government ownership.'}),403
    if role=='NGO Coordinator':
        org=conn.execute("SELECT COALESCE(u.organization_id,(SELECT organization_id FROM organization_memberships WHERE user_id=u.id AND membership_role='Coordinator' AND status='Active' LIMIT 1)) FROM users u WHERE u.id=?",(user_id,)).fetchone()
        if shelter['owner_type']!='ngo' or not org or shelter['owner_organization_id']!=org[0]: return jsonify({'error':'Shelter is outside this NGO ownership.'}),403

    data = request.get_json(silent=True) or {}
    occupants_raw = data.get('occupants') if data.get('occupants') is not None else shelter['occupants']
    capacity_raw = data.get('capacity') if data.get('capacity') is not None else shelter['capacity']

    if isinstance(occupants_raw, bool) or isinstance(capacity_raw, bool) or isinstance(occupants_raw, float) or isinstance(capacity_raw, float):
        return jsonify({'error': 'Occupants and capacity must be whole integers.'}), 400

    try:
        occupants = int(occupants_raw)
        capacity = int(capacity_raw)
        if occupants < 0 or capacity <= 0:
            return jsonify({'error': 'Occupants must be >= 0 and capacity must be > 0.'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Occupants and capacity must be valid integers.'}), 400

    pct = occupants / capacity
    status = 'Near capacity' if pct >= 0.9 else 'Operational'

    with conn:
        conn.execute("UPDATE shelters SET occupants = ?, capacity = ?, status = ? WHERE id = ?", (occupants, capacity, status, id))
        conn.execute('''
            INSERT INTO activities (workspace_key, title, details)
            VALUES ('shelters', ?, ?)
        ''', (f"Shelter Headcount: {shelter['name']}", f"Verified occupancy at {occupants}/{capacity} beds ({round(pct*100)}%). Status: {status}."))
        log_system_event(conn, 'shelter_updated', {'id': id, 'occupants': occupants, 'capacity': capacity, 'status': status})

    updated = conn.execute("SELECT * FROM shelters WHERE id = ?", (id,)).fetchone()
    return jsonify(dict(updated))

# ----------------- FUNDS & BUDGET -----------------

@app.route('/api/funds', methods=['GET'])
@roles_required('Administrator', 'Government Official', 'NGO Coordinator')
def get_funds():
    conn=get_db();role=session['role'];where='';params=[]
    if role=='NGO Coordinator':
        org=conn.execute("SELECT COALESCE(u.organization_id,(SELECT organization_id FROM organization_memberships WHERE user_id=u.id AND membership_role='Coordinator' AND status='Active' LIMIT 1)) FROM users u WHERE u.id=?",(session['user_id'],)).fetchone()
        if not org or not org[0]:return jsonify({'error':'NGO ownership is not configured.'}),403
        where=' AND organization_id=?';params=[org[0]]
    elif role=='Government Official':where=' AND organization_id IS NULL'
    budget=conn.execute("SELECT COALESCE(SUM(budget_amount_paise),0) FROM fund_budgets WHERE status='Approved'"+where,params).fetchone()[0]
    tx_where=where
    spent=conn.execute("SELECT COALESCE(SUM(CASE WHEN transaction_type='Refund' THEN -amount_paise ELSE amount_paise END),0) FROM fund_transactions WHERE transaction_type IN ('Payment','Refund') AND status='Completed'"+tx_where,params).fetchone()[0]
    committed=conn.execute("SELECT COALESCE(SUM(amount_paise),0) FROM fund_transactions WHERE transaction_type='Commitment' AND status='Completed'"+tx_where,params).fetchone()[0]
    cats=conn.execute("SELECT category,SUM(budget_amount_paise) AS allocated_paise FROM fund_budgets WHERE status='Approved'"+where+" GROUP BY category ORDER BY category",params).fetchall()
    trans_budget=conn.execute("SELECT COALESCE(SUM(budget_amount_paise),0) FROM fund_budgets WHERE status='Approved' AND (category LIKE '%Logistics%' OR category LIKE '%Transport%')"+where,params).fetchone()[0]
    med_budget=conn.execute("SELECT COALESCE(SUM(budget_amount_paise),0) FROM fund_budgets WHERE status='Approved' AND category LIKE '%Medical%'"+where,params).fetchone()[0]
    trans_spent=conn.execute("SELECT COALESCE(SUM(amount_paise),0) FROM fund_transactions WHERE transaction_type='Payment' AND status='Completed' AND (reason LIKE '%Logistics%' OR reason LIKE '%Transport%' OR reference_code LIKE '%FUEL%')"+tx_where,params).fetchone()[0]
    med_spent=conn.execute("SELECT COALESCE(SUM(amount_paise),0) FROM fund_transactions WHERE transaction_type='Payment' AND status='Completed' AND (reason LIKE '%Medical%' OR reference_code LIKE '%MED%')"+tx_where,params).fetchone()[0]
    def fmt(paise):
        rupees=paise/100
        return f'\u20B9{rupees/100000:.1f}L' if rupees>=100000 else f'\u20B9{rupees:,.0f}'
    category_rows=[dict(x) for x in cats]
    for item in category_rows:item['percentage']=round(item['allocated_paise']*100/budget) if budget else 0
    if budget and category_rows:
        category_rows[-1]['percentage']+=100-sum(item['percentage'] for item in category_rows)
    return jsonify({'categories':category_rows,'totalAllocated':fmt(budget),'totalUtilized':fmt(spent),'remainingBalance':fmt(max(0,budget-committed)),'totalAllocatedPaise':budget,'totalUtilizedPaise':spent,'remainingBalancePaise':max(0,budget-committed),'totalCommittedPaise':committed,'transportUsedPct':round(trans_spent*100/trans_budget) if trans_budget else 0,'medicalUsedPct':round(med_spent*100/med_budget) if med_budget else 0})

# ----------------- WORKSPACE ACTIVITIES & LOGS -----------------

@app.route('/api/workspace-activity', methods=['GET', 'POST'])
@login_required
def workspace_activity():
    conn = get_db()
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        key = (data.get('key') or 'general').strip()
        title = (data.get('title') or 'Action').strip()
        details = (data.get('details') or '').strip()

        if not title:
            return jsonify({'error': 'Title is required'}), 400

        with conn:
            conn.execute('INSERT INTO activities (workspace_key, title, details) VALUES (?, ?, ?)', (key, title, details))
            log_system_event(conn, 'activity_logged', {'key': key, 'title': title})

        return jsonify({'success': True})
    else:
        key = (request.args.get('key') or '').strip()
        if key:
            rows = conn.execute('SELECT * FROM activities WHERE workspace_key = ? ORDER BY id DESC LIMIT 50', (key,)).fetchall()
        else:
            rows = conn.execute('SELECT * FROM activities ORDER BY id DESC LIMIT 50').fetchall()
        return jsonify([dict(r) for r in rows])

# ----------------- REAL-TIME EVENT STREAMING (SSE & POLLING) -----------------

@app.route('/api/events/stream', methods=['GET'])
@login_required
def events_stream():
    """
    Server-Sent Events (SSE) endpoint.
    Streams real-time system events from SQLite system_events table.
    Supports 'Last-Event-ID' header or 'since_id' query param.
    Keeps alive with periodic comments (: heartbeat).
    """
    since_param = request.args.get('since_id')
    header_id = request.headers.get('Last-Event-ID')
    start_id = 0
    if since_param and since_param.isdigit():
        start_id = int(since_param)
    elif header_id and header_id.isdigit():
        start_id = int(header_id)
    else:
        try:
            db_init = database.get_db()
            row = db_init.execute("SELECT MAX(id) FROM system_events").fetchone()
            start_id = row[0] or 0
            db_init.close()
        except Exception:
            start_id = 0

    def event_generator(cursor_id):
        last_id = cursor_id
        yield f"id: {last_id}\nevent: connected\ndata: {{\"status\": \"connected\", \"last_id\": {last_id}}}\n\n"

        heartbeat_counter = 0
        while True:
            time.sleep(1.0)
            heartbeat_counter += 1
            try:
                db = database.get_db()
                new_events = db.execute(
                    "SELECT id, event_type, payload, created_at FROM system_events WHERE id > ? ORDER BY id ASC LIMIT 25",
                    (last_id,)
                ).fetchall()
                db.close()

                if new_events:
                    for ev in new_events:
                        last_id = ev['id']
                        data_str = json.dumps({'id': ev['id'], 'event_type': ev['event_type']})
                        yield f"id: {last_id}\nevent: {ev['event_type']}\ndata: {data_str}\n\n"
                    heartbeat_counter = 0
                elif heartbeat_counter >= 15:
                    yield ": heartbeat\n\n"
                    heartbeat_counter = 0
            except GeneratorExit:
                break
            except Exception:
                time.sleep(2.0)

    response = Response(event_generator(start_id), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Connection'] = 'keep-alive'
    return response

@app.route('/api/events/poll', methods=['GET'])
@login_required
def events_poll():
    """
    Polling fallback endpoint for environments where EventSource is blocked or reconnecting.
    """
    since_id = 0
    since_param = request.args.get('since_id') or request.args.get('since')
    if since_param and str(since_param).isdigit():
        since_id = int(since_param)

    conn = get_db()
    rows = conn.execute(
        "SELECT id, event_type, payload, created_at FROM system_events WHERE id > ? ORDER BY id ASC LIMIT 50",
        (since_id,)
    ).fetchall()

    latest_row = conn.execute("SELECT MAX(id) FROM system_events").fetchone()
    latest_id = latest_row[0] or since_id

    events = []
    user_role = session.get('role')
    user_id = session.get('user_id')
    user_name = session.get('name')

    for r in rows:
        payload_obj = {}

        # Redact requester PII for citizens if not own request
        if user_role == 'Citizen' and 'requester_name' in payload_obj:
            if payload_obj.get('requester_name') != user_name:
                payload_obj['requester_name'] = 'Confidential'
                if 'address' in payload_obj:
                    payload_obj['address'] = payload_obj.get('area', '')

        events.append({
            'id': r['id'],
            'event_type': r['event_type'],
            'payload': payload_obj,
            'created_at': r['created_at']
        })

    return jsonify({
        'events': events,
        'latest_id': latest_id,
        'last_id': latest_id
    })

# ----------------- CSV EXPORTS (WITH INJECTION DEFENSE & AUTH) -----------------

@app.route('/api/export/<dataset>.csv', methods=['GET'])
@login_required
def export_csv(dataset):
    user_role = session.get('role')
    # Sensitive staff, inventory, and dispatch data restricted to authorized staff/responders
    if user_role == 'Citizen' and dataset in ('inventory', 'volunteers', 'dispatches'):
        return jsonify({'error': 'Access denied. You do not have permission to export operational datasets.'}), 403

    conn = get_db()
    output = io.StringIO()
    # Write UTF-8 BOM so Excel on Windows correctly decodes Unicode & accented text
    output.write('\ufeff')
    writer = csv.writer(output)

    if dataset == 'requests':
        writer.writerow(['Request ID', 'Requester Name', 'Area', 'Address', 'Need', 'People', 'Vulnerable', 'Priority Score', 'Status', 'Time'])
        if user_role == 'Citizen':
            rows = conn.execute("SELECT id, requester_name, area, address, need, people_affected, vulnerable_people, priority_score, status, time_str FROM emergency_requests WHERE requester_user_id = ? ORDER BY priority_score DESC", (session.get('user_id'),)).fetchall()
        else:
            rows = conn.execute("SELECT id, requester_name, area, address, need, people_affected, vulnerable_people, priority_score, status, time_str FROM emergency_requests ORDER BY priority_score DESC").fetchall()
        for r in rows:
            writer.writerow([
                sanitize_csv_cell(r['id']),
                sanitize_csv_cell(r['requester_name']),
                sanitize_csv_cell(r['area']),
                sanitize_csv_cell(r['address']),
                sanitize_csv_cell(r['need']),
                r['people_affected'],
                'Yes' if r['vulnerable_people'] else 'No',
                r['priority_score'],
                sanitize_csv_cell(r['status']),
                sanitize_csv_cell(r['time_str'])
            ])
        filename = 'drras_emergency_requests.csv'

    elif dataset == 'inventory':
        writer.writerow(['Resource Name', 'Available Units', 'Target Stock', 'Warehouse', 'Status'])
        role=session.get('role'); user_id=session.get('user_id'); scope_sql=''; params=[]
        if role == 'Government Official':
            scope_sql="WHERE w.owner_type='government' AND w.owner_organization_id IS NULL"
        elif role == 'NGO Coordinator':
            org=conn.execute("SELECT COALESCE(u.organization_id,(SELECT organization_id FROM organization_memberships WHERE user_id=u.id AND membership_role='Coordinator' AND status='Active' LIMIT 1)) FROM users u WHERE u.id=?",(user_id,)).fetchone()
            scope_sql="WHERE w.owner_type='ngo' AND w.owner_organization_id=?"; params=[org[0] if org else None]
        elif role not in ('Administrator','Government Official','NGO Coordinator'):
            return jsonify({'error':'Access denied. You do not have permission to export inventory.'}),403
        rows = conn.execute(f"""SELECT r.name AS resource_name,MAX(0,ws.on_hand_units-ws.reserved_units) AS available_units,
            ws.target_stock,w.name AS warehouse_name FROM warehouse_stock ws
            JOIN warehouses w ON w.id=ws.warehouse_id JOIN resources r ON r.id=ws.resource_id
            {scope_sql} ORDER BY w.name,r.name""",params).fetchall()
        for r in rows:
            writer.writerow([
                sanitize_csv_cell(r['resource_name']),
                r['available_units'],
                r['target_stock'],
                sanitize_csv_cell(r['warehouse_name']),
                sanitize_csv_cell(calc_inventory_status(r['available_units'],r['target_stock']))
            ])
        filename = 'drras_inventory_stock.csv'

    elif dataset == 'volunteers':
        writer.writerow(['Initials', 'Name', 'Skill', 'Zone', 'Status'])
        rows = conn.execute("SELECT initials, name, skill, zone, status FROM volunteers").fetchall()
        for r in rows:
            writer.writerow([
                sanitize_csv_cell(r['initials']),
                sanitize_csv_cell(r['name']),
                sanitize_csv_cell(r['skill']),
                sanitize_csv_cell(r['zone']),
                sanitize_csv_cell(r['status'])
            ])
        filename = 'drras_volunteers.csv'

    elif dataset == 'dispatches':
        writer.writerow(['Dispatch ID', 'Vehicle', 'Driver', 'Destination', 'Load', 'Status', 'ETA', 'Linked Request'])
        rows = conn.execute("SELECT id, vehicle, driver, destination, load_items, status, eta, request_id FROM dispatches").fetchall()
        for r in rows:
            writer.writerow([
                sanitize_csv_cell(r['id']),
                sanitize_csv_cell(r['vehicle']),
                sanitize_csv_cell(r['driver']),
                sanitize_csv_cell(r['destination']),
                sanitize_csv_cell(r['load_items']),
                sanitize_csv_cell(r['status']),
                sanitize_csv_cell(r['eta']),
                sanitize_csv_cell(r['request_id'])
            ])
        filename = 'drras_dispatches.csv'

    else:
        return jsonify({'error': 'Unknown dataset'}), 400

    output.seek(0)
    return Response(
        output.getvalue().encode('utf-8'),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1')
    print(f"===========================================================")
    print(" DRRAS - Disaster Relief Resource Allocation System")
    print(f" Python Flask + SQLite + Vanilla JS Engine")
    print(f" Serving live at: http://127.0.0.1:{port}")
    print(f"===========================================================")
    print(f' DRRAS serving on 0.0.0.0:{port}', flush=True)
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
