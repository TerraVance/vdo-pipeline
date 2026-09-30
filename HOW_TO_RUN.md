# How to Run the Video Generation Pipeline

This guide provides step-by-step instructions to get the Interactive AI Video Generation Pipeline running on your local machine.

## Prerequisites

Before starting, ensure you have the following installed:
1. **Python 3.9+** (for the backend)
2. **Node.js 18+** (for the frontend)
3. **Docker** (for running Redis locally)
4. **Supabase Account** (or local Supabase CLI setup)

You will also need your API keys:
- **Gemini API Key** (for prompt refinement, Imagen 3, Veo 2)
- **Freepik API Key** (for Mystic Image, AI Video)

---

## Step 1: Supabase Setup

1. Create a new project in your Supabase dashboard.
2. **Database Setup (Migration)**: 
   - Go to the **SQL Editor** in your Supabase dashboard.
   - Copy the contents of [`schema.sql`](./schema.sql) (located in the root of this repository) and run it. This will create the `projects` table and setup Row Level Security (RLS) policies.
3. **Storage (Crucial)**:
   - Go to **Storage** in the Supabase dashboard.
   - Click **New Bucket**.
   - Name the bucket exactly: `media`.
   - **Important:** Set the bucket to **Public**. If you don't do this, image generation will fail because the frontend won't be able to display the generated images.
4. Go to **Project Settings -> API** and copy:
   - `Project URL`
   - `anon public key`
   - `service_role secret` (for backend operations)

---

## Step 2: Backend Setup

Open a terminal and navigate to the `backend` directory:

```bash
cd backend
```

1. **Environment Variables**:
   Copy the example environment file and fill in your keys.
   ```bash
   cp ../.env.example .env
   ```
   Edit `.env` and fill in:
   - Supabase credentials (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`)
   - API Keys (`GEMINI_API_KEY`, `FREEPIK_API_KEY`)
   - Redis URL (default `redis://localhost:6379/0` is fine for local docker)

2. **Python Virtual Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Start Redis**:
   You need Redis running for Celery background tasks.
   ```bash
   docker start vdo-redis

   docker run -d -p 6379:6379 --name vdo-redis redis
   ```

4. **Start the Celery Worker**:
   In the activated virtual environment, start Celery to process image/video generation tasks:
   ```bash
   celery -A app.core.celery_app worker --loglevel=info
   ```

5. **Start the FastAPI Server**:
   Open a *new* terminal, navigate to `backend`, activate the venv, and start Uvicorn:
   ```bash
   cd backend
   source venv/bin/activate
   uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
   ```

---

## Step 3: Frontend Setup

Open a *new* terminal and navigate to the `frontend` directory:

```bash
cd frontend
```

1. **Environment Variables**:
   Create a `.env.local` file:
   ```bash
   cp .env.example .env.local
   ```
   Edit `.env.local` and fill in:
   - `NEXT_PUBLIC_SUPABASE_URL` (Same as backend)
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `NEXT_PUBLIC_API_URL` (Defaults to `http://localhost:8001`)

2. **Install Dependencies**:
   ```bash
   npm install
   ```

3. **Start the Next.js Development Server** (on port 3003):
   ```bash
   npm run dev
   ```

---

## Step 4: Run the App

1. Open your browser and navigate to: **http://localhost:3003**
2. The backend API docs are available at: **http://localhost:8001/docs**
2. You should see the Interactive AI Video Generation Pipeline UI.
3. Start by entering a prompt in **Step 1** and proceed through the steps to test the end-to-end integration!

## Troubleshooting

- **Image Generation Hangs/Fails**: Check the Celery terminal logs. Ensure your `media` bucket in Supabase exists and is public.
- **Backend API Errors**: Check the Uvicorn terminal logs. Ensure your `.env` keys are correct.
- **CORS Issues**: If the frontend cannot communicate with the backend, ensure `NEXT_PUBLIC_API_URL` exactly matches where FastAPI is running (`http://localhost:8001`), and check the CORS settings in `backend/app/main.py`.


Service	URL
🟢 Frontend (Next.js)      	      http://localhost:3003
🟢 Backend (FastAPI)	               http://localhost:8001
🟢 API Docs (Swagger)	            http://localhost:8001/docs
🟢 Celery	running in background
🟢 Redis	vdo-redis container
