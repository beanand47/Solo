import os
import secrets
import hmac
import hashlib

from itsdangerous import URLSafeTimedSerializer


SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production")
csrf_serializer = URLSafeTimedSerializer(SECRET_KEY)


def generate_csrf_token() -> str:
    return csrf_serializer.dumps(secrets.token_hex(16), salt="csrf")


def validate_csrf_token(token: str) -> bool:
    try:
        csrf_serializer.loads(token, salt="csrf", max_age=3600)
        return True
    except Exception:
        return False
