"""Auditar cúmulos multi: ¿misma casa/dirección o mezcla?"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from secure_io import read_parquet  # noqa: E402
from tipologia_direccion import (  # noqa: E402
    classify_direccion,
    extract_unidad,
    normalize_dir,
)

df = read_parquet(ROOT / "data" / "processed" / "solicitudes.parquet")
reps = df[df["es_representante"] & (df["n_reportes"] >= 5)].sort_values(
    "n_reportes", ascending=False
)
print(f"Grupos con n>=5: {len(reps)}")
print("Top 12 (cualquier tipología):")
print(
    reps[["n_reportes", "tipo_ubicacion", "unidad_dir", "direccion"]]
    .head(12)
    .to_string(max_colwidth=65)
)

print("\n\n=== AUDIT grupos tipo_ubicacion=casa (top 15 por n) ===\n")
casas = reps[reps["tipo_ubicacion"] == "casa"].head(15)

resumen = []
for _, r in casas.iterrows():
    g = df[df["dedup_key"] == r["dedup_key"]].copy()
    g["_dir_n"] = g["direccion"].map(normalize_dir)
    g["_uni"] = g["direccion"].map(extract_unidad)
    g["_tipo"] = g["direccion"].map(classify_direccion)
    uniq_dirs = int(g["_dir_n"].nunique())
    unis = [u for u in g["_uni"].tolist() if u]
    uniq_uni = len(set(unis))
    # ¿números de casa distintos?
    casa_nums = sorted({u.split(":", 1)[1] for u in unis if u.startswith("casa:")})
    mismo = uniq_uni <= 1 and (len(casa_nums) <= 1)
    resumen.append(
        {
            "n": int(r["n_reportes"]),
            "key": r["dedup_key"],
            "uniq_dirs": uniq_dirs,
            "casa_nums": ",".join(casa_nums) or "(sin nº)",
            "ok_misma_casa": mismo,
            "tipos": dict(g["_tipo"].value_counts()),
        }
    )
    flag = "OK" if mismo else "MEZCLA"
    print(
        f"[{flag}] n={int(r['n_reportes'])} key={r['dedup_key']} "
        f"dirs_distintas={uniq_dirs} casas={casa_nums or ['(sin nº)']}"
    )
    print(f"  display: {str(r['direccion'])[:100]}")
    for _, row in g.iterrows():
        print(
            f"  - {row['codigo_caso']} | {row['_tipo']} | "
            f"{row['_uni'] or '-':12} | {str(row['direccion'])[:95]}"
        )
    print()

res = pd.DataFrame(resumen)
print("=== RESUMEN CASA top15 ===")
print(f"OK misma casa: {(res.ok_misma_casa).sum()} / {len(res)}")
print(f"MEZCLA dudosa: {(~res.ok_misma_casa).sum()} / {len(res)}")

# Ampliar: todos los multi casa con unidad explícita conflictiva
print("\n=== Todos los multi (n>=2) tipo casa con >1 número de casa ===")
multi = df[df["es_representante"] & (df["n_reportes"] >= 2) & (df["tipo_ubicacion"] == "casa")]
bad = 0
samples = []
for _, r in multi.iterrows():
    g = df[df["dedup_key"] == r["dedup_key"]]
    unis = {extract_unidad(d) for d in g["direccion"].tolist()}
    unis.discard("")
    casa_nums = {u for u in unis if u.startswith("casa:")}
    if len(casa_nums) > 1:
        bad += 1
        if len(samples) < 8:
            samples.append((int(r["n_reportes"]), r["dedup_key"], sorted(casa_nums), str(r["direccion"])[:80]))

print(f"Grupos casa multi: {len(multi)}")
print(f"Con 2+ números de casa distintos: {bad}")
for s in samples:
    print(f"  n={s[0]} {s[1]} nums={s[2]} | {s[3]}")

# También: grupos donde display dice casa X pero hay casas Y en miembros
print("\n=== Grupos n>=4 con direcciones muy distintas (token overlap bajo) ===")
from rapidfuzz import fuzz

suspect = []
for _, r in reps.head(40).iterrows():
    g = df[df["dedup_key"] == r["dedup_key"]]
    dirs = [normalize_dir(d) for d in g["direccion"].tolist() if normalize_dir(d)]
    if len(dirs) < 2:
        continue
    scores = []
    for i in range(len(dirs)):
        for j in range(i + 1, len(dirs)):
            scores.append(fuzz.token_set_ratio(dirs[i], dirs[j]))
    if scores and min(scores) < 60:
        suspect.append((int(r["n_reportes"]), r["tipo_ubicacion"], min(scores), str(r["direccion"])[:70]))

print(f"En top40 multi>=5, con algún par <60 similitud: {len(suspect)}")
for s in suspect[:12]:
    print(f"  n={s[0]} tipo={s[1]} min_sim={s[2]:.0f} | {s[3]}")
