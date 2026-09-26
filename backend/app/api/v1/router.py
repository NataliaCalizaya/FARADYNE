from fastapi import APIRouter
from app.api.v1.endpoints import mastiles, modelos3d, niveles_proteccion, planos, proyecto

api_router = APIRouter()

api_router.include_router(proyecto.router)
api_router.include_router(planos.router)
api_router.include_router(planos.modelos2d_router)
api_router.include_router(modelos3d.router)
api_router.include_router(niveles_proteccion.router)
api_router.include_router(mastiles.router)
