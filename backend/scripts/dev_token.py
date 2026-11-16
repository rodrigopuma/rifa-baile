"""SOMENTE DESENVOLVIMENTO: gera um JWT HS256 (formato Supabase) para testar o /admin sem
um projeto Supabase. Requer SUPABASE_JWT_SECRET definido e ENVIRONMENT != production.

  python -m scripts.dev_token --email dev@local   # também cadastra o admin local
"""
from __future__ import annotations

import argparse
import time
import uuid

import jwt

from app.config import get_settings
from app.db import new_session
from app.models import AdminUser


def main() -> None:
    s = get_settings()
    if s.environment == "production" or not s.supabase_jwt_secret:
        raise SystemExit("Indisponível: defina SUPABASE_JWT_SECRET e use ENVIRONMENT=development.")
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", default="dev@local")
    ap.add_argument("--hours", type=int, default=8)
    args = ap.parse_args()
    uid = uuid.uuid5(uuid.NAMESPACE_DNS, args.email)
    with new_session() as db:
        if not db.get(AdminUser, uid):
            db.add(AdminUser(id=uid, email=args.email, name="Admin de desenvolvimento"))
            db.commit()
    now = int(time.time())
    token = jwt.encode({"sub": str(uid), "email": args.email, "aud": s.supabase_jwt_audience,
                        "role": "authenticated", "iat": now, "exp": now + args.hours * 3600},
                       s.supabase_jwt_secret, algorithm="HS256")
    print(token)


if __name__ == "__main__":
    main()
