"""
DRRAS Extended API Blueprint
Implements the comprehensive disaster response API catalog:
- Incidents & Zones
- Zone Adoptions
- Request Verification & Extended Lifecycle
- Resources & Warehouses
- In-Kind & Cash Donations
- Volunteer Tasks & Checkpoints
- Vehicles & Dispatches (Proof, Route Blockage, Rerouting)
- Shelter Admissions & Transfers
- Financial Budgets, Requests & Ledger Transactions
- Public Advisories & Inter-Agency Requests
- In-App Notifications & Audit Logs
"""

import csv
import io
import json
import os
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Blueprint, request, jsonify, session, Response, g
from werkzeug.security import generate_password_hash, check_password_hash
import database
import services
from services import BusinessLogicError

api_bp = Blueprint('api_extended', __name__)

def get_db():
    if 'db' not in g:
        g.db = database.get_db()
    return g.db

def current_ngo_id(conn=None, user_id=None, require_approved=True):
    conn = conn or get_db()
    user_id = user_id or session.get('user_id')
    row = conn.execute("""SELECT COALESCE(u.organization_id, (
        SELECT om.organization_id FROM organization_memberships om
        WHERE om.user_id=u.id AND om.status='Active' AND om.membership_role='Coordinator'
        ORDER BY om.id LIMIT 1)) AS organization_id
        FROM users u WHERE u.id=? AND u.role='NGO Coordinator'""", (user_id,)).fetchone()
    org_id = row['organization_id'] if row else None
    if not org_id:
        raise BusinessLogicError('This NGO account is not linked to an organization.', code='NGO_SCOPE_REQUIRED', status_code=403)
    if require_approved and not conn.execute("SELECT 1 FROM organizations WHERE id=? AND status='Approved'", (org_id,)).fetchone():
        raise BusinessLogicError('The NGO organization is not approved for operations.', code='NGO_NOT_APPROVED', status_code=403)
    return org_id


def user_scope(conn=None, user_id=None, role=None):
    conn = conn or get_db()
    user_id = user_id or session.get('user_id')
    role = role or session.get('role')
    if role == 'NGO Coordinator':
        return ('ngo', current_ngo_id(conn, user_id))
    if role == 'Driver':
        row = conn.execute("SELECT organization_id FROM users WHERE id=?", (user_id,)).fetchone()
        return ('ngo', row['organization_id']) if row and row['organization_id'] else ('government', None)
    if role in ('Government Official', 'Volunteer'):
        return ('government' if role == 'Government Official' else 'unassigned', None)
    return (None, None)


def is_available_driver(conn, driver_id, owner_type, organization_id=None, request_id=None):
    user = conn.execute("SELECT id, status, role, organization_id FROM users WHERE id=?", (driver_id,)).fetchone()
    if not user or user['role'] != 'Driver' or user['status'] != 'ACTIVE':
        return False
    if owner_type == 'government':
        if user['organization_id'] is not None or not conn.execute("SELECT 1 FROM government_driver_approvals WHERE user_id=?", (driver_id,)).fetchone():
            return False
    elif owner_type == 'ngo':
        org_match = user['organization_id'] == organization_id or conn.execute("SELECT 1 FROM organization_memberships WHERE user_id=? AND organization_id=? AND membership_role='Driver' AND status='Active'", (driver_id, organization_id)).fetchone()
        if not org_match or not conn.execute("SELECT 1 FROM ngo_personnel_approvals WHERE user_id=? AND organization_id=? AND personnel_type='Driver' AND decision='Approved'", (driver_id, organization_id)).fetchone():
            return False
    active = conn.execute("""SELECT 1 FROM dispatches d WHERE d.driver_user_id=?
        AND d.status IN ('Loading','Ready','En route','Arrived','Delivered Pending Proof','Delivered Pending Confirmation','Needs Review','Proof Rejected')
        AND (? IS NULL OR d.request_id<>?) LIMIT 1""", (driver_id, request_id, request_id)).fetchone()
    assigned = conn.execute("""SELECT 1 FROM response_assignments a WHERE a.driver_user_id=?
        AND a.status IN ('Assigned','Active') AND (? IS NULL OR a.request_id<>?) LIMIT 1""", (driver_id, request_id, request_id)).fetchone()
    return not active and not assigned

def dispatch_scope_required(f):
    @wraps(f)
    def decorated(dispatch_id,*args,**kwargs):
        conn=get_db(); user_id=session.get('user_id'); role=session.get('role')
        row=conn.execute("SELECT d.*,r.requester_user_id FROM dispatches d LEFT JOIN emergency_requests r ON r.id=d.request_id WHERE d.id=?",(dispatch_id,)).fetchone()
        if not row: return jsonify({'error':'Dispatch record not found.'}),404
        allowed=False
        if role=='Administrator': allowed=True
        elif role=='Government Official': allowed=row['owner_type']=='government' and row['owner_organization_id'] is None
        elif role=='NGO Coordinator':
            try: org_id=current_ngo_id(conn,user_id)
            except BusinessLogicError as e: return jsonify({'error':e.message,'code':e.code}),e.status_code
            allowed=row['owner_type']=='ngo' and row['owner_organization_id']==org_id
        elif role=='Driver':
            u=conn.execute('SELECT organization_id FROM users WHERE id=?',(user_id,)).fetchone(); org_id=u[0] if u else None; scope='ngo' if org_id else 'government'
            allowed=row['driver_user_id']==user_id and row['owner_type']==scope and row['owner_organization_id']==org_id
        elif role=='Citizen': allowed=row['requester_user_id']==user_id
        elif role=='Volunteer': allowed=bool(conn.execute("SELECT 1 FROM volunteer_tasks t JOIN volunteers v ON v.id=t.volunteer_id WHERE t.dispatch_id=? AND v.user_id=?",(dispatch_id,user_id)).fetchone())
        if not allowed: return jsonify({'error':'Dispatch is outside your assigned owner scope.'}),403
        return f(dispatch_id,*args,**kwargs)
    return decorated

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

# =========================================================================
# OWNER-SCOPED PERSONNEL MANAGEMENT
# =========================================================================

@api_bp.route('/api/organizations/public', methods=['GET'])
def public_approved_organizations():
    conn=get_db()
    rows=conn.execute("SELECT id,name FROM organizations WHERE organization_type='NGO' AND status='Approved' ORDER BY name").fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/demo-accounts', methods=['GET'])
def demo_login_accounts():
    mode=(os.environ.get('DRRAS_DEMO_MODE') or '').strip().lower()
    production=(os.environ.get('DRRAS_ENV') or os.environ.get('FLASK_ENV') or '').strip().lower()=='production'
    # Never publish demo credentials in production. Outside production this
    # endpoint is disabled unless a developer explicitly opts in.
    enabled=(mode in ('1','true','yes','on')) and not production
    if not enabled:return jsonify([])
    conn=get_db()
    specs=[
        ("Administrator",None,["admin123","adminDemo26!"],"Administrator", "1=1"),
        ("Government Official",None,["official123","govDemo26!"],"Government Official", "1=1"),
        ("NGO Coordinator",1,["ngo123","ngoDemo26!"],"NGO Coordinator", "EXISTS(SELECT 1 FROM organization_memberships m WHERE m.user_id=u.id AND m.organization_id=1 AND m.membership_role='Coordinator' AND m.status='Active')"),
        ("Citizen",None,["citizen123","citizenDemo26!"],"Citizen", "1=1"),
        ("Driver",None,["driver123","driveDemo26!"],"Government Driver", "u.organization_id IS NULL AND EXISTS(SELECT 1 FROM government_driver_approvals a WHERE a.user_id=u.id)"),
        ("Driver",1,["driver123","driveDemo26!"],"NGO Driver", "EXISTS(SELECT 1 FROM ngo_personnel_approvals a WHERE a.user_id=u.id AND a.organization_id=1 AND a.personnel_type='Driver' AND a.decision='Approved')"),
        ("Volunteer",None,["govvol123","respondDemo26!"],"Government Volunteer/Responder", "EXISTS(SELECT 1 FROM government_personnel gp JOIN volunteers v ON v.user_id=gp.user_id WHERE gp.user_id=u.id AND gp.status='Active' AND v.owner_type='government' AND v.organization_id IS NULL AND v.verified=1)"),
        ("Volunteer",1,["volunteer123","serveDemo26!"],"NGO Volunteer", "EXISTS(SELECT 1 FROM ngo_personnel_approvals a JOIN volunteers v ON v.user_id=a.user_id WHERE a.user_id=u.id AND a.organization_id=1 AND a.personnel_type='Volunteer' AND a.decision='Approved' AND v.owner_type='ngo' AND v.organization_id=a.organization_id AND v.verified=1)")
    ]
    result=[]
    for role,org_id,passwords,label,where in specs:
        matches=conn.execute(f"SELECT u.id,u.name,u.email,u.role,u.status,u.organization_id,u.password AS password_hash FROM users u WHERE u.role=? AND u.status='ACTIVE' AND {where} ORDER BY u.id",(role,)).fetchall()
        match=next(((row,password) for row in matches for password in passwords if check_password_hash(row['password_hash'],password)),None)
        if match:
            row,password=match
            result.append({'id':row['id'],'name':row['name'],'email':row['email'],'password':password,'role':row['role'],'organization_id':org_id,'label':label,'demo':True})
    return jsonify(result)

@api_bp.route('/api/ngo/personnel', methods=['GET'])
@roles_required('NGO Coordinator')
def ngo_personnel_list():
    conn=get_db()
    try: org_id=current_ngo_id(conn)
    except BusinessLogicError as e: return jsonify({'error':e.message,'code':e.code}),e.status_code
    users=conn.execute("""SELECT u.id,u.name,u.email,u.role,u.status,m.membership_role,
        a.decision AS approval_status,a.decided_at,a.reason
        FROM users u LEFT JOIN organization_memberships m ON m.user_id=u.id AND m.organization_id=?
        LEFT JOIN ngo_personnel_approvals a ON a.user_id=u.id AND a.organization_id=?
        WHERE u.organization_id=? AND u.role IN ('Volunteer','Driver') ORDER BY u.role,u.name""",(org_id,org_id,org_id)).fetchall()
    roster=conn.execute("""SELECT id,name,skill,zone,status,verified,user_id FROM volunteers
        WHERE organization_id=? AND owner_type='ngo' ORDER BY name""",(org_id,)).fetchall()
    return jsonify({'organization_id':org_id,'accounts':[dict(r) for r in users],'volunteers':[dict(r) for r in roster]})

@api_bp.route('/api/ngo/volunteers', methods=['POST'])
@roles_required('NGO Coordinator')
def ngo_register_volunteer():
    conn=get_db(); data=request.get_json(silent=True) or {}
    try: org_id=current_ngo_id(conn)
    except BusinessLogicError as e: return jsonify({'error':e.message,'code':e.code}),e.status_code
    email=(data.get('email') or '').strip().lower(); name=(data.get('name') or '').strip(); password=data.get('password') or ''
    skill=(data.get('skill') or '').strip(); zone=(data.get('zone') or '').strip()
    if not email or not name or len(password)<8 or not skill or not zone: return jsonify({'error':'Name, email, password of at least 8 characters, skill and zone are required.'}),400
    if conn.execute("SELECT 1 FROM users WHERE LOWER(email)=?",(email,)).fetchone(): return jsonify({'error':'An account already exists with this email.'}),409
    initials=''.join(x[0].upper() for x in name.split() if x)[:2] or 'V'
    with conn:
        cur=conn.execute("INSERT INTO users(email,password,name,initials,role,status,organization_id) VALUES(?,?,?,?,'Volunteer','PENDING',?)",(email,generate_password_hash(password),name,initials,org_id))
        uid=cur.lastrowid
        conn.execute("INSERT INTO organization_memberships(organization_id,user_id,membership_role,status) VALUES(?,?,'Volunteer','Inactive')",(org_id,uid))
        database.log_audit_event(conn,session['user_id'],'REGISTER_NGO_VOLUNTEER','users',uid,new_state={'organization_id':org_id,'skill':skill,'zone':zone,'status':'PENDING'})
        database.log_system_event(conn,'ngo_personnel_pending',{'user_id':uid,'organization_id':org_id,'role':'Volunteer'})
    return jsonify({'id':uid,'name':name,'email':email,'role':'Volunteer','status':'PENDING','organization_id':org_id,'skill':skill,'zone':zone}),201

@api_bp.route('/api/ngo/drivers', methods=['POST'])
@roles_required('NGO Coordinator')
def ngo_register_driver():
    conn=get_db(); data=request.get_json(silent=True) or {}
    try: org_id=current_ngo_id(conn)
    except BusinessLogicError as e: return jsonify({'error':e.message,'code':e.code}),e.status_code
    email=(data.get('email') or '').strip().lower(); name=(data.get('name') or '').strip(); password=data.get('password') or ''
    if not email or not name or len(password)<8: return jsonify({'error':'Name, email, and a password of at least 8 characters are required.'}),400
    if conn.execute("SELECT 1 FROM users WHERE LOWER(email)=?",(email,)).fetchone(): return jsonify({'error':'An account already exists with this email.'}),409
    initials=''.join(x[0].upper() for x in name.split() if x)[:2] or 'D'
    with conn:
        cur=conn.execute("INSERT INTO users(email,password,name,initials,role,status,organization_id) VALUES(?,?,?,?,'Driver','PENDING',?)",(email,generate_password_hash(password),name,initials,org_id))
        uid=cur.lastrowid
        conn.execute("INSERT INTO organization_memberships(organization_id,user_id,membership_role,status) VALUES(?,?,'Driver','Inactive')",(org_id,uid))
        database.log_audit_event(conn,session['user_id'],'REGISTER_NGO_DRIVER','users',uid,new_state={'organization_id':org_id,'status':'PENDING'})
        database.log_system_event(conn,'ngo_personnel_pending',{'user_id':uid,'organization_id':org_id,'role':'Driver'})
    return jsonify({'id':uid,'name':name,'email':email,'role':'Driver','classification':'NGO Driver','status':'PENDING','organization_id':org_id}),201

@api_bp.route('/api/ngo/personnel/<int:user_id>/<decision>', methods=['POST'])
@roles_required('NGO Coordinator')
def ngo_decide_personnel(user_id,decision):
    if decision not in ('approve','reject'): return jsonify({'error':'Decision must be approve or reject.'}),400
    conn=get_db(); data=request.get_json(silent=True) or {}
    try: org_id=current_ngo_id(conn)
    except BusinessLogicError as e: return jsonify({'error':e.message,'code':e.code}),e.status_code
    user=conn.execute("SELECT * FROM users WHERE id=? AND organization_id=? AND role IN ('Volunteer','Driver')",(user_id,org_id)).fetchone()
    if not user: return jsonify({'error':'Personnel account is not owned by this NGO.'}),404
    if user['status']!='PENDING': return jsonify({'error':'Only a pending personnel account can be reviewed.'}),409
    ptype=user['role']; result='Approved' if decision=='approve' else 'Rejected'; status='ACTIVE' if decision=='approve' else 'REJECTED'; reason=(data.get('reason') or f'{result} by the owning NGO Coordinator').strip()
    try:
        with conn:
            conn.execute("INSERT INTO ngo_personnel_approvals(user_id,organization_id,personnel_type,decision,decided_by_user_id,reason) VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,organization_id,personnel_type) DO UPDATE SET decision=excluded.decision,decided_by_user_id=excluded.decided_by_user_id,decided_at=CURRENT_TIMESTAMP,reason=excluded.reason",(user_id,org_id,ptype,result,session['user_id'],reason))
            conn.execute("UPDATE users SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(status,user_id))
            conn.execute("UPDATE organization_memberships SET status=? WHERE user_id=? AND organization_id=?",('Active' if result=='Approved' else 'Inactive',user_id,org_id))
            if result=='Approved' and ptype=='Driver':
                conn.execute("INSERT OR IGNORE INTO organization_memberships(organization_id,user_id,membership_role,status) VALUES(?,?,'Driver','Active')",(org_id,user_id))
            if result=='Approved' and ptype=='Volunteer':
                existing=conn.execute("SELECT id FROM volunteers WHERE user_id=?",(user_id,)).fetchone()
                if not existing:
                    initials=''.join(x[0].upper() for x in user['name'].split() if x)[:2] or 'V'
                    conn.execute("INSERT INTO volunteers(initials,name,skill,zone,status,user_id,organization_id,verified,owner_type) VALUES(?,?,?,?,'Available',?,?,1,'ngo')",(initials,user['name'],(data.get('skill') or 'General Response').strip(),(data.get('zone') or 'Unassigned Zone').strip(),user_id,org_id))
            database.log_audit_event(conn,session['user_id'],f'{result.upper()}_NGO_{ptype.upper()}','users',user_id,old_state={'status':'PENDING'},new_state={'status':status,'organization_id':org_id},reason=reason)
            database.log_system_event(conn,'ngo_personnel_status_changed',{'user_id':user_id,'organization_id':org_id,'role':ptype,'status':status})
            database.create_notification(conn,user_id,'account_approved' if result=='Approved' else 'account_rejected',f'NGO {ptype} {result}',reason,'users',user_id)
        return jsonify({'user_id':user_id,'organization_id':org_id,'role':ptype,'status':status,'decision':result})
    except sqlite3.IntegrityError:
        return jsonify({'error':'Could not persist personnel review because its ownership link is invalid.'}),409

@api_bp.route('/api/government/drivers', methods=['POST'])
@roles_required('Administrator','Government Official')
def government_provision_driver():
    conn=get_db(); data=request.get_json(silent=True) or {}
    email=(data.get('email') or '').strip().lower(); name=(data.get('name') or '').strip(); password=data.get('password') or ''
    if not email or not name or len(password)<8: return jsonify({'error':'Name, email, and a password of at least 8 characters are required.'}),400
    if conn.execute("SELECT 1 FROM users WHERE LOWER(email)=?",(email,)).fetchone(): return jsonify({'error':'An account already exists with this email.'}),409
    initials=''.join(x[0].upper() for x in name.split() if x)[:2] or 'D'
    with conn:
        cur=conn.execute("INSERT INTO users(email,password,name,initials,role,status) VALUES(?,?,?,?,'Driver','ACTIVE')",(email,generate_password_hash(password),name,initials))
        uid=cur.lastrowid
        conn.execute("INSERT INTO government_driver_approvals(user_id,approved_by_user_id,reason) VALUES(?,?,?)",(uid,session['user_id'],(data.get('reason') or 'Provisioned by authorized Government administrator').strip()))
        database.log_audit_event(conn,session['user_id'],'PROVISION_GOVERNMENT_DRIVER','users',uid,new_state={'classification':'Government Driver','status':'ACTIVE'})
        database.log_system_event(conn,'government_driver_provisioned',{'user_id':uid})
    return jsonify({'id':uid,'name':name,'email':email,'classification':'Government Driver','status':'ACTIVE'}),201

@api_bp.route('/api/government/personnel', methods=['GET','POST'])
@roles_required('Administrator','Government Official')
def government_personnel_collection():
    conn=get_db()
    if request.method=='GET':
        return jsonify([dict(r) for r in conn.execute("SELECT p.* FROM government_personnel p ORDER BY p.category,p.name").fetchall()])
    data=request.get_json(silent=True) or {}; name=(data.get('name') or '').strip(); category=(data.get('category') or '').strip(); unit=(data.get('service_unit') or '').strip()
    if not name or not category or not unit: return jsonify({'error':'Name, category and service/unit are required.'}),400
    if category not in ('Police','Firefighter','Doctor / Paramedic','Search and Rescue','Civil Defence','Other Government Responder'): return jsonify({'error':'Choose a supported Government personnel category.'}),400
    with conn:
        cur=conn.execute("INSERT INTO government_personnel(name,category,service_unit,skills,status,incident_id,zone_id,created_by_user_id,approved_by_user_id,approved_at) VALUES(?,?,?,?, 'Active',?,?,?,?,CURRENT_TIMESTAMP)",(name,category,unit,(data.get('skills') or '').strip(),data.get('incident_id'),data.get('zone_id'),session['user_id'],session['user_id']))
        database.log_audit_event(conn,session['user_id'],'CREATE_GOVERNMENT_PERSONNEL','government_personnel',cur.lastrowid,new_state={'name':name,'category':category})
        database.log_system_event(conn,'government_personnel_updated',{'id':cur.lastrowid,'status':'Active'})
    return jsonify(dict(conn.execute("SELECT * FROM government_personnel WHERE id=?",(cur.lastrowid,)).fetchone())),201

# =========================================================================
# 1. USER ADMINISTRATION & AUDIT LOGS
# =========================================================================

@api_bp.route('/api/admin/users', methods=['GET'])
@roles_required('Administrator')
def list_users():
    conn = get_db()
    role_filter = request.args.get('role')
    status_filter = request.args.get('status')
    q = (request.args.get('q') or '').strip().lower()

    query = "SELECT id, email, name, initials, role, status, phone, organization_id, created_at, last_login_at, suspended_at, suspension_reason FROM users WHERE 1=1"
    params = []
    if role_filter:
        query += " AND role = ?"
        params.append(role_filter)
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    if q:
        query += " AND (LOWER(name) LIKE ? OR LOWER(email) LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])

    query += " ORDER BY id DESC"
    rows = conn.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/admin/users/<int:user_id>/approve', methods=['POST'])
@roles_required('Administrator')
def approve_user_by_id(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return jsonify({'error': f'User ID {user_id} not found'}), 404

    data = request.get_json(silent=True) or {}
    reason = data.get('reason') or 'Registration approved by Administrator'

    with conn:
        conn.execute("UPDATE users SET status = 'ACTIVE', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
        database.log_audit_event(conn, session['user_id'], 'APPROVE_USER', 'users', user_id,
                                 old_state={'status': user['status']}, new_state={'status': 'ACTIVE'}, reason=reason)
        database.create_notification(conn, user_id, 'account_approved', 'Account Approved', 'Your DRRAS access has been approved. You may now sign in and perform role operations.', 'users', user_id)
        database.log_system_event(conn, 'user_status_changed', {'id': user_id, 'email': user['email'], 'status': 'ACTIVE', 'role': user['role']})

    return jsonify({'success': True, 'message': f"Account for {user['email']} approved."})

@api_bp.route('/api/admin/users/<int:user_id>/reject', methods=['POST'])
@roles_required('Administrator')
def reject_user_by_id(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return jsonify({'error': f'User ID {user_id} not found'}), 404

    data = request.get_json(silent=True) or {}
    reason = data.get('reason') or 'Registration rejected by Administrator'

    with conn:
        conn.execute("UPDATE users SET status = 'REJECTED', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
        database.log_audit_event(conn, session['user_id'], 'REJECT_USER', 'users', user_id,
                                 old_state={'status': user['status']}, new_state={'status': 'REJECTED'}, reason=reason)
        database.log_system_event(conn, 'user_status_changed', {'id': user_id, 'email': user['email'], 'status': 'REJECTED', 'role': user['role']})

    return jsonify({'success': True, 'message': f"Account for {user['email']} rejected."})

@api_bp.route('/api/admin/users/<int:user_id>/suspend', methods=['POST'])
@roles_required('Administrator')
def suspend_user(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json(silent=True) or {}
    reason = data.get('reason') or 'Account suspended by Administrator'

    with conn:
        conn.execute("UPDATE users SET status = 'SUSPENDED', suspended_at = CURRENT_TIMESTAMP, suspension_reason = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (reason, user_id))
        database.log_audit_event(conn, session['user_id'], 'SUSPEND_USER', 'users', user_id,
                                 old_state={'status': user['status']}, new_state={'status': 'SUSPENDED'}, reason=reason)
        database.log_system_event(conn, 'user_status_changed', {'id': user_id, 'status': 'SUSPENDED'})

    return jsonify({'success': True, 'message': f"User {user['email']} suspended."})

@api_bp.route('/api/admin/users/<int:user_id>/reactivate', methods=['POST'])
@roles_required('Administrator')
def reactivate_user(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json(silent=True) or {}
    reason = data.get('reason') or 'Account reactivated by Administrator'

    with conn:
        conn.execute("UPDATE users SET status = 'ACTIVE', suspended_at = NULL, suspension_reason = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
        database.log_audit_event(conn, session['user_id'], 'REACTIVATE_USER', 'users', user_id,
                                 old_state={'status': user['status']}, new_state={'status': 'ACTIVE'}, reason=reason)
        database.log_system_event(conn, 'user_status_changed', {'id': user_id, 'status': 'ACTIVE'})

    return jsonify({'success': True, 'message': f"User {user['email']} reactivated."})

@api_bp.route('/api/admin/audit-logs', methods=['GET'])
@roles_required('Administrator')
def list_audit_logs():
    conn = get_db()
    entity_type = request.args.get('entity_type')
    action = request.args.get('action')
    actor_id = request.args.get('actor_user_id')

    query = '''
        SELECT a.id, a.actor_user_id, u.name as actor_name, u.role as actor_role, a.action, a.entity_type, a.entity_id,
               a.old_state_json, a.new_state_json, a.reason, a.request_id, a.created_at
        FROM audit_logs a
        LEFT JOIN users u ON a.actor_user_id = u.id
        WHERE 1=1
    '''
    params = []
    if entity_type:
        query += " AND a.entity_type = ?"
        params.append(entity_type)
    if action:
        query += " AND a.action = ?"
        params.append(action)
    if actor_id and str(actor_id).isdigit():
        query += " AND a.actor_user_id = ?"
        params.append(int(actor_id))

    query += " ORDER BY a.id DESC LIMIT 100"
    rows = conn.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])

# =========================================================================
# 2. INCIDENTS & ZONES
# =========================================================================

@api_bp.route('/api/incidents', methods=['GET'])
def get_incidents():
    conn = get_db()
    status_filter = request.args.get('status')
    query = "SELECT * FROM incidents WHERE 1=1"
    params = []
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/incidents', methods=['POST'])
@roles_required('Government Official')
def create_incident():
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    itype = (data.get('incident_type') or 'Flood').strip()
    severity = (data.get('severity') or 'Severe').strip()
    district = (data.get('district') or 'Demo District').strip()
    description = (data.get('description') or '').strip()

    if not title or not description:
        return jsonify({'error': 'Title and description are required.'}), 400

    conn = get_db()
    max_num_row = conn.execute("SELECT MAX(CAST(SUBSTR(id, 10) AS INTEGER)) FROM incidents").fetchone()
    next_num = (max_num_row[0] or 0) + 1
    inc_id = f"INC-2026-{next_num:03d}"

    user_id = session.get('user_id')
    with conn:
        conn.execute('''
            INSERT INTO incidents (id, title, incident_type, severity, description, district, status, command_officer_user_id, reported_at, activated_at, created_by_user_id)
            VALUES (?, ?, ?, ?, ?, ?, 'Active', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
        ''', (inc_id, title, itype, severity, description, district, user_id, user_id))

        database.log_audit_event(conn, user_id, 'CREATE_INCIDENT', 'incidents', inc_id,
                                 new_state={'title': title, 'status': 'Active', 'severity': severity})
        database.log_system_event(conn, 'incident_created', {'id': inc_id, 'title': title})

    created = conn.execute("SELECT * FROM incidents WHERE id = ?", (inc_id,)).fetchone()
    return jsonify(dict(created)), 201

@api_bp.route('/api/incidents/<incident_id>', methods=['GET'])
def get_incident_detail(incident_id):
    conn = get_db()
    inc = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
    if not inc:
        return jsonify({'error': 'Incident not found'}), 404
    zones = conn.execute("SELECT * FROM zones WHERE incident_id = ?", (incident_id,)).fetchall()
    res = dict(inc)
    res['zones'] = [dict(z) for z in zones]
    return jsonify(res)

@api_bp.route('/api/incidents/<incident_id>/activate', methods=['POST'])
@roles_required('Government Official')
def activate_incident(incident_id):
    conn = get_db()
    inc = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
    if not inc:
        return jsonify({'error': 'Incident not found'}), 404

    data = request.get_json(silent=True) or {}
    reason = data.get('reason') or 'Activated by Incident Command'
    with conn:
        conn.execute("UPDATE incidents SET status = 'Active', activated_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (incident_id,))
        database.log_audit_event(conn, session['user_id'], 'ACTIVATE_INCIDENT', 'incidents', incident_id, reason=reason)
        database.log_system_event(conn, 'incident_updated', {'id': incident_id, 'status': 'Active'})

    return jsonify(dict(conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()))

@api_bp.route('/api/incidents/<incident_id>/stabilize', methods=['POST'])
@roles_required('Government Official')
def stabilize_incident(incident_id):
    conn = get_db()
    data = request.get_json(silent=True) or {}
    reason = data.get('reason') or 'Stabilization phase initiated'
    with conn:
        conn.execute("UPDATE incidents SET status = 'Stabilizing', stabilized_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (incident_id,))
        database.log_audit_event(conn, session['user_id'], 'STABILIZE_INCIDENT', 'incidents', incident_id, reason=reason)
        database.log_system_event(conn, 'incident_updated', {'id': incident_id, 'status': 'Stabilizing'})
    return jsonify(dict(conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()))

@api_bp.route('/api/incidents/<incident_id>/close', methods=['POST'])
@roles_required('Government Official')
def close_incident(incident_id):
    conn = get_db()
    # Check open critical requests or active dispatches
    open_reqs = conn.execute("SELECT COUNT(*) FROM emergency_requests WHERE incident_id = ? AND status NOT IN ('Delivered', 'Closed', 'Rejected')", (incident_id,)).fetchone()[0]
    active_dsp = conn.execute("SELECT COUNT(*) FROM dispatches WHERE incident_id = ? AND status NOT IN ('Delivered', 'Cancelled')", (incident_id,)).fetchone()[0]

    data = request.get_json(silent=True) or {}
    override = data.get('override', False)
    reason = data.get('reason') or 'Incident operations successfully concluded'

    if (open_reqs > 0 or active_dsp > 0) and not override:
        return jsonify({
            'error': f'Cannot close incident: {open_reqs} open requests and {active_dsp} active dispatches remain. Use authorized override to force close.',
            'open_requests': open_reqs,
            'active_dispatches': active_dsp
        }), 409

    with conn:
        conn.execute("UPDATE incidents SET status = 'Closed', closed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (incident_id,))
        database.log_audit_event(conn, session['user_id'], 'CLOSE_INCIDENT', 'incidents', incident_id, reason=reason)
        database.log_system_event(conn, 'incident_updated', {'id': incident_id, 'status': 'Closed'})

    return jsonify(dict(conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()))

@api_bp.route('/api/incidents/<incident_id>/zones', methods=['GET'])
def get_incident_zones(incident_id):
    conn = get_db()
    rows = conn.execute("SELECT * FROM zones WHERE incident_id = ? ORDER BY id ASC", (incident_id,)).fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/incidents/<incident_id>/zones', methods=['POST'])
@roles_required('Government Official')
def create_zone(incident_id):
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    district = (data.get('district') or 'Demo District').strip()
    desc = data.get('description') or ''
    severity = data.get('severity') or 'High'
    lat = data.get('center_lat') or 30.90
    lng = data.get('center_lng') or 75.85

    if not name:
        return jsonify({'error': 'Zone name is required.'}), 400

    conn = get_db()
    max_z = conn.execute("SELECT MAX(CAST(SUBSTR(id, 3) AS INTEGER)) FROM zones").fetchone()
    next_z = (max_z[0] or 0) + 1
    zid = f"Z-{next_z:02d}"

    with conn:
        conn.execute('''
            INSERT INTO zones (id, incident_id, name, description, district, center_lat, center_lng, severity, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active')
        ''', (zid, incident_id, name, desc, district, lat, lng, severity))
        database.log_audit_event(conn, session['user_id'], 'CREATE_ZONE', 'zones', zid, new_state={'name': name, 'severity': severity})

    created = conn.execute("SELECT * FROM zones WHERE id = ?", (zid,)) .fetchone()
    return jsonify(dict(created)), 201

@api_bp.route('/api/admin/urgency-weights', methods=['GET'])
@roles_required('Administrator')
def get_urgency_weights():
    return jsonify({
        'base_urgency': 58,
        'vulnerability_bonus': 25,
        'population_bonus': 10,
        'population_threshold': 8,
        'critical_need_bonus': 10,
        'critical_needs': ['medical', 'rescue'],
        'min_score': 58,
        'max_score': 99
    })

@api_bp.route('/api/zones', methods=['GET'])
def get_all_zones():
    conn = get_db()
    rows = conn.execute("SELECT * FROM zones ORDER BY id ASC").fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/adoptions', methods=['GET'])
def get_all_adoptions():
    conn = get_db()
    status_filter = request.args.get('status')
    query = '''
        SELECT za.*, o.name as organization_name, z.name as zone_name
        FROM zone_adoptions za
        JOIN organizations o ON za.organization_id = o.id
        LEFT JOIN zones z ON za.zone_id = z.id
        WHERE 1=1
    '''
    params = []
    if status_filter:
        query += " AND za.status = ?"
        params.append(status_filter)
    query += " ORDER BY za.id DESC"
    rows = conn.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/zones/<zone_id>/adoptions', methods=['GET'])
def get_zone_adoptions(zone_id):
    conn = get_db()
    rows = conn.execute('''
        SELECT za.*, o.name as organization_name
        FROM zone_adoptions za
        JOIN organizations o ON za.organization_id = o.id
        WHERE za.zone_id = ?
        ORDER BY za.id DESC
    ''', (zone_id,)).fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/zones/<zone_id>/adoptions', methods=['POST'])
@roles_required('NGO Coordinator')
def request_zone_adoption(zone_id):
    data = request.get_json(silent=True) or {}
    user_id = session['user_id']
    conn = get_db()

    # Organization membership is established by approved account provisioning; never attach a user to an arbitrary NGO.
    try: org_id=current_ngo_id(conn,user_id)
    except BusinessLogicError as e: return jsonify({'error':e.message,'code':e.code}),e.status_code

    zone = conn.execute("SELECT incident_id FROM zones WHERE id = ?", (zone_id,)).fetchone()
    if not zone:
        return jsonify({'error': 'Zone not found'}), 404

    cap = data.get('requested_capacity') or 'Relief supply distribution & volunteer camps'
    vols = int(data.get('available_volunteers') or 10)
    res_summary = data.get('available_resource_summary') or 'Relief vans & dry rations'

    with conn:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO zone_adoptions (incident_id, zone_id, organization_id, requested_by_user_id, requested_capacity, available_volunteers, available_resource_summary, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Requested')
        ''', (zone['incident_id'], zone_id, org_id, user_id, cap, vols, res_summary))
        adp_id = cur.lastrowid
        database.log_audit_event(conn, user_id, 'REQUEST_ZONE_ADOPTION', 'zone_adoptions', adp_id, new_state={'zone_id': zone_id, 'organization_id': org_id})
        database.log_system_event(conn, 'adoption_requested', {'id': adp_id, 'zone_id': zone_id, 'organization_id': org_id})

    return jsonify({'id': adp_id, 'adoption_id': adp_id, 'status': 'Requested', 'success': True, 'message': 'Zone adoption request submitted for District Command review.'}), 201

@api_bp.route('/api/adoptions/<int:adoption_id>/approve', methods=['POST'])
@roles_required('Government Official')
def approve_zone_adoption(adoption_id):
    conn = get_db()
    adp = conn.execute("SELECT * FROM zone_adoptions WHERE id = ?", (adoption_id,)).fetchone()
    if not adp:
        return jsonify({'error': 'Adoption record not found'}), 404

    data = request.get_json(silent=True) or {}
    reason = data.get('reason') or 'Approved by District Command'

    with conn:
        conn.execute("UPDATE zone_adoptions SET status = 'Approved', reviewed_by_user_id = ?, reviewed_at = CURRENT_TIMESTAMP, decision_reason = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                     (session['user_id'], reason, adoption_id))
        database.log_audit_event(conn, session['user_id'], 'APPROVE_ADOPTION', 'zone_adoptions', adoption_id, reason=reason)
        database.create_notification(conn, adp['requested_by_user_id'], 'adoption_approved', 'Zone Adoption Approved', f"Your adoption of {adp['zone_id']} has been approved.", 'zone_adoptions', adoption_id)
        database.log_system_event(conn, 'adoption_approved', {'id': adoption_id, 'zone_id': adp['zone_id']})

    updated = conn.execute("SELECT * FROM zone_adoptions WHERE id = ?", (adoption_id,)).fetchone()
    res = dict(updated)
    res['success'] = True
    return jsonify(res)

@api_bp.route('/api/adoptions/<int:adoption_id>/reject', methods=['POST'])
@roles_required('Government Official')
def reject_zone_adoption(adoption_id):
    conn = get_db()
    data = request.get_json(silent=True) or {}
    reason = data.get('reason') or 'Rejected by District Command'
    with conn:
        conn.execute("UPDATE zone_adoptions SET status = 'Rejected', reviewed_by_user_id = ?, reviewed_at = CURRENT_TIMESTAMP, decision_reason = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                     (session['user_id'], reason, adoption_id))
        database.log_audit_event(conn, session['user_id'], 'REJECT_ADOPTION', 'zone_adoptions', adoption_id, reason=reason)

    updated = conn.execute("SELECT * FROM zone_adoptions WHERE id = ?", (adoption_id,)).fetchone()
    res = dict(updated)
    res['success'] = True
    return jsonify(res)

# =========================================================================
# 3. EMERGENCY REQUESTS EXTENDED LIFECYCLE
# =========================================================================

@api_bp.route('/api/requests/<request_id>', methods=['GET'])
@login_required
def get_request_detail(request_id):
    conn = get_db()
    req = conn.execute("SELECT * FROM emergency_requests WHERE id = ?", (request_id,)).fetchone()
    if not req:
        return jsonify({'error': 'Request not found'}), 404

    user_role = session.get('role')
    user_id = session.get('user_id')
    user_name = session.get('name')

    # Enforce request visibility using persisted ownership and coverage.
    if user_role == 'Citizen' and req['requester_user_id'] != user_id:
        return jsonify({'error': 'Access denied. You can only view your own emergency requests.'}), 403
    if user_role == 'NGO Coordinator':
        try: current_ngo_id(conn,user_id)
        except BusinessLogicError as e:return jsonify({'error':e.message,'code':e.code}),e.status_code
    elif user_role == 'Driver':
        if not conn.execute('SELECT 1 FROM dispatches WHERE request_id=? AND driver_user_id=?',(request_id,user_id)).fetchone():return jsonify({'error':'Request is outside your assigned dispatches.'}),403
    elif user_role == 'Volunteer':
        if not conn.execute('SELECT 1 FROM volunteer_tasks t JOIN volunteers v ON v.id=t.volunteer_id WHERE t.request_id=? AND v.user_id=?',(request_id,user_id)).fetchone():return jsonify({'error':'Request is outside your assigned tasks.'}),403
    elif user_role not in ('Citizen','Administrator','Government Official'):
        return jsonify({'error':'Access denied.'}),403

    items = conn.execute('''
        SELECT ri.*, r.name as resource_name, r.unit
        FROM request_items ri
        JOIN resources r ON ri.resource_id = r.id
        WHERE ri.request_id = ?
    ''', (request_id,)).fetchall()

    timeline = conn.execute("SELECT * FROM request_events WHERE request_id = ? ORDER BY id ASC", (request_id,)).fetchall()

    res = dict(req)
    res['items'] = [dict(i) for i in items]
    res['timeline'] = [dict(t) for t in timeline]
    owner=conn.execute("""SELECT a.id,a.owner_type,a.organization_id,o.name AS organization_name,a.status,
        a.volunteer_id,a.government_personnel_id,a.driver_user_id,a.vehicle_id,a.assigned_at
        FROM response_assignments a LEFT JOIN organizations o ON o.id=a.organization_id
        WHERE a.request_id=? AND a.status IN ('Assigned','Active','Completed')
        ORDER BY a.id DESC LIMIT 1""",(request_id,)).fetchone()
    res['response_assignment']=dict(owner) if owner else None
    res['dispatches'] = [dict(d) for d in conn.execute('SELECT id,status,driver,vehicle,destination,eta,delivered_at FROM dispatches WHERE request_id=? ORDER BY id',(request_id,)).fetchall()]
    return jsonify(res)

@api_bp.route('/api/government/response-options/<request_id>', methods=['GET'])
@roles_required('Government Official', 'Administrator')
def government_response_options(request_id):
    conn = get_db()
    req = conn.execute("SELECT id, status, verification_status, need,response_owner_type,response_organization_id FROM emergency_requests WHERE id=?", (request_id,)).fetchone()
    if not req:
        return jsonify({'error': 'Request not found.'}), 404
    personnel = conn.execute("""SELECT p.id,p.name,p.category,p.service_unit,p.status,'Government Responder' AS personnel_role,'Government' AS organization_name,
        (SELECT COUNT(*) FROM response_assignments a WHERE a.government_personnel_id=p.id AND a.status IN ('Assigned','Active')) AS active_assignments
        FROM government_personnel p WHERE p.status='Active' ORDER BY p.category,p.name""").fetchall()
    active_dispatch_states = "'Loading','Ready','En route','Arrived','Delivered Pending Proof','Delivered Pending Confirmation','Needs Review','Proof Rejected'"
    drivers = conn.execute(f"""SELECT u.id,u.name,u.status,'Government Driver' AS personnel_role,'Government' AS organization_name,
        (SELECT COUNT(*) FROM dispatches d WHERE d.driver_user_id=u.id AND d.status IN ({active_dispatch_states})) AS active_dispatches
        FROM users u JOIN government_driver_approvals ga ON ga.user_id=u.id
        WHERE u.role='Driver' AND u.status='ACTIVE' AND u.organization_id IS NULL ORDER BY u.name""").fetchall()
    need=(req['need'] or '').lower()
    pattern='%Ambulance%' if 'medical' in need else '%Rescue%' if ('rescue' in need or 'boat' in need) else '%Cargo%' if ('food' in need or 'ration' in need) else '%Relief%'
    vehicles=conn.execute("""SELECT id,vehicle_code,registration_number,vehicle_type,status,capacity_units,capacity_description,current_driver_user_id FROM vehicles
        WHERE owner_type='government' AND owner_organization_id IS NULL AND status='Available'
        AND current_driver_user_id IS NULL
        AND NOT EXISTS(SELECT 1 FROM dispatches d WHERE d.vehicle_id=vehicles.id AND d.status IN ('Loading','Ready','En route','Arrived','Delivered Pending Proof','Delivered Pending Confirmation','Needs Review','Proof Rejected'))
        AND NOT EXISTS(SELECT 1 FROM response_assignments a WHERE a.vehicle_id=vehicles.id AND a.status IN ('Assigned','Active'))
        AND (vehicle_type LIKE ? OR vehicle_code LIKE ?) ORDER BY id""",(pattern,pattern)).fetchall()
    return jsonify({'request_id':request_id,
        'eligible':req['response_owner_type'] is None and req['status'] not in ('Rejected','Closed','Delivered','Duplicate','Cancelled'),
        'response_owner_type':req['response_owner_type'],'response_organization_id':req['response_organization_id'],
        'personnel':[dict(p,available=(p['active_assignments']==0),organization_name='Government') for p in personnel],
        'drivers':[dict(d,available=(d['status']=='ACTIVE' and d['active_dispatches']==0 and is_available_driver(conn,d['id'],'government',request_id=request_id))) for d in drivers],
        'vehicles':[dict(v,available=(v['status']=='Available' and v['current_driver_user_id'] is None)) for v in vehicles]})


@api_bp.route('/api/ngo/response-options/<request_id>', methods=['GET'])
@roles_required('NGO Coordinator')
def ngo_response_options(request_id):
    conn=get_db()
    try: org_id=current_ngo_id(conn)
    except BusinessLogicError as e: return jsonify({'error':e.message,'code':e.code}),e.status_code
    req=conn.execute("SELECT * FROM emergency_requests WHERE id=?",(request_id,)).fetchone()
    if not req: return jsonify({'error':'Request not found.'}),404
    owner=conn.execute("""SELECT r.response_owner_type,r.response_organization_id,o.name AS organization_name,
        a.status AS assignment_status
        FROM emergency_requests r
        LEFT JOIN organizations o ON o.id=r.response_organization_id
        LEFT JOIN response_assignments a ON a.request_id=r.id AND a.owner_type=r.response_owner_type
          AND a.organization_id IS r.response_organization_id AND a.status IN ('Assigned','Active','Completed')
        WHERE r.id=? ORDER BY a.id DESC LIMIT 1""",(request_id,)).fetchone()
    eligible=bool(owner['response_owner_type'] is None
        and req['status'] not in ('Rejected','Closed','Delivered','Duplicate','Cancelled')
        and req['verification_status']!='Rejected')
    volunteers=conn.execute("""SELECT v.id,v.name,v.skill,v.zone,v.status,o.name AS organization_name,'NGO Volunteer' AS personnel_role,
        (SELECT COUNT(*) FROM volunteer_tasks t WHERE t.volunteer_id=v.id AND t.status IN ('Assigned','Accepted','In Progress','Submitted for Review','Needs Correction')) AS active_tasks
        FROM volunteers v JOIN organizations o ON o.id=v.organization_id WHERE v.organization_id=? AND v.owner_type='ngo' AND v.verified=1 AND v.status='Available' ORDER BY v.name""",(org_id,)).fetchall()
    drivers=conn.execute("""SELECT DISTINCT u.id,u.name,u.status,o.name AS organization_name,'NGO Driver' AS personnel_role FROM users u
        LEFT JOIN organization_memberships m ON m.user_id=u.id AND m.organization_id=? AND m.membership_role='Driver' AND m.status='Active'
        JOIN ngo_personnel_approvals a ON a.user_id=u.id AND a.organization_id=? AND a.personnel_type='Driver' AND a.decision='Approved'
        JOIN organizations o ON o.id=a.organization_id
        WHERE u.role='Driver' AND u.status='ACTIVE' AND (u.organization_id=? OR m.id IS NOT NULL) ORDER BY u.name""",(org_id,org_id,org_id)).fetchall()
    need=(req['need'] or '').lower(); pattern='%Ambulance%' if 'medical' in need else '%Rescue%' if ('rescue' in need or 'boat' in need) else '%Cargo%' if ('food' in need or 'ration' in need) else '%Relief%'
    vehicles=conn.execute("""SELECT id,vehicle_code,registration_number,vehicle_type,status,capacity_units,capacity_description,current_driver_user_id FROM vehicles
        WHERE owner_type='ngo' AND owner_organization_id=? AND status='Available' AND current_driver_user_id IS NULL
          AND NOT EXISTS(SELECT 1 FROM dispatches d WHERE d.vehicle_id=vehicles.id AND d.status IN ('Loading','Ready','En route','Arrived','Delivered Pending Proof','Delivered Pending Confirmation','Needs Review','Proof Rejected'))
          AND NOT EXISTS(SELECT 1 FROM response_assignments a WHERE a.vehicle_id=vehicles.id AND a.status IN ('Assigned','Active'))
          AND (vehicle_type LIKE ? OR vehicle_code LIKE ?) ORDER BY id""",(org_id,pattern,pattern)).fetchall()
    return jsonify({'request_id':request_id,'organization_id':org_id,'eligible':eligible,
        'blocked_reason':('This request has already been claimed or is no longer available.' if not eligible else None),
        'response_owner_type':owner['response_owner_type'],'response_organization_id':owner['response_organization_id'],
        'response_organization_name':owner['organization_name'],'assignment_status':owner['assignment_status'],
        'volunteers':[dict(v,available=(v['status']=='Available' and v['active_tasks']==0)) for v in volunteers],
        'drivers':[dict(d,available=is_available_driver(conn,d['id'],'ngo',org_id,request_id)) for d in drivers],
        'vehicles':[dict(v,available=(v['status']=='Available' and v['current_driver_user_id'] is None)) for v in vehicles]})


@api_bp.route('/api/requests/<request_id>/ngo-assign', methods=['POST'])
@roles_required('NGO Coordinator')
def assign_ngo_request(request_id):
    conn=get_db(); data=request.get_json(silent=True) or {}
    try: org_id=current_ngo_id(conn)
    except BusinessLogicError as e: return jsonify({'error':e.message,'code':e.code}),e.status_code
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            req=conn.execute("SELECT * FROM emergency_requests WHERE id=?",(request_id,)).fetchone()
            if not req: raise BusinessLogicError('Request not found.','NOT_FOUND',404)
            vid=data.get('volunteer_id'); did=data.get('driver_user_id'); vehicle_id=data.get('vehicle_id')
            try: vid=int(vid); did=int(did); vehicle_id=int(vehicle_id)
            except (TypeError,ValueError): raise BusinessLogicError('Select an eligible Volunteer, Driver, and vehicle.','ASSIGNMENT_REQUIRED',400)
            vol=conn.execute("SELECT * FROM volunteers WHERE id=? AND organization_id=? AND owner_type='ngo' AND verified=1 AND status='Available'",(vid,org_id)).fetchone()
            if not vol or conn.execute("SELECT 1 FROM volunteer_tasks WHERE volunteer_id=? AND status IN ('Assigned','Accepted','In Progress','Submitted for Review','Needs Correction')",(vid,)).fetchone(): raise BusinessLogicError('Selected Volunteer is unapproved, unavailable, or already assigned.','VOLUNTEER_UNAVAILABLE',409)
            if not is_available_driver(conn,did,'ngo',org_id,request_id): raise BusinessLogicError('Selected NGO Driver is unapproved, unavailable, or belongs to another organization.','DRIVER_UNAVAILABLE',409)
            need=(req['need'] or '').lower(); pattern='%Ambulance%' if 'medical' in need else '%Rescue%' if ('rescue' in need or 'boat' in need) else '%Cargo%' if ('food' in need or 'ration' in need) else '%Relief%'
            veh=conn.execute("""SELECT * FROM vehicles WHERE id=? AND owner_type='ngo' AND owner_organization_id=?
                AND status='Available' AND current_driver_user_id IS NULL
                AND NOT EXISTS(SELECT 1 FROM dispatches d WHERE d.vehicle_id=vehicles.id AND d.status IN ('Loading','Ready','En route','Arrived','Delivered Pending Proof','Delivered Pending Confirmation','Needs Review','Proof Rejected'))
                AND NOT EXISTS(SELECT 1 FROM response_assignments a WHERE a.vehicle_id=vehicles.id AND a.status IN ('Assigned','Active'))
                AND (vehicle_type LIKE ? OR vehicle_code LIKE ?)""",(vehicle_id,org_id,pattern,pattern)).fetchone()
            if not veh: raise BusinessLogicError('Selected vehicle is unavailable, incompatible, or not owned by this NGO.','VEHICLE_UNAVAILABLE',409)
            if services.required_vehicle_capacity(conn,request_id) > int(veh['capacity_units'] or 0):
                raise BusinessLogicError('Selected NGO vehicle does not have enough capacity for this request.','VEHICLE_CAPACITY_INSUFFICIENT',409)
            services.claim_request_service(conn,request_id,'ngo',org_id,session['user_id'])
            next_num=(conn.execute("SELECT MAX(CAST(SUBSTR(id,6) AS INTEGER)) FROM volunteer_tasks").fetchone()[0] or 0)+1
            task_id=f'TASK-{next_num:03d}'
            cur=conn.execute("INSERT INTO response_assignments (request_id,owner_type,organization_id,volunteer_id,driver_user_id,vehicle_id,status,assigned_by_user_id,notes) VALUES (?,'ngo',?,?,?,?,'Assigned',?,?)",(request_id,org_id,vid,did,vehicle_id,session['user_id'],(data.get('notes') or '').strip()))
            conn.execute("INSERT INTO volunteer_tasks (id,incident_id,zone_id,organization_id,volunteer_id,request_id,title,task_type,description,quantity_expected,status,assigned_by_user_id) VALUES (?,?,?,?,?,?,?,?,?,0,'Assigned',?)",(task_id,req['incident_id'],req['zone_id'],org_id,vid,request_id,(data.get('title') or f"NGO response for {request_id}").strip(),'Request Response',(data.get('notes') or f"Support {req['need']} in {req['area']}").strip(),session['user_id']))
            conn.execute("UPDATE volunteers SET status='On task' WHERE id=? AND status='Available'",(vid,))
            if conn.execute('SELECT changes()').fetchone()[0]!=1: raise BusinessLogicError('Selected Volunteer was assigned concurrently. Refresh and retry.','VOLUNTEER_UNAVAILABLE',409)
            conn.execute("UPDATE vehicles SET status='Reserved',current_driver_user_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='Available'",(did,vehicle_id))
            if conn.execute('SELECT changes()').fetchone()[0] != 1: raise BusinessLogicError('Selected vehicle was taken by another assignment. Refresh and retry.','VEHICLE_UNAVAILABLE',409)
            database.log_audit_event(conn,session['user_id'],'ASSIGN_NGO_RESPONSE','response_assignments',cur.lastrowid,new_state={'request_id':request_id,'organization_id':org_id,'volunteer_id':vid,'driver_user_id':did,'vehicle_id':vehicle_id})
            database.log_system_event(conn,'ngo_response_assigned',{'request_id':request_id,'organization_id':org_id,'task_id':task_id})
            if vol['user_id']: database.create_notification(conn,vol['user_id'],'task_assigned','NGO response task assigned',f'You were assigned to {request_id}.','volunteer_tasks',task_id)
            database.create_notification(conn,did,'dispatch_assigned','NGO response assignment',f'You were assigned to support {request_id}.','emergency_requests',request_id)
        return jsonify({'assignment_id':cur.lastrowid,'task_id':task_id,'status':'Assigned','request_id':request_id,'organization_id':org_id}),201
    except BusinessLogicError as e:
        return jsonify({'error':e.message,'code':e.code}),e.status_code
    except sqlite3.IntegrityError:
        return jsonify({'error':'The request or selected personnel were assigned concurrently. Refresh options and retry.','code':'ASSIGNMENT_CONFLICT'}),409

@api_bp.route('/api/requests/<request_id>/verify', methods=['POST'])
@roles_required('Government Official', 'Administrator')
def verify_request(request_id):
    data = request.get_json(silent=True) or {}
    decision = data.get('decision') or 'Verified'
    reason = data.get('reason') or 'Priority and severity confirmed by responder'
    conn = get_db()
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            updated = services.verify_request_service(conn, request_id, decision, reason, session['user_id'], session['role'], response_personnel_id=data.get('response_personnel_id'), driver_user_id=data.get('driver_user_id'), vehicle_id=data.get('vehicle_id'))
        return jsonify(dict(updated))
    except BusinessLogicError as e:
        return jsonify({'error': e.message, 'code': e.code}), e.status_code

@api_bp.route('/api/requests/<request_id>/mark-duplicate', methods=['POST'])
@roles_required('Government Official', 'NGO Coordinator')
def mark_duplicate_request(request_id):
    data = request.get_json(silent=True) or {}
    primary_id = (data.get('primary_request_id') or '').strip()
    reason = data.get('reason') or 'Duplicate entry for same household'
    if not primary_id:
        return jsonify({'error': 'primary_request_id is required.'}), 400

    conn = get_db()
    try:
        with conn:
            updated = services.mark_duplicate_request_service(conn, request_id, primary_id, reason, session['user_id'], session['role'])
        return jsonify(dict(updated))
    except BusinessLogicError as e:
        return jsonify({'error': e.message, 'code': e.code}), e.status_code

@api_bp.route('/api/requests/<request_id>/timeline', methods=['GET'])
@login_required
def get_request_timeline(request_id):
    conn = get_db()
    req = conn.execute("SELECT requester_user_id, requester_name FROM emergency_requests WHERE id = ?", (request_id,)).fetchone()
    if not req:
        return jsonify({'error': 'Request not found'}), 404

    user_role = session.get('role')
    if user_role == 'Citizen' and req['requester_user_id'] != session.get('user_id') and req['requester_name'] != session.get('name'):
        return jsonify({'error': 'Access denied'}), 403

    events = conn.execute("SELECT * FROM request_events WHERE request_id = ? ORDER BY id ASC", (request_id,)).fetchall()
    return jsonify([dict(e) for e in events])

@api_bp.route('/api/requests/<request_id>/items', methods=['GET'])
@login_required
def get_request_items(request_id):
    conn = get_db()
    req = conn.execute("SELECT id, requester_user_id, requester_name FROM emergency_requests WHERE id = ?", (request_id,)).fetchone()
    if not req:
        return jsonify({'error': 'Request not found'}), 404

    user_role = session.get('role')
    if user_role == 'Citizen' and req['requester_user_id'] != session.get('user_id') and req['requester_name'] != session.get('name'):
        return jsonify({'error': 'Access denied'}), 403

    rows = conn.execute('''
        SELECT ri.*, r.name as resource_name, r.unit as resource_unit
        FROM request_items ri
        JOIN resources r ON ri.resource_id = r.id
        WHERE ri.request_id = ?
        ORDER BY ri.id ASC
    ''', (request_id,)).fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/requests/<request_id>/items', methods=['POST'])
@roles_required('Administrator', 'Government Official', 'NGO Coordinator')
def add_request_item(request_id):
    conn = get_db()
    req = conn.execute("SELECT * FROM emergency_requests WHERE id = ?", (request_id,)).fetchone()
    if not req:
        return jsonify({'error': 'Request not found'}), 404
    data = request.get_json(silent=True) or {}
    res_id = data.get('resource_id')
    qty = int(data.get('quantity_requested') or 1)
    notes = data.get('notes')
    if not res_id or qty <= 0:
        return jsonify({'error': 'Valid resource_id and positive quantity_requested are required.'}), 400

    with conn:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO request_items (request_id, resource_id, quantity_requested, notes)
            VALUES (?, ?, ?, ?)
        ''', (request_id, res_id, qty, notes))
        it_id = cur.lastrowid
        database.log_audit_event(conn, session['user_id'], 'ADD_REQUEST_ITEM', 'request_items', it_id, new_state={'request_id': request_id, 'resource_id': res_id, 'quantity': qty})

    item_row = conn.execute("SELECT * FROM request_items WHERE id = ?", (it_id,)).fetchone()
    return jsonify(dict(item_row)), 201

@api_bp.route('/api/requests/<request_id>/confirm-delivery', methods=['POST'])
@login_required
def citizen_confirm_delivery(request_id):
    conn = get_db()
    req = conn.execute("SELECT * FROM emergency_requests WHERE id = ?", (request_id,)).fetchone()
    if not req:
        return jsonify({'error': 'Request not found'}), 404

    user_role = session.get('role')
    user_id = session.get('user_id')
    user_name = session.get('name')

    # Record-level authorization: Citizen can only confirm their own request
    if user_role == 'Citizen' and req['requester_user_id'] != user_id:
        return jsonify({'error': 'Access denied. You can only confirm delivery for your own emergency requests.'}), 403

    # Validate status: cannot confirm if not yet dispatched
    if req['status'] not in ('Delivered Pending Confirmation', 'Delivered'):
        return jsonify({'error': f"Cannot confirm delivery for request in status '{req['status']}'."}), 400

    data = request.get_json(silent=True) or {}
    notes = data.get('notes') or 'Aid supplies received in good condition'

    with conn:
        conn.execute("UPDATE emergency_requests SET status = 'Delivered', delivery_confirmed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (request_id,))
        conn.execute('''
            INSERT INTO request_events (request_id, event_type, from_status, to_status, notes, actor_user_id)
            VALUES (?, 'CITIZEN_CONFIRMED', ?, 'Delivered', ?, ?)
        ''', (request_id, req['status'], notes, user_id))
        database.log_audit_event(conn, user_id, 'CONFIRM_DELIVERY', 'emergency_requests', request_id, reason=notes)
        database.log_system_event(conn, 'request_updated', {'id': request_id, 'status': 'Delivered'})

    return jsonify({'success': True, 'message': 'Delivery confirmed. Thank you!'})

@api_bp.route('/api/requests/<request_id>/report-issue', methods=['POST'])
@login_required
def report_request_issue(request_id):
    conn = get_db()
    req = conn.execute("SELECT * FROM emergency_requests WHERE id = ?", (request_id,)).fetchone()
    if not req:
        return jsonify({'error': 'Request not found'}), 404

    user_role = session.get('role')
    user_id = session.get('user_id')
    user_name = session.get('name')

    # Record-level authorization: Citizen can only report issue for their own request
    if user_role == 'Citizen' and req['requester_user_id'] != user_id:
        return jsonify({'error': 'Access denied. You can only report issues for your own emergency requests.'}), 403

    if req['status'] not in ('Delivered Pending Proof', 'Delivered Pending Confirmation', 'Delivered', 'Partially Fulfilled'):
        return jsonify({'error': f"Cannot report delivery issue for request in status '{req['status']}'."}), 400

    data = request.get_json(silent=True) or {}
    issue_type = data.get('issue_type') or 'PartialDelivery'
    desc = data.get('description') or data.get('reason') or 'Reported delivery discrepancy'

    with conn:
        conn.execute("UPDATE emergency_requests SET status = 'Partially Fulfilled', review_reason = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (desc, request_id))
        conn.execute('''
            INSERT INTO request_events (request_id, event_type, from_status, to_status, reason, actor_user_id)
            VALUES (?, 'DELIVERY_DISCREPANCY', ?, 'Partially Fulfilled', ?, ?)
        ''', (request_id, req['status'], desc, user_id))
        database.log_audit_event(conn, user_id, 'REPORT_REQUEST_ISSUE', 'emergency_requests', request_id, reason=desc)
        database.log_system_event(conn, 'request_updated', {'id': request_id, 'status': 'Partially Fulfilled'})

    return jsonify({'success': True, 'message': 'Delivery issue reported to incident coordinator.'})

@api_bp.route('/api/requests/<request_id>/request-info', methods=['POST'])
@roles_required('Government Official', 'NGO Coordinator', 'Administrator')
def request_more_info(request_id):
    conn = get_db()
    req = conn.execute("SELECT * FROM emergency_requests WHERE id = ?", (request_id,)).fetchone()
    if not req:
        return jsonify({'error': 'Request not found'}), 404
    data = request.get_json(silent=True) or {}
    question = (data.get('notes') or data.get('question') or 'Additional landmark and family details required').strip()
    with conn:
        conn.execute("UPDATE emergency_requests SET verification_status = 'NeedsReview', review_reason = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (question, request_id))
        conn.execute('''
            INSERT INTO request_events (request_id, event_type, from_status, to_status, notes, actor_user_id)
            VALUES (?, 'INFO_REQUESTED', ?, ?, ?, ?)
        ''', (request_id, req['status'], req['status'], question, session['user_id']))
        database.log_audit_event(conn, session['user_id'], 'REQUEST_INFO', 'emergency_requests', request_id, reason=question)
    return jsonify({'success': True, 'message': 'Additional information requested from requester.'})

@api_bp.route('/api/requests/<request_id>/reject', methods=['POST'])
@roles_required('Government Official', 'Administrator')
def reject_emergency_request(request_id):
    conn = get_db()
    req = conn.execute("SELECT * FROM emergency_requests WHERE id = ?", (request_id,)).fetchone()
    if not req:
        return jsonify({'error': 'Request not found'}), 404
    data = request.get_json(silent=True) or {}
    reason = (data.get('reason') or 'Request invalid or out of relief scope').strip()
    with conn:
        conn.execute("UPDATE emergency_requests SET status = 'Rejected', verification_status = 'Rejected', review_reason = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (reason, request_id))
        conn.execute('''
            INSERT INTO request_events (request_id, event_type, from_status, to_status, reason, actor_user_id)
            VALUES (?, 'REQUEST_REJECTED', ?, 'Rejected', ?, ?)
        ''', (request_id, req['status'], reason, session['user_id']))
        database.log_audit_event(conn, session['user_id'], 'REJECT_REQUEST', 'emergency_requests', request_id, reason=reason)
        database.log_system_event(conn, 'request_updated', {'id': request_id, 'status': 'Rejected'})
    return jsonify({'success': True, 'message': f'Request {request_id} rejected.'})

@api_bp.route('/api/requests/<request_id>/escalate', methods=['POST'])
@roles_required('Government Official', 'NGO Coordinator', 'Administrator')
def escalate_emergency_request(request_id):
    conn = get_db()
    req = conn.execute("SELECT * FROM emergency_requests WHERE id = ?", (request_id,)).fetchone()
    if not req:
        return jsonify({'error': 'Request not found'}), 404
    data = request.get_json(silent=True) or {}
    reason = (data.get('reason') or 'Urgent life-safety risk escalated').strip()
    new_priority = min(99, max(req['priority_score'] + 15, 90))
    with conn:
        conn.execute("UPDATE emergency_requests SET priority_score = ?, review_reason = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_priority, reason, request_id))
        conn.execute('''
            INSERT INTO request_events (request_id, event_type, from_status, to_status, reason, actor_user_id)
            VALUES (?, 'REQUEST_ESCALATED', ?, ?, ?, ?)
        ''', (request_id, req['status'], req['status'], f"Escalated to priority {new_priority}: {reason}", session['user_id']))
        database.log_audit_event(conn, session['user_id'], 'ESCALATE_REQUEST', 'emergency_requests', request_id, reason=reason)
        database.log_system_event(conn, 'request_updated', {'id': request_id, 'priority_score': new_priority})
    return jsonify({'success': True, 'message': f'Request escalated to priority score {new_priority}.', 'priority_score': new_priority})

@api_bp.route('/api/requests/<request_id>/close', methods=['POST'])
@roles_required('Government Official', 'Administrator')
def close_emergency_request(request_id):
    conn = get_db()
    req = conn.execute("SELECT * FROM emergency_requests WHERE id = ?", (request_id,)).fetchone()
    if not req:
        return jsonify({'error': 'Request not found'}), 404
    data = request.get_json(silent=True) or {}
    reason = (data.get('reason') or 'Operational closure confirmed by supervisor').strip()
    with conn:
        conn.execute("UPDATE emergency_requests SET status = 'Closed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (request_id,))
        conn.execute('''
            INSERT INTO request_events (request_id, event_type, from_status, to_status, notes, actor_user_id)
            VALUES (?, 'REQUEST_CLOSED', ?, 'Closed', ?, ?)
        ''', (request_id, req['status'], reason, session['user_id']))
        database.log_audit_event(conn, session['user_id'], 'CLOSE_REQUEST', 'emergency_requests', request_id, reason=reason)
        database.log_system_event(conn, 'request_updated', {'id': request_id, 'status': 'Closed'})
    return jsonify({'success': True, 'message': f'Request {request_id} closed.'})

# =========================================================================
# 4. RESOURCES, WAREHOUSES & STOCK
# =========================================================================

@api_bp.route('/api/resources', methods=['GET'])
def get_resources():
    conn = get_db()
    cat = request.args.get('category')
    query = "SELECT * FROM resources WHERE is_active = 1"
    params = []
    if cat:
        query += " AND category = ?"
        params.append(cat)
    query += " ORDER BY id ASC"
    rows = conn.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/resources', methods=['POST'])
@roles_required('Administrator', 'Government Official')
def create_resource():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    cat = (data.get('category') or 'General').strip()
    unit = (data.get('unit') or 'units').strip()
    sku = data.get('sku')

    if not name:
        return jsonify({'error': 'Resource name is required.'}), 400

    conn = get_db()
    existing = conn.execute("SELECT id FROM resources WHERE LOWER(name) = ?", (name.lower(),)).fetchone()
    if existing:
        return jsonify({'error': f"Resource '{name}' already exists."}), 409

    with conn:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO resources (sku, name, category, unit, is_active)
            VALUES (?, ?, ?, ?, 1)
        ''', (sku, name, cat, unit))
        res_id = cur.lastrowid
        database.log_audit_event(conn, session['user_id'], 'CREATE_RESOURCE', 'resources', res_id, new_state={'name': name, 'category': cat})

    return jsonify({'id': res_id, 'name': name, 'category': cat, 'unit': unit}), 201

@api_bp.route('/api/warehouses', methods=['GET'])
@login_required
def get_warehouses():
    conn=get_db(); role=session.get('role'); user_id=session.get('user_id'); where=''; params=[]
    if role=='Government Official': where=" WHERE w.owner_type='government' AND w.owner_organization_id IS NULL"
    elif role=='NGO Coordinator':
        try: org_id=current_ngo_id(conn)
        except BusinessLogicError as e: return jsonify({'error':e.message,'code':e.code}),e.status_code
        where=" WHERE w.owner_type='ngo' AND w.owner_organization_id=?"; params=[org_id]
    elif role=='Driver':
        u=conn.execute('SELECT organization_id FROM users WHERE id=?',(user_id,)).fetchone(); org_id=u[0] if u else None
        where=" WHERE w.owner_type=? AND w.owner_organization_id IS ?"; params=['ngo' if org_id else 'government',org_id]
    elif role not in ('Administrator',): return jsonify({'error':'Access denied.'}),403
    rows=conn.execute('SELECT w.*,o.name AS owner_name FROM warehouses w LEFT JOIN organizations o ON o.id=w.owner_organization_id'+where+' ORDER BY w.id ASC',params).fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/warehouses', methods=['POST'])
@roles_required('Administrator','Government Official','NGO Coordinator')
def create_warehouse():
    conn=get_db(); data=request.get_json(silent=True) or {}; role=session['role']
    code=(data.get('code') or '').strip().upper(); name=(data.get('name') or '').strip(); district=(data.get('district') or '').strip(); address=(data.get('address') or '').strip()
    if not code or not name or not district or not address: return jsonify({'error':'Warehouse code, name, district and address are required.'}),400
    if conn.execute('SELECT 1 FROM warehouses WHERE code=?',(code,)).fetchone(): return jsonify({'error':'Warehouse code already exists.'}),409
    if role=='NGO Coordinator':
        try: org_id=current_ngo_id(conn)
        except BusinessLogicError as e: return jsonify({'error':e.message,'code':e.code}),e.status_code
        owner='ngo'
    elif role=='Government Official': owner='government'; org_id=None
    else:
        owner=(data.get('owner_type') or 'government').strip().lower(); org_raw=data.get('owner_organization_id')
        if owner=='ngo':
            try: org_id=int(org_raw)
            except (TypeError,ValueError): return jsonify({'error':'Select an approved NGO owner.'}),400
            if not conn.execute("SELECT 1 FROM organizations WHERE id=? AND organization_type='NGO' AND status='Approved'",(org_id,)).fetchone():return jsonify({'error':'Organization is not approved.'}),400
        elif owner=='government': org_id=None
        else:return jsonify({'error':'Owner must be government or ngo.'}),400
    lat=data.get('lat');lng=data.get('lng')
    try:
        if (lat is None)!=(lng is None): raise ValueError()
        lat=float(lat) if lat is not None else None;lng=float(lng) if lng is not None else None
        if lat is not None and not(-90<=lat<=90 and -180<=lng<=180):raise ValueError()
    except (TypeError,ValueError):return jsonify({'error':'Coordinates must be a valid latitude/longitude pair.'}),400
    with conn:
        cur=conn.execute("INSERT INTO warehouses(code,name,district,address,lat,lng,status,manager_user_id,owner_type,owner_organization_id) VALUES(?,?,?,?,?,?,'Active',?,?,?)",(code,name,district,address,lat,lng,session['user_id'],owner,org_id));wid=cur.lastrowid
        database.log_audit_event(conn,session['user_id'],'CREATE_WAREHOUSE','warehouses',wid,new_state={'owner_type':owner,'organization_id':org_id})
        database.log_system_event(conn,'warehouse_created',{'id':wid,'owner_type':owner,'organization_id':org_id})
    return jsonify(dict(conn.execute('SELECT * FROM warehouses WHERE id=?',(wid,)).fetchone())),201

@api_bp.route('/api/warehouses/<int:warehouse_id>/stock', methods=['POST'])
@roles_required('Administrator','Government Official','NGO Coordinator')
def create_warehouse_stock(warehouse_id):
    conn=get_db();data=request.get_json(silent=True) or {};role=session['role']
    wh=conn.execute('SELECT * FROM warehouses WHERE id=?',(warehouse_id,)).fetchone()
    if not wh:return jsonify({'error':'Warehouse not found.'}),404
    if role=='Government Official' and not(wh['owner_type']=='government' and wh['owner_organization_id'] is None):return jsonify({'error':'Warehouse is outside Government ownership.'}),403
    if role=='NGO Coordinator':
        try:org_id=current_ngo_id(conn)
        except BusinessLogicError as e:return jsonify({'error':e.message,'code':e.code}),e.status_code
        if wh['owner_type']!='ngo' or wh['owner_organization_id']!=org_id:return jsonify({'error':'Warehouse is outside this NGO ownership.'}),403
    if role not in ('Administrator','Government Official','NGO Coordinator'):return jsonify({'error':'Access denied.'}),403
    try: rid=int(data.get('resource_id')); quantity=int(data.get('quantity')); target=int(data.get('target_stock'))
    except (ValueError,TypeError):return jsonify({'error':'Resource, quantity and target stock must be whole numbers.'}),400
    if quantity<0 or target<=0:return jsonify({'error':'Quantity must be non-negative and target stock must be positive.'}),400
    if not conn.execute('SELECT 1 FROM resources WHERE id=? AND is_active=1',(rid,)).fetchone():return jsonify({'error':'Active resource not found.'}),404
    if conn.execute('SELECT 1 FROM warehouse_stock WHERE warehouse_id=? AND resource_id=?',(warehouse_id,rid)).fetchone():return jsonify({'error':'This resource already has a stock record at the selected warehouse.'}),409
    status=database.calc_inventory_status(quantity,target)
    with conn:
        cur=conn.execute("INSERT INTO warehouse_stock(warehouse_id,resource_id,on_hand_units,reserved_units,target_stock,status) VALUES(?,?,?,0,?,?)",(warehouse_id,rid,quantity,target,status));sid=cur.lastrowid
        if quantity:conn.execute("INSERT INTO inventory_transactions(warehouse_stock_id,transaction_type,quantity_units,direction,reference_type,reference_id,performed_by_user_id,reason) VALUES(?,'OpeningBalance',?,'IN','warehouse_stock',?,?,?)",(sid,quantity,str(sid),session['user_id'],'Opening stock'))
        database.log_audit_event(conn,session['user_id'],'CREATE_WAREHOUSE_STOCK','warehouse_stock',sid,new_state={'warehouse_id':warehouse_id,'resource_id':rid,'quantity':quantity})
        database.log_system_event(conn,'inventory_updated',{'warehouse_id':warehouse_id,'resource_id':rid,'available_units':quantity})
    return jsonify(dict(conn.execute('SELECT * FROM warehouse_stock WHERE id=?',(sid,)).fetchone())),201

@api_bp.route('/api/warehouses/<int:warehouse_id>/stock', methods=['GET'])
@login_required
def get_warehouse_stock(warehouse_id):
    conn=get_db(); role=session.get('role'); user_id=session.get('user_id')
    wh=conn.execute('SELECT * FROM warehouses WHERE id=?',(warehouse_id,)).fetchone()
    if not wh: return jsonify({'error':'Warehouse not found.'}),404
    if role=='Government Official' and not (wh['owner_type']=='government' and wh['owner_organization_id'] is None): return jsonify({'error':'Warehouse is outside Government ownership.'}),403
    if role=='NGO Coordinator':
        try: org_id=current_ngo_id(conn)
        except BusinessLogicError as e: return jsonify({'error':e.message,'code':e.code}),e.status_code
        if wh['owner_type']!='ngo' or wh['owner_organization_id']!=org_id: return jsonify({'error':'Warehouse is outside this NGO ownership.'}),403
    if role=='Driver':
        usr=conn.execute('SELECT organization_id FROM users WHERE id=?',(user_id,)).fetchone(); org_id=usr[0] if usr else None; scope='ngo' if org_id else 'government'
        if wh['owner_type']!=scope or wh['owner_organization_id']!=org_id: return jsonify({'error':'Warehouse is outside your fleet ownership.'}),403
    if role not in ('Administrator','Government Official','NGO Coordinator','Driver'): return jsonify({'error':'Access denied.'}),403
    rows=conn.execute('''SELECT ws.*,r.name AS resource_name,r.category,r.unit,(ws.on_hand_units-ws.reserved_units) AS available_units
        FROM warehouse_stock ws JOIN resources r ON r.id=ws.resource_id WHERE ws.warehouse_id=? ORDER BY ws.id''',(warehouse_id,)).fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/inventory/transactions', methods=['GET'])
@roles_required('Administrator', 'Government Official', 'NGO Coordinator')
def get_inventory_transactions():
    conn = get_db()
    rows = conn.execute(f'''
        SELECT it.*, r.name as resource_name, w.code as warehouse_code, w.name as warehouse_name, u.name as performed_by_name
        FROM inventory_transactions it
        JOIN warehouse_stock ws ON it.warehouse_stock_id = ws.id
        JOIN resources r ON ws.resource_id = r.id
        JOIN warehouses w ON ws.warehouse_id = w.id
        LEFT JOIN users u ON it.performed_by_user_id = u.id
        ORDER BY it.id DESC LIMIT 100
    ''').fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/inventory/ledger', methods=['GET'])
@login_required
def get_inventory_ledger():
    conn = get_db()
    role=session.get('role'); user_id=session.get('user_id'); scope_sql=''; params=[]
    if role == 'Government Official':
        scope_sql="WHERE w.owner_type='government' AND w.owner_organization_id IS NULL"
    elif role == 'NGO Coordinator':
        org=conn.execute("SELECT COALESCE(u.organization_id,(SELECT organization_id FROM organization_memberships WHERE user_id=u.id AND membership_role='Coordinator' AND status='Active' LIMIT 1)) FROM users u WHERE u.id=?",(user_id,)).fetchone()
        scope_sql="WHERE w.owner_type='ngo' AND w.owner_organization_id=?"; params=[org[0] if org else None]
    elif role != 'Administrator':
        return jsonify({'error':'Access denied.'}),403
    rows = conn.execute(f'''
        SELECT it.*, r.name as resource_name, w.code as warehouse_code, w.name as warehouse_name, u.name as performed_by_name
        FROM inventory_transactions it
        JOIN warehouse_stock ws ON it.warehouse_stock_id = ws.id
        JOIN resources r ON ws.resource_id = r.id
        JOIN warehouses w ON ws.warehouse_id = w.id
        LEFT JOIN users u ON it.performed_by_user_id = u.id
        {scope_sql} ORDER BY it.id DESC LIMIT 200
    ''',params).fetchall()
    return jsonify([dict(r) for r in rows])

# =========================================================================
# 5. DONATIONS
# =========================================================================

@api_bp.route('/api/donations', methods=['GET'])
@login_required
def list_donations():
    conn = get_db()
    dtype = request.args.get('type')
    status_filter = request.args.get('status')
    user_role = session.get('role')

    query = """
        SELECT d.*, w.name AS destination_warehouse_name, o.name AS recipient_organization_name,
               (SELECT COALESCE(SUM(quantity_declared), 0) FROM donation_items WHERE donation_id = d.id) as declared_quantity,
               (SELECT COALESCE(SUM(quantity_accepted), 0) FROM donation_items WHERE donation_id = d.id) as accepted_quantity,
               (SELECT GROUP_CONCAT(r.name, ', ') FROM donation_items di JOIN resources r ON di.resource_id = r.id WHERE di.donation_id = d.id) as item_names
        FROM donations d LEFT JOIN warehouses w ON w.id=d.destination_warehouse_id
        LEFT JOIN organizations o ON o.id=d.organization_id
        WHERE 1=1
    """
    params = []
    if user_role == 'Citizen':
        query += " AND d.submitted_by_user_id = ?"
        params.append(session.get('user_id'))
    elif user_role == 'NGO Coordinator':
        try: org_id=current_ngo_id(conn)
        except BusinessLogicError as e: return jsonify({'error':e.message,'code':e.code}),e.status_code
        query += " AND d.organization_id = ?"; params.append(org_id)
    elif user_role == 'Driver':
        return jsonify({'error':'Drivers cannot access donation records.'}),403
    elif user_role == 'Government Official':
        query += " AND d.organization_id IS NULL"
    elif user_role != 'Administrator':
        return jsonify({'error':'Access denied.'}),403
    if dtype:
        query += " AND d.donation_type = ?"
        params.append(dtype)
    if status_filter:
        query += " AND d.status = ?"
        params.append(status_filter)
    query += " ORDER BY d.id DESC"
    rows = conn.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/donations/<donation_id>/mark-in-transit', methods=['POST'])
@roles_required('NGO Coordinator', 'Government Official', 'Administrator')
def donation_mark_in_transit(donation_id):
    conn = get_db()
    don = conn.execute("SELECT * FROM donations WHERE id = ?", (donation_id,)).fetchone()
    if not don:
        return jsonify({'error': 'Donation not found'}), 404
    if don['status'] != 'Submitted':
        return jsonify({'error': f"Cannot mark donation in status '{don['status']}' as in transit."}), 400
    with conn:
        conn.execute("UPDATE donations SET status = 'In Transit', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (donation_id,))
        database.log_audit_event(conn, session['user_id'], 'DONATION_IN_TRANSIT', 'donations', donation_id)
        database.log_system_event(conn, 'donation_updated', {'id': donation_id, 'status': 'In Transit'})
    return jsonify({'success': True, 'message': f'Donation {donation_id} is now In Transit.'})

@api_bp.route('/api/donations/<donation_id>/receive', methods=['POST'])
@roles_required('NGO Coordinator', 'Government Official', 'Administrator')
def donation_receive(donation_id):
    conn = get_db()
    don = conn.execute("SELECT * FROM donations WHERE id = ?", (donation_id,)).fetchone()
    if not don:
        return jsonify({'error': 'Donation not found'}), 404
    if don['status'] not in ('Submitted', 'In Transit'):
        return jsonify({'error': f"Cannot receive donation in status '{don['status']}'."}), 400
    with conn:
        conn.execute("UPDATE donations SET status = 'Received', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (donation_id,))
        database.log_audit_event(conn, session['user_id'], 'DONATION_RECEIVED', 'donations', donation_id)
        database.log_system_event(conn, 'donation_updated', {'id': donation_id, 'status': 'Received'})
    return jsonify({'success': True, 'message': f'Donation {donation_id} received at warehouse bay, awaiting verification.'})

@api_bp.route('/api/donations', methods=['POST'])
@roles_required('NGO Coordinator', 'Government Official', 'Administrator', 'Citizen')
def create_donation():
    data = request.get_json(silent=True) or {}
    conn = get_db()
    try:
        with conn:
            don = services.intake_donation_service(conn, data, session['user_id'])
        return jsonify(dict(don)), 201
    except BusinessLogicError as e:
        return jsonify({'error': e.message, 'code': e.code}), e.status_code

@api_bp.route('/api/donations/<donation_id>', methods=['GET'])
@login_required
def get_donation_detail(donation_id):
    conn = get_db()
    don = conn.execute("SELECT * FROM donations WHERE id = ?", (donation_id,)).fetchone()
    if not don:
        return jsonify({'error': 'Donation not found'}), 404
    role=session.get('role')
    if role=='NGO Coordinator':
        try: own_id=current_ngo_id(conn)
        except BusinessLogicError as e:return jsonify({'error':e.message,'code':e.code}),e.status_code
        if don['organization_id']!=own_id:return jsonify({'error':'Donation is outside this NGO ownership.'}),403
    elif role=='Citizen' and don['submitted_by_user_id']!=session.get('user_id'):return jsonify({'error':'Donation is outside your record.'}),403
    elif role not in ('Administrator','Government Official','NGO Coordinator','Citizen'):return jsonify({'error':'Access denied.'}),403

    items = conn.execute('''
        SELECT di.*, r.name as resource_name, r.unit
        FROM donation_items di
        JOIN resources r ON di.resource_id = r.id
        WHERE di.donation_id = ?
    ''', (donation_id,)).fetchall()

    res = dict(don)
    res['items'] = [dict(i) for i in items]
    return jsonify(res)

@api_bp.route('/api/donations/<donation_id>/verify', methods=['POST'])
@roles_required('Government Official', 'Administrator')
def verify_donation(donation_id):
    data = request.get_json(silent=True) or {}
    decision = data.get('decision') or 'Accept'
    reason = data.get('reason') or 'Physical quantity verified by warehouse staff'
    items_ver = data.get('items') or []

    conn = get_db()
    try:
        with conn:
            don = services.verify_donation_service(conn, donation_id, decision, reason, items_ver, session['user_id'], session['role'])
        return jsonify(dict(don))
    except BusinessLogicError as e:
        return jsonify({'error': e.message, 'code': e.code}), e.status_code

# =========================================================================
# 6. VOLUNTEER TASKS & FIELD REPORTS
# =========================================================================

@api_bp.route('/api/volunteer-tasks', methods=['GET'])
@login_required
def list_volunteer_tasks():
    conn = get_db()
    user_role = session.get('role')
    user_name = session.get('name')
    user_id = session.get('user_id')

    query = '''
        SELECT vt.*, v.name as volunteer_name, v.skill as volunteer_skill, u.name as assigned_by_name
        FROM volunteer_tasks vt
        JOIN volunteers v ON vt.volunteer_id = v.id
        LEFT JOIN users u ON vt.assigned_by_user_id = u.id
        WHERE 1=1
    '''
    params = []

    if user_role == 'Volunteer':
        query += " AND v.user_id = ?"; params.append(user_id)
    elif user_role == 'NGO Coordinator':
        org_id=current_ngo_id(conn,user_id); query += " AND vt.organization_id = ?"; params.append(org_id)
    elif user_role == 'Government Official':
        query += " AND (vt.organization_id IS NULL OR v.owner_type='government')"

    status_f = request.args.get('status')
    if status_f:
        query += " AND vt.status = ?"
        params.append(status_f)

    query += " ORDER BY vt.id DESC"
    rows = conn.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/volunteer-tasks', methods=['POST'])
@roles_required('Administrator', 'Government Official', 'NGO Coordinator')
def create_volunteer_task():
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    ttype = (data.get('task_type') or 'Distribution').strip()
    desc = (data.get('description') or '').strip()
    vid = data.get('volunteer_id')

    conn = get_db()
    if not vid:
        return jsonify({'error':'Select a specific available Volunteer from the roster.'}),400
    try: vid=int(vid)
    except (TypeError,ValueError): return jsonify({'error':'Volunteer ID must be an integer.'}),400
    vol=conn.execute("SELECT * FROM volunteers WHERE id=?",(vid,)).fetchone()
    if not vol: return jsonify({'error':'Volunteer is not in the roster.'}),404
    if vol['status']!='Available' or not vol['verified']:
        return jsonify({'error':'Volunteer must be verified and available before task assignment.'}),409
    if conn.execute("SELECT 1 FROM volunteer_tasks WHERE volunteer_id=? AND status IN ('Assigned','Accepted','In Progress','Submitted for Review','Needs Correction')",(vid,)).fetchone():
        return jsonify({'error':'Volunteer already has an active task.'}),409
    owner_org=vol['organization_id'] if vol['owner_type']=='ngo' else None
    if session.get('role')=='NGO Coordinator':
        try: requester_org=current_ngo_id(conn)
        except BusinessLogicError as e: return jsonify({'error':e.message,'code':e.code}),e.status_code
        if vol['owner_type']!='ngo' or owner_org!=requester_org:
            return jsonify({'error':'Volunteer belongs to another owner or organization.'}),403
    elif session.get('role')=='Government Official' and vol['owner_type']!='government':
        return jsonify({'error':'Government may assign only Government-owned responders.'}),403
    if not title or not desc:
        return jsonify({'error':'Title and description are required.'}),400

    max_t = conn.execute("SELECT MAX(CAST(SUBSTR(id, 6) AS INTEGER)) FROM volunteer_tasks").fetchone()
    next_num = (max_t[0] or 0) + 1
    tid = f"TASK-{next_num:03d}"

    q_exp = int(data.get('quantity_expected') or data.get('target_quantity') or 0)
    inc_id = data.get('incident_id')
    if inc_id:
        chk_inc = conn.execute("SELECT id FROM incidents WHERE id = ?", (inc_id,)).fetchone()
        inc_id = chk_inc['id'] if chk_inc else None
    else:
        chk_def = conn.execute("SELECT id FROM incidents WHERE id = 'INC-2026-FLOOD'").fetchone()
        inc_id = chk_def['id'] if chk_def else None

    zone_id = data.get('zone_id')
    if zone_id:
        chk_z = conn.execute("SELECT id FROM zones WHERE id = ?", (zone_id,)).fetchone()
        zone_id = chk_z['id'] if chk_z else None
    else:
        chk_z = conn.execute("SELECT id FROM zones WHERE id = 'Z-01'").fetchone()
        zone_id = chk_z['id'] if chk_z else None

    req_id = data.get('request_id')
    if req_id:
        chk_r = conn.execute("SELECT id FROM emergency_requests WHERE id = ?", (req_id,)).fetchone()
        if not chk_r:
            req_id = None

    with conn:
        conn.execute('''
            INSERT INTO volunteer_tasks (id, incident_id, zone_id, organization_id, volunteer_id, request_id, title, task_type, description, quantity_expected, status, assigned_by_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Assigned', ?)
        ''', (tid, inc_id, zone_id, owner_org, vid, req_id, title, ttype, desc, q_exp, session['user_id']))
        conn.execute("UPDATE volunteers SET status='On task' WHERE id=? AND status='Available'",(vid,))

        vol_user = conn.execute("SELECT user_id FROM volunteers WHERE id = ?", (vid,)).fetchone()
        if vol_user and vol_user[0]:
            database.create_notification(conn, vol_user[0], 'task_assigned', f"New Task: {title}", desc, 'volunteer_tasks', tid)

        database.log_audit_event(conn, session['user_id'], 'CREATE_VOLUNTEER_TASK', 'volunteer_tasks', tid, new_state={'title': title, 'volunteer_id': vid})
        database.log_system_event(conn, 'volunteer_task_created', {'id': tid, 'title': title})

    return jsonify(dict(conn.execute("SELECT * FROM volunteer_tasks WHERE id = ?", (tid,)).fetchone())), 201

@api_bp.route('/api/volunteer-tasks/<task_id>/<action>', methods=['POST'])
@login_required
def volunteer_task_action(task_id, action):
    allowed_actions = ('accept', 'decline', 'check-in', 'progress', 'submit', 'approve')
    if action not in allowed_actions:
        return jsonify({'error': f'Invalid action: {action}'}), 400

    data = request.get_json(silent=True) or {}
    conn = get_db()
    task_owner=conn.execute("SELECT t.*,v.owner_type,v.organization_id AS volunteer_org,v.user_id AS volunteer_user_id FROM volunteer_tasks t JOIN volunteers v ON v.id=t.volunteer_id WHERE t.id=?",(task_id,)).fetchone()
    if not task_owner: return jsonify({'error':'Volunteer task record not found.'}),404
    role=session.get('role'); uid=session.get('user_id')
    if role=='NGO Coordinator':
        try: own_id=current_ngo_id(conn,uid)
        except BusinessLogicError as e: return jsonify({'error':e.message,'code':e.code}),e.status_code
        if task_owner['organization_id']!=own_id: return jsonify({'error':'Task is outside this NGO ownership.'}),403
    elif role=='Government Official' and (task_owner['owner_type']!='government' or task_owner['organization_id'] is not None):
        return jsonify({'error':'Task is outside Government ownership.'}),403
    elif role=='Volunteer' and task_owner['volunteer_user_id']!=uid: return jsonify({'error':'Task is assigned to another Volunteer.'}),403
    try:
        with conn:
            task = services.update_volunteer_task_status_service(
                conn, task_id, action, session['user_id'], session['name'], session['role'], payload=data
            )
        return jsonify(dict(task))
    except BusinessLogicError as e:
        return jsonify({'error': e.message, 'code': e.code, 'details': e.details}), e.status_code

@api_bp.route('/api/field-reports', methods=['GET'])
@login_required
def list_field_reports():
    conn = get_db()
    role=session.get('role'); user_id=session.get('user_id'); scope=''; params=[]
    if role == 'Citizen':
        scope='WHERE fr.reporter_user_id=?'; params=[user_id]
    elif role == 'NGO Coordinator':
        org_id=current_ngo_id(conn,user_id)
        scope="WHERE fr.reporter_user_id=? OR fr.zone_id IN (SELECT zone_id FROM zone_adoptions WHERE organization_id=? AND status IN ('Approved','Active'))"
        params=[user_id,org_id]
    elif role == 'Volunteer':
        scope='WHERE fr.reporter_user_id=?'; params=[user_id]
    elif role == 'Driver':
        scope='WHERE fr.zone_id IN (SELECT d.zone_id FROM dispatches d WHERE d.driver_user_id=?)'; params=[user_id]
    elif role not in ('Administrator','Government Official'):
        return jsonify({'error':'Access denied.'}),403
    rows = conn.execute(f'''
        SELECT fr.*, u.name as reporter_name
        FROM field_reports fr
        LEFT JOIN users u ON fr.reporter_user_id = u.id
        {scope}
        ORDER BY fr.id DESC
    ''',params).fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/field-reports', methods=['POST'])
@login_required
def create_field_report():
    data = request.get_json(silent=True) or {}
    cat = (data.get('category') or 'Road Access').strip()
    sev = (data.get('severity') or 'High').strip()
    desc = (data.get('description') or '').strip()

    if not desc:
        return jsonify({'error': 'Description is required.'}), 400

    conn = get_db()
    max_f = conn.execute("SELECT MAX(CAST(SUBSTR(id, 4) AS INTEGER)) FROM field_reports").fetchone()
    next_num = (max_f[0] or 0) + 1
    frid = f"FR-{next_num:03d}"

    inc_id = data.get('incident_id')
    if inc_id:
        chk_inc = conn.execute("SELECT id FROM incidents WHERE id = ?", (inc_id,)).fetchone()
        inc_id = chk_inc['id'] if chk_inc else None
    else:
        chk_def = conn.execute("SELECT id FROM incidents WHERE id = 'INC-2026-FLOOD'").fetchone()
        inc_id = chk_def['id'] if chk_def else None

    zone_id = data.get('zone_id')
    if zone_id:
        chk_z = conn.execute("SELECT id FROM zones WHERE id = ?", (zone_id,)).fetchone()
        zone_id = chk_z['id'] if chk_z else None

    lat = data.get('lat')
    lng = data.get('lng')

    with conn:
        conn.execute('''
            INSERT INTO field_reports (id, incident_id, zone_id, reporter_user_id, category, severity, description, lat, lng, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Submitted')
        ''', (frid, inc_id, zone_id, session['user_id'], cat, sev, desc, lat, lng))
        database.log_audit_event(conn, session['user_id'], 'SUBMIT_FIELD_REPORT', 'field_reports', frid, new_state={'category': cat, 'severity': sev})
        database.log_system_event(conn, 'field_report_submitted', {'id': frid, 'category': cat, 'severity': sev})

    return jsonify(dict(conn.execute("SELECT * FROM field_reports WHERE id = ?", (frid,)).fetchone())), 201

# =========================================================================
# 7. FLEET & DISPATCH EXTENDED
# =========================================================================

@api_bp.route('/api/allocation-options/<request_id>', methods=['GET'])
@roles_required('Administrator','Government Official','NGO Coordinator')
def allocation_options(request_id):
    conn=get_db(); req=conn.execute("SELECT id,status,verification_status,need,response_owner_type,response_organization_id FROM emergency_requests WHERE id=?",(request_id,)).fetchone()
    if not req: return jsonify({'error':'Request not found.'}),404
    role=session.get('role'); org_id=None; owner='government'
    if role=='NGO Coordinator':
        try: org_id=current_ngo_id(conn)
        except BusinessLogicError as e: return jsonify({'error':e.message,'code':e.code}),e.status_code
        owner='ngo'
    if req['response_owner_type']!=owner or (owner=='ngo' and req['response_organization_id']!=org_id):
        return jsonify({'error':'This request is claimed by another response organization.','code':'ALLOCATION_SCOPE_DENIED'}),409
    if (owner=='government' and req['verification_status']!='Verified') or req['status']!='Awaiting allocation':
        return jsonify({'error':'Only claimed requests awaiting allocation can be allocated.','code':'VERIFICATION_REQUIRED'}),409
    team=conn.execute("""SELECT a.*,gp.name AS personnel_name,gp.category AS personnel_category,v.name AS volunteer_name,
        du.name AS driver_name,ve.vehicle_code,ve.vehicle_type
        FROM response_assignments a LEFT JOIN government_personnel gp ON gp.id=a.government_personnel_id
        LEFT JOIN volunteers v ON v.id=a.volunteer_id JOIN users du ON du.id=a.driver_user_id JOIN vehicles ve ON ve.id=a.vehicle_id
        WHERE a.request_id=? AND a.owner_type=? AND a.organization_id IS ? AND a.status IN ('Assigned','Active') ORDER BY a.id DESC LIMIT 1""",(request_id,owner,org_id)).fetchone()
    need=(req['need'] or '').lower(); pattern='%Ambulance%' if 'medical' in need else '%Rescue%' if ('rescue' in need or 'boat' in need) else '%Cargo%' if ('food' in need or 'ration' in need) else '%Relief%'
    if owner=='government':
        driver_rows=conn.execute("""SELECT u.id,u.name,u.status,(SELECT COUNT(*) FROM dispatches d WHERE d.driver_user_id=u.id AND d.status IN ('Loading','Ready','En route','Arrived','Delivered Pending Proof','Delivered Pending Confirmation','Needs Review','Proof Rejected')) AS active_dispatches FROM users u JOIN government_driver_approvals ga ON ga.user_id=u.id WHERE u.role='Driver' AND u.status='ACTIVE' AND u.organization_id IS NULL ORDER BY u.name""").fetchall()
    else:
        driver_rows=conn.execute("""SELECT DISTINCT u.id,u.name,u.status,0 AS active_dispatches FROM users u
          LEFT JOIN organization_memberships m ON m.user_id=u.id AND m.organization_id=? AND m.membership_role='Driver' AND m.status='Active'
          JOIN ngo_personnel_approvals a ON a.user_id=u.id AND a.organization_id=? AND a.personnel_type='Driver' AND a.decision='Approved'
          WHERE u.role='Driver' AND u.status='ACTIVE' AND (u.organization_id=? OR m.id IS NOT NULL) ORDER BY u.name""",(org_id,org_id,org_id)).fetchall()
    drivers=[dict(d,available=is_available_driver(conn,d['id'],owner,org_id,request_id)) for d in driver_rows]
    vehicles=conn.execute("""SELECT id,vehicle_code,registration_number,vehicle_type,status,capacity_units,capacity_description,current_driver_user_id FROM vehicles WHERE owner_type=? AND owner_organization_id IS ?
      AND (id=? OR (status='Available' AND current_driver_user_id IS NULL
       AND NOT EXISTS(SELECT 1 FROM dispatches d WHERE d.vehicle_id=vehicles.id AND d.status IN ('Loading','Ready','En route','Arrived','Delivered Pending Proof','Delivered Pending Confirmation','Needs Review','Proof Rejected'))
       AND NOT EXISTS(SELECT 1 FROM response_assignments a WHERE a.vehicle_id=vehicles.id AND a.status IN ('Assigned','Active'))))
      AND (vehicle_type LIKE ? OR vehicle_code LIKE ?) ORDER BY id""",(owner,org_id,team['vehicle_id'] if team else -1,pattern,pattern)).fetchall()
    vehicle_options=[dict(v,available=bool((v['status']=='Available' and v['current_driver_user_id'] is None) or (team and v['id']==team['vehicle_id']))) for v in vehicles]
    return jsonify({'request_id':request_id,'owner_type':owner,'organization_id':org_id,'drivers':drivers,'vehicles':vehicle_options,'team_assignment':dict(team) if team else None,'assignment_required':team is None})

@api_bp.route('/api/vehicles', methods=['GET'])
@login_required
def list_vehicles():
    conn=get_db(); role=session.get('role'); user_id=session.get('user_id'); where=''; params=[]
    if role=='Government Official': where=" WHERE v.owner_type='government' AND v.owner_organization_id IS NULL"
    elif role=='NGO Coordinator':
        try: org_id=current_ngo_id(conn)
        except BusinessLogicError as e: return jsonify({'error':e.message,'code':e.code}),e.status_code
        where=" WHERE v.owner_type='ngo' AND v.owner_organization_id=?"; params=[org_id]
    elif role=='Driver':
        u=conn.execute('SELECT organization_id FROM users WHERE id=?',(user_id,)).fetchone(); org_id=u[0] if u else None
        where=" WHERE v.owner_type=? AND v.owner_organization_id IS ?"; params=['ngo' if org_id else 'government',org_id]
    elif role not in ('Administrator',): return jsonify({'error':'Access denied.'}),403
    rows=conn.execute('SELECT v.*,o.name AS owner_name FROM vehicles v LEFT JOIN organizations o ON o.id=v.owner_organization_id'+where+' ORDER BY v.id ASC',params).fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/dispatches/<dispatch_id>', methods=['GET'])
@login_required
@dispatch_scope_required
def get_dispatch_detail(dispatch_id):
    conn = get_db()
    row = conn.execute("SELECT d.*, w.name AS warehouse_name, w.lat AS pickup_lat, w.lng AS pickup_lng, r.lat AS destination_lat, r.lng AS destination_lng, r.area AS request_area FROM dispatches d LEFT JOIN warehouses w ON w.id=d.warehouse_id LEFT JOIN emergency_requests r ON r.id=d.request_id WHERE d.id = ?", (dispatch_id,)).fetchone()
    if not row:
        return jsonify({'error': 'Dispatch not found'}), 404

    user_role = session.get('role')
    user_id = session.get('user_id')
    user_name = session.get('name')

    # Record-level and owner-scope authorization
    if user_role == 'Government Official' and (row['owner_type']!='government' or row['owner_organization_id'] is not None):
        return jsonify({'error':'Dispatch is outside Government ownership.'}),403
    if user_role == 'NGO Coordinator':
        try: org_id=current_ngo_id(conn)
        except BusinessLogicError as e: return jsonify({'error':e.message,'code':e.code}),e.status_code
        if row['owner_type']!='ngo' or row['owner_organization_id']!=org_id: return jsonify({'error':'Dispatch is outside this NGO ownership.'}),403
    if user_role == 'Driver':
        u=conn.execute('SELECT organization_id FROM users WHERE id=?',(user_id,)).fetchone(); org_id=u[0] if u else None; scope='ngo' if org_id else 'government'
        if row['owner_type']!=scope or row['owner_organization_id']!=org_id: return jsonify({'error':'Dispatch is outside this Driver ownership scope.'}),403
        if row['driver_user_id'] != user_id:
            return jsonify({'error': 'Access denied to this dispatch'}), 403

    if user_role == 'Citizen':
        chk_own = conn.execute("SELECT id FROM emergency_requests WHERE id = ? AND requester_user_id = ?", (row['request_id'], user_id)).fetchone()
        if not chk_own:
            return jsonify({'error': 'Access denied to this dispatch'}), 403

    dsp = dict(row)
    dsp['items'] = [dict(it) for it in conn.execute("SELECT di.*, r.name as resource_name FROM dispatch_items di JOIN resources r ON di.resource_id = r.id WHERE di.dispatch_id = ?", (dispatch_id,)).fetchall()]
    dsp['proofs'] = [dict(p) for p in conn.execute("SELECT * FROM delivery_proofs WHERE dispatch_id = ?", (dispatch_id,)).fetchall()]
    return jsonify(dsp)

@api_bp.route('/api/dispatches/<dispatch_id>/ready', methods=['POST'])
@login_required
@dispatch_scope_required
def dispatch_ready(dispatch_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()
    if not row:
        return jsonify({'error': 'Dispatch not found'}), 404
    with conn:
        conn.execute("UPDATE dispatches SET status = 'Ready', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (dispatch_id,))
        if row['vehicle_id']:
            conn.execute("UPDATE vehicles SET status = 'Loading' WHERE id = ?", (row['vehicle_id'],))
        database.log_audit_event(conn, session['user_id'], 'DISPATCH_READY', 'dispatches', dispatch_id, new_state={'status': 'Ready'})
        database.log_system_event(conn, 'dispatch_updated', {'id': dispatch_id, 'status': 'Ready'})
    return jsonify(dict(conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()))

@api_bp.route('/api/dispatches/<dispatch_id>/start', methods=['POST'])
@login_required
@dispatch_scope_required
def dispatch_start(dispatch_id):
    conn = get_db()
    try:
        with conn:
            dsp = services.driver_start_trip_service(conn, dispatch_id, session['user_id'], session['name'], session['role'])
        return jsonify(dict(dsp))
    except BusinessLogicError as e:
        return jsonify({'error': e.message, 'code': e.code}), e.status_code

@api_bp.route('/api/dispatches/<dispatch_id>/arrive', methods=['POST'])
@login_required
@dispatch_scope_required
def dispatch_arrive(dispatch_id):
    conn = get_db()
    try:
        with conn:
            dsp = services.driver_arrive_service(conn, dispatch_id, session['user_id'], session['name'], session['role'])
        return jsonify(dict(dsp))
    except BusinessLogicError as e:
        return jsonify({'error': e.message, 'code': e.code}), e.status_code

@api_bp.route('/api/dispatches/<dispatch_id>/route-blockage', methods=['POST'])
@login_required
@dispatch_scope_required
def dispatch_route_blockage(dispatch_id):
    data = request.get_json(silent=True) or {}
    reason = (data.get('reason') or 'Flood water inundating road').strip()
    notes = data.get('notes')
    lat = data.get('lat')
    lng = data.get('lng')

    blockage_location = data.get('blockage_location')
    suggested_detour = data.get('suggested_detour')
    extra_notes = []
    if blockage_location:
        extra_notes.append(f"Location: {blockage_location}")
    if suggested_detour:
        extra_notes.append(f"Detour: {suggested_detour}")
    if notes:
        extra_notes.append(notes)
    combined_notes = " Â· ".join(extra_notes) if extra_notes else None

    conn = get_db()
    try:
        with conn:
            dsp = services.report_route_blockage_service(conn, dispatch_id, session['user_id'], session['name'], session['role'], reason, combined_notes, lat, lng)
        return jsonify(dict(dsp))
    except BusinessLogicError as e:
        return jsonify({'error': e.message, 'code': e.code}), e.status_code

@api_bp.route('/api/dispatches/<dispatch_id>/reroute', methods=['POST'])
@roles_required('Government Official', 'NGO Coordinator', 'Administrator')
def dispatch_reroute(dispatch_id):
    data = request.get_json(silent=True) or {}
    new_dest = (data.get('destination') or '').strip()
    reason = (data.get('reason') or 'Diverting along high embankment bypass road').strip()
    if not new_dest:
        return jsonify({'error': 'New destination is required.'}), 400

    conn = get_db()
    try:
        with conn:
            dsp = services.reroute_dispatch_service(conn, dispatch_id, session['user_id'], new_dest, reason)
        return jsonify(dict(dsp))
    except BusinessLogicError as e:
        return jsonify({'error': e.message, 'code': e.code}), e.status_code

@api_bp.route('/api/dispatches/<dispatch_id>/delivery-proof', methods=['POST'])
@login_required
@dispatch_scope_required
def dispatch_delivery_proof(dispatch_id):
    data = request.get_json(silent=True) or {}
    ptype = data.get('proof_type') or 'RecipientConfirmation'
    pref = data.get('proof_reference') or (f"Recipient: {data['recipient_name']}" if data.get('recipient_name') else 'SIG-DELIVERY-VERIFIED')
    notes = data.get('notes') or 'Handover completed at destination point'
    items = data.get('items')

    conn = get_db()
    if not isinstance(items, list) or not items:
        return jsonify({'error': 'Itemized delivery quantities are required for every dispatch manifest line.'}), 400

    try:
        with conn:
            prf = services.submit_delivery_proof_service(conn, dispatch_id, session['user_id'], session['name'], session['role'], ptype, pref, notes, items)
        dsp_row = conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()
        res_data = dict(dsp_row)
        res_data['proof'] = dict(prf)
        return jsonify(res_data)
    except BusinessLogicError as e:
        return jsonify({'error': e.message, 'code': e.code}), e.status_code

@api_bp.route('/api/dispatches/<dispatch_id>/review-delivery', methods=['POST'])
@roles_required('Government Official', 'Administrator', 'NGO Coordinator')
def dispatch_review_delivery(dispatch_id):
    data = request.get_json(silent=True) or {}
    decision = data.get('decision') or 'Verified'
    reason = data.get('reason') or 'Recipient signatures and item counts verified'

    conn = get_db()
    try:
        with conn:
            dsp = services.review_delivery_service(conn, dispatch_id, decision, reason, session['user_id'], session['role'])
        return jsonify(dict(dsp))
    except BusinessLogicError as e:
        return jsonify({'error': e.message, 'code': e.code}), e.status_code

@api_bp.route('/api/dispatches/<dispatch_id>/return', methods=['POST'])
@login_required
@dispatch_scope_required
def dispatch_return(dispatch_id):
    data = request.get_json(silent=True) or {}
    items = data.get('returned_items')
    notes = data.get('notes') or 'Trip returned to warehouse'

    conn = get_db()
    try:
        with conn:
            dsp = services.return_dispatch_service(conn, dispatch_id, session['user_id'], session['name'], session['role'], returned_items=items, return_notes=notes)
        return jsonify(dict(dsp))
    except BusinessLogicError as e:
        return jsonify({'error': e.message, 'code': e.code}), e.status_code

@api_bp.route('/api/dispatches/<dispatch_id>/cancel', methods=['POST'])
@roles_required('Government Official', 'NGO Coordinator', 'Administrator')
def dispatch_cancel(dispatch_id):
    data = request.get_json(silent=True) or {}
    reason = (data.get('reason') or 'Operational recall or safety cancellation').strip()

    conn = get_db()
    try:
        with conn:
            dsp = services.cancel_dispatch_service(conn, dispatch_id, session['user_id'], session['role'], reason)
        return jsonify(dict(dsp))
    except BusinessLogicError as e:
        return jsonify({'error': e.message, 'code': e.code}), e.status_code

# =========================================================================
# 8. SHELTERS ADMISSIONS & ZERO DOUBLE-COUNTING TRANSFERS
# =========================================================================

@api_bp.route('/api/shelters/<int:shelter_id>/admissions', methods=['POST'])
@roles_required('Government Official', 'Administrator', 'NGO Coordinator')
def shelter_admit(shelter_id):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    try:
        with conn:
            adm = services.admit_shelter_service(conn, shelter_id, data, session['user_id'])
        return jsonify(dict(adm)), 201
    except BusinessLogicError as e:
        return jsonify({'error': e.message, 'code': e.code, 'details': e.details}), e.status_code

@api_bp.route('/api/shelter-admissions', methods=['GET'])
def list_shelter_admissions():
    conn = get_db()
    sid = request.args.get('shelter_id')
    query = '''
        SELECT sa.*, s.name as shelter_name
        FROM shelter_admissions sa
        JOIN shelters s ON sa.shelter_id = s.id
        WHERE 1=1
    '''
    params = []
    if sid and str(sid).isdigit():
        query += " AND sa.shelter_id = ?"
        params.append(int(sid))
    query += " ORDER BY sa.id DESC"
    rows = conn.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/shelter-admissions/<admission_id>/transfer', methods=['POST'])
@roles_required('Government Official', 'Administrator', 'NGO Coordinator')
def shelter_transfer(admission_id):
    data = request.get_json(silent=True) or {}
    to_shelter_id = data.get('to_shelter_id')
    count = data.get('people_count')
    reason = data.get('reason') or 'Relief shelter redistribution'

    if not to_shelter_id:
        return jsonify({'error': 'to_shelter_id is required.'}), 400

    conn = get_db()
    try:
        with conn:
            trf = services.transfer_shelter_service(conn, admission_id, int(to_shelter_id), count, reason, session['user_id'])
        return jsonify(dict(trf))
    except BusinessLogicError as e:
        return jsonify({'error': e.message, 'code': e.code}), e.status_code

@api_bp.route('/api/shelter-admissions/<admission_id>/exit', methods=['POST'])
@roles_required('Government Official', 'Administrator', 'NGO Coordinator')
def shelter_exit(admission_id):
    conn = get_db()
    adm = conn.execute("SELECT * FROM shelter_admissions WHERE id = ?", (admission_id,)).fetchone()
    if not adm:
        return jsonify({'error': 'Shelter admission not found'}), 404
    if adm['status'] != 'Admitted':
        return jsonify({'error': f"Cannot exit admission in status '{adm['status']}'."}), 400

    data = request.get_json(silent=True) or {}
    reason = (data.get('reason') or 'Evacuee safely returned home or relocated').strip()
    shelter = conn.execute("SELECT * FROM shelters WHERE id = ?", (adm['shelter_id'],)).fetchone()
    count = adm['people_count']

    with conn:
        conn.execute("UPDATE shelter_admissions SET status = 'Exited', exited_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (admission_id,))
        if shelter:
            new_occ = max(0, shelter['occupants'] - count)
            pct = new_occ / shelter['capacity'] if shelter['capacity'] > 0 else 0
            st = 'Near capacity' if pct >= 0.9 else 'Operational'
            conn.execute("UPDATE shelters SET occupants = ?, status = ? WHERE id = ?", (new_occ, st, adm['shelter_id']))
            database.log_system_event(conn, 'shelter_updated', {'id': adm['shelter_id'], 'occupants': new_occ, 'status': st})
        database.log_audit_event(conn, session['user_id'], 'EXIT_SHELTER', 'shelter_admissions', admission_id, reason=reason)

    return jsonify({'success': True, 'message': f'Admission {admission_id} recorded as exited.'})

# =========================================================================
# 9. FINANCE & BUDGET (EXACT INTEGER PAISE)
# =========================================================================

@api_bp.route('/api/fund-budgets', methods=['GET'])
@roles_required('Administrator', 'Government Official', 'NGO Coordinator')
def list_fund_budgets():
    conn = get_db()
    role=session.get('role')
    if role=='NGO Coordinator':
        try:org_id=current_ngo_id(conn)
        except BusinessLogicError as e:return jsonify({'error':e.message,'code':e.code}),e.status_code
        rows=conn.execute("SELECT * FROM fund_budgets WHERE organization_id=? ORDER BY id ASC",(org_id,)).fetchall()
    elif role=='Government Official':rows=conn.execute("SELECT * FROM fund_budgets WHERE organization_id IS NULL ORDER BY id ASC").fetchall()
    else:rows=conn.execute("SELECT * FROM fund_budgets ORDER BY id ASC").fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/fund-budgets', methods=['POST'])
@roles_required('Government Official', 'Administrator')
def create_fund_budget():
    data = request.get_json(silent=True) or {}
    inc_id = data.get('incident_id')
    cat = (data.get('category') or 'General Relief').strip()
    amt_raw = data.get('budget_amount_paise') if data.get('budget_amount_paise') is not None else (int(data.get('amount_inr', 0)) * 100)
    if not inc_id or not amt_raw or int(amt_raw) <= 0:
        return jsonify({'error': 'Incident ID and positive budget amount are required.'}), 400

    conn = get_db()
    with conn:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO fund_budgets (incident_id, category, budget_amount_paise, status, approved_by_user_id, approved_at)
            VALUES (?, ?, ?, 'Approved', ?, CURRENT_TIMESTAMP)
        ''', (inc_id, cat, int(amt_raw), session['user_id']))
        b_id = cur.lastrowid
        database.log_audit_event(conn, session['user_id'], 'CREATE_FUND_BUDGET', 'fund_budgets', b_id, new_state={'amount_paise': int(amt_raw), 'category': cat})
        database.log_system_event(conn, 'fund_budget_created', {'id': b_id, 'amount_paise': int(amt_raw)})

    return jsonify(dict(conn.execute("SELECT * FROM fund_budgets WHERE id = ?", (b_id,)).fetchone())), 201

@api_bp.route('/api/fund-requests', methods=['GET'])
@roles_required('Administrator', 'Government Official', 'NGO Coordinator')
def list_fund_requests():
    conn = get_db()
    query='''SELECT fr.*,o.name AS organization_name,u.name AS requested_by_name FROM fund_requests fr JOIN organizations o ON fr.organization_id=o.id LEFT JOIN users u ON u.id=fr.requested_by_user_id WHERE 1=1''';params=[]
    if session['role']=='NGO Coordinator':
        try:org_id=current_ngo_id(conn)
        except BusinessLogicError as e:return jsonify({'error':e.message,'code':e.code}),e.status_code
        query+=' AND fr.organization_id=?';params.append(org_id)
    query+=' ORDER BY fr.id DESC';rows=conn.execute(query,params).fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/fund-requests', methods=['POST'])
@roles_required('NGO Coordinator')
def create_fund_request():
    data = request.get_json(silent=True) or {}
    cat = (data.get('category') or 'Food Supplies').strip()
    purpose = (data.get('purpose') or '').strip()
    amt_raw = data.get('requested_amount_paise') if data.get('requested_amount_paise') is not None else (int(data.get('amount_inr', 0)) * 100)

    if not purpose or not amt_raw or int(amt_raw) <= 0:
        return jsonify({'error': 'Purpose and positive requested amount are required.'}), 400

    conn = get_db()
    user_id = session['user_id']
    if session['role']=='NGO Coordinator':
        try:org_id=current_ngo_id(conn,user_id)
        except BusinessLogicError as e:return jsonify({'error':e.message,'code':e.code}),e.status_code
    else:org_id=None
    chk_org = conn.execute("SELECT id FROM organizations WHERE id = ?", (org_id,)).fetchone()
    if not chk_org:
        chk_any_org = conn.execute("SELECT id FROM organizations LIMIT 1").fetchone()
        if chk_any_org:
            org_id = chk_any_org['id']
        else:
            return jsonify({'error': 'An approved organization is required to submit fund requests.'}), 400

    inc_id = data.get('incident_id')
    if inc_id:
        chk_inc = conn.execute("SELECT id FROM incidents WHERE id = ?", (inc_id,)).fetchone()
        inc_id = chk_inc['id'] if chk_inc else None
    if not inc_id:
        chk_def = conn.execute("SELECT id FROM incidents WHERE id = 'INC-2026-FLOOD'").fetchone()
        inc_id = chk_def['id'] if chk_def else None
    if not inc_id:
        chk_any = conn.execute("SELECT id FROM incidents LIMIT 1").fetchone()
        inc_id = chk_any['id'] if chk_any else None
    if not inc_id:
        return jsonify({'error': 'An active incident is required to submit fund requests.'}), 400

    max_fr = conn.execute("SELECT MAX(CAST(SUBSTR(id, 9) AS INTEGER)) FROM fund_requests").fetchone()
    next_num = (max_fr[0] or 0) + 1
    frid = f"FR-2026-{next_num:02d}"

    with conn:
        conn.execute('''
            INSERT INTO fund_requests (id, incident_id, organization_id, category, purpose, requested_amount_paise, status, requested_by_user_id)
            VALUES (?, ?, ?, ?, ?, ?, 'Submitted', ?)
        ''', (frid, inc_id, org_id, cat, purpose, int(amt_raw), user_id))
        database.log_audit_event(conn, user_id, 'CREATE_FUND_REQUEST', 'fund_requests', frid, new_state={'amount_paise': int(amt_raw), 'purpose': purpose})
        database.log_system_event(conn, 'fund_request_submitted', {'id': frid, 'amount_paise': int(amt_raw)})

    return jsonify(dict(conn.execute("SELECT * FROM fund_requests WHERE id = ?", (frid,)).fetchone())), 201

@api_bp.route('/api/fund-requests/<request_id>/<action>', methods=['POST'])
@login_required
def fund_request_action(request_id, action):
    allowed = ('approve', 'commit', 'pay', 'reconcile')
    if action not in allowed:
        return jsonify({'error': f'Invalid fund action: {action}'}), 400

    data = request.get_json(silent=True) or {}
    conn = get_db()
    try:
        with conn:
            fr = services.fund_request_action_service(conn, request_id, action, session['user_id'], session['role'], data)
        return jsonify(dict(fr))
    except BusinessLogicError as e:
        return jsonify({'error': e.message, 'code': e.code}), e.status_code

@api_bp.route('/api/fund-transactions', methods=['GET'])
@roles_required('Administrator', 'Government Official', 'NGO Coordinator')
def list_fund_transactions():
    conn = get_db()
    query='''SELECT ft.*,u.name AS performed_by_name FROM fund_transactions ft LEFT JOIN users u ON u.id=ft.performed_by_user_id WHERE 1=1''';params=[]
    if session['role']=='NGO Coordinator':
        try:org_id=current_ngo_id(conn)
        except BusinessLogicError as e:return jsonify({'error':e.message,'code':e.code}),e.status_code
        query+=' AND ft.organization_id=?';params.append(org_id)
    query+=' ORDER BY ft.id DESC';rows=conn.execute(query,params).fetchall()
    return jsonify([dict(r) for r in rows])

# =========================================================================
# 10. NOTIFICATIONS, ADVISORIES & REPORTS
# =========================================================================

@api_bp.route('/api/notifications', methods=['GET'])
@login_required
def get_user_notifications():
    conn = get_db()
    user_id = session['user_id']
    rows = conn.execute("SELECT * FROM notifications WHERE recipient_user_id = ? ORDER BY id DESC LIMIT 50", (user_id,)).fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/notifications/<int:id>/read', methods=['POST'])
@login_required
def mark_notification_read(id):
    conn = get_db()
    with conn:
        conn.execute("UPDATE notifications SET read_at = CURRENT_TIMESTAMP WHERE id = ? AND recipient_user_id = ?", (id, session['user_id']))
    return jsonify({'success': True})

@api_bp.route('/api/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    conn = get_db()
    with conn:
        conn.execute("UPDATE notifications SET read_at = CURRENT_TIMESTAMP WHERE recipient_user_id = ? AND read_at IS NULL", (session['user_id'],))
    return jsonify({'success': True})

@api_bp.route('/api/advisories', methods=['GET'])
def get_advisories():
    conn = get_db()
    rows = conn.execute("SELECT * FROM public_advisories WHERE status='Published' AND (valid_until IS NULL OR valid_until>datetime('now','localtime')) ORDER BY published_at DESC,id DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/advisories', methods=['POST'])
@roles_required('Government Official')
def create_advisory():
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    body = (data.get('body') or '').strip()
    cat = (data.get('category') or 'Evacuation').strip()
    if not title or not body:
        return jsonify({'error': 'Title and advisory text are required.'}), 400

    conn = get_db()
    max_a = conn.execute("SELECT MAX(CAST(SUBSTR(id, 10) AS INTEGER)) FROM public_advisories").fetchone()
    next_num = (max_a[0] or 0) + 1
    aid = f"ADV-2026-{next_num:02d}"

    inc_id = data.get('incident_id')
    if inc_id:
        chk_inc = conn.execute("SELECT id FROM incidents WHERE id = ?", (inc_id,)).fetchone()
        inc_id = chk_inc['id'] if chk_inc else None
    else:
        chk_def = conn.execute("SELECT id FROM incidents WHERE id = 'INC-2026-FLOOD'").fetchone()
        inc_id = chk_def['id'] if chk_def else None

    zone_id = data.get('zone_id')
    if zone_id:
        chk_z = conn.execute("SELECT id FROM zones WHERE id = ?", (zone_id,)).fetchone()
        zone_id = chk_z['id'] if chk_z else None

    with conn:
        conn.execute('''
            INSERT INTO public_advisories (id, incident_id, zone_id, title, body, category, status, created_by_user_id, approved_by_user_id, published_at)
            VALUES (?, ?, ?, ?, ?, ?, 'Published', ?, ?, CURRENT_TIMESTAMP)
        ''', (aid, inc_id, zone_id, title, body, cat, session['user_id'], session['user_id']))
        database.log_audit_event(conn, session['user_id'], 'PUBLISH_ADVISORY', 'public_advisories', aid, new_state={'title': title})
        database.log_system_event(conn, 'advisory_published', {'id': aid, 'title': title})

    return jsonify(dict(conn.execute("SELECT * FROM public_advisories WHERE id = ?", (aid,)).fetchone())), 201

@api_bp.route('/api/inter-agency-requests', methods=['GET'])
def get_inter_agency_requests():
    conn = get_db()
    rows = conn.execute("SELECT * FROM inter_agency_requests ORDER BY id DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@api_bp.route('/api/inter-agency-requests', methods=['POST'])
@roles_required('Government Official')
def create_inter_agency_request():
    data = request.get_json(silent=True) or {}
    req_agency = data.get('requesting_agency') or 'District Administration'
    rec_agency = data.get('receiving_agency') or 'National Disaster Response Force (NDRF)'
    cap = (data.get('capability') or '').strip()
    qty = int(data.get('quantity') or 1)
    urgency = data.get('urgency') or 'Immediate'
    dest = (data.get('destination') or '').strip()
    needed_by = (data.get('needed_by') or 'Immediate').strip()

    if not cap or not dest:
        return jsonify({'error': 'Capability and destination are required.'}), 400

    conn = get_db()
    max_i = conn.execute("SELECT MAX(CAST(SUBSTR(id, 10) AS INTEGER)) FROM inter_agency_requests").fetchone()
    next_num = (max_i[0] or 0) + 1
    iar_id = f"IAR-2026-{next_num:02d}"

    inc_id = data.get('incident_id')
    if inc_id:
        chk_inc = conn.execute("SELECT id FROM incidents WHERE id = ?", (inc_id,)).fetchone()
        inc_id = chk_inc['id'] if chk_inc else None
    if not inc_id:
        chk_def = conn.execute("SELECT id FROM incidents WHERE id = 'INC-2026-FLOOD'").fetchone()
        inc_id = chk_def['id'] if chk_def else None
    if not inc_id:
        chk_any = conn.execute("SELECT id FROM incidents LIMIT 1").fetchone()
        inc_id = chk_any['id'] if chk_any else None
    if not inc_id:
        return jsonify({'error': 'An active incident is required for inter-agency coordination.'}), 400

    with conn:
        conn.execute('''
            INSERT INTO inter_agency_requests (id, incident_id, requesting_agency, receiving_agency, capability, quantity, urgency, destination, needed_by, status, submitted_by_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Mobilized', ?)
        ''', (iar_id, inc_id, req_agency, rec_agency, cap, qty, urgency, dest, needed_by, session['user_id']))
        database.log_audit_event(conn, session['user_id'], 'CREATE_INTER_AGENCY_REQUEST', 'inter_agency_requests', iar_id, new_state={'capability': cap, 'receiving_agency': rec_agency})

    return jsonify(dict(conn.execute("SELECT * FROM inter_agency_requests WHERE id = ?", (iar_id,)).fetchone())), 201

@api_bp.route('/api/incidents/<incident_id>/report', methods=['GET'])
def get_incident_operational_report(incident_id):
    conn = get_db()
    inc = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
    if not inc:
        return jsonify({'error': 'Incident not found'}), 404

    # Comprehensive live DB aggregations
    total_reqs = conn.execute("SELECT COUNT(*) FROM emergency_requests WHERE incident_id = ?", (incident_id,)).fetchone()[0]
    delivered_reqs = conn.execute("SELECT COUNT(*) FROM emergency_requests WHERE incident_id = ? AND status = 'Delivered'", (incident_id,)).fetchone()[0]
    total_dispatches = conn.execute("SELECT COUNT(*) FROM dispatches WHERE incident_id = ?", (incident_id,)).fetchone()[0]
    active_volunteers = conn.execute("SELECT COUNT(*) FROM volunteers WHERE status = 'On task'").fetchone()[0]
    shelter_occupants = conn.execute("SELECT COALESCE(SUM(occupants), 0) FROM shelters").fetchone()[0]

    # Dynamic funds aggregation
    budget_row = conn.execute("SELECT COALESCE(SUM(budget_amount_paise), 0) FROM fund_budgets WHERE incident_id = ?", (incident_id,)).fetchone()
    spent_row = conn.execute("SELECT COALESCE(SUM(amount_paise), 0) FROM fund_transactions WHERE incident_id = ? AND transaction_type = 'Payment'", (incident_id,)).fetchone()
    budget_paise = budget_row[0]
    spent_paise = spent_row[0]

    total_admissions = conn.execute("SELECT COUNT(*) FROM shelter_admissions WHERE incident_id = ?", (incident_id,)).fetchone()[0]

    return jsonify({
        'incident': dict(inc),
        'metrics': {
            'totalRequests': total_reqs,
            'deliveredRequests': delivered_reqs,
            'totalDispatches': total_dispatches,
            'activeVolunteers': active_volunteers,
            'shelterOccupants': shelter_occupants,
            'budgetAllocatedPaise': budget_paise,
            'budgetSpentPaise': spent_paise,
            'budgetRemainingPaise': max(0, budget_paise - spent_paise),
            'budgetAllocatedInr': budget_paise / 100,
            'budgetSpentInr': spent_paise / 100
        },
        'requests': {
            'total': total_reqs,
            'delivered': delivered_reqs
        },
        'finance': {
            'budget_paise': budget_paise,
            'total_paid_paise': spent_paise,
            'remaining_paise': max(0, budget_paise - spent_paise)
        },
        'shelter_admissions': total_admissions
    })
