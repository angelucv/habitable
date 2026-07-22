"""Análisis por fuente × NASA: 1×10 (cola+abordaje), Habitable (verdad), IA (validación)."""

from __future__ import annotations

import html as html_lib
from io import BytesIO
from pathlib import Path
from typing import Any

import audit_ui
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
LITE_PQ = NASA_DIR / "nasa_map_lite.parquet"

VIEWS = {
    "Caracas / La Guaira": (10.55, -66.92, 11),
    "La Guaira costa": (10.60, -66.93, 12),
    "Gran Caracas": (10.48, -66.90, 10),
    "Petare (cuadrícula)": (10.47, -66.80, 13),
}

BASEMAPS: dict[str, tuple[str, str, str]] = {
    "OSM claro (Carto)": ("CartoDB positron", "© OpenStreetMap © CARTO", "OSM claro"),
    "OpenStreetMap": ("OpenStreetMap", "© OpenStreetMap", "OpenStreetMap"),
    "Satélite (Esri)": (
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "Tiles © Esri",
        "Satélite Esri",
    ),
    "Topográfico": (
        "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        "© OpenStreetMap © OpenTopoMap",
        "Topográfico",
    ),
}

RADII = (30, 50, 100)
IA_ALERT_COLORS = {
    "Afectado": "#B91C1C",
    "Posiblemente afectado": "#EA580C",
    "revision humana": "#7C3AED",
}


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


def _add_circles(
    fmap: folium.Map,
    df: pd.DataFrame,
    *,
    name: str,
    color,
    show: bool,
    pop_fn,
    radius: float = 1.5,
) -> None:
    data = df.dropna(subset=["lat", "lng"]) if not df.empty else df
    if data is None or data.empty:
        return
    fg = folium.FeatureGroup(name=f"{name} · {_fmt(len(data))}", show=show)

    def _col(r):
        if callable(color):
            return color(r)
        return color

    for r in data.itertuples(index=False):
        c = _col(r)
        folium.CircleMarker(
            location=[float(r.lat), float(r.lng)],
            radius=radius,
            color=c,
            fill=True,
            fill_color=c,
            fill_opacity=0.75,
            weight=1,
            popup=folium.Popup(pop_fn(r), max_width=380),
        ).add_to(fg)
    fg.add_to(fmap)


def _heat_map_html(
    *,
    layers: list[tuple[str, pd.DataFrame, str, bool]],
    points: list[tuple[str, pd.DataFrame, Any, bool, Any]] | None = None,
    basemap: str,
    view: str,
    gis_ids: tuple[str, ...] = (),
    zone_mode: str = "contorno",
) -> str:
    from pages_abordaje import (
        LAYER_CATALOG,
        _highlight_fn,
        _load_geojson_dict,
        _style_fn,
        _tooltip_fields,
    )

    lat, lng, zoom = VIEWS.get(view, VIEWS["Caracas / La Guaira"])
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

    catalog = {c["id"]: c for c in LAYER_CATALOG}
    outline_only = zone_mode == "contorno"
    for lid in gis_ids:
        meta = catalog.get(lid)
        if not meta:
            continue
        data = _load_geojson_dict(lid)
        if not data or not data.get("features"):
            continue
        color = meta["color"]
        name = meta["label"]
        kind = meta.get("kind", "polygon")
        tip_keys = meta.get("tooltip") or []
        if kind == "points":
            fg = folium.FeatureGroup(name=name, show=True)
            for feat in data["features"]:
                geom = feat.get("geometry") or {}
                if geom.get("type") != "Point":
                    continue
                coords = geom.get("coordinates") or []
                if len(coords) < 2:
                    continue
                props = feat.get("properties") or {}
                tip = _tooltip_fields(props, tip_keys)
                folium.CircleMarker(
                    location=[coords[1], coords[0]],
                    radius=1.5,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.7,
                    weight=1,
                    tooltip=folium.Tooltip(tip) if tip else None,
                ).add_to(fg)
            fg.add_to(m)
        else:
            sample_props = (
                (data["features"][0].get("properties") or {}) if data["features"] else {}
            )
            fields = [k for k in tip_keys if k in sample_props]
            base_fill = float(meta.get("fill_opacity", 0.04))
            if zone_mode == "relleno":
                base_fill = max(base_fill, 0.12)
            gj_kwargs: dict[str, Any] = {
                "name": name,
                "style_function": _style_fn(
                    color, base_fill, outline_only=outline_only
                ),
                "highlight_function": _highlight_fn(color),
                "show": True,
            }
            if fields:
                from folium import GeoJsonTooltip

                gj_kwargs["tooltip"] = GeoJsonTooltip(
                    fields=fields,
                    aliases=fields,
                    sticky=False,
                    labels=True,
                )
            folium.GeoJson(data, **gj_kwargs).add_to(m)

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
            _add_circles(m, df, name=name, color=color, show=show, pop_fn=pop_fn)

    folium.LayerControl(collapsed=True, position="topright").add_to(m)
    return m.get_root().render()


def _intro_cruceros_clave() -> None:
    st.info(
        "**Reglas de lectura de cruces:**\n\n"
        "1. **Habitable = verdad de campo** → mide qué tan confiable es NASA.\n"
        "2. **1×10 pendientes × NASA/IA** → orienta el próximo abordaje.\n"
        "3. **IA óptico vs NASA radar** → si IA alerta y NASA no (o al revés), "
        "revisar NASA; la IA suele ser más localizada en daño visible.\n"
        "4. **Calor confiable** = Habitable ROJO/NEGRO ∩ NASA `likely_damaged`."
    )


def _gis_layer_picker(key_prefix: str) -> tuple[tuple[str, ...], str]:
    from pages_abordaje import LAYER_CATALOG, _layer_path

    zone_mode = st.radio(
        "Estilo zonas GIS",
        options=["contorno", "suave", "relleno"],
        index=0,
        horizontal=True,
        key=f"{key_prefix}_zone",
        format_func=lambda x: {
            "contorno": "Solo contorno",
            "suave": "Relleno suave",
            "relleno": "Relleno marcado",
        }.get(x, x),
    )
    available = [m for m in LAYER_CATALOG if _layer_path(m["id"]) is not None]
    by_group: dict[str, list] = {}
    for meta in available:
        by_group.setdefault(meta["group"], []).append(meta)
    selected: list[str] = []
    with st.expander(
        "Capas GIS de abordaje (apagadas por defecto — planificar territorio)",
        expanded=False,
    ):
        st.caption(
            "Mismas capas que «Mapas de abordaje»: máscaras, cuadrículas, microzonas."
        )
        for group, items in by_group.items():
            st.markdown(f"**{group}**")
            cols = st.columns(2)
            for i, meta in enumerate(items):
                with cols[i % 2]:
                    heavy = " · pesada" if meta.get("heavy") else ""
                    on = st.checkbox(
                        f"{meta['label']}{heavy}",
                        value=False,
                        key=f"{key_prefix}_gis_{meta['id']}",
                    )
                    if on:
                        selected.append(meta["id"])
    return tuple(sorted(selected)), zone_mode


# ─── 1×10 ───────────────────────────────────────────────────────────────────


def page_nasa_1x10(summary: dict | None = None) -> None:
    st.caption(
        "Planificar abordaje: cola 1×10 + capas GIS de abordaje + guía NASA e IA."
    )
    if summary:
        st.caption(f"Corte BI · 1×10 {summary.get('n_1x10', '—')}")
    _intro_cruceros_clave()

    df = _load(str(CRUCE_1X10))
    if df.empty:
        st.error("Falta cruce 1×10 × NASA.")
        return

    ia_all = _load(str(CRUCE_IA))
    lite = _load(str(LITE_PQ))

    pend = df[df["match_cat"] == "solo_1x10"] if "match_cat" in df.columns else df
    radio = st.select_slider("Radio NASA (m)", options=list(RADII), value=50, key="n1_radio")
    near = _near(pend, radio)
    alta = near[near["nasa_label"] == "likely_damaged"] if not near.empty else near
    media = near[near["nasa_label"] == "not_damaged"] if not near.empty else near
    sin = pend[pend["nasa_dist_m"] > 100] if not pend.empty else pend

    # IA alertas cerca (guía)
    ia_alert = pd.DataFrame()
    if not ia_all.empty:
        ia_n = _near(ia_all, radio)
        ia_alert = ia_n[
            ~ia_n["estatus_riesgo"].astype(str).str.lower().str.contains("no afect")
        ]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pendientes 1×10", _fmt(len(pend)))
    c2.metric(
        f"Coinc. ≤{radio} m",
        f"{_pct(len(near), len(pend)):.1f}%",
        delta=f"{_fmt(len(near))} loc.",
        delta_color="off",
    )
    c3.metric(
        "Cola alta (NASA likely)",
        _fmt(len(alta)),
        delta=f"{_pct(len(alta), len(pend)):.1f}% pendientes",
        delta_color="off",
    )
    c4.metric("Guía IA alertas ≤radio", _fmt(len(ia_alert)))

    st.markdown("##### Mapa de planificación (abordaje + NASA + IA)")
    st.caption(
        "Activa cuadrículas/máscaras GIS como en Mapas de abordaje. "
        "La cola 1×10 (rojo) es lo a despachar; NASA/IA son guías, no sustituyen campo."
    )

    c_a, c_b = st.columns(2)
    with c_a:
        basemap = st.selectbox("Mapa base", list(BASEMAPS.keys()), key="n1_bm")
    with c_b:
        view = st.selectbox("Vista", list(VIEWS.keys()), key="n1_view")

    gis_ids, zone_mode = _gis_layer_picker("n1")

    g1, g2, g3, g4 = st.columns(4)
    with g1:
        show_heat = st.checkbox("Calor cola alta", value=True, key="n1_heat")
    with g2:
        show_pts = st.checkbox(
            f"Puntos cola NASA likely ({_fmt(len(alta))})",
            value=True,
            key="n1_pts",
        )
    with g3:
        show_ia = st.checkbox(
            f"Guía IA alertas ({_fmt(len(ia_alert))})",
            value=True,
            key="n1_ia",
        )
    with g4:
        show_nasa_coinc = st.checkbox(
            "NASA coinc. fuentes (lite)",
            value=False,
            key="n1_nasa_coinc",
            help="Footprints NASA que ya cruzaron con alguna fuente (muestreo).",
        )

    nasa_coinc = pd.DataFrame()
    if show_nasa_coinc and not lite.empty and "kind" in lite.columns:
        nasa_coinc = lite[lite["kind"].isin(["coincide_fuentes", "likely_damaged"])]

    def _pop_x10(r):
        return _popup(
            "1×10 pendiente × NASA — cola abordaje",
            {
                "Caso": getattr(r, "codigo_caso", ""),
                "NASA": getattr(r, "nasa_label", ""),
                "Dist. m": round(float(getattr(r, "nasa_dist_m", 0) or 0), 1),
                "Estado": getattr(r, "estado_n", ""),
                "Municipio": getattr(r, "municipio_n", ""),
                "Dirección": getattr(r, "direccion", ""),
            },
        )

    def _pop_ia(r):
        return _popup(
            "Guía IA (óptico)",
            {
                "Código": getattr(r, "codigo", ""),
                "Estatus IA": getattr(r, "estatus_riesgo", ""),
                "NASA": getattr(r, "nasa_label", ""),
                "Zona": getattr(r, "zona", ""),
            },
        )

    def _pop_nasa(r):
        return _popup(
            "NASA (guía)",
            {
                "Label": getattr(r, "label", ""),
                "Kind": getattr(r, "kind", ""),
                "FID": getattr(r, "nasa_fid", ""),
            },
        )

    def _ia_color(r):
        return IA_ALERT_COLORS.get(str(getattr(r, "estatus_riesgo", "")), "#EA580C")

    pts: list = []
    if show_pts:
        pts.append(("Cola 1×10 × NASA likely", alta, "#DC2626", True, _pop_x10))
    if show_ia and not ia_alert.empty:
        pts.append(("Guía IA alertas", ia_alert, _ia_color, True, _pop_ia))
    if show_nasa_coinc and not nasa_coinc.empty:
        # subsample if huge for planning map
        nc = nasa_coinc
        if len(nc) > 25_000:
            nc = nc.sample(25_000, random_state=42)
        pts.append(
            (
                "NASA guía (muestra)",
                nc,
                lambda r: "#DC2626"
                if str(getattr(r, "label", "")) == "likely_damaged"
                else "#64748B",
                False,
                _pop_nasa,
            )
        )

    heat_layers = []
    if show_heat and not alta.empty:
        heat_layers.append((f"Calor cola alta · {_fmt(len(alta))}", alta, "", True))
    if not media.empty:
        heat_layers.append(
            (f"Calor 1×10 × not_damaged · {_fmt(len(media))}", media, "", False)
        )

    with st.spinner("Generando mapa de planificación…"):
        html = _heat_map_html(
            layers=heat_layers,
            points=pts or None,
            basemap=basemap,
            view=view,
            gis_ids=gis_ids,
            zone_mode=zone_mode,
        )
    components.html(html, height=680, scrolling=False)

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
    audit_ui.download_button(
        "Descargar cola alta CSV",
        data=buf.getvalue(),
        file_name="cola_1x10_nasa_likely.csv",
        mime="text/csv",
        key="n1_dl",
    )
    st.caption(f"Sin cobertura radar >100 m entre pendientes: {_fmt(len(sin))}.")


# ─── Habitable ───────────────────────────────────────────────────────────────


def page_nasa_habitable(summary: dict | None = None) -> None:
    st.caption(
        "Habitable = verdad de campo. La matriz mide errores y aciertos de NASA."
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
    if near.empty:
        st.warning("Sin puntos dentro del radio.")
        return

    st.markdown("##### Matriz (Habitable = verdad · NASA = a evaluar)")
    st.caption(
        "Filas = semáforo de inspección. Columnas = lo que dice el radar. "
        "Cuando discrepan, **el error se atribuye a NASA** (salvo revisión de GPS)."
    )
    ct = pd.crosstab(near["etiqueta_n"], near["nasa_label"], margins=True)
    st.dataframe(ct, use_container_width=True)

    crit = near[near["etiqueta_n"].isin(["ROJO", "NEGRO"])]
    verde = near[near["etiqueta_n"] == "VERDE"]
    amar = near[near["etiqueta_n"] == "AMARILLO"]
    # Lecturas de error
    nasa_ok_crit = crit[crit["nasa_label"] == "likely_damaged"]
    nasa_miss_crit = crit[crit["nasa_label"] == "not_damaged"]
    nasa_fp_verde = verde[verde["nasa_label"] == "likely_damaged"]
    nasa_ok_verde = verde[verde["nasa_label"] == "not_damaged"]
    nasa_fp_amar = amar[amar["nasa_label"] == "likely_damaged"]

    interpret = pd.DataFrame(
        [
            {
                "Cruce": "ROJO/NEGRO × likely_damaged",
                "Quién manda": "Habitable (verdad)",
                "Lectura": "NASA ACIERTA — calor confiable",
                "n": len(nasa_ok_crit),
                "% base": f"{_pct(len(nasa_ok_crit), len(crit))}% de críticos",
            },
            {
                "Cruce": "ROJO/NEGRO × not_damaged",
                "Quién manda": "Habitable (verdad)",
                "Lectura": "NASA FALLA (no detectó daño de campo)",
                "n": len(nasa_miss_crit),
                "% base": f"{_pct(len(nasa_miss_crit), len(crit))}% de críticos",
            },
            {
                "Cruce": "VERDE × likely_damaged",
                "Quién manda": "Habitable (verdad)",
                "Lectura": "NASA SOBRE-ALERTA (radar marca daño; campo OK)",
                "n": len(nasa_fp_verde),
                "% base": f"{_pct(len(nasa_fp_verde), len(verde))}% de VERDE",
            },
            {
                "Cruce": "VERDE × not_damaged",
                "Quién manda": "Habitable (verdad)",
                "Lectura": "NASA ACIERTA (ambos OK)",
                "n": len(nasa_ok_verde),
                "% base": f"{_pct(len(nasa_ok_verde), len(verde))}% de VERDE",
            },
            {
                "Cruce": "AMARILLO × likely_damaged",
                "Quién manda": "Habitable (verdad)",
                "Lectura": "Revisar — campo intermedio + radar alerta",
                "n": len(nasa_fp_amar),
                "% base": f"{_pct(len(nasa_fp_amar), len(amar))}% de AMARILLO",
            },
        ]
    )
    st.markdown("##### Dónde NASA acierta o se equivoca")
    st.dataframe(interpret, use_container_width=True, hide_index=True)

    # Confiabilidad global simple sobre críticos + verdes (excluye amarillo del score)
    den = len(nasa_ok_crit) + len(nasa_miss_crit) + len(nasa_fp_verde) + len(nasa_ok_verde)
    num = len(nasa_ok_crit) + len(nasa_ok_verde)
    score = _pct(num, den)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Insp. ≤ radio", _fmt(len(near)), delta=f"{_pct(len(near), len(df)):.1f}% del total")
    c2.metric(
        "Confiabilidad NASA (aprox.)",
        f"{score:.1f}%",
        delta=f"{_fmt(num)} aciertos / {_fmt(den)} (crít.+VERDE)",
        delta_color="off",
    )
    c3.metric(
        "NASA sobre-alerta (VERDE)",
        _fmt(len(nasa_fp_verde)),
        delta=f"{_pct(len(nasa_fp_verde), len(verde)):.1f}% VERDE",
        delta_color="off",
    )
    c4.metric(
        "NASA no detectó (críticos)",
        _fmt(len(nasa_miss_crit)),
        delta=f"{_pct(len(nasa_miss_crit), len(crit)):.1f}% ROJO/NEGRO",
        delta_color="off",
    )

    st.markdown("##### % `likely_damaged` por semáforo (≤ radio)")
    rows = []
    for et in ["NEGRO", "ROJO", "AMARILLO", "VERDE"]:
        g = near[near["etiqueta_n"] == et]
        n_l = int((g["nasa_label"] == "likely_damaged").sum()) if not g.empty else 0
        rows.append(
            {
                "Semáforo (verdad)": et,
                "n": len(g),
                "NASA likely": n_l,
                "% NASA likely": _pct(n_l, len(g)),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(
        "Gradiente VERDE→NEGRO en % likely = NASA se alinea con campo. "
        "Si VERDE tiene mucho likely, hay sobre-alerta radar a filtrar."
    )

    basemap = st.selectbox("Mapa base", list(BASEMAPS.keys()), key="nh_bm")
    view = st.selectbox("Vista", list(VIEWS.keys()), key="nh_view")

    def _pop_c(r):
        return _popup(
            "NASA ACIERTA — Hab crítico × likely (calor confiable)",
            {
                "Id": getattr(r, "id", ""),
                "Semáforo (verdad)": getattr(r, "etiqueta_n", ""),
                "NASA": getattr(r, "nasa_label", ""),
                "Dist. m": round(float(getattr(r, "nasa_dist_m", 0) or 0), 1),
                "Edificio": getattr(r, "nombre_edificacion", ""),
            },
        )

    def _pop_s(r):
        return _popup(
            "NASA SOBRE-ALERTA — Hab VERDE × likely",
            {
                "Id": getattr(r, "id", ""),
                "Semáforo (verdad)": getattr(r, "etiqueta_n", ""),
                "NASA (posible error)": getattr(r, "nasa_label", ""),
                "Edificio": getattr(r, "nombre_edificacion", ""),
            },
        )

    def _pop_m(r):
        return _popup(
            "NASA FALLA — Hab crítico × not_damaged",
            {
                "Id": getattr(r, "id", ""),
                "Semáforo (verdad)": getattr(r, "etiqueta_n", ""),
                "NASA (no detectó)": getattr(r, "nasa_label", ""),
                "Edificio": getattr(r, "nombre_edificacion", ""),
            },
        )

    html = _heat_map_html(
        layers=[
            (
                f"Calor confiable (NASA acierta) · {_fmt(len(nasa_ok_crit))}",
                nasa_ok_crit,
                "",
                True,
            ),
            (
                f"Sobre-alerta NASA · {_fmt(len(nasa_fp_verde))}",
                nasa_fp_verde,
                "",
                False,
            ),
            (
                f"NASA no detectó · {_fmt(len(nasa_miss_crit))}",
                nasa_miss_crit,
                "",
                False,
            ),
        ],
        points=[
            ("NASA acierta", nasa_ok_crit, "#7F1D1D", True, _pop_c),
            ("NASA sobre-alerta", nasa_fp_verde, "#F59E0B", False, _pop_s),
            ("NASA no detectó", nasa_miss_crit, "#2563EB", False, _pop_m),
        ],
        basemap=basemap,
        view=view,
    )
    components.html(html, height=560, scrolling=False)

    st.success(
        f"**Calor a publicar / priorizar:** {_fmt(len(nasa_ok_crit))} sitios "
        f"(ROJO/NEGRO ∩ likely). "
        f"**Revisar NASA:** {_fmt(len(nasa_fp_verde))} sobre-alertas + "
        f"{_fmt(len(nasa_miss_crit))} no detectados en críticos."
    )


# ─── IA ──────────────────────────────────────────────────────────────────────


def page_nasa_ia(summary: dict | None = None) -> None:
    st.caption(
        "IA óptico vs NASA radar: acuerdos y desacuerdos. "
        "Cuando discrepan, priorizar revisión de NASA (la IA suele ser más puntual)."
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
    st.caption(
        "No hay inspección Habitable aquí: es **modelo vs modelo**. "
        "Hipótesis operativa: la IA (cambio óptico) es más localizada; "
        "los desacuerdos sirven para **re-revisar NASA**."
    )
    ct = pd.crosstab(near["estatus_riesgo"], near["nasa_label"], margins=True)
    st.dataframe(ct, use_container_width=True)

    alert = near[
        ~near["estatus_riesgo"].astype(str).str.lower().str.contains("no afect")
    ]
    noaf = near[near["estatus_riesgo"].astype(str).str.lower().str.contains("no afect")]
    doble = alert[alert["nasa_label"] == "likely_damaged"]
    solo_ia = alert[alert["nasa_label"] == "not_damaged"]
    solo_nasa = noaf[noaf["nasa_label"] == "likely_damaged"]
    ambos_ok = noaf[noaf["nasa_label"] == "not_damaged"] if not noaf.empty else noaf

    interpret = pd.DataFrame(
        [
            {
                "Cruce": "IA alerta × NASA likely",
                "Lectura": "ACUERDO daño (doble alerta) — calor modelado fuerte",
                "Acción": "Priorizar en mapa de afectación modelada",
                "n": len(doble),
                "%": f"{_pct(len(doble), len(alert))}% de alertas IA",
            },
            {
                "Cruce": "IA alerta × NASA not_damaged",
                "Lectura": "Desacuerdo — IA ve daño, NASA no",
                "Acción": "Revisar NASA / posible falso negativo radar",
                "n": len(solo_ia),
                "%": f"{_pct(len(solo_ia), len(alert))}% de alertas IA",
            },
            {
                "Cruce": "IA no afectado × NASA likely",
                "Lectura": "Desacuerdo — NASA alerta, IA no",
                "Acción": "Revisar NASA / posible sobre-alerta radar",
                "n": len(solo_nasa),
                "%": f"{_pct(len(solo_nasa), len(noaf))}% de «No afectado»",
            },
            {
                "Cruce": "IA no afectado × NASA not_damaged",
                "Lectura": "ACUERDO OK",
                "Acción": "Baja prioridad",
                "n": len(ambos_ok),
                "%": f"{_pct(len(ambos_ok), len(noaf))}% de «No afectado»",
            },
        ]
    )
    st.markdown("##### Lectura de cruces (quién revisar)")
    st.dataframe(interpret, use_container_width=True, hide_index=True)

    agree = len(doble) + len(ambos_ok)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sitios IA ≤ radio", _fmt(len(near)))
    c2.metric(
        "Doble alerta (acuerdo daño)",
        _fmt(len(doble)),
        delta=f"{_pct(len(doble), len(alert)):.1f}% alertas IA",
        delta_color="off",
    )
    c3.metric(
        "Revisar NASA (solo IA)",
        _fmt(len(solo_ia)),
        delta_color="off",
    )
    c4.metric(
        "Revisar NASA (solo radar)",
        _fmt(len(solo_nasa)),
        delta_color="off",
    )
    st.metric(
        "Acuerdo burdo óptico↔radar",
        f"{_pct(agree, len(near)):.1f}%",
        delta=f"{_fmt(agree)} / {_fmt(len(near))} (daño+daño o ok+ok)",
        delta_color="off",
    )
    st.warning(
        f"Hay **{_fmt(len(solo_nasa))}** sitios donde NASA marca `likely_damaged` "
        f"pero la IA dice «No afectado» — candidatos a filtrar del calor NASA. "
        f"Y **{_fmt(len(solo_ia))}** donde solo la IA alerta — candidatos a que el radar "
        f"se haya quedado corto."
    )

    basemap = st.selectbox("Mapa base", list(BASEMAPS.keys()), key="ni_bm")
    view = st.selectbox("Vista", list(VIEWS.keys()), key="ni_view")

    def _pop_d(r):
        return _popup(
            "Doble alerta IA × NASA (acuerdo daño)",
            {
                "Código": getattr(r, "codigo", ""),
                "IA": getattr(r, "estatus_riesgo", ""),
                "NASA": getattr(r, "nasa_label", ""),
                "Zona": getattr(r, "zona", ""),
            },
        )

    html = _heat_map_html(
        layers=[
            (f"Calor doble alerta · {_fmt(len(doble))}", doble, "", True),
            (f"Solo IA → revisar NASA · {_fmt(len(solo_ia))}", solo_ia, "", False),
            (
                f"Solo NASA → revisar NASA · {_fmt(len(solo_nasa))}",
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

    st.info(
        f"**Mapa de calor modelado recomendado:** doble alerta ({_fmt(len(doble))}). "
        f"Para recalibrar NASA, inspeccionar muestras de solo-IA y solo-NASA."
    )


def page_nasa_analisis_router(
    sol=None,
    hab=None,
    summary: dict | None = None,
    sub: str = "nasa_mapa",
) -> None:
    _ = (sol, hab)
    if sub == "nasa_1x10":
        page_nasa_1x10(summary)
    elif sub == "nasa_hab":
        page_nasa_habitable(summary)
    elif sub == "nasa_ia":
        page_nasa_ia(summary)
