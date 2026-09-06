from datetime import datetime, timedelta, timezone
from functools import lru_cache

import bcrypt
from jose import JWSError, jwt

from src.utils.config_loader import get_jwt_settings


class AuthService:
    def __init__(self):
        cfg = get_jwt_settings()
        self._secret = cfg["secret_key"]
        self._algorithm = cfg["algorithm"]
        self._expire_minutes = cfg["access_token_expire_minutes"]

    def hash_password(self, plain: str) -> str:
        return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify_password(self, plain: str, hashed: str) -> bool:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

    def create_access_token(self, user_id: str, email: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=self._expire_minutes)
        payload = {
            "sub": user_id,       # subject — user_id
            "email": email,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_token(self, token: str) -> dict:
        """Raises JWTError if invalid or expired."""
        return jwt.decode(token, self._secret, algorithms=[self._algorithm])


@lru_cache(maxsize=1)
def get_auth_service() -> AuthService:
    return AuthService()