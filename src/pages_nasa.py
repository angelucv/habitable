"""Sección ensayo: Mapa NASA × 1×10 × Habitable × IA (estilo abordaje, sin clusters)."""

from __future__ import annotations

import html as html_lib
import json
from io import BytesIO
from pathlib import Path
from typing import Any

import folium
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parents[1]
NASA_DIR = ROOT / "data" / "external_nasa"
LITE_PQ = NASA_DIR / "nasa_map_lite.parquet"
LITE_META = NASA_DIR / "nasa_map_lite_meta.json"
CRUCE_1X10 = NASA_DIR / "cruce_1x10_nasa" / "cruce_1x10_nasa_detallado.parquet"
CRUCE_HAB = NASA_DIR / "cruce_habitable_nasa" / "cruce_habitable_nasa_detallado.parquet"
CRUCE_IA = NASA_DIR / "cruce_ia_nasa" / "cruce_ia_nasa_detallado.parquet"

VIEWS = {
    "Caracas / La Guaira": (10.55, -66.92, 11),
    "La Guaira costa": (10.60, -66.93, 12),
    "Gran Caracas": (10.48, -66.90, 10),
    "AOI NASA (norte)": (10.45, -67.3, 9),
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

NASA_COLORS = {
    "likely_damaged": "#DC2626",
    "not_damaged": "#64748B",
    "not_assessed": "#D97706",
}

PRIORIDAD_COLORS = {
    "alta": "#DC2626",
    "media": "#2563EB",
    "revisar": "#CA8A04",
    "sin_radar": "#9CA3AF",
}

IA_COLORS = {
    "Afectado": "#B91C1C",
    "Posiblemente afectado": "#EA580C",
    "No afectado": "#059669",
    "revision humana": "#7C3AED",
}

ETIQUETA_HEX = {
    "VERDE": "#16A34A",
    "AMARILLO": "#CA8A04",
    "ROJO": "#DC2626",
    "NEGRO": "#111827",
}


def _esc(val: Any) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    if s in ("", "nan", "None", "<NA>"):
        return ""
    return html_lib.escape(s)


def _fmt_popup(title: str, fields: dict[str, Any]) -> str:
    parts = [f"<b>{html_lib.escape(str(title))}</b>"]
    for lab, val in fields.items():
        if val is None:
            continue
        if isinstance(val, float) and pd.isna(val):
            continue
        s = str(val).strip()
        if s in ("", "nan", "None", "<NA>"):
            continue
        parts.append(f"<b>{html_lib.escape(str(lab))}</b>: {html_lib.escape(s)}")
    return "<br/>".join(parts)


def _tile_layer(key: str, show: bool = True) -> folium.TileLayer:
    tiles, attr, name = BASEMAPS[key]
    if tiles.startswith("http"):
        return folium.TileLayer(
            tiles=tiles,
            attr=attr,
            name=name,
            show=show,
            overlay=False,
            control=True,
            max_zoom=19,
        )
    return folium.TileLayer(
        tiles=tiles,
        name=name,
        show=show,
        overlay=False,
        control=True,
        max_zoom=19,
    )


def _fmt_n(n: int) -> str:
    return f"{int(n):,}".replace(",", ".")


def _coinc_stats(df: pd.DataFrame, max_dist: float) -> tuple[int, int, float]:
    """total, n_coinc (≤ radio), pct."""
    if df is None or df.empty:
        return 0, 0, 0.0
    total = len(df)
    if "nasa_dist_m" not in df.columns:
        return total, 0, 0.0
    n_coinc = int((df["nasa_dist_m"] <= float(max_dist)).sum())
    pct = round(100.0 * n_coinc / total, 1) if total else 0.0
    return total, n_coinc, pct


def _layer_label(nombre: str, total: int, pct: float, radio: float) -> str:
    return (
        f"{nombre} · {_fmt_n(total)} tot · {pct:.1f}% coinc. ≤{int(radio)} m"
    )


def _point_color(
    r,
    *,
    mode: str,
    source: str,
) -> str:
    if source == "nasa":
        return NASA_COLORS.get(str(getattr(r, "label", "")), "#6B7280")
    if source == "ia":
        return IA_COLORS.get(str(getattr(r, "estatus_riesgo", "")), "#6B7280")
    if mode == "semaforo" and source == "hab":
        et = str(getattr(r, "etiqueta_n", "") or "").upper()
        return ETIQUETA_HEX.get(et, "#6B7280")
    if mode == "prioridad":
        return PRIORIDAD_COLORS.get(str(getattr(r, "nasa_prioridad", "")), "#6B7280")
    return NASA_COLORS.get(str(getattr(r, "nasa_label", "")), "#6B7280")


def _add_circle_layer(
    fmap: folium.Map,
    df: pd.DataFrame,
    *,
    name: str,
    show: bool,
    color_fn,
    popup_fn,
    tip_fn,
    radius: float = 1.5,
) -> int:
    data = df.dropna(subset=["lat", "lng"])
    if data.empty:
        return 0
    fg = folium.FeatureGroup(name=name, show=show)
    for r in data.itertuples(index=False):
        color = color_fn(r)
        folium.CircleMarker(
            location=[float(r.lat), float(r.lng)],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            weight=1,
            popup=folium.Popup(popup_fn(r), max_width=380),
            tooltip=tip_fn(r),
        ).add_to(fg)
    fg.add_to(fmap)
    return len(data)


def _df_to_bytes(df: pd.DataFrame | None) -> bytes:
    if df is None or df.empty:
        return b""
    buf = BytesIO()
    df.to_parquet(buf, index=False)
    return buf.getvalue()


def _read_bytes(b: bytes) -> pd.DataFrame:
    if not b:
        return pd.DataFrame()
    return pd.read_parquet(BytesIO(b))


@st.cache_data(show_spinner=False)
def _load_lite() -> tuple[pd.DataFrame, dict]:
    if not LITE_PQ.exists():
        return pd.DataFrame(), {}
    meta = {}
    if LITE_META.exists():
        meta = json.loads(LITE_META.read_text(encoding="utf-8"))
    return pd.read_parquet(LITE_PQ), meta


@st.cache_data(show_spinner=False)
def _load_cruce(path_str: str) -> pd.DataFrame:
    p = Path(path_str)
    if not p.exists():
        return pd.DataFrame()
    return pd.read_parquet(p)


@st.cache_data(show_spinner="Generando mapa NASA…")
def _cached_nasa_html(
    *,
    basemap: str,
    view_name: str,
    color_mode: str,
    likely_b: bytes,
    coinc_b: bytes,
    inv_b: bytes,
    x10_b: bytes,
    hab_b: bytes,
    ia_b: bytes,
    show_likely: bool,
    show_coinc: bool,
    show_inv: bool,
    show_x10: bool,
    show_hab: bool,
    show_ia: bool,
    layer_names: tuple[str, ...],
) -> str:
    lat, lng, zoom = VIEWS[view_name]
    m = folium.Map(
        location=[lat, lng],
        zoom_start=zoom,
        tiles=None,
        control_scale=True,
        prefer_canvas=True,
    )
    m.add_child(_tile_layer(basemap, show=True))
    for key in BASEMAPS:
        if key != basemap:
            m.add_child(_tile_layer(key, show=False))

    nasa_likely = _read_bytes(likely_b)
    nasa_coinc = _read_bytes(coinc_b)
    nasa_inv = _read_bytes(inv_b)
    x10 = _read_bytes(x10_b)
    hab = _read_bytes(hab_b)
    ia = _read_bytes(ia_b)
    # layer_names: likely, coinc, inv, x10, hab, ia
    n_likely = layer_names[0] if len(layer_names) > 0 else "NASA daño probable"
    n_coinc = layer_names[1] if len(layer_names) > 1 else "NASA coinc. fuentes"
    n_inv = layer_names[2] if len(layer_names) > 2 else "NASA inventario"
    n_x10 = layer_names[3] if len(layer_names) > 3 else "1×10"
    n_hab = layer_names[4] if len(layer_names) > 4 else "Habitable"
    n_ia = layer_names[5] if len(layer_names) > 5 else "IA"

    if show_likely and not nasa_likely.empty:
        _add_circle_layer(
            m,
            nasa_likely,
            name=n_likely,
            show=True,
            color_fn=lambda r: NASA_COLORS["likely_damaged"],
            popup_fn=lambda r: _fmt_popup(
                "Fuente: NASA Sentinel-1 (daño probable)",
                {
                    "Label": getattr(r, "label", ""),
                    "Probabilidad": getattr(r, "damage_probability", ""),
                    "FID": getattr(r, "nasa_fid", ""),
                },
            ),
            tip_fn=lambda r: "NASA · likely_damaged",
            radius=1.5,
        )

    if show_coinc and not nasa_coinc.empty:
        _add_circle_layer(
            m,
            nasa_coinc,
            name=n_coinc,
            show=True,
            color_fn=lambda r: NASA_COLORS.get(
                str(getattr(r, "label", "")), "#0EA5E9"
            ),
            popup_fn=lambda r: _fmt_popup(
                "Fuente: NASA (coincide con 1×10 / Habitable / IA)",
                {
                    "Label": getattr(r, "label", ""),
                    "Kind": getattr(r, "kind", ""),
                    "FID": getattr(r, "nasa_fid", ""),
                    "Probabilidad": getattr(r, "damage_probability", ""),
                },
            ),
            tip_fn=lambda r: f"NASA coinc. · {getattr(r, 'label', '')}",
            radius=1.5,
        )

    if show_inv and not nasa_inv.empty:
        _add_circle_layer(
            m,
            nasa_inv,
            name=n_inv,
            show=True,
            color_fn=lambda r: NASA_COLORS.get(str(getattr(r, "label", "")), "#6B7280"),
            popup_fn=lambda r: _fmt_popup(
                "Fuente: NASA inventario (muestra 500 m)",
                {
                    "Label": getattr(r, "label", ""),
                    "Kind": getattr(r, "kind", ""),
                    "FID": getattr(r, "nasa_fid", ""),
                },
            ),
            tip_fn=lambda r: f"NASA · {getattr(r, 'label', '')}",
            radius=1.5,
        )

    if show_x10 and not x10.empty:
        _add_circle_layer(
            m,
            x10,
            name=n_x10,
            show=True,
            color_fn=lambda r: _point_color(r, mode=color_mode, source="x10"),
            popup_fn=lambda r: _fmt_popup(
                "Fuente: 1×10 × NASA",
                {
                    "Caso": getattr(r, "codigo_caso", ""),
                    "Label NASA": getattr(r, "nasa_label", ""),
                    "Distancia NASA": round(float(getattr(r, "nasa_dist_m", 0) or 0), 1),
                    "Dentro footprint": getattr(r, "nasa_within", ""),
                    "Prioridad": getattr(r, "nasa_prioridad", ""),
                    "Cruce 1×10": getattr(r, "match_cat", ""),
                    "Estado": getattr(r, "estado_n", ""),
                    "Municipio": getattr(r, "municipio_n", ""),
                    "Dirección": getattr(r, "direccion", ""),
                },
            ),
            tip_fn=lambda r: (
                f"1×10 · {getattr(r, 'nasa_label', '')} · "
                f"{round(float(getattr(r, 'nasa_dist_m', 0) or 0), 0):.0f} m"
            ),
            radius=1.5,
        )

    if show_hab and not hab.empty:
        mode_hab = "semaforo" if color_mode == "semaforo" else color_mode
        _add_circle_layer(
            m,
            hab,
            name=n_hab,
            show=True,
            color_fn=lambda r: _point_color(r, mode=mode_hab, source="hab"),
            popup_fn=lambda r: _fmt_popup(
                "Fuente: Habitable × NASA",
                {
                    "Id": getattr(r, "id", ""),
                    "Semáforo": getattr(r, "etiqueta_n", ""),
                    "Label NASA": getattr(r, "nasa_label", ""),
                    "Distancia NASA": round(float(getattr(r, "nasa_dist_m", 0) or 0), 1),
                    "Prioridad": getattr(r, "nasa_prioridad", ""),
                    "Edificio": getattr(r, "nombre_edificacion", ""),
                    "Estado": getattr(r, "estado_n", ""),
                    "Municipio": getattr(r, "municipio_n", ""),
                },
            ),
            tip_fn=lambda r: (
                f"Habitable {getattr(r, 'etiqueta_n', '')} · "
                f"{getattr(r, 'nasa_label', '')}"
            ),
            radius=1.5,
        )

    if show_ia and not ia.empty:
        _add_circle_layer(
            m,
            ia,
            name=n_ia,
            show=True,
            color_fn=lambda r: _point_color(r, mode=color_mode, source="ia"),
            popup_fn=lambda r: _fmt_popup(
                "Fuente: Análisis IA × NASA",
                {
                    "Código": getattr(r, "codigo", ""),
                    "Estatus IA": getattr(r, "estatus_riesgo", ""),
                    "Label NASA": getattr(r, "nasa_label", ""),
                    "Distancia NASA": round(float(getattr(r, "nasa_dist_m", 0) or 0), 1),
                    "Zona": getattr(r, "zona", ""),
                    "Tipo": getattr(r, "tipo_estructura", ""),
                    "Texto": str(getattr(r, "descripcion_danos", "") or "")[:280],
                },
            ),
            tip_fn=lambda r: (
                f"IA · {getattr(r, 'estatus_riesgo', '')} · "
                f"{getattr(r, 'nasa_label', '')}"
            ),
            radius=1.5,
        )

    folium.LayerControl(collapsed=True, position="topright").add_to(m)
    return m.get_root().render()


def page_nasa(
    sol=None,
    hab=None,
    summary: dict | None = None,
    sub: str = "nasa_mapa",
) -> None:
    if sub in ("nasa_1x10", "nasa_hab", "nasa_ia"):
        from pages_nasa_analisis import page_nasa_analisis_router

        page_nasa_analisis_router(sol, hab, summary, sub=sub)
        return

    _ = (sol, hab)
    st.caption(
        "Ensayo local: puntos sueltos (estilo mapas de abordaje, sin agrupar). "
        "En cada fuente: total de localidades y % de coincidencia con NASA al radio elegido."
    )
    if summary:
        st.caption(
            f"Corte BI · 1×10 {summary.get('n_1x10', '—')} · "
            f"Habitable {summary.get('n_hab', '—')}"
        )

    lite, meta = _load_lite()
    if lite.empty:
        st.error(
            "Falta el muestreo NASA para mapa. Ejecuta "
            "`scripts/build_nasa_map_lite.py`."
        )
        return

    x10_all = _load_cruce(str(CRUCE_1X10))
    hab_all = _load_cruce(str(CRUCE_HAB))
    ia_all = _load_cruce(str(CRUCE_IA))

    nasa_likely = lite[lite["kind"] == "likely_damaged"].copy()
    nasa_coinc = (
        lite[lite["kind"] == "coincide_fuentes"].copy()
        if "kind" in lite.columns
        else lite.iloc[0:0].copy()
    )
    nasa_inv = lite[lite["kind"] == "inventario_500m"].copy()

    c1, c2, c3 = st.columns([1.2, 1.2, 1.6])
    with c1:
        basemap = st.selectbox(
            "Mapa base",
            options=list(BASEMAPS.keys()),
            index=0,
            key="nasa_basemap",
        )
    with c2:
        view_name = st.selectbox(
            "Vista inicial",
            options=list(VIEWS.keys()),
            index=0,
            key="nasa_view",
        )
    with c3:
        color_mode = st.radio(
            "Color de cruces",
            options=["prioridad", "nasa_label", "semaforo"],
            index=0,
            horizontal=True,
            key="nasa_color_mode",
            format_func=lambda x: {
                "prioridad": "Prioridad NASA",
                "nasa_label": "Label NASA",
                "semaforo": "Semáforo Hab / IA estatus",
            }.get(x, x),
            help="En Habitable, «semáforo» usa VERDE/AMARILLO/ROJO/NEGRO. En IA siempre estatus.",
        )

    st.markdown("##### Filtros de coincidencia")
    f1, f2, f3 = st.columns(3)
    with f1:
        max_dist = st.select_slider(
            "Radio coincidencia NASA (m)",
            options=[30, 50, 100, 200, 500],
            value=100,
            key="nasa_max_dist",
            help="% coincidencia = localidades con footprint NASA a ≤ este radio.",
        )
    with f2:
        only_alta = st.checkbox(
            "Solo prioridad alta en mapa",
            value=False,
            key="nasa_only_alta",
        )
    with f3:
        only_pend_x10 = st.checkbox(
            "1×10 solo pendientes",
            value=True,
            key="nasa_only_pend",
        )

    # Universo por fuente (antes de filtrar el mapa por radio)
    x10_base = x10_all
    if only_pend_x10 and not x10_base.empty and "match_cat" in x10_base.columns:
        x10_base = x10_base[x10_base["match_cat"] == "solo_1x10"]
    hab_base = hab_all
    ia_base = ia_all
    show_ia_noafect = st.checkbox(
        "Incluir IA «No afectado» en totales",
        value=False,
        key="nasa_ia_noafect",
    )
    if (
        not ia_base.empty
        and not show_ia_noafect
        and "estatus_riesgo" in ia_base.columns
    ):
        ia_base = ia_base[
            ~ia_base["estatus_riesgo"].astype(str).str.lower().str.contains("no afect")
        ]

    t_x10, c_x10, p_x10 = _coinc_stats(x10_base, max_dist)
    t_hab, c_hab, p_hab = _coinc_stats(hab_base, max_dist)
    t_ia, c_ia, p_ia = _coinc_stats(ia_base, max_dist)

    # Lo que se dibuja: solo coincidentes al radio (+ filtros opcionales)
    def _for_map(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        out = df[df["nasa_dist_m"] <= float(max_dist)] if "nasa_dist_m" in df.columns else df
        if only_alta and "nasa_prioridad" in out.columns:
            out = out[out["nasa_prioridad"] == "alta"]
        return out

    x10_map = _for_map(x10_base)
    hab_map = _for_map(hab_base)
    ia_map = _for_map(ia_base)

    st.markdown("##### Capas NASA")
    if meta:
        st.caption(
            f"Cruces hechos sobre inventario completo "
            f"({_fmt_n(meta.get('n_nasa_source', 2_700_098))}). "
            f"Muestreo mapa incluye **100%** de footprints coincidentes ≤"
            f"{int(meta.get('coinc_max_m', 100))} m "
            f"({_fmt_n(meta.get('coinc_fids_en_lite', 0))} / "
            f"{_fmt_n(meta.get('coinc_fids_union', 0))})."
        )
    n1, n2, n3 = st.columns(3)
    with n1:
        show_likely = st.checkbox(
            f"NASA daño probable · {_fmt_n(len(nasa_likely))} tot",
            value=True,
            key="nasa_show_likely",
        )
    with n2:
        show_coinc = st.checkbox(
            f"NASA coinc. con fuentes · {_fmt_n(len(nasa_coinc))} tot",
            value=True,
            key="nasa_show_coinc",
            help=(
                "Footprints del inventario completo (2.7M) que coinciden "
                "con 1×10, Habitable o IA ≤ radio del muestreo. "
                "Prioridad del mapa para no perder matches."
            ),
        )
    with n3:
        show_inv = st.checkbox(
            f"NASA inventario 500 m · {_fmt_n(len(nasa_inv))} tot",
            value=False,
            key="nasa_show_inv",
            help="Relleno de cobertura (apagado por defecto).",
        )

    st.markdown("##### Fuentes cruzadas (total · % coincidencia con NASA)")
    k1, k2, k3 = st.columns(3)
    with k1:
        show_x10 = st.checkbox(
            _layer_label("1×10", t_x10, p_x10, max_dist),
            value=True,
            key="nasa_show_x10",
            help=f"Coinciden {_fmt_n(c_x10)} de {_fmt_n(t_x10)} localidades ≤ {max_dist} m.",
        )
    with k2:
        show_hab = st.checkbox(
            _layer_label("Habitable", t_hab, p_hab, max_dist),
            value=True,
            key="nasa_show_hab",
            help=f"Coinciden {_fmt_n(c_hab)} de {_fmt_n(t_hab)} localidades ≤ {max_dist} m.",
        )
    with k3:
        show_ia = st.checkbox(
            _layer_label("IA óptico", t_ia, p_ia, max_dist),
            value=True,
            key="nasa_show_ia",
            help=f"Coinciden {_fmt_n(c_ia)} de {_fmt_n(t_ia)} localidades ≤ {max_dist} m.",
        )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("NASA likely", _fmt_n(len(nasa_likely)))
    m2.metric(
        "1×10 coinc.",
        f"{p_x10:.1f}%",
        delta=f"{_fmt_n(c_x10)} / {_fmt_n(t_x10)}",
        delta_color="off",
    )
    m3.metric(
        "Habitable coinc.",
        f"{p_hab:.1f}%",
        delta=f"{_fmt_n(c_hab)} / {_fmt_n(t_hab)}",
        delta_color="off",
    )
    m4.metric(
        "IA coinc.",
        f"{p_ia:.1f}%",
        delta=f"{_fmt_n(c_ia)} / {_fmt_n(t_ia)}",
        delta_color="off",
    )

    if meta:
        st.caption(
            f"NASA lite · {_fmt_n(meta.get('n_total_lite', len(lite)))} pts "
            f"(likely {_fmt_n(meta.get('n_likely_damaged', 0))} + "
            f"coinc. fuentes {_fmt_n(meta.get('n_coincide_fuentes', 0))} + "
            f"relleno {_fmt_n(meta.get('n_inventario_500m', 0))} @ "
            f"{meta.get('cell_m', 500)} m)"
        )

    if not any([show_likely, show_coinc, show_inv, show_x10, show_hab, show_ia]):
        st.info("Activa al menos una capa.")
        return

    n_draw = (
        (len(nasa_likely) if show_likely else 0)
        + (len(nasa_coinc) if show_coinc else 0)
        + (len(nasa_inv) if show_inv else 0)
        + (len(x10_map) if show_x10 else 0)
        + (len(hab_map) if show_hab else 0)
        + (len(ia_map) if show_ia else 0)
    )
    if n_draw > 40_000:
        st.warning(
            f"Se dibujarán ~{_fmt_n(n_draw)} puntos sueltos (sin agrupar). "
            "La primera carga puede demorar; apaga inventario NASA o baja capas."
        )

    layer_names = (
        f"NASA daño probable · {_fmt_n(len(nasa_likely))}",
        f"NASA coinc. fuentes · {_fmt_n(len(nasa_coinc))}",
        f"NASA inventario 500 m · {_fmt_n(len(nasa_inv))}",
        _layer_label("1×10", t_x10, p_x10, max_dist)
        + f" · mapa {_fmt_n(len(x10_map))}",
        _layer_label("Habitable", t_hab, p_hab, max_dist)
        + f" · mapa {_fmt_n(len(hab_map))}",
        _layer_label("IA", t_ia, p_ia, max_dist) + f" · mapa {_fmt_n(len(ia_map))}",
    )

    html = _cached_nasa_html(
        basemap=basemap,
        view_name=view_name,
        color_mode=color_mode,
        likely_b=_df_to_bytes(nasa_likely if show_likely else None),
        coinc_b=_df_to_bytes(nasa_coinc if show_coinc else None),
        inv_b=_df_to_bytes(nasa_inv if show_inv else None),
        x10_b=_df_to_bytes(x10_map if show_x10 else None),
        hab_b=_df_to_bytes(hab_map if show_hab else None),
        ia_b=_df_to_bytes(ia_map if show_ia else None),
        show_likely=show_likely,
        show_coinc=show_coinc,
        show_inv=show_inv,
        show_x10=show_x10,
        show_hab=show_hab,
        show_ia=show_ia,
        layer_names=layer_names,
    )
    components.html(html, height=720, scrolling=False)

    st.caption(
        "Puntos sueltos (CircleMarker, como abordaje). "
        "Clic = detalle. Coincidencia = localidad con estructura NASA a ≤ radio. "
        "En el mapa solo se dibujan las que coinciden (salvo capas NASA)."
    )
