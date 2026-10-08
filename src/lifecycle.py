#!/usr/bin/env python3
# Copyright (c) 2026 Oluwatobiloba Benjamin Ogungbangbe. All rights reserved.
# Owner: Oluwatobiloba Benjamin Ogungbangbe. Not for sale. See LICENSE.
# Permission is valid only if the owner confirms it himself.
"""Joiner, mover, and leaver workflow.

What this file is
-----------------
This is the program you run. It reads an HR spreadsheet (CSV), checks each
person, updates a local staff directory, and writes an audit log.

Demo mode is the default. The directory is data/directory.json on this PC.
That file stands in for Entra ID so the same folder runs anywhere.
It never reads a tenant id, password, certificate, or client secret.

The other script, Invoke-UserLifecycle.ps1, does the same job in PowerShell.
Read NOTES.md if you want the full walkthrough before the code.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Folder that contains samples/, rules/, and data/. The script lives in src/.
ROOT = Path(__file__).resolve().parent.parent

# A new starter row is rejected if any of these are blank.
REQUIRED_JOINER = [
    "employee_id",
    "first_name",
    "last_name",
    "department",
    "job_title",
    "location",
    "role",
    "manager_email",
    "start_date",
]
# Used only to catch a manager address that is not an email. Not a full validator.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def utc_now() -> str:
    """Time stamp for the audit log. UTC so two machines agree on the order."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path) -> dict:
    """Read a JSON file. Used for config, rules, and the saved directory."""
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, payload: dict) -> None:
    """Write JSON. Creates the folder if this is the first run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def read_csv(path: Path) -> list[dict]:
    """Read the HR file. The first row must be the column names.

    Excel on a UK PC may save a UTF-8 mark, spaces in the header, or
    semicolons instead of commas. Those are accepted. Empty rows are skipped.
    """
    text = path.read_text(encoding="utf-8-sig")
    sample = text[:1000]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    rows = []
    for row in csv.DictReader(text.splitlines(), delimiter=delimiter):
        clean = {str(key).strip(): str(value).strip() if value else "" for key, value in row.items() if key}
        if any(clean.values()):
            rows.append(clean)
    return rows


def canonical(name: str, choices: dict) -> str:
    """Match a rules name without caring about capital letters or extra spaces."""
    wanted = name.strip().lower()
    for key in choices:
        if key.lower() == wanted:
            return key
    return name.strip()


def normal_date(value: str) -> str:
    """Turn a UK or Excel date into YYYY-MM-DD. Leave anything else unchanged."""
    text = value.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return text


def slug(first: str, last: str) -> str:
    """Build the mailbox name. 'Ada Okoye' becomes 'ada.okoye'."""
    raw = f"{first}.{last}".lower()
    return re.sub(r"[^a-z0-9.]", "", raw)


class Lifecycle:
    """Holds the rules, the directory, and the log for one run.

    config: tenant name and email domain. Fake values in the sample.
    rules: which department, location, and role get which groups.
    directory: the staff list. This is the stand-in for Entra ID.
    events: what happened to each person on this run. Written at the end.
    """

    def __init__(self, config: dict, rules: dict, directory_path: Path, log_dir: Path, report_dir: Path, strict_manager: bool = False):
        self.config = config
        self.rules = rules
        self.directory_path = directory_path
        self.log_dir = log_dir
        self.report_dir = report_dir
        self.strict_manager = strict_manager
        self.directory = self._load_directory()
        self.events: list[dict] = []

    def _load_directory(self) -> dict:
        """Open the staff file, or start an empty one on the first run."""
        if self.directory_path.exists():
            return load_json(self.directory_path)
        return {"tenant": self.config["tenant"], "users": []}

    def save(self) -> None:
        """Write the staff file. Skipped when the run is a dry-run."""
        self.directory["tenant"] = self.config["tenant"]
        save_json(self.directory_path, self.directory)

    def log(self, action: str, status: str, detail: dict) -> None:
        """Remember one result. action is joiner, mover, or leaver."""
        self.events.append({"time": utc_now(), "action": action, "status": status, **detail})

    def find(self, employee_id: str | None = None, email: str | None = None) -> dict | None:
        """Find a person by HR number or email. Used by mover and leaver."""
        for user in self.directory["users"]:
            if employee_id and user["employee_id"] == employee_id:
                return user
            if email and user["email"].lower() == email.lower():
                return user
        return None

    def groups_for(self, department: str, location: str, role: str) -> list[str]:
        """Build the group list from the rules file, not from hardcoded names.

        A Finance manager in the corporate office gets finance groups, the
        site group, and the managers group. Sorted so the log is stable.
        """
        groups = []
        groups.extend(self.rules["departments"][department]["groups"])
        groups.extend(self.rules["locations"].get(location, {}).get("groups", []))
        groups.extend(self.rules["roles"].get(role, {}).get("groups", []))
        return sorted(set(groups))

    def validate_joiner(self, row: dict) -> list[str]:
        """Return a list of problems. An empty list means the row is safe to create.

        Reject unknown departments so a typo does not create an account with
        no access and no error.
        """
        errors = []
        for field in REQUIRED_JOINER:
            if field not in row or not str(row.get(field, "")).strip():
                if field == "manager_email" and not self.config.get("require_manager", True):
                    continue
                errors.append(f"missing {field}")
        department = canonical(row.get("department", ""), self.rules["departments"])
        row["department"] = department
        if department and department not in self.rules["departments"]:
            errors.append(f"unknown department '{department}'")
        location = canonical(row.get("location", ""), self.rules["locations"])
        row["location"] = location
        if location and location not in self.rules["locations"]:
            errors.append(f"unknown location '{location}'")
        role = canonical(row.get("role", ""), self.rules["roles"])
        row["role"] = role
        if role and role not in self.rules["roles"]:
            errors.append(f"unknown role '{role}'")
        if row.get("start_date"):
            row["start_date"] = normal_date(row["start_date"])
        manager = row.get("manager_email", "")
        if manager and not EMAIL_RE.match(manager):
            errors.append("manager_email is not a valid address")
        if self.strict_manager and manager and not self.find(email=manager):
            errors.append("manager is not in the directory")
        existing = self.find(employee_id=row.get("employee_id"))
        email = ""
        if row.get("first_name") and row.get("last_name"):
            email = f"{slug(row['first_name'], row['last_name'])}@{self.config['default_domain']}"
            for user in self.directory["users"]:
                if user["email"].lower() == email.lower() and user["employee_id"] != row.get("employee_id"):
                    errors.append(f"email already exists: {email}")
                    break
        if existing and email and existing["email"].lower() == email.lower():
            return ["already provisioned, no change"]
        if existing:
            errors.append("employee_id already exists")
        return errors

    def join(self, row: dict) -> dict:
        """Create one account. Does nothing permanent if the row is invalid."""
        errors = self.validate_joiner(row)
        if errors == ["already provisioned, no change"]:
            existing = self.find(employee_id=row.get("employee_id"))
            result = {
                "employee_id": row.get("employee_id", ""),
                "email": existing["email"] if existing else "",
                "status": "unchanged",
                "row": row.get("_row"),
                "errors": ["already provisioned, no change"],
            }
            self.log("joiner", "unchanged", result)
            return result
        if errors:
            result = {"employee_id": row.get("employee_id", ""), "status": "rejected", "row": row.get("_row"), "errors": errors}
            self.log("joiner", "rejected", result)
            return result
        email = f"{slug(row['first_name'], row['last_name'])}@{self.config['default_domain']}"
        groups = self.groups_for(row["department"], row["location"], row["role"])
        licence = self.rules["departments"][row["department"]]["licence"]
        user = {
            "employee_id": row["employee_id"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "email": email,
            "upn": f"{slug(row['first_name'], row['last_name'])}@{self.config['tenant']}",
            "department": row["department"],
            "job_title": row["job_title"],
            "location": row["location"],
            "role": row["role"],
            "manager_email": row["manager_email"],
            "start_date": row["start_date"],
            "enabled": True,
            "sessions_revoked": False,
            "groups": groups,
            "licence": licence,
            "created_at": utc_now(),
        }
        self.directory["users"].append(user)
        result = {
            "employee_id": user["employee_id"],
            "email": email,
            "status": "created",
            "row": row.get("_row"),
            "groups": groups,
            "licence": licence,
        }
        self.log("joiner", "created", result)
        return result

    def leave(self, row: dict) -> dict:
        """Disable one account. The account stays in the directory as a record.

        Order matches a real leaver: block sign-in, revoke sessions, remove
        groups, record the licence, then log it. Missing people are reported,
        not created.
        """
        user = self.find(employee_id=row.get("employee_id"), email=row.get("email"))
        if not user:
            result = {"employee_id": row.get("employee_id", ""), "email": row.get("email", ""), "status": "not_found"}
            self.log("leaver", "not_found", result)
            return result
        removed = list(user["groups"])
        licence = user.get("licence")
        user["enabled"] = False
        user["sessions_revoked"] = True
        user["groups"] = []
        user["licence_at_leave"] = licence
        user["licence"] = None
        user["left_at"] = utc_now()
        user["leave_reason"] = row.get("reason", "")
        result = {
            "employee_id": user["employee_id"],
            "email": user["email"],
            "status": "disabled",
            "sign_in": "blocked",
            "sessions": "revoked",
            "groups_removed": removed,
            "licence_recorded": licence,
        }
        self.log("leaver", "disabled", result)
        return result

    def move(self, row: dict) -> dict:
        """Change department, location, or role and rebuild the group list.

        Groups that only belonged to the old department are removed.
        Groups for the new department are added. Shared groups stay.
        A disabled account is not moved.
        """
        user = self.find(employee_id=row.get("employee_id"), email=row.get("email"))
        if not user:
            result = {"employee_id": row.get("employee_id", ""), "status": "not_found"}
            self.log("mover", "not_found", result)
            return result
        if not user.get("enabled", False):
            result = {"employee_id": user["employee_id"], "status": "rejected", "errors": ["account is disabled"]}
            self.log("mover", "rejected", result)
            return result
        new_department = canonical(row.get("new_department") or user["department"], self.rules["departments"])
        new_location = canonical(row.get("new_location") or user["location"], self.rules["locations"])
        new_role = canonical(row.get("new_role") or user["role"], self.rules["roles"])
        errors = []
        if new_department not in self.rules["departments"]:
            errors.append(f"unknown department '{new_department}'")
        if new_location not in self.rules["locations"]:
            errors.append(f"unknown location '{new_location}'")
        if new_role not in self.rules["roles"]:
            errors.append(f"unknown role '{new_role}'")
        if errors:
            result = {"employee_id": user["employee_id"], "status": "rejected", "errors": errors}
            self.log("mover", "rejected", result)
            return result
        old_groups = list(user["groups"])
        new_groups = self.groups_for(new_department, new_location, new_role)
        user["department"] = new_department
        user["location"] = new_location
        user["role"] = new_role
        if row.get("new_job_title"):
            user["job_title"] = row["new_job_title"]
        if row.get("new_manager_email"):
            user["manager_email"] = row["new_manager_email"]
        user["groups"] = new_groups
        user["licence"] = self.rules["departments"][new_department]["licence"]
        user["moved_at"] = utc_now()
        result = {
            "employee_id": user["employee_id"],
            "email": user["email"],
            "status": "moved",
            "groups_removed": sorted(set(old_groups) - set(new_groups)),
            "groups_added": sorted(set(new_groups) - set(old_groups)),
            "department": new_department,
            "manager_email": user["manager_email"],
        }
        self.log("mover", "moved", result)
        return result

    def write_reports(self, action: str) -> tuple[Path, Path]:
        """Write the JSON audit log and the Markdown ticket note."""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.log_dir / f"{action}-{stamp}.json"
        report_path = self.report_dir / f"{action}-{stamp}.md"
        save_json(log_path, {"tenant": self.config["tenant"], "action": action, "events": self.events})
        lines = [
            f"# {action.title()} report",
            "",
            "Demo only. This did not change a real tenant.",
            "",
            f"Tenant: `{self.config['tenant']}`",
            f"Generated: {utc_now()}",
            "",
            "| Status | Employee | Detail |",
            "| --- | --- | --- |",
        ]
        for event in self.events:
            detail = self.event_detail(event)
            lines.append(f"| {event['status']} | {event.get('employee_id', '')} | {detail} |")
        lines.append("")
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return log_path, report_path

    @staticmethod
    def event_detail(event: dict) -> str:
        """One readable cell for the report. Movers include groups off and on."""
        if event.get("errors"):
            return ", ".join(event["errors"])
        removed = event.get("groups_removed")
        added = event.get("groups_added")
        if removed is not None or added is not None:
            off = ", ".join(removed or []) or "none"
            on = ", ".join(added or []) or "none"
            return f"{event.get('email', '')}; removed: {off}; added: {on}"
        return event.get("email") or event.get("status") or ""


def parse_args() -> argparse.Namespace:
    """Command line. action is joiner, mover, or leaver. input is the CSV."""
    parser = argparse.ArgumentParser(
        description="Demo only. Joiner, mover, and leaver against a local directory. Does not connect to a tenant.",
        epilog="Start with the installer, then: python3 src/lifecycle.py menu",
    )
    parser.add_argument("action", choices=["menu", "demo", "joiner", "mover", "leaver", "list", "reset"], help="menu is the easy start; demo runs the samples; list shows the staff file; reset deletes only that file")
    parser.add_argument("--input", help="CSV file for joiner, mover, or leaver. Not used by demo, list, or reset.")
    parser.add_argument("--config", default=str(ROOT / "config.example.json"), help="Settings file. The sample uses a fake tenant.")
    parser.add_argument("--rules", default=str(ROOT / "rules" / "department-rules.json"), help="Department, location, and role group map.")
    parser.add_argument("--directory", default=str(ROOT / "data" / "directory.json"), help="Local staff file. Created on first run. Not a real directory.")
    parser.add_argument("--dry-run", action="store_true", help="Check the CSV and write the report, but do not change the staff file.")
    parser.add_argument("--strict-manager", action="store_true", help="Reject a joiner whose manager email is not already in the directory. Off for the demo.")
    return parser.parse_args()


def print_result(item: dict) -> None:
    """Print one person. Rejections include the row and the reason."""
    reason = ""
    if item.get("errors"):
        reason = " — " + ", ".join(item["errors"])
    row = f"row {item['row']}: " if item.get("row") else ""
    print(f"  {item['status']:10} {row}{item.get('employee_id', '')} {item.get('email', '')}{reason}")


def run_action(engine: Lifecycle, action: str, rows: list[dict]) -> list[dict]:
    results = []
    for number, row in enumerate(rows, start=2):
        row = dict(row)
        row["_row"] = number
        if action == "joiner":
            results.append(engine.join(row))
        elif action == "leaver":
            results.append(engine.leave(row))
        else:
            results.append(engine.move(row))
    return results


def write_demo_summary(report_dir: Path, tenant: str, steps: list[tuple[str, list[dict]]]) -> Path:
    """One ticket note for the whole demo."""
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / "demo-summary.md"
    lines = [
        "# Demo summary",
        "",
        "Demo only. This did not change a real tenant.",
        "",
        f"Tenant: `{tenant}`",
        f"Generated: {utc_now()}",
        "",
        "Owner: Oluwatobiloba Benjamin Ogungbangbe. Not for sale.",
        "",
        "| Step | Status | Employee | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for action, results in steps:
        for item in results:
            detail = Lifecycle.event_detail(item)
            lines.append(f"| {action} | {item['status']} | {item.get('employee_id', '')} | {detail} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def menu() -> int:
    """Numbered menu so the commands do not have to be remembered."""
    print("DEMO ONLY. No tenant is contacted.")
    print("Owner: Oluwatobiloba Benjamin Ogungbangbe. Not for sale. See LICENSE.")
    print("")
    print("1  Run the sample demo")
    print("2  Show the staff list")
    print("3  Open the ticket summary path")
    print("4  Reset the local staff file")
    print("5  Quit")
    choice = input("Choose 1-5: ").strip()
    script = str(Path(__file__).resolve())
    if choice == "1":
        return subprocess_call([sys.executable, script, "demo"])
    if choice == "2":
        return subprocess_call([sys.executable, script, "list"])
    if choice == "3":
        summary = ROOT / "reports" / "demo-summary.md"
        print(summary if summary.exists() else "No summary yet. Choose 1 first.")
        return 0
    if choice == "4":
        return subprocess_call([sys.executable, script, "reset"])
    print("Quit.")
    return 0


def subprocess_call(command: list[str]) -> int:
    import subprocess
    return subprocess.call(command)


def main() -> int:
    """Load files, process every row, save, print a one-line result per person."""
    args = parse_args()
    print("DEMO ONLY. No tenant is contacted. Results are written on this computer.")
    print("Owner: Oluwatobiloba Benjamin Ogungbangbe. Not for sale. See LICENSE.")
    config = load_json(Path(args.config))
    rules = load_json(Path(args.rules))
    directory = Path(args.directory)
    if args.action == "menu":
        return menu()
    if args.action == "reset":
        if directory.exists():
            directory.unlink()
            print(f"reset: removed {directory}")
        else:
            print("reset: no staff file to remove")
        return 0
    if args.action == "list":
        if not directory.exists():
            print("list: no staff file yet. Run demo or joiner first.")
            return 0
        data = load_json(directory)
        print(f"{'ID':6} {'Enabled':7} {'Department':16} Email")
        for user in data.get("users", []):
            enabled = "yes" if user.get("enabled") else "no"
            print(f"{user['employee_id']:6} {enabled:7} {user['department']:16} {user['email']}")
            print(f"       groups: {', '.join(user.get('groups') or []) or 'none'}")
        return 0
    if args.action in {"joiner", "mover", "leaver"} and not args.input:
        print("This action needs --input. Example: --input samples/joiners.csv")
        return 1
    engine = Lifecycle(config, rules, directory, ROOT / "logs", ROOT / "reports", strict_manager=args.strict_manager)
    if args.action == "demo":
        if directory.exists():
            directory.unlink()
        engine = Lifecycle(config, rules, directory, ROOT / "logs", ROOT / "reports", strict_manager=args.strict_manager)
        steps = [
            ("joiner", ROOT / "samples" / "joiners.csv"),
            ("mover", ROOT / "samples" / "movers.csv"),
            ("leaver", ROOT / "samples" / "leavers.csv"),
        ]
        exit_code = 0
        ran = []
        for action, path in steps:
            engine.events = []
            results = run_action(engine, action, read_csv(path))
            engine.save()
            _, report_path = engine.write_reports(action)
            ran.append((action, results))
            print(f"{action}: report {report_path}")
            for item in results:
                print_result(item)
            if not any(item["status"] in {"created", "disabled", "moved", "unchanged"} for item in results):
                exit_code = 1
        summary = write_demo_summary(ROOT / "reports", config["tenant"], ran)
        print(f"demo summary: {summary}")
        print("demo finished. Next: python3 src/lifecycle.py list")
        return exit_code
    results = run_action(engine, args.action, read_csv(Path(args.input)))
    if not args.dry_run:
        engine.save()
    log_path, report_path = engine.write_reports(args.action)
    created = sum(1 for item in results if item["status"] in {"created", "disabled", "moved"})
    unchanged = sum(1 for item in results if item["status"] == "unchanged")
    rejected = len(results) - created - unchanged
    print(f"{args.action}: {created} completed, {unchanged} already provisioned, {rejected} rejected or not found")
    print(f"audit log: {log_path}")
    print(f"report: {report_path}")
    print("Next: open the report. It is the ticket note for this run.")
    for item in results:
        print_result(item)
    return 0 if created else 1


if __name__ == "__main__":
    sys.exit(main())
