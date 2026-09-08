"""Local-only visual QA using disposable synthetic accounts; no provider keys.

Run as a module. This file is deliberately absent from Dockerfile.roxy-home.
"""
import os
import secrets
import tempfile
from pathlib import Path


def main():
    import uvicorn

    directory = Path(tempfile.mkdtemp(prefix="roxy-fitness-preview-"))
    os.chdir(directory)
    for key in list(os.environ):
        if key.startswith("ROXY_") or "OPENAI" in key or "ELEVENLABS" in key or key.endswith("_API_KEY"):
            os.environ.pop(key)
    os.environ.update(ROXY_HOME_API_KEY=secrets.token_urlsafe(32), ROXY_STATE_SYNC_USERS="fitness-preview",
                      ROXY_HOME_RECIPE_IMAGE_GENERATION_ENABLED="0", ROXY_HOME_RECIPE_VIDEO_ENABLED="0")
    from fastapi.responses import RedirectResponse
    from roxy_os.home_accounts import HomeAccountStore
    from tools import roxy_home_service as service

    member = HomeAccountStore("data/roxy_home_accounts.json").bootstrap(
        "fitness-preview", household_name="Vista previa local", username="fitness-preview",
        display_name="Prueba local", password=secrets.token_urlsafe(32))

    @service.app.get("/fitness-preview")
    def enter_preview():
        response = RedirectResponse("/lista#ejercicio", status_code=303)
        response.set_cookie(service.SESSION_COOKIE, service._member_session_cookie(member), httponly=True, samesite="strict")
        response.headers["Cache-Control"] = "no-store"
        return response

    print(f"Synthetic Home preview only: {directory}", flush=True)
    uvicorn.run(service.app, host="127.0.0.1", port=8767, access_log=False)


if __name__ == "__main__":
    main()
