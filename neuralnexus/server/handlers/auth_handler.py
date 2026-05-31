"""
handlers/auth_handler.py
------------------------
Business logic for user authentication in NeuralNexus.
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional, Tuple

DB_PATH: str = os.environ.get("DB_PATH", "lms.db")

from security.token_manager import session_manager
from database.db_methods import validate_user


def _generate_token_expiry() -> str:
    """Return a session expiry timestamp 2 hours from now (YYYYMMDDHHmmss)."""
    return (datetime.now() + timedelta(hours=2)).strftime("%Y%m%d%H%M%S")


def login(
    email: str,
    password: str,
    role: str,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Authenticate a user and return an AES-encrypted session token.

    Returns:
        (token, None)   on success
        (None, error)   on failure
    """
    with sqlite3.connect(DB_PATH) as conn:
        is_valid, _courses, user_id = validate_user(conn, email, password, role)

    if is_valid:
        token = session_manager.encrypt(f"{user_id}|{role}|{_generate_token_expiry()}")
        return token, None
    return None, "Invalid Credentials"


# Alias used by security/access_control.py (legacy name)
generateExpiry = _generate_token_expiry
