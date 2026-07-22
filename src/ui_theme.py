"""Tema visual ejecutivo del BI (CSS + bloques de cabecera/KPI)."""

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

        /* —— Menú lateral: secciones (alto contraste) —— */
        section[data-testid="stSidebar"] div[class*="st-key-nav_home"] button,
        section[data-testid="stSidebar"] div[class*="st-key-nav_sec_"] button {{
            min-height: 2.55rem !important;
            border-radius: 8px !important;
            font-size: 0.9rem !important;
            font-weight: 700 !important;
            justify-content: flex-start !important;
            text-align: left !important;
            margin-bottom: 0.35rem !important;
        }}
        section[data-testid="stSidebar"] div[class*="st-key-nav_home"] button[kind="secondary"],
        section[data-testid="stSidebar"] div[class*="st-key-nav_sec_"] button[kind="secondary"] {{
            background: rgba(255,255,255,0.14) !important;
            border: 1px solid rgba(255,255,255,0.45) !important;
            color: #FFFFFF !important;
        }}
        section[data-testid="stSidebar"] div[class*="st-key-nav_home"] button[kind="secondary"] p,
        section[data-testid="stSidebar"] div[class*="st-key-nav_home"] button[kind="secondary"] span,
        section[data-testid="stSidebar"] div[class*="st-key-nav_sec_"] button[kind="secondary"] p,
        section[data-testid="stSidebar"] div[class*="st-key-nav_sec_"] button[kind="secondary"] span {{
            color: #FFFFFF !important;
            font-weight: 700 !important;
            opacity: 1 !important;
        }}
        section[data-testid="stSidebar"] div[class*="st-key-nav_home"] button[kind="primary"],
        section[data-testid="stSidebar"] div[class*="st-key-nav_sec_"] button[kind="primary"] {{
            background: #FFFFFF !important;
            border: 1px solid {VE_YELLOW} !important;
            box-shadow: inset 4px 0 0 0 {VE_YELLOW} !important;
            color: {NAVY} !important;
        }}
        section[data-testid="stSidebar"] div[class*="st-key-nav_home"] button[kind="primary"] p,
        section[data-testid="stSidebar"] div[class*="st-key-nav_home"] button[kind="primary"] span,
        section[data-testid="stSidebar"] div[class*="st-key-nav_sec_"] button[kind="primary"] p,
        section[data-testid="stSidebar"] div[class*="st-key-nav_sec_"] button[kind="primary"] span {{
            color: {NAVY} !important;
            font-weight: 700 !important;
            opacity: 1 !important;
        }}
        section[data-testid="stSidebar"] h3 {{
            color: #FFFFFF !important;
            font-weight: 700 !important;
        }}
        section[data-testid="stSidebar"] .stCaption,
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
            color: #E2E8F0 !important;
            opacity: 1 !important;
        }}

        /* —— Índice ejecutivo (sin tarjetas apiladas) —— */
        .nav-index {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.85rem;
            margin: 0.5rem 0 1.2rem 0;
        }}
        @media (max-width: 900px) {{
            .nav-index {{ grid-template-columns: 1fr; }}
        }}
        .nav-index-card {{
            background: {SURFACE};
            border: 1px solid {LINE};
            border-radius: 10px;
            padding: 0.95rem 1.05rem 0.85rem;
            border-top: 3px solid {STEEL};
        }}
        .nav-index-card h3 {{
            font-family: 'Source Serif 4', Georgia, serif;
            font-size: 1.1rem;
            color: {NAVY};
            margin: 0 0 0.35rem 0;
        }}
        .nav-index-card p {{
            color: {MUTED};
            font-size: 0.88rem;
            margin: 0 0 0.55rem 0;
            line-height: 1.4;
        }}
        .nav-index-card ul {{
            margin: 0;
            padding-left: 1.1rem;
            color: {INK};
            font-size: 0.86rem;
        }}
        .nav-index-card li {{
            margin: 0.15rem 0;
        }}
        .nav-index-incluye {{
            color: {INK};
            font-size: 0.84rem;
            margin: 0;
            line-height: 1.45;
        }}
        .nav-index-incluye strong {{
            color: {NAVY};
            font-weight: 700;
        }}
        .nav-exec {{
            margin: 0.25rem 0 1.35rem 0;
            border-top: 1px solid {LINE};
        }}
        .nav-exec-sec {{
            padding: 1.05rem 0 0.95rem 0;
            border-bottom: 1px solid {LINE};
        }}
        .nav-exec-sec-title {{
            font-family: 'Source Serif 4', Georgia, serif;
            font-size: 1.2rem;
            font-weight: 700;
            color: {NAVY};
            margin: 0 0 0.25rem 0;
            line-height: 1.25;
        }}
        .nav-exec-sec-blurb {{
            color: {MUTED};
            font-size: 0.9rem;
            margin: 0 0 0.7rem 0;
            line-height: 1.45;
        }}
        .nav-exec-item {{
            padding: 0.15rem 0 0.55rem 0.75rem;
            border-left: 2px solid {LINE};
            margin: 0 0 0.15rem 0.1rem;
        }}
        .nav-exec-item-blurb {{
            font-size: 0.84rem;
            color: {MUTED};
            margin: 0.05rem 0 0 0;
            line-height: 1.4;
            padding-left: 0.05rem;
        }}
        /* Nombres del índice como vínculos (sin botón-caja) */
        div[class*="st-key-home_go_item_"] button {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
            min-height: 0 !important;
            height: auto !important;
            justify-content: flex-start !important;
            color: {STEEL} !important;
            font-weight: 700 !important;
            font-size: 0.95rem !important;
            text-align: left !important;
        }}
        div[class*="st-key-home_go_item_"] button p,
        div[class*="st-key-home_go_item_"] button span {{
            color: {STEEL} !important;
            font-weight: 700 !important;
            text-align: left !important;
        }}
        div[class*="st-key-home_go_item_"] button:hover {{
            background: transparent !important;
            color: {NAVY} !important;
            text-decoration: underline !important;
        }}
        div[class*="st-key-home_go_item_"] button:hover p,
        div[class*="st-key-home_go_item_"] button:hover span {{
            color: {NAVY} !important;
        }}
        .nav-back {{
            margin: 0 0 0.75rem 0;
        }}
        div[class*="st-key-nav_back_home"] button {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
            min-height: 0 !important;
            height: auto !important;
            justify-content: flex-start !important;
            color: {STEEL} !important;
            font-weight: 600 !important;
            font-size: 0.88rem !important;
        }}
        div[class*="st-key-nav_back_home"] button p,
        div[class*="st-key-nav_back_home"] button span {{
            color: {STEEL} !important;
            font-weight: 600 !important;
        }}
        div[class*="st-key-nav_back_home"] button:hover {{
            background: transparent !important;
            text-decoration: underline !important;
            color: {NAVY} !important;
        }}
        .nav-crumb {{
            color: {MUTED};
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin: 0 0 0.35rem 0;
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
            grid-template-columns: repeat(var(--kpi-cols, 5), minmax(0, 1fr));
            gap: 0.75rem;
            margin: 0.4rem 0 1rem 0;
        }}
        @media (max-width: 1100px) {{
            .kpi-strip {{ grid-template-columns: repeat(min(3, var(--kpi-cols, 3)), minmax(0, 1fr)); }}
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
            min-width: 0;
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
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .kpi-hint {{
            font-size: 0.78rem;
            color: {MUTED};
            margin-top: 0.25rem;
            font-weight: 500;
        }}

        /* Filas KPI (paneles estrechos / inicio) */
        .kpi-rows {{
            display: flex;
            flex-direction: column;
            gap: 0.45rem;
            margin: 0.55rem 0 0.35rem 0;
        }}
        .kpi-row {{
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 0.75rem;
            background: {SURFACE};
            border: 1px solid {LINE};
            border-radius: 8px;
            padding: 0.55rem 0.85rem;
            border-left: 3px solid {STEEL};
        }}
        .kpi-row.tone-success {{ border-left-color: {SUCCESS}; }}
        .kpi-row.tone-info {{ border-left-color: {ACCENT}; }}
        .kpi-row.tone-warning {{ border-left-color: {VE_RED}; }}
        .kpi-row.tone-muted {{ border-left-color: #64748B; }}
        .kpi-row.tone-flag {{ border-left-color: {VE_YELLOW}; }}
        .kpi-row-label {{
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
            color: {MUTED};
            flex: 1 1 auto;
            min-width: 0;
        }}
        .kpi-row-right {{
            text-align: right;
            flex: 0 0 auto;
        }}
        .kpi-row-value {{
            font-family: 'Source Serif 4', Georgia, serif;
            font-size: 1.35rem;
            font-weight: 700;
            color: {NAVY};
            white-space: nowrap;
            line-height: 1.1;
        }}
        .kpi-row-hint {{
            font-size: 0.72rem;
            color: {MUTED};
            margin-top: 0.1rem;
            white-space: nowrap;
        }}

        /* Franja KPI compacta (inicio: total → desglose → torta) */
        .kpi-inline {{
            display: flex;
            flex-wrap: nowrap;
            align-items: flex-end;
            gap: 0.35rem 0.85rem;
            margin: 0.35rem 0 0.15rem 0;
            padding: 0.15rem 0 0.35rem 0;
            overflow-x: auto;
        }}
        .kpi-inline-item {{
            flex: 1 1 0;
            min-width: 0;
            text-align: left;
        }}
        .kpi-inline-item + .kpi-inline-item {{
            border-left: 1px solid {LINE};
            padding-left: 0.75rem;
        }}
        .kpi-inline-label {{
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: {MUTED};
            line-height: 1.2;
            margin-bottom: 0.12rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .kpi-inline-value {{
            font-family: 'Source Serif 4', Georgia, serif;
            font-size: 1.15rem;
            font-weight: 700;
            line-height: 1.1;
            white-space: nowrap;
        }}
        .kpi-inline-pct {{
            font-size: 0.72rem;
            font-weight: 600;
            color: {MUTED};
            margin-top: 0.08rem;
            line-height: 1.2;
            white-space: nowrap;
        }}

        /* —— Paneles KPI por fuente (inicio) —— */
        .kpi-fuentes {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            margin: 0.35rem 0 1.1rem 0;
        }}
        @media (max-width: 900px) {{
            .kpi-fuentes {{ grid-template-columns: 1fr; }}
        }}
        .kpi-fuente {{
            background: {SURFACE};
            border: 1px solid {LINE};
            border-radius: 10px;
            padding: 0.85rem 1rem 0.95rem;
            border-left: 4px solid {ACCENT};
        }}
        .kpi-fuente.fuente-hab {{
            border-left-color: {SUCCESS};
        }}
        .kpi-fuente-head {{
            margin-bottom: 0.65rem;
            padding-bottom: 0.55rem;
            border-bottom: 1px solid {LINE};
        }}
        .kpi-fuente-tag {{
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: {ACCENT};
            margin-bottom: 0.2rem;
        }}
        .kpi-fuente.fuente-hab .kpi-fuente-tag {{
            color: {SUCCESS};
        }}
        .kpi-fuente-title {{
            font-family: 'Source Serif 4', Georgia, serif;
            font-size: 1.15rem;
            font-weight: 700;
            color: {NAVY};
            margin: 0 0 0.25rem 0;
            line-height: 1.2;
        }}
        .kpi-fuente-corte {{
            font-size: 0.78rem;
            color: {MUTED};
            line-height: 1.35;
        }}
        .kpi-fuente-corte strong {{
            color: {NAVY};
            font-weight: 600;
        }}
        .kpi-fuente .kpi-strip {{
            margin: 0.15rem 0 0 0;
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
        .kpi-fuente .kpi-strip.kpi-strip-4 {{
            grid-template-columns: repeat(4, minmax(0, 1fr));
        }}
        @media (max-width: 700px) {{
            .kpi-fuente .kpi-strip.kpi-strip-4 {{
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }}
        }}
        .kpi-fuente .kpi-card {{
            padding: 0.65rem 0.75rem 0.55rem;
        }}
        .kpi-fuente .kpi-value {{
            font-size: 1.35rem;
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
    """items: [{label, value, tone?, hint?}]. Columnas = nº de ítems (máx. 5)."""
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
    n = max(1, min(len(items), 5))
    st.markdown(
        f'<div class="kpi-strip" style="--kpi-cols:{n}">{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )


def render_kpi_rows(items: list[dict]) -> None:
    """KPI en filas horizontales (legibles en columnas estrechas)."""
    rows = []
    for it in items:
        tone = it.get("tone", "")
        cls = f"kpi-row tone-{tone}" if tone else "kpi-row"
        hint = (
            f'<div class="kpi-row-hint">{it["hint"]}</div>'
            if it.get("hint")
            else ""
        )
        rows.append(
            f'<div class="{cls}">'
            f'<div class="kpi-row-label">{it["label"]}</div>'
            f'<div class="kpi-row-right">'
            f'<div class="kpi-row-value">{it["value"]}</div>'
            f"{hint}</div></div>"
        )
    st.markdown(
        f'<div class="kpi-rows">{"".join(rows)}</div>',
        unsafe_allow_html=True,
    )


def render_kpi_inline(items: list[dict]) -> None:
    """
    Desglose compacto en una sola franja (estilo panel ejecutivo).
    items: [{label, value, color, pct?}] — sin tarjetas.
    """
    cells = []
    for it in items:
        color = it.get("color") or NAVY
        pct = (
            f'<div class="kpi-inline-pct">{it["pct"]}</div>'
            if it.get("pct")
            else ""
        )
        cells.append(
            f'<div class="kpi-inline-item">'
            f'<div class="kpi-inline-label">{it["label"]}</div>'
            f'<div class="kpi-inline-value" style="color:{color}">{it["value"]}</div>'
            f"{pct}</div>"
        )
    st.markdown(
        f'<div class="kpi-inline">{"".join(cells)}</div>',
        unsafe_allow_html=True,
    )


def render_sidebar_nav(active_item: str) -> str:
    """
    Menú izquierdo: Inicio + secciones (las pestañas van en la pantalla).
    Devuelve el id de ítem activo (o 'inicio').
    """
    from nav_schema import HOME_ID, NAV_SECTIONS, resolve_nav

    st.markdown("### Navegación")
    st.caption("Elige una sección; las subpestañas aparecen en la pantalla.")

    home_on = active_item == HOME_ID
    if st.button(
        "Inicio · índice",
        key="nav_home",
        use_container_width=True,
        type="primary" if home_on else "secondary",
    ):
        st.session_state["nav_item"] = HOME_ID
        st.rerun()

    sec_id, _ = resolve_nav(active_item)
    for sec in NAV_SECTIONS:
        on = sec_id == sec.id and active_item != HOME_ID
        if st.button(
            sec.label,
            key=f"nav_sec_{sec.id}",
            use_container_width=True,
            type="primary" if on else "secondary",
            help=sec.blurb,
        ):
            # Entrar a la sección en su primera pestaña (o conservar si ya estábamos)
            if on and active_item in {it.id for it in sec.items}:
                st.session_state["nav_item"] = active_item
            else:
                st.session_state["nav_item"] = sec.items[0].id
            st.rerun()

    return st.session_state.get("nav_item", HOME_ID)


def _corte_fuente_label(summary: dict, fuente: str) -> tuple[str, str]:
    """
    (archivo, fecha_corte_legible).
    Fecha desde el nombre del archivo (YYYY-MM-DD); si no hay, indica cruce.
    """
    import re
    from pathlib import Path

    if fuente == "1x10":
        arch = summary.get("corte_1x10_archivo") or Path(
            str(summary.get("source_1x10") or "")
        ).name
    else:
        arch = summary.get("corte_habitable_archivo") or Path(
            str(summary.get("source_habitable") or "")
        ).name

    arch = arch or "(sin archivo)"
    m = re.search(
        r"(20\d{2})[-_](\d{2})[-_](\d{2})(?:[-_](\d{2})[-_]?(\d{2}))?",
        arch,
    )
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        fecha = f"{d}/{mo}/{y}"
        if m.group(4) and m.group(5):
            fecha += f" {m.group(4)}:{m.group(5)}"
    else:
        gen = summary.get("corte_generado_en") or "—"
        fecha = f"sin fecha en archivo · cruce {gen}"
    return str(arch), fecha


def render_home_index(
    summary: dict | None = None,
    hab=None,
) -> None:
    """Pantalla de inicio con panorama rápido + índice de secciones."""
    from nav_schema import NAV_SECTIONS

    if summary is not None:
        n_1x10 = int(summary.get("n_1x10", 0) or 0)
        n_atend = int(summary.get("coincide_auto", 0) or 0)
        n_pend = int(summary.get("solo_1x10", 0) or 0)
        n_hab = int(summary.get("n_hab", 0) or 0)
        pct_at = 100.0 * n_atend / max(n_1x10, 1)

        n_verde = n_ama = n_rojo = n_neg = 0
        if hab is not None and len(hab) and "etiqueta_n" in hab.columns:
            vc = hab["etiqueta_n"].astype(str).str.upper().value_counts()
            n_verde = int(vc.get("VERDE", 0))
            n_ama = int(vc.get("AMARILLO", 0))
            n_rojo = int(vc.get("ROJO", 0))
            n_neg = int(vc.get("NEGRO", 0))

        def _fn(n: int) -> str:
            return f"{int(n):,}".replace(",", ".")

        arch_1, fecha_1 = _corte_fuente_label(summary, "1x10")
        arch_h, fecha_h = _corte_fuente_label(summary, "hab")
        gen = summary.get("corte_generado_en") or "—"

        st.markdown(
            "##### Panorama por fuente",
        )
        st.caption(
            "Cada bloque es una fuente distinta, con su propio corte de datos."
        )

        from streamlit_echarts import st_echarts

        from charts_echarts import ETIQUETA_COLORS, HOME_1X10_COLORS, donut

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(
                f"""
                <div class="kpi-fuente fuente-1x10">
                  <div class="kpi-fuente-head">
                    <div class="kpi-fuente-tag">Fuente A · demanda ciudadana</div>
                    <div class="kpi-fuente-title">1×10</div>
                    <div class="kpi-fuente-corte">
                      Corte de esta fuente: <strong>{fecha_1}</strong><br/>
                      Archivo: <strong>{arch_1}</strong>
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            render_kpi_rows(
                [
                    {
                        "label": "Solicitudes",
                        "value": _fn(n_1x10),
                        "tone": "info",
                    },
                ]
            )
            pct_pend = 100.0 * n_pend / max(n_atend + n_pend, 1)
            render_kpi_inline(
                [
                    {
                        "label": "Ya atendidas",
                        "value": _fn(n_atend),
                        "color": HOME_1X10_COLORS["atendidas"],
                        "pct": f"{pct_at:.1f}%",
                    },
                    {
                        "label": "Pendientes",
                        "value": _fn(n_pend),
                        "color": HOME_1X10_COLORS["pendientes"],
                        "pct": f"{pct_pend:.1f}%",
                    },
                ]
            )
            st_echarts(
                donut(
                    f"Atención · {pct_at:.1f}% ya atendidas",
                    ["Ya atendidas", "Pendientes"],
                    [n_atend, n_pend],
                    [
                        HOME_1X10_COLORS["atendidas"],
                        HOME_1X10_COLORS["pendientes"],
                    ],
                ),
                height="280px",
                key="home_donut_1x10",
            )
        with col_b:
            st.markdown(
                f"""
                <div class="kpi-fuente fuente-hab">
                  <div class="kpi-fuente-head">
                    <div class="kpi-fuente-tag">Fuente B · inspecciones de campo</div>
                    <div class="kpi-fuente-title">Habitable</div>
                    <div class="kpi-fuente-corte">
                      Corte de esta fuente: <strong>{fecha_h}</strong><br/>
                      Archivo: <strong>{arch_h}</strong>
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            render_kpi_rows(
                [
                    {
                        "label": "Inspecciones",
                        "value": _fn(n_hab),
                        "tone": "info",
                    },
                ]
            )
            labs_hab = ["Verde", "Amarillo", "Rojo", "Negro"]
            vals_hab = [n_verde, n_ama, n_rojo, n_neg]
            cols_hab = [
                ETIQUETA_COLORS["VERDE"],
                ETIQUETA_COLORS["AMARILLO"],
                ETIQUETA_COLORS["ROJO"],
                ETIQUETA_COLORS["NEGRO"],
            ]
            render_kpi_inline(
                [
                    {
                        "label": "Verde",
                        "value": _fn(n_verde),
                        "color": ETIQUETA_COLORS["VERDE"],
                        "pct": f"{100 * n_verde / max(n_hab, 1):.1f}%",
                    },
                    {
                        "label": "Amarillo",
                        "value": _fn(n_ama),
                        "color": ETIQUETA_COLORS["AMARILLO"],
                        "pct": f"{100 * n_ama / max(n_hab, 1):.1f}%",
                    },
                    {
                        "label": "Rojo",
                        "value": _fn(n_rojo),
                        "color": ETIQUETA_COLORS["ROJO"],
                        "pct": f"{100 * n_rojo / max(n_hab, 1):.1f}%",
                    },
                    {
                        "label": "Negro",
                        "value": _fn(n_neg),
                        "color": ETIQUETA_COLORS["NEGRO"],
                        "pct": f"{100 * n_neg / max(n_hab, 1):.1f}%",
                    },
                ]
            )
            st_echarts(
                donut("Distribución por etiqueta", labs_hab, vals_hab, cols_hab),
                height="280px",
                key="home_donut_hab",
            )

        st.caption(
            f"**Dos fuentes, dos cortes distintos.** "
            f"El cruce espacial entre ambas se generó el **{gen}**. "
            "Detalle en «Información general por fuentes»."
        )

    render_section(
        "Índice del tablero",
        "Pulsa el nombre de una subsección para abrirla. Desde cualquier pantalla "
        "puedes volver al índice general.",
    )

    mid = (len(NAV_SECTIONS) + 1) // 2
    left_secs = NAV_SECTIONS[:mid]
    right_secs = NAV_SECTIONS[mid:]

    def _render_exec_column(sections: tuple) -> None:
        for sec in sections:
            st.markdown(
                f'<div class="nav-exec-sec">'
                f'<div class="nav-exec-sec-title">{sec.label}</div>'
                f'<div class="nav-exec-sec-blurb">{sec.blurb}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
            for it in sec.items:
                st.markdown('<div class="nav-exec-item">', unsafe_allow_html=True)
                if st.button(
                    it.label,
                    key=f"home_go_item_{it.id}",
                    use_container_width=False,
                ):
                    st.session_state["nav_item"] = it.id
                    st.rerun()
                st.markdown(
                    f'<div class="nav-exec-item-blurb">{it.blurb}</div></div>',
                    unsafe_allow_html=True,
                )

    col_l, col_r = st.columns(2, gap="large")
    with col_l:
        st.markdown('<div class="nav-exec">', unsafe_allow_html=True)
        _render_exec_column(left_secs)
        st.markdown("</div>", unsafe_allow_html=True)
    with col_r:
        st.markdown('<div class="nav-exec">', unsafe_allow_html=True)
        _render_exec_column(right_secs)
        st.markdown("</div>", unsafe_allow_html=True)


def render_back_to_index() -> None:
    """Vínculo ejecutivo para volver al índice general."""
    from nav_schema import HOME_ID

    st.markdown('<div class="nav-back">', unsafe_allow_html=True)
    if st.button("← Índice general", key="nav_back_home"):
        st.session_state["nav_item"] = HOME_ID
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_page_crumb(section_label: str, item_label: str) -> None:
    st.markdown(
        f'<div class="nav-crumb">{section_label} · {item_label}</div>',
        unsafe_allow_html=True,
    )


def render_section_subtabs(section) -> str:
    """Pestañas internas de una sección (en el área principal)."""
    options = [(it.id, it.label) for it in section.items]
    return render_section_tabs(
        options,
        state_key="nav_item",
        heading=f"Pestañas · {section.label}",
    )
