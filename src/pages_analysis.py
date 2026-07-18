"""Páginas de análisis 1×10 y Habitable (reportes de daños)."""

from __future__ import annotations

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

    sec = render_section_tabs(
        [
            ("matriz", "Matriz semáforo"),
            ("explorar", "Explorar / reportería"),
            ("ne", "No estructurales"),
            ("mod", "Estructurales moderados"),
            ("sev", "Severos y externos"),
        ],
        state_key="hab_dano",
        heading="Secciones de análisis Habitable",
    )
    if sec == "matriz":
        _tab_matriz_semaforo(hab)
    elif sec == "explorar":
        _tab_explorar_pygwalker(hab)
    elif sec == "ne":
        _tab_no_estructural(hab)
    elif sec == "mod":
        _tab_moderado(hab)
    else:
        _tab_severo_externo(hab)


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

    # Tope para no saturar memoria/HTML en instancias pequeñas
    max_rows = st.slider(
        "Máx. filas en el explorador",
        min_value=500,
        max_value=min(len(explore), 10000),
        value=min(len(explore), 5000),
        step=500,
        help="Si el navegador va lento, baja este tope o acota el territorio.",
        key="explore_max_rows",
    )
    if len(explore) > max_rows:
        explore = explore.sample(max_rows, random_state=42)
        st.caption(
            f"Muestra aleatoria de {fmt_num(max_rows)} filas "
            f"(universo filtrado: {fmt_num(len(base))})."
        )

    st.info(
        f"Vista inicial · {fmt_num(len(explore))} inspecciones · "
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
