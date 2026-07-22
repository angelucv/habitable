"""Cifrado en reposo (Fernet) para datos sensibles del BI.

Clave: variable de entorno ``BI_DATA_KEY`` (url-safe base64 de Fernet)
o ``st.secrets["crypto"]["data_key"]``.

Formato en disco: magic ``CPEHENC1\\0`` + token Fernet.
Sin clave en desarrollo: lectura/escritura en claro (passthrough).
En producción (``BI_REQUIRE_AUTH`` / ``BI_ENV``) la clave es obligatoria.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

MAGIC = b"CPEHENC1\0"


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def is_production_mode() -> bool:
    if _env_truthy("BI_REQUIRE_AUTH"):
        return True
    env = os.environ.get("BI_ENV", "").strip().lower()
    return env in ("production", "prod", "ministerio", "ministry")


def generate_key() -> str:
    return Fernet.generate_key().decode("ascii")


def _key_material() -> str | None:
    raw = os.environ.get("BI_DATA_KEY", "").strip()
    if raw:
        return raw
    try:
        import streamlit as st

        crypto = st.secrets.get("crypto", {})  # type: ignore[attr-defined]
        if isinstance(crypto, dict):
            k = str(crypto.get("data_key") or "").strip()
            if k:
                return k
        k2 = str(st.secrets.get("BI_DATA_KEY", "") or "").strip()  # type: ignore[attr-defined]
        if k2:
            return k2
    except Exception:
        pass
    return None


def encryption_enabled() -> bool:
    return bool(_key_material())


def _fernet() -> Fernet:
    key = _key_material()
    if not key:
        raise RuntimeError(
            "Falta BI_DATA_KEY (o secrets crypto.data_key) para cifrar/descifrar datos."
        )
    try:
        return Fernet(key.encode("ascii") if isinstance(key, str) else key)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "BI_DATA_KEY no es una clave Fernet válida. "
            "Genere una con: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        ) from exc


def assert_crypto_ready() -> None:
    """En producción exige clave; si hay archivos cifrados, también exige clave."""
    if is_production_mode() and not encryption_enabled():
        raise RuntimeError(
            "Modo producción: defina BI_DATA_KEY para cifrado en reposo de datos."
        )


def is_encrypted_blob(data: bytes) -> bool:
    return data.startswith(MAGIC)


def is_encrypted_file(path: Path | str) -> bool:
    p = Path(path)
    if not p.is_file() or p.stat().st_size < len(MAGIC):
        return False
    with p.open("rb") as f:
        return f.read(len(MAGIC)) == MAGIC


def read_bytes(path: Path | str) -> bytes:
    raw = Path(path).read_bytes()
    if not is_encrypted_blob(raw):
        return raw
    try:
        return _fernet().decrypt(raw[len(MAGIC) :])
    except InvalidToken as exc:
        raise RuntimeError(
            f"No se pudo descifrar {path}. Verifique BI_DATA_KEY."
        ) from exc


def write_bytes(path: Path | str, data: bytes, *, encrypt: bool | None = None) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    do_enc = encryption_enabled() if encrypt is None else encrypt
    if do_enc:
        out = MAGIC + _fernet().encrypt(data)
    else:
        out = data
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_bytes(out)
    tmp.replace(p)


def read_text(path: Path | str, encoding: str = "utf-8") -> str:
    return read_bytes(path).decode(encoding)


def write_text(
    path: Path | str, text: str, *, encoding: str = "utf-8", encrypt: bool | None = None
) -> None:
    write_bytes(path, text.encode(encoding), encrypt=encrypt)


def read_json(path: Path | str) -> Any:
    return json.loads(read_text(path))


def write_json(
    path: Path | str, obj: Any, *, indent: int | None = 2, encrypt: bool | None = None
) -> None:
    write_text(
        path,
        json.dumps(obj, ensure_ascii=False, indent=indent),
        encrypt=encrypt,
    )


def read_parquet(path: Path | str):
    import pandas as pd

    return pd.read_parquet(io.BytesIO(read_bytes(path)))


def write_parquet(df, path: Path | str, *, index: bool = False, encrypt: bool | None = None) -> None:
    buf = io.BytesIO()
    df.to_parquet(buf, index=index)
    write_bytes(path, buf.getvalue(), encrypt=encrypt)


def encrypt_file_in_place(path: Path | str) -> bool:
    """Cifra un archivo claro. Devuelve True si se cifró; False si ya estaba cifrado."""
    p = Path(path)
    raw = p.read_bytes()
    if is_encrypted_blob(raw):
        return False
    if not encryption_enabled():
        raise RuntimeError("Defina BI_DATA_KEY antes de cifrar archivos.")
    write_bytes(p, raw, encrypt=True)
    return True


def decrypt_file_in_place(path: Path | str) -> bool:
    """Descifra a claro (solo mantenimiento)."""
    p = Path(path)
    raw = p.read_bytes()
    if not is_encrypted_blob(raw):
        return False
    plain = read_bytes(p)
    write_bytes(p, plain, encrypt=False)
    return True
