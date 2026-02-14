import base64
import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
from uuid import UUID
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.settings import settings

security = HTTPBearer()

@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: str
    role: str
    is_active: bool

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")

def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))

def _sign(message: bytes) -> str:
    sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), message, hashlib.sha256).digest()
    return _b64url_encode(sig)

def _encode(payload: Dict[str, Any]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h}.{p}".encode("utf-8")
    s = _sign(signing_input)
    return f"{h}.{p}.{s}"

def decode_token(token: str) -> Dict[str, Any]:
    try:
        h, p, s = token.split(".")
    except ValueError as exc:
        _log_auth_failure(
            failure_reason="malformed_token",
            extra={}
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    signing_input = f"{h}.{p}".encode("utf-8")
    expected = _sign(signing_input)
    if not hmac.compare_digest(expected, s):
        # Try to extract user_id if possible
        user_id = None
        try:
            payload = json.loads(_b64url_decode(p).decode("utf-8"))
            user_id = payload.get("sub")
        except Exception:
            pass
        _log_auth_failure(
            failure_reason="invalid_signature",
            extra={"user_id": user_id}
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        payload = json.loads(_b64url_decode(p).decode("utf-8"))
    except Exception as exc:
        _log_auth_failure(
            failure_reason="malformed_token",
            extra={}
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    exp = payload.get("exp")
    if exp is not None and datetime.now(timezone.utc).timestamp() > float(exp):
        _log_auth_failure(
            failure_reason="expired_token",
            extra={"user_id": payload.get("sub")}
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    return payload


def _log_auth_failure(failure_reason: str, extra: dict):
    import inspect
    from fastapi import Request
    import sys
    # Try to get request context if available
    request = None
    for frame_info in inspect.stack():
        frame = frame_info.frame
        if "request" in frame.f_locals and isinstance(frame.f_locals["request"], Request):
            request = frame.f_locals["request"]
            break
    request_path = request.url.path if request else None
    http_method = request.method if request else None
    client_ip = request.client.host if request and request.client else None
    user_id = extra.get("user_id") if extra else None
    log_data = {
        "failure_reason": failure_reason,
        "request_path": request_path,
        "http_method": http_method,
        "client_ip": client_ip,
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logging.warning(f"AUTH FAILURE: {log_data}")

def create_access_token(
    user: Optional[Any] = None,
    *,
    user_id: Optional[Union[str, UUID]] = None,
    email: Optional[str] = None,
    role: Optional[str] = None,
    is_active: bool = True,
) -> str:
    if user is not None:
        user_id = getattr(user, "id")
        email = getattr(user, "email")
        role = getattr(user, "role")
        is_active = bool(getattr(user, "is_active", True))

    if user_id is None or email is None or role is None:
        raise ValueError("missing_user_fields")

    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "is_active": is_active,
        "type": "access",
        "exp": exp.timestamp(),
    }
    return _encode(payload)

def create_refresh_token(user: Any) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=30)
    payload = {
        "sub": str(getattr(user, "id")),
        "email": getattr(user, "email"),
        "role": getattr(user, "role"),
        "type": "refresh",
        "exp": exp.timestamp(),
    }
    return _encode(payload)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    request: Request = None,
) -> CurrentUser:
    token = credentials.credentials
    try:
        data = decode_token(token)
    except HTTPException as exc:
        # Already logged in decode_token
        raise
    if data.get("type") != "access":
        _log_auth_failure(
            failure_reason="invalid_token",
            extra={
                "request_path": request.url.path if request else None,
                "http_method": request.method if request else None,
                "client_ip": request.client.host if request and request.client else None,
                "user_id": data.get("sub") if data else None,
            },
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        user_id = UUID(str(data.get("sub")))
    except Exception as exc:
        _log_auth_failure(
            failure_reason="malformed_token",
            extra={
                "request_path": request.url.path if request else None,
                "http_method": request.method if request else None,
                "client_ip": request.client.host if request and request.client else None,
                "user_id": data.get("sub") if data else None,
            },
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    return CurrentUser(
        id=user_id,
        email=str(data.get("email")),
        role=str(data.get("role")),
        is_active=bool(data.get("is_active", True)),
    )
