#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import secrets
from datetime import datetime, timezone
from typing import Sequence

import streamlit_app as app


def reset_local_password(username: str, password: str, confirmation: str) -> tuple[bool, str]:
    clean_username = app.text_display(username).strip().lower()
    if not clean_username:
        return False, "Username requerido."
    if password != confirmation:
        return False, "La confirmacion no coincide."
    if len(password or "") < app.ROXY_PASSWORD_MIN_LENGTH:
        return False, f"La contrasena debe tener al menos {app.ROXY_PASSWORD_MIN_LENGTH} caracteres."
    data = app.roxy_load_users()
    profile = data.get("users", {}).get(clean_username)
    if not isinstance(profile, dict):
        return False, "Cuenta local no encontrada."
    salt = secrets.token_hex(16)
    profile["password_salt"] = salt
    profile["password_hash"] = app.roxy_hash_password(password, salt, app.ROXY_PASSWORD_ITERATIONS)
    profile["password_iterations"] = app.ROXY_PASSWORD_ITERATIONS
    profile["password_reset_at"] = datetime.now(timezone.utc).isoformat()
    profile.pop("session_token_hash", None)
    profile.pop("session_token", None)
    app.roxy_save_users(data)
    try:
        app.roxy_auth_attempt_guard().clear(clean_username)
    except Exception:
        pass
    return True, "Contrasena restablecida; todas las sesiones recordadas fueron revocadas."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Restablece una contrasena local de Roxy sin exponerla en argumentos o logs."
    )
    parser.add_argument("username", help="Username local exacto")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    password = getpass.getpass("Nueva contrasena: ")
    confirmation = getpass.getpass("Confirmar nueva contrasena: ")
    ok, message = reset_local_password(args.username, password, confirmation)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
