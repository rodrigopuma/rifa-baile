"""Tokens de acesso a pedidos e autenticação administrativa (Supabase Auth)."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from functools import lru_cache

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import AdminUser

_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # sem 0/O/1/I


def new_order_code() -> str:
    return "RF-" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(7))


def new_access_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def token_matches(token: str | None, token_hash: str) -> bool:
    if not token:
        return False
    return hmac.compare_digest(hash_token(token), token_hash)


# ---- Admin -----------------------------------------------------------------

@lru_cache
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True)


def decode_supabase_jwt(token: str) -> dict:
    s = get_settings()
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "")
        if alg == "HS256":
            if not s.supabase_jwt_secret:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Autenticação não configurada")
            return jwt.decode(token, s.supabase_jwt_secret, algorithms=["HS256"],
                              audience=s.supabase_jwt_audience)
        if alg in ("RS256", "ES256") and s.supabase_url:
            key = _jwks_client(f"{s.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json")
            signing_key = key.get_signing_key_from_jwt(token)
            return jwt.decode(token, signing_key.key, algorithms=[alg], audience=s.supabase_jwt_audience)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão inválida ou expirada") from exc
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token não suportado")


def require_admin(authorization: str | None = Header(default=None),
                  db: Session = Depends(get_db)) -> AdminUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Autenticação necessária",
                            headers={"WWW-Authenticate": "Bearer"})
    claims = decode_supabase_jwt(authorization.split(" ", 1)[1].strip())
    try:
        user_id = uuid.UUID(str(claims.get("sub")))
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token sem usuário") from exc
    admin = db.get(AdminUser, user_id)
    if not admin or not admin.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Usuário sem permissão administrativa")
    return admin
