"""Helpers ECharts para el BI (streamlit-echarts)."""

from __future__ import annotations

from typing import Sequence

# Paleta alineada al tablero ejecutivo (fondo claro)
PALETTE = [
    "#1F4E79",  # navy steel
    "#2A6F97",  # accent
    "#1F6B4A",  # verde
    "#B45309",  # ámbar
    "#5C6B7A",  # muted
    "#9B2C2C",  # rojo
    "#0C2340",  # navy deep
    "#64748B",  # slate
]

# Semáforo Habitable (colores de etiqueta, legibles en fondo claro)
ETIQUETA_COLORS = {
    "VERDE": "#15803D",
    "AMARILLO": "#EAB308",
    "ROJO": "#CF142B",
    "NEGRO": "#0F172A",
    "SIN": "#94A3B8",
}

# Demanda 1×10 en Inicio: navy ejecutivo (sin semáforo, para no confundir)
HOME_1X10_COLORS = {
    "atendidas": "#0C2340",  # navy institucional
    "pendientes": "#5B7C99",  # acero suave
}

MATCH_COLORS = {
    "solo_1x10": "#B45309",
    "coincide_geo_solo": "#94A3B8",
    "coincide_alta": "#1F6B4A",
    "coincide_media": "#2A6F97",
}

MATCH_LABELS = {
    "solo_1x10": "Solo 1×10 (pendiente)",
    "coincide_geo_solo": "Dudosos geo",
    "coincide_alta": "Coincide alta",
    "coincide_media": "Coincide media",
}


def _base_text() -> dict:
    return {"color": "#5C6B7A", "fontFamily": "Source Sans 3, Segoe UI, sans-serif"}


def donut(title: str, labels: Sequence[str], values: Sequence[float], colors: Sequence[str] | None = None) -> dict:
    cols = list(colors) if colors else PALETTE[: len(labels)]
    total = sum(values)
    data = [{"name": str(l), "value": int(v)} for l, v in zip(labels, values)]
    return {
        "backgroundColor": "transparent",
        "title": {
            "text": title,
            "left": "center",
            "top": 8,
            "textStyle": {"color": "#0C2340", "fontSize": 14, "fontWeight": 600},
        },
        "tooltip": {"trigger": "item", "formatter": "{b}<br/>{c} ({d}%)"},
        "legend": {
            "bottom": 4,
            "left": "center",
            "textStyle": _base_text(),
            "type": "scroll",
        },
        "color": cols,
        "series": [
            {
                "name": title,
                "type": "pie",
                "radius": ["48%", "70%"],
                "center": ["50%", "52%"],
                "avoidLabelOverlap": True,
                "itemStyle": {"borderRadius": 4, "borderColor": "#FFFFFF", "borderWidth": 2},
                "label": {
                    "show": True,
                    "formatter": "{b}\n{d}%",
                    "color": "#0C2340",
                    "fontSize": 11,
                    "fontWeight": 600,
                    "lineHeight": 14,
                },
                "emphasis": {
                    "label": {
                        "show": True,
                        "fontSize": 12,
                        "fontWeight": "bold",
                        "color": "#0C2340",
                    },
                    "scale": True,
                },
                "labelLine": {
                    "show": True,
                    "length": 10,
                    "length2": 8,
                    "lineStyle": {"color": "#94A3B8"},
                },
                "data": data,
            }
        ],
        "graphic": [
            {
                "type": "text",
                "left": "center",
                "top": "48%",
                "style": {
                    "text": f"{total/1000:.1f}K\nTotal" if total >= 1000 else f"{total}\nTotal",
                    "textAlign": "center",
                    "fill": "#0C2340",
                    "fontSize": 16,
                    "fontWeight": 600,
                    "fontFamily": "Source Sans 3, Segoe UI, sans-serif",
                },
            }
        ],
    }


def bar_vertical(
    title: str,
    categories: Sequence[str],
    values: Sequence[float],
    *,
    color_by_bar: bool = True,
) -> dict:
    cols = PALETTE[: max(len(categories), 1)]
    series_data = [
        {
            "value": int(v),
            "itemStyle": {"color": cols[i % len(cols)], "borderRadius": [4, 4, 0, 0]},
        }
        for i, v in enumerate(values)
    ]
    return {
        "backgroundColor": "transparent",
        "title": {
            "text": title,
            "left": "center",
            "top": 8,
            "textStyle": {"color": "#0C2340", "fontSize": 14, "fontWeight": 600},
        },
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "grid": {"left": 48, "right": 16, "top": 48, "bottom": 56, "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": list(categories),
            "axisLabel": {**_base_text(), "rotate": 30, "interval": 0, "fontSize": 11},
            "axisLine": {"lineStyle": {"color": "#D8DEE6"}},
        },
        "yAxis": {
            "type": "value",
            "axisLabel": _base_text(),
            "splitLine": {"lineStyle": {"color": "#E8EDF2"}},
        },
        "series": [
            {
                "type": "bar",
                "data": series_data if color_by_bar else list(map(int, values)),
                "barMaxWidth": 42,
                "label": {
                    "show": True,
                    "position": "top",
                    "color": "#5C6B7A",
                    "fontSize": 10,
                },
            }
        ],
    }


def bar_stacked_pct(
    title: str,
    categories: Sequence[str],
    series: Sequence[tuple[str, Sequence[float], str]],
) -> dict:
    """
    Barras apiladas al 100%.
    series: [(nombre, valores_%, color_hex), ...]
    """
    series_opts = []
    for i, (name, vals, color) in enumerate(series):
        series_opts.append(
            {
                "name": name,
                "type": "bar",
                "stack": "semaforo",
                "emphasis": {"focus": "series"},
                "itemStyle": {
                    "color": color,
                    "borderRadius": [4, 4, 0, 0] if i == len(series) - 1 else 0,
                },
                "data": [round(float(v), 1) for v in vals],
                "barMaxWidth": 48,
            }
        )
    return {
        "backgroundColor": "transparent",
        "title": {
            "text": title,
            "left": "center",
            "top": 8,
            "textStyle": {"color": "#0C2340", "fontSize": 14, "fontWeight": 600},
        },
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
        },
        "legend": {
            "bottom": 4,
            "left": "center",
            "textStyle": _base_text(),
        },
        "grid": {"left": 48, "right": 16, "top": 48, "bottom": 72, "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": list(categories),
            "axisLabel": {**_base_text(), "rotate": 30, "interval": 0, "fontSize": 11},
            "axisLine": {"lineStyle": {"color": "#D8DEE6"}},
        },
        "yAxis": {
            "type": "value",
            "max": 100,
            "axisLabel": {**_base_text(), "formatter": "{value}%"},
            "splitLine": {"lineStyle": {"color": "#E8EDF2"}},
        },
        "series": series_opts,
    }


def bar_horizontal(title: str, categories: Sequence[str], values: Sequence[float]) -> dict:
    cols = PALETTE[: max(len(categories), 1)]
    # ECharts horizontal: categories on y, reverse for top-first
    cats = list(categories)[::-1]
    vals = list(values)[::-1]
    series_data = [
        {
            "value": int(v),
            "itemStyle": {
                "color": cols[(len(cats) - 1 - i) % len(cols)],
                "borderRadius": [0, 4, 4, 0],
            },
        }
        for i, v in enumerate(vals)
    ]
    return {
        "backgroundColor": "transparent",
        "title": {
            "text": title,
            "left": "center",
            "top": 8,
            "textStyle": {"color": "#0C2340", "fontSize": 14, "fontWeight": 600},
        },
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "grid": {"left": 8, "right": 48, "top": 48, "bottom": 24, "containLabel": True},
        "xAxis": {
            "type": "value",
            "axisLabel": _base_text(),
            "splitLine": {"lineStyle": {"color": "#E8EDF2"}},
        },
        "yAxis": {
            "type": "category",
            "data": cats,
            "axisLabel": {**_base_text(), "fontSize": 11},
            "axisLine": {"lineStyle": {"color": "#D8DEE6"}},
        },
        "series": [
            {
                "type": "bar",
                "data": series_data,
                "barMaxWidth": 22,
                "label": {
                    "show": True,
                    "position": "right",
                    "color": "#5C6B7A",
                    "fontSize": 10,
                },
            }
        ],
    }
