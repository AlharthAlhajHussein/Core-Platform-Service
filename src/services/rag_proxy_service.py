import httpx
from fastapi import HTTPException, status, UploadFile
from uuid import UUID

from helpers.config import settings

class RAGProxyService:
    """
    A secure proxy service to communicate with the RAG-Engine-Service.
    This ensures the RAG service is never exposed directly to the public internet
    and all requests are authenticated and authorized through the Core Platform.
    """
    def __init__(self):
        self.base_url = settings.rag_service_url.rstrip('/')
        self.headers = {"X-Internal-Secret": settings.internal_secret}

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """A helper to make authenticated async requests to the RAG service."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method,
                    f"{self.base_url}{endpoint}",
                    headers=self.headers,
                    timeout=30.0, # Set a reasonable timeout
                    **kwargs
                )
                response.raise_for_status() # Raises HTTPStatusError for 4xx/5xx responses
                return response
            except httpx.HTTPStatusError as e:
                # Forward the RAG service's error status and detail if possible
                detail = e.response.json().get("detail", "An error occurred in the RAG service.")
                raise HTTPException(status_code=e.response.status_code, detail=detail)
            except httpx.RequestError:
                # Handle network errors (e.g., connection refused)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="The RAG service is currently unavailable."
                )

    async def create_knowledge_bucket(self, name: str, company_id: UUID) -> dict:
        """
        Sends a request to the RAG service to create a new knowledge container.
        """
        payload = {"name": name, "metadata": {"company_id": str(company_id)}}
        response = await self._make_request("POST", "/v1/containers", json=payload)
        return response.json()

# Instantiate the service to be used as a singleton
rag_proxy_service = RAGProxyService()