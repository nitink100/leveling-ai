
# Leveling AI — “Make promotions concrete” (Founding Engineer Interview Project)

A prototype web app where a manager can upload a **role leveling guide (PDF)** + provide a **company website**, and the system generates **3 concrete examples per cell** in the leveling matrix so direct reports can understand *what “operating at that level” actually looks like*.

This repo is intentionally designed as a **fast, explainable pipeline**:
- **Frontend-forward UX** (results render in the browser, no downloads)
- **< 1 minute perceived latency** (async pipeline + polling)
- **Future-friendly data modeling** (structured storage for later email generation, regeneration, querying by guide/role/level)

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
   - Each cell: original definition + **3 generated examples**

---

## Tech stack (why these choices)

### Frontend
- **Next.js (React)** UI
- Calls backend APIs with a bearer token
- Polls `/status` until pipeline completes, then loads `/results`

### Backend
- **FastAPI** (thin routers, thick services)
- **Celery + Redis** for async pipeline orchestration (fast response to uploads, work happens in background)
- **Postgres (Supabase)** for structured storage and future querying
- **Supabase Storage** for storing PDFs privately + generating signed download URLs
- **Gemini (google-genai)** for structured matrix parsing + example generation
- PDF extraction utilities (`pypdf`, `pdfplumber`, `PyMuPDF/fitz`) + quality scoring and fallback strategy

**Design goal:** Separate concerns cleanly:
- Routers: I/O + auth only
- Services: orchestration + status transitions
- Repos: DB access patterns
- Tasks: async pipeline steps
- Models: schema that supports future access patterns (email generation, regeneration, analytics)

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
   * **Phase 4**: Generate 3 examples per cell (idempotent per prompt_version)

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
- PDF extraction + LLM calls can take seconds and occasionally retry
- We don’t want the user waiting on a single long HTTP request (timeouts, bad UX)
- We want a design that can later handle **bursts (e.g., 100 uploads/sec)** by adding workers horizontally

---

### The pattern: “Create record → enqueue job → poll status → fetch results”

#### 1) Upload endpoint returns fast
When the frontend uploads a guide (`POST /api/guides`), the API does only the **minimal synchronous work**:
- Validate inputs (URL, PDF mime/type/size, role title)
- Create/lookup `Company` (keyed by website URL)
- Upload PDF to **private** storage (Supabase Storage) and store `pdf_path`
- Create `LevelingGuide` DB row with `status=QUEUED`
- Enqueue the background workflow (Celery)
- Return `{ guide_id, status }` immediately

This keeps the upload endpoint consistently fast and predictable.

#### 2) Status is the source of truth
Every guide row has a `status` field that acts like a **state machine**.  
Workers update status at each stage, so:
- UI can show progress clearly
- if something fails, the error is visible
- retries/resumes are possible
- you can operationally inspect what the system is doing

Typical transitions:
- `QUEUED`
- `EXTRACTING_TEXT` → `TEXT_EXTRACTED` (or `FAILED_BAD_PDF`)
- `PARSING_MATRIX` → `MATRIX_PARSED` (or `FAILED_PARSE`)
- `GENERATING_EXAMPLES` → `COMPLETE` (or `FAILED_GENERATION`)

> This status model is intentionally simple but powerful: it supports UI progress, debuggability, retries, and scaling.

#### 3) Background workers do the heavy lifting
We run **Celery workers** backed by **Redis** (broker + optional result backend).  
The pipeline is executed in stages, and each stage:
- reads the guide metadata + artifacts from DB
- performs a specific job
- writes outputs back to structured tables
- updates `status`

This is why results are quick while the UI stays responsive.

---

### How the workers are made safe & reliable (prototype-grade but scalable)

#### At-least-once execution
Celery is configured with reliable delivery semantics:
- **`acks_late=True`**: a task is acknowledged *after* it finishes
- **`worker_prefetch_multiplier=1`**: prevents a worker from reserving many tasks at once (fairer load distribution)
- **`task_reject_on_worker_lost=True`**: if a worker dies mid-task, the broker can re-queue it

This gives good resilience for a pipeline that calls external services (LLM + storage).

#### Idempotent writes + prompt versioning
We write outputs in a structured way:
- extracted text and parsed JSON are stored as artifacts
- generated examples are stored per cell and keyed by `(cell_id, prompt_name, prompt_version)`

So reruns don’t create chaos.
This also unlocks future features:
- regenerate using prompt `v2` while keeping `v1`
- compare quality across versions
- re-run only failed cells

---

### How the frontend uses async safely

The UI does **polling**, which is the simplest and most reliable pattern for prototypes:
1. Upload → receives `guide_id`
2. Poll `GET /api/guides/:id/status`
3. When status reaches `COMPLETE`, call `GET /api/guides/:id/results`

This avoids WebSockets complexity while still providing a good UX and keeping the system easy to reason about.

---

### Scaling story (how this design scales cleanly)

This architecture scales primarily by **adding worker capacity**, not by making the API server heavier.

#### Scaling levers
- **API servers** scale horizontally (stateless)
- **Workers** scale horizontally (add more Celery worker replicas)
- **Queues** can be separated per stage:
  - extraction queue
  - parse queue
  - generation queue

This allows you to allocate resources where the bottleneck is:
- heavy CPU extraction? add extraction workers
- LLM throughput? add generation workers and rate-limit externally

#### How to handle 100 uploads/sec (evolution plan)
If this were pushed hard, the next practical steps are:
- Add **rate limiting** per user / per IP at the API layer
- Add **task concurrency controls** per queue and per worker pool
- Add **deduplication / job coalescing** (same PDF uploaded twice)
- Use a managed queue (SQS/PubSub) if Redis becomes a bottleneck
- Use autoscaling (K8s HPA) based on queue depth + latency metrics

---

### Operational clarity (debuggability)
Because status + artifacts are stored:
- you can inspect a guide and see exactly where it is stuck
- you can see extraction quality signals
- you can replay pipeline steps
- errors become actionable (bad PDF vs parse failure vs LLM failure)

This is one of the biggest wins of the status-driven async design: **it behaves like a product system even though it’s a prototype**.

---

# Local setup (run frontend + backend)

## Prereqs

* Node 18+
* Python 3.11+
* Redis (local or hosted)
* Postgres (recommended: Supabase Postgres)
* A Supabase project with:

  * Postgres database
  * Storage bucket (default used: `leveling-guides`)
* Gemini API key (Google GenAI)

---

## 1) Backend setup (FastAPI + Celery)

### Install Python deps

If your repo has a requirements file, use it. If not, this is the minimum set implied by the code:

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
# optional (defaults to broker)
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

This project is a prototype and does not ship migrations in this zip.
Create tables in Supabase using SQL editor (minimal schema aligned to `app/models/*`):

```sql
-- Enable UUID generation (Supabase typically has pgcrypto enabled)
create extension if not exists pgcrypto;

create table if not exists companies (
  id uuid primary key default gen_random_uuid(),
  website_url text not null unique,
  name text null,
  context text null,
  created_at timestamp not null default now()
);

create table if not exists leveling_guides (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  role_title text null,
  original_filename text null,
  mime_type text null,
  pdf_path text not null,
  status varchar(32) not null default 'QUEUED',
  error_message text null,
  created_at timestamp not null default now(),
  updated_at timestamp not null default now()
);

create index if not exists ix_leveling_guides_company_id on leveling_guides(company_id);
create index if not exists ix_leveling_guides_status_created_at on leveling_guides(status, created_at);

create table if not exists guide_artifacts (
  id uuid primary key default gen_random_uuid(),
  guide_id uuid not null references leveling_guides(id) on delete cascade,
  type varchar(64) not null,
  content_text text null,
  content_json jsonb null,
  created_at timestamp not null default now()
);

create table if not exists parse_runs (
  id uuid primary key default gen_random_uuid(),
  guide_id uuid not null references leveling_guides(id) on delete cascade,
  strategy varchar(32) not null,
  status varchar(16) not null,
  confidence float null,
  model text null,
  prompt_version varchar(32) null,
  input_artifact_id uuid null references guide_artifacts(id),
  output_artifact_id uuid null references guide_artifacts(id),
  error_message text null,
  created_at timestamp not null default now()
);

create table if not exists levels (
  id uuid primary key default gen_random_uuid(),
  guide_id uuid not null references leveling_guides(id) on delete cascade,
  code varchar(64) not null,
  title text null,
  position int not null default 0,
  created_at timestamp not null default now(),
  constraint uq_levels_guide_code unique (guide_id, code)
);

create index if not exists ix_levels_guide_position on levels(guide_id, position);

create table if not exists competencies (
  id uuid primary key default gen_random_uuid(),
  guide_id uuid not null references leveling_guides(id) on delete cascade,
  name text not null,
  position int not null default 0,
  created_at timestamp not null default now(),
  constraint uq_competencies_guide_name unique (guide_id, name)
);

create index if not exists ix_competencies_guide_position on competencies(guide_id, position);

create table if not exists guide_cells (
  id uuid primary key default gen_random_uuid(),
  guide_id uuid not null references leveling_guides(id) on delete cascade,
  competency_id uuid not null references competencies(id) on delete cascade,
  level_id uuid not null references levels(id) on delete cascade,
  definition_text text null,
  source_artifact_id uuid null references guide_artifacts(id),
  created_at timestamp not null default now(),
  constraint uq_cells_competency_level unique (competency_id, level_id)
);

create index if not exists ix_cells_guide on guide_cells(guide_id);

create table if not exists cell_generations (
  id uuid primary key default gen_random_uuid(),
  guide_id uuid not null references leveling_guides(id) on delete cascade,
  cell_id uuid not null references guide_cells(id) on delete cascade,
  prompt_name varchar(64) not null default 'generate_examples',
  prompt_version varchar(32) not null default 'v1',
  status varchar(16) not null default 'SUCCESS',
  model varchar(128) null,
  trace_id varchar(64) null,
  content_json jsonb null,
  error_message text null,
  created_at timestamp not null default now(),
  constraint uq_cellgen_cell_prompt_ver unique (cell_id, prompt_name, prompt_version)
);

create index if not exists ix_cellgen_guide on cell_generations(guide_id);
create index if not exists ix_cellgen_cell on cell_generations(cell_id);
```

### Run the backend API

From repo root (where `app/` exists):

```bash
uvicorn app.main:app --reload --port 8000
```

### Run the Celery worker (required for async pipeline)

In another terminal:

```bash
celery -A app.celery_app.celery_app worker -l info \
  -Q extract_q,parse_q,generate_q
```

> Redis must be running for Celery (`REDIS_BROKER_URL`).

---

## 2) Frontend setup (Next.js)

### Frontend env (example)

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

Frontend stores the token and sends it on API calls:
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

  * returns the fully rendered matrix (levels, competencies, definitions, examples)

---

# Why this is “efficient” (tradeoffs + judgment)

### Fast perceived performance

* Upload endpoint responds immediately after storing the PDF + metadata
* All heavy work runs in Celery
* Polling is simple, reliable, and frontend-friendly

### Reliable execution

Celery worker is configured for **at-least-once** semantics:

* `acks_late = True`
* `worker_prefetch_multiplier = 1`
* `task_reject_on_worker_lost = True`

### Structured outputs, not blobs

We store:

* extracted artifacts
* matrix structure
* per-cell generations keyed by prompt version

This makes future features straightforward:

* email generation
* “show diffs between v1 and v2 prompts”
* search/filter analytics by company/role/competency/level

### Security baseline (prototype-appropriate)

* PDFs are stored in **private** storage
* Backend generates **signed URLs** for access (`/api/guides/:id/pdf`)
* Token auth protects all `/api/guides/*` routes
* CORS is explicitly configured

---

# Troubleshooting

### “Upload works but status never changes”

* Celery worker isn’t running or Redis is misconfigured
* Check:

  * `REDIS_BROKER_URL`
  * `celery worker` logs

### “DB errors”

* `DATABASE_URL` wrong or tables not created
* Ensure Supabase IP/credentials allow access
* Run the SQL bootstrap above

### “Gemini errors”

* Missing/invalid `GEMINI_API_KEY`
* Set `GEMINI_MODEL` to a valid deployed model for your account

---

# If I had more time (1–4 sentences)

I’d add migrations (Alembic) + a proper auth model (multi-user sessions), implement background job observability (task traces + retries surfaced in UI), add evaluation harnesses for LLM outputs (schema checks + rubric scoring), and containerize with Docker Compose for one-command local setup and easy deployment.
::contentReference[oaicite:0]{index=0}
```
