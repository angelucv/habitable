"""Cruce territorial 1×10 × capas GIS de abordaje (+ estado Habitable)."""

from __future__ import annotations

from typing import Any

import pandas as pd

# Capas poligonales a cruzar (excluye puntos del paquete GIS).
EXPORT_LAYER_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "mascara_altagracia",
        "col": "mascara_altagracia",
        "label": "Máscara Altagracia",
        "prop_keys": ("Parroquia", "Municipio", "ENTIDAD", "Estado", "Name"),
    },
    {
        "id": "mascara_san_bernardino",
        "col": "mascara_san_bernardino",
        "label": "Máscara San Bernardino",
        "prop_keys": ("Parroquia", "Municipio", "ENTIDAD", "Estado", "Name"),
    },
    {
        "id": "mascara_san_jose",
        "col": "mascara_san_jose",
        "label": "Máscara San José",
        "prop_keys": ("Parroquia", "Municipio", "ENTIDAD", "Estado", "Name"),
    },
    {
        "id": "mascara_petare",
        "col": "mascara_petare",
        "label": "Máscara Petare",
        "prop_keys": ("Parroquia", "Municipio", "Estado", "Name"),
    },
    {
        "id": "cuadricula_petare",
        "col": "cuadricula_petare",
        "label": "Cuadrícula Petare",
        "prop_keys": ("id", "row_index", "col_index", "Name"),
    },
    {
        "id": "cuadricula_abordaje",
        "col": "cuadricula_abordaje",
        "label": "Cuadrícula abordaje",
        "prop_keys": ("id", "row_index", "col_index", "Name"),
    },
    {
        "id": "bloques_la_guaira",
        "col": "bloque_la_guaira",
        "label": "Bloque La Guaira",
        "prop_keys": ("BLOQUE", "SECTOR", "ZONA", "NOM_MAPA", "Name"),
    },
    {
        "id": "microzonas_amenaza",
        "col": "microzona_amenaza",
        "label": "Microzona amenaza",
        "prop_keys": ("Name", "NOMBRE", "name"),
    },
    {
        "id": "microzonas_laderas",
        "col": "microzona_laderas",
        "label": "Microzona laderas",
        "prop_keys": ("Name", "NOMBRE", "name"),
    },
    {
        "id": "microzonas_sedimentos",
        "col": "microzona_sedimentos",
        "label": "Microzona sedimentos",
        "prop_keys": ("Name", "NOMBRE", "name"),
    },
    {
        "id": "parroquias",
        "col": "parroquia_capa",
        "label": "Parroquia (capa)",
        "prop_keys": ("Parroquia", "Municipio", "Estado", "Name"),
    },
    {
        "id": "parroquias_ine_2025",
        "col": "parroquia_ine_2025",
        "label": "Parroquia INE 2025",
        "prop_keys": ("Parroquia", "Municipio", "ENTIDAD", "Name"),
    },
    {
        "id": "segmentos_censales",
        "col": "segmento_censal",
        "label": "Segmento censal",
        "prop_keys": ("COD_SEG", "NOM_PARROQ", "NOM_MUNICI", "NOM_ENTIDA", "Name"),
        "heavy": True,
    },
)


def _prop_label(props: dict, keys: tuple[str, ...]) -> str:
    parts: list[str] = []
    for k in keys:
        if k in props and props[k] not in (None, "", "null"):
            parts.append(str(props[k]).strip())
    # dedupe preservando orden
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return " · ".join(out) if out else "sí"


def _match_habitable_label(cat: object) -> str:
    return {
        "solo_1x10": "No — pendiente (solo 1×10)",
        "coincide_alta": "Sí — coincidencia alta",
        "coincide_media": "Sí — coincidencia media",
        "coincide_geo_solo": "Cerca en mapa (revisar)",
        "no_mapeable": "Sin GPS / no mapeable",
    }.get(str(cat or ""), str(cat or "—"))


def _build_layer_index(geojson: dict, prop_keys: tuple[str, ...]):
    from shapely.geometry import shape
    from shapely.strtree import STRtree

    geoms = []
    labels = []
    for feat in geojson.get("features") or []:
        geom = feat.get("geometry")
        if not geom:
            continue
        try:
            g = shape(geom)
            if g.is_empty:
                continue
            if not g.is_valid:
                g = g.buffer(0)
        except Exception:  # noqa: BLE001
            continue
        props = feat.get("properties") or {}
        geoms.append(g)
        labels.append(_prop_label(props, prop_keys))
    if not geoms:
        return None, []
    return STRtree(geoms), labels


def _lookup_point(tree, labels: list[str], lon: float, lat: float) -> str:
    from shapely.geometry import Point

    if tree is None or not labels:
        return ""
    pt = Point(float(lon), float(lat))
    try:
        idxs = tree.query(pt, predicate="intersects")
    except TypeError:
        idxs = tree.query(pt)
    if idxs is None:
        return ""
    try:
        import numpy as np

        arr = np.asarray(idxs).ravel()
        if len(arr) == 0:
            return ""
        # Preferir el polígono de menor área (más específico) si hay solapes
        best_i = int(arr[0])
        best_area = None
        geoms = getattr(tree, "geometries", None)
        for raw in arr:
            i = int(raw)
            area = None
            if geoms is not None:
                try:
                    area = float(geoms[i].area)
                except Exception:  # noqa: BLE001
                    area = None
            if best_area is None or (area is not None and area < best_area):
                best_area = area if area is not None else best_area
                best_i = i
        return labels[best_i] if 0 <= best_i < len(labels) else ""
    except Exception:  # noqa: BLE001
        try:
            i = int(idxs[0])
            return labels[i] if 0 <= i < len(labels) else ""
        except Exception:  # noqa: BLE001
            return ""


def construir_cruce_1x10_capas(
    sol: pd.DataFrame,
    *,
    layer_ids: list[str] | None = None,
    solo_mapeables: bool = True,
    solo_representantes: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Cruza puntos 1×10 con capas poligonales de ``data/gis_lite``.

    Devuelve (dataframe listo para Excel, meta).
    """
    from pages_abordaje import _load_geojson_dict, _layer_path

    if sol is None or sol.empty:
        raise ValueError("No hay solicitudes 1×10 para cruzar.")

    work = sol.copy()
    if solo_representantes and "es_representante" in work.columns:
        # Si la columna existe, preferir representantes; si todo es False, no filtrar
        mask_rep = work["es_representante"].fillna(False).astype(bool)
        if bool(mask_rep.any()):
            work = work.loc[mask_rep].copy()
    if solo_mapeables and "mapeable" in work.columns:
        work = work.loc[work["mapeable"].fillna(False).astype(bool)].copy()
    if "mapa_ok" in work.columns:
        # Preferir GPS fiable, pero no vaciar el universo
        ok = work["mapa_ok"].fillna(False).astype(bool)
        if bool(ok.any()):
            work = work.loc[ok].copy()

    work = work.dropna(subset=["lat", "lng"]).copy()
    if work.empty:
        raise ValueError("No quedan puntos 1×10 con coordenadas tras el filtro.")

    wanted = set(layer_ids) if layer_ids else {s["id"] for s in EXPORT_LAYER_SPECS}
    specs = [s for s in EXPORT_LAYER_SPECS if s["id"] in wanted]

    meta: dict[str, Any] = {
        "n_puntos": int(len(work)),
        "capas": {},
        "capas_faltantes": [],
    }

    # Columnas base de negocio
    base_cols = [
        c
        for c in (
            "codigo_caso",
            "codigos_grupo",
            "cedula",
            "denunciante",
            "telefono",
            "telefono_alt",
            "estado",
            "estado_n",
            "municipio",
            "municipio_n",
            "parroquia",
            "parroquia_n",
            "direccion",
            "descripcion",
            "lat",
            "lng",
            "match_cat",
            "match_dist_m",
            "match_score",
            "hab_id",
            "hab_nombre",
            "hab_etiqueta",
            "n_reportes",
            "tipo_ubicacion",
            "tipo_dir",
        )
        if c in work.columns
    ]
    out = work[base_cols].copy()
    if "match_cat" in out.columns:
        cat = out["match_cat"]
        out["en_habitable"] = cat.map(
            lambda c: "Sí"
            if str(c) in ("coincide_alta", "coincide_media")
            else (
                "Cerca"
                if str(c) == "coincide_geo_solo"
                else ("No" if str(c) == "solo_1x10" else "—")
            )
        )
        out["estado_cruce_habitable"] = cat.map(_match_habitable_label)
    else:
        out["en_habitable"] = "—"
        out["estado_cruce_habitable"] = "—"
    if "hab_etiqueta" in out.columns:
        out["etiqueta_inspeccion_habitable"] = (
            out["hab_etiqueta"].fillna("").astype(str).str.strip().str.upper()
        )
    else:
        out["etiqueta_inspeccion_habitable"] = ""
    if "hab_nombre" in out.columns:
        out["edificio_habitable"] = out["hab_nombre"].fillna("").astype(str)
    else:
        out["edificio_habitable"] = ""
    if "hab_id" in out.columns:
        out["id_inspeccion_habitable"] = out["hab_id"].fillna("").astype(str)
    else:
        out["id_inspeccion_habitable"] = ""

    lats = out["lat"].astype(float).to_numpy()
    lngs = out["lng"].astype(float).to_numpy()

    for spec in specs:
        stem = spec["id"]
        col = spec["col"]
        if _layer_path(stem) is None:
            meta["capas_faltantes"].append(stem)
            out[col] = ""
            continue
        gj = _load_geojson_dict(stem)
        if not gj:
            meta["capas_faltantes"].append(stem)
            out[col] = ""
            continue
        tree, labels = _build_layer_index(gj, tuple(spec["prop_keys"]))
        vals = [
            _lookup_point(tree, labels, float(lon), float(lat))
            for lon, lat in zip(lngs, lats)
        ]
        out[col] = vals
        n_hit = sum(1 for v in vals if v)
        meta["capas"][stem] = {
            "label": spec["label"],
            "n_con_match": int(n_hit),
            "pct": round(100.0 * n_hit / max(len(vals), 1), 1),
        }

    # Orden de columnas legible
    front = [
        c
        for c in (
            "codigo_caso",
            "codigos_grupo",
            "denunciante",
            "cedula",
            "telefono",
            "telefono_alt",
            "estado_n",
            "municipio_n",
            "parroquia_n",
            "direccion",
            "lat",
            "lng",
            "en_habitable",
            "estado_cruce_habitable",
            "etiqueta_inspeccion_habitable",
            "id_inspeccion_habitable",
            "edificio_habitable",
            "match_dist_m",
            "match_score",
            "n_reportes",
            "tipo_ubicacion",
        )
        if c in out.columns
    ]
    capa_cols = [s["col"] for s in specs if s["col"] in out.columns]
    rest = [c for c in out.columns if c not in front and c not in capa_cols]
    out = out[front + capa_cols + rest]
    return out.reset_index(drop=True), meta


__all__ = [
    "EXPORT_LAYER_SPECS",
    "construir_cruce_1x10_capas",
]
