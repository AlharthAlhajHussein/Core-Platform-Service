from fastapi import FastAPI
from routers import base

app = FastAPI(
    title="Core Platform API",
    description="A Core Platform API built with FastAPI.",
    version="1.0.0",
    # openapi_url="/openapi.json",
    # docs_url="/docs",
    # redoc_url="/redoc",
    # contact={"name": "Alharth Alhaj Hussein", "email": "alharth.alhaj.hussein@gmail.com"}
)

app.include_router(base.router)

