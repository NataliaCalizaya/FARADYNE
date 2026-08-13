from fastapi import APIRouter, UploadFile, File, BackgroundTasks

router = APIRouter()

@router.post("/dxf")
async def upload_dxf(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    pass
