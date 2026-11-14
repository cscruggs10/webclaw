"""Read-only PostgreSQL adapter for Webclaw's skill lookups.

ERPClaw's own scripts talk to Postgres through erpclaw_lib. Webclaw's
dashboard also reads the shared books (company id, audit activity, entity
search) with sqlite-shaped SQL. This wrapper translates the few catalog
queries those callers use and maps ``?`` placeholders to ``%s``. It does
not run accounting writes.
"""
import re

from runtime_paths import postgres_url_from

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MASTER_ONE = re.compile(
    r"""(?is)^select\s+name\s+from\s+sqlite_master\s+where\s+type\s*=\s*'table'\s+and\s+name\s*=\s*\?\s*$"""
)
_MASTER_ALL = re.compile(
    r"""(?is)^select\s+name\s+from\s+sqlite_master\s+where\s+type\s*=\s*'table'(?:\s+order\s+by\s+name)?\s*$"""
)
_PRAGMA = re.compile(
    r"""(?is)^pragma\s+table_info\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\)\s*$"""
)


class Row:
    """Indexable and mapping-style row, close enough to sqlite3.Row for callers."""

    def __init__(self, columns: list[str], values: tuple):
        self._columns = columns
        self._values = values
        self._map = {name: values[i] for i, name in enumerate(columns) if i < len(values)}

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._map[key]
        return self._values[key]

    def keys(self):
        return self._map.keys()

    def __iter__(self):
        return iter(self._map)

    def __len__(self):
        return len(self._values)


class Cursor:
    def __init__(self, columns: list[str], rows: list[tuple]):
        self._columns = columns
        self._rows = [Row(columns, row) for row in rows]
        self._index = 0

    def fetchone(self):
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row

    def fetchall(self):
        rows = self._rows[self._index:]
        self._index = len(self._rows)
        return rows

    def __iter__(self):
        return iter(self.fetchall())


def translate_sql(sql: str, params=None) -> tuple[str, tuple]:
    """Turn the sqlite-shaped reads Webclaw issues into PostgreSQL.

    Returns SQL that already uses ``%s`` placeholders.
    """
    text = sql.strip().rstrip(";")
    values = tuple(params or ())
    if _MASTER_ONE.match(text):
        return (
            "SELECT table_name AS name FROM information_schema.tables "
            "WHERE table_schema NOT IN ('pg_catalog', 'information_schema') "
            "AND table_name = %s",
            values,
        )
    if _MASTER_ALL.match(text):
        return (
            "SELECT table_name AS name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
            "ORDER BY table_name",
            (),
        )
    pragma = _PRAGMA.match(text)
    if pragma:
        table = pragma.group(1)
        if not _IDENT.match(table):
            raise ValueError("unsafe table name")
        return (
            "SELECT (ordinal_position - 1) AS cid, column_name AS name, "
            "data_type AS type, "
            "CASE WHEN is_nullable = 'NO' THEN 1 ELSE 0 END AS notnull, "
            "column_default AS dflt_value, 0 AS pk "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s "
            "ORDER BY ordinal_position",
            (table,),
        )
    if "?" in text:
        text = text.replace("?", "%s")
    return text, values


class PostgresSkillConnection:
    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql: str, params=None) -> Cursor:
        translated, values = translate_sql(sql, params)
        cur = self._raw.cursor()
        try:
            cur.execute(translated, values)
            rows = cur.fetchall() if cur.description else []
            columns = [d[0] for d in cur.description] if cur.description else []
        finally:
            cur.close()
        return Cursor(columns, rows)

    def close(self) -> None:
        self._raw.close()

    def commit(self) -> None:
        self._raw.commit()


def open_postgres() -> PostgresSkillConnection:
    """Open the ERPClaw Postgres database. Raises if it is not configured."""
    import psycopg2

    url = postgres_url_from(os_environ())
    if not url:
        raise RuntimeError("postgresql dialect is set but no connection URL is configured")
    raw = psycopg2.connect(url, connect_timeout=5)
    raw.autocommit = True
    return PostgresSkillConnection(raw)


def os_environ() -> dict:
    import os
    return os.environ


def postgres_reachable() -> bool:
    """True when a one-row probe succeeds. Never raises, never logs the URL."""
    try:
        conn = open_postgres()
    except Exception:
        return False
    try:
        row = conn.execute("SELECT 1").fetchone()
        return row is not None
    except Exception:
        return False
    finally:
        conn.close()
