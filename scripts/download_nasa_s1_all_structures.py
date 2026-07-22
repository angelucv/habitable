"""Descarga inventario completo NASA S1 Structures (likely_damaged / not_damaged / not_assessed).

Guarda centroides + atributos en parquet particionado por lotes y un consolidado final.
Reanudable: salta offsets ya descargados.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "external_nasa" / "nasa_s1_all_structures"
OUT.mkdir(parents=True, exist_ok=True)
PART_DIR = OUT / "parts"
PART_DIR.mkdir(parents=True, exist_ok=True)

BASE = (
    "https://services7.arcgis.com/WSiUmUhlFx4CtMBB/arcgis/rest/services/"
    "202610_s1_likelydmgareas/FeatureServer/0"
)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CPEH-BI/1.0)"}


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def features_to_rows(feats: list[dict]) -> list[dict]:
    rows = []
    for f in feats:
        a = f.get("attributes") or {}
        g = f.get("geometry") or {}
        # returnCentroid -> geometry often Point; sometimes centroid field
        lat = lng = None
        if "y" in g and "x" in g:
            lat, lng = g.get("y"), g.get("x")
        elif g.get("rings"):
            # fallback: rough ring mean (should not happen with returnCentroid)
            xs, ys = [], []
            for ring in g["rings"]:
                for x, y in ring:
                    xs.append(x)
                    ys.append(y)
            if xs:
                lng, lat = sum(xs) / len(xs), sum(ys) / len(ys)
        row = dict(a)
        row["lng"] = lng
        row["lat"] = lat
        rows.append(row)
    return rows


def main() -> None:
    meta = get_json(BASE + "?f=pjson")
    max_rec = int(meta.get("maxRecordCount") or 2000)
    print("maxRecordCount", max_rec)

    count = get_json(
        BASE
        + "/query?"
        + urllib.parse.urlencode(
            {"where": "1=1", "returnCountOnly": "true", "f": "pjson"}
        )
    )["count"]
    print("TOTAL features", count)

    # resume
    done_offsets = {
        int(p.stem.split("_")[-1])
        for p in PART_DIR.glob("part_*.parquet")
    }
    print("parts already:", len(done_offsets))

    offset = 0
    t0 = time.time()
    while offset < count:
        part_path = PART_DIR / f"part_{offset:07d}.parquet"
        if offset in done_offsets and part_path.exists():
            offset += max_rec
            continue

        params = {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "returnCentroid": "true",
            "outSR": "4326",
            "f": "json",
            "resultOffset": str(offset),
            "resultRecordCount": str(max_rec),
            "orderByFields": "fid",
        }
        url = BASE + "/query?" + urllib.parse.urlencode(params)
        try:
            data = get_json(url)
        except Exception as e:
            print("ERROR offset", offset, type(e).__name__, e)
            time.sleep(2)
            continue

        feats = data.get("features") or []
        if not feats:
            print("empty at offset", offset, "stop")
            break

        rows = features_to_rows(feats)
        # ArcGIS sometimes puts centroid separately
        if rows and rows[0].get("lat") is None:
            # try geometry.centroid in each feature
            for i, f in enumerate(feats):
                c = (f.get("centroid") or {}) if isinstance(f, dict) else {}
                if "y" in c and "x" in c:
                    rows[i]["lat"] = c["y"]
                    rows[i]["lng"] = c["x"]

        df = pd.DataFrame(rows)
        df.to_parquet(part_path, index=False)
        n_ok = int(df["lat"].notna().sum()) if "lat" in df.columns else 0
        print(
            f"offset {offset}/{count} (+{len(df)}) lat_ok={n_ok} "
            f"elapsed={time.time()-t0:.0f}s -> {part_path.name}"
        )
        offset += len(feats)
        time.sleep(0.12)

    # consolidate
    parts = sorted(PART_DIR.glob("part_*.parquet"))
    print("consolidating", len(parts), "parts...")
    dfs = [pd.read_parquet(p) for p in parts]
    all_df = pd.concat(dfs, ignore_index=True)
    out_pq = OUT / "nasa_s1_all_structures_centroids.parquet"
    all_df.to_parquet(out_pq, index=False)
    print("saved", out_pq, "n=", len(all_df), "MB=", round(out_pq.stat().st_size / 1024 / 1024, 1))
    if "label" in all_df.columns:
        print(all_df["label"].value_counts(dropna=False).to_string())
    manifest = {
        "source": BASE,
        "n": int(len(all_df)),
        "fields": list(all_df.columns),
        "labels": all_df["label"].value_counts(dropna=False).to_dict()
        if "label" in all_df.columns
        else {},
        "lat_ok": int(all_df["lat"].notna().sum()) if "lat" in all_df.columns else 0,
        "note": "Centroides + atributos. Polígonos completos no incluidos (muy pesados).",
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("done", manifest)


if __name__ == "__main__":
    main()
