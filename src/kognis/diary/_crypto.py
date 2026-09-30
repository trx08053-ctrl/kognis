"""Защита записей «под замком» (D4): AES-GCM ключом данных сервера + пароль замка (argon2id)."""

import base64
import binascii
import os
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from kognis.errors import CodedError, CodedValueError

FORMAT_VERSION = 1
MIN_LOCK_PASSWORD = 8
MAX_LOCK_PASSWORD = 256
KEY_LENGTH = 32
NONCE_LENGTH = 12

_hasher = PasswordHasher()  # argon2id по умолчанию


class DataKeyError(CodedError):
    """Ключ данных сервера (KOGNIS_DATA_KEY) не задан или некорректен."""


class WrongLockPasswordError(CodedError):
    """Неверный пароль замка."""


class EntryUnreadableError(CodedError):
    """Запись не расшифровывается: ключ данных сервера сменился или данные повреждены."""


@dataclass(frozen=True)
class Sealed:
    cipher: bytes
    nonce: bytes
    lock_hash: str
    version: int = FORMAT_VERSION


def parse_data_key(raw: str | bytes | None) -> bytes:
    """KOGNIS_DATA_KEY — base64 от 32 байт."""
    if not raw:
        raise DataKeyError("data_key.missing")
    try:
        key = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as err:
        raise DataKeyError("data_key.invalid") from err
    if len(key) != KEY_LENGTH:
        raise DataKeyError("data_key.invalid")
    return key


def validate_lock_password(password: str) -> str:
    if not MIN_LOCK_PASSWORD <= len(password) <= MAX_LOCK_PASSWORD:
        raise CodedValueError("lock.password_short", min=MIN_LOCK_PASSWORD)
    return password


def _aad(owner_id: int) -> bytes:
    return f"kognis-entry:v{FORMAT_VERSION}:{owner_id}".encode()


def seal(key: bytes, owner_id: int, text: str, password: str) -> Sealed:
    nonce = os.urandom(NONCE_LENGTH)
    cipher = AESGCM(key).encrypt(nonce, text.encode(), _aad(owner_id))
    return Sealed(cipher, nonce, _hasher.hash(validate_lock_password(password)))


def open_sealed(key: bytes, owner_id: int, sealed: Sealed, password: str) -> str:
    """Сначала пароль замка, затем расшифровка; текст не попадает в сообщения об ошибках."""
    try:
        _hasher.verify(sealed.lock_hash, password)
    except (VerificationError, InvalidHashError) as err:
        raise WrongLockPasswordError("lock.password_wrong") from err
    try:
        return AESGCM(key).decrypt(sealed.nonce, sealed.cipher, _aad(owner_id)).decode()
    except (InvalidTag, UnicodeDecodeError) as err:
        raise EntryUnreadableError("entry.unreadable") from err
