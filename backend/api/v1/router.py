from fastapi import APIRouter
from .endpoints import auth, projects, uploads, model2d, model3d, spda, reports, exports

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
api_router.include_router(model2d.router, prefix="/model2d", tags=["model2d"])
api_router.include_router(model3d.router, prefix="/model3d", tags=["model3d"])
api_router.include_router(spda.router, prefix="/spda", tags=["spda"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(exports.router, prefix="/exports", tags=["exports"])
