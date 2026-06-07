"""Frontend history routes served by the FastAPI production host."""

from fastapi.testclient import TestClient

import src.app as app_module


def test_settings_route_serves_the_frontend_index(tmp_path, monkeypatch):
    index_path = tmp_path / "index.html"
    index_path.write_text("<html><body>planner shell</body></html>", encoding="utf-8")
    monkeypatch.setattr(app_module, "frontend_dist", tmp_path)

    response = TestClient(app_module.app).get("/settings")

    assert response.status_code == 200
    assert "planner shell" in response.text
