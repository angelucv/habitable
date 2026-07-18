"""
Utilidades geográficas y de normalización de texto
=================================================

- ``parse_coord``: repara lat/lng mal formados en Excel.
- ``in_venezuela`` / ``mapa_ok_flag`` / ``quality_flag``: calidad del pin.
- ``is_hotspot``: detecta el punto repetido en Libertador (baja confianza).
- ``normalize_name``: limpia nombres de edificios para fuzzy matching.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

import numpy as np
import pandas as pd

_STOP = {
    "EDIFICIO",
    "EDIF",
    "RESIDENCIAS",
    "RESIDENCIA",
    "TORRE",
    "CONJUNTO",
    "URBANIZACION",
    "URB",
    "CASA",
    "BLOQUE",
    "PH",
    "EL",
    "LA",
    "LOS",
    "LAS",
    "DE",
    "DEL",
    "Y",
}


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def normalize_name(value) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    s = strip_accents(str(value)).upper().strip()
    s = re.sub(r"[^A-Z0-9\s]", " ", s)
    tokens = [t for t in s.split() if t and t not in _STOP]
    return " ".join(tokens)


def parse_coord(value, kind: str = "lat") -> float:
    """Repara coords con coma decimal, espacio o dígitos pegados."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        v = float(value)
        if kind == "lat" and abs(v) <= 90:
            return v
        if kind == "lng" and abs(v) <= 180:
            return v
        # entero enorme tipo 105166178616
        digits = re.sub(r"\D", "", str(value))
        if len(digits) >= 8:
            sign = -1.0 if str(value).strip().startswith("-") or v < 0 else 1.0
            return sign * float(digits[:2] + "." + digits[2:])
        return np.nan

    t = str(value).strip().replace(",", ".")
    if " " in t:
        parts = t.split()
        if len(parts) == 2 and all(
            p.replace(".", "").replace("-", "").isdigit() for p in parts
        ):
            t = parts[0] + "." + parts[1]

    try:
        v = float(t)
    except ValueError:
        digits = re.sub(r"\D", "", t)
        if len(digits) >= 8:
            sign = -1.0 if "-" in t else 1.0
            return sign * float(digits[:2] + "." + digits[2:])
        return np.nan

    if kind == "lat" and abs(v) > 90:
        digits = re.sub(r"\D", "", t)
        if len(digits) >= 8:
            sign = -1.0 if "-" in t or v < 0 else 1.0
            return sign * float(digits[:2] + "." + digits[2:])
        return np.nan
    if kind == "lng" and abs(v) > 180:
        digits = re.sub(r"\D", "", t)
        if len(digits) >= 8:
            sign = -1.0 if "-" in t or v < 0 else 1.0
            return sign * float(digits[:2] + "." + digits[2:])
        return np.nan
    return v


def in_venezuela(lat: float, lng: float, cfg: dict) -> bool:
    if np.isnan(lat) or np.isnan(lng):
        return False
    return (
        cfg["lat_min"] <= lat <= cfg["lat_max"]
        and cfg["lng_min"] <= lng <= cfg["lng_max"]
    )


def is_hotspot(lat: float, lng: float, cfg: dict) -> bool:
    if np.isnan(lat) or np.isnan(lng):
        return False
    d = int(cfg.get("hotspot_decimals", 6))
    return round(lat, d) == round(cfg["hotspot_lat"], d) and round(
        lng, d
    ) == round(cfg["hotspot_lng"], d)


def haversine_m(lat1, lng1, lat2, lng2) -> float:
    r = 6371000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dl = np.radians(lng2 - lng1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return float(2 * r * np.arcsin(np.sqrt(a)))


# Bboxes generosos por estado (solo para validar GPS vs etiqueta administrativa)
STATE_BBOX: dict[str, tuple[float, float, float, float]] = {
    # lat_min, lat_max, lng_min, lng_max
    "CARACAS": (10.35, 10.55, -67.15, -66.70),
    "DISTRITO CAPITAL": (10.35, 10.55, -67.15, -66.70),
    "LA GUAIRA": (10.45, 10.62, -67.20, -66.75),
    "VARGAS": (10.45, 10.62, -67.20, -66.75),
    "MIRANDA": (10.15, 10.58, -67.10, -65.80),
    "ARAGUA": (9.90, 10.55, -68.00, -66.70),
    "CARABOBO": (9.95, 10.55, -68.50, -67.55),
    "YARACUY": (9.90, 10.70, -69.20, -68.20),
    "LARA": (9.50, 10.70, -70.60, -68.80),
    "FALCON": (10.70, 12.20, -71.40, -68.00),
    "ZULIA": (8.50, 11.90, -73.40, -70.50),
    "NUEVA ESPARTA": (10.85, 11.20, -64.50, -63.70),
    "SUCRE": (10.20, 10.80, -64.50, -61.80),
    "ANZOATEGUI": (7.80, 10.30, -65.70, -62.40),
}

# Estados cuya costa/norte legítimo supera ~10.70
NORTHERN_COAST_OK = {
    "FALCON",
    "ZULIA",
    "NUEVA ESPARTA",
    "SUCRE",
    "ANZOATEGUI",
    "MONAGAS",
    "DELTA AMACURO",
}

# Límite norte de tierra firme en el litoral central (lng, lat_max).
# Todo lo que esté al norte de esta polilínea ≈ mar Caribe.
# Valores ligeramente al sur de la línea de costa real para no pintar GPS offshore.
COAST_NORTH_CENTRAL: list[tuple[float, float]] = [
    (-67.30, 10.530),
    (-67.20, 10.555),
    (-67.12, 10.575),  # Taguao / Catia La Mar oeste
    (-67.05, 10.590),
    (-67.00, 10.598),  # Maiquetía
    (-66.95, 10.600),  # La Guaira
    (-66.90, 10.605),  # Macuto
    (-66.85, 10.612),  # Caraballeda
    (-66.80, 10.616),  # Naiguatá
    (-66.75, 10.612),
    (-66.70, 10.580),
    (-66.60, 10.550),
]


def coast_max_lat(lng: float) -> float | None:
    """Latitud máxima de tierra para un lng en el litoral central; None si fuera de rango."""
    pts = COAST_NORTH_CENTRAL
    if lng < pts[0][0] or lng > pts[-1][0]:
        return None
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        if x0 <= lng <= x1:
            if x1 == x0:
                return max(y0, y1)
            t = (lng - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return pts[-1][1]


def in_state_bbox(lat: float, lng: float, estado_n: str) -> bool:
    """True si no hay bbox del estado o el punto cae dentro."""
    if np.isnan(lat) or np.isnan(lng):
        return False
    key = (estado_n or "").upper().strip()
    box = STATE_BBOX.get(key)
    if box is None:
        return True
    la0, la1, lo0, lo1 = box
    return la0 <= lat <= la1 and lo0 <= lng <= lo1


def is_open_caribbean(lat: float, lng: float, estado_n: str) -> bool:
    """GPS en mar: al norte de la costa central o umbrales por estado."""
    if np.isnan(lat) or np.isnan(lng):
        return True
    key = (estado_n or "").upper().strip()
    if key in NORTHERN_COAST_OK:
        return False

    # Polilínea costera (Caracas / La Guaira / Miranda costera)
    max_lat = coast_max_lat(lng)
    if max_lat is not None and lat > max_lat + 0.001:
        return True

    # Norte genérico fuera del corredor costero modelado
    if lat > 10.68:
        return True
    if key in {"CARACAS", "DISTRITO CAPITAL", "MIRANDA"} and lat > 10.56:
        return True
    if key in {"LA GUAIRA", "VARGAS"} and lat < 10.45:
        return True
    return False


def mapa_ok_flag(lat: float, lng: float, estado_n: str, cfg: dict) -> bool:
    """Punto apto para pintar en mapa (evita GPS basura en el Caribe)."""
    if not in_venezuela(lat, lng, cfg):
        return False
    if is_open_caribbean(lat, lng, estado_n):
        return False
    if not in_state_bbox(lat, lng, estado_n):
        return False
    return True


def quality_flag(lat: float, lng: float, cfg: dict, estado_n: str = "") -> str:
    if np.isnan(lat) or np.isnan(lng):
        return "sin_coords"
    if not in_venezuela(lat, lng, cfg):
        return "fuera_ve"
    if is_hotspot(lat, lng, cfg):
        return "hotspot"
    if is_open_caribbean(lat, lng, estado_n):
        return "mar_abierto"
    if estado_n and not in_state_bbox(lat, lng, estado_n):
        return "fuera_estado"
    # precisión pobre
    s = f"{lat:.10f}".rstrip("0")
    decimals = len(s.split(".")[1]) if "." in s else 0
    if decimals < 5:
        return "baja_precision"
    return "alta"
