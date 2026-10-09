from fastapi import APIRouter, HTTPException, Depends
from typing import List
from app.core.database import get_supabase
from app.core.security import get_current_user_optional, get_current_user_required
from app.models.schemas import (
    CreateProjectRequest,
    ProjectResponse,
    ProjectStatusResponse,
    SelectImageRequest,
)
import uuid

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(payload: CreateProjectRequest, user_id: str = Depends(get_current_user_optional)):
    """Stage 4.1 — Create a new project with a raw prompt and style tags."""
    db = get_supabase()
    data = {
        "id": str(uuid.uuid4()),
        "raw_prompt": payload.raw_prompt,
        "style_tags": payload.style_tags,
        "status": "DRAFT",
        "image_urls": [],
        "user_id": user_id,
    }
    result = db.table("projects").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create project")
    row = result.data[0]
    return _map_row(row)


@router.get("", response_model=List[ProjectResponse])
def get_all_projects():
    """Fetch all projects."""
    db = get_supabase()
    try:
        result = (
            db.table("projects")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return [_map_row(row) for row in (result.data or [])]
    except Exception as e:
        print(f"DB error in get_all_projects: {e}")
        raise HTTPException(status_code=503, detail="Database temporarily unavailable. Please try again.")


@router.get("/me", response_model=List[ProjectResponse])
def get_user_projects(user_id: str = Depends(get_current_user_required)):
    """Fetch all projects belonging to the current user (Gallery view)."""
    db = get_supabase()
    try:
        result = (
            db.table("projects")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return [_map_row(row) for row in (result.data or [])]
    except Exception as e:
        print(f"DB error in get_user_projects: {e}")
        raise HTTPException(status_code=503, detail="Database temporarily unavailable. Please try again.")


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, user_id: str = Depends(get_current_user_required)):
    """Delete a project and its associated media files."""
    db = get_supabase()
    
    # 1. Verify ownership
    result = db.table("projects").select("user_id").eq("id", project_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Project not found")
    if result.data["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this project")

    try:
        # 2. Delete media from storage bucket
        # We can try to list and remove all files in the project's folder
        files = db.storage.from_("media").list(f"projects/{project_id}/images")
        for f in files:
            db.storage.from_("media").remove([f"projects/{project_id}/images/{f['name']}"])
    except Exception as e:
        print(f"Warning: Failed to cleanup storage for {project_id}: {e}")

    # 3. Delete from database
    db.table("projects").delete().eq("id", project_id).execute()
    return None


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
    try:
        result = (
            db.table("projects")
            .select("id, status, task_id, image_urls, selected_image_url")
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
        )
    except HTTPException:
        raise  # re-raise 404s cleanly
    except Exception as e:
        print(f"DB error in get_project_status: {e}")
        raise HTTPException(status_code=503, detail="Database temporarily unavailable. Please try again.")


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
        status=row["status"],
        task_id=row.get("task_id"),
        user_id=row.get("user_id"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )
