"""Container entrypoint: init the books, then replace this process with uvicorn.

Database URLs stay in the environment for child processes. They are not printed.
"""
import os
import sys


def main() -> None:
    os.environ.setdefault("SKILLS_DIR", "/opt/skills")
    os.environ.setdefault("ERPCLAW_HOME", "/data/erpclaw")
    os.environ.setdefault("WEBCLAW_DB_PATH", "/data/webclaw/webclaw.sqlite")
    os.environ.setdefault("UPLOAD_DIR", "/data/uploads")
    os.environ.setdefault("OPENCLAW_SKILLS_DIR", os.environ.get("SKILLS_DIR", "/opt/skills"))

    from bootstrap_admin import ensure_admin
    from bootstrap_erp import bootstrap_erp

    bootstrap_erp()
    ensure_admin()

    port = os.environ.get("PORT", "8001")
    # Working directory in the image is the api package, matching the systemd unit.
    os.execvp(
        sys.executable,
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", port],
    )


if __name__ == "__main__":
    main()
