"""
Análisis de descripción 1×10 (referencia)
=========================================

Clasificación heurística por palabras clave en el campo `descripcion`.
No sustituye inspección de campo ni el semáforo Habitable: solo referencia
para orientar lectura de la demanda ciudadana.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

import pandas as pd

# Orden de gravedad (mayor = más severo en la heurística)
NIVEL_ORDEN = {
    "sin_texto": 0,
    "sin_indicios": 1,
    "leve_aparente": 2,
    "moderado_aparente": 3,
    "severo_aparente": 4,
    "critico_aparente": 5,
}

NIVEL_ETIQUETA = {
    "sin_texto": "Sin descripción",
    "sin_indicios": "Sin indicios claros en el texto",
    "leve_aparente": "Leve aparente (referencia)",
    "moderado_aparente": "Moderado aparente (referencia)",
    "severo_aparente": "Severo aparente (referencia)",
    "critico_aparente": "Crítico aparente (referencia)",
}

# Frases / tokens (sin acentos, mayúsculas) → nivel
# Se evalúa del más grave al más leve (primera coincidencia gana el piso;
# luego se puede subir si hay más señales).
_CRITICO = [
    "colapso",
    "colapsado",
    "derrumbe",
    "derrumb",
    "inhabitable",
    "evacu",
    "riesgo inminente",
    "peligro inminente",
    "caida total",
    "caido el techo",
    "hundimiento",
    "se vino abajo",
    "destruido",
    "destruccion total",
]

_SEVERO = [
    "columna",
    "columnas",
    "viga",
    "vigas",
    "fractura",
    "fracturad",
    "estructural",
    "estructura",
    "inclin",
    "asentamiento",
    "desplome",
    "desplom",
    "riesgo de colapso",
    "peligro de colapso",
    "losas",
    "losa",
    "cimiento",
    "cimientos",
]

_MODERADO = [
    "grieta",
    "grietas",
    "agrietad",
    "fisura",
    "fisuras",
    "desprend",
    "despegad",
    "rajadur",
    "hendidur",
    "paredes",
    "pared",
    "balcon",
    "ventana",
    "ventanas",
    "humedad",
    "filtracion",
]

_LEVE = [
    "cosmetico",
    "pintura",
    "estuco",
    "ceramica",
    "vidrio",
    "puerta",
    "revision",
    "revisar",
]


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def normalizar_texto(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = _strip_accents(str(value)).upper().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _hit_any(text: str, patterns: list[str]) -> list[str]:
    found = []
    for p in patterns:
        token = _strip_accents(p).upper()
        if token and token in text:
            found.append(p)
    return found


def clasificar_descripcion(texto) -> dict:
    """
    Devuelve nivel heurístico + palabras detectadas.
    Solo referencia; no es dictamen técnico.
    """
    raw = "" if texto is None or (isinstance(texto, float) and pd.isna(texto)) else str(texto)
    norm = normalizar_texto(raw)
    if not norm:
        return {
            "nivel_descripcion": "sin_texto",
            "nivel_descripcion_label": NIVEL_ETIQUETA["sin_texto"],
            "nivel_score": 0,
            "palabras_clave": "",
        }

    hits: list[str] = []
    nivel = "sin_indicios"
    for patterns, cand in (
        (_CRITICO, "critico_aparente"),
        (_SEVERO, "severo_aparente"),
        (_MODERADO, "moderado_aparente"),
        (_LEVE, "leve_aparente"),
    ):
        found = _hit_any(norm, patterns)
        if found:
            hits.extend(found)
            nivel = cand
            break

    # Refuerzo: si ya hay severo y además crítico, subir
    if nivel != "critico_aparente":
        crit = _hit_any(norm, _CRITICO)
        if crit:
            hits = list(dict.fromkeys(crit + hits))
            nivel = "critico_aparente"
        elif nivel in ("sin_indicios", "leve_aparente"):
            sev = _hit_any(norm, _SEVERO)
            if sev:
                hits = list(dict.fromkeys(sev + hits))
                nivel = "severo_aparente"
            elif nivel == "sin_indicios":
                mod = _hit_any(norm, _MODERADO)
                if mod:
                    hits = list(dict.fromkeys(mod + hits))
                    nivel = "moderado_aparente"

    hits = list(dict.fromkeys(hits))[:12]
    return {
        "nivel_descripcion": nivel,
        "nivel_descripcion_label": NIVEL_ETIQUETA[nivel],
        "nivel_score": NIVEL_ORDEN[nivel],
        "palabras_clave": ", ".join(hits),
    }


def enrich_descripciones(sol: pd.DataFrame) -> pd.DataFrame:
    """Añade columnas de clasificación por descripción a cada caso."""
    out = sol.copy()
    if "descripcion" not in out.columns:
        out["descripcion"] = ""
        out["nivel_descripcion"] = "sin_texto"
        out["nivel_descripcion_label"] = NIVEL_ETIQUETA["sin_texto"]
        out["nivel_score"] = 0
        out["palabras_clave"] = ""
        return out

    rows = out["descripcion"].map(clasificar_descripcion)
    extra = pd.DataFrame(list(rows))
    for c in extra.columns:
        out[c] = extra[c].values
    return out


def resumen_niveles(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "nivel_descripcion" not in df.columns:
        return pd.DataFrame(columns=["nivel", "etiqueta", "n", "pct"])
    vc = df["nivel_descripcion"].value_counts()
    n = int(vc.sum()) or 1
    rows = []
    for code, cnt in vc.items():
        rows.append(
            {
                "nivel": code,
                "etiqueta": NIVEL_ETIQUETA.get(str(code), str(code)),
                "n": int(cnt),
                "pct": round(100 * int(cnt) / n, 1),
            }
        )
    rows.sort(key=lambda r: -NIVEL_ORDEN.get(r["nivel"], 0))
    return pd.DataFrame(rows)


def top_palabras(df: pd.DataFrame, top_n: int = 30) -> pd.DataFrame:
    """Frecuencia de tokens útiles en descripciones (minería simple)."""
    if df is None or df.empty or "descripcion" not in df.columns:
        return pd.DataFrame(columns=["palabra", "n"])
    stop = {
        "DE",
        "LA",
        "EL",
        "EN",
        "Y",
        "A",
        "LOS",
        "LAS",
        "DEL",
        "SE",
        "QUE",
        "CON",
        "POR",
        "UN",
        "UNA",
        "AL",
        "ES",
        "SU",
        "PARA",
        "COMO",
        "MAS",
        "HAY",
        "HAN",
        "TODO",
        "TODA",
        "MIS",
        "MI",
        "NOS",
        "YA",
        "SI",
        "NO",
        "O",
        "THE",
        "EDIFICIO",
        "CASA",
        "APTO",
        "APARTAMENTO",
    }
    bag: Counter[str] = Counter()
    for t in df["descripcion"].fillna("").astype(str):
        norm = normalizar_texto(t)
        tokens = re.findall(r"[A-Z0-9]{4,}", norm)
        for tok in tokens:
            if tok in stop:
                continue
            bag[tok] += 1
    return pd.DataFrame(bag.most_common(top_n), columns=["palabra", "n"])


def frame_casos_por_nivel(
    sol: pd.DataFrame,
    *,
    niveles: list[str] | None = None,
    estados: list[str] | None = None,
    limit: int = 500,
) -> pd.DataFrame:
    """Muestra casos enriquecidos para la UI / descarga."""
    enr = enrich_descripciones(sol)
    if estados and "estado_n" in enr.columns:
        enr = enr[enr["estado_n"].isin(estados)]
    if niveles:
        enr = enr[enr["nivel_descripcion"].isin(niveles)]
    cols = [
        c
        for c in [
            "codigo_caso",
            "nivel_descripcion_label",
            "palabras_clave",
            "descripcion",
            "direccion",
            "estado_n",
            "municipio_n",
            "parroquia_n",
            "match_cat",
            "n_reportes",
        ]
        if c in enr.columns
    ]
    return (
        enr.sort_values("nivel_score", ascending=False)[cols]
        .head(limit)
        .reset_index(drop=True)
    )


def agregar_nivel_a_ubicaciones(
    ubicaciones: pd.DataFrame,
    sol: pd.DataFrame,
) -> pd.DataFrame:
    """
    Une a cada ubicación el peor nivel de descripción entre sus casos
    (referencia; no es prioridad operativa).
    """
    if ubicaciones is None or ubicaciones.empty:
        return ubicaciones
    enr = enrich_descripciones(sol)
    if "dedup_key" not in enr.columns or "dedup_key" not in ubicaciones.columns:
        return ubicaciones

    def _worst(g: pd.DataFrame) -> pd.Series:
        i = g["nivel_score"].idxmax()
        row = g.loc[i]
        return pd.Series(
            {
                "nivel_descripcion_ref": row["nivel_descripcion_label"],
                "palabras_clave_ref": row["palabras_clave"],
            }
        )

    agg = enr.groupby("dedup_key", sort=False).apply(_worst).reset_index()
    # groupby.apply puede dejar dedup_key como índice o columna según pandas
    if "dedup_key" not in agg.columns and agg.index.name == "dedup_key":
        agg = agg.reset_index()
    return ubicaciones.merge(agg, on="dedup_key", how="left")
