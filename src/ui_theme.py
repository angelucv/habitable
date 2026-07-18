"""
Tema visual ejecutivo y componentes de UI compartidos
=====================================================

- CSS institucional (navy + acentos bandera VE).
- Hero, cinta de estrellas, franjas KPI.
- ``render_section_tabs``: pestañas/secciones con borde y selección clara.

Usado por ``app.py`` y ``pages_analysis.py``.
"""

from __future__ import annotations

import streamlit as st

# Paleta institucional + acentos bandera VE (discreto)
NAVY = "#0C2340"
STEEL = "#1F4E79"
ACCENT = "#2A6F97"
INK = "#0F172A"
MUTED = "#334155"
LINE = "#CBD5E1"
SURFACE = "#FFFFFF"
PAGE = "#F4F6F9"
SUCCESS = "#166534"
WARN = "#9A3412"
# Bandera Venezuela
VE_YELLOW = "#FCD116"
VE_BLUE = "#0033A0"
VE_RED = "#CF142B"
SIDEBAR_TEXT = "#F1F5F9"
SIDEBAR_MUTED = "#CBD5E1"


def inject_executive_css() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&family=Source+Sans+3:wght@400;500;600;700&display=swap');

        html, body, [class*="css"], .stApp {{
            font-family: 'Source Sans 3', 'Segoe UI', sans-serif;
            color: {INK};
        }}
        .stApp {{
            background: {PAGE};
        }}
        [data-testid="stHeader"] {{
            background: rgba(244, 246, 249, 0.92);
            border-bottom: 1px solid {LINE};
        }}

        /* —— Cinta bandera VE (discreta) —— */
        .ve-ribbon {{
            display: flex;
            flex-direction: column;
            border-radius: 8px 8px 0 0;
            overflow: hidden;
            margin: 0 0 0.55rem 0;
            box-shadow: 0 1px 2px rgba(12, 35, 64, 0.08);
        }}
        .ve-stripe {{
            height: 7px;
            width: 100%;
        }}
        .ve-stripe-y {{ background: {VE_YELLOW}; }}
        .ve-stripe-b {{
            background: {VE_BLUE};
            height: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 7px;
        }}
        .ve-stripe-r {{ background: {VE_RED}; }}
        .ve-star {{
            width: 9px;
            height: 9px;
            display: inline-block;
            background: #FFFFFF;
            clip-path: polygon(
                50% 0%, 61% 35%, 98% 35%, 68% 57%,
                79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%
            );
            opacity: 1;
        }}

        /* —— Sidebar navy —— */
        [data-testid="stSidebar"] {{
            background: {NAVY} !important;
            border-right: none;
        }}
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] .stMarkdown,
        section[data-testid="stSidebar"] .stMarkdown p,
        section[data-testid="stSidebar"] .stMarkdown strong,
        section[data-testid="stSidebar"] .stCaption,
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
            color: {SIDEBAR_TEXT} !important;
        }}
        section[data-testid="stSidebar"] hr {{
            border-color: rgba(255,255,255,0.22);
        }}
        section[data-testid="stSidebar"] div[data-testid="stMetric"] {{
            background: rgba(255,255,255,0.10) !important;
            border: 1px solid rgba(255,255,255,0.22) !important;
            border-top: 3px solid {VE_YELLOW} !important;
            border-radius: 8px;
            padding: 0.75rem 0.9rem;
        }}
        section[data-testid="stSidebar"] div[data-testid="stMetric"] label,
        section[data-testid="stSidebar"] div[data-testid="stMetric"] p,
        section[data-testid="stSidebar"] div[data-testid="stMetric"] span,
        section[data-testid="stSidebar"] div[data-testid="stMetric"] div {{
            color: #F8FAFC !important;
            opacity: 1 !important;
        }}
        section[data-testid="stSidebar"] div[data-testid="stMetricValue"],
        section[data-testid="stSidebar"] div[data-testid="stMetricValue"] * {{
            color: #FFFFFF !important;
            font-family: 'Source Serif 4', Georgia, serif !important;
            font-size: 1.45rem !important;
            font-weight: 700 !important;
            opacity: 1 !important;
        }}
        section[data-testid="stSidebar"] div[data-testid="stMetricLabel"],
        section[data-testid="stSidebar"] div[data-testid="stMetricLabel"] *,
        section[data-testid="stSidebar"] div[data-testid="stMetricLabel"] label,
        section[data-testid="stSidebar"] div[data-testid="stMetricLabel"] p {{
            color: #E2E8F0 !important;
            font-weight: 700 !important;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            font-size: 0.72rem !important;
            opacity: 1 !important;
        }}
        section[data-testid="stSidebar"] .stButton > button {{
            background: #FFFFFF !important;
            color: {NAVY} !important;
            border: 1px solid #FFFFFF !important;
            font-weight: 700 !important;
        }}
        section[data-testid="stSidebar"] .stButton > button:hover {{
            background: #E2E8F0 !important;
            color: {NAVY} !important;
        }}
        section[data-testid="stSidebar"] .stButton > button p,
        section[data-testid="stSidebar"] .stButton > button span {{
            color: {NAVY} !important;
        }}

        /* —— Hero —— */
        .bi-hero {{
            background: linear-gradient(105deg, {NAVY} 0%, {STEEL} 52%, {ACCENT} 100%);
            color: #F8FAFC;
            padding: 1.25rem 1.5rem 1.15rem;
            border-radius: 0 0 10px 10px;
            margin-bottom: 1rem;
            border-left: 4px solid {VE_YELLOW};
            border-right: 4px solid {VE_RED};
        }}
        .bi-hero-kicker {{
            font-size: 0.72rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: #E2E8F0 !important;
            font-weight: 600;
            margin: 0 0 0.35rem 0;
        }}
        .bi-hero h1 {{
            font-family: 'Source Serif 4', Georgia, serif;
            font-size: 1.75rem;
            font-weight: 700;
            margin: 0 0 0.4rem 0;
            line-height: 1.2;
            color: #FFFFFF !important;
        }}
        .bi-hero p {{
            margin: 0;
            font-size: 0.95rem;
            color: #F1F5F9 !important;
            max-width: 52rem;
            line-height: 1.45;
            opacity: 1 !important;
        }}

        /* —— KPI strip —— */
        .kpi-strip {{
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 0.75rem;
            margin: 0.4rem 0 1rem 0;
        }}
        @media (max-width: 1100px) {{
            .kpi-strip {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
        }}
        @media (max-width: 700px) {{
            .kpi-strip {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        }}
        .kpi-card {{
            background: {SURFACE};
            border: 1px solid {LINE};
            border-radius: 8px;
            padding: 0.85rem 1rem 0.75rem;
            border-top: 3px solid {STEEL};
        }}
        .kpi-card.tone-success {{ border-top-color: {SUCCESS}; }}
        .kpi-card.tone-info {{ border-top-color: {ACCENT}; }}
        .kpi-card.tone-warning {{ border-top-color: {VE_RED}; }}
        .kpi-card.tone-muted {{ border-top-color: #64748B; }}
        .kpi-card.tone-flag {{ border-top-color: {VE_YELLOW}; }}
        .kpi-label {{
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: {MUTED};
            margin-bottom: 0.35rem;
        }}
        .kpi-value {{
            font-family: 'Source Serif 4', Georgia, serif;
            font-size: 1.55rem;
            font-weight: 700;
            color: {NAVY};
            line-height: 1.1;
        }}
        .kpi-hint {{
            font-size: 0.78rem;
            color: {MUTED};
            margin-top: 0.25rem;
            font-weight: 500;
        }}

        .bi-section {{
            margin: 1.25rem 0 0.65rem 0;
            padding-bottom: 0.4rem;
            border-bottom: 1px solid {LINE};
        }}
        .bi-section h2 {{
            font-family: 'Source Serif 4', Georgia, serif;
            font-size: 1.25rem;
            font-weight: 700;
            color: {NAVY};
            margin: 0;
        }}
        .bi-section p {{
            margin: 0.25rem 0 0 0;
            color: {MUTED};
            font-size: 0.9rem;
            font-weight: 500;
        }}

        [data-testid="stMain"] .stCaption,
        [data-testid="stMain"] [data-testid="stCaptionContainer"],
        [data-testid="stMain"] [data-testid="stCaptionContainer"] p {{
            color: {MUTED} !important;
            opacity: 1 !important;
            font-weight: 500 !important;
        }}
        [data-testid="stMain"] label,
        [data-testid="stMain"] [data-testid="stWidgetLabel"] p {{
            color: {INK} !important;
            font-weight: 600 !important;
        }}

        /* —— Pestañas principales: barra tipo carpeta —— */
        div[data-testid="stMain"] div[data-baseweb="tab-list"],
        div[data-testid="stMain"] .stTabs [data-baseweb="tab-list"] {{
            display: flex !important;
            gap: 0 !important;
            background: #E8EEF4 !important;
            border: 1px solid {LINE} !important;
            border-bottom: 3px solid {STEEL} !important;
            border-radius: 10px 10px 0 0 !important;
            padding: 0.45rem 0.45rem 0 0.45rem !important;
            margin-bottom: 0 !important;
        }}
        div[data-testid="stMain"] .stTabs [data-baseweb="tab"] {{
            flex: 1 1 0 !important;
            height: auto !important;
            min-height: 3rem !important;
            margin: 0 0.2rem 0 0 !important;
            padding: 0.75rem 1rem !important;
            background: #D9E2EC !important;
            color: {NAVY} !important;
            font-weight: 700 !important;
            font-size: 0.95rem !important;
            border: 1px solid #B8C5D3 !important;
            border-bottom: none !important;
            border-radius: 8px 8px 0 0 !important;
            box-shadow: none !important;
            opacity: 1 !important;
        }}
        div[data-testid="stMain"] .stTabs [data-baseweb="tab"]:last-child {{
            margin-right: 0 !important;
        }}
        div[data-testid="stMain"] .stTabs [data-baseweb="tab"] p,
        div[data-testid="stMain"] .stTabs [data-baseweb="tab"] span,
        div[data-testid="stMain"] .stTabs [data-baseweb="tab"] div {{
            color: {NAVY} !important;
            font-weight: 700 !important;
            opacity: 1 !important;
        }}
        div[data-testid="stMain"] .stTabs [aria-selected="true"] {{
            background: #FFFFFF !important;
            color: {STEEL} !important;
            border-color: {STEEL} !important;
            border-top: 3px solid {VE_YELLOW} !important;
            position: relative;
            z-index: 2;
            margin-bottom: -3px !important;
            padding-bottom: calc(0.75rem + 3px) !important;
        }}
        div[data-testid="stMain"] .stTabs [aria-selected="true"] p,
        div[data-testid="stMain"] .stTabs [aria-selected="true"] span,
        div[data-testid="stMain"] .stTabs [aria-selected="true"] div {{
            color: {STEEL} !important;
        }}
        div[data-testid="stMain"] .stTabs [data-baseweb="tab-highlight"],
        div[data-testid="stMain"] .stTabs [data-baseweb="tab-border"] {{
            display: none !important;
            height: 0 !important;
        }}
        div[data-testid="stMain"] .stTabs [data-baseweb="tab-panel"],
        div[data-testid="stMain"] .stTabs > div > div[data-baseweb="tab-panel"] {{
            background: #FFFFFF !important;
            border: 1px solid {LINE} !important;
            border-top: none !important;
            border-radius: 0 0 10px 10px !important;
            padding: 1rem 1.1rem 1.2rem 1.1rem !important;
        }}

        /* Quitar estilos de radio (ya no se usan en nav) */
        /* Sub-pestañas Habitable: misma lógica más compacta */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 0;
        }}
        /* —— Fin pestañas —— */

        /* Navegación radio (legacy, no usada en principal) */
        div[data-testid="stMain"] div[role="radiogroup"] {{
            gap: 0.65rem;
        }}


        /* Métricas área principal */
        [data-testid="stMain"] div[data-testid="stMetric"] {{
            background: {SURFACE};
            border: 1px solid {LINE};
            border-radius: 8px;
            padding: 0.75rem 0.9rem;
            border-top: 3px solid {STEEL};
        }}
        [data-testid="stMain"] div[data-testid="stMetricValue"],
        [data-testid="stMain"] div[data-testid="stMetricValue"] * {{
            font-family: 'Source Serif 4', Georgia, serif;
            font-size: 1.45rem;
            color: {NAVY} !important;
            opacity: 1 !important;
        }}
        [data-testid="stMain"] div[data-testid="stMetricLabel"],
        [data-testid="stMain"] div[data-testid="stMetricLabel"] * {{
            color: {MUTED} !important;
            font-weight: 700 !important;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            font-size: 0.72rem;
            opacity: 1 !important;
        }}

        .stExpander {{
            border: 1px solid {LINE};
            border-radius: 8px;
            background: {SURFACE};
        }}
        [data-testid="stDataFrame"] {{
            border: 1px solid {LINE};
            border-radius: 8px;
            overflow: hidden;
        }}

        #MainMenu {{ visibility: hidden; }}
        footer {{ visibility: hidden; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_flag_ribbon() -> None:
    stars = "".join('<span class="ve-star" aria-hidden="true"></span>' for _ in range(8))
    st.markdown(
        f"""
        <div class="ve-ribbon" role="img" aria-label="Cinta con colores de la bandera de Venezuela">
          <div class="ve-stripe ve-stripe-y"></div>
          <div class="ve-stripe ve-stripe-b">{stars}</div>
          <div class="ve-stripe ve-stripe-r"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero(
    title: str,
    subtitle: str,
    kicker: str = "Comisión Presidencial · Habitabilidad",
) -> None:
    render_flag_ribbon()
    st.markdown(
        f"""
        <div class="bi-hero">
          <div class="bi-hero-kicker">{kicker}</div>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section(title: str, subtitle: str | None = None) -> None:
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(
        f"""
        <div class="bi-section">
          <h2>{title}</h2>
          {sub}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_tabs(
    options: list[tuple[str, str]],
    *,
    state_key: str,
    heading: str = "Secciones",
) -> str:
    """
    Pestañas/secciones con borde y selección clara.
    options: [(id, etiqueta), ...]
    """
    valid = {k for k, _ in options}
    if state_key not in st.session_state or st.session_state[state_key] not in valid:
        st.session_state[state_key] = options[0][0]

    # CSS scoped por prefijo de key de Streamlit (st-key-<state_key>_…)
    prefix = state_key
    selectors = ",\n        ".join(
        f'div[class*="st-key-{prefix}_{k}"] button' for k, _ in options
    )
    sel_sec = ",\n        ".join(
        f'div[class*="st-key-{prefix}_{k}"] button[kind="secondary"]' for k, _ in options
    )
    sel_pri = ",\n        ".join(
        f'div[class*="st-key-{prefix}_{k}"] button[kind="primary"]' for k, _ in options
    )
    sel_sec_txt = ",\n        ".join(
        f'div[class*="st-key-{prefix}_{k}"] button[kind="secondary"] p,\n'
        f'        div[class*="st-key-{prefix}_{k}"] button[kind="secondary"] span'
        for k, _ in options
    )
    sel_pri_txt = ",\n        ".join(
        f'div[class*="st-key-{prefix}_{k}"] button[kind="primary"] p,\n'
        f'        div[class*="st-key-{prefix}_{k}"] button[kind="primary"] span'
        for k, _ in options
    )

    st.markdown(
        f"""
        <style>
        {selectors} {{
          min-height: 3rem !important;
          border-radius: 8px !important;
          font-weight: 700 !important;
          font-size: 0.92rem !important;
          border-width: 2px !important;
        }}
        {sel_sec} {{
          background: #F1F5F9 !important;
          border-color: #64748B !important;
          color: #0C2340 !important;
        }}
        {sel_sec_txt} {{
          color: #0C2340 !important;
          font-weight: 700 !important;
        }}
        {sel_pri} {{
          background: #1F4E79 !important;
          border-color: #0C2340 !important;
          color: #FFFFFF !important;
          box-shadow: inset 0 4px 0 0 #FCD116 !important;
        }}
        {sel_pri_txt} {{
          color: #FFFFFF !important;
          font-weight: 700 !important;
        }}
        </style>
        <div style="
          background:#E2E8F0;border:2px solid #94A3B8;border-bottom:3px solid #1F4E79;
          border-radius:10px;padding:0.55rem 0.55rem 0.2rem 0.55rem;margin:0.35rem 0 0.35rem 0;
        ">
          <div style="color:#334155;font-size:0.7rem;font-weight:700;letter-spacing:0.06em;
                      text-transform:uppercase;margin:0 0 0.4rem 0.2rem;">{heading}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(len(options))
    for col, (key, label) in zip(cols, options):
        with col:
            active = st.session_state[state_key] == key
            if st.button(
                label,
                key=f"{prefix}_{key}",
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                st.session_state[state_key] = key
                st.rerun()
    return st.session_state[state_key]


def render_kpi_strip(items: list[dict]) -> None:
    """items: [{label, value, tone?, hint?}]"""
    cards = []
    for it in items:
        tone = it.get("tone", "")
        cls = f"kpi-card tone-{tone}" if tone else "kpi-card"
        hint = f'<div class="kpi-hint">{it["hint"]}</div>' if it.get("hint") else ""
        cards.append(
            f'<div class="{cls}">'
            f'<div class="kpi-label">{it["label"]}</div>'
            f'<div class="kpi-value">{it["value"]}</div>'
            f"{hint}</div>"
        )
    st.markdown(
        f'<div class="kpi-strip">{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )
