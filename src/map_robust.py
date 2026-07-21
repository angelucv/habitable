"""Mapa operativo: Folium optimizado (FastMarkerCluster + heatmap)."""

from __future__ import annotations

import html as html_lib
from typing import Any

import folium
from folium.plugins import FastMarkerCluster, HeatMap, MarkerCluster, MeasureControl, MiniMap
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Basemaps públicos (sin API key)
BASEMAPS: dict[str, tuple[str, str, str]] = {
    "OpenStreetMap": ("OpenStreetMap", "© OpenStreetMap", "OpenStreetMap"),
    "OSM claro (Carto)": ("CartoDB positron", "© OpenStreetMap © CARTO", "OSM claro"),
    "OSM oscuro (Carto)": (
        "CartoDB dark_matter",
        "© OpenStreetMap © CARTO",
        "OSM oscuro",
    ),
    "Satélite (Esri)": (
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "Tiles © Esri",
        "Satélite Esri",
    ),
    "Calles (Esri)": (
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        "Tiles © Esri",
        "Calles Esri",
    ),
    "Topográfico": (
        "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        "© OpenStreetMap © OpenTopoMap",
        "Topográfico",
    ),
}

ETIQUETA_HEX = {
    "VERDE": "#228B22",
    "AMARILLO": "#DAA520",
    "ROJO": "#B22222",
    "NEGRO": "#111111",
    "SIN": "#888888",
}

VIEWS = {
    "Caracas / La Guaira": (10.50, -66.92, 11),
    "Gran Caracas": (10.45, -66.90, 10),
    "Nacional (norte VE)": (10.4, -67.5, 7),
}

# Por encima de esto: FastMarkerCluster (sin CircleMarker Python)
FAST_THRESHOLD = 400


def _tile_layer(key: str, show: bool = False) -> folium.TileLayer:
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


def _esc(val: Any) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    if s in ("", "nan"):
        return ""
    return html_lib.escape(s)


def _popup_from_dict(kind: str, fields: dict[str, Any]) -> str:
    parts = [f"<b>{_esc(kind)}</b>"]
    for lab, val in fields.items():
        s = _esc(val)
        if s:
            parts.append(f"{lab}: {s}")
    return "<br/>".join(parts)


def _popup_row(r: pd.Series, kind: str) -> str:
    fields = {}
    mapping = [
        ("codigo_caso", "Caso"),
        ("n_reportes", "Reportes"),
        ("direccion", "Dirección"),
        ("nombre_edificacion", "Edificio"),
        ("match_cat", "Cruce"),
        ("hab_nombre", "Habitable"),
        ("etiqueta_n", "Etiqueta"),
        ("estado_n", "Estado"),
        ("match_dist_m", "Dist. m"),
    ]
    for col, lab in mapping:
        if col not in r.index:
            continue
        val = r[col]
        if col == "match_dist_m" and pd.notna(val):
            try:
                val = f"{float(val):.1f}"
            except Exception:
                pass
        fields[lab] = val
    return _popup_from_dict(kind, fields)


def _prepare(
    df: pd.DataFrame, max_markers: int | None
) -> tuple[pd.DataFrame, int, bool]:
    if df is None or df.empty:
        return df, 0, False
    data = df.dropna(subset=["lat", "lng"])
    total = len(data)
    if max_markers is not None and total > max_markers:
        return data.sample(max_markers, random_state=42), total, True
    return data, total, False


def _fast_callback(color: str) -> str:
    """Callback JS: un solo tipo de círculo + popup en row[2]."""
    return f"""
function (row) {{
    var marker = L.circleMarker(new L.LatLng(row[0], row[1]), {{
        radius: row[3] || 5,
        color: '{color}',
        fillColor: '{color}',
        fillOpacity: 0.75,
        weight: 1
    }});
    if (row[2]) {{ marker.bindPopup(row[2]); }}
    return marker;
}};
"""


def _add_points_fast(
    fmap: folium.Map,
    df: pd.DataFrame,
    *,
    name: str,
    color: str,
    show: bool,
    kind: str,
    max_markers: int | None = None,
) -> int:
    data, total, truncated = _prepare(df, max_markers)
    if data is None or data.empty:
        return 0

    label = f"{name} · {len(data):,}".replace(",", ".")
    if truncated:
        label = f"{name} · {len(data):,}/{total:,}".replace(",", ".")

    fg = folium.FeatureGroup(name=label, show=show)

    # Capas pequeñas: MarkerCluster clásico (mejor UX al hacer zoom)
    if len(data) <= FAST_THRESHOLD:
        cluster = MarkerCluster().add_to(fg)
        for r in data.itertuples(index=False):
            n_rep = int(getattr(r, "n_reportes", 1) or 1)
            radius = 5 if n_rep <= 1 else min(5 + n_rep, 14)
            series = pd.Series(r._asdict()) if hasattr(r, "_asdict") else None
            popup = _popup_row(series, kind) if series is not None else kind
            folium.CircleMarker(
                location=[float(r.lat), float(r.lng)],
                radius=radius,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.75,
                weight=1,
                popup=folium.Popup(popup, max_width=320),
            ).add_to(cluster)
    else:
        # Batch JS: evita crear miles de objetos Python Folium
        rows = []
        has_dir = "direccion" in data.columns
        has_cod = "codigo_caso" in data.columns
        has_n = "n_reportes" in data.columns
        has_hab = "hab_nombre" in data.columns
        has_est = "estado_n" in data.columns
        for r in data.itertuples(index=False):
            n_rep = int(getattr(r, "n_reportes", 1) or 1) if has_n else 1
            radius = 5 if n_rep <= 1 else min(5 + n_rep, 14)
            fields = {
                "Caso": getattr(r, "codigo_caso", "") if has_cod else "",
                "Reportes": n_rep,
                "Dirección": getattr(r, "direccion", "") if has_dir else "",
                "Habitable": getattr(r, "hab_nombre", "") if has_hab else "",
                "Estado": getattr(r, "estado_n", "") if has_est else "",
            }
            rows.append(
                [float(r.lat), float(r.lng), _popup_from_dict(kind, fields), radius]
            )
        FastMarkerCluster(data=rows, callback=_fast_callback(color)).add_to(fg)

    fg.add_to(fmap)
    return len(data)


def _add_habitable_fast(
    fmap: folium.Map,
    df: pd.DataFrame,
    *,
    show: bool,
    max_markers: int | None = None,
) -> int:
    data, total, truncated = _prepare(df, max_markers)
    if data is None or data.empty:
        return 0

    label = f"Inspecciones Habitable · {len(data):,}".replace(",", ".")
    if truncated:
        label = f"Inspecciones Habitable · {len(data):,}/{total:,}".replace(",", ".")

    fg = folium.FeatureGroup(name=label, show=show)

    if len(data) <= FAST_THRESHOLD:
        cluster = MarkerCluster().add_to(fg)
        for r in data.itertuples(index=False):
            et = str(getattr(r, "etiqueta_n", "SIN") or "SIN").upper()
            color = ETIQUETA_HEX.get(et, "#888888")
            series = pd.Series(r._asdict()) if hasattr(r, "_asdict") else None
            popup = _popup_row(series, "Habitable") if series is not None else "Habitable"
            folium.CircleMarker(
                location=[float(r.lat), float(r.lng)],
                radius=5,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.8,
                weight=1,
                popup=folium.Popup(popup, max_width=300),
            ).add_to(cluster)
    else:
        # Un FastMarkerCluster por color de semáforo (más liviano que 1 a 1 en Python)
        for et, color in ETIQUETA_HEX.items():
            sub = data[data["etiqueta_n"].fillna("SIN").astype(str).str.upper() == et]
            if sub.empty:
                continue
            rows = []
            for r in sub.itertuples(index=False):
                fields = {
                    "Edificio": getattr(r, "nombre_edificacion", ""),
                    "Dirección": getattr(r, "direccion", ""),
                    "Etiqueta": et,
                    "Estado": getattr(r, "estado_n", ""),
                }
                rows.append(
                    [float(r.lat), float(r.lng), _popup_from_dict("Habitable", fields), 5]
                )
            FastMarkerCluster(data=rows, callback=_fast_callback(color)).add_to(fg)

        # Resto sin etiqueta conocida
        known = set(ETIQUETA_HEX)
        other = data[~data["etiqueta_n"].fillna("SIN").astype(str).str.upper().isin(known)]
        if not other.empty:
            rows = [
                [
                    float(r.lat),
                    float(r.lng),
                    _popup_from_dict(
                        "Habitable",
                        {
                            "Edificio": getattr(r, "nombre_edificacion", ""),
                            "Dirección": getattr(r, "direccion", ""),
                        },
                    ),
                    5,
                ]
                for r in other.itertuples(index=False)
            ]
            FastMarkerCluster(data=rows, callback=_fast_callback("#888888")).add_to(fg)

    fg.add_to(fmap)
    return len(data)


def _add_heatmap(
    fmap: folium.Map,
    df: pd.DataFrame,
    *,
    name: str,
    show: bool = False,
) -> None:
    if df is None or df.empty:
        return
    data = df.dropna(subset=["lat", "lng"])
    if data.empty:
        return
    pts = data[["lat", "lng"]].astype(float).values.tolist()
    fg = folium.FeatureGroup(name=name, show=show)
    HeatMap(pts, radius=12, blur=16, max_zoom=15, min_opacity=0.3).add_to(fg)
    fg.add_to(fmap)


def build_map(
    *,
    sol_map: pd.DataFrame,
    hab_map: pd.DataFrame,
    coin: pd.DataFrame,
    solo: pd.DataFrame,
    dud: pd.DataFrame,
    basemap: str,
    view_name: str,
    show_1x10: bool,
    show_hab: bool,
    show_coin: bool,
    show_solo: bool,
    show_dud: bool,
    show_heat_pend: bool,
    show_heat_hab: bool,
    show_extra_basemaps: bool,
    max_markers: int | None = None,
    focus_lat: float | None = None,
    focus_lng: float | None = None,
    focus_zoom: int = 17,
    highlight: pd.DataFrame | None = None,
    show_minimap: bool = False,
) -> folium.Map:
    if focus_lat is not None and focus_lng is not None:
        lat, lng, zoom = float(focus_lat), float(focus_lng), focus_zoom
    else:
        lat, lng, zoom = VIEWS.get(view_name, VIEWS["Caracas / La Guaira"])
    fmap = folium.Map(
        location=[lat, lng],
        zoom_start=zoom,
        tiles=None,
        control_scale=True,
        prefer_canvas=True,
    )

    primary = basemap if basemap in BASEMAPS else "OSM claro (Carto)"
    _tile_layer(primary, show=True).add_to(fmap)

    if show_extra_basemaps:
        for key in BASEMAPS:
            if key == primary:
                continue
            _tile_layer(key, show=False).add_to(fmap)

    # Heatmaps primero (baratos); marcadores después
    if show_heat_pend and show_solo:
        _add_heatmap(fmap, solo, name="Densidad pendientes", show=True)
    if show_heat_hab and show_hab:
        _add_heatmap(fmap, hab_map, name="Densidad inspecciones", show=False)

    if show_hab and not (show_heat_hab and max_markers is not None and max_markers <= 0):
        # Si hay heatmap hab y modo muy agresivo, se puede omitir; normalmente mostramos ambos
        _add_habitable_fast(fmap, hab_map, show=True, max_markers=max_markers)

    if show_coin:
        _add_points_fast(
            fmap,
            coin,
            name="Ya atendidas (1×10∩Habitable)",
            color="#8A2BE2",
            show=True,
            kind="Ya atendida",
            max_markers=max_markers,
        )
    if show_solo:
        _add_points_fast(
            fmap,
            solo,
            name="Pendientes 1×10",
            color="#FF8C00",
            show=True,
            kind="Pendiente",
            max_markers=max_markers,
        )
    if show_1x10:
        _add_points_fast(
            fmap,
            sol_map,
            name="Todas solicitudes 1×10",
            color="#1E90FF",
            show=False,
            kind="Solicitud 1×10",
            max_markers=max_markers,
        )
    if show_dud:
        _add_points_fast(
            fmap,
            dud,
            name="Dudosos (geo cerca, nombre distinto)",
            color="#808080",
            show=True,
            kind="Dudoso",
            max_markers=max_markers,
        )

    if highlight is not None and not highlight.empty:
        hg = folium.FeatureGroup(name="Resultado de búsqueda", show=True)
        for r in highlight.dropna(subset=["lat", "lng"]).itertuples(index=False):
            series = pd.Series(r._asdict()) if hasattr(r, "_asdict") else None
            popup = _popup_row(series, "Búsqueda") if series is not None else "Búsqueda"
            folium.Marker(
                location=[float(r.lat), float(r.lng)],
                popup=folium.Popup(popup, max_width=360),
                tooltip=_esc(getattr(r, "direccion", "Resultado")),
                icon=folium.Icon(color="red", icon="home", prefix="fa"),
            ).add_to(hg)
        hg.add_to(fmap)

    if show_minimap:
        MiniMap(toggle_display=True, position="bottomleft").add_to(fmap)
    MeasureControl(position="topleft").add_to(fmap)
    folium.LayerControl(collapsed=True, position="topright").add_to(fmap)
    return fmap


@st.cache_data(show_spinner="Generando mapa…", ttl=600)
def _cached_map_html(
    *,
    coin_bytes: bytes,
    solo_bytes: bytes,
    dud_bytes: bytes,
    hab_bytes: bytes,
    sol_bytes: bytes,
    highlight_bytes: bytes,
    basemap: str,
    view_name: str,
    show_1x10: bool,
    show_hab: bool,
    show_coin: bool,
    show_solo: bool,
    show_dud: bool,
    show_heat_pend: bool,
    show_heat_hab: bool,
    show_extra_basemaps: bool,
    max_markers: int | None,
    focus_lat: float | None,
    focus_lng: float | None,
    show_minimap: bool,
) -> str:
    """Cachea el HTML del mapa para no regenerar con los mismos filtros."""
    from io import BytesIO

    def read(b: bytes) -> pd.DataFrame:
        if not b:
            return pd.DataFrame()
        return pd.read_parquet(BytesIO(b))

    fmap = build_map(
        sol_map=read(sol_bytes),
        hab_map=read(hab_bytes),
        coin=read(coin_bytes),
        solo=read(solo_bytes),
        dud=read(dud_bytes),
        basemap=basemap,
        view_name=view_name,
        show_1x10=show_1x10,
        show_hab=show_hab,
        show_coin=show_coin,
        show_solo=show_solo,
        show_dud=show_dud,
        show_heat_pend=show_heat_pend,
        show_heat_hab=show_heat_hab,
        show_extra_basemaps=show_extra_basemaps,
        max_markers=max_markers,
        focus_lat=focus_lat,
        focus_lng=focus_lng,
        highlight=read(highlight_bytes) if highlight_bytes else None,
        show_minimap=show_minimap,
    )
    return fmap.get_root().render()


def _df_to_bytes(df: pd.DataFrame | None, cols: list[str] | None = None) -> bytes:
    if df is None or df.empty:
        return b""
    from io import BytesIO

    out = BytesIO()
    use = df
    if cols:
        keep = [c for c in cols if c in df.columns]
        use = df[keep]
    use.to_parquet(out, index=False)
    return out.getvalue()


_SOL_COLS = [
    "lat",
    "lng",
    "direccion",
    "codigo_caso",
    "n_reportes",
    "hab_nombre",
    "estado_n",
    "match_cat",
    "match_dist_m",
]
_HAB_COLS = [
    "lat",
    "lng",
    "nombre_edificacion",
    "direccion",
    "etiqueta_n",
    "estado_n",
]


def render_map_ui(
    sol_map: pd.DataFrame,
    hab_map: pd.DataFrame,
    coin: pd.DataFrame,
    solo: pd.DataFrame,
    dud: pd.DataFrame,
) -> None:
    """Controles compactos del mapa: base/vista + capas + búsqueda."""

    c1, c2, c3 = st.columns([1.2, 1.2, 1.6])
    with c1:
        basemap = st.selectbox(
            "Mapa base",
            options=list(BASEMAPS.keys()),
            index=list(BASEMAPS.keys()).index("OSM claro (Carto)"),
            key="map_op_basemap",
            help="También en el control de capas del mapa.",
        )
    with c2:
        view_name = st.selectbox(
            "Vista",
            list(VIEWS.keys()),
            key="map_op_view",
            help="Encadre al cargar.",
        )
    with c3:
        q = st.text_input(
            "Buscar",
            value="",
            placeholder="Edificio, dirección o código…",
            key="map_op_q",
            help="Centra y marca resultados en rojo.",
        )

    layer_opts = [
        "Habitable",
        "Coincidencias (alta+media)",
        "Solo 1×10 (pendientes)",
        "Dudosos geo",
        "Todas solicitudes 1×10",
    ]
    l1, l2 = st.columns([3, 2])
    with l1:
        layers = st.multiselect(
            "Capas",
            options=layer_opts,
            default=[
                "Habitable",
                "Coincidencias (alta+media)",
                "Solo 1×10 (pendientes)",
            ],
            key="map_op_layers",
            help="Dudosos apagados por defecto. Coincidencias = atendidas.",
        )
    with l2:
        heat_opts = st.multiselect(
            "Densidad",
            options=["Pendientes", "Inspecciones Habitable"],
            default=[],
            key="map_op_heat",
            help="Heatmap opcional.",
        )
    show_hab = "Habitable" in layers
    show_coin = "Coincidencias (alta+media)" in layers
    show_solo = "Solo 1×10 (pendientes)" in layers
    show_dud = "Dudosos geo" in layers
    show_1x10 = "Todas solicitudes 1×10" in layers
    show_heat_pend = "Pendientes" in heat_opts
    show_heat_hab = "Inspecciones Habitable" in heat_opts

    highlight = pd.DataFrame()
    focus_lat = focus_lng = None
    if q.strip():
        tokens = [t.strip() for t in q.strip().split() if t.strip()]
        mask = pd.Series(True, index=sol_map.index)
        text = (
            sol_map.get("direccion", pd.Series("", index=sol_map.index))
            .fillna("")
            .astype(str)
        )
        if "hab_nombre" in sol_map.columns:
            text = text + " " + sol_map["hab_nombre"].fillna("").astype(str)
        if "codigo_caso" in sol_map.columns:
            text = text + " " + sol_map["codigo_caso"].fillna("").astype(str)
        for t in tokens:
            mask &= text.str.contains(t, case=False, na=False, regex=False)
        highlight = sol_map.loc[mask].copy()
        if highlight.empty:
            st.caption(f"Sin resultados para «{q}».")
        else:
            st.caption(
                f"{len(highlight):,} resultado(s) · "
                f"{highlight.iloc[0].get('direccion', '')}".replace(",", ".")
            )
            focus_lat = float(highlight.iloc[0]["lat"])
            focus_lng = float(highlight.iloc[0]["lng"])
            with st.expander("Resultados de búsqueda", expanded=False):
                cols = [
                    c
                    for c in [
                        "codigo_caso",
                        "direccion",
                        "match_cat",
                        "n_reportes",
                        "hab_nombre",
                        "match_dist_m",
                        "estado_n",
                    ]
                    if c in highlight.columns
                ]
                st.dataframe(highlight[cols].head(40), use_container_width=True)

    with st.expander("Extras del mapa", expanded=False):
        show_minimap = st.checkbox("Mini-mapa", value=False, key="map_op_minimap")
        st.caption(
            "Si el mapa tarda, reduce capas o filtra por territorio."
        )

    # Sin tope: todos los puntos del filtro actual
    max_markers = None
    # Siempre cargar todas las bases en el LayerControl del mapa
    show_extra = True

    html = _cached_map_html(
        coin_bytes=_df_to_bytes(coin, _SOL_COLS),
        solo_bytes=_df_to_bytes(solo, _SOL_COLS),
        dud_bytes=_df_to_bytes(dud, _SOL_COLS),
        hab_bytes=_df_to_bytes(hab_map, _HAB_COLS),
        sol_bytes=_df_to_bytes(sol_map if show_1x10 else None, _SOL_COLS),
        highlight_bytes=_df_to_bytes(
            highlight.head(80) if not highlight.empty else None, _SOL_COLS
        ),
        basemap=basemap,
        view_name=view_name,
        show_1x10=show_1x10,
        show_hab=show_hab,
        show_coin=show_coin,
        show_solo=show_solo,
        show_dud=show_dud,
        show_heat_pend=show_heat_pend,
        show_heat_hab=show_heat_hab,
        show_extra_basemaps=show_extra,
        max_markers=max_markers,
        focus_lat=focus_lat,
        focus_lng=focus_lng,
        show_minimap=show_minimap,
    )
    components.html(html, height=640, scrolling=False)

    st.caption(
        "Leyenda: semáforo Habitable · violeta = atendidas · naranja = pendientes · "
        "gris = dudosos · rojo = búsqueda · control de capas / mapas base arriba a la derecha."
    )


# —— Mapa dedicado: 1×10 pendientes por ubicación ——

_PEND_COLS = [
    "lat",
    "lng",
    "direccion",
    "codigo_caso",
    "codigos_casos",
    "codigos_grupo",
    "n_reportes",
    "cantidad_casos",
    "cumulo_casos",
    "estado_n",
    "municipio_n",
    "parroquia_n",
    "estatus_cruce",
]


def _volumen_casos(row) -> int:
    for attr in ("cantidad_casos", "n_reportes"):
        v = getattr(row, attr, None)
        if v is not None and not (isinstance(v, float) and pd.isna(v)):
            try:
                return max(1, int(v))
            except (TypeError, ValueError):
                pass
    return 1


def _color_por_volumen(n: int) -> str:
    """Más reportes → color más intenso (resalta concentraciones)."""
    if n >= 10:
        return "#7F1D1D"  # rojo oscuro
    if n >= 5:
        return "#DC2626"  # rojo
    if n >= 2:
        return "#EA580C"  # naranja fuerte
    return "#F59E0B"  # ámbar (1 caso)


def _radius_por_volumen(n: int) -> float:
    """Radios muy compactos para no tapar localidades del mapa base."""
    if n >= 10:
        return 3.5
    if n >= 5:
        return 2.5
    if n >= 2:
        return 2.0
    return 1.5


def _add_heatmap_weighted(
    fmap: folium.Map,
    df: pd.DataFrame,
    *,
    name: str,
    show: bool = True,
    weight_col: str = "cantidad_casos",
) -> None:
    """Heatmap ponderado por cantidad de casos en la ubicación."""
    if df is None or df.empty:
        return
    data = df.dropna(subset=["lat", "lng"]).copy()
    if data.empty:
        return
    if weight_col not in data.columns and "n_reportes" in data.columns:
        weight_col = "n_reportes"
    if weight_col in data.columns:
        w = pd.to_numeric(data[weight_col], errors="coerce").fillna(1).clip(lower=1)
        pts = [
            [float(la), float(lo), float(ww)]
            for la, lo, ww in zip(data["lat"], data["lng"], w)
        ]
    else:
        pts = data[["lat", "lng"]].astype(float).values.tolist()
    fg = folium.FeatureGroup(name=name, show=show)
    HeatMap(
        pts,
        radius=18,
        blur=22,
        max_zoom=16,
        min_opacity=0.35,
    ).add_to(fg)
    fg.add_to(fmap)


def _add_pendientes_volumen(
    fmap: folium.Map,
    df: pd.DataFrame,
    *,
    show: bool = True,
    max_markers: int | None = None,
) -> int:
    """Círculos por ubicación: tamaño y color según cantidad de casos."""
    data, total, truncated = _prepare(df, max_markers)
    if data is None or data.empty:
        return 0

    label = f"Pendientes por ubicación · {len(data):,}".replace(",", ".")
    if truncated:
        label = f"Pendientes por ubicación · {len(data):,}/{total:,}".replace(",", ".")

    fg = folium.FeatureGroup(name=label, show=show)
    # Sin cluster: el tamaño/color por volumen debe verse; cluster lo ocultaría
    for r in data.itertuples(index=False):
        n = _volumen_casos(r)
        color = _color_por_volumen(n)
        radius = _radius_por_volumen(n)
        codes = getattr(r, "codigos_casos", None) or getattr(r, "codigos_grupo", "")
        fields = {
            "Cúmulo": getattr(r, "cumulo_casos", "")
            or getattr(r, "cantidad_casos", n),
            "Códigos": codes,
            "Dirección": getattr(r, "direccion", ""),
            "Estado": getattr(r, "estado_n", ""),
            "Municipio": getattr(r, "municipio_n", ""),
        }
        popup = _popup_from_dict("1×10 pendiente (ubicación)", fields)
        folium.CircleMarker(
            location=[float(r.lat), float(r.lng)],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.75 if n >= 5 else 0.65,
            weight=1,
            popup=folium.Popup(popup, max_width=360),
            tooltip=f"{n} caso(s) · {_esc(getattr(r, 'direccion', ''))[:60]}",
        ).add_to(fg)
    fg.add_to(fmap)
    return len(data)


def build_pendientes_map(
    *,
    ubicaciones: pd.DataFrame,
    basemap: str,
    view_name: str,
    show_puntos: bool,
    show_heat: bool,
    show_extra_basemaps: bool,
    max_markers: int | None = None,
    focus_lat: float | None = None,
    focus_lng: float | None = None,
    highlight: pd.DataFrame | None = None,
    show_minimap: bool = False,
) -> folium.Map:
    if focus_lat is not None and focus_lng is not None:
        lat, lng, zoom = float(focus_lat), float(focus_lng), 15
    else:
        lat, lng, zoom = VIEWS.get(view_name, VIEWS["Caracas / La Guaira"])
    fmap = folium.Map(
        location=[lat, lng],
        zoom_start=zoom,
        tiles=None,
        control_scale=True,
        prefer_canvas=True,
    )
    primary = basemap if basemap in BASEMAPS else "OSM claro (Carto)"
    _tile_layer(primary, show=True).add_to(fmap)
    if show_extra_basemaps:
        for key in BASEMAPS:
            if key == primary:
                continue
            _tile_layer(key, show=False).add_to(fmap)

    if show_heat:
        _add_heatmap_weighted(
            fmap,
            ubicaciones,
            name="Mapa de calor (concentración de casos)",
            show=True,
        )
    if show_puntos:
        _add_pendientes_volumen(
            fmap,
            ubicaciones,
            show=True,
            max_markers=max_markers,
        )

    if highlight is not None and not highlight.empty:
        hg = folium.FeatureGroup(name="Resultado de búsqueda", show=True)
        for r in highlight.dropna(subset=["lat", "lng"]).itertuples(index=False):
            n = _volumen_casos(r)
            folium.Marker(
                location=[float(r.lat), float(r.lng)],
                popup=folium.Popup(
                    _popup_from_dict(
                        "Búsqueda",
                        {
                            "Cantidad": n,
                            "Códigos": getattr(r, "codigos_casos", "")
                            or getattr(r, "codigos_grupo", ""),
                            "Dirección": getattr(r, "direccion", ""),
                        },
                    ),
                    max_width=360,
                ),
                tooltip=_esc(getattr(r, "direccion", "Resultado")),
                icon=folium.Icon(color="red", icon="home", prefix="fa"),
            ).add_to(hg)
        hg.add_to(fmap)

    if show_minimap:
        MiniMap(toggle_display=True, position="bottomleft").add_to(fmap)
    MeasureControl(position="topleft").add_to(fmap)
    folium.LayerControl(collapsed=True, position="topright").add_to(fmap)
    return fmap


@st.cache_data(show_spinner="Generando mapa de pendientes…", ttl=600)
def _cached_pendientes_map_html(
    *,
    ubic_bytes: bytes,
    highlight_bytes: bytes,
    basemap: str,
    view_name: str,
    show_puntos: bool,
    show_heat: bool,
    show_extra_basemaps: bool,
    max_markers: int | None,
    focus_lat: float | None,
    focus_lng: float | None,
    show_minimap: bool,
) -> str:
    from io import BytesIO

    def read(b: bytes) -> pd.DataFrame:
        if not b:
            return pd.DataFrame()
        return pd.read_parquet(BytesIO(b))

    fmap = build_pendientes_map(
        ubicaciones=read(ubic_bytes),
        basemap=basemap,
        view_name=view_name,
        show_puntos=show_puntos,
        show_heat=show_heat,
        show_extra_basemaps=show_extra_basemaps,
        max_markers=max_markers,
        focus_lat=focus_lat,
        focus_lng=focus_lng,
        highlight=read(highlight_bytes) if highlight_bytes else None,
        show_minimap=show_minimap,
    )
    return fmap.get_root().render()


def render_pendientes_map_ui(ubicaciones: pd.DataFrame) -> None:
    """
    Mapa de 1×10 pendientes agrupados por ubicación.
    Controles compactos para que el mapa quede arriba.
    """
    if ubicaciones is None or ubicaciones.empty:
        st.warning("Sin ubicaciones pendientes para mapear con el filtro actual.")
        return

    work = ubicaciones.dropna(subset=["lat", "lng"]).copy()
    if "mapa_ok" in work.columns:
        # Cinturón de seguridad: nunca pintar mar/dudosos si vienen marcados
        work = work[work["mapa_ok"].fillna(True)]
    if "cantidad_casos" not in work.columns and "n_reportes" in work.columns:
        work["cantidad_casos"] = work["n_reportes"]
    if "cantidad_casos" not in work.columns:
        work["cantidad_casos"] = 1
    if work.empty:
        st.warning(
            "Sin ubicaciones con GPS válido para mapear. "
            "Prueba activar «Incluir GPS en mar / dudosos» o amplía el filtro."
        )
        return

    # Una sola franja de controles (menos scroll hasta el mapa)
    c1, c2, c3, c4 = st.columns([1.2, 1.1, 1.6, 1.4])
    with c1:
        basemap = st.selectbox(
            "Base",
            options=list(BASEMAPS.keys()),
            index=list(BASEMAPS.keys()).index("OSM claro (Carto)"),
            key="pend_basemap",
            label_visibility="collapsed",
            help="Mapa base",
        )
        st.caption("Base")
    with c2:
        view_name = st.selectbox(
            "Vista",
            list(VIEWS.keys()),
            key="pend_view",
            label_visibility="collapsed",
        )
        st.caption("Vista")
    with c3:
        layer_opts = [
            "Puntos por volumen de casos",
            "Mapa de calor (concentración)",
        ]
        layers = st.multiselect(
            "Capas",
            options=layer_opts,
            default=layer_opts,
            key="pend_layers",
            label_visibility="collapsed",
        )
        st.caption("Capas")
    with c4:
        q = st.text_input(
            "Buscar",
            value="",
            placeholder="Dirección o código…",
            key="pend_search",
            label_visibility="collapsed",
        )
        st.caption("Búsqueda")

    show_puntos = "Puntos por volumen de casos" in layers
    show_heat = "Mapa de calor (concentración)" in layers

    highlight = pd.DataFrame()
    focus_lat = focus_lng = None
    if q.strip():
        tokens = [t.strip() for t in q.strip().split() if t.strip()]
        mask = pd.Series(True, index=work.index)
        text = work.get("direccion", pd.Series("", index=work.index)).fillna("").astype(str)
        for col in ("codigos_casos", "codigos_grupo", "codigo_caso"):
            if col in work.columns:
                text = text + " " + work[col].fillna("").astype(str)
        for t in tokens:
            mask &= text.str.contains(t, case=False, na=False, regex=False)
        highlight = work.loc[mask].copy()
        if highlight.empty:
            st.warning(f"Sin resultados para «{q}».")
        else:
            focus_lat = float(highlight.iloc[0]["lat"])
            focus_lng = float(highlight.iloc[0]["lng"])
            st.caption(
                f"{len(highlight):,} resultado(s) · "
                f"{highlight.iloc[0].get('direccion', '')}".replace(",", ".")
            )

    with st.expander("Extras", expanded=False):
        show_minimap = st.checkbox("Mini-mapa", value=False, key="pend_mini")
        st.caption(
            "Leyenda: ámbar=1 · naranja=2–4 · rojo=5–9 · rojo oscuro=10+."
        )

    to_map = work.sort_values("cantidad_casos", ascending=False)
    html = _cached_pendientes_map_html(
        ubic_bytes=_df_to_bytes(to_map, _PEND_COLS),
        highlight_bytes=_df_to_bytes(
            highlight.head(80) if not highlight.empty else None, _PEND_COLS
        ),
        basemap=basemap,
        view_name=view_name,
        show_puntos=show_puntos,
        show_heat=show_heat,
        show_extra_basemaps=True,
        max_markers=None,
        focus_lat=focus_lat,
        focus_lng=focus_lng,
        show_minimap=show_minimap,
    )
    components.html(html, height=640, scrolling=False)
    st.caption(
        f"En mapa: {len(to_map):,} ubicaciones · "
        f"{int(to_map['cantidad_casos'].sum()):,} casos · "
        f"capas/bases arriba a la derecha.".replace(",", ".")
    )
