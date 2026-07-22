"""Local-first security, made enforceable — not a promise, a guard.

A CEO's inputs here are the company's weaknesses, hidden risks, executive
conduct issues — more sensitive than most data the company holds. The 2026
landscape makes the threat concrete: 97% of surveyed organizations had at least
one GenAI-related security breach in the past year (Capgemini), and Samsung
employees leaking confidential code into a public AI tool led to an internal AI
ban. The market answer ("encrypt sensitive data before feeding it into AI
tools") is our architecture:

  1. offline_guard() — a context manager that BLOCKS all outbound network at the
     socket layer. The deterministic core runs fully inside it (proven by tests);
     any accidental network call raises instead of leaking.
  2. At-rest encryption for portfolios (state data) — scrypt KDF + Fernet
     (AES128-CBC + HMAC), passphrase never stored.
  3. LLM calls are the ONLY sanctioned outbound path, behind explicit flags, and
     they raise loudly inside offline mode.
"""
from __future__ import annotations

import base64
import contextlib
import json
import socket
from pathlib import Path


class NetworkBlockedError(RuntimeError):
    """Raised when code attempts outbound network inside offline mode."""


@contextlib.contextmanager
def offline_guard():
    """Block ALL network access (socket creation + name resolution) in this context.

    The deterministic core never needs the network; running under this guard turns
    that claim into an enforced invariant. Loopback is NOT exempted on purpose —
    offline means offline.
    """
    real_socket = socket.socket
    real_create = socket.create_connection
    real_getaddr = socket.getaddrinfo

    def _blocked(*_a, **_k):
        raise NetworkBlockedError(
            "오프라인 모드: 네트워크 접근이 차단됨 — 민감 데이터는 이 기계를 떠나지 않는다"
        )

    socket.socket = _blocked          # type: ignore[misc]
    socket.create_connection = _blocked  # type: ignore[assignment]
    socket.getaddrinfo = _blocked     # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket = real_socket   # type: ignore[misc]
        socket.create_connection = real_create  # type: ignore[assignment]
        socket.getaddrinfo = real_getaddr  # type: ignore[assignment]


# --------------------------------------------------------------------------- #
# At-rest encryption (scrypt KDF + Fernet). `cryptography` is an optional
# dependency — imported lazily so the core stays dependency-free without it.
# --------------------------------------------------------------------------- #

MAGIC = "SELFDEPLOY-ENC-1"


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def encrypt_json(data: dict, passphrase: str) -> str:
    """Serialize + encrypt a JSON-able object; returns an armored JSON envelope."""
    import os

    from cryptography.fernet import Fernet

    salt = os.urandom(16)
    token = Fernet(_derive_key(passphrase, salt)).encrypt(
        json.dumps(data, ensure_ascii=False).encode("utf-8")
    )
    return json.dumps({
        "magic": MAGIC,
        "salt": base64.b64encode(salt).decode("ascii"),
        "token": token.decode("ascii"),
    })


def decrypt_json(envelope: str, passphrase: str) -> dict:
    from cryptography.fernet import Fernet

    env = json.loads(envelope)
    if env.get("magic") != MAGIC:
        raise ValueError("암호화 파일이 아님 (magic mismatch)")
    salt = base64.b64decode(env["salt"])
    plain = Fernet(_derive_key(passphrase, salt)).decrypt(env["token"].encode("ascii"))
    return json.loads(plain.decode("utf-8"))


def is_encrypted_file(path: str | Path) -> bool:
    try:
        head = Path(path).read_text(encoding="utf-8")[:256]
        return MAGIC in head
    except (OSError, UnicodeDecodeError):
        return False
