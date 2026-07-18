"""
Páginas de análisis (pestañas 1×10 y Habitable)
===============================================

- ``page_1x10``: demanda ciudadana, territorio, pendientes.
- ``page_habitable``: semáforo y tres secciones de reportes de daños
  (no estructurales / moderados / severos-externos) según criterios
  del documento técnico de la Comisión.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts

from charts_echarts import (
    ETIQUETA_COLORS,
    MATCH_COLORS,
    bar_horizontal,
    bar_vertical,
    donut,
)
from habitable_reports import (
    component_presence_counts,
    count_cuadrillas,
    etiqueta_counts,
    externo_breakdown,
    filter_territorio,
    list_view,
    mask_externo_alto,
    mask_externo_moderado,
    mask_moderado,
    mask_no_estructural,
    mask_severo,
    moderado_band_summary,
    severo_mechanism_summary,
)


def fmt_num(n: float | int) -> str:
    return f"{int(n):,}".replace(",", ".")


def page_1x10(sol: pd.DataFrame, summary: dict):
    from ui_theme import render_kpi_strip, render_section

    render_section(
        "Análisis 1×10",
        "Demanda ciudadana: volumen, territorio y estado frente a Habitable. "
        f"Ubicaciones unificadas a {summary.get('dedupe_radius_m', 20)} m.",
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
            "Caracas"
            if x == "CARACAS"
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

    st.markdown("#### Pendientes de atender")
    estados = st.multiselect(
        "Filtrar pendientes por estado",
        options=sorted(work["estado_n"].unique()),
        default=["CARACAS", "LA GUAIRA"]
        if {"CARACAS", "LA GUAIRA"} <= set(work["estado_n"].unique())
        else [],
        key="pend_est",
    )
    pend = work[work["match_cat"] == "solo_1x10"]
    if estados:
        pend = pend[pend["estado_n"].isin(estados)]
    show_cols = [
        c
        for c in [
            "n_reportes",
            "codigo_caso",
            "codigos_grupo",
            "estado_n",
            "municipio_n",
            "parroquia_n",
            "direccion",
            "lat",
            "lng",
        ]
        if c in pend.columns
    ]
    st.dataframe(pend[show_cols].head(500), use_container_width=True)
    st.download_button(
        "Descargar pendientes (CSV)",
        data=pend[show_cols].to_csv(index=False).encode("utf-8-sig"),
        file_name="pendientes_1x10_unificados.csv",
        mime="text/csv",
    )


def _hab_filters(hab: pd.DataFrame, key_prefix: str) -> pd.DataFrame:
    estados = sorted(hab["estado_n"].dropna().unique().tolist())
    default = [
        e
        for e in ["DISTRITO CAPITAL", "LA GUAIRA", "MIRANDA", "CARACAS"]
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


def page_habitable(hab: pd.DataFrame, summary: dict):
    from ui_theme import render_kpi_strip, render_section, render_section_tabs

    render_section(
        "Análisis Habitable",
        "Resultado de campo: riesgo, tipología y reportes de daños "
        "(no estructurales · moderados · severos/externos).",
    )

    rn = int(hab["etiqueta_n"].isin(["ROJO", "NEGRO"]).sum())
    render_kpi_strip(
        [
            {"label": "Inspecciones", "value": fmt_num(len(hab)), "tone": "info"},
            {
                "label": "Alta confianza",
                "value": fmt_num(int(hab["alta_confianza"].sum())),
                "tone": "success",
            },
            {
                "label": "Verde",
                "value": fmt_num(int((hab["etiqueta_n"] == "VERDE").sum())),
                "tone": "success",
            },
            {
                "label": "Rojo + negro",
                "value": fmt_num(rn),
                "tone": "warning",
            },
            {
                "label": "% crítico",
                "value": f"{100 * rn / max(len(hab), 1):.1f}%",
                "tone": "muted",
            },
        ]
    )

    sec = render_section_tabs(
        [
            ("ne", "No estructurales"),
            ("mod", "Estructurales moderados"),
            ("sev", "Severos y externos"),
        ],
        state_key="hab_dano",
        heading="Secciones de reportes de daños",
    )
    if sec == "ne":
        _tab_no_estructural(hab)
    elif sec == "mod":
        _tab_moderado(hab)
    else:
        _tab_severo_externo(hab)


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
