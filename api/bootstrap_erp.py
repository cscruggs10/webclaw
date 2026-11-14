"""First-boot ERPClaw + AutomotiveClaw init. Safe to run on every start.

What this will not do:

* pass ``--force`` to ``initialize-database`` (that drops a SQLite file)
* create a company when any company row already exists
* print database URLs, passwords, or JWT secrets

PostgreSQL is the database when ``DATABASE_URL`` or ``ERPCLAW_DB_URL`` is set.
SQLite under ``ERPCLAW_HOME`` is used only when neither URL is set.
"""
import json
import os
import subprocess
import sys

from runtime_paths import apply_database_env, erpclaw_home, modules_dir, redact


def _scripts() -> tuple[str, str, str, str]:
    root = os.environ.get("ERPCLAW_DIR", "/opt/skills/erpclaw")
    auto = os.environ.get("AUTOMOTIVE_DIR", "/opt/skills/automotiveclaw")
    setup = os.path.join(root, "scripts", "erpclaw-setup", "db_query.py")
    gl = os.path.join(root, "scripts", "erpclaw-gl", "db_query.py")
    init_auto = os.path.join(auto, "init_db.py")
    return root, setup, gl, init_auto


def _parse_json(stdout: str) -> dict:
    text = stdout.strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.rfind("\n{")
        if start == -1:
            raise
        data = json.loads(text[start + 1:])
    if not isinstance(data, dict):
        raise ValueError("skill response was not a JSON object")
    return data


def _run(script: str, args: list[str], timeout: int = 600) -> dict:
    if not os.path.isfile(script):
        raise SystemExit(f"webclaw: missing ERPClaw script {script}")
    proc = subprocess.run(
        [sys.executable, script, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=os.environ.copy(),
    )
    if proc.returncode != 0:
        action = args[1] if len(args) > 1 and args[0] == "--action" else os.path.basename(script)
        print(f"webclaw: {action} failed", file=sys.stderr)
        detail = redact((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()
        if detail:
            print(detail[-2000:], file=sys.stderr)
        raise SystemExit(1)
    try:
        return _parse_json(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        print(f"webclaw: {os.path.basename(script)} returned no JSON", file=sys.stderr)
        print(redact(proc.stdout)[-1000:], file=sys.stderr)
        raise SystemExit(1)


def _link_module(name: str, source: str) -> None:
    if not os.path.isdir(source):
        return
    dest_root = modules_dir()
    os.makedirs(dest_root, exist_ok=True)
    dest = os.path.join(dest_root, name)
    real_src = os.path.realpath(source)
    if os.path.islink(dest):
        if os.path.realpath(dest) == real_src:
            return
        os.unlink(dest)
    elif os.path.exists(dest):
        # A real directory was placed here on purpose. Leave it alone.
        return
    os.symlink(real_src, dest)


def _ensure_company(setup: str, gl: str) -> None:
    name = os.environ.get("COMPANY_NAME", "").strip()
    listed = _run(setup, ["--action", "list-companies", "--limit", "1"])
    if listed.get("status") == "error":
        print("webclaw: list-companies failed", file=sys.stderr)
        print(redact(listed.get("message") or listed.get("error") or ""), file=sys.stderr)
        raise SystemExit(1)
    count = listed.get("total_count")
    if count is None:
        count = len(listed.get("companies") or [])
    if int(count) > 0:
        print(
            f"webclaw: {int(count)} company row(s) already present; books left unchanged",
            flush=True,
        )
        return
    if not name:
        print(
            "webclaw: no company yet and COMPANY_NAME is unset; not creating one",
            flush=True,
        )
        return

    args = [
        "--action", "setup-company",
        "--name", name,
        "--currency", os.environ.get("COMPANY_CURRENCY", "USD"),
        "--country", os.environ.get("COMPANY_COUNTRY", "United States"),
        "--fiscal-year-start-month", os.environ.get("COMPANY_FISCAL_MONTH", "1"),
    ]
    abbr = os.environ.get("COMPANY_ABBR", "").strip()
    if abbr:
        args.extend(["--abbr", abbr])
    created = _run(setup, args)
    company_id = created.get("company_id")
    if not company_id:
        print("webclaw: setup-company did not return a company id", file=sys.stderr)
        raise SystemExit(1)
    print("webclaw: created company from COMPANY_NAME", flush=True)

    _run(setup, ["--action", "seed-defaults", "--company-id", company_id])
    print("webclaw: seeded default currencies and units", flush=True)

    template = os.environ.get("CHART_TEMPLATE", "us_gaap")
    chart = _run(
        gl,
        ["--action", "setup-chart-of-accounts", "--company-id", company_id, "--template", template],
        timeout=180,
    )
    if chart.get("company_defaults_error"):
        print("webclaw: chart of accounts did not set company default accounts", file=sys.stderr)
        print(redact(str(chart.get("company_defaults_error"))), file=sys.stderr)
        raise SystemExit(1)
    print("webclaw: chart of accounts ready", flush=True)


def bootstrap_erp() -> None:
    """Initialize schema, link the automotive module, create a company if needed."""
    updated, notes = apply_database_env(dict(os.environ))
    os.environ.update(updated)
    for note in notes:
        print(f"webclaw: {note}", flush=True)

    home = erpclaw_home()
    os.makedirs(home, exist_ok=True)
    webclaw_db = os.environ.get("WEBCLAW_DB_PATH", os.path.join(home, "webclaw.sqlite"))
    webclaw_dir = os.path.dirname(webclaw_db)
    if webclaw_dir:
        os.makedirs(webclaw_dir, exist_ok=True)
    os.makedirs(os.environ.get("UPLOAD_DIR", "/data/uploads"), exist_ok=True)

    _root, setup, gl, init_auto = _scripts()
    _run(setup, ["--action", "initialize-database"])
    print("webclaw: erpclaw schema initialized", flush=True)

    lib_pkg = os.path.join(home, "lib", "erpclaw_lib")
    if not os.path.isdir(lib_pkg):
        raise SystemExit("webclaw: ERPCLAW_HOME/lib was not linked; refusing to serve")

    if not os.path.isfile(init_auto):
        raise SystemExit(f"webclaw: automotive init script missing at {init_auto}")
    proc = subprocess.run(
        [sys.executable, init_auto],
        capture_output=True,
        text=True,
        timeout=300,
        env=os.environ.copy(),
    )
    if proc.returncode != 0:
        print("webclaw: automotive schema init failed", file=sys.stderr)
        print(redact((proc.stderr or "") + "\n" + (proc.stdout or ""))[-2000:], file=sys.stderr)
        raise SystemExit(1)
    print("webclaw: automotive schema initialized", flush=True)

    auto_dir = os.environ.get("AUTOMOTIVE_DIR", "/opt/skills/automotiveclaw")
    _link_module("automotiveclaw", auto_dir)
    _ensure_company(setup, gl)


if __name__ == "__main__":
    bootstrap_erp()
