"""
BI local F0 — Cruce 1×10 × Habitable
Ejecutar: streamlit run app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
DATA = ROOT / "data" / "processed"

from charts_echarts import bar_vertical  # noqa: E402
from data_ingest import render_upload_panel  # noqa: E402
from map_robust import render_map_ui  # noqa: E402
from pages_analysis import (  # noqa: E402
    page_1x10,
    page_habitable,
    page_reportes_inspecciones,
)
from ui_theme import (  # noqa: E402
    inject_executive_css,
    render_hero,
    render_kpi_strip,
    render_section,
)


@st.cache_data(show_spinner="Cargando datos procesados…")
def load_data():
    sol = pd.read_parquet(DATA / "solicitudes.parquet")
    hab = pd.read_parquet(DATA / "inspecciones.parquet")
    summary = json.loads((DATA / "summary.json").read_text(encoding="utf-8"))
    return sol, hab, summary


def ensure_data_ready() -> bool:
    needed = [
        DATA / "solicitudes.parquet",
        DATA / "inspecciones.parquet",
        DATA / "summary.json",
    ]
    return all(p.exists() for p in needed)


def filter_estado(df: pd.DataFrame, estados: list[str], col: str = "estado_n"):
    if not estados:
        return df
    return df[df[col].isin(estados)]


def fmt_num(n: float | int) -> str:
    return f"{int(n):,}".replace(",", ".")


def _label_corte(summary: dict) -> dict:
    """Etiquetas legibles del corte de datos (sidebar)."""
    from pathlib import Path

    gen = summary.get("corte_generado_en") or "—"
    a1 = summary.get("corte_1x10_archivo") or Path(
        str(summary.get("source_1x10") or "")
    ).name
    a2 = summary.get("corte_habitable_archivo") or Path(
        str(summary.get("source_habitable") or "")
    ).name
    n1 = summary.get("corte_1x10_n", summary.get("n_1x10", 0))
    n2 = summary.get("corte_habitable_n", summary.get("n_hab", 0))
    return {
        "generado": gen,
        "archivo_1x10": a1 or "(sin dato)",
        "archivo_hab": a2 or "(sin dato)",
        "n_1x10": fmt_num(n1 or 0),
        "n_hab": fmt_num(n2 or 0),
        "etiq_1x10": summary.get("corte_1x10_etiqueta") or "17/07/2026",
        "etiq_hab": summary.get("corte_habitable_etiqueta") or "",
        "nota": summary.get("corte_nota")
        or (
            "Habitable actualizado al corte descargado el 21/07/2026 a las 10:00. "
            "La información de 1×10 corresponde al corte del 17/07/2026 (semana previa)."
        ),
    }


def page_mapa(sol: pd.DataFrame, hab: pd.DataFrame, summary: dict):
    render_section(
        "Mapa operativo",
        "Cruce espacial de solicitudes 1×10 con inspecciones Habitable. "
        f"Radio {summary.get('radius_m', 50)} m · unificación {summary.get('dedupe_radius_m', 20)} m.",
    )

    estados_sol = sorted(sol["estado_n"].dropna().unique().tolist())
    f1, f2 = st.columns([3, 2])
    with f1:
        estados = st.multiselect(
            "Territorio (vacío = nacional)",
            options=estados_sol,
            default=[],
            help="Vacío = país completo. Acota a Caracas / La Guaira / Miranda para enfocarte.",
        )
    with f2:
        with st.expander("Filtros avanzados", expanded=False):
            hide_bad = st.checkbox(
                "Ocultar GPS dudosos (mar / fuera de estado)",
                value=False,
                help="Limpia puntos en el Caribe. Reduce el volumen mostrado.",
            )
            show_all_reports = st.checkbox(
                "Sin unificar ubicaciones (todos los reportes)",
                value=False,
                help=f"Por defecto se unifica a {summary.get('dedupe_radius_m', 20)} m.",
            )

    sol_f = filter_estado(sol, estados) if estados else sol
    hab_f = filter_estado(hab, estados) if estados else hab

    sol_geo = sol_f[sol_f["mapeable"]]
    n_ocultos = 0
    if hide_bad and "mapa_ok" in sol_geo.columns:
        n_ocultos = int((~sol_geo["mapa_ok"]).sum())
        sol_geo = sol_geo[sol_geo["mapa_ok"]]

    n_brutos = len(sol_geo)
    if not show_all_reports and "es_representante" in sol_geo.columns:
        sol_geo = sol_geo[sol_geo["es_representante"]]
        n_multi = (
            int((sol_geo["n_reportes"] >= 2).sum())
            if "n_reportes" in sol_geo.columns
            else 0
        )
    else:
        n_multi = 0

    if "alta_confianza" in hab_f.columns:
        hab_geo = hab_f[hab_f["alta_confianza"]]
    else:
        hab_geo = hab_f[hab_f["mapeable"]] if "mapeable" in hab_f.columns else hab_f

    sol_map = sol_geo
    hab_map = hab_geo
    coin = sol_map[sol_map["match_cat"].isin(["coincide_alta", "coincide_media"])]
    solo = sol_map[sol_map["match_cat"] == "solo_1x10"]
    dud = sol_map[sol_map["match_cat"] == "coincide_geo_solo"]

    render_kpi_strip(
        [
            {"label": "Solicitudes 1×10", "value": fmt_num(len(sol_map)), "tone": "info"},
            {
                "label": "Inspecciones",
                "value": fmt_num(len(hab_map)),
                "tone": "success",
            },
            {
                "label": "Ya atendidas",
                "value": fmt_num(len(coin)),
                "tone": "info",
                "hint": "Coincidencia alta + media",
            },
            {
                "label": "Pendientes",
                "value": fmt_num(len(solo)),
                "tone": "warning",
            },
            {"label": "Por revisar", "value": fmt_num(len(dud)), "tone": "muted"},
        ]
    )
    st.caption(
        f"Universo mostrado: {fmt_num(len(sol_map))} ubicaciones "
        f"(de {fmt_num(n_brutos)} reportes"
        + (f"; sitios con varios reportes: {fmt_num(n_multi)}" if n_multi else "")
        + ")."
        + (f" GPS dudosos ocultos: {fmt_num(n_ocultos)}." if n_ocultos else "")
    )

    render_map_ui(sol_map, hab_map, coin, solo, dud)

    render_section("Embudo del cruce", "Volumen según el filtro territorial actual.")
    funnel_cats = [
        "Solicitudes",
        "En mapa",
        "Ya atendidas",
        "Pendientes",
        "Por revisar",
    ]
    funnel_vals = [
        int(len(sol_f)),
        int(len(sol_map)),
        int(len(coin)),
        int(len(solo)),
        int(len(dud)),
    ]
    st_echarts(
        bar_vertical("Casos", funnel_cats, funnel_vals),
        height="280px",
        key="map_funnel",
    )

    render_section("Cruce por estado", "Desglose de solicitudes 1×10 visibles en el mapa.")
    if "estado_n" in sol_map.columns and "match_cat" in sol_map.columns:
        g = (
            sol_map.groupby("estado_n")["match_cat"]
            .value_counts()
            .unstack(fill_value=0)
        )
        for col in [
            "solo_1x10",
            "coincide_alta",
            "coincide_media",
            "coincide_geo_solo",
        ]:
            if col not in g.columns:
                g[col] = 0
        g = g[
            ["solo_1x10", "coincide_alta", "coincide_media", "coincide_geo_solo"]
        ]
        g = g.sort_values("solo_1x10", ascending=False).head(12)
        g = g.rename(
            columns={
                "solo_1x10": "Pendientes",
                "coincide_alta": "Alta",
                "coincide_media": "Media",
                "coincide_geo_solo": "Por revisar",
            }
        )
        g.index.name = "Estado"
        st.dataframe(g, use_container_width=True)

    with st.expander("Calidad geográfica 1×10"):
        if "calidad_geo" in sol_f.columns:
            vc = sol_f["calidad_geo"].value_counts()
            st_echarts(
                bar_vertical("Calidad geo", vc.index.tolist(), vc.values.tolist()),
                height="320px",
                key="map_calidad",
            )

    with st.expander("Muestra de coincidencias altas"):
        cols = [
            c
            for c in [
                "codigo_caso",
                "direccion",
                "hab_nombre",
                "match_dist_m",
                "match_score",
                "hab_etiqueta",
                "estado_n",
            ]
            if c in coin.columns
        ]
        alta = coin[coin["match_cat"] == "coincide_alta"][cols].head(30)
        st.dataframe(alta, use_container_width=True)


def render_main_tabs() -> str:
    """Pestañas principales del tablero."""
    from ui_theme import render_section_tabs

    return render_section_tabs(
        [
            ("mapa", "Mapa operativo"),
            ("x10", "Análisis 1×10"),
            ("hab", "Análisis Habitable"),
            ("reportes", "1×10 pendientes"),
        ],
        state_key="vista",
        heading="Pestañas del tablero",
    )

def main():
    st.set_page_config(
        page_title="BI Cruce Inspecciones",
        page_icon="▣",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_executive_css()

    if not ensure_data_ready():
        st.warning(
            "Aún no hay datos procesados. Carga los Excel abajo y pulsa "
            "**Procesar cruce**."
        )

    render_hero(
        "Cruce de inspecciones",
        "Tablero ejecutivo: demanda ciudadana (1×10) frente a inspecciones "
        "de campo (Habitable). Identifica lo ya atendido y lo pendiente.",
        kicker="Comisión Presidencial · Evaluación de Habitabilidad",
    )

    with st.expander("Cargar / actualizar archivos fuente", expanded=not ensure_data_ready()):
        render_upload_panel()

    if not ensure_data_ready():
        st.stop()

    sol, hab, summary = load_data()

    with st.sidebar:
        corte = _label_corte(summary)
        st.markdown("### Corte de información")
        st.markdown(
            f"""
            <div style="background:rgba(252,209,22,0.12);border:1px solid rgba(252,209,22,0.45);border-radius:8px;padding:0.75rem 0.85rem;margin:0.35rem 0 0.9rem 0;">
              <div style="color:#FCD116;font-size:0.68rem;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;margin-bottom:0.45rem;">Fuentes en uso</div>
              <div style="color:#E2E8F0;font-size:0.72rem;margin-bottom:0.55rem;">
                <div style="color:#94A3B8;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.04em;">1×10</div>
                <div style="color:#FFFFFF;font-weight:600;">Corte {corte['etiq_1x10']}</div>
                <div style="color:#CBD5E1;">{corte['n_1x10']} registros</div>
                <div style="color:#94A3B8;font-size:0.62rem;word-break:break-word;">{corte['archivo_1x10']}</div>
              </div>
              <div style="color:#E2E8F0;font-size:0.72rem;margin-bottom:0.55rem;">
                <div style="color:#94A3B8;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.04em;">Habitable</div>
                <div style="color:#FFFFFF;font-weight:600;">Corte {corte['etiq_hab'] or '—'}</div>
                <div style="color:#CBD5E1;">{corte['n_hab']} inspecciones</div>
                <div style="color:#94A3B8;font-size:0.62rem;word-break:break-word;">{corte['archivo_hab']}</div>
              </div>
              <div style="color:#F8FAFC;font-size:0.7rem;line-height:1.45;border-top:1px solid rgba(255,255,255,0.15);padding-top:0.5rem;margin-bottom:0.45rem;">
                {corte['nota']}
              </div>
              <div style="color:#94A3B8;font-size:0.68rem;">
                Cruce generado: <span style="color:#F8FAFC;font-weight:600;">{corte['generado']}</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            "Habitable se actualiza con cada descarga nueva; 1×10 permanece en el corte indicado hasta nueva carga."
        )
        st.divider()
        st.markdown("### Panorama nacional")
        st.markdown(
            f"""
            <div style="display:flex;flex-direction:column;gap:0.55rem;margin:0.4rem 0 0.8rem 0;">
              <div style="background:rgba(255,255,255,0.10);border:1px solid rgba(255,255,255,0.22);border-top:3px solid #FCD116;border-radius:8px;padding:0.7rem 0.85rem;">
                <div style="color:#E2E8F0;font-size:0.7rem;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;">Solicitudes 1×10</div>
                <div style="color:#FFFFFF;font-family:Source Serif 4,Georgia,serif;font-size:1.45rem;font-weight:700;">{fmt_num(summary.get("n_1x10", 0))}</div>
              </div>
              <div style="background:rgba(255,255,255,0.10);border:1px solid rgba(255,255,255,0.22);border-top:3px solid #FCD116;border-radius:8px;padding:0.7rem 0.85rem;">
                <div style="color:#E2E8F0;font-size:0.7rem;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;">Inspecciones Habitable</div>
                <div style="color:#FFFFFF;font-family:Source Serif 4,Georgia,serif;font-size:1.45rem;font-weight:700;">{fmt_num(summary.get("n_hab", 0))}</div>
              </div>
              <div style="background:rgba(255,255,255,0.10);border:1px solid rgba(255,255,255,0.22);border-top:3px solid #FCD116;border-radius:8px;padding:0.7rem 0.85rem;">
                <div style="color:#E2E8F0;font-size:0.7rem;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;">Ya atendidas</div>
                <div style="color:#FFFFFF;font-family:Source Serif 4,Georgia,serif;font-size:1.45rem;font-weight:700;">{fmt_num(summary.get("coincide_auto", 0))}</div>
              </div>
              <div style="background:rgba(255,255,255,0.10);border:1px solid rgba(255,255,255,0.22);border-top:3px solid #FCD116;border-radius:8px;padding:0.7rem 0.85rem;">
                <div style="color:#E2E8F0;font-size:0.7rem;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;">Pendientes</div>
                <div style="color:#FFFFFF;font-family:Source Serif 4,Georgia,serif;font-size:1.45rem;font-weight:700;">{fmt_num(summary.get("solo_1x10", 0))}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            f"Matching a {summary.get('radius_m')} m · "
            f"Unificación {summary.get('dedupe_radius_m', 20)} m"
        )
        st.divider()
        if summary.get("ubicaciones_unicas"):
            st.markdown("**Ubicaciones 1×10**")
            st.write(fmt_num(summary.get("ubicaciones_unicas", 0)))
            st.caption(
                f"Sitios con varios reportes: "
                f"{fmt_num(summary.get('ubicaciones_con_multiples_reportes', 0))}"
            )
        st.divider()
        if st.button("Recargar datos", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.markdown(
            """
            <div style="margin-top:1.25rem;padding-top:0.85rem;border-top:1px solid rgba(255,255,255,0.2);">
              <div style="color:#94A3B8;font-size:0.68rem;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;margin-bottom:0.25rem;">Elaborado por</div>
              <a href="mailto:angelc.cvea@gmail.com"
                 style="color:#F8FAFC;font-size:0.82rem;font-weight:600;text-decoration:none;word-break:break-all;">
                angelc.cvea@gmail.com
              </a>
            </div>
            """,
            unsafe_allow_html=True,
        )

    vista = render_main_tabs()
    if vista == "mapa":
        page_mapa(sol, hab, summary)
    elif vista == "x10":
        page_1x10(sol, summary)
    elif vista == "reportes":
        page_reportes_inspecciones(sol, summary)
    else:
        page_habitable(hab, summary)


if __name__ == "__main__":
    main()
