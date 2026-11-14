"""Guards for the Railway boot path. No network and no secrets in output."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pg_skill_db import translate_sql
from runtime_paths import apply_database_env, redact


def test_database_url_selects_postgres_without_leaking():
    secret = "s3cr3t-token"
    env, notes = apply_database_env({
        "DATABASE_URL": f"postgres://erpclaw:{secret}@db.internal:5432/erpclaw",
    })
    assert env["ERPCLAW_DB_DIALECT"] == "postgresql"
    assert env["ERPCLAW_DB_URL"].startswith("postgresql://")
    assert env["ERPCLAW_DB_PATH"] == env["ERPCLAW_DB_URL"]
    blob = "\n".join(notes)
    assert secret not in blob
    assert "postgresql" in blob


def test_missing_url_falls_back_to_sqlite_and_says_so():
    env, notes = apply_database_env({"ERPCLAW_HOME": "/data/erpclaw"})
    assert env["ERPCLAW_DB_DIALECT"] == "sqlite"
    assert env["ERPCLAW_DB_PATH"] == "/data/erpclaw/data.sqlite"
    assert "sqlite fallback" in notes[0]


def test_postgres_dialect_without_url_refuses():
    with pytest.raises(SystemExit):
        apply_database_env({"ERPCLAW_DB_DIALECT": "postgresql"})


def test_redact_strips_url():
    raw = "failed for postgresql://erpclaw:s3cr3t@db:5432/erpclaw"
    cleaned = redact(raw)
    assert "s3cr3t" not in cleaned
    assert "postgresql://[redacted]" in cleaned


def test_translate_sqlite_master_and_pragma():
    sql, params = translate_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        ("company",),
    )
    assert "information_schema" in sql
    assert params == ("company",)
    sql, params = translate_sql("PRAGMA table_info('account')")
    assert "information_schema.columns" in sql
    assert params == ("account",)
    sql, params = translate_sql("SELECT id FROM company WHERE id = ?", ("abc",))
    assert "%s" in sql
    assert "?" not in sql
    assert params == ("abc",)


def test_admin_password_is_not_reset(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WEBCLAW_DB_PATH", str(tmp_path / "webclaw.sqlite"))
    monkeypatch.setenv("WEBCLAW_ENV", "production")
    monkeypatch.setenv("ADMIN_EMAIL", "corey@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "Local-Test-1")
    monkeypatch.setenv("WEBCLAW_JWT_SECRET", "local-dev-jwt-secret-not-for-production-00")

    import db
    db._tables_initialized = False
    from bootstrap_admin import ensure_admin

    ensure_admin()
    conn = db.get_connection()
    first = conn.execute("SELECT password_hash FROM webclaw_user").fetchone()[0]
    conn.execute("UPDATE webclaw_user SET password_hash = ?", ("replaced-hash",))
    conn.commit()
    conn.close()

    ensure_admin()
    conn = db.get_connection()
    second = conn.execute("SELECT password_hash FROM webclaw_user").fetchone()[0]
    conn.close()
    assert second == "replaced-hash"
    assert second != first
    captured = capsys.readouterr()
    assert "Local-Test-1" not in captured.out
    assert "Local-Test-1" not in captured.err
    assert "local-dev-jwt-secret" not in captured.out


def test_production_without_admin_refuses(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBCLAW_DB_PATH", str(tmp_path / "empty.sqlite"))
    monkeypatch.setenv("WEBCLAW_ENV", "production")
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("WEBCLAW_JWT_SECRET", raising=False)
    import db
    db._tables_initialized = False
    from bootstrap_admin import ensure_admin
    with pytest.raises(SystemExit):
        ensure_admin()


def test_volume_upload_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "volume")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    import storage
    saved = storage.save_upload("title scan.pdf", b"scan-bytes", "application/pdf")
    data, content_type, filename = storage.open_upload(saved["key"])
    assert data == b"scan-bytes"
    assert content_type == "application/pdf"
    assert filename.endswith(".pdf")
    assert saved["backend"] == "volume"
    assert "s3cr3t" not in saved["url"]
