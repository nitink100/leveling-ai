# app/routers/llm_health.py
from fastapi import APIRouter
from app.llm.client import llm_generate

router = APIRouter(prefix="/api/llm", tags=["llm"])

@router.get("/health")
def llm_health():
    resp = llm_generate(
        purpose="healthcheck",
        prompt_name="generate_examples",
        prompt_version="v1",
        variables={
            "company_context": "Acme builds SaaS tools for finance teams.",
            "role": "Full Stack Engineer",
            "competency": "Execution",
            "level": "Mid",
            "cell_text": "Delivers features end-to-end with high quality.",
        },
    )
    return {"ok": True, "sample": resp.output_text[:200]}
