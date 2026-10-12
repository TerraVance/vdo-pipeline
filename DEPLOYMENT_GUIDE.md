# 🚀 Complete Production Deployment Guide

This guide covers everything required to deploy the **Interactive AI Video / Image Generation Pipeline** to production and make it live on the internet.

---

## 🏛️ System Architecture Overview

Before deploying, understand the 5 interconnected components:

```mermaid
graph TD
    User([End User Browser]) -->|HTTPS / Next.js UI| Vercel[Frontend: Vercel / Next.js]
    Vercel -->|REST API Requests| FastAPI[Backend: FastAPI Web Service]
    Vercel -->|Auth & Realtime| SupabaseDB[(Supabase: PostgreSQL & Auth)]
    
    FastAPI -->|Enqueue Tasks| Redis[(Redis: Task Broker)]
    FastAPI -->|Direct Queries / CRUD| SupabaseDB
    FastAPI -->|Prompt Refinement| GeminiAPI[Google Gemini API]
    
    CeleryWorker[Worker: Celery Background Worker] -->|Poll & Consume Tasks| Redis
    CeleryWorker -->|Image Gen: Imagen 3| GeminiAPI
    CeleryWorker -->|Image Gen: Mystic| FreepikAPI[Freepik API]
    CeleryWorker -->|Upload Generated Images| SupabaseStorage[Supabase Storage: media bucket]
    CeleryWorker -->|Update Status / URLs| SupabaseDB
```

---

## 📋 Recommended Deployment Stack

| Component | Recommended Platform | Why | Cost / Tier |
|---|---|---|---|
| **Frontend** | [Vercel](https://vercel.com) | Native Next.js 16 support, global CDN, instant HTTPS | Free / $20 Pro |
| **Backend API** | [Render](https://render.com) or [Railway](https://railway.app) | Zero-maintenance container / Python Web Service | Free / $7 Starter |
| **Celery Worker** | [Render](https://render.com) or [Railway](https://railway.app) | Dedicated background worker with autoscaling | $7 Starter |
| **Redis Broker** | [Upstash](https://upstash.com) or Render Redis | Serverless managed Redis with TLS (`rediss://`) | Free / $3+ |
| **Database & Storage** | [Supabase](https://supabase.com) | Managed Postgres, Auth, S3-compatible Storage | Free / $25 Pro |
| **AI Providers** | Google Cloud / Freepik | Gemini & Mystic APIs | Pay-as-you-go |

---

## Phase 1: Supabase Setup (Database & Storage)

### 1.1 Create Supabase Project
1. Log in to [Supabase](https://supabase.com) and click **New project**.
2. Note your **Database Password** and select your closest AWS region.

### 1.2 Run Database Migrations
1. Open the **SQL Editor** in your Supabase project dashboard.
2. Open [`supabase/schema.sql`](./supabase/schema.sql) from this repository.
3. Paste the entire content into the SQL Editor and click **Run**.
4. Confirm tables are created: `projects`, `messages`, `conversations`, `style_presets`.

### 1.3 Create Public Media Storage Bucket (CRITICAL)
1. Go to **Storage** in the left sidebar of the Supabase dashboard.
2. Click **New bucket**.
3. Name the bucket **exactly**: `media`.
4. **Important**: Toggle **Public bucket** to **ON**.
   > If the bucket is not public, generated images cannot be displayed by user browsers.
5. Click **Save bucket**.

### 1.4 Retrieve Supabase Credentials
Go to **Project Settings → API** and copy:
- **Project URL** (`https://xyzcompany.supabase.co`)
- **anon public key** (`eyJhbGci...`)
- **service_role key** (`eyJhbGci...`)
- **JWT Secret** (Under Settings → API → JWT Settings)

---

## Phase 2: Redis Provisioning (Message Broker)

Celery requires a reliable Redis broker for dispatching asynchronous image generation tasks.

### Option A: Upstash Redis (Recommended — Serverless & Free)
1. Sign up at [Upstash](https://upstash.com).
2. Click **Create Database**.
3. Select **Redis**, choose your primary region, and click **Create**.
4. In the database details, scroll to **Connect your database**.
5. Select the **redis-py / Celery** tab and copy the `rediss://...` connection string:
   ```
   rediss://default:YOUR_PASSWORD@your-endpoint.upstash.io:6379
   ```

### Option B: Render or Railway Redis
If you prefer keeping everything inside Render or Railway, simply provision a Redis instance from their dashboard:
- In Render: Click **New + → Redis**.
- In Railway: Click **New + → Database → Add Redis**.

---

## Phase 3: Deploy Backend & Celery Worker on Render

We have provided a native `render.yaml` blueprint in this repo. You can deploy both the API and Worker in 1 click or manually.

### 3.1 Method A: 1-Click Blueprint Deploy
1. Push your repository to GitHub.
2. Go to [Render Dashboard](https://dashboard.render.com).
3. Click **New + → Blueprint**.
4. Select your GitHub repository (`vdo-pipeline`).
5. Render will automatically detect [`render.yaml`](./render.yaml) and configure:
   - `vdo-backend-api` (FastAPI Web Service)
   - `vdo-celery-worker` (Background Worker)
   - `vdo-redis` (Managed Redis)
6. Fill in the prompted secret environment variables (see table below).
7. Click **Apply**.

---

### 3.2 Method B: Manual Step-by-Step Configuration on Render

If you prefer setting up services individually:

#### Step 1: Create FastAPI Web Service
1. Click **New + → Web Service**.
2. Connect your GitHub repository.
3. Configure the service:
   - **Name**: `vdo-backend-api`
   - **Language / Runtime**: `Python`
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path**: `/api/v1/health`
4. Add Environment Variables (see Section 3.3).
5. Click **Create Web Service**.
6. Once deployed, copy your backend URL: e.g. `https://vdo-backend-api.onrender.com`.

#### Step 2: Create Celery Background Worker
1. Click **New + → Background Worker**.
2. Connect the same GitHub repository.
3. Configure the worker:
   - **Name**: `vdo-celery-worker`
   - **Language / Runtime**: `Python`
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `celery -A app.core.celery_app worker --loglevel=info --concurrency=4`
4. Add the exact same Environment Variables as the Web Service.
5. Click **Create Background Worker**.

---

### 3.3 Backend & Worker Environment Variables Table

Set these variables in **both** the Web Service and the Background Worker:

| Variable | Description | Example |
|---|---|---|
| `PYTHON_VERSION` | Python runtime version | `3.11.9` |
| `SUPABASE_URL` | Supabase Project URL | `https://xxxx.supabase.co` |
| `SUPABASE_ANON_KEY` | Supabase anon public key | `eyJhbGciOi...` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service_role secret key | `eyJhbGciOi...` |
| `SUPABASE_JWT_SECRET` | Supabase JWT Secret | `super-secret-jwt-key` |
| `DATABASE_URL` | Supabase Direct Postgres URI | `postgresql://postgres:...@db...` |
| `REDIS_URL` | Redis connection URL | `rediss://default:...@upstash.io:6379` |
| `GEMINI_API_KEY` | Google Gemini API Key | `AIzaSy...` |
| `FREEPIK_API_KEY` | Freepik Mystic API Key | `FPSX...` |
| `ALLOWED_ORIGINS` | Extra allowed CORS origins (optional) | `https://yourdomain.com` |

---

## Phase 4: Deploy Next.js Frontend on Vercel

Vercel provides zero-configuration deployment for Next.js with global CDN caching and edge optimization.

### 4.1 Connect to Vercel
1. Log in to [Vercel](https://vercel.com).
2. Click **Add New... → Project**.
3. Import your GitHub repository (`vdo-pipeline`).

### 4.2 Configure Build & Root Directory
1. In the **Project Configuration** screen:
   - **Framework Preset**: `Next.js`
   - **Root Directory**: Click **Edit** and choose `frontend`.
2. Leave Build Command and Output Directory as default (`next build`).

### 4.3 Configure Frontend Environment Variables
Expand **Environment Variables** and add:

| Variable | Value | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `https://vdo-backend-api.onrender.com` | Your live Render backend URL (no trailing slash) |
| `NEXT_PUBLIC_SUPABASE_URL` | `https://xxxx.supabase.co` | Same as backend |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `eyJhbGciOi...` | Same as backend |

### 4.4 Deploy
1. Click **Deploy**.
2. Vercel will build the Next.js app in ~60 seconds.
3. You will receive a live URL: `https://vdo-pipeline.vercel.app` (or custom domain).

---

## Phase 5: Alternative Full-Stack Single-Server Deployment (Docker Compose)

If you want to run everything on a single virtual private server (e.g., **AWS EC2**, **DigitalOcean Droplet**, or **Hetzner**) for ~$5–$10/month:

### 5.1 Server Setup (Ubuntu 22.04 / 24.04)
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker & Docker Compose
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
```

### 5.2 Clone Repository & Configure Environment
```bash
git clone https://github.com/TerraVance/vdo-pipeline.git
cd vdo-pipeline

# Create root .env file from template
cp .env.example .env
nano .env  # Fill in SUPABASE_URL, GEMINI_API_KEY, FREEPIK_API_KEY, etc.
```

### 5.3 Launch Entire Stack
```bash
docker compose up -d --build
```
This starts:
- Redis on port `6379`
- FastAPI on port `8001`
- Celery worker (4 concurrent processes)
- Next.js frontend on port `3000`

### 5.4 Setup Automatic SSL with Caddy (Reverse Proxy)
Install Caddy to handle SSL certificates automatically:
```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```

Create `/etc/caddy/Caddyfile`:
```caddy
app.yourdomain.com {
    reverse_proxy localhost:3000
}

api.yourdomain.com {
    reverse_proxy localhost:8001
}
```

Restart Caddy:
```bash
sudo systemctl restart caddy
```

---

## Phase 6: Live Pre-Flight Verification Checklist

Run these 5 checks immediately after deployment to guarantee 100% operation:

### ✅ 1. API Health & Database Ping
Open in browser or run curl:
```bash
curl -I https://<YOUR_BACKEND_URL>/api/v1/health
# Expect: HTTP/2 200 {"status": "ok"}

curl https://<YOUR_BACKEND_URL>/api/v1/health/db
# Expect: {"status": "ok", "supabase": "connected"}
```

### ✅ 2. Swagger Interactive Docs
Navigate to:
```
https://<YOUR_BACKEND_URL>/docs
```
Confirm all endpoints are listed:
- `/api/v1/projects/...`
- `/api/v1/chat/...`
- `/api/v1/images/...`

### ✅ 3. Test Prompt Refinement (Step 2)
On the live frontend (`https://<YOUR_FRONTEND_URL>/studio`):
1. Type a prompt: `A cinematic neon cybernetic tiger walking in rainy Tokyo night`.
2. Click **Refine Prompt**.
3. Verify Gemini returns the parsed `image_prompt` and full production script.

### ✅ 4. Test Asynchronous Image Generation (Step 3)
1. Select an image model (e.g. `Gemini Imagen 3` or `Freepik Mystic Photo`).
2. Select an aspect ratio (e.g. `16:9`).
3. Click **Generate Images**.
4. Check Celery worker logs in Render/Railway:
   ```
   [Task ...] Starting generate_images_task for project=...
   [GeminiImageProvider] image[0] generated successfully
   [Task ...] Completed generate_images_task (... 4 images)
   ```
5. Check that all 4 images appear on the UI and load cleanly from Supabase CDN.

### ✅ 5. Test Chat / Studio Message Deletion
1. In the studio sidebar, create a new chat or generate in chat.
2. Delete the chat.
3. Confirm that the chat messages and associated images in Supabase Storage are completely purged.

---

## Phase 7: Production Operations & Maintenance

### 1. Zero-Downtime Worker Restarts
When redeploying the Celery worker, use warm shutdown:
```bash
celery -A app.core.celery_app worker --loglevel=info -Ofair
```
Celery will finish any currently generating image tasks before gracefully restarting.

### 2. Monitoring Celery Tasks
To inspect worker throughput or tasks in flight:
```bash
celery -A app.core.celery_app inspect active
celery -A app.core.celery_app inspect stats
```

### 3. Scaling Workers
As user traffic increases:
- **Vertical scaling**: Increase Celery `--concurrency` parameter (`--concurrency=8` or `16`).
- **Horizontal scaling**: Increase the instance count of `vdo-celery-worker` in Render or Railway. Multiple workers will automatically coordinate and share tasks through Redis with zero configuration.

### 4. AI Provider Quotas & Circuit Breakers
The codebase includes automatic circuit breakers:
- If Gemini hits `429 RESOURCE_EXHAUSTED`, the system automatically routes to Freepik Mystic without hanging or failing requests.
- All errors are logged with structured logs in `backend/app/core/logging.py`.
