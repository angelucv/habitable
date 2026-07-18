"""
Deduplicación espacial de solicitudes 1×10
==========================================

Varias personas pueden reportar el mismo edificio. Este módulo agrupa
puntos dentro de ``dedupe_radius_m`` (BallTree + BFS) y deja un
representante con ``n_reportes`` y ``es_representante``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

_MATCH_RANK = {
    "coincide_alta": 0,
    "coincide_media": 1,
    "solo_1x10": 2,
    "coincide_geo_solo": 3,
    "no_mapeable": 4,
}

R_EARTH = 6_371_000.0


def _cluster_by_radius(
    lat: np.ndarray,
    lng: np.ndarray,
    radius_m: float,
) -> np.ndarray:
    """
    Asigna id de cluster por proximidad (radio en metros).
    Unión de vecinos dentro del radio (componentes conexas aproximadas
    vía BFS sobre vecinos del BallTree).
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

    cluster_id = 0
    for i in range(n):
        if labels[i] >= 0:
            continue
        # BFS
        stack = [i]
        labels[i] = cluster_id
        while stack:
            j = stack.pop()
            for k in neighbors[j]:
                if labels[k] < 0:
                    labels[k] = cluster_id
                    stack.append(int(k))
        cluster_id += 1
    return labels


def dedupe_solicitudes(
    sol: pd.DataFrame,
    *,
    radius_m: float = 20.0,
) -> pd.DataFrame:
    """
    Agrupa solicitudes mapeables a menos de `radius_m` metros.
    Conserva un representante por grupo (mejor match_cat) y anota n_reportes.
    """
    out = sol.copy()
    out["dedup_key"] = ""
    out["n_reportes"] = 1
    out["codigos_grupo"] = out["codigo_caso"].astype(str)
    out["es_representante"] = True

    mapeable = out["mapeable"].fillna(False).to_numpy()
    idx = np.flatnonzero(mapeable)
    if len(idx) == 0:
        # no mapeables: cada uno su grupo
        out["dedup_key"] = [f"nm:{c}" for c in out["codigo_caso"].astype(str)]
        return out

    lat = out.loc[idx, "lat"].to_numpy(dtype=float)
    lng = out.loc[idx, "lng"].to_numpy(dtype=float)
    labels = _cluster_by_radius(lat, lng, radius_m)

    # claves
    keys = np.array([""] * len(out), dtype=object)
    keys[~mapeable] = [f"nm:{c}" for c in out.loc[~mapeable, "codigo_caso"].astype(str)]
    keys[idx] = [f"c{int(x)}" for x in labels]
    out["dedup_key"] = keys

    out["_rank"] = out.get("match_cat", "no_mapeable").map(
        lambda x: _MATCH_RANK.get(str(x), 9)
    )
    out["_mapa_pref"] = (
        (~out["mapa_ok"]).astype(int) if "mapa_ok" in out.columns else 0
    )
    out = out.sort_values(
        ["dedup_key", "_rank", "_mapa_pref", "codigo_caso"],
        kind="mergesort",
    )

    sizes = out.groupby("dedup_key", sort=False)["codigo_caso"].transform("count")
    codes = out.groupby("dedup_key", sort=False)["codigo_caso"].transform(
        lambda s: " | ".join(s.astype(str).head(8))
    )
    out["n_reportes"] = sizes.astype(int)
    out["codigos_grupo"] = codes
    out["es_representante"] = ~out.duplicated(subset=["dedup_key"], keep="first")
    out["dedupe_radius_m"] = float(radius_m)

    out = out.drop(columns=["_rank", "_mapa_pref"], errors="ignore")
    return out


def resumen_dedupe(sol: pd.DataFrame) -> dict:
    if "es_representante" not in sol.columns:
        return {}
    mapeable = sol[sol.get("mapeable", True) == True]  # noqa: E712
    reps = mapeable[mapeable["es_representante"]]
    multi = reps[reps["n_reportes"] >= 2]
    return {
        "solicitudes_mapeables": int(len(mapeable)),
        "ubicaciones_unicas": int(len(reps)),
        "ubicaciones_con_multiples_reportes": int(len(multi)),
        "reportes_en_grupos_multi": int(multi["n_reportes"].sum()) if len(multi) else 0,
        "max_reportes_misma_ubicacion": int(reps["n_reportes"].max())
        if len(reps)
        else 0,
        "dedupe_radius_m": float(sol["dedupe_radius_m"].iloc[0])
        if "dedupe_radius_m" in sol.columns and len(sol)
        else None,
    }
