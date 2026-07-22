"""Descarga TODA la capa NASA S1 Structures (~2.7M) a GeoJSON local (~1 GB).

- Incluye likely_damaged / not_damaged / not_assessed
- Geometría polígono completa (no solo centroides)
- Escritura en streaming (no carga todo en RAM)
- Reanudable por archivos part_XXXXXX.geojsonl
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "external_nasa" / "nasa_s1_all_full"
PART_DIR = OUT / "parts_geojsonl"
OUT.mkdir(parents=True, exist_ok=True)
PART_DIR.mkdir(parents=True, exist_ok=True)

BASE = (
    "https://services7.arcgis.com/WSiUmUhlFx4CtMBB/arcgis/rest/services/"
    "202610_s1_likelydmgareas/FeatureServer/0"
)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CPEH-BI/1.0)"}
FINAL = OUT / "nasa_s1_all_structures.geojson"
MANIFEST = OUT / "manifest.json"


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> None:
    meta = get_json(BASE + "?f=pjson")
    max_rec = int(meta.get("maxRecordCount") or 2000)
    count = get_json(
        BASE
        + "/query?"
        + urllib.parse.urlencode(
            {"where": "1=1", "returnCountOnly": "true", "f": "pjson"}
        )
    )["count"]
    print(f"TOTAL={count} maxRecordCount={max_rec}", flush=True)
    print(f"Destino final: {FINAL}", flush=True)
    print("Estimado GeoJSON completo: ~0.9–1.2 GB", flush=True)

    done = {int(p.stem.split("_")[-1]) for p in PART_DIR.glob("part_*.geojsonl")}
    print(f"parts ya descargadas: {len(done)}", flush=True)

    offset = 0
    t0 = time.time()
    while offset < count:
        part = PART_DIR / f"part_{offset:07d}.geojsonl"
        if offset in done and part.exists() and part.stat().st_size > 0:
            offset += max_rec
            continue

        params = {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
            "resultOffset": str(offset),
            "resultRecordCount": str(max_rec),
            "orderByFields": "fid",
        }
        url = BASE + "/query?" + urllib.parse.urlencode(params)
        try:
            data = get_json(url)
        except Exception as e:
            print(f"ERROR offset={offset} {type(e).__name__}: {e}", flush=True)
            time.sleep(3)
            continue

        feats = data.get("features") or []
        if not feats:
            print(f"empty offset={offset}, stop", flush=True)
            break

        with part.open("w", encoding="utf-8") as f:
            for feat in feats:
                f.write(json.dumps(feat, ensure_ascii=False, separators=(",", ":")))
                f.write("\n")

        mb = part.stat().st_size / (1024 * 1024)
        elapsed = time.time() - t0
        pct = 100.0 * min(offset + len(feats), count) / count
        print(
            f"offset {offset}/{count} (+{len(feats)}) "
            f"{pct:.1f}% part={mb:.2f}MB elapsed={elapsed:.0f}s",
            flush=True,
        )
        offset += len(feats)
        time.sleep(0.1)

    # Ensamblar FeatureCollection único
    parts = sorted(PART_DIR.glob("part_*.geojsonl"))
    print(f"Ensamblando {len(parts)} parts -> {FINAL.name} ...", flush=True)
    n = 0
    with FINAL.open("w", encoding="utf-8") as out:
        out.write('{"type":"FeatureCollection","features":[\n')
        first = True
        for part in parts:
            with part.open("r", encoding="utf-8") as inp:
                for line in inp:
                    line = line.strip()
                    if not line:
                        continue
                    if not first:
                        out.write(",\n")
                    out.write(line)
                    first = False
                    n += 1
                    if n % 100000 == 0:
                        print(f"  written {n} features...", flush=True)
        out.write("\n]}\n")

    size_mb = FINAL.stat().st_size / (1024 * 1024)
    manifest = {
        "source": BASE,
        "n_features": n,
        "expected_count": count,
        "file": str(FINAL),
        "size_mb": round(size_mb, 2),
        "format": "GeoJSON FeatureCollection (polígonos completos)",
        "labels_note": "likely_damaged + not_damaged + not_assessed",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK n={n} size_mb={size_mb:.1f} -> {FINAL}", flush=True)
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
