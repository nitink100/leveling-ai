from app.schemas.matrix_schema import ParsedMatrix

def parse_matrix_from_text_llm(text: str, llm_client) -> ParsedMatrix:
    """
    Phase-3 parser: Uses LLM to turn extracted PDF text into a structured matrix schema.
    llm_client is an injected dependency (keeps functional core clean).
    """
    # You likely already have something like:
    # llm_client.generate_structured(prompt=..., schema=ParsedMatrix)
    # Below is the intended call shape.
    return llm_client.generate_structured(
        prompt_key="PARSE_MATRIX_V1",
        input_text=text,
        schema=ParsedMatrix,
    )
