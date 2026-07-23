"""Política de mapas base (tiles) — ministerio / cifrado de área operativa.

En producción no se usan OSM/Carto/Esri salvo ``BI_ALLOW_PUBLIC_TILES=1``.
Configure tiles internos con ``BI_TILES_URL`` (plantilla ``{z}/{x}/{y}``).
"""

from __future__ import annotations

import os
from typing import Any

import folium

# Marcador interno: no pedir tiles a Internet
NONE_TILES = "__none__"
NONE_KEY = "Sin mapa base (solo puntos)"
INTERNAL_KEY = "Mapa institucional"

PUBLIC_BASEMAPS: dict[str, tuple[str, str, str]] = {
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

# Subconjunto usado en abordaje / NASA (menos opciones)
PUBLIC_BASEMAPS_LITE: dict[str, tuple[str, str, str]] = {
    "OSM claro (Carto)": PUBLIC_BASEMAPS["OSM claro (Carto)"],
    "OpenStreetMap": PUBLIC_BASEMAPS["OpenStreetMap"],
    "Satélite (Esri)": PUBLIC_BASEMAPS["Satélite (Esri)"],
    "Topográfico": PUBLIC_BASEMAPS["Topográfico"],
}


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def is_production_mode() -> bool:
    if _env_truthy("BI_REQUIRE_AUTH"):
        return True
    env = os.environ.get("BI_ENV", "").strip().lower()
    return env in ("production", "prod", "ministerio", "ministry")


def _secret_tiles() -> dict[str, str]:
    try:
        import streamlit as st

        block = st.secrets.get("tiles", {})  # type: ignore[attr-defined]
        if isinstance(block, dict):
            return {str(k): str(v) for k, v in block.items() if v is not None}
    except Exception:
        pass
    return {}


def internal_tiles_url() -> str | None:
    url = os.environ.get("BI_TILES_URL", "").strip()
    if url:
        return url
    sec = _secret_tiles()
    url = str(sec.get("url") or "").strip()
    return url or None


def internal_tiles_attr() -> str:
    attr = os.environ.get("BI_TILES_ATTR", "").strip()
    if attr:
        return attr
    sec = _secret_tiles()
    return str(sec.get("attr") or "© Institución · uso interno").strip()


def internal_tiles_name() -> str:
    name = os.environ.get("BI_TILES_NAME", "").strip()
    if name:
        return name
    sec = _secret_tiles()
    return str(sec.get("name") or "Institucional").strip()


def public_tiles_allowed() -> bool:
    """En prod, públicos solo con permiso explícito."""
    if _env_truthy("BI_ALLOW_PUBLIC_TILES"):
        return True
    sec = _secret_tiles()
    if str(sec.get("allow_public") or "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    if is_production_mode():
        return False
    return True


def using_internal_tiles() -> bool:
    return bool(internal_tiles_url())


def tile_policy_caption() -> str:
    if using_internal_tiles():
        return "Mapa base: **tiles institucionales** (BI_TILES_URL)."
    if public_tiles_allowed():
        return "Mapa base: proveedores públicos (solo desarrollo / permiso explícito)."
    return (
        "Mapa base: **sin tiles externos** (producción). "
        "Defina BI_TILES_URL o BI_ALLOW_PUBLIC_TILES=1."
    )


def available_basemaps(*, lite: bool = False) -> dict[str, tuple[str, str, str]]:
    """
    Catálogo efectivo según política.

    ``lite=True``: opciones reducidas (abordaje / NASA).
    """
    out: dict[str, tuple[str, str, str]] = {}
    url = internal_tiles_url()
    if url:
        out[INTERNAL_KEY] = (url, internal_tiles_attr(), internal_tiles_name())
    if public_tiles_allowed():
        public = PUBLIC_BASEMAPS_LITE if lite else PUBLIC_BASEMAPS
        for k, v in public.items():
            if k not in out:
                out[k] = v
    if not out:
        out[NONE_KEY] = (NONE_TILES, "CPEH · sin tiles externos", "Sin base")
    return out


def default_basemap_key(basemaps: dict[str, tuple[str, str, str]] | None = None) -> str:
    bm = basemaps if basemaps is not None else available_basemaps()
    if INTERNAL_KEY in bm:
        return INTERNAL_KEY
    if NONE_KEY in bm:
        return NONE_KEY
    if "OSM claro (Carto)" in bm:
        return "OSM claro (Carto)"
    return next(iter(bm.keys()))


def make_tile_layer(
    key: str,
    *,
    basemaps: dict[str, tuple[str, str, str]] | None = None,
    show: bool = False,
) -> folium.TileLayer | None:
    """Crea TileLayer Folium, o ``None`` si no hay mapa base."""
    bm = basemaps if basemaps is not None else available_basemaps()
    if key not in bm:
        key = default_basemap_key(bm)
    tiles, attr, name = bm[key]
    if tiles == NONE_TILES or not tiles:
        return None
    if str(tiles).startswith("http"):
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
        attr=attr,
    )


def add_basemap_layers(
    fmap: Any,
    primary: str,
    *,
    basemaps: dict[str, tuple[str, str, str]] | None = None,
    show_extras: bool = True,
) -> None:
    """Añade capa primaria y, opcionalmente, el resto al LayerControl."""
    bm = basemaps if basemaps is not None else available_basemaps()
    if primary not in bm:
        primary = default_basemap_key(bm)
    layer = make_tile_layer(primary, basemaps=bm, show=True)
    if layer is not None:
        fmap.add_child(layer)
    if show_extras:
        for key in bm:
            if key == primary:
                continue
            extra = make_tile_layer(key, basemaps=bm, show=False)
            if extra is not None:
                fmap.add_child(extra)
