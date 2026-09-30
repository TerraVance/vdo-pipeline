import asyncio
import base64
import httpx
from app.core.celery_app import celery_app
from app.core.database import get_supabase
from app.services.image_service import get_image_provider
from app.models.schemas import PipelineStatus


@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def generate_images_task(self, project_id: str, model: str, prompt: str):
    """
    Celery task — Stage 6.6:
    1. Call image provider API
    2. Upload each image to Supabase Storage
    3. Update project row with image URLs and IMAGES_READY status
    """
    db = get_supabase()
    try:
        # Update status to GENERATING_IMAGES
        db.table("projects").update(
            {"status": PipelineStatus.GENERATING_IMAGES.value, "task_id": self.request.id}
        ).eq("id", project_id).execute()

        # Run async image generation
        provider = get_image_provider(model)
        raw_urls = asyncio.run(
            provider.generate(prompt=prompt, count=4)
        )

        # Upload to Supabase Storage and get public URLs
        public_urls = []
        for i, url_or_data in enumerate(raw_urls):
            storage_path = f"projects/{project_id}/images/image_{i}.png"
            image_bytes = _fetch_or_decode_image(url_or_data)
            db.storage.from_("media").upload(
                storage_path, image_bytes, {"content-type": "image/png", "upsert": "true"}
            )
            public_url = db.storage.from_("media").get_public_url(storage_path)
            public_urls.append(public_url)

        # Update project with results
        db.table("projects").update(
            {
                "image_urls": public_urls,
                "status": PipelineStatus.IMAGES_READY.value,
            }
        ).eq("id", project_id).execute()

    except Exception as exc:
        if self.request.retries >= self.max_retries:
            db.table("projects").update(
                {"status": PipelineStatus.FAILED.value}
            ).eq("id", project_id).execute()
        raise self.retry(exc=exc)


def _fetch_or_decode_image(url_or_data: str) -> bytes:
    """Handle both public URLs and base64 data URLs returned by providers."""
    if url_or_data.startswith("data:image"):
        # base64 encoded image from Gemini
        header, encoded = url_or_data.split(",", 1)
        return base64.b64decode(encoded)
    else:
        # Fetch from public URL
        response = httpx.get(url_or_data, timeout=30)
        response.raise_for_status()
        return response.content
