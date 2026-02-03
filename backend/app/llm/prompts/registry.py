# app/llm/prompts/registry.py

from dataclasses import dataclass
from typing import Callable

from app.llm.prompts import templates

@dataclass(frozen=True)
class PromptTemplate:
    name: str
    version: str
    template: str

PROMPTS: dict[tuple[str, str], PromptTemplate] = {
    ("parse_matrix", "v1"): PromptTemplate("parse_matrix", "v1", templates.PARSE_MATRIX_V1),
    ("generate_examples", "v1"): PromptTemplate("generate_examples", "v1", templates.GENERATE_EXAMPLES_V2),
    ("generate_examples_batch", "v1"): PromptTemplate("generate_examples_batch", "v1", templates.GENERATE_EXAMPLES_BATCH_V2),

}

def get_prompt(name: str, version: str) -> PromptTemplate:
    key = (name, version)
    if key not in PROMPTS:
        raise KeyError(f"Unknown prompt: {name}@{version}")
    return PROMPTS[key]
