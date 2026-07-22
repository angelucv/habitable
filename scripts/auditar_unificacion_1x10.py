"""Auditoría de unificación 1×10: ¿los multi-reportes son la misma ubicación?"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from secure_io import read_parquet  # noqa: E402

try:
    from rapidfuzz import fuzz
except ImportError:
    from difflib import SequenceMatcher

    class fuzz:  # type: ignore
        @staticmethod
        def token_set_ratio(a, b):
            return 100 * SequenceMatcher(None, a, b).ratio()


R_EARTH = 6_371_000.0
CASA_RE = re.compile(
    r"\b(CASA|CASITA|QUINTA|ANEXO|VIVIENDA UNIFAM)\w*", re.I
)
EDIF_RE = re.compile(
    r"\b(EDIFICIO|RESIDENCIAS?|TORRE|CONJUNTO|URBANIZACI[OÓ]N|BLOQUE|APT[OA]?|APARTAMENTO)\w*",
    re.I,
)


def haversine_m(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = map(np.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlng / 2) ** 2
    return 2 * R_EARTH * np.arcsin(np.sqrt(a))


def norm_dir(s):
    s = str(s or "").upper()
    return re.sub(r"\s+", " ", s).strip()


def diameter_m(lats, lngs):
    n = len(lats)
    if n <= 1:
        return 0.0
    if n <= 45:
        dist = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                d = float(haversine_m(lats[i], lngs[i], lats[j], lngs[j]))
                if d > dist:
                    dist = d
        return dist
    cand = [
        int(lats.argmin()),
        int(lats.argmax()),
        int(lngs.argmin()),
        int(lngs.argmax()),
    ]
    dist = 0.0
    for a in cand:
        for b in cand:
            dist = max(dist, float(haversine_m(lats[a], lngs[a], lats[b], lngs[b])))
    return dist


def main():
    sol = read_parquet(ROOT / "data" / "processed" / "solicitudes.parquet")
    m = sol[sol["mapeable"]].copy()
    print("mapeables", len(m), "grupos", m["dedup_key"].nunique())
    print(
        "multi grupos",
        m.loc[m["n_reportes"] >= 2, "dedup_key"].nunique(),
    )

    rows = []
    for key, g in m[m["n_reportes"] >= 2].groupby("dedup_key", sort=False):
        n = len(g)
        lats = g["lat"].to_numpy(float)
        lngs = g["lng"].to_numpy(float)
        dist = diameter_m(lats, lngs)
        dirs = [norm_dir(x) for x in g["direccion"].tolist()]
        dirs_nz = [d for d in dirs if d]
        scores = []
        for i in range(len(dirs_nz)):
            for j in range(i + 1, min(len(dirs_nz), i + 10)):
                scores.append(fuzz.token_set_ratio(dirs_nz[i], dirs_nz[j]))
        score_min = min(scores) if scores else None
        score_med = float(np.median(scores)) if scores else None
        text_all = " | ".join(dirs_nz[:25])
        casa = bool(CASA_RE.search(text_all))
        edif = bool(EDIF_RE.search(text_all))
        rows.append(
            {
                "dedup_key": key,
                "n": n,
                "diametro_m": round(dist, 1),
                "score_dir_min": score_min,
                "score_dir_med": round(score_med, 1) if score_med is not None else None,
                "dirs_unicas": len(set(dirs_nz)),
                "parece_casa": casa and not edif,
                "parece_edif": edif,
                "mixto_casa_edif": casa and edif,
                "estado": g["estado_n"].mode().iloc[0] if len(g) else "",
                "dir_rep": dirs_nz[0][:140] if dirs_nz else "",
                "codigos": " | ".join(g["codigo_caso"].astype(str).head(10).tolist()),
            }
        )

    aud = pd.DataFrame(rows)
    print("\n=== DIAMETRO (m) entre extremos del grupo ===")
    print(aud["diametro_m"].describe(percentiles=[0.5, 0.75, 0.9, 0.95, 0.99]).to_string())
    print(
        f">20m: {(aud.diametro_m > 20).sum()} ({100 * (aud.diametro_m > 20).mean():.1f}%)"
    )
    print(f">40m: {(aud.diametro_m > 40).sum()}")
    print(f">100m: {(aud.diametro_m > 100).sum()}")

    print("\n=== SIMILITUD DIRECCION (min token_set) ===")
    print(aud["score_dir_min"].describe(percentiles=[0.25, 0.5, 0.75]).to_string())
    print("score_min < 50:", int((aud.score_dir_min.fillna(100) < 50).sum()))
    print("score_min < 70:", int((aud.score_dir_min.fillna(100) < 70).sum()))

    print("\n=== TEXTO CASA / EDIFICIO ===")
    print("parece_casa (sin edif):", int(aud.parece_casa.sum()))
    print("parece_edif:", int(aud.parece_edif.sum()))
    print("mixto:", int(aud.mixto_casa_edif.sum()))

    sus = aud[
        (aud.diametro_m > 40)
        | (aud.score_dir_min.fillna(100) < 55)
        | ((aud.dirs_unicas >= 3) & (aud.score_dir_min.fillna(100) < 70))
    ].sort_values(["diametro_m", "n"], ascending=False)

    print(f"\n=== SOSPECHOSOS: {len(sus)} de {len(aud)} ===")
    print("sospechosos n>=5:", int((sus.n >= 5).sum()))
    print("sospechosos casa:", int(sus.parece_casa.sum()))

    print("\n--- Top 12 por diametro ---")
    print(
        sus.head(12)[
            ["n", "diametro_m", "score_dir_min", "dirs_unicas", "parece_casa", "dir_rep"]
        ].to_string()
    )

    casas = aud[aud.parece_casa]
    casas_bad = casas[
        (casas.diametro_m > 30)
        | (casas.score_dir_min.fillna(100) < 60)
        | (casas.dirs_unicas >= 3)
    ].sort_values(["n", "diametro_m"], ascending=False)
    print(f"\ncasas multi: {len(casas)} | casas dudosas: {len(casas_bad)}")
    print(
        casas_bad.head(15)[
            ["n", "diametro_m", "score_dir_min", "dirs_unicas", "dir_rep", "codigos"]
        ].to_string()
    )

    print("\n=== DETALLE 5 PEOR DIAMETRO ===")
    for key in sus.head(5)["dedup_key"]:
        g = m[m.dedup_key == key][
            ["codigo_caso", "direccion", "lat", "lng", "parroquia_n"]
        ].copy()
        base_lat, base_lng = float(g.iloc[0]["lat"]), float(g.iloc[0]["lng"])
        g["dist_al_1_m"] = [
            round(float(haversine_m(base_lat, base_lng, r.lat, r.lng)), 1)
            for r in g.itertuples()
        ]
        diam = float(aud.loc[aud.dedup_key == key, "diametro_m"].iloc[0])
        print(f"\nKEY {key} n={len(g)} diametro={diam} m")
        print(g.head(15).to_string(index=False))

    # Calidad “buena” vs dudosa
    bueno = aud[
        (aud.diametro_m <= 25) & (aud.score_dir_min.fillna(0) >= 70)
    ]
    print("\n=== CALIDAD RESUMEN ===")
    print(f"grupos multi: {len(aud)}")
    print(
        f"coherentes (diam<=25m y dir_sim>=70): {len(bueno)} "
        f"({100 * len(bueno) / max(len(aud), 1):.1f}%)"
    )
    print(
        f"sospechosos (criterio arriba): {len(sus)} "
        f"({100 * len(sus) / max(len(aud), 1):.1f}%)"
    )

    out_dir = Path("data/processed")
    aud.sort_values(["diametro_m", "n"], ascending=False).to_csv(
        out_dir / "auditoria_unificacion_1x10.csv", index=False, encoding="utf-8-sig"
    )
    sus.to_csv(
        out_dir / "auditoria_unificacion_sospechosos.csv",
        index=False,
        encoding="utf-8-sig",
    )
    casas_bad.to_csv(
        out_dir / "auditoria_unificacion_casas_dudosas.csv",
        index=False,
        encoding="utf-8-sig",
    )
    print("\nCSV guardados en data/processed/")


if __name__ == "__main__":
    main()
