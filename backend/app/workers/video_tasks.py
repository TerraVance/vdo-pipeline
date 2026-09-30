import asyncio
import httpx
from app.core.celery_app import celery_app
from app.core.database import get_supabase
from app.services.video_service import get_video_provider
from app.models.schemas import PipelineStatus


@celery_app.task(bind=True, max_retries=1, default_retry_delay=30)
def synthesize_video_task(self, project_id: str, model: str, image_url: str, prompt: str):
    """
    Celery task — Stage 7.6:
    1. Call video provider API (may take 30-120s)
    2. Download the MP4
    3. Upload to Supabase Storage
    4. Update project row with final_video_url and VIDEO_READY status
    """
    db = get_supabase()
    try:
        # Update status to GENERATING_VIDEO
        db.table("projects").update(
            {"status": PipelineStatus.GENERATING_VIDEO.value, "task_id": self.request.id}
        ).eq("id", project_id).execute()

        # Run async video generation
        provider = get_video_provider(model)
        video_url = asyncio.run(
            provider.generate(image_url=image_url, prompt=prompt)
        )

        # Download MP4 from provider URL
        video_bytes = _download_video(video_url)

        # Upload to Supabase Storage
        storage_path = f"projects/{project_id}/video/final.mp4"
        db.storage.from_("media").upload(
            storage_path, video_bytes, {"content-type": "video/mp4", "upsert": "true"}
        )
        public_url = db.storage.from_("media").get_public_url(storage_path)

        # Update project with final video URL
        db.table("projects").update(
            {
                "final_video_url": public_url,
                "status": PipelineStatus.VIDEO_READY.value,
            }
        ).eq("id", project_id).execute()

    except Exception as exc:
        import traceback
        with open("celery_error.log", "a") as f:
            f.write(f"Task Failed: {self.request.id}\n")
            traceback.print_exc(file=f)
            
        if self.request.retries >= self.max_retries:
            db.table("projects").update(
                {"status": PipelineStatus.FAILED.value}
            ).eq("id", project_id).execute()
        raise self.retry(exc=exc)


def _download_video(url: str) -> bytes:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = httpx.get(url, headers=headers, timeout=120, follow_redirects=True)
    response.raise_for_status()
    return response.content
