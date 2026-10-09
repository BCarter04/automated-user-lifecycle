"""Ask for the real-tenant details and keep the secret off GitHub.

Copyright (c) 2026 Oluwatobiloba Benjamin Ogungbangbe. All rights reserved.
The secret is written only to .secret on this PC. That file is not uploaded.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.json"
SECRET = ROOT / ".secret"


def save_live(tenant: str, tenant_id: str, client_id: str, domain: str, secret: str) -> str:
    """Save the names in config.json. Save the secret only in .secret."""
    missing = []
    if not tenant.strip():
        missing.append("tenant name, such as contoso.onmicrosoft.com")
    if not tenant_id.strip():
        missing.append("tenant id")
    if not client_id.strip():
        missing.append("application client id")
    if not domain.strip():
        missing.append("email domain, such as contoso.com")
    if missing:
        return "Not saved. Still needed: " + "; ".join(missing)
    config = {
        "tenant": tenant.strip(),
        "tenant_id": tenant_id.strip(),
        "client_id": client_id.strip(),
        "default_domain": domain.strip(),
        "mode": "live",
        "licence_sku": "Microsoft 365 E3",
        "require_manager": True,
        "notes": "Live names only. The secret is in .secret and is not uploaded.",
    }
    CONFIG.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    if secret.strip():
        SECRET.write_text(secret.strip(), encoding="utf-8")
        try:
            SECRET.chmod(0o600)
        except OSError:
            pass
        return "Saved on this PC. config.json has the names. .secret has the secret. Neither file is uploaded."
    return "Saved the names in config.json. The secret was left blank. Put it in .secret on this PC before a connection test."


def read_secret() -> str:
    if os.environ.get("LIFECYCLE_CLIENT_SECRET"):
        return os.environ["LIFECYCLE_CLIENT_SECRET"]
    if SECRET.exists():
        return SECRET.read_text(encoding="utf-8").strip()
    return ""


def test_connection() -> str:
    """Ask Entra for a token. This does not create or disable a user."""
    if not CONFIG.exists():
        return "No config.json on this PC. Fill the live form first."
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    secret = read_secret()
    if not secret:
        return "No secret on this PC. Paste it in the live form, or set LIFECYCLE_CLIENT_SECRET. It is not uploaded."
    tenant = config.get("tenant_id") or config.get("tenant")
    body = urllib.parse.urlencode({
        "client_id": config.get("client_id", ""),
        "client_secret": secret,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }).encode("utf-8")
    url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    request = urllib.request.Request(url, data=body, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:300]
        return f"Connection failed. Entra refused the sign-in. Check the tenant id, client id, and secret. {detail}"
    except urllib.error.URLError as error:
        return f"Connection failed. This PC could not reach Entra. {error.reason}"
    if not payload.get("access_token"):
        return "Connection failed. Entra did not return a token."
    return "Connected. Entra accepted the app. No user was created or disabled. The token was not saved."
