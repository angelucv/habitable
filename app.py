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

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
DATA = ROOT / "data" / "processed"

from data_ingest import render_upload_panel  # noqa: E402
from map_robust import render_map_ui  # noqa: E402
from pages_abordaje import page_abordaje  # noqa: E402
from pages_nasa import page_nasa  # noqa: E402
from pages_analysis import (  # noqa: E402
    page_1x10,
    page_habitable,
    page_reportes_inspecciones,
)
from pages_caracteristicas import page_info_1x10, page_info_habitable  # noqa: E402
from ui_theme import (  # noqa: E402
    inject_executive_css,
    render_hero,
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
    }


def page_mapa(sol: pd.DataFrame, hab: pd.DataFrame, summary: dict, sub: str = "mapa_vista"):
    """Mapa operativo: vista de mapa (las características van en otra pestaña)."""
    st.caption(
        f"Cruce 1×10 × Habitable · radio {summary.get('radius_m', 50)} m · "
        f"unificación {summary.get('dedupe_radius_m', 10)} m "
        f"(estricto + dirección)"
    )

    estados_sol = sorted(sol["estado_n"].dropna().unique().tolist())
    f1, f2, f3 = st.columns([2.4, 1.2, 1.2])
    with f1:
        estados = st.multiselect(
            "Territorio",
            options=estados_sol,
            default=[],
            key="map_op_est",
            help="Vacío = nacional.",
        )
    with f2:
        hide_bad = st.checkbox(
            "Ocultar GPS dudosos",
            value=True,
            key="map_op_hide_bad",
            help="Oculta mar / fuera de estado.",
        )
    with f3:
        show_all_reports = st.checkbox(
            "Sin unificar",
            value=False,
            key="map_op_all",
            help="Todos los reportes (no solo ubicación).",
        )

    sol_f = filter_estado(sol, estados) if estados else sol
    hab_f = filter_estado(hab, estados) if estados else hab

    sol_geo = sol_f[sol_f["mapeable"]]
    n_ocultos = 0
    if hide_bad and "mapa_ok" in sol_geo.columns:
        n_ocultos = int((~sol_geo["mapa_ok"]).sum())
        sol_geo = sol_geo[sol_geo["mapa_ok"]]

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

    st.caption(
        f"**{fmt_num(len(sol_map))}** ubic. · **{fmt_num(len(hab_map))}** insp. · "
        f"**{fmt_num(len(coin))}** atendidas · **{fmt_num(len(solo))}** pendientes · "
        f"**{fmt_num(len(dud))}** por revisar"
        + (f" · multi {fmt_num(n_multi)}" if n_multi else "")
        + (f" · GPS ocultos {fmt_num(n_ocultos)}" if n_ocultos else "")
    )

    render_map_ui(sol_map, hab_map, coin, solo, dud)

def main():
    st.set_page_config(
        page_title="BI Cruce Inspecciones",
        page_icon="▣",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_executive_css()

    from nav_schema import HOME_ID, find_section, resolve_nav
    from ui_theme import (
        render_back_to_index,
        render_home_index,
        render_section,
        render_section_subtabs,
        render_sidebar_nav,
    )

    if "nav_item" not in st.session_state:
        st.session_state["nav_item"] = HOME_ID

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
        active = render_sidebar_nav(st.session_state["nav_item"])
        st.session_state["nav_item"] = active
        st.divider()
        corte = _label_corte(summary)
        st.markdown("### Corte de información")
        st.markdown(
            f"""
            <div style="background:rgba(252,209,22,0.12);border:1px solid rgba(252,209,22,0.45);border-radius:8px;padding:0.75rem 0.85rem;margin:0.35rem 0 0.9rem 0;">
              <div style="color:#FCD116;font-size:0.68rem;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;margin-bottom:0.45rem;">Fuentes en uso</div>
              <div style="color:#E2E8F0;font-size:0.72rem;margin-bottom:0.55rem;">
                <div style="color:#94A3B8;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.04em;">1×10</div>
                <div style="color:#FFFFFF;font-weight:600;word-break:break-word;">{corte['archivo_1x10']}</div>
                <div style="color:#CBD5E1;">{corte['n_1x10']} registros</div>
              </div>
              <div style="color:#E2E8F0;font-size:0.72rem;margin-bottom:0.55rem;">
                <div style="color:#94A3B8;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.04em;">Habitable</div>
                <div style="color:#FFFFFF;font-weight:600;word-break:break-word;">{corte['archivo_hab']}</div>
                <div style="color:#CBD5E1;">{corte['n_hab']} inspecciones</div>
              </div>
              <div style="color:#94A3B8;font-size:0.68rem;border-top:1px solid rgba(255,255,255,0.15);padding-top:0.45rem;">
                Cruce generado: <span style="color:#F8FAFC;font-weight:600;">{corte['generado']}</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            "Al subir archivos nuevos y procesar el cruce, este bloque se actualiza."
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
            f"Unificación {summary.get('dedupe_radius_m', 10)} m "
            f"+ dir≥{summary.get('dedupe_addr_min', 75)}"
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

    nav_item = st.session_state.get("nav_item", HOME_ID)
    sec_id, item_id = resolve_nav(nav_item)
    if sec_id == HOME_ID:
        render_home_index(summary, hab)
        return

    sec = find_section(sec_id)
    if not sec:
        render_home_index(summary, hab)
        return

    render_back_to_index()
    render_section(sec.label, sec.blurb)
    item_id = render_section_subtabs(sec)
    st.session_state["nav_item"] = item_id

    if sec_id == "fuentes":
        if item_id == "fuentes_hab":
            page_info_habitable(hab, summary)
        else:
            page_info_1x10(sol, summary)
    elif sec_id == "mapa":
        page_mapa(sol, hab, summary, sub=item_id)
    elif sec_id == "abordaje":
        page_abordaje(sol, hab, summary, sub=item_id)
    elif sec_id == "nasa":
        page_nasa(sol, hab, summary, sub=item_id)
    elif sec_id == "x10":
        page_1x10(sol, summary, sub=item_id)
    elif sec_id == "pend":
        page_reportes_inspecciones(sol, summary, sub=item_id)
    else:
        page_habitable(hab, summary, sub=item_id)


if __name__ == "__main__":
    main()
