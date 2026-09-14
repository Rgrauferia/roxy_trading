"""Disposable, loopback-only login QA; never included in the production image.

Run: python -m tools.roxy_home_login_preview
Open: http://127.0.0.1:8768/lista#hoy
Synthetic username: loginqa
Synthetic password: Local-QA-only-2026

By default this fixture is offline and inherits no provider credentials.
--voice-config opts into only Home official fixed-script TTS using a one-use 0600
file; --resume-data preserves a synthetic snapshot. Production is never edited.
Its cookie name is separate from other previews.
"""
from __future__ import annotations

import os
import json
import re
import secrets
import shutil
import tempfile
from pathlib import Path


def consume_voice_config(path: Path) -> dict[str, str]:
    """Read a one-use, owner-only Home TTS credential file; never echo values."""
    info = path.lstat()
    if path.is_symlink() or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("La configuración temporal de voz necesita permisos 0600.")
    values = json.loads(path.read_text())
    keys = {"ROXY_HOME_ELEVENLABS_API_KEY", "ROXY_HOME_ELEVENLABS_VOICE_ID", "ROXY_HOME_ELEVENLABS_MODEL_ID"}
    if not isinstance(values, dict) or set(values) != keys or not all(isinstance(v, str) and v.strip() for v in values.values()):
        raise ValueError("Se necesita únicamente la configuración de voz de Home.")
    if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", values[k]) for k in keys if not k.endswith("API_KEY")):
        raise ValueError("Identificador de voz no válido.")
    path.unlink()
    return values


def preview_transport(original_request, voice: dict[str, str]):
    """Keep the synthetic fixture offline except for its exact Home TTS voice."""
    import requests
    from roxy_os.home_tour import CHAPTERS, EXTRA_SCRIPTS, WORLD_SPEECH, speech_for
    scripts = [row["speech"] for row in CHAPTERS] + list(EXTRA_SCRIPTS.values()) + list(WORLD_SPEECH.values())
    scripts += [speech_for(f"fitness:{kind}:{index}") for kind in ("strength", "balance", "flexibility") for index in range(10)]
    allowed_text = {" ".join(text.split()) for text in scripts if text}
    endpoint = f"https://api.elevenlabs.io/v1/text-to-speech/{voice.get('ROXY_HOME_ELEVENLABS_VOICE_ID', '')}?output_format=mp3_44100_128"

    def request(session, method, url, **kwargs):
        body = kwargs.get("json") or {}
        if (voice and method.upper() == "POST" and url == endpoint
                and isinstance(body, dict) and body.get("text") in allowed_text
                and body.get("model_id") == voice["ROXY_HOME_ELEVENLABS_MODEL_ID"]):
            kwargs["allow_redirects"] = False
            return original_request(session, method, url, **kwargs)
        raise requests.ConnectionError("Esta prueba sólo permite los guiones fijos de la voz oficial de Home.")
    return request


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--voice-config", type=Path, help="One-use 0600 file containing only Home TTS configuration.")
    parser.add_argument("--resume-data", type=Path, help="Copy an existing synthetic preview snapshot without changing its source.")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use a loopback port between 1024 and 65535.")
    import requests
    import uvicorn

    voice = consume_voice_config(args.voice_config) if args.voice_config else {}

    original_directory = Path.cwd()
    # Existing values are discarded only in this disposable preview process.
    for key in list(os.environ):
        if key.startswith(("ROXY_", "FAL_")) or "OPENAI" in key or "ELEVENLABS" in key or key.endswith("_API_KEY"):
            os.environ.pop(key)
    os.environ.update(
        ROXY_HOME_API_KEY=secrets.token_urlsafe(32),
        ROXY_STATE_SYNC_USERS="login-qa",
        ROXY_HOME_RECIPE_IMAGE_GENERATION_ENABLED="0",
        ROXY_HOME_VIDEO_ENABLED="0",
        ROXY_HOME_RECIPE_VIDEO_ENABLED="0",
    )
    os.environ.update(voice)
    requests.sessions.Session.request = preview_transport(requests.sessions.Session.request, voice)
    with tempfile.TemporaryDirectory(prefix="roxy-login-qa-") as directory:
        try:
            if args.resume_data:
                if not (args.resume_data / "data/roxy_home_accounts.json").is_file():
                    raise ValueError("La copia de prueba no contiene su cuenta sintética.")
                shutil.copytree(args.resume_data, directory, dirs_exist_ok=True)
            os.chdir(directory)
            from roxy_os.home_accounts import HomeAccountStore
            from tools import roxy_home_service as service

            service.SESSION_COOKIE = "roxy_home_login_qa_session" + (f"_{args.port}" if args.port != 8768 else "")

            def local_cookie(response, value):
                # Only this loopback fixture uses a non-Secure cookie over HTTP.
                # Production continues using Secure=True in the real service.
                response.set_cookie(service.SESSION_COOKIE, value, httponly=True,
                                    samesite="strict", path="/", max_age=3600)

            service._set_session_cookie = local_cookie
            if not Path("data/roxy_home_accounts.json").exists():
                HomeAccountStore("data/roxy_home_accounts.json").bootstrap(
                    "login-qa", household_name="Hogar de prueba local",
                    username="loginqa", display_name="Prueba de acceso",
                    password="Local-QA-only-2026",
                )
            if voice:
                from dataclasses import replace
                original_voice_config = service._home_voice_config
                service._home_voice_config = lambda: replace(original_voice_config(), daily_requests=40, daily_characters=10000)
                print("Official Home voice enabled for fixed tutorial scripts only; other providers remain disabled.", flush=True)
            print(f"Disposable synthetic data only: {directory}", flush=True)
            print(f"Login QA: http://127.0.0.1:{args.port}/lista#hoy", flush=True)
            print("Synthetic login only: loginqa / Local-QA-only-2026", flush=True)
            uvicorn.run(service.app, host="127.0.0.1", port=args.port, access_log=False)
        finally:
            os.chdir(original_directory)


if __name__ == "__main__":
    main()
