from datetime import timezone
from pathlib import Path

from roxy_time import utc_now, utc_now_naive, utc_now_naive_iso


def test_roxy_utc_clock_preserves_aware_and_legacy_contracts():
    aware = utc_now()
    naive = utc_now_naive()
    encoded = utc_now_naive_iso()

    assert aware.tzinfo == timezone.utc
    assert naive.tzinfo is None
    assert "+" not in encoded
    assert "Z" not in encoded


def test_production_python_sources_do_not_use_deprecated_utcnow():
    root = Path(__file__).resolve().parents[1]
    offenders = []
    excluded = {".venv", ".git", "tests", "training_videos", "output"}
    for path in root.rglob("*.py"):
        if any(part in excluded for part in path.relative_to(root).parts):
            continue
        if "datetime.utcnow()" in path.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(str(path.relative_to(root)))

    assert offenders == []
