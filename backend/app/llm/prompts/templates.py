# app/llm/prompts/templates.py

PARSE_MATRIX_V1 = """
You are extracting a leveling guide matrix from text.
Return STRICT JSON only.

Rules:
- If you cannot confidently extract, set "confidence" < 0.6 and explain in "notes".
- Do not hallucinate missing rows/columns.
- Keep labels exactly as in the text.

Return JSON with shape:
{
  "confidence": 0.0-1.0,
  "role": "string|null",
  "levels": ["string", ...],
  "competencies": [
    {
      "name": "string",
      "cells": {
        "<level>": "string"
      }
    }
  ],
  "notes": "string"
}

TEXT:
{{text}}

{{__REPAIR_INSTRUCTIONS__}}
""".strip()


GENERATE_EXAMPLES_V1 = """
You are generating specific examples for a leveling guide cell.

Company context:
{{company_context}}

Role:
{{role}}

Competency:
{{competency}}

Level:
{{level}}

Cell expectation text:
{{cell_text}}

Return STRICT JSON only:
{
  "examples": [
    {"title": "string", "example": "string"},
    {"title": "string", "example": "string"},
    {"title": "string", "example": "string"}
  ]
}

Constraints:
- Make examples concrete and realistic.
- Avoid confidential / sensitive / illegal instructions.
- Keep each example 2-4 sentences.

{{__REPAIR_INSTRUCTIONS__}}
""".strip()


SMOKE_TEST_V1 = """
Return exactly this JSON:
{"ok": true}

{{__REPAIR_INSTRUCTIONS__}}
""".strip()
