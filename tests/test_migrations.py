import os
import tempfile
import sqlite3
import pytest
import migrations
import database

def test_fresh_database_migrations():
    """Verifies that all migrations run cleanly on a completely fresh, empty SQLite database."""
    fd, path = tempfile.mkstemp(suffix='.db', prefix='fresh_test_')
    os.close(fd)
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")

        # Apply all migrations
        migrations.apply_migrations(conn)

        # Verify schema_migrations has recorded versions
        rows = conn.execute("SELECT version, description FROM schema_migrations ORDER BY version ASC").fetchall()
        applied_versions = [r['version'] for r in rows]
        assert 1 in applied_versions
        assert 2 in applied_versions
        assert 3 in applied_versions
        assert 4 in applied_versions
        assert 7 in applied_versions
        assert 8 in applied_versions
        assert 9 in applied_versions
        assert 11 in applied_versions
        assert 13 in applied_versions
        assert conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='request_escalation_cycles'").fetchone()[0] == 0
        request_columns = [c['name'] for c in conn.execute('PRAGMA table_info(emergency_requests)').fetchall()]
        assert {'response_owner_type', 'response_organization_id', 'claimed_at'} <= set(request_columns)

        # Verify key canonical tables exist
        tables = [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert 'incidents' in tables
        assert 'zones' in tables
        assert 'organizations' in tables
        assert 'zone_adoptions' in tables
        assert 'resources' in tables
        assert 'warehouses' in tables
        assert 'warehouse_stock' in tables
        assert 'inventory_reservations' in tables
        assert 'volunteer_tasks' in tables
        assert 'donations' in tables
        assert 'shelter_admissions' in tables
        assert 'shelter_transfers' in tables
        assert 'fund_budgets' in tables
        assert 'fund_requests' in tables
        assert 'fund_transactions' in tables
        assert 'audit_logs' in tables
        assert 'notifications' in tables
        assert 'district' in [c['name'] for c in conn.execute('PRAGMA table_info(shelters)').fetchall()]
        assignment_columns = {c['name'] for c in conn.execute('PRAGMA table_info(response_assignments)').fetchall()}
        assert {'driver_decision','driver_decided_at','driver_decline_reason'} <= assignment_columns

        # Legacy migration markers can be reapplied without restoring timeout state or losing requests.
        conn.execute("INSERT INTO emergency_requests(id,requester_name,area,address,need,people_affected,priority_score,status,created_at) VALUES('REQ-LEGACY-1','Legacy Citizen','Ward 1','Ward 1','Food',2,50,'Awaiting allocation','2026-10-27 00:00:00')")
        conn.execute("DELETE FROM schema_migrations WHERE version=8")
        migrations.apply_migrations(conn)
        assert conn.execute("SELECT requester_name FROM emergency_requests WHERE id='REQ-LEGACY-1'").fetchone()['requester_name']=='Legacy Citizen'
        assert conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='request_escalation_cycles'").fetchone()[0] == 0
        # Re-running migrations should be idempotent and not error.
        migrations.apply_migrations(conn)
        conn.close()
    finally:
        if os.path.exists(path):
            os.remove(path)

def test_migration_from_legacy_schema():
    """Verifies that applying migrations to an existing legacy schema extends tables without data loss."""
    fd, path = tempfile.mkstemp(suffix='.db', prefix='legacy_test_')
    os.close(fd)
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")

        # Create old schema
        conn.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            initials TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE'
        )''')
        conn.execute("INSERT INTO users (email, password, name, initials, role) VALUES ('legacy@drras.in', 'pwd', 'Legacy User', 'LU', 'Citizen')")
        conn.commit()

        # Apply migrations
        migrations.apply_migrations(conn)

        # Verify existing data preserved
        user = conn.execute("SELECT * FROM users WHERE email = 'legacy@drras.in'").fetchone()
        assert user is not None
        assert user['name'] == 'Legacy User'

        # Verify new columns added
        assert 'organization_id' in user.keys()
        assert 'phone' in user.keys()
        assert 'suspended_at' in user.keys()

        conn.close()
    finally:
        if os.path.exists(path):
            os.remove(path)
