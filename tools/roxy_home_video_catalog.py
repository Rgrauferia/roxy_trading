#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from roxy_os.home_video_actions import ACTION_LIBRARY_VERSION, ROXY_ACTION_CLIPS, action_prompt


def build_plan(price_per_clip: float) -> dict[str, object]:
    clips = [
        {
            "key": clip.key,
            "label": clip.label,
            "family": clip.family,
            "prompt": action_prompt(clip.key),
            "estimated_cost_usd": round(price_per_clip, 3),
        }
        for clip in ROXY_ACTION_CLIPS
    ]
    families: dict[str, int] = {}
    for clip in ROXY_ACTION_CLIPS:
        families[clip.family] = families.get(clip.family, 0) + 1
    return {
        "action_library_version": ACTION_LIBRARY_VERSION,
        "clip_count": len(clips),
        "families": families,
        "price_per_clip_usd": round(price_per_clip, 3),
        "estimated_total_usd": round(len(clips) * price_per_clip, 2),
        "clips": clips,
        "generation_started": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan seguro del catálogo audiovisual reutilizable de Roxy Home")
    parser.add_argument("--price-per-clip", type=float, default=0.102)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    if args.price_per_clip < 0:
        parser.error("--price-per-clip no puede ser negativo")
    plan = build_plan(args.price_per_clip)
    print(json.dumps(plan, ensure_ascii=False, indent=None if args.compact else 2, sort_keys=True))


if __name__ == "__main__":
    main()
