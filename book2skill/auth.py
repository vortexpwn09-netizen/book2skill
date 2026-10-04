from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any
from uuid import uuid4


PASSWORD_ITERATIONS = 310_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (TypeError, ValueError):
        return False


def create_user(users: list[dict[str, Any]], email: str, password: str) -> dict[str, Any]:
    normalized_email = email.strip().lower()
    if any(user["email"] == normalized_email for user in users):
        raise ValueError(f"User already exists: {normalized_email}")

    user = {
        "id": uuid4().hex,
        "email": normalized_email,
        "password_hash": hash_password(password),
    }
    users.append(user)
    return {"id": user["id"], "email": user["email"]}


def authenticate_user(users: list[dict[str, Any]], email: str, password: str) -> dict[str, Any] | None:
    normalized_email = email.strip().lower()
    for user in users:
        if user["email"] == normalized_email and verify_password(password, user.get("password_hash", "")):
            return {"id": user["id"], "email": user["email"]}
    return None


def list_users(users: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"id": user["id"], "email": user["email"]} for user in users]
