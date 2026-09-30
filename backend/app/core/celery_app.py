from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "vdo_pipeline",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.image_tasks",
        "app.workers.video_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # Process one task at a time per worker
    broker_connection_retry_on_startup=True, # Recommended by Celery 5.3+
    task_reject_on_worker_lost=True, # Re-queue task if worker crashes
)
