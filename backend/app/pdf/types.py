"""app/pdf/types.py

Lightweight dataclasses for PDF extraction + quality scoring outputs.
Design goals:
- deterministic extraction (no LLM)
- cheap, explainable confidence score + flags
"""


from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedPDF:
    text: str
    page_count: int
    pages_with_text: int
    strategy: str  # "pymupdf" | "pdfplumber" | "pypdf"


@dataclass(frozen=True)
class QualityReport:
    confidence: float  # 0.0 - 1.0
    char_count: int
    word_count: int
    line_count: int
    printable_ratio: float
    has_matrix_signals: bool
    has_table_signals: bool
    is_scanned_likely: bool
    is_garbled_likely: bool
    notes: list[str]


@dataclass(frozen=True)
class ExtractionResult:
    extracted: ExtractedPDF
    quality: QualityReport
