from datetime import timedelta
from google.cloud import storage
from helpers.config import settings
import logging

logger = logging.getLogger("uvicorn.error")

def generate_signed_url(media_url: str | None, expiration_minutes: int = 60) -> str | None:
    if not media_url:
        return None
        
    try:
        bucket_name = settings.gcs_bucket1
        blob_name = media_url
        
        # Parse gs:// URI
        if media_url.startswith("gs://"):
            parts = media_url[5:].split("/", 1)
            if len(parts) == 2:
                bucket_name = parts[0]
                blob_name = parts[1]
        # Parse standard GCS HTTPS URL
        elif media_url.startswith("https://storage.googleapis.com/"):
            parts = media_url[31:].split("/", 1)
            if len(parts) == 2:
                bucket_name = parts[0]
                blob_name = parts[1]
        # If it's a completely external URL (e.g. standard https:// that isn't GCS), return as is
        elif media_url.startswith("http"):
            return media_url
            
        client = storage.Client(project=settings.gcs_project)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET",
            service_account_email=settings.signer_email
        )
    except Exception as e:
        logger.error(f"Failed to generate signed URL for {media_url}: {e}")
        return media_url # Fallback to original so we don't break the UI entirely