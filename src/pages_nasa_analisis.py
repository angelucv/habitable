"""Análisis por fuente × NASA: 1×10 (cola), Habitable (confiabilidad), IA (validación)."""

from __future__ import annotations

import html as html_lib
from io import BytesIO
from pathlib import Path
from typing import Any

import folium
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from folium.plugins import HeatMap

ROOT = Path(__file__).resolve().parents[1]
NASA_DIR = ROOT / "data" / "external_nasa"
CRUCE_1X10 = NASA_DIR / "cruce_1x10_nasa" / "cruce_1x10_nasa_detallado.parquet"
CRUCE_HAB = NASA_DIR / "cruce_habitable_nasa" / "cruce_habitable_nasa_detallado.parquet"
CRUCE_IA = NASA_DIR / "cruce_ia_nasa" / "cruce_ia_nasa_detallado.parquet"

VIEWS = {
    "Caracas / La Guaira": (10.55, -66.92, 11),
    "La Guaira costa": (10.60, -66.93, 12),
    "Gran Caracas": (10.48, -66.90, 10),
}

BASEMAPS: dict[str, tuple[str, str, str]] = {
    "OSM claro (Carto)": ("CartoDB positron", "© OpenStreetMap © CARTO", "OSM claro"),
    "Satélite (Esri)": (
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "Tiles © Esri",
        "Satélite Esri",
    ),
}

RADII = (30, 50, 100)


def _fmt(n: int | float) -> str:
    if isinstance(n, float):
        return f"{n:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{int(n):,}".replace(",", ".")


def _tile(key: str, show: bool = True) -> folium.TileLayer:
    tiles, attr, name = BASEMAPS[key]
    if tiles.startswith("http"):
        return folium.TileLayer(
            tiles=tiles, attr=attr, name=name, show=show, overlay=False, control=True
        )
    return folium.TileLayer(tiles=tiles, name=name, show=show, overlay=False, control=True)


def _popup(title: str, fields: dict[str, Any]) -> str:
    parts = [f"<b>{html_lib.escape(str(title))}</b>"]
    for lab, val in fields.items():
        if val is None or (isinstance(val, float) and pd.isna(val)):
            continue
        s = str(val).strip()
        if s in ("", "nan", "None"):
            continue
        parts.append(f"<b>{html_lib.escape(str(lab))}</b>: {html_lib.escape(s)}")
    return "<br/>".join(parts)


@st.cache_data(show_spinner=False)
def _load(path_str: str) -> pd.DataFrame:
    p = Path(path_str)
    if not p.exists():
        return pd.DataFrame()
    return pd.read_parquet(p)


def _near(df: pd.DataFrame, radio: float) -> pd.DataFrame:
    if df.empty or "nasa_dist_m" not in df.columns:
        return df.iloc[0:0]
    return df[df["nasa_dist_m"] <= float(radio)]


def _pct(num: int, den: int) -> float:
    return round(100.0 * num / den, 1) if den else 0.0


def _heat_map_html(
    *,
    layers: list[tuple[str, pd.DataFrame, str, bool]],
    points: list[tuple[str, pd.DataFrame, str, bool, Any]] | None = None,
    basemap: str,
    view: str,
    height_note: str = "",
) -> str:
    """layers: (name, df, gradient_unused, show) — HeatMap.
    points: (name, df, color, show, popup_builder)
    """
    lat, lng, zoom = VIEWS[view]
    m = folium.Map(
        location=[lat, lng],
        zoom_start=zoom,
        tiles=None,
        control_scale=True,
        prefer_canvas=True,
    )
    m.add_child(_tile(basemap, show=True))
    for k in BASEMAPS:
        if k != basemap:
            m.add_child(_tile(k, show=False))

    for name, df, _grad, show in layers:
        data = df.dropna(subset=["lat", "lng"]) if not df.empty else df
        if data is None or data.empty:
            continue
        fg = folium.FeatureGroup(name=name, show=show)
        pts = [[float(r.lat), float(r.lng)] for r in data.itertuples(index=False)]
        HeatMap(pts, radius=14, blur=18, max_zoom=16, min_opacity=0.35).add_to(fg)
        fg.add_to(m)

    if points:
        for name, df, color, show, pop_fn in points:
            data = df.dropna(subset=["lat", "lng"]) if not df.empty else df
            if data is None or data.empty:
                continue
            fg = folium.FeatureGroup(
                name=f"{name} · {_fmt(len(data))}", show=show
            )
            for r in data.itertuples(index=False):
                folium.CircleMarker(
                    location=[float(r.lat), float(r.lng)],
                    radius=1.5,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.75,
                    weight=1,
                    popup=folium.Popup(pop_fn(r), max_width=360),
                ).add_to(fg)
            fg.add_to(m)

    folium.LayerControl(collapsed=True, position="topright").add_to(m)
    _ = height_note
    return m.get_root().render()


def _intro_cruceros_clave() -> None:
    st.info(
        "**Cruces más importantes (orden operativo):**\n\n"
        "1. **Habitable ROJO/NEGRO × NASA `likely_damaged`** — ancla de verdad de campo; "
        "sirve para calibrar zonas de calor confiables.\n"
        "2. **1×10 pendientes × NASA `likely_damaged`** — cola de próximos casos a abordar.\n"
        "3. **IA alerta × NASA `likely_damaged`** — acuerdo de dos modelados (óptico + radar).\n"
        "4. **Desacuerdos** — NASA dice daño y Habitable VERDE (posible sobre-alerta radar); "
        "o Habitable crítico y NASA `not_damaged` (revisar / fuera de sensibilidad SAR)."
    )


# ─── 1×10 ───────────────────────────────────────────────────────────────────


def page_nasa_1x10(summary: dict | None = None) -> None:
    st.caption(
        "Orientar siguientes casos: pendientes 1×10 con señal NASA de daño probable."
    )
    if summary:
        st.caption(f"Corte BI · 1×10 {summary.get('n_1x10', '—')}")
    _intro_cruceros_clave()

    df = _load(str(CRUCE_1X10))
    if df.empty:
        st.error("Falta cruce 1×10 × NASA.")
        return

    pend = df[df["match_cat"] == "solo_1x10"] if "match_cat" in df.columns else df
    radio = st.select_slider("Radio NASA (m)", options=list(RADII), value=50, key="n1_radio")
    near = _near(pend, radio)
    alta = near[near["nasa_label"] == "likely_damaged"] if not near.empty else near
    media = near[near["nasa_label"] == "not_damaged"] if not near.empty else near
    sin = pend[pend["nasa_dist_m"] > 100] if not pend.empty else pend

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pendientes 1×10", _fmt(len(pend)))
    c2.metric(
        f"Coinc. ≤{radio} m",
        f"{_pct(len(near), len(pend)):.1f}%",
        delta=f"{_fmt(len(near))} loc.",
        delta_color="off",
    )
    c3.metric(
        "Prioridad alta (likely)",
        _fmt(len(alta)),
        delta=f"{_pct(len(alta), len(pend)):.1f}% de pendientes",
        delta_color="off",
    )
    c4.metric("Sin radar >100 m", _fmt(len(sin)))

    st.markdown("##### Cola prioritaria (likely_damaged ≤ radio)")
    st.caption(
        "Estas localidades concentran demanda ciudadana sin inspección Habitable "
        "y con señal radar de daño probable → candidatos a despachar."
    )

    basemap = st.selectbox("Mapa base", list(BASEMAPS.keys()), key="n1_bm")
    view = st.selectbox("Vista", list(VIEWS.keys()), key="n1_view")
    show_pts = st.checkbox("Mostrar puntos de cola (además del calor)", value=True, key="n1_pts")

    def _pop(r):
        return _popup(
            "1×10 pendiente × NASA",
            {
                "Caso": getattr(r, "codigo_caso", ""),
                "NASA": getattr(r, "nasa_label", ""),
                "Dist. m": round(float(getattr(r, "nasa_dist_m", 0) or 0), 1),
                "Estado": getattr(r, "estado_n", ""),
                "Municipio": getattr(r, "municipio_n", ""),
                "Dirección": getattr(r, "direccion", ""),
            },
        )

    html = _heat_map_html(
        layers=[
            (
                f"Calor cola alta · {_fmt(len(alta))}",
                alta,
                "",
                True,
            ),
            (
                f"Calor coinc. not_damaged · {_fmt(len(media))}",
                media,
                "",
                False,
            ),
        ],
        points=[
            ("Cola likely", alta, "#DC2626", True, _pop),
        ]
        if show_pts
        else None,
        basemap=basemap,
        view=view,
    )
    components.html(html, height=560, scrolling=False)

    # Territorio
    if not alta.empty and "municipio_n" in alta.columns:
        st.markdown("##### Territorio — cola alta")
        g = (
            alta.groupby(["estado_n", "municipio_n"], dropna=False)
            .size()
            .reset_index(name="n")
            .sort_values("n", ascending=False)
            .head(20)
        )
        st.dataframe(g, use_container_width=True, hide_index=True)

    cols_show = [
        c
        for c in [
            "codigo_caso",
            "estado_n",
            "municipio_n",
            "direccion",
            "nasa_label",
            "nasa_dist_m",
            "nasa_damage_probability",
            "n_reportes",
        ]
        if c in alta.columns
    ]
    st.markdown("##### Listado cola (descargable)")
    st.dataframe(
        alta[cols_show].sort_values("nasa_dist_m").head(500),
        use_container_width=True,
        hide_index=True,
    )
    buf = BytesIO()
    alta.to_csv(buf, index=False)
    st.download_button(
        "Descargar cola alta CSV",
        data=buf.getvalue(),
        file_name="cola_1x10_nasa_likely.csv",
        mime="text/csv",
        key="n1_dl",
    )


# ─── Habitable ───────────────────────────────────────────────────────────────


def page_nasa_habitable(summary: dict | None = None) -> None:
    st.caption(
        "Confiabilidad NASA según inspecciones: ¿dónde el radar coincide con el semáforo de campo?"
    )
    if summary:
        st.caption(f"Corte BI · Habitable {summary.get('n_hab', '—')}")
    _intro_cruceros_clave()

    df = _load(str(CRUCE_HAB))
    if df.empty:
        st.error("Falta cruce Habitable × NASA.")
        return

    radio = st.select_slider("Radio NASA (m)", options=list(RADII), value=50, key="nh_radio")
    near = _near(df, radio)

    # Matriz etiqueta × nasa_label
    if near.empty:
        st.warning("Sin puntos dentro del radio.")
        return

    ct = pd.crosstab(near["etiqueta_n"], near["nasa_label"], margins=True)
    st.markdown("##### Matriz semáforo Habitable × label NASA")
    st.dataframe(ct, use_container_width=True)

    crit = near[near["etiqueta_n"].isin(["ROJO", "NEGRO"])]
    verde = near[near["etiqueta_n"] == "VERDE"]
    conf_pos = crit[crit["nasa_label"] == "likely_damaged"]  # campo malo + radar malo
    sobre = verde[verde["nasa_label"] == "likely_damaged"]  # radar alerta, campo OK
    sub = crit[crit["nasa_label"] == "not_damaged"]  # campo malo, radar no

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Insp. ≤ radio", _fmt(len(near)), delta=f"{_pct(len(near), len(df)):.1f}% del total")
    c2.metric(
        "Zona calor confirmada",
        _fmt(len(conf_pos)),
        delta=f"{_pct(len(conf_pos), len(crit)):.1f}% de ROJO/NEGRO",
        delta_color="off",
    )
    c3.metric(
        "Posible sobre-alerta NASA",
        _fmt(len(sobre)),
        delta=f"{_pct(len(sobre), len(verde)):.1f}% de VERDE",
        delta_color="off",
    )
    c4.metric(
        "Campo crítico sin radar",
        _fmt(len(sub)),
        delta=f"{_pct(len(sub), len(crit)):.1f}% de ROJO/NEGRO",
        delta_color="off",
    )

    # Tasas likely por semáforo
    st.markdown("##### % `likely_damaged` por semáforo (≤ radio)")
    rows = []
    for et in ["NEGRO", "ROJO", "AMARILLO", "VERDE"]:
        g = near[near["etiqueta_n"] == et]
        n_l = int((g["nasa_label"] == "likely_damaged").sum()) if not g.empty else 0
        rows.append(
            {
                "Semáforo": et,
                "n": len(g),
                "likely_damaged": n_l,
                "% likely": _pct(n_l, len(g)),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(
        "Si % likely sube de VERDE → NEGRO, el radar se alinea con el criterio de campo "
        "(señal de confiabilidad relativa en el AOI)."
    )

    basemap = st.selectbox("Mapa base", list(BASEMAPS.keys()), key="nh_bm")
    view = st.selectbox("Vista", list(VIEWS.keys()), key="nh_view")

    def _pop_c(r):
        return _popup(
            "Calor confirmado (Hab crítico × NASA likely)",
            {
                "Id": getattr(r, "id", ""),
                "Semáforo": getattr(r, "etiqueta_n", ""),
                "NASA": getattr(r, "nasa_label", ""),
                "Dist. m": round(float(getattr(r, "nasa_dist_m", 0) or 0), 1),
                "Edificio": getattr(r, "nombre_edificacion", ""),
                "Municipio": getattr(r, "municipio_n", ""),
            },
        )

    def _pop_s(r):
        return _popup(
            "Sobre-alerta NASA (Hab VERDE × likely)",
            {
                "Id": getattr(r, "id", ""),
                "Semáforo": getattr(r, "etiqueta_n", ""),
                "NASA": getattr(r, "nasa_label", ""),
                "Edificio": getattr(r, "nombre_edificacion", ""),
            },
        )

    html = _heat_map_html(
        layers=[
            (
                f"Calor confirmado ROJO/NEGRO×likely · {_fmt(len(conf_pos))}",
                conf_pos,
                "",
                True,
            ),
            (
                f"Sobre-alerta (VERDE×likely) · {_fmt(len(sobre))}",
                sobre,
                "",
                False,
            ),
            (
                f"Crítico sin radar (ROJO/NEGRO×not_damaged) · {_fmt(len(sub))}",
                sub,
                "",
                False,
            ),
        ],
        points=[
            ("Confirmados", conf_pos, "#7F1D1D", True, _pop_c),
            ("Sobre-alerta", sobre, "#F59E0B", False, _pop_s),
        ],
        basemap=basemap,
        view=view,
    )
    components.html(html, height=560, scrolling=False)

    st.markdown("##### Retroalimentación a zonas de calor")
    st.success(
        f"Usar como **núcleo de calor confiable** las **{_fmt(len(conf_pos))}** localidades "
        f"ROJO/NEGRO con NASA `likely_damaged` ≤ {radio} m. "
        f"Tratar con cautela las **{_fmt(len(sobre))}** VERDE×likely (calor NASA no confirmado en campo)."
    )


# ─── IA ──────────────────────────────────────────────────────────────────────


def page_nasa_ia(summary: dict | None = None) -> None:
    st.caption(
        "Validar modelados: acuerdo óptico (IA) × radar (NASA) y mapas de calor de doble alerta."
    )
    _ = summary
    _intro_cruceros_clave()

    df = _load(str(CRUCE_IA))
    if df.empty:
        st.error("Falta cruce IA × NASA.")
        return

    radio = st.select_slider("Radio NASA (m)", options=list(RADII), value=50, key="ni_radio")
    near = _near(df, radio)
    if near.empty:
        st.warning("Sin puntos dentro del radio.")
        return

    st.markdown("##### Matriz estatus IA × label NASA")
    ct = pd.crosstab(near["estatus_riesgo"], near["nasa_label"], margins=True)
    st.dataframe(ct, use_container_width=True)

    alert = near[
        ~near["estatus_riesgo"].astype(str).str.lower().str.contains("no afect")
    ]
    noaf = near[near["estatus_riesgo"].astype(str).str.lower().str.contains("no afect")]
    doble = alert[alert["nasa_label"] == "likely_damaged"]
    solo_ia = alert[alert["nasa_label"] == "not_damaged"]
    solo_nasa = noaf[noaf["nasa_label"] == "likely_damaged"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sitios IA ≤ radio", _fmt(len(near)))
    c2.metric(
        "Doble alerta (IA+NASA)",
        _fmt(len(doble)),
        delta=f"{_pct(len(doble), len(alert)):.1f}% de alertas IA",
        delta_color="off",
    )
    c3.metric(
        "Solo IA (NASA not_damaged)",
        _fmt(len(solo_ia)),
        delta_color="off",
    )
    c4.metric(
        "Solo NASA (IA no afect.)",
        _fmt(len(solo_nasa)),
        delta_color="off",
    )

    # Acuerdo simple
    # Acuerdan daño: IA alerta + likely; acuerdan ok: no afect + not_damaged
    agree_dmg = len(doble)
    agree_ok = (
        int((noaf["nasa_label"] == "not_damaged").sum()) if not noaf.empty else 0
    )
    agree = agree_dmg + agree_ok
    st.metric(
        "Acuerdo burdo óptico↔radar",
        f"{_pct(agree, len(near)):.1f}%",
        delta=f"{_fmt(agree)} / {_fmt(len(near))} (daño+daño o ok+ok)",
        delta_color="off",
    )

    basemap = st.selectbox("Mapa base", list(BASEMAPS.keys()), key="ni_bm")
    view = st.selectbox("Vista", list(VIEWS.keys()), key="ni_view")

    def _pop_d(r):
        return _popup(
            "Doble alerta IA × NASA",
            {
                "Código": getattr(r, "codigo", ""),
                "IA": getattr(r, "estatus_riesgo", ""),
                "NASA": getattr(r, "nasa_label", ""),
                "Zona": getattr(r, "zona", ""),
                "Dist. m": round(float(getattr(r, "nasa_dist_m", 0) or 0), 1),
            },
        )

    html = _heat_map_html(
        layers=[
            (
                f"Calor doble alerta · {_fmt(len(doble))}",
                doble,
                "",
                True,
            ),
            (
                f"Solo IA · {_fmt(len(solo_ia))}",
                solo_ia,
                "",
                False,
            ),
            (
                f"Solo NASA (IA no afect.) · {_fmt(len(solo_nasa))}",
                solo_nasa,
                "",
                False,
            ),
        ],
        points=[("Doble alerta", doble, "#9F1239", True, _pop_d)],
        basemap=basemap,
        view=view,
    )
    components.html(html, height=560, scrolling=False)

    st.markdown("##### Lectura")
    st.info(
        f"**Mapa de calor recomendado para afectación modelada:** doble alerta "
        f"({_fmt(len(doble))} sitios). "
        f"Sirve para validar ambos modelos; las zonas solo-IA o solo-NASA son "
        f"candidatas a revisión humana / campo."
    )


def page_nasa_analisis_router(
    sol=None,
    hab=None,
    summary: dict | None = None,
    sub: str = "nasa_mapa",
) -> None:
    """Compat: el router principal sigue en pages_nasa / app."""
    _ = (sol, hab)
    if sub == "nasa_1x10":
        page_nasa_1x10(summary)
    elif sub == "nasa_hab":
        page_nasa_habitable(summary)
    elif sub == "nasa_ia":
        page_nasa_ia(summary)
