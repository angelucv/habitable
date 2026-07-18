"""
Mapa operativo del BI (Folium)
==============================

Construye el mapa con:
- Varias bases cartográficas (OSM, Carto, Esri, Topo).
- Capas: Habitable, coincidencias, pendientes, dudosos.
- FastMarkerCluster para volúmenes grandes.
- Búsqueda y marcadores destacados.

``render_map_ui`` es lo que llama ``app.page_mapa``.
"""

from __future__ import annotations

import html as html_lib
from typing import Any

import gc

import folium
from folium.plugins import FastMarkerCluster, HeatMap, MarkerCluster, MeasureControl, MiniMap
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from runtime_limits import heat_max_points, is_low_memory, map_max_markers

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
    max_points: int | None = None,
) -> None:
    if df is None or df.empty:
        return
    data = df.dropna(subset=["lat", "lng"])
    if data.empty:
        return
    cap = max_points if max_points is not None else heat_max_points()
    if len(data) > cap:
        data = data.sample(cap, random_state=42)
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
    show_measure: bool = True,
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

    # Heatmaps primero (livianos); no exigen la capa de marcadores
    if show_heat_pend:
        _add_heatmap(fmap, solo, name="Densidad pendientes", show=True)
    if show_heat_hab:
        _add_heatmap(fmap, hab_map, name="Densidad inspecciones", show=True)

    if show_hab:
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
    if show_measure:
        MeasureControl(position="topleft").add_to(fmap)
    folium.LayerControl(collapsed=True, position="topright").add_to(fmap)
    return fmap


@st.cache_data(show_spinner="Generando mapa…", ttl=300, max_entries=2)
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
    show_measure: bool = True,
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
        show_measure=show_measure,
    )
    html = fmap.get_root().render()
    del fmap
    gc.collect()
    return html


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
    """Controles del mapa agrupados: cartografía → capas → búsqueda → avanzado."""

    # —— Cartografía ——
    from ui_theme import render_section

    low_mem = is_low_memory()
    default_cap = map_max_markers()

    if low_mem:
        st.info(
            "Modo bajo consumo (Render): el mapa limita marcadores por capa y "
            "usa densidad para pendientes. Filtra por estado o sube de plan "
            "si necesitas ver todos los puntos a la vez."
        )

    render_section(
        "Cartografía",
        "Elige mapa base y vista."
        + (
            " En bajo consumo solo se carga la base seleccionada."
            if low_mem
            else " Todas las bases quedan en el control de capas del mapa."
        ),
    )
    c1, c2 = st.columns(2)
    with c1:
        basemap = st.selectbox(
            "Mapa base inicial",
            options=list(BASEMAPS.keys()),
            index=list(BASEMAPS.keys()).index("OSM claro (Carto)"),
            help="OpenStreetMap, Carto, Esri (satélite/calles) y topográfico. "
            "También puedes cambiarlos en el control de capas del mapa (arriba a la derecha).",
        )
    with c2:
        view_name = st.selectbox(
            "Vista inicial",
            list(VIEWS.keys()),
            help="Encadre al cargar. La búsqueda puede recentrar el mapa.",
        )
    if not low_mem:
        st.caption(
            "Cambio de base también disponible en el control de capas del mapa "
            "(arriba a la derecha)."
        )

    # —— Capas de datos ——
    render_section(
        "Capas de datos",
        "Dudosos apagados por defecto. Coincidencias = ya atendidas (alta + media).",
    )
    layer_opts = [
        "Habitable",
        "Coincidencias (alta+media)",
        "Solo 1×10 (pendientes)",
        "Dudosos geo",
        "Todas solicitudes 1×10",
    ]
    # En bajo consumo: marcadores solo Habitable + coincidencias;
    # pendientes van por heatmap (mucho menos RAM).
    default_layers = (
        ["Habitable", "Coincidencias (alta+media)"]
        if low_mem
        else [
            "Habitable",
            "Coincidencias (alta+media)",
            "Solo 1×10 (pendientes)",
        ]
    )
    layers = st.multiselect(
        "Qué mostrar en el mapa (marcadores)",
        options=layer_opts,
        default=default_layers,
        help="Como en el mockup: Dudosos apagados por defecto. "
        "Coincidencias = ya atendidas (match alta+media).",
    )
    show_hab = "Habitable" in layers
    show_coin = "Coincidencias (alta+media)" in layers
    show_solo = "Solo 1×10 (pendientes)" in layers
    show_dud = "Dudosos geo" in layers
    show_1x10 = "Todas solicitudes 1×10" in layers

    heat_opts = st.multiselect(
        "Densidad (heatmap)",
        options=["Pendientes", "Inspecciones Habitable"],
        default=["Pendientes"] if low_mem else [],
        help="Capa de densidad (liviana). No requiere activar marcadores de la misma capa.",
    )
    show_heat_pend = "Pendientes" in heat_opts
    show_heat_hab = "Inspecciones Habitable" in heat_opts

    st.caption(
        f"Selección → Habitable {len(hab_map):,} · "
        f"Coincidencias {len(coin):,} · Solo 1×10 {len(solo):,} · "
        f"Dudosos {len(dud):,} · Todas 1×10 {len(sol_map):,}".replace(",", ".")
    )

    # —— Búsqueda ——
    render_section("Búsqueda", "Centra el mapa y marca resultados.")
    q = st.text_input(
        "Edificio o dirección",
        value="",
        placeholder="Ej. Cattleya, Samanes, Andrés Bello",
        help="Centra el mapa y marca resultados en rojo.",
        label_visibility="collapsed",
    )
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
            st.warning(f"Sin resultados para «{q}» en el filtro actual.")
        else:
            st.success(
                f"{len(highlight):,} resultado(s). "
                f"Primero: {highlight.iloc[0].get('direccion', '')}".replace(",", ".")
            )
            focus_lat = float(highlight.iloc[0]["lat"])
            focus_lng = float(highlight.iloc[0]["lng"])
            with st.expander("Ver resultados de búsqueda"):
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

    # —— Extras ——
    with st.expander("Extras del mapa", expanded=False):
        show_minimap = st.checkbox("Mini-mapa", value=False)
        if low_mem or default_cap is not None:
            cap_ui = st.number_input(
                "Máx. marcadores por capa",
                min_value=200,
                max_value=8000,
                value=int(default_cap or 900),
                step=100,
                help="Baja este valor si el servicio se reinicia por memoria.",
            )
            max_markers = int(cap_ui)
        else:
            max_markers = None
            st.caption(
                "Sin tope de marcadores. Si el mapa tarda, filtra por estado "
                "o activa modo bajo consumo (BI_LOW_MEMORY=1)."
            )
        show_extra = st.checkbox(
            "Cargar todos los mapas base en el control de capas",
            value=not low_mem,
        )
        show_measure = st.checkbox(
            "Herramienta de medición",
            value=not low_mem,
        )

    html = _cached_map_html(
        coin_bytes=_df_to_bytes(coin, _SOL_COLS),
        solo_bytes=_df_to_bytes(solo, _SOL_COLS),
        dud_bytes=_df_to_bytes(dud, _SOL_COLS),
        hab_bytes=_df_to_bytes(hab_map, _HAB_COLS),
        sol_bytes=_df_to_bytes(sol_map if show_1x10 else None, _SOL_COLS),
        highlight_bytes=_df_to_bytes(
            highlight.head(40) if not highlight.empty else None, _SOL_COLS
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
        show_measure=show_measure,
    )
    components.html(html, height=640, scrolling=False)
    del html
    gc.collect()

    cap_note = (
        f" Tope {max_markers} marcadores/capa."
        if max_markers
        else ""
    )
    st.caption(
        "Leyenda: semáforo Habitable · violeta = atendidas · naranja = pendientes · "
        "gris = dudosos · rojo = búsqueda · control de capas / mapas base arriba a la derecha."
        + cap_note
    )
