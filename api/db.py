"""Database connection helper for Webclaw.

Provides connections to:
1. Webclaw's own DB (auth, sessions, chat, config, audit)
2. Skill-specific DBs (for entity resolution, read from SKILL.md)

Replaces erpclaw_lib.db — webclaw has zero dependency on any skill's shared lib.
"""
import glob
import os
import re
import sqlite3
import stat

import yaml

from pg_skill_db import open_postgres
from runtime_paths import erpclaw_sqlite_path, skills_dir, use_postgres

SKILLS_DIR = skills_dir()
_SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DEFAULT_WEBCLAW_DB = os.path.expanduser(
    os.environ.get("WEBCLAW_DB_PATH", "~/.openclaw/webclaw/webclaw.sqlite")
)

# Cache: skill_name → db_path (from SKILL.md webclaw.database)
_skill_db_cache: dict[str, str] = {}
_tables_initialized = False


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    """Apply standard SQLite PRAGMAs for safety and performance."""
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")


def _ensure_dir(path: str) -> None:
    """Create parent directory if it doesn't exist."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Get a connection to webclaw's own database.

    This database stores auth (users, sessions, roles), chat history,
    config, and audit logs — independent of any skill's database.

    Args:
        db_path: Override path. Defaults to WEBCLAW_DB_PATH env var
                 or ~/.openclaw/webclaw/webclaw.sqlite.

    Returns:
        sqlite3.Connection with row_factory=sqlite3.Row.
    """
    global _tables_initialized
    path = db_path or os.environ.get("WEBCLAW_DB_PATH", DEFAULT_WEBCLAW_DB)
    _ensure_dir(path)
    is_new = not os.path.exists(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)

    # Auto-initialize tables on first use
    if not _tables_initialized:
        try:
            from init_webclaw_db import init_tables
            init_tables(conn)
        except Exception as e:
            import sys
            print(f"WARNING: webclaw schema init: {e}", file=sys.stderr)
        _tables_initialized = True

    if is_new:
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        except OSError as e:
            import sys
            print(f"WARNING: could not set DB permissions: {e}", file=sys.stderr)
    return conn


def _shared_skill_names() -> set[str]:
    raw = os.environ.get("WEBCLAW_SHARED_DB_SKILLS", "automotiveclaw")
    return {part.strip() for part in raw.split(",") if part.strip()}


def _is_shared_books(db_path: str | None) -> bool:
    """True when a skill points at the ERPClaw books file (any install root)."""
    if not db_path:
        return False
    expanded = os.path.abspath(os.path.expanduser(db_path))
    shared = {
        os.path.abspath(erpclaw_sqlite_path()),
        os.path.abspath(os.path.expanduser("~/.openclaw/erpclaw/data.sqlite")),
    }
    return expanded in shared


def _uses_shared_books(skill_name: str, db_path: str | None) -> bool:
    if skill_name == "erpclaw" or skill_name.startswith("erpclaw-"):
        return db_path is None or _is_shared_books(db_path) or not os.path.isfile(db_path or "")
    if skill_name in _shared_skill_names():
        return True
    return _is_shared_books(db_path)


def get_skill_db(skill_name: str):
    """Get a DB connection for a specific skill's data.

    Reads webclaw.database from the skill's SKILL.md frontmatter.
    Falls back to the shared ERPClaw books. When ``ERPCLAW_DB_DIALECT`` is
    ``postgresql``, skills that share those books get a Postgres connection
    instead of the SQLite file named in SKILL.md.

    Returns:
        A connection, or None if the database is not available.
    """
    db_path = _resolve_skill_db_path(skill_name)
    if use_postgres() and _uses_shared_books(skill_name, db_path):
        try:
            return open_postgres()
        except Exception:
            return None
    if not db_path or not os.path.isfile(db_path):
        return None

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)
    return conn


def _resolve_skill_db_path(skill_name: str) -> str | None:
    """Resolve the database path for a skill from its SKILL.md."""
    if not _SKILL_NAME_RE.match(skill_name):
        return None
    if skill_name in _skill_db_cache:
        return _skill_db_cache[skill_name]

    skill_md = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
    db_path = None

    try:
        with open(skill_md, "r") as f:
            content = f.read()
        if content.startswith("---"):
            end = content.index("---", 3)
            frontmatter = yaml.safe_load(content[3:end])
            if frontmatter:
                # Check webclaw.database first (ERPClaw modules)
                webclaw = frontmatter.get("webclaw", {})
                if isinstance(webclaw, dict) and webclaw.get("database"):
                    db_path = os.path.expanduser(webclaw["database"])
                # Then check top-level database key (standalone skills like OilCRM)
                elif frontmatter.get("database"):
                    db_path = os.path.expanduser(frontmatter["database"])
    except Exception:
        pass

    # Fallback: the shared ERPClaw books, when that file is already there.
    if not db_path:
        for candidate in (
            erpclaw_sqlite_path(),
            os.path.expanduser("~/.openclaw/erpclaw/data.sqlite"),
        ):
            if os.path.exists(candidate):
                db_path = candidate
                break

    _skill_db_cache[skill_name] = db_path
    return db_path


def get_all_skill_db_paths() -> dict[str, str]:
    """Discover all skill DB paths from installed skills.

    Returns:
        Dict of skill_name → db_path for all skills with discoverable databases.
    """
    paths: dict[str, str] = {}
    for skill_md in sorted(glob.glob(os.path.join(SKILLS_DIR, "*/SKILL.md"))):
        skill_name = os.path.basename(os.path.dirname(skill_md))
        db_path = _resolve_skill_db_path(skill_name)
        if db_path:
            paths[skill_name] = db_path
    return paths
