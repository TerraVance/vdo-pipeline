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
from google import genai
from app.core.config import get_settings
from app.workers.image_tasks import generate_message_images_task

SYSTEM_PROMPT_CHAT = """\
You are an elite AI Prompt Engineer and Creative Director. 
Your goal is to help the user craft the perfect, highly-detailed prompt for AI image generators (like Midjourney, Gemini, or Freepik).

CRITICAL INSTRUCTIONS:
1. Carefully read ALL rules and constraints the user provides.
2. Ensure every single detail the user asks for (colors, lighting, character expressions, background effects) is explicitly included in the prompt you generate.
3. If the user asks for at least 100 words, make sure your prompt is richly detailed and meets the word count requirement.
4. Format your response beautifully so the user can easily read and copy the final prompt.
5. Do NOT use strict labels like 'IMAGE_PROMPT:' unless it helps readability. Just converse naturally and provide the best possible image prompt.
"""

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
    result = db.table("sessions").select("*").eq("id", session_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Session not found")
    return result.data[0]


def _cleanup_message_storage(db, messages: List[dict]):
    """Delete all image files from Supabase Storage and revoke any active Celery tasks."""
    files_to_remove = set()
    for msg in messages:
        msg_id = msg.get("id")
        if not msg_id:
            continue
        
        # Revoke Celery task if still pending/running
        task_id = msg.get("task_id")
        if task_id:
            try:
                from app.core.celery_app import celery_app
                celery_app.control.revoke(task_id, terminate=True)
            except Exception:
                pass

        # 1. List files in storage under messages/{msg_id}/images
        folder = f"messages/{msg_id}/images"
        try:
            items = db.storage.from_("media").list(folder)
            for item in items:
                name = item.get("name") if isinstance(item, dict) else getattr(item, "name", None)
                if name and name != ".emptyFolderPlaceholder":
                    files_to_remove.add(f"{folder}/{name}")
        except Exception as e:
            print(f"Warning listing storage in {folder}: {e}")

        # 2. Extract paths from image_urls
        for url in (msg.get("image_urls") or []):
            if "/media/" in url:
                path = url.split("/media/", 1)[1].split("?")[0]
                files_to_remove.add(path)

    if files_to_remove:
        file_list = list(files_to_remove)
        print(f"Cleaning up {len(file_list)} files from storage: {file_list}")
        for i in range(0, len(file_list), 50):
            try:
                db.storage.from_("media").remove(file_list[i : i + 50])
            except Exception as e:
                print(f"Warning removing storage files: {e}")


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str):
    db = get_supabase()
    result = db.table("sessions").select("id").eq("id", session_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # 1. Find all messages in this session and delete their storage images
    try:
        messages_res = db.table("messages").select("id, task_id, image_urls").eq("session_id", session_id).execute()
        if messages_res.data:
            _cleanup_message_storage(db, messages_res.data)
    except Exception as e:
        print(f"Warning cleaning storage for session {session_id}: {e}")

    # 2. Delete messages from database table
    try:
        db.table("messages").delete().eq("session_id", session_id).execute()
    except Exception as e:
        print(f"Warning deleting messages for session {session_id}: {e}")

    # 3. Delete session from database table
    db.table("sessions").delete().eq("id", session_id).execute()


@router.delete("/sessions/{session_id}/messages/{message_id}", status_code=204)
def delete_message(session_id: str, message_id: str):
    db = get_supabase()
    res = db.table("messages").select("id, task_id, image_urls").eq("id", message_id).eq("session_id", session_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Message not found")

    _cleanup_message_storage(db, res.data)
    db.table("messages").delete().eq("id", message_id).execute()


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
    session = db.table("sessions").select("*").eq("id", session_id).execute()
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
    
    # Auto-generate title if this is the first message
    session_data = session.data[0]
    is_first_message = session_data.get("title") == "New Conversation"
    if is_first_message:
        try:
            settings = get_settings()
            client = genai.Client(api_key=settings.gemini_api_key)
            title_resp = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=f"Summarize this concept in 3 to 5 words for a short chat title. Don't use quotes, punctuation, or extra text. Concept: {payload.content}"
            )
            new_title = title_resp.text.strip().replace('"', '')
        except Exception:
            new_title = payload.content[:30] + ("..." if len(payload.content) > 30 else "")
            
        db.table("sessions").update({"title": new_title, "updated_at": "now()"}).eq("id", session_id).execute()
    else:
        # Just update session updated_at
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
    
    if payload.action == ActionType.REFINE_PROMPT.value:
        settings = get_settings()
        try:
            client = genai.Client(api_key=settings.gemini_api_key)
            
            # Fetch conversation history so the model remembers past prompts
            history_messages = db.table("messages").select("*").eq("session_id", session_id).neq("id", user_msg["id"]).order("created_at", desc=False).execute()
            
            gemini_history = []
            for msg in history_messages.data:
                # Map our roles to Gemini roles ('user' -> 'user', 'assistant' -> 'model')
                role = "model" if msg["role"] == "assistant" else "user"
                # Skip system messages or empty content
                if not msg["content"] or msg["role"] not in ["user", "assistant"]:
                    continue
                gemini_history.append({"role": role, "parts": [{"text": msg["content"]}]})
            
            chat = client.chats.create(
                model=payload.model or "gemini-3.8-flash",
                config=genai.types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT_CHAT,
                    temperature=0.7,
                    max_output_tokens=8192,
                    safety_settings=[
                        genai.types.SafetySetting(
                            category=genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                            threshold=genai.types.HarmBlockThreshold.BLOCK_NONE,
                        ),
                        genai.types.SafetySetting(
                            category=genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                            threshold=genai.types.HarmBlockThreshold.BLOCK_NONE,
                        ),
                        genai.types.SafetySetting(
                            category=genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                            threshold=genai.types.HarmBlockThreshold.BLOCK_NONE,
                        ),
                        genai.types.SafetySetting(
                            category=genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                            threshold=genai.types.HarmBlockThreshold.BLOCK_NONE,
                        ),
                    ]
                ),
                history=gemini_history
            )
            
            response = chat.send_message(payload.content)
            assistant_msg["content"] = response.text
            assistant_msg["status"] = MessageStatus.COMPLETED.value
        except Exception as e:
            assistant_msg["content"] = f"Error generating prompt: {e}"
            assistant_msg["status"] = MessageStatus.FAILED.value
            
        result = db.table("messages").insert(assistant_msg).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create assistant message")
        return result.data[0]

    elif payload.action == ActionType.CREATE_IMAGE.value:
        assistant_msg["content"] = f"Generating image using {payload.model}..."
        
        result = db.table("messages").insert(assistant_msg).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create assistant message")
            
        msg_id = result.data[0]["id"]
        
        task = generate_message_images_task.delay(msg_id, payload.model, payload.content, payload.aspect_ratio or "16:9")
        db.table("messages").update({"task_id": task.id}).eq("id", msg_id).execute()
        
        # Manually return the updated data so frontend knows the task_id
        msg_data = result.data[0]
        msg_data["task_id"] = task.id
        return msg_data

    else:
        assistant_msg["content"] = "I can help you create images. Select an action below."
        assistant_msg["status"] = MessageStatus.COMPLETED.value
        result = db.table("messages").insert(assistant_msg).execute()
        return result.data[0]
