#!/usr/bin/env python3
"""Seed local demo users (employee vs HR) and two PDFs with different ACLs.

Not invoked by default CI: needs a running stack and FastEmbed cache.
"""

from __future__ import annotations

import logging
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

UI = "http://localhost:3001"

WALKTHROUGH = f"""
Demo is ready. UI: {UI}

Users (local only — do not use these passwords outside Compose):
  {DEMO_EMPLOYEE_EMAIL}   {DEMO_EMPLOYEE_PASSWORD}   role=employee  departments=[]
  {DEMO_HR_EMAIL}         {DEMO_HR_PASSWORD}         role=employee  departments=['hr']
  {DEMO_ADMIN_EMAIL}      {DEMO_ADMIN_PASSWORD}      role=admin     (KB upload)

Documents:
  Employee-Handbook.pdf    access_roles=['all']   visible to everyone in this org
  HR-Compensation.pdf      access_roles=['hr']    HR department only

Walkthrough:
  1. Open {UI} and log in as {DEMO_EMPLOYEE_EMAIL}
  2. Ask: What are the core working hours at Docwise?
     → answer from the handbook (page 1) with a citation
  3. Ask: What is the individual contributor L3 salary band in USD?
     → refuse; SQL ACL drops the HR chunk before the LLM
  4. Log out, log in as {DEMO_HR_EMAIL}
  5. Ask the salary question again
     → 72000 to 88000 USD from HR-Compensation.pdf
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
