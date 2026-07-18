"""
Carga de Excel desde la interfaz Streamlit
==========================================

Permite a cualquier colaborador autenticado:
1. Subir el archivo de solicitudes 1×10.
2. Subir el archivo de inspecciones Habitable.
3. Ejecutar el pipeline (``prepare_data.run_pipeline``).
4. Invalidar caché del BI para que las tres pestañas muestren datos nuevos.

Por defecto el servicio arranca con un **cruce precargado** en
``data/processed/``. Una carga nueva **sustituye** ese resultado.

Los Excel se guardan en ``data/uploads/`` (no se versionan en Git).
"""

from __future__ import annotations

import gc
import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from prepare_data import run_pipeline
from runtime_limits import allow_heavy_pipeline, is_low_memory
from ui_theme import render_section

ROOT = Path(__file__).resolve().parents[1]
UPLOAD_DIR = ROOT / "data" / "uploads"
PROCESSED = ROOT / "data" / "processed"
META_PATH = UPLOAD_DIR / "last_upload.json"
SEED_META = PROCESSED / "seed_meta.json"


def _ensure_upload_dir() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _save_upload(uploaded, dest: Path) -> Path:
    _ensure_upload_dir()
    dest.write_bytes(uploaded.getbuffer())
    return dest


def data_origin_caption() -> str | None:
    """Texto corto sobre el origen del cruce actual (sidebar / panel)."""
    if META_PATH.exists():
        try:
            ts = META_PATH.read_text(encoding="utf-8").strip()
            return f"Datos actualizados por carga · {ts}"
        except Exception:  # noqa: BLE001
            return "Datos actualizados por carga en la UI"
    if SEED_META.exists():
        try:
            meta = json.loads(SEED_META.read_text(encoding="utf-8"))
            gen = meta.get("generado_en", "")
            return f"Precarga del despliegue · {gen}"
        except Exception:  # noqa: BLE001
            return "Precarga del despliegue"
    if (PROCESSED / "summary.json").exists():
        return "Cruce procesado disponible"
    return None


def render_upload_panel() -> None:
    """Cargar Excel nuevos: al procesar, sustituyen el cruce precargado."""
    ready = (PROCESSED / "solicitudes.parquet").exists() and (
        PROCESSED / "inspecciones.parquet"
    ).exists()

    render_section(
        "Actualizar datos (opcional)",
        "El tablero ya trae un cruce precargado. Si subes Excel nuevos y "
        "procesas, **sustituyen** el resultado actual en mapa y análisis.",
    )

    origin = data_origin_caption()
    if origin:
        st.caption(origin)
    if ready:
        try:
            summary = json.loads(
                (PROCESSED / "summary.json").read_text(encoding="utf-8")
            )
            st.info(
                f"En uso ahora → 1×10: {summary.get('n_1x10', 0):,} · "
                f"Habitable: {summary.get('n_hab', 0):,} · "
                f"Ya atendidas: {summary.get('coincide_auto', 0):,} · "
                f"Pendientes: {summary.get('solo_1x10', 0):,}".replace(",", ".")
            )
        except Exception:  # noqa: BLE001
            pass

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
            st.caption(f"Guardado previo: {path_1x10.name}")
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
            st.caption(f"Guardado previo: {path_hab.name}")

    if is_low_memory() and not allow_heavy_pipeline():
        st.warning(
            "En modo bajo consumo el procesamiento desde Excel está bloqueado. "
            "Define `BI_ALLOW_HEAVY_PIPELINE=1` o desactiva `BI_LOW_MEMORY`."
        )

    b1, b2 = st.columns([2, 1])
    with b1:
        run = st.button(
            "Sustituir cruce con estos archivos",
            type="primary",
            use_container_width=True,
            disabled=is_low_memory() and not allow_heavy_pipeline(),
        )
    with b2:
        st.caption("Reemplaza la precarga · 1–2 min.")

    if run:
        if is_low_memory() and not allow_heavy_pipeline():
            st.error("Pipeline bloqueado en modo bajo consumo.")
            return

        if f1:
            _save_upload(f1, path_1x10)
        if f2:
            _save_upload(f2, path_hab)

        if not path_1x10.exists() or not path_hab.exists():
            st.error(
                "Se necesitan ambos archivos. Carga 1×10 y Habitable "
                "(o deja los ya guardados de una carga previa)."
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
            finally:
                gc.collect()

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        META_PATH.write_text(now, encoding="utf-8")
        # Marca que ya no es la precarga del despliegue
        SEED_META.write_text(
            json.dumps(
                {
                    "origen": "carga_ui",
                    "generado_en": now,
                    "nota": "Sustituyó la precarga del despliegue.",
                    "n_1x10": summary.get("n_1x10"),
                    "n_hab": summary.get("n_hab"),
                    "coincide_auto": summary.get("coincide_auto"),
                    "solo_1x10": summary.get("solo_1x10"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        st.success(
            f"Cruce sustituido · 1×10: {summary.get('n_1x10', 0):,} · "
            f"Habitable: {summary.get('n_hab', 0):,} · "
            f"Ya atendidas: {summary.get('coincide_auto', 0):,}".replace(",", ".")
        )
        st.cache_data.clear()
        st.rerun()
