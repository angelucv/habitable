"""Cruce detallado local: Habitable × NASA S1 Structures (inventario completo).

Misma lógica que 1×10: within polígono + distancia al más cercano (UTM 19N).
Reutiliza parquet NASA si existe.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import STRtree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from secure_io import read_parquet  # noqa: E402
NASA_PQ = (
    ROOT
    / "data"
    / "external_nasa"
    / "nasa_s1_all_full"
    / "nasa_s1_all_structures.parquet"
)
HAB_PQ = ROOT / "data" / "processed" / "inspecciones.parquet"
OUT = ROOT / "data" / "external_nasa" / "cruce_habitable_nasa"
OUT.mkdir(parents=True, exist_ok=True)

CRS_METRIC = "EPSG:32619"
RADII_M = (30, 50, 100, 200)


def load_nasa() -> gpd.GeoDataFrame:
    print(f"Cargando NASA parquet: {NASA_PQ}", flush=True)
    gdf = gpd.read_parquet(NASA_PQ)
    if gdf.crs is None:
        gdf = gdf.set_crs(4326)
    else:
        gdf = gdf.to_crs(4326)
    return gdf


def load_habitable() -> gpd.GeoDataFrame:
    h = read_parquet(HAB_PQ)
    s = h.dropna(subset=["lat", "lng"]).copy()
    if "mapeable" in s.columns:
        s = s[s["mapeable"].fillna(False)]
    if "mapa_ok" in s.columns:
        s = s[s["mapa_ok"].fillna(False)]
    gdf = gpd.GeoDataFrame(
        s,
        geometry=gpd.points_from_xy(s["lng"], s["lat"]),
        crs=4326,
    )
    print(f"Habitable ubicaciones a cruzar (mapa_ok): {len(gdf)}", flush=True)
    return gdf


def main() -> None:
    t_all = time.time()
    nasa = load_nasa()
    print("labels NASA:", nasa["label"].value_counts(dropna=False).to_dict(), flush=True)
    hab = load_habitable()

    print(f"Proyectando a {CRS_METRIC}...", flush=True)
    nasa_m = nasa.to_crs(CRS_METRIC)
    hab_m = hab.to_crs(CRS_METRIC)

    print("Polígonos NASA + STRtree...", flush=True)
    nasa_m = nasa_m.copy()
    polys = list(nasa_m.geometry.values)
    tree = STRtree(polys)

    print("Matching detallado (within + nearest)...", flush=True)
    pts = list(hab_m.geometry.values)
    nearest_idx = tree.nearest(pts)

    rows = []
    for i, (pt, j) in enumerate(zip(pts, nearest_idx)):
        poly = polys[int(j)]
        inside = bool(poly.contains(pt))
        if not inside:
            for k in tree.query(pt.buffer(5.0)):
                if polys[int(k)].contains(pt):
                    j = int(k)
                    poly = polys[j]
                    inside = True
                    break

        dist = 0.0 if inside else float(poly.distance(pt))
        rec = nasa_m.iloc[int(j)]
        src = hab_m.iloc[i]
        label = str(rec.get("label", "") or "")
        rows.append(
            {
                "id": src.get("id", ""),
                "etiqueta_n": src.get("etiqueta_n", src.get("etiqueta", "")),
                "nombre_edificacion": src.get("nombre_edificacion", ""),
                "direccion": src.get("direccion", ""),
                "estado_n": src.get("estado_n", ""),
                "municipio_n": src.get("municipio_n", ""),
                "lat": float(src.get("lat")),
                "lng": float(src.get("lng")),
                "uso_n": src.get("uso_n", ""),
                "nasa_fid": rec.get("fid", None),
                "nasa_overture_id": str(rec.get("overture_id", "") or ""),
                "nasa_label": label,
                "nasa_damage": rec.get("damage", None),
                "nasa_damage_probability": rec.get("damage_probability", None),
                "nasa_within": inside,
                "nasa_dist_m": dist,
                "nasa_prioridad": (
                    "alta"
                    if label == "likely_damaged" and (inside or dist <= 50)
                    else (
                        "media"
                        if label == "not_damaged" and (inside or dist <= 50)
                        else ("sin_radar" if dist > 100 else "revisar")
                    )
                ),
            }
        )
        if (i + 1) % 5000 == 0:
            print(f"  procesados {i+1}/{len(pts)}", flush=True)

    out = pd.DataFrame(rows)
    out_path = OUT / "cruce_habitable_nasa_detallado.parquet"
    out.to_parquet(out_path, index=False)
    print(f"saved {out_path} n={len(out)}", flush=True)

    summary: dict = {
        "n_habitable": int(len(out)),
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
        "by_etiqueta_le50": {},
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

    near50 = out[out["nasa_dist_m"] <= 50]
    for etiq, g in near50.groupby("etiqueta_n"):
        summary["by_etiqueta_le50"][str(etiq)] = {
            "n": int(len(g)),
            "likely_damaged": int((g["nasa_label"] == "likely_damaged").sum()),
            "pct_likely": round(
                100 * float((g["nasa_label"] == "likely_damaged").mean()), 2
            ),
            "not_damaged": int((g["nasa_label"] == "not_damaged").sum()),
            "not_assessed": int((g["nasa_label"] == "not_assessed").sum()),
        }

    # ROJO/NEGRO con likely_damaged
    crit = out[out["etiqueta_n"].isin(["ROJO", "NEGRO"])]
    summary["criticos_rojo_negro"] = {
        "n": int(len(crit)),
        "likely_damaged_le50": int(
            (
                (crit["nasa_label"] == "likely_damaged") & (crit["nasa_dist_m"] <= 50)
            ).sum()
        ),
        "not_damaged_le50": int(
            ((crit["nasa_label"] == "not_damaged") & (crit["nasa_dist_m"] <= 50)).sum()
        ),
        "sin_radar_gt100": int((crit["nasa_dist_m"] > 100).sum()),
    }

    sum_path = OUT / "summary_cruce_habitable_nasa.json"
    sum_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    print(f"elapsed_total_s={time.time()-t_all:.0f}", flush=True)


if __name__ == "__main__":
    main()
