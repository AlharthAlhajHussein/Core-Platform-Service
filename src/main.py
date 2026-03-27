from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from helpers.config import settings
from routers import internal_api, auth_router

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="The central source of truth and administrative backbone for the Agents Platform.",
    contact={
        "name": "API Support",
        "url": "https://example.com/support",
        "email": "support@example.com",
    },
)

# Add CORS middleware to allow cross-origin requests from your frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend's domain e.g. ["https://dashboard.your-app.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all the routers
app.include_router(internal_api.router)
app.include_router(auth_router.router)

@app.get("/", tags=["Health Check"])
async def health_check():
    """A simple health check endpoint to confirm the service is running."""
    return {"status": "ok", "message": f"{settings.app_name} v{settings.app_version} is running!"}