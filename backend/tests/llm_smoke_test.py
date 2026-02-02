from app.llm.client import llm_generate

resp = llm_generate(
    purpose="smoke_test",
    prompt_name="parse_matrix",
    prompt_version="v1",
    variables={"text": "Return JSON {\"ok\": true}"},
    response_mime_type="application/json",
)
print(resp.output_text)
