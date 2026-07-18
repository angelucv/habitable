"""
Carga de Excel desde la interfaz Streamlit
==========================================

Permite a cualquier colaborador autenticado:
1. Subir el archivo de solicitudes 1×10.
2. Subir el archivo de inspecciones Habitable.
3. Ejecutar el pipeline (``prepare_data.run_pipeline``).
4. Invalidar caché del BI para que las tres pestañas muestren datos nuevos.

Los archivos se guardan en ``data/uploads/`` (no se versionan en Git).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st

from prepare_data import run_pipeline
from ui_theme import render_section

ROOT = Path(__file__).resolve().parents[1]
UPLOAD_DIR = ROOT / "data" / "uploads"
META_PATH = UPLOAD_DIR / "last_upload.json"


def _ensure_upload_dir() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _save_upload(uploaded, dest: Path) -> Path:
    _ensure_upload_dir()
    dest.write_bytes(uploaded.getbuffer())
    return dest


def render_upload_panel() -> None:
    """Sección ejecutiva: cargar Excel 1×10 y Habitable → regenerar cruce."""
    render_section(
        "Cargar datos y actualizar cruce",
        "Sube los Excel de solicitudes 1×10 e inspecciones Habitable. "
        "Al procesar se regeneran el mapa y los dos análisis.",
    )

    _ensure_upload_dir()
    path_1x10 = UPLOAD_DIR / "solicitudes_1x10.xlsx"
    path_hab = UPLOAD_DIR / "inspecciones_habitable.xlsx"

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Archivo 1×10** (solicitudes)")
        f1 = st.file_uploader(
            "Excel de solicitudes ciudadanas",
            type=["xlsx", "xls"],
            key="upload_1x10",
            label_visibility="collapsed",
        )
        if path_1x10.exists() and not f1:
            st.caption(f"En uso: {path_1x10.name}")
    with c2:
        st.markdown("**Archivo Habitable** (inspecciones)")
        f2 = st.file_uploader(
            "Excel de inspecciones Habitable",
            type=["xlsx", "xls"],
            key="upload_hab",
            label_visibility="collapsed",
        )
        sheet = st.text_input(
            "Hoja Habitable",
            value="Inspecciones",
            help="Nombre de la hoja (por defecto Inspecciones).",
        )
        if path_hab.exists() and not f2:
            st.caption(f"En uso: {path_hab.name}")

    b1, b2 = st.columns([2, 1])
    with b1:
        run = st.button(
            "Procesar cruce y actualizar pestañas",
            type="primary",
            use_container_width=True,
        )
    with b2:
        st.caption("Puede tardar 1–2 minutos con archivos grandes.")

    if run:
        if f1:
            _save_upload(f1, path_1x10)
        if f2:
            _save_upload(f2, path_hab)

        if not path_1x10.exists() or not path_hab.exists():
            st.error(
                "Se necesitan ambos archivos. Carga 1×10 y Habitable "
                "(o deja los ya guardados en una carga previa)."
            )
            return

        with st.spinner("Procesando limpieza, matching y unificación…"):
            try:
                summary = run_pipeline(
                    solicitudes_path=path_1x10,
                    habitable_path=path_hab,
                    habitable_sheet=sheet.strip() or "Inspecciones",
                    quiet=True,
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"No se pudo procesar: {exc}")
                return

        META_PATH.write_text(
            datetime.now().isoformat(timespec="seconds"),
            encoding="utf-8",
        )
        st.success(
            f"Cruce actualizado · 1×10: {summary.get('n_1x10', 0):,} · "
            f"Habitable: {summary.get('n_hab', 0):,} · "
            f"Ya atendidas: {summary.get('coincide_auto', 0):,}".replace(",", ".")
        )
        st.cache_data.clear()
        st.rerun()
