"""Crear admin inicial por CLI (alternativa a la UI de bootstrap).

Ejemplo:
  .\\.venv\\Scripts\\python.exe scripts\\bootstrap_bi_admin.py --user admin --password \"TuClaveSegura\"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from auth_users import create_user, has_any_users  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Bootstrap admin BI CPEH")
    p.add_argument("--user", default="admin")
    p.add_argument("--password", required=True)
    p.add_argument("--force", action="store_true", help="Crear aunque ya existan usuarios")
    args = p.parse_args()
    if has_any_users() and not args.force:
        print("Ya hay usuarios. Use --force para añadir otro admin.")
        sys.exit(1)
    u = create_user(args.user, args.password, role="admin")
    print(f"OK admin «{u.username}». Al entrar en el BI deberá escanear el QR de Google Authenticator.")


if __name__ == "__main__":
    main()
