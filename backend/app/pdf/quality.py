"""app/pdf/quality.py

Cheap, explainable heuristics to score PDF text extraction quality.

We do NOT do OCR in Phase-2. If the PDF is likely scanned (no embedded text),
confidence is low and we flag it as bad.
"""



import re
import string

from app.pdf.types import QualityReport


_MATRIX_SIGNAL_PATTERNS = [
    r"\blevel\b",
    r"\bcompetenc(y|ies)\b",
    r"\bscope\b",
    r"\bexpectation(s)?\b",
    r"\bresponsibilit(y|ies)\b",
    r"\bbehavior(s)?\b",
]

_TABLE_SIGNAL_PATTERNS = [
    r"\btable\b",
    r"\brow\b",
    r"\bcolumn\b",
    r"\|",
]


def _printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    printable = set(string.printable)
    good = sum(1 for ch in text if ch in printable)
    return good / max(1, len(text))


def _has_any_pattern(text: str, patterns: list[str]) -> bool:
    t = (text or "").lower()
    for p in patterns:
        if re.search(p, t):
            return True
    return False


def score_extraction(text: str, page_count: int, pages_with_text: int) -> QualityReport:
    raw = text or ""
    char_count = len(raw)
    word_count = len(re.findall(r"\w+", raw))
    line_count = raw.count("\n") + (1 if raw else 0)
    printable_ratio = _printable_ratio(raw)

    has_matrix_signals = _has_any_pattern(raw, _MATRIX_SIGNAL_PATTERNS)
    has_table_signals = _has_any_pattern(raw, _TABLE_SIGNAL_PATTERNS)

    is_scanned_likely = pages_with_text == 0 or char_count < 200
    is_garbled_likely = (char_count > 0) and (printable_ratio < 0.85)

    notes: list[str] = []

    if char_count < 800 or pages_with_text == 0:
        confidence = 0.10
        if pages_with_text == 0:
            notes.append("No pages had extractable text")
        if char_count < 800:
            notes.append("Extracted text is very small")
    elif 800 <= char_count <= 2500:
        confidence = 0.40
        notes.append("Moderate text volume")
    else:
        confidence = 0.80
        notes.append("High text volume")

    if has_matrix_signals and char_count > 2500:
        confidence = min(0.95, confidence + 0.15)
        notes.append("Detected leveling/matrix signals")
    elif has_matrix_signals:
        confidence = min(0.85, confidence + 0.10)
        notes.append("Detected some matrix signals")

    if is_garbled_likely:
        confidence = max(0.05, confidence - 0.25)
        notes.append("Text looks garbled (low printable ratio)")

    if has_table_signals:
        confidence = min(0.95, confidence + 0.05)
        notes.append("Detected possible table signals")

    if is_scanned_likely:
        confidence = min(confidence, 0.10)
        notes.append("Looks like scanned/empty PDF (no embedded text)")

    return QualityReport(
        confidence=float(round(confidence, 3)),
        char_count=char_count,
        word_count=word_count,
        line_count=line_count,
        printable_ratio=float(round(printable_ratio, 3)),
        has_matrix_signals=has_matrix_signals,
        has_table_signals=has_table_signals,
        is_scanned_likely=is_scanned_likely,
        is_garbled_likely=is_garbled_likely,
        notes=notes,
    )
