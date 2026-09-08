"""Small, deliberately non-clinical first-release preference contract."""
from __future__ import annotations

import re
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONSENT_VERSION = "fitness-preferences-v1"
CONSENT_PURPOSE = "fitness_preferences"
Goal = Literal["strength", "muscle_gain", "fat_loss", "healthy_weight_gain", "fitness_habit"]
Day = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TimeWindow(StrictModel):
    start: str
    end: str

    @field_validator("start", "end")
    @classmethod
    def valid_clock(cls, value: str) -> str:
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("Usa una hora local HH:MM.")
        return value

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("La ventana debe terminar después de comenzar, el mismo día.")
        return self


class DayAvailability(StrictModel):
    day: Day
    windows: list[TimeWindow] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def nonoverlapping(self):
        ordered = sorted(self.windows, key=lambda item: item.start)
        if any(a.end > b.start for a, b in zip(ordered, ordered[1:])):
            raise ValueError("Las ventanas de un día no pueden superponerse.")
        return self


class FitnessProfileInput(StrictModel):
    # Null is unknown, never interpreted as an adult or an absence of risk.
    age_band: Literal["18_29", "30_44", "45_64", "65_plus"] | None = None
    language: Literal["es", "en"] = "es"
    weight_unit: Literal["kg", "lb"] = "kg"
    length_unit: Literal["cm", "ft_in"] = "cm"
    timezone: str = Field(min_length=1, max_length=64)
    primary_goal: Goal | None = None
    secondary_goal: Goal | None = None
    without_weight_or_calories: bool = True
    experience: Literal["beginner", "intermediate", "prefer_not_to_say"] = "prefer_not_to_say"
    locations: list[Literal["home", "gym", "outdoors"]] = Field(default_factory=list, max_length=3)
    equipment: list[Literal["bodyweight", "mat", "bands", "dumbbells", "bench", "barbell", "confirmed_gym_machines"]] = Field(default_factory=list, max_length=7)
    availability: list[DayAvailability] = Field(default_factory=list, max_length=7)
    session_minutes: int | None = Field(default=None, ge=5, le=180)
    travel_minutes: int = Field(default=0, ge=0, le=180)

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Selecciona una zona horaria válida.") from None
        return value

    @model_validator(mode="after")
    def consistent_preferences(self):
        if self.secondary_goal and not self.primary_goal:
            raise ValueError("Selecciona primero el objetivo principal.")
        if self.secondary_goal == self.primary_goal and self.primary_goal:
            raise ValueError("Los dos objetivos deben ser distintos.")
        if {self.primary_goal, self.secondary_goal} == {"fat_loss", "healthy_weight_gain"}:
            raise ValueError("Selecciona objetivos compatibles; no perder y aumentar peso a la vez.")
        for entries in (self.locations, self.equipment, [item.day for item in self.availability]):
            if len(entries) != len(set(entries)):
                raise ValueError("No repitas días, lugares o equipo.")
        return self


class FitnessConsentInput(StrictModel):
    purpose: Literal["fitness_preferences"]
    text_version: Literal["fitness-preferences-v1"]
    granted: bool


class FitnessWriteRequest(StrictModel):
    expected_version: int = Field(ge=0, le=2**53 - 1)
    profile: FitnessProfileInput


class FitnessConsentRequest(StrictModel):
    expected_version: int = Field(ge=0, le=2**53 - 1)
    consent: FitnessConsentInput


class FitnessDeleteRequest(StrictModel):
    expected_version: int = Field(ge=0, le=2**53 - 1)
    confirm_delete: Literal[True]

    @field_validator("confirm_delete", mode="before")
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError("Confirma explícitamente que quieres eliminar las preferencias.")
        return value
