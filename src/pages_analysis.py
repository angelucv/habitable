"""Páginas de análisis 1×10 y Habitable (reportes de daños)."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts

from charts_echarts import (
    ETIQUETA_COLORS,
    MATCH_COLORS,
    bar_horizontal,
    bar_stacked_pct,
    bar_vertical,
    donut,
)
from habitable_reports import (
    PISO_BANDS,
    RIESGO_LEVELS,
    RISK_DIMS,
    component_presence_counts,
    count_cuadrillas,
    crosstab_etiqueta,
    etiqueta_counts,
    externo_breakdown,
    filter_territorio,
    habitable_explore_frame,
    list_view,
    mask_externo_alto,
    mask_externo_moderado,
    mask_moderado,
    mask_no_estructural,
    mask_severo,
    moderado_band_summary,
    prepare_matriz_frame,
    risk_profile_top,
    semaforo_mix_by,
    severo_mechanism_summary,
)


from depuracion_1x10 import (
    ESTATUS_CRUCE,
    apply_export_filters,
    excel_bytes_depurado,
    resumen_depuracion,
    texto_leyenda_hojas_excel,
)


def fmt_num(n: float | int) -> str:
    return f"{int(n):,}".replace(",", ".")


def _seccion_depuracion_1x10(sol: pd.DataFrame, summary: dict) -> None:
    """Cómo se depuró el 1×10, resumen de correcciones y descarga Excel."""
    from ui_theme import render_kpi_strip, render_section

    r = resumen_depuracion(sol, summary)
    render_section(
        "Depuración del archivo 1×10",
        "El Excel ciudadano se limpia antes del cruce con Habitable. "
        "Aquí se resume qué se corrigió y qué queda pendiente de revisión.",
    )

    with st.expander("Cómo se depuró la información", expanded=False):
        st.markdown(
            f"""
1. **Encoding** — se corrige mojibake en textos crudos (p. ej. «nÃºmero» →
   «número») antes del resto del análisis; `direccion` queda depurada
   (`direccion_raw` conserva el original).
2. **Coordenadas** — se interpretan latitud/longitud (separadores, signos) y se
   valida que caigan en Venezuela.
3. **Calidad GPS** — se marcan puntos en mar abierto, fuera del estado declarado
   o sin coordenadas (`calidad_geo`).
4. **Territorio** — estado / municipio / parroquia se normalizan (mayúsculas,
   espacios) para filtros y mapas.
5. **Cruce Habitable** — vecinos a ≤ {r['radius_m']:.0f} m + similitud de
   dirección/nombre; se clasifica atendida, pendiente o por revisar.
6. **Unificación (estricto)** — reportes a ≤ {r['dedupe_radius_m']:.0f} m **y**
   dirección similar se agrupan si la tipología léxica es coherente
   (no mezcla casa↔edificio; no une apto/casa con número distinto).
   El **representante** muestra la dirección más completa del grupo
   (`direccion_display`). Sirve para mapa/cúmulo; **no** sustituye la visita
   caso a caso.

El archivo descargable conserva el **dato original** (cuando está disponible) y
añade columnas depuradas, **si cruzó con Habitable**, el **estatus de la
inspección** (verde/amarillo/rojo/negro) y flags de revisión.
            """.strip()
        )

    render_kpi_strip(
        [
            {
                "label": "Total reportes",
                "value": fmt_num(r["n_total"]),
                "tone": "info",
            },
            {
                "label": "Cruzados Habitable",
                "value": fmt_num(r["n_cruzados_habitable"]),
                "tone": "success",
                "hint": "Alta + media",
            },
            {
                "label": "Sin mapear",
                "value": fmt_num(r["n_sin_mapear"]),
                "tone": "warning",
                "hint": "GPS inválido / incompleto",
            },
            {
                "label": "GPS dudosos",
                "value": fmt_num(r["n_gps_dudoso"]),
                "tone": "flag",
                "hint": "Mar o fuera del estado",
            },
            {
                "label": "Por revisar (cruce)",
                "value": fmt_num(r["n_por_revisar_match"]),
                "tone": "muted",
                "hint": "Cerca en mapa, nombre dudoso",
            },
        ]
    )

    st.markdown("#### Resumen de correcciones y pendientes")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f"""
- **Cruzadas con Habitable (alta+media):** {fmt_num(r['n_ya_atendidas'])}
- **No cruzadas — pendientes de atender:** {fmt_num(r['n_pendientes_atender'])}
- **Ubicaciones unificadas:** {fmt_num(r.get('ubicaciones_unicas') or 0)}
- **Sitios con varios reportes:** {fmt_num(r.get('ubicaciones_con_multiples_reportes') or 0)}
            """.strip()
        )
    with c2:
        st.markdown(
            f"""
- **Sin poderse mapear (revisar GPS):** {fmt_num(r['n_sin_mapear'])}
- **Mapeables con GPS dudoso:** {fmt_num(r['n_gps_dudoso'])}
- **Cruce dudoso (revisar nombre):** {fmt_num(r['n_por_revisar_match'])}
- **Total pendiente de revisión:** {fmt_num(r['n_pendiente_revision'])}
            """.strip()
        )

    if r.get("hab_etiqueta_cruzados"):
        with st.expander("Estatus Habitable en casos cruzados", expanded=False):
            rows = [
                {"estatus": k, "n": v}
                for k, v in sorted(
                    r["hab_etiqueta_cruzados"].items(), key=lambda x: -x[1]
                )
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if r["calidad_geo"]:
        with st.expander("Detalle por calidad geográfica", expanded=False):
            rows = []
            from depuracion_1x10 import CALIDAD_GEO_DESC

            for k, v in sorted(r["calidad_geo"].items(), key=lambda x: -x[1]):
                rows.append(
                    {
                        "calidad_geo": k,
                        "descripción": CALIDAD_GEO_DESC.get(k, ""),
                        "n": v,
                    }
                )
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("#### Descargar Excel depurado (caso a caso)")
    st.caption(
        "Una fila = un **código de caso** (vecino a contactar), con "
        "`codigo_caso`, `denunciante`, `telefono` y cédula. "
        "No se agrupa por edificio: si varios reportes caen en la misma "
        "ubicación, cada caso sigue saliendo aparte. "
        "También: `estatus_para_contacto`, `en_cola_pendiente`, "
        "`cruzado_con_habitable`, `estatus_inspeccion_habitable`. "
        "La columna `direccion` ya viene con encoding corregido "
        "(`direccion_raw` = original)."
    )
    _contact_cols = [
        c for c in ("codigo_caso", "denunciante", "telefono") if c in sol.columns
    ]
    if len(_contact_cols) < 3:
        st.warning(
            "Faltan columnas de contacto en los datos cargados "
            "(denunciante / teléfono). Regenera el parquet desde el Excel 1×10 "
            "completo para no perder identidad del caso."
        )
    st.info(
        "La unificación (GPS corto + dirección similar) solo sirve para "
        "mapa/estadísticas. Para Habitable e informar atendido/pendiente usa "
        "siempre la descarga **caso a caso**: el cúmulo puede agrupar vecinos "
        "afines y no garantiza una sola casa/edificio."
    )

    estados_all = sorted(sol["estado_n"].dropna().unique().tolist()) if "estado_n" in sol.columns else []
    f1, f2, f3 = st.columns(3)
    with f1:
        filt_est = st.multiselect(
            "Estado",
            options=estados_all,
            default=[],
            key="dep_est",
            help="Vacío = todos los estados.",
        )
    sol_mun = sol
    if filt_est and "estado_n" in sol.columns:
        sol_mun = sol[sol["estado_n"].isin(filt_est)]
    munis_all = (
        sorted(sol_mun["municipio_n"].dropna().unique().tolist())
        if "municipio_n" in sol_mun.columns
        else []
    )
    with f2:
        filt_mun = st.multiselect(
            "Municipio",
            options=munis_all,
            default=[],
            key="dep_mun",
        )
    sol_par = sol_mun
    if filt_mun and "municipio_n" in sol_par.columns:
        sol_par = sol_par[sol_par["municipio_n"].isin(filt_mun)]
    parrs_all = (
        sorted(sol_par["parroquia_n"].replace("", pd.NA).dropna().unique().tolist())
        if "parroquia_n" in sol_par.columns
        else []
    )
    with f3:
        filt_parr = st.multiselect(
            "Parroquia",
            options=parrs_all,
            default=[],
            key="dep_parr",
        )

    g1, g2, g3 = st.columns(3)
    with g1:
        filt_cruce = st.multiselect(
            "Estatus de cruce Habitable",
            options=list(ESTATUS_CRUCE.values()),
            default=[],
            key="dep_cruce",
            help="Cruzado / no cruzado / por revisar.",
        )
    with g2:
        eti_opts = ["VERDE", "AMARILLO", "ROJO", "NEGRO", "(sin etiqueta)"]
        filt_eti = st.multiselect(
            "Estatus inspección Habitable",
            options=eti_opts,
            default=[],
            key="dep_eti",
        )
    with g3:
        cal_opts = (
            sorted(sol["calidad_geo"].dropna().unique().tolist())
            if "calidad_geo" in sol.columns
            else []
        )
        filt_cal = st.multiselect(
            "Calidad GPS",
            options=cal_opts,
            default=[],
            key="dep_cal",
        )

    t1, t2, t3 = st.columns(3)
    with t1:
        solo_cola = st.checkbox(
            "Solo cola pendiente (no cruzados)",
            value=False,
            key="dep_cola",
            help="Casos aún no atendidos según el cruce — para Habitable / contacto.",
        )
    with t2:
        solo_rev = st.checkbox(
            "Solo pendientes de revisión (GPS o cruce dudoso)",
            value=False,
            key="dep_rev",
        )
    with t3:
        solo_rep = st.checkbox(
            "Solo representantes (mapa) — no usar para contacto",
            value=False,
            key="dep_rep",
            help="Oculta vecinos del mismo cluster. No recomendado para informar caso a caso.",
        )

    filtrado = apply_export_filters(
        sol,
        estados=filt_est or None,
        municipios=filt_mun or None,
        parroquias=filt_parr or None,
        estatus_cruce=filt_cruce or None,
        etiquetas_hab=filt_eti or None,
        calidad_geo=filt_cal or None,
        solo_representantes=solo_rep,
        solo_requiere_revision=solo_rev,
        solo_cola_pendiente=solo_cola,
    )
    n_casos = (
        filtrado["codigo_caso"].nunique()
        if "codigo_caso" in filtrado.columns
        else len(filtrado)
    )
    st.info(
        f"Filas / casos a descargar: **{fmt_num(len(filtrado))}** "
        f"({fmt_num(n_casos)} códigos distintos) "
        f"de {fmt_num(len(sol))} en el universo completo."
    )
    if solo_rep:
        st.warning(
            "Tienes activo «solo representantes»: se ocultan casos vecinos "
            "del mismo punto. Para contactar por número de caso, desactívalo."
        )

    try:
        if filtrado.empty:
            st.warning("Sin filas con los filtros actuales. Amplía la selección.")
        else:
            xlsx = excel_bytes_depurado(filtrado)
            st.download_button(
                "Descargar 1×10 caso a caso (Excel)",
                data=xlsx,
                file_name="solicitudes_1x10_casos_contacto.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True,
                help="Una fila por código de caso + cruce Habitable + cola de contacto.",
            )
            with st.expander("Qué contiene cada pestaña del Excel", expanded=True):
                st.markdown(
                    """
- **`cola_pendiente_casos`**: casos del 1×10 **sin** cruce útil con Habitable (aún no atendidos). Para la cola de contacto / pedir revisión.
- **`casos_atendidos_informar`**: casos del 1×10 **ya cruzados** con Habitable (alta o media). Para informar al ciudadano.
- **`1x10_depurado`**: **todos** los casos del filtro (pendientes + cruzados + dudosos), con denunciante y teléfono.
- **`cruce_habitable`** / **`estatus_habitable`** / **`calidad_geo`** / **`resumen_depuracion`**: conteos y totales de apoyo.
- **`leyenda_hojas`**: esta misma explicación dentro del archivo.
                    """.strip()
                )
                st.caption(
                    "Atajo: si solo necesitan no atendidos, abran "
                    "`cola_pendiente_casos`. No hace falta filtrar a mano."
                )
                st.markdown("##### Texto para compartir")
                st.code(texto_leyenda_hojas_excel(), language=None)
    except Exception as exc:  # noqa: BLE001
        st.warning(f"No se pudo generar el Excel depurado: {exc}")


def page_1x10(sol: pd.DataFrame, summary: dict, sub: str = "x10_analisis"):
    from ui_theme import render_kpi_strip, render_section

    if sub == "x10_depuracion":
        render_section(
            "Depuración 1×10",
            "Limpieza del Excel ciudadano antes del cruce con Habitable.",
        )
        _seccion_depuracion_1x10(sol, summary)
        return

    if sub == "x10_cola":
        render_section(
            "Cola pendientes",
            "Casos 1×10 sin cruce Habitable, listos para contacto por código.",
        )
    else:
        render_section(
            "Territorio y cruce",
            "Demanda ciudadana: volumen, territorio y estado frente a Habitable. "
            f"Ubicaciones unificadas a {summary.get('dedupe_radius_m', 10)} m "
            f"(GPS + dirección; posible agrupación).",
        )

    use_unique = st.toggle(
        "Usar ubicaciones unificadas (recomendado)",
        value=True,
        key="x10_unique",
    )
    base = sol[sol["mapeable"]].copy()
    if use_unique and "es_representante" in base.columns:
        work = base[base["es_representante"]]
    else:
        work = base

    if sub == "x10_cola":
        st.markdown("#### Pendientes de atender (cola por código de caso)")
        st.caption(
            "Listado **caso a caso** (no unificado). Sirve para contactar por "
            "`codigo_caso` e indicar a Habitable qué falta por revisar."
        )
        estados = st.multiselect(
            "Filtrar pendientes por estado",
            options=sorted(base["estado_n"].unique()),
            default=["DISTRITO CAPITAL", "LA GUAIRA"]
            if {"DISTRITO CAPITAL", "LA GUAIRA"} <= set(base["estado_n"].unique())
            else [],
            key="pend_est",
        )
        pend = base[base["match_cat"] == "solo_1x10"].copy()
        if estados:
            pend = pend[pend["estado_n"].isin(estados)]
        show_cols = [
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
                "n_reportes",
                "codigos_grupo",
                "lat",
                "lng",
                "match_cat",
            ]
            if c in pend.columns
        ]
        st.dataframe(
            pend[show_cols].head(500), use_container_width=True, hide_index=True
        )
        st.caption(
            f"Mostrando hasta 500 de {fmt_num(len(pend))} casos pendientes "
            f"(una fila por código)."
        )
        st.download_button(
            "Descargar cola pendiente caso a caso (CSV)",
            data=pend[show_cols].to_csv(index=False).encode("utf-8-sig"),
            file_name="cola_pendiente_1x10_casos.csv",
            mime="text/csv",
        )
        return

    alta = int((work["match_cat"] == "coincide_alta").sum())
    media = int((work["match_cat"] == "coincide_media").sum())
    solo = int((work["match_cat"] == "solo_1x10").sum())
    dud = int((work["match_cat"] == "coincide_geo_solo").sum())
    atendidas = alta + media
    n_map = max(len(work), 1)
    n_multi = (
        int((work["n_reportes"] >= 2).sum())
        if "n_reportes" in work.columns
        else 0
    )

    render_kpi_strip(
        [
            {"label": "Reportes", "value": fmt_num(len(sol)), "tone": "info"},
            {
                "label": "Ubicaciones" if use_unique else "Mapeables",
                "value": fmt_num(len(work)),
                "tone": "info",
            },
            {
                "label": "Ya atendidas",
                "value": f"{100 * atendidas / n_map:.1f}%",
                "tone": "success",
                "hint": fmt_num(atendidas),
            },
            {
                "label": "Pendientes",
                "value": f"{100 * solo / n_map:.1f}%",
                "tone": "warning",
                "hint": fmt_num(solo),
            },
            {
                "label": "Por revisar",
                "value": fmt_num(dud),
                "tone": "muted",
                "hint": f"Multi-reporte: {fmt_num(n_multi)}",
            },
        ]
    )

    col1, col2 = st.columns(2)
    with col1:
        est = work["estado_n"].value_counts().head(8)
        labels = [
            "Distrito Capital"
            if x == "DISTRITO CAPITAL"
            else "La Guaira"
            if x == "LA GUAIRA"
            else x.title()
            for x in est.index
        ]
        st_echarts(
            bar_vertical(
                "Por estado (universo actual)",
                labels,
                est.values.tolist(),
            ),
            height="380px",
            key="x10_estado",
        )
    with col2:
        order = [
            "solo_1x10",
            "coincide_geo_solo",
            "coincide_alta",
            "coincide_media",
        ]
        labels_map = {
            "solo_1x10": "Pendiente de atender",
            "coincide_geo_solo": "Por revisar (dudoso)",
            "coincide_alta": "Ya atendida (alta)",
            "coincide_media": "Ya atendida (media)",
        }
        cruce = work["match_cat"].value_counts()
        labs, vals, cols = [], [], []
        for k in order:
            if k in cruce.index:
                labs.append(labels_map[k])
                vals.append(int(cruce[k]))
                cols.append(MATCH_COLORS.get(k, "#9CA3AF"))
        st_echarts(
            donut("¿La solicitud ya fue atendida?", labs, vals, cols),
            height="380px",
            key="x10_cruce",
        )

    if "n_reportes" in work.columns:
        top = (
            work[work["n_reportes"] >= 2]
            .sort_values("n_reportes", ascending=False)
            .head(15)
        )
        if not top.empty:
            st.markdown("#### Ubicaciones con más reportes repetidos")
            show = [
                c
                for c in [
                    "n_reportes",
                    "direccion",
                    "estado_n",
                    "parroquia_n",
                    "match_cat",
                    "codigos_grupo",
                ]
                if c in top.columns
            ]
            st.dataframe(top[show], use_container_width=True, hide_index=True)

    parr = work["parroquia_n"].replace("", np.nan).dropna().value_counts().head(10)
    st_echarts(
        bar_horizontal(
            "Top parroquias",
            [str(x).title() for x in parr.index],
            parr.values.tolist(),
        ),
        height="420px",
        key="x10_parroq",
    )


def _hab_filters(hab: pd.DataFrame, key_prefix: str) -> pd.DataFrame:
    estados = sorted(hab["estado_n"].dropna().unique().tolist())
    default = [
        e
        for e in ["DISTRITO CAPITAL", "LA GUAIRA", "MIRANDA"]
        if e in estados
    ]
    sel_est = st.multiselect(
        "Estado",
        options=estados,
        default=default or estados[:3],
        key=f"{key_prefix}_est",
    )
    hab_f = filter_territorio(hab, estados=sel_est or None)
    munis = sorted(hab_f["municipio_n"].dropna().unique().tolist())
    sel_mun = st.multiselect(
        "Municipio (opcional)",
        options=munis,
        default=[],
        key=f"{key_prefix}_mun",
    )
    if sel_mun:
        hab_f = filter_territorio(hab_f, municipios=sel_mun)
    return hab_f


def page_habitable(hab: pd.DataFrame, summary: dict, sub: str = "hab_matriz"):
    from ui_theme import render_kpi_strip, render_section

    render_section(
        "Análisis Habitable",
        "Resultado de campo: riesgo, tipología y reportes de daños "
        "(no estructurales · moderados · severos/externos).",
    )

    n_hab = max(len(hab), 1)
    n_verde = int((hab["etiqueta_n"] == "VERDE").sum())
    n_amarillo = int((hab["etiqueta_n"] == "AMARILLO").sum())
    n_crit = int(hab["etiqueta_n"].isin(["ROJO", "NEGRO"]).sum())
    render_kpi_strip(
        [
            {"label": "Inspecciones", "value": fmt_num(len(hab)), "tone": "info"},
            {
                "label": "Verde",
                "value": fmt_num(n_verde),
                "tone": "success",
                "hint": f"{100 * n_verde / n_hab:.1f}%",
            },
            {
                "label": "Amarillo",
                "value": fmt_num(n_amarillo),
                "tone": "flag",
                "hint": f"{100 * n_amarillo / n_hab:.1f}%",
            },
            {
                "label": "Rojo + negro",
                "value": fmt_num(n_crit),
                "tone": "warning",
                "hint": f"{100 * n_crit / n_hab:.1f}%",
            },
            {
                "label": "Alta confianza",
                "value": fmt_num(int(hab["alta_confianza"].sum())),
                "tone": "muted",
            },
        ]
    )

    if sub == "hab_matriz":
        _tab_matriz_semaforo(hab)
    elif sub == "hab_explorar":
        _tab_explorar_perspective(hab)
    elif sub == "hab_ne":
        _tab_no_estructural(hab)
    elif sub == "hab_mod":
        _tab_moderado(hab)
    else:
        _tab_severo_externo(hab)


def _tab_explorar_perspective(hab: pd.DataFrame):
    """Ensayo local: Perspective (pivot/filtro/gráfico) en lugar de PyGWalker."""
    from ui_theme import render_section

    render_section(
        "Explorar / reportería (Perspective · ensayo)",
        "Pivot, filtros y gráficos en el navegador (WASM). Ensayo local para "
        "evaluar si sustituye a PyGWalker.",
    )
    st.caption(
        "Herramienta: Perspective. No publicar en prod hasta validar rendimiento "
        "y usabilidad con el equipo."
    )

    base = _hab_filters(hab, "explore")
    explore = habitable_explore_frame(base)
    if explore.empty:
        st.warning("Sin filas en el filtro actual.")
        return

    st.info(
        f"Universo del filtro · {fmt_num(len(explore))} inspecciones · "
        f"{len(explore.columns)} campos. "
        "Prueba pivotes por `etiqueta` / `estado` y cambia el plugin (tabla o gráfico)."
    )

    with st.expander("Campos disponibles en esta vista", expanded=False):
        st.write(", ".join(explore.columns.tolist()))

    # Serialización JSON-safe (NaN/Inf → null; fechas → texto)
    work = explore.copy()
    for c in work.columns:
        if pd.api.types.is_datetime64_any_dtype(work[c]):
            work[c] = work[c].dt.strftime("%Y-%m-%d %H:%M:%S")
    # to_json convierte NaN → null (dict(orient=records) deja NaN inválido en JSON)
    rows = json.loads(work.to_json(orient="records", date_format="iso"))

    try:
        from streamlit_perspective import perspective_static
    except Exception:
        # Prod / entornos sin el paquete: mantener PyGWalker.
        _tab_explorar_pygwalker(hab)
        return

    perspective_static(
        rows,
        height=780,
        config={
            "plugin": "datagrid",
            "settings": True,
        },
        key="hab_perspective_explore",
    )


def _tab_explorar_pygwalker(hab: pd.DataFrame):
    """Ventana PyGWalker: el usuario construye sus propios análisis/reportes."""
    import streamlit.components.v1 as components

    from ui_theme import render_section

    render_section(
        "Explorar / reportería libre",
        "Arrastra campos a filas, columnas, color o tamaño para armar tablas y "
        "gráficos. Parte del universo Habitable filtrado por territorio.",
    )
    st.caption(
        "Herramienta: PyGWalker (Graphic Walker). Los gráficos se construyen "
        "en esta sesión; no sustituyen los reportes oficiales de la matriz."
    )

    base = _hab_filters(hab, "explore")
    explore = habitable_explore_frame(base)
    if explore.empty:
        st.warning("Sin filas en el filtro actual.")
        return

    st.info(
        f"Universo completo del filtro · {fmt_num(len(explore))} inspecciones · "
        f"{len(explore.columns)} campos. "
        "Sugerencia: `etiqueta` o `semaforo_grupo` en color; "
        "`estado` / `num_pisos` en ejes."
    )

    with st.expander("Campos disponibles en esta vista", expanded=False):
        st.write(", ".join(explore.columns.tolist()))

    try:
        import pygwalker as pyg
    except ImportError:
        st.error(
            "Falta instalar PyGWalker. En el entorno del BI ejecuta: "
            "`pip install pygwalker`"
        )
        return

    # Embed HTML (compatible con Streamlit reciente; evita API Tornado rota)
    from io import BytesIO

    buf = BytesIO()
    explore.to_parquet(buf, index=False)
    payload = buf.getvalue()

    @st.cache_data(show_spinner="Generando explorador PyGWalker…")
    def _pyg_html(data_bytes: bytes) -> str:
        return pyg.to_html(pd.read_parquet(BytesIO(data_bytes)))

    html = _pyg_html(payload)
    components.html(html, height=920, scrolling=True)


def _tab_matriz_semaforo(hab: pd.DataFrame):
    """Ensayo local: cruces etiqueta × riesgos / tipología con filtro territorial."""
    from ui_theme import render_kpi_strip, render_section

    st.caption(
        "Ensayo local · composición siempre en verde · amarillo · rojo+negro. "
        "Los filtros recalculan N y todas las tablas."
    )
    base = _hab_filters(hab, "matriz")
    work = prepare_matriz_frame(base)
    if work.empty:
        st.warning("Sin inspecciones con etiqueta V/A/R/N en el filtro actual.")
        return

    n = len(work)
    n_v = int((work["et"] == "VERDE").sum())
    n_a = int((work["et"] == "AMARILLO").sum())
    n_c = int(work["et"].isin(["ROJO", "NEGRO"]).sum())
    render_kpi_strip(
        [
            {"label": "En filtro", "value": fmt_num(n), "tone": "info"},
            {
                "label": "Verde",
                "value": fmt_num(n_v),
                "tone": "success",
                "hint": f"{100 * n_v / n:.1f}%",
            },
            {
                "label": "Amarillo",
                "value": fmt_num(n_a),
                "tone": "flag",
                "hint": f"{100 * n_a / n:.1f}%",
            },
            {
                "label": "Rojo + negro",
                "value": fmt_num(n_c),
                "tone": "warning",
                "hint": f"{100 * n_c / n:.1f}%",
            },
        ]
    )

    render_section(
        "Etiqueta × riesgos",
        "A / B / C / vacío. Negros del dato Habitable; vacíos no se imputan.",
    )
    dim_labels = list(RISK_DIMS.values())
    dim_keys = list(RISK_DIMS.keys())
    c1, c2 = st.columns([2, 1])
    with c1:
        dim_label = st.selectbox(
            "Dimensión de riesgo",
            options=dim_labels,
            index=dim_keys.index("peor_riesgo"),
            key="matriz_risk_dim",
        )
    with c2:
        mode = st.radio(
            "Valores",
            options=["Conteo", "% fila"],
            horizontal=True,
            key="matriz_risk_mode",
        )
    dim_key = dim_keys[dim_labels.index(dim_label)]
    col_src = "peor_riesgo_n" if dim_key == "peor_riesgo" else f"{dim_key}_n"
    ct = crosstab_etiqueta(work, col_src, RIESGO_LEVELS)
    if mode == "% fila":
        show = ct.copy().astype(float)
        for idx in show.index:
            den = float(ct.loc[idx, "Total"]) or 1.0
            show.loc[idx] = (ct.loc[idx] / den * 100).round(1)
        st.dataframe(
            show.rename(columns={"VACIO": "Vacío"}),
            use_container_width=True,
        )
        st.caption("Porcentajes dentro de cada etiqueta (fila). Total de fila = 100%.")
    else:
        st.dataframe(
            ct.rename(columns={"VACIO": "Vacío"}),
            use_container_width=True,
        )

    # Margen de columnas como barras
    margin = ct.loc["Total", RIESGO_LEVELS]
    st_echarts(
        bar_vertical(
            f"Distribución — {dim_label}",
            ["A", "B", "C", "Vacío"],
            [int(margin[c]) for c in RIESGO_LEVELS],
        ),
        height="280px",
        key="matriz_risk_margin",
    )

    render_section(
        "Tipología × semáforo",
        "Composición verde / amarillo / rojo+negro por característica.",
    )
    tipo = st.radio(
        "Característica",
        options=["Pisos", "Uso", "Material"],
        horizontal=True,
        key="matriz_tipo",
    )
    if tipo == "Pisos":
        mix = semaforo_mix_by(work, "piso_band", PISO_BANDS + ["Sin dato"])
        ct_tipo = crosstab_etiqueta(work, "piso_band", PISO_BANDS + ["Sin dato"])
    elif tipo == "Uso":
        cats = work["uso_g"].value_counts().index.tolist()
        mix = semaforo_mix_by(work, "uso_g", cats)
        ct_tipo = crosstab_etiqueta(work, "uso_g", cats)
    else:
        cats = work["material_g"].value_counts().index.tolist()
        mix = semaforo_mix_by(work, "material_g", cats)
        ct_tipo = crosstab_etiqueta(work, "material_g", cats)

    with st.expander("Matriz etiqueta × tipología (conteos)", expanded=False):
        st.dataframe(ct_tipo, use_container_width=True)

    if not mix.empty:
        show_mix = mix.rename(
            columns={
                "categoria": "Categoría",
                "n": "n",
                "pct_verde": "% verde",
                "pct_amarillo": "% amarillo",
                "pct_rojo_negro": "% rojo+negro",
            }
        )
        st.dataframe(show_mix, use_container_width=True, hide_index=True)
        st_echarts(
            bar_stacked_pct(
                f"Composición semáforo por {tipo.lower()}",
                mix["categoria"].tolist(),
                [
                    ("Verde", mix["pct_verde"].tolist(), ETIQUETA_COLORS["VERDE"]),
                    (
                        "Amarillo",
                        mix["pct_amarillo"].tolist(),
                        ETIQUETA_COLORS["AMARILLO"],
                    ),
                    (
                        "Rojo + negro",
                        mix["pct_rojo_negro"].tolist(),
                        ETIQUETA_COLORS["ROJO"],
                    ),
                ],
            ),
            height="340px",
            key="matriz_tipo_stack",
        )

    with st.expander("Perfiles Ext|Sev|Mod|Comp más frecuentes"):
        prof = risk_profile_top(work, n=15)
        if prof.empty:
            st.caption("Sin perfiles.")
        else:
            st.dataframe(
                prof.rename(columns={"perfil": "Perfil", "n": "n", "pct": "%"}),
                use_container_width=True,
                hide_index=True,
            )
            st.caption("Orden: externo | severo | moderado | componentes.")


def _tab_no_estructural(hab: pd.DataFrame):
    st.markdown(
        "**Criterio (doc. técnico):** `riesgo_externo=A`, `riesgo_severo=A`, "
        "`riesgo_moderado=A` y `riesgo_componentes ≠ A`. "
        "Prioriza mitigación rápida (fachadas, instalaciones, servicios)."
    )
    base = _hab_filters(hab, "ne")
    sub = base.loc[mask_no_estructural(base)]
    m1, m2 = st.columns(2)
    m1.metric("Infraestructuras en categoría", fmt_num(len(sub)))
    m2.metric("Cuadrillas (inspectores)", fmt_num(count_cuadrillas(sub)))

    if sub.empty:
        st.warning("Sin registros con el filtro actual.")
        return

    col1, col2 = st.columns(2)
    with col1:
        eti = etiqueta_counts(sub)
        labs = [k.title() for k in eti.index if eti[k] > 0]
        vals = [int(eti[k]) for k in eti.index if eti[k] > 0]
        cols = [ETIQUETA_COLORS.get(k, "#9CA3AF") for k in eti.index if eti[k] > 0]
        st_echarts(
            donut("% por etiqueta de riesgo", labs, vals, cols),
            height="360px",
            key="ne_eti",
        )
    with col2:
        comps = component_presence_counts(sub)
        items = sorted(comps.items(), key=lambda x: x[1], reverse=True)
        items = [(k, v) for k, v in items if v > 0][:10]
        if items:
            st_echarts(
                bar_horizontal(
                    "Componentes / servicios informados",
                    [k for k, _ in items],
                    [v for _, v in items],
                ),
                height="360px",
                key="ne_comp",
            )
        else:
            st.info("Sin conteos de componentes en el subconjunto.")

    with st.expander("Lista de infraestructuras (exportable)"):
        vista = list_view(sub, 800)
        st.dataframe(vista, use_container_width=True)
        st.download_button(
            "CSV no estructurales",
            data=vista.to_csv(index=False).encode("utf-8-sig"),
            file_name="habitable_no_estructurales.csv",
            mime="text/csv",
            key="dl_ne",
        )


def _tab_moderado(hab: pd.DataFrame):
    st.markdown(
        "**Criterio:** `riesgo_externo=A`, `riesgo_severo=A`, "
        "`riesgo_moderado ∈ {A,B,C}`. Bandas Bajo (<10%) / Medio (10–30%) / "
        "Alto (>30%) por elemento según fórmula exam/(exam+mod)."
    )
    base = _hab_filters(hab, "mod")
    sub = base.loc[mask_moderado(base)]
    st.metric("Infraestructuras en categoría", fmt_num(len(sub)))

    if sub.empty:
        st.warning("Sin registros con el filtro actual.")
        return

    summary = moderado_band_summary(sub)
    eti = etiqueta_counts(sub)
    col1, col2 = st.columns(2)
    with col1:
        labs = [k.title() for k in eti.index if eti[k] > 0]
        vals = [int(eti[k]) for k in eti.index if eti[k] > 0]
        cols = [ETIQUETA_COLORS.get(k, "#9CA3AF") for k in eti.index if eti[k] > 0]
        st_echarts(
            donut("Etiqueta (V / A / R / N)", labs, vals, cols),
            height="340px",
            key="mod_eti",
        )
    with col2:
        st.metric(
            "Combinación banda media",
            fmt_num(summary["combinacion_moderados"]),
        )
        st.metric(
            "Combinación altos (≥2 elementos)",
            fmt_num(summary["combinacion_altos_2plus"]),
        )
        st.metric(
            "Al menos un elemento alto",
            fmt_num(summary["al_menos_un_alto"]),
        )

    st.markdown("##### Bandas por elemento estructural")
    rows = []
    for elem, bands in summary["by_element"].items():
        rows.append(
            {
                "Elemento": elem,
                "Bajo (<10%)": bands.get("Bajo (<10%)", 0),
                "Medio (10–30%)": bands.get("Medio (10–30%)", 0),
                "Alto (>30%)": bands.get("Alto (>30%)", 0),
                "Sin dato": bands.get("Sin dato", 0),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    altos = [(r["Elemento"], r["Alto (>30%)"]) for r in rows if r["Alto (>30%)"] > 0]
    if altos:
        st_echarts(
            bar_vertical(
                "Elementos en banda alta (>30%)",
                [a[0] for a in altos],
                [a[1] for a in altos],
            ),
            height="320px",
            key="mod_alto",
        )

    with st.expander("Lista de infraestructuras (exportable)"):
        vista = list_view(sub, 800)
        st.dataframe(vista, use_container_width=True)
        st.download_button(
            "CSV estructurales moderados",
            data=vista.to_csv(index=False).encode("utf-8-sig"),
            file_name="habitable_estructurales_moderados.csv",
            mime="text/csv",
            key="dl_mod",
        )


def _tab_severo_externo(hab: pd.DataFrame):
    st.markdown(
        "**Severos:** `riesgo_severo=C` o `sev_* > 0` (mecanismo de falla). "
        "**Externos:** riesgo del entorno (aledaños, geología, asentamiento, "
        "inclinación, colapso)."
    )
    base = _hab_filters(hab, "sev")

    st.markdown("### Daños estructurales severos")
    sub_sev = base.loc[mask_severo(base)]
    rojas = sub_sev[sub_sev["etiqueta_n"].isin(["ROJO", "NEGRO"])]
    c1, c2, c3 = st.columns(3)
    c1.metric("Con daño severo", fmt_num(len(sub_sev)))
    c2.metric("Rojas / negras", fmt_num(len(rojas)))
    c3.metric(
        "% rojas-negras en severos",
        f"{100 * len(rojas) / max(len(sub_sev), 1):.1f}%",
    )

    if not sub_sev.empty:
        mech = severo_mechanism_summary(sub_sev)
        col1, col2 = st.columns(2)
        with col1:
            solo = mech["solo"]
            st_echarts(
                donut(
                    "Mecanismo (solo un elemento)",
                    list(solo.keys()),
                    list(solo.values()),
                ),
                height="340px",
                key="sev_solo",
            )
        with col2:
            st_echarts(
                bar_vertical(
                    "Severos: solo vs combinación",
                    ["Solo un elemento", "Combinación 2+", "Con algún sev_*"],
                    [
                        sum(solo.values()),
                        mech["combinacion_2plus"],
                        mech["con_algun_sev"],
                    ],
                ),
                height="340px",
                key="sev_combo",
            )
        with st.expander("Lista estructuras con daño severo"):
            vista = list_view(sub_sev, 800)
            st.dataframe(vista, use_container_width=True)
            st.download_button(
                "CSV severos",
                data=vista.to_csv(index=False).encode("utf-8-sig"),
                file_name="habitable_estructurales_severos.csv",
                mime="text/csv",
                key="dl_sev",
            )
    else:
        st.warning("Sin daños severos en el filtro actual.")

    st.markdown("### Daños externos (entorno)")
    mod_ext = base.loc[mask_externo_moderado(base)]
    alto_ext = base.loc[mask_externo_alto(base)]
    e1, e2 = st.columns(2)
    e1.metric("Externos moderados", fmt_num(len(mod_ext)))
    e2.metric("Externos altos (C)", fmt_num(len(alto_ext)))

    col1, col2 = st.columns(2)
    with col1:
        br = externo_breakdown(mod_ext, "B") if len(mod_ext) else {}
        items = [(k, v) for k, v in br.items() if v > 0]
        if items:
            st_echarts(
                bar_horizontal(
                    "Moderados por tipo (B)",
                    [k for k, _ in items],
                    [v for _, v in items],
                ),
                height="320px",
                key="ext_mod",
            )
    with col2:
        br = externo_breakdown(alto_ext, "C") if len(alto_ext) else {}
        items = [(k, v) for k, v in br.items() if v > 0]
        if items:
            st_echarts(
                bar_horizontal(
                    "Altos por tipo (C)",
                    [k for k, _ in items],
                    [v for _, v in items],
                ),
                height="320px",
                key="ext_alto",
            )

    with st.expander("Lista daños externos altos"):
        st.dataframe(list_view(alto_ext, 500), use_container_width=True)


def page_reportes_inspecciones(
    sol: pd.DataFrame, summary: dict, sub: str = "pend_mapa"
):
    """1×10 pendientes: mapa por ubicación + listado/descargas + diagnóstico."""
    from map_robust import render_pendientes_map_ui
    from reportes_inspecciones import (
        DIAGNOSTICO_CRUCE,
        excel_bytes_reportes_inspeccion,
        frame_ubicaciones_inspeccion,
        resumen_ubicaciones,
    )
    from ui_theme import render_kpi_strip, render_section

    render_section(
        "1×10 pendientes",
        "Ubicaciones agrupadas · filtros + descarga arriba · mapa debajo.",
    )

    sec = {
        "pend_mapa": "mapa",
        "pend_listado": "listado",
        "pend_descripcion": "descripcion",
        "pend_diagnostico": "diagnostico",
    }.get(sub, "mapa")

    # Filtros territoriales compartidos (mapa + listado)
    estados_all = (
        sorted(sol["estado_n"].dropna().unique().tolist())
        if "estado_n" in sol.columns
        else []
    )
    default_est = [
        e
        for e in ["DISTRITO CAPITAL", "LA GUAIRA", "MIRANDA"]
        if e in estados_all
    ]

    if sec == "diagnostico":
        render_kpi_strip(
            [
                {
                    "label": "Cruzados auto",
                    "value": fmt_num(summary.get("coincide_auto", 0)),
                    "tone": "success",
                    "hint": f"{summary.get('pct_ya_insp', 0)}% de mapeables",
                },
                {
                    "label": "Pendientes 1×10",
                    "value": fmt_num(summary.get("solo_1x10", 0)),
                    "tone": "warning",
                    "hint": f"{summary.get('pct_pendiente', 0)}% mapeables",
                },
                {
                    "label": "Dudosos",
                    "value": fmt_num(summary.get("dudosos", 0)),
                    "tone": "muted",
                },
                {
                    "label": "Habitable",
                    "value": fmt_num(summary.get("n_hab", 0)),
                    "tone": "info",
                },
            ]
        )
        st.markdown(
            """
### Lectura ejecutiva

El cruce automático es relativamente bajo sobre todo por **cobertura y densidad**,
no solo por umbrales de nombre:

1. Gran parte de las 1×10 mapeables no tienen inspección Habitable a **≤50 m**
   (la mediana de distancia al Habitable más cercano supera ese radio).
   En Miranda y el interior la brecha es de **campo**.
2. Donde sí hay algo cerca, en Distrito Capital / La Guaira el pin suele ser
   **otro edificio** (densidad urbana).
3. 1×10 compara la **dirección completa** vs el **nombre corto** de Habitable;
   el matching revisa **varios vecinos** en el radio y similitud parcial.

**Implicación para inspecciones:** priorizar la cola por **ubicación**
(esta pestaña), no caso a caso: varios vecinos del mismo punto se visitan
una sola vez.
            """.strip()
        )
        st.dataframe(
            pd.DataFrame(DIAGNOSTICO_CRUCE),
            use_container_width=True,
            hide_index=True,
        )
        return

    # —— Barra compacta: filtros + descarga (mapa queda arriba) ——
    st.markdown("##### Filtros y descarga")
    r1 = st.columns([1.2, 1.1, 1.1, 0.75, 1.0])
    with r1[0]:
        filt_est = st.multiselect(
            "Estado",
            options=estados_all,
            default=default_est,
            key="ri_est",
        )
    sol_f = sol
    if filt_est and "estado_n" in sol.columns:
        sol_f = sol[sol["estado_n"].isin(filt_est)]
    munis = (
        sorted(sol_f["municipio_n"].dropna().unique().tolist())
        if "municipio_n" in sol_f.columns
        else []
    )
    with r1[1]:
        filt_mun = st.multiselect(
            "Municipio",
            options=munis,
            default=[],
            key="ri_mun",
        )
    sol_p = sol_f
    if filt_mun and "municipio_n" in sol_p.columns:
        sol_p = sol_p[sol_p["municipio_n"].isin(filt_mun)]
    parrs = (
        sorted(sol_p["parroquia_n"].replace("", pd.NA).dropna().unique().tolist())
        if "parroquia_n" in sol_p.columns
        else []
    )
    with r1[2]:
        filt_parr = st.multiselect(
            "Parroquia",
            options=parrs,
            default=[],
            key="ri_parr",
        )
    with r1[3]:
        min_casos = st.number_input(
            "Mín. casos",
            min_value=1,
            max_value=50,
            value=1,
            key="ri_min",
        )
    with r1[4]:
        solo_multi = st.checkbox(
            "Cúmulos 2+",
            value=False,
            key="ri_multi",
            help="Solo ubicaciones con 2 o más reportes (volumen, no prioridad).",
        )
        cumulo_5 = st.checkbox(
            "Cúmulos 5+",
            value=False,
            key="ri_cumulo5",
            help="Solo puntos con 5 o más casos agrupados (cúmulo, no prioridad).",
        )
        incluir_gps_dudoso = st.checkbox(
            "Incluir GPS en mar / dudosos",
            value=False,
            key="ri_gps_dudoso",
            help="Por defecto se ocultan puntos en mar abierto o fuera de estado.",
        )

    min_eff = max(
        int(min_casos),
        2 if solo_multi else 1,
        5 if cumulo_5 else 1,
    )

    # Conteo de excluidos por GPS dudoso (para aviso)
    n_excl_gps = 0
    if not incluir_gps_dudoso and "mapa_ok" in sol.columns:
        base_geo = sol
        if filt_est and "estado_n" in sol.columns:
            base_geo = base_geo[base_geo["estado_n"].isin(filt_est)]
        if "match_cat" in base_geo.columns:
            base_geo = base_geo[base_geo["match_cat"].isin(["solo_1x10", "no_mapeable"])]
        if "mapeable" in base_geo.columns:
            base_geo = base_geo[base_geo["mapeable"].fillna(False)]
        if "es_representante" in base_geo.columns:
            base_geo = base_geo[base_geo["es_representante"]]
        n_excl_gps = int((~base_geo["mapa_ok"].fillna(False)).sum())

    pend = frame_ubicaciones_inspeccion(
        sol,
        solo_pendientes=True,
        solo_mapa_ok=not incluir_gps_dudoso,
        estados=filt_est or None,
        municipios=filt_mun or None,
        parroquias=filt_parr or None,
        min_casos=min_eff,
    )
    if not pend.empty and "cantidad_casos" in pend.columns:
        pend = pend.copy()
        pend["n_reportes"] = pend["cantidad_casos"]

    rp = resumen_ubicaciones(pend)

    # Firma del filtro activo (tabla/mapa). Streamlit puede servir un
    # download_button con payload viejo si el key no cambia con el filtro.
    filt_payload = {
        "est": sorted(filt_est or []),
        "mun": sorted(filt_mun or []),
        "parr": sorted(filt_parr or []),
        "min": int(min_eff),
        "gps_dudoso": bool(incluir_gps_dudoso),
        "n_pend": int(len(pend)),
    }
    filt_sig = hashlib.sha1(
        json.dumps(filt_payload, ensure_ascii=True, sort_keys=True).encode(
            "utf-8"
        )
    ).hexdigest()[:12]
    export_ss = "ri_export_bytes"
    export = st.session_state.get(export_ss)
    export_ok = isinstance(export, dict) and export.get("sig") == filt_sig

    extra_gps = (
        f" · ocultos por GPS dudoso/mar: **{fmt_num(n_excl_gps)}**"
        if (not incluir_gps_dudoso and n_excl_gps)
        else ""
    )
    alcance = []
    if filt_est:
        alcance.append(
            "Estados: "
            + ", ".join(filt_est[:3])
            + ("…" if len(filt_est) > 3 else "")
        )
    else:
        alcance.append("Estados: todos")
    if filt_mun:
        alcance.append(f"Municipios: {len(filt_mun)}")
    if filt_parr:
        alcance.append(f"Parroquias: {len(filt_parr)}")
    if min_eff > 1:
        alcance.append(f"Mín. casos: {min_eff}")

    st.caption(
        f"**{fmt_num(len(pend))}** ubicaciones pendientes · "
        f"**{fmt_num(rp['n_casos'])}** casos 1×10 en total · "
        f"**{fmt_num(rp['n_multi'])}** ubicaciones con 2 o más reportes · "
        f"máximo **{fmt_num(rp['max_casos'])}** casos en un mismo punto"
        f"{extra_gps}"
    )
    st.caption(
        "Filtro activo · "
        + " · ".join(alcance)
        + f" · id `{filt_sig}`"
    )

    # CSV ligero siempre alineado al filtro; Excel solo al preparar
    # (evita payload stale + bloqueo al regenerar xlsx en cada clic).
    csv_bytes = pend.to_csv(index=False).encode("utf-8-sig")
    d1, d2, d3 = st.columns([1, 1, 1.4])
    with d1:
        st.download_button(
            "CSV filtrado",
            data=csv_bytes,
            file_name=f"pendientes_1x10_filtrado_{filt_sig}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"dl_{sec}_csv_{filt_sig}",
        )
    with d2:
        prep = st.button(
            "Preparar Excel filtrado",
            use_container_width=True,
            type="primary" if not export_ok else "secondary",
            key=f"prep_{sec}_xlsx_{filt_sig}",
            help=(
                "Genera el Excel con el filtro actual. "
                "Obligatorio tras cambiar Estado/Municipio/… "
                "antes de descargar."
            ),
        )
        if prep:
            with st.spinner("Generando Excel con el filtro actual…"):
                todos = frame_ubicaciones_inspeccion(
                    sol,
                    solo_pendientes=False,
                    solo_mapa_ok=not incluir_gps_dudoso,
                    estados=filt_est or None,
                    municipios=filt_mun or None,
                    parroquias=filt_parr or None,
                    min_casos=min_eff,
                )
                st.session_state[export_ss] = {
                    "sig": filt_sig,
                    "n": int(len(pend)),
                    "xlsx": excel_bytes_reportes_inspeccion(
                        pend, todos, summary=summary
                    ),
                    "alcance": " · ".join(alcance),
                }
            st.rerun()
    with d3:
        if export_ok and isinstance(export, dict) and "xlsx" in export:
            st.download_button(
                f"Excel filtrado ({fmt_num(export.get('n', len(pend)))} ub.)",
                data=export["xlsx"],
                file_name=(
                    f"reportes_1x10_pendientes_filtrado_{filt_sig}.xlsx"
                ),
                mime=(
                    "application/vnd.openxmlformats-officedocument"
                    ".spreadsheetml.sheet"
                ),
                use_container_width=True,
                key=f"dl_{sec}_xlsx_{filt_sig}",
            )
        else:
            prev_n = (
                export.get("n")
                if isinstance(export, dict)
                else None
            )
            if isinstance(export, dict) and export.get("sig") != filt_sig:
                st.warning(
                    "El Excel listo es de **otro filtro**"
                    + (
                        f" ({fmt_num(prev_n)} ub.)"
                        if prev_n is not None
                        else ""
                    )
                    + ". Pulsa **Preparar Excel filtrado**."
                )
            else:
                st.info("Pulsa **Preparar Excel filtrado** para bajarlo.")

    if sec == "mapa":
        render_pendientes_map_ui(pend)
        return

    if sec == "descripcion":
        from analisis_descripcion import (
            NIVEL_ETIQUETA,
            enrich_descripciones,
            frame_casos_por_nivel,
            resumen_niveles,
            top_palabras,
        )

        st.info(
            "Clasificación **heurística por palabras** en la descripción del "
            "ciudadano. Es solo **referencia** para lectura de la demanda: "
            "no sustituye la inspección ni el semáforo Habitable, y **no** "
            "define prioridad operativa por sí sola."
        )
        # Universo de casos (no ubicaciones) con mismos filtros territoriales
        base = sol.copy()
        if filt_est and "estado_n" in base.columns:
            base = base[base["estado_n"].isin(filt_est)]
        if filt_mun and "municipio_n" in base.columns:
            base = base[base["municipio_n"].isin(filt_mun)]
        if filt_parr and "parroquia_n" in base.columns:
            base = base[base["parroquia_n"].isin(filt_parr)]

        enr = enrich_descripciones(base)
        res = resumen_niveles(enr)
        c1, c2 = st.columns([1.2, 1])
        with c1:
            st.markdown("###### Distribución por nivel aparente")
            st.dataframe(res, use_container_width=True, hide_index=True)
        with c2:
            st.markdown("###### Palabras frecuentes en descripciones")
            st.dataframe(
                top_palabras(enr, 25),
                use_container_width=True,
                hide_index=True,
            )

        nivel_opts = list(NIVEL_ETIQUETA.keys())
        labels = [NIVEL_ETIQUETA[k] for k in nivel_opts]
        sel_lab = st.multiselect(
            "Filtrar por nivel aparente",
            options=labels,
            default=[
                NIVEL_ETIQUETA["critico_aparente"],
                NIVEL_ETIQUETA["severo_aparente"],
            ],
            key="desc_niveles",
        )
        inv = {v: k for k, v in NIVEL_ETIQUETA.items()}
        sel_codes = [inv[x] for x in sel_lab if x in inv]
        muestra = frame_casos_por_nivel(
            base,
            niveles=sel_codes or None,
            limit=500,
        )
        st.caption(
            f"Muestra hasta 500 casos · universo filtrado: {fmt_num(len(enr))}."
        )
        st.dataframe(muestra, use_container_width=True, hide_index=True)
        st.download_button(
            "CSV análisis de descripción (muestra)",
            data=muestra.to_csv(index=False).encode("utf-8-sig"),
            file_name="analisis_descripcion_1x10.csv",
            mime="text/csv",
            key="dl_desc_csv",
        )
        return

    # ---- Listado ----
    st.caption(
        "Una fila ≈ ubicación · **cantidad_casos** (cúmulo) + **codigos_casos**. "
        "Agrupación estricta (GPS corto + dirección similar). "
        "**Para Habitable:** puede haber más de una casa/edificio; "
        "usar los códigos para inspección caso a caso. El cúmulo no es prioridad."
    )
    show_cols = [
        c
        for c in [
            "cumulo_casos",
            "cantidad_casos",
            "codigos_casos",
            "direccion",
            "estado_n",
            "municipio_n",
            "parroquia_n",
            "lat",
            "lng",
            "estatus_cruce",
            "calidad_geo",
            "nota_agrupacion",
        ]
        if c in pend.columns
    ]
    st.dataframe(
        pend[show_cols].head(800),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(f"Hasta 800 de {fmt_num(len(pend))} ubicaciones.")