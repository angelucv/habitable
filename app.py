"""
BI Cruce Inspecciones — Habitable × 1×10
========================================

Punto de entrada de Streamlit.

Qué hace este archivo
---------------------
- Aplica el tema ejecutivo (colores, tipografía, pestañas).
- Opcionalmente exige contraseña (variable BI_PASSWORD o secrets).
- Permite cargar Excel 1×10 y Habitable y regenerar el cruce.
- Ofrece tres vistas: Mapa operativo · Análisis 1×10 · Análisis Habitable.

Ejecución local
---------------
    streamlit run app.py

Producción (Render)
-------------------
El Dockerfile arranca este mismo comando escuchando en $PORT.

Colaboradores: ver DOCUMENTACION.md en la raíz del repositorio.
"""

from __future__ import annotations

import gc
import json
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts

# Raíz del proyecto y carpeta de datos ya procesados (parquet)
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
DATA = ROOT / "data" / "processed"

from charts_echarts import bar_vertical  # noqa: E402
from data_ingest import render_upload_panel  # noqa: E402
from map_robust import render_map_ui  # noqa: E402
from pages_analysis import page_1x10, page_habitable  # noqa: E402
from runtime_limits import is_low_memory  # noqa: E402
from ui_theme import (  # noqa: E402
    inject_executive_css,
    render_hero,
    render_kpi_strip,
    render_section,
)

# Texto libre pesado: no hace falta en el BI en memoria
_DROP_HEAVY = {"observaciones"}


def check_password() -> bool:
    """
    Control de acceso simple para producción colaborativa.

    Orden de prioridad de la clave:
    1) Variable de entorno BI_PASSWORD (recomendada en Render)
    2) st.secrets["auth"]["password"] (archivo secrets.toml local)

    Si no hay clave configurada, el tablero queda abierto
    (útil en desarrollo local).
    """
    expected = os.environ.get("BI_PASSWORD", "").strip()
    if not expected:
        try:
            expected = str(st.secrets.get("auth", {}).get("password", "")).strip()
        except Exception:
            expected = ""

    if not expected:
        return True  # Sin clave → modo abierto (solo desarrollo)

    if st.session_state.get("bi_auth_ok"):
        return True

    st.markdown("### Acceso al tablero")
    st.caption("BI Cruce Habitable × 1×10 — uso restringido al equipo autorizado.")
    pwd = st.text_input("Contraseña", type="password", key="bi_pwd_input")
    if st.button("Entrar", type="primary"):
        if pwd == expected:
            st.session_state["bi_auth_ok"] = True
            st.rerun()
        st.error("Contraseña incorrecta.")
    return False


@st.cache_data(show_spinner="Cargando datos procesados…")
def load_data():
    """Lee parquet + summary generados por prepare_data / carga UI."""
    sol_path = DATA / "solicitudes.parquet"
    hab_path = DATA / "inspecciones.parquet"
    if is_low_memory():
        try:
            import pyarrow.parquet as pq

            def _read(path: Path) -> pd.DataFrame:
                names = [n for n in pq.read_schema(path).names if n not in _DROP_HEAVY]
                return pd.read_parquet(path, columns=names)

            sol = _read(sol_path)
            hab = _read(hab_path)
        except Exception:  # noqa: BLE001
            sol = pd.read_parquet(sol_path)
            hab = pd.read_parquet(hab_path)
    else:
        sol = pd.read_parquet(sol_path)
        hab = pd.read_parquet(hab_path)
    summary = json.loads((DATA / "summary.json").read_text(encoding="utf-8"))
    return sol, hab, summary


def ensure_data_ready() -> bool:
    """True si ya existe un cruce procesado listo para pintar el BI."""
    needed = [
        DATA / "solicitudes.parquet",
        DATA / "inspecciones.parquet",
        DATA / "summary.json",
    ]
    return all(p.exists() for p in needed)


def filter_estado(df: pd.DataFrame, estados: list[str], col: str = "estado_n"):
    """Filtra por lista de estados; lista vacía = sin filtro (nacional)."""
    if not estados:
        return df
    return df[df[col].isin(estados)]


def fmt_num(n: float | int) -> str:
    """Formato numérico es-VE (punto de miles)."""
    return f"{int(n):,}".replace(",", ".")


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
        ],
        state_key="vista",
        heading="Pestañas del tablero",
    )

def main():
    """Orquesta autenticación, carga de datos y las tres vistas del BI."""
    st.set_page_config(
        page_title="BI Cruce Inspecciones",
        page_icon="▣",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_executive_css()

    # Puerta de acceso (producción). En local sin BI_PASSWORD no pide clave.
    if not check_password():
        st.stop()

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

    if is_low_memory():
        st.caption(
            "Servicio en modo bajo consumo de memoria · mapa con tope de marcadores."
        )

    # Carga de Excel y regeneración del matching (actualiza las 3 pestañas)
    with st.expander("Cargar / actualizar archivos fuente", expanded=not ensure_data_ready()):
        render_upload_panel()

    if not ensure_data_ready():
        st.stop()

    sol, hab, summary = load_data()
    gc.collect()

    with st.sidebar:
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

    # Navegación principal (Mapa / 1×10 / Habitable)
    vista = render_main_tabs()
    if vista == "mapa":
        page_mapa(sol, hab, summary)
    elif vista == "x10":
        page_1x10(sol, summary)
    else:
        page_habitable(hab, summary)


if __name__ == "__main__":
    main()
