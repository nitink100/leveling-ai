import io
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_upload_creates_queued_guide(client, monkeypatch):
    # Mock storage upload so no external dependency
    from app.services.storage.supabase_storage import StoredObject

    def fake_upload_private_pdf(self, company_id, file):
        return StoredObject(bucket="test-bucket", path=f"companies/{company_id}/guides/{uuid.uuid4()}/sample.pdf")

    monkeypatch.setattr(
        "app.services.storage.supabase_storage.SupabaseStorage.upload_private_pdf",
        fake_upload_private_pdf,
    )

    pdf_bytes = b"%PDF-1.4\n%fake pdf\n"
    files = {"pdf": ("sample.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {"website_url": "https://example.com", "role_title": "Software Engineer"}

    resp = client.post("/api/guides", data=data, files=files)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["status"] == "QUEUED"
    assert "id" in body or "guide_id" in body  # depending on your schema
