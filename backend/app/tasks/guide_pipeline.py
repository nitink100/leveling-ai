from __future__ import annotations

import logging

from app.celery_app import celery_app
from app.constants.statuses import GuideStatus
from app.core import AppError
from app.core.request_context import clear_context, set_context
from app.db.session import SessionLocal
from app.services.storage.supabase_storage import SupabaseStorage

logger = logging.getLogger("app.tasks.guide_pipeline")


@celery_app.task(
    name="app.tasks.guide_pipeline.extract_text_task",
    bind=True,
    max_retries=5,
    default_retry_delay=15,
)
def extract_text_task(self, guide_id: str):
    """
    Phase-2 driver:
      QUEUED -> EXTRACTING_TEXT -> TEXT_EXTRACTED | FAILED_BAD_PDF
    Then chains parse_matrix_task if TEXT_EXTRACTED.
    """
    set_context(task_id=getattr(self.request, "id", None), guide_id=guide_id)
    from app.services.guide_service import GuideService

    db = SessionLocal()
    try:
        logger.info("task.start", extra={"task": "extract_text_task"})
        svc = GuideService(db=db, storage=SupabaseStorage())

        # extract_pdf_text sets status internally + commits
        svc.extract_pdf_text(guide_id)

        guide = svc.get_status(guide_id)
        if not guide:
            logger.warning("guide.not_found", extra={"task": "extract_text_task"})
            return {"ok": False, "guide_id": guide_id, "error": "Guide not found"}

        status = str(guide.status)
        logger.info("guide.status", extra={"task": "extract_text_task", "status": status})

        if status == GuideStatus.TEXT_EXTRACTED.value:
            parse_matrix_task.delay(guide_id)
            logger.info("task.chain", extra={"from": "extract_text_task", "to": "parse_matrix_task"})
            return {"ok": True, "guide_id": guide_id, "status": status, "chained": "parse_matrix_task"}

        return {"ok": True, "guide_id": guide_id, "status": status, "chained": None}

    except AppError as e:
        logger.warning("task.app_error", extra={"task": "extract_text_task", "error": str(e)})
        return {"ok": False, "guide_id": guide_id, "error": str(e)}
    except Exception as e:
        logger.exception("task.retry", extra={"task": "extract_text_task"})
        raise self.retry(exc=e)
    finally:
        db.close()
        clear_context()


@celery_app.task(
    name="app.tasks.guide_pipeline.parse_matrix_task",
    bind=True,
    max_retries=5,
    default_retry_delay=15,
)
def parse_matrix_task(self, guide_id: str):
    """
    Phase-3 driver:
      TEXT_EXTRACTED -> PARSING_MATRIX -> MATRIX_PARSED | FAILED_PARSE
    Then chains kickoff_generation_task if MATRIX_PARSED.
    """
    set_context(task_id=getattr(self.request, "id", None), guide_id=guide_id)
    from app.services.guide_service import GuideService

    db = SessionLocal()
    try:
        logger.info("task.start", extra={"task": "parse_matrix_task"})
        svc = GuideService(db=db, storage=SupabaseStorage())

        svc.parse_matrix(guide_id)

        guide = svc.get_status(guide_id)
        if not guide:
            logger.warning("guide.not_found", extra={"task": "parse_matrix_task"})
            return {"ok": False, "guide_id": guide_id, "error": "Guide not found"}

        status = str(guide.status)
        logger.info("guide.status", extra={"task": "parse_matrix_task", "status": status})

        if status == GuideStatus.MATRIX_PARSED.value:
            kickoff_generation_task.delay(guide_id)
            logger.info("task.chain", extra={"from": "parse_matrix_task", "to": "kickoff_generation_task"})
            return {"ok": True, "guide_id": guide_id, "status": status, "chained": "kickoff_generation_task"}

        return {"ok": True, "guide_id": guide_id, "status": status, "chained": None}

    except AppError as e:
        logger.warning("task.app_error", extra={"task": "parse_matrix_task", "error": str(e)})
        return {"ok": False, "guide_id": guide_id, "error": str(e)}
    except Exception as e:
        logger.exception("task.retry", extra={"task": "parse_matrix_task"})
        raise self.retry(exc=e)
    finally:
        db.close()
        clear_context()


@celery_app.task(
    name="app.tasks.guide_pipeline.kickoff_generation_task",
    bind=True,
    max_retries=3,
    default_retry_delay=20,
)
def kickoff_generation_task(self, guide_id: str, prompt_version: str = "v1"):
    """
    Phase-4 kickoff:
      MATRIX_PARSED -> GENERATING_EXAMPLES
    Enqueues chunk tasks + finalize poller.
    """
    from app.services.generation_service import GenerationService
    from app.services.guide_service import GuideService

    set_context(task_id=getattr(self.request, "id", None), guide_id=guide_id)

    db = SessionLocal()
    try:
        logger.info("task.start", extra={"task": "kickoff_generation_task", "prompt_version": prompt_version})
        svc = GenerationService(db=db)
        out = svc.start_phase4(guide_id, prompt_version=prompt_version)
        logger.info("task.done", extra={"task": "kickoff_generation_task", "status": out.get("status")})
        return out
    except AppError as e:
        logger.warning("task.app_error", extra={"task": "kickoff_generation_task", "error": str(e)})
        return {"ok": False, "guide_id": guide_id, "error": str(e)}
    except Exception as e:
        logger.exception("task.retry", extra={"task": "kickoff_generation_task"})
        raise self.retry(exc=e)
    finally:
        db.close()
        clear_context()


@celery_app.task(
    name="app.tasks.guide_pipeline.generate_cells_task",
    bind=True,
    max_retries=3,
    default_retry_delay=15,
)
def generate_cells_task(
    self,
    guide_id: str,
    level_id: str,
    start: int,
    end: int,
    prompt_version: str = "v1",
):
    from app.services.generation_service import GenerationService
    from app.services.guide_service import GuideService

    set_context(task_id=getattr(self.request, "id", None), guide_id=guide_id)

    db = SessionLocal()
    try:
        logger.info(
            "task.start",
            extra={
                "task": "generate_cells_task",
                "level_id": level_id,
                "start": start,
                "end": end,
                "prompt_version": prompt_version,
            },
        )
        svc = GenerationService(db=db)
        res = svc.generate_level_chunk(guide_id, level_id, start, end, prompt_version=prompt_version)
        logger.info("task.done", extra={"task": "generate_cells_task", "written": res.get("written")})
        return res
    except AppError as e:
        logger.warning("task.app_error", extra={"task": "generate_cells_task", "error": str(e), "level_id": level_id})
        return {"ok": False, "guide_id": guide_id, "level_id": level_id, "error": str(e)}
    except Exception as e:
        logger.exception("task.retry", extra={"task": "generate_cells_task", "level_id": level_id})
        raise self.retry(exc=e)
    finally:
        db.close()
        clear_context()


@celery_app.task(
    name="app.tasks.guide_pipeline.finalize_generation_task",
    bind=True,
    max_retries=240,
    default_retry_delay=30,
)
def finalize_generation_task(self, guide_id: str, prompt_version: str = "v1"):
    """
    Polls until generation finished:
      GENERATING_EXAMPLES -> DONE | FAILED_GENERATION
    """
    from app.services.generation_service import GenerationService
    from app.services.guide_service import GuideService

    set_context(task_id=getattr(self.request, "id", None), guide_id=guide_id)

    db = SessionLocal()
    try:
        logger.info("task.start", extra={"task": "finalize_generation_task", "prompt_version": prompt_version})
        svc = GenerationService(db=db)
        res = svc.finalize_phase4(guide_id, prompt_version=prompt_version)

        st = res.get("status")
        logger.info("guide.status", extra={"task": "finalize_generation_task", "status": st})

        if st in {GuideStatus.DONE.value, GuideStatus.FAILED_GENERATION.value}:
            logger.info("task.done", extra={"task": "finalize_generation_task", "status": st})
            return res

        raise self.retry(exc=Exception("Not done yet"))
    finally:
        db.close()
        clear_context()
