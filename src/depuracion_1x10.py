"""
Depuración del archivo 1×10 — resumen y exportación
===================================================

Documenta las limpiezas aplicadas en el pipeline y arma un Excel
con columnas originales + columnas depuradas adicionales (cruce Habitable
y estatus de inspección), con filtros opcionales para la descarga.
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

# Agrupación legible para filtros y Excel
ESTATUS_CRUCE = {
    "coincide_alta": "Cruzado (alta confianza)",
    "coincide_media": "Cruzado (media confianza)",
    "coincide_geo_solo": "Por revisar (cruce dudoso)",
    "solo_1x10": "No cruzado (pendiente)",
    "no_mapeable": "No cruzado (sin GPS)",
}

CRUZADO_SI = {"coincide_alta", "coincide_media"}
CRUZADO_REVISAR = {"coincide_geo_solo"}

# Estatus operativo para contactar al ciudadano por número de caso
ESTATUS_CONTACTO = {
    "coincide_alta": "Atendido — informar al ciudadano (cruce alto)",
    "coincide_media": "Atendido — informar al ciudadano (cruce medio)",
    "coincide_geo_solo": "Por revisar — no informar aún (cruce dudoso)",
    "solo_1x10": "Pendiente en cola — aún no atendido en Habitable",
    "no_mapeable": "Pendiente GPS — no se pudo ubicar para cruzar",
}

HAB_ETIQUETA_DESC = {
    "VERDE": "Habitable — acceso permitido",
    "AMARILLO": "Habitable — acceso restringido",
    "ROJO": "Habitable — no habitable / alto riesgo",
    "NEGRO": "Habitable — máximo riesgo (etiqueta negra)",
    "": "Sin inspección Habitable vinculada",
}


def enrich_habitable_cruce(df: pd.DataFrame) -> pd.DataFrame:
    """Añade columnas explícitas de cruce Habitable, estatus y cola de contacto."""
    out = df.copy()
    if "match_cat" in out.columns:
        cat = out["match_cat"].astype(str)
        out["cruzado_con_habitable"] = cat.map(
            lambda c: "Sí"
            if c in CRUZADO_SI
            else ("Por revisar" if c in CRUZADO_REVISAR else "No")
        )
        out["estatus_cruce"] = cat.map(lambda c: ESTATUS_CRUCE.get(c, c))
        out["match_cat_desc"] = cat.map(lambda c: MATCH_CAT_DESC.get(c, c))
        out["estatus_para_contacto"] = cat.map(
            lambda c: ESTATUS_CONTACTO.get(c, c)
        )
        out["en_cola_pendiente"] = cat.isin(["solo_1x10", "no_mapeable"])
        out["atendido_segun_cruce"] = cat.isin(CRUZADO_SI)
        out["requiere_revision_antes_de_informar"] = cat.isin(
            CRUZADO_REVISAR | {"no_mapeable"}
        )
    else:
        out["cruzado_con_habitable"] = "No"
        out["estatus_cruce"] = "Sin dato de cruce"
        out["match_cat_desc"] = ""
        out["estatus_para_contacto"] = "Sin dato"
        out["en_cola_pendiente"] = True
        out["atendido_segun_cruce"] = False
        out["requiere_revision_antes_de_informar"] = True

    if "hab_etiqueta" in out.columns:
        eti = (
            out["hab_etiqueta"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
        )
        out["estatus_inspeccion_habitable"] = eti
        out["estatus_inspeccion_habitable_desc"] = eti.map(
            lambda e: HAB_ETIQUETA_DESC.get(
                e, f"Habitable — {e}" if e else HAB_ETIQUETA_DESC[""]
            )
        )
        if "match_cat" in out.columns:
            sin = ~out["match_cat"].isin(CRUZADO_SI | CRUZADO_REVISAR)
            out.loc[sin, "estatus_inspeccion_habitable"] = ""
            out.loc[sin, "estatus_inspeccion_habitable_desc"] = (
                "Sin inspección Habitable vinculada"
            )
    else:
        out["estatus_inspeccion_habitable"] = ""
        out["estatus_inspeccion_habitable_desc"] = "Sin dato Habitable"

    if "hab_nombre" in out.columns:
        out["edificacion_habitable"] = out["hab_nombre"].fillna("").astype(str)

    # Una fila = un código de caso (no se colapsa el edificio)
    if "codigo_caso" in out.columns:
        out["fila_es_caso_individual"] = True
    if "n_reportes" in out.columns:
        out["casos_cerca_misma_ubicacion"] = out["n_reportes"]
        out["nota_ubicacion"] = out["n_reportes"].map(
            lambda n: (
                f"Hay {int(n)} reportes 1×10 cerca (≤20 m); "
                "cada fila sigue siendo un caso distinto a contactar."
                if pd.notna(n) and int(n) > 1
                else "Caso único en su ubicación."
            )
        )
    return out


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
    cruzados = ya_atendidas

    hab_eti = {}
    if "hab_etiqueta" in sol.columns and cruzados:
        mask = sol["match_cat"].isin(CRUZADO_SI) if "match_cat" in sol.columns else True
        sub = sol.loc[mask, "hab_etiqueta"].fillna("").astype(str).str.upper().str.strip()
        hab_eti = {str(k) if k else "(sin etiqueta)": int(v) for k, v in sub.value_counts().items()}

    return {
        "n_total": n,
        "n_mapeable": mapeable,
        "n_sin_mapear": no_map,
        "n_mapa_ok": mapa_ok,
        "n_gps_dudoso": gps_dudoso,
        "n_por_revisar_match": por_revisar_match,
        "n_pendientes_atender": pendientes_atender,
        "n_ya_atendidas": ya_atendidas,
        "n_cruzados_habitable": cruzados,
        "n_pendiente_revision": no_map + gps_dudoso + por_revisar_match,
        "calidad_geo": calidad,
        "match_cat": cats,
        "hab_etiqueta_cruzados": hab_eti,
        "radius_m": summary.get("radius_m", 50),
        "dedupe_radius_m": summary.get("dedupe_radius_m", 20),
        "ubicaciones_unicas": summary.get("ubicaciones_unicas"),
        "ubicaciones_con_multiples_reportes": summary.get(
            "ubicaciones_con_multiples_reportes"
        ),
    }


def apply_export_filters(
    sol: pd.DataFrame,
    *,
    estados: list[str] | None = None,
    municipios: list[str] | None = None,
    parroquias: list[str] | None = None,
    estatus_cruce: list[str] | None = None,
    etiquetas_hab: list[str] | None = None,
    calidad_geo: list[str] | None = None,
    solo_representantes: bool = False,
    solo_requiere_revision: bool = False,
    solo_cola_pendiente: bool = False,
) -> pd.DataFrame:
    """Filtra el universo 1×10 antes de armar el Excel."""
    out = sol
    if estados and "estado_n" in out.columns:
        out = out[out["estado_n"].isin(estados)]
    if municipios and "municipio_n" in out.columns:
        out = out[out["municipio_n"].isin(municipios)]
    if parroquias and "parroquia_n" in out.columns:
        out = out[out["parroquia_n"].isin(parroquias)]
    if estatus_cruce and "match_cat" in out.columns:
        # UI pasa etiquetas legibles o códigos
        inv = {v: k for k, v in ESTATUS_CRUCE.items()}
        codes = []
        for e in estatus_cruce:
            codes.append(inv.get(e, e))
        out = out[out["match_cat"].isin(codes)]
    if etiquetas_hab and "hab_etiqueta" in out.columns:
        eti = out["hab_etiqueta"].fillna("").astype(str).str.upper().str.strip()
        want: set[str] = set()
        for e in etiquetas_hab:
            el = str(e).strip().lower()
            if el in ("(sin etiqueta)", "sin etiqueta", ""):
                want.add("")
            else:
                want.add(str(e).upper().strip())
        out = out[eti.isin(want)]
    if calidad_geo and "calidad_geo" in out.columns:
        out = out[out["calidad_geo"].isin(calidad_geo)]
    if solo_representantes and "es_representante" in out.columns:
        out = out[out["es_representante"]]
    if solo_cola_pendiente and "match_cat" in out.columns:
        out = out[out["match_cat"].isin(["solo_1x10", "no_mapeable"])]
    if solo_requiere_revision:
        if "mapeable" in out.columns and "mapa_ok" in out.columns:
            gps = (~out["mapeable"]) | (out["mapeable"] & ~out["mapa_ok"])
        else:
            gps = pd.Series(False, index=out.index)
        cruce = (
            out["match_cat"].isin(["coincide_geo_solo", "no_mapeable"])
            if "match_cat" in out.columns
            else pd.Series(False, index=out.index)
        )
        out = out[gps | cruce]
    return out


def frame_export_depurado(sol: pd.DataFrame) -> pd.DataFrame:
    """
    Universo 1×10 con dato original + columnas depuradas + cruce Habitable.
    """
    out = enrich_habitable_cruce(sol)
    if "calidad_geo" in out.columns:
        out["calidad_geo_desc"] = (
            out["calidad_geo"].astype(str).map(CALIDAD_GEO_DESC).fillna("")
        )
    if "mapeable" in out.columns and "mapa_ok" in out.columns:
        out["requiere_revision_gps"] = (~out["mapeable"]) | (
            out["mapeable"] & ~out["mapa_ok"]
        )
    if "match_cat" in out.columns:
        out["requiere_revision_cruce"] = out["match_cat"].isin(
            ["coincide_geo_solo", "no_mapeable"]
        )

    originales = [
        c
        for c in [
            "codigo_caso",
            "cedula",
            "denunciante",
            "telefono",
            "telefono_alt",
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
            "fila_es_caso_individual",
            "estatus_para_contacto",
            "en_cola_pendiente",
            "atendido_segun_cruce",
            "requiere_revision_antes_de_informar",
            "cruzado_con_habitable",
            "estatus_cruce",
            "match_cat",
            "match_cat_desc",
            "requiere_revision_cruce",
            "match_dist_m",
            "match_score",
            "hab_id",
            "edificacion_habitable",
            "hab_nombre",
            "estatus_inspeccion_habitable",
            "estatus_inspeccion_habitable_desc",
            "hab_etiqueta",
            "casos_cerca_misma_ubicacion",
            "nota_ubicacion",
            "dedup_key",
            "n_reportes",
            "codigos_grupo",
            "es_representante",
        ]
        if c in out.columns
    ]
    ordered = originales + [c for c in depuradas if c not in originales]
    rest = [c for c in out.columns if c not in ordered]
    return out[ordered + rest]


def excel_bytes_depurado(sol: pd.DataFrame) -> bytes:
    """Genera .xlsx en memoria (openpyxl) para el subconjunto recibido."""
    df = frame_export_depurado(sol)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="1x10_depurado", index=False)
        r = resumen_depuracion(sol)
        resumen_rows = [
            ("Filas en este archivo", r["n_total"]),
            ("Mapeables (GPS en VE)", r["n_mapeable"]),
            ("Sin mapear (GPS inválido)", r["n_sin_mapear"]),
            ("GPS dudosos (mar / fuera estado)", r["n_gps_dudoso"]),
            ("Cruzados con Habitable (alta+media)", r["n_cruzados_habitable"]),
            ("Por revisar (cruce dudoso)", r["n_por_revisar_match"]),
            ("No cruzados — pendientes de atender", r["n_pendientes_atender"]),
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
        # Desglose cruce + semáforo Habitable en cruzados
        if "match_cat" in sol.columns:
            cruce_rows = []
            for code, label in ESTATUS_CRUCE.items():
                cruce_rows.append(
                    {
                        "estatus_cruce": label,
                        "match_cat": code,
                        "n": int((sol["match_cat"] == code).sum()),
                    }
                )
            pd.DataFrame(cruce_rows).to_excel(
                writer, sheet_name="cruce_habitable", index=False
            )
        # Cola operativa: una fila por caso pendiente de contactar / informar
        enriched = frame_export_depurado(sol)
        if "en_cola_pendiente" in enriched.columns:
            cola = enriched[enriched["en_cola_pendiente"]]
            cols_cola = [
                c
                for c in [
                    "codigo_caso",
                    "cedula",
                    "denunciante",
                    "telefono",
                    "telefono_alt",
                    "direccion",
                    "estado_n",
                    "municipio_n",
                    "parroquia_n",
                    "estatus_para_contacto",
                    "en_cola_pendiente",
                    "cruzado_con_habitable",
                    "estatus_cruce",
                    "estatus_inspeccion_habitable",
                    "edificacion_habitable",
                    "nota_ubicacion",
                ]
                if c in cola.columns
            ]
            cola[cols_cola].to_excel(
                writer, sheet_name="cola_pendiente_casos", index=False
            )
        if "atendido_segun_cruce" in enriched.columns:
            aten = enriched[enriched["atendido_segun_cruce"]]
            cols_a = [
                c
                for c in [
                    "codigo_caso",
                    "cedula",
                    "denunciante",
                    "telefono",
                    "telefono_alt",
                    "direccion",
                    "estatus_para_contacto",
                    "estatus_inspeccion_habitable",
                    "estatus_inspeccion_habitable_desc",
                    "edificacion_habitable",
                    "match_dist_m",
                    "nota_ubicacion",
                ]
                if c in aten.columns
            ]
            aten[cols_a].to_excel(
                writer, sheet_name="casos_atendidos_informar", index=False
            )
        if r.get("hab_etiqueta_cruzados"):
            pd.DataFrame(
                [
                    {
                        "estatus_inspeccion_habitable": k,
                        "descripcion": HAB_ETIQUETA_DESC.get(
                            k if k != "(sin etiqueta)" else "", k
                        ),
                        "n": v,
                    }
                    for k, v in sorted(
                        r["hab_etiqueta_cruzados"].items(), key=lambda x: -x[1]
                    )
                ]
            ).to_excel(writer, sheet_name="estatus_habitable", index=False)
    return buf.getvalue()
