#!/usr/bin/env python3
# Copyright (c) 2026 Oluwatobiloba Benjamin Ogungbangbe. All rights reserved.
# Owner: Oluwatobiloba Benjamin Ogungbangbe. Not for sale. See LICENSE.
# Permission is valid only if the owner confirms it himself.
"""First-run window. Double-click Start-Here. No commands to type.

This opens a page on this computer only. It checks the folders, runs the
sample demo, and shows the staff list and the ticket note.
It does not contact a tenant.
"""

from __future__ import annotations

import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import lifecycle  # noqa: E402

PORT = 8765


def setup() -> str:
    """Create the local folders and the fake config. Nothing is downloaded."""
    for name in ("data", "logs", "reports"):
        (ROOT / name).mkdir(parents=True, exist_ok=True)
    config = ROOT / "config.json"
    if not config.exists():
        config.write_text((ROOT / "config.example.json").read_text(encoding="utf-8"), encoding="utf-8")
        return "Folders are ready. config.json was created from the example. It uses a fake tenant."
    return "Folders are ready. Your existing config.json was left unchanged."


def run_demo() -> str:
    config = lifecycle.load_json(ROOT / "config.example.json")
    rules = lifecycle.load_json(ROOT / "rules" / "department-rules.json")
    directory = ROOT / "data" / "directory.json"
    if directory.exists():
        directory.unlink()
    engine = lifecycle.Lifecycle(config, rules, directory, ROOT / "logs", ROOT / "reports")
    lines = ["DEMO ONLY. No tenant is contacted.", ""]
    ran = []
    for action, path in (
        ("joiner", ROOT / "samples" / "joiners.csv"),
        ("mover", ROOT / "samples" / "movers.csv"),
        ("leaver", ROOT / "samples" / "leavers.csv"),
    ):
        engine.events = []
        results = lifecycle.run_action(engine, action, lifecycle.read_csv(path))
        engine.save()
        engine.write_reports(action)
        ran.append((action, results))
        lines.append(action)
        for item in results:
            reason = ", ".join(item.get("errors") or [])
            extra = f" — {reason}" if reason else ""
            lines.append(f"  {item['status']:10} {item.get('employee_id', '')} {item.get('email', '')}{extra}")
        lines.append("")
    summary = lifecycle.write_demo_summary(ROOT / "reports", config["tenant"], ran)
    lines.append(f"Ticket note: {summary}")
    return "\n".join(lines)


def staff_list() -> str:
    path = ROOT / "data" / "directory.json"
    if not path.exists():
        return "No staff file yet. Click Run the sample demo."
    data = lifecycle.load_json(path)
    lines = ["ID     Enabled  Department        Email"]
    for user in data.get("users", []):
        enabled = "yes" if user.get("enabled") else "no"
        lines.append(f"{user['employee_id']:6} {enabled:7}  {user['department']:16}  {user['email']}")
        lines.append(f"       groups: {', '.join(user.get('groups') or []) or 'none'}")
    return "\n".join(lines)


def ticket() -> str:
    path = ROOT / "reports" / "demo-summary.md"
    if not path.exists():
        return "No ticket note yet. Click Run the sample demo."
    return path.read_text(encoding="utf-8")


def reset() -> str:
    path = ROOT / "data" / "directory.json"
    if path.exists():
        path.unlink()
        return "Local staff file removed. The sample files were not changed."
    return "No staff file to remove."


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>User lifecycle demo</title>
<style>
  body { font-family: Segoe UI, sans-serif; margin: 32px auto; max-width: 860px; color: #1a1a1a; }
  h1 { font-size: 28px; margin-bottom: 4px; }
  .note { background: #fff6d8; border: 1px solid #e2c56a; padding: 12px 14px; }
  button { font-size: 16px; margin: 8px 8px 8px 0; padding: 10px 14px; cursor: pointer; }
  pre { background: #f4f4f4; padding: 14px; white-space: pre-wrap; }
  p.owner { color: #444; }
</style>
</head>
<body>
  <h1>User lifecycle demo</h1>
  <p class="note">Demo only. This does not contact a tenant and does not change a real account.</p>
  <p class="owner">Owner: Oluwatobiloba Benjamin Ogungbangbe. Not for sale. Permission is valid only if the owner confirms it.</p>
  <form method="post" action="/setup"><button>1. Set up this computer</button></form>
  <form method="post" action="/demo"><button>2. Run the sample demo</button></form>
  <form method="get" action="/list"><button>3. Show the staff list</button></form>
  <form method="get" action="/ticket"><button>4. Open the ticket note</button></form>
  <form method="post" action="/reset"><button>Reset the local staff file</button></form>
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
        path = urlparse(self.path).path
        if path == "/demo":
            self.respond(run_demo())
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
    print("DEMO ONLY. Opening the first-run window.")
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
