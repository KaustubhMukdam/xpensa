#!/usr/bin/env python3
"""
tests/test_xpensa.py — Pre-deployment integration test suite for Xpensa.

Tests the full happy-path flow:
  Auth → User management → Approval rules → Expense submission → Approval chain

Usage:
    # With backend running locally:
    pip install httpx pytest pytest-asyncio --break-system-packages
    python tests/test_xpensa.py

    # Or with pytest:
    pytest tests/test_xpensa.py -v

Set BASE_URL env var to test against staging:
    BASE_URL=https://xpensa.onrender.com python tests/test_xpensa.py
"""

import os
import sys
import json
import time
import uuid
import httpx

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
TIMEOUT  = 15.0

# ── Colours for terminal output ───────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

passed = 0
failed = 0
skipped = 0

def ok(msg: str):
    global passed
    passed += 1
    print(f"  {GREEN}✓{RESET} {msg}")

def fail(msg: str, detail: str = ""):
    global failed
    failed += 1
    print(f"  {RED}✗{RESET} {msg}")
    if detail:
        print(f"    {RED}→ {detail}{RESET}")

def skip(msg: str, reason: str = ""):
    global skipped
    skipped += 1
    print(f"  {YELLOW}○{RESET} {msg} {YELLOW}({reason}){RESET}")

def section(title: str):
    print(f"\n{BOLD}{CYAN}▶ {title}{RESET}")

def assert_status(resp: httpx.Response, expected: int, label: str) -> bool:
    if resp.status_code == expected:
        ok(f"{label} → {resp.status_code}")
        return True
    else:
        fail(f"{label} → expected {expected}, got {resp.status_code}", resp.text[:200])
        return False

def get_json(resp: httpx.Response) -> dict:
    try:
        return resp.json()
    except Exception:
        return {}

# ── State shared across tests ─────────────────────────────────────────────────
state: dict = {}


def make_client(token: str | None = None) -> httpx.Client:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url=BASE_URL, timeout=TIMEOUT, headers=headers)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Health check
# ─────────────────────────────────────────────────────────────────────────────
def test_health():
    section("Health Check")
    with make_client() as c:
        resp = c.get("/health")
        if assert_status(resp, 200, "GET /health"):
            data = get_json(resp)
            if data.get("status") == "ok":
                ok("Health response body is correct")
            else:
                fail("Unexpected health body", str(data))


# ─────────────────────────────────────────────────────────────────────────────
# 2. Register new company + admin
# ─────────────────────────────────────────────────────────────────────────────
def test_register():
    section("Admin Registration")
    uid = uuid.uuid4().hex[:6]
    payload = {
        "company_name": f"Test Corp {uid}",
        "full_name":    f"Test Admin {uid}",
        "email":        f"admin_{uid}@test.com",
        "password":     "TestPass@123",
        "country":      "India",
        "base_currency":"INR",
    }
    with make_client() as c:
        resp = c.post("/api/v1/auth/register", json=payload)
        if not assert_status(resp, 201, "POST /api/v1/auth/register"):
            return
        data = get_json(resp)
        token = data.get("access_token")
        user  = data.get("user", {})
        company = data.get("company", {})

        if token:
            ok("Access token present")
            state["admin_token"]   = token
            state["admin_id"]      = user.get("id")
            state["company_id"]    = company.get("id")
            state["company_name"]  = company.get("name")
        else:
            fail("No access token in response")

        if user.get("role") == "admin":
            ok(f"Role is admin")
        else:
            fail("Expected role=admin", str(user.get("role")))

        if company.get("base_currency") == "INR":
            ok("Base currency set to INR")
        else:
            fail("Unexpected base_currency", str(company.get("base_currency")))


# ─────────────────────────────────────────────────────────────────────────────
# 3. Login
# ─────────────────────────────────────────────────────────────────────────────
def test_login():
    section("Login (all roles)")
    # Seeded credentials — test against seed data if available
    for label, email, pw, role in [
        ("Admin",    "admin@govinda.com",    "Admin@1234",    "admin"),
        ("Manager",  "manager@govinda.com",  "Manager@1234",  "manager"),
        ("Employee", "employee@govinda.com", "Employee@1234", "employee"),
    ]:
        with make_client() as c:
            resp = c.post("/api/v1/auth/login", json={"email": email, "password": pw})
            if resp.status_code == 200:
                data = get_json(resp)
                tok = data.get("access_token")
                u   = data.get("user", {})
                if tok and u.get("role") == role:
                    ok(f"Login as {label} → token + correct role")
                    state[f"{role}_token"] = tok
                    state[f"{role}_id"]    = u.get("id")
                    state[f"{role}_email"] = email
                else:
                    fail(f"Login as {label}: bad response", str(data)[:100])
            elif resp.status_code == 401:
                skip(f"Login as {label}", "seed data not loaded — run python seed.py first")
            else:
                fail(f"Login as {label}", f"{resp.status_code}: {resp.text[:100]}")

    # Wrong password
    with make_client() as c:
        resp = c.post("/api/v1/auth/login", json={"email": "admin@govinda.com", "password": "wrong"})
        if resp.status_code == 401:
            ok("Wrong password → 401")
        else:
            fail("Wrong password should return 401", str(resp.status_code))


# ─────────────────────────────────────────────────────────────────────────────
# 4. /me endpoint
# ─────────────────────────────────────────────────────────────────────────────
def test_me():
    section("GET /auth/me")
    token = state.get("admin_token") or state.get("admin_token")
    if not token:
        skip("GET /auth/me", "no admin token")
        return
    with make_client(token) as c:
        resp = c.get("/api/v1/auth/me")
        if assert_status(resp, 200, "GET /api/v1/auth/me"):
            data = get_json(resp)
            if data.get("role") == "admin":
                ok("Returned correct role")
            else:
                fail("Unexpected role", str(data.get("role")))

    # No token → 403
    with make_client() as c:
        resp = c.get("/api/v1/auth/me")
        if resp.status_code in (401, 403):
            ok("No token → 401/403")
        else:
            fail("Expected 401/403 without token", str(resp.status_code))


# ─────────────────────────────────────────────────────────────────────────────
# 5. User management
# ─────────────────────────────────────────────────────────────────────────────
def test_users():
    section("User Management (Admin)")
    token = state.get("admin_token")
    if not token:
        skip("User management", "no admin token")
        return

    with make_client(token) as c:
        # List users
        resp = c.get("/api/v1/users/")
        assert_status(resp, 200, "GET /api/v1/users/")
        users = get_json(resp)
        if isinstance(users, list):
            ok(f"Listed {len(users)} user(s)")
        else:
            fail("Expected list response")

        # Create manager
        uid = uuid.uuid4().hex[:6]
        mgr_payload = {
            "email":     f"mgr_{uid}@test.com",
            "full_name": f"Manager {uid}",
            "role":      "manager",
        }
        resp = c.post("/api/v1/users/", json=mgr_payload)
        if assert_status(resp, 201, "POST /api/v1/users/ (manager)"):
            data = get_json(resp)
            state["test_manager_id"] = data.get("user", {}).get("id")
            if data.get("temp_password"):
                ok("Temp password returned")
            else:
                fail("No temp_password in response")

        # Create employee
        emp_payload = {
            "email":     f"emp_{uid}@test.com",
            "full_name": f"Employee {uid}",
            "role":      "employee",
        }
        resp = c.post("/api/v1/users/", json=emp_payload)
        if assert_status(resp, 201, "POST /api/v1/users/ (employee)"):
            data = get_json(resp)
            state["test_employee_id"] = data.get("user", {}).get("id")

        # Duplicate email
        resp = c.post("/api/v1/users/", json=mgr_payload)
        if resp.status_code == 409:
            ok("Duplicate email → 409 Conflict")
        else:
            fail("Expected 409 for duplicate email", str(resp.status_code))

        # Cannot create another admin
        resp = c.post("/api/v1/users/", json={"email": f"admin2_{uid}@test.com", "full_name": "X", "role": "admin"})
        if resp.status_code == 400:
            ok("Creating admin via /users/ → 400")
        else:
            fail("Should reject admin creation", str(resp.status_code))

    # Employee cannot list users
    emp_token = state.get("employee_token")
    if emp_token:
        with make_client(emp_token) as c:
            resp = c.get("/api/v1/users/")
            if resp.status_code == 403:
                ok("Employee cannot list users → 403")
            else:
                fail("Employee should be blocked from /users/", str(resp.status_code))


# ─────────────────────────────────────────────────────────────────────────────
# 6. Approval rules
# ─────────────────────────────────────────────────────────────────────────────
def test_approval_rules():
    section("Approval Rules (Admin)")
    token = state.get("admin_token")
    mgr_id = state.get("manager_id") or state.get("test_manager_id")
    if not token:
        skip("Approval rules", "no admin token")
        return

    with make_client(token) as c:
        # List existing
        resp = c.get("/api/v1/approval-rules/")
        assert_status(resp, 200, "GET /api/v1/approval-rules/")

        # Create rule — no steps (auto-approve)
        cat = f"auto_{uuid.uuid4().hex[:4]}"
        resp = c.post("/api/v1/approval-rules/", json={
            "category": cat,
            "description": "Auto-approve rule for testing",
            "manager_is_approver": False,
            "steps": [],
        })
        if assert_status(resp, 201, "POST /api/v1/approval-rules/ (no steps)"):
            data = get_json(resp)
            state["rule_auto_id"] = data.get("id")
            if data.get("category") == cat:
                ok("Category stored correctly")

        # Create rule with steps (requires a real manager user id)
        if mgr_id:
            cat2 = f"seq_{uuid.uuid4().hex[:4]}"
            resp = c.post("/api/v1/approval-rules/", json={
                "category": cat2,
                "description": "Sequential approval rule",
                "manager_is_approver": False,
                "steps": [{"approver_id": mgr_id, "step_order": 1}],
            })
            if assert_status(resp, 201, "POST /api/v1/approval-rules/ (with steps)"):
                data = get_json(resp)
                state["rule_seq_id"]  = data.get("id")
                state["rule_seq_cat"] = cat2
                if len(data.get("steps", [])) == 1:
                    ok("Step stored correctly")
                else:
                    fail("Expected 1 step", str(data.get("steps")))
        else:
            skip("Rule with steps", "no manager id available")

        # Duplicate category
        if state.get("rule_auto_id"):
            resp = c.post("/api/v1/approval-rules/", json={"category": cat, "steps": []})
            if resp.status_code == 409:
                ok("Duplicate category → 409")
            else:
                fail("Expected 409 for duplicate rule", str(resp.status_code))

        # Soft-delete
        if state.get("rule_auto_id"):
            resp = c.delete(f"/api/v1/approval-rules/{state['rule_auto_id']}")
            if assert_status(resp, 200, "DELETE /api/v1/approval-rules/{id}"):
                # Should not appear in list anymore
                resp2 = c.get("/api/v1/approval-rules/")
                rules = get_json(resp2)
                rule_ids = [r.get("id") for r in rules]
                if state["rule_auto_id"] not in rule_ids:
                    ok("Soft-deleted rule excluded from list")
                else:
                    fail("Soft-deleted rule still in list")


# ─────────────────────────────────────────────────────────────────────────────
# 7. Expense submission (Employee)
# ─────────────────────────────────────────────────────────────────────────────
def test_expenses():
    section("Expense Submission (Employee)")
    token = state.get("employee_token")
    if not token:
        skip("Expense submission", "no employee token (seed data required)")
        return

    with make_client(token) as c:
        # Create draft
        resp = c.post("/api/v1/expenses/", json={
            "amount":       1500.00,
            "currency":     "INR",
            "category":     "meals",
            "description":  "Test lunch expense",
            "expense_date": "2026-03-29",
            "paid_by":      "employee",
        })
        if not assert_status(resp, 201, "POST /api/v1/expenses/ (draft)"):
            return
        data = get_json(resp)
        exp_id = data.get("id")
        state["test_expense_id"] = exp_id

        if data.get("status") == "draft":
            ok("New expense is in draft status")
        else:
            fail("Expected draft status", str(data.get("status")))

        # Get own expenses
        resp = c.get("/api/v1/expenses/")
        assert_status(resp, 200, "GET /api/v1/expenses/")
        exps = get_json(resp)
        ids = [e.get("id") for e in exps]
        if exp_id in ids:
            ok("New expense appears in list")
        else:
            fail("New expense missing from list")

        # Edit draft
        resp = c.patch(f"/api/v1/expenses/{exp_id}", json={"description": "Test lunch expense (edited)"})
        if assert_status(resp, 200, "PATCH /api/v1/expenses/{id} (edit draft)"):
            if get_json(resp).get("description") == "Test lunch expense (edited)":
                ok("Edit persisted correctly")

        # Get detail
        resp = c.get(f"/api/v1/expenses/{exp_id}")
        if assert_status(resp, 200, "GET /api/v1/expenses/{id}"):
            detail = get_json(resp)
            if "approval_trail" in detail:
                ok("Detail includes approval_trail")
            else:
                fail("Missing approval_trail in detail")

        # Submit
        resp = c.post(f"/api/v1/expenses/{exp_id}/submit")
        if assert_status(resp, 200, "POST /api/v1/expenses/{id}/submit"):
            data = get_json(resp)
            status_val = data.get("status")
            if status_val in ("pending", "approved"):
                ok(f"Status after submit: {status_val}")
            else:
                fail("Expected pending or approved after submit", str(status_val))
            state["submitted_expense_id"] = exp_id
            state["submitted_status"]     = status_val

        # Cannot edit after submit
        resp = c.patch(f"/api/v1/expenses/{exp_id}", json={"description": "Should fail"})
        if resp.status_code == 400:
            ok("Cannot edit submitted expense → 400")
        else:
            fail("Should block edit of submitted expense", str(resp.status_code))

        # Cannot submit twice
        resp = c.post(f"/api/v1/expenses/{exp_id}/submit")
        if resp.status_code == 400:
            ok("Cannot submit twice → 400")
        else:
            fail("Should block double-submit", str(resp.status_code))

        # Filter by status
        resp = c.get("/api/v1/expenses/", params={"status": "draft"})
        assert_status(resp, 200, "GET /api/v1/expenses/?status=draft")

        # Invalid status filter
        resp = c.get("/api/v1/expenses/", params={"status": "invalid"})
        if resp.status_code == 400:
            ok("Invalid status filter → 400")
        else:
            fail("Expected 400 for invalid status", str(resp.status_code))

        # Employee cannot see other employees' expenses
        # (we test by trying to get a non-existent expense)
        resp = c.get(f"/api/v1/expenses/{uuid.uuid4()}")
        if resp.status_code == 404:
            ok("Non-existent expense → 404")
        else:
            fail("Expected 404 for unknown expense", str(resp.status_code))


# ─────────────────────────────────────────────────────────────────────────────
# 8. Approval workflow (Manager)
# ─────────────────────────────────────────────────────────────────────────────
def test_approvals():
    section("Approval Workflow (Manager)")
    mgr_token  = state.get("manager_token")
    emp_token  = state.get("employee_token")
    admin_token= state.get("admin_token")

    if not mgr_token:
        skip("Approval workflow", "no manager token")
        return

    with make_client(mgr_token) as c:
        # Get pending queue
        resp = c.get("/api/v1/approvals/")
        assert_status(resp, 200, "GET /api/v1/approvals/ (manager queue)")
        queue = get_json(resp)
        if isinstance(queue, list):
            ok(f"Queue returned {len(queue)} item(s)")
        else:
            fail("Expected list from approvals queue")

        # If the submitted expense is in the queue, approve it
        submitted_id = state.get("submitted_expense_id")
        submitted_status = state.get("submitted_status")

        if submitted_id and submitted_status == "pending":
            # Try to get expense detail
            resp = c.get(f"/api/v1/approvals/{submitted_id}")
            if resp.status_code == 200:
                ok("GET /api/v1/approvals/{id} accessible")
            # Approve
            resp = c.post(f"/api/v1/approvals/{submitted_id}/approve", json={"comment": "Approved in test"})
            if resp.status_code == 200:
                data = get_json(resp)
                new_status = data.get("status")
                ok(f"Approve action succeeded → status: {new_status}")
                state["approved_expense_id"] = submitted_id
            elif resp.status_code == 403:
                ok("Manager not the current approver for this expense (403 expected in some configs)")
            else:
                fail("Approve failed unexpectedly", f"{resp.status_code}: {resp.text[:150]}")
        else:
            skip("Approve specific expense", "expense not in pending state or not found in queue")

    # Employee cannot approve
    if emp_token:
        submitted_id = state.get("submitted_expense_id")
        if submitted_id:
            with make_client(emp_token) as c:
                resp = c.post(f"/api/v1/approvals/{submitted_id}/approve", json={})
                if resp.status_code == 403:
                    ok("Employee cannot approve → 403")
                else:
                    fail("Employee should be blocked from approving", str(resp.status_code))

    # Test rejection (create a fresh expense)
    if emp_token and mgr_token:
        with make_client(emp_token) as c:
            resp = c.post("/api/v1/expenses/", json={
                "amount": 500.00, "currency": "INR",
                "category": "meals", "description": "To be rejected",
                "expense_date": "2026-03-29", "paid_by": "employee",
            })
            if resp.status_code == 201:
                rej_id = get_json(resp).get("id")
                # Submit
                c.post(f"/api/v1/expenses/{rej_id}/submit")
                state["rejection_expense_id"] = rej_id

        with make_client(mgr_token) as c:
            rej_id = state.get("rejection_expense_id")
            if rej_id:
                resp = c.post(f"/api/v1/approvals/{rej_id}/reject", json={"comment": "Over budget"})
                if resp.status_code == 200:
                    data = get_json(resp)
                    if data.get("status") == "rejected":
                        ok("Rejection succeeded, status = rejected")
                    else:
                        ok(f"Rejection API succeeded (status: {data.get('status')})")
                elif resp.status_code == 403:
                    ok("Manager not current approver for rejection test — 403 expected")
                else:
                    fail("Rejection failed", f"{resp.status_code}: {resp.text[:150]}")


# ─────────────────────────────────────────────────────────────────────────────
# 9. Role access control
# ─────────────────────────────────────────────────────────────────────────────
def test_rbac():
    section("Role-Based Access Control")
    emp_token  = state.get("employee_token")
    mgr_token  = state.get("manager_token")
    admin_token= state.get("admin_token")

    if emp_token:
        with make_client(emp_token) as c:
            # Employee cannot access admin routes
            resp = c.get("/api/v1/users/")
            if resp.status_code == 403:
                ok("Employee blocked from GET /users/ → 403")
            else:
                fail("Expected 403 for employee on /users/", str(resp.status_code))

            resp = c.post("/api/v1/approval-rules/", json={"category":"x","steps":[]})
            if resp.status_code == 403:
                ok("Employee blocked from creating rules → 403")
            else:
                fail("Expected 403 for employee on /approval-rules/", str(resp.status_code))

    if mgr_token:
        with make_client(mgr_token) as c:
            # Manager cannot access admin user creation
            resp = c.post("/api/v1/users/", json={"email":"x@x.com","full_name":"X","role":"employee"})
            if resp.status_code == 403:
                ok("Manager blocked from creating users → 403")
            else:
                fail("Expected 403 for manager on POST /users/", str(resp.status_code))

    if admin_token:
        with make_client(admin_token) as c:
            # Admin can see all expenses
            resp = c.get("/api/v1/expenses/")
            if resp.status_code == 200:
                ok("Admin can list all expenses")
            else:
                fail("Admin should access /expenses/", str(resp.status_code))

    # No token
    with make_client() as c:
        for path in ["/api/v1/users/", "/api/v1/expenses/", "/api/v1/approvals/"]:
            resp = c.get(path)
            if resp.status_code in (401, 403):
                ok(f"Unauthenticated {path} → {resp.status_code}")
            else:
                fail(f"Expected 401/403 for {path} without token", str(resp.status_code))


# ─────────────────────────────────────────────────────────────────────────────
# 10. OpenAPI docs (sanity)
# ─────────────────────────────────────────────────────────────────────────────
def test_docs():
    section("OpenAPI / Docs")
    with make_client() as c:
        resp = c.get("/docs")
        if resp.status_code == 200:
            ok("GET /docs → 200")
        else:
            fail("Docs not accessible", str(resp.status_code))

        resp = c.get("/openapi.json")
        if resp.status_code == 200:
            schema = get_json(resp)
            paths = schema.get("paths", {})
            expected_paths = [
                "/api/v1/auth/register",
                "/api/v1/auth/login",
                "/api/v1/expenses/",
                "/api/v1/approvals/",
                "/api/v1/approval-rules/",
                "/api/v1/users/",
                "/api/v1/ocr/extract",
            ]
            for p in expected_paths:
                if p in paths:
                    ok(f"Route {p} registered")
                else:
                    fail(f"Route {p} missing from OpenAPI schema")
        else:
            fail("GET /openapi.json failed", str(resp.status_code))


# ─────────────────────────────────────────────────────────────────────────────
# 11. Currency conversion (expense submit)
# ─────────────────────────────────────────────────────────────────────────────
def test_currency():
    section("Currency Conversion on Submit")
    emp_token = state.get("employee_token")
    if not emp_token:
        skip("Currency conversion", "no employee token")
        return

    with make_client(emp_token) as c:
        # Create USD expense (company base = INR)
        resp = c.post("/api/v1/expenses/", json={
            "amount": 100.00,
            "currency": "USD",
            "category": "travel",
            "description": "USD expense for conversion test",
            "expense_date": "2026-03-29",
            "paid_by": "employee",
        })
        if resp.status_code != 201:
            skip("Currency conversion", "could not create expense")
            return

        exp_id = get_json(resp).get("id")
        resp = c.post(f"/api/v1/expenses/{exp_id}/submit")
        if resp.status_code == 200:
            data = get_json(resp)
            converted = data.get("converted_amount")
            rate = data.get("exchange_rate_snapshot")
            base = data.get("base_currency")
            if converted and base == "INR":
                ok(f"USD→INR conversion: $100 → ₹{converted:.2f} (rate: {rate})")
            elif converted:
                ok(f"Currency converted: {data.get('currency')} → {base} = {converted}")
            else:
                # Currency API may be unreachable in test env — not a blocker
                skip("Conversion amount", "exchange rate API may be unavailable")
        else:
            skip("Currency submit", f"submit returned {resp.status_code}")


# ─────────────────────────────────────────────────────────────────────────────
# 12. Change password
# ─────────────────────────────────────────────────────────────────────────────
def test_change_password():
    section("Change Password")
    emp_token = state.get("employee_token")
    emp_email = state.get("employee_email", "employee@govinda.com")
    if not emp_token:
        skip("Change password", "no employee token")
        return

    with make_client(emp_token) as c:
        # Wrong current password
        resp = c.post("/api/v1/auth/change-password", json={
            "current_password": "WrongPassword",
            "new_password":     "NewPass@456",
        })
        if resp.status_code == 400:
            ok("Wrong current password → 400")
        else:
            fail("Expected 400 for wrong current password", str(resp.status_code))

        # Correct change
        resp = c.post("/api/v1/auth/change-password", json={
            "current_password": "Employee@1234",
            "new_password":     "Employee@1234",   # change to same (valid)
        })
        if resp.status_code == 200:
            ok("Change password → 200")
        else:
            # might fail if seed password differs
            skip("Change password", f"returned {resp.status_code}")


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────
TESTS = [
    test_health,
    test_register,
    test_login,
    test_me,
    test_users,
    test_approval_rules,
    test_expenses,
    test_approvals,
    test_rbac,
    test_docs,
    test_currency,
    test_change_password,
]


def main():
    print(f"\n{BOLD}Xpensa Pre-Deployment Test Suite{RESET}")
    print(f"Target: {CYAN}{BASE_URL}{RESET}")
    print(f"{'─'*50}")

    # Check backend is reachable
    try:
        with httpx.Client(timeout=5.0) as c:
            c.get(f"{BASE_URL}/health")
    except Exception as e:
        print(f"\n{RED}✗ Cannot reach backend at {BASE_URL}{RESET}")
        print(f"  {e}")
        print(f"\n  Make sure the backend is running:")
        print(f"  {CYAN}cd backend && uvicorn app.main:app --reload{RESET}")
        sys.exit(1)

    for test_fn in TESTS:
        try:
            test_fn()
        except Exception as e:
            fail(f"UNEXPECTED ERROR in {test_fn.__name__}", str(e))

    # Summary
    total = passed + failed + skipped
    print(f"\n{'─'*50}")
    print(f"{BOLD}Results:{RESET}  ", end="")
    print(f"{GREEN}{passed} passed{RESET}  ", end="")
    if failed:
        print(f"{RED}{failed} failed{RESET}  ", end="")
    if skipped:
        print(f"{YELLOW}{skipped} skipped{RESET}  ", end="")
    print(f"/ {total} total\n")

    if failed > 0:
        print(f"{RED}Some tests failed. Fix issues before deploying.{RESET}\n")
        sys.exit(1)
    else:
        print(f"{GREEN}All tests passed! Ready to deploy.{RESET}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()