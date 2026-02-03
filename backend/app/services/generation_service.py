# app/services/generation_service.py
import json
import re
import uuid
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.constants.statuses import GuideStatus
from app.core import AppError, ErrorCode, ErrorReason
from app.core.config import settings

from app.llm.client import llm_generate_structured
from app.models.leveling_guide import LevelingGuide
from app.models.level import Level
from app.models.competency import Competency
from app.models.guide_cell import GuideCell

from app.repos.leveling_guide.write import LevelingGuideWriteRepo
from app.repos.leveling_guide.read import LevelingGuideReadRepo
from app.repos.generation.write import GenerationWriteRepo
from app.repos.generation.read import GenerationReadRepo
from app.schemas.generation_schema import GenerateExamplesBatchResult
from app.celery_app import celery_app

PROMPT_NAME = "generate_examples_batch"


class GenerationService:
    def __init__(self, db: Session):
        self.db = db
        self.guide_write = LevelingGuideWriteRepo(db)
        self.guide_read = LevelingGuideReadRepo(db)
        self.gen_write = GenerationWriteRepo(db)
        self.gen_read = GenerationReadRepo(db)

    # ----------------------------
    # Context helpers
    # ----------------------------
    def _base_context(self, guide: LevelingGuide) -> str:
        parts: list[str] = []

        if guide.company and guide.company.name:
            parts.append(f"Company name: {guide.company.name.strip()}")

        if guide.company and guide.company.website_url:
            parts.append(f"Company website URL: {guide.company.website_url.strip()}")

        if guide.role_title:
            parts.append(f"Role title: {guide.role_title.strip()}")

        parts.append(
            "Important: Do not guess company domain/products/technology stack from the URL. "
            "If company context is missing, keep examples generic and grounded only in the leveling guide cell text."
        )
        return "\n".join([p for p in parts if p]).strip()

    def _chunk_ranges(self, n: int, chunk_size: int) -> List[Tuple[int, int]]:
        out: List[Tuple[int, int]] = []
        i = 0
        while i < n:
            j = min(i + chunk_size, n)
            out.append((i, j))
            i = j
        return out

    # ----------------------------
    # Validation / guardrails
    # ----------------------------
    def _normalize_text(self, s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip()).lower()

    def _count_sentences(self, s: str) -> int:
        parts = [p for p in re.split(r"[.!?]+", (s or "").strip()) if p.strip()]
        return len(parts)

    def _build_allowed_corpus(self, base_context: str, items: list[dict]) -> str:
        texts: list[str] = [base_context]
        for it in items:
            texts.append(it.get("competency", "") or "")
            texts.append(it.get("cell_text", "") or "")
        return "\n".join(texts)

    def _find_forbidden_terms(self, text: str, allowed_corpus: str) -> list[str]:
        deny = [
            "redis", "redis cloud",
            "kafka", "kubernetes", "docker",
            "aws", "gcp", "azure",
            "spark", "datadog", "opentelemetry",
            "terraform", "helm",
            "postgres", "mysql", "mongodb",
            "grpc", "protobuf",
            "vault",
        ]
        allowed_lower = (allowed_corpus or "").lower()
        out_lower = (text or "").lower()
        hits: list[str] = []
        for term in deny:
            if term in out_lower and term not in allowed_lower:
                hits.append(term)
        return hits

    def _validate_batch_result(
        self,
        result: GenerateExamplesBatchResult,
        items: list[dict],
        base_context: str,
    ) -> tuple[bool, str | None]:
        if not result or not getattr(result, "results", None):
            return False, "Missing results in LLM output"

        if len(result.results) != len(items):
            return False, f"Expected {len(items)} results, got {len(result.results)}"

        expected_competencies = [it.get("competency") for it in items]
        got_competencies = [r.competency for r in result.results]

        missing = [c for c in expected_competencies if c and c not in got_competencies]
        if missing:
            return False, f"Missing competencies in output: {missing}"

        allowed_corpus = self._build_allowed_corpus(base_context, items)

        for r in result.results:
            if not r.competency:
                return False, "Missing competency name in output"
            if not r.examples or len(r.examples) != 3:
                return False, f"Competency '{r.competency}' must have exactly 3 examples"

            norm_examples: list[str] = []
            for ex in r.examples:
                title = (ex.title or "").strip()
                body = (ex.example or "").strip()

                if not title or not body:
                    return False, f"Empty title/example in competency '{r.competency}'"

                sc = self._count_sentences(body)
                if sc < 2 or sc > 5:
                    return False, f"Example length out of range (2-4 sentences) in '{r.competency}'"

                forbidden = self._find_forbidden_terms(f"{title} {body}", allowed_corpus)
                if forbidden:
                    return False, f"Forbidden terms not present in inputs: {forbidden}"

                norm_examples.append(self._normalize_text(body))

            if len(set(norm_examples)) != 3:
                return False, f"Duplicate/near-duplicate examples in competency '{r.competency}'"

        return True, None

    def _repair_instructions_for_batch(self) -> str:
        return (
            "Return STRICT JSON only. "
            "Ensure results contains exactly one entry per input competency. "
            "For each competency, return exactly 3 examples with non-empty title/example. "
            "Do NOT include any company/product/technology terms unless they appear verbatim in Base context or cell_text. "
            "Keep each example 2-4 sentences. Escape all quotes/newlines properly."
        )

    # ----------------------------
    # Phase-4 entry
    # ----------------------------
    def start_phase4(self, guide_id: str, *, prompt_version: str = "v1", chunk_size: int = 6) -> dict:
        gid = uuid.UUID(guide_id)
        guide = self.db.query(LevelingGuide).filter(LevelingGuide.id == gid).first()
        if not guide:
            raise AppError(
                code=ErrorCode.NOT_FOUND,
                reason=str(ErrorReason.RESOURCE_NOT_FOUND),
                message="Guide not found",
                status_code=404,
            )

        # terminal already done
        if guide.status == GuideStatus.DONE.value:
            return {"ok": True, "guide_id": guide_id, "status": guide.status}

        # IMPORTANT: avoid double-enqueue if kickoff task retries while already generating
        if guide.status == GuideStatus.GENERATING_EXAMPLES.value:
            return {"ok": True, "guide_id": guide_id, "status": guide.status, "tasks_enqueued": 0}

        if guide.status != GuideStatus.MATRIX_PARSED.value:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                reason=str(ErrorReason.INVALID_INPUT),
                message=f"Guide not ready for Phase-4 (current={guide.status})",
                status_code=409,
            )

        # claim MATRIX_PARSED -> GENERATING_EXAMPLES
        claimed = self.guide_write.claim_status(
            gid,
            from_status=GuideStatus.MATRIX_PARSED.value,
            to_status=GuideStatus.GENERATING_EXAMPLES.value,
        )
        if not claimed:
            self.db.rollback()
            # someone else claimed; treat as already in progress
            refreshed = self.db.query(LevelingGuide).filter(LevelingGuide.id == gid).first()
            return {"ok": True, "guide_id": guide_id, "status": (refreshed.status if refreshed else guide.status)}

        self.db.commit()

        # load ordered levels + competencies
        levels = (
            self.db.query(Level)
            .filter(Level.guide_id == gid)
            .order_by(Level.position.asc())
            .all()
        )
        comps = (
            self.db.query(Competency)
            .filter(Competency.guide_id == gid)
            .order_by(Competency.position.asc())
            .all()
        )

        if not levels or not comps:
            raise AppError(
                code=ErrorCode.NOT_FOUND,
                reason=str(ErrorReason.RESOURCE_NOT_FOUND),
                message="Missing levels/competencies; run Phase-3 first",
                status_code=404,
            )

        effective_chunk_size = chunk_size if len(comps) > 8 else len(comps)
        ranges = self._chunk_ranges(len(comps), effective_chunk_size)

        enqueued = 0
        for lvl in levels:
            for (a, b) in ranges:
                celery_app.send_task(
                    "app.tasks.guide_pipeline.generate_cells_task",
                    args=[str(gid), str(lvl.id), a, b, prompt_version],
                )
                enqueued += 1

        # Enqueue finalize after a small delay. (No imports, no circular deps)
        celery_app.send_task(
            "app.tasks.guide_pipeline.finalize_generation_task",
            args=[str(gid), prompt_version],
            countdown=30,
        )

        return {
            "ok": True,
            "guide_id": str(gid),
            "status": GuideStatus.GENERATING_EXAMPLES.value,
            "tasks_enqueued": enqueued,
            "levels": len(levels),
            "competencies": len(comps),
            "chunk_size": effective_chunk_size,
        }

    # ----------------------------
    # Worker unit
    # ----------------------------
    def generate_level_chunk(
        self,
        guide_id: str,
        level_id: str,
        start: int,
        end: int,
        *,
        prompt_version: str = "v1",
    ) -> dict:
        gid = uuid.UUID(guide_id)
        lid = uuid.UUID(level_id)

        guide = self.db.query(LevelingGuide).filter(LevelingGuide.id == gid).first()
        if not guide:
            raise AppError(
                code=ErrorCode.NOT_FOUND,
                reason=str(ErrorReason.RESOURCE_NOT_FOUND),
                message="Guide not found",
                status_code=404,
            )

        if guide.status not in {GuideStatus.GENERATING_EXAMPLES.value, GuideStatus.DONE.value}:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                reason=str(ErrorReason.INVALID_INPUT),
                message=f"Guide not in GENERATING_EXAMPLES/DONE (current={guide.status})",
                status_code=409,
            )

        level = self.db.query(Level).filter(Level.id == lid, Level.guide_id == gid).first()
        if not level:
            raise AppError(
                code=ErrorCode.NOT_FOUND,
                reason=str(ErrorReason.RESOURCE_NOT_FOUND),
                message="Level not found",
                status_code=404,
            )

        comps = (
            self.db.query(Competency)
            .filter(Competency.guide_id == gid)
            .order_by(Competency.position.asc())
            .all()
        )
        chunk = comps[start:end]
        if not chunk:
            return {"ok": True, "skipped": True, "reason": "empty_chunk"}

        cells = (
            self.db.query(GuideCell)
            .filter(
                GuideCell.guide_id == gid,
                GuideCell.level_id == lid,
                GuideCell.competency_id.in_([c.id for c in chunk]),
            )
            .all()
        )
        cell_by_comp = {c.competency_id: c for c in cells}

        items: list[dict] = []
        wanted: list[tuple[Competency, GuideCell]] = []

        for comp in chunk:
            cell = cell_by_comp.get(comp.id)
            if not cell:
                continue

            existing = self.gen_read.get_cell_generation(
                cell_id=cell.id,
                prompt_name=PROMPT_NAME,
                prompt_version=prompt_version,
            )
            if existing and existing.status == "SUCCESS":
                continue

            items.append({"competency": comp.name, "cell_text": (cell.definition_text or "").strip()})
            wanted.append((comp, cell))

        if not items:
            return {"ok": True, "skipped": True, "reason": "already_done"}

        base_context = self._base_context(guide)
        role = (guide.role_title or "Unknown").strip()
        level_label = (level.code or "").strip()

        variables = {
            "base_context": base_context,
            "role": role,
            "level": level_label,
            "items_json": json.dumps(items, ensure_ascii=False),
        }

        result = llm_generate_structured(
            purpose="generate_examples_batch",
            prompt_name=PROMPT_NAME,
            prompt_version=prompt_version,
            variables=variables,
            schema=GenerateExamplesBatchResult,
        )

        ok, err = self._validate_batch_result(result, items, base_context)
        if not ok:
            variables2 = dict(variables)
            variables2["__REPAIR_INSTRUCTIONS__"] = self._repair_instructions_for_batch()

            result2 = llm_generate_structured(
                purpose="generate_examples_batch",
                prompt_name=PROMPT_NAME,
                prompt_version=prompt_version,
                variables=variables2,
                schema=GenerateExamplesBatchResult,
            )

            ok2, err2 = self._validate_batch_result(result2, items, base_context)
            if ok2:
                result = result2
            else:
                # persist FAILED for this chunk
                try:
                    for comp, cell in wanted:
                        self.gen_write.upsert_cell_generation(
                            guide_id=gid,
                            cell_id=cell.id,
                            prompt_name=PROMPT_NAME,
                            prompt_version=prompt_version,
                            status="FAILED",
                            content_json=None,
                            model=getattr(settings, "GEMINI_MODEL", None),
                            trace_id=None,
                            error_message=f"LLM validation failed: {err2 or err}",
                        )
                    self.db.commit()
                except Exception:
                    self.db.rollback()

                # bubble error so Celery can retry if you want
                raise AppError(
                    code=ErrorCode.INTERNAL_ERROR,
                    reason=str(ErrorReason.INTERNAL_ERROR),
                    message=f"LLM output validation failed: {err2 or err}",
                    status_code=500,
                )

        # persist atomically
        try:
            out_map = {r.competency: r for r in result.results}

            written = 0
            for comp, cell in wanted:
                r = out_map.get(comp.name)
                if not r:
                    self.gen_write.upsert_cell_generation(
                        guide_id=gid,
                        cell_id=cell.id,
                        prompt_name=PROMPT_NAME,
                        prompt_version=prompt_version,
                        status="FAILED",
                        content_json=None,
                        model=getattr(settings, "GEMINI_MODEL", None),
                        trace_id=None,
                        error_message="Missing competency in LLM output",
                    )
                    written += 1
                    continue

                payload = {"examples": [e.model_dump() for e in r.examples]}
                self.gen_write.upsert_cell_generation(
                    guide_id=gid,
                    cell_id=cell.id,
                    prompt_name=PROMPT_NAME,
                    prompt_version=prompt_version,
                    status="SUCCESS",
                    content_json=payload,
                    model=getattr(settings, "GEMINI_MODEL", None),
                    trace_id=None,
                    error_message=None,
                )
                written += 1

            self.db.commit()
            return {"ok": True, "guide_id": guide_id, "level_id": level_id, "start": start, "end": end, "written": written}

        except Exception:
            self.db.rollback()
            raise

    # ----------------------------
    # Finalize Phase-4
    # ----------------------------
    def finalize_phase4(self, guide_id: str, *, prompt_version: str = "v1") -> dict:
        gid = uuid.UUID(guide_id)

        guide = self.db.query(LevelingGuide).filter(LevelingGuide.id == gid).first()
        if not guide:
            raise AppError(
                code=ErrorCode.NOT_FOUND,
                reason=str(ErrorReason.RESOURCE_NOT_FOUND),
                message="Guide not found",
                status_code=404,
            )

        # terminal fast-return
        if guide.status in {
            GuideStatus.DONE.value,
            GuideStatus.FAILED_GENERATION.value,
            GuideStatus.FAILED_PARSE.value,
            GuideStatus.FAILED_BAD_PDF.value,
        }:
            return {"ok": True, "guide_id": guide_id, "status": guide.status}

        total_cells = int(
            self.db.query(GuideCell)
            .filter(GuideCell.guide_id == gid)
            .count()
        )

        total_rows = int(
            self.gen_read.count_total_for_guide(
                guide_id=gid,
                prompt_name=PROMPT_NAME,
                prompt_version=prompt_version,
            )
        )

        success = int(
            self.gen_read.count_success_for_guide(
                guide_id=gid,
                prompt_name=PROMPT_NAME,
                prompt_version=prompt_version,
            )
        )

        failed = max(0, total_rows - success)

        # Mark terminal when outcomes exist for all cells (SUCCESS or FAILED)
        if total_cells > 0 and total_rows >= total_cells:
            final_status = GuideStatus.FAILED_GENERATION.value if failed > 0 else GuideStatus.DONE.value
            self.guide_write.update_status(gid, final_status, error_message=None)
            self.db.commit()
            return {
                "ok": True,
                "guide_id": guide_id,
                "status": final_status,
                "success": success,
                "failed": failed,
                "total": total_cells,
            }

        return {
            "ok": True,
            "guide_id": guide_id,
            "status": guide.status,
            "success": success,
            "failed": failed,
            "total": total_cells,
        }

    # ----------------------------
    # Results API helper
    # ----------------------------
    def get_results(self, guide_id: str, *, prompt_version: str = "v1") -> dict:
        gid = uuid.UUID(guide_id)

        guide = self.db.query(LevelingGuide).filter(LevelingGuide.id == gid).first()
        if not guide:
            raise AppError(
                code=ErrorCode.NOT_FOUND,
                reason=str(ErrorReason.RESOURCE_NOT_FOUND),
                message="Guide not found",
                status_code=404,
            )

        levels = (
            self.db.query(Level)
            .filter(Level.guide_id == gid)
            .order_by(Level.position.asc())
            .all()
        )
        comps = (
            self.db.query(Competency)
            .filter(Competency.guide_id == gid)
            .order_by(Competency.position.asc())
            .all()
        )
        cells = self.db.query(GuideCell).filter(GuideCell.guide_id == gid).all()

        gens = self.gen_read.list_generations_for_guide(
            guide_id=gid,
            prompt_name=PROMPT_NAME,
            prompt_version=prompt_version,
        )

        gen_by_cell: dict[str, dict] = {}
        for g in gens:
            gen_by_cell[str(g.cell_id)] = {"status": g.status, "payload": g.content_json}

        cell_map: dict[tuple[str, str], GuideCell] = {}
        for c in cells:
            cell_map[(str(c.competency_id), str(c.level_id))] = c

        out_levels = [{"id": str(l.id), "label": l.code, "position": l.position} for l in levels]
        out_comps: list[dict] = []

        for comp in comps:
            row = {"id": str(comp.id), "name": comp.name, "position": comp.position, "cells": []}
            for lvl in levels:
                cell = cell_map.get((str(comp.id), str(lvl.id)))
                if not cell:
                    row["cells"].append(
                        {
                            "level_id": str(lvl.id),
                            "cell_id": None,
                            "definition_text": None,
                            "examples": [],
                            "generation_status": "MISSING_CELL",
                        }
                    )
                    continue

                g = gen_by_cell.get(str(cell.id)) or {}
                status = g.get("status") or "PENDING"
                payload = g.get("payload") or {}
                examples = (payload.get("examples") or []) if isinstance(payload, dict) else []

                row["cells"].append(
                    {
                        "level_id": str(lvl.id),
                        "cell_id": str(cell.id),
                        "definition_text": cell.definition_text,
                        "examples": examples,
                        "generation_status": status if status else ("SUCCESS" if examples else "PENDING"),
                    }
                )
            out_comps.append(row)

        expected = len(levels) * len(comps)
        completed = self.gen_read.count_success_for_guide(
            guide_id=gid,
            prompt_name=PROMPT_NAME,
            prompt_version=prompt_version,
        )

        return {
            "ok": True,
            "guide_id": str(gid),
            "status": guide.status,
            "prompt_version": prompt_version,
            "progress": {"expected": expected, "completed": completed},
            "levels": out_levels,
            "competencies": out_comps,
        }
