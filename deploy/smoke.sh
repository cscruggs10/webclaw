#!/bin/sh
# Exercise the local compose stack through the Next.js proxy.
# Does not print passwords. Expects the compose file's local admin.
set -eu

BASE="${BASE:-http://127.0.0.1:3000}"
EMAIL="${ADMIN_EMAIL:-corey@example.com}"
PASSWORD="${ADMIN_PASSWORD:-Local-Test-1}"
ROTATED="${ADMIN_PASSWORD_ROTATED:-Local-Test-2}"

python3 - "$BASE" "$EMAIL" "$PASSWORD" "$ROTATED" <<'PY'
import json, sys, urllib.error, urllib.request

base, email, password, rotated = sys.argv[1:]

def req(method, path, body=None, token=None, raw=False):
    data = None if body is None else json.dumps(body).encode()
    headers = {}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
            return response.status, payload if raw else json.loads(payload.decode() or "{}")
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        try:
            parsed = json.loads(payload.decode() or "{}")
        except json.JSONDecodeError:
            parsed = {"message": payload[:300].decode("utf-8", "replace")}
        return exc.code, parsed

print("health", req("GET", "/api/health")[1])
code, health = req("GET", "/api/v1/health")
print("api", code, {k: health.get(k) for k in ("status", "service", "database", "erpclaw", "webclaw_db")})
if code != 200 or health.get("database") != "postgresql" or health.get("erpclaw") != "ok":
    sys.exit("health check did not report postgresql ok")

code, login = req("POST", "/api/v1/auth/login", {"email": email, "password": password})
if code != 200:
    print("login failed", code, login.get("message"))
    sys.exit(1)
token = login["access_token"]
print("login ok")

code, skills = req("GET", "/api/v1/schema/skills", token=token)
names = sorted(s.get("name") for s in skills.get("skills", []))
print("skills", names)
for needed in ("erpclaw", "automotiveclaw"):
    if needed not in names:
        sys.exit(f"missing skill {needed}")

for skill in ("erpclaw", "automotiveclaw"):
    code, ui = req("GET", f"/api/ui-config/{skill}")
    if code != 200 or not isinstance(ui, dict):
        sys.exit(f"ui-config {skill} failed {code}")
    print(f"ui-config {skill} ok keys={sorted(ui)[:6]}")

code, companies = req("GET", "/api/v1/erpclaw/list-companies", token=token)
if code != 200:
    print(companies)
    sys.exit("list-companies failed")
rows = companies.get("companies") or []
if not rows:
    sys.exit("no company")
company_id = rows[0].get("id") or rows[0].get("company_id")
print("company", rows[0].get("name"), "id_present", bool(company_id))

code, customer = req("POST", "/api/v1/automotiveclaw/auto-add-customer", {
    "company-id": company_id,
    "name": "Test Buyer",
    "customer-type": "individual",
    "phone": "555-0100",
}, token=token)
if code != 200:
    print("customer", code, customer.get("message") or customer.get("error"))
    sys.exit(1)
print("customer", customer.get("customer_id") or customer.get("id"))

code, vehicle = req("POST", "/api/v1/automotiveclaw/auto-add-vehicle", {
    "company-id": company_id,
    "make": "Ford",
    "model": "F-150",
    "year": "2019",
    "vin": "1FTEW1EP5KFA00001",
    "selling-price": "18500.00",
    "vehicle-condition": "used",
}, token=token)
if code != 200:
    print("vehicle", code, vehicle.get("message") or vehicle.get("error"))
    sys.exit(1)
print("vehicle", vehicle.get("id") or vehicle.get("vehicle_id"))

# multipart upload through the proxy
boundary = "----webclawboundary"
content = b"title-scan-test"
body = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="file"; filename="title.txt"\r\n'
    f"Content-Type: text/plain\r\n\r\n"
).encode() + content + f"\r\n--{boundary}--\r\n".encode()
request = urllib.request.Request(
    base + "/api/v1/files/upload",
    data=body,
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    },
    method="POST",
)
with urllib.request.urlopen(request, timeout=30) as response:
    uploaded = json.loads(response.read().decode())
print("upload", uploaded.get("backend"), "bytes", uploaded.get("bytes"))
key = uploaded["key"]
request = urllib.request.Request(
    base + f"/api/v1/files/{key}",
    headers={"Authorization": f"Bearer {token}"},
)
with urllib.request.urlopen(request, timeout=30) as response:
    downloaded = response.read()
if downloaded != content:
    sys.exit("downloaded file did not match")
print("download ok")

code, changed = req("POST", "/api/v1/auth/change-password", {
    "current_password": password,
    "new_password": rotated,
}, token=token)
if code != 200:
    print("change-password", code, changed.get("message"))
    sys.exit(1)
print("password rotated; restart the api and run smoke-after-restart.sh")
open("/tmp/webclaw-smoke-rotated", "w").write("1\n")
PY
