"""Prepara parquet de 1×10 y Habitable con matching a radio configurable."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import tomllib
from rapidfuzz import fuzz
from sklearn.neighbors import BallTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geo_utils import (  # noqa: E402
    in_venezuela,
    is_hotspot,
    mapa_ok_flag,
    normalize_estado,
    normalize_name,
    parse_coord,
    quality_flag,
)
from dedupe_1x10 import dedupe_solicitudes, resumen_dedupe  # noqa: E402

R_EARTH = 6_371_000.0
OUT = ROOT / "data" / "processed"


def load_config() -> dict:
    with open(ROOT / "config.toml", "rb") as f:
        return tomllib.load(f)


def prepare_solicitudes(path: str, geo_cfg: dict) -> pd.DataFrame:
    df = pd.read_excel(path, dtype=str)
    # Normaliza encabezados (espacios / puntos) antes del rename
    df.columns = (
        pd.Index(df.columns)
        .map(lambda c: str(c).strip().upper().replace("  ", " "))
    )
    rename_map = {
        "CODIGO CASO": "codigo_caso",
        "CÓDIGO CASO": "codigo_caso",
        "CEDULA": "cedula",
        "CÉDULA": "cedula",
        "DENUNCIANTE": "denunciante",
        "TELEFONO": "telefono",
        "TELÉFONO": "telefono",
        "TELEFONO ALT.": "telefono_alt",
        "TELEFONO ALT": "telefono_alt",
        "TELÉFONO ALT.": "telefono_alt",
        "TELÉFONO ALT": "telefono_alt",
        "ESTADO": "estado",
        "MUNICIPIO": "municipio",
        "PARROQ": "parroquia",
        "PARROQUIA": "parroquia",
        "LATITUD": "lat_raw",
        "LONGITUD": "lng_raw",
        "DIRECCION": "direccion",
        "DIRECCIÓN": "direccion",
        "DESCRIP": "descripcion",
        "DESCRIPCION": "descripcion",
        "DESCRIPCIÓN": "descripcion",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    # Contacto: no perder identidad del caso ni del denunciante
    for col in ("codigo_caso", "cedula", "denunciante", "telefono", "telefono_alt"):
        if col not in df.columns:
            df[col] = ""
        else:
            df[col] = df[col].fillna("").astype(str).str.strip()
    df["lat"] = df["lat_raw"].map(lambda v: parse_coord(v, "lat"))
    df["lng"] = df["lng_raw"].map(lambda v: parse_coord(v, "lng"))
    df["nombre_n"] = df["direccion"].map(normalize_name)
    df["estado_n"] = df["estado"].map(normalize_estado)
    df["municipio_n"] = df["municipio"].fillna("").str.upper().str.strip()
    df["parroquia_n"] = df["parroquia"].fillna("").str.upper().str.strip()
    df["mapeable"] = df.apply(
        lambda r: in_venezuela(r["lat"], r["lng"], geo_cfg), axis=1
    )
    df["mapa_ok"] = [
        mapa_ok_flag(lat, lng, est, geo_cfg)
        for lat, lng, est in zip(df["lat"], df["lng"], df["estado_n"])
    ]
    df["calidad_geo"] = [
        quality_flag(lat, lng, geo_cfg, est)
        for lat, lng, est in zip(df["lat"], df["lng"], df["estado_n"])
    ]
    return df


def prepare_habitable(path: str, sheet: str, geo_cfg: dict) -> pd.DataFrame:
    src = Path(path)
    if src.suffix.lower() == ".csv":
        df = pd.read_csv(src, dtype=str, encoding="utf-8")
    else:
        df = pd.read_excel(src, sheet_name=sheet, dtype=str)
    df["lat"] = df["lat"].map(lambda v: parse_coord(v, "lat"))
    df["lng"] = df["lng"].map(lambda v: parse_coord(v, "lng"))
    df["nombre_n"] = df["nombre_edificacion"].map(normalize_name)
    df["estado_n"] = df["estado"].map(normalize_estado)
    df["municipio_n"] = df["municipio"].fillna("").str.upper().str.strip()
    df["etiqueta_n"] = df["etiqueta"].fillna("SIN").str.upper().str.strip()
    df["uso_n"] = df["uso"].fillna("Sin dato").str.strip()
    df["material_n"] = df["material"].fillna("Sin dato").str.strip()
    df["num_pisos_n"] = pd.to_numeric(df["num_pisos"], errors="coerce")
    df["mapeable"] = df.apply(
        lambda r: in_venezuela(r["lat"], r["lng"], geo_cfg), axis=1
    )
    df["hotspot"] = [
        is_hotspot(lat, lng, geo_cfg) for lat, lng in zip(df["lat"], df["lng"])
    ]
    df["alta_confianza"] = df["mapeable"] & ~df["hotspot"]
    df["mapa_ok"] = [
        mapa_ok_flag(lat, lng, est, geo_cfg) and (not hot)
        for lat, lng, est, hot in zip(
            df["lat"], df["lng"], df["estado_n"], df["hotspot"]
        )
    ]
    df["calidad_geo"] = [
        quality_flag(lat, lng, geo_cfg, est)
        for lat, lng, est in zip(df["lat"], df["lng"], df["estado_n"])
    ]
    return df


def _best_name_score(n1: str, n2: str) -> float:
    """Compara dirección 1×10 vs nombre Habitable (token_set + partial)."""
    if not n1 or not n2:
        return 0.0
    a = float(fuzz.token_set_ratio(n1, n2))
    b = float(fuzz.partial_ratio(n1, n2))
    return max(a, b)


def match_solicitudes(
    sol: pd.DataFrame,
    hab: pd.DataFrame,
    radius_m: float,
    score_high: int,
    score_medium: int,
    score_geo_min: int = 40,
    k_neighbors: int = 5,
) -> pd.DataFrame:
    """
    Matching geo + nombre.

    Usa hasta `k_neighbors` candidatos Habitable dentro del radio y elige
    el de mejor score de nombre (evita quedarse con un vecino distinto).
    """
    out = sol.copy()
    out["match_cat"] = "no_mapeable"
    out["match_dist_m"] = np.nan
    out["match_score"] = np.nan
    out["hab_id"] = ""
    out["hab_nombre"] = ""
    out["hab_etiqueta"] = ""

    hab_m = hab.loc[hab["alta_confianza"]].reset_index(drop=True)
    mask = out["mapeable"].to_numpy()
    if not mask.any() or hab_m.empty:
        out.loc[mask, "match_cat"] = "solo_1x10"
        return out

    idx_sol = np.flatnonzero(mask)
    coords_h = np.radians(hab_m[["lat", "lng"]].to_numpy(dtype=float))
    tree = BallTree(coords_h, metric="haversine")
    coords_s = np.radians(out.loc[mask, ["lat", "lng"]].to_numpy(dtype=float))
    k = int(min(max(k_neighbors, 1), len(hab_m)))
    dist, nn = tree.query(coords_s, k=k)
    if k == 1:
        dist = dist.reshape(-1, 1)
        nn = nn.reshape(-1, 1)
    dist_m = dist * R_EARTH

    cats, dists, scores, hids, hnames, hetiquetas = [], [], [], [], [], []
    for i, row_i in enumerate(idx_sol):
        n1 = out.at[row_i, "nombre_n"]
        best = None  # (score, dist, j)
        for t in range(k):
            d = float(dist_m[i, t])
            if d > radius_m:
                continue
            j = int(nn[i, t])
            n2 = hab_m.at[j, "nombre_n"]
            score = _best_name_score(n1, n2)
            if best is None or score > best[0] or (
                score == best[0] and d < best[1]
            ):
                best = (score, d, j)

        if best is None:
            cats.append("solo_1x10")
            dists.append(np.nan)
            scores.append(np.nan)
            hids.append("")
            hnames.append("")
            hetiquetas.append("")
            continue

        score, d, j = best
        if score >= score_high:
            cat = "coincide_alta"
        elif score >= score_medium or (d <= 20 and score >= 50):
            cat = "coincide_media"
        elif score >= score_geo_min:
            cat = "coincide_geo_solo"
        else:
            cat = "solo_1x10"
        cats.append(cat)
        if cat == "solo_1x10" and score < score_geo_min:
            dists.append(np.nan)
            scores.append(np.nan)
            hids.append("")
            hnames.append("")
            hetiquetas.append("")
        else:
            dists.append(d)
            scores.append(score)
            hids.append(str(hab_m.at[j, "id"]))
            hnames.append(str(hab_m.at[j, "nombre_edificacion"]))
            hetiquetas.append(str(hab_m.at[j, "etiqueta_n"]))

    out.loc[mask, "match_cat"] = cats
    out.loc[mask, "match_dist_m"] = dists
    out.loc[mask, "match_score"] = scores
    out.loc[mask, "hab_id"] = hids
    out.loc[mask, "hab_nombre"] = hnames
    out.loc[mask, "hab_etiqueta"] = hetiquetas
    return out


def build_summary(sol: pd.DataFrame, hab: pd.DataFrame, radius_m: float) -> dict:
    mapeable = sol.loc[sol["mapeable"]]
    vc = mapeable["match_cat"].value_counts()
    alta = int(vc.get("coincide_alta", 0))
    media = int(vc.get("coincide_media", 0))
    geo = int(vc.get("coincide_geo_solo", 0))
    solo = int(vc.get("solo_1x10", 0))

    # Métricas sobre ubicaciones unificadas (representantes)
    if "es_representante" in sol.columns:
        uniq = mapeable.loc[mapeable["es_representante"]]
        vu = uniq["match_cat"].value_counts()
        u_alta = int(vu.get("coincide_alta", 0))
        u_media = int(vu.get("coincide_media", 0))
        u_solo = int(vu.get("solo_1x10", 0))
        u_geo = int(vu.get("coincide_geo_solo", 0))
    else:
        u_alta = u_media = u_solo = u_geo = None

    return {
        "radius_m": radius_m,
        "n_1x10": int(len(sol)),
        "n_1x10_mapeable": int(sol["mapeable"].sum()),
        "n_hab": int(len(hab)),
        "n_hab_alta": int(hab["alta_confianza"].sum()),
        "n_hab_hotspot": int(hab["hotspot"].sum()),
        "cats": {str(k): int(v) for k, v in vc.items()},
        "coincide_auto": alta + media,
        "solo_1x10": solo,
        "dudosos": geo,
        "pct_ya_insp": round(100 * (alta + media) / max(len(mapeable), 1), 1),
        "pct_pendiente": round(100 * solo / max(len(mapeable), 1), 1),
        "n_1x10_mapa_ok": int(sol["mapa_ok"].sum())
        if "mapa_ok" in sol.columns
        else None,
        "n_1x10_mapa_malo": int((sol["mapeable"] & ~sol["mapa_ok"]).sum())
        if "mapa_ok" in sol.columns
        else None,
        "n_hab_mapa_ok": int(hab["mapa_ok"].sum())
        if "mapa_ok" in hab.columns
        else None,
        "uniq_ya_atendidas": (u_alta + u_media) if u_alta is not None else None,
        "uniq_pendientes": u_solo,
        "uniq_dudosos": u_geo,
    }


def run_pipeline(
    *,
    solicitudes_path: str | Path | None = None,
    habitable_path: str | Path | None = None,
    habitable_sheet: str | None = None,
    quiet: bool = False,
) -> dict:
    """Ejecuta limpieza + matching + parquet. Retorna summary."""
    cfg = load_config()
    geo = cfg["geo"]
    match_cfg = cfg["matching"]
    sources = cfg["sources"]

    sol_src = str(solicitudes_path or sources["solicitudes_1x10"])
    hab_src = str(habitable_path or sources["inspecciones_habitable"])
    sheet = habitable_sheet or sources.get("habitable_sheet", "Inspecciones")

    def _log(msg: str) -> None:
        if not quiet:
            print(msg)

    _log("Cargando 1×10…")
    sol = prepare_solicitudes(sol_src, geo)
    _log("Cargando Habitable…")
    hab_src_path = Path(hab_src)
    try:
        if hab_src_path.suffix.lower() == ".csv":
            hab = prepare_habitable(hab_src, sheet, geo)
            sheet = "(csv)"
        else:
            hab = prepare_habitable(hab_src, sheet, geo)
    except ValueError:
        # Si el nombre de hoja no existe, usar la primera
        xl = pd.ExcelFile(hab_src)
        hab = prepare_habitable(hab_src, xl.sheet_names[0], geo)
        sheet = xl.sheet_names[0]
        _log(f"Hoja Habitable: {sheet}")
    _log(f"Habitable filas: {len(hab)}")

    _log(f"Matching radio {match_cfg['radius_m']} m…")
    sol = match_solicitudes(
        sol,
        hab,
        radius_m=float(match_cfg["radius_m"]),
        score_high=int(match_cfg["name_score_high"]),
        score_medium=int(match_cfg["name_score_medium"]),
        score_geo_min=int(match_cfg.get("name_score_geo_min", 40)),
    )
    _log("Deduplicando ubicaciones 1×10…")
    sol = dedupe_solicitudes(
        sol, radius_m=float(match_cfg.get("dedupe_radius_m", 20))
    )
    summary = build_summary(sol, hab, float(match_cfg["radius_m"]))
    summary.update(resumen_dedupe(sol))
    summary["source_1x10"] = sol_src
    summary["source_habitable"] = hab_src
    summary["habitable_sheet"] = sheet

    OUT.mkdir(parents=True, exist_ok=True)
    sol_path = OUT / "solicitudes.parquet"
    hab_path = OUT / "inspecciones.parquet"
    sum_path = OUT / "summary.json"

    # Contacto primero: número de caso + denunciante (operación 1×10)
    for col in ("codigo_caso", "cedula", "denunciante", "telefono", "telefono_alt"):
        if col not in sol.columns:
            sol[col] = ""
    sol_cols = [
        c
        for c in [
            "codigo_caso",
            "cedula",
            "denunciante",
            "telefono",
            "telefono_alt",
            "estado",
            "estado_n",
            "municipio",
            "municipio_n",
            "parroquia",
            "parroquia_n",
            "direccion",
            "descripcion",
            "lat_raw",
            "lng_raw",
            "lat",
            "lng",
            "mapeable",
            "mapa_ok",
            "calidad_geo",
            "match_cat",
            "match_dist_m",
            "match_score",
            "hab_id",
            "hab_nombre",
            "hab_etiqueta",
            "dedup_key",
            "n_reportes",
            "codigos_grupo",
            "es_representante",
        ]
        if c in sol.columns
    ]
    hab_cols = [
        c
        for c in [
            "id",
            "etiqueta",
            "etiqueta_n",
            "nombre_edificacion",
            "direccion",
            "estado",
            "estado_n",
            "municipio",
            "municipio_n",
            "uso",
            "uso_n",
            "material",
            "material_n",
            "num_pisos",
            "num_pisos_n",
            "ente",
            "lat",
            "lng",
            "mapeable",
            "hotspot",
            "alta_confianza",
            "mapa_ok",
            "calidad_geo",
            "created_at",
            "observaciones",
            "inspector_nombre",
            "validated",
            "evento",
            "fecha_evento",
            "riesgo_externo",
            "riesgo_severo",
            "riesgo_moderado",
            "riesgo_componentes",
            "comp_losa",
            "comp_paredes",
            "comp_tanques",
            "comp_gas_agua_electricidad",
            "comp_ascensores",
            "acc_medidas",
            "acc_inspecciones",
            "serv_electricidad",
            "serv_gas",
            "serv_agua",
            "serv_cantv",
            "mod_columna_exam",
            "mod_columna_mod",
            "mod_muro_concreto_exam",
            "mod_muro_concreto_mod",
            "mod_muro_mamposteria_exam",
            "mod_muro_mamposteria_mod",
            "mod_viga_exam",
            "mod_viga_mod",
            "sev_columna",
            "sev_muro_concreto",
            "sev_muro_mamposteria",
            "sev_viga",
            "ext_colapso_estructura",
            "ext_peligro_aledanos",
            "ext_peligro_geologico",
            "ext_asentamiento",
            "ext_inclinacion",
        ]
        if c in hab.columns
    ]

    sol[sol_cols].to_parquet(sol_path, index=False)
    hab[hab_cols].to_parquet(hab_path, index=False)
    sum_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _log(f"OK {sol_path}")
    _log(f"OK {hab_path}")
    _log(f"OK {sum_path}")
    return summary


def main() -> None:
    summary = run_pipeline(quiet=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
