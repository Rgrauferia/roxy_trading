"""Trusted, bounded Home screen context. Never receives browser-supplied facts."""
from typing import Any, Literal

HomeScreen = Literal["", "house", "kitchen", "today", "recipes", "pets", "plants", "fitness", "design", "family", "calendar", "shopping", "pantry", "more"]

_SCREENS = {
    "house": ("Mi casa", "Entradas a los espacios de Home y preferencias de la casa."),
    "kitchen": ("Cocina", "Recetas, plan de comidas y despensa."),
    "today": ("Hoy", "Comidas del día, lista pendiente y próximos eventos."),
    "recipes": ("Recetas", "Explorar comidas, bebidas y postres; guardar recetas y abrir su preparación paso a paso."),
    "pets": ("Mascotas", "Perfiles por especie, cuidados, historial y alimentación apropiada. No todas las especies tienen recetas."),
    "plants": ("Jardín", "Registrar plantas, revisar su ubicación y condiciones y consultar cuidados y recordatorios."),
    "fitness": ("Ejercicio", "Registro personal, biblioteca y experiencia de entrenamiento. La disponibilidad de un plan debe comprobarse en el módulo."),
    "design": ("Renueva", "Añadir fotos de un espacio, indicar prioridades y revisar propuestas."),
    "family": ("Nexo", "Mapa, ubicación autorizada y clima. Este contexto no incluye coordenadas ni clima actual."),
    "calendar": ("Calendario", "Consultar eventos y revisar borradores antes de guardarlos."),
    "shopping": ("Compra", "Lista de productos, cantidades y preparación de compras. Comprar requiere confirmación explícita."),
    "pantry": ("Despensa", "Alimentos disponibles y cantidades registradas."),
    "more": ("Espacios y ajustes", "Acceso a módulos, perfil y configuración."),
}


def build_application_context(screen: str = "", recipe: dict[str, Any] | None = None) -> dict[str, Any]:
    key = screen if screen in _SCREENS else ""
    label, features = _SCREENS.get(key, ("Roxy Home", "Recetas, compras, despensa y espacios del hogar."))
    result: dict[str, Any] = {
        "name": "Roxy Home", "screen": key, "screen_label": label,
        "screen_functions": features,
        "scope": "Asistente integrado de Home, no conexión a Muse personal ni al dot de ChatGPT. Las funciones descritas no prueban que haya datos o un servicio externo disponible.",
    }
    if recipe:
        result["selected_recipe"] = {
            "id": str(recipe.get("id") or "")[:100],
            "title": str(recipe.get("title") or "")[:200],
            "servings": recipe.get("servings"),
            "ingredients": [
                {key: item.get(key) for key in ("name", "quantity", "unit", "notes")}
                for item in (recipe.get("ingredients") or [])[:40] if isinstance(item, dict)
            ],
            "steps": [str(step)[:2000] for step in (recipe.get("steps") or [])[:50]],
        }
    return result
