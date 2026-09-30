# **Product Requirements Document (PRD): Interactive AI Video Generation Pipeline**

## **1. Product Overview**
The Interactive AI Video Generation Pipeline is a web-based SaaS application designed to transform simple text concepts into high-quality, fully realized videos. Unlike monolithic text-to-video tools that generate black-box results, this platform introduces a granular, **Human-in-the-Loop (HITL)** wizard architecture.
Users retain complete creative control at every critical milestone—prompt expansion, image generation, and video synthesis. By enforcing checkpoint validation, the application minimizes credit burn and ensures the final video matches the user's precise vision.

## **2. Target Audience**
The platform serves creators who require high-production visual media without the traditional learning curve of prompt engineering or video editing suites:
  - **Content Creators & Social Media Managers:** Need rapid, engaging video assets for TikTok, Instagram Reels, and YouTube Shorts.
  - **Digital Marketers & Agencies:** Requiring fast iteration on video ad variants, storyboards, and campaign concepts.
  - **Educators & Course Creators:** Looking to generate visual aids, narrative scenes, or dynamic explainer footage without stock video subscriptions.

## **3. Core Features & User Flow**
The core user experience is structured around a sequential 4-step stateful wizard. Users can advance forward upon approval or step backward to make modifications without losing session state.

### **Step 1: Idea Input**
  - **Interface:** Clean, focused landing page featuring a primary text entry box and optional style tag selectors (e.g., *Cinematic, Cyberpunk, Photorealistic, Anime*).
  - **Functionality:** Captures the raw conceptual input from the user (e.g., *"A neon-lit cyberpunk alleyway at night with rain reflecting off the asphalt"*).
  - **Action:** Clicking **"Initialize Pipeline"** triggers the payload creation and navigates to Step 2.

### **Step 2: Prompt Refinement**
  - **Interface:** Side-by-side comparison panel showing the original input versus the AI-expanded prompt.
  - **Functionality:** The system passes the raw input to the **Gemini API** (with a fallback to a Playwright-managed web automation worker) to build a rich, detailed production prompt including lighting, camera angles, textures, and mood details.
  - **User Actions:**
      - **Manual Edit:** Users can directly modify the expanded text in an editable text field.
      - **Regenerate:** Request a new prompt expansion using alternate system instructions.
      - **Proceed:** Approve prompt and send request to Step 3.

### **Step 3: Visual Generation**
  - **Interface:** Interactive 2x2 grid displaying generated static image options.
  - **Functionality:** Calls the image generation models (**Google Flow**, **Nano Banana Pro**, **Nano Banana 2**, **Gemini**, or **Freepik Magnific**) to render 2–4 candidate frame variations based on the refined prompt.
  - **User Actions:**
      - **Select:** Choose a primary frame to serve as the baseline seed for video generation.
      - **Iterate Prompt:** Adjust text modifiers and re-trigger visual generation.
      - **Backtrack:** Return to Step 2 to fundamentally alter the core prompt structure.

### **Step 4: Video Synthesis**
  - **Interface:** Video player featuring playback controls, resolution toggles, direct download options, and export format selections.
  - **Functionality:** Sends the selected image frame and generation parameters to advanced video engines (**Kling 2.5**, **Minimax Hailuo Fast 2.3 Fast**, **Gemini**, or **Freepik** at **720p** resolution).
  - **User Actions:**
      - **Preview & Export:** Render final MP4 asset.
      - **Backtrack:** Revert to Step 3 to pick a different image frame if motion artifacts occur.

---

### **Step-by-Step State & Action Summary**

| Step | Focus Area | Inputs | Processing Engine | User Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| **01** | **Idea Input** | Raw Text, Style Tags | Client Input Processing | Submit draft concept |
| **02** | **Prompt Refinement** | Raw Concept | Gemini API / Playwright Fallback | Edit expanded text, regenerate prompt |
| **03** | **Visual Generation** | Refined Prompt | Google Flow / Nano Banana / Gemini / Freepik | Select 1 of 4 images, refine prompt, step back |
| **04** | **Video Synthesis** | Seed Image + Prompt | Kling 2.5 / Minimax / Gemini / Freepik (720p) | Download MP4, step back to re-frame |

---

## **4. System Architecture & Tech Stack**
The platform uses a decoupled client-server model designed for asynchronous handling of long-running generation tasks.

```text
+-----------------------------------------------------------------------+
|                            FRONTEND                                   |
|                Next.js / React (Hosted on Vercel)                     |
|           Stateful Stepper UI & Real-Time Status Polling              |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                            BACKEND                                    |
|               FastAPI (Python) (Hosted on Render)                     |
|              Modular REST Endpoints & Orchestration                   |
+-----------------------------------------------------------------------+
        |                          |                          |
        v                          v                          v
+---------------+          +---------------+          +-----------------+
|   DATABASE    |          |  JOB QUEUE    |          |  EXTERNAL APIs  |
|  Supabase     |          | Redis + Bull  |          |  - Gemini API   |
| (PostgreSQL)  |          | Celery Workers|          |  - Google Flow  |
| Session State |          | Background    |          |  - Nano Banana  |
| Job Statuses  |          | Render Tasks  |          |  - Freepik      |
|               |          |               |          |  - Kling/Minimax|
+---------------+          +---------------+          +-----------------+
```

### **Technology Matrix**
  - **Frontend Framework:** **Next.js** (React) deployed on **Vercel**. Manages stateful stepper transitions, local draft persistence, and progress polling hooks.
  - **Backend Framework:** **FastAPI (Python)** or **Node.js** hosted on **Render**. Exposes modular endpoints (`/api/prompt/refine`, `/api/image/generate`, `/api/video/synthesize`).
  - **Database & Storage:** **Supabase (PostgreSQL)** for session state, media metadata, and pipeline execution logs.
      - *Pipeline State Values:* `DRAFT`, `PROMPT_REFINED`, `IMAGES_GENERATED`, `VIDEO_GENERATED`, `FAILED`
  - **Task Engine:** **Redis + Celery (or BullMQ)** to handle async video processing tasks and prevent HTTP timeout errors during long video renders.
  - **API Integrations:**
      - *LLM:* Gemini API (Primary text expansion engine).
      - *Image:* Google Flow, Nano Banana Pro, Nano Banana 2, Gemini, Freepik Magnific.
      - *Video:* Kling 2.5, Minimax Hailuo Fast 2.3 Fast, Gemini, Freepik (720p resolution).

## **5. Non-Functional Requirements**
  - **Performance & Asynchrony:**
      - Text and Image requests must complete under 10 seconds.
      - Video synthesis must run via background jobs with a maximum completion threshold of 120 seconds.
      - Frontend must use optimistic UI updates and polling intervals (every 3–5s) for active rendering tasks.
  - **Security:**
      - Third-party API credentials must be secured in environment variables (`.env`) and managed via server-side key vaults.
      - All user sessions must be isolated in Supabase with Row Level Security (RLS) enabled.
  - **Usability & Feedback:**
      - Clear visual loading indicators, progress percentages, and animated skeleton screens at each stage.
      - In-line error handling with action-oriented retry messaging (e.g., *"Model timed out. Click to retry image generation."*).

## **6. Future Enhancements**
  - **Automated Voiceovers (TTS):** Integration with ElevenLabs or OpenAI Audio APIs to generate narrative voice tracks based on refined scripts.
  - **Dynamic Audio Layering:** Automatic background music selection aligned with the video's generated mood tags.
  - **Credits & Monetization System:** Stripe-powered billing integration, introducing token/credit usage tracking per video render cycle.
  - **Multi-Scene Storyboarding:** Expanding the single-frame pipeline into a multi-shot sequence editor for longer video projects.