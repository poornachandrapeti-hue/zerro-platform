"""Short-lived HMAC signed cross-service authentication tickets. Never place tickets in URLs."""
import base64
import hashlib
import hmac
import json
import time


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue_ticket(secret: str, claims: dict, lifetime: int = 45) -> str:
    if len(secret) < 32:
        raise ValueError("SSO secret must be at least 32 characters")
    data = dict(claims, exp=int(time.time()) + lifetime, aud="zerro-command-center")
    body = _b64(json.dumps(data, separators=(",", ":"), sort_keys=True).encode())
    signature = _b64(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
    return body + "." + signature


def verify_ticket(secret: str, token: str) -> dict:
    if len(secret) < 32 or len(token) > 8192 or token.count(".") != 1:
        raise ValueError("Invalid ticket")
    body, signature = token.split(".")
    expected = _b64(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(expected, signature):
        raise ValueError("Invalid signature")
    data = json.loads(_unb64(body))
    if data.get("aud") != "zerro-command-center" or not isinstance(data.get("exp"), int) or not int(time.time()) < data["exp"] <= int(time.time()) + 3600:
        raise ValueError("Expired or invalid ticket")
    return data
