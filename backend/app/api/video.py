from fastapi import APIRouter, HTTPException
from app.core.database import get_supabase
from app.models.schemas import SynthesizeVideoRequest
from app.workers.video_tasks import synthesize_video_task

router = APIRouter(prefix="/api/v1/projects", tags=["video"])


@router.post("/{project_id}/synthesize-video", status_code=202)
def synthesize_video(project_id: str, payload: SynthesizeVideoRequest):
    """
    Stage 7.7 — Enqueue video synthesis task.
    Returns 202 immediately; frontend polls /status for VIDEO_READY.
    """
    db = get_supabase()

    result = db.table("projects").select("*").eq("id", project_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Project not found")

    project = result.data
    prompt = payload.prompt or project.get("refined_prompt") or project["raw_prompt"]

    task = synthesize_video_task.delay(
        project_id=project_id,
        model=payload.model.value,
        image_url=payload.image_url,
        prompt=prompt,
    )

    return {
        "message": "Video synthesis started",
        "task_id": task.id,
        "project_id": project_id,
        "model": payload.model.value,
    }
