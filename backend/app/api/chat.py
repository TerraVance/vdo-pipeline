from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List
from app.core.database import get_supabase
from app.core.security import get_current_user_optional, get_current_user_required
from app.models.schemas import (
    CreateSessionRequest,
    SessionResponse,
    SendMessageRequest,
    MessageResponse,
    MessageRole,
    MessageStatus,
    ActionType
)
import uuid
import datetime

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

@router.post("/sessions", response_model=SessionResponse, status_code=201)
def create_session(payload: CreateSessionRequest, user_id: str = Depends(get_current_user_optional)):
    db = get_supabase()
    data = {
        "id": str(uuid.uuid4()),
        "title": payload.title,
        "user_id": user_id,
    }
    result = db.table("sessions").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create session")
    return result.data[0]


@router.get("/sessions", response_model=List[SessionResponse])
def get_user_sessions(user_id: str = Depends(get_current_user_required)):
    db = get_supabase()
    try:
        result = (
            db.table("sessions")
            .select("*")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as e:
        print(f"DB error in get_user_sessions: {e}")
        raise HTTPException(status_code=503, detail="Database temporarily unavailable.")


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str):
    db = get_supabase()
    result = db.table("sessions").select("*").eq("id", session_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Session not found")
    return result.data


@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
def get_session_messages(session_id: str):
    db = get_supabase()
    result = (
        db.table("messages")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .execute()
    )
    return result.data or []


@router.post("/sessions/{session_id}/messages", response_model=MessageResponse, status_code=201)
def send_message(session_id: str, payload: SendMessageRequest):
    db = get_supabase()
    
    # 1. Verify session
    session = db.table("sessions").select("id").eq("id", session_id).single().execute()
    if not session.data:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # 2. Insert User Message
    user_msg = {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "role": MessageRole.USER.value,
        "content": payload.content,
        "action": payload.action,
        "model": payload.model,
        "aspect_ratio": payload.aspect_ratio,
        "status": MessageStatus.COMPLETED.value
    }
    db.table("messages").insert(user_msg).execute()
    
    # Update session updated_at
    db.table("sessions").update({"updated_at": "now()"}).eq("id", session_id).execute()

    # 3. Handle Action and create Assistant Message
    assistant_msg = {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "role": MessageRole.ASSISTANT.value,
        "content": "",
        "action": payload.action,
        "model": payload.model,
        "aspect_ratio": payload.aspect_ratio,
        "status": MessageStatus.PENDING.value
    }
    
    # Here we would enqueue Celery tasks and update the assistant_msg with task_id.
    # For now, we stub this out pending refactoring of celery tasks.
    if payload.action == ActionType.REFINE_PROMPT.value:
        # e.g., call synchronous LLM
        assistant_msg["content"] = f"Refined prompt based on: {payload.content}"
        assistant_msg["status"] = MessageStatus.COMPLETED.value
    elif payload.action == ActionType.CREATE_IMAGE.value:
        assistant_msg["content"] = f"Generating image using {payload.model}..."
        # task_id = enqueue_image_task(...)
        # assistant_msg["task_id"] = task_id
    else:
        assistant_msg["content"] = "I can help you create images. Select an action below."
        assistant_msg["status"] = MessageStatus.COMPLETED.value
        
    result = db.table("messages").insert(assistant_msg).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create assistant message")
        
    return result.data[0]
