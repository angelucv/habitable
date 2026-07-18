"""
Límites de memoria para despliegue (Render free / instancias pequeñas)
======================================================================

Render inyecta ``RENDER=true``. El plan free suele tener ~512 MB RAM;
el mapa Folium con decenas de miles de marcadores y el pipeline Excel
superan ese techo con facilidad.

Variables de entorno:
- ``BI_LOW_MEMORY=1`` fuerza el modo austero (también auto si ``RENDER``).
- ``BI_LOW_MEMORY=0`` lo desactiva aunque esté en Render.
- ``BI_MAP_MAX_MARKERS`` tope por capa (default 900 en bajo consumo).
- ``BI_ALLOW_HEAVY_PIPELINE=1`` permite «Procesar cruce» en bajo consumo
  (sigue pudiendo provocar OOM).
"""

from __future__ import annotations

import os


def _env_flag(name: str) -> str | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    return raw.strip().lower()


def is_low_memory() -> bool:
    """True en Render o si BI_LOW_MEMORY=1; False solo si BI_LOW_MEMORY=0."""
    override = _env_flag("BI_LOW_MEMORY")
    if override in ("0", "false", "no", "off"):
        return False
    if override in ("1", "true", "yes", "on"):
        return True
    # Render siempre marca RENDER=true en el servicio
    return _env_flag("RENDER") in ("true", "1", "yes")


def map_max_markers() -> int | None:
    """Tope de puntos por capa; None = sin tope (solo desarrollo local)."""
    raw = os.environ.get("BI_MAP_MAX_MARKERS", "").strip()
    if raw:
        try:
            n = int(raw)
            return None if n <= 0 else n
        except ValueError:
            pass
    if is_low_memory():
        return 900
    return None


def heat_max_points() -> int:
    """Tope de puntos en HeatMap (más liviano que marcadores, pero no infinito)."""
    raw = os.environ.get("BI_HEAT_MAX_POINTS", "").strip()
    if raw:
        try:
            return max(500, int(raw))
        except ValueError:
            pass
    return 4000 if is_low_memory() else 15000


def allow_heavy_pipeline() -> bool:
    """Permite regenerar matching in-process (Excel → parquet)."""
    if not is_low_memory():
        return True
    return _env_flag("BI_ALLOW_HEAVY_PIPELINE") in ("1", "true", "yes", "on")
