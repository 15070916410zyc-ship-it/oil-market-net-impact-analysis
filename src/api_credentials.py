"""Per-request API credentials and encrypted browser persistence helpers."""

from __future__ import annotations

from contextvars import ContextVar
import json
from typing import Any, Mapping

from cryptography.fernet import Fernet, InvalidToken


ALLOWED_API_KEYS = ("FRED_API_KEY", "EIA_API_KEY")
_SESSION_API_KEYS: ContextVar[dict[str, str]] = ContextVar(
    "net_impact_session_api_keys",
    default={},
)
_ALLOW_SHARED_API_FALLBACK: ContextVar[bool] = ContextVar(
    "net_impact_allow_shared_api_fallback",
    default=True,
)


def _normalise_api_keys(values: Mapping[str, Any] | None) -> dict[str, str]:
    """Return non-empty supported API keys without retaining caller mappings."""
    source = values or {}
    return {
        key: str(source.get(key, "") or "").strip()
        for key in ALLOWED_API_KEYS
        if str(source.get(key, "") or "").strip()
    }


def set_session_api_keys(
    values: Mapping[str, Any] | None,
    *,
    allow_shared_fallback: bool = True,
) -> None:
    """Activate API keys for the current Streamlit request context only."""
    _SESSION_API_KEYS.set(_normalise_api_keys(values))
    _ALLOW_SHARED_API_FALLBACK.set(bool(allow_shared_fallback))


def clear_session_api_keys() -> None:
    """Clear request-local API keys and restore local-software fallback behavior."""
    _SESSION_API_KEYS.set({})
    _ALLOW_SHARED_API_FALLBACK.set(True)


def get_session_api_key(name: str) -> str:
    """Return one API key active in the current request context."""
    if name not in ALLOWED_API_KEYS:
        return ""
    return _SESSION_API_KEYS.get().get(name, "")


def shared_api_fallback_allowed() -> bool:
    """Return whether process and API.env credentials may be consulted."""
    return _ALLOW_SHARED_API_FALLBACK.get()


def encrypt_api_keys(values: Mapping[str, Any], encryption_key: str) -> str:
    """Encrypt supported API keys for storage in one visitor's browser cookie."""
    payload = json.dumps(
        {"version": 1, "keys": _normalise_api_keys(values)},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return Fernet(str(encryption_key).strip()).encrypt(payload).decode("ascii")


def decrypt_api_keys(token: str, encryption_key: str) -> dict[str, str]:
    """Decrypt a browser cookie, ignoring missing, malformed, or tampered values."""
    if not str(token or "").strip() or not str(encryption_key or "").strip():
        return {}
    try:
        payload = Fernet(str(encryption_key).strip()).decrypt(str(token).strip())
        decoded = json.loads(payload.decode("utf-8"))
    except (InvalidToken, ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    if not isinstance(decoded, dict) or decoded.get("version") != 1:
        return {}
    keys = decoded.get("keys")
    return _normalise_api_keys(keys if isinstance(keys, dict) else {})
