"""JWT token creation and verification (PyJWT, HS256)."""
import hashlib
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import jwt

ACCESS_TOKEN_EXPIRY = timedelta(minutes=15)
REFRESH_TOKEN_EXPIRY = timedelta(days=7)
ALGORITHM = "HS256"


def get_signing_secret(conn: sqlite3.Connection) -> str:
    """Get the JWT signing secret.

    ``WEBCLAW_JWT_SECRET`` wins when it is set, and is stored so later
    processes without the variable still match. Otherwise the value already
    in ``webclaw_config`` is used, or a new random secret is stored.
    The secret itself is never logged.
    """
    row = conn.execute("SELECT value FROM webclaw_config WHERE key = 'jwt_secret'").fetchone()
    stored = None
    if row:
        stored = row[0] if isinstance(row, tuple) else row["value"]
    env_secret = os.environ.get("WEBCLAW_JWT_SECRET", "").strip()
    if env_secret:
        if stored != env_secret:
            if stored:
                conn.execute(
                    "UPDATE webclaw_config SET value = ?, updated_at = datetime('now') WHERE key = 'jwt_secret'",
                    (env_secret,),
                )
            else:
                conn.execute(
                    "INSERT INTO webclaw_config (key, value) VALUES ('jwt_secret', ?)",
                    (env_secret,),
                )
            conn.commit()
        return env_secret
    if stored:
        return stored
    secret = secrets.token_hex(32)  # 256-bit
    conn.execute(
        "INSERT INTO webclaw_config (key, value) VALUES ('jwt_secret', ?)", (secret,)
    )
    conn.commit()
    return secret


def create_access_token(user_id: str, email: str, secret: str) -> str:
    """Create a short-lived access token (15 min)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "iat": now,
        "exp": now + ACCESS_TOKEN_EXPIRY,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def create_refresh_token(user_id: str, secret: str) -> tuple[str, str]:
    """Create a refresh token (7 day). Returns (raw_token, token_hash)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + REFRESH_TOKEN_EXPIRY,
        "jti": str(uuid.uuid4()),
    }
    raw_token = jwt.encode(payload, secret, algorithm=ALGORITHM)
    token_hash = hash_token(raw_token)
    return raw_token, token_hash


def verify_token(token: str, secret: str, expected_type: str = "access") -> dict | None:
    """Verify and decode a JWT token. Returns payload or None."""
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type:
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def hash_token(token: str) -> str:
    """SHA-256 hash of a token for DB storage."""
    return hashlib.sha256(token.encode()).hexdigest()
