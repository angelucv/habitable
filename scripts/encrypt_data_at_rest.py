"""Cifra en reposo los artefactos sensibles del BI (Fernet / BI_DATA_KEY).

Uso:
  # Generar clave y guardarla (no la suba a Git)
  $env:BI_DATA_KEY = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

  python scripts/encrypt_data_at_rest.py
  python scripts/encrypt_data_at_rest.py --generate   # imprime clave nueva y sale
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from secure_io import (  # noqa: E402
    encryption_enabled,
    encrypt_file_in_place,
    generate_key,
    is_encrypted_file,
)

TARGETS = [
    ROOT / "data" / "processed" / "solicitudes.parquet",
    ROOT / "data" / "processed" / "inspecciones.parquet",
    ROOT / "data" / "processed" / "summary.json",
    ROOT / "data" / "auth" / "users.json",
    ROOT / "data" / "uploads" / "solicitudes_1x10.xlsx",
    ROOT / "data" / "uploads" / "inspecciones_habitable.csv",
    ROOT / "data" / "uploads" / "inspecciones_habitable.xlsx",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Cifrado en reposo CPEH BI")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Imprime una BI_DATA_KEY nueva y termina",
    )
    args = parser.parse_args()

    if args.generate:
        print(generate_key())
        return 0

    if not encryption_enabled():
        print(
            "ERROR: defina BI_DATA_KEY antes de cifrar.\n"
            "  python scripts/encrypt_data_at_rest.py --generate\n"
            "  $env:BI_DATA_KEY = '<clave>'\n"
            "  python scripts/encrypt_data_at_rest.py",
            file=sys.stderr,
        )
        return 1

    n_ok = n_skip = n_miss = 0
    for path in TARGETS:
        if not path.exists():
            n_miss += 1
            print(f"  (ausente) {path.relative_to(ROOT)}")
            continue
        if is_encrypted_file(path):
            n_skip += 1
            print(f"  ya cifrado  {path.relative_to(ROOT)}")
            continue
        encrypt_file_in_place(path)
        n_ok += 1
        print(f"  cifrado     {path.relative_to(ROOT)}")

    print(f"\nListo: {n_ok} cifrados, {n_skip} ya cifrados, {n_miss} ausentes.")
    print("Guarde BI_DATA_KEY en el entorno del servidor / Render secrets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
