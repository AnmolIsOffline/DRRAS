import sqlite3
import json

def table_has_column(conn, table_name, column_name):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1].lower() for row in cur.fetchall()]
    return column_name.lower() in columns

def apply_migrations(conn):
    """
    Applies versioned, ordered, and idempotent SQLite migrations.
    Uses PRAGMA foreign_keys = ON and commits each migration transactionally.
    """
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        description TEXT NOT NULL
    )
    ''')
    conn.commit()

    applied = {row[0] for row in cur.execute("SELECT version FROM schema_migrations").fetchall()}

    # Migration 1: Base legacy schema if not existing
    if 1 not in applied:
        with conn:
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
            )''')
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
            )''')
            cur.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_name TEXT UNIQUE NOT NULL COLLATE NOCASE,
                available_units INTEGER NOT NULL CHECK(available_units >= 0),
                target_stock INTEGER NOT NULL CHECK(target_stock > 0),
                warehouse_name TEXT NOT NULL DEFAULT 'Central Relief',
                status TEXT NOT NULL
            )''')
            cur.execute('''
            CREATE TABLE IF NOT EXISTS volunteers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                initials TEXT NOT NULL,
                name TEXT NOT NULL,
                skill TEXT NOT NULL,
                zone TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Available'
            )''')
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
            )''')
            cur.execute('''
            CREATE TABLE IF NOT EXISTS shelters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                occupants INTEGER NOT NULL CHECK(occupants >= 0),
                capacity INTEGER NOT NULL CHECK(capacity > 0),
                status TEXT NOT NULL
            )''')
            cur.execute('''
            CREATE TABLE IF NOT EXISTS funds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                percentage INTEGER NOT NULL CHECK(percentage >= 0 AND percentage <= 100),
                color TEXT NOT NULL
            )''')
            cur.execute('''
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_key TEXT NOT NULL,
                title TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            cur.execute('''
            CREATE TABLE IF NOT EXISTS system_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            cur.execute("INSERT INTO schema_migrations (version, description) VALUES (1, 'Base legacy tables')")

    # Migration 2: Extend existing tables with non-breaking optional columns
    if 2 not in applied:
        with conn:
            # Users extensions
            user_cols = [
                ('phone', 'TEXT NULL'),
                ('organization_id', 'INTEGER NULL'),
                ('updated_at', 'TEXT NULL'),
                ('last_login_at', 'TEXT NULL'),
                ('suspended_at', 'TEXT NULL'),
                ('suspension_reason', 'TEXT NULL')
            ]
            for col, col_type in user_cols:
                if not table_has_column(conn, 'users', col):
                    cur.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")

            # Emergency Requests extensions
            req_cols = [
                ('requester_user_id', 'INTEGER NULL'),
                ('incident_id', 'TEXT NULL'),
                ('zone_id', 'TEXT NULL'),
                ('description', 'TEXT NULL'),
                ('verification_status', "TEXT NOT NULL DEFAULT 'Unverified'"),
                ('verified_by_user_id', 'INTEGER NULL'),
                ('verified_at', 'TEXT NULL'),
                ('review_reason', 'TEXT NULL'),
                ('duplicate_of_request_id', 'TEXT NULL'),
                ('assigned_organization_id', 'INTEGER NULL'),
                ('closed_by_user_id', 'INTEGER NULL'),
                ('closed_at', 'TEXT NULL'),
                ('delivery_confirmed_at', 'TEXT NULL'),
                ('updated_at', 'TEXT NULL')
            ]
            for col, col_type in req_cols:
                if not table_has_column(conn, 'emergency_requests', col):
                    cur.execute(f"ALTER TABLE emergency_requests ADD COLUMN {col} {col_type}")

            # Volunteers extensions
            vol_cols = [
                ('user_id', 'INTEGER NULL'),
                ('organization_id', 'INTEGER NULL'),
                ('verified', 'INTEGER NOT NULL DEFAULT 0'),
                ('availability_start', 'TEXT NULL'),
                ('availability_end', 'TEXT NULL'),
                ('phone', 'TEXT NULL'),
                ('updated_at', 'TEXT NULL')
            ]
            for col, col_type in vol_cols:
                if not table_has_column(conn, 'volunteers', col):
                    cur.execute(f"ALTER TABLE volunteers ADD COLUMN {col} {col_type}")

            # Dispatches extensions
            dsp_cols = [
                ('incident_id', 'TEXT NULL'),
                ('zone_id', 'TEXT NULL'),
                ('vehicle_id', 'INTEGER NULL'),
                ('driver_user_id', 'INTEGER NULL'),
                ('created_by_user_id', 'INTEGER NULL'),
                ('warehouse_id', 'INTEGER NULL'),
                ('planned_at', 'TEXT NULL'),
                ('departed_at', 'TEXT NULL'),
                ('arrived_at', 'TEXT NULL'),
                ('delivered_at', 'TEXT NULL'),
                ('returned_at', 'TEXT NULL'),
                ('route_status', 'TEXT NULL'),
                ('route_blockage_reason', 'TEXT NULL'),
                ('delivery_result', 'TEXT NULL'),
                ('delivery_notes', 'TEXT NULL'),
                ('updated_at', 'TEXT NULL')
            ]
            for col, col_type in dsp_cols:
                if not table_has_column(conn, 'dispatches', col):
                    cur.execute(f"ALTER TABLE dispatches ADD COLUMN {col} {col_type}")

            # Shelters extensions
            shelter_cols = [
                ('incident_id', 'TEXT NULL'),
                ('zone_id', 'TEXT NULL'),
                ('address', 'TEXT NULL'),
                ('lat', 'REAL NULL'),
                ('lng', 'REAL NULL'),
                ('created_by_user_id', 'INTEGER NULL'),
                ('updated_at', 'TEXT NULL')
            ]
            for col, col_type in shelter_cols:
                if not table_has_column(conn, 'shelters', col):
                    cur.execute(f"ALTER TABLE shelters ADD COLUMN {col} {col_type}")

            cur.execute("INSERT INTO schema_migrations (version, description) VALUES (2, 'Extend existing tables with relational columns')")

    # Migration 3: Canonical normalized domain tables
    if 3 not in applied:
        with conn:
            # 1. Incidents
            cur.execute('''
            CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                incident_type TEXT NOT NULL,
                severity TEXT NOT NULL CHECK(severity IN ('Low','Medium','High','Severe','Catastrophic')),
                description TEXT NOT NULL,
                district TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('Draft','Under Verification','Active','Stabilizing','Closed','Rejected','Cancelled')),
                command_officer_user_id INTEGER NOT NULL REFERENCES users(id),
                reported_at TEXT NOT NULL,
                activated_at TEXT NULL,
                stabilized_at TEXT NULL,
                closed_at TEXT NULL,
                created_by_user_id INTEGER NOT NULL REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 2. Zones
            cur.execute('''
            CREATE TABLE IF NOT EXISTS zones (
                id TEXT PRIMARY KEY,
                incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE RESTRICT,
                name TEXT NOT NULL,
                description TEXT NULL,
                district TEXT NOT NULL,
                address_or_boundary TEXT NULL,
                center_lat REAL NULL CHECK(center_lat IS NULL OR (center_lat >= -90.0 AND center_lat <= 90.0)),
                center_lng REAL NULL CHECK(center_lng IS NULL OR (center_lng >= -180.0 AND center_lng <= 180.0)),
                severity TEXT NOT NULL CHECK(severity IN ('Low','Medium','High','Severe','Critical')),
                status TEXT NOT NULL DEFAULT 'Active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(incident_id, name)
            )''')

            # 3. Organizations & Memberships
            cur.execute('''
            CREATE TABLE IF NOT EXISTS organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                organization_type TEXT NOT NULL CHECK(organization_type IN ('NGO','Public Agency','Supplier','Donor','Other')),
                registration_reference TEXT NULL,
                contact_name TEXT NOT NULL,
                contact_email TEXT NULL,
                contact_phone TEXT NULL,
                status TEXT NOT NULL DEFAULT 'Approved' CHECK(status IN ('Pending','Approved','Rejected','Suspended')),
                verified_by_user_id INTEGER NULL REFERENCES users(id),
                verified_at TEXT NULL,
                verification_reason TEXT NULL,
                created_by_user_id INTEGER NULL REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            cur.execute('''
            CREATE TABLE IF NOT EXISTS organization_memberships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                membership_role TEXT NOT NULL DEFAULT 'Member' CHECK(membership_role IN ('Coordinator','Supervisor','Member','Driver','Volunteer')),
                status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active','Inactive','Suspended')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(organization_id, user_id)
            )''')

            # 4. Zone Adoptions
            cur.execute('''
            CREATE TABLE IF NOT EXISTS zone_adoptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE RESTRICT,
                zone_id TEXT NOT NULL REFERENCES zones(id) ON DELETE RESTRICT,
                organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
                requested_by_user_id INTEGER NOT NULL REFERENCES users(id),
                requested_capacity TEXT NULL,
                available_volunteers INTEGER NOT NULL DEFAULT 0 CHECK(available_volunteers >= 0),
                available_resource_summary TEXT NULL,
                start_at TEXT NULL,
                end_at TEXT NULL,
                status TEXT NOT NULL DEFAULT 'Requested' CHECK(status IN ('Requested','Under Review','Approved','Rejected','Active','Expired','Revoked')),
                reviewed_by_user_id INTEGER NULL REFERENCES users(id),
                reviewed_at TEXT NULL,
                decision_reason TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 5. Resources (Catalog items)
            cur.execute('''
            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT NULL UNIQUE,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                category TEXT NOT NULL,
                unit TEXT NOT NULL DEFAULT 'units',
                description TEXT NULL,
                track_expiry INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 6. Warehouses
            cur.execute('''
            CREATE TABLE IF NOT EXISTS warehouses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                district TEXT NOT NULL,
                address TEXT NOT NULL,
                lat REAL NULL,
                lng REAL NULL,
                status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active','Inactive','Temporarily Closed')),
                manager_user_id INTEGER NULL REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 7. Warehouse Stock (Canonical Stock Balance)
            cur.execute('''
            CREATE TABLE IF NOT EXISTS warehouse_stock (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                warehouse_id INTEGER NOT NULL REFERENCES warehouses(id) ON DELETE RESTRICT,
                resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE RESTRICT,
                on_hand_units INTEGER NOT NULL CHECK(on_hand_units >= 0),
                reserved_units INTEGER NOT NULL DEFAULT 0 CHECK(reserved_units >= 0 AND reserved_units <= on_hand_units),
                target_stock INTEGER NOT NULL CHECK(target_stock > 0),
                status TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(warehouse_id, resource_id)
            )''')

            # 8. Inventory Reservations & Reservation Items
            cur.execute('''
            CREATE TABLE IF NOT EXISTS inventory_reservations (
                id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL REFERENCES emergency_requests(id) ON DELETE RESTRICT,
                dispatch_id TEXT NULL REFERENCES dispatches(id) ON DELETE SET NULL,
                status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active','Partially Issued','Issued','Released','Expired','Cancelled')),
                reserved_by_user_id INTEGER NOT NULL REFERENCES users(id),
                expires_at TEXT NULL,
                released_at TEXT NULL,
                idempotency_key TEXT UNIQUE NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            cur.execute('''
            CREATE TABLE IF NOT EXISTS inventory_reservation_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reservation_id TEXT NOT NULL REFERENCES inventory_reservations(id) ON DELETE CASCADE,
                warehouse_stock_id INTEGER NOT NULL REFERENCES warehouse_stock(id) ON DELETE RESTRICT,
                quantity_units INTEGER NOT NULL CHECK(quantity_units > 0),
                issued_units INTEGER NOT NULL DEFAULT 0 CHECK(issued_units >= 0),
                returned_units INTEGER NOT NULL DEFAULT 0 CHECK(returned_units >= 0),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(reservation_id, warehouse_stock_id)
            )''')

            # 9. Inventory Transactions (Stock Ledger)
            cur.execute('''
            CREATE TABLE IF NOT EXISTS inventory_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                warehouse_stock_id INTEGER NOT NULL REFERENCES warehouse_stock(id) ON DELETE RESTRICT,
                transaction_type TEXT NOT NULL CHECK(transaction_type IN ('OpeningBalance','DonationReceived','Reserved','ReservationReleased','Issued','Returned','Damaged','Adjustment')),
                quantity_units INTEGER NOT NULL CHECK(quantity_units > 0),
                direction TEXT NOT NULL CHECK(direction IN ('IN','OUT','MEMO')),
                reference_type TEXT NULL,
                reference_id TEXT NULL,
                idempotency_key TEXT NULL UNIQUE,
                reason TEXT NULL,
                performed_by_user_id INTEGER NOT NULL REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 10. Request Items & Request Events
            cur.execute('''
            CREATE TABLE IF NOT EXISTS request_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL REFERENCES emergency_requests(id) ON DELETE CASCADE,
                resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE RESTRICT,
                quantity_requested INTEGER NOT NULL CHECK(quantity_requested > 0),
                quantity_reserved INTEGER NOT NULL DEFAULT 0 CHECK(quantity_reserved >= 0),
                quantity_issued INTEGER NOT NULL DEFAULT 0 CHECK(quantity_issued >= 0),
                quantity_delivered INTEGER NOT NULL DEFAULT 0 CHECK(quantity_delivered >= 0),
                quantity_returned INTEGER NOT NULL DEFAULT 0 CHECK(quantity_returned >= 0),
                notes TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            cur.execute('''
            CREATE TABLE IF NOT EXISTS request_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL REFERENCES emergency_requests(id) ON DELETE CASCADE,
                event_type TEXT NOT NULL,
                from_status TEXT NULL,
                to_status TEXT NULL,
                reason TEXT NULL,
                notes TEXT NULL,
                actor_user_id INTEGER NULL REFERENCES users(id),
                metadata_json TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 11. Vehicles & Fleet
            cur.execute('''
            CREATE TABLE IF NOT EXISTS vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_code TEXT NOT NULL UNIQUE,
                vehicle_type TEXT NOT NULL,
                capacity_units INTEGER NULL CHECK(capacity_units IS NULL OR capacity_units >= 0),
                capacity_description TEXT NULL,
                capabilities_json TEXT NULL,
                status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available','Reserved','Loading','EnRoute','Maintenance','OutOfService')),
                current_driver_user_id INTEGER NULL REFERENCES users(id),
                warehouse_id INTEGER NULL REFERENCES warehouses(id),
                last_inspection_at TEXT NULL,
                maintenance_notes TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 12. Dispatch Items & Delivery Proofs
            cur.execute('''
            CREATE TABLE IF NOT EXISTS dispatch_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dispatch_id TEXT NOT NULL REFERENCES dispatches(id) ON DELETE CASCADE,
                resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE RESTRICT,
                quantity_planned INTEGER NOT NULL CHECK(quantity_planned > 0),
                quantity_loaded INTEGER NOT NULL DEFAULT 0 CHECK(quantity_loaded >= 0),
                quantity_delivered INTEGER NOT NULL DEFAULT 0 CHECK(quantity_delivered >= 0),
                quantity_returned INTEGER NOT NULL DEFAULT 0 CHECK(quantity_returned >= 0),
                quantity_damaged INTEGER NOT NULL DEFAULT 0 CHECK(quantity_damaged >= 0),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            cur.execute('''
            CREATE TABLE IF NOT EXISTS delivery_proofs (
                id TEXT PRIMARY KEY,
                dispatch_id TEXT NOT NULL REFERENCES dispatches(id) ON DELETE CASCADE,
                request_id TEXT NOT NULL REFERENCES emergency_requests(id) ON DELETE CASCADE,
                submitted_by_user_id INTEGER NOT NULL REFERENCES users(id),
                proof_type TEXT NOT NULL CHECK(proof_type IN ('RecipientConfirmation','OTP','ImageReference','SupervisorVerification','Other')),
                proof_reference TEXT NULL,
                recipient_confirmation TEXT NULL,
                delivered_at TEXT NULL,
                notes TEXT NULL,
                status TEXT NOT NULL DEFAULT 'Submitted' CHECK(status IN ('Submitted','Verified','Rejected','NeedsReview')),
                reviewed_by_user_id INTEGER NULL REFERENCES users(id),
                reviewed_at TEXT NULL,
                review_reason TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 13. Volunteer Tasks & Checkpoints
            cur.execute('''
            CREATE TABLE IF NOT EXISTS volunteer_tasks (
                id TEXT PRIMARY KEY,
                incident_id TEXT NULL REFERENCES incidents(id) ON DELETE SET NULL,
                zone_id TEXT NULL REFERENCES zones(id) ON DELETE SET NULL,
                organization_id INTEGER NULL REFERENCES organizations(id) ON DELETE SET NULL,
                volunteer_id INTEGER NOT NULL REFERENCES volunteers(id) ON DELETE RESTRICT,
                request_id TEXT NULL REFERENCES emergency_requests(id) ON DELETE SET NULL,
                dispatch_id TEXT NULL REFERENCES dispatches(id) ON DELETE SET NULL,
                title TEXT NOT NULL,
                task_type TEXT NOT NULL,
                description TEXT NOT NULL,
                quantity_expected INTEGER NOT NULL DEFAULT 0 CHECK(quantity_expected >= 0),
                quantity_received INTEGER NOT NULL DEFAULT 0 CHECK(quantity_received >= 0),
                quantity_completed INTEGER NOT NULL DEFAULT 0 CHECK(quantity_completed >= 0),
                quantity_damaged INTEGER NOT NULL DEFAULT 0 CHECK(quantity_damaged >= 0),
                quantity_remaining INTEGER NOT NULL DEFAULT 0 CHECK(quantity_remaining >= 0),
                status TEXT NOT NULL DEFAULT 'Assigned' CHECK(status IN ('Created','Assigned','Accepted','Declined','In Progress','Submitted for Review','Completed','Needs Correction','Cancelled','Reassignment Required')),
                shift_start TEXT NULL,
                shift_end TEXT NULL,
                assigned_by_user_id INTEGER NOT NULL REFERENCES users(id),
                accepted_at TEXT NULL,
                started_at TEXT NULL,
                submitted_at TEXT NULL,
                reviewed_at TEXT NULL,
                completed_at TEXT NULL,
                reviewed_by_user_id INTEGER NULL REFERENCES users(id),
                review_notes TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            cur.execute('''
            CREATE TABLE IF NOT EXISTS task_checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL REFERENCES volunteer_tasks(id) ON DELETE CASCADE,
                checkpoint_type TEXT NOT NULL CHECK(checkpoint_type IN ('CheckIn','Progress','CheckOut','FieldReport')),
                lat REAL NULL,
                lng REAL NULL,
                notes TEXT NULL,
                quantity_delta INTEGER NULL,
                created_by_user_id INTEGER NOT NULL REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 14. Donations & Donation Items
            cur.execute('''
            CREATE TABLE IF NOT EXISTS donations (
                id TEXT PRIMARY KEY,
                organization_id INTEGER NULL REFERENCES organizations(id) ON DELETE SET NULL,
                donor_name TEXT NOT NULL,
                donation_type TEXT NOT NULL CHECK(donation_type IN ('Cash','InKind')),
                incident_id TEXT NULL REFERENCES incidents(id) ON DELETE SET NULL,
                zone_id TEXT NULL REFERENCES zones(id) ON DELETE SET NULL,
                destination_warehouse_id INTEGER NULL REFERENCES warehouses(id) ON DELETE SET NULL,
                declared_amount_paise INTEGER NULL CHECK(declared_amount_paise IS NULL OR declared_amount_paise >= 0),
                currency TEXT NOT NULL DEFAULT 'INR',
                declared_notes TEXT NULL,
                status TEXT NOT NULL DEFAULT 'Submitted' CHECK(status IN ('Draft','Submitted','In Transit','Received','Verification Pending','Accepted','Partially Accepted','Rejected','Cancelled','Exception Review')),
                reference_code TEXT NULL UNIQUE,
                submitted_by_user_id INTEGER NOT NULL REFERENCES users(id),
                received_at TEXT NULL,
                verified_at TEXT NULL,
                verified_by_user_id INTEGER NULL REFERENCES users(id),
                verification_notes TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            cur.execute('''
            CREATE TABLE IF NOT EXISTS donation_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                donation_id TEXT NOT NULL REFERENCES donations(id) ON DELETE CASCADE,
                resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE RESTRICT,
                quantity_declared INTEGER NOT NULL CHECK(quantity_declared > 0),
                quantity_received INTEGER NOT NULL DEFAULT 0 CHECK(quantity_received >= 0),
                quantity_accepted INTEGER NOT NULL DEFAULT 0 CHECK(quantity_accepted >= 0),
                quantity_rejected INTEGER NOT NULL DEFAULT 0 CHECK(quantity_rejected >= 0),
                reason TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 15. Shelter Admissions & Transfers
            cur.execute('''
            CREATE TABLE IF NOT EXISTS shelter_admissions (
                id TEXT PRIMARY KEY,
                shelter_id INTEGER NOT NULL REFERENCES shelters(id) ON DELETE RESTRICT,
                incident_id TEXT NULL REFERENCES incidents(id) ON DELETE SET NULL,
                request_id TEXT NULL REFERENCES emergency_requests(id) ON DELETE SET NULL,
                household_reference TEXT NULL,
                people_count INTEGER NOT NULL CHECK(people_count > 0),
                status TEXT NOT NULL DEFAULT 'Admitted' CHECK(status IN ('Referred','Confirmed','Arrived','Admitted','NoShow','Transferred','Exited','Cancelled')),
                referred_by_user_id INTEGER NULL REFERENCES users(id),
                checked_in_by_user_id INTEGER NULL REFERENCES users(id),
                admitted_at TEXT NULL,
                exited_at TEXT NULL,
                notes TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            cur.execute('''
            CREATE TABLE IF NOT EXISTS shelter_transfers (
                id TEXT PRIMARY KEY,
                admission_id TEXT NOT NULL REFERENCES shelter_admissions(id) ON DELETE RESTRICT,
                from_shelter_id INTEGER NOT NULL REFERENCES shelters(id) ON DELETE RESTRICT,
                to_shelter_id INTEGER NOT NULL REFERENCES shelters(id) ON DELETE RESTRICT,
                people_count INTEGER NOT NULL CHECK(people_count > 0),
                status TEXT NOT NULL DEFAULT 'Completed' CHECK(status IN ('Requested','Approved','InTransit','Completed','Cancelled')),
                requested_by_user_id INTEGER NOT NULL REFERENCES users(id),
                approved_by_user_id INTEGER NULL REFERENCES users(id),
                completed_at TEXT NULL,
                reason TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 16. Financial Tables (All amounts in integer paise)
            cur.execute('''
            CREATE TABLE IF NOT EXISTS fund_budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE RESTRICT,
                organization_id INTEGER NULL REFERENCES organizations(id) ON DELETE SET NULL,
                category TEXT NOT NULL,
                budget_amount_paise INTEGER NOT NULL CHECK(budget_amount_paise >= 0),
                currency TEXT NOT NULL DEFAULT 'INR',
                status TEXT NOT NULL DEFAULT 'Approved' CHECK(status IN ('Draft','Proposed','Approved','Exhausted','Closed')),
                approved_by_user_id INTEGER NOT NULL REFERENCES users(id),
                approved_at TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            cur.execute('''
            CREATE TABLE IF NOT EXISTS fund_requests (
                id TEXT PRIMARY KEY,
                incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE RESTRICT,
                organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
                category TEXT NOT NULL,
                purpose TEXT NOT NULL,
                requested_amount_paise INTEGER NOT NULL CHECK(requested_amount_paise > 0),
                approved_amount_paise INTEGER NOT NULL DEFAULT 0 CHECK(approved_amount_paise >= 0),
                status TEXT NOT NULL DEFAULT 'Submitted' CHECK(status IN ('Draft','Submitted','Approved','Committed','Partially Paid','Paid','Reconciled','Rejected','Cancelled','Disputed')),
                requested_by_user_id INTEGER NOT NULL REFERENCES users(id),
                reviewed_by_user_id INTEGER NULL REFERENCES users(id),
                decision_reason TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            cur.execute('''
            CREATE TABLE IF NOT EXISTS fund_transactions (
                id TEXT PRIMARY KEY,
                fund_request_id TEXT NULL REFERENCES fund_requests(id) ON DELETE SET NULL,
                budget_id INTEGER NULL REFERENCES fund_budgets(id) ON DELETE SET NULL,
                incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE RESTRICT,
                organization_id INTEGER NULL REFERENCES organizations(id) ON DELETE SET NULL,
                transaction_type TEXT NOT NULL CHECK(transaction_type IN ('DonationReceived','Commitment','Payment','Refund','Adjustment')),
                amount_paise INTEGER NOT NULL CHECK(amount_paise > 0),
                currency TEXT NOT NULL DEFAULT 'INR',
                reference_code TEXT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'Completed' CHECK(status IN ('Pending','Completed','Reversed','Failed')),
                performed_by_user_id INTEGER NOT NULL REFERENCES users(id),
                approved_by_user_id INTEGER NULL REFERENCES users(id),
                receipt_reference TEXT NULL,
                reason TEXT NULL,
                occurred_at TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 17. Notifications & Structured Audit Log
            cur.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                entity_type TEXT NULL,
                entity_id TEXT NULL,
                read_at TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            cur.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_user_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NULL,
                old_state_json TEXT NULL,
                new_state_json TEXT NULL,
                reason TEXT NULL,
                request_id TEXT NULL,
                ip_summary TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # 18. Field Reports, Inter-Agency Requests & Public Advisories
            cur.execute('''
            CREATE TABLE IF NOT EXISTS field_reports (
                id TEXT PRIMARY KEY,
                incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE RESTRICT,
                zone_id TEXT NULL REFERENCES zones(id) ON DELETE SET NULL,
                reporter_user_id INTEGER NOT NULL REFERENCES users(id),
                category TEXT NOT NULL,
                severity TEXT NOT NULL CHECK(severity IN ('Low','Medium','High','Critical')),
                description TEXT NOT NULL,
                lat REAL NULL,
                lng REAL NULL,
                resource_requirement TEXT NULL,
                evidence_reference TEXT NULL,
                status TEXT NOT NULL DEFAULT 'Submitted' CHECK(status IN ('Submitted','Under Review','Verified','Actioned','Dismissed')),
                reviewer_user_id INTEGER NULL REFERENCES users(id),
                review_reason TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            cur.execute('''
            CREATE TABLE IF NOT EXISTS inter_agency_requests (
                id TEXT PRIMARY KEY,
                incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE RESTRICT,
                requesting_agency TEXT NOT NULL,
                receiving_agency TEXT NOT NULL,
                capability TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK(quantity > 0),
                urgency TEXT NOT NULL CHECK(urgency IN ('Normal','Urgent','Immediate')),
                destination TEXT NOT NULL,
                needed_by TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Submitted' CHECK(status IN ('Submitted','Acknowledged','Accepted','Mobilized','Completed','Rejected')),
                submitted_by_user_id INTEGER NOT NULL REFERENCES users(id),
                decision_reason TEXT NULL,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                acknowledged_at TEXT NULL,
                accepted_at TEXT NULL,
                mobilized_at TEXT NULL,
                completed_at TEXT NULL
            )''')

            cur.execute('''
            CREATE TABLE IF NOT EXISTS public_advisories (
                id TEXT PRIMARY KEY,
                incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE RESTRICT,
                zone_id TEXT NULL REFERENCES zones(id) ON DELETE SET NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                category TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Draft' CHECK(status IN ('Draft','Review','Approved','Published','Expired','Withdrawn')),
                created_by_user_id INTEGER NOT NULL REFERENCES users(id),
                approved_by_user_id INTEGER NULL REFERENCES users(id),
                published_at TEXT NULL,
                valid_until TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # Performance Indexes
            cur.execute('CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_zones_incident ON zones(incident_id);')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_warehouse_stock_lookup ON warehouse_stock(warehouse_id, resource_id);')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_inv_tx_stock ON inventory_transactions(warehouse_stock_id);')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_volunteer_tasks_volunteer ON volunteer_tasks(volunteer_id);')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_volunteer_tasks_status ON volunteer_tasks(status);')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_dispatches_driver_uid ON dispatches(driver_user_id);')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_shelter_adm_shelter ON shelter_admissions(shelter_id, status);')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_fund_tx_incident ON fund_transactions(incident_id);')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor_user_id, created_at);')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON notifications(recipient_user_id, read_at);')

            cur.execute("INSERT INTO schema_migrations (version, description) VALUES (3, 'Create canonical normalized domain tables and indexes')")

    # Migration 4: Initial Canonical Data Synchronization
    # Synchronizes legacy inventory into resources and warehouse_stock if empty
    if 4 not in applied:
        with conn:
            # 1. Ensure Default Warehouse
            cur.execute("SELECT COUNT(*) FROM warehouses WHERE code = 'WH-CENTRAL'")
            if cur.fetchone()[0] == 0:
                cur.execute('''
                INSERT INTO warehouses (code, name, district, address, lat, lng, status)
                VALUES ('WH-CENTRAL', 'Central Relief Depot', 'Demo District', 'Station Road, Sector 3, Ludhiana', 30.9010, 75.8570, 'Active')
                ''')
            wh_id = cur.execute("SELECT id FROM warehouses WHERE code = 'WH-CENTRAL'").fetchone()[0]

            # 2. Sync inventory rows to resources and warehouse_stock
            inv_rows = cur.execute("SELECT id, resource_name, available_units, target_stock, status FROM inventory").fetchall()
            for r in inv_rows:
                r_name = r['resource_name']
                # Determine category & unit
                cat = 'General'
                unit = 'units'
                r_lower = r_name.lower()
                if 'water' in r_lower:
                    cat = 'Water & Sanitation'; unit = 'litres'
                elif 'food' in r_lower or 'ration' in r_lower:
                    cat = 'Food Supplies'; unit = 'kits'
                elif 'medical' in r_lower:
                    cat = 'Medical'; unit = 'kits'
                elif 'blanket' in r_lower:
                    cat = 'Shelter & Warmth'; unit = 'pieces'
                elif 'tent' in r_lower:
                    cat = 'Shelter & Warmth'; unit = 'tents'

                cur.execute("SELECT id FROM resources WHERE LOWER(name) = ?", (r_name.lower(),))
                res_match = cur.fetchone()
                if not res_match:
                    sku = f"RES-{r['id']:03d}"
                    cur.execute('''
                    INSERT INTO resources (sku, name, category, unit, is_active)
                    VALUES (?, ?, ?, ?, 1)
                    ''', (sku, r_name, cat, unit))
                    res_id = cur.lastrowid
                else:
                    res_id = res_match[0]

                # Ensure warehouse_stock entry
                cur.execute("SELECT id FROM warehouse_stock WHERE warehouse_id = ? AND resource_id = ?", (wh_id, res_id))
                if not cur.fetchone():
                    cur.execute('''
                    INSERT INTO warehouse_stock (warehouse_id, resource_id, on_hand_units, reserved_units, target_stock, status, updated_at)
                    VALUES (?, ?, ?, 0, ?, ?, CURRENT_TIMESTAMP)
                    ''', (wh_id, res_id, r['available_units'], r['target_stock'], r['status']))

            # 3. Ensure Drivers exist in users table
            drivers_to_ensure = [
                ('driver@drras.in', 'Arjun Mehta', 'AR'),
                ('simran.driver@drras.in', 'Simran Kaur', 'SK'),
                ('karan.driver@drras.in', 'Karan Gill', 'KG')
            ]
            from werkzeug.security import generate_password_hash
            for email, name, initials in drivers_to_ensure:
                cur.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email.lower(),))
                if not cur.fetchone():
                    cur.execute('''
                    INSERT INTO users (email, password, name, initials, role, status)
                    VALUES (?, ?, ?, ?, 'Driver', 'ACTIVE')
                    ''', (email.lower(), generate_password_hash('driver123'), name, initials))

            # 4. Sync Dispatches foreign keys (driver_user_id, warehouse_id)
            for d in cur.execute("SELECT id, driver FROM dispatches").fetchall():
                cur.execute("SELECT id FROM users WHERE LOWER(name) = ?", (d['driver'].lower(),))
                u = cur.fetchone()
                driver_uid = u[0] if u else None
                cur.execute("UPDATE dispatches SET driver_user_id = ?, warehouse_id = ? WHERE id = ?", (driver_uid, wh_id, d['id']))

            # 5. Ensure Vehicles table has records matching existing dispatches
            vehicles_to_seed = [
                ('V-12', 'Relief Van', 80, 'Medium cargo van for medical kits and rapid water transport'),
                ('V-04', 'Cargo Truck', 250, 'Heavy 5-ton transport truck for bulk food rations and tents'),
                ('V-18', 'Ambulance', 20, 'Emergency mobile trauma unit with primary medical responder gear'),
                ('V-08', 'Rapid Rescue Unit', 40, 'Inflatable raft transport & water rescue unit with ropes')
            ]
            for vcode, vtype, cap, desc in vehicles_to_seed:
                cur.execute("SELECT id FROM vehicles WHERE vehicle_code = ?", (vcode,))
                if not cur.fetchone():
                    cur.execute('''
                    INSERT INTO vehicles (vehicle_code, vehicle_type, capacity_units, capacity_description, warehouse_id, status)
                    VALUES (?, ?, ?, ?, ?, 'Available')
                    ''', (vcode, vtype, cap, desc, wh_id))

            # Link dispatches to vehicle_id
            for d in cur.execute("SELECT id, vehicle FROM dispatches").fetchall():
                v_code = d['vehicle'].split('Ã‚Â·')[0].strip() if 'Ã‚Â·' in d['vehicle'] else d['vehicle'].split()[0].strip()
                cur.execute("SELECT id FROM vehicles WHERE vehicle_code = ?", (v_code,))
                vrow = cur.fetchone()
                if vrow:
                    cur.execute("UPDATE dispatches SET vehicle_id = ? WHERE id = ?", (vrow[0], d['id']))

            # 6. Ensure default approved NGO organization and membership exist
            cur.execute("SELECT id FROM organizations WHERE id = 1")
            if not cur.fetchone():
                cur.execute('''
                INSERT INTO organizations (id, name, organization_type, registration_reference, contact_name, contact_email, contact_phone, status)
                VALUES (1, 'Punjab Relief Foundation', 'NGO', 'REG-NGO-2024-PB', 'Neha Kapoor', 'ngo@drras.in', '+91 98765 43210', 'Approved')
                ''')

            # Ensure NGO user membership
            cur.execute("SELECT id FROM users WHERE LOWER(email) = 'ngo@drras.in'")
            ngo_u = cur.fetchone()
            if ngo_u:
                cur.execute("SELECT id FROM organization_memberships WHERE organization_id = 1 AND user_id = ?", (ngo_u[0],))
                if not cur.fetchone():
                    cur.execute('''
                    INSERT INTO organization_memberships (organization_id, user_id, membership_role, status)
                    VALUES (1, ?, 'Coordinator', 'Active')
                    ''', (ngo_u[0],))

            cur.execute("INSERT INTO schema_migrations (version, description) VALUES (4, 'Sync legacy inventory and vehicles to canonical models')")


    # Migration 5: Explicit owner scopes and response-team assignment records.
    # Only rows with reliable provenance are classified; ambiguous legacy rows stay unassigned.
    applied = {row[0] for row in cur.execute("SELECT version FROM schema_migrations").fetchall()}
    if 5 not in applied:
        with conn:
            for table in ('warehouses', 'vehicles', 'dispatches', 'shelters'):
                if not table_has_column(conn, table, 'owner_type'):
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN owner_type TEXT NOT NULL DEFAULT 'unassigned'")
                if not table_has_column(conn, table, 'owner_organization_id'):
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN owner_organization_id INTEGER NULL REFERENCES organizations(id) ON DELETE RESTRICT")
            if not table_has_column(conn, 'volunteers', 'owner_type'):
                cur.execute("ALTER TABLE volunteers ADD COLUMN owner_type TEXT NOT NULL DEFAULT 'unassigned'")

            cur.execute("UPDATE warehouses SET owner_type='government' WHERE code='WH-CENTRAL' AND owner_type='unassigned'")
            cur.execute('''UPDATE warehouses SET owner_type='ngo', owner_organization_id=(
                SELECT COALESCE(u.organization_id, (SELECT MIN(om.organization_id) FROM organization_memberships om WHERE om.user_id=u.id AND om.status='Active'))
                FROM users u WHERE u.id=warehouses.manager_user_id)
                WHERE manager_user_id IN (SELECT id FROM users WHERE role='NGO Coordinator')''')
            cur.execute('''UPDATE warehouses SET owner_type='government' WHERE owner_type='unassigned'
                AND manager_user_id IN (SELECT id FROM users WHERE role IN ('Administrator','Government Official'))''')
            cur.execute('''UPDATE vehicles SET owner_type=(SELECT w.owner_type FROM warehouses w WHERE w.id=vehicles.warehouse_id),
                owner_organization_id=(SELECT w.owner_organization_id FROM warehouses w WHERE w.id=vehicles.warehouse_id)
                WHERE EXISTS (SELECT 1 FROM warehouses w WHERE w.id=vehicles.warehouse_id AND w.owner_type IN ('government','ngo'))''')
            cur.execute('''UPDATE dispatches SET owner_type=(SELECT w.owner_type FROM warehouses w WHERE w.id=dispatches.warehouse_id),
                owner_organization_id=(SELECT w.owner_organization_id FROM warehouses w WHERE w.id=dispatches.warehouse_id)
                WHERE EXISTS (SELECT 1 FROM warehouses w WHERE w.id=dispatches.warehouse_id AND w.owner_type IN ('government','ngo'))''')
            cur.execute('''UPDATE shelters SET owner_type='ngo', owner_organization_id=(
                SELECT COALESCE(u.organization_id, (SELECT MIN(om.organization_id) FROM organization_memberships om WHERE om.user_id=u.id AND om.status='Active'))
                FROM users u WHERE u.id=shelters.created_by_user_id)
                WHERE created_by_user_id IN (SELECT id FROM users WHERE role='NGO Coordinator')''')
            cur.execute("UPDATE shelters SET owner_type='government' WHERE created_by_user_id IN (SELECT id FROM users WHERE role IN ('Administrator','Government Official'))")
            cur.execute("UPDATE volunteers SET owner_type='ngo' WHERE organization_id IS NOT NULL")

            cur.execute('''CREATE TABLE IF NOT EXISTS government_personnel (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, category TEXT NOT NULL,
                service_unit TEXT NOT NULL, skills TEXT NULL,
                status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active','Inactive','Pending','Rejected')),
                incident_id TEXT NULL REFERENCES incidents(id) ON DELETE SET NULL,
                zone_id TEXT NULL REFERENCES zones(id) ON DELETE SET NULL,
                user_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
                created_by_user_id INTEGER NOT NULL REFERENCES users(id),
                approved_by_user_id INTEGER NULL REFERENCES users(id), approved_at TEXT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NULL)''')
            cur.execute('''CREATE TABLE IF NOT EXISTS response_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL REFERENCES emergency_requests(id) ON DELETE RESTRICT,
                owner_type TEXT NOT NULL CHECK(owner_type IN ('government','ngo')),
                organization_id INTEGER NULL REFERENCES organizations(id) ON DELETE RESTRICT,
                government_personnel_id INTEGER NULL REFERENCES government_personnel(id) ON DELETE RESTRICT,
                volunteer_id INTEGER NULL REFERENCES volunteers(id) ON DELETE RESTRICT,
                driver_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE RESTRICT,
                dispatch_id TEXT NULL REFERENCES dispatches(id) ON DELETE SET NULL,
                status TEXT NOT NULL DEFAULT 'Assigned' CHECK(status IN ('Assigned','Active','Completed','Cancelled')),
                assigned_by_user_id INTEGER NOT NULL REFERENCES users(id),
                assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, notes TEXT NULL,
                UNIQUE(request_id, owner_type, organization_id))''')
            cur.execute('''CREATE TABLE IF NOT EXISTS government_driver_approvals (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                classification TEXT NOT NULL DEFAULT 'Government Driver' CHECK(classification='Government Driver'),
                approved_by_user_id INTEGER NOT NULL REFERENCES users(id),
                approved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, reason TEXT NULL)''')
            cur.execute('''CREATE TABLE IF NOT EXISTS ngo_personnel_approvals (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                personnel_type TEXT NOT NULL CHECK(personnel_type IN ('Volunteer','Driver')),
                decision TEXT NOT NULL CHECK(decision IN ('Approved','Rejected')),
                decided_by_user_id INTEGER NOT NULL REFERENCES users(id),
                decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, reason TEXT NULL,
                PRIMARY KEY(user_id, organization_id, personnel_type))''')
            # These three active accounts are the explicit legacy Government demo driver identities.
            cur.execute("""INSERT OR IGNORE INTO government_driver_approvals (user_id, approved_by_user_id, reason)
                SELECT u.id, (SELECT id FROM users WHERE role='Administrator' ORDER BY id LIMIT 1), 'Existing active Government demo driver provisioned by the legacy seed process'
                FROM users u WHERE u.role='Driver' AND u.status='ACTIVE' AND u.organization_id IS NULL
                  AND LOWER(u.email) IN ('driver@drras.in','simran.driver@drras.in','karan.driver@drras.in')
                  AND EXISTS (SELECT 1 FROM users a WHERE a.role='Administrator')""")
            # Reconcile the seeded coordinator with its approved organization, even when older
            # databases predate organization_memberships population.
            cur.execute("""INSERT OR IGNORE INTO organization_memberships (organization_id,user_id,membership_role,status)
                SELECT COALESCE((SELECT id FROM organizations WHERE LOWER(contact_email)=LOWER(u.email) AND status='Approved' ORDER BY id LIMIT 1),
                                (SELECT id FROM organizations WHERE organization_type='NGO' AND status='Approved' ORDER BY id LIMIT 1)),
                       u.id,'Coordinator','Active'
                FROM users u WHERE LOWER(u.email)='ngo@drras.in' AND u.role='NGO Coordinator'
                  AND EXISTS (SELECT 1 FROM organizations WHERE organization_type='NGO' AND status='Approved')""")            # Preserve and classify the named legacy demo Volunteer through its existing NGO account.
            cur.execute("""UPDATE users SET organization_id=COALESCE((SELECT organization_id FROM organization_memberships WHERE user_id=users.id AND membership_role='Coordinator' AND status='Active' ORDER BY organization_id LIMIT 1),(SELECT organization_id FROM organization_memberships WHERE user_id=(SELECT id FROM users WHERE LOWER(email)='ngo@drras.in') AND membership_role='Coordinator' AND status='Active' ORDER BY organization_id LIMIT 1))
                WHERE LOWER(email)='volunteer@drras.in' AND role='Volunteer' AND organization_id IS NULL""")
            cur.execute("""INSERT OR IGNORE INTO organization_memberships (organization_id,user_id,membership_role,status)
                SELECT u.organization_id,u.id,'Volunteer','Active' FROM users u
                WHERE LOWER(u.email)='volunteer@drras.in' AND u.organization_id IS NOT NULL""")
            cur.execute("""UPDATE volunteers SET user_id=(SELECT id FROM users WHERE LOWER(email)='volunteer@drras.in'),
                organization_id=(SELECT organization_id FROM users WHERE LOWER(email)='volunteer@drras.in'),
                owner_type='ngo',verified=1
                WHERE LOWER(name)=(SELECT LOWER(name) FROM users WHERE LOWER(email)='volunteer@drras.in')""")
            cur.execute("""INSERT OR IGNORE INTO ngo_personnel_approvals (user_id,organization_id,personnel_type,decision,decided_by_user_id,reason)
                SELECT u.id,u.organization_id,'Volunteer','Approved',
                  COALESCE((SELECT id FROM users WHERE role='NGO Coordinator' AND (organization_id=u.organization_id OR id IN (SELECT user_id FROM organization_memberships WHERE organization_id=u.organization_id AND membership_role='Coordinator')) LIMIT 1),
                           (SELECT id FROM users WHERE role='Administrator' LIMIT 1)),
                  'Existing linked demo Volunteer account'
                FROM users u WHERE LOWER(u.email)='volunteer@drras.in' AND u.organization_id IS NOT NULL""")
            cur.execute('CREATE INDEX IF NOT EXISTS idx_scope_warehouses ON warehouses(owner_type, owner_organization_id)')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_scope_vehicles ON vehicles(owner_type, owner_organization_id, status)')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_scope_dispatches ON dispatches(owner_type, owner_organization_id, status)')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_response_assignments_driver ON response_assignments(driver_user_id, status)')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_response_assignments_volunteer ON response_assignments(volunteer_id, status)')
            cur.execute("INSERT INTO schema_migrations (version, description) VALUES (5, 'Add ownership scopes and Government/NGO response assignments')")

    # Migration 6: Repair missing demo coordinator membership from the approved organization contact.
    applied = {row[0] for row in cur.execute("SELECT version FROM schema_migrations").fetchall()}
    if 6 not in applied:
        with conn:
            cur.execute("""INSERT OR IGNORE INTO organization_memberships (organization_id,user_id,membership_role,status)
                SELECT COALESCE((SELECT id FROM organizations WHERE LOWER(contact_email)=LOWER(u.email) AND status='Approved' ORDER BY id LIMIT 1),
                                (SELECT id FROM organizations WHERE organization_type='NGO' AND status='Approved' ORDER BY id LIMIT 1)),
                       u.id,'Coordinator','Active'
                FROM users u WHERE LOWER(u.email)='ngo@drras.in' AND u.role='NGO Coordinator'
                  AND EXISTS (SELECT 1 FROM organizations WHERE organization_type='NGO' AND status='Approved')""")
            cur.execute("""UPDATE shelters SET owner_type='government' WHERE owner_type='unassigned'
                AND LOWER(name) LIKE 'govt.%'""")
            cur.execute("INSERT INTO schema_migrations (version,description) VALUES (6,'Repair missing coordinator membership and classify explicitly named Government shelters')")
    # Migrations 7 and 8 are retained as version markers for databases upgraded
    # from releases that created timeout-based request cycles.
    applied = {row[0] for row in cur.execute("SELECT version FROM schema_migrations").fetchall()}
    if 7 not in applied:
        with conn:
            cur.execute("INSERT INTO schema_migrations (version,description) VALUES (7,'Legacy timeout-cycle migration marker')")
    applied = {row[0] for row in cur.execute("SELECT version FROM schema_migrations").fetchall()}
    if 8 not in applied:
        with conn:
            cur.execute("INSERT INTO schema_migrations (version,description) VALUES (8,'Legacy timeout-cycle backfill migration marker')")

    # Migration 9: add district data used by the shelter creation form/API.
    applied = {row[0] for row in cur.execute("SELECT version FROM schema_migrations").fetchall()}
    if 9 not in applied:
        with conn:
            if not table_has_column(conn,'shelters','district'):
                cur.execute("ALTER TABLE shelters ADD COLUMN district TEXT NULL")
            cur.execute("INSERT INTO schema_migrations (version,description) VALUES (9,'Add shelter district field used by scoped shelter creation')")

    # Migration 10: collapse exact NGO roster/shelter duplicates created by older
    # startup seeds. Keep the lowest stable row id and reparent operational history.
    applied = {row[0] for row in cur.execute("SELECT version FROM schema_migrations").fetchall()}
    if 10 not in applied:
        with conn:
            volunteer_groups = cur.execute("""
                SELECT user_id, MIN(id) AS keep_id FROM volunteers
                WHERE user_id IS NOT NULL GROUP BY user_id HAVING COUNT(*) > 1
            """).fetchall()
            for group in volunteer_groups:
                keep_id = group['keep_id']
                duplicates = [r['id'] for r in cur.execute(
                    "SELECT id FROM volunteers WHERE user_id=? AND id<>? ORDER BY id",
                    (group['user_id'], keep_id)).fetchall()]
                for duplicate_id in duplicates:
                    cur.execute("UPDATE volunteer_tasks SET volunteer_id=? WHERE volunteer_id=?", (keep_id, duplicate_id))
                    cur.execute("UPDATE response_assignments SET volunteer_id=? WHERE volunteer_id=?", (keep_id, duplicate_id))
                    cur.execute("DELETE FROM volunteers WHERE id=?", (duplicate_id,))

            shelter_groups = cur.execute("""
                SELECT name, owner_organization_id, MIN(id) AS keep_id, MAX(occupants) AS max_occupants
                FROM shelters WHERE owner_type='ngo' AND owner_organization_id IS NOT NULL
                  AND name LIKE '% Relief Shelter'
                GROUP BY name, owner_organization_id HAVING COUNT(*) > 1
            """).fetchall()
            for group in shelter_groups:
                keep_id = group['keep_id']
                duplicates = [r['id'] for r in cur.execute(
                    "SELECT id FROM shelters WHERE name=? AND owner_type='ngo' AND owner_organization_id=? AND id<>? ORDER BY id",
                    (group['name'], group['owner_organization_id'], keep_id)).fetchall()]
                for duplicate_id in duplicates:
                    cur.execute("UPDATE shelter_admissions SET shelter_id=? WHERE shelter_id=?", (keep_id, duplicate_id))
                    cur.execute("UPDATE shelter_transfers SET from_shelter_id=? WHERE from_shelter_id=?", (keep_id, duplicate_id))
                    cur.execute("UPDATE shelter_transfers SET to_shelter_id=? WHERE to_shelter_id=?", (keep_id, duplicate_id))
                    cur.execute("DELETE FROM shelters WHERE id=?", (duplicate_id,))
                cur.execute("UPDATE shelters SET occupants=MAX(occupants,?) WHERE id=?", (group['max_occupants'], keep_id))

            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_volunteers_user_id ON volunteers(user_id) WHERE user_id IS NOT NULL")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_demo_ngo_relief_shelter ON shelters(name,owner_organization_id) WHERE owner_type='ngo' AND owner_organization_id IS NOT NULL AND name LIKE '% Relief Shelter'")
            cur.execute("INSERT INTO schema_migrations (version,description) VALUES (10,'Deduplicate repeat-seeded NGO volunteers and shelters; enforce stable demo roster keys')")

    # Migration 11: replace timeout cycles with an immediate, persisted claim.
    applied = {row[0] for row in cur.execute("SELECT version FROM schema_migrations").fetchall()}
    if 11 not in applied:
        with conn:
            if not table_has_column(conn, 'emergency_requests', 'response_owner_type'):
                cur.execute("ALTER TABLE emergency_requests ADD COLUMN response_owner_type TEXT NULL CHECK(response_owner_type IN ('government','ngo'))")
            if not table_has_column(conn, 'emergency_requests', 'response_organization_id'):
                cur.execute("ALTER TABLE emergency_requests ADD COLUMN response_organization_id INTEGER NULL REFERENCES organizations(id) ON DELETE RESTRICT")
            if not table_has_column(conn, 'emergency_requests', 'claimed_at'):
                cur.execute("ALTER TABLE emergency_requests ADD COLUMN claimed_at TEXT NULL")
            cur.execute("""UPDATE emergency_requests SET
                response_owner_type=(SELECT a.owner_type FROM response_assignments a
                    WHERE a.request_id=emergency_requests.id AND a.status IN ('Assigned','Active') ORDER BY a.id LIMIT 1),
                response_organization_id=(SELECT a.organization_id FROM response_assignments a
                    WHERE a.request_id=emergency_requests.id AND a.status IN ('Assigned','Active') ORDER BY a.id LIMIT 1),
                claimed_at=(SELECT a.assigned_at FROM response_assignments a
                    WHERE a.request_id=emergency_requests.id AND a.status IN ('Assigned','Active') ORDER BY a.id LIMIT 1)
                WHERE EXISTS(SELECT 1 FROM response_assignments a
                    WHERE a.request_id=emergency_requests.id AND a.status IN ('Assigned','Active'))""")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_emergency_requests_response_owner ON emergency_requests(response_owner_type,response_organization_id)")
            cur.execute("DROP TABLE IF EXISTS request_escalation_cycles")
            cur.execute("INSERT INTO schema_migrations (version,description) VALUES (11,'Remove timeout cycles and persist the winning response owner')")

    # Migration 12: persist unique fictional registration numbers for the fleet.
    # The app previously identified vehicles only by vehicle_code, so registration
    # is additive and preserves every vehicle primary key and ownership link.
    applied = {row[0] for row in cur.execute("SELECT version FROM schema_migrations").fetchall()}
    if 12 not in applied:
        with conn:
            if not table_has_column(conn, 'vehicles', 'registration_number'):
                cur.execute("ALTER TABLE vehicles ADD COLUMN registration_number TEXT NULL")
            cur.execute("""UPDATE vehicles SET registration_number=
                CASE WHEN owner_type='government' THEN 'PB10GV'
                     WHEN owner_organization_id=1 THEN 'PB11PR'
                     WHEN owner_organization_id=2 THEN 'PB12KA'
                     WHEN owner_organization_id=3 THEN 'PB13RC'
                     ELSE 'PB99UN' END || printf('%04d',id)
                WHERE registration_number IS NULL OR trim(registration_number)=''""")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_vehicles_registration_number ON vehicles(registration_number)")
            cur.execute("INSERT INTO schema_migrations (version,description) VALUES (12,'Add unique persisted fleet registration numbers')")
