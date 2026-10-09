# Technical Architecture & Implementation Guide
**Interactive AI Video Generation Pipeline**

This document outlines the technical architecture, technology stack, and implementation details for building the Interactive AI Video Generation Pipeline.

---

## 1. System Architecture Diagram

The system employs a decoupled, asynchronous architecture due to the long-running nature of AI generation tasks.

```mermaid
graph TD
    %% Frontend
    subgraph Frontend [Next.js Client]
        UI[Stateful Wizard UI]
        State[Local Session State]
        Poll[Status Polling Hook]
    end

    %% Backend API
    subgraph Backend [FastAPI Server]
        Auth[Auth Middleware]
        API_Prompt[/api/prompt/refine]
        API_Image[/api/image/generate]
        API_Video[/api/video/synthesize]
        Webhook[/api/webhooks]
    end

    %% Async Workers
    subgraph Workers [Celery + Redis]
        Queue[(Redis Queue)]
        Worker_Img[Image Gen Worker]
        Worker_Vid[Video Gen Worker]
    end

    %% Persistence
    subgraph DB [Supabase]
        Postgres[(PostgreSQL)]
        Storage[(Media Storage)]
    end

    %% External APIs
    subgraph External [External AI APIs]
        Gemini[Gemini API]
        ImgAPI[Google Flow / Nano Banana / Gemini / Freepik]
        VidAPI[Kling 2.5 / Minimax / Gemini / Freepik]
    end

    %% Connections
    UI <--> State
    State -- REST calls --> Backend
    Backend -- DB Operations --> DB
    
    API_Prompt -- Sync Call --> Gemini
    
    API_Image -- Enqueue Task --> Queue
    API_Video -- Enqueue Task --> Queue
    Queue --> Worker_Img
    Queue --> Worker_Vid
    
    Worker_Img -- Async Call --> ImgAPI
    Worker_Vid -- Async Call --> VidAPI
    
    Worker_Img -- Updates Status --> DB
    Worker_Vid -- Updates Status --> DB
    
    Poll -- Checks Status --> Postgres
```

---

## 2. Technology Stack

### Frontend (Client-Side)
*   **Framework**: Next.js 14+ (App Router)
*   **Language**: TypeScript
*   **Styling**: Tailwind CSS
*   **State Management**: Zustand (for wizard steps and form data) + React Query (for API polling)
*   **Deployment**: Vercel

### Backend (Server-Side)
*   **Framework**: FastAPI (Python 3.11+)
*   **Language**: Python
*   **Task Queue**: Celery
*   **Message Broker**: Redis
*   **Deployment**: Render (Web Service + Background Worker)

### Database & Storage
*   **Platform**: Supabase
*   **Database**: PostgreSQL
*   **File Storage**: Supabase Storage (S3-compatible)
*   **Authentication**: Supabase Auth (if user accounts are needed)

### Third-Party AI Services
*   **LLM (Text)**: Google Gemini API
*   **Image Generation**: Google Gemini (via `generate_content` with `IMAGE` modality), Freepik API (Mystic)
*   **Video Generation**: Google Gemini (Veo 3.1, Veo 3.1 Lite), Freepik API (Kling / Minimax)

*Note: The backend implements smart Quota Exhaustion Tracking for Gemini API. If a `429 RESOURCE_EXHAUSTED` error is hit, the provider is temporarily disabled for the specified cooldown period, and the system automatically falls back to Freepik or propagates an honest failure to the UI.*
---

## 3. Database Schema (Supabase PostgreSQL)

We need a primary table to track the state of a video generation session.

### `projects` table
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID (PK) | Unique identifier for the generation pipeline |
| `user_id` | UUID (FK) | (Optional) Link to authenticated user |
| `raw_prompt` | TEXT | The initial idea from Step 1 |
| `style_tags` | JSONB | Array of selected styles (e.g., `["Cyberpunk", "Neon"]`) |
| `refined_prompt` | TEXT | Full cinematic script from Gemini (Step 2) |
| `image_prompt` | TEXT | Focused visual description for image models |
| `motion_prompt` | TEXT | Specific movement directive for video models |
| `image_urls` | JSONB | Array of URLs for the generated candidate images (Step 3) |
| `selected_image_url` | TEXT | The single image chosen by the user (legacy single-scene) |
| `selected_image_urls`| JSONB | Array of images chosen for multi-scene video |
| `final_video_url` | TEXT | URL to the generated MP4 file (Step 4) |
| `status` | ENUM | Current pipeline state (see below) |
| `task_id` | VARCHAR | ID of the current Celery task (for background tracking) |
| `created_at` | TIMESTAMPTZ | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | Last update timestamp |

### `Pipeline Status ENUM`
*   `DRAFT`: Initial state
*   `PROMPT_REFINED`: Gemini returned text
*   `GENERATING_IMAGES`: Celery worker is fetching images
*   `IMAGES_READY`: 2x2 grid ready for user selection
*   `GENERATING_VIDEO`: Celery worker is synthesizing video
*   `VIDEO_READY`: Final MP4 is available
*   `FAILED`: Task failed

---

## 4. API Endpoints (FastAPI)

### A. Prompt Refinement (Synchronous)
*   **POST** `/api/v1/projects/{project_id}/refine-prompt`
*   **Payload**: `{ "regenerate": bool, "gemini_model": "string" }`
*   **Action**: Calls Gemini API synchronously with an advanced prompt engineer system prompt.
*   **Response**: Returns `{ "refined_prompt": "...", "image_prompt": "...", "motion_prompt": "..." }`. (< 2 seconds)

### B. Image Generation (Asynchronous)
*   **POST** `/api/v1/projects/{project_id}/generate-images`
*   **Payload**: `{ "model": "gemini_imagen3", "prompt": "string" }`
*   **Action**: Enqueues a Celery task. Updates status to `GENERATING_IMAGES`.
*   **Response**: `202 Accepted` with `task_id`.

### C. Video Synthesis (Asynchronous)
*   **POST** `/api/v1/projects/{project_id}/synthesize-video`
*   **Payload**: `{ "model": "gemini_veo2", "image_url": "string", "prompt": "string" }`
*   **Action**: Enqueues a Celery task. Updates status to `GENERATING_VIDEO`.
*   **Response**: `202 Accepted` with `task_id`.

### D. Status Polling
*   **GET** `/api/v1/projects/{project_id}/status`
*   **Action**: Queries DB for current status and URLs.
*   **Response**: Returns current state of the project. Frontend polls this every 3-5 seconds when a task is running.

---

## 5. Background Task Flow (Celery)

Since Image and Video APIs can take anywhere from 5 to 120 seconds, we cannot hold the HTTP connection open.

**Video Task Example:**
1. User clicks "Generate Video".
2. Next.js calls FastAPI `POST /synthesize-video`.
3. FastAPI pushes a message to Redis queue.
4. FastAPI immediately returns `202 Accepted`. Next.js starts polling the `GET /status` endpoint.
5. Celery Worker picks up the message from Redis.
6. Worker sends POST request to Kling 2.5 / Minimax.
7. Worker waits for external API to complete (via internal polling or webhook).
8. External API finishes, Worker downloads MP4.
9. Worker uploads MP4 to Supabase Storage.
10. Worker updates `projects` row: `status = VIDEO_READY`, `final_video_url = <supabase_url>`.
11. Next.js polling loop detects `VIDEO_READY` and displays the video to the user.

---

## 6. Security & Environment Variables

**Required Environment Variables:**
*   **Supabase**: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (and `NEXT_PUBLIC_SUPABASE_ANON_KEY` for frontend)
*   **Redis**: `REDIS_URL`
*   **AI APIs**:
    *   `GEMINI_API_KEY`: Used for Gemini Text (Prompt refinement), Gemini Image Generation (Imagen 3), and Gemini Video Generation (Veo 3.1).
    *   `FREEPIK_API_KEY`: Used for Freepik Mystic (Image) and Freepik Video (Kling / Minimax / Video).

*Security Note: All 3rd party AI API calls happen from the FastAPI/Celery backend. The Next.js frontend never sees these API keys.*
