"""NASA map-lite priorizando coincidencias con 1×10 / Habitable / IA.

Los cruces detallados ya usan el inventario completo (2.7M).
Este muestreo para mapa incluye:
  1) TODOS los likely_damaged
  2) TODOS los footprints NASA que coinciden con alguna de las 3 fuentes
     (por defecto ≤ 100 m; configurable)
  3) Relleno de cobertura: 1 pts / celda 500 m del resto

Así el mapa muestra la mayor cantidad posible de casos coincidentes
sin dibujar 2.7M polígonos.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
NASA_PQ = (
    ROOT
    / "data"
    / "external_nasa"
    / "nasa_s1_all_full"
    / "nasa_s1_all_structures.parquet"
)
OUT = ROOT / "data" / "external_nasa" / "nasa_map_lite.parquet"
META = ROOT / "data" / "external_nasa" / "nasa_map_lite_meta.json"

CRUCES = (
    ROOT / "data" / "external_nasa" / "cruce_1x10_nasa" / "cruce_1x10_nasa_detallado.parquet",
    ROOT
    / "data"
    / "external_nasa"
    / "cruce_habitable_nasa"
    / "cruce_habitable_nasa_detallado.parquet",
    ROOT / "data" / "external_nasa" / "cruce_ia_nasa" / "cruce_ia_nasa_detallado.parquet",
)

CELL_M = 500
CRS_METRIC = "EPSG:32619"
COINC_MAX_M = 100.0


def _coinciding_fids(max_m: float = COINC_MAX_M) -> set:
    fids: set = set()
    detail = {}
    for p in CRUCES:
        if not p.exists():
            print(f"  WARN falta cruce: {p}", flush=True)
            continue
        df = pd.read_parquet(p, columns=["nasa_fid", "nasa_dist_m"])
        near = df[df["nasa_dist_m"] <= max_m]
        ids = set(near["nasa_fid"].dropna().tolist())
        detail[p.parent.name] = {
            "rows_le_max": int(len(near)),
            "unique_fid": int(len(ids)),
        }
        fids |= ids
    print("  cruces coincidentes:", json.dumps(detail, ensure_ascii=False), flush=True)
    print(f"  union fids ≤{max_m} m: {len(fids)}", flush=True)
    return fids


def main() -> None:
    t0 = time.time()
    print(f"Cargando NASA completo: {NASA_PQ}", flush=True)
    gdf = gpd.read_parquet(NASA_PQ)
    if gdf.crs is None:
        gdf = gdf.set_crs(4326)
    else:
        gdf = gdf.to_crs(4326)
    assert len(gdf) == 2_700_098 or len(gdf) > 2_000_000, len(gdf)
    print(f"  n_nasa={len(gdf)}", flush=True)

    print("Recolectando fids coincidentes de los 3 cruces…", flush=True)
    coinc_fids = _coinciding_fids(COINC_MAX_M)

    print("Centroides UTM…", flush=True)
    m = gdf.to_crs(CRS_METRIC)
    cent = m.geometry.centroid
    xs = cent.x.values
    ys = cent.y.values
    cent_wgs = gpd.GeoSeries(cent, crs=CRS_METRIC).to_crs(4326)
    lats = cent_wgs.y.values
    lngs = cent_wgs.x.values
    labels = gdf["label"].astype(str).values
    probs = (
        gdf["damage_probability"].values
        if "damage_probability" in gdf.columns
        else np.full(len(gdf), np.nan)
    )
    fids = gdf["fid"].values if "fid" in gdf.columns else np.arange(len(gdf))

    is_likely = labels == "likely_damaged"
    # fid puede ser int; normalizar comparación
    fid_set = coinc_fids
    is_coinc = np.array([f in fid_set for f in fids], dtype=bool)
    # si tipos no matchean (int vs float), reintentar
    if is_coinc.sum() == 0 and len(fid_set):
        sample = next(iter(fid_set))
        if isinstance(sample, (int, np.integer)):
            is_coinc = np.isin(fids.astype(np.int64), list(fid_set))
        else:
            is_coinc = np.isin(fids.astype(object), list(fid_set))

    gx = np.floor(xs / CELL_M).astype(np.int64)
    gy = np.floor(ys / CELL_M).astype(np.int64)
    pri = np.where(labels == "not_assessed", 0, 1)

    df = pd.DataFrame(
        {
            "i": np.arange(len(gdf)),
            "gx": gx,
            "gy": gy,
            "pri": pri,
            "label": labels,
            "lat": lats,
            "lng": lngs,
            "nasa_fid": fids,
            "damage_probability": probs,
            "is_likely": is_likely,
            "is_coinc": is_coinc,
        }
    )

    # 1) likely completo
    likely = df[df["is_likely"]].copy()
    likely["kind"] = "likely_damaged"
    print(f"likely_damaged: {len(likely)}", flush=True)

    # 2) coincidentes (aunque no sean likely) — máxima cobertura de cruces
    coinc = df[df["is_coinc"] & ~df["is_likely"]].copy()
    coinc["kind"] = "coincide_fuentes"
    print(f"coincide_fuentes (no likely): {len(coinc)}", flush=True)

    # 3) relleno grilla 500 m del resto (ni likely ni coinc)
    rest = df[~df["is_likely"] & ~df["is_coinc"]].sort_values(["gx", "gy", "pri", "i"])
    sample = rest.drop_duplicates(["gx", "gy"], keep="first").copy()
    sample["kind"] = "inventario_500m"
    print(f"inventario_500m relleno: {len(sample)}", flush=True)

    out = pd.concat([likely, coinc, sample], ignore_index=True)
    # dedupe por fid por si overlap
    before = len(out)
    out = out.drop_duplicates(subset=["nasa_fid"], keep="first")
    print(f"dedupe fid: {before} -> {len(out)}", flush=True)

    keep = ["lat", "lng", "label", "kind", "nasa_fid", "damage_probability"]
    out = out[keep]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)

    # verificación: ¿cuántos fids coincidentes quedaron fuera?
    out_fids = set(out["nasa_fid"].tolist())
    missing = coinc_fids - out_fids
    # also check likely+coinc kinds cover coinc
    in_lite_coinc = len(coinc_fids & out_fids)

    meta = {
        "cell_m": CELL_M,
        "coinc_max_m": COINC_MAX_M,
        "n_nasa_source": int(len(gdf)),
        "n_total_lite": int(len(out)),
        "n_likely_damaged": int((out["kind"] == "likely_damaged").sum()),
        "n_coincide_fuentes": int((out["kind"] == "coincide_fuentes").sum()),
        "n_inventario_500m": int((out["kind"] == "inventario_500m").sum()),
        "coinc_fids_union": int(len(coinc_fids)),
        "coinc_fids_en_lite": int(in_lite_coinc),
        "coinc_fids_missing": int(len(missing)),
        "by_label": out["label"].value_counts().to_dict(),
        "by_kind": out["kind"].value_counts().to_dict(),
        "cruces_usaron_nasa_completo": True,
        "elapsed_s": round(time.time() - t0, 1),
        "mb": round(OUT.stat().st_size / 1e6, 2),
    }
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2), flush=True)
    if missing:
        print(f"ALERTA: faltan {len(missing)} fids coincidentes en lite", flush=True)
    else:
        print("OK: 100% de fids coincidentes (≤100 m) están en el muestreo.", flush=True)


if __name__ == "__main__":
    main()
