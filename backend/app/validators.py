from __future__ import annotations

import re

_DIGITS = re.compile(r"\D+")


def only_digits(value: str) -> str:
    return _DIGITS.sub("", value or "")


def is_valid_cpf(value: str) -> bool:
    cpf = only_digits(value)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for size in (9, 10):
        total = sum(int(cpf[i]) * (size + 1 - i) for i in range(size))
        digit = (total * 10) % 11 % 10
        if digit != int(cpf[size]):
            return False
    return True


def mask_cpf(value: str) -> str:
    cpf = only_digits(value)
    return f"***.{cpf[3:6]}.{cpf[6:9]}-**" if len(cpf) == 11 else ""


def normalize_br_phone(value: str) -> str | None:
    """Aceita celular brasileiro com DDD (11 dígitos), opcionalmente com +55."""
    d = only_digits(value)
    if len(d) == 13 and d.startswith("55"):
        d = d[2:]
    if len(d) != 11 or d[2] != "9" or d[0] == "0":
        return None
    return d


def format_phone(d: str) -> str:
    return f"({d[:2]}) {d[2:7]}-{d[7:]}" if len(d) == 11 else d


def mask_phone(d: str) -> str:
    return f"({d[:2]}) *****-{d[7:]}" if len(d) == 11 else ""
