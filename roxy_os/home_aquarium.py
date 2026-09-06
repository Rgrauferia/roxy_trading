"""Inventory and conservative stocking checks, not an automatic compatibility certificate."""
from __future__ import annotations

import math

from roxy_os.home_pet_habitats import identity


def validate_inhabitants(value):
    if not isinstance(value, list) or len(value) > 12:
        raise ValueError("Añade como máximo 12 grupos de habitantes por acuario.")
    clean = []
    for row in value:
        if not isinstance(row, dict) or set(row) - {"species", "count", "sex", "adult_cm"}:
            raise ValueError("Revisa los datos de cada habitante.")
        name = str(row.get("species") or "").strip()
        if not name or len(name) > 100:
            raise ValueError("Cada grupo necesita su especie exacta (hasta 100 caracteres).")
        try:
            count = float(row.get("count", 0))
            adult = None if row.get("adult_cm") in {None, ""} else float(row["adult_cm"])
        except (ValueError, TypeError):
            raise ValueError("Revisa cantidad y tamaño adulto de cada especie.") from None
        if isinstance(row.get("count"), bool) or not math.isfinite(count) or count != int(count) or not 1 <= count <= 1000:
            raise ValueError("La cantidad de habitantes debe ser un número entero entre 1 y 1000.")
        if adult is not None and (isinstance(row.get("adult_cm"), bool) or not math.isfinite(adult) or not 0 < adult <= 500):
            raise ValueError("Indica un tamaño adulto válido en centímetros o déjalo vacío.")
        sex = row.get("sex") or "unknown"
        if sex not in {"male", "female", "mixed", "unknown"}:
            raise ValueError("Revisa el sexo registrado para cada grupo.")
        clean.append({"species": name, "count": int(count), "sex": sex, "adult_cm": adult})
    return clean


def aquarium_assessment(values):
    inhabitants = values.get("inhabitants") or []
    count = sum(row["count"] for row in inhabitants)
    alerts = []
    if inhabitants and values.get("residents") is not None and count != values["residents"]:
        alerts.append(f"Hay {count} habitantes detallados, pero el total guardado es {int(values['residents'])}. Revisa ambas cantidades.")
    bettas = [row for row in inhabitants if "betta" in identity(row["species"])]
    if sum(row["count"] for row in bettas if row["sex"] == "male") > 1:
        alerts.append("No mantengas dos machos betta en el mismo acuario. Revisa una separación segura con un especialista.")
    goldfish = any(any(term in identity(row["species"]) for term in ("goldfish", "carassius", "pez dorado")) for row in inhabitants)
    if bettas and goldfish:
        alerts.append("Betta y goldfish tienen necesidades de temperatura y manejo diferentes: no se recomienda esta combinación.")
    if any(row.get("adult_cm") is None for row in inhabitants):
        alerts.append("Falta el tamaño adulto de algún habitante; su tamaño actual no basta para dimensionar el acuario.")
    volume = values.get("volume_l")
    capacity = "Confirma el volumen real, dimensiones, filtración, tamaño adulto, territorio y necesidades de grupo antes de añadir animales."
    if volume is not None:
        capacity = f"{volume:g} L de agua registrados para {count} habitantes detallados. Este cociente no demuestra espacio suficiente: falta revisar las necesidades de cada especie."
    return {"status": "REVIEW_REQUIRED", "inhabitants": inhabitants, "count": count,
            "alerts": alerts, "capacity_note": capacity,
            "compatibility_note": "Sin alertas detectadas no significa convivencia segura. La lista de Roxy no cubre todas las combinaciones; confirma la población completa con un especialista.",
            "sources": [
                {"label": "RSPCA · convivencia de peces", "url": "https://www.rspca.org.uk/en/adviceandwelfare/pets/fish/company"},
                {"label": "RSPCA Victoria · necesidades de agua", "url": "https://rspcavic.org/learn/fish"},
            ]}
