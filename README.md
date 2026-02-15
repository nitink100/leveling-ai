
# Leveling AI — Make promotions concrete (Founding Engineer Interview Project)

A prototype web app where a manager can upload a **role leveling guide (PDF)** + provide a **company website**, and the system generates **3 concrete examples per cell** in the leveling matrix so direct reports can understand what “operating at that level” actually looks like.

This repo is intentionally designed as a **fast, explainable pipeline**:
- **Frontend-forward UX**: results render in the browser (no downloads)
- **< 1 minute perceived latency**: async pipeline + status polling
- **Future-friendly data modeling**: structured storage for later email generation, regeneration, and querying by company/role/level

---

## What is a “leveling guide”?
A **leveling guide** (also called a **career ladder** or **promotion rubric**) is typically a matrix that describes expectations across levels (e.g., L1 → L5).

- **Rows = competencies** (Execution, Communication, Technical Design, Leadership, etc.)
- **Columns = levels** (Junior → Senior → Staff)
- **Each cell = definition** of what that competency looks like at that level

The problem: these definitions are often generic (“drives alignment”, “delivers impact”). Direct reports ask:
**“What specifically do I need to do?”**

This app answers that by generating **3 concrete examples per cell**, turning vague criteria into actionable behaviors.

---

## What you can do in the app
1. Login (simple prototype auth)
2. Enter:
   - Company website URL
   - Role title
   - Upload leveling guide PDF
3. The app shows progress (queued → extracting → parsing → generating)
4. The app renders the completed matrix:
   - Level columns (L1/L2/…)
   - Competency rows (Communication, Execution, etc.)
   - Each cell: original definition + **3 AI-generated examples**

---

## Tech stack (why these choices)

### Frontend
- **Next.js (React)** UI
- Calls backend APIs with a bearer token
- Polls `/status` until the pipeline completes, then loads `/results`

### Backend
- **FastAPI** (thin routers, thick services)
- **Celery + Redis** for async pipeline orchestration (fast API response, heavy work in background)
- **Postgres (Supabase)** for structured storage and future querying
- **Supabase Storage** for storing PDFs privately + serving signed URLs
- **Gemini (google-genai)** for structured matrix parsing + example generation
- PDF extraction utilities (`pypdf`, `pdfplumber`, `PyMuPDF/fitz`) + quality scoring and fallback strategy

**Design goal:** Clean separation of concerns:
- Routers: request/response, auth, validation
- Services: orchestration + status transitions
- Repos: DB access patterns
- Tasks: async pipeline stages
- Models: schema built for future access patterns (email generation, regeneration, analytics)

---

## System architecture (high level)

```mermaid
flowchart LR
  A[Next.js UI] -->|"POST /auth/login"| B[FastAPI]
  A -->|"POST /api/guides (multipart: pdf + fields)"| B

  B -->|Store metadata| D[(Postgres - Supabase)]
  B -->|"Upload PDF (private)"| E[Supabase Storage]
  B -->|enqueue| C[Redis Broker]
  C --> F[Celery Worker]

  F -->|"Phase 2: extract text"| D
  F -->|"Phase 3: parse matrix"| D
  F -->|"Phase 4: generate examples"| D

  A -->|"poll GET /api/guides/:id/status"| B
  A -->|"GET /api/guides/:id/results"| B
  B --> D
````

---

## Pipeline (how results are generated quickly)

When you upload, the backend immediately:

1. Validates inputs (URL, role title, PDF)
2. Creates/updates a `Company` record (keyed by website URL)
3. Uploads the PDF to **private** Supabase Storage
4. Creates a `LevelingGuide` row with `status=QUEUED`
5. Enqueues the async pipeline:

   * **Phase 2**: Extract PDF text + compute extraction quality signals
   * **Phase 3**: Parse matrix structure (levels, competencies, cell definitions)
   * **Phase 4**: Generate 3 examples per cell (idempotent per `prompt_version`)

The frontend polls status and then fetches results when complete.

### Status model (simplified)

The guide progresses through statuses like:

* `QUEUED`
* `EXTRACTING_TEXT` → `TEXT_EXTRACTED` (or `FAILED_BAD_PDF`)
* `PARSING_MATRIX` → `MATRIX_PARSED` (or `FAILED_PARSE`)
* `GENERATING_EXAMPLES` → `COMPLETE` (or `FAILED_GENERATION`)

---

## Data model (built for future access patterns)

This prototype stores *everything needed* for later email generation + querying:

* `companies`

  * `website_url` unique key (+ optional name/context)
* `leveling_guides`

  * role title, PDF path, status, errors, timestamps
  * indexed for polling + filtering by company
* `guide_artifacts`

  * extracted text, chunks, parsed JSON artifacts
* `levels`

  * columns in the leveling grid (L1/L2/…)
* `competencies`

  * rows in the leveling grid
* `guide_cells`

  * each competency×level cell + original definition text
* `cell_generations`

  * generated examples per cell, keyed by (cell_id, prompt_name, prompt_version)
  * supports regeneration and quality evaluation over time
* `parse_runs`

  * tracks parse attempts, strategy, confidence, prompt/model used

This gives clean access patterns for:

* “Send an email summary for guide X”
* “Show all examples for competency Y across levels”
* “Regenerate v2 prompts but keep v1 history”
* “Compare results across companies/roles”

---

## Async backend design (status-driven pipeline, background workers, and scale)

A core goal of this project was **fast UX** while still doing heavyweight work (PDF extraction + structured parsing + LLM generation). The backend is built as a **status-driven async pipeline** so the upload request returns quickly and the expensive steps run reliably in the background.

### Why async?

* PDF extraction + LLM calls can take seconds and occasionally retry
* Avoid a single long HTTP request (timeouts, poor UX)
* Scale later by adding workers horizontally (e.g., bursts like 100 uploads/sec)

### The pattern: “Create record → enqueue job → poll status → fetch results”

#### 1) Upload endpoint returns fast

`POST /api/guides` does only minimal synchronous work:

* Validate inputs (URL, PDF mime/type/size, role title)
* Create/lookup `Company`
* Upload PDF to **private** storage and store `pdf_path`
* Create `LevelingGuide` row with `status=QUEUED`
* Enqueue background workflow (Celery)
* Return `{ guide_id, status }` immediately

#### 2) Status is the source of truth

`leveling_guides.status` acts like a lightweight state machine. Workers update it at each stage so:

* UI can show progress clearly
* Failures are visible and diagnosable
* Retries/resumes are possible
* Operators can inspect what’s happening in production

#### 3) Background workers do the heavy lifting

Celery workers (Redis broker) execute the pipeline stages:

* Read guide metadata + artifacts from DB
* Perform one stage (extract / parse / generate)
* Persist outputs back to DB
* Update the guide `status`

### Reliability choices (prototype-grade but scalable)

* **At-least-once task execution** with Celery:

  * `acks_late=True` (ack only after completion)
  * `worker_prefetch_multiplier=1` (fair load distribution)
  * `task_reject_on_worker_lost=True` (re-queue on worker crash)
* **Idempotent writes**:

  * `cell_generations` keyed by `(cell_id, prompt_name, prompt_version)` to prevent duplicates and enable regeneration/versioning.

### How this scales cleanly

This design scales primarily by **adding worker capacity**, not by making the API server heavier:

* API servers: stateless, scale horizontally
* Workers: scale horizontally by increasing replicas
* Optional queue separation by stage (extract / parse / generate) to tune compute for bottlenecks

---

# Local setup (run frontend + backend)

## Prereqs

* Node 18+
* Python 3.11+
* Redis (local or hosted)
* Postgres (recommended: Supabase Postgres)
* A Supabase project with:

  * Postgres database
  * Storage bucket (default: `leveling-guides`)
* Gemini API key (Google GenAI)

---

## Default login (prototype)

* Username: `admin`
* Password: `admin`

You can change these via env vars:

* `ADMIN_USERNAME`
* `ADMIN_PASSWORD`

---

## 1) Backend setup (FastAPI + Celery)

### Install Python deps

If your repo has a `requirements.txt`, use it. Otherwise, this is the minimal set implied by the code:

```bash
pip install fastapi uvicorn celery redis python-dotenv \
  sqlalchemy psycopg2-binary pydantic pydantic-settings \
  supabase httpx python-jose[cryptography] \
  pypdf pdfplumber pymupdf google-genai
```

### Create backend `.env` (repo root)

Backend reads env from `./.env` (see `app/core/config.py` and `app/celery_app.py`).

```env
# --- Core ---
ENV=local
PROJECT_NAME=LevelingAI

# --- Database (Supabase Postgres recommended) ---
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:5432/DBNAME

# --- Redis (Celery broker) ---
REDIS_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# --- Supabase ---
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY
SUPABASE_STORAGE_BUCKET=leveling-guides
SUPABASE_STORAGE_SIGNED_URL_TTL_SECONDS=3600

# --- Auth (prototype admin login) ---
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin
JWT_SECRET_KEY=change-me
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRES_MINUTES=60

# --- LLM (Gemini) ---
LLM_PROVIDER=gemini
GEMINI_API_KEY=YOUR_GEMINI_KEY
GEMINI_MODEL=gemini-1.5-pro

# --- Runtime tuning ---
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=2
LLM_MAX_OUTPUT_TOKENS=800
LLM_TEMPERATURE=0.4
LLM_LOG_PROMPTS=false

# --- CORS ---
CORS_ALLOW_ORIGINS=http://localhost:3000
```

### Database bootstrap (tables)

This prototype doesn’t ship migrations. Create tables in Supabase using SQL editor (schema aligned to `app/models/*`).
(Use the SQL bootstrap you already have in this README.)

### Run the backend API

```bash
uvicorn app.main:app --reload --port 8000
```

### Run the Celery worker (required)

In another terminal:

```bash
celery -A app.celery_app.celery_app worker -l info \
  -Q extract_q,parse_q,generate_q
```

> Redis must be running for Celery (`REDIS_BROKER_URL`). Cloud Redis works the same.

---

## 2) Frontend setup (Next.js)

### Frontend env

Create `frontend/.env.local` (or `.env.local` if Next.js lives at repo root):

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### Install + run

```bash
npm install
npm run dev
```

Open: `http://localhost:3000`

---

# How frontend ↔ backend integrate (API contract)

### Auth

* `POST /auth/login`

  * body: `{ "username": "...", "password": "..." }`
  * returns: `{ access_token, token_type, expires_in_minutes }`

Frontend stores the token and sends:
`Authorization: Bearer <token>`

### Upload

* `POST /api/guides`

  * multipart form-data:

    * `website_url` (string)
    * `role_title` (string)
    * `pdf` (file)
    * optional: `company_name`, `company_context`
  * returns: `{ guide_id, status, created_at, ... }`
  * immediately enqueues async pipeline

### Status polling

* `GET /api/guides/:guide_id/status`

  * returns status + timestamps
  * frontend polls until completion

### Results

* `GET /api/guides/:guide_id/results?prompt_version=v1`

  * returns the full matrix (levels, competencies, definitions, examples)

---

# Deployment

## Frontend (Vercel)

1. Import the repo into Vercel
2. Set:

   * `NEXT_PUBLIC_API_BASE_URL = https://<your-backend-domain>`
3. Deploy
4. Add the Vercel URL to GitHub “About → Website”

## Backend (Railway or Fly.io)

The backend needs:

* Postgres (Supabase recommended)
* Redis (local or cloud, e.g., Upstash/Redis Cloud)
* Supabase Storage bucket
* Gemini API key

### Railway (typical)

Deploy two services from the same repo:

1. **API service**

* Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

2. **Worker service**

* Start command:

```bash
celery -A app.celery_app.celery_app worker -l info
```

Make sure both services share the same env vars (`DATABASE_URL`, `REDIS_BROKER_URL`, `SUPABASE_*`, `GEMINI_*`).

### Fly.io (typical)

* Deploy FastAPI as one app/process
* Deploy Celery worker as a second app/process (or a process group)
* Use a managed Redis and shared DB env vars across both

---

# Troubleshooting

### “Upload works but status never changes”

* Worker isn’t running, or Redis broker URL is wrong.
* Check:

  * `REDIS_BROKER_URL`
  * Celery worker logs

### “DB errors”

* `DATABASE_URL` wrong or tables not created.
* Ensure Supabase credentials allow access.

### “Gemini errors”

* Missing/invalid `GEMINI_API_KEY`
* Confirm `GEMINI_MODEL` is valid for your account

---

# If I had more time (1–4 sentences)

I’d add Alembic migrations + multi-user auth, implement job observability (trace IDs, retries surfaced in UI), add an evaluation harness for LLM outputs (schema validation + rubric scoring), and containerize with Docker Compose for one-command local setup and smoother deployments.
