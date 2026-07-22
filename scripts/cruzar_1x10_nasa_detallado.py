"""Cruce detallado local: 1×10 × NASA S1 Structures (inventario completo).

Para cada ubicación 1×10 (representante, GPS ok):
  1) ¿cae DENTRO de algún footprint NASA?
  2) si no, distancia al polígono/centroide más cercano
  3) etiqueta NASA (likely_damaged / not_damaged / not_assessed),
     probabilidad, overture_id, fid

Salida: parquet + resumen JSON en data/external_nasa/cruce_1x10_nasa/
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import prepare, STRtree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from secure_io import read_parquet  # noqa: E402
NASA_GJ = (
    ROOT
    / "data"
    / "external_nasa"
    / "nasa_s1_all_full"
    / "nasa_s1_all_structures.geojson"
)
NASA_PQ = (
    ROOT
    / "data"
    / "external_nasa"
    / "nasa_s1_all_full"
    / "nasa_s1_all_structures.parquet"
)
SOL_PQ = ROOT / "data" / "processed" / "solicitudes.parquet"
OUT = ROOT / "data" / "external_nasa" / "cruce_1x10_nasa"
OUT.mkdir(parents=True, exist_ok=True)

# UTM 19N — costa Caracas / La Guaira
CRS_METRIC = "EPSG:32619"
RADII_M = (30, 50, 100, 200)


def load_nasa() -> gpd.GeoDataFrame:
    if NASA_PQ.exists():
        print(f"Cargando NASA parquet: {NASA_PQ}", flush=True)
        gdf = gpd.read_parquet(NASA_PQ)
    else:
        print(f"Cargando NASA GeoJSON (~1.4 GB): {NASA_GJ}", flush=True)
        t0 = time.time()
        gdf = gpd.read_file(NASA_GJ, engine="pyogrio")
        print(f"  leído n={len(gdf)} en {time.time()-t0:.0f}s", flush=True)
        # normalizar columnas
        keep = [
            c
            for c in [
                "fid",
                "overture_id",
                "subtype",
                "class",
                "coverage_fraction",
                "within_coverage",
                "label",
                "damage_probability",
                "damage",
                "geometry",
            ]
            if c in gdf.columns
        ]
        gdf = gdf[keep].copy()
        print("  guardando parquet para reusos futuros...", flush=True)
        gdf.to_parquet(NASA_PQ, index=False)
        print(
            f"  parquet OK MB={NASA_PQ.stat().st_size/1024/1024:.1f}",
            flush=True,
        )
    if gdf.crs is None:
        gdf = gdf.set_crs(4326)
    else:
        gdf = gdf.to_crs(4326)
    return gdf


def load_1x10() -> gpd.GeoDataFrame:
    sol = read_parquet(SOL_PQ)
    s = sol.dropna(subset=["lat", "lng"]).copy()
    if "mapeable" in s.columns:
        s = s[s["mapeable"].fillna(False)]
    if "mapa_ok" in s.columns:
        s = s[s["mapa_ok"].fillna(False)]
    if "es_representante" in s.columns:
        s = s[s["es_representante"].fillna(True)]
    gdf = gpd.GeoDataFrame(
        s,
        geometry=gpd.points_from_xy(s["lng"], s["lat"]),
        crs=4326,
    )
    print(f"1×10 ubicaciones a cruzar: {len(gdf)}", flush=True)
    return gdf


def main() -> None:
    t_all = time.time()
    nasa = load_nasa()
    print("labels NASA:", nasa["label"].value_counts(dropna=False).to_dict(), flush=True)
    sol = load_1x10()

    print(f"Proyectando a {CRS_METRIC}...", flush=True)
    nasa_m = nasa.to_crs(CRS_METRIC)
    sol_m = sol.to_crs(CRS_METRIC)

    # Centroides NASA para nearest rápido
    print("Centroides NASA + STRtree...", flush=True)
    nasa_m = nasa_m.copy()
    nasa_m["geom_poly"] = nasa_m.geometry
    nasa_m["geometry"] = nasa_m.geometry.centroid
    # tree sobre polígonos originales para within / distance
    polys = list(nasa_m["geom_poly"].values)
    tree = STRtree(polys)
    # prepared for within checks on candidates
    print("Matching detallado (within + nearest)...", flush=True)

    rows = []
    pts = list(sol_m.geometry.values)
    # Batch query nearest via tree
    # shapely STRtree.nearest returns index of nearest geom
    nearest_idx = tree.nearest(pts)

    for i, (pt, j) in enumerate(zip(pts, nearest_idx)):
        poly = polys[int(j)]
        # within exacto del nearest; si no, buscar cualquier within en bbox pequeño
        inside = bool(poly.contains(pt))
        if not inside:
            # candidatos que intersectan un buffer pequeño
            cand = tree.query(pt.buffer(5.0))  # 5 m buffer query
            for k in cand:
                if polys[int(k)].contains(pt):
                    j = int(k)
                    poly = polys[j]
                    inside = True
                    break

        dist = 0.0 if inside else float(poly.distance(pt))
        rec = nasa_m.iloc[int(j)]
        src = sol_m.iloc[i]
        rows.append(
            {
                "codigo_caso": src.get("codigo_caso", ""),
                "lat": float(src.get("lat")),
                "lng": float(src.get("lng")),
                "estado_n": src.get("estado_n", ""),
                "municipio_n": src.get("municipio_n", ""),
                "parroquia_n": src.get("parroquia_n", ""),
                "direccion": src.get("direccion_display", src.get("direccion", "")),
                "match_cat": src.get("match_cat", ""),
                "n_reportes": src.get("n_reportes", 1),
                "nasa_fid": rec.get("fid", rec.get("OBJECTID", None)),
                "nasa_overture_id": str(rec.get("overture_id", "") or ""),
                "nasa_label": str(rec.get("label", "") or ""),
                "nasa_damage": rec.get("damage", None),
                "nasa_damage_probability": rec.get("damage_probability", None),
                "nasa_within": inside,
                "nasa_dist_m": dist,
                "nasa_prioridad": (
                    "alta"
                    if str(rec.get("label", "")) == "likely_damaged"
                    and (inside or dist <= 50)
                    else (
                        "media"
                        if str(rec.get("label", "")) == "not_damaged"
                        and (inside or dist <= 50)
                        else (
                            "sin_radar"
                            if dist > 100
                            else "revisar"
                        )
                    )
                ),
            }
        )
        if (i + 1) % 5000 == 0:
            print(f"  procesados {i+1}/{len(pts)}", flush=True)

    out = pd.DataFrame(rows)
    out_path = OUT / "cruce_1x10_nasa_detallado.parquet"
    out.to_parquet(out_path, index=False)
    print(f"saved {out_path} n={len(out)}", flush=True)

    # Resumen
    summary = {
        "n_1x10": int(len(out)),
        "n_nasa": int(len(nasa)),
        "within_polygon": int(out["nasa_within"].sum()),
        "within_pct": round(100 * float(out["nasa_within"].mean()), 2),
        "by_label_all_nearest": out["nasa_label"].value_counts(dropna=False).to_dict(),
        "by_prioridad": out["nasa_prioridad"].value_counts(dropna=False).to_dict(),
        "dist_m": {
            "median": round(float(out["nasa_dist_m"].median()), 2),
            "p90": round(float(out["nasa_dist_m"].quantile(0.9)), 2),
            "mean": round(float(out["nasa_dist_m"].mean()), 2),
        },
        "radios": {},
    }
    for r in RADII_M:
        near = out[out["nasa_dist_m"] <= r]
        summary["radios"][str(r)] = {
            "n": int(len(near)),
            "pct": round(100 * len(near) / max(len(out), 1), 2),
            "by_label": near["nasa_label"].value_counts(dropna=False).to_dict(),
            "likely_damaged": int((near["nasa_label"] == "likely_damaged").sum()),
            "not_damaged": int((near["nasa_label"] == "not_damaged").sum()),
            "not_assessed": int((near["nasa_label"] == "not_assessed").sum()),
        }

    # pendientes 1x10 con señal daño NASA
    if "match_cat" in out.columns:
        pend = out[out["match_cat"] == "solo_1x10"]
        summary["pendientes_solo_1x10"] = {
            "n": int(len(pend)),
            "likely_damaged_le50": int(
                (
                    (pend["nasa_label"] == "likely_damaged")
                    & (pend["nasa_dist_m"] <= 50)
                ).sum()
            ),
            "not_damaged_le50": int(
                (
                    (pend["nasa_label"] == "not_damaged") & (pend["nasa_dist_m"] <= 50)
                ).sum()
            ),
            "sin_radar_gt100": int((pend["nasa_dist_m"] > 100).sum()),
        }

    sum_path = OUT / "summary_cruce_1x10_nasa.json"
    sum_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    print(f"elapsed_total_s={time.time()-t_all:.0f}", flush=True)


if __name__ == "__main__":
    main()
