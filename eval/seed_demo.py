#!/usr/bin/env python3
"""Seed local demo users and the twelve-PDF catalog with mixed ACLs.

Not invoked by default CI: needs a running stack and FastEmbed cache.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"
if BACKEND_DIR.is_dir():
    sys.path.insert(0, str(BACKEND_DIR))
elif Path("/app/app").is_dir():
    sys.path.insert(0, "/app")
sys.path.insert(0, str(EVAL_DIR))

from corpus import (
    DEMO_ACCOUNTS,
    DEMO_ADMIN_EMAIL,
    DEMO_ADMIN_PASSWORD,
    DEMO_EMPLOYEE_EMAIL,
    DEMO_EMPLOYEE_PASSWORD,
    DEMO_HR_EMAIL,
    DEMO_HR_PASSWORD,
    seed_demo,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

UI = os.environ.get("FRONTEND_URL", "http://localhost:3001").rstrip("/")

WALKTHROUGH = f"""
Demo is ready. UI: {UI}

Demo credentials (public in this demo; do not reuse these passwords elsewhere):
  {DEMO_EMPLOYEE_EMAIL}   {DEMO_EMPLOYEE_PASSWORD}   role=employee  departments=[]
  {DEMO_HR_EMAIL}         {DEMO_HR_PASSWORD}         role=employee  departments=['hr']
  {DEMO_ADMIN_EMAIL}      {DEMO_ADMIN_PASSWORD}      role=admin     (KB upload)

Documents (same org):
  Employee-Handbook.pdf         access_roles=['all']       everyone in this org
  Leave-Policy.pdf              access_roles=['all']
  Expense-Policy.pdf            access_roles=['all']
  Engineering-Onboarding.pdf    access_roles=['all']
  HR-Compensation.pdf           access_roles=['hr']        HR department only
  Finance-Q4-Memo.pdf           access_roles=['finance']   finance department only
  Security-Runbook.pdf          access_roles=['all']       longer all-access runbook
  Recruiting-FAQ.pdf            access_roles=['hr']        short HR-only FAQ
  Travel-Policy.pdf             access_roles=['all']       travel cap + receipts
  IT-Access-Checklist.pdf       access_roles=['all']       onboarding checklist
  Operations-Handbook.pdf       access_roles=['all']       long operations manual
  People-Compendium.pdf         access_roles=['hr']        long HR-only compendium

Walkthrough:
  1. Open {UI} → «Войти как сотрудник» ({DEMO_EMPLOYEE_EMAIL})
  2. Ask: What are the core working hours at Docwise?
     → handbook page 1 + PDF highlight on the citation
  3. Ask: What is the individual contributor L3 salary band in USD?
     → refuse; SQL ACL drops the HR chunk before the LLM
  4. Log out → «Войти как HR» ({DEMO_HR_EMAIL})
  5. Ask the salary question again
     → 72000 to 88000 USD from HR-Compensation.pdf
  6. Neither account sees Finance-Q4-Memo.pdf in the list or in chat
  7. Employee can still open Security-Runbook.pdf and Travel-Policy.pdf
  8. Employee can open IT-Access-Checklist.pdf, but not Recruiting-FAQ.pdf
  9. Employee can open Operations-Handbook.pdf, but not People-Compendium.pdf
  10. HR sees both long docs; the People-Compendium stays hidden from employee

The three demo emails keep membership only in org Demo (password login would otherwise pick an older org).
"""


def main() -> int:
    result = seed_demo()
    print(WALKTHROUGH)
    print("Seeded users:")
    for account in DEMO_ACCOUNTS:
        print(f"  {account.email}  role={account.role}  departments={list(account.departments)}")
    print("Seeded documents:")
    for doc in result["documents"]:
        print(
            f"  {doc['slug']}  id={doc['id']}  roles={doc['access_roles']}  "
            f"pages={doc['pages']}  chunks={doc['chunks']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
