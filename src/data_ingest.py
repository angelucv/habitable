"""Carga de archivos fuente 1×10 y Habitable desde el BI."""

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
    from secure_io import write_bytes

    _ensure_upload_dir()
    write_bytes(dest, bytes(uploaded.getbuffer()))
    return dest


def _resolve_hab_path() -> Path | None:
    """Prefiere CSV reciente; si no, Excel cargado."""
    csv_p = UPLOAD_DIR / "inspecciones_habitable.csv"
    xlsx_p = UPLOAD_DIR / "inspecciones_habitable.xlsx"
    cands = [p for p in (csv_p, xlsx_p) if p.exists()]
    if not cands:
        return None
    return max(cands, key=lambda p: p.stat().st_mtime)


def render_upload_panel() -> None:
    """Sección ejecutiva: cargar 1×10 y Habitable → regenerar cruce."""
    render_section(
        "Cargar datos y actualizar cruce",
        "Sube el Excel de solicitudes 1×10 y el Excel/CSV de inspecciones Habitable. "
        "Al procesar se regeneran el mapa y los dos análisis.",
    )

    _ensure_upload_dir()
    path_1x10 = UPLOAD_DIR / "solicitudes_1x10.xlsx"
    path_hab_xlsx = UPLOAD_DIR / "inspecciones_habitable.xlsx"
    path_hab_csv = UPLOAD_DIR / "inspecciones_habitable.csv"
    path_hab_current = _resolve_hab_path()

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
            "Excel o CSV de inspecciones Habitable",
            type=["xlsx", "xls", "csv"],
            key="upload_hab",
            label_visibility="collapsed",
        )
        sheet = st.text_input(
            "Hoja Habitable (solo Excel)",
            value="Inspecciones",
            help="Nombre de la hoja si el archivo es Excel. En CSV se ignora.",
        )
        if path_hab_current is not None and not f2:
            st.caption(f"En uso: {path_hab_current.name}")

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
            name = (getattr(f2, "name", "") or "").lower()
            dest = path_hab_csv if name.endswith(".csv") else path_hab_xlsx
            _save_upload(f2, dest)
            # Evitar que un archivo viejo del otro formato gane por mtime
            other = path_hab_xlsx if dest == path_hab_csv else path_hab_csv
            if other.exists():
                other.unlink()

        path_hab = _resolve_hab_path()
        if not path_1x10.exists() or path_hab is None:
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
                from audit_log import log_event

                log_event(
                    "pipeline_fail",
                    username=str(st.session_state.get("bi_username") or ""),
                    role=str(st.session_state.get("bi_role") or ""),
                    detail={"error": str(exc)[:300]},
                )
                st.error(f"No se pudo procesar: {exc}")
                return

        from audit_log import log_event

        log_event(
            "pipeline_ok",
            username=str(st.session_state.get("bi_username") or ""),
            role=str(st.session_state.get("bi_role") or ""),
            detail={
                "n_1x10": summary.get("n_1x10"),
                "n_hab": summary.get("n_hab"),
                "file_1x10": path_1x10.name,
                "file_hab": path_hab.name if path_hab else "",
            },
        )
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
