from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, get_current_user, hash_password, verify_password
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.auth_schema import LoginRequest, RegistroRequest, TokenResponse, UsuarioResponse, UsuarioUpdateRequest

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/registro", response_model=UsuarioResponse, status_code=201)
def registrar_usuario(payload: RegistroRequest, db: Session = Depends(get_db)):
    if UsuarioRepository.get_by_email(db, payload.email):
        raise HTTPException(status_code=409, detail="Ya existe un usuario con ese email.")
    return UsuarioRepository.create_usuario(
        db,
        nombre=payload.nombre,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Login con JSON {email, password}. Lo usa el frontend."""
    return _autenticar(db, payload.email, payload.password)


@router.post("/token", response_model=TokenResponse, include_in_schema=False)
def login_form(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Mismo login pero con form-data: lo usa el botón 'Authorize' de Swagger (/docs)."""
    return _autenticar(db, form.username, form.password)


@router.get("/me", response_model=UsuarioResponse)
def usuario_actual(usuario: Dict[str, Any] = Depends(get_current_user)):
    return usuario


@router.patch("/me", response_model=UsuarioResponse)
def actualizar_usuario_actual(
    payload: UsuarioUpdateRequest,
    db: Session = Depends(get_db),
    usuario: Dict[str, Any] = Depends(get_current_user),
):
    # Cambio de contraseña requiere la actual.
    if payload.password_nueva is not None:
        if not payload.password_actual or not verify_password(payload.password_actual, usuario["password_hash"]):
            raise HTTPException(status_code=400, detail="Contraseña actual incorrecta.")
        new_hash = hash_password(payload.password_nueva)
    else:
        new_hash = None

    # Email único.
    if payload.email is not None and payload.email.lower() != usuario["email"].lower():
        existente = UsuarioRepository.get_by_email(db, payload.email)
        if existente and existente["id_usuario"] != usuario["id_usuario"]:
            raise HTTPException(status_code=409, detail="Ya existe un usuario con ese email.")

    updated = UsuarioRepository.update_usuario(
        db,
        id_usuario=usuario["id_usuario"],
        nombre=payload.nombre,
        email=payload.email,
        password_hash=new_hash,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return updated


def _autenticar(db: Session, email: str, password: str) -> Dict[str, Any]:
    usuario = UsuarioRepository.get_by_email(db, email)
    if not usuario or not usuario["activo"] or not verify_password(password, usuario["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos.",
        )
    return {
        "access_token": create_access_token(usuario["id_usuario"]),
        "token_type": "bearer",
        "usuario": usuario,
    }