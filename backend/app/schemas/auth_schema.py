from datetime import datetime

from pydantic import BaseModel, Field


class RegistroRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    email: str = Field(min_length=3, max_length=150, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str
    password: str


class UsuarioResponse(BaseModel):
    id_usuario: int
    nombre: str
    email: str
    fecha_creacion: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioResponse