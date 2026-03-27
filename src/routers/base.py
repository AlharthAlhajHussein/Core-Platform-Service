from fastapi import APIRouter
from fastapi.responses import JSONResponse
from helpers import settings

router = APIRouter(
    prefix="/api/v1",
    tags=["base"],
)

@router.get("/")
async def root():
    return JSONResponse(content={"APP NAME": settings.app_name, 
                                 "VERSION": settings.app_version, 
                                 "MESSAGE": "Hi, Welcome to the Core Platform API!"})