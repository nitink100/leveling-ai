# app/llm/prompts/templates.py

PARSE_MATRIX_V1 = """
You are extracting a leveling guide matrix from text.
Return STRICT JSON only (no markdown).

Rules:
- IMPORTANT: All JSON string values must be valid JSON. Escape quotes and newlines.
- Do NOT include unescaped double quotes inside strings.
- Replace fancy quotes with normal quotes if needed.
- Keep each cell value concise (max 350 chars). If longer, summarize faithfully.
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
  "notes": "string|null"
}

TEXT:
{{text}}

{{__REPAIR_INSTRUCTIONS__}}
""".strip()


GENERATE_EXAMPLES_V1 = """
You are generating promotion evidence examples for a leveling guide cell.

INPUTS
- Company context (may be empty): {{company_context}}
- Role: {{role}}
- Level: {{level}}
- Competency: {{competency}}
- Level definition (ground truth): {{cell_text}}

HARD RULES (MUST FOLLOW)
1) Ground truth: Use ONLY the Level definition text as the source of expectations.
2) No hallucinated company/product/tech:
   - If company_context is empty or vague, DO NOT invent company name, products, domain, customers, or tech stack.
   - Only mention specific tools/tech/products if they appear in company_context OR in the level definition text.
3) Examples must be concrete and realistic for the role and level.
4) Diversity: The 3 examples must be meaningfully different:
   - (a) technical execution, (b) collaboration/process, (c) business/customer impact.
5) Output strict JSON only. No extra keys.

Return STRICT JSON only:
{
  "examples": [
    {"title": "string", "example": "string"},
    {"title": "string", "example": "string"},
    {"title": "string", "example": "string"}
  ]
}

Style constraints:
- 2–4 sentences per example.
- Plain English, no buzzwords.
- No confidential / sensitive / illegal instructions.

{{__REPAIR_INSTRUCTIONS__}}
""".strip()


GENERATE_EXAMPLES_BATCH_V1 = """
You are generating promotion evidence examples for a leveling guide.

The leveling guide cell text is the ONLY ground truth.
Do not invent company/product/domain/tech specifics.

INPUTS
- Base context (may be empty or minimal): {{base_context}}
- Role: {{role}}
- Level: {{level}}

You will receive a JSON list called ITEMS. Each item has:
- competency: string
- cell_text: string

HARD RULES (MUST FOLLOW)
1) Ground truth: Use ONLY each item.cell_text to decide what “good” looks like.
2) No hallucinated company/product/tech:
   - If base_context does not explicitly name a company/product/tech, do NOT introduce any company name or product.
   - Only mention tools/tech/products if they appear verbatim in base_context OR item.cell_text.
   - If unsure, stay generic.
3) Each item must produce exactly 3 examples.
4) Diversity: The 3 examples must be meaningfully different:
   - (a) technical execution, (b) collaboration/process, (c) business/customer impact.
5) JSON safety:
   - Escape all quotes/newlines correctly.
   - Return STRICT JSON only. No markdown. No extra keys.

Return STRICT JSON only:
{
  "level": "string",
  "results": [
    {
      "competency": "string",
      "examples": [
        {"title": "string", "example": "string"},
        {"title": "string", "example": "string"},
        {"title": "string", "example": "string"}
      ]
    }
  ]
}

ITEMS:
{{items_json}}

{{__REPAIR_INSTRUCTIONS__}}
""".strip()

GENERATE_EXAMPLES_V2 = """
You are generating promotion evidence examples for a leveling guide cell.

The goal is to help a manager and direct report clearly understand
what observable behaviors would demonstrate performance at this level.

INPUTS
- Company context (may be empty or minimal): {{company_context}}
- Role: {{role}}
- Level: {{level}}
- Competency: {{competency}}
- Level definition (ground truth): {{cell_text}}

NON-NEGOTIABLE RULES
1) Ground truth only:
   - Use ONLY the level definition text to determine expectations.
   - Do NOT add expectations not implied by the definition.

2) No hallucinated company or tech:
   - If company_context does not explicitly name a company, product, customer, or technology,
     DO NOT invent any.
   - You may reference generic artifacts (e.g. design doc, PR, experiment, rollout plan)
     that are role-agnostic and common across engineering roles.

3) Role sensitivity:
   - Examples must be plausible for the given role.
   - If the role is broad (e.g. "Software Engineer"), stay role-neutral.
   - Do NOT assume frontend/backend unless stated.

4) Evidence requirement (critical):
   Each example MUST include at least one concrete, checkable signal such as:
   - a deliverable (document, feature, system, migration, launch)
   - a constraint (ambiguity, timeline, trade-off, dependency)
   - an outcome (what changed, improved, or became easier for others)

5) Level differentiation:
   - Examples must reflect the scope implied by the level:
     junior → execution with guidance
     mid → independent delivery
     senior → ownership and mentoring
     staff+ → cross-team impact and strategy

6) Diversity:
   The 3 examples must differ in focus:
   - (a) execution / problem solving
   - (b) collaboration / process
   - (c) impact / leverage

OUTPUT FORMAT (STRICT JSON ONLY)
{
  "examples": [
    {"title": "string", "example": "string"},
    {"title": "string", "example": "string"},
    {"title": "string", "example": "string"}
  ]
}

STYLE CONSTRAINTS
- 2–4 sentences per example
- Plain English, no buzzwords
- Avoid phrases like "successfully", "effectively", "led" unless followed by specifics
- No confidential or sensitive content

{{__REPAIR_INSTRUCTIONS__}}
""".strip()

GENERATE_EXAMPLES_BATCH_V2 = """
You are generating promotion evidence examples for a leveling guide.

Your task is to turn abstract leveling definitions into concrete,
observable examples that a manager could realistically use in a promotion discussion.

The leveling guide text is the ONLY ground truth.

INPUTS
- Base context (may be empty or minimal): {{base_context}}
- Role: {{role}}
- Level: {{level}}

You will receive ITEMS as JSON. Each item contains:
- competency: string
- cell_text: string

NON-NEGOTIABLE RULES

1) Ground truth only:
   - Use ONLY item.cell_text to determine expectations.
   - Do NOT import assumptions from other levels or competencies.

2) No hallucinated company or technology:
   - If base_context does not explicitly name a company, product, domain, or technology,
     DO NOT invent any.
   - You may use role-agnostic engineering artifacts:
     (e.g. design docs, PRs, experiments, rollout plans, metrics, reviews).

3) Evidence anchors (mandatory):
   Each example MUST include at least one of:
   - a concrete deliverable or artifact
   - a real constraint or trade-off
   - a visible outcome or signal others could observe

4) Level-appropriate scope:
   - Junior levels focus on execution with guidance.
   - Mid levels focus on independent delivery.
   - Senior levels focus on ownership and mentoring.
   - Staff+ levels focus on cross-team leverage, strategy, or org impact.

5) Diversity within each competency:
   The 3 examples must differ meaningfully in focus:
   - execution
   - collaboration/process
   - impact or leverage

6) Anti-generic rule:
   - Do NOT restate the definition in different words.
   - Each example must add new, concrete detail.

OUTPUT FORMAT (STRICT JSON ONLY)
{
  "level": "string",
  "results": [
    {
      "competency": "string",
      "examples": [
        {"title": "string", "example": "string"},
        {"title": "string", "example": "string"},
        {"title": "string", "example": "string"}
      ]
    }
  ]
}

STYLE CONSTRAINTS
- 2–4 sentences per example
- Plain, precise English
- Avoid exaggerated metrics unless justified by context
- No markdown, no extra keys

ITEMS:
{{items_json}}

{{__REPAIR_INSTRUCTIONS__}}
""".strip()
