"""
Corrección de encoding / mojibake en textos crudos.

Muchos Excel/CSV de 1×10 llegan con UTF-8 interpretado como Latin-1
(p. ej. «nÃºmero» en lugar de «número»). Se aplica al inicio del pipeline
para que dirección, descripción y territorio se analicen y muestren bien.
"""

from __future__ import annotations

import re
from typing import Iterable

import pandas as pd

# Señales típicas de UTF-8 leído como Latin-1 / Windows-1252
_MOJI_MARKERS = (
    "Ã",
    "Â",
    "â€",
    "ðŸ",
    "ï¿½",
)

# Columnas de texto frecuentes en 1×10 / Habitable
TEXT_COLS_1X10 = (
    "direccion",
    "descripcion",
    "denunciante",
    "estado",
    "municipio",
    "parroquia",
    "codigo_caso",
    "cedula",
    "telefono",
    "telefono_alt",
)

TEXT_COLS_HAB = (
    "nombre_edificacion",
    "direccion",
    "estado",
    "municipio",
    "uso",
    "material",
    "etiqueta",
    "ente",
    "observaciones",
    "inspector_nombre",
    "evento",
)


def looks_mojibake(s: str) -> bool:
    if not s:
        return False
    return any(m in s for m in _MOJI_MARKERS)


# Residuos frecuentes cuando el round-trip parcial falla (mayúsculas mezcladas)
_RESIDUE_MAP = (
    ("Ã\x8d", "Í"),
    ("Ã\x81", "Á"),
    ("Ã\x89", "É"),
    ("Ã\x93", "Ó"),
    ("Ã\x9a", "Ú"),
    ("Ã\x91", "Ñ"),
    ("Ã\xad", "í"),
    ("Ã¡", "á"),
    ("Ã©", "é"),
    ("Ã­", "í"),
    ("Ã³", "ó"),
    ("Ãº", "ú"),
    ("Ã±", "ñ"),
    ("Ã", "Á"),
    ("Ã‰", "É"),
    ("Ã", "Í"),
    ("Ã“", "Ó"),
    ("Ãš", "Ú"),
    ("Ã‘", "Ñ"),
    ("Â¿", "¿"),
    ("Â¡", "¡"),
)


def fix_mojibake_text(value: object) -> str:
    """
    Corrige texto con encoding doble (mojibake) de forma idempotente.
    Vacíos / NaN → ''.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = str(value)
    if s.lower() in ("nan", "none", "<na>"):
        return ""

    # Hasta 3 pases: a veces hay doble corrupción
    for _ in range(3):
        if not looks_mojibake(s):
            break
        try:
            fixed = s.encode("latin-1").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            try:
                fixed = s.encode("cp1252").decode("utf-8")
            except (UnicodeDecodeError, UnicodeEncodeError):
                break
        if fixed == s:
            break
        s = fixed

    # Mapa residual (casos que no cierran el round-trip)
    if looks_mojibake(s) or "Ã" in s:
        for bad, good in _RESIDUE_MAP:
            if bad in s:
                s = s.replace(bad, good)

    # Residuos frecuentes si el round-trip parcial falló
    s = (
        s.replace("NAºMERO", "NÚMERO")
        .replace("NA°MERO", "NÚMERO")
        .replace("nAºmero", "número")
    )
    # Espacios raros / NBSP
    s = s.replace("\xa0", " ").replace("\u200b", "")
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s


def fix_series(series: pd.Series) -> pd.Series:
    return series.map(fix_mojibake_text)


def fix_dataframe_text(
    df: pd.DataFrame,
    cols: Iterable[str] | None = None,
    *,
    keep_raw_suffix: str = "_raw",
    keep_raw_for: Iterable[str] | None = ("direccion",),
) -> pd.DataFrame:
    """
    Corrige columnas de texto in-place (copia).
    Para `keep_raw_for`, guarda el original en `{col}_raw` antes de corregir.
    """
    out = df.copy()
    if cols is None:
        cols = [
            c
            for c in out.columns
            if out[c].dtype == object or str(out[c].dtype) == "string"
        ]
    keep = set(keep_raw_for or ())
    for col in cols:
        if col not in out.columns:
            continue
        raw = out[col]
        if col in keep:
            raw_col = f"{col}{keep_raw_suffix}"
            if raw_col not in out.columns:
                out[raw_col] = raw.fillna("").astype(str)
        out[col] = fix_series(raw)
    return out


def encoding_fix_stats(before: pd.Series, after: pd.Series) -> dict:
    """Cuántas celdas cambiaron tras la corrección."""
    b = before.fillna("").astype(str)
    a = after.fillna("").astype(str)
    changed = int((b != a).sum())
    moji_before = int(b.map(looks_mojibake).sum())
    moji_after = int(a.map(looks_mojibake).sum())
    return {
        "n": int(len(b)),
        "cambiadas": changed,
        "mojibake_antes": moji_before,
        "mojibake_despues": moji_after,
    }
