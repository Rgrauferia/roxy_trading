"""Private, household-shared plant care for Roxy Home."""

from __future__ import annotations

import base64
import json
import os
import re
import tempfile
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from roxy_os.home_ai import HomeAIBudgetLedger, HomeAIConfig, HomeAIConfigurationError

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


IMAGE_TYPES = {
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
    "image/webp": (b"RIFF", ".webp"),
}
VIDEO_TYPES = {"video/mp4": (b"", ".mp4")}
MAX_IMAGE_BYTES = 6_000_000
MAX_JOURNAL_MEDIA_BYTES = 12_000_000

CARE_SOURCES = [
    {"label": "University of Illinois Extension · Riego", "url": "https://extension.illinois.edu/houseplants/watering"},
    {"label": "University of Illinois Extension · Cuidados", "url": "https://extension.illinois.edu/houseplants/care"},
    {"label": "ASPCA · Plantas tóxicas y no tóxicas", "url": "https://www.aspca.org/pet-care/aspca-poison-control/toxic-and-non-toxic-plants"},
]

PLANT_CATALOG: dict[str, dict[str, Any]] = {
    "pothos": {
        "common_name": "Pothos", "scientific_name": "Epipremnum aureum", "light": "Luz indirecta media a brillante",
        "soil_check_days": 7, "soil_rule": "Revisa los primeros 5 cm; riega solo si están secos.",
        "fertilizer": "Fertilizante balanceado para plantas de interior, diluido y solo durante crecimiento activo.",
        "history": "Enredadera tropical del sudeste asiático, popular por su resistencia y crecimiento colgante.",
        "toxicity": "Tóxica para perros y gatos si se mastica; contiene oxalatos de calcio insolubles.", "pet_safe": False,
    },
    "monstera": {
        "common_name": "Monstera", "scientific_name": "Monstera deliciosa", "light": "Luz indirecta brillante",
        "soil_check_days": 7, "soil_rule": "Revisa los primeros 5 cm y riega cuando estén secos; evita agua acumulada.",
        "fertilizer": "Fertilizante balanceado a media concentración en primavera y verano.",
        "history": "Trepadora tropical americana conocida por las perforaciones naturales de sus hojas adultas.",
        "toxicity": "Tóxica para perros y gatos si se mastica; contiene oxalatos de calcio insolubles.", "pet_safe": False,
    },
    "snake_plant": {
        "common_name": "Lengua de suegra", "scientific_name": "Dracaena trifasciata", "light": "Tolera poca luz; prefiere luz indirecta",
        "soil_check_days": 14, "soil_rule": "Deja secar bien el sustrato entre riegos; es sensible al exceso de agua.",
        "fertilizer": "Fertilización ligera durante crecimiento activo; evita sobrefertilizar.",
        "history": "Planta africana de hojas rígidas, adaptada a almacenar agua y tolerar periodos secos.",
        "toxicity": "Tóxica para perros y gatos; la ASPCA señala saponinas como principio tóxico.", "pet_safe": False,
    },
    "spider_plant": {
        "common_name": "Cinta", "scientific_name": "Chlorophytum comosum", "light": "Luz indirecta media a brillante",
        "soil_check_days": 6, "soil_rule": "Revisa la capa superior y riega cuando comience a secarse, dejando drenar.",
        "fertilizer": "Fertilizante balanceado diluido en primavera y verano.",
        "history": "Originaria del sur de África; produce hijuelos colgantes fáciles de propagar.",
        "toxicity": "Generalmente considerada no tóxica para perros y gatos; evita que la mascota la ingiera en cantidad.", "pet_safe": True,
    },
    "aloe": {
        "common_name": "Aloe vera", "scientific_name": "Aloe vera", "light": "Luz brillante; sol directo gradual",
        "soil_check_days": 14, "soil_rule": "Riega únicamente cuando el sustrato esté completamente seco y deja drenar.",
        "fertilizer": "Poco fertilizante; fórmula para cactus/suculentas durante crecimiento activo.",
        "history": "Suculenta usada históricamente por el gel de sus hojas; no debe confundirse uso tópico con ingestión segura.",
        "toxicity": "Tóxica para perros y gatos si la ingieren.", "pet_safe": False,
    },
    "peace_lily": {
        "common_name": "Lirio de paz", "scientific_name": "Spathiphyllum", "light": "Luz indirecta media",
        "soil_check_days": 5, "soil_rule": "Mantén humedad moderada sin encharcar; comprueba la tierra antes de regar.",
        "fertilizer": "Fertilizante balanceado diluido durante crecimiento activo.",
        "history": "Planta tropical americana apreciada por sus espatas blancas y tolerancia al interior.",
        "toxicity": "Tóxica para perros y gatos si se mastica; contiene oxalatos de calcio insolubles.", "pet_safe": False,
    },
    "basil": {
        "common_name": "Albahaca", "scientific_name": "Ocimum basilicum", "light": "Sol suave o luz muy brillante",
        "soil_check_days": 2, "soil_rule": "Revisa con frecuencia y riega cuando la superficie empiece a secarse; no dejes agua estancada.",
        "fertilizer": "Abono suave para hierbas comestibles siguiendo la etiqueta.",
        "history": "Hierba aromática de la familia de la menta, cultivada en muchas cocinas mediterráneas y asiáticas.",
        "toxicity": "Generalmente considerada no tóxica para perros y gatos.", "pet_safe": True,
    },
    "orchid": {
        "common_name": "Orquídea Phalaenopsis", "scientific_name": "Phalaenopsis", "light": "Luz indirecta brillante",
        "soil_check_days": 7, "soil_rule": "Revisa raíces y sustrato; riega cuando estén casi secos y elimina todo exceso.",
        "fertilizer": "Fertilizante para orquídeas, muy diluido, durante crecimiento activo.",
        "history": "Orquídea epífita asiática cuyas raíces necesitan aireación, no tierra compacta.",
        "toxicity": "Generalmente considerada no tóxica para perros y gatos.", "pet_safe": True,
    },
    "succulent": {
        "common_name": "Suculenta", "scientific_name": "Suculenta sin identificar", "light": "Luz brillante; sol directo gradual según especie",
        "soil_check_days": 14, "soil_rule": "Espera a que el sustrato se seque completamente antes de regar.",
        "fertilizer": "Fórmula para cactus/suculentas a baja concentración durante crecimiento activo.",
        "history": "Grupo diverso de plantas que almacenan agua; la especie exacta es necesaria para consejos específicos.",
        "toxicity": "Desconocida hasta confirmar la especie; mantenla fuera del alcance de mascotas.", "pet_safe": None,
    },
    "unknown": {
        "common_name": "Planta por identificar", "scientific_name": "Especie sin confirmar", "light": "Pendiente de identificación",
        "soil_check_days": 7, "soil_rule": "Comprueba la humedad; no riegues sin conocer la condición de la tierra.",
        "fertilizer": "No fertilices hasta confirmar la especie y observar crecimiento activo.",
        "history": "Confirma la identificación para ver información específica y segura.",
        "toxicity": "Desconocida; mantenla fuera del alcance de niños y mascotas.", "pet_safe": None,
    },
}

PLANT_ENVIRONMENT = {
    "pothos": {"plant_type": "Trepadora tropical", "temperature": "65–85 °F (18–29 °C)", "humidity": "Media; agradece humedad moderada"},
    "monstera": {"plant_type": "Trepadora tropical", "temperature": "65–85 °F (18–29 °C)", "humidity": "Media a alta, con circulación de aire"},
    "snake_plant": {"plant_type": "Suculenta tropical", "temperature": "60–85 °F (16–29 °C)", "humidity": "Normal del hogar; evita humedad constante"},
    "spider_plant": {"plant_type": "Herbácea perenne", "temperature": "60–80 °F (16–27 °C)", "humidity": "Media"},
    "aloe": {"plant_type": "Suculenta", "temperature": "55–80 °F (13–27 °C)", "humidity": "Baja; necesita sustrato aireado"},
    "peace_lily": {"plant_type": "Tropical de sotobosque", "temperature": "65–80 °F (18–27 °C)", "humidity": "Media a alta"},
    "basil": {"plant_type": "Hierba aromática anual", "temperature": "65–85 °F (18–29 °C)", "humidity": "Media; evita hojas mojadas por mucho tiempo"},
    "orchid": {"plant_type": "Orquídea epífita", "temperature": "65–80 °F (18–27 °C)", "humidity": "Media a alta con buena ventilación"},
    "succulent": {"plant_type": "Suculenta por confirmar", "temperature": "Depende de la especie exacta", "humidity": "Generalmente baja; confirma la especie"},
    "unknown": {"plant_type": "Tipo por confirmar", "temperature": "Pendiente de identificación", "humidity": "Pendiente de identificación"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def _decode_image(data_url: str) -> tuple[bytes, str, str]:
    match = re.fullmatch(r"data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=\s]+)", str(data_url or ""))
    if not match:
        raise ValueError("Selecciona una foto JPEG, PNG o WebP válida.")
    media_type = match.group(1)
    raw = base64.b64decode(match.group(2), validate=True)
    signature, suffix = IMAGE_TYPES[media_type]
    valid = raw.startswith(signature) and (media_type != "image/webp" or raw[8:12] == b"WEBP")
    if not valid or not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("La foto no es válida o supera 6 MB.")
    return raw, media_type, suffix


def _decode_journal_media(data_url: str) -> tuple[bytes, str, str]:
    if str(data_url or "").startswith("data:image/"):
        return _decode_image(data_url)
    match = re.fullmatch(r"data:(video/mp4);base64,([A-Za-z0-9+/=\s]+)", str(data_url or ""))
    if not match:
        raise ValueError("La revisión debe ser una foto JPEG, PNG o WebP, o un video MP4.")
    raw = base64.b64decode(match.group(2), validate=True)
    if not raw or len(raw) > MAX_JOURNAL_MEDIA_BYTES or b"ftyp" not in raw[:32]:
        raise ValueError("El video no es válido o supera 12 MB.")
    return raw, match.group(1), VIDEO_TYPES[match.group(1)][1]


class HomePlantStore:
    def __init__(self, path: str | Path = "data/roxy_home_plants.json", image_root: str | Path = "data/roxy_home_plants") -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self.image_root = Path(image_root)

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {"schema_version": 1, "households": {}}

    def _read(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return self._empty()
        return value if isinstance(value, dict) else self._empty()

    def _write(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temp_name, self.path)
        finally:
            try: os.unlink(temp_name)
            except FileNotFoundError: pass

    def _locked(self, callback: Callable[[dict[str, Any]], Any]) -> Any:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            if fcntl is not None: fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                value = self._read(); result = callback(value); self._write(value); return result
            finally:
                if fcntl is not None: fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _household(value: dict[str, Any], owner: str) -> dict[str, Any]:
        return value.setdefault("households", {}).setdefault(owner, {"plants": {}, "vacation": {"enabled": False}})

    def snapshot(self, owner: str, user_id: str) -> dict[str, Any]:
        value = self._read(); household = self._household(value, owner)
        plants = [public_plant(row, user_id) for row in household.get("plants", {}).values() if not row.get("archived")]
        plants.sort(key=lambda row: (row.get("room", ""), row.get("display_name", "").casefold()))
        today = date.today().isoformat()
        due = []
        upcoming = []
        for plant in plants:
            for task in plant.get("care_tasks", []):
                if task.get("status") != "PENDING":
                    continue
                enriched = {**task, "plant_id": plant["id"], "plant_name": plant["display_name"], "photo_url": plant["photo_url"]}
                upcoming.append(enriched)
                if str(task.get("due_date") or "") <= today:
                    due.append(enriched)
        due.sort(key=lambda row: (row.get("due_date", ""), row.get("plant_name", "")))
        upcoming.sort(key=lambda row: (row.get("due_date", ""), row.get("plant_name", ""), row.get("title", "")))
        identification_pending = sum(1 for row in plants if row.get("species_key") == "unknown" or row.get("identification", {}).get("status") != "CONFIRMED")
        watched_ids = {row["plant_id"] for row in due}
        return {
            "status": "READY", "plants": plants, "due_today": due, "upcoming_care": upcoming[:30],
            "health_summary": {"total": len(plants), "good": max(0, len(plants) - len(watched_ids) - identification_pending), "watch": len(watched_ids), "needs_identification": identification_pending},
            "environment": {"sensor_status": "not_connected", "temperature_c": None, "humidity_percent": None},
            "vacation": deepcopy(household.get("vacation") or {}), "care_sources": CARE_SOURCES,
        }

    def plant(self, owner: str, plant_id: str) -> dict[str, Any]:
        row = self._household(self._read(), owner).get("plants", {}).get(plant_id)
        if not row or row.get("archived"): raise KeyError(plant_id)
        return deepcopy(row)

    def create(self, owner: str, user_id: str, values: dict[str, Any], identification: dict[str, Any] | None = None) -> dict[str, Any]:
        raw, media_type, suffix = _decode_image(values.get("photo_data_url", ""))
        plant_id = uuid4().hex
        directory = self.image_root / re.sub(r"[^a-zA-Z0-9_.-]+", "_", owner) / plant_id
        directory.mkdir(parents=True, exist_ok=True)
        photo_path = directory / f"original{suffix}"
        photo_path.write_bytes(raw)
        key = _text(values.get("species_key"), 40)
        identification = identification or {}
        proposed_key = _text(identification.get("species_key"), 40)
        if key not in PLANT_CATALOG or key == "unknown":
            key = proposed_key if proposed_key in PLANT_CATALOG and proposed_key != "unknown" else "unknown"
        profile = deepcopy(PLANT_CATALOG[key])
        created = _now()
        first_due = (date.today() + timedelta(days=max(1, int(profile["soil_check_days"])))).isoformat()
        row = {
            "id": plant_id, "owner_id": owner, "created_by": user_id, "display_name": _text(values.get("display_name"), 60) or profile["common_name"],
            "species_key": key, **profile, "room": _text(values.get("room"), 60) or "Sin ubicación", "placement": _text(values.get("placement"), 20) or "indoor",
            "pot_type": _text(values.get("pot_type"), 30) or "unknown", "drainage": bool(values.get("drainage")),
            "light_exposure": _text(values.get("light_exposure"), 40) or "unknown", "notes": _text(values.get("notes"), 800),
            "photo_path": str(photo_path), "photo_media_type": media_type,
            "identification": {
                "status": "CONFIRMED"
                if key != "unknown" and values.get("species_key") not in (None, "", "unknown")
                else "PROPOSED"
                if proposed_key and proposed_key != "unknown"
                else "NEEDS_CONFIRMATION",
                **identification,
            },
            "care_tasks": [
                {"id": uuid4().hex, "action": "CHECK_SOIL", "title": "Revisar tierra y hojas", "due_date": first_due, "cadence_days": profile["soil_check_days"], "status": "PENDING", "calendar_event_id": ""},
                {"id": uuid4().hex, "action": "ROTATE", "title": "Rotar la maceta", "due_date": (date.today() + timedelta(days=14)).isoformat(), "cadence_days": 14, "status": "PENDING", "calendar_event_id": ""},
                {"id": uuid4().hex, "action": "FERTILIZE", "title": "Revisar si necesita fertilizante", "due_date": (date.today() + timedelta(days=30)).isoformat(), "cadence_days": 30, "status": "PENDING", "calendar_event_id": ""},
            ],
            "journal": [], "created_at": created, "updated_at": created, "archived": False,
        }
        def apply(value: dict[str, Any]) -> dict[str, Any]:
            self._household(value, owner)["plants"][plant_id] = row; return deepcopy(row)
        return self._locked(apply)

    def update(self, owner: str, plant_id: str, values: dict[str, Any]) -> dict[str, Any]:
        def apply(value: dict[str, Any]) -> dict[str, Any]:
            row = self._household(value, owner).get("plants", {}).get(plant_id)
            if not row or row.get("archived"): raise KeyError(plant_id)
            for key, limit in (("display_name", 60), ("room", 60), ("placement", 20), ("pot_type", 30), ("light_exposure", 40), ("notes", 800)):
                if key in values: row[key] = _text(values[key], limit)
            if "drainage" in values: row["drainage"] = bool(values["drainage"])
            species_key = _text(values.get("species_key"), 40)
            if species_key and species_key in PLANT_CATALOG and species_key != "unknown":
                row.update(deepcopy(PLANT_CATALOG[species_key]))
                row["species_key"] = species_key
                row["identification"] = {"status": "CONFIRMED", "species_key": species_key, "confidence": 1.0}
            row["updated_at"] = _now(); return deepcopy(row)
        return self._locked(apply)

    def complete_task(self, owner: str, plant_id: str, task_id: str, completed_by: str, observation: str = "") -> dict[str, Any]:
        def apply(value: dict[str, Any]) -> dict[str, Any]:
            row = self._household(value, owner).get("plants", {}).get(plant_id)
            if not row: raise KeyError(plant_id)
            task = next((item for item in row.get("care_tasks", []) if item.get("id") == task_id), None)
            if not task: raise KeyError(task_id)
            task.update({"status": "DONE", "completed_at": _now(), "completed_by": completed_by, "observation": _text(observation, 300)})
            if task.get("action") == "CHECK_SOIL":
                task["result"] = "WATERED" if "reg" in observation.casefold() else "CHECKED"
            cadence = max(1, int(task.get("cadence_days") or row.get("soil_check_days") or 7))
            row.setdefault("care_tasks", []).append({"id": uuid4().hex, "action": task.get("action"), "title": task.get("title"), "due_date": (date.today() + timedelta(days=cadence)).isoformat(), "cadence_days": cadence, "status": "PENDING", "calendar_event_id": ""})
            row["updated_at"] = _now(); return deepcopy(row)
        return self._locked(apply)

    def link_task_calendar(self, owner: str, plant_id: str, task_id: str, event_id: str) -> dict[str, Any]:
        def apply(value: dict[str, Any]) -> dict[str, Any]:
            row = self._household(value, owner).get("plants", {}).get(plant_id)
            if not row or row.get("archived"):
                raise KeyError(plant_id)
            task = next((item for item in row.get("care_tasks", []) if item.get("id") == task_id), None)
            if not task:
                raise KeyError(task_id)
            task["calendar_event_id"] = _text(event_id, 64)
            row["updated_at"] = _now()
            return deepcopy(task)

        return self._locked(apply)

    def add_journal(self, owner: str, plant_id: str, user_id: str, notes: str, photo_data_url: str = "") -> dict[str, Any]:
        photo_path = ""; media_type = ""
        if photo_data_url:
            raw, media_type, suffix = _decode_journal_media(photo_data_url)
            directory = self.image_root / re.sub(r"[^a-zA-Z0-9_.-]+", "_", owner) / plant_id / "journal"; directory.mkdir(parents=True, exist_ok=True)
            photo_path = str(directory / f"{uuid4().hex}{suffix}"); Path(photo_path).write_bytes(raw)
        entry = {"id": uuid4().hex, "created_at": _now(), "created_by": user_id, "notes": _text(notes, 600), "photo_path": photo_path, "photo_media_type": media_type}
        def apply(value: dict[str, Any]) -> dict[str, Any]:
            row = self._household(value, owner).get("plants", {}).get(plant_id)
            if not row: raise KeyError(plant_id)
            row.setdefault("journal", []).append(entry); row["updated_at"] = _now(); return deepcopy(entry)
        return self._locked(apply)

    def set_vacation(self, owner: str, values: dict[str, Any]) -> dict[str, Any]:
        clean = {"enabled": bool(values.get("enabled")), "starts_on": _text(values.get("starts_on"), 10), "ends_on": _text(values.get("ends_on"), 10), "caregiver": _text(values.get("caregiver"), 80), "notes": _text(values.get("notes"), 500), "updated_at": _now()}
        def apply(value: dict[str, Any]) -> dict[str, Any]: self._household(value, owner)["vacation"] = clean; return deepcopy(clean)
        return self._locked(apply)

    def delete(self, owner: str, plant_id: str) -> None:
        def apply(value: dict[str, Any]) -> None:
            row = self._household(value, owner).get("plants", {}).get(plant_id)
            if not row: raise KeyError(plant_id)
            row["archived"] = True; row["updated_at"] = _now()
        self._locked(apply)


class HomePlantIdentifier:
    def __init__(self, config: HomeAIConfig | None = None, client: Any = None) -> None:
        self.config = config; self.client = client

    @classmethod
    def from_env(cls) -> "HomePlantIdentifier":
        try: return cls(HomeAIConfig.from_env())
        except HomeAIConfigurationError: return cls(None)

    @property
    def configured(self) -> bool: return self.config is not None

    def identify(self, data_url: str) -> dict[str, Any]:
        if not self.config: return {"status": "UNAVAILABLE", "species_key": "unknown", "confidence": 0, "alternatives": [], "warning": "La identificación visual no está conectada; elige la especie manualmente."}
        _decode_image(data_url)
        if self.client is None:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.config.api_key)
        ledger = HomeAIBudgetLedger(self.config.budget_path, request_limit=self.config.daily_request_limit, output_token_limit=self.config.daily_output_token_limit)
        ledger.reserve_request()
        schema = {"type": "object", "additionalProperties": False, "required": ["species_key", "confidence", "alternatives", "warning"], "properties": {"species_key": {"type": "string", "enum": sorted(PLANT_CATALOG)}, "confidence": {"type": "number", "minimum": 0, "maximum": 1}, "alternatives": {"type": "array", "items": {"type": "string"}, "maxItems": 3}, "warning": {"type": "string"}}}
        response = self.client.responses.create(model=self.config.routine_model, input=[{"role": "user", "content": [{"type": "input_text", "text": "Identifica la planta de la foto solo si hay rasgos visibles suficientes. Elige la clave de catálogo más cercana; usa unknown si no es fiable. No diagnostiques enfermedades. Devuelve español."}, {"type": "input_image", "image_url": data_url}]}], text={"format": {"type": "json_schema", "name": "roxy_plant_identification", "strict": True, "schema": schema}}, max_output_tokens=500, store=False)
        usage = getattr(response, "usage", None); ledger.record_output_tokens(int(getattr(usage, "output_tokens", 0) or 0))
        result = json.loads(str(getattr(response, "output_text", "") or "{}")); result["status"] = "PROPOSED"; result["confidence"] = min(float(result.get("confidence") or 0), 0.95); return result


def public_plant(row: dict[str, Any], user_id: str) -> dict[str, Any]:
    result = {key: deepcopy(value) for key, value in row.items() if key not in {"photo_path", "photo_media_type"}}
    result["photo_url"] = f"/v1/home-plants/{user_id}/{row['id']}/image"
    for key, value in PLANT_ENVIRONMENT.get(str(row.get("species_key") or "unknown"), PLANT_ENVIRONMENT["unknown"]).items():
        result.setdefault(key, value)
    for entry in result.get("journal", []):
        if entry.get("photo_path"):
            entry["photo_url"] = f"/v1/home-plants/{user_id}/{row['id']}/journal/{entry['id']}/image"
        entry["media_type"] = entry.get("photo_media_type") or ""
        entry.pop("photo_path", None); entry.pop("photo_media_type", None)
    result["sources"] = CARE_SOURCES
    result["product_queries"] = [f"sustrato para {row.get('common_name')}", f"fertilizante para {row.get('common_name')}", "medidor de humedad para plantas"]
    return result
