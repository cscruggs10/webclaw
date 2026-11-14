#!/bin/sh
# After `docker compose restart api`: the rotated password must still work
# and the original env password must not have been written back.
set -eu
BASE="${BASE:-http://127.0.0.1:3000}"
EMAIL="${ADMIN_EMAIL:-corey@example.com}"
PASSWORD="${ADMIN_PASSWORD:-Local-Test-1}"
ROTATED="${ADMIN_PASSWORD_ROTATED:-Local-Test-2}"

python3 - "$BASE" "$EMAIL" "$PASSWORD" "$ROTATED" <<'PY'
import json, sys, urllib.error, urllib.request

base, email, original, rotated = sys.argv[1:]

def req(method, path, body=None, token=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"} if body is not None else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        try:
            parsed = json.loads(payload.decode() or "{}")
        except json.JSONDecodeError:
            parsed = {}
        return exc.code, parsed

code, old = req("POST", "/api/v1/auth/login", {"email": email, "password": original})
if code == 200:
    sys.exit("original password still works; restart rewrote the hash from ADMIN_PASSWORD")
print("original password rejected after restart")

code, login = req("POST", "/api/v1/auth/login", {"email": email, "password": rotated})
if code != 200:
    print(login.get("message"))
    sys.exit("rotated password did not survive restart")
token = login["access_token"]
print("rotated password survived restart")

code, vehicles = req("GET", "/api/v1/automotiveclaw/auto-list-vehicles", token=token)
if code != 200:
    print(vehicles)
    sys.exit("list vehicles failed")
count = vehicles.get("total_count")
if count is None:
    count = len(vehicles.get("vehicles") or vehicles.get("rows") or [])
print("vehicles_visible", count if count else "response_ok")

# Put the local password back so a later smoke run can log in with the compose value.
code, restored = req("POST", "/api/v1/auth/change-password", {
    "current_password": rotated,
    "new_password": original,
}, token=token)
if code != 200:
    print(restored.get("message"))
    sys.exit("could not restore local password")
print("local password restored")
PY
