"""Deduplicación espacial estricta de solicitudes 1×10 (para inspecciones)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from rapidfuzz import fuzz
from sklearn.neighbors import BallTree

from tipologia_direccion import (
    annotate_tipologia,
    classify_direccion,
    extract_unidad,
    identidad_casa,
    normalize_dir,
    tipologias_conflictivas,
)

# Umbral extra cuando el texto habla de casa (misma casa, no solo barrio)
DEFAULT_CASA_ADDR_MIN = 92.0

_MATCH_RANK = {
    "coincide_alta": 0,
    "coincide_media": 1,
    "solo_1x10": 2,
    "coincide_geo_solo": 3,
    "no_mapeable": 4,
}

R_EARTH = 6_371_000.0

# Defaults orientados a visita casa/edificio por casa
DEFAULT_RADIUS_M = 10.0
DEFAULT_ADDR_MIN = 75
# Pins casi idénticos: aún así exigen similitud mínima de dirección
DEFAULT_AUTO_MERGE_M = 3.0
DEFAULT_AUTO_ADDR_MIN = 55.0


def _addr_score(a: str, b: str) -> float:
    if not a and not b:
        return 100.0
    if not a or not b:
        return 0.0
    return float(fuzz.token_set_ratio(a, b))


def _haversine_m(lat1, lng1, lat2, lng2) -> float:
    lat1, lng1, lat2, lng2 = map(np.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlng / 2) ** 2
    return float(2 * R_EARTH * np.arcsin(np.sqrt(a)))


def _puede_unir(
    dist: float,
    dir_a: str,
    dir_b: str,
    tipo_a: str,
    tipo_b: str,
    unidad_a: str,
    unidad_b: str,
    id_casa_a: str,
    id_casa_b: str,
    *,
    radius_m: float,
    addr_score_min: float,
    auto_merge_m: float,
    auto_addr_min: float,
    casa_addr_min: float = DEFAULT_CASA_ADDR_MIN,
) -> bool:
    """Reglas estrictas GPS + dirección + tipología + misma casa."""
    if dist > radius_m:
        return False
    if tipologias_conflictivas(tipo_a, tipo_b):
        return False

    # —— Regla dura «casa»: solo la misma casa ——
    if id_casa_a or id_casa_b:
        # Una habla de casa y la otra no → no unir (evita puentes por barrio)
        if bool(id_casa_a) != bool(id_casa_b):
            return False
        # Ambas hablan de casa: deben ser la misma identidad
        # (mismo nº, o mismo texto completo si no hay nº)
        if id_casa_a != id_casa_b:
            return False
        # Casa sin número (huella casa:~…): solo si el texto es casi idéntico
        if id_casa_a.startswith("casa:~"):
            if _addr_score(dir_a, dir_b) < 98.0:
                return False
        # Casa con número: aún así exigir dirección coherente (misma calle)
        else:
            need = max(float(addr_score_min), float(casa_addr_min))
            if dist <= auto_merge_m:
                need = min(need, max(float(auto_addr_min), 85.0))
            return _addr_score(dir_a, dir_b) >= need

    # Unidad apto/piso (sin palabra casa): misma unidad exacta
    if unidad_a != unidad_b:
        return False

    score = _addr_score(dir_a, dir_b)
    if dist <= auto_merge_m:
        return score >= auto_addr_min
    return score >= addr_score_min


def _cluster_strict(
    lat: np.ndarray,
    lng: np.ndarray,
    direcciones: list[str],
    tipos: list[str],
    unidades: list[str],
    ids_casa: list[str],
    *,
    radius_m: float,
    addr_score_min: float,
    auto_merge_m: float,
    auto_addr_min: float = DEFAULT_AUTO_ADDR_MIN,
) -> np.ndarray:
    """
    Componentes conexas: arista solo si distancia ≤ radius_m Y
    dirección/tipología/unidad/casa coherentes.
    """
    n = len(lat)
    labels = np.full(n, -1, dtype=int)
    if n == 0:
        return labels
    if n == 1:
        return np.array([0], dtype=int)

    coords = np.radians(np.column_stack([lat, lng]))
    tree = BallTree(coords, metric="haversine")
    rad = radius_m / R_EARTH
    neighbors = tree.query_radius(coords, r=rad)

    adj: list[list[int]] = [[] for _ in range(n)]
    for i in range(n):
        for j in neighbors[i]:
            j = int(j)
            if j <= i:
                continue
            dist = _haversine_m(lat[i], lng[i], lat[j], lng[j])
            if _puede_unir(
                dist,
                direcciones[i],
                direcciones[j],
                tipos[i],
                tipos[j],
                unidades[i],
                unidades[j],
                ids_casa[i],
                ids_casa[j],
                radius_m=radius_m,
                addr_score_min=addr_score_min,
                auto_merge_m=auto_merge_m,
                auto_addr_min=auto_addr_min,
            ):
                adj[i].append(j)
                adj[j].append(i)

    cluster_id = 0
    for i in range(n):
        if labels[i] >= 0:
            continue
        stack = [i]
        labels[i] = cluster_id
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if labels[v] < 0:
                    labels[v] = cluster_id
                    stack.append(v)
        cluster_id += 1
    return labels


def _tipo_grupo(series: pd.Series) -> str:
    """Mayoría tipológica del grupo (ignora sin_indicio si hay otra)."""
    vc = series.value_counts()
    if vc.empty:
        return "sin_indicio"
    con = vc.drop(labels=["sin_indicio"], errors="ignore")
    if len(con):
        return str(con.index[0])
    return "sin_indicio"


def dedupe_solicitudes(
    sol: pd.DataFrame,
    *,
    radius_m: float = DEFAULT_RADIUS_M,
    addr_score_min: float = DEFAULT_ADDR_MIN,
    auto_merge_m: float = DEFAULT_AUTO_MERGE_M,
    auto_addr_min: float = DEFAULT_AUTO_ADDR_MIN,
) -> pd.DataFrame:
    """
    Agrupa solicitudes mapeables para mapa/estadística de ubicación.

    Criterio estricto (orientado a Habitable: casa/edificio a visitar):
    - radio GPS ≤ radius_m (default 10 m)
    - dirección similar (≥ addr_score_min); pin ≤ auto_merge_m exige ≥ auto_addr_min
    - tipología léxica conflictiva (casa↔edificio, etc.) no une
    - unidades explícitas distintas (apto 3 vs apto 12 / casa 11 vs 27) no unen

    Representante: mejor cruce Habitable → GPS OK → dirección más rica
    (tipología + unidad + longitud) → codigo_caso.
    """
    out = annotate_tipologia(sol, "direccion" if "direccion" in sol.columns else "")

    out["dedup_key"] = ""
    out["n_reportes"] = 1
    out["codigos_grupo"] = out["codigo_caso"].astype(str)
    out["es_representante"] = True
    out["dedupe_radius_m"] = float(radius_m)
    out["dedupe_addr_min"] = float(addr_score_min)
    out["dedupe_auto_m"] = float(auto_merge_m)
    out["dedupe_auto_addr_min"] = float(auto_addr_min)
    out["tipo_ubicacion"] = out["tipo_dir"]
    out["direccion_display"] = (
        out["direccion"] if "direccion" in out.columns else ""
    )

    mapeable = out["mapeable"].fillna(False).to_numpy()
    idx = np.flatnonzero(mapeable)
    if len(idx) == 0:
        out["dedup_key"] = [f"nm:{c}" for c in out["codigo_caso"].astype(str)]
        out["nota_agrupacion"] = (
            "Sin GPS usable: cada caso es su propia ubicación."
        )
        return out

    lat = out.loc[idx, "lat"].to_numpy(dtype=float)
    lng = out.loc[idx, "lng"].to_numpy(dtype=float)
    dir_col = "direccion" if "direccion" in out.columns else None
    dirs = [
        normalize_dir(out.loc[i, dir_col] if dir_col else "")
        for i in idx
    ]
    tipos = [classify_direccion(d) for d in dirs]
    unidades = [extract_unidad(d) for d in dirs]
    ids_casa = [identidad_casa(d) for d in dirs]
    labels = _cluster_strict(
        lat,
        lng,
        dirs,
        tipos,
        unidades,
        ids_casa,
        radius_m=float(radius_m),
        addr_score_min=float(addr_score_min),
        auto_merge_m=float(auto_merge_m),
        auto_addr_min=float(auto_addr_min),
    )

    keys = np.array([""] * len(out), dtype=object)
    keys[~mapeable] = [f"nm:{c}" for c in out.loc[~mapeable, "codigo_caso"].astype(str)]
    keys[idx] = [f"c{int(x)}" for x in labels]
    out["dedup_key"] = keys

    # Tipología del grupo (mayoría)
    tipo_g = out.groupby("dedup_key", sort=False)["tipo_dir"].transform(_tipo_grupo)
    out["tipo_ubicacion"] = tipo_g

    out["_rank"] = out.get("match_cat", "no_mapeable").map(
        lambda x: _MATCH_RANK.get(str(x), 9)
    )
    out["_mapa_pref"] = (
        (~out["mapa_ok"]).astype(int) if "mapa_ok" in out.columns else 0
    )
    # Representante: cruce → GPS → riqueza de dirección → código
    out["_score_neg"] = -out["score_dir_rep"].astype(float)
    out = out.sort_values(
        ["dedup_key", "_rank", "_mapa_pref", "_score_neg", "codigo_caso"],
        kind="mergesort",
    )

    sizes = out.groupby("dedup_key", sort=False)["codigo_caso"].transform("count")
    codes = out.groupby("dedup_key", sort=False)["codigo_caso"].transform(
        lambda s: " | ".join(dict.fromkeys(s.astype(str).tolist()))
    )
    out["n_reportes"] = sizes.astype(int)
    out["codigos_grupo"] = codes
    out["es_representante"] = ~out.duplicated(subset=["dedup_key"], keep="first")

    # Dirección mostrada = la del representante (propagada al grupo)
    rep_dir = (
        out.loc[out["es_representante"], ["dedup_key", "direccion"]]
        .drop_duplicates("dedup_key")
        .set_index("dedup_key")["direccion"]
    )
    if "direccion" in out.columns:
        out["direccion_display"] = out["dedup_key"].map(rep_dir).fillna(out["direccion"])
    else:
        out["direccion_display"] = ""

    r = float(radius_m)
    a = float(addr_score_min)
    am = float(auto_merge_m)
    aa = float(auto_addr_min)

    def _nota(n: int) -> str:
        if n <= 1:
            return "Caso único en su ubicación (criterio estricto + tipología)."
        return (
            f"{n} reportes agrupados (≤{r:.0f} m y dirección similar ≥{a:.0f}; "
            f"pin ≤{am:.0f} m exige texto ≥{aa:.0f}; tipología/unidad coherentes). "
            "Puede haber más de una edificación: revisar cada codigo_caso."
        )

    out["nota_agrupacion"] = out["n_reportes"].map(
        lambda n: _nota(int(n)) if pd.notna(n) else _nota(1)
    )

    out = out.drop(
        columns=["_rank", "_mapa_pref", "_score_neg"],
        errors="ignore",
    )
    return out


def resumen_dedupe(sol: pd.DataFrame) -> dict:
    if "es_representante" not in sol.columns:
        return {}
    mapeable = sol[sol.get("mapeable", True) == True]  # noqa: E712
    reps = mapeable[mapeable["es_representante"]]
    multi = reps[reps["n_reportes"] >= 2]
    out = {
        "solicitudes_mapeables": int(len(mapeable)),
        "ubicaciones_unicas": int(len(reps)),
        "ubicaciones_con_multiples_reportes": int(len(multi)),
        "reportes_en_grupos_multi": int(multi["n_reportes"].sum()) if len(multi) else 0,
        "max_reportes_misma_ubicacion": int(reps["n_reportes"].max())
        if len(reps)
        else 0,
        "dedupe_radius_m": float(sol["dedupe_radius_m"].iloc[0])
        if "dedupe_radius_m" in sol.columns and len(sol)
        else DEFAULT_RADIUS_M,
        "dedupe_addr_min": float(sol["dedupe_addr_min"].iloc[0])
        if "dedupe_addr_min" in sol.columns and len(sol)
        else DEFAULT_ADDR_MIN,
        "dedupe_auto_m": float(sol["dedupe_auto_m"].iloc[0])
        if "dedupe_auto_m" in sol.columns and len(sol)
        else DEFAULT_AUTO_MERGE_M,
        "dedupe_auto_addr_min": float(sol["dedupe_auto_addr_min"].iloc[0])
        if "dedupe_auto_addr_min" in sol.columns and len(sol)
        else DEFAULT_AUTO_ADDR_MIN,
        "dedupe_modo": "estricto_gps_direccion_tipologia",
    }
    if "tipo_dir" in sol.columns:
        vc = sol["tipo_dir"].value_counts()
        out["tipologia_dir"] = {str(k): int(v) for k, v in vc.items()}
    if "tipo_ubicacion" in reps.columns:
        vc2 = reps["tipo_ubicacion"].value_counts()
        out["tipologia_ubicaciones"] = {str(k): int(v) for k, v in vc2.items()}
    return out
