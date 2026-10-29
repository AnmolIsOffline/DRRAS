"""Stable, fictional identity normalization for the packaged DRRAS demo users.

Identity is keyed by immutable user id so renaming never changes credentials,
ownership, approvals, assignments, or future seed matching.
"""
from __future__ import annotations

FIRST = "Aarav Aditi Aman Amrita Ananya Arjun Avneet Devika Guneet Harleen Jasleen Kabir Kiran Manpreet Navdeep Priya Raghav Simran Tanvi Vanya Yashika Zorawar Meher Ishaan".split()
LAST = "Ahluwalia Anand Bedi Chawla Dhillon Gill Grewal Joshi Kapoor Kaur Khanna Malhotra Mehta Nanda Sandhu Sharma Sidhu Singh Sodhi Suri Verma Walia".split()
ORG = {1: "punjabrelief", 2: "khalsaaid", 3: "redcross"}
ORG_NAMES = {1: "Punjab Relief Coalition", 2: "Khalsa Aid Foundation", 3: "Red Cross District Chapter"}


def human_name(user_id: int) -> str:
    i = int(user_id) - 1
    return f"{FIRST[i % len(FIRST)]} {LAST[(i * 7 + i // len(FIRST)) % len(LAST)]}"


def account_category(role: str, organization_id: int | None, user_id: int) -> str:
    if role == "Driver":
        return (f"ngo_{ORG[organization_id]}_driver" if organization_id in ORG else "govt_driver")
    if role == "Volunteer":
        return (f"ngo_{ORG[organization_id]}_volunteer" if organization_id in ORG else "govt_responder")
    if role == "Administrator": return "govt_admin"
    if role == "Government Official": return "govt_official"
    if role == "NGO Coordinator":
        oid = organization_id
        return f"ngo_{ORG.get(oid, 'punjabrelief')}_coordinator"
    return "citizen"


def canonical_email(name: str, category: str) -> str:
    first, last = name.lower().split(" ", 1)
    first = "".join(ch for ch in first if ch.isalnum())
    last = "".join(ch for ch in last if ch.isalnum())
    return f"{first}.{last}_{category}@drras-demo.local"


def normalize_demo_identities(conn) -> int:
    """Rename demo identities and their linked profile/snapshot labels in place."""
    rows = conn.execute("SELECT id,name,role,organization_id FROM users ORDER BY id").fetchall()
    updates = []
    for row in rows:
        uid, role, oid = row["id"], row["role"], row["organization_id"]
        name = human_name(uid)
        category = account_category(role, oid, uid)
        email = canonical_email(name, category)
        conflict = conn.execute("SELECT id FROM users WHERE email=? COLLATE NOCASE AND id<>?", (email, uid)).fetchone()
        if conflict:
            raise ValueError(f"Canonical demo email collision: {email} (users {uid}, {conflict['id']})")
        conn.execute("UPDATE users SET name=?,email=?,initials=? WHERE id=?", (name, email, ''.join(p[0] for p in name.split()).upper(), uid))
        conn.execute("UPDATE volunteers SET name=?,initials=? WHERE user_id=?", (name, ''.join(p[0] for p in name.split()).upper(), uid))
        conn.execute("UPDATE government_personnel SET name=? WHERE user_id=?", (name, uid))
        conn.execute("UPDATE dispatches SET driver=? WHERE driver_user_id=?", (name, uid))
        if role == "NGO Coordinator" and oid in ORG:
            conn.execute("UPDATE organizations SET contact_name=?,contact_email=? WHERE id=?", (name, email, oid))
        updates.append((uid, name, email))
    return len(updates)
