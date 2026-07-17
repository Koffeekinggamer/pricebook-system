"""
Simple app login for Streamlit.

Credentials (first match wins):
  1. Streamlit secrets: st.secrets["auth"]["username"] + password or password_hash
  2. Environment: FAF_APP_USER / FAF_APP_PASSWORD
  3. Local defaults for single-store use (change these via secrets)

password_hash = sha256 hex of the password string (optional instead of plain password).
"""

from __future__ import annotations

import hashlib
import os
from typing import Optional, Tuple


# Fallback only if secrets/env are not set — change via .streamlit/secrets.toml
_DEFAULT_USER = "faf"
_DEFAULT_PASSWORD = "foothills2026"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_expected_credentials() -> Tuple[str, Optional[str], Optional[str]]:
    """
    Returns (username, plain_password_or_None, password_hash_or_None).
    Prefer hash when both are present.
    """
    # 1) Streamlit secrets
    try:
        import streamlit as st

        auth = st.secrets.get("auth", None)
        if auth:
            user = str(auth.get("username") or "").strip()
            pw = auth.get("password")
            ph = auth.get("password_hash")
            plain = str(pw) if pw is not None and str(pw) != "" else None
            hashed = str(ph).strip().lower() if ph else None
            if user and (plain or hashed):
                return user, plain, hashed
    except Exception:
        pass

    # 2) Environment
    user = (os.environ.get("FAF_APP_USER") or "").strip()
    plain = os.environ.get("FAF_APP_PASSWORD")
    hashed = (os.environ.get("FAF_APP_PASSWORD_HASH") or "").strip().lower() or None
    if user and (plain or hashed):
        return user, plain if plain else None, hashed

    # 3) Built-in single-user defaults
    return _DEFAULT_USER, _DEFAULT_PASSWORD, None


def check_login(username: str, password: str) -> bool:
    exp_user, exp_plain, exp_hash = get_expected_credentials()
    if not username or not password:
        return False
    if username.strip() != exp_user:
        return False
    if exp_hash:
        return _sha256(password) == exp_hash
    if exp_plain is not None:
        return password == exp_plain
    return False


def credentials_source_hint() -> str:
    try:
        import streamlit as st

        if st.secrets.get("auth"):
            return "secrets.toml"
    except Exception:
        pass
    if os.environ.get("FAF_APP_USER"):
        return "environment"
    return "default"
