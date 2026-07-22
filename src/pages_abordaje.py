"""Mapas de abordaje — capas GIS lite (planificación territorial)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import folium
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parents[1]
GIS_LITE = ROOT / "data" / "gis_lite"

VIEWS = {
    "Caracas / La Guaira": (10.50, -66.92, 11),
    "Gran Caracas": (10.45, -66.90, 10),
    "Petare (cuadrícula)": (10.47, -66.80, 13),
    "La Guaira (bloques)": (10.60, -66.93, 12),
    "Nacional (norte VE)": (10.4, -67.5, 7),
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

# Capas GIS: por defecto APAGADAS (no tapan puntos del cruce).
# Relleno muy suave; el detalle sale al pasar el mouse (hover), no como mancha permanente.
LAYER_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "id": "mascara_altagracia",
        "label": "Máscara Altagracia",
        "group": "Máscaras parroquiales",
        "default": False,
        "heavy": False,
        "color": "#2563EB",
        "fill_opacity": 0.04,
        "tooltip": ["Parroquia", "Municipio", "ENTIDAD", "Estado"],
    },
    {
        "id": "mascara_san_bernardino",
        "label": "Máscara San Bernardino",
        "group": "Máscaras parroquiales",
        "default": False,
        "heavy": False,
        "color": "#7C3AED",
        "fill_opacity": 0.04,
        "tooltip": ["Parroquia", "Municipio", "ENTIDAD", "Estado"],
    },
    {
        "id": "mascara_san_jose",
        "label": "Máscara San José",
        "group": "Máscaras parroquiales",
        "default": False,
        "heavy": False,
        "color": "#DB2777",
        "fill_opacity": 0.04,
        "tooltip": ["Parroquia", "Municipio", "ENTIDAD", "Estado"],
    },
    {
        "id": "mascara_petare",
        "label": "Máscara Petare",
        "group": "Máscaras parroquiales",
        "default": False,
        "heavy": False,
        "color": "#0891B2",
        "fill_opacity": 0.04,
        "tooltip": ["Parroquia", "Municipio", "Estado"],
    },
    {
        "id": "cuadricula_petare",
        "label": "Cuadrícula Petare (36 celdas · ~1 km)",
        "group": "Cuadrículas / bloques",
        "default": False,
        "heavy": False,
        "color": "#0F766E",
        "fill_opacity": 0.03,
        "tooltip": ["id", "row_index", "col_index"],
    },
    {
        "id": "cuadricula_abordaje",
        "label": "Cuadrícula GPKG (6 celdas · recorte)",
        "group": "Cuadrículas / bloques",
        "default": False,
        "heavy": False,
        "color": "#115E59",
        "fill_opacity": 0.03,
        "tooltip": ["id", "row_index", "col_index"],
    },
    {
        "id": "bloques_la_guaira",
        "label": "Bloques La Guaira (~85 · ~600 m)",
        "group": "Cuadrículas / bloques",
        "default": False,
        "heavy": False,
        "color": "#C2410C",
        "fill_opacity": 0.05,
        "tooltip": ["BLOQUE", "SECTOR", "ZONA", "NOM_MAPA"],
    },
    {
        "id": "microzonas_amenaza",
        "label": "Microzonas — amenaza general",
        "group": "Microzonificación sísmica",
        "default": False,
        "heavy": False,
        "color": "#B45309",
        "fill_opacity": 0.04,
        "tooltip": ["Name"],
    },
    {
        "id": "microzonas_laderas",
        "label": "Microzonas — laderas",
        "group": "Microzonificación sísmica",
        "default": False,
        "heavy": False,
        "color": "#CA8A04",
        "fill_opacity": 0.04,
        "tooltip": ["Name"],
    },
    {
        "id": "microzonas_sedimentos",
        "label": "Microzonas — sedimentos",
        "group": "Microzonificación sísmica",
        "default": False,
        "heavy": False,
        "color": "#65A30D",
        "fill_opacity": 0.04,
        "tooltip": ["Name"],
    },
    {
        "id": "puntos_db",
        "label": "Puntos de campo (paquete abordaje)",
        "group": "Puntos del paquete GIS",
        "default": False,
        "heavy": False,
        "color": "#1D4ED8",
        "kind": "points",
        "tooltip": ["NOMBRE DE", "ETIQUETA", "SECTOR", "MUNICIPIO", "ESTADO"],
    },
    {
        "id": "parroquias",
        "label": "Parroquias (capa base)",
        "group": "Territorio (pesadas)",
        "default": False,
        "heavy": True,
        "color": "#475569",
        "fill_opacity": 0.02,
        "tooltip": ["Parroquia", "Municipio", "Estado"],
    },
    {
        "id": "parroquias_ine_2025",
        "label": "Parroquias INE 2025",
        "group": "Territorio (pesadas)",
        "default": False,
        "heavy": True,
        "color": "#334155",
        "fill_opacity": 0.02,
        "tooltip": ["Parroquia", "Municipio", "ENTIDAD"],
    },
    {
        "id": "segmentos_censales",
        "label": "Segmentos censales (~28 mil)",
        "group": "Territorio (pesadas)",
        "default": False,
        "heavy": True,
        "color": "#64748B",
        "fill_opacity": 0.02,
        "tooltip": ["COD_SEG", "NOM_PARROQ", "NOM_MUNICI", "NOM_ENTIDA"],
    },
)


def _layer_path(stem: str) -> Path | None:
    """Prefiere GeoJSON (sin geopandas en producción); parquet solo como respaldo."""
    for name in (f"{stem}.geojson", f"{stem}.geojson.zip", f"{stem}.parquet"):
        p = GIS_LITE / name
        if p.exists():
            return p
    return None


@st.cache_data(show_spinner="Cargando capa GIS…", ttl=3600)
def _load_geojson_dict(stem: str) -> dict | None:
    path = _layer_path(stem)
    if path is None:
        return None

    # .geojson.zip — liviano y sin dependencias GIS nativas
    if path.name.endswith(".geojson.zip"):
        import zipfile

        with zipfile.ZipFile(path) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(".geojson")]
            if not names:
                return None
            return json.loads(zf.read(names[0]).decode("utf-8"))

    if path.suffix.lower() == ".geojson":
        return json.loads(path.read_text(encoding="utf-8"))

    # Parquet solo si geopandas está instalado (local / opcional)
    if path.suffix.lower() == ".parquet":
        try:
            import geopandas as gpd
        except ImportError:
            return None
        gdf = gpd.read_parquet(path)
        if gdf.crs is None:
            gdf = gdf.set_crs(4326)
        else:
            gdf = gdf.to_crs(4326)
        return json.loads(gdf.to_json())

    return None


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


def _style_fn(color: str, fill_opacity: float, *, outline_only: bool = False):
    fill = 0.0 if outline_only else fill_opacity

    def _style(_feature):
        return {
            "fillColor": color,
            "color": color,
            "weight": 1.0,
            "fillOpacity": fill,
            "opacity": 0.75,
        }

    return _style


def _highlight_fn(color: str):
    """Resalta la zona solo al pasar el mouse (no tapa de forma permanente)."""

    def _hi(_feature):
        return {
            "fillColor": color,
            "color": color,
            "weight": 2.5,
            "fillOpacity": 0.22,
            "opacity": 0.95,
        }

    return _hi


def _tooltip_fields(props: dict, keys: list[str]) -> str:
    parts = []
    for k in keys:
        if k in props and props[k] not in (None, "", "null"):
            parts.append(f"<b>{k}</b>: {props[k]}")
    return "<br/>".join(parts) if parts else ""


def _fmt_popup(title: str, fields: dict[str, Any]) -> str:
    """Popup HTML con fuente y detalle (omite vacíos)."""
    import html as html_lib
    import pandas as pd

    parts = [f"<b>{html_lib.escape(str(title))}</b>"]
    for lab, val in fields.items():
        if val is None:
            continue
        if isinstance(val, float) and pd.isna(val):
            continue
        s = str(val).strip()
        if s in ("", "nan", "None", "<NA>"):
            continue
        if lab.lower().startswith("dist") and s.replace(".", "", 1).isdigit():
            try:
                s = f"{float(s):.0f} m"
            except ValueError:
                pass
        parts.append(f"<b>{html_lib.escape(str(lab))}</b>: {html_lib.escape(s)}")
    return "<br/>".join(parts)


def _codigos_punto(r) -> str:
    for attr in ("codigos_casos", "codigos_grupo", "codigo_caso"):
        v = getattr(r, attr, None)
        if v is None:
            continue
        s = str(v).strip()
        if s and s.lower() not in ("nan", "none"):
            return s
    return ""


def _match_label(cat: str) -> str:
    return {
        "solo_1x10": "Pendiente — solo en 1×10",
        "coincide_alta": "Atendida — coincidencia alta",
        "coincide_media": "Atendida — coincidencia media",
        "coincide_geo_solo": "Por revisar — cerca en mapa",
        "no_mapeable": "Sin GPS / no mapeable",
    }.get(str(cat or ""), str(cat or "—"))


def _enrich_hab_con_1x10(hab, sol):
    """Añade columnas x10_* a Habitable según cruce (hab_id)."""
    import pandas as pd

    if hab is None or not isinstance(hab, pd.DataFrame) or hab.empty:
        return hab
    out = hab.copy()
    out["x10_en_demanda"] = "No"
    out["x10_n_casos"] = 0
    out["x10_codigos"] = ""
    out["x10_match"] = ""

    if sol is None or not isinstance(sol, pd.DataFrame) or sol.empty:
        return out
    if "hab_id" not in sol.columns or "id" not in out.columns:
        return out

    link = sol.copy()
    link["_hid"] = link["hab_id"].astype(str).str.strip()
    link = link[link["_hid"].ne("") & link["_hid"].str.lower().ne("nan")]
    if link.empty:
        return out

    # Preferir representantes / códigos de grupo
    def _agg(g: pd.DataFrame) -> pd.Series:
        codes = []
        for col in ("codigos_grupo", "codigo_caso"):
            if col in g.columns:
                for v in g[col].dropna().astype(str):
                    v = v.strip()
                    if v and v.lower() != "nan":
                        codes.append(v)
        # unique preserve order
        seen = set()
        uniq = []
        for c in codes:
            for part in [p.strip() for p in c.replace("|", ",").split(",")]:
                if part and part not in seen:
                    seen.add(part)
                    uniq.append(part)
        n = int(g["n_reportes"].fillna(1).sum()) if "n_reportes" in g.columns else len(g)
        if "n_reportes" in g.columns and "es_representante" in g.columns:
            reps = g[g["es_representante"].fillna(False)]
            if not reps.empty:
                n = int(reps["n_reportes"].fillna(1).sum())
        cats = (
            g["match_cat"].dropna().astype(str).unique().tolist()
            if "match_cat" in g.columns
            else []
        )
        return pd.Series(
            {
                "x10_n_casos": n,
                "x10_codigos": " | ".join(uniq[:12])
                + (" …" if len(uniq) > 12 else ""),
                "x10_match": ", ".join(_match_label(c) for c in cats[:3]),
            }
        )

    agg = link.groupby("_hid", sort=False).apply(_agg, include_groups=False)
    if agg.empty:
        return out

    out["_hid"] = out["id"].astype(str).str.strip()
    out = out.drop(columns=["x10_n_casos", "x10_codigos", "x10_match"], errors="ignore")
    out = out.merge(agg, left_on="_hid", right_index=True, how="left")
    out["x10_n_casos"] = out["x10_n_casos"].fillna(0).astype(int)
    out["x10_codigos"] = out["x10_codigos"].fillna("")
    out["x10_match"] = out["x10_match"].fillna("")
    out["x10_en_demanda"] = out["x10_n_casos"].gt(0).map({True: "Sí", False: "No"})
    out = out.drop(columns=["_hid"], errors="ignore")
    return out


def _build_map(
    selected_ids: tuple[str, ...],
    basemap: str,
    view_name: str,
    *,
    solo_bytes: bytes = b"",
    coin_bytes: bytes = b"",
    hab_bytes: bytes = b"",
    show_solo: bool = False,
    show_coin: bool = False,
    show_hab: bool = False,
    zone_mode: str = "contorno",
) -> str:
    from io import BytesIO

    import pandas as pd

    from map_robust import (
        ETIQUETA_HEX,
        _color_por_volumen,
        _radius_por_volumen,
        _volumen_casos,
    )

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
        if key == basemap:
            continue
        m.add_child(_tile_layer(key, show=False))

    catalog = {c["id"]: c for c in LAYER_CATALOG}
    for lid in selected_ids:
        meta = catalog.get(lid)
        if not meta:
            continue
        data = _load_geojson_dict(lid)
        if not data or not data.get("features"):
            continue

        tip_keys = meta.get("tooltip") or []
        color = meta["color"]
        name = meta["label"]
        kind = meta.get("kind", "polygon")

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
                popup = _fmt_popup(
                    "Fuente: paquete MAPAS ABORDAJE",
                    {
                        "Capa": name,
                        **{k: props.get(k) for k in tip_keys},
                    },
                )
                folium.CircleMarker(
                    location=[coords[1], coords[0]],
                    radius=1.5,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.7,
                    weight=1,
                    tooltip=folium.Tooltip(tip) if tip else None,
                    popup=folium.Popup(popup, max_width=360),
                ).add_to(fg)
            fg.add_to(m)
        else:
            sample_props = (
                (data["features"][0].get("properties") or {}) if data["features"] else {}
            )
            fields = [k for k in tip_keys if k in sample_props and k.lower() != "description"]
            outline_only = zone_mode == "contorno"
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
                gj_kwargs["tooltip"] = folium.GeoJsonTooltip(
                    fields=fields,
                    aliases=fields,
                    sticky=False,
                    labels=True,
                    style=(
                        "background-color:white;border:1px solid #ccc;"
                        "border-radius:4px;padding:6px;font-size:12px;"
                    ),
                )
            folium.GeoJson(data, **gj_kwargs).add_to(m)

    def _read(b: bytes) -> pd.DataFrame:
        if not b:
            return pd.DataFrame()
        return pd.read_parquet(BytesIO(b))

    solo = _read(solo_bytes)
    coin = _read(coin_bytes)
    hab = _read(hab_bytes)

    # Pendientes 1×10 — mismo tamaño compacto + popup enriquecido
    if show_solo and not solo.empty:
        if "cantidad_casos" not in solo.columns and "n_reportes" in solo.columns:
            solo = solo.copy()
            solo["cantidad_casos"] = solo["n_reportes"]
        fg = folium.FeatureGroup(
            name=f"1×10 pendientes · {len(solo):,}".replace(",", "."),
            show=True,
        )
        for r in solo.dropna(subset=["lat", "lng"]).itertuples(index=False):
            n = _volumen_casos(r)
            color = _color_por_volumen(n)
            radius = _radius_por_volumen(n)
            dir_show = getattr(r, "direccion_display", None) or getattr(
                r, "direccion", ""
            )
            popup = _fmt_popup(
                "Fuente: 1×10 (pendiente)",
                {
                    "Estado cruce": _match_label(getattr(r, "match_cat", "solo_1x10")),
                    "Casos en ubicación": n,
                    "Códigos 1×10": _codigos_punto(r),
                    "Dirección": dir_show,
                    "Estado": getattr(r, "estado_n", ""),
                    "Municipio": getattr(r, "municipio_n", ""),
                    "Parroquia": getattr(r, "parroquia_n", ""),
                    "En Habitable": "No (aún sin cruce)",
                },
            )
            tip = f"{n} caso(s) · 1×10 · {str(dir_show)[:50]}"
            folium.CircleMarker(
                location=[float(r.lat), float(r.lng)],
                radius=radius,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.75 if n >= 5 else 0.65,
                weight=1,
                popup=folium.Popup(popup, max_width=380),
                tooltip=tip,
            ).add_to(fg)
        fg.add_to(m)

    if show_coin and not coin.empty:
        fg = folium.FeatureGroup(
            name=f"1×10 atendidas · {len(coin):,}".replace(",", "."),
            show=True,
        )
        for r in coin.dropna(subset=["lat", "lng"]).itertuples(index=False):
            n = _volumen_casos(r)
            radius = _radius_por_volumen(n)
            dist = getattr(r, "match_dist_m", None)
            popup = _fmt_popup(
                "Fuente: 1×10 + Habitable (cruzado)",
                {
                    "Estado cruce": _match_label(getattr(r, "match_cat", "")),
                    "Casos 1×10": n,
                    "Códigos 1×10": _codigos_punto(r),
                    "Dirección 1×10": getattr(r, "direccion_display", None)
                    or getattr(r, "direccion", ""),
                    "Edificio Habitable": getattr(r, "hab_nombre", ""),
                    "Id Habitable": getattr(r, "hab_id", ""),
                    "Semáforo Habitable": getattr(r, "hab_etiqueta", ""),
                    "Distancia cruce": dist,
                    "Estado": getattr(r, "estado_n", ""),
                    "Municipio": getattr(r, "municipio_n", ""),
                },
            )
            tip = f"Atendida · {n} caso(s) · {_codigos_punto(r)[:40]}"
            folium.CircleMarker(
                location=[float(r.lat), float(r.lng)],
                radius=radius,
                color="#7C3AED",
                fill=True,
                fill_color="#7C3AED",
                fill_opacity=0.7,
                weight=1,
                popup=folium.Popup(popup, max_width=380),
                tooltip=tip,
            ).add_to(fg)
        fg.add_to(m)

    if show_hab and not hab.empty:
        fg = folium.FeatureGroup(
            name=f"Habitable semáforo · {len(hab):,}".replace(",", "."),
            show=True,
        )
        for r in hab.dropna(subset=["lat", "lng"]).itertuples(index=False):
            et = str(getattr(r, "etiqueta_n", "SIN") or "SIN").upper()
            color = ETIQUETA_HEX.get(et, "#888888")
            en_x10 = str(getattr(r, "x10_en_demanda", "No") or "No")
            n_x10 = int(getattr(r, "x10_n_casos", 0) or 0)
            popup = _fmt_popup(
                "Fuente: Habitable (inspección)",
                {
                    "Id inspección": getattr(r, "id", ""),
                    "Semáforo": et,
                    "Edificio": getattr(r, "nombre_edificacion", ""),
                    "Dirección": getattr(r, "direccion", ""),
                    "Estado": getattr(r, "estado_n", ""),
                    "Municipio": getattr(r, "municipio_n", ""),
                    "Parroquia": getattr(r, "parroquia_n", ""),
                    "¿Aparece en 1×10?": en_x10
                    + (f" ({n_x10} caso(s))" if n_x10 else ""),
                    "Códigos 1×10": getattr(r, "x10_codigos", ""),
                    "Tipo de cruce": getattr(r, "x10_match", ""),
                },
            )
            tip = f"Habitable {et} · 1×10: {en_x10}"
            folium.CircleMarker(
                location=[float(r.lat), float(r.lng)],
                radius=1.5,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7,
                weight=1,
                popup=folium.Popup(popup, max_width=380),
                tooltip=tip,
            ).add_to(fg)
        fg.add_to(m)

    folium.LayerControl(collapsed=True, position="topright").add_to(m)
    return m.get_root().render()


def _prep_sol_geo(sol) -> Any:
    """Solicitudes mapeables, GPS ok, representantes si aplica."""
    import pandas as pd

    if sol is None or not isinstance(sol, pd.DataFrame) or sol.empty:
        return sol.iloc[0:0] if sol is not None else pd.DataFrame()
    out = sol
    if "mapeable" in out.columns:
        out = out[out["mapeable"].fillna(False)]
    if "mapa_ok" in out.columns:
        out = out[out["mapa_ok"].fillna(False)]
    if "es_representante" in out.columns:
        out = out[out["es_representante"].fillna(True)]
    return out


def _prep_hab_geo(hab) -> Any:
    import pandas as pd

    if hab is None or not isinstance(hab, pd.DataFrame) or hab.empty:
        return hab.iloc[0:0] if hab is not None else pd.DataFrame()
    out = hab
    if "alta_confianza" in out.columns:
        out = out[out["alta_confianza"].fillna(False)]
    elif "mapeable" in out.columns:
        out = out[out["mapeable"].fillna(False)]
    return out


def page_abordaje(
    sol=None,
    hab=None,
    summary: dict | None = None,
    sub: str = "abordaje_capas",
) -> None:
    """Capas GIS de abordaje + puntos del cruce, o descarga del cruce territorial."""
    if sub == "abordaje_descarga":
        _render_abordaje_descarga(sol, summary)
        return
    _render_abordaje_mapa(sol, hab, summary)


def _render_abordaje_descarga(sol=None, summary: dict | None = None) -> None:
    """Pestaña: generar Excel/CSV 1×10 × capas GIS + estado Habitable."""
    import io

    import pandas as pd
    import streamlit as st

    from abordaje_export import EXPORT_LAYER_SPECS, construir_cruce_1x10_capas
    from ui_theme import render_section

    render_section(
        "Descargar cruce territorial",
        "Listado de casos 1×10 con cruce a las capas de Mapas de abordaje "
        "(máscaras, cuadrículas, microzonas, parroquias INE, segmentos censales) "
        "y el estado de inspección Habitable cuando hay match.",
    )
    if summary:
        st.caption(
            f"Corte cruce BI · {summary.get('corte_generado_en', '—')} · "
            f"radio {summary.get('radius_m', 50)} m"
        )

    available = []
    missing = []
    for spec in EXPORT_LAYER_SPECS:
        if _layer_path(spec["id"]) is not None:
            available.append(spec)
        else:
            missing.append(spec["label"])
    if missing:
        st.warning("Capas no encontradas en disco: " + ", ".join(missing))
    if not available:
        st.error("No hay capas GIS disponibles para el cruce.")
        return

    default_ids = [
        s["id"] for s in available if not s.get("heavy")
    ]
    # Incluir parroquias INE por defecto si existe
    for prefer in ("parroquias_ine_2025", "parroquias"):
        if any(s["id"] == prefer for s in available) and prefer not in default_ids:
            default_ids.append(prefer)

    labels = {
        s["id"]: f"{s['label']}" + (" · pesada" if s.get("heavy") else "")
        for s in available
    }
    sel = st.multiselect(
        "Capas a cruzar",
        options=[s["id"] for s in available],
        default=default_ids,
        format_func=lambda i: labels.get(i, i),
        key="abordaje_export_layers",
        help="Los segmentos censales (~28 mil polígonos) pueden tardar más.",
    )
    c1, c2 = st.columns(2)
    with c1:
        solo_rep = st.checkbox(
            "Solo ubicaciones representantes (dedupe)",
            value=True,
            key="abordaje_export_rep",
        )
    with c2:
        solo_map = st.checkbox(
            "Solo puntos mapeables / GPS ok",
            value=True,
            key="abordaje_export_mapok",
        )

    if not sel:
        st.info("Seleccione al menos una capa.")
        return

    if st.button(
        "Generar cruce y preparar descarga",
        type="primary",
        key="abordaje_export_run",
    ):
        with st.spinner("Cruzando puntos 1×10 con las capas seleccionadas…"):
            try:
                df, meta = construir_cruce_1x10_capas(
                    sol if isinstance(sol, pd.DataFrame) else pd.DataFrame(),
                    layer_ids=list(sel),
                    solo_mapeables=solo_map,
                    solo_representantes=solo_rep,
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"No se pudo generar el cruce: {exc}")
                return
        st.session_state["abordaje_export_df"] = df
        st.session_state["abordaje_export_meta"] = meta

    df = st.session_state.get("abordaje_export_df")
    meta = st.session_state.get("abordaje_export_meta") or {}
    if not isinstance(df, pd.DataFrame) or df.empty:
        st.caption("Pulse el botón para materializar el archivo de descarga.")
        return

    st.success(
        f"Listo · {len(df):,} filas".replace(",", ".")
        + (
            f" · capas faltantes: {', '.join(meta.get('capas_faltantes') or [])}"
            if meta.get("capas_faltantes")
            else ""
        )
    )
    if meta.get("capas"):
        rows = [
            {
                "Capa": v.get("label"),
                "Con match": v.get("n_con_match"),
                "%": v.get("pct"),
            }
            for v in meta["capas"].values()
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    st.dataframe(df.head(200), hide_index=True, width="stretch", height=360)
    st.caption("Vista previa (200 filas). El archivo completo va en la descarga.")

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="cruce_1x10_capas", index=False)
        pd.DataFrame(
            [
                {"clave": k, "valor": str(v)}
                for k, v in {
                    "n_puntos": meta.get("n_puntos"),
                    "capas": list((meta.get("capas") or {}).keys()),
                    "faltantes": meta.get("capas_faltantes"),
                }.items()
            ]
        ).to_excel(writer, sheet_name="meta", index=False)
    st.download_button(
        "Descargar Excel del cruce territorial",
        data=buf.getvalue(),
        file_name="cruce_1x10_capas_abordaje.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        key="abordaje_export_dl_xlsx",
    )
    st.download_button(
        "Descargar CSV",
        data=df.to_csv(index=False).encode("utf-8-sig"),
        file_name="cruce_1x10_capas_abordaje.csv",
        mime="text/csv",
        key="abordaje_export_dl_csv",
    )


def _render_abordaje_mapa(
    sol=None,
    hab=None,
    summary: dict | None = None,
) -> None:
    """Capas GIS de abordaje + puntos del cruce (pendientes y semáforo)."""
    import pandas as pd

    from map_robust import _df_to_bytes

    st.caption(
        "Capas de planificación (MAPAS ABORDAJE) con los puntos del BI: "
        "pendientes 1×10 y Habitable por semáforo."
    )
    if summary:
        st.caption(
            f"Radio cruce {summary.get('radius_m', 50)} m · "
            f"unificación {summary.get('dedupe_radius_m', 10)} m"
        )

    if not GIS_LITE.exists():
        st.error(
            "No se encontró `data/gis_lite/`. Genera las capas con el script de conversión."
        )
        return

    manifest_path = GIS_LITE / "manifest.json"
    if manifest_path.exists():
        try:
            man = json.loads(manifest_path.read_text(encoding="utf-8"))
            st.caption(
                f"GIS lite · preset **{man.get('preset', '—')}** · "
                f"~{man.get('total_parquet_mb', '?')} MB parquet"
            )
        except Exception:
            pass

    sol_geo = _prep_sol_geo(sol)
    hab_geo = _enrich_hab_con_1x10(_prep_hab_geo(hab), sol)
    solo = (
        sol_geo[sol_geo["match_cat"] == "solo_1x10"]
        if isinstance(sol_geo, pd.DataFrame)
        and not sol_geo.empty
        and "match_cat" in sol_geo.columns
        else pd.DataFrame()
    )
    coin = (
        sol_geo[sol_geo["match_cat"].isin(["coincide_alta", "coincide_media"])]
        if isinstance(sol_geo, pd.DataFrame)
        and not sol_geo.empty
        and "match_cat" in sol_geo.columns
        else pd.DataFrame()
    )

    # Controles principales
    c1, c2, c3 = st.columns([1.2, 1.2, 2])
    with c1:
        basemap = st.selectbox(
            "Mapa base",
            options=list(BASEMAPS.keys()),
            index=0,
            key="abordaje_basemap",
        )
    with c2:
        view_name = st.selectbox(
            "Vista inicial",
            options=list(VIEWS.keys()),
            index=0,
            key="abordaje_view",
        )
    with c3:
        st.markdown("##### Puntos del cruce BI")
        show_solo = st.checkbox(
            f"1×10 pendientes ({len(solo):,})".replace(",", "."),
            value=True,
            key="abordaje_show_solo",
            help="Ubicaciones 1×10 sin cruce Habitable (representantes, GPS ok).",
        )
        show_hab = st.checkbox(
            f"Habitable semáforo ({len(hab_geo):,})".replace(",", "."),
            value=True,
            key="abordaje_show_hab",
            help="Inspecciones con color VERDE / AMARILLO / ROJO / NEGRO.",
        )
        show_coin = st.checkbox(
            f"1×10 atendidas ({len(coin):,})".replace(",", "."),
            value=False,
            key="abordaje_show_coin",
            help="Coincidencia alta/media con Habitable.",
        )

    zone_mode = st.radio(
        "Estilo de zonas GIS (máscaras / microzonas / cuadrículas)",
        options=["contorno", "suave", "relleno"],
        index=0,
        horizontal=True,
        key="abordaje_zone_mode",
        help=(
            "Contorno = solo borde (recomendado). "
            "Suave = relleno muy liviano. "
            "Relleno = más visible. "
            "En todos los modos, al pasar el mouse se resalta la zona."
        ),
        format_func=lambda x: {
            "contorno": "Solo contorno",
            "suave": "Relleno suave",
            "relleno": "Relleno marcado",
        }.get(x, x),
    )

    available = []
    missing = []
    for meta in LAYER_CATALOG:
        if _layer_path(meta["id"]) is not None:
            available.append(meta)
        else:
            missing.append(meta["label"])

    if missing:
        st.warning("Capas GIS no encontradas: " + ", ".join(missing))

    by_group: dict[str, list[dict]] = {}
    for meta in available:
        by_group.setdefault(meta["group"], []).append(meta)

    selected: list[str] = []
    with st.expander(
        "Capas GIS de abordaje (apagadas por defecto — actívalas solo si las necesitas)",
        expanded=False,
    ):
        st.caption(
            "Las zonas se dibujan como contorno/hover para no tapar los puntos del cruce."
        )
        for group, items in by_group.items():
            st.markdown(f"**{group}**")
            if group == "Territorio (pesadas)":
                st.caption("Muchos polígonos: la primera carga puede demorar.")
            cols = st.columns(2)
            for i, meta in enumerate(items):
                with cols[i % 2]:
                    heavy = " · pesada" if meta.get("heavy") else ""
                    on = st.checkbox(
                        f"{meta['label']}{heavy}",
                        value=bool(meta.get("default")),
                        key=f"abordaje_ly2_{meta['id']}",
                    )
                    if on:
                        selected.append(meta["id"])

    if not selected and not (show_solo or show_hab or show_coin):
        st.info("Activa al menos una capa GIS o una capa de puntos del cruce.")
        return

    heavy_on = [
        m["label"] for m in available if m["id"] in selected and m.get("heavy")
    ]
    if heavy_on:
        st.warning(
            "Capas pesadas activas: "
            + ", ".join(heavy_on)
            + ". La primera carga puede demorar."
        )

    sol_cols = [
        "lat",
        "lng",
        "direccion",
        "direccion_display",
        "codigo_caso",
        "codigos_casos",
        "codigos_grupo",
        "n_reportes",
        "cantidad_casos",
        "cumulo_casos",
        "hab_nombre",
        "hab_id",
        "hab_etiqueta",
        "estado_n",
        "municipio_n",
        "parroquia_n",
        "match_cat",
        "match_dist_m",
    ]
    hab_cols = [
        "lat",
        "lng",
        "id",
        "nombre_edificacion",
        "direccion",
        "etiqueta_n",
        "estado_n",
        "municipio_n",
        "parroquia_n",
        "x10_en_demanda",
        "x10_n_casos",
        "x10_codigos",
        "x10_match",
    ]

    with st.spinner("Generando mapa de abordaje…"):
        html = _cached_abordaje_html(
            selected_ids=tuple(sorted(selected)),
            basemap=basemap,
            view_name=view_name,
            solo_bytes=_df_to_bytes(solo if show_solo else None, sol_cols),
            coin_bytes=_df_to_bytes(coin if show_coin else None, sol_cols),
            hab_bytes=_df_to_bytes(hab_geo if show_hab else None, hab_cols),
            show_solo=show_solo,
            show_coin=show_coin,
            show_hab=show_hab,
            zone_mode=zone_mode,
        )
    components.html(html, height=700, scrolling=False)

    st.caption(
        "Puntos: clic para detalle (fuente, códigos, cruce). "
        "Zonas GIS: contorno + resalte al pasar el mouse (no mancha permanente)."
    )

    with st.expander("Inventario de capas GIS en disco", expanded=False):
        rows = []
        for meta in LAYER_CATALOG:
            p = _layer_path(meta["id"])
            mb = round(p.stat().st_size / (1024 * 1024), 2) if p else None
            rows.append(
                {
                    "Capa": meta["label"],
                    "Grupo": meta["group"],
                    "Archivo": p.name if p else "—",
                    "MB": mb if mb is not None else "—",
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)


@st.cache_data(show_spinner=False, ttl=600)
def _cached_abordaje_html(
    selected_ids: tuple[str, ...],
    basemap: str,
    view_name: str,
    solo_bytes: bytes = b"",
    coin_bytes: bytes = b"",
    hab_bytes: bytes = b"",
    show_solo: bool = False,
    show_coin: bool = False,
    show_hab: bool = False,
    zone_mode: str = "contorno",
) -> str:
    return _build_map(
        selected_ids,
        basemap,
        view_name,
        solo_bytes=solo_bytes,
        coin_bytes=coin_bytes,
        hab_bytes=hab_bytes,
        show_solo=show_solo,
        show_coin=show_coin,
        show_hab=show_hab,
        zone_mode=zone_mode,
    )
