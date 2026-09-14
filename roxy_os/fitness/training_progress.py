"""Read-only, descriptive summaries of the member's validated manual records.

This projection neither recommends an increase nor changes a workout. Dates are
the recorded local dates; the stored write time is not an exercise start time.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from decimal import Decimal

from .training_content import CONTENT_VERSION, training_catalog, training_detail

FORMAT = "roxy-home-training-progress-v1"


def _sum(values):
    """Avoid binary rounding artefacts in manually entered fractional seconds."""
    items = list(values)
    return float(sum((Decimal(str(item)) for item in items), Decimal(0)))


def _difference(current, previous):
    if current is None or previous is None:
        return None
    return float(Decimal(str(current)) - Decimal(str(previous)))


def _number(value):
    return format(value, ".12g").replace(".", ",")


def _programs(provided):
    if provided is None:
        return {item["id"]: training_detail(item["id"]) for item in training_catalog()["programs"]}
    # Injection is for a reviewed content collection, never a client request.
    rows = provided.values() if isinstance(provided, dict) else provided
    return {item["id"]: item for item in rows}


def _current_program(log, programs):
    program = programs.get(log["program_id"])
    return program if program and program["content_version"] == log["content_version"] else None


def _work_exercises(program):
    return {item["id"]: item for item in program["exercises"] if item["phase"] == "work"} if program else {}


def _axis(exercise, detail):
    axes = {"reps" if series["reps"] is not None else "seconds" for series in exercise["sets"]}
    if len(axes) == 1:
        return next(iter(axes))
    if not axes and detail:
        return detail["tracking_unit"]
    return None


def _repeat_available(log, program):
    if not program:
        return False
    expected = _work_exercises(program)
    if {item["exercise_id"] for item in log["exercises"]} != set(expected):
        return False
    for item in log["exercises"]:
        detail = expected[item["exercise_id"]]
        if not item["skipped"] and _axis(item, detail) != detail["tracking_unit"]:
            return False
        if not detail.get("load_recordable", False) and any(series.get("load") is not None for series in item["sets"]):
            return False
    return True


def _entry(log, exercise, program_title):
    sets = deepcopy(exercise["sets"])
    axes = {"reps" if item["reps"] is not None else "seconds" for item in sets}
    reps = sum(item["reps"] for item in sets) if axes == {"reps"} else None
    seconds = _sum(item["seconds"] for item in sets) if axes == {"seconds"} else None
    count = len(sets)
    if exercise["skipped"]:
        label = "Omitido por ti; sin series realizadas."
    else:
        parts = [f"{count} {'serie' if count == 1 else 'series'}"]
        if reps is not None:
            parts.append(f"{reps} repeticiones registradas")
        if seconds is not None:
            parts.append(f"{_number(seconds)} segundos registrados")
        label = " · ".join(parts)
    return {"session_id": log["session_id"], "program_id": log["program_id"],
            "program_title": program_title, "performed_on": log["performed_on"],
            "timezone": log["timezone"], "skipped": exercise["skipped"], "sets": sets,
            "totals": {"sets": count, "reps": reps, "seconds": seconds}, "label": label}


def _comparison(latest, previous, latest_count, previous_count, axis):
    if latest_count > 1 or previous_count > 1:
        return "multiple_entries_on_day", None
    if previous is None:
        return "no_previous_day", None
    if latest["skipped"] or previous["skipped"]:
        return "skipped_entry", None
    if axis not in {"reps", "seconds"}:
        return "unknown_tracking_unit", None
    old, new = previous["sets"], latest["sets"]
    load_deltas = [_difference(new[index].get("load_kg"), old[index].get("load_kg"))
                   if index < len(new) and index < len(old) else None
                   for index in range(max(len(old), len(new)))]
    # Per-index loads compare the first recorded set with the first, and so on;
    # absent loads and unmatched sets never become a zero-load measurement.
    return "compared", {
        "previous_session_id": previous["session_id"],
        "set_count_delta": latest["totals"]["sets"] - previous["totals"]["sets"],
        "reps_delta": _difference(latest["totals"]["reps"], previous["totals"]["reps"]) if axis == "reps" else None,
        "seconds_delta": _difference(latest["totals"]["seconds"], previous["totals"]["seconds"]) if axis == "seconds" else None,
        "load_kg_deltas": load_deltas,
        "label": "Diferencias entre lo que registraste en dos fechas. Las cargas se comparan por orden de serie; estos cambios no miden por sí solos tu fuerza ni tu salud.",
        "interpretation": "descriptive_only",
    }


def training_progress(snapshot, *, programs=None):
    """Project a validated TrainingLogsRepository snapshot without reading profile.

    Exercise histories share exact exercise ID, content version and recording
    unit across routines. Same-day entries have no known exercise order, so no
    comparison is produced when either comparison day contains more than one.
    Missing historical content stays visible but cannot be repeated from here.
    """
    available = _programs(programs)
    logs = sorted(snapshot["logs"], key=lambda item: (item["performed_on"], item["session_id"]), reverse=True)
    grouped = {}
    workouts = []
    inferred_axes = defaultdict(set)
    # If content has been retired, skipped records can join a known historical
    # axis only when the actual records establish one unambiguous unit.
    for log in logs:
        details = _work_exercises(_current_program(log, available))
        for exercise in log["exercises"]:
            axis = _axis(exercise, details.get(exercise["exercise_id"]))
            if axis:
                inferred_axes[(log["content_version"], exercise["exercise_id"])].add(axis)
    for log in logs:
        program = _current_program(log, available)
        title = program["title"] if program else "Rutina guardada"
        details = _work_exercises(program)
        workouts.append({"session_id": log["session_id"], "program_id": log["program_id"],
                         "program_title": title, "content_version": log["content_version"],
                         "performed_on": log["performed_on"], "timezone": log["timezone"],
                         "duration_minutes": log["duration_minutes"],
                         "performed_exercises": sum(not item["skipped"] for item in log["exercises"]),
                         "skipped_exercises": sum(item["skipped"] for item in log["exercises"]),
                         "set_count": sum(len(item["sets"]) for item in log["exercises"]),
                         "can_repeat": _repeat_available(log, program)})
        for exercise in log["exercises"]:
            detail = details.get(exercise["exercise_id"])
            axis = _axis(exercise, detail)
            if axis is None and exercise["skipped"]:
                choices = inferred_axes[(log["content_version"], exercise["exercise_id"])]
                if len(choices) == 1:
                    axis = next(iter(choices))
            # Mismatching stored units never borrow the current exercise label.
            if detail and axis != detail["tracking_unit"]:
                detail = None
            key = f"{log['content_version']}:{exercise['exercise_id']}:{axis or 'unknown'}"
            if key not in grouped:
                grouped[key] = {"key": key, "exercise_id": exercise["exercise_id"],
                                "name": f"Ejercicio guardado ({exercise['exercise_id']})",
                                "content_version": log["content_version"], "tracking_unit": axis,
                                "per_side": None, "current_content_available": False,
                                "source_links": [], "history": []}
            group = grouped[key]
            if detail:
                group.update(name=detail["name"], per_side=detail["dose"]["per_side"],
                             current_content_available=True, source_links=deepcopy(detail["source_links"]))
            group["history"].append(_entry(log, exercise, title))
    exercises = []
    for group in grouped.values():
        history = group["history"]
        latest = history[0]
        previous = next((item for item in history if item["performed_on"] < latest["performed_on"]), None)
        day_counts = Counter(item["performed_on"] for item in history)
        latest_count = day_counts[latest["performed_on"]]
        previous_count = day_counts[previous["performed_on"]] if previous else 0
        reason, comparison = _comparison(latest, previous, latest_count, previous_count, group["tracking_unit"])
        group.update(entry_count=len(history), performed_count=sum(not item["skipped"] for item in history),
                     skipped_count=sum(item["skipped"] for item in history), latest=deepcopy(latest),
                     previous=deepcopy(previous), latest_day_entry_count=latest_count,
                     previous_day_entry_count=previous_count, comparison_reason=reason, comparison=comparison)
        exercises.append(group)
    exercises.sort(key=lambda item: (item["name"].casefold(), item["key"]))
    dates = [item["performed_on"] for item in logs]
    durations = [item["duration_minutes"] for item in logs if item["duration_minutes"] is not None]
    return {"format": FORMAT, "logs_version": snapshot["version"], "content_version": CONTENT_VERSION,
            "updated_at": snapshot["updated_at"], "self_reported": True, "clinical_approval": False,
            "summary": {"recorded_sessions": len(logs), "active_days": len(set(dates)),
                        "exercise_entries": sum(len(item["exercises"]) for item in logs),
                        "performed_exercise_entries": sum(item["performed_exercises"] for item in workouts),
                        "skipped_exercise_entries": sum(item["skipped_exercises"] for item in workouts),
                        "total_sets": sum(item["set_count"] for item in workouts),
                        "first_performed_on": min(dates) if dates else None,
                        "last_performed_on": max(dates) if dates else None,
                        "duration": {"reported_sessions": len(durations), "unreported_sessions": len(logs) - len(durations),
                                     "total_minutes": _sum(durations) if durations else None}},
            "workouts": workouts, "exercises": exercises}
