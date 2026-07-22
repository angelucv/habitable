"""Auditoría append-only de accesos y descargas (ministerio).

Registro en ``data/audit/audit.jsonl`` (una línea JSON por evento).
No se versiona en Git.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "data" / "audit"
AUDIT_PATH = AUDIT_DIR / "audit.jsonl"


def _ensure_dir() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def log_event(
    action: str,
    *,
    username: str | None = None,
    role: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Escribe un evento de auditoría. Fallos de disco no tumbaron la app."""
    try:
        _ensure_dir()
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "username": username or "",
            "role": role or "",
            "host": os.environ.get("COMPUTERNAME")
            or os.environ.get("HOSTNAME")
            or "",
            "detail": detail or {},
        }
        with AUDIT_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read_events(limit: int = 100) -> list[dict[str, Any]]:
    if not AUDIT_PATH.exists():
        return []
    try:
        lines = AUDIT_PATH.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-max(limit, 1) :]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return list(reversed(out))
