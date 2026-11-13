import time
from collections import defaultdict, deque

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from homefinder.config import get_settings
from homefinder.server.deps import require_family

router = APIRouter()
WINDOW, MAX_ATTEMPTS, GLOBAL_MAX = 60.0, 5, 30
BCRYPT_MAX_BYTES = 72
_attempts: dict[str, deque] = defaultdict(deque)
_global_failures: deque = deque()  # failures from any IP: behind docker-proxy all IPv6 clients share one address


def reset_rate_limit() -> None:
    _attempts.clear()
    _global_failures.clear()


def _ip(request: Request) -> str:
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "?")


class LoginBody(BaseModel):
    password: str = Field(max_length=256)


@router.post("/login", status_code=204)
def login(body: LoginBody, request: Request):
    ip, now = _ip(request), time.monotonic()
    for k, v in list(_attempts.items()):  # expire old failures and forget idle IPs (no entry per IP forever)
        while v and now - v[0] > WINDOW:
            v.popleft()
        if not v:
            del _attempts[k]
    while _global_failures and now - _global_failures[0] > WINDOW:
        _global_failures.popleft()
    q = _attempts[ip]
    if len(q) >= MAX_ATTEMPTS or len(_global_failures) >= GLOBAL_MAX:
        raise HTTPException(429, "too many attempts")
    h = get_settings().family_password_hash.encode()
    pw = body.password.encode()
    # bcrypt 5 raises ValueError above 72 bytes: such a password can never match, so count it as a failure
    if not h or len(pw) > BCRYPT_MAX_BYTES or not bcrypt.checkpw(pw, h):
        q.append(now)
        _global_failures.append(now)
        raise HTTPException(401, "wrong password")
    request.session["family"] = True
    return Response(status_code=204)


@router.post("/logout", status_code=204)
def logout(request: Request):
    request.session.clear()
    return Response(status_code=204)


@router.get("/me", dependencies=[Depends(require_family)])
def me():
    return {"ok": True}
