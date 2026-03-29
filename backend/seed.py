"""
seed.py — Populate the database with demo data for the Xpensa hackathon demo.

Usage (from backend/ directory):
    python seed.py

Creates:
  - Demo company: "Govinda Industries" (USD base currency)
  - Admin user:    admin@govinda.com / Admin@1234
  - Manager user:  manager@govinda.com / Manager@1234
  - Employee user: employee@govinda.com / Employee@1234
  - Approval rule for "travel" (2-step: manager → admin)
  - 4 sample expenses in various states: draft, pending, approved, rejected

Re-running this script will wipe existing demo data and reseed fresh.
"""
import sys
import os
from datetime import date, datetime, timezone, timedelta

# Allow running from backend/ directory
sys.path.insert(0, os.path.dirname(__file__))

from sqlmodel import Session, select, SQLModel
from app.core.database import engine
from app.core.security import hash_password
from app.models.company import Company
from app.models.user import User, UserRole
from app.models.approval_rule import ApprovalRule, ApprovalStep
from app.models.expense import Expense, ApprovalRecord, ExpenseStatus, ApprovalAction


def seed():
    print("🌱 Seeding demo data...")

    # Ensure tables exist
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # ── Wipe existing demo data ────────────────────────────────────────────
        for demo_name in ("Acme Corp", "Govinda Industries"):
            existing = session.exec(
                select(Company).where(Company.name == demo_name)
            ).first()
            if existing:
                print(f"  🗑️  Wiping existing data for '{demo_name}'...")
                # Delete in FK-safe order
                users_in_co = session.exec(
                    select(User).where(User.company_id == existing.id)
                ).all()
                user_ids = [u.id for u in users_in_co]

                expenses_in_co = session.exec(
                    select(Expense).where(Expense.company_id == existing.id)
                ).all()
                exp_ids = [e.id for e in expenses_in_co]

                if exp_ids:
                    records = session.exec(
                        select(ApprovalRecord).where(ApprovalRecord.expense_id.in_(exp_ids))
                    ).all()
                    for r in records:
                        session.delete(r)
                    for e in expenses_in_co:
                        session.delete(e)

                rules = session.exec(
                    select(ApprovalRule).where(ApprovalRule.company_id == existing.id)
                ).all()
                for rule in rules:
                    steps = session.exec(
                        select(ApprovalStep).where(ApprovalStep.rule_id == rule.id)
                    ).all()
                    for s in steps:
                        session.delete(s)
                    session.delete(rule)

                for u in users_in_co:
                    session.delete(u)
                session.delete(existing)
                session.flush()
                print(f"     Done.")

        # ── Company ────────────────────────────────────────────────────────────
        company = Company(
            name="Govinda Industries",
            country="India",
            base_currency="INR",
        )
        session.add(company)
        session.flush()
        print(f"  ✅ Company: {company.name} (id={company.id})")

        # ── Users ──────────────────────────────────────────────────────────────
        admin = User(
            email="admin@govinda.com",
            full_name="Govind Admin",
            hashed_password=hash_password("Admin@1234"),
            role=UserRole.admin,
            company_id=company.id,
            must_change_password=False,
        )
        manager = User(
            email="manager@govinda.com",
            full_name="Mohan Manager",
            hashed_password=hash_password("Manager@1234"),
            role=UserRole.manager,
            company_id=company.id,
            must_change_password=False,
        )
        employee = User(
            email="employee@govinda.com",
            full_name="Priya Employee",
            hashed_password=hash_password("Employee@1234"),
            role=UserRole.employee,
            company_id=company.id,
            must_change_password=False,
        )
        session.add_all([admin, manager, employee])
        session.flush()
        print(f"  ✅ Admin:    admin@govinda.com / Admin@1234")
        print(f"  ✅ Manager:  manager@govinda.com / Manager@1234")
        print(f"  ✅ Employee: employee@govinda.com / Employee@1234")

        # ── Approval Rule: Travel (2-step: manager → admin) ───────────────────
        rule = ApprovalRule(
            company_id=company.id,
            category="travel",
            description="All travel expenses require manager then admin approval at Govinda Industries",
            manager_is_approver=False,
            min_approval_percentage=None,
        )
        session.add(rule)
        session.flush()

        step1 = ApprovalStep(rule_id=rule.id, approver_id=manager.id, step_order=1)
        step2 = ApprovalStep(rule_id=rule.id, approver_id=admin.id, step_order=2)
        session.add_all([step1, step2])
        session.flush()
        print(f"  ✅ Approval rule: 'travel' (Step 1: manager → Step 2: admin)")

        # ── Approval Rule: Meals (auto-approve — no steps) ────────────────────
        meals_rule = ApprovalRule(
            company_id=company.id,
            category="meals",
            description="Meal expenses at Govinda Industries: manager approval only",
            manager_is_approver=True,
        )
        session.add(meals_rule)
        session.flush()
        print(f"  ✅ Approval rule: 'meals' (manager is approver)")

        # ── Sample Expenses ────────────────────────────────────────────────────
        today = date.today()

        # 1. Draft expense
        draft_exp = Expense(
            company_id=company.id,
            employee_id=employee.id,
            amount=18500.00,
            currency="INR",
            category="travel",
            description="Train ticket to Mumbai head office",
            expense_date=today - timedelta(days=1),
            paid_by="employee",
            status=ExpenseStatus.draft,
        )
        session.add(draft_exp)

        # 2. Approved expense (travel, went through full chain)
        approved_exp = Expense(
            company_id=company.id,
            employee_id=employee.id,
            amount=95000.00,
            currency="INR",
            converted_amount=95000.00,
            base_currency="INR",
            exchange_rate_snapshot=1.0,
            category="travel",
            description="Flight to Delhi HQ for quarterly review",
            expense_date=today - timedelta(days=15),
            paid_by="employee",
            status=ExpenseStatus.approved,
        )
        session.add(approved_exp)
        session.flush()

        # Approval records for approved expense
        ar1 = ApprovalRecord(
            expense_id=approved_exp.id,
            approver_id=manager.id,
            step_order=1,
            action=ApprovalAction.approve,
            comment="Verified — business-critical trip",
            acted_at=datetime.now(timezone.utc) - timedelta(days=14),
        )
        ar2 = ApprovalRecord(
            expense_id=approved_exp.id,
            approver_id=admin.id,
            step_order=2,
            action=ApprovalAction.approve,
            comment="Approved by finance",
            acted_at=datetime.now(timezone.utc) - timedelta(days=13),
        )
        session.add_all([ar1, ar2])

        # 3. Rejected expense
        rejected_exp = Expense(
            company_id=company.id,
            employee_id=employee.id,
            amount=12000.00,
            currency="INR",
            converted_amount=12000.00,
            base_currency="INR",
            exchange_rate_snapshot=1.0,
            category="meals",
            description="Team dinner at 5-star restaurant",
            expense_date=today - timedelta(days=7),
            paid_by="employee",
            status=ExpenseStatus.rejected,
        )
        session.add(rejected_exp)
        session.flush()

        ar_rejected = ApprovalRecord(
            expense_id=rejected_exp.id,
            approver_id=manager.id,
            step_order=0,
            action=ApprovalAction.reject,
            comment="Over budget limit for meals. Maximum allowed is ₹3,000 per employee.",
            acted_at=datetime.now(timezone.utc) - timedelta(days=6),
        )
        session.add(ar_rejected)

        # 4. Pending expense (waiting for manager)
        pending_exp = Expense(
            company_id=company.id,
            employee_id=employee.id,
            amount=4200.00,
            currency="INR",
            converted_amount=4200.00,
            base_currency="INR",
            exchange_rate_snapshot=1.0,
            category="travel",
            description="Cab rides for client site visits in Pune",
            expense_date=today - timedelta(days=2),
            paid_by="employee",
            status=ExpenseStatus.pending,
        )
        session.add(pending_exp)
        session.flush()

        ar_pending = ApprovalRecord(
            expense_id=pending_exp.id,
            approver_id=manager.id,
            step_order=1,
            action=None,  # Still waiting
        )
        session.add(ar_pending)

        session.commit()
        print(f"  ✅ 4 sample expenses: 1 draft, 1 approved, 1 rejected, 1 pending")
        print()
        print("🎉 Seed complete!")
        print()
        print("─" * 52)
        print("Demo credentials (Govinda Industries):")
        print("  Admin:    admin@govinda.com    / Admin@1234")
        print("  Manager:  manager@govinda.com  / Manager@1234")
        print("  Employee: employee@govinda.com / Employee@1234")
        print("─" * 52)


if __name__ == "__main__":
    seed()
