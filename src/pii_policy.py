"""Política de minimización de PII de contacto según rol.

Roles con contacto (cédula, denunciante, teléfonos): ``operador``, ``admin``.
Rol ``ejecutivo``: sin columnas de contacto en memoria de sesión / UI / descargas.
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd

CONTACT_COLUMNS: tuple[str, ...] = (
    "cedula",
    "denunciante",
    "telefono",
    "telefono_alt",
)


def contact_columns_present(df: pd.DataFrame) -> list[str]:
    if df is None or df.empty:
        return []
    return [c for c in CONTACT_COLUMNS if c in df.columns]


def strip_contact_columns(
    df: pd.DataFrame | None, *, columns: Iterable[str] | None = None
) -> pd.DataFrame:
    """Elimina columnas de contacto (copia)."""
    if df is None:
        return pd.DataFrame()
    if df.empty:
        return df.copy()
    cols = list(columns) if columns is not None else list(CONTACT_COLUMNS)
    drop = [c for c in cols if c in df.columns]
    if not drop:
        return df
    return df.drop(columns=drop)


def mask_cedula(value) -> str:
    s = str(value or "").strip()
    if not s or s.lower() in ("nan", "none"):
        return ""
    digits = "".join(ch for ch in s if ch.isalnum())
    if len(digits) <= 4:
        return "***"
    return f"{digits[:1]}***{digits[-3:]}"


def mask_phone(value) -> str:
    s = str(value or "").strip()
    if not s or s.lower() in ("nan", "none"):
        return ""
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) <= 4:
        return "****"
    return f"****{digits[-4:]}"


def mask_contact_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Enmascara en lugar de borrar (p. ej. previsualizaciones controladas)."""
    if df is None or df.empty:
        return df
    out = df.copy()
    if "cedula" in out.columns:
        out["cedula"] = out["cedula"].map(mask_cedula)
    if "telefono" in out.columns:
        out["telefono"] = out["telefono"].map(mask_phone)
    if "telefono_alt" in out.columns:
        out["telefono_alt"] = out["telefono_alt"].map(mask_phone)
    if "denunciante" in out.columns:
        out["denunciante"] = out["denunciante"].map(
            lambda v: (str(v).strip()[:1] + "***") if str(v).strip() else ""
        )
    return out


def apply_sol_pii_policy(sol: pd.DataFrame, *, allow_contact: bool) -> pd.DataFrame:
    """Aplica política al dataframe de solicitudes 1×10."""
    if allow_contact:
        return sol
    return strip_contact_columns(sol)
