from enum import Enum
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class PipelineStatus(str, Enum):
    DRAFT = "DRAFT"
    PROMPT_REFINED = "PROMPT_REFINED"
    GENERATING_IMAGES = "GENERATING_IMAGES"
    IMAGES_READY = "IMAGES_READY"
    FAILED = "FAILED"


# ── Image Models ──────────────────────────────────────────────────────────────
# Each value maps to a specific model endpoint.
# Grouped by which API key powers them.

class ImageModel(str, Enum):
    # ── Gemini API (GEMINI_API_KEY) ─────────────────────────────────
    GEMINI_IMAGEN3 = "gemini_imagen3"
    # → gemini-3.1-flash-image — flagship image model (via generate_content)

    GEMINI_IMAGEN3_FAST = "gemini_imagen3_fast"
    # → gemini-3.1-flash-lite-image — ~2× faster, lighter

    GEMINI_IMAGE_PRO = "gemini_image_pro"
    # → gemini-3-pro-image — highest quality (paid tier)

    # ── Freepik API (FREEPIK_API_KEY) ─────────────────────────────────
    FREEPIK_MYSTIC_PHOTO = "freepik_mystic_photo"
    # → Mystic endpoint, style=photo — photorealistic output

    FREEPIK_MYSTIC_ART = "freepik_mystic_art"
    # → Mystic endpoint, style=digital-art — illustrated / stylised output



# ── Request Schemas ───────────────────────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    raw_prompt: str
    style_tags: List[str] = []


class RefinePromptRequest(BaseModel):
    regenerate: bool = False  # True → use alternate Gemini system prompt
    gemini_model: str = "gemini-3-flash-preview"  # which Gemini text model to use


# ── Available Gemini text models (for frontend dropdown) ──────────────────────
GEMINI_TEXT_MODELS = [
    {"id": "gemini-3-flash-preview", "label": "Gemini 3 Flash",        "description": "Latest & fastest — recommended"},
    {"id": "gemini-3.8-flash",       "label": "Gemini 3.8 Flash",      "description": "Stable, proven for creative tasks"},
    {"id": "gemini-3.1-flash-lite",  "label": "Gemini 3.1 Flash Lite", "description": "Most cost-efficient, high volume"},
    {"id": "gemini-3.1-pro-preview", "label": "Gemini 3.1 Pro",        "description": "Highest quality, slower (paid tier)"},
]


class GenerateImagesRequest(BaseModel):
    model: ImageModel = ImageModel.GEMINI_IMAGEN3  # default: gemini-3.1-flash-image
    prompt: Optional[str] = None                   # override stored refined_prompt
    aspect_ratio: str = "16:9"                     # e.g. "16:9", "9:16", "1:1", "4:3", "3:4"




class SelectImageRequest(BaseModel):
    image_url: str


# ── Response Schemas ──────────────────────────────────────────────────────────

class ProjectResponse(BaseModel):
    id: str
    raw_prompt: str
    style_tags: List[str]
    refined_prompt: Optional[str] = None
    image_urls: List[str] = []
    selected_image_url: Optional[str] = None
    status: PipelineStatus
    task_id: Optional[str] = None
    user_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProjectStatusResponse(BaseModel):
    id: str
    status: PipelineStatus
    task_id: Optional[str] = None
    image_urls: List[str] = []
    selected_image_url: Optional[str] = None


class RefinePromptResponse(BaseModel):
    project_id: str
    original_prompt: str
    refined_prompt: str
    image_prompt: str = ""   # focused visual description → image model
    status: PipelineStatus


# ── Chat Studio Schemas ───────────────────────────────────────────────────────

class MessageStatus(str, Enum):
    COMPLETED = "COMPLETED"
    PENDING = "PENDING"
    FAILED = "FAILED"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ActionType(str, Enum):
    CREATE_IMAGE = "create_image"
    REFINE_PROMPT = "refine_prompt"


class CreateSessionRequest(BaseModel):
    title: str = "New Conversation"


class SessionResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    title: str
    created_at: datetime
    updated_at: datetime


class SendMessageRequest(BaseModel):
    content: str
    action: Optional[ActionType] = None
    model: Optional[str] = None
    aspect_ratio: Optional[str] = None


class MessageResponse(BaseModel):
    id: str
    session_id: str
    role: MessageRole
    content: str
    action: Optional[str] = None
    model: Optional[str] = None
    aspect_ratio: Optional[str] = None
    image_urls: List[str] = []
    status: MessageStatus
    task_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
