from fastapi import Header, HTTPException

from .config import settings


def require_admin(x_admin_token: str = Header(default="")):
    if x_admin_token != settings.admin_token:
        raise HTTPException(401, "bad admin token")
