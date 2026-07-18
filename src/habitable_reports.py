"""
Clasificación de reportes Habitable según solicitud técnica
(Comisión Presidencial — reportes de daños).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

RISK_COLS = [
    "riesgo_externo",
    "riesgo_severo",
    "riesgo_moderado",
    "riesgo_componentes",
]

COMP_COLS = [
    "comp_losa",
    "comp_paredes",
    "comp_tanques",
    "comp_gas_agua_electricidad",
    "comp_ascensores",
    "acc_medidas",
    "acc_inspecciones",
    "serv_electricidad",
    "serv_gas",
    "serv_agua",
    "serv_cantv",
]

COMP_LABELS = {
    "comp_losa": "Losas",
    "comp_paredes": "Paredes",
    "comp_tanques": "Tanques",
    "comp_gas_agua_electricidad": "Gas / agua / electricidad",
    "comp_ascensores": "Ascensores",
    "acc_medidas": "Medidas de acceso",
    "acc_inspecciones": "Inspecciones recomendadas",
    "serv_electricidad": "Servicio electricidad",
    "serv_gas": "Servicio gas",
    "serv_agua": "Servicio agua",
    "serv_cantv": "Servicio telecomunicaciones",
}

MOD_PAIRS = [
    ("Columna o unión", "mod_columna_exam", "mod_columna_mod"),
    ("Muro de concreto", "mod_muro_concreto_exam", "mod_muro_concreto_mod"),
    ("Muro de mampostería", "mod_muro_mamposteria_exam", "mod_muro_mamposteria_mod"),
    ("Viga / arriostramiento", "mod_viga_exam", "mod_viga_mod"),
]

SEV_COLS = [
    ("Columna", "sev_columna"),
    ("Muro concreto", "sev_muro_concreto"),
    ("Muro mampostería", "sev_muro_mamposteria"),
    ("Viga", "sev_viga"),
]

EXT_COLS = [
    ("Colapso estructura", "ext_colapso_estructura"),
    ("Peligro aledaños", "ext_peligro_aledanos"),
    ("Peligro geológico", "ext_peligro_geologico"),
    ("Asentamiento", "ext_asentamiento"),
    ("Inclinación", "ext_inclinacion"),
]


def _norm_abc(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.upper()


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def filter_territorio(
    df: pd.DataFrame,
    estados: list[str] | None = None,
    municipios: list[str] | None = None,
) -> pd.DataFrame:
    out = df
    if estados:
        out = out[out["estado_n"].isin(estados)]
    if municipios:
        out = out[out["municipio_n"].isin(municipios)]
    return out


def mask_no_estructural(df: pd.DataFrame) -> pd.Series:
    """
    riesgo_externo=A, riesgo_severo=A, riesgo_moderado=A,
    riesgo_componentes != A
    """
    re_ = _norm_abc(df.get("riesgo_externo", pd.Series(index=df.index)))
    rs = _norm_abc(df.get("riesgo_severo", pd.Series(index=df.index)))
    rm = _norm_abc(df.get("riesgo_moderado", pd.Series(index=df.index)))
    rc = _norm_abc(df.get("riesgo_componentes", pd.Series(index=df.index)))
    return (re_ == "A") & (rs == "A") & (rm == "A") & (rc != "") & (rc != "A")


def mask_moderado(df: pd.DataFrame) -> pd.Series:
    """riesgo_externo=A, riesgo_severo=A, riesgo_moderado in {A,B,C}."""
    re_ = _norm_abc(df.get("riesgo_externo", pd.Series(index=df.index)))
    rs = _norm_abc(df.get("riesgo_severo", pd.Series(index=df.index)))
    rm = _norm_abc(df.get("riesgo_moderado", pd.Series(index=df.index)))
    return (re_ == "A") & (rs == "A") & rm.isin(["A", "B", "C"])


def mask_severo(df: pd.DataFrame) -> pd.Series:
    """Daño severo: riesgo_severo=C o algún sev_* > 0."""
    rs = _norm_abc(df.get("riesgo_severo", pd.Series(index=df.index)))
    any_sev = pd.Series(False, index=df.index)
    for _, col in SEV_COLS:
        if col in df.columns:
            any_sev = any_sev | (_to_num(df[col]) > 0)
    return (rs == "C") | any_sev


def mask_externo_moderado(df: pd.DataFrame) -> pd.Series:
    """
    ext_colapso_estructura=A y al menos un peligro externo en B.
    """
    colapso = _norm_abc(df.get("ext_colapso_estructura", pd.Series(index=df.index)))
    peligros = [
        "ext_peligro_aledanos",
        "ext_peligro_geologico",
        "ext_asentamiento",
        "ext_inclinacion",
    ]
    any_b = pd.Series(False, index=df.index)
    for c in peligros:
        if c in df.columns:
            any_b = any_b | (_norm_abc(df[c]) == "B")
    return (colapso == "A") & any_b


def mask_externo_alto(df: pd.DataFrame) -> pd.Series:
    """Cualquier campo externo en C."""
    any_c = pd.Series(False, index=df.index)
    for _, col in EXT_COLS:
        if col in df.columns:
            any_c = any_c | (_norm_abc(df[col]) == "C")
    return any_c


def ratio_band(exam: pd.Series, mod: pd.Series) -> pd.Series:
    e = _to_num(exam)
    m = _to_num(mod)
    den = e + m
    ratio = np.where(den > 0, e / den, np.nan)
    out = pd.Series("Sin dato", index=exam.index)
    out = out.mask(den > 0, "Bajo (<10%)")
    out = out.mask((den > 0) & (ratio >= 0.10) & (ratio <= 0.30), "Medio (10–30%)")
    out = out.mask((den > 0) & (ratio > 0.30), "Alto (>30%)")
    return out


def etiqueta_counts(df: pd.DataFrame) -> pd.Series:
    order = ["VERDE", "AMARILLO", "ROJO", "NEGRO"]
    vc = df["etiqueta_n"].value_counts()
    return vc.reindex(order).fillna(0).astype(int)


def component_presence_counts(df: pd.DataFrame) -> dict[str, int]:
    """Cuenta registros con valor informado en cada componente/servicio."""
    out = {}
    for col in COMP_COLS:
        label = COMP_LABELS.get(col, col)
        if col not in df.columns:
            out[label] = 0
            continue
        s = df[col].fillna("").astype(str).str.strip()
        out[label] = int((s != "").sum())
    return out


def moderado_band_summary(df: pd.DataFrame) -> dict:
    bands = ["Bajo (<10%)", "Medio (10–30%)", "Alto (>30%)", "Sin dato"]
    by_element = {}
    medio_flags = []
    alto_flags = []
    for name, exam_c, mod_c in MOD_PAIRS:
        if exam_c not in df.columns or mod_c not in df.columns:
            by_element[name] = {b: 0 for b in bands}
            continue
        band = ratio_band(df[exam_c], df[mod_c])
        vc = band.value_counts()
        by_element[name] = {b: int(vc.get(b, 0)) for b in bands}
        medio_flags.append(band == "Medio (10–30%)")
        alto_flags.append(band == "Alto (>30%)")

    if medio_flags:
        medio_n = int(pd.concat(medio_flags, axis=1).any(axis=1).sum())
    else:
        medio_n = 0
    if alto_flags:
        # combinación: 2+ elementos en alto
        mat = pd.concat(alto_flags, axis=1)
        alto_n = int((mat.sum(axis=1) >= 2).sum())
        alto_al_menos_uno = int(mat.any(axis=1).sum())
    else:
        alto_n = 0
        alto_al_menos_uno = 0

    return {
        "by_element": by_element,
        "combinacion_moderados": medio_n,
        "combinacion_altos_2plus": alto_n,
        "al_menos_un_alto": alto_al_menos_uno,
    }


def severo_mechanism_summary(df: pd.DataFrame) -> dict:
    flags = {}
    for name, col in SEV_COLS:
        if col in df.columns:
            flags[name] = _to_num(df[col]) > 0
        else:
            flags[name] = pd.Series(False, index=df.index)

    mat = pd.DataFrame(flags)
    n_active = mat.sum(axis=1)
    only = {}
    for name in flags:
        only[name] = int(((n_active == 1) & mat[name]).sum())
    combo = int((n_active >= 2).sum())
    return {"solo": only, "combinacion_2plus": combo, "con_algun_sev": int((n_active >= 1).sum())}


def externo_breakdown(df: pd.DataFrame, nivel: str) -> dict[str, int]:
    """nivel: B (moderado) o C (alto)."""
    nivel = nivel.upper()
    out = {}
    flags = []
    for name, col in EXT_COLS:
        if col not in df.columns:
            out[name] = 0
            continue
        m = _norm_abc(df[col]) == nivel
        out[name] = int(m.sum())
        flags.append(m)
    if flags:
        mat = pd.concat(flags, axis=1)
        out["Combinados (2+)"] = int((mat.sum(axis=1) >= 2).sum())
    else:
        out["Combinados (2+)"] = 0
    return out


def count_cuadrillas(df: pd.DataFrame) -> int:
    if "inspector_nombre" not in df.columns:
        return 0
    s = df["inspector_nombre"].fillna("").astype(str).str.strip()
    s = s[(s != "") & (~s.str.lower().isin(["no especificado", "nan", "none"]))]
    return int(s.nunique())


LIST_COLS = [
    "id",
    "nombre_edificacion",
    "etiqueta_n",
    "estado_n",
    "municipio_n",
    "direccion",
    "inspector_nombre",
    "lat",
    "lng",
]


def list_view(df: pd.DataFrame, limit: int = 500) -> pd.DataFrame:
    cols = [c for c in LIST_COLS if c in df.columns]
    return df[cols].head(limit)
