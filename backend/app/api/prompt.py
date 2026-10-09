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
#
# The LLM returns a structured response with THREE clearly-delimited sections.
# This lets image generation and video generation each use the right prompt type.

SYSTEM_PROMPT_PRIMARY = """\
You are a world-class creative director and AI prompt engineer.

Given the user's raw concept, produce a structured production brief with exactly THREE sections.
Each section must start on its own line with the exact label shown.

IMAGE_PROMPT:
A focused, 40–60 word visual description for a still-image AI generator.
Describe ONLY the static visual: subject details, scene setting, lighting, color palette, camera angle.
Do NOT mention motion, animation, or time-based events.

FULL_SCRIPT:
A rich 120–160 word cinematic production description.
Include: subject, scene, lighting, color palette, texture, atmosphere, style reference.

CRITICAL RULES:
- The user's original concept MUST be the core of every section. Expand it, never replace it.
- Output ONLY the three labeled sections — no preamble, no explanation, no markdown.
- Start your response immediately with "IMAGE_PROMPT:"
"""

SYSTEM_PROMPT_ALTERNATE = """\
You are an avant-garde visual artist and AI prompt engineer. Your style is bold and unexpected.

Given the user's raw concept, produce a structured production brief with exactly THREE sections.

IMAGE_PROMPT:
A 40–60 word striking static visual description for an image AI.
Use unconventional composition, distinctive color treatment, unexpected framing.
ONLY describe the still visual — no motion.

FULL_SCRIPT:
A 120–160 word avant-garde visual production brief.
Push boundaries while staying true to the user's original concept.

CRITICAL RULES:
- The user's original concept MUST be preserved as the foundation.
- Output ONLY the three labeled sections — no preamble, no explanation.
- Start immediately with "IMAGE_PROMPT:"
"""


def _parse_dual_prompt(text: str) -> dict:
    """
    Parse the structured LLM output into image_prompt, motion_prompt, full_script.
    Returns a dict with all three keys (each may be empty string on parse failure).
    """
    sections = {"image_prompt": "", "full_script": ""}
    current = None
    lines_buffer: list[str] = []

    label_map = {
        "IMAGE_PROMPT:": "image_prompt",
        "FULL_SCRIPT:": "full_script",
    }

    for line in text.splitlines():
        stripped = line.strip()
        matched_label = None
        for label, key in label_map.items():
            if stripped.startswith(label):
                # Save accumulated lines to previous section
                if current:
                    sections[current] = " ".join(lines_buffer).strip()
                current = key
                lines_buffer = [stripped[len(label):].strip()]
                matched_label = label
                break
        if not matched_label and current:
            lines_buffer.append(stripped)

    # Save the last section
    if current:
        sections[current] = " ".join(lines_buffer).strip()

    return sections


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/gemini-models")
def get_gemini_models():
    """Return the list of available Gemini text models for the frontend dropdown."""
    return {"models": GEMINI_TEXT_MODELS}


@router.post("/{project_id}/refine-prompt", response_model=RefinePromptResponse)
def refine_prompt(project_id: str, payload: RefinePromptRequest):
    """
    Stage 2 — Call Gemini to expand the raw prompt into a structured production brief.

    Returns:
      - refined_prompt   (full cinematic script — displayed in Step 2 UI)
      - image_prompt     (focused visual description → fed to image gen in Step 3)
    """
    settings = get_settings()
    db = get_supabase()

    # Fetch the project (without .single() to avoid PGRST116 exception on 0 rows)
    result = db.table("projects").select("*").eq("id", project_id).execute()
    if not result.data or len(result.data) == 0:
        raise HTTPException(status_code=404, detail="Project not found. Please click '+ New Project' to start fresh.")

    project = result.data[0]
    raw_prompt = project["raw_prompt"]
    style_tags = project.get("style_tags") or []

    # ── DEBUG: log exactly what we received from DB ───────────────────────────
    print(f"\n[refine_prompt] project_id={project_id}")
    print(f"[refine_prompt] raw_prompt from DB: {raw_prompt!r}")
    print(f"[refine_prompt] style_tags: {style_tags}")
    print(f"[refine_prompt] regenerate={payload.regenerate}, model={payload.gemini_model}")

    # Build user message — always embed the full original text
    style_context = f"\nStyle preferences: {', '.join(style_tags)}." if style_tags else ""
    user_message = (
        f"USER'S ORIGINAL CONCEPT (preserve this exactly as the core idea):\n"
        f"{raw_prompt}"
        f"{style_context}"
    )

    # Select system prompt
    system_prompt = SYSTEM_PROMPT_ALTERNATE if payload.regenerate else SYSTEM_PROMPT_PRIMARY

    # Validate model ID
    valid_ids = {m["id"] for m in GEMINI_TEXT_MODELS}
    model_id = payload.gemini_model if payload.gemini_model in valid_ids else "gemini-3-flash-preview"

    parsed = {"image_prompt": "", "full_script": ""}

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=model_id,
            contents=user_message,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.82,
                max_output_tokens=600,
            ),
        )
        raw_output = response.text.strip()
        print(f"[refine_prompt] LLM raw output ({len(raw_output)} chars):\n{raw_output[:500]}")
        parsed = _parse_dual_prompt(raw_output)
        print(f"[refine_prompt] parsed image_prompt: {parsed['image_prompt'][:80]!r}")
        print(f"[refine_prompt] parsed full_script (first 100): {parsed['full_script'][:100]!r}")

        # If parse failed (missing sections), use full output as refined_prompt
        if not parsed["image_prompt"] and not parsed["full_script"]:
            parsed["full_script"] = raw_output
            parsed["image_prompt"] = raw_output[:300]  # truncate for image model

    except Exception as e:
        print(f"Gemini API error in refine_prompt: {e}")
        # Graceful fallback — user is not blocked
        style_suffix = f" {style_context}".strip()
        parsed["full_script"] = f"{raw_prompt}{style_suffix}"
        parsed["image_prompt"] = f"{raw_prompt}{style_suffix}"

    # refined_prompt shown in Step 2 UI = full script
    refined_prompt = parsed["full_script"] or parsed["image_prompt"] or raw_prompt

    # Persist all three to DB
    # image_prompt and motion_prompt columns must exist in the projects table.
    # If they don't yet, the update will silently ignore them (Supabase/PostgREST
    # ignores unknown columns in PATCH/UPDATE calls).
    db.table("projects").update(
        {
            "refined_prompt": refined_prompt,
            "image_prompt": parsed["image_prompt"],
            "status": PipelineStatus.PROMPT_REFINED.value,
        }
    ).eq("id", project_id).execute()

    return RefinePromptResponse(
        project_id=project_id,
        original_prompt=raw_prompt,
        refined_prompt=refined_prompt,
        image_prompt=parsed["image_prompt"],
        status=PipelineStatus.PROMPT_REFINED,
    )
