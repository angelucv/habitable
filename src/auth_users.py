"""Usuarios locales del BI: roles, hash de clave y TOTP (Google Authenticator)."""

from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import bcrypt
import pyotp

ROOT = Path(__file__).resolve().parents[1]
AUTH_DIR = ROOT / "data" / "auth"
USERS_PATH = AUTH_DIR / "users.json"

Role = Literal["ejecutivo", "operador", "admin"]
ROLES: tuple[Role, ...] = ("ejecutivo", "operador", "admin")

ROLE_LABELS = {
    "ejecutivo": "Ejecutivo (agregados)",
    "operador": "Operador (colas / contacto)",
    "admin": "Administrador",
}

TOTP_ISSUER = "CPEH-BI"


@dataclass
class User:
    username: str
    password_hash: str
    role: Role
    totp_secret: str
    totp_enabled: bool = False
    active: bool = True
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "User":
        role = str(d.get("role") or "ejecutivo")
        if role not in ROLES:
            role = "ejecutivo"
        return cls(
            username=str(d.get("username") or "").strip().lower(),
            password_hash=str(d.get("password_hash") or ""),
            role=role,  # type: ignore[arg-type]
            totp_secret=str(d.get("totp_secret") or ""),
            totp_enabled=bool(d.get("totp_enabled", False)),
            active=bool(d.get("active", True)),
            created_at=str(d.get("created_at") or ""),
        )


def _ensure_dir() -> None:
    AUTH_DIR.mkdir(parents=True, exist_ok=True)


def load_users() -> dict[str, User]:
    _ensure_dir()
    if not USERS_PATH.exists():
        return {}
    try:
        raw = json.loads(USERS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    users: dict[str, User] = {}
    for item in raw.get("users", []):
        u = User.from_dict(item)
        if u.username:
            users[u.username] = u
    return users


def save_users(users: dict[str, User]) -> None:
    _ensure_dir()
    payload = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "users": [u.to_dict() for u in users.values()],
    }
    tmp = USERS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(USERS_PATH)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode(
        "ascii"
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("ascii")
        )
    except Exception:
        return False


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(username: str, secret: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(
        name=username, issuer_name=TOTP_ISSUER
    )


def verify_totp(secret: str, code: str) -> bool:
    code = (code or "").strip().replace(" ", "")
    if not secret or not code:
        return False
    totp = pyotp.TOTP(secret)
    # valid_window=1 tolera desfase de reloj ±30s
    return bool(totp.verify(code, valid_window=1))


def get_user(username: str) -> User | None:
    return load_users().get(username.strip().lower())


def create_user(
    username: str,
    password: str,
    role: Role = "operador",
    *,
    totp_secret: str | None = None,
) -> User:
    username = username.strip().lower()
    if not username or not password:
        raise ValueError("Usuario y contraseña son obligatorios.")
    if role not in ROLES:
        raise ValueError(f"Rol inválido: {role}")
    users = load_users()
    if username in users:
        raise ValueError(f"El usuario «{username}» ya existe.")
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
        totp_secret=totp_secret or new_totp_secret(),
        totp_enabled=False,
        active=True,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    users[username] = user
    save_users(users)
    return user


def update_user(user: User) -> None:
    users = load_users()
    users[user.username] = user
    save_users(users)


def set_totp_enabled(username: str, enabled: bool = True) -> User:
    user = get_user(username)
    if not user:
        raise ValueError("Usuario no encontrado.")
    user.totp_enabled = enabled
    update_user(user)
    return user


def reset_totp(username: str) -> User:
    user = get_user(username)
    if not user:
        raise ValueError("Usuario no encontrado.")
    user.totp_secret = new_totp_secret()
    user.totp_enabled = False
    update_user(user)
    return user


def authenticate_password(username: str, password: str) -> User | None:
    user = get_user(username)
    if not user or not user.active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def has_any_users() -> bool:
    return bool(load_users())


def bootstrap_token_ok(token: str) -> bool:
    """En producción exige BI_PASSWORD/BI_BOOTSTRAP_TOKEN para crear el primer admin."""
    import os

    if not _env_production():
        return True
    expected = (
        os.environ.get("BI_BOOTSTRAP_TOKEN", "").strip()
        or os.environ.get("BI_PASSWORD", "").strip()
    )
    if not expected:
        return False
    return secrets.compare_digest(
        (token or "").encode("utf-8"), expected.encode("utf-8")
    )


def _env_production() -> bool:
    import os

    if os.environ.get("BI_REQUIRE_AUTH", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return True
    return os.environ.get("BI_ENV", "").strip().lower() in (
        "production",
        "prod",
        "ministerio",
        "ministry",
    )


def role_can_upload(role: str) -> bool:
    return role == "admin"


def role_can_manage_users(role: str) -> bool:
    return role == "admin"


def role_can_see_contact(role: str) -> bool:
    """PII de contacto: operador y admin (siguiente paso: enmascarar para ejecutivo)."""
    return role in ("operador", "admin")
