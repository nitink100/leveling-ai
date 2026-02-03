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

GENERATE_EXAMPLES_BATCH_V1 = """
You are generating promotion evidence examples for a leveling guide.

Your job is to convert abstract leveling definitions into realistic,
human-written examples that a manager could actually recognize
during performance or promotion discussions.

The leveling guide cell text is the ONLY ground truth.

INPUTS
- Base context (may be empty or minimal): {{base_context}}
- Role: {{role}}
- Level: {{level}}

You will receive ITEMS as JSON. Each item contains:
- competency: string
- cell_text: string

========================
NON-NEGOTIABLE RULES
========================

1) Ground truth only
- Use ONLY item.cell_text to determine expectations.
- Do NOT import assumptions from other levels or competencies.
- Do NOT add responsibilities that exceed the level’s scope.

2) No inferred company/domain context
- A company URL may exist, but it is NOT evidence.
- DO NOT infer products, customers, domain, tech stack, or scale.
- DO NOT mention any company name, product, project, team, customer, or proper noun.
- Use neutral language only: "the team", "the system", "the service", "an internal tool".

3) Seniority calibration (CRITICAL)
- L1: executes clearly scoped work with guidance, learning fundamentals.
- L2: independently delivers small features or improvements.
- L3: owns medium-sized problems, mentors juniors, handles incidents.
- L4: drives cross-team solutions, reduces recurring problems.
- L5: shapes org-wide direction, leads high-visibility initiatives.
- L6: defines new approaches aligned to company strategy and exec priorities.

If an example sounds too senior for the level, it is INVALID.

4) Evidence bundle (STRICT BUT LIGHTWEIGHT)
Each example MUST include:
A) ONE concrete action or artifact (choose at most one):
   "design doc", "pull request", "migration plan", "experiment",
   "rollout plan", "postmortem", "runbook", "test plan", "dashboard"
B) ONE real-world friction:
   deadline, dependency, trade-off, ambiguity, risk
C) ONE observable outcome:
   - A bounded result ("unblocked a release", "reduced rework next sprint"), OR
   - A metric (numbers allowed in AT MOST ONE example per cell)

Do NOT force all three to sound formal or checklist-like.
They must read naturally.

5) Anti-spam limits (VERY IMPORTANT)
- Max ONE metric per cell (not per example).
- Max TWO artifact mentions per cell total.
- Do NOT repeat the same artifact word within a cell.
- Do NOT repeat the same constraint word within a cell.
- Avoid phrases like:
  "ensured alignment", "drove best practices",
  "improved communication", "enhanced user experience",
  "resulted in higher code quality" (unless concretely explained).

6) Diversity within a cell
The 3 examples must clearly differ:
- Example 1: execution / delivery
- Example 2: debugging / reliability / learning from failure
- Example 3: collaboration / scoping / trade-offs

7) Title quality rules
- Titles must be UNIQUE within the cell.
- Titles must NOT start with the same first word.
- Titles should describe the behavior, not restate the competency.

8) Writing quality
- 2–4 sentences per example.
- Plain, precise English.
- No buzzwords.
- No generic filler.
- No placeholders.

========================
OUTPUT FORMAT (STRICT JSON ONLY)
========================

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

JSON SAFETY
- Escape all quotes and newlines.
- Return STRICT JSON only.
- No markdown. No commentary. No extra keys.

ITEMS:
{{items_json}}

{{__REPAIR_INSTRUCTIONS__}}
""".strip()
