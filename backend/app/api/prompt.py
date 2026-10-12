from __future__ import annotations
from fastapi import APIRouter, HTTPException
import time
from app.core.database import get_supabase
from app.core.config import get_settings
from app.core.logging import logger
from app.core.circuit_breaker import gemini_text_breaker
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

# Finish reasons that indicate the model will never produce output on this prompt
_TERMINAL_FINISH_REASONS = {"SAFETY", "RECITATION", "PROHIBITED_CONTENT", "SPII"}


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


def _extract_text_from_response(response) -> str | None:
    """
    Safely extract text from a Gemini GenerateContentResponse.

    Returns the text string if the model produced output, or None if:
    - The response has no candidates
    - The candidate was blocked (safety / recitation)
    - The candidate has no text parts
    """
    if not response.candidates:
        logger.warning("[_extract_text] Response has no candidates")
        return None

    candidate = response.candidates[0]

    # Check finish reason for terminal blocks (don't retry these)
    finish_reason = str(getattr(candidate, "finish_reason", "") or "")
    if finish_reason in _TERMINAL_FINISH_REASONS:
        logger.warning(f"[_extract_text] Candidate blocked: finish_reason={finish_reason}")
        return None  # Caller interprets None + terminal reason as "no point retrying"

    # Extract text parts
    if not (candidate.content and candidate.content.parts):
        logger.warning("[_extract_text] Candidate has no content parts")
        return None

    text = "".join(
        part.text for part in candidate.content.parts if getattr(part, "text", None)
    ).strip()

    if not text:
        logger.warning("[_extract_text] Candidate parts contain no text")
        return None

    return text


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

    logger.info(f"[refine_prompt] project_id={project_id}, regenerate={payload.regenerate}, model={payload.gemini_model}")

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
    raw_output: str | None = None

    try:
        # ── Circuit breaker check ─────────────────────────────────────────────
        if not gemini_text_breaker.allow_request():
            raise RuntimeError("Gemini text circuit is OPEN — skipping call")

        client = genai.Client(api_key=settings.gemini_api_key)

        # ── Retry loop: up to 3 attempts with exponential backoff ─────────────
        max_attempts = 3
        last_exc: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                response = client.models.generate_content(
                    model=model_id,
                    contents=user_message,
                    config=genai.types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.82,
                        max_output_tokens=600,
                    ),
                )
                text = _extract_text_from_response(response)

                if text is not None:
                    raw_output = text
                    gemini_text_breaker.record_success()
                    break  # ✅ success

                # Check if this is a terminal block (no point retrying)
                candidate = response.candidates[0] if response.candidates else None
                finish_reason = str(getattr(candidate, "finish_reason", "") or "")
                if finish_reason in _TERMINAL_FINISH_REASONS:
                    logger.warning(f"[refine_prompt] Blocked by safety filter (finish_reason={finish_reason}). Using fallback.")
                    gemini_text_breaker.record_failure()
                    break  # don't waste attempts on a safety block

                # Empty output but not terminal — retry
                wait = min(2.0 * (2 ** (attempt - 1)), 16.0)
                logger.warning(f"[refine_prompt] Attempt {attempt}/{max_attempts}: empty model output. Retrying in {wait:.1f}s...")
                time.sleep(wait)

            except Exception as e:
                last_exc = e
                error_str = str(e)
                gemini_text_breaker.record_failure()

                # Quota exhausted — no point retrying
                if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
                    logger.warning(f"[refine_prompt] Quota exhausted on attempt {attempt}. Falling back.")
                    break

                if attempt < max_attempts:
                    wait = min(2.0 * (2 ** (attempt - 1)), 16.0)
                    logger.warning(f"[refine_prompt] Attempt {attempt}/{max_attempts} error: {e}. Retrying in {wait:.1f}s...")
                    time.sleep(wait)
                else:
                    logger.error(f"[refine_prompt] All {max_attempts} attempts failed. Last error: {e}")
                    raise  # propagate to outer except for fallback handling

    except Exception as e:
        logger.error(f"[refine_prompt] Gemini API error: {e}")
        raw_output = None  # trigger fallback below

    # ── Parse structured output or fall back gracefully ───────────────────────
    if raw_output:
        parsed = _parse_dual_prompt(raw_output)
        logger.debug(f"[refine_prompt] parsed image_prompt: {parsed['image_prompt'][:80]!r}")

        # If parse failed (missing sections), use full output as refined_prompt
        if not parsed["image_prompt"] and not parsed["full_script"]:
            parsed["full_script"] = raw_output
            parsed["image_prompt"] = raw_output[:300]  # truncate for image model
    else:
        # Graceful fallback — user is not blocked, raw prompt is used directly
        style_suffix = f" {style_context}".strip()
        parsed["full_script"] = f"{raw_prompt}{style_suffix}"
        parsed["image_prompt"] = f"{raw_prompt}{style_suffix}"
        logger.warning("[refine_prompt] Using raw prompt as fallback due to Gemini failure")

    # refined_prompt shown in Step 2 UI = full script
    refined_prompt = parsed["full_script"] or parsed["image_prompt"] or raw_prompt

    # Persist all three to DB
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
