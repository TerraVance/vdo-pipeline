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
    Stage 3 — Enqueue image generation task.
    Returns 202 immediately; frontend polls /status for updates.

    Prompt priority:
      1. payload.prompt  (manual override from Step 3 iterate editor)
      2. project.image_prompt  (focused 40-60 word visual description from Phase 1 refinement)
      3. project.refined_prompt  (full cinematic script — fallback for old projects)
      4. project.raw_prompt  (last resort)
    """
    db = get_supabase()

    # Fetch project to get the prompt
    result = db.table("projects").select("*").eq("id", project_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Project not found")

    project = result.data

    # Use focused image_prompt so the image model gets a static visual description,
    # not a 200-word video production script.
    prompt = (
        payload.prompt
        or project.get("image_prompt")
        or project.get("refined_prompt")
        or project["raw_prompt"]
    )

    # Enqueue Celery task
    task = generate_images_task.delay(
        project_id=project_id,
        model=payload.model.value,
        prompt=prompt,
        aspect_ratio=payload.aspect_ratio,
    )

    return {
        "message": "Image generation started",
        "task_id": task.id,
        "project_id": project_id,
        "model": payload.model.value,
        "prompt_used": prompt[:100] + "..." if len(prompt) > 100 else prompt,
    }
