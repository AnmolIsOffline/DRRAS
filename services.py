"""
DRRAS Enterprise Core Business Services
Implements transactional workflows, state machines, inventory reservations,
and audit trail generation for the DRRAS disaster response platform.
"""

import json
from datetime import datetime, timezone
from database import calc_inventory_status, log_system_event, log_audit_event, create_notification

class BusinessLogicError(Exception):
    def __init__(self, message, code="BUSINESS_LOGIC_ERROR", status_code=400, details=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


def required_vehicle_capacity(conn, request_id):
    """Return the outstanding relief units needed for a request, using the same
    explicit items or legacy need mapping that allocation consumes."""
    rows=conn.execute("SELECT resource_id,quantity_requested,quantity_reserved FROM request_items WHERE request_id=?",(request_id,)).fetchall()
    if rows:
        return sum(max(0,int(r['quantity_requested'] or 0)-int(r['quantity_reserved'] or 0)) for r in rows)
    req=conn.execute('SELECT need,people_affected FROM emergency_requests WHERE id=?',(request_id,)).fetchone()
    if not req: return 0
    need=(req['need'] or '').lower(); people=req['people_affected'] or 1
    quantities=[]
    if 'water' in need: quantities.append(('water',min(people*2,20)))
    if 'food' in need or 'ration' in need: quantities.append(('food',min(max(1,people//2),10)))
    if 'medical' in need: quantities.append(('medical',min(max(1,people//4),5)))
    if 'blanket' in need: quantities.append(('blanket',min(people,10)))
    if 'tent' in need: quantities.append(('tent',min(max(1,people//5),2)))
    return sum(qty for pattern,qty in quantities if conn.execute("SELECT 1 FROM resources WHERE LOWER(name) LIKE ? LIMIT 1",(f'%{pattern}%',)).fetchone())

# =========================================================================
# 1. EMERGENCY REQUEST WORKFLOWS
# =========================================================================

def claim_request_service(conn, request_id, owner_type, organization_id, actor_id):
    row = conn.execute("SELECT id,status,verification_status,response_owner_type FROM emergency_requests WHERE id=?", (request_id,)).fetchone()
    if not row:
        raise BusinessLogicError("Emergency request not found", code="NOT_FOUND", status_code=404)
    if row['status'] in ('Rejected', 'Closed', 'Delivered', 'Duplicate', 'Cancelled') or row['verification_status'] == 'Rejected':
        raise BusinessLogicError("This request is no longer available for assignment.", code="REQUEST_INELIGIBLE", status_code=409)

    claimed_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
    changed = conn.execute("""UPDATE emergency_requests
        SET response_owner_type=?,response_organization_id=?,claimed_at=?
        WHERE id=? AND response_owner_type IS NULL
          AND NOT EXISTS(SELECT 1 FROM response_assignments a
              WHERE a.request_id=emergency_requests.id AND a.status IN ('Assigned','Active'))""",
        (owner_type, organization_id, claimed_at, request_id)).rowcount
    if changed != 1:
        raise BusinessLogicError("Another organization has already claimed this request.", code="REQUEST_CLAIMED", status_code=409)

    log_audit_event(conn, actor_id, 'CLAIM_EMERGENCY_REQUEST', 'emergency_requests', request_id,
                    new_state={'owner_type': owner_type, 'organization_id': organization_id, 'claimed_at': claimed_at})
    log_system_event(conn, 'request_claimed', {
        'request_id': request_id,
        'owner_type': owner_type,
        'organization_id': organization_id,
    })
    return claimed_at


def verify_request_service(conn, request_id, decision, reason, actor_id, actor_role, response_personnel_id=None, driver_user_id=None, vehicle_id=None):
    """
    Verifies, requests info, rejects, or marks duplicate an emergency request.
    Decisions: 'Verified', 'More Information Required', 'Rejected'
    """
    row = conn.execute("SELECT * FROM emergency_requests WHERE id = ?", (request_id,)).fetchone()
    if not row:
        raise BusinessLogicError("Emergency request not found", code="NOT_FOUND", status_code=404)

    if actor_role not in ('Administrator', 'Government Official'):
        raise BusinessLogicError("Only Government Officials or Administrators can verify emergency requests.", code="FORBIDDEN", status_code=403)
    if row['response_owner_type'] not in (None, 'government'):
        raise BusinessLogicError("This request has already been accepted by an NGO.", code="REQUEST_CLAIMED", status_code=409)

    old_status = row['status']
    old_vstatus = row['verification_status'] or 'Unverified'

    if decision == 'Verified':
        try:
            response_personnel_id = int(response_personnel_id)
            driver_user_id = int(driver_user_id)
            vehicle_id = int(vehicle_id)
        except (TypeError, ValueError):
            raise BusinessLogicError('Select an eligible Government response person, Government Driver, and compatible Government vehicle before verification.', code='RESPONSE_ASSIGNMENT_REQUIRED', status_code=400)
        personnel = conn.execute("SELECT * FROM government_personnel WHERE id=? AND status='Active'", (response_personnel_id,)).fetchone()
        if not personnel:
            raise BusinessLogicError('Selected Government response person is unavailable or inactive.', code='PERSONNEL_UNAVAILABLE', status_code=409)
        if conn.execute("SELECT 1 FROM response_assignments WHERE government_personnel_id=? AND status IN ('Assigned','Active')", (response_personnel_id,)).fetchone():
            raise BusinessLogicError('Selected Government response person already has an active assignment.', code='PERSONNEL_UNAVAILABLE', status_code=409)
        driver = conn.execute("SELECT id,name FROM users WHERE id=? AND role='Driver' AND status='ACTIVE' AND organization_id IS NULL", (driver_user_id,)).fetchone()
        approved = conn.execute("SELECT 1 FROM government_driver_approvals WHERE user_id=?", (driver_user_id,)).fetchone()
        active_trip = conn.execute("SELECT 1 FROM dispatches WHERE driver_user_id=? AND status IN ('Loading','Ready','En route','Arrived','Delivered Pending Proof','Delivered Pending Confirmation','Needs Review','Proof Rejected')", (driver_user_id,)).fetchone()
        assigned_trip = conn.execute("SELECT 1 FROM response_assignments WHERE driver_user_id=? AND status IN ('Assigned','Active')", (driver_user_id,)).fetchone()
        if not driver or not approved or active_trip or assigned_trip:
            raise BusinessLogicError('Selected Government Driver is not approved, active, or available.', code='DRIVER_UNAVAILABLE', status_code=409)
        vehicle = conn.execute("""SELECT * FROM vehicles WHERE id=? AND owner_type='government' AND owner_organization_id IS NULL
            AND status='Available' AND current_driver_user_id IS NULL
            AND NOT EXISTS(SELECT 1 FROM dispatches d WHERE d.vehicle_id=vehicles.id AND d.status IN ('Loading','Ready','En route','Arrived','Delivered Pending Proof','Delivered Pending Confirmation','Needs Review','Proof Rejected'))
            AND NOT EXISTS(SELECT 1 FROM response_assignments a WHERE a.vehicle_id=vehicles.id AND a.status IN ('Assigned','Active'))""", (vehicle_id,)).fetchone()
        need_text=(row['need'] or '').lower()
        vehicle_pattern='%Ambulance%' if 'medical' in need_text else '%Rescue%' if ('rescue' in need_text or 'boat' in need_text) else '%Cargo%' if ('food' in need_text or 'ration' in need_text) else '%Relief%'
        if not vehicle or not (vehicle['vehicle_type'].lower().find(vehicle_pattern.strip('%').lower()) >= 0 or vehicle['vehicle_code'].lower().find(vehicle_pattern.strip('%').lower()) >= 0):
            raise BusinessLogicError('Selected vehicle is unavailable or incompatible with the Government request.', code='VEHICLE_UNAVAILABLE', status_code=409)
        if required_vehicle_capacity(conn,request_id) > int(vehicle['capacity_units'] or 0):
            raise BusinessLogicError('Selected Government vehicle does not have enough capacity for this request.',code='VEHICLE_CAPACITY_INSUFFICIENT',status_code=409)
        claim_request_service(conn, request_id, 'government', None, actor_id)
        conn.execute("INSERT INTO response_assignments (request_id,owner_type,government_personnel_id,driver_user_id,vehicle_id,status,assigned_by_user_id,notes) VALUES (?,'government',?,?,?,'Assigned',?,?)", (request_id,response_personnel_id,driver_user_id,vehicle_id,actor_id,reason))
        conn.execute("UPDATE vehicles SET status='Reserved',current_driver_user_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='Available'", (driver_user_id,vehicle_id))
        if conn.execute("SELECT changes()").fetchone()[0] != 1:
            raise BusinessLogicError('Selected vehicle was reserved by another operation. Refresh and retry.', code='VEHICLE_UNAVAILABLE', status_code=409)
        new_vstatus = 'Verified'
        new_status = 'Awaiting allocation' if old_status in ('Under Review', 'Submitted', 'Unverified') else old_status
    elif decision == 'More Information Required':
        new_vstatus = 'More Information Required'
        new_status = 'More Information Required'
    elif decision == 'Rejected':
        new_vstatus = 'Rejected'
        new_status = 'Rejected'
    else:
        raise BusinessLogicError(f"Invalid verification decision: {decision}", code="INVALID_DECISION", status_code=400)

    conn.execute('''
        UPDATE emergency_requests
        SET verification_status = ?, status = ?, verified_by_user_id = ?, verified_at = CURRENT_TIMESTAMP, review_reason = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (new_vstatus, new_status, actor_id, reason, request_id))

    # Record event
    conn.execute('''
        INSERT INTO request_events (request_id, event_type, from_status, to_status, reason, actor_user_id)
        VALUES (?, 'VERIFICATION_DECISION', ?, ?, ?, ?)
    ''', (request_id, old_vstatus, new_vstatus, reason, actor_id))

    log_audit_event(conn, actor_id, 'VERIFY_REQUEST', 'emergency_requests', request_id,
                    old_state={'status': old_status, 'verification_status': old_vstatus},
                    new_state={'status': new_status, 'verification_status': new_vstatus},
                    reason=reason)

    log_system_event(conn, 'request_updated', {'id': request_id, 'status': new_status, 'verification_status': new_vstatus})
    return conn.execute("SELECT * FROM emergency_requests WHERE id = ?", (request_id,)).fetchone()


def mark_duplicate_request_service(conn, request_id, primary_request_id, reason, actor_id, actor_role):
    if request_id == primary_request_id:
        raise BusinessLogicError("A request cannot be marked as a duplicate of itself.", code="INVALID_DUPLICATE", status_code=400)

    req = conn.execute("SELECT * FROM emergency_requests WHERE id = ?", (request_id,)).fetchone()
    if not req:
        raise BusinessLogicError("Request not found", code="NOT_FOUND", status_code=404)

    primary = conn.execute("SELECT * FROM emergency_requests WHERE id = ?", (primary_request_id,)).fetchone()
    if not primary:
        raise BusinessLogicError("Primary request to link as duplicate does not exist.", code="PRIMARY_NOT_FOUND", status_code=404)

    # Check circular duplication
    if primary['duplicate_of_request_id'] == request_id:
        raise BusinessLogicError("Circular duplicate relationship detected.", code="CIRCULAR_DUPLICATE", status_code=400)

    old_status = req['status']
    conn.execute('''
        UPDATE emergency_requests
        SET status = 'Duplicate', duplicate_of_request_id = ?, review_reason = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (primary_request_id, reason, request_id))

    conn.execute('''
        INSERT INTO request_events (request_id, event_type, from_status, to_status, reason, actor_user_id, notes)
        VALUES (?, 'MARKED_DUPLICATE', ?, 'Duplicate', ?, ?, ?)
    ''', (request_id, old_status, reason, actor_id, f"Duplicate of {primary_request_id}"))

    log_audit_event(conn, actor_id, 'MARK_DUPLICATE', 'emergency_requests', request_id,
                    old_state={'status': old_status}, new_state={'status': 'Duplicate', 'primary_id': primary_request_id}, reason=reason)
    return conn.execute("SELECT * FROM emergency_requests WHERE id = ?", (request_id,)).fetchone()


def allocate_request_service(conn, request_id, actor_id, actor_role, idempotency_key=None, emergency_override=False, selected_driver_id=None, selected_vehicle_id=None):
    """
    Atomic Request Allocation Service:
    1. Validates request state and verification.
    2. Identifies required items from request_items or maps legacy text need.
    3. Checks warehouse stock and creates active stock reservation.
    4. Selects active driver and compatible available vehicle.
    5. Creates linked dispatch and dispatch manifest items.
    6. Records inventory transactions and logs audit event atomically.
    """
    row = conn.execute("SELECT * FROM emergency_requests WHERE id = ?", (request_id,)).fetchone()
    if not row:
        raise BusinessLogicError("Emergency request not found", code="NOT_FOUND", status_code=404)

    if row['status'] == 'Delivered':
        raise BusinessLogicError("Request has already been delivered and cannot be reallocated.", code="ALREADY_DELIVERED", status_code=400)

    if row['status'] == 'Closed':
        raise BusinessLogicError("Request is closed and cannot be reallocated.", code="ALREADY_CLOSED", status_code=400)

    expected_owner = 'ngo' if actor_role == 'NGO Coordinator' else 'government'
    actor_org = None
    if actor_role == 'NGO Coordinator':
        actor_org = conn.execute("SELECT COALESCE(u.organization_id,(SELECT organization_id FROM organization_memberships WHERE user_id=u.id AND membership_role='Coordinator' AND status='Active' LIMIT 1)) FROM users u WHERE u.id=?", (actor_id,)).fetchone()[0]

    # Idempotency is scoped to the owning response team; never return another organization's dispatch.
    if row['status'] in ('Allocated', 'Dispatched'):
        existing_dsp = conn.execute("SELECT * FROM dispatches WHERE request_id=? AND owner_type=? AND owner_organization_id IS ? ORDER BY id DESC LIMIT 1", (request_id,expected_owner,actor_org)).fetchone()
        if existing_dsp:
            return {'request':dict(row),'dispatch':dict(existing_dsp),'message':'Request is already allocated to this response owner.'}
        if conn.execute("SELECT 1 FROM dispatches WHERE request_id=? LIMIT 1",(request_id,)).fetchone():
            raise BusinessLogicError('This request already has an active dispatch owned by another response organization.',code='ALLOCATION_SCOPE_DENIED',status_code=409)

    if row['response_owner_type'] != expected_owner or (expected_owner == 'ngo' and row['response_organization_id'] != actor_org):
        raise BusinessLogicError('This request has not been claimed by this response organization.', code='ALLOCATION_SCOPE_DENIED', status_code=409)
    if row['verification_status'] != 'Verified' and not emergency_override and expected_owner != 'ngo':
        raise BusinessLogicError(f"Request cannot be allocated in verification status '{row['verification_status']}'. Must be verified before Government allocation.", code="UNVERIFIED_REQUEST", status_code=409)

    # Every fulfilment must use the response team saved during verification/NGO acceptance.
    assignment = conn.execute("SELECT * FROM response_assignments WHERE request_id=? AND owner_type=? AND organization_id IS ? AND status IN ('Assigned','Active') ORDER BY id DESC LIMIT 1", (request_id,expected_owner,actor_org)).fetchone()
    if not assignment:
        raise BusinessLogicError('A response person/Volunteer, approved Driver, and compatible vehicle must be assigned before resource allocation.', code='RESPONSE_ASSIGNMENT_REQUIRED', status_code=409)
    if assignment['owner_type'] != expected_owner or (expected_owner == 'ngo' and assignment['organization_id'] != actor_org):
        raise BusinessLogicError('This response assignment is owned by a different organization.', code='ALLOCATION_SCOPE_DENIED', status_code=403)
    if selected_driver_id is not None and int(selected_driver_id) != assignment['driver_user_id']:
        raise BusinessLogicError('Allocation must use the Driver selected in the response assignment.', code='ASSIGNED_DRIVER_MISMATCH', status_code=409)
    if selected_vehicle_id is not None and int(selected_vehicle_id) != assignment['vehicle_id']:
        raise BusinessLogicError('Allocation must use the vehicle selected in the response assignment.', code='ASSIGNED_VEHICLE_MISMATCH', status_code=409)
    driver_row = conn.execute("SELECT id,name FROM users WHERE id=? AND role='Driver' AND status='ACTIVE'", (assignment['driver_user_id'],)).fetchone()
    if not driver_row:
        raise BusinessLogicError('The assigned Driver is no longer active.', code='DRIVER_UNAVAILABLE', status_code=409)
    active_other = conn.execute("SELECT 1 FROM dispatches WHERE driver_user_id=? AND request_id<>? AND status IN ('Loading','Ready','En route','Arrived','Delivered Pending Proof','Delivered Pending Confirmation','Needs Review','Proof Rejected')", (assignment['driver_user_id'],request_id)).fetchone()
    if active_other:
        raise BusinessLogicError('The assigned Driver has another unresolved trip.', code='DRIVER_UNAVAILABLE', status_code=409)
    driver_id, driver_name = driver_row['id'], driver_row['name']
    vehicle_row = conn.execute("""SELECT id,vehicle_code,registration_number,vehicle_type,capacity_units,status,current_driver_user_id FROM vehicles
        WHERE id=? AND owner_type=? AND owner_organization_id IS ? AND status IN ('Available','Reserved')
          AND (current_driver_user_id IS NULL OR current_driver_user_id=?)
          AND NOT EXISTS(SELECT 1 FROM dispatches d WHERE d.vehicle_id=vehicles.id AND d.status IN ('Loading','Ready','En route','Arrived','Delivered Pending Proof','Delivered Pending Confirmation','Needs Review','Proof Rejected'))
          AND NOT EXISTS(SELECT 1 FROM response_assignments a WHERE a.vehicle_id=vehicles.id AND a.status IN ('Assigned','Active') AND a.id<>?)""", (assignment['vehicle_id'],expected_owner,actor_org,driver_id,assignment['id'])).fetchone()
    if not vehicle_row:
        raise BusinessLogicError('The assigned vehicle is no longer available in the correct owner scope.', code='VEHICLE_UNAVAILABLE', status_code=409)
    wh_row = conn.execute("SELECT id FROM warehouses WHERE owner_type=? AND owner_organization_id IS ? AND status='Active' ORDER BY id LIMIT 1", (expected_owner,actor_org)).fetchone()
    if not wh_row:
        raise BusinessLogicError('No active warehouse is configured for this response owner.', code='WAREHOUSE_UNAVAILABLE', status_code=409)
    wh_id = wh_row['id']

    # Determine items to allocate
    req_items = conn.execute("SELECT * FROM request_items WHERE request_id = ?", (request_id,)).fetchall()
    items_to_reserve = []

    if req_items:
        for it in req_items:
            qty = it['quantity_requested'] - it['quantity_reserved']
            if qty > 0:
                items_to_reserve.append({'resource_id': it['resource_id'], 'quantity': qty, 'item_id': it['id']})
    else:
        # Map legacy text need to resources
        need_lower = (row['need'] or '').lower()
        people = row['people_affected'] or 1
        mappings = []
        if 'water' in need_lower:
            mappings.append(('water', min(people * 2, 20)))
        if 'food' in need_lower or 'ration' in need_lower:
            mappings.append(('food', min(max(1, people // 2), 10)))
        if 'medical' in need_lower:
            mappings.append(('medical', min(max(1, people // 4), 5)))
        if 'blanket' in need_lower:
            mappings.append(('blanket', min(people, 10)))
        if 'tent' in need_lower:
            mappings.append(('tent', min(max(1, people // 5), 2)))

        if not mappings:
            raise BusinessLogicError('Add explicit request resource items before allocation; the assistance description has no unambiguous resource mapping.', code='RESOURCE_MAPPING_REQUIRED', status_code=409)

        for pattern, qty in mappings:
            res_row = conn.execute("SELECT id FROM resources WHERE LOWER(name) LIKE ? LIMIT 1", (f"%{pattern}%",)).fetchone()
            if res_row:
                items_to_reserve.append({'resource_id': res_row[0], 'quantity': qty, 'item_id': None})

    requested_capacity = sum(max(0, int(item['quantity'])) for item in items_to_reserve)
    if requested_capacity > int(vehicle_row['capacity_units'] or 0):
        raise BusinessLogicError(
            f"The assigned vehicle capacity ({vehicle_row['capacity_units'] or 0} relief units) is below the requested load ({requested_capacity} units).",
            code='VEHICLE_CAPACITY_INSUFFICIENT', status_code=409
        )

    # Validate stock availability
    for item in items_to_reserve:
        st_row = conn.execute('''
            SELECT id, on_hand_units, reserved_units, (on_hand_units - reserved_units) AS available
            FROM warehouse_stock
            WHERE warehouse_id = ? AND resource_id = ?
        ''', (wh_id, item['resource_id'])).fetchone()

        avail = (st_row['available'] if st_row else 0)
        if avail < item['quantity']:
            res_name = conn.execute("SELECT name FROM resources WHERE id = ?", (item['resource_id'],)).fetchone()[0]
            raise BusinessLogicError(
                f"Insufficient stock for resource '{res_name}'. Available to allocate: {avail}, required: {item['quantity']}.",
                code="INSUFFICIENT_STOCK",
                status_code=409,
                details={'resource_id': item['resource_id'], 'resource_name': res_name, 'available': avail, 'requested': item['quantity']}
            )

    # Assignment was validated above. The saved driver and vehicle are authoritative.
    veh_id = vehicle_row['id']
    veh_display = f"{vehicle_row['vehicle_code']} ? {vehicle_row['vehicle_type']}"
    owner_org_id = assignment['organization_id'] if expected_owner == 'ngo' else None

    # Generate dispatch ID
    max_dsp_row = conn.execute("SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM dispatches").fetchone()
    next_dsp_num = (max_dsp_row[0] or 0) + 1
    dsp_id = f"DSP-{next_dsp_num:02d}"

    # Generate Reservation ID
    resv_id = f"RSV-{next_dsp_num:03d}"

    # 1. Update Request
    conn.execute("UPDATE emergency_requests SET status = 'Allocated', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (request_id,))

    # 2. Create Dispatch
    conn.execute('''
        INSERT INTO dispatches (id, vehicle, driver, destination, load_items, status, eta, request_id, vehicle_id, driver_user_id, created_by_user_id, warehouse_id, incident_id, zone_id, owner_type, owner_organization_id)
        VALUES (?, ?, ?, ?, ?, 'Loading', 'Not recorded', ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (dsp_id, veh_display, driver_name, row['area'], row['need'], request_id, veh_id, driver_id, actor_id, wh_id, row['incident_id'], row['zone_id'], expected_owner, owner_org_id))

    if veh_id:
        conn.execute("UPDATE vehicles SET status = 'Loading', current_driver_user_id = ? WHERE id = ?", (driver_id, veh_id))
    conn.execute("UPDATE response_assignments SET dispatch_id=?,status='Active' WHERE id=?", (dsp_id, assignment['id']))
    if assignment['volunteer_id']:
        conn.execute("UPDATE volunteer_tasks SET dispatch_id=? WHERE request_id=? AND volunteer_id=? AND status IN ('Assigned','Accepted','In Progress')", (dsp_id,request_id,assignment['volunteer_id']))

    # 3. Create Reservation
    conn.execute('''
        INSERT INTO inventory_reservations (id, request_id, dispatch_id, status, reserved_by_user_id, idempotency_key)
        VALUES (?, ?, ?, 'Active', ?, ?)
    ''', (resv_id, request_id, dsp_id, actor_id, idempotency_key))

    # 4. Reserve Stock and record Reservation Items & Ledger Transactions
    for item in items_to_reserve:
        st_row = conn.execute("SELECT id FROM warehouse_stock WHERE warehouse_id = ? AND resource_id = ?", (wh_id, item['resource_id'])).fetchone()
        st_id = st_row['id']
        qty = item['quantity']

        conn.execute('''
            UPDATE warehouse_stock
            SET reserved_units = reserved_units + ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (qty, st_id))

        conn.execute('''
            INSERT INTO inventory_reservation_items (reservation_id, warehouse_stock_id, quantity_units)
            VALUES (?, ?, ?)
        ''', (resv_id, st_id, qty))

        conn.execute('''
            INSERT INTO inventory_transactions (warehouse_stock_id, transaction_type, quantity_units, direction, reference_type, reference_id, performed_by_user_id, reason)
            VALUES (?, 'Reserved', ?, 'MEMO', 'emergency_requests', ?, ?, 'Stock reserved for dispatch allocation')
        ''', (st_id, qty, request_id, actor_id))

        if item['item_id']:
            conn.execute("UPDATE request_items SET quantity_reserved = quantity_reserved + ? WHERE id = ?", (qty, item['item_id']))
        else:
            conn.execute('''
                INSERT INTO request_items (request_id, resource_id, quantity_requested, quantity_reserved)
                VALUES (?, ?, ?, ?)
            ''', (request_id, item['resource_id'], qty, qty))

    # 5. Create Dispatch Items
    for item in items_to_reserve:
        conn.execute('''
            INSERT INTO dispatch_items (dispatch_id, resource_id, quantity_planned, quantity_loaded)
            VALUES (?, ?, ?, ?)
        ''', (dsp_id, item['resource_id'], item['quantity'], item['quantity']))

    # 6. Recalculate status for warehouse stock
    inv_items = conn.execute("SELECT id, available_units, target_stock FROM inventory").fetchall()
    for inv_item in inv_items:
        new_st = calc_inventory_status(inv_item['available_units'], inv_item['target_stock'])
        conn.execute("UPDATE inventory SET status = ? WHERE id = ?", (new_st, inv_item['id']))

    # 7. Audit, Activities & Events
    conn.execute('''
        INSERT INTO activities (workspace_key, title, details)
        VALUES ('dispatches', ?, ?)
    ''', (f"Allocation: {dsp_id} for {request_id}", f"Dispatched {veh_display} to {row['area']} (Driver: {driver_name})."))

    conn.execute('''
        INSERT INTO request_events (request_id, event_type, from_status, to_status, reason, actor_user_id, notes)
        VALUES (?, 'ALLOCATED', ?, 'Allocated', 'Resources allocated and dispatch generated', ?, ?)
    ''', (request_id, row['status'], actor_id, f"Dispatch: {dsp_id}, Vehicle: {veh_display}, Driver: {driver_name}"))

    log_audit_event(conn, actor_id, 'ALLOCATE_REQUEST', 'emergency_requests', request_id,
                    old_state={'status': row['status']},
                    new_state={'status': 'Allocated', 'dispatch_id': dsp_id, 'driver': driver_name, 'vehicle': veh_display},
                    reason='Authorized resource allocation')

    create_notification(conn, driver_id, 'dispatch_assigned', f"New Trip: {dsp_id}", f"You have been assigned to deliver supplies to {row['area']}.", 'dispatches', dsp_id)

    log_system_event(conn, 'request_allocated', {
        'id': request_id,
        'dispatch_id': dsp_id,
        'driver': driver_name,
        'vehicle': veh_display
    })
    log_system_event(conn, 'inventory_updated', {'action': 'allocated_deduction', 'request_id': request_id})

    return {
        'request': dict(conn.execute("SELECT * FROM emergency_requests WHERE id = ?", (request_id,)).fetchone()),
        'dispatch': dict(conn.execute("SELECT * FROM dispatches WHERE id = ?", (dsp_id,)).fetchone()),
        'dispatch_id': dsp_id,
        'reservation_id': resv_id
    }


# =========================================================================
# 2. DISPATCH & FLEET WORKFLOWS
# =========================================================================

def driver_start_trip_service(conn, dispatch_id, actor_id, actor_name, actor_role):
    """
    Assigned Driver starts the trip: Loading/Ready -> En route
    """
    dsp = conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()
    if not dsp:
        raise BusinessLogicError("Dispatch record not found", code="NOT_FOUND", status_code=404)

    if actor_role not in ('Driver', 'Administrator', 'Government Official'):
        raise BusinessLogicError("You are not authorized to operate dispatches.", code="FORBIDDEN", status_code=403)
    if actor_role == 'Driver' and dsp['driver_user_id'] != actor_id:
        raise BusinessLogicError("You are not authorized to operate another driver's dispatch.", code="FORBIDDEN", status_code=403)

    if dsp['status'] in ('Delivered', 'Cancelled', 'En route'):
        raise BusinessLogicError(f"Cannot start trip from current status '{dsp['status']}'.", code="INVALID_STATUS", status_code=400)

    # Transition to En route
    conn.execute('''
        UPDATE dispatches
        SET status = 'En route', departed_at = CURRENT_TIMESTAMP, eta = 'Not recorded', route_status = 'Clear', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (dispatch_id,))

    if dsp['vehicle_id']:
        conn.execute("UPDATE vehicles SET status = 'EnRoute' WHERE id = ?", (dsp['vehicle_id'],))

    if dsp['request_id']:
        conn.execute("UPDATE emergency_requests SET status = 'Dispatched', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (dsp['request_id'],))
        conn.execute('''
            INSERT INTO request_events (request_id, event_type, from_status, to_status, notes, actor_user_id)
            VALUES (?, 'DISPATCH_DEPARTED', 'Allocated', 'Dispatched', 'Relief vehicle is en route', ?)
        ''', (dsp['request_id'], actor_id))

    log_audit_event(conn, actor_id, 'START_DISPATCH', 'dispatches', dispatch_id,
                    old_state={'status': dsp['status']}, new_state={'status': 'En route'})
    log_system_event(conn, 'dispatch_advanced', {'id': dispatch_id, 'status': 'En route', 'request_id': dsp['request_id']})

    return conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()


def driver_arrive_service(conn, dispatch_id, actor_id, actor_name, actor_role):
    """
    Driver arrives at delivery destination: En route -> Arrived
    """
    dsp = conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()
    if not dsp:
        raise BusinessLogicError("Dispatch record not found", code="NOT_FOUND", status_code=404)

    if actor_role not in ('Driver', 'Administrator', 'Government Official'):
        raise BusinessLogicError("You are not authorized to operate dispatches.", code="FORBIDDEN", status_code=403)
    if actor_role == 'Driver' and dsp['driver_user_id'] != actor_id:
        raise BusinessLogicError("You are not authorized to operate this dispatch.", code="FORBIDDEN", status_code=403)

    if dsp['status'] != 'En route':
        raise BusinessLogicError(f"Dispatch must be 'En route' to arrive. Current status is '{dsp['status']}'.", code="INVALID_STATUS", status_code=400)

    conn.execute('''
        UPDATE dispatches
        SET status = 'Arrived', arrived_at = CURRENT_TIMESTAMP, eta = 'At site', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (dispatch_id,))

    log_audit_event(conn, actor_id, 'ARRIVE_DISPATCH', 'dispatches', dispatch_id,
                    old_state={'status': 'En route'}, new_state={'status': 'Arrived'})
    log_system_event(conn, 'dispatch_advanced', {'id': dispatch_id, 'status': 'Arrived', 'request_id': dsp['request_id']})
    return conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()


def report_route_blockage_service(conn, dispatch_id, actor_id, actor_name, actor_role, reason, notes=None, lat=None, lng=None):
    """
    Driver reports flood water / route blockage: transitions to 'Route Blocked'
    """
    dsp = conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()
    if not dsp:
        raise BusinessLogicError("Dispatch record not found", code="NOT_FOUND", status_code=404)

    if actor_role not in ('Driver', 'Administrator', 'Government Official'):
        raise BusinessLogicError("You are not authorized to operate dispatches.", code="FORBIDDEN", status_code=403)
    if actor_role == 'Driver' and dsp['driver_user_id'] != actor_id:
        raise BusinessLogicError("You are not authorized to update this dispatch.", code="FORBIDDEN", status_code=403)

    conn.execute('''
        UPDATE dispatches
        SET route_status = 'Blocked', route_blockage_reason = ?, status = 'Route Blocked', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (reason, dispatch_id))

    # Create activity
    conn.execute('''
        INSERT INTO activities (workspace_key, title, details)
        VALUES ('dispatches', ?, ?)
    ''', (f"Route Blocked: {dispatch_id}", f"Driver {dsp['driver']} encountered road block: {reason}. {notes or ''}"))

    # Notify command official
    officials = conn.execute("SELECT id FROM users WHERE role = 'Government Official'").fetchall()
    for off in officials:
        create_notification(conn, off['id'], 'route_blockage', f"Route Blockage: {dispatch_id}", f"{dsp['driver']} reported '{reason}' en route to {dsp['destination']}.", 'dispatches', dispatch_id)

    log_audit_event(conn, actor_id, 'ROUTE_BLOCKAGE', 'dispatches', dispatch_id, reason=reason)
    log_system_event(conn, 'route_blocked', {'id': dispatch_id, 'reason': reason})
    return conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()


def reroute_dispatch_service(conn, dispatch_id, actor_id, new_destination, reason):
    """
    Government Official or Coordinator re-routes a blocked dispatch.
    """
    dsp = conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()
    if not dsp:
        raise BusinessLogicError("Dispatch record not found", code="NOT_FOUND", status_code=404)

    old_dest = dsp['destination']
    conn.execute('''
        UPDATE dispatches
        SET destination = ?, route_status = 'Rerouted', status = 'En route', eta = 'Not recorded', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (new_destination, dispatch_id))

    log_audit_event(conn, actor_id, 'REROUTE_DISPATCH', 'dispatches', dispatch_id,
                    old_state={'destination': old_dest, 'status': dsp['status']},
                    new_state={'destination': new_destination, 'status': 'En route'},
                    reason=reason)

    if dsp['driver_user_id']:
        create_notification(conn, dsp['driver_user_id'], 'trip_rerouted', f"Rerouted: {dispatch_id}", f"New destination: {new_destination}. Reason: {reason}", 'dispatches', dispatch_id)

    log_system_event(conn, 'dispatch_advanced', {'id': dispatch_id, 'status': 'En route', 'destination': new_destination})
    return conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()


def submit_delivery_proof_service(conn, dispatch_id, actor_id, actor_name, actor_role, proof_type, proof_ref, notes, delivered_items=None):
    dsp = conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()
    if not dsp:
        raise BusinessLogicError("Dispatch not found", code="NOT_FOUND", status_code=404)
    if actor_role not in ('Driver', 'Administrator', 'Government Official'):
        raise BusinessLogicError("You are not authorized to operate dispatches.", code="FORBIDDEN", status_code=403)
    if actor_role == 'Driver':
        if dsp['driver_user_id'] and dsp['driver_user_id'] != actor_id:
            raise BusinessLogicError("You are not authorized to submit proof for another driver's dispatch.", code="FORBIDDEN", status_code=403)
        elif not dsp['driver_user_id'] and actor_name != dsp['driver']:
            raise BusinessLogicError("You are not authorized to submit proof for this dispatch.", code="FORBIDDEN", status_code=403)
    if conn.execute("SELECT id FROM delivery_proofs WHERE dispatch_id = ?", (dispatch_id,)).fetchone():
        raise BusinessLogicError("Delivery proof has already been submitted for this dispatch.", code="PROOF_ALREADY_SUBMITTED", status_code=409)
    if dsp['status'] != 'Arrived':
        raise BusinessLogicError("Dispatch must be Arrived before delivery proof can be submitted.", code="INVALID_STATUS", status_code=409)
    if not isinstance(delivered_items, list) or not delivered_items:
        raise BusinessLogicError("Itemized delivery quantities are required.", code="MANIFEST_REQUIRED", status_code=400)
    manifest = conn.execute("SELECT resource_id, quantity_loaded FROM dispatch_items WHERE dispatch_id = ?", (dispatch_id,)).fetchall()
    if not manifest:
        raise BusinessLogicError("Dispatch has no recorded manifest.", code="MANIFEST_REQUIRED", status_code=409)
    loaded = {r['resource_id']: r['quantity_loaded'] for r in manifest}
    seen = set()
    for item in delivered_items:
        rid = item.get('resource_id')
        if rid not in loaded or rid in seen:
            raise BusinessLogicError("Each proof item must reference a unique resource in this dispatch manifest.", code="INVALID_MANIFEST_ITEM", status_code=400)
        seen.add(rid)
        quantities = [item.get('quantity_delivered', 0), item.get('quantity_returned', 0), item.get('quantity_damaged', 0)]
        if any(isinstance(q, bool) or not isinstance(q, int) or q < 0 for q in quantities):
            raise BusinessLogicError("Delivered, returned and damaged quantities must be non-negative whole numbers.", code="INVALID_QUANTITY", status_code=400)
        if sum(quantities) != loaded[rid]:
            raise BusinessLogicError("For every manifest item, delivered + returned + damaged must equal loaded quantity.", code="QUANTITY_MISMATCH", status_code=409)
    if seen != set(loaded):
        raise BusinessLogicError("Proof must reconcile every item in the dispatch manifest.", code="INCOMPLETE_MANIFEST", status_code=400)
    req_id = dsp['request_id']
    proof_id = f"PRF-{dispatch_id}"
    conn.execute("INSERT INTO delivery_proofs (id, dispatch_id, request_id, submitted_by_user_id, proof_type, proof_reference, notes, delivered_at, status) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 'Submitted')", (proof_id, dispatch_id, req_id, actor_id, proof_type, proof_ref, notes))
    for item in delivered_items:
        rid = item['resource_id']
        q_del = item.get('quantity_delivered', 0)
        q_ret = item.get('quantity_returned', 0)
        q_dam = item.get('quantity_damaged', 0)
        conn.execute("UPDATE dispatch_items SET quantity_delivered = ?, quantity_returned = ?, quantity_damaged = ?, updated_at = CURRENT_TIMESTAMP WHERE dispatch_id = ? AND resource_id = ?", (q_del, q_ret, q_dam, dispatch_id, rid))
        if req_id:
            conn.execute("UPDATE request_items SET quantity_delivered = quantity_delivered + ?, quantity_returned = quantity_returned + ? WHERE request_id = ? AND resource_id = ?", (q_del, q_ret, req_id, rid))
    conn.execute("UPDATE dispatches SET status = 'Delivered Pending Proof', delivered_at = CURRENT_TIMESTAMP, eta = 'Pending Verification', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (dispatch_id,))
    log_audit_event(conn, actor_id, 'SUBMIT_DELIVERY_PROOF', 'delivery_proofs', proof_id, reason=notes)
    log_system_event(conn, 'delivery_proof_submitted', {'dispatch_id': dispatch_id, 'proof_id': proof_id})
    return conn.execute("SELECT * FROM delivery_proofs WHERE id = ?", (proof_id,)).fetchone()


def review_delivery_service(conn, dispatch_id, decision, reason, actor_id, actor_role):
    """
    Supervisor or Government Official reviews delivery proof:
    - If verified/accepted: marks dispatch Delivered, requests Delivered, reconciles stock, sets vehicle Available.
    - If rejected: marks dispatch Proof Rejected, keeps request in Dispatched, keeps vehicle with trip, preserves stock accounting.
    - If needs review: marks dispatch Needs Review, keeps request in Dispatched.
    """
    dsp = conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()
    if not dsp:
        raise BusinessLogicError("Dispatch not found", code="NOT_FOUND", status_code=404)

    if actor_role not in ('Administrator', 'Government Official', 'NGO Coordinator'):
        raise BusinessLogicError("Access denied. Insufficient role to review delivery.", code="FORBIDDEN", status_code=403)

    req_id = dsp['request_id']
    req = conn.execute("SELECT * FROM emergency_requests WHERE id = ?", (req_id,)).fetchone() if req_id else None

    if decision in ('Verified', 'Accept', 'Approved'):
        proof_status = 'Verified'
        new_dsp_status = 'Delivered'

        conn.execute('''
            UPDATE dispatches
            SET status = ?, delivery_result = ?, delivery_notes = ?, delivered_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (new_dsp_status, decision, reason, dispatch_id))

        conn.execute('''
            UPDATE delivery_proofs
            SET status = ?, reviewed_by_user_id = ?, reviewed_at = CURRENT_TIMESTAMP, review_reason = ?
            WHERE dispatch_id = ?
        ''', (proof_status, actor_id, reason, dispatch_id))

        if req_id:
            conn.execute("UPDATE emergency_requests SET status = 'Delivered', delivery_confirmed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (req_id,))
            conn.execute('''
                INSERT INTO request_events (request_id, event_type, from_status, to_status, notes, actor_user_id)
                VALUES (?, 'DELIVERY_VERIFIED', ?, 'Delivered', ?, ?)
            ''', (req_id, req['status'] if req else 'Dispatched', f"Verified by supervisor: {reason}", actor_id))

        # Reconcile inventory reservations & warehouse stock:
        # Decrement reserved_units and on_hand_units, mark reservation 'Issued'
        resv_items = conn.execute('''
            SELECT ri.*, ws.id as ws_id, ws.warehouse_id, ws.resource_id, ws.on_hand_units, ws.reserved_units
            FROM inventory_reservation_items ri
            JOIN inventory_reservations r ON ri.reservation_id = r.id
            JOIN warehouse_stock ws ON ri.warehouse_stock_id = ws.id
            WHERE r.dispatch_id = ? AND r.status = 'Active'
        ''', (dispatch_id,)).fetchall()

        for ritem in resv_items:
            qty = ritem['quantity_units']
            conn.execute('''
                UPDATE warehouse_stock
                SET on_hand_units = MAX(0, on_hand_units - ?),
                    reserved_units = MAX(0, reserved_units - ?),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (qty, qty, ritem['ws_id']))

            conn.execute('''
                UPDATE inventory_reservation_items
                SET issued_units = issued_units + ?
                WHERE id = ?
            ''', (qty, ritem['id']))

            conn.execute('''
                INSERT INTO inventory_transactions (warehouse_stock_id, transaction_type, quantity_units, direction, reference_type, reference_id, performed_by_user_id, reason)
                VALUES (?, 'Issued', ?, 'OUT', 'dispatches', ?, ?, ?)
            ''', (ritem['ws_id'], qty, dispatch_id, actor_id, f"Supplies verified & delivered to recipient: {reason}"))

        conn.execute("UPDATE inventory_reservations SET status = 'Issued', updated_at = CURRENT_TIMESTAMP WHERE dispatch_id = ? AND status = 'Active'", (dispatch_id,))

        conn.execute("UPDATE response_assignments SET status='Completed' WHERE dispatch_id=? AND status='Active'",(dispatch_id,))
        # Vehicle returns to Available on trip completion
        if dsp['vehicle_id']:
            conn.execute("UPDATE vehicles SET status = 'Available', current_driver_user_id = NULL WHERE id = ?", (dsp['vehicle_id'],))

    elif decision in ('Reject', 'Rejected'):
        proof_status = 'Rejected'
        new_dsp_status = 'Proof Rejected'

        conn.execute('''
            UPDATE dispatches
            SET status = ?, delivery_result = ?, delivery_notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (new_dsp_status, decision, reason, dispatch_id))

        conn.execute('''
            UPDATE delivery_proofs
            SET status = ?, reviewed_by_user_id = ?, reviewed_at = CURRENT_TIMESTAMP, review_reason = ?
            WHERE dispatch_id = ?
        ''', (proof_status, actor_id, reason, dispatch_id))

        # IMPORTANT: Request is NOT marked Delivered! It remains Dispatched / Delivery Exception!
        if req_id:
            conn.execute("UPDATE emergency_requests SET status = 'Dispatched', review_reason = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (f"Delivery proof rejected: {reason}", req_id))
            conn.execute('''
                INSERT INTO request_events (request_id, event_type, from_status, to_status, notes, actor_user_id)
                VALUES (?, 'DELIVERY_PROOF_REJECTED', ?, 'Dispatched', ?, ?)
            ''', (req_id, req['status'] if req else 'Dispatched', f"Proof rejected: {reason}", actor_id))

        # Vehicle is NOT marked Available (trip unresolved)
        # Reservation remains Active/accounted for

    else:  # NeedsReview
        proof_status = 'NeedsReview'
        new_dsp_status = 'Needs Review'

        conn.execute('''
            UPDATE dispatches
            SET status = ?, delivery_result = ?, delivery_notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (new_dsp_status, decision, reason, dispatch_id))

        conn.execute('''
            UPDATE delivery_proofs
            SET status = ?, reviewed_by_user_id = ?, reviewed_at = CURRENT_TIMESTAMP, review_reason = ?
            WHERE dispatch_id = ?
        ''', (proof_status, actor_id, reason, dispatch_id))

        if req_id:
            conn.execute('''
                INSERT INTO request_events (request_id, event_type, from_status, to_status, notes, actor_user_id)
                VALUES (?, 'PROOF_NEEDS_REVIEW', ?, ?, ?, ?)
            ''', (req_id, req['status'] if req else 'Dispatched', req['status'] if req else 'Dispatched', f"Proof requires review: {reason}", actor_id))

    log_audit_event(conn, actor_id, 'REVIEW_DELIVERY', 'dispatches', dispatch_id,
                    old_state={'status': dsp['status']}, new_state={'status': new_dsp_status}, reason=reason)
    log_system_event(conn, 'dispatch_advanced', {'id': dispatch_id, 'status': new_dsp_status, 'request_id': req_id})
    return conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()


# =========================================================================
# 3. DONATIONS & IN-KIND VERIFICATION WORKFLOWS
# =========================================================================

def intake_donation_service(conn, data, actor_id):
    """
    Registers a Cash or In-Kind donation.
    """
    dtype = (data.get('donation_type') or 'InKind').strip()
    if dtype not in ('Cash', 'InKind'):
        raise BusinessLogicError("Donation type must be 'Cash' or 'InKind'.", code="INVALID_TYPE", status_code=400)

    actor=conn.execute('SELECT role,organization_id,name FROM users WHERE id=?',(actor_id,)).fetchone()
    if not actor:raise BusinessLogicError('Authenticated donor account is missing.',code='NOT_FOUND',status_code=401)
    role=actor['role']; org_id=None
    donor_name=actor['name'] if role=='Citizen' else (data.get('donor_name') or '').strip()
    if not donor_name:
        raise BusinessLogicError("Donor name is required.", code="VALIDATION_ERROR", status_code=400)

    # Generate ID
    max_d = conn.execute("SELECT MAX(CAST(SUBSTR(id, 10) AS INTEGER)) FROM donations").fetchone()
    next_num = (max_d[0] or 0) + 1
    did = f"DON-2026-{next_num:03d}"

    inc_id = data.get('incident_id')
    if inc_id:
        chk_inc = conn.execute("SELECT id FROM incidents WHERE id = ?", (inc_id,)).fetchone()
        if not chk_inc:
            inc_id = None
    else:
        chk_def = conn.execute("SELECT id FROM incidents WHERE id = 'INC-2026-FLOOD'").fetchone()
        inc_id = chk_def['id'] if chk_def else None

    zone_id = data.get('zone_id')
    if zone_id:
        chk_zone = conn.execute("SELECT id FROM zones WHERE id = ?", (zone_id,)).fetchone()
        if not chk_zone:
            zone_id = None

    wh_id=data.get('destination_warehouse_id')
    if role=='Citizen':
        recipient_type=(data.get('recipient_type') or '').strip().lower()
        if recipient_type=='government':
            owner_type='government';owner_org_id=None
        elif recipient_type=='ngo':
            try:org_id=int(data.get('organization_id'))
            except (TypeError,ValueError):raise BusinessLogicError('Select an approved NGO recipient.',code='RECIPIENT_REQUIRED',status_code=400)
            if not conn.execute("SELECT 1 FROM organizations WHERE id=? AND organization_type='NGO' AND status='Approved'",(org_id,)).fetchone():
                raise BusinessLogicError('The selected NGO is not approved to receive donations.',code='INVALID_RECIPIENT',status_code=400)
            owner_type='ngo';owner_org_id=org_id
        else:
            raise BusinessLogicError('Select Government or an approved NGO as the recipient.',code='RECIPIENT_REQUIRED',status_code=400)
        if wh_id in (None,''):
            wh=conn.execute("SELECT * FROM warehouses WHERE owner_type=? AND owner_organization_id IS ? AND status='Active' ORDER BY id LIMIT 1",(owner_type,owner_org_id)).fetchone()
            if not wh:
                raise BusinessLogicError('The selected recipient has no active relief warehouse configured.',code='RECIPIENT_WAREHOUSE_UNAVAILABLE',status_code=409)
            wh_id=wh['id']
        else:
            try:wh_id=int(wh_id)
            except (TypeError,ValueError):raise BusinessLogicError('Invalid destination warehouse.',code='WAREHOUSE_REQUIRED',status_code=400)
            wh=conn.execute("SELECT * FROM warehouses WHERE id=? AND status='Active'",(wh_id,)).fetchone()
        if not wh:raise BusinessLogicError('The selected destination warehouse is not active.',code='WAREHOUSE_NOT_FOUND',status_code=404)
        if wh['owner_type']!=owner_type or wh['owner_organization_id']!=owner_org_id:
            raise BusinessLogicError('The destination warehouse does not belong to the selected recipient.',code='WAREHOUSE_SCOPE_DENIED',status_code=403)
    else:
        try:wh_id=int(wh_id)
        except (TypeError,ValueError):raise BusinessLogicError('Select the warehouse that will physically receive this donation.',code='WAREHOUSE_REQUIRED',status_code=400)
        wh=conn.execute("SELECT * FROM warehouses WHERE id=? AND status='Active'",(wh_id,)).fetchone()
        if not wh:raise BusinessLogicError('The selected destination warehouse is not active.',code='WAREHOUSE_NOT_FOUND',status_code=404)
    wh=conn.execute("SELECT * FROM warehouses WHERE id=? AND status='Active'",(wh_id,)).fetchone()
    if not wh:raise BusinessLogicError('The selected destination warehouse is not active.',code='WAREHOUSE_NOT_FOUND',status_code=404)
    if role=='NGO Coordinator':
        row=conn.execute("SELECT COALESCE(organization_id,(SELECT organization_id FROM organization_memberships WHERE user_id=? AND membership_role='Coordinator' AND status='Active' LIMIT 1)) FROM users WHERE id=?",(actor_id,actor_id)).fetchone()
        org_id=row[0] if row else None
        if not org_id or wh['owner_type']!='ngo' or wh['owner_organization_id']!=org_id:raise BusinessLogicError('NGO donations must be received at a warehouse owned by that NGO.',code='WAREHOUSE_SCOPE_DENIED',status_code=403)
    elif role=='Government Official':
        if wh['owner_type']!='government' or wh['owner_organization_id'] is not None:raise BusinessLogicError('Government donations must be received at a Government warehouse.',code='WAREHOUSE_SCOPE_DENIED',status_code=403)
    elif role=='Administrator':
        org_id=wh['owner_organization_id'] if wh['owner_type']=='ngo' else None
    elif role=='Citizen':
        pass  # Recipient ownership was verified above; the pledge remains pending staff verification.
    else:raise BusinessLogicError('Role cannot register donations.',code='FORBIDDEN',status_code=403)

    ref_code = data.get('reference_code') or f"REF-{next_num:04d}"
    notes = data.get('notes') or ''

    amt_paise = None
    if dtype == 'Cash':
        amt_raw = data.get('declared_amount_paise') if data.get('declared_amount_paise') is not None else (int(data.get('amount_inr', 0)) * 100)
        amt_paise = int(amt_raw)
        if amt_paise <= 0:
            raise BusinessLogicError("Cash donation amount must be greater than zero.", code="INVALID_AMOUNT", status_code=400)

    conn.execute('''
        INSERT INTO donations (id, organization_id, donor_name, donation_type, incident_id, zone_id, destination_warehouse_id, declared_amount_paise, declared_notes, status, reference_code, submitted_by_user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Submitted', ?, ?)
    ''', (did, org_id, donor_name, dtype, inc_id, zone_id, wh_id, amt_paise, notes, ref_code, actor_id))

    # In-kind items
    items = data.get('items') or []
    if dtype == 'InKind':
        if not items:
            raise BusinessLogicError("In-kind donations must contain at least one relief item.", code="MISSING_ITEMS", status_code=400)
        for it in items:
            rid = it.get('resource_id')
            if not rid and it.get('resource_name'):
                name_clean = it['resource_name'].strip().lower()
                res_match = conn.execute("SELECT id FROM resources WHERE LOWER(name) LIKE ? LIMIT 1", (f"%{name_clean}%",)).fetchone()
                if not res_match:
                    for kw in ('food', 'water', 'medical', 'blanket', 'tent'):
                        if kw in name_clean:
                            res_match = conn.execute("SELECT id FROM resources WHERE LOWER(name) LIKE ? LIMIT 1", (f"%{kw}%",)).fetchone()
                            if res_match:
                                break
                if res_match:
                    rid = res_match['id']
            qdec = int(it.get('quantity_declared', 0))
            if not rid or qdec <= 0:
                raise BusinessLogicError(f"Invalid donation item: resource '{it.get('resource_name', rid)}' is not valid or quantity is non-positive.", code="INVALID_ITEM", status_code=400)
            conn.execute('''
                INSERT INTO donation_items (donation_id, resource_id, quantity_declared, quantity_received, quantity_accepted, quantity_rejected)
                VALUES (?, ?, ?, 0, 0, 0)
            ''', (did, rid, qdec))

    log_audit_event(conn, actor_id, 'REGISTER_DONATION', 'donations', did, new_state={'type': dtype, 'donor': donor_name})
    log_system_event(conn, 'donation_registered', {'id': did, 'type': dtype, 'donor': donor_name})
    return conn.execute("SELECT * FROM donations WHERE id = ?", (did,)).fetchone()


def verify_donation_service(conn, donation_id, decision, reason, items_verification, actor_id, actor_role):
    """
    Authorized receipt verification:
    Only verified/accepted physical in-kind quantities enter inventory stock ledger.
    Mismatch between declared and received creates an explicit discrepancy.
    Idempotent: Cannot accept twice.
    """
    don = conn.execute("SELECT * FROM donations WHERE id = ?", (donation_id,)).fetchone()
    if not don:
        raise BusinessLogicError("Donation record not found", code="NOT_FOUND", status_code=404)

    if don['status'] in ('Accepted', 'Partially Accepted'):
        raise BusinessLogicError("Donation has already been accepted and entered into stock. Cannot re-verify.", code="ALREADY_ACCEPTED", status_code=400)

    if actor_role not in ('Administrator', 'Government Official', 'NGO Coordinator'):
        raise BusinessLogicError("Access denied. Insufficient role to verify donation.", code="FORBIDDEN", status_code=403)

    # Dual-control: NGO Coordinator cannot self-verify own submitted donation receipt
    if actor_role == 'NGO Coordinator' and don['submitted_by_user_id'] == actor_id:
        raise BusinessLogicError("Dual-control policy violation: Requester cannot self-approve donation receipt.", code="DUAL_CONTROL_VIOLATION", status_code=403)

    wh_id = don['destination_warehouse_id'] or 1
    new_status = 'Accepted' if decision in ('Accept', 'Accepted') else ('Partially Accepted' if decision == 'PartiallyAccept' else 'Rejected')

    conn.execute('''
        UPDATE donations
        SET status = ?, verified_by_user_id = ?, verified_at = CURRENT_TIMESTAMP, verification_notes = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (new_status, actor_id, reason, donation_id))

    if don['donation_type'] == 'InKind' and new_status in ('Accepted', 'Partially Accepted'):
        for it_ver in items_verification:
            item_id = it_ver.get('donation_item_id')
            q_rec = int(it_ver.get('quantity_received', 0))
            q_acc = int(it_ver.get('quantity_accepted', 0))
            q_rej = int(it_ver.get('quantity_rejected', 0))
            item_reason = it_ver.get('reason') or reason

            if q_acc > q_rec:
                raise BusinessLogicError("Accepted quantity cannot exceed physically received quantity.", code="INVALID_QUANTITY", status_code=400)

            conn.execute('''
                UPDATE donation_items
                SET quantity_received = ?, quantity_accepted = ?, quantity_rejected = ?, reason = ?
                WHERE id = ? AND donation_id = ?
            ''', (q_rec, q_acc, q_rej, item_reason, item_id, donation_id))

            d_item = conn.execute("SELECT resource_id FROM donation_items WHERE id = ?", (item_id,)).fetchone()
            if d_item and q_acc > 0:
                res_id = d_item['resource_id']
                st_row = conn.execute("SELECT id FROM warehouse_stock WHERE warehouse_id = ? AND resource_id = ?", (wh_id, res_id)).fetchone()
                if st_row:
                    st_id = st_row['id']
                    # Add to stock
                    conn.execute("UPDATE warehouse_stock SET on_hand_units = on_hand_units + ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (q_acc, st_id))
                    # Ledger movement
                    conn.execute('''
                        INSERT INTO inventory_transactions (warehouse_stock_id, transaction_type, quantity_units, direction, reference_type, reference_id, performed_by_user_id, reason)
                        VALUES (?, 'DonationReceived', ?, 'IN', 'donations', ?, ?, ?)
                    ''', (st_id, q_acc, donation_id, actor_id, item_reason))

                    # Mirror in legacy inventory table
                    rname = conn.execute("SELECT name FROM resources WHERE id = ?", (res_id,)).fetchone()[0]
                    conn.execute("UPDATE inventory SET available_units = available_units + ? WHERE LOWER(resource_name) = ?", (q_acc, rname.lower()))

    # Cash donation: Record in fund_transactions if accepted
    elif don['donation_type'] == 'Cash' and new_status in ('Accepted', 'Partially Accepted') and don['declared_amount_paise']:
        tx_id = f"TX-DON-{donation_id}"
        conn.execute('''
            INSERT OR REPLACE INTO fund_transactions (id, incident_id, organization_id, transaction_type, amount_paise, reference_code, status, performed_by_user_id, reason, occurred_at)
            VALUES (?, ?, ?, 'DonationReceived', ?, ?, 'Completed', ?, ?, CURRENT_TIMESTAMP)
        ''', (tx_id, don['incident_id'], don['organization_id'], don['declared_amount_paise'], don['reference_code'], actor_id, f"Verified cash donation: {don['donor_name']}"))

    log_audit_event(conn, actor_id, 'VERIFY_DONATION', 'donations', donation_id,
                    old_state={'status': don['status']}, new_state={'status': new_status}, reason=reason)
    log_system_event(conn, 'donation_verified', {'id': donation_id, 'status': new_status})
    return conn.execute("SELECT * FROM donations WHERE id = ?", (donation_id,)).fetchone()


# =========================================================================
# 4. VOLUNTEER TASKS & FIELD REPORT WORKFLOWS
# =========================================================================

def update_volunteer_task_status_service(conn, task_id, action, actor_id, actor_name, actor_role, payload=None):
    """
    Manages persistent volunteer task lifecycle:
    Created -> Assigned -> Accepted/Declined -> In Progress -> Submitted for Review -> Completed
    Requires distribution quantity reconciliation: received = completed + damaged + remaining
    """
    payload = payload or {}
    task = conn.execute("SELECT * FROM volunteer_tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        raise BusinessLogicError("Volunteer task record not found", code="NOT_FOUND", status_code=404)

    vol = conn.execute("SELECT * FROM volunteers WHERE id = ?", (task['volunteer_id'],)).fetchone()
    is_assigned_vol = (vol and vol['name'] == actor_name) or (vol and vol['user_id'] == actor_id)
    is_supervisor = actor_role in ('Administrator', 'Government Official', 'NGO Coordinator')

    current_status = task['status']
    old_state = {'status': current_status}

    if action == 'accept':
        if not is_assigned_vol and not is_supervisor:
            raise BusinessLogicError("Only the assigned volunteer can accept this task.", code="FORBIDDEN", status_code=403)
        if current_status not in ('Created', 'Assigned', 'Needs Correction'):
            raise BusinessLogicError(f"Cannot accept task from status '{current_status}'.", code="INVALID_STATUS", status_code=400)
        conn.execute("UPDATE volunteer_tasks SET status = 'Accepted', accepted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (task_id,))
        conn.execute("UPDATE volunteers SET status = 'On task' WHERE id = ?", (task['volunteer_id'],))
        new_status = 'Accepted'

    elif action == 'decline':
        if not is_assigned_vol and not is_supervisor:
            raise BusinessLogicError("Only the assigned volunteer can decline this task.", code="FORBIDDEN", status_code=403)
        reason = payload.get('reason') or 'Declined by volunteer'
        conn.execute("UPDATE volunteer_tasks SET status = 'Declined', review_notes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (reason, task_id,))
        # Check if volunteer has other active tasks
        other_active = conn.execute("SELECT COUNT(*) FROM volunteer_tasks WHERE volunteer_id = ? AND id != ? AND status IN ('Assigned','Accepted','In Progress','Submitted for Review','Needs Correction')", (task['volunteer_id'], task_id)).fetchone()[0]
        if other_active == 0:
            conn.execute("UPDATE volunteers SET status = 'Available' WHERE id = ?", (task['volunteer_id'],))
        new_status = 'Declined'

    elif action == 'check-in':
        if not is_assigned_vol and not is_supervisor:
            raise BusinessLogicError("Only the assigned responder can log check-in.", code="FORBIDDEN", status_code=403)
        lat = payload.get('lat')
        lng = payload.get('lng')
        notes = payload.get('notes') or 'Field check-in recorded'
        conn.execute('''
            INSERT INTO task_checkpoints (task_id, checkpoint_type, lat, lng, notes, quantity_delta, created_by_user_id)
            VALUES (?, 'CheckIn', ?, ?, ?, 0, ?)
        ''', (task_id, lat, lng, notes, actor_id))
        conn.execute("UPDATE volunteer_tasks SET status = 'In Progress', started_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (task_id,))
        new_status = 'In Progress'

    elif action == 'progress':
        if not is_assigned_vol and not is_supervisor:
            raise BusinessLogicError("Only the assigned volunteer or supervisor can log task progress.", code="FORBIDDEN", status_code=403)
        notes = payload.get('notes') or ''
        q_delta = int(payload.get('quantity_delta', 0))
        conn.execute('''
            INSERT INTO task_checkpoints (task_id, checkpoint_type, notes, quantity_delta, created_by_user_id)
            VALUES (?, 'Progress', ?, ?, ?)
        ''', (task_id, notes, q_delta, actor_id))
        if q_delta > 0:
            conn.execute("UPDATE volunteer_tasks SET quantity_completed = quantity_completed + ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (q_delta, task_id))
        new_status = task['status']

    elif action == 'submit':
        # Completion report submitted by volunteer
        if not is_assigned_vol and not is_supervisor:
            raise BusinessLogicError("Only the assigned volunteer can submit completion.", code="FORBIDDEN", status_code=403)

        q_rec = int(payload.get('quantity_received', payload.get('received_quantity', task['quantity_received'])))
        q_comp = int(payload.get('quantity_completed', payload.get('completed_quantity', task['quantity_completed'])))
        q_dam = int(payload.get('quantity_damaged', payload.get('damaged_quantity', 0)))
        q_rem = int(payload.get('quantity_remaining', payload.get('remaining_quantity', 0)))
        notes = payload.get('notes') or ''

        # Quantity reconciliation equation: received = completed + damaged + remaining
        if q_rec != (q_comp + q_dam + q_rem):
            raise BusinessLogicError(
                f"Quantity reconciliation failed: Received ({q_rec}) must exactly equal Completed ({q_comp}) + Damaged ({q_dam}) + Remaining ({q_rem}).",
                code="RECONCILIATION_FAILED",
                status_code=400,
                details={'received': q_rec, 'sum': q_comp + q_dam + q_rem}
            )

        conn.execute('''
            UPDATE volunteer_tasks
            SET status = 'Submitted for Review', quantity_received = ?, quantity_completed = ?, quantity_damaged = ?, quantity_remaining = ?,
                submitted_at = CURRENT_TIMESTAMP, review_notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (q_rec, q_comp, q_dam, q_rem, notes, task_id))
        new_status = 'Submitted for Review'

    elif action == 'approve':
        if not is_supervisor:
            raise BusinessLogicError("Only authorized supervisors can approve volunteer tasks.", code="FORBIDDEN", status_code=403)
        if current_status != 'Submitted for Review':
            raise BusinessLogicError(f"Task cannot be approved from status '{current_status}'. Must be 'Submitted for Review'.", code="INVALID_STATUS", status_code=400)

        reason = payload.get('reason') or 'Task completion approved by supervisor'
        conn.execute('''
            UPDATE volunteer_tasks
            SET status = 'Completed', reviewed_by_user_id = ?, reviewed_at = CURRENT_TIMESTAMP, completed_at = CURRENT_TIMESTAMP,
                review_notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (actor_id, reason, task_id))

        # Check if volunteer has other active tasks
        other_active = conn.execute("SELECT COUNT(*) FROM volunteer_tasks WHERE volunteer_id = ? AND id != ? AND status IN ('Assigned','Accepted','In Progress','Submitted for Review','Needs Correction')", (task['volunteer_id'], task_id)).fetchone()[0]
        if other_active == 0:
            conn.execute("UPDATE volunteers SET status = 'Available' WHERE id = ?", (task['volunteer_id'],))
        new_status = 'Completed'

    else:
        raise BusinessLogicError(f"Unknown volunteer task action: {action}", code="INVALID_ACTION", status_code=400)

    log_audit_event(conn, actor_id, f"TASK_{action.upper()}", 'volunteer_tasks', task_id,
                    old_state=old_state, new_state={'status': new_status})
    log_system_event(conn, 'volunteer_task_updated', {'id': task_id, 'status': new_status})
    return conn.execute("SELECT * FROM volunteer_tasks WHERE id = ?", (task_id,)).fetchone()


# =========================================================================
# 5. SHELTER ADMISSIONS & TRANSFERS (ZERO DOUBLE-COUNTING)
# =========================================================================

def admit_shelter_service(conn, shelter_id, data, actor_id):
    """
    Admits evacuated household/people to shelter with strict capacity validation.
    """
    shelter = conn.execute("SELECT * FROM shelters WHERE id = ?", (shelter_id,)).fetchone()
    if not shelter:
        raise BusinessLogicError("Shelter not found", code="NOT_FOUND", status_code=404)

    people_count = int(data.get('people_count') or 1)
    if people_count <= 0:
        raise BusinessLogicError("People count must be a positive integer.", code="INVALID_COUNT", status_code=400)

    current_occupants = shelter['occupants']
    capacity = shelter['capacity']

    if current_occupants + people_count > capacity:
        raise BusinessLogicError(
            f"Shelter '{shelter['name']}' capacity exceeded. Available beds: {capacity - current_occupants}, requested: {people_count}.",
            code="SHELTER_CAPACITY_EXCEEDED",
            status_code=409,
            details={'current_occupants': current_occupants, 'capacity': capacity, 'requested': people_count}
        )

    # Generate admission ID
    max_a = conn.execute("SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM shelter_admissions").fetchone()
    next_num = (max_a[0] or 0) + 1
    adm_id = f"ADM-{next_num:03d}"

    hh_ref = data.get('household_reference') or f"HH-{next_num:03d}"
    notes = data.get('notes') or ''
    req_id = data.get('request_id')

    inc_id = data.get('incident_id')
    if inc_id:
        chk_inc = conn.execute("SELECT id FROM incidents WHERE id = ?", (inc_id,)).fetchone()
        inc_id = chk_inc['id'] if chk_inc else None
    else:
        chk_def = conn.execute("SELECT id FROM incidents WHERE id = 'INC-2026-FLOOD'").fetchone()
        inc_id = chk_def['id'] if chk_def else None

    conn.execute('''
        INSERT INTO shelter_admissions (id, shelter_id, incident_id, request_id, household_reference, people_count, status, referred_by_user_id, checked_in_by_user_id, admitted_at)
        VALUES (?, ?, ?, ?, ?, ?, 'Admitted', ?, ?, CURRENT_TIMESTAMP)
    ''', (adm_id, shelter_id, inc_id, req_id, hh_ref, people_count, actor_id, actor_id))

    new_occupants = current_occupants + people_count
    pct = new_occupants / capacity
    status = 'Near capacity' if pct >= 0.9 else 'Operational'

    conn.execute("UPDATE shelters SET occupants = ?, status = ? WHERE id = ?", (new_occupants, status, shelter_id))

    log_audit_event(conn, actor_id, 'ADMIT_SHELTER', 'shelters', shelter_id,
                    old_state={'occupants': current_occupants}, new_state={'occupants': new_occupants, 'admission_id': adm_id})
    log_system_event(conn, 'shelter_updated', {'id': shelter_id, 'occupants': new_occupants, 'status': status})
    return conn.execute("SELECT * FROM shelter_admissions WHERE id = ?", (adm_id,)).fetchone()


def transfer_shelter_service(conn, admission_id, to_shelter_id, people_count, reason, actor_id):
    """
    Atomically transfers occupants from one shelter to another.
    Guarantees zero double counting: Decrements from source and increments to destination in same transaction.
    """
    adm = conn.execute("SELECT * FROM shelter_admissions WHERE id = ?", (admission_id,)).fetchone()
    if not adm:
        raise BusinessLogicError("Shelter admission not found", code="NOT_FOUND", status_code=404)

    if adm['status'] != 'Admitted':
        raise BusinessLogicError(f"Cannot transfer admission in status '{adm['status']}'.", code="INVALID_STATUS", status_code=400)

    from_shelter_id = adm['shelter_id']
    if from_shelter_id == to_shelter_id:
        raise BusinessLogicError("Source and destination shelter must be different.", code="INVALID_DESTINATION", status_code=400)

    from_s = conn.execute("SELECT * FROM shelters WHERE id = ?", (from_shelter_id,)).fetchone()
    to_s = conn.execute("SELECT * FROM shelters WHERE id = ?", (to_shelter_id,)).fetchone()
    if not to_s:
        raise BusinessLogicError("Destination shelter not found", code="NOT_FOUND", status_code=404)

    count = int(people_count or adm['people_count'])
    if count <= 0:
        raise BusinessLogicError("Transfer people count must be greater than zero.", code="INVALID_COUNT", status_code=400)
    if count > adm['people_count']:
        raise BusinessLogicError(f"Transfer count ({count}) exceeds admission occupant count ({adm['people_count']}).", code="COUNT_EXCEEDS_ADMISSION", status_code=400)
    if from_s['occupants'] < count:
        raise BusinessLogicError(f"Source shelter occupancy mismatch: currently has {from_s['occupants']} occupants, cannot transfer {count}.", code="OCCUPANCY_MISMATCH", status_code=400)

    # Validate destination capacity
    if to_s['occupants'] + count > to_s['capacity']:
        raise BusinessLogicError(
            f"Destination shelter '{to_s['name']}' cannot accommodate {count} people. Available capacity: {to_s['capacity'] - to_s['occupants']}.",
            code="DESTINATION_FULL",
            status_code=409
        )

    # Transfer record
    max_t = conn.execute("SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM shelter_transfers").fetchone()
    next_t_num = (max_t[0] or 0) + 1
    trf_id = f"TRF-{next_t_num:03d}"

    conn.execute('''
        INSERT INTO shelter_transfers (id, admission_id, from_shelter_id, to_shelter_id, people_count, status, requested_by_user_id, approved_by_user_id, completed_at, reason)
        VALUES (?, ?, ?, ?, ?, 'Completed', ?, ?, CURRENT_TIMESTAMP, ?)
    ''', (trf_id, admission_id, from_shelter_id, to_shelter_id, count, actor_id, actor_id, reason))

    # Atomically adjust shelter occupancies
    from_occ = from_s['occupants'] - count
    to_occ = to_s['occupants'] + count

    conn.execute("UPDATE shelters SET occupants = ? WHERE id = ?", (from_occ, from_shelter_id))
    conn.execute("UPDATE shelters SET occupants = ? WHERE id = ?", (to_occ, to_shelter_id))

    # Split admission if partial transfer, or move entire admission if all occupants transferred
    if count < adm['people_count']:
        remaining = adm['people_count'] - count
        conn.execute("UPDATE shelter_admissions SET people_count = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (remaining, admission_id))
        max_a = conn.execute("SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM shelter_admissions").fetchone()
        next_num = (max_a[0] or 0) + 1
        new_adm_id = f"ADM-{next_num:03d}"
        conn.execute('''
            INSERT INTO shelter_admissions (id, shelter_id, incident_id, request_id, household_reference, people_count, status, referred_by_user_id, checked_in_by_user_id, admitted_at)
            VALUES (?, ?, ?, ?, ?, ?, 'Admitted', ?, ?, CURRENT_TIMESTAMP)
        ''', (new_adm_id, to_shelter_id, adm['incident_id'], adm['request_id'], f"{adm['household_reference']}-T", count, actor_id, actor_id))
    else:
        conn.execute("UPDATE shelter_admissions SET shelter_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (to_shelter_id, admission_id))

    log_audit_event(conn, actor_id, 'TRANSFER_SHELTER', 'shelter_transfers', trf_id,
                    old_state={'from_shelter': from_shelter_id, 'from_occupants': from_s['occupants']},
                    new_state={'to_shelter': to_shelter_id, 'to_occupants': to_occ},
                    reason=reason)

    log_system_event(conn, 'shelter_updated', {'id': from_shelter_id, 'occupants': from_occ})
    log_system_event(conn, 'shelter_updated', {'id': to_shelter_id, 'occupants': to_occ})
    return conn.execute("SELECT * FROM shelter_transfers WHERE id = ?", (trf_id,)).fetchone()

shelter_transfer_service = transfer_shelter_service


# =========================================================================
# 6. FINANCE & LEDGER (EXACT INTEGER PAISE)
# =========================================================================

def fund_request_action_service(conn, request_id, action, actor_id, actor_role, payload=None):
    """
    Financial dual-control lifecycle using exact integer paise:
    Submitted -> Approved -> Committed -> Paid -> Reconciled
    """
    payload = payload or {}
    fr = conn.execute("SELECT * FROM fund_requests WHERE id = ?", (request_id,)).fetchone()
    if not fr:
        raise BusinessLogicError("Fund request not found", code="NOT_FOUND", status_code=404)

    curr_status = fr['status']

    if action == 'approve':
        if actor_role not in ('Administrator', 'Government Official'):
            raise BusinessLogicError("Only Government Officials can authorize fund requests.", code="FORBIDDEN", status_code=403)
        # Dual-control: requester cannot approve their own request
        if fr['requested_by_user_id'] == actor_id:
            raise BusinessLogicError("Dual-control policy violation: Requester cannot approve their own financial request.", code="DUAL_CONTROL_VIOLATION", status_code=403)

        appr_amt = int(payload.get('approved_amount_paise') if payload.get('approved_amount_paise') is not None else fr['requested_amount_paise'])
        if appr_amt <= 0 or appr_amt > fr['requested_amount_paise']:
            raise BusinessLogicError("Approved amount must be positive and not exceed requested amount.", code="INVALID_AMOUNT", status_code=400)

        reason = payload.get('reason') or 'Budget allocation authorized'
        conn.execute('''
            UPDATE fund_requests
            SET status = 'Approved', approved_amount_paise = ?, reviewed_by_user_id = ?, decision_reason = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (appr_amt, actor_id, reason, request_id))
        new_status = 'Approved'

    elif action == 'commit':
        if actor_role not in ('Administrator', 'Government Official', 'NGO Coordinator'):
            raise BusinessLogicError("Insufficient role to commit funds.", code="FORBIDDEN", status_code=403)
        if curr_status != 'Approved':
            raise BusinessLogicError(f"Request must be Approved before Commitment. Current status: '{curr_status}'.", code="INVALID_STATUS", status_code=400)
        ref = payload.get('reference_code') or f"COMM-{request_id}"
        tx_id = f"TX-COMM-{request_id}"
        conn.execute('''
            INSERT INTO fund_transactions (id, fund_request_id, incident_id, organization_id, transaction_type, amount_paise, reference_code, status, performed_by_user_id, reason, occurred_at)
            VALUES (?, ?, ?, ?, 'Commitment', ?, ?, 'Completed', ?, 'Committed purchase order', CURRENT_TIMESTAMP)
        ''', (tx_id, request_id, fr['incident_id'], fr['organization_id'], fr['approved_amount_paise'], ref, actor_id))
        conn.execute("UPDATE fund_requests SET status = 'Committed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (request_id,))
        new_status = 'Committed'

    elif action == 'pay':
        if actor_role not in ('Administrator', 'Government Official'):
            raise BusinessLogicError("Only Government Officials or Administrators can execute fund disbursements.", code="FORBIDDEN", status_code=403)
        if curr_status not in ('Committed', 'Partially Paid'):
            raise BusinessLogicError(f"Request must be Committed before disbursement. Current status: '{curr_status}'.", code="INVALID_STATUS", status_code=400)
        pay_amt = int(payload.get('amount_paise') if payload.get('amount_paise') is not None else fr['approved_amount_paise'])
        if pay_amt <= 0:
            raise BusinessLogicError("Payment amount must be greater than zero.", code="INVALID_AMOUNT", status_code=400)
        if pay_amt > fr['approved_amount_paise']:
            raise BusinessLogicError(f"Payment amount ({pay_amt} paise) cannot exceed approved amount ({fr['approved_amount_paise']} paise).", code="EXCEEDS_APPROVED_AMOUNT", status_code=400)
        ref = payload.get('reference_code') or f"PAY-{request_id}"
        receipt = payload.get('receipt_reference') or 'RECEIPT-01'
        tx_id = f"TX-PAY-{request_id}"
        conn.execute('''
            INSERT INTO fund_transactions (id, fund_request_id, incident_id, organization_id, transaction_type, amount_paise, reference_code, status, performed_by_user_id, receipt_reference, reason, occurred_at)
            VALUES (?, ?, ?, ?, 'Payment', ?, ?, 'Completed', ?, ?, 'Payment disbursed to supplier', CURRENT_TIMESTAMP)
        ''', (tx_id, request_id, fr['incident_id'], fr['organization_id'], pay_amt, ref, actor_id, receipt))
        conn.execute("UPDATE fund_requests SET status = 'Paid', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (request_id,))
        new_status = 'Paid'

    elif action == 'reconcile':
        if actor_role not in ('Administrator', 'Government Official'):
            raise BusinessLogicError("Only Government Officials or Administrators can reconcile fund requests.", code="FORBIDDEN", status_code=403)
        if curr_status != 'Paid':
            raise BusinessLogicError("Only Paid requests can be reconciled.", code="INVALID_STATUS", status_code=400)
        conn.execute("UPDATE fund_requests SET status = 'Reconciled', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (request_id,))
        new_status = 'Reconciled'

    else:
        raise BusinessLogicError(f"Unknown fund action: {action}", code="INVALID_ACTION", status_code=400)

    log_audit_event(conn, actor_id, f"FUND_{action.upper()}", 'fund_requests', request_id,
                    old_state={'status': curr_status}, new_state={'status': new_status})
    log_system_event(conn, 'fund_request_updated', {'id': request_id, 'status': new_status})
    return conn.execute("SELECT * FROM fund_requests WHERE id = ?", (request_id,)).fetchone()


def return_dispatch_service(conn, dispatch_id, actor_id, actor_name, actor_role, returned_items=None, return_notes=None):
    """
    Assigned driver or warehouse receiver returns a dispatch to warehouse:
    Restores returned goods to warehouse stock, sets vehicle to Available, marks dispatch 'Returned to Warehouse'.
    """
    dsp = conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()
    if not dsp:
        raise BusinessLogicError("Dispatch record not found", code="NOT_FOUND", status_code=404)

    if actor_role not in ('Driver', 'Administrator', 'Government Official', 'NGO Coordinator'):
        raise BusinessLogicError("Access denied.", code="FORBIDDEN", status_code=403)
    if actor_role == 'Driver':
        if dsp['driver_user_id'] != actor_id:
            raise BusinessLogicError("You are not authorized to return another driver's dispatch.", code="FORBIDDEN", status_code=403)

    wh_id = dsp['warehouse_id'] or 1
    notes = return_notes or 'Dispatch returned to warehouse'

    if returned_items and isinstance(returned_items, list):
        for it in returned_items:
            res_id = it.get('resource_id')
            q_ret = int(it.get('quantity_returned', 0))
            if res_id and q_ret > 0:
                conn.execute('''
                    UPDATE dispatch_items 
                    SET quantity_returned = quantity_returned + ?, updated_at = CURRENT_TIMESTAMP
                    WHERE dispatch_id = ? AND resource_id = ?
                ''', (q_ret, dispatch_id, res_id))
                
                st_row = conn.execute("SELECT id FROM warehouse_stock WHERE warehouse_id = ? AND resource_id = ?", (wh_id, res_id)).fetchone()
                if st_row:
                    conn.execute("UPDATE warehouse_stock SET on_hand_units = on_hand_units + ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (q_ret, st_row['id']))
                    conn.execute('''
                        INSERT INTO inventory_transactions (warehouse_stock_id, transaction_type, quantity_units, direction, reference_type, reference_id, performed_by_user_id, reason)
                        VALUES (?, 'Returned', ?, 'IN', 'dispatches', ?, ?, ?)
                    ''', (st_row['id'], q_ret, dispatch_id, actor_id, f"Goods returned to warehouse: {notes}"))

    conn.execute('''
        UPDATE dispatches 
        SET status = 'Returned to Warehouse', returned_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP, delivery_notes = ?
        WHERE id = ?
    ''', (notes, dispatch_id))

    if dsp['vehicle_id']:
        conn.execute("UPDATE vehicles SET status = 'Available', current_driver_user_id = NULL WHERE id = ?", (dsp['vehicle_id'],))

    log_audit_event(conn, actor_id, 'RETURN_DISPATCH', 'dispatches', dispatch_id, reason=notes)
    log_system_event(conn, 'dispatch_updated', {'id': dispatch_id, 'status': 'Returned to Warehouse'})
    return conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()


def cancel_dispatch_service(conn, dispatch_id, actor_id, actor_role, reason):
    """
    Authorized official or coordinator cancels a dispatch:
    Releases active stock reservations, marks dispatch Cancelled, frees vehicle.
    """
    dsp = conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()
    if not dsp:
        raise BusinessLogicError("Dispatch record not found", code="NOT_FOUND", status_code=404)

    if actor_role not in ('Administrator', 'Government Official', 'NGO Coordinator'):
        raise BusinessLogicError("Access denied. Insufficient role to cancel dispatch.", code="FORBIDDEN", status_code=403)

    if dsp['status'] in ('Delivered', 'Cancelled'):
        raise BusinessLogicError(f"Cannot cancel dispatch in status '{dsp['status']}'.", code="INVALID_STATUS", status_code=400)

    # Release reservations
    resv_items = conn.execute('''
        SELECT ri.*, ws.id as ws_id
        FROM inventory_reservation_items ri
        JOIN inventory_reservations r ON ri.reservation_id = r.id
        JOIN warehouse_stock ws ON ri.warehouse_stock_id = ws.id
        WHERE r.dispatch_id = ? AND r.status = 'Active'
    ''', (dispatch_id,)).fetchall()

    for ritem in resv_items:
        qty = ritem['quantity_units']
        conn.execute("UPDATE warehouse_stock SET reserved_units = MAX(0, reserved_units - ?), updated_at = CURRENT_TIMESTAMP WHERE id = ?", (qty, ritem['ws_id']))
        conn.execute('''
            INSERT INTO inventory_transactions (warehouse_stock_id, transaction_type, quantity_units, direction, reference_type, reference_id, performed_by_user_id, reason)
            VALUES (?, 'ReservationReleased', ?, 'MEMO', 'dispatches', ?, ?, ?)
        ''', (ritem['ws_id'], qty, dispatch_id, actor_id, f"Dispatch cancelled: {reason}"))

    conn.execute("UPDATE inventory_reservations SET status = 'Cancelled', released_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE dispatch_id = ?", (dispatch_id,))

    conn.execute("UPDATE dispatches SET status = 'Cancelled', updated_at = CURRENT_TIMESTAMP, delivery_notes = ? WHERE id = ?", (reason, dispatch_id))

    if dsp['vehicle_id']:
        conn.execute("UPDATE vehicles SET status = 'Available', current_driver_user_id = NULL WHERE id = ?", (dsp['vehicle_id'],))

    if dsp['request_id']:
        conn.execute("UPDATE emergency_requests SET status = 'Awaiting allocation', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (dsp['request_id'],))
        conn.execute('''
            INSERT INTO request_events (request_id, event_type, from_status, to_status, notes, actor_user_id)
            VALUES (?, 'DISPATCH_CANCELLED', 'Dispatched', 'Awaiting allocation', ?, ?)
        ''', (dsp['request_id'], f"Dispatch cancelled: {reason}", actor_id))

    log_audit_event(conn, actor_id, 'CANCEL_DISPATCH', 'dispatches', dispatch_id, reason=reason)
    log_system_event(conn, 'dispatch_updated', {'id': dispatch_id, 'status': 'Cancelled'})
    return conn.execute("SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)).fetchone()
