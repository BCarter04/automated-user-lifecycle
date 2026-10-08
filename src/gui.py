#!/usr/bin/env python3
# Copyright (c) 2026 Oluwatobiloba Benjamin Ogungbangbe. All rights reserved.
# Owner: Oluwatobiloba Benjamin Ogungbangbe. Not for sale. See LICENSE.
# Permission is valid only if the owner confirms it himself.
"""First-run window. Double-click Start-Here. No commands to type.

The page explains the demo and the live use on this PC. Live use reads a
CSV on this computer and writes the staff file, log, and ticket note here.
It does not contact a tenant.
"""

from __future__ import annotations

import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import lifecycle  # noqa: E402

PORT = 8765


def setup() -> str:
    """Create the local folders and the fake config. Nothing is downloaded."""
    for name in ("data", "logs", "reports", "inbox"):
        (ROOT / name).mkdir(parents=True, exist_ok=True)
    config = ROOT / "config.json"
    if not config.exists():
        config.write_text((ROOT / "config.example.json").read_text(encoding="utf-8"), encoding="utf-8")
        return "This PC is ready. Folders created. config.json uses the fake tenant name and is not uploaded."
    return "This PC is ready. Existing config.json was left unchanged."


def engine():
    config_path = ROOT / "config.json"
    if not config_path.exists():
        setup()
    config = lifecycle.load_json(config_path)
    rules = lifecycle.load_json(ROOT / "rules" / "department-rules.json")
    return lifecycle.Lifecycle(config, rules, ROOT / "data" / "directory.json", ROOT / "logs", ROOT / "reports"), config


REQUIRED = {
    "joiner": ["employee_id", "first_name", "last_name", "department", "job_title", "location", "role", "manager_email", "start_date"],
    "mover": ["employee_id", "email"],
    "leaver": ["employee_id", "email"],
}


def missing_columns(action: str, rows: list[dict]) -> list[str]:
    if not rows:
        return ["no data rows"]
    have = set(rows[0].keys())
    return [name for name in REQUIRED.get(action, []) if name not in have]


def preview_text(action: str, rows: list[dict]) -> str:
    missing = missing_columns(action, rows)
    lines = [f"Preview only. Nothing has been written. Action: {action}", f"Rows: {len(rows)}"]
    if missing:
        lines.append("Missing columns: " + ", ".join(missing))
        lines.append("Fix the file before you confirm. The staff list was not touched.")
    else:
        lines.append("Columns are present. First rows:")
    for row in rows[:3]:
        lines.append("  " + ", ".join(f"{key}={value}" for key, value in row.items() if value))
    if len(rows) > 3:
        lines.append(f"  ... {len(rows) - 3} more row(s)")
    return "\n".join(lines)


def run_rows(action: str, rows: list[dict], dry_run: bool = False, source_name: str = "pasted.csv") -> str:
    if action not in {"joiner", "mover", "leaver"}:
        return "Choose joiner, mover, or leaver."
    if not rows:
        return "No rows to process. Paste a CSV, choose a file, or give a path on this PC."
    missing = missing_columns(action, rows)
    if missing:
        return "Staff list not touched. Missing columns: " + ", ".join(missing)
    current, _config = engine()
    results = lifecycle.run_action(current, action, rows)
    stamp = lifecycle.utc_now().replace(":", "").replace("-", "")
    inbox = ROOT / "inbox" / f"{action}-{stamp}-{source_name}"
    save_rows(inbox, rows)
    if not dry_run:
        current.save()
    _, report = current.write_reports(action)
    lines = [
        "DRY RUN. Staff file was not changed." if dry_run else "LIVE ON THIS PC. No tenant was contacted.",
        f"File used: {inbox}",
        f"Ticket note: {report}",
        f"Staff file: {ROOT / 'data' / 'directory.json'}",
        "",
    ]
    for item in results:
        reason = ", ".join(item.get("errors") or [])
        extra = f" — {reason}" if reason else ""
        lines.append(f"{item['status']:10} {item.get('employee_id', '')} {item.get('email', '')}{extra}")
    return "\n".join(lines)


def save_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    import csv
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def find_person(query: str) -> str:
    query = query.strip()
    if not query:
        return "Type an employee id or an email."
    path = ROOT / "data" / "directory.json"
    if not path.exists():
        return "No staff file on this PC yet."
    data = lifecycle.load_json(path)
    for user in data.get("users", []):
        if query.lower() in {user.get("employee_id", "").lower(), user.get("email", "").lower()}:
            sign_in = "blocked" if not user.get("enabled") else "allowed"
            return "\n".join([
                f"Employee: {user.get('employee_id')} {user.get('first_name', '')} {user.get('last_name', '')}",
                f"Email: {user.get('email')}",
                f"Department: {user.get('department')}",
                f"Manager: {user.get('manager_email')}",
                f"Licence: {user.get('licence') or user.get('licence_at_leave') or 'none'}",
                f"Sign-in: {sign_in}",
                f"Groups: {', '.join(user.get('groups') or []) or 'none'}",
            ])
    return f"No person matches {query}."


def run_demo() -> str:
    setup()
    parts = []
    ran = []
    current, config = engine()
    if (ROOT / "data" / "directory.json").exists():
        (ROOT / "data" / "directory.json").unlink()
        current, config = engine()
    for action, path in (
        ("joiner", ROOT / "samples" / "joiners.csv"),
        ("mover", ROOT / "samples" / "movers.csv"),
        ("leaver", ROOT / "samples" / "leavers.csv"),
    ):
        current.events = []
        results = lifecycle.run_action(current, action, lifecycle.read_csv(path))
        current.save()
        current.write_reports(action)
        ran.append((action, results))
        parts.append(action)
        for item in results:
            reason = ", ".join(item.get("errors") or [])
            extra = f" — {reason}" if reason else ""
            parts.append(f"  {item['status']:10} {item.get('employee_id', '')} {item.get('email', '')}{extra}")
        parts.append("")
    summary = lifecycle.write_demo_summary(ROOT / "reports", config["tenant"], ran)
    parts.append(f"Ticket note: {summary}")
    return "DEMO ONLY. No tenant was contacted.\n\n" + "\n".join(parts)


def rows_from_request(fields: dict) -> tuple[str, list[dict], str]:
    action = (fields.get("action") or ["joiner"])[0]
    pasted = (fields.get("csv") or [""])[0].strip()
    path_text = (fields.get("path") or [""])[0].strip()
    if path_text:
        path = Path(path_text)
        if not path.is_file():
            return action, [], f"File not found on this PC: {path}"
        return action, lifecycle.read_csv(path), path.name
    if pasted:
        inbox = ROOT / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        temp = inbox / "preview.csv"
        temp.write_text(pasted + "\n", encoding="utf-8")
        return action, lifecycle.read_csv(temp), "pasted.csv"
    return action, [], ""


def live_from_request(fields: dict) -> str:
    action, rows, source = rows_from_request(fields)
    if not rows and source == "":
        return "Paste the spreadsheet, choose a file, or type the full path of a CSV already on this PC."
    if not rows:
        return source
    confirmed = (fields.get("confirm") or [""])[0] == "yes"
    dry_run = (fields.get("dry_run") or [""])[0] == "yes"
    if not confirmed:
        return preview_text(action, rows)
    return run_rows(action, rows, dry_run=dry_run, source_name=source)


def staff_list() -> str:
    path = ROOT / "data" / "directory.json"
    if not path.exists():
        return "No staff file on this PC yet. Run the demo, or run a live joiner file."
    data = lifecycle.load_json(path)
    lines = [f"Staff file on this PC: {path}", "", "ID     Enabled  Department        Email"]
    for user in data.get("users", []):
        enabled = "yes" if user.get("enabled") else "no"
        lines.append(f"{user['employee_id']:6} {enabled:7}  {user['department']:16}  {user['email']}")
        lines.append(f"       groups: {', '.join(user.get('groups') or []) or 'none'}")
    return "\n".join(lines)


def ticket() -> str:
    path = ROOT / "reports" / "demo-summary.md"
    reports = sorted((ROOT / "reports").glob("*.md"))
    if reports:
        path = reports[-1]
    if not path.exists():
        return "No ticket note yet. Run the demo or a live file first."
    return f"Latest ticket note: {path}\n\n" + path.read_text(encoding="utf-8")


def reset() -> str:
    path = ROOT / "data" / "directory.json"
    if path.exists():
        path.unlink()
        return "Staff file on this PC removed. Sample files and rules were not changed."
    return "No staff file to remove."


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>User lifecycle on this PC</title>
<style>
  body { font-family: Segoe UI, sans-serif; margin: 28px auto; max-width: 920px; color: #1a1a1a; line-height: 1.45; }
  h1 { font-size: 28px; margin-bottom: 4px; }
  h2 { font-size: 20px; margin-top: 28px; }
  .note { background: #fff6d8; border: 1px solid #e2c56a; padding: 12px 14px; }
  button { font-size: 16px; margin: 8px 8px 8px 0; padding: 10px 14px; cursor: pointer; }
  pre, textarea, input, select { font-family: Consolas, monospace; font-size: 14px; }
  pre { background: #f4f4f4; padding: 14px; white-space: pre-wrap; }
  textarea { width: 100%; height: 140px; }
  input[type=text] { width: 100%; padding: 8px; }
  label { display: block; margin-top: 10px; }
  ol { padding-left: 20px; }
</style>
</head>
<body>
  <h1>User lifecycle on this PC</h1>
  <p class="note">Demo and live use both stay on this computer. Neither contacts a tenant or changes a real Microsoft 365 account.</p>
  <p>Owner: Oluwatobiloba Benjamin Ogungbangbe. Not for sale. Permission is valid only if the owner confirms it.</p>

  <h2>How to run it</h2>
  <ol>
    <li>Double-click Start-Here. You are already in this window if you can read this.</li>
    <li>Click <b>Set up this computer</b>. It creates data, logs, reports, and inbox. Nothing is downloaded.</li>
    <li>Click <b>Run the sample demo</b> to see a joiner, a mover, and a leaver with fake people.</li>
    <li>Click <b>Show the staff list</b>, <b>Find one person</b>, and <b>Open the ticket note</b>.</li>
    <li>For a file on this PC: choose it, click <b>Preview</b>, then click <b>Run</b>. Tick dry run if you only want the ticket note.</li>
  </ol>
  <p>After the sample demo you should see 5 created, 1 rejected, Ada Okoye moved, and Sam Patel disabled. E9999 is not found. That is expected.</p>
  <p>Python 3 is the only requirement. If the window did not open, install Python from python.org and tick Add python.exe to PATH, then double-click Start-Here again.</p>

  <form method="post" action="/setup"><button>Set up this computer</button></form>
  <form method="post" action="/demo"><button>Run the sample demo</button></form>
  <form method="get" action="/list"><button>Show the staff list</button></form>
  <form method="get" action="/ticket"><button>Open the ticket note</button></form>
  <form method="post" action="/reset"><button>Reset the staff file on this PC</button></form>

  <h2>Find one person</h2>
  <form method="get" action="/person">
    <label>Employee id or email
      <input type="text" name="q" placeholder="E1001 or ada.okoye@example.com">
    </label>
    <button>Find</button>
  </form>

  <h2>Live use on this PC</h2>
  <p>Click Preview first. It shows the first rows and does not write the staff file. Click Run only after the preview looks right. Dry run writes the ticket note and leaves the staff file unchanged. The file you use is copied to inbox with the same time as the ticket note. inbox is not uploaded to GitHub. Do not use a real employee export if this folder will be copied to GitHub.</p>
  <form method="post" action="/live">
    <label>Action
      <select name="action">
        <option>joiner</option>
        <option>mover</option>
        <option>leaver</option>
      </select>
    </label>
    <label>Choose a CSV on this PC
      <input type="file" id="file" accept=".csv,text/csv">
    </label>
    <label>Or type the full path
      <input type="text" name="path" placeholder="C:\\Users\\you\\Desktop\\joiners.csv">
    </label>
    <label>Or paste the CSV
      <textarea name="csv" id="csv" placeholder="employee_id,first_name,last_name,department,job_title,location,role,manager_email,start_date"></textarea>
    </label>
    <label><input type="checkbox" name="dry_run" value="yes"> Dry run only. Do not change the staff file.</label>
    <button name="confirm" value="no">Preview</button>
    <button name="confirm" value="yes">Run</button>
  </form>
  <script>
    document.getElementById("file").addEventListener("change", function () {
      var reader = new FileReader();
      reader.onload = function () { document.getElementById("csv").value = reader.result; };
      reader.readAsText(this.files[0]);
    });
  </script>

  <h2>Result</h2>
  <pre>{result}</pre>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/list":
            self.respond(staff_list())
        elif path == "/person":
            from urllib.parse import parse_qs
            query = parse_qs(urlparse(self.path).query).get("q", [""])[0]
            self.respond(find_person(query))
        elif path == "/ticket":
            self.respond(ticket())
        else:
            self.respond(setup())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        fields = parse_qs(self.rfile.read(length).decode("utf-8", errors="replace"))
        path = urlparse(self.path).path
        if path == "/demo":
            self.respond(run_demo())
        elif path == "/live":
            self.respond(live_from_request(fields))
        elif path == "/reset":
            self.respond(reset())
        else:
            self.respond(setup())

    def respond(self, result: str):
        body = PAGE.replace("{result}", escape(result)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


def escape(text: str) -> str:
    return text.replace("&", "&").replace("<", "<").replace(">", ">")


def main() -> int:
    setup()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print("DEMO AND LIVE USE STAY ON THIS PC. Opening the window.")
    print(url)
    print("Close this window when you are finished.")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
