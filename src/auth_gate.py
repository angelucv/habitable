"""Gate de acceso al BI (contraseña compartida).

Fuentes (en orden):
  1. Variable de entorno ``BI_PASSWORD``
  2. ``st.secrets["auth"]["password"]`` o ``st.secrets["BI_PASSWORD"]``

Comportamiento:
  - Si hay contraseña configurada → exige login antes de datos/carga.
  - Si no hay contraseña y ``BI_REQUIRE_AUTH=1`` (o ``BI_ENV=production``) → bloquea.
  - Si no hay contraseña en desarrollo → aviso y acceso abierto (solo local).
"""

from __future__ import annotations

import hmac
import os
from typing import Optional

import streamlit as st

SESSION_KEY = "bi_authenticated"


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _is_production_mode() -> bool:
    if _env_truthy("BI_REQUIRE_AUTH"):
        return True
    env = os.environ.get("BI_ENV", "").strip().lower()
    return env in ("production", "prod", "ministerio", "ministry")


def get_configured_password() -> Optional[str]:
    pwd = os.environ.get("BI_PASSWORD", "").strip()
    if pwd:
        return pwd
    try:
        auth = st.secrets.get("auth", None)
        if auth is not None:
            p = str(auth.get("password", "") or "").strip()
            if p:
                return p
        p2 = str(st.secrets.get("BI_PASSWORD", "") or "").strip()
        if p2:
            return p2
    except Exception:
        # Sin secrets.toml / Streamlit Secrets no configurados
        pass
    return None


def is_authenticated() -> bool:
    return bool(st.session_state.get(SESSION_KEY, False))


def logout() -> None:
    st.session_state.pop(SESSION_KEY, None)


def _check_password(entered: str, expected: str) -> bool:
    if not entered or not expected:
        return False
    return hmac.compare_digest(entered.encode("utf-8"), expected.encode("utf-8"))


def require_login() -> bool:
    """Muestra formulario de acceso si hace falta.

    Returns:
        True si la sesión puede continuar; False si debe detenerse (ya hizo st.stop
        o debe hacerse stop tras el return — esta función llama st.stop()).
    """
    expected = get_configured_password()

    if expected is None:
        if _is_production_mode():
            st.error(
                "Acceso bloqueado: no hay contraseña configurada. "
                "Defina `BI_PASSWORD` (variable de entorno) o "
                "`[auth] password` en secrets del servidor."
            )
            st.stop()
            return False
        st.warning(
            "Tablero **sin autenticación** (modo desarrollo). "
            "Para producción ministerial configure `BI_PASSWORD` o "
            "`BI_REQUIRE_AUTH=1`."
        )
        return True

    if is_authenticated():
        return True

    st.markdown("### Acceso restringido")
    st.caption(
        "Tablero de cruce 1×10 × Habitable. Introduzca la clave institucional."
    )
    with st.form("bi_login_form", clear_on_submit=False):
        entered = st.text_input("Contraseña", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)
    if submitted:
        if _check_password(entered, expected):
            st.session_state[SESSION_KEY] = True
            st.rerun()
        st.error("Contraseña incorrecta.")
    st.stop()
    return False
