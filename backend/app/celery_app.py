# app/celery_app.py
import os
from celery import Celery
from dotenv import load_dotenv

from app.core.logging_config import configure_logging

load_dotenv()

# Ensure logging is configured in worker processes as early as possible.
configure_logging()

BROKER_URL = os.environ["REDIS_BROKER_URL"]
BACKEND_URL = os.environ.get("CELERY_RESULT_BACKEND", BROKER_URL)

celery_app = Celery(
    "guide_pipeline",
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=["app.tasks.guide_pipeline"],
)

# reliability defaults (important for at-least-once)
celery_app.conf.task_acks_late = True
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_reject_on_worker_lost = True

# prevent Celery from overriding our root logger
celery_app.conf.worker_hijack_root_logger = False

# routing queues per phase (optional but recommended)
celery_app.conf.task_routes = {
    "app.tasks.guide_pipeline.extract_text_task": {"queue": "extract_q"},
    "app.tasks.guide_pipeline.parse_matrix_task": {"queue": "parse_q"},
    "app.tasks.guide_pipeline.kickoff_generation_task": {"queue": "generate_q"},
    "app.tasks.guide_pipeline.generate_cells_task": {"queue": "generate_q"},
    "app.tasks.guide_pipeline.finalize_generation_task": {"queue": "generate_q"},
}
