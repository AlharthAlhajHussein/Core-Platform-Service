from cryptography.fernet import Fernet
from helpers.config import settings

if not settings.fernet_key:
    raise ValueError("FERNET_KEY must be set in the environment variables (e.g. .env).")

# Initialize Fernet directly with the dedicated key from settings
_fernet = Fernet(settings.fernet_key)

def encrypt(data: str) -> str:
    """Encrypts a string using Fernet (symmetric encryption)."""
    if not data:
        return data
    return _fernet.encrypt(data.encode()).decode()

def decrypt(data: str) -> str:
    """Decrypts a Fernet-encrypted string."""
    if not data:
        return data
    return _fernet.decrypt(data.encode()).decode()