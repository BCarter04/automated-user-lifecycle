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


def run_rows(action: str, rows: list[dict], clear: bool = False) -> str:
    if action not in {"joiner", "mover", "leaver"}:
        return "Choose joiner, mover, or leaver."
    if not rows:
        return "No rows to process. Paste a CSV or give a path on this PC."
    current, config = engine()
    if clear and (ROOT / "data" / "directory.json").exists():
        (ROOT / "data" / "directory.json").unlink()
        current, config = engine()
    results = lifecycle.run_action(current, action, rows)
    current.save()
    _, report = current.write_reports(action)
    lines = [
        "LIVE ON THIS PC. No tenant was contacted.",
        f"Staff file: {ROOT / 'data' / 'directory.json'}",
        f"Ticket note: {report}",
        "",
    ]
    for item in results:
        reason = ", ".join(item.get("errors") or [])
        extra = f" — {reason}" if reason else ""
        lines.append(f"{item['status']:10} {item.get('employee_id', '')} {item.get('email', '')}{extra}")
    return "\n".join(lines)


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


def live_from_request(fields: dict) -> str:
    action = (fields.get("action") or ["joiner"])[0]
    pasted = (fields.get("csv") or [""])[0].strip()
    path_text = (fields.get("path") or [""])[0].strip()
    if pasted:
        inbox = ROOT / "inbox" / f"{action}-pasted.csv"
        inbox.write_text(pasted + "\n", encoding="utf-8")
        rows = lifecycle.read_csv(inbox)
        return run_rows(action, rows)
    if path_text:
        path = Path(path_text)
        if not path.is_file():
            return f"File not found on this PC: {path}"
        return run_rows(action, lifecycle.read_csv(path))
    return "Paste the spreadsheet, or type the full path of a CSV already on this PC."


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
    <li>Click <b>Show the staff list</b> and <b>Open the ticket note</b>.</li>
    <li>For a real file on this PC, use the live form below. Do not paste real employee data if this folder will be copied to GitHub.</li>
  </ol>
  <p>Python 3 is the only requirement. If the window did not open, install Python from python.org and tick Add python.exe to PATH, then double-click Start-Here again.</p>

  <form method="post" action="/setup"><button>Set up this computer</button></form>
  <form method="post" action="/demo"><button>Run the sample demo</button></form>
  <form method="get" action="/list"><button>Show the staff list</button></form>
  <form method="get" action="/ticket"><button>Open the ticket note</button></form>
  <form method="post" action="/reset"><button>Reset the staff file on this PC</button></form>

  <h2>Live use on this PC</h2>
  <p>This writes the staff file on this computer: data/directory.json. Put a CSV in the box, or type the full path of a CSV already on this PC. The path wins if both are filled. A second run of the same person is marked already provisioned, not rejected.</p>
  <p>Joiner columns: employee_id, first_name, last_name, department, job_title, location, role, manager_email, start_date.</p>
  <p>Mover columns: employee_id, email, new_department, new_job_title, new_location, new_role, new_manager_email.</p>
  <p>Leaver columns: employee_id, email, reason. Departments must match rules/department-rules.json.</p>
  <form method="post" action="/live">
    <label>Action
      <select name="action">
        <option>joiner</option>
        <option>mover</option>
        <option>leaver</option>
      </select>
    </label>
    <label>CSV path already on this PC
      <input type="text" name="path" placeholder="C:\\Users\\you\\Desktop\\joiners.csv">
    </label>
    <label>Or paste the CSV here
      <textarea name="csv" placeholder="employee_id,first_name,last_name,department,job_title,location,role,manager_email,start_date"></textarea>
    </label>
    <button>Run on this PC</button>
  </form>

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
