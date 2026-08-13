from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.post("/login")
async def login():
    raise HTTPException(status_code=501, detail="Auth not enabled yet")

@router.post("/register")
async def register():
    raise HTTPException(status_code=501, detail="Auth not enabled yet")
