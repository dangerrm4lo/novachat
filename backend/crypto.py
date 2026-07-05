# crypto.py - функции шифрования и хеширования
import hashlib
import secrets
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

def hash_password(password: str, salt: bytes = None) -> tuple:
    """Хеширование пароля с солью"""
    if salt is None:
        salt = os.urandom(32)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.b64encode(kdf.derive(password.encode()))
    return key.decode(), base64.b64encode(salt).decode()

def verify_password(password: str, hashed: str, salt: str) -> bool:
    """Проверка пароля"""
    salt_bytes = base64.b64decode(salt)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt_bytes,
        iterations=100000,
    )
    try:
        kdf.derive(password.encode())
        return True
    except:
        return False

def generate_key() -> str:
    """Генерация ключа для симметричного шифрования"""
    return base64.b64encode(os.urandom(32)).decode()

def encrypt_message(content: str, key: str) -> str:
    """Шифрование сообщения"""
    fernet = Fernet(key.encode())
    return fernet.encrypt(content.encode()).decode()

def decrypt_message(encrypted: str, key: str) -> str:
    """Расшифровка сообщения"""
    fernet = Fernet(key.encode())
    return fernet.decrypt(encrypted.encode()).decode()

def generate_session_token() -> str:
    """Генерация токена сессии"""
    return secrets.token_urlsafe(32)