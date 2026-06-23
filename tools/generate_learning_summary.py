#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = PROJECT_DIR / "training_videos" / "video_learning_index.json"
DEFAULT_OUTPUT = PROJECT_DIR / "training_videos" / "NATALIA_LEARNING_SUMMARY.md"


THEME_KEYWORDS = {
    "Canales y tendencia": [
        "canal alcista",
        "canal bajista",
        "canal lateral",
        "tendencia alcista",
        "tendencia bajista",
        "cambio de canal",
    ],
    "Medias moviles": [
        "sma20",
        "sma40",
        "sma100",
        "sma200",
        "ema9",
        "media movil",
        "medias moviles",
        "cruce de medias",
    ],
    "Saltos y rupturas": [
        "salto",
        "ruptura",
        "maximos historicos",
        "linea de resistencia",
        "breakout",
        "quiebre",
    ],
    "Entrada multitemporal": [
        "15m",
        "15 minutos",
        "1h",
        "hora",
        "2 horas",
        "4 horas",
        "multitemporal",
    ],
    "Volumen y liquidez": [
        "volumen",
        "liquidez",
        "spread",
        "open interest",
        "dark pool",
        "vwap",
    ],
    "Opciones": [
        "opciones",
        "call",
        "put",
        "delta",
        "dte",
        "break-even",
        "contrato",
    ],
    "Riesgo": [
        "riesgo",
        "stop",
        "target",
        "objetivo",
        "perdida",
        "profit factor",
        "win rate",
    ],
    "Brokers y ejecucion": [
        "broker",
        "ibkr",
        "interactive brokers",
        "schwab",
        "webull",
        "e-trade",
        "orden limit",
        "margin",
    ],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"videos": [], "materials": []}
    return json.loads(path.read_text(errors="ignore"))


def read_text(path_text: str | None, max_chars: int = 24_000) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    if not path.exists():
        return ""
    return path.read_text(errors="ignore")[:max_chars]


def source_matches(item: dict[str, Any], source_filter: str) -> bool:
    if not source_filter:
        return True
    return source_filter in str(item.get("source_path") or "")


def item_text(item: dict[str, Any]) -> str:
    chunks = [
        str(item.get("source_path") or ""),
        " ".join(str(topic) for topic in item.get("topics") or []),
        read_text(item.get("notes_path")),
    ]
    target_dir = item.get("target_dir")
    if target_dir:
        target = Path(str(target_dir))
        chunks.append(read_text(str(target / "ocr_combined.txt"), max_chars=18_000))
        chunks.append(read_text(str(target / "extracted_text.txt"), max_chars=18_000))
    return "\n".join(chunk for chunk in chunks if chunk)


def classify_themes(text: str) -> list[str]:
    lower = text.lower()
    themes = []
    for theme, needles in THEME_KEYWORDS.items():
        if any(needle in lower for needle in needles):
            themes.append(theme)
    return themes


def extract_bullets(text: str, headings: tuple[str, ...], limit: int = 30) -> list[str]:
    bullets: list[str] = []
    active = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        normalized = line.strip("# ").lower()
        if any(heading in normalized for heading in headings):
            active = True
            continue
        if active and line.startswith("## "):
            active = False
        if active and line.startswith("- "):
            clean = re.sub(r"\s+", " ", line[2:]).strip()
            if clean and clean not in bullets:
                bullets.append(clean)
        if len(bullets) >= limit:
            break
    return bullets


def concise_sources(items: list[dict[str, Any]], limit: int = 25) -> list[str]:
    rows = []
    for item in items[:limit]:
        source = Path(str(item.get("source_path") or "")).name
        topics = ", ".join(item.get("topics") or []) or "pendiente"
        rows.append(f"- `{source}` | temas: {topics}")
    return rows


def build_summary(index: dict[str, Any], source_filter: str) -> str:
    videos = [item for item in index.get("videos", []) if source_matches(item, source_filter)]
    materials = [item for item in index.get("materials", []) if source_matches(item, source_filter)]
    all_items = videos + materials

    theme_counts: Counter[str] = Counter()
    topic_counts: Counter[str] = Counter()
    rule_counts: Counter[str] = Counter()
    app_counts: Counter[str] = Counter()
    examples_by_theme: dict[str, list[str]] = defaultdict(list)

    for item in all_items:
        text = item_text(item)
        for topic in item.get("topics") or []:
            topic_counts[str(topic)] += 1
        themes = classify_themes(text)
        for theme in themes:
            theme_counts[theme] += 1
            if len(examples_by_theme[theme]) < 5:
                examples_by_theme[theme].append(Path(str(item.get("source_path") or "")).name)
        for rule in extract_bullets(text, ("reglas operables", "requisitos", "requisito"), limit=80):
            rule_counts[rule] += 1
        for app_rule in extract_bullets(text, ("como usarlo en la app", "mejoras para roxy"), limit=80):
            app_counts[app_rule] += 1

    lines = [
        "# Resumen de aprendizaje - Roxy Trading",
        "",
        f"Generado: `{now_iso()}`",
        f"Fuente filtrada: `{source_filter or 'todo el indice de aprendizaje'}`",
        "",
        "## Estado del procesamiento",
        "",
        f"- Videos indexados: `{len(videos)}`",
        f"- Materiales indexados: `{len(materials)}`",
        f"- Total de fuentes leidas para este resumen: `{len(all_items)}`",
        "",
        "## Lo aprendido hasta ahora",
        "",
    ]

    if theme_counts:
        for theme, count in theme_counts.most_common():
            examples = ", ".join(examples_by_theme.get(theme, [])[:3])
            lines.append(f"- **{theme}**: aparece en `{count}` fuentes. Ejemplos: {examples or 'sin ejemplo'}")
    else:
        lines.append("- Todavia no hay suficiente texto clasificado para extraer temas solidos.")

    lines.extend(["", "## Reglas que deben alimentar el cerebro de Roxy", ""])
    if rule_counts:
        for rule, count in rule_counts.most_common(18):
            lines.append(f"- {rule} (`{count}` fuente/s)")
    else:
        lines.extend(
            [
                "- Confirmar contexto mayor antes de entrada: 1h/4h para direccion, 15m para timing.",
                "- No operar si precio esta bajo filtro mayor de medias y no hay recuperacion confirmada.",
                "- Exigir volumen, riesgo medible y target minimo de 2% antes de alerta real.",
            ]
        )

    lines.extend(["", "## En que mejora Roxy", ""])
    improvements = [
        "Trade Plan mas directo: Operar, Mirar Call, Esperar o No operar con una razon concreta.",
        "Filtro multitemporal mas fuerte: 1h/4h validan estructura y 15m decide entrada.",
        "Grafica principal mas educativa: velas, SMA/EMA, canal, zonas, stop, objetivos, volumen y nota de la estrategia activa.",
        "Roxy Lab con mas criterio: cada estrategia nueva entra en paper/laboratorio antes de afectar alertas reales.",
        "Memoria real: cada senal debe registrar si llego a 2%, 5%, 10% o si toco stop.",
        "Opciones mas conservadoras: no sugerir call/put sin setup base, liquidez, spread, delta, DTE y riesgo maximo.",
        "Alertas con menos ruido: solo cuando tendencia, entrada, volumen, riesgo y target esten alineados.",
    ]
    for item in improvements:
        lines.append(f"- {item}")

    if app_counts:
        lines.extend(["", "## Cambios concretos sugeridos por las notas", ""])
        for rule, count in app_counts.most_common(12):
            lines.append(f"- {rule} (`{count}` fuente/s)")

    lines.extend(["", "## Temas detectados por frecuencia", ""])
    if topic_counts:
        for topic, count in topic_counts.most_common(20):
            lines.append(f"- {topic}: `{count}`")
    else:
        lines.append("- Sin temas estructurados todavia para esta fuente.")

    lines.extend(["", "## Fuentes recientes consideradas", ""])
    lines.extend(concise_sources(all_items, limit=30) or ["- No hay fuentes indexadas todavia."])

    lines.extend(
        [
            "",
            "## Regla de seguridad",
            "",
            "- Este conocimiento mejora analisis y paper trading. No habilita ejecucion real automatica hasta que existan credenciales, pruebas, controles de riesgo y aprobacion explicita.",
            "- Roxy debe medir resultados antes de subir confianza o tamano de posicion.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera resumen maestro del aprendizaje de Roxy.")
    parser.add_argument("--index", default=str(DEFAULT_INDEX))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--source-filter", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    index = load_json(Path(args.index))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_summary(index, args.source_filter), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
