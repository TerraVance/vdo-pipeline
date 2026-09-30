from enum import Enum
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class PipelineStatus(str, Enum):
    DRAFT = "DRAFT"
    PROMPT_REFINED = "PROMPT_REFINED"
    GENERATING_IMAGES = "GENERATING_IMAGES"
    IMAGES_READY = "IMAGES_READY"
    GENERATING_VIDEO = "GENERATING_VIDEO"
    VIDEO_READY = "VIDEO_READY"
    FAILED = "FAILED"


# ── Image Models ──────────────────────────────────────────────────────────────
# Each value maps to a specific model endpoint.
# Grouped by which API key powers them.

class ImageModel(str, Enum):
    # ── Gemini API (GEMINI_API_KEY) ─────────────────────────────────
    GEMINI_IMAGEN3 = "gemini_imagen3"
    # → gemini-3.1-flash-image — current flagship image model

    GEMINI_IMAGEN3_FAST = "gemini_imagen3_fast"
    # → gemini-3.1-flash-lite-image — ~2× faster, lighter

    GEMINI_IMAGE_PRO = "gemini_image_pro"
    # → gemini-3-pro-image — highest quality (paid tier)

    # ── Freepik API (FREEPIK_API_KEY) ─────────────────────────────────
    FREEPIK_MYSTIC_PHOTO = "freepik_mystic_photo"
    # → Mystic endpoint, style=photo — photorealistic output

    FREEPIK_MYSTIC_ART = "freepik_mystic_art"
    # → Mystic endpoint, style=digital-art — illustrated / stylised output


# ── Video Models ──────────────────────────────────────────────────────────────

class VideoModel(str, Enum):
    # ── Gemini API (GEMINI_API_KEY) ─────────────────────────────────
    GEMINI_VEO2 = "gemini_veo2"
    # → veo-3.1-generate-preview — cinematic quality, 5s

    GEMINI_VEO2_FAST = "gemini_veo2_fast"
    # → veo-3.1-fast-generate-preview — faster render

    # ── Freepik API (FREEPIK_API_KEY) ─────────────────────────────────
    FREEPIK_VIDEO = "freepik_video"
    # → /v1/ai/video — image-to-video, 5s, 720p


# ── Request Schemas ───────────────────────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    raw_prompt: str
    style_tags: List[str] = []


class RefinePromptRequest(BaseModel):
    regenerate: bool = False  # True → use alternate Gemini system prompt
    gemini_model: str = "gemini-3.8-flash"  # which Gemini text model to use


# ── Available Gemini text models (for frontend dropdown) ──────────────────────
GEMINI_TEXT_MODELS = [
    {"id": "gemini-3.8-flash",      "label": "Gemini 3.8 Flash",      "description": "Latest & fastest — recommended"},
    {"id": "gemini-3.5-flash",      "label": "Gemini 3.5 Flash",      "description": "Stable, proven for creative tasks"},
    {"id": "gemini-3.5-flash-lite", "label": "Gemini 3.5 Flash Lite", "description": "Most cost-efficient, high volume"},
    {"id": "gemini-3.1-pro",        "label": "Gemini 3.1 Pro",        "description": "Highest quality, slower (paid tier)"},
]


class GenerateImagesRequest(BaseModel):
    model: ImageModel = ImageModel.GEMINI_IMAGEN3  # default: gemini-3.1-flash-image
    prompt: Optional[str] = None                   # override stored refined_prompt


class SynthesizeVideoRequest(BaseModel):
    model: VideoModel = VideoModel.GEMINI_VEO2  # default: veo-3.1-generate-preview
    image_url: str
    prompt: Optional[str] = None


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
    final_video_url: Optional[str] = None
    status: PipelineStatus
    task_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProjectStatusResponse(BaseModel):
    id: str
    status: PipelineStatus
    task_id: Optional[str] = None
    image_urls: List[str] = []
    selected_image_url: Optional[str] = None
    final_video_url: Optional[str] = None


class RefinePromptResponse(BaseModel):
    project_id: str
    original_prompt: str
    refined_prompt: str
    status: PipelineStatus
