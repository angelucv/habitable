"""Helpers de UI con auditoría (descargas)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from audit_log import log_event


def _session_actor() -> tuple[str, str]:
    return (
        str(st.session_state.get("bi_username") or ""),
        str(st.session_state.get("bi_role") or ""),
    )


def download_button(
    label: str,
    data: Any,
    file_name: str,
    *,
    mime: str | None = None,
    key: str | None = None,
    help: str | None = None,
    type: str | None = None,
    use_container_width: bool = False,
    audit_action: str = "download",
) -> bool:
    """``st.download_button`` + registro de auditoría al hacer clic."""
    kwargs: dict[str, Any] = {
        "label": label,
        "data": data,
        "file_name": file_name,
        "use_container_width": use_container_width,
    }
    if mime is not None:
        kwargs["mime"] = mime
    if key is not None:
        kwargs["key"] = key
    if help is not None:
        kwargs["help"] = help
    if type is not None:
        kwargs["type"] = type

    clicked = st.download_button(**kwargs)
    if clicked:
        user, role = _session_actor()
        nbytes = None
        try:
            if isinstance(data, (bytes, bytearray)):
                nbytes = len(data)
            elif isinstance(data, str):
                nbytes = len(data.encode("utf-8"))
        except Exception:
            nbytes = None
        log_event(
            audit_action,
            username=user,
            role=role,
            detail={
                "file_name": file_name,
                "label": label,
                "mime": mime or "",
                "bytes": nbytes,
            },
        )
    return bool(clicked)
