"""
Reportes operativos para el equipo de inspecciones
=================================================

Agrupa la demanda 1×10 por ubicación (criterio estricto: GPS corto +
dirección similar), de modo que cada fila ≈ un punto a priorizar.

Importante para Habitable: el cúmulo puede incluir vecinos afines; no
garantiza una sola casa/edificio. Revisar siempre los codigos_casos.

Campos clave:
- cantidad_casos / n_reportes
- codigos_casos (todos los código_caso del grupo)
- nota_agrupacion (si está disponible)
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd

from depuracion_1x10 import ESTATUS_CRUCE, MATCH_CAT_DESC

# Causas del cruce bajo (texto para UI / Excel leyenda)
DIAGNOSTICO_CRUCE = [
    {
        "causa": "Sin inspección Habitable cerca (≤50 m)",
        "peso_aprox": "Mayoría de las 1×10 mapeables",
        "lectura": (
            "El vecino Habitable más cercano suele estar a más de 50 m "
            "(mediana nacional del orden de ~100–130 m). En Miranda y el "
            "interior la brecha es de cobertura de campo."
        ),
    },
    {
        "causa": "Hay Habitable cerca pero es otro edificio",
        "peso_aprox": "Bloque importante en DC / La Guaira",
        "lectura": (
            "A ≤50 m el nombre no coincide lo suficiente. En zonas densas "
            "el pin cercano suele ser un vecino distinto. 1×10 usa la "
            "dirección completa; Habitable, el nombre corto del edificio."
        ),
    },
    {
        "causa": "Cruce dudoso (cerca + nombre parcial)",
        "peso_aprox": "Cola de revisión",
        "lectura": "Requiere revisión manual antes de informar al ciudadano.",
    },
    {
        "causa": "Ya cruzado (alta + media confianza)",
        "peso_aprox": "Ver KPI «Cruzados auto» / % ya inspeccionado",
        "lectura": (
            "Hay vínculo usable con una inspección Habitable. El matching "
            "revisa varios vecinos en el radio y similitud parcial de nombre."
        ),
    },
]


def _codigos_completos(series: pd.Series) -> str:
    vals = [str(x).strip() for x in series.tolist() if str(x).strip()]
    # únicos preservando orden
    seen: set[str] = set()
    out: list[str] = []
    for v in vals:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return " | ".join(out)


def frame_ubicaciones_inspeccion(
    sol: pd.DataFrame,
    *,
    solo_pendientes: bool = True,
    solo_mapeables: bool = True,
    solo_mapa_ok: bool = True,
    estados: list[str] | None = None,
    municipios: list[str] | None = None,
    parroquias: list[str] | None = None,
    min_casos: int = 1,
) -> pd.DataFrame:
    """
    Una fila por ubicación (dedup_key): cantidad de casos + todos los códigos.

    Si no hay dedup_key, agrupa por redondeo de coords (aprox. 10 m).
    Por defecto excluye GPS dudosos (mar abierto / fuera de estado).
    """
    if sol is None or sol.empty:
        return pd.DataFrame()

    work = sol.copy()
    if solo_mapeables and "mapeable" in work.columns:
        work = work[work["mapeable"].fillna(False)]
    if solo_mapa_ok and "mapa_ok" in work.columns:
        work = work[work["mapa_ok"].fillna(False)]
    elif solo_mapa_ok and "calidad_geo" in work.columns:
        work = work[
            ~work["calidad_geo"].isin(["mar_abierto", "fuera_ve", "sin_coords"])
        ]
    if estados and "estado_n" in work.columns:
        work = work[work["estado_n"].isin(estados)]
    if municipios and "municipio_n" in work.columns:
        work = work[work["municipio_n"].isin(municipios)]
    if parroquias and "parroquia_n" in work.columns:
        work = work[work["parroquia_n"].isin(parroquias)]
    if solo_pendientes and "match_cat" in work.columns:
        work = work[work["match_cat"].isin(["solo_1x10", "no_mapeable"])]

    if work.empty:
        return pd.DataFrame()

    if "dedup_key" in work.columns and work["dedup_key"].astype(str).str.len().gt(0).any():
        key = "dedup_key"
    else:
        # Fallback: cluster por coords redondeadas
        work = work.copy()
        work["_lat_r"] = work["lat"].round(4) if "lat" in work.columns else 0
        work["_lng_r"] = work["lng"].round(4) if "lng" in work.columns else 0
        work["dedup_key"] = (
            work["_lat_r"].astype(str) + "|" + work["_lng_r"].astype(str)
        )
        key = "dedup_key"

    # Representante: preferir es_representante si existe
    if "es_representante" in work.columns:
        reps = work[work["es_representante"]].copy()
        # por si el filtro dejó grupos sin representante
        missing = set(work[key].unique()) - set(reps[key].unique())
        if missing:
            extra = (
                work[work[key].isin(missing)]
                .sort_values(key)
                .drop_duplicates(subset=[key], keep="first")
            )
            reps = pd.concat([reps, extra], ignore_index=True)
    else:
        reps = work.drop_duplicates(subset=[key], keep="first").copy()

    agg = (
        work.groupby(key, sort=False)
        .agg(
            cantidad_casos=("codigo_caso", "count"),
            codigos_casos=("codigo_caso", _codigos_completos),
        )
        .reset_index()
    )

    cols_rep = [
        c
        for c in [
            key,
            "direccion_display",
            "direccion",
            "tipo_ubicacion",
            "tipo_dir",
            "unidad_dir",
            "estado_n",
            "municipio_n",
            "parroquia_n",
            "lat",
            "lng",
            "match_cat",
            "match_dist_m",
            "match_score",
            "hab_id",
            "hab_nombre",
            "hab_etiqueta",
            "calidad_geo",
            "mapa_ok",
            "nota_agrupacion",
            "dedupe_radius_m",
            "dedupe_addr_min",
        ]
        if c in reps.columns
    ]
    out = reps[cols_rep].merge(agg, on=key, how="left")

    out["cantidad_casos"] = out["cantidad_casos"].fillna(1).astype(int)
    if min_casos > 1:
        out = out[out["cantidad_casos"] >= min_casos]

    if "match_cat" in out.columns:
        out["estatus_cruce"] = out["match_cat"].map(
            lambda c: ESTATUS_CRUCE.get(str(c), str(c))
        )
        out["match_cat_desc"] = out["match_cat"].map(
            lambda c: MATCH_CAT_DESC.get(str(c), str(c))
        )

    out["cumulo_casos"] = out["cantidad_casos"].map(
        lambda n: (
            f"Cúmulo de {int(n)} casos (posible agrupación; revisar en campo)"
            if pd.notna(n) and int(n) > 1
            else "1 caso en el punto"
        )
    )
    if "nota_agrupacion" not in out.columns:
        out["nota_agrupacion"] = out["cantidad_casos"].map(
            lambda n: (
                "Varios reportes agrupados con GPS corto + dirección similar. "
                "Puede haber más de una casa/edificio: usar codigos_casos."
                if pd.notna(n) and int(n) > 1
                else "Caso único en ubicación (criterio estricto)."
            )
        )

    # Orden operativo: más reportes primero (volumen, no prioridad normativa)
    out = out.sort_values(
        ["cantidad_casos", "estado_n", "municipio_n"],
        ascending=[False, True, True],
        kind="mergesort",
    )

    ordered = [
        c
        for c in [
            "cumulo_casos",
            "cantidad_casos",
            "codigos_casos",
            "nota_agrupacion",
            "tipo_ubicacion",
            "direccion_display",
            "direccion",
            "estado_n",
            "municipio_n",
            "parroquia_n",
            "lat",
            "lng",
            "estatus_cruce",
            "match_cat",
            "match_cat_desc",
            "hab_nombre",
            "hab_etiqueta",
            "match_dist_m",
            "match_score",
            "calidad_geo",
            "mapa_ok",
            key,
        ]
        if c in out.columns
    ]
    rest = [c for c in out.columns if c not in ordered]
    return out[ordered + rest].reset_index(drop=True)


def resumen_ubicaciones(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {
            "n_ubicaciones": 0,
            "n_casos": 0,
            "n_multi": 0,
            "max_casos": 0,
        }
    return {
        "n_ubicaciones": int(len(df)),
        "n_casos": int(df["cantidad_casos"].sum()) if "cantidad_casos" in df.columns else 0,
        "n_multi": int((df["cantidad_casos"] >= 2).sum())
        if "cantidad_casos" in df.columns
        else 0,
        "max_casos": int(df["cantidad_casos"].max())
        if "cantidad_casos" in df.columns
        else 0,
    }


def excel_bytes_reportes_inspeccion(
    pendientes: pd.DataFrame,
    todos: pd.DataFrame | None = None,
    *,
    summary: dict | None = None,
) -> bytes:
    """Excel de insumos para cuadrillas de inspección."""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {
                    "hoja": "pendientes_por_ubicacion",
                    "contenido": (
                        "Ubicaciones 1×10 sin cruce útil con Habitable. "
                        "Una fila ≈ punto a priorizar; cantidad_casos y "
                        "codigos_casos agrupan reportes cercanos CON dirección "
                        "y tipología coherentes. direccion_display es la más "
                        "completa del grupo. Puede haber más de una "
                        "casa/edificio: revisar cada codigo_caso en campo."
                    ),
                },
                {
                    "hoja": "todas_ubicaciones",
                    "contenido": (
                        "Todas las ubicaciones del filtro (incluye ya cruzadas). "
                        "Útil para contraste con lo inspeccionado."
                    ),
                },
                {
                    "hoja": "diagnostico_cruce",
                    "contenido": "Por qué el % de cruce automático es bajo.",
                },
            ]
        ).to_excel(writer, sheet_name="leyenda", index=False)

        pendientes.to_excel(
            writer, sheet_name="pendientes_por_ubicacion", index=False
        )
        if todos is not None and not todos.empty:
            todos.to_excel(writer, sheet_name="todas_ubicaciones", index=False)

        pd.DataFrame(DIAGNOSTICO_CRUCE).to_excel(
            writer, sheet_name="diagnostico_cruce", index=False
        )

        if summary:
            rows = [
                ("Inspecciones Habitable", summary.get("n_hab")),
                ("Solicitudes 1×10", summary.get("n_1x10")),
                ("Cruzados auto (alta+media)", summary.get("coincide_auto")),
                ("% ya inspeccionado (mapeables)", summary.get("pct_ya_insp")),
                ("Pendientes solo_1x10", summary.get("solo_1x10")),
                ("Dudosos", summary.get("dudosos")),
                ("Radio matching (m)", summary.get("radius_m")),
                ("Radio unificación ubicaciones (m)", summary.get("dedupe_radius_m")),
                ("Ubicaciones únicas", summary.get("ubicaciones_unicas")),
            ]
            pd.DataFrame(rows, columns=["indicador", "valor"]).to_excel(
                writer, sheet_name="resumen", index=False
            )
    return buf.getvalue()
