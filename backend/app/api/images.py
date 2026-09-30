from fastapi import APIRouter, HTTPException
from app.core.database import get_supabase
from app.models.schemas import (
    GenerateImagesRequest,
    PipelineStatus,
)
from app.workers.image_tasks import generate_images_task

router = APIRouter(prefix="/api/v1/projects", tags=["images"])


@router.post("/{project_id}/generate-images", status_code=202)
def generate_images(project_id: str, payload: GenerateImagesRequest):
    """
    Stage 6.7 — Enqueue image generation task.
    Returns 202 immediately; frontend polls /status for updates.
    """
    db = get_supabase()

    # Fetch project to get the prompt
    result = db.table("projects").select("*").eq("id", project_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Project not found")

    project = result.data
    prompt = payload.prompt or project.get("refined_prompt") or project["raw_prompt"]

    # Enqueue Celery task
    task = generate_images_task.delay(
        project_id=project_id,
        model=payload.model.value,
        prompt=prompt,
    )

    return {
        "message": "Image generation started",
        "task_id": task.id,
        "project_id": project_id,
        "model": payload.model.value,
    }
