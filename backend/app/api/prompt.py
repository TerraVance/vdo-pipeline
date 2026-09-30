from fastapi import APIRouter, HTTPException
from app.core.database import get_supabase
from app.core.config import get_settings
from app.models.schemas import (
    RefinePromptRequest,
    RefinePromptResponse,
    PipelineStatus,
    GEMINI_TEXT_MODELS,
)
from google import genai

router = APIRouter(prefix="/api/v1/projects", tags=["prompt"])

# ── System prompt templates ───────────────────────────────────────────────────

SYSTEM_PROMPT_PRIMARY = """You are a world-class creative director and prompt engineer specializing in AI video and image generation.
Your task is to take a raw concept and expand it into a rich, detailed production-ready prompt.

The refined prompt MUST include:
- Precise subject description (character/object/scene details)
- Camera angle and movement (e.g., "slow dolly push-in", "bird's eye view", "Dutch angle")
- Lighting setup (e.g., "dramatic neon backlighting", "golden hour soft rays", "high-contrast chiaroscuro")
- Color palette and mood (e.g., "desaturated blues and teals", "warm amber tones")
- Texture and material details (e.g., "wet asphalt reflecting neon", "worn leather texture")
- Atmospheric effects (e.g., "heavy rain", "volumetric fog", "lens flare")
- Style reference (e.g., "cinematic, anamorphic lens, 4K ultra-HD, film grain")

Keep the output to 150-200 words. Output ONLY the refined prompt, no explanation or preamble."""

SYSTEM_PROMPT_ALTERNATE = """You are an avant-garde visual artist and AI prompt engineer. Your style is unexpected, bold, and imaginative.
Expand the user's concept into a striking, unconventional production prompt.

Include:
- Unexpected compositional choices (e.g., symmetrical split-diopter, extreme macro)
- Distinctive color treatment (e.g., "monochromatic teal with single red accent")
- Unusual atmospheric conditions
- Specific cinematic or artistic style reference
- Emotional undertone
- Material and textural specifics

Keep output to 150-200 words. Output ONLY the refined prompt, no preamble."""


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/gemini-models")
def get_gemini_models():
    """Return the list of available Gemini text models for the frontend dropdown."""
    return {"models": GEMINI_TEXT_MODELS}


@router.post("/{project_id}/refine-prompt", response_model=RefinePromptResponse)
def refine_prompt(project_id: str, payload: RefinePromptRequest):
    """Stage 5 — Call Gemini to expand the raw prompt into a production-ready description."""
    settings = get_settings()
    db = get_supabase()

    # Fetch the project
    result = db.table("projects").select("*").eq("id", project_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Project not found")

    project = result.data
    raw_prompt = project["raw_prompt"]
    style_tags = project.get("style_tags") or []

    # Build user message
    style_context = f" Style preferences: {', '.join(style_tags)}." if style_tags else ""
    user_message = f"Raw concept: {raw_prompt}{style_context}"

    # Select system prompt
    system_prompt = SYSTEM_PROMPT_ALTERNATE if payload.regenerate else SYSTEM_PROMPT_PRIMARY

    # Validate model ID — fall back to latest if unknown is passed
    valid_ids = {m["id"] for m in GEMINI_TEXT_MODELS}
    model_id = payload.gemini_model if payload.gemini_model in valid_ids else "gemini-3.8-flash"

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=model_id,
            contents=user_message,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.85,
                max_output_tokens=400,
            ),
        )
        refined_prompt = response.text.strip()
    except Exception as e:
        print(f"Gemini API error (falling back to raw prompt): {e}")
        # If Gemini is overloaded (503) or fails, just gracefully bypass it 
        # using the raw prompt so the user isn't blocked.
        refined_prompt = f"{raw_prompt} {style_context}".strip()

    # Persist to DB
    db.table("projects").update(
        {
            "refined_prompt": refined_prompt,
            "status": PipelineStatus.PROMPT_REFINED.value,
        }
    ).eq("id", project_id).execute()

    return RefinePromptResponse(
        project_id=project_id,
        original_prompt=raw_prompt,
        refined_prompt=refined_prompt,
        status=PipelineStatus.PROMPT_REFINED,
    )
