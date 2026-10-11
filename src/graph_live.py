"""Microsoft 365 actions after a successful Entra sign-in.

Copyright (c) 2026 Oluwatobiloba Benjamin Ogungbangbe. All rights reserved.
Uses the token from the details saved on this PC. The secret is not uploaded.
"""

from __future__ import annotations

import json
import secrets
import string
import urllib.error
import urllib.parse
import urllib.request

import live_setup

GRAPH = "https://graph.microsoft.com/v1.0"


def token() -> str:
    if not live_setup.CONFIG.exists():
        raise RuntimeError("No config.json on this PC. Fill section 5 first.")
    config = json.loads(live_setup.CONFIG.read_text(encoding="utf-8"))
    secret = live_setup.read_secret()
    if not secret:
        raise RuntimeError("No secret on this PC. Fill section 5 first.")
    tenant = config.get("tenant_id") or config.get("tenant")
    body = urllib.parse.urlencode({
        "client_id": config.get("client_id", ""),
        "client_secret": secret,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }).encode("utf-8")
    request = urllib.request.Request(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        data=body,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("access_token"):
        raise RuntimeError("Entra did not return a token.")
    return payload["access_token"]


def call(method: str, path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        GRAPH + path,
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"Graph {method} {path} failed. {detail}") from error


def find_user(employee_id: str, email: str) -> dict | None:
    for field, value in (("employeeId", employee_id), ("mail", email), ("userPrincipalName", email)):
        if not value:
            continue
        safe = value.replace("'", "''")
        result = call("GET", f"/users?$filter={field} eq '{safe}'&$select=id,mail,userPrincipalName,accountEnabled,employeeId")
        if result.get("value"):
            return result["value"][0]
    return None


def find_group(name: str) -> str | None:
    safe = name.replace("'", "''")
    result = call("GET", f"/groups?$filter=displayName eq '{safe}'&$select=id,displayName")
    if result.get("value"):
        return result["value"][0]["id"]
    return None


def find_sku(name: str) -> str | None:
    result = call("GET", "/subscribedSkus")
    wanted = name.lower()
    for sku in result.get("value", []):
        if wanted in {str(sku.get("skuPartNumber", "")).lower(), str(sku.get("skuId", "")).lower()}:
            return sku["skuId"]
        if wanted in str(sku.get("skuPartNumber", "")).lower().replace("_", " "):
            return sku["skuId"]
    return None


def temp_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "Aa1!" + "".join(secrets.choice(alphabet) for _ in range(12))


def apply_joiner(row: dict, groups: list[str], licence: str, domain: str) -> dict:
    email = f"{row['first_name']}.{row['last_name']}@{domain}".lower().replace(" ", "")
    existing = find_user(row.get("employee_id", ""), email)
    password = ""
    if existing:
        user_id = existing["id"]
        status = "already in Microsoft 365"
    else:
        password = temp_password()
        created = call("POST", "/users", {
            "accountEnabled": True,
            "displayName": f"{row['first_name']} {row['last_name']}",
            "mailNickname": email.split("@")[0],
            "userPrincipalName": email,
            "employeeId": row.get("employee_id", ""),
            "department": row.get("department", ""),
            "jobTitle": row.get("job_title", ""),
            "passwordProfile": {"forceChangePasswordNextSignIn": True, "password": password},
        })
        user_id = created["id"]
        status = "created in Microsoft 365"
    missing = []
    for name in groups:
        group_id = find_group(name)
        if not group_id:
            missing.append(name)
            continue
        try:
            call("POST", f"/groups/{group_id}/members/$ref", {"@odata.id": f"{GRAPH}/directoryObjects/{user_id}"})
        except RuntimeError as error:
            if "already exist" not in str(error).lower():
                missing.append(f"{name} ({error})")
    if licence:
        sku = find_sku(licence)
        if sku:
            call("POST", f"/users/{user_id}/assignLicense", {"addLicenses": [{"skuId": sku}], "removeLicenses": []})
        else:
            missing.append(f"licence {licence}")
    return {"status": status, "email": email, "temp_password": password, "missing": missing}


def apply_leaver(employee_id: str, email: str) -> dict:
    user = find_user(employee_id, email)
    if not user:
        return {"status": "not found in Microsoft 365"}
    call("PATCH", f"/users/{user['id']}", {"accountEnabled": False})
    try:
        call("POST", f"/users/{user['id']}/revokeSignInSessions", {})
    except RuntimeError:
        pass
    return {"status": "blocked in Microsoft 365", "email": user.get("userPrincipalName", email)}


def apply_mover(employee_id: str, email: str, department: str, groups_added: list[str], groups_removed: list[str]) -> dict:
    user = find_user(employee_id, email)
    if not user:
        return {"status": "not found in Microsoft 365"}
    call("PATCH", f"/users/{user['id']}", {"department": department})
    missing = []
    for name in groups_added:
        group_id = find_group(name)
        if not group_id:
            missing.append(name)
            continue
        try:
            call("POST", f"/groups/{group_id}/members/$ref", {"@odata.id": f"{GRAPH}/directoryObjects/{user['id']}"})
        except RuntimeError as error:
            if "already exist" not in str(error).lower():
                missing.append(name)
    for name in groups_removed:
        group_id = find_group(name)
        if not group_id:
            continue
        try:
            call("DELETE", f"/groups/{group_id}/members/{user['id']}/$ref")
        except RuntimeError:
            missing.append(f"could not remove {name}")
    return {"status": "moved in Microsoft 365", "email": user.get("userPrincipalName", email), "missing": missing}
