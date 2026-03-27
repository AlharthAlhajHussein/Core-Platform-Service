from cryptography.fernet import Fernet, InvalidToken
from helpers import settings

fernet = Fernet(settings.fernet_key)

def encrypt_data(data: str | None) -> str | None:
    """Encrypts a string using Fernet."""
    if data is None:
        return None
    return fernet.encrypt(data.encode('utf-8')).decode('utf-8')

def decrypt_data(encrypted_data: str | None) -> str | None:
    """Decrypts a Fernet-encrypted string."""
    if encrypted_data is None:
        return None
    try:
        return fernet.decrypt(encrypted_data.encode('utf-8')).decode('utf-8')
    except InvalidToken:
        # Handle cases where the token is malformed or invalid
        # This is a critical edge case for data integrity
        return None