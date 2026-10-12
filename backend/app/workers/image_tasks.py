import asyncio
import base64
import time
import httpx
from celery.exceptions import MaxRetriesExceededError
from app.core.celery_app import celery_app
from app.core.database import get_supabase
from app.services.image_service import get_image_provider
from app.models.schemas import PipelineStatus
from app.core.logging import logger


# ── Retryable vs fatal error classification ───────────────────────────────────
# Retryable: transient failures (network, rate-limit, empty output, timeout)
# Fatal: programming errors or permanent auth failures — no point retrying
_RETRYABLE_ERRORS = (RuntimeError, TimeoutError, httpx.TimeoutException, asyncio.TimeoutError)
_FATAL_ERRORS = (ValueError, PermissionError)


def _is_retryable(exc: Exception) -> bool:
    """Returns True if the exception is worth retrying."""
    if isinstance(exc, _FATAL_ERRORS):
        return False
    return True


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,   # base delay; grows exponentially via retry_backoff
    retry_backoff=True,       # 30s → 60s → 120s
    retry_backoff_max=120,    # cap at 120s
    retry_jitter=True,        # add ±10% random jitter to avoid thundering herd
)
def generate_images_task(self, project_id: str, model: str, prompt: str, aspect_ratio: str = "16:9"):
    """
    Celery task — Project image generation:
    1. Call image provider API (Gemini or Freepik)
    2. Upload each image to Supabase Storage
    3. Update project row with image URLs and IMAGES_READY status

    Retry policy:
    - Up to 3 retries with exponential backoff (30s → 60s → 120s) + jitter
    - Only retries on transient errors (RuntimeError, TimeoutError, httpx timeouts)
    - Fatal errors (ValueError, PermissionError) mark the project FAILED immediately
    """
    task_id = self.request.id
    logger.info(
        f"[Task {task_id}] generate_images_task started — "
        f"project={project_id}, model={model}, ratio={aspect_ratio}, "
        f"attempt={self.request.retries + 1}/{self.max_retries + 1}"
    )
    db = get_supabase()

    try:
        # Update status to GENERATING_IMAGES
        db.table("projects").update(
            {"status": PipelineStatus.GENERATING_IMAGES.value, "task_id": task_id}
        ).eq("id", project_id).execute()

        # Run async image generation in a synchronous Celery context
        provider = get_image_provider(model)
        raw_urls = asyncio.run(
            provider.generate(prompt=prompt, count=4, aspect_ratio=aspect_ratio)
        )

        if not raw_urls:
            raise RuntimeError(f"Provider '{model}' returned zero images for project={project_id}")

        # Upload to Supabase Storage and collect public URLs
        timestamp = int(time.time())
        public_urls: list[str] = []

        for i, url_or_data in enumerate(raw_urls):
            storage_path = f"projects/{project_id}/images/image_{i}.png"
            image_bytes = _fetch_or_decode_image(url_or_data)
            db.storage.from_("media").upload(
                storage_path,
                image_bytes,
                {"content-type": "image/png", "upsert": "true"},
            )
            public_url = db.storage.from_("media").get_public_url(storage_path)
            public_urls.append(f"{public_url}?t={timestamp}")

        # Persist results
        db.table("projects").update(
            {
                "image_urls": public_urls,
                "status": PipelineStatus.IMAGES_READY.value,
            }
        ).eq("id", project_id).execute()

        logger.info(
            f"[Task {task_id}] generate_images_task COMPLETED — "
            f"project={project_id}, {len(public_urls)} image(s) uploaded"
        )

    except _FATAL_ERRORS as exc:
        # Non-retryable: mark failed immediately without retrying
        logger.error(
            f"[Task {task_id}] Fatal error in generate_images_task for project={project_id}: {exc}"
        )
        db.table("projects").update(
            {"status": PipelineStatus.FAILED.value}
        ).eq("id", project_id).execute()
        raise  # do NOT call self.retry — let Celery mark task as FAILURE

    except Exception as exc:
        logger.exception(
            f"[Task {task_id}] Error in generate_images_task for project={project_id} "
            f"(attempt {self.request.retries + 1}/{self.max_retries + 1}): {exc}"
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error(
                f"[Task {task_id}] Max retries exceeded for project={project_id}. Marking FAILED."
            )
            db.table("projects").update(
                {"status": PipelineStatus.FAILED.value}
            ).eq("id", project_id).execute()
            raise


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
)
def generate_message_images_task(self, message_id: str, model: str, prompt: str, aspect_ratio: str = "16:9"):
    """
    Celery task — Studio Chat image generation:
    1. Call image provider API (Gemini or Freepik)
    2. Upload each image to Supabase Storage under messages/{message_id}/images/
    3. Update message row with public URLs and COMPLETED status

    Retry policy: same as generate_images_task (3 retries, exponential backoff + jitter).
    """
    task_id = self.request.id
    logger.info(
        f"[Task {task_id}] generate_message_images_task started — "
        f"message={message_id}, model={model}, ratio={aspect_ratio}, "
        f"attempt={self.request.retries + 1}/{self.max_retries + 1}"
    )
    db = get_supabase()

    try:
        # Run async image generation
        provider = get_image_provider(model)
        raw_urls = asyncio.run(
            provider.generate(prompt=prompt, count=4, aspect_ratio=aspect_ratio)
        )

        if not raw_urls:
            raise RuntimeError(f"Provider '{model}' returned zero images for message={message_id}")

        # Upload to Supabase Storage and collect public URLs
        timestamp = int(time.time())
        public_urls: list[str] = []

        for i, url_or_data in enumerate(raw_urls):
            storage_path = f"messages/{message_id}/images/image_{i}.png"
            image_bytes = _fetch_or_decode_image(url_or_data)
            db.storage.from_("media").upload(
                storage_path,
                image_bytes,
                {"content-type": "image/png", "upsert": "true"},
            )
            public_url = db.storage.from_("media").get_public_url(storage_path)
            public_urls.append(f"{public_url}?t={timestamp}")

        # Persist results
        db.table("messages").update(
            {
                "image_urls": public_urls,
                "status": "COMPLETED",
            }
        ).eq("id", message_id).execute()

        logger.info(
            f"[Task {task_id}] generate_message_images_task COMPLETED — "
            f"message={message_id}, {len(public_urls)} image(s) uploaded"
        )

    except _FATAL_ERRORS as exc:
        logger.error(
            f"[Task {task_id}] Fatal error in generate_message_images_task for message={message_id}: {exc}"
        )
        db.table("messages").update(
            {"status": "FAILED"}
        ).eq("id", message_id).execute()
        raise

    except Exception as exc:
        logger.exception(
            f"[Task {task_id}] Error in generate_message_images_task for message={message_id} "
            f"(attempt {self.request.retries + 1}/{self.max_retries + 1}): {exc}"
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error(
                f"[Task {task_id}] Max retries exceeded for message={message_id}. Marking FAILED."
            )
            db.table("messages").update(
                {"status": "FAILED"}
            ).eq("id", message_id).execute()
            raise


def _fetch_or_decode_image(url_or_data: str) -> bytes:
    """Handle both public URLs and base64 data URLs returned by providers."""
    if url_or_data.startswith("data:image"):
        # base64 encoded image from Gemini
        _, encoded = url_or_data.split(",", 1)
        return base64.b64decode(encoded)

    # Fetch from public URL (e.g. Freepik CDN)
    with httpx.Client(timeout=30) as client:
        response = client.get(url_or_data)
        response.raise_for_status()
        return response.content
