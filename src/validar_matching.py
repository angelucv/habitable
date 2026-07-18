"""Validación de matching 1x10 ↔ Habitable para canvas de revisión."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz import fuzz
from sklearn.neighbors import BallTree

_STOP = {
    "EDIFICIO",
    "EDIF",
    "RESIDENCIAS",
    "RESIDENCIA",
    "TORRE",
    "CONJUNTO",
    "URBANIZACION",
    "URB",
    "CASA",
    "BLOQUE",
    "PH",
    "EL",
    "LA",
    "LOS",
    "LAS",
    "DE",
    "DEL",
    "Y",
}

HOT_LAT, HOT_LNG = 10.488587, -66.976782
RADIUS_M = 40
R_EARTH = 6371000.0

OUT = Path(__file__).resolve().parent.parent / "data" / "processed"


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def normalize_name(value) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    s = strip_accents(str(value)).upper().strip()
    s = re.sub(r"[^A-Z0-9\s]", " ", s)
    tokens = [t for t in s.split() if t and t not in _STOP]
    return " ".join(tokens)


def parse_coord(value, kind: str = "lat") -> float:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        v = float(value)
        if kind == "lat" and abs(v) <= 90:
            return v
        if kind == "lng" and abs(v) <= 180:
            return v
        digits = re.sub(r"\D", "", str(value))
        if len(digits) >= 8:
            sign = -1.0 if str(value).strip().startswith("-") or v < 0 else 1.0
            return sign * float(digits[:2] + "." + digits[2:])
        return np.nan

    t = str(value).strip().replace(",", ".")
    if " " in t:
        parts = t.split()
        if len(parts) == 2 and all(
            p.replace(".", "").replace("-", "").isdigit() for p in parts
        ):
            t = parts[0] + "." + parts[1]
    try:
        v = float(t)
    except ValueError:
        digits = re.sub(r"\D", "", t)
        if len(digits) >= 8:
            sign = -1.0 if "-" in t else 1.0
            return sign * float(digits[:2] + "." + digits[2:])
        return np.nan

    if kind == "lat" and abs(v) > 90:
        digits = re.sub(r"\D", "", t)
        if len(digits) >= 8:
            sign = -1.0 if "-" in t or v < 0 else 1.0
            return sign * float(digits[:2] + "." + digits[2:])
        return np.nan
    if kind == "lng" and abs(v) > 180:
        digits = re.sub(r"\D", "", t)
        if len(digits) >= 8:
            sign = -1.0 if "-" in t or v < 0 else 1.0
            return sign * float(digits[:2] + "." + digits[2:])
        return np.nan
    return v


def sample_rows(df: pd.DataFrame, n: int = 5) -> list[dict]:
    out = []
    for _, r in df.head(n).iterrows():
        out.append(
            {
                "caso": str(r["CODIGO CASO"])[:14],
                "dir": str(r.get("DIRECCION", ""))[:55],
                "hab": str(r.get("hab_nombre", ""))[:40],
                "m": None
                if pd.isna(r["match_dist_m"])
                else round(float(r["match_dist_m"]), 1),
                "s": int(r["match_score"])
                if r["match_score"] == r["match_score"]
                else 0,
                "est": str(r["estado_n"])[:18],
            }
        )
    return out


def main() -> None:
    x1 = pd.read_excel(
        r"C:\Users\Angel\Downloads\Sin título 1x10.xlsx", dtype=str
    )
    x1["lat"] = x1["LATITUD"].map(lambda v: parse_coord(v, "lat"))
    x1["lng"] = x1["LONGITUD"].map(lambda v: parse_coord(v, "lng"))
    x1["nombre_n"] = x1["DIRECCION"].map(normalize_name)
    x1["estado_n"] = x1["ESTADO"].fillna("").str.upper().str.strip()
    x1["mapeable"] = x1["lat"].between(0.5, 12.5) & x1["lng"].between(
        -73.5, -59.5
    )

    hab = pd.read_excel(
        r"C:\Users\Angel\Downloads\habitable_inspecciones_2026-07-16.xlsx",
        sheet_name="Inspecciones",
        dtype=str,
    )
    hab["lat"] = hab["lat"].map(lambda v: parse_coord(v, "lat"))
    hab["lng"] = hab["lng"].map(lambda v: parse_coord(v, "lng"))
    hab["nombre_n"] = hab["nombre_edificacion"].map(normalize_name)
    hab["estado_n"] = hab["estado"].fillna("").str.upper().str.strip()
    hab["mapeable"] = hab["lat"].between(0.5, 12.5) & hab["lng"].between(
        -73.5, -59.5
    )
    hab["hotspot"] = (hab["lat"].round(6) == round(HOT_LAT, 6)) & (
        hab["lng"].round(6) == round(HOT_LNG, 6)
    )
    hab["alta"] = hab["mapeable"] & ~hab["hotspot"]

    print("1x10", len(x1), "mapeable", int(x1["mapeable"].sum()))
    print(
        "hab",
        len(hab),
        "alta",
        int(hab["alta"].sum()),
        "hotspot",
        int(hab["hotspot"].sum()),
    )

    hab_m = hab.loc[hab["alta"]].reset_index(drop=True)
    x1_m = x1.loc[x1["mapeable"]].reset_index(drop=True)

    coords_h = np.radians(hab_m[["lat", "lng"]].to_numpy(dtype=float))
    tree = BallTree(coords_h, metric="haversine")
    coords_x = np.radians(x1_m[["lat", "lng"]].to_numpy(dtype=float))
    dist, idx = tree.query(coords_x, k=1)
    dist_m = dist[:, 0] * R_EARTH
    nearest_i = idx[:, 0]
    within = dist_m <= RADIUS_M

    cats, dists, scores, hids, hnames = [], [], [], [], []
    for i in range(len(x1_m)):
        if not within[i]:
            cats.append("solo_1x10")
            dists.append(np.nan)
            scores.append(0)
            hids.append("")
            hnames.append("")
            continue
        j = int(nearest_i[i])
        n1 = x1_m.at[i, "nombre_n"]
        n2 = hab_m.at[j, "nombre_n"]
        score = fuzz.token_set_ratio(n1, n2) if n1 and n2 else 0
        d = float(dist_m[i])
        if score >= 85:
            cat = "coincide_alta"
        elif score >= 70 or (d <= 20 and score >= 50):
            cat = "coincide_media"
        else:
            cat = "coincide_geo_solo"
        cats.append(cat)
        dists.append(d)
        scores.append(score)
        hids.append(str(hab_m.at[j, "id"]))
        hnames.append(str(hab_m.at[j, "nombre_edificacion"]))

    x1_m = x1_m.copy()
    x1_m["match_cat"] = cats
    x1_m["match_dist_m"] = dists
    x1_m["match_score"] = scores
    x1_m["hab_id"] = hids
    x1_m["hab_nombre"] = hnames
    vc = x1_m["match_cat"].value_counts()
    print(vc.to_string())

    sb_mask = x1_m["PARROQ"].fillna("").str.contains(
        "BERNARDINO", case=False
    ) | x1_m["DIRECCION"].fillna("").str.contains("BERNARDINO", case=False)
    print("SB", int(sb_mask.sum()))
    if sb_mask.any():
        print(x1_m.loc[sb_mask, "match_cat"].value_counts().to_string())

    summary = {
        "n_1x10": int(len(x1)),
        "n_1x10_mapeable": int(x1["mapeable"].sum()),
        "pct_1x10_map": round(100 * float(x1["mapeable"].mean()), 1),
        "n_hab": int(len(hab)),
        "n_hab_alta": int(hab["alta"].sum()),
        "n_hab_hotspot": int(hab["hotspot"].sum()),
        "cats": {str(k): int(v) for k, v in vc.items()},
        "n_mapeable": int(len(x1_m)),
        "pct_solo": round(100 * vc.get("solo_1x10", 0) / len(x1_m), 1),
        "pct_alta": round(100 * vc.get("coincide_alta", 0) / len(x1_m), 1),
        "pct_media": round(100 * vc.get("coincide_media", 0) / len(x1_m), 1),
        "pct_geo": round(100 * vc.get("coincide_geo_solo", 0) / len(x1_m), 1),
        "sb_n": int(sb_mask.sum()),
        "sb_cats": {
            str(k): int(v)
            for k, v in x1_m.loc[sb_mask, "match_cat"].value_counts().items()
        }
        if sb_mask.any()
        else {},
        "estado_solo": {
            str(k): int(v)
            for k, v in x1_m.loc[
                x1_m.match_cat.eq("solo_1x10"), "estado_n"
            ]
            .value_counts()
            .head(6)
            .items()
        },
        "estado_alta": {
            str(k): int(v)
            for k, v in x1_m.loc[
                x1_m.match_cat.eq("coincide_alta"), "estado_n"
            ]
            .value_counts()
            .head(6)
            .items()
        },
        "samp_alta": sample_rows(
            x1_m.loc[x1_m.match_cat.eq("coincide_alta")]
        ),
        "samp_media": sample_rows(
            x1_m.loc[x1_m.match_cat.eq("coincide_media")]
        ),
        "samp_geo": sample_rows(
            x1_m.loc[x1_m.match_cat.eq("coincide_geo_solo")]
        ),
        "samp_solo": sample_rows(
            x1_m.loc[
                x1_m.match_cat.eq("solo_1x10")
                & x1_m.estado_n.isin(
                    ["CARACAS", "DISTRITO CAPITAL", "LA GUAIRA"]
                )
            ]
        ),
        "radius_m": RADIUS_M,
    }

    OUT.mkdir(parents=True, exist_ok=True)
    out_json = OUT / "validacion_matching_summary.json"
    out_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Wrote", out_json)
    print("SUMMARY_JSON")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
