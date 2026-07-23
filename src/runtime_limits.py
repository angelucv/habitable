"""
Límites de memoria, subida y pipeline (despliegue / auditoría)
=============================================================

Render inyecta ``RENDER=true``. El plan free suele tener ~512 MB RAM;
el mapa Folium con decenas de miles de marcadores y el pipeline Excel
superan ese techo con facilidad.

Variables de entorno:
- ``BI_LOW_MEMORY=1`` fuerza el modo austero (también auto si ``RENDER``).
- ``BI_LOW_MEMORY=0`` lo desactiva aunque esté en Render.
- ``BI_MAP_MAX_MARKERS`` tope por capa (default 900 en bajo consumo).
- ``BI_ALLOW_HEAVY_PIPELINE=1`` permite «Procesar cruce» en bajo consumo
  (sigue pudiendo provocar OOM).
- ``BI_UPLOAD_MAX_MB`` tope por archivo subido (default 40 MB; 25 en bajo consumo).
- ``BI_PIPELINE_MAX_ROWS`` tope orientativo de filas 1×10+Habitable combinadas
  tras leer (default 200_000; 80_000 en bajo consumo). 0 = sin tope.
"""

from __future__ import annotations

import os
from typing import Any


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


def upload_max_mb() -> int:
    """Tope de tamaño por archivo de carga (MB)."""
    raw = os.environ.get("BI_UPLOAD_MAX_MB", "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    return 25 if is_low_memory() else 40


def upload_max_bytes() -> int:
    return int(upload_max_mb() * 1024 * 1024)


def pipeline_max_rows() -> int | None:
    """Tope de filas combinadas (1×10 + Habitable) al procesar; None = sin tope."""
    raw = os.environ.get("BI_PIPELINE_MAX_ROWS", "").strip()
    if raw:
        try:
            n = int(raw)
            return None if n <= 0 else n
        except ValueError:
            pass
    return 80_000 if is_low_memory() else 200_000


def check_upload_size(uploaded: Any, *, label: str = "archivo") -> str | None:
    """
    Valida tamaño del ``UploadedFile`` de Streamlit.
    Devuelve mensaje de error o ``None`` si OK.
    """
    if uploaded is None:
        return None
    try:
        nbytes = int(getattr(uploaded, "size", None) or len(uploaded.getbuffer()))
    except Exception:
        return None
    limit = upload_max_bytes()
    if nbytes > limit:
        mb = nbytes / (1024 * 1024)
        return (
            f"{label} pesa {mb:.1f} MB y el tope es {upload_max_mb()} MB. "
            f"Reduzca el archivo o suba BI_UPLOAD_MAX_MB."
        )
    return None


def pipeline_blocked_message() -> str | None:
    """Si el pipeline no debe correr en esta instancia, mensaje para la UI."""
    if allow_heavy_pipeline():
        return None
    return (
        "Esta instancia está en modo bajo consumo (Render / BI_LOW_MEMORY). "
        "No se permite «Procesar cruce» aquí para evitar caída por memoria. "
        "Genere el cruce en un entorno con más RAM o defina "
        "BI_ALLOW_HEAVY_PIPELINE=1 bajo su responsabilidad."
    )
