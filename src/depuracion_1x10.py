"""
Depuración del archivo 1×10 — resumen y exportación
===================================================

Documenta las limpiezas aplicadas en el pipeline y arma un Excel
con columnas originales + columnas depuradas adicionales.
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd

CALIDAD_GEO_DESC = {
    "alta": "Coordenadas válidas y coherentes con el estado",
    "sin_coords": "Sin latitud/longitud usable",
    "fuera_ve": "Coordenadas fuera del territorio venezolano",
    "mar_abierto": "Punto cae en mar abierto (GPS dudoso)",
    "fuera_estado": "GPS no coincide con el estado declarado",
    "hotspot": "Coordenada repetida masiva (hotspot)",
    "baja_precision": "Baja precisión geográfica",
}

MATCH_CAT_DESC = {
    "solo_1x10": "Pendiente de atender (sin cruce Habitable útil)",
    "coincide_alta": "Ya atendida — coincidencia alta (geo + nombre)",
    "coincide_media": "Ya atendida — coincidencia media",
    "coincide_geo_solo": "Por revisar — cerca en mapa, nombre dudoso",
    "no_mapeable": "Sin mapear — GPS inválido o incompleto",
}


def resumen_depuracion(sol: pd.DataFrame, summary: dict | None = None) -> dict:
    """Totales de correcciones / calidad para la UI de Análisis 1×10."""
    summary = summary or {}
    n = len(sol)
    mapeable = int(sol["mapeable"].sum()) if "mapeable" in sol.columns else 0
    no_map = n - mapeable
    mapa_ok = int(sol["mapa_ok"].sum()) if "mapa_ok" in sol.columns else 0
    gps_dudoso = 0
    if "mapeable" in sol.columns and "mapa_ok" in sol.columns:
        gps_dudoso = int((sol["mapeable"] & ~sol["mapa_ok"]).sum())

    calidad = {}
    if "calidad_geo" in sol.columns:
        calidad = {
            str(k): int(v) for k, v in sol["calidad_geo"].value_counts().items()
        }

    cats = {}
    if "match_cat" in sol.columns:
        cats = {str(k): int(v) for k, v in sol["match_cat"].value_counts().items()}

    por_revisar_match = int(cats.get("coincide_geo_solo", 0))
    pendientes_atender = int(cats.get("solo_1x10", 0))
    ya_atendidas = int(cats.get("coincide_alta", 0)) + int(
        cats.get("coincide_media", 0)
    )

    return {
        "n_total": n,
        "n_mapeable": mapeable,
        "n_sin_mapear": no_map,
        "n_mapa_ok": mapa_ok,
        "n_gps_dudoso": gps_dudoso,
        "n_por_revisar_match": por_revisar_match,
        "n_pendientes_atender": pendientes_atender,
        "n_ya_atendidas": ya_atendidas,
        "n_pendiente_revision": no_map + gps_dudoso + por_revisar_match,
        "calidad_geo": calidad,
        "match_cat": cats,
        "radius_m": summary.get("radius_m", 50),
        "dedupe_radius_m": summary.get("dedupe_radius_m", 20),
        "ubicaciones_unicas": summary.get("ubicaciones_unicas"),
        "ubicaciones_con_multiples_reportes": summary.get(
            "ubicaciones_con_multiples_reportes"
        ),
    }


def frame_export_depurado(sol: pd.DataFrame) -> pd.DataFrame:
    """
    Universo 1×10 con dato original + columnas depuradas.
    Listo para Excel de trabajo posterior.
    """
    out = sol.copy()
    if "calidad_geo" in out.columns:
        out["calidad_geo_desc"] = (
            out["calidad_geo"].astype(str).map(CALIDAD_GEO_DESC).fillna("")
        )
    if "match_cat" in out.columns:
        out["match_cat_desc"] = (
            out["match_cat"].astype(str).map(MATCH_CAT_DESC).fillna("")
        )
    if "mapeable" in out.columns and "mapa_ok" in out.columns:
        out["requiere_revision_gps"] = (~out["mapeable"]) | (
            out["mapeable"] & ~out["mapa_ok"]
        )
    if "match_cat" in out.columns:
        out["requiere_revision_cruce"] = out["match_cat"].isin(
            ["coincide_geo_solo", "no_mapeable"]
        )

    # Bloque original (tal como llegó / se conservó) + bloque depurado
    originales = [
        c
        for c in [
            "codigo_caso",
            "cedula",
            "denunciante",
            "telefono",
            "estado",
            "municipio",
            "parroquia",
            "direccion",
            "descripcion",
            "lat_raw",
            "lng_raw",
        ]
        if c in out.columns
    ]
    # Si no hay lat_raw, el lat/lng parseado sigue siendo la referencia usable
    depuradas = [
        c
        for c in [
            "estado_n",
            "municipio_n",
            "parroquia_n",
            "lat",
            "lng",
            "mapeable",
            "mapa_ok",
            "calidad_geo",
            "calidad_geo_desc",
            "requiere_revision_gps",
            "match_cat",
            "match_cat_desc",
            "requiere_revision_cruce",
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
        if c in out.columns
    ]
    ordered = originales + [c for c in depuradas if c not in originales]
    # Cualquier otra columna al final
    rest = [c for c in out.columns if c not in ordered]
    return out[ordered + rest]


def excel_bytes_depurado(sol: pd.DataFrame) -> bytes:
    """Genera .xlsx en memoria (openpyxl)."""
    df = frame_export_depurado(sol)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="1x10_depurado", index=False)
        # Hoja resumen corta
        r = resumen_depuracion(sol)
        resumen_rows = [
            ("Total reportes", r["n_total"]),
            ("Mapeables (GPS en VE)", r["n_mapeable"]),
            ("Sin mapear (GPS inválido)", r["n_sin_mapear"]),
            ("GPS dudosos (mar / fuera estado)", r["n_gps_dudoso"]),
            ("Por revisar (cruce dudoso)", r["n_por_revisar_match"]),
            ("Pendientes de atender", r["n_pendientes_atender"]),
            ("Ya atendidas (alta+media)", r["n_ya_atendidas"]),
            (
                "Total pendiente de revisión (GPS + cruce)",
                r["n_pendiente_revision"],
            ),
            ("Radio matching (m)", r["radius_m"]),
            ("Radio unificación (m)", r["dedupe_radius_m"]),
        ]
        pd.DataFrame(resumen_rows, columns=["indicador", "valor"]).to_excel(
            writer, sheet_name="resumen_depuracion", index=False
        )
        if r["calidad_geo"]:
            pd.DataFrame(
                [
                    {
                        "calidad_geo": k,
                        "descripcion": CALIDAD_GEO_DESC.get(k, ""),
                        "n": v,
                    }
                    for k, v in sorted(
                        r["calidad_geo"].items(), key=lambda x: -x[1]
                    )
                ]
            ).to_excel(writer, sheet_name="calidad_geo", index=False)
    return buf.getvalue()
