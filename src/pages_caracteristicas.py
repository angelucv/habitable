"""Información general por fuentes (1×10 y Habitable por separado)."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts

from charts_echarts import ETIQUETA_COLORS, MATCH_COLORS, bar_horizontal, bar_vertical, donut
from ui_theme import render_kpi_strip, render_section


def fmt_num(n: float | int) -> str:
    return f"{int(n):,}".replace(",", ".")


def _pretty_estado(x: str) -> str:
    u = str(x).upper()
    if u == "DISTRITO CAPITAL":
        return "Distrito Capital"
    if u == "LA GUAIRA":
        return "La Guaira"
    if x == "(vacío)":
        return "(vacío)"
    return str(x).title()


def _top_counts(series: pd.Series, n: int = 12) -> tuple[list[str], list[int]]:
    vc = (
        series.fillna("(vacío)")
        .astype(str)
        .replace("", "(vacío)")
        .value_counts()
        .head(n)
    )
    labels = [_pretty_estado(x) for x in vc.index]
    return labels, [int(v) for v in vc.values]


def _fill_rate(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    rows = []
    n = max(len(df), 1)
    for c in cols:
        if c not in df.columns:
            continue
        s = df[c]
        if s.dtype == object or pd.api.types.is_string_dtype(s):
            filled = int(s.fillna("").astype(str).str.strip().ne("").sum())
        else:
            filled = int(s.notna().sum())
        rows.append(
            {
                "Campo": c,
                "Con dato": filled,
                "% completo": round(100 * filled / n, 1),
            }
        )
    return pd.DataFrame(rows)


def _corte_caption(summary: dict, fuente: str) -> None:
    if fuente == "1x10":
        arch = summary.get("corte_1x10_archivo") or "—"
        n = summary.get("corte_1x10_n", summary.get("n_1x10", 0))
    else:
        arch = summary.get("corte_habitable_archivo") or "—"
        n = summary.get("corte_habitable_n", summary.get("n_hab", 0))
    st.caption(
        f"Archivo: **{arch}** · {fmt_num(n or 0)} registros · "
        f"cruce generado {summary.get('corte_generado_en', '—')}"
    )


def page_info_1x10(sol: pd.DataFrame, summary: dict) -> None:
    """Panorama de la fuente 1×10."""
    render_section(
        "Fuente 1×10",
        "Demanda ciudadana: volumen, cruce con Habitable, tipología en dirección y territorio.",
    )
    _corte_caption(summary, "1x10")
    enc = summary.get("encoding_direccion") or {}
    if enc.get("cambiadas"):
        st.caption(
            f"Encoding: **{fmt_num(enc['cambiadas'])}** direcciones corregidas "
            f"(mojibake {fmt_num(enc.get('mojibake_antes', 0))} → "
            f"{fmt_num(enc.get('mojibake_despues', 0))}). "
            "Se muestra `direccion` depurada."
        )

    n = len(sol)
    n_map = int(sol["mapeable"].sum()) if "mapeable" in sol.columns else 0
    n_ok = int(sol["mapa_ok"].sum()) if "mapa_ok" in sol.columns else n_map
    alta = int((sol.get("match_cat") == "coincide_alta").sum()) if "match_cat" in sol.columns else 0
    media = int((sol.get("match_cat") == "coincide_media").sum()) if "match_cat" in sol.columns else 0
    solo = int((sol.get("match_cat") == "solo_1x10").sum()) if "match_cat" in sol.columns else 0
    dud = int((sol.get("match_cat") == "coincide_geo_solo").sum()) if "match_cat" in sol.columns else 0
    n_ubic = int(summary.get("ubicaciones_unicas", 0) or 0)
    n_multi = int(summary.get("ubicaciones_con_multiples_reportes", 0) or 0)

    render_kpi_strip(
        [
            {"label": "Registros", "value": fmt_num(n), "tone": "info"},
            {
                "label": "Mapeables",
                "value": fmt_num(n_map),
                "tone": "info",
                "hint": f"GPS OK: {fmt_num(n_ok)}",
            },
            {
                "label": "Ya atendidas",
                "value": fmt_num(alta + media),
                "tone": "success",
                "hint": f"Alta {fmt_num(alta)} · media {fmt_num(media)}",
            },
            {
                "label": "Pendientes",
                "value": fmt_num(solo),
                "tone": "warning",
                "hint": f"Por revisar: {fmt_num(dud)}",
            },
            {
                "label": "Ubicaciones",
                "value": fmt_num(n_ubic),
                "tone": "muted",
                "hint": f"Con varios reportes: {fmt_num(n_multi)}",
            },
        ]
    )

    c1, c2 = st.columns(2)
    with c1:
        if "match_cat" in sol.columns:
            order = [
                "solo_1x10",
                "coincide_alta",
                "coincide_media",
                "coincide_geo_solo",
                "no_mapeable",
            ]
            labels_map = {
                "solo_1x10": "Pendiente",
                "coincide_alta": "Atendida alta",
                "coincide_media": "Atendida media",
                "coincide_geo_solo": "Por revisar",
                "no_mapeable": "No mapeable",
            }
            vc = sol["match_cat"].value_counts()
            labs, vals, cols = [], [], []
            for k in order:
                if k in vc.index:
                    labs.append(labels_map[k])
                    vals.append(int(vc[k]))
                    cols.append(MATCH_COLORS.get(k, "#9CA3AF"))
            st_echarts(
                donut("Estatus frente a Habitable", labs, vals, cols),
                height="340px",
                key="info_x10_match",
            )
    with c2:
        tipo_col = "tipo_dir" if "tipo_dir" in sol.columns else None
        if tipo_col:
            from tipologia_direccion import TIPO_ETIQUETA, TIPO_LABELS

            order = [t for t in TIPO_LABELS if t in sol[tipo_col].values]
            vc = sol[tipo_col].value_counts()
            labs = [TIPO_ETIQUETA.get(k, k) for k in order]
            vals = [int(vc.get(k, 0)) for k in order]
            st_echarts(
                bar_vertical("Tipología en la dirección", labs, vals),
                height="340px",
                key="info_x10_tipo",
            )
            con_tipo = int((sol[tipo_col] != "sin_indicio").sum())
            con_uni = (
                int(sol["unidad_dir"].astype(str).str.len().gt(0).sum())
                if "unidad_dir" in sol.columns
                else 0
            )
            st.caption(
                f"Indicio léxico en **{fmt_num(con_tipo)}** direcciones "
                f"({100 * con_tipo / max(n, 1):.1f}%). "
                f"Unidad explícita (apto/casa/piso + nº): **{fmt_num(con_uni)}**. "
                "El representante del cúmulo prioriza la dirección más rica "
                "(tipología + unidad + detalle)."
            )
        elif "calidad_geo" in sol.columns:
            labs, vals = _top_counts(sol["calidad_geo"], 8)
            st_echarts(
                bar_vertical("Calidad GPS", labs, vals),
                height="340px",
                key="info_x10_geo",
            )

    st.markdown("#### Territorio")
    t1, t2 = st.columns(2)
    with t1:
        if "estado_n" in sol.columns:
            labs, vals = _top_counts(sol["estado_n"], 12)
            st_echarts(
                bar_horizontal("Por estado", labs, vals),
                height="380px",
                key="info_x10_est",
            )
    with t2:
        if "municipio_n" in sol.columns and "estado_n" in sol.columns:
            estados = sorted(sol["estado_n"].dropna().unique().tolist())
            default = [
                e
                for e in ["DISTRITO CAPITAL", "LA GUAIRA", "MIRANDA"]
                if e in estados
            ]
            sel = st.multiselect(
                "Estados para municipios",
                options=estados,
                default=default or estados[:3],
                key="info_x10_mun_est",
                help="Filtra municipios a unos pocos estados para leer mejor el gráfico.",
            )
            sub = sol[sol["estado_n"].isin(sel)] if sel else sol
            labs, vals = _top_counts(sub["municipio_n"], 12)
            st_echarts(
                bar_horizontal("Por municipio (filtro)", labs, vals),
                height="340px",
                key="info_x10_mun",
            )

    with st.expander("Completitud de campos clave", expanded=False):
        st.dataframe(
            _fill_rate(
                sol,
                [
                    "codigo_caso",
                    "direccion",
                    "descripcion",
                    "estado_n",
                    "municipio_n",
                    "parroquia_n",
                    "lat",
                    "lng",
                    "denunciante",
                    "telefono",
                    "cedula",
                ],
            ),
            use_container_width=True,
            hide_index=True,
        )


def page_info_habitable(hab: pd.DataFrame, summary: dict) -> None:
    """Panorama de la fuente Habitable."""
    render_section(
        "Fuente Habitable",
        "Inspecciones de campo: semáforo (4 etiquetas), territorio y tipología básica.",
    )
    _corte_caption(summary, "hab")

    n = len(hab)
    n_map = int(hab["mapeable"].sum()) if "mapeable" in hab.columns else 0
    n_alta = int(hab["alta_confianza"].sum()) if "alta_confianza" in hab.columns else 0
    n_verde = int((hab.get("etiqueta_n") == "VERDE").sum()) if "etiqueta_n" in hab.columns else 0
    n_ama = int((hab.get("etiqueta_n") == "AMARILLO").sum()) if "etiqueta_n" in hab.columns else 0
    n_rojo = int((hab.get("etiqueta_n") == "ROJO").sum()) if "etiqueta_n" in hab.columns else 0
    n_neg = int((hab.get("etiqueta_n") == "NEGRO").sum()) if "etiqueta_n" in hab.columns else 0

    render_kpi_strip(
        [
            {"label": "Inspecciones", "value": fmt_num(n), "tone": "info"},
            {
                "label": "Mapeables",
                "value": fmt_num(n_map),
                "tone": "info",
                "hint": f"Alta confianza: {fmt_num(n_alta)}",
            },
            {
                "label": "Verde",
                "value": fmt_num(n_verde),
                "tone": "success",
                "hint": f"{100 * n_verde / max(n, 1):.1f}%",
            },
            {
                "label": "Amarillo",
                "value": fmt_num(n_ama),
                "tone": "flag",
                "hint": f"{100 * n_ama / max(n, 1):.1f}%",
            },
            {
                "label": "Rojo + negro",
                "value": fmt_num(n_rojo + n_neg),
                "tone": "warning",
                "hint": f"Rojo {fmt_num(n_rojo)} · negro {fmt_num(n_neg)}",
            },
        ]
    )

    st.markdown("#### Semáforo (4 etiquetas)")
    s1, s2 = st.columns([1.1, 1])
    with s1:
        if "etiqueta_n" in hab.columns:
            order = ["VERDE", "AMARILLO", "ROJO", "NEGRO"]
            vc = hab["etiqueta_n"].value_counts()
            labs, vals, cols = [], [], []
            for k in order:
                if k in vc.index:
                    labs.append(k.title())
                    vals.append(int(vc[k]))
                    cols.append(ETIQUETA_COLORS.get(k, "#9CA3AF"))
            st_echarts(
                donut("Distribución por etiqueta", labs, vals, cols),
                height="360px",
                key="info_hab_etiq",
            )
    with s2:
        if "etiqueta_n" in hab.columns:
            order = ["VERDE", "AMARILLO", "ROJO", "NEGRO"]
            vc = hab["etiqueta_n"].value_counts()
            tab = pd.DataFrame(
                {
                    "Etiqueta": [k.title() for k in order if k in vc.index],
                    "Inspecciones": [int(vc[k]) for k in order if k in vc.index],
                    "%": [
                        round(100 * int(vc[k]) / max(n, 1), 1)
                        for k in order
                        if k in vc.index
                    ],
                }
            )
            st.dataframe(tab, use_container_width=True, hide_index=True)
        # Característica operativa: quién inspecciona (no repetir tipología abajo)
        col_ente = "ente" if "ente" in hab.columns else None
        if col_ente:
            labs, vals = _top_counts(hab[col_ente], 8)
            st_echarts(
                bar_vertical("Por organismo (ente)", labs, vals),
                height="260px",
                key="info_hab_ente",
            )

    st.markdown("#### Territorio")
    # Semáforo × estado (top estados)
    if "estado_n" in hab.columns and "etiqueta_n" in hab.columns:
        top_est = hab["estado_n"].value_counts().head(10).index.tolist()
        sub = hab[hab["estado_n"].isin(top_est)]
        g = (
            sub.groupby(["estado_n", "etiqueta_n"])
            .size()
            .unstack(fill_value=0)
        )
        for col in ["VERDE", "AMARILLO", "ROJO", "NEGRO"]:
            if col not in g.columns:
                g[col] = 0
        g = g[["VERDE", "AMARILLO", "ROJO", "NEGRO"]]
        g = g.loc[top_est]
        g.index = [_pretty_estado(x) for x in g.index]
        st.markdown("##### Semáforo por estado (top 10)")
        st.dataframe(g, use_container_width=True)

        labs = list(g.index)
        totals = g.sum(axis=1)
        st_echarts(
            bar_horizontal(
                "Inspecciones por estado",
                labs,
                totals.tolist(),
            ),
            height="360px",
            key="info_hab_est",
        )

    if "municipio_n" in hab.columns and "estado_n" in hab.columns:
        estados = sorted(hab["estado_n"].dropna().unique().tolist())
        default = [
            e
            for e in ["DISTRITO CAPITAL", "LA GUAIRA", "MIRANDA"]
            if e in estados
        ]
        sel = st.multiselect(
            "Estados para desglose municipal",
            options=estados,
            default=default or estados[:2],
            key="info_hab_mun_est",
            help="Elige pocos estados: hay muchos municipios a nivel nacional.",
        )
        sub = hab[hab["estado_n"].isin(sel)] if sel else hab
        n_mun = sub["municipio_n"].nunique()
        st.caption(f"Municipios en el filtro: **{fmt_num(n_mun)}** (se muestran hasta 15).")
        m1, m2 = st.columns(2)
        with m1:
            labs, vals = _top_counts(sub["municipio_n"], 15)
            st_echarts(
                bar_horizontal("Por municipio", labs, vals),
                height="400px",
                key="info_hab_mun",
            )
        with m2:
            if "etiqueta_n" in sub.columns:
                top_m = sub["municipio_n"].value_counts().head(10).index.tolist()
                g2 = (
                    sub[sub["municipio_n"].isin(top_m)]
                    .groupby(["municipio_n", "etiqueta_n"])
                    .size()
                    .unstack(fill_value=0)
                )
                for col in ["VERDE", "AMARILLO", "ROJO", "NEGRO"]:
                    if col not in g2.columns:
                        g2[col] = 0
                g2 = g2[["VERDE", "AMARILLO", "ROJO", "NEGRO"]].loc[top_m]
                g2.index = [str(x).title() for x in g2.index]
                st.markdown("##### Semáforo · top municipios")
                st.dataframe(g2, use_container_width=True)

    st.markdown("#### Tipología básica")
    t1, t2, t3 = st.columns(3)
    with t1:
        col = "uso_n" if "uso_n" in hab.columns else "uso"
        if col in hab.columns:
            labs, vals = _top_counts(hab[col], 8)
            st_echarts(
                bar_horizontal("Uso", labs, vals),
                height="320px",
                key="info_hab_uso",
            )
    with t2:
        col = "material_n" if "material_n" in hab.columns else "material"
        if col in hab.columns:
            labs, vals = _top_counts(hab[col], 8)
            st_echarts(
                bar_horizontal("Material", labs, vals),
                height="320px",
                key="info_hab_mat",
            )
    with t3:
        col = "num_pisos_n" if "num_pisos_n" in hab.columns else "num_pisos"
        if col in hab.columns:
            s = pd.to_numeric(hab[col], errors="coerce")
            bands = pd.cut(
                s,
                bins=[-0.1, 1, 3, 5, 10, 200],
                labels=["1", "2–3", "4–5", "6–10", "11+"],
            )
            labs, vals = _top_counts(bands.astype(str), 6)
            st_echarts(
                bar_vertical("Pisos", labs, vals),
                height="320px",
                key="info_hab_pisos",
            )

    with st.expander("Completitud de campos clave", expanded=False):
        st.dataframe(
            _fill_rate(
                hab,
                [
                    "id",
                    "nombre_edificacion",
                    "direccion",
                    "estado_n",
                    "municipio_n",
                    "etiqueta_n",
                    "uso",
                    "material",
                    "num_pisos",
                    "lat",
                    "lng",
                    "inspector_nombre",
                ],
            ),
            use_container_width=True,
            hide_index=True,
        )


# Compat: nombre anterior
def page_caracteristicas_fuentes(sol, hab, summary):
    page_info_1x10(sol, summary)
    st.divider()
    page_info_habitable(hab, summary)
