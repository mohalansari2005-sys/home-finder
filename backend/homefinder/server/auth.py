import time
from collections import defaultdict, deque

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from homefinder.config import get_settings
from homefinder.server.deps import require_family

router = APIRouter()
WINDOW, MAX_ATTEMPTS = 60.0, 5
_attempts: dict[str, deque] = defaultdict(deque)


def reset_rate_limit() -> None:
    _attempts.clear()


def _ip(request: Request) -> str:
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "?")


class LoginBody(BaseModel):
    password: str


@router.post("/login", status_code=204)
def login(body: LoginBody, request: Request):
    q = _attempts[_ip(request)]
    now = time.monotonic()
    while q and now - q[0] > WINDOW:
        q.popleft()
    if len(q) >= MAX_ATTEMPTS:
        raise HTTPException(429, "too many attempts")
    h = get_settings().family_password_hash.encode()
    if not h or not bcrypt.checkpw(body.password.encode(), h):
        q.append(now)
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
