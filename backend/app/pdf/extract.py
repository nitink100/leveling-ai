"""app/pdf/extract.py

Deterministic PDF -> text extraction.

Preferred strategy:
1) PyMuPDF (fitz)
2) pdfplumber
3) pypdf (very basic)
"""



import io

from app.core import AppError, ErrorCode, ErrorReason
from app.pdf.types import ExtractedPDF


def extract_text_from_bytes(pdf_bytes: bytes) -> ExtractedPDF:
    if not pdf_bytes:
        raise AppError(
            code=ErrorCode.VALIDATION_ERROR,
            reason=ErrorReason.INVALID_INPUT,
            message="Empty PDF bytes",
            status_code=400,
        )

    # 1) PyMuPDF
    try:
        import fitz  # type: ignore

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_count = doc.page_count
        texts: list[str] = []
        pages_with_text = 0
        for i in range(page_count):
            page = doc.load_page(i)
            t = page.get_text("text") or ""
            if t.strip():
                pages_with_text += 1
            texts.append(t)
        doc.close()
        return ExtractedPDF(
            text="\n\n".join(texts),
            page_count=page_count,
            pages_with_text=pages_with_text,
            strategy="pymupdf",
        )
    except Exception:
        pass

    # 2) pdfplumber
    try:
        import pdfplumber  # type: ignore

        texts = []
        pages_with_text = 0
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            page_count = len(pdf.pages)
            for p in pdf.pages:
                t = p.extract_text() or ""
                if t.strip():
                    pages_with_text += 1
                texts.append(t)
        return ExtractedPDF(
            text="\n\n".join(texts),
            page_count=page_count,
            pages_with_text=pages_with_text,
            strategy="pdfplumber",
        )
    except Exception:
        pass

    # 3) pypdf (weak fallback)
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(pdf_bytes))
        page_count = len(reader.pages)
        texts: list[str] = []
        pages_with_text = 0
        for p in reader.pages:
            t = (p.extract_text() or "")
            if t.strip():
                pages_with_text += 1
            texts.append(t)
        return ExtractedPDF(
            text="\n\n".join(texts),
            page_count=page_count,
            pages_with_text=pages_with_text,
            strategy="pypdf",
        )
    except Exception as e:
        raise AppError(
            code=ErrorCode.CONFIG_ERROR,
            reason=ErrorReason.MISSING_DEPENDENCY,
            message="No PDF extraction backend available. Install PyMuPDF (fitz) or pdfplumber.",
            status_code=500,
        ) from e
