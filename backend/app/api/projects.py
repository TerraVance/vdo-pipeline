from fastapi import APIRouter, HTTPException
from app.core.database import get_supabase
from app.models.schemas import (
    CreateProjectRequest,
    ProjectResponse,
    ProjectStatusResponse,
    SelectImageRequest,
)
import uuid

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(payload: CreateProjectRequest):
    """Stage 4.1 — Create a new project with a raw prompt and style tags."""
    db = get_supabase()
    data = {
        "id": str(uuid.uuid4()),
        "raw_prompt": payload.raw_prompt,
        "style_tags": payload.style_tags,
        "status": "DRAFT",
        "image_urls": [],
    }
    result = db.table("projects").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create project")
    row = result.data[0]
    return _map_row(row)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str):
    """Stage 4.2 — Retrieve full project state."""
    db = get_supabase()
    result = db.table("projects").select("*").eq("id", project_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Project not found")
    return _map_row(result.data)


@router.get("/{project_id}/status", response_model=ProjectStatusResponse)
def get_project_status(project_id: str):
    """Lightweight status poll endpoint — called by frontend every 3-5s."""
    db = get_supabase()
    result = (
        db.table("projects")
        .select("id, status, task_id, image_urls, selected_image_url, final_video_url")
        .eq("id", project_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Project not found")
    row = result.data
    return ProjectStatusResponse(
        id=row["id"],
        status=row["status"],
        task_id=row.get("task_id"),
        image_urls=row.get("image_urls") or [],
        selected_image_url=row.get("selected_image_url"),
        final_video_url=row.get("final_video_url"),
    )


@router.patch("/{project_id}/select-image", response_model=ProjectResponse)
def select_image(project_id: str, payload: SelectImageRequest):
    """User picks one image from the 2x2 grid as the video seed."""
    db = get_supabase()
    result = (
        db.table("projects")
        .update({"selected_image_url": payload.image_url})
        .eq("id", project_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Project not found")
    return _map_row(result.data[0])


# ── Helper ────────────────────────────────────────────────────────────

def _map_row(row: dict) -> ProjectResponse:
    return ProjectResponse(
        id=row["id"],
        raw_prompt=row["raw_prompt"],
        style_tags=row.get("style_tags") or [],
        refined_prompt=row.get("refined_prompt"),
        image_urls=row.get("image_urls") or [],
        selected_image_url=row.get("selected_image_url"),
        final_video_url=row.get("final_video_url"),
        status=row["status"],
        task_id=row.get("task_id"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )
