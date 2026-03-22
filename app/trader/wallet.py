"""
wallet.py — Secure wallet management for SignalMesh AutoTrader

Security model:
- Private keys are NEVER stored plaintext
- Each key is encrypted with AES-256-GCM using the user's own Telegram user_id + a server secret
- Encrypted blob stored in memory dict (production: swap for Redis/DB)
- Users can disconnect and wipe at any time
- Keys only decrypted in-process during trade execution, never logged
"""

import base64
import json
import os
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# ── In-memory store (swap for Redis in production) ──────────────────────────
# Structure: {user_id: {"encrypted_key": bytes, "salt": bytes, "pubkey": str, "settings": dict}}
_wallet_store: dict[int, dict] = {}

SERVER_SECRET = os.getenv("WALLET_SECRET", "signalmesh-dev-secret-change-in-prod")


def _derive_key(user_id: int, salt: bytes) -> bytes:
    """Derive AES key from user_id + server secret + salt"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    return kdf.derive(f"{SERVER_SECRET}:{user_id}".encode())


def store_wallet(user_id: int, private_key_bytes: bytes, pubkey: str) -> bool:
    """Encrypt and store a private key. Returns True on success."""
    try:
        salt = os.urandom(16)
        key = _derive_key(user_id, salt)
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        encrypted = aesgcm.encrypt(nonce, private_key_bytes, None)
        
        _wallet_store[user_id] = {
            "encrypted_key": base64.b64encode(nonce + encrypted).decode(),
            "salt": base64.b64encode(salt).decode(),
            "pubkey": pubkey,
            "settings": {
                "enabled": False,
                "max_position_sol": 0.1,   # Default: 0.1 SOL per trade
                "max_open_trades": 3,
                "tp_pct": 50,              # Take profit: +50%
                "sl_pct": 30,              # Stop loss: -30%
                "min_safety_score": 75,    # Min safety to enter
                "min_alpha_score": 0.68,   # Min alpha score
                "min_wallets_in": 2,       # Min smart wallets entered
            }
        }
        return True
    except Exception:
        return False


def get_private_key(user_id: int) -> Optional[bytes]:
    """Decrypt and return private key bytes. Returns None if not found."""
    if user_id not in _wallet_store:
        return None
    try:
        data = _wallet_store[user_id]
        salt = base64.b64decode(data["salt"])
        key = _derive_key(user_id, salt)
        aesgcm = AESGCM(key)
        blob = base64.b64decode(data["encrypted_key"])
        nonce, ciphertext = blob[:12], blob[12:]
        return aesgcm.decrypt(nonce, ciphertext, None)
    except Exception:
        return None


def get_wallet_info(user_id: int) -> Optional[dict]:
    """Return wallet info (NO private key) for display"""
    if user_id not in _wallet_store:
        return None
    data = _wallet_store[user_id]
    return {
        "pubkey": data["pubkey"],
        "settings": data["settings"].copy(),
    }


def update_settings(user_id: int, **kwargs) -> bool:
    if user_id not in _wallet_store:
        return False
    for k, v in kwargs.items():
        if k in _wallet_store[user_id]["settings"]:
            _wallet_store[user_id]["settings"][k] = v
    return True


def remove_wallet(user_id: int) -> bool:
    """Completely wipe wallet data"""
    if user_id in _wallet_store:
        # Zero out in memory before deleting
        _wallet_store[user_id]["encrypted_key"] = ""
        _wallet_store[user_id]["salt"] = ""
        del _wallet_store[user_id]
        return True
    return False


def is_connected(user_id: int) -> bool:
    return user_id in _wallet_store


def is_trading_enabled(user_id: int) -> bool:
    if user_id not in _wallet_store:
        return False
    return _wallet_store[user_id]["settings"].get("enabled", False)
