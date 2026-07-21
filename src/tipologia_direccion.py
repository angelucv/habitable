"""
Tipología léxica a partir de la dirección 1×10.

Detecta indicios de casa / edificio / apartamento / local / informal
para: (1) enriquecer estadísticas, (2) afinar el agrupamiento GPS,
(3) elegir la dirección representativa del cúmulo.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

import pandas as pd

# Etiquetas canónicas (orden = prioridad al votar en un grupo)
TIPO_LABELS = (
    "casa",
    "edificio",
    "apartamento",
    "local",
    "informal",
    "sin_indicio",
)

TIPO_ETIQUETA = {
    "casa": "Casa / vivienda unifamiliar",
    "edificio": "Edificio / torre / residencia",
    "apartamento": "Apartamento / piso / PH",
    "local": "Local / comercio / oficina",
    "informal": "Rancho / informal",
    "sin_indicio": "Sin tipología en el texto",
}

# Pares que NO deben unirse salvo pin casi idéntico (auto_merge)
_CONFLICTOS = {
    frozenset({"casa", "edificio"}),
    frozenset({"casa", "apartamento"}),
    frozenset({"casa", "local"}),
    frozenset({"casa", "informal"}),
    frozenset({"edificio", "local"}),
    frozenset({"edificio", "informal"}),
    frozenset({"apartamento", "local"}),
    frozenset({"apartamento", "informal"}),
    frozenset({"local", "informal"}),
}

# Patrones (texto ya sin acentos, mayúsculas)
_PATS: list[tuple[str, re.Pattern[str]]] = [
    (
        "informal",
        re.compile(
            r"\bRANCHOS?\b|\bBARRACAS?\b|\bIMPROVISAD|\bCHOZAS?\b|\bCANEY\b"
        ),
    ),
    (
        "apartamento",
        re.compile(
            r"\bAPTOS?\b|\bAPT\.?\b|\bAPARTAMENTOS?\b|\bPISO\s*\d|\bPH\b|"
            r"\bPENTHOUSE\b|\bDUPLEX\b|\bTRIBLEX\b"
        ),
    ),
    (
        "edificio",
        re.compile(
            r"\bEDIFICIOS?\b|\bEDIF\.?\b|\bTORRES?\b|\bRESIDENCIAS?\b|"
            r"\bCONJUNTOS?\b|\bBLOQUES?\b|\bURBANIZACI\w*\b"
        ),
    ),
    (
        "casa",
        re.compile(
            r"\bCASAS?\b|\bCS\.?\b|\bVIVIENDAS?\b|\bCHALETS?\b|\bQUINTAS?\b|"
            r"\bANEXOS?\b|\bHABITACION\b|\bHABITACIONES\b"
        ),
    ),
    (
        "local",
        re.compile(
            r"\bLOCAL(ES)?\b|\bCOMERCIO\b|\bTIENDA\b|\bOFICINA\b|"
            r"\bGALPON(ES)?\b|\bDEPOSITO\b|\bBODEGA\b"
        ),
    ),
]

_UNIT_APTO = re.compile(
    r"(?:APTO|APT\.?|APARTAMENTO)\s*"
    r"(?:N\S{0,12})?\s*(\d+[A-Z]?)",
    re.I,
)
# Casa + número: «casa 57», «casa nro 12», «casa número 207», «casa12»,
# y mojibake «casa naºmero 207»
_UNIT_CASA = re.compile(
    r"(?:CASA|CS\.?)\s*(?:N\S{0,12}\s*)?(\d+[A-Z]?)",
    re.I,
)
_UNIT_PISO = re.compile(
    r"PISO\s*(?:N\S{0,12})?\s*(\d+)",
    re.I,
)
_PALABRA_CASA = re.compile(r"\bCASAS?\b")
_CASA_SN = re.compile(r"\bCASA\s+S\.?\s*/?\s*N\b")
_HAS_NUM = re.compile(r"\d+")


def fix_mojibake(s: str) -> str:
    """Compat: delega en el módulo central de encoding."""
    from text_encoding import fix_mojibake_text

    return fix_mojibake_text(s)


def strip_accents(s: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def normalize_dir(s: object) -> str:
    t = fix_mojibake(str(s or "") if s is not None else "")
    t = strip_accents(t).upper().strip()
    t = re.sub(r"\s+", " ", t)
    t = t.replace("NAºMERO", "NUMERO").replace("NA°MERO", "NUMERO")
    return t


def tiene_palabra_casa(s: object) -> bool:
    return bool(_PALABRA_CASA.search(normalize_dir(s)))


def classify_direccion(s: object) -> str:
    """Una etiqueta canónica por dirección (primera coincidencia por gravedad léxica)."""
    t = normalize_dir(s)
    if not t:
        return "sin_indicio"
    for label, pat in _PATS:
        if pat.search(t):
            return label
    return "sin_indicio"


def extract_unidad(s: object) -> str:
    """
    Identificador de unidad si aparece (apto/casa/piso + número).
    Vacío si no hay señal clara.
    """
    t = normalize_dir(s)
    if not t:
        return ""
    m = _UNIT_APTO.search(t)
    if m:
        return f"apto:{m.group(1).upper()}"
    m = _UNIT_CASA.search(t)
    if m:
        return f"casa:{m.group(1).upper()}"
    if _CASA_SN.search(t):
        return "casa:SN"
    m = _UNIT_PISO.search(t)
    if m:
        return f"piso:{m.group(1)}"
    return ""


def identidad_casa(s: object) -> str:
    """
    Clave de identidad cuando el texto habla de casa.
    - casa:57 / casa:SN si hay número o S/N
    - casa:~TEXTO si dice casa/vivienda sin número
    - '' si no habla de casa
    """
    t = normalize_dir(s)
    if not t:
        return ""
    u = extract_unidad(t)
    if u.startswith("casa:"):
        return u
    if not (_PALABRA_CASA.search(t) or re.search(r"\bVIVIENDAS?\b", t)):
        return ""
    return f"casa:~{t}"


def tipologias_conflictivas(a: str, b: str) -> bool:
    """True si las tipologías no deberían unirse (salvo pin casi idéntico)."""
    if a == "sin_indicio" or b == "sin_indicio":
        return False
    if a == b:
        return False
    # edificio ↔ apartamento: mismo inmueble frecuente → no conflicto duro
    if {a, b} == {"edificio", "apartamento"}:
        return False
    return frozenset({a, b}) in _CONFLICTOS


def unidades_conflictivas(ua: str, ub: str) -> bool:
    """
    True si ambas tienen unidad explícita distinta del mismo tipo
    (apto:3 vs apto:7, casa:12 vs casa:15).
    """
    if not ua or not ub or ua == ub:
        return False
    ka, _, _ = ua.partition(":")
    kb, _, _ = ub.partition(":")
    return ka == kb and ua != ub


def score_direccion_representativa(s: object, tipo: str | None = None) -> float:
    """
    Calidad de la dirección para mostrarla en el cúmulo.
    Más alto = mejor candidato a representante.
    """
    t = normalize_dir(s)
    if not t:
        return 0.0
    tipo = tipo or classify_direccion(t)
    score = 0.0
    # Longitud útil (cap)
    score += min(len(t), 120) / 10.0
    if tipo != "sin_indicio":
        score += 25.0
    if extract_unidad(t):
        score += 12.0
    if _HAS_NUM.search(t):
        score += 8.0
    # Señales de vía
    if re.search(r"\b(CALLE|AVENIDA|AV\.?|CARRERA|VEREDA|CALLEJON)\b", t):
        score += 6.0
    if re.search(r"\b(SECTOR|BARRIO|URB\.?|URBANIZACI)\b", t):
        score += 4.0
    return score


def annotate_tipologia(df: pd.DataFrame, col: str = "direccion") -> pd.DataFrame:
    """Añade tipo_dir, unidad_dir y score_dir_rep."""
    out = df.copy()
    src = out[col] if col in out.columns else pd.Series("", index=out.index)
    out["tipo_dir"] = src.map(classify_direccion)
    out["unidad_dir"] = src.map(extract_unidad)
    out["score_dir_rep"] = [
        score_direccion_representativa(d, t)
        for d, t in zip(src.tolist(), out["tipo_dir"].tolist())
    ]
    return out


def resumen_tipologia(series: Iterable[object] | pd.Series) -> dict[str, int]:
    counts = {k: 0 for k in TIPO_LABELS}
    for s in series:
        counts[classify_direccion(s)] += 1
    return counts
