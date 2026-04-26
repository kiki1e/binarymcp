from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.auth import create_token
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    if body.username != settings.admin_username or body.password != settings.admin_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_token(body.username)
    return LoginResponse(token=token, username=body.username)
