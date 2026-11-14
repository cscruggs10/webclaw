"""Create the first dashboard admin from the environment. Idempotent.

The password is read from ``ADMIN_PASSWORD`` and stored only as a hash.
Nothing in this module prints the password, the JWT secret, or the database URL.
A later restart does not change an existing password.
"""
import os
import sys
import uuid

import db
from auth.jwt_utils import get_signing_secret
from auth.passwords import hash_password, validate_password_strength


def _user_count(conn) -> int:
    row = conn.execute("SELECT COUNT(*) FROM webclaw_user").fetchone()
    return row[0] if isinstance(row, tuple) else row[0]


def ensure_admin() -> None:
    """Ensure a JWT secret and, when asked, the first admin user.

    Production with zero users and no ``ADMIN_EMAIL`` refuses to serve, so a
    public ``/setup`` page is not left open on the books. Development (and the
    test suite) keeps the setup page.
    """
    # Login compares a lowercased email, so store it that way.
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")
    full_name = os.environ.get("ADMIN_NAME", "").strip()
    is_prod = os.environ.get("WEBCLAW_ENV", "production").lower() != "development"

    secret = os.environ.get("WEBCLAW_JWT_SECRET", "").strip()
    if secret and len(secret) < 32:
        raise SystemExit("WEBCLAW_JWT_SECRET must be at least 32 characters")

    if email and not password:
        raise SystemExit("ADMIN_EMAIL is set but ADMIN_PASSWORD is empty")
    if password and not email:
        raise SystemExit("ADMIN_PASSWORD is set but ADMIN_EMAIL is empty")
    if password:
        problem = validate_password_strength(password)
        if problem:
            raise SystemExit(f"ADMIN_PASSWORD is not acceptable: {problem}")

    conn = db.get_connection()
    try:
        # Touch the secret now so a generated one is persisted before traffic,
        # or the env secret replaces a previously generated one.
        get_signing_secret(conn)
        count = _user_count(conn)
        if not email:
            if is_prod and count == 0:
                raise SystemExit(
                    "Refusing to start in production with no dashboard user. "
                    "Set ADMIN_EMAIL and ADMIN_PASSWORD."
                )
            if count == 0:
                print("webclaw: no ADMIN_EMAIL; dashboard setup page is open", flush=True)
            return
        if count > 0:
            print("webclaw: dashboard user already present; password unchanged", flush=True)
            return

        user_id = str(uuid.uuid4())
        username = email.split("@", 1)[0] or "admin"
        conn.execute(
            """INSERT INTO webclaw_user (id, username, email, full_name, password_hash, status)
               VALUES (?, ?, ?, ?, ?, 'active')""",
            (user_id, username, email, full_name or username, hash_password(password)),
        )
        role = conn.execute(
            "SELECT id FROM webclaw_role WHERE name = 'System Manager'"
        ).fetchone()
        if not role:
            role_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO webclaw_role (id, name, description, is_system) "
                "VALUES (?, 'System Manager', 'Full system access', 1)",
                (role_id,),
            )
        else:
            role_id = role[0] if isinstance(role, tuple) else role["id"]
        conn.execute(
            "INSERT INTO webclaw_user_role (id, user_id, role_id) VALUES (?, ?, ?)",
            (str(uuid.uuid4()), user_id, role_id),
        )
        conn.commit()
        print("webclaw: dashboard admin created from ADMIN_EMAIL", flush=True)
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        ensure_admin()
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        raise
