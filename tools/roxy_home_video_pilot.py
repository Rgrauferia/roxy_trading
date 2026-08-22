#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from roxy_os.home_recipe_videos import HomeRecipeVideoConfig, HomeRecipeVideoStore
from roxy_os.home_video_actions import ACTION_BY_KEY, action_prompt


IMAGE_MODEL = "fal-ai/minimax/image-01/subject-reference"
VIDEO_MODEL = "fal-ai/minimax/hailuo-02/standard/image-to-video"
PILOT_ACTIONS = ("mix_dry", "knead_dough", "shake_cocktail")
IMAGE_PRICE_USD = 0.01
VIDEO_SECONDS = 6
VIDEO_512_PRICE_PER_SECOND_USD = 0.017
ESTIMATED_PILOT_COST_USD = round(
    len(PILOT_ACTIONS) * (IMAGE_PRICE_USD + VIDEO_SECONDS * VIDEO_512_PRICE_PER_SECOND_USD), 3
)


def _queue_url(model: str) -> str:
    return f"https://queue.fal.run/{model}"


def _trusted_url(value: Any, *, queue: bool = False) -> str:
    url = str(value or "")
    parsed = urlparse(url)
    host = str(parsed.hostname or "").lower()
    allowed = host == "queue.fal.run" if queue else host == "fal.media" or host.endswith(".fal.media")
    if parsed.scheme != "https" or not allowed:
        raise ValueError("fal.ai devolvió una URL no permitida.")
    return url


def _submit(session: Any, key: str, model: str, payload: dict[str, Any]) -> dict[str, str]:
    base = _queue_url(model)
    response = session.post(
        base,
        headers={"Authorization": f"Key {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=45,
    )
    response.raise_for_status()
    body = response.json()
    request_id = str(body.get("request_id") or "").strip()
    if not request_id:
        raise RuntimeError("fal.ai no devolvió request_id.")
    return {
        "request_id": request_id,
        "status_url": _trusted_url(body.get("status_url") or f"{base}/requests/{request_id}/status", queue=True),
        "response_url": _trusted_url(body.get("response_url") or f"{base}/requests/{request_id}", queue=True),
    }


def _wait_result(session: Any, key: str, job: dict[str, str], *, timeout_seconds: int = 900) -> dict[str, Any]:
    headers = {"Authorization": f"Key {key}"}
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = session.get(job["status_url"], headers=headers, timeout=30)
        response.raise_for_status()
        status = str(response.json().get("status") or "").upper()
        if status in {"COMPLETED", "READY"}:
            result = session.get(job["response_url"], headers=headers, timeout=30)
            result.raise_for_status()
            return result.json()
        if status in {"FAILED", "CANCELLED"}:
            raise RuntimeError("La generación piloto no terminó correctamente.")
        time.sleep(5)
    raise TimeoutError("La generación piloto superó el tiempo máximo.")


def _download(session: Any, url: str, destination: Path) -> int:
    url = _trusted_url(url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    response = session.get(url, stream=True, timeout=(15, 180))
    response.raise_for_status()
    maximum = 100 * 1024 * 1024
    total = 0
    handle, temporary = tempfile.mkstemp(prefix=".roxy-pilot-", suffix=destination.suffix, dir=str(destination.parent))
    try:
        with os.fdopen(handle, "wb") as stream:
            for chunk in response.iter_content(256 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > maximum:
                    raise ValueError("El archivo piloto supera 100 MB.")
                stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        if total < 1_024:
            raise ValueError("El proveedor devolvió un archivo piloto vacío.")
        os.replace(temporary, destination)
        return total
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def pilot_plan(maximum_usd: float) -> dict[str, Any]:
    return {
        "actions": [ACTION_BY_KEY[key].label for key in PILOT_ACTIONS],
        "image_model": IMAGE_MODEL,
        "video_model": VIDEO_MODEL,
        "resolution": "512P",
        "seconds_per_clip": VIDEO_SECONDS,
        "estimated_cost_usd": ESTIMATED_PILOT_COST_USD,
        "maximum_authorized_usd": round(maximum_usd, 2),
        "within_budget": ESTIMATED_PILOT_COST_USD <= maximum_usd,
        "automatic_retries": 0,
    }


def run_pilot(maximum_usd: float, *, session: Any = requests) -> dict[str, Any]:
    plan = pilot_plan(maximum_usd)
    if maximum_usd <= 0 or not plan["within_budget"]:
        raise ValueError("El piloto supera el presupuesto autorizado.")
    config = HomeRecipeVideoConfig.from_env()
    key = str(os.getenv("ROXY_HOME_VIDEO_FAL_KEY") or "").strip()
    if not key:
        raise RuntimeError("Falta ROXY_HOME_VIDEO_FAL_KEY en el servidor Home.")
    owner = str(os.getenv("ROXY_HOME_VIDEO_PILOT_OWNER", "local_user") or "local_user")
    store = HomeRecipeVideoStore(os.getenv("ROXY_HOME_VIDEO_LIBRARY_PATH", "data/roxy_home_recipe_video_library.json"))
    pilot_id = f"pilot-{int(time.time())}"
    directory = config.media_dir / pilot_id
    completed: list[dict[str, Any]] = []
    for index, action_key in enumerate(PILOT_ACTIONS, start=1):
        still_prompt = (
            action_prompt(action_key)
            + " Create a single realistic vertical first frame. Her face and the exact starting position of both hands, "
            "tool, container, and generic ingredients must all be visible and ready for the action."
        )
        image_job = _submit(
            session,
            key,
            IMAGE_MODEL,
            {
                "prompt": still_prompt,
                "image_url": config.roxy_reference_url,
                "aspect_ratio": "9:16",
                "num_images": 1,
                "prompt_optimizer": False,
            },
        )
        image_result = _wait_result(session, key, image_job)
        images = image_result.get("images") or (image_result.get("data") or {}).get("images") or []
        image_url = _trusted_url((images[0] if images else {}).get("url"))
        video_job = _submit(
            session,
            key,
            VIDEO_MODEL,
            {
                "prompt": (
                    f"Roxy continuously and clearly {ACTION_BY_KEY[action_key].direction}. Preserve her exact face, "
                    "green apron, kitchen, tools, and ingredients from the first frame. Natural practical motion, correct "
                    "hands, steady camera, no cuts, no text, no logos, no new people."
                ),
                "image_url": image_url,
                "duration": "6",
                "resolution": "512P",
                "prompt_optimizer": False,
            },
        )
        video_result = _wait_result(session, key, video_job)
        video = video_result.get("video") or (video_result.get("data") or {}).get("video") or {}
        media_path = directory / f"{index:02d}-{action_key}.mp4"
        byte_count = _download(session, str(video.get("url") or ""), media_path)
        completed.append(
            {
                "action_key": action_key,
                "provider_request_id": video_job["request_id"],
                "media_path": str(media_path.resolve()),
                "bytes": byte_count,
            }
        )
    record = store.register_action_pilot(
        owner,
        completed,
        provider="fal.ai economical Roxy pilot",
        model=f"{IMAGE_MODEL} + {VIDEO_MODEL} 512P",
        estimated_cost_usd=ESTIMATED_PILOT_COST_USD,
    )
    return {"status": "REVIEW", "video_id": record["id"], "owner": owner, "plan": plan}


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera tres clips piloto reutilizables de Roxy dentro de un límite rígido")
    parser.add_argument("--confirm-max-usd", type=float)
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args()
    maximum = float(args.confirm_max_usd or 0)
    if args.plan:
        print(json.dumps(pilot_plan(maximum or 1.0), ensure_ascii=False, indent=2, sort_keys=True))
        return
    if args.confirm_max_usd is None:
        parser.error("La generación requiere --confirm-max-usd")
    print(json.dumps(run_pilot(maximum), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
