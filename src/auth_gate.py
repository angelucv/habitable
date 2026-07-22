"""Gate de acceso multi-usuario + TOTP (Google Authenticator)."""

from __future__ import annotations

import io
import os
from typing import Optional

import streamlit as st

from auth_users import (
    ROLE_LABELS,
    ROLES,
    authenticate_password,
    bootstrap_token_ok,
    create_user,
    get_user,
    has_any_users,
    role_can_manage_users,
    role_can_see_contact,
    role_can_upload,
    set_totp_enabled,
    totp_provisioning_uri,
    verify_totp,
)

SESSION_AUTH = "bi_authenticated"
SESSION_USER = "bi_username"
SESSION_ROLE = "bi_role"
SESSION_ENROLL = "bi_enroll_username"


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _is_production_mode() -> bool:
    if _env_truthy("BI_REQUIRE_AUTH"):
        return True
    env = os.environ.get("BI_ENV", "").strip().lower()
    return env in ("production", "prod", "ministerio", "ministry")


def current_username() -> Optional[str]:
    return st.session_state.get(SESSION_USER)


def current_role() -> Optional[str]:
    return st.session_state.get(SESSION_ROLE)


def is_authenticated() -> bool:
    return bool(st.session_state.get(SESSION_AUTH)) and bool(current_username())


def can_upload() -> bool:
    return role_can_upload(current_role() or "")


def can_see_contact() -> bool:
    return role_can_see_contact(current_role() or "")


def can_manage_users() -> bool:
    return role_can_manage_users(current_role() or "")


def _set_session(username: str, role: str) -> None:
    from audit_log import log_event

    st.session_state[SESSION_AUTH] = True
    st.session_state[SESSION_USER] = username
    st.session_state[SESSION_ROLE] = role
    st.session_state.pop(SESSION_ENROLL, None)
    log_event("login_ok", username=username, role=role)


def logout() -> None:
    from audit_log import log_event

    user = current_username()
    role = current_role()
    log_event("logout", username=user, role=role)
    for k in (SESSION_AUTH, SESSION_USER, SESSION_ROLE, SESSION_ENROLL):
        st.session_state.pop(k, None)


def _qr_image_bytes(uri: str) -> bytes:
    import qrcode

    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _render_enroll(username: str) -> None:
    user = get_user(username)
    if not user:
        st.error("Usuario no encontrado.")
        logout()
        st.stop()
        return

    st.markdown("### Activar Google Authenticator (2FA)")
    st.caption(
        f"Usuario **{username}** · rol **{ROLE_LABELS.get(user.role, user.role)}**. "
        "Escanee el QR con Google Authenticator (u otra app TOTP) y confirme con un código."
    )
    uri = totp_provisioning_uri(user.username, user.totp_secret)
    st.image(_qr_image_bytes(uri), caption="QR TOTP", width=220)
    with st.expander("Clave manual (si no puede escanear)"):
        st.code(user.totp_secret, language=None)

    with st.form("bi_enroll_totp"):
        code = st.text_input("Código de 6 dígitos", max_chars=8, autocomplete="one-time-code")
        ok = st.form_submit_button("Confirmar y activar 2FA", type="primary")
    if ok:
        if verify_totp(user.totp_secret, code):
            set_totp_enabled(username, True)
            _set_session(username, user.role)
            st.success("2FA activado.")
            st.rerun()
        st.error("Código incorrecto o reloj desfasado. Reintente.")
    if st.button("Cancelar y volver al login"):
        logout()
        st.rerun()
    st.stop()


def _render_bootstrap() -> None:
    st.markdown("### Configuración inicial — crear administrador")
    st.caption(
        "No hay usuarios todavía. Cree el primer **admin**. "
        "Luego deberá activar Google Authenticator."
    )
    need_token = _is_production_mode()
    with st.form("bi_bootstrap_admin"):
        token = ""
        if need_token:
            token = st.text_input(
                "Token de arranque (BI_PASSWORD / BI_BOOTSTRAP_TOKEN)",
                type="password",
            )
        username = st.text_input("Usuario admin", value="admin")
        password = st.text_input("Contraseña", type="password")
        password2 = st.text_input("Repetir contraseña", type="password")
        submitted = st.form_submit_button("Crear administrador", type="primary")
    if submitted:
        if not bootstrap_token_ok(token):
            st.error(
                "Token de arranque inválido o ausente. "
                "En producción defina BI_PASSWORD o BI_BOOTSTRAP_TOKEN."
            )
            st.stop()
            return
        if password != password2 or len(password) < 8:
            st.error("Las contraseñas deben coincidir y tener al menos 8 caracteres.")
            st.stop()
            return
        try:
            user = create_user(username, password, role="admin")
        except ValueError as e:
            st.error(str(e))
            st.stop()
            return
        st.session_state[SESSION_ENROLL] = user.username
        st.rerun()
    st.stop()


def _render_login() -> None:
    st.markdown("### Acceso al tablero")
    st.caption(
        "Usuario institucional + contraseña + código de Google Authenticator (si ya está enrolado)."
    )
    with st.form("bi_login_form"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        totp_code = st.text_input(
            "Código 2FA (6 dígitos)",
            help="Obligatorio si ya activó Google Authenticator.",
            max_chars=8,
            autocomplete="one-time-code",
        )
        submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)
    if submitted:
        user = authenticate_password(username, password)
        if not user:
            from audit_log import log_event

            log_event(
                "login_fail",
                username=(username or "").strip().lower(),
                detail={"reason": "bad_credentials"},
            )
            st.error("Usuario o contraseña incorrectos.")
            st.stop()
            return
        if not user.totp_enabled:
            st.session_state[SESSION_ENROLL] = user.username
            st.rerun()
            return
        if not verify_totp(user.totp_secret, totp_code):
            from audit_log import log_event

            log_event(
                "login_fail",
                username=user.username,
                role=user.role,
                detail={"reason": "bad_totp"},
            )
            st.error("Código 2FA incorrecto.")
            st.stop()
            return
        _set_session(user.username, user.role)
        st.rerun()
    st.stop()


def render_user_admin_panel() -> None:
    """Panel simple para que un admin cree usuarios y vea auditoría."""
    if not can_manage_users():
        return
    with st.sidebar.expander("Administrar usuarios", expanded=False):
        st.caption("Crear cuenta y forzar enrolamiento 2FA en el primer acceso.")
        with st.form("bi_create_user"):
            u = st.text_input("Nuevo usuario")
            p = st.text_input("Contraseña temporal", type="password")
            role = st.selectbox(
                "Rol",
                options=list(ROLES),
                format_func=lambda r: ROLE_LABELS.get(r, r),
                index=1,
            )
            go = st.form_submit_button("Crear usuario")
        if go:
            try:
                create_user(u, p, role=role)  # type: ignore[arg-type]
                from audit_log import log_event

                log_event(
                    "user_create",
                    username=current_username(),
                    role=current_role(),
                    detail={"new_user": u.strip().lower(), "new_role": role},
                )
                st.success(f"Usuario «{u}» creado. Debe activar 2FA al entrar.")
            except ValueError as e:
                st.error(str(e))

    with st.sidebar.expander("Auditoría reciente", expanded=False):
        from audit_log import AUDIT_PATH, read_events

        st.caption(f"Registro: `{AUDIT_PATH.name}` (solo admin).")
        events = read_events(40)
        if not events:
            st.info("Sin eventos aún.")
        else:
            import pandas as pd

            rows = [
                {
                    "ts": e.get("ts", "")[:19],
                    "action": e.get("action", ""),
                    "user": e.get("username", ""),
                    "role": e.get("role", ""),
                    "file": (e.get("detail") or {}).get("file_name", ""),
                }
                for e in events
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

def require_login() -> bool:
    """Exige sesión autenticada (+ 2FA). Llama ``st.stop`` si no hay acceso."""
    # Flujo enrolamiento pendiente
    enroll = st.session_state.get(SESSION_ENROLL)
    if enroll:
        _render_enroll(str(enroll))
        return False

    if is_authenticated():
        # Refrescar rol por si cambió en disco
        u = get_user(current_username() or "")
        if not u or not u.active:
            logout()
            st.warning("Sesión inválida. Vuelva a iniciar sesión.")
            st.stop()
            return False
        st.session_state[SESSION_ROLE] = u.role
        return True

    if not has_any_users():
        _render_bootstrap()
        return False

    _render_login()
    return False


# Compatibilidad con llamadas antiguas
def get_configured_password() -> Optional[str]:
    return os.environ.get("BI_PASSWORD", "").strip() or None
