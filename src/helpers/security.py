from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import JWTError, jwt
from helpers.config import settings
from helpers.redis_client import is_blocklisted

# 1. Password Hashing Setup
# By using "sha256_crypt" as the default, passlib will first hash the password
# with SHA-256 and then pass that fixed-length hash to bcrypt. This elegantly
# solves the 72-byte limit of bcrypt while maintaining its slowness factor,
# which is crucial for security. "bcrypt" is kept for verifying old passwords
# if you ever needed to migrate.
pwd_context = CryptContext(schemes=["sha256_crypt", "bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed one."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashes a plain password."""
    return pwd_context.hash(password)


# 2. JWT Creation
def create_access_token(data: dict, expires_delta: timedelta | None = None, token_type: str = "access") -> str:
    """Creates a new JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire, "token_type": token_type})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """Creates a new JWT refresh token."""
    expires = timedelta(days=settings.refresh_token_expire_days)
    return create_access_token(data=data, expires_delta=expires, token_type="refresh")