"""Where Webclaw and ERPClaw live on disk.

OpenClaw installs are unchanged when nothing is set:

* skills directory: ``~/clawd/skills``
* ERPClaw home: ``~/.openclaw/erpclaw``

Railway and any other layout set ``SKILLS_DIR`` (or ``OPENCLAW_SKILLS_DIR``)
and ``ERPCLAW_HOME``. Cross-skill calls inside ERPClaw look at
``OPENCLAW_SKILLS_DIR`` first, which is why both names are honored.
"""
import os
import re

_SECRET_URL = re.compile(
    r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"\\]+"
)
_SECRET_ASSIGN = re.compile(
    r"(?i)((?:secret|password|token|aws_secret_access_key)[A-Za-z0-9_]*\s*[=:]\s*)\S+"
)


def redact(text: str) -> str:
    """Remove connection URLs and password assignments from text that may be logged."""
    if not text:
        return ""
    cleaned = _SECRET_URL.sub(
        lambda match: match.group(0).split("://", 1)[0] + "://[redacted]",
        text,
    )
    return _SECRET_ASSIGN.sub(r"\1[redacted]", cleaned)


def erpclaw_home() -> str:
    return os.path.expanduser(os.environ.get("ERPCLAW_HOME", "~/.openclaw/erpclaw"))


def skills_dir() -> str:
    raw = (
        os.environ.get("SKILLS_DIR")
        or os.environ.get("OPENCLAW_SKILLS_DIR")
        or "~/clawd/skills"
    )
    return os.path.expanduser(raw)


def modules_dir() -> str:
    raw = os.environ.get("ERPCLAW_MODULES_DIR")
    if raw:
        return os.path.expanduser(raw)
    return os.path.join(erpclaw_home(), "modules")


def erpclaw_lib_dir() -> str:
    return os.path.join(erpclaw_home(), "lib")


def erpclaw_sqlite_path() -> str:
    return os.path.join(erpclaw_home(), "data.sqlite")


def _normalize_pg_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


def postgres_url_from(env: dict) -> str:
    """Return a postgresql:// URL from env, or an empty string.

    ``ERPCLAW_DB_URL`` wins over ``DATABASE_URL``. ``postgres://`` is rewritten
    to ``postgresql://`` because ERPClaw's URL check accepts both, and the
    rewritten form is what its PostgreSQL path documents.
    """
    url = (env.get("ERPCLAW_DB_URL") or env.get("DATABASE_URL") or "").strip()
    if url.startswith("postgres://") or url.startswith("postgresql://"):
        return _normalize_pg_url(url)
    path = (env.get("ERPCLAW_DB_PATH") or "").strip()
    if path.startswith("postgres://") or path.startswith("postgresql://"):
        return _normalize_pg_url(path)
    return ""


def apply_database_env(env: dict) -> tuple[dict, list[str]]:
    """Fill ERPClaw's dialect variables. Notes never include secrets.

    PostgreSQL is selected when a postgresql URL is present. SQLite is the
    fallback only when no URL is configured, and the note says so.
    """
    updated = dict(env)
    url = postgres_url_from(updated)
    if url:
        updated["ERPCLAW_DB_DIALECT"] = "postgresql"
        updated["ERPCLAW_DB_URL"] = url
        # automotiveclaw/init_db.py reads ERPCLAW_DB_PATH, not ERPCLAW_DB_URL.
        path = (updated.get("ERPCLAW_DB_PATH") or "").strip()
        if not path.startswith("postgresql://"):
            updated["ERPCLAW_DB_PATH"] = url
        if (updated.get("DATABASE_URL") or "").startswith("postgres://"):
            updated["DATABASE_URL"] = url
        return updated, ["erpclaw database: postgresql"]

    if (updated.get("ERPCLAW_DB_DIALECT") or "").strip().lower() == "postgresql":
        raise SystemExit(
            "ERPCLAW_DB_DIALECT=postgresql but neither DATABASE_URL nor "
            "ERPCLAW_DB_URL is a postgresql:// URL"
        )

    home = os.path.expanduser(updated.get("ERPCLAW_HOME", "~/.openclaw/erpclaw"))
    updated["ERPCLAW_DB_DIALECT"] = "sqlite"
    updated.setdefault("ERPCLAW_DB_PATH", os.path.join(home, "data.sqlite"))
    return updated, [
        "erpclaw database: sqlite fallback because no DATABASE_URL is set. "
        "Books are a file under ERPCLAW_HOME and need a persistent volume."
    ]


def use_postgres() -> bool:
    return (os.environ.get("ERPCLAW_DB_DIALECT") or "").strip().lower() == "postgresql"
