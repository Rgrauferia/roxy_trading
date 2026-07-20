from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from durable_storage import atomic_write_text


VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}
MATERIAL_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".heic",
    ".txt",
    ".csv",
    ".tsv",
    ".log",
    ".doc",
    ".docx",
    ".odt",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
}
DEFAULT_SCAN_KEYWORDS = (
    "roxy",
    "trading",
    "trade",
    "masterclass",
    "master class",
    "clase",
    "trimestral",
    "refuerzo",
    "check list",
    "checklist",
    "negociable",
    "negociables",
    "patron",
    "imparable",
    "media",
    "medias",
    "timing",
    "timinng",
    "movil",
    "moviles",
    "sma",
    "ema",
    "salto",
    "canal",
    "lateralidad",
    "lateralidades",
    "lateral",
    "opcion",
    "opciones",
    "accion",
    "acciones",
    "soporte",
    "fed",
    "webull",
    "classroom",
    "operativa",
    "lecture",
    "crypto",
    "bolsa",
    "invest",
    "benchmarking",
    "cointegration",
    "economic",
    "economy",
    "cycle",
    "fomc",
    "monetary",
    "fiscal",
    "liquidity",
    "vwap",
    "dark pool",
    "dark pools",
    "market",
    "sentiment",
    "valuation",
    "fundamental",
    "ratio",
    "hedging",
    "index",
    "indexes",
    "exchange",
    "ecn",
    "router",
    "latency",
    "short squeeze",
    "pair trading",
    "trend analysis",
    "trading technique",
    "risk management",
    "money management",
    "expectancy",
    "educated betting",
    "psychology",
    "loss aversion",
    "anchoring",
    "confirmation bias",
    "broker",
    "orders",
    "order types",
    "level1",
    "level2",
    "time and sales",
    "financial statement",
    "growth",
    "value companies",
    "ddm",
    "strategy types",
    "gameplan",
    "reports",
    "indicators",
)
SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    "training_videos",
    "output",
    "logs",
    "db",
    "analyzed_videos",
    "archived_videos",
    "videos_analizados",
    "roxy_videos_analizados",
    "roxyvideosanalizados",
    "roxy_trading_snapshot_20260610_154139",
    "roxy_trading_snapshot_20260610_154149",
    "output_archive",
    "MacArchive",
    "macarchive",
    "RoxyEnterprise",
    "roxyenterprise",
}
PARTIAL_DOWNLOAD_SUFFIXES = (".download", ".crdownload", ".part", ".tmp")
NON_STUDY_FILE_PATTERNS = (
    "requirements",
    "secrets_scan",
    "roxy_audit",
    "weekly_report",
    "watchlist_",
    "last_sent",
    "latest_alert",
    "top_picks",
    "runtime_backup",
    "output_maintenance",
    "ma_daily_report",
    "ma_live_report",
    "ma_confluence_report",
    "options_report",
    "roxy_ai_brief",
    "roxy_status",
    "roxy_learning_journal",
    "roxy_realtime_check",
    "latest_project_snapshot",
    "standard_sample",
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str, fallback: str = "video") -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return (text or fallback)[:90]


def run_command(args: list[str], *, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        timeout_text = stderr or f"timeout after {timeout}s"
        return subprocess.CompletedProcess(args, 124, stdout, timeout_text)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def default_sources() -> list[Path]:
    env_sources = os.environ.get("ROXY_VIDEO_SOURCES", "")
    if env_sources.strip():
        return [Path(item).expanduser() for item in env_sources.split(os.pathsep) if item.strip()]
    home = Path.home()
    return [
        home / "Downloads",
        home / "Movies",
        home / "Desktop",
        home / "Documents" / "Roxy trading",
        home / "Documents" / "Roxy Trading",
    ]


def configured_archive_dir(env: dict[str, str] | None = None) -> Path | None:
    values = env if env is not None else os.environ
    raw = str(values.get("ROXY_VIDEO_ARCHIVE_DIR") or "").strip()
    return Path(raw).expanduser() if raw else None


def source_allows_all(source: Path) -> bool:
    source_text = str(source).lower()
    return "roxy" in source_text or "trading" in source_text


def normalized_keyword_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def should_skip_dir(name: str) -> bool:
    lower = name.lower()
    return (
        lower in SKIP_DIR_NAMES
        or lower.startswith(".")
        or lower.startswith("roxy_trading_snapshot")
        or lower.endswith(PARTIAL_DOWNLOAD_SUFFIXES)
    )


def looks_like_learning_video(path: Path, *, allow_all: bool = False) -> bool:
    if is_partial_download_path(path):
        return False
    if path.name.startswith("._"):
        return False
    if path.suffix.lower() not in VIDEO_EXTENSIONS:
        return False
    if allow_all:
        return True
    haystack = normalized_keyword_text(f"{path.parent} {path.stem}")
    return any(normalized_keyword_text(keyword) in haystack for keyword in DEFAULT_SCAN_KEYWORDS)


def looks_like_learning_material(path: Path, *, allow_all: bool = False) -> bool:
    if is_partial_download_path(path):
        return False
    if path.suffix.lower() not in MATERIAL_EXTENSIONS:
        return False
    if path.name.startswith("~$") or path.name.startswith("._"):
        return False
    stem = path.stem.lower()
    if any(pattern in stem for pattern in NON_STUDY_FILE_PATTERNS):
        return False
    if allow_all:
        return True
    haystack = normalized_keyword_text(f"{path.parent} {path.stem}")
    return any(normalized_keyword_text(keyword) in haystack for keyword in DEFAULT_SCAN_KEYWORDS)


def is_partial_download_path(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    for part in parts:
        if part.endswith(PARTIAL_DOWNLOAD_SUFFIXES):
            return True
        if any(f"{suffix}." in part for suffix in PARTIAL_DOWNLOAD_SUFFIXES):
            return True
    return False


def safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return 0.0


def iter_video_files(sources: list[Path], *, max_depth: int = 4) -> list[Path]:
    found: dict[str, Path] = {}
    for source in sources:
        source = source.expanduser()
        if not source.exists():
            continue
        allow_all = source_allows_all(source)
        root_depth = len(source.parts)
        for current_root, dirnames, filenames in os.walk(source):
            current = Path(current_root)
            depth = len(current.parts) - root_depth
            dirnames[:] = [
                name
                for name in dirnames
                if not should_skip_dir(name) and depth < max_depth
            ]
            for filename in filenames:
                candidate = current / filename
                if looks_like_learning_video(candidate, allow_all=allow_all):
                    try:
                        resolved = candidate.resolve(strict=True)
                    except FileNotFoundError:
                        continue
                    found[str(resolved)] = resolved
    return sorted(found.values(), key=safe_mtime, reverse=True)


def iter_material_files(sources: list[Path], *, max_depth: int = 4) -> list[Path]:
    found: dict[str, Path] = {}
    for source in sources:
        source = source.expanduser()
        if not source.exists():
            continue
        allow_all = source_allows_all(source)
        root_depth = len(source.parts)
        for current_root, dirnames, filenames in os.walk(source):
            current = Path(current_root)
            depth = len(current.parts) - root_depth
            dirnames[:] = [
                name
                for name in dirnames
                if not should_skip_dir(name) and depth < max_depth
            ]
            for filename in filenames:
                candidate = current / filename
                if looks_like_learning_material(candidate, allow_all=allow_all):
                    try:
                        resolved = candidate.resolve(strict=True)
                    except FileNotFoundError:
                        continue
                    found[str(resolved)] = resolved
    return sorted(found.values(), key=safe_mtime, reverse=True)


def file_identity(path: Path) -> dict[str, Any]:
    stat = path.stat()
    stable = f"{path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}"
    return {
        "path": str(path.resolve()),
        "size_bytes": stat.st_size,
        "mtime": int(stat.st_mtime),
        "fingerprint": hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16],
    }


def output_dir_for(path: Path, identity: dict[str, Any], out_root: Path) -> Path:
    return out_root / f"{slugify(path.stem)}_{identity['fingerprint']}"


def ffprobe_metadata(path: Path) -> dict[str, Any]:
    if not command_exists("ffprobe"):
        return {"error": "ffprobe no instalado"}
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    proc = run_command(cmd, timeout=60)
    if proc.returncode != 0:
        return {"error": proc.stderr.strip() or "ffprobe fallo"}
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {"error": "ffprobe devolvio JSON invalido"}
    fmt = data.get("format") or {}
    duration = None
    try:
        duration = float(fmt.get("duration")) if fmt.get("duration") is not None else None
    except (TypeError, ValueError):
        duration = None
    video_stream = next((item for item in data.get("streams", []) if item.get("codec_type") == "video"), {})
    audio_stream = next((item for item in data.get("streams", []) if item.get("codec_type") == "audio"), {})
    return {
        "duration_seconds": duration,
        "duration_minutes": round(duration / 60.0, 2) if duration else None,
        "size_bytes": int(fmt.get("size") or 0) if str(fmt.get("size") or "").isdigit() else None,
        "bit_rate": fmt.get("bit_rate"),
        "video_codec": video_stream.get("codec_name"),
        "audio_codec": audio_stream.get("codec_name"),
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "avg_frame_rate": video_stream.get("avg_frame_rate"),
    }


def extract_audio(path: Path, audio_dir: Path, slug: str, *, force: bool = False, timeout: int = 900) -> Path | None:
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / f"{slug}.m4a"
    if audio_path.exists() and not force:
        return audio_path
    if not command_exists("ffmpeg"):
        return None
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "32k",
        str(audio_path),
    ]
    proc = run_command(cmd, timeout=timeout)
    if proc.returncode != 0:
        return None
    return audio_path


def extract_frames(
    path: Path,
    frames_dir: Path,
    *,
    every_seconds: int = 300,
    force: bool = False,
    timeout: int = 900,
) -> list[Path]:
    frames_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(frames_dir.glob("frame_*.jpg"))
    if existing and not force:
        return existing
    if not command_exists("ffmpeg"):
        return []
    for old in existing:
        old.unlink(missing_ok=True)
    metadata = ffprobe_metadata(path)
    duration_seconds = float(metadata.get("duration_seconds") or 0.0)
    if duration_seconds <= 0:
        sample_points = [30.0]
    else:
        interval = max(180, int(every_seconds))
        sample_count = max(1, min(12, int(duration_seconds // interval) + 1))
        if sample_count == 1:
            sample_points = [max(5.0, min(duration_seconds * 0.5, duration_seconds - 1))]
        else:
            sample_points = [
                max(5.0, min(duration_seconds - 1, (duration_seconds * (idx + 1)) / (sample_count + 1)))
                for idx in range(sample_count)
            ]
    per_frame_timeout = max(15, min(int(timeout), 45))
    for idx, timestamp in enumerate(sample_points, start=1):
        target = frames_dir / f"frame_{idx:03d}.jpg"
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{timestamp:.2f}",
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-vf",
            "scale=1366:-1",
            "-q:v",
            "3",
            str(target),
        ]
        proc = run_command(cmd, timeout=per_frame_timeout)
        if proc.returncode != 0:
            target.unlink(missing_ok=True)
    return sorted(frames_dir.glob("frame_*.jpg"))


def ocr_frames(frames: list[Path], ocr_dir: Path, *, force: bool = False) -> list[Path]:
    ocr_dir.mkdir(parents=True, exist_ok=True)
    if not command_exists("tesseract"):
        return []
    outputs: list[Path] = []
    for frame in frames:
        txt_path = ocr_dir / f"{frame.stem}.txt"
        if txt_path.exists() and not force:
            outputs.append(txt_path)
            continue
        base = ocr_dir / frame.stem
        proc = run_command(["tesseract", str(frame), str(base), "-l", "eng+spa", "--psm", "6"], timeout=120)
        if proc.returncode == 0 and txt_path.exists():
            outputs.append(txt_path)
    return sorted(outputs)


def read_ocr_text(ocr_files: list[Path]) -> str:
    sections = []
    for txt in ocr_files:
        body = txt.read_text(errors="ignore").strip()
        if body:
            sections.append(f"--- {txt.stem} ---\n{body}")
    return "\n\n".join(sections)


def transcribe_audio(
    audio_path: Path | None,
    transcript_dir: Path,
    *,
    enabled: bool = False,
    model_size: str = "tiny",
    language: str = "es",
    force: bool = False,
) -> Path | None:
    if not enabled or audio_path is None or not audio_path.exists():
        return None
    transcript_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = transcript_dir / f"{audio_path.stem}.transcript.txt"
    if transcript_path.exists() and not force:
        return transcript_path
    try:
        from faster_whisper import WhisperModel
    except Exception:
        return None
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(audio_path), language=language, vad_filter=True)
    lines = [
        f"# Transcript",
        f"language={getattr(info, 'language', language)} probability={getattr(info, 'language_probability', '-')}",
        "",
    ]
    for segment in segments:
        lines.append(f"[{segment.start:08.2f} -> {segment.end:08.2f}] {segment.text.strip()}")
    transcript_path.write_text("\n".join(lines) + "\n")
    return transcript_path


def read_transcript_text(transcript_path: Path | None) -> str:
    if transcript_path is None or not transcript_path.exists():
        return ""
    try:
        return transcript_path.read_text(errors="ignore")
    except OSError:
        return ""


def detected_topics(text: str) -> list[str]:
    lower = text.lower()
    checks = [
        ("Medias moviles", ("media", "medias", "sma", "ema", "moving average")),
        ("Canales y tendencias", ("canales", "tendencias", "canal y tendencia", "canales y tendencias")),
        ("Lateralidades", ("lateralidad", "lateralidades", "lateral", "rango lateral")),
        ("Timing de entrada", ("timing", "tiempo de entrada", "entrada precisa")),
        ("Debilidad de tendencia", ("debilidad", "debilita", "pierde fuerza")),
        ("Canal alcista", ("canal alcista", "tendencia alcista", "fuerza alcista")),
        ("Canal bajista", ("canal bajista", "tendencia bajista", "fuerza bajista")),
        ("SMA20/SMA40 como piso", ("20 y 40 son pisos", "sma de 20 y 40", "avg 20", "avg 40")),
        ("SMA200 filtro mayor", ("sma 200", "avg 200", "m200", "media 200")),
        ("Ruptura o quiebre", ("ruptura", "quiebre", "break", "maximos historicos")),
        ("Fuerza inversa", ("fuerza inversa", "inversa entre medias")),
        ("Opciones", ("call", "put", "opcion", "opciones")),
        ("VWAP y liquidez", ("vwap", "liquidity", "liquidez", "dark pool", "dark pools")),
        ("Microestructura de mercado", ("market maker", "market-making", "order router", "latency", "exchange", "ecn")),
        ("Macro/FED", ("fomc", "monetary", "fiscal", "economic cycle", "economic indicator", "leading economic")),
        ("Fundamentales y valoracion", ("valuation", "fundamental", "ratios", "growth", "value compan")),
        ("Estrategias cuantitativas", ("pair trading", "cointegration", "hedging", "short squeeze")),
    ]
    return [label for label, needles in checks if any(needle in lower for needle in needles)]


def build_notes(path: Path, metadata: dict[str, Any], ocr_text: str, transcript_text: str = "") -> str:
    combined_text = "\n".join(part for part in [path.stem, ocr_text, transcript_text] if part)
    topics = detected_topics(combined_text)
    topics_text = "\n".join(f"- {item}" for item in topics) or "- Pendiente de clasificacion"
    rules = [
        "No operar una media aislada: confirmar tendencia, canal, volumen, riesgo y target minimo 2%.",
        "Si SMA20/SMA40 sostienen el precio como piso y SMA200 acompana, Roxy puede clasificar canal alcista o pullback sano.",
        "Si el precio quiebra SMA40 dentro de un canal alcista, bajar de BUY a WATCH hasta recuperar.",
        "Si el precio queda debajo de SMA200, bloquear compras hasta recuperacion confirmada.",
        "Separacion sana entre medias confirma fuerza; separacion excesiva exige no perseguir la entrada.",
        "Validar 1h/4h como contexto y 15m como entrada antes de cualquier alerta.",
    ]
    if "Canal bajista" in topics:
        rules.append("En canal bajista, Roxy prioriza No operar o mirar put solo con liquidez y stop definido.")
    if "Ruptura o quiebre" in topics:
        rules.append("Rupturas deben cerrar sobre resistencia y sostener el nivel; no basta una mecha.")
    rule_text = "\n".join(f"- {item}" for item in rules)
    ocr_preview = ocr_text[:6000] if ocr_text else "OCR pendiente o sin texto legible."
    transcript_preview = transcript_text[:6000] if transcript_text else "Transcripcion pendiente. Usa `--transcribe` para activar Whisper local."
    return f"""# Analisis de video para Roxy

Fuente: `{path}`
Generado: `{now_iso()}`
Duracion: `{metadata.get('duration_minutes') or '-'} min`
Resolucion: `{metadata.get('width') or '-'}x{metadata.get('height') or '-'}`

## Temas detectados

{topics_text}

## Reglas operables para Roxy

{rule_text}

## Como usarlo en la app

- Agregar el video a Estudios como referencia.
- Usarlo para mejorar `trade_brief.py` solo cuando la regla sea medible con datos.
- Medir cada senal derivada: llego a 2%, 5%, 10% o toco stop.
- Mantener cambios nuevos en modo paper/laboratorio hasta tener evidencia.

## Texto OCR relevante

```text
{ocr_preview}
```

## Transcripcion de audio

```text
{transcript_preview}
```
"""


def strip_xml_text(xml_body: str) -> str:
    text = re.sub(r"<[^>]+>", " ", xml_body)
    text = (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&apos;", "'")
    )
    return re.sub(r"\s+", " ", text).strip()


def extract_pdf_text(path: Path, *, max_pages: int = 30) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        return ""
    try:
        reader = PdfReader(str(path))
    except Exception:
        return ""
    chunks = []
    for page_number, page in enumerate(reader.pages[:max_pages], start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        page_text = page_text.strip()
        if page_text:
            chunks.append(f"--- page {page_number} ---\n{page_text}")
    return "\n\n".join(chunks)


def extract_zip_xml_text(path: Path, *, max_members: int = 80) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            names = [
                name
                for name in zf.namelist()
                if name.endswith(".xml")
                and (
                    name.startswith("word/")
                    or name.startswith("ppt/")
                    or name.startswith("xl/worksheets/")
                    or name.startswith("xl/sharedStrings")
                )
            ][:max_members]
            chunks = []
            for name in names:
                try:
                    body = zf.read(name).decode("utf-8", errors="ignore")
                except Exception:
                    continue
                text = strip_xml_text(body)
                if text:
                    chunks.append(f"--- {name} ---\n{text}")
            return "\n\n".join(chunks)
    except Exception:
        return ""


def extract_plain_text(path: Path, *, max_chars: int = 120_000) -> str:
    try:
        return path.read_text(errors="ignore")[:max_chars]
    except Exception:
        return ""


def image_for_ocr(path: Path, work_dir: Path) -> Path:
    if path.suffix.lower() != ".heic":
        return path
    work_dir.mkdir(parents=True, exist_ok=True)
    converted = work_dir / f"{slugify(path.stem)}.png"
    if converted.exists():
        return converted
    if not command_exists("sips"):
        return path
    proc = run_command(["sips", "-s", "format", "png", str(path), "--out", str(converted)], timeout=120)
    return converted if proc.returncode == 0 and converted.exists() else path


def extract_image_text(path: Path, work_dir: Path) -> str:
    if not command_exists("tesseract"):
        return ""
    ocr_input = image_for_ocr(path, work_dir)
    out_base = work_dir / slugify(path.stem)
    txt_path = out_base.with_suffix(".txt")
    if txt_path.exists():
        return txt_path.read_text(errors="ignore")
    proc = run_command(["tesseract", str(ocr_input), str(out_base), "-l", "eng+spa", "--psm", "6"], timeout=120)
    if proc.returncode != 0 or not txt_path.exists():
        return ""
    return txt_path.read_text(errors="ignore")


def extract_material_text(path: Path, work_dir: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(path)
    if suffix in {".png", ".jpg", ".jpeg", ".heic"}:
        return extract_image_text(path, work_dir / "ocr")
    if suffix in {".txt", ".csv", ".tsv", ".log"}:
        return extract_plain_text(path)
    if suffix in {".docx", ".pptx", ".xlsx"}:
        return extract_zip_xml_text(path)
    if suffix in {".doc", ".ppt", ".xls", ".odt"} and command_exists("textutil"):
        proc = run_command(["textutil", "-convert", "txt", "-stdout", str(path)], timeout=120)
        return proc.stdout if proc.returncode == 0 else ""
    return ""


def material_metadata(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "kind": path.suffix.lower().lstrip(".") or "file",
        "size_bytes": stat.st_size,
        "mtime": int(stat.st_mtime),
    }


def build_material_notes(path: Path, metadata: dict[str, Any], extracted_text: str) -> str:
    combined_text = "\n".join(part for part in [path.stem, extracted_text] if part)
    topics = detected_topics(combined_text)
    topics_text = "\n".join(f"- {item}" for item in topics) or "- Pendiente de clasificacion"
    lower = combined_text.lower()
    rules = [
        "Convertir solo reglas medibles en cambios del motor; teoria sin dato medible queda en Estudios.",
        "Validar cualquier regla nueva contra backtest, paper trading y memoria antes de subir peso.",
        "Mantener anti-ruido: 1h confirma, 15m da entrada, volumen acompana, riesgo bajo y target 2% viable.",
    ]
    if any(word in lower for word in ("vwap", "liquidity", "dark pool", "market maker", "order router")):
        rules.append("Usar liquidez/VWAP como filtro de calidad: no perseguir entradas lejos de zona institucional o con spread pobre.")
    if any(word in lower for word in ("fomc", "monetary", "fiscal", "economic", "indicator", "cycle")):
        rules.append("Marcar eventos macro/FED como filtro de sesion: reducir agresividad cuando el calendario pueda romper estructura tecnica.")
    if any(word in lower for word in ("valuation", "fundamental", "ratio", "growth", "value")):
        rules.append("Usar fundamentales para contexto de watchlist, no para gatillo intradia; el gatillo sigue siendo tecnico.")
    if any(word in lower for word in ("short squeeze", "pair trading", "hedging", "strategy")):
        rules.append("Clasificar la estrategia antes de operar; no mezclar squeeze, pair trade o hedge con pullback SMA.")
    if any(word in lower for word in ("trend", "sma", "ema", "moving average", "media movil")):
        rules.append("Cruzar tendencia con SMA/EMA 20/40/100/200 y confirmar que no contradiga el canal mayor.")
    rule_text = "\n".join(f"- {item}" for item in rules)
    preview = extracted_text[:9000] if extracted_text else "Texto no extraido. Puede requerir OCR manual o PDF escaneado."
    return f"""# Analisis de material de estudio para Roxy

Fuente: `{path}`
Generado: `{now_iso()}`
Tipo: `{metadata.get('kind')}`
Tamano: `{metadata.get('size_bytes')}` bytes

## Temas detectados

{topics_text}

## Reglas operables para Roxy

{rule_text}

## Como usarlo en la app

- Guardarlo en Estudios como referencia de conocimiento.
- Pasar a Roxy Lab solo si se puede medir con datos.
- Mantener cualquier aprendizaje nuevo en paper/preview hasta tener muestra suficiente.

## Texto extraido relevante

```text
{preview}
```
"""


def process_material(path: Path, out_root: Path, *, force: bool = False) -> dict[str, Any]:
    identity = file_identity(path)
    target_dir = output_dir_for(path, identity, out_root)
    target_dir.mkdir(parents=True, exist_ok=True)
    metadata = material_metadata(path)
    text_path = target_dir / "extracted_text.txt"
    if text_path.exists() and not force:
        extracted_text = text_path.read_text(errors="ignore")
    else:
        extracted_text = extract_material_text(path, target_dir)
        if extracted_text:
            text_path.write_text(extracted_text)
    notes_dir = target_dir / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    notes_path = notes_dir / "auto_knowledge.md"
    notes_path.write_text(build_material_notes(path, metadata, extracted_text))
    manifest = {
        "source_path": str(path),
        "processed_at": now_iso(),
        "identity": identity,
        "metadata": metadata,
        "text_path": str(text_path) if text_path.exists() else None,
        "text_chars": len(extracted_text or ""),
        "notes_path": str(notes_path),
        "topics": detected_topics("\n".join(part for part in [path.stem, extracted_text] if part)),
        "target_dir": str(target_dir),
        "material_type": metadata.get("kind"),
    }
    write_json(target_dir / "manifest.json", manifest)
    return manifest


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    atomic_write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", path)


def manifest_collection(item: dict[str, Any]) -> str:
    if item.get("material_type"):
        return "materials"
    return "videos"


def indexable_manifest_item(item: dict[str, Any]) -> bool:
    return not is_partial_download_path(Path(str(item.get("source_path") or "")))


def manifest_items(out_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    videos: list[dict[str, Any]] = []
    materials: list[dict[str, Any]] = []
    for manifest_path in sorted(out_root.glob("*/manifest.json")):
        item = load_json(manifest_path, None)
        if not isinstance(item, dict):
            continue
        if not indexable_manifest_item(item):
            continue
        if not item.get("target_dir"):
            item["target_dir"] = str(manifest_path.parent)
        collection = manifest_collection(item)
        if collection == "materials":
            materials.append(item)
        else:
            videos.append(item)
    return videos, materials


def index_content_signature(index: dict[str, Any]) -> dict[str, Any]:
    return {
        "videos": index.get("videos") or [],
        "materials": index.get("materials") or [],
    }


def safe_relative_child(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def directory_size_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return total
    for current_root, _dirnames, filenames in os.walk(path):
        for filename in filenames:
            try:
                total += (Path(current_root) / filename).stat().st_size
            except OSError:
                continue
    return total


def cleanup_partial_artifacts(out_root: Path, index: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    indexed_targets = {
        str(item.get("target_dir") or "")
        for collection in ("videos", "materials")
        for item in index.get(collection, [])
        if isinstance(item, dict) and item.get("target_dir")
    }
    removed: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    reclaimed_bytes = 0
    for manifest_path in sorted(out_root.glob("*/manifest.json")):
        item = load_json(manifest_path, None)
        if not isinstance(item, dict) or indexable_manifest_item(item):
            continue
        target_dir = Path(str(item.get("target_dir") or manifest_path.parent))
        if str(target_dir) in indexed_targets:
            skipped.append({"path": str(target_dir), "reason": "indexed"})
            continue
        if target_dir != manifest_path.parent or not safe_relative_child(target_dir, out_root):
            skipped.append({"path": str(target_dir), "reason": "unsafe_target"})
            continue
        size_bytes = directory_size_bytes(target_dir)
        if not dry_run:
            shutil.rmtree(target_dir)
        reclaimed_bytes += size_bytes
        removed.append({"path": str(target_dir), "source_path": str(item.get("source_path") or ""), "size_bytes": size_bytes})
    return {
        "dry_run": bool(dry_run),
        "removed_count": len(removed),
        "removed": removed,
        "skipped_count": len(skipped),
        "skipped": skipped,
        "reclaimed_bytes": reclaimed_bytes,
        "reclaimed_mb": round(reclaimed_bytes / (1024**2), 3),
    }


def process_video(
    path: Path,
    out_root: Path,
    *,
    force: bool = False,
    every_seconds: int = 300,
    transcribe: bool = False,
    model_size: str = "tiny",
    language: str = "es",
    ffmpeg_timeout: int = 900,
) -> dict[str, Any]:
    identity = file_identity(path)
    target_dir = output_dir_for(path, identity, out_root)
    target_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(path.stem)
    metadata = ffprobe_metadata(path)
    audio_path = (
        extract_audio(path, target_dir / "audio", slug, force=force, timeout=ffmpeg_timeout)
        if transcribe
        else None
    )
    frames = extract_frames(
        path,
        target_dir / "frames",
        every_seconds=every_seconds,
        force=force,
        timeout=ffmpeg_timeout,
    )
    ocr_files = ocr_frames(frames, target_dir / "ocr", force=force)
    ocr_text = read_ocr_text(ocr_files)
    if ocr_text:
        (target_dir / "ocr_combined.txt").write_text(ocr_text)
    transcript_path = transcribe_audio(
        audio_path,
        target_dir / "transcripts",
        enabled=transcribe,
        model_size=model_size,
        language=language,
        force=force,
    )
    transcript_text = read_transcript_text(transcript_path)
    notes_dir = target_dir / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    notes_path = notes_dir / "auto_knowledge.md"
    notes_path.write_text(build_notes(path, metadata, ocr_text, transcript_text))
    manifest = {
        "source_path": str(path),
        "processed_at": now_iso(),
        "identity": identity,
        "metadata": metadata,
        "audio_path": str(audio_path) if audio_path else None,
        "frames_count": len(frames),
        "ocr_count": len(ocr_files),
        "transcript_path": str(transcript_path) if transcript_path else None,
        "notes_path": str(notes_path),
        "topics": detected_topics("\n".join(part for part in [path.stem, ocr_text, transcript_text] if part)),
        "target_dir": str(target_dir),
    }
    write_json(target_dir / "manifest.json", manifest)
    return manifest


def unique_archive_path(archive_dir: Path, source: Path) -> Path:
    archive_dir.mkdir(parents=True, exist_ok=True)
    candidate = archive_dir / source.name
    if not candidate.exists():
        return candidate
    stem = source.stem
    suffix = source.suffix
    for number in range(2, 1000):
        candidate = archive_dir / f"{stem}_{number}{suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"No se pudo crear nombre unico para archivar {source}")


def archive_video_source(source: Path, archive_dir: Path) -> Path | None:
    if not source.exists() or not source.is_file():
        return None
    try:
        expected_size = source.stat().st_size
    except OSError:
        expected_size = None
    archive_target = unique_archive_path(archive_dir, source)
    try:
        moved = shutil.move(str(source), str(archive_target))
        return Path(moved)
    except FileNotFoundError:
        if archive_target.exists():
            try:
                archived_size = archive_target.stat().st_size
            except OSError:
                archived_size = None
            if expected_size is None or archived_size == expected_size:
                return archive_target
            try:
                archive_target.unlink()
            except OSError:
                pass
        return None
    except (PermissionError, OSError):
        return None


def archive_learning_source(source: Path, archive_dir: Path) -> Path | None:
    return archive_video_source(source, archive_dir)


def archive_processed_sources(index: dict[str, Any], archive_dir: Path) -> list[dict[str, str]]:
    archived: list[dict[str, str]] = []
    for collection in ("videos", "materials"):
        for item in index.get(collection, []):
            source = Path(str(item.get("source_path") or "")).expanduser()
            if not source.exists() or not source.is_file():
                continue
            target = archive_learning_source(source, archive_dir)
            if target is None:
                continue
            item["archived_path"] = str(target)
            item["archived_at"] = now_iso()
            archived.append({"from": str(source), "to": str(target)})
    return archived


def update_index(
    out_root: Path,
    processed: list[dict[str, Any]],
    processed_materials: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    index_path = out_root / "video_learning_index.json"
    index = load_json(index_path, {"updated_at": None, "videos": [], "materials": []})
    manifest_videos, manifest_materials = manifest_items(out_root)
    by_source = {
        str(item.get("source_path")): item
        for item in index.get("videos", [])
        if isinstance(item, dict) and indexable_manifest_item(item)
    }
    for item in [*manifest_videos, *processed]:
        if indexable_manifest_item(item):
            by_source[str(item.get("source_path"))] = item
    videos = sorted(by_source.values(), key=lambda item: str(item.get("processed_at") or ""), reverse=True)
    material_by_source = {
        str(item.get("source_path")): item
        for item in index.get("materials", [])
        if isinstance(item, dict) and indexable_manifest_item(item)
    }
    for item in [*manifest_materials, *(processed_materials or [])]:
        if indexable_manifest_item(item):
            material_by_source[str(item.get("source_path"))] = item
    materials = sorted(material_by_source.values(), key=lambda item: str(item.get("processed_at") or ""), reverse=True)
    updated = {"updated_at": now_iso(), "videos": videos, "materials": materials}
    if index_content_signature(updated) == index_content_signature(index):
        return index
    write_json(index_path, updated)
    return updated


def write_sync_file(out_root: Path, index: dict[str, Any]) -> Path:
    sync_path = out_root / "ROXY_LEARNING_SYNC.md"
    rows = []
    for item in index.get("videos", [])[:20]:
        topics = ", ".join(item.get("topics") or []) or "pendiente"
        rows.append(
            f"- `{Path(str(item.get('source_path'))).name}` -> `{item.get('target_dir')}` | temas: {topics}"
        )
    body = "\n".join(rows) or "- Sin videos procesados todavia."
    material_rows = []
    for item in index.get("materials", [])[:30]:
        topics = ", ".join(item.get("topics") or []) or "pendiente"
        material_rows.append(
            f"- `{Path(str(item.get('source_path'))).name}` -> `{item.get('target_dir')}` | temas: {topics}"
        )
    material_body = "\n".join(material_rows) or "- Sin materiales procesados todavia."
    sync_path.write_text(
        f"""# Roxy Learning Sync

Este archivo coordina el trabajo entre pestanas de Codex. La responsabilidad de esta rama es aprendizaje por videos/materiales, no ejecucion real.

Ultima actualizacion: `{index.get('updated_at')}`

## Videos procesados

{body}

## Materiales procesados

{material_body}

## Regla de coordinacion

- Otra pestana puede leer estas notas, pero debe evitar editar archivos dentro de `training_videos/` mientras corre ingestion.
- Las reglas nuevas pasan primero por Estudios/Roxy Lab.
- Ninguna regla aprendida de video/material habilita orden real automaticamente.
"""
    )
    return sync_path


def idle_learning_review(index: dict[str, Any]) -> dict[str, Any]:
    videos = list(index.get("videos") or [])
    materials = list(index.get("materials") or [])
    topic_counts: dict[str, int] = {}
    for item in [*videos, *materials]:
        for topic in item.get("topics") or []:
            topic_counts[str(topic)] = topic_counts.get(str(topic), 0) + 1
    ranked_topics = sorted(topic_counts.items(), key=lambda item: (-item[1], item[0]))

    strategy_actions = []
    if topic_counts.get("Medias moviles", 0) or topic_counts.get("SMA200 filtro mayor", 0):
        strategy_actions.append(
            {
                "area": "Medias moviles",
                "action": "Revisar que todo BUY exija estructura 20/40/100/200, SMA200 no bloqueando y target 2% viable.",
            }
        )
    if topic_counts.get("Canales y tendencias", 0) or topic_counts.get("Canal alcista", 0):
        strategy_actions.append(
            {
                "area": "Canal/Tendencia",
                "action": "Comparar 1h/2h/4h contra 15m para evitar entradas contra canal mayor.",
            }
        )
    if topic_counts.get("Timing de entrada", 0):
        strategy_actions.append(
            {
                "area": "Timing",
                "action": "Mantener 1m/5m solo como precision; nunca autorizar BUY sin 15m y 1h.",
            }
        )
    if topic_counts.get("Lateralidades", 0):
        strategy_actions.append(
            {
                "area": "Lateralidad",
                "action": "Separar operaciones piso-techo/techo-piso de rupturas; no mezclar score con canal alcista.",
            }
        )
    if topic_counts.get("Opciones", 0):
        strategy_actions.append(
            {
                "area": "Opciones",
                "action": "Cruzar Mirar Call/Put con delta, DTE, spread, volumen, open interest y break-even.",
            }
        )
    if topic_counts.get("VWAP y liquidez", 0) or topic_counts.get("Microestructura de mercado", 0):
        strategy_actions.append(
            {
                "area": "Liquidez/VWAP",
                "action": "Usar VWAP, liquidez, spreads y posible flujo institucional como filtro de calidad antes de entrar.",
            }
        )
    if topic_counts.get("Macro/FED", 0):
        strategy_actions.append(
            {
                "area": "Macro/FED",
                "action": "Reducir agresividad cerca de FOMC, CPI, PCE, NFP y eventos de tasas salvo confirmacion tecnica superior.",
            }
        )
    if topic_counts.get("Fundamentales y valoracion", 0):
        strategy_actions.append(
            {
                "area": "Fundamentales",
                "action": "Usar valoracion/ratios para contexto de watchlist y tamano, no como gatillo intradia aislado.",
            }
        )
    if topic_counts.get("Estrategias cuantitativas", 0):
        strategy_actions.append(
            {
                "area": "Estrategias cuantitativas",
                "action": "Mantener pair trading, cointegration, hedging y squeeze como familias separadas; no mezclarlas con pullback SMA.",
            }
        )
    if not strategy_actions:
        strategy_actions.append(
            {
                "area": "Recoleccion",
                "action": "Seguir acumulando videos/notas; no hay suficientes temas clasificados para ajustar reglas.",
            }
        )

    latest = []
    for item in videos[:6]:
        latest.append(
            {
                "kind": "video",
                "source": Path(str(item.get("source_path") or "")).name,
                "processed_at": item.get("processed_at"),
                "topics": item.get("topics") or [],
                "notes_path": item.get("notes_path"),
            }
        )
    latest_materials = []
    for item in materials[:8]:
        latest_materials.append(
            {
                "kind": "material",
                "source": Path(str(item.get("source_path") or "")).name,
                "processed_at": item.get("processed_at"),
                "topics": item.get("topics") or [],
                "notes_path": item.get("notes_path"),
                "material_type": item.get("material_type") or item.get("metadata", {}).get("kind"),
            }
        )

    return {
        "generated_at": now_iso(),
        "video_count": len(videos),
        "material_count": len(materials),
        "total_sources": len(videos) + len(materials),
        "topic_counts": dict(ranked_topics),
        "strategy_actions": strategy_actions,
        "latest_videos": latest,
        "latest_materials": latest_materials,
    }


def write_idle_learning_review(out_root: Path, index: dict[str, Any]) -> Path:
    review = idle_learning_review(index)
    json_path = out_root / "idle_learning_review.json"
    md_path = out_root / "idle_learning_review.md"
    write_json(json_path, review)
    topic_lines = "\n".join(
        f"- {topic}: {count}" for topic, count in review.get("topic_counts", {}).items()
    ) or "- Sin temas clasificados todavia."
    action_lines = "\n".join(
        f"- **{item.get('area')}**: {item.get('action')}" for item in review.get("strategy_actions", [])
    )
    latest_lines = "\n".join(
        f"- `{item.get('source')}` | temas: {', '.join(item.get('topics') or []) or 'pendiente'}"
        for item in review.get("latest_videos", [])
    ) or "- Sin videos en indice."
    md_path.write_text(
        f"""# Roxy Idle Learning Review

Generado: `{review.get('generated_at')}`
Videos estudiados: `{review.get('video_count')}`
Materiales estudiados: `{review.get('material_count')}`

Esta revision corre cuando no hay videos/materiales nuevos. Sirve para convertir lo ya aprendido en mejoras candidatas para Roxy Lab, sin activar ejecucion real automaticamente.

## Temas mas repetidos

{topic_lines}

## Mejoras candidatas para Roxy

{action_lines}

## Videos recientes estudiados

{latest_lines}

## Materiales recientes estudiados

{chr(10).join(f"- `{item.get('source')}` ({item.get('material_type') or 'file'}) | temas: {', '.join(item.get('topics') or []) or 'pendiente'}" for item in review.get('latest_materials', [])) or "- Sin materiales en indice."}
"""
    )
    return md_path


def _source_label(item: dict[str, Any]) -> str:
    source = str(item.get("source_path") or item.get("source") or "")
    return Path(source).name if source else "fuente desconocida"


def _topic_source_map(index: dict[str, Any]) -> dict[str, list[str]]:
    mapped: dict[str, list[str]] = {}
    for item in [*(index.get("videos") or []), *(index.get("materials") or [])]:
        label = _source_label(item)
        for topic in item.get("topics") or []:
            key = str(topic)
            mapped.setdefault(key, [])
            if label not in mapped[key]:
                mapped[key].append(label)
    return mapped


def _sources_for(topic_sources: dict[str, list[str]], topics: list[str], limit: int = 8) -> list[str]:
    sources: list[str] = []
    for topic in topics:
        for source in topic_sources.get(topic, []):
            if source not in sources:
                sources.append(source)
            if len(sources) >= limit:
                return sources
    return sources


def build_teacher_playbook(index: dict[str, Any]) -> dict[str, Any]:
    """Build a source-backed operating playbook from studied videos/materials.

    The playbook is intentionally deterministic. It does not invent a winning
    system; it converts the teacher material already indexed into rules Roxy can
    use as filters, explanations, and pre-trade checks.
    """
    videos = list(index.get("videos") or [])
    materials = list(index.get("materials") or [])
    topic_counts: dict[str, int] = {}
    for item in [*videos, *materials]:
        for topic in item.get("topics") or []:
            topic_counts[str(topic)] = topic_counts.get(str(topic), 0) + 1
    topic_sources = _topic_source_map(index)

    def has(*topics: str) -> bool:
        return any(topic_counts.get(topic, 0) > 0 for topic in topics)

    strategy_rules: list[dict[str, Any]] = []
    if has("Medias moviles", "SMA200 filtro mayor"):
        strategy_rules.append(
            {
                "id": "ma_alignment",
                "name": "Alineacion de medias antes de entrar",
                "use_when": "Acciones o crypto con estrategia de tendencia/pullback.",
                "rule": "Roxy debe validar EMA/SMA rapidas, medias 20/40 y filtro mayor antes de marcar una entrada.",
                "entry_requirements": [
                    "15m define la zona precisa de entrada.",
                    "1h confirma direccion y evita entrar contra la tendencia mayor.",
                    "La media mayor no debe bloquear el recorrido al target.",
                    "La entrada debe tener stop, target y R/R minimo visibles.",
                ],
                "reject_if": [
                    "Precio extendido lejos de medias.",
                    "Medias cruzadas sin direccion limpia.",
                    "Target queda demasiado cerca para compensar el riesgo.",
                ],
                "source_topics": ["Medias moviles", "SMA200 filtro mayor"],
                "sources": _sources_for(topic_sources, ["Medias moviles", "SMA200 filtro mayor"]),
            }
        )
    if has("Canales y tendencias", "Canal alcista"):
        strategy_rules.append(
            {
                "id": "channel_context",
                "name": "Canal y tendencia mandan el contexto",
                "use_when": "Roxy detecta movimiento dentro de canal o posible ruptura.",
                "rule": "Separar operativa dentro del canal de operativa por ruptura; no mezclar ambas senales.",
                "entry_requirements": [
                    "Marcar piso, techo y mitad del canal.",
                    "Confirmar si el precio esta en zona de rebote o zona de rechazo.",
                    "La recomendacion debe decir si busca rebote, continuacion o breakout.",
                ],
                "reject_if": [
                    "Entrada en medio del canal sin ventaja clara.",
                    "Ruptura sin volumen o sin cierre de confirmacion.",
                ],
                "source_topics": ["Canales y tendencias", "Canal alcista"],
                "sources": _sources_for(topic_sources, ["Canales y tendencias", "Canal alcista"]),
            }
        )
    if has("Timing de entrada"):
        strategy_rules.append(
            {
                "id": "timing_precision",
                "name": "Timing: precision sin perder contexto",
                "use_when": "Roxy baja a 1m/5m para ejecutar.",
                "rule": "1m y 5m solo afinan la entrada; la direccion debe venir de 15m/1h.",
                "entry_requirements": [
                    "Confirmar gatillo corto despues de definir plan 15m/1h.",
                    "No recalcular una compra por cada tick; esperar cierre o micro-confirmacion.",
                    "Mostrar tiempo restante si la estrategia depende de ciclo de 20m/2h/daily.",
                ],
                "reject_if": [
                    "Solo existe senal de 1m sin apoyo de timeframes mayores.",
                    "El spread o la volatilidad anula la precision del gatillo.",
                ],
                "source_topics": ["Timing de entrada"],
                "sources": _sources_for(topic_sources, ["Timing de entrada"]),
            }
        )
    if has("Lateralidades"):
        strategy_rules.append(
            {
                "id": "range_playbook",
                "name": "Lateralidad: piso, techo y paciencia",
                "use_when": "Mercado sin tendencia clara.",
                "rule": "Roxy debe tratar lateralidades como operativas de rango, no como tendencia.",
                "entry_requirements": [
                    "Identificar soporte y resistencia del rango.",
                    "Comprar cerca del piso solo con rechazo confirmado.",
                    "Evitar perseguir velas hacia el centro del rango.",
                ],
                "reject_if": [
                    "Precio esta en mitad del rango.",
                    "No hay volumen/confirmacion en la zona extrema.",
                ],
                "source_topics": ["Lateralidades"],
                "sources": _sources_for(topic_sources, ["Lateralidades"]),
            }
        )
    if has("Opciones"):
        strategy_rules.append(
            {
                "id": "options_contract_quality",
                "name": "Opciones: contrato primero, hype nunca",
                "use_when": "Roxy traduzca una tesis a calls/puts.",
                "rule": "Una oportunidad de opciones debe validar delta, DTE, spread, volumen, OI y break-even.",
                "entry_requirements": [
                    "Mostrar contrato candidato, expiracion y break-even.",
                    "Evitar spreads amplios y contratos sin liquidez.",
                    "Comparar riesgo/recompensa contra operar la accion.",
                ],
                "reject_if": [
                    "Contrato iliquido.",
                    "Break-even demasiado lejos para el movimiento esperado.",
                    "Evento binario no contemplado.",
                ],
                "source_topics": ["Opciones"],
                "sources": _sources_for(topic_sources, ["Opciones"]),
            }
        )
    if has("VWAP y liquidez", "Microestructura de mercado"):
        strategy_rules.append(
            {
                "id": "liquidity_filter",
                "name": "Liquidez/VWAP como filtro de calidad",
                "use_when": "Entrada intradia o confirmacion de fuerza.",
                "rule": "Roxy debe considerar VWAP, volumen, spread y liquidez antes de subir la confianza.",
                "entry_requirements": [
                    "Precio respetando VWAP o recuperandolo con volumen.",
                    "Spread razonable para el activo.",
                    "Volumen relativo suficiente para confirmar movimiento.",
                ],
                "reject_if": [
                    "Movimiento con volumen seco.",
                    "Spread o slippage alto.",
                    "Falso breakout sin participacion.",
                ],
                "source_topics": ["VWAP y liquidez", "Microestructura de mercado"],
                "sources": _sources_for(topic_sources, ["VWAP y liquidez", "Microestructura de mercado"]),
            }
        )
    if has("Macro/FED"):
        strategy_rules.append(
            {
                "id": "macro_event_guard",
                "name": "Filtro macro y eventos",
                "use_when": "Hay CPI, PCE, FOMC, NFP, earnings o evento de tasas cerca.",
                "rule": "Roxy debe reducir agresividad o pedir confirmacion extra antes de operar cerca de eventos.",
                "entry_requirements": [
                    "Mostrar evento relevante y hora.",
                    "Evitar senales debiles antes de noticias de alto impacto.",
                    "Usar menor tamano o esperar ruptura confirmada despues del evento.",
                ],
                "reject_if": [
                    "Evento de alto impacto esta encima y la senal no esta completa.",
                    "Volatilidad esperada invalida el stop.",
                ],
                "source_topics": ["Macro/FED"],
                "sources": _sources_for(topic_sources, ["Macro/FED"]),
            }
        )

    anti_patterns = [
        {
            "id": "chasing",
            "name": "Perseguir precio",
            "avoid": "No entrar despues de una vela extendida si la zona de entrada ya paso.",
            "roxy_response": "Marcar ESPERAR CONFIRMACION y recalcular nueva zona.",
            "sources": _sources_for(topic_sources, ["Timing de entrada", "Canales y tendencias", "Medias moviles"], 5),
        },
        {
            "id": "single_timeframe",
            "name": "Operar con un solo timeframe",
            "avoid": "No aprobar oportunidad si solo 1m/5m se ve bien y 15m/1h no confirma.",
            "roxy_response": "Bajar confianza y explicar que falta confirmacion superior.",
            "sources": _sources_for(topic_sources, ["Timing de entrada", "Medias moviles"], 5),
        },
        {
            "id": "no_plan",
            "name": "Senal sin plan",
            "avoid": "No mostrar COMPRA/VENDER sin entrada, stop, target, R/R, invalidez y razon.",
            "roxy_response": "Convertir la senal en NO OPERAR hasta completar el plan.",
            "sources": _sources_for(topic_sources, ["Check list y no negociables", "Riesgo", "Medias moviles"], 5),
        },
        {
            "id": "revenge_trading",
            "name": "Recuperar perdidas a la fuerza",
            "avoid": "No aumentar riesgo para recuperar una perdida previa.",
            "roxy_response": "Bloquear operativa si el riesgo supera 1R o el usuario esta forzando entrada.",
            "sources": _sources_for(topic_sources, ["Riesgo", "Check list y no negociables"], 5),
        },
    ]

    opportunity_checklist = [
        "Datos live confirmados y timestamp fresco.",
        "Activo, timeframe y mercado definidos.",
        "Regimen identificado: tendencia, canal, lateralidad, ruptura o no operar.",
        "Direccion validada por timeframe mayor.",
        "Entrada, stop, target, R/R y razon visibles.",
        "Volumen/liquidez suficientes para operar.",
        "Evento macro/earnings revisado.",
        "Semaforo final: OPERAR AHORA, ESPERAR CONFIRMACION o NO OPERAR.",
        "Explicacion de Roxy con las 3-5 razones principales.",
    ]

    return {
        "generated_at": now_iso(),
        "source_counts": {
            "videos": len(videos),
            "materials": len(materials),
            "total": len(videos) + len(materials),
        },
        "topic_counts": dict(sorted(topic_counts.items(), key=lambda item: (-item[1], item[0]))),
        "strategy_rules": strategy_rules,
        "anti_patterns": anti_patterns,
        "opportunity_checklist": opportunity_checklist,
        "classroom_foundation": [
            "Que es trading y que no es trading.",
            "Tipos de activos: acciones, crypto, opciones, ETF, indices y forex.",
            "Precio, spread, volumen, liquidez, ordenes y riesgo.",
            "Velas, timeframes, tendencia, soporte/resistencia y medias moviles.",
            "Plan de operacion: entrada, stop, target, R/R, tamano y diario.",
        ],
    }


def write_teacher_playbook(out_root: Path, index: dict[str, Any]) -> Path:
    playbook = build_teacher_playbook(index)
    json_path = out_root / "roxy_teacher_playbook.json"
    md_path = out_root / "roxy_teacher_playbook.md"
    write_json(json_path, playbook)
    rule_lines = []
    for rule in playbook.get("strategy_rules", []):
        sources = ", ".join(rule.get("sources") or []) or "sin fuente clasificada"
        requirements = "\n".join(f"  - {item}" for item in rule.get("entry_requirements") or [])
        rejects = "\n".join(f"  - {item}" for item in rule.get("reject_if") or [])
        rule_lines.append(
            f"### {rule.get('name')}\n"
            f"- Uso: {rule.get('use_when')}\n"
            f"- Regla: {rule.get('rule')}\n"
            f"- Requisitos:\n{requirements}\n"
            f"- Bloquear si:\n{rejects}\n"
            f"- Fuentes: {sources}"
        )
    anti_lines = "\n".join(
        f"- **{item.get('name')}**: {item.get('avoid')} Respuesta de Roxy: {item.get('roxy_response')}"
        for item in playbook.get("anti_patterns", [])
    )
    checklist = "\n".join(f"- {item}" for item in playbook.get("opportunity_checklist", []))
    topic_lines = "\n".join(
        f"- {topic}: {count}" for topic, count in (playbook.get("topic_counts") or {}).items()
    ) or "- Sin temas clasificados."
    md_path.write_text(
        f"""# Roxy Teacher Playbook

Generado: `{playbook.get('generated_at')}`
Videos estudiados: `{playbook.get('source_counts', {}).get('videos')}`
Materiales estudiados: `{playbook.get('source_counts', {}).get('materials')}`

Este archivo alimenta el cerebro operativo de Roxy con reglas derivadas de clases, videos y materiales ya indexados. No habilita ordenes automaticas ni garantiza rentabilidad; sirve como filtro, explicacion y checklist de decision.

## Temas detectados

{topic_lines}

## Reglas operativas

{chr(10).join(rule_lines) or "- Todavia no hay reglas suficientes."}

## Antipatrones que Roxy debe evitar

{anti_lines}

## Checklist antes de mostrar una oportunidad

{checklist}
"""
    )
    return md_path


def already_processed(index: dict[str, Any], path: Path) -> bool:
    identity = file_identity(path)
    for collection in ("videos", "materials"):
        for item in index.get(collection, []):
            if item.get("identity", {}).get("fingerprint") == identity["fingerprint"]:
                return True
    return False


def run_once(args: argparse.Namespace) -> dict[str, Any]:
    out_root = Path(args.output).expanduser()
    if not out_root.is_absolute():
        out_root = project_root() / out_root
    out_root.mkdir(parents=True, exist_ok=True)
    sources = [Path(item).expanduser() for item in args.source] if args.source else default_sources()
    index = load_json(out_root / "video_learning_index.json", {"updated_at": None, "videos": [], "materials": []})
    previous_targets = {
        str(item.get("target_dir") or "")
        for collection in ("videos", "materials")
        for item in index.get(collection, [])
        if item.get("target_dir")
    }
    reconcile_index_only = bool(getattr(args, "reconcile_index_only", False))
    media_kind = str(getattr(args, "media_kind", "all") or "all")
    videos = (
        []
        if reconcile_index_only or media_kind == "materials"
        else iter_video_files(sources, max_depth=args.max_depth)
    )
    materials = (
        []
        if reconcile_index_only or media_kind == "videos"
        else iter_material_files(sources, max_depth=args.max_depth)
    )
    processed = []
    processed_materials = []
    if not reconcile_index_only:
        for video in videos:
            if not args.force and already_processed(index, video):
                continue
            manifest = process_video(
                video,
                out_root,
                force=args.force,
                every_seconds=args.every_seconds,
                transcribe=args.transcribe,
                model_size=args.model_size,
                language=args.language,
                ffmpeg_timeout=int(getattr(args, "ffmpeg_timeout", 900) or 900),
            )
            processed.append(manifest)
            index = update_index(out_root, processed, processed_materials)
            if args.limit and len(processed) >= args.limit:
                break
    remaining_limit = max(0, int(args.limit) - len(processed)) if args.limit else 0
    if not reconcile_index_only:
        for material in materials:
            if args.limit and remaining_limit <= 0:
                break
            if not args.force and already_processed(index, material):
                continue
            manifest = process_material(material, out_root, force=args.force)
            processed_materials.append(manifest)
            index = update_index(out_root, processed, processed_materials)
            if args.limit:
                remaining_limit -= 1
    updated = update_index(out_root, processed, processed_materials)
    updated_targets = {
        str(item.get("target_dir") or "")
        for collection in ("videos", "materials")
        for item in updated.get(collection, [])
        if item.get("target_dir")
    }
    manifest_reconciled = max(0, len(updated_targets - previous_targets) - len(processed) - len(processed_materials))
    index_changed = index_content_signature(updated) != index_content_signature(index)
    archived = []
    if args.archive_dir:
        archive_dir = Path(args.archive_dir).expanduser()
        if not archive_dir.is_absolute():
            archive_dir = project_root() / archive_dir
        if processed or processed_materials:
            by_source = {
                str(item.get("source_path")): item
                for collection in ("videos", "materials")
                for item in updated.get(collection, [])
            }
            for item in [*processed, *processed_materials]:
                source = Path(str(item.get("source_path") or "")).expanduser()
                target = archive_learning_source(source, archive_dir)
                if target is None:
                    continue
                item["archived_path"] = str(target)
                item["archived_at"] = now_iso()
                if str(item.get("source_path")) in by_source:
                    by_source[str(item.get("source_path"))].update(
                        {"archived_path": str(target), "archived_at": item["archived_at"]}
                    )
                archived.append({"from": str(source), "to": str(target)})
            write_json(out_root / "video_learning_index.json", updated)
        if args.archive_indexed:
            archived.extend(archive_processed_sources(updated, archive_dir))
            if archived:
                write_json(out_root / "video_learning_index.json", updated)
    partial_cleanup = {"removed_count": 0, "reclaimed_bytes": 0, "reclaimed_mb": 0.0, "skipped_count": 0}
    if bool(getattr(args, "cleanup_partial_artifacts", False)):
        partial_cleanup = cleanup_partial_artifacts(out_root, updated)
        if partial_cleanup.get("removed_count"):
            updated = update_index(out_root, [], [])
    idle_review_path = None
    if args.idle_review and not processed and not processed_materials:
        idle_review_path = write_idle_learning_review(out_root, updated)
    teacher_playbook_path = write_teacher_playbook(out_root, updated)
    if (
        index_changed
        or processed
        or archived
        or partial_cleanup.get("removed_count")
        or idle_review_path
        or teacher_playbook_path
        or not (out_root / "ROXY_LEARNING_SYNC.md").exists()
    ):
        write_sync_file(out_root, updated)
    return {
        "found": len(videos),
        "materials_found": len(materials),
        "processed": len(processed),
        "materials_processed": len(processed_materials),
        "manifest_reconciled": manifest_reconciled,
        "archived": len(archived),
        "partial_artifacts_removed": int(partial_cleanup.get("removed_count") or 0),
        "partial_artifacts_reclaimed_mb": float(partial_cleanup.get("reclaimed_mb") or 0.0),
        "partial_artifacts_skipped": int(partial_cleanup.get("skipped_count") or 0),
        "idle_review": str(idle_review_path) if idle_review_path else None,
        "teacher_playbook": str(teacher_playbook_path),
        "archive_dir": str(Path(args.archive_dir).expanduser()) if args.archive_dir else None,
        "output": str(out_root),
        "index": updated,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingesta videos de trading para el laboratorio de aprendizaje de Roxy.")
    parser.add_argument("--source", action="append", default=[], help="Carpeta a escanear. Se puede repetir.")
    parser.add_argument("--output", default="training_videos", help="Carpeta de salida dentro del proyecto.")
    parser.add_argument("--limit", type=int, default=0, help="Maximo de videos nuevos por corrida. 0 = sin limite.")
    parser.add_argument("--max-depth", type=int, default=4, help="Profundidad maxima de escaneo por carpeta.")
    parser.add_argument("--every-seconds", type=int, default=300, help="Frecuencia de capturas para OCR.")
    parser.add_argument(
        "--ffmpeg-timeout",
        type=int,
        default=900,
        help="Segundos maximos para extraer audio o frames de un video antes de saltarlo parcialmente.",
    )
    parser.add_argument("--transcribe", action="store_true", help="Transcribir audio con faster-whisper local.")
    parser.add_argument("--model-size", default="tiny", help="Modelo faster-whisper: tiny, base, small, medium.")
    parser.add_argument("--language", default="es", help="Idioma para Whisper.")
    parser.add_argument("--force", action="store_true", help="Reprocesar aunque ya exista en el indice.")
    parser.add_argument(
        "--media-kind",
        choices=("all", "videos", "materials"),
        default="all",
        help="Tipo de fuente a procesar en esta corrida.",
    )
    parser.add_argument("--archive-dir", default="", help="Mover videos procesados correctamente a esta carpeta.")
    parser.add_argument(
        "--archive-indexed",
        action="store_true",
        help="Tambien mover fuentes que ya estaban indexadas y todavia existen en su ubicacion original.",
    )
    parser.add_argument(
        "--idle-review",
        action="store_true",
        help="Si no hay videos nuevos, generar una revision de aprendizaje usando el indice existente.",
    )
    parser.add_argument(
        "--reconcile-index-only",
        action="store_true",
        help="Reconstruir el indice desde manifests existentes sin escanear ni procesar fuentes.",
    )
    parser.add_argument(
        "--cleanup-partial-artifacts",
        action="store_true",
        help="Eliminar artefactos generados desde fuentes parciales no indexadas.",
    )
    parser.add_argument("--watch", action="store_true", help="Mantener escaneando en loop.")
    parser.add_argument("--interval", type=int, default=2100, help="Segundos entre escaneos si --watch esta activo.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    while True:
        result = run_once(args)
        print(json.dumps({k: v for k, v in result.items() if k != "index"}, indent=2))
        if not args.watch:
            break
        time.sleep(max(60, args.interval))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
