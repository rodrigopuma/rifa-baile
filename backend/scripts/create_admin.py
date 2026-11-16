"""Autoriza um usuário do Supabase Auth a acessar o painel /admin.

1. Crie o usuário em Supabase > Authentication > Users (e-mail e senha).
2. Copie o UUID do usuário e rode:
     python -m scripts.create_admin --id <UUID> --email admin@exemplo.com --name "Nome"
"""
from __future__ import annotations

import argparse
import uuid

from app.db import new_session
from app.models import AdminUser
from app.services import audit


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--email", required=True)
    ap.add_argument("--name", default="")
    args = ap.parse_args()
    with new_session() as db:
        uid = uuid.UUID(args.id)
        admin = db.get(AdminUser, uid) or AdminUser(id=uid, email=args.email.lower())
        admin.email, admin.name, admin.active = args.email.lower(), args.name, True
        db.add(admin)
        audit.log(db, "admin_granted", entity_type="admin_user", entity_id=uid, details={"email": admin.email})
        db.commit()
        print(f"Administrador autorizado: {admin.email}")


if __name__ == "__main__":
    main()
